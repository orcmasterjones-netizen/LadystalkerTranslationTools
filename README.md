# Experimental Lady Stalker extraction and retranslation kit

CREDIT to RetchErezzed for the English MACHINE TRANSLATION patch for: Lady Stalker: Kako kara no Chousen Super Famicom / SNES
https://www.romhacking.net/translations/7687/

A spreadsheet comparing the machine translation to the Japanese text:
[https://docs.google.com/spreadsheets/d/1r9tgzWNMF61ixo1x2PMF-ePCaV6QFM3urqfz5nA3llY/edit?gid=510070301#gid=510070301](https://docs.google.com/spreadsheets/d/e/2PACX-1vR3Hmv2-kBZEsAhIZWb3zizjndKe45VVunL_t0f3R0WhbB6wQ3s8iXGLDNsmIHKj6cHKMqlC31Ouch7/pubhtml)

This package extracts the Japanese text from the headerless Super Famicom ROM
`Lady Stalker - Kako kara no Chousen (Japan).sfc`. It also analyzes the existing
ENG v1.0 machine-translation patch, pairs its English with the Japanese source,
and can compile edited workspaces into a text-only overlay IPS.

These tools should allow anybody to easily create a more human translation.  It is not thoroughly tested though, so use with caution and carefully check the resulting rom.  This was mostly an experiment to see how quickly it could be put together, so no guarantees.  Even the Japanese text rip should be double-checked. 

## Results

- 1,220 compressed message records
- 59,425 decoded 9-bit symbols, including formatting/control codes
- 352 byte-encoded entity and item names
- 6 word-encoded dynamic phrases
- 1,578 total text records
- Every valid compressed message reaches the game's `0x1C0` end symbol
- No unknown character glyphs occur in the compressed message bank

The human-readable dump is `ladystalker_japanese_text.txt`. It contains the
message bank first, followed by the lookup strings that the engine inserts at
runtime.

The supplied ROM itself is not copied into any output.

## Files

| File | Purpose |
| --- | --- |
| `ladystalker_japanese_text.txt` | Readable UTF-8 dump of messages and dynamic lookup strings |
| `ladystalker_japanese_text.tsv` | Lossless message table with IDs, ROM offsets, compressed sizes, raw symbols, and Unicode text |
| `ladystalker_lookup_strings.tsv` | Entity names, item names, and dynamic phrases with offsets and raw codes |
| `ladystalker_glyph_table.tsv` | Complete `0x000`–`0x1BF` proportional-font mapping and usage counts |
| `ladystalker_extract.py` | Reproducible extractor |
| `ladystalker_script_workspace.tsv` | Japanese and machine-English messages with an empty professional-translation column |
| `ladystalker_lookup_workspace.tsv` | Japanese and machine-English names/items/phrases with an editable translation column |
| `ladystalker_machine_english_text.txt` | Readable reference dump from ENG v1.0 |
| `ladystalker_patch_workspace.py` | Reproducibly rebuild the paired workspaces |
| `ladystalker_reinsert.py` | Compile edited workspaces into an overlay IPS |
| `ladystalker_patch_map.json` | Machine-readable addresses and record counts |
| `PATCH_ANALYSIS.md` | Reverse-engineering findings and proof |
| `TRANSLATOR_GUIDE.md` | Editing, compilation, and QA workflow |

## Running the extractor

```bash
python3 ladystalker_extract.py "Lady Stalker - Kako kara no Chousen (Japan).sfc" --out-dir output
```

The script intentionally validates the exact input before decoding it:

- Size: `0x280000` bytes (2,621,440 bytes), with no copier header
- SHA-256: `d0275f6fdc38f26b53b017bdd7fe26e13b9871a93671c76f48800e4f733b2385`
- Internal title: `LADY STALKER`

## Text format

Message IDs are written as `GG:II`. `GG` selects one of five compressed groups
and `II` is the record index within that group. The final group has 211 valid
records; the other four have 256 each.

Voicing marks are stored before their kana in the ROM. The extractor reorders
and normalizes them, so sequences such as `dakuten + テ` become the ordinary
Unicode character `デ`.

Runtime behavior that cannot be represented as literal text remains as a
readable tag:

| Tag | Meaning |
| --- | --- |
| `<NUMBER>` | Insert a runtime numeric value |
| `<SPEAKER>「` | Insert the current speaker's name, then an opening quote |
| `<INSERT_A>`–`<INSERT_D>` | Insert a runtime-selected name or phrase |
| `<WAIT>` / `<WAIT_INPUT>` | Pause, or wait for player input |
| `<PAUSE_60>` / `<PAUSE_30>` | Timed pause |
| `<CLEAR>` | Clear/reset the text area |
| `<NOP>` | Explicit no-operation control |
| `<ICON_170>` etc. | Non-Unicode pictogram preserved by exact glyph ID |

The arrow glyphs have been represented as `↘`, `↖`, `↙`, and `↗`.

## Compression and storage notes

The main text uses a context-adaptive Huffman code over 9-bit symbols:

1. The five group offsets begin at ROM offset `0x022287`.
2. Records are byte-length-prefixed. The valid record area ends exactly at
   `0x02A2D4`, where executable code resumes. The five group counts are
   `256, 256, 256, 256, 196`.
3. The previous decoded symbol is the context. Context `0x1C0` starts a
   message.
4. A context points into a preorder-coded binary tree through the table at
   `0x0201AA`. A zero bit is a branch and a one bit is a leaf.
5. Each tree's leaf values are packed as reverse-addressed 9-bit symbols
   immediately before its topology data.
6. Decoding stops at symbol `0x1C0`.

The proportional 16×15 font begins at `0x046236`, uses 30 bytes per glyph, and
contains 448 glyphs. The dynamic byte-string table occupies
`0x0D8091`–`0x0D8B8B`; the six 16-bit phrases occupy
`0x0D91CA`–`0x0D9212`.

## Verification

The ROM was run under an instrumented SNES emulator while its ROM reads, WRAM,
VRAM, message state, and PPU state were captured. The first-room line at
message `04:B3` independently renders in-game as:

```text
<SPEAKER>「行くわよ デスランド島へ!
ああ 体がうずく! ああ
はやく あばれまわりたい!
```

That observation verifies the Huffman traversal, glyph ordering, dakuten
handling, line control, and message-index calculation together.

The v1.0 English patch independently confirms the `0x02A2D4` boundary: its
direct-text pointer table supplies 1,220 translated records, then uses fifteen
`FF:FFFF` fallback entries for IDs `04:C4` through `04:D2`. Those IDs point
into executable code in the Japanese ROM and are not script messages.

Decorative text baked into artwork (for example, the title logo) is not OCR
output and is outside the engine text stores. The dump covers the complete
engine-readable message and dynamic-name stores for this exact ROM revision.

## USAGE EXAMPLE

It’s pleasantly simple now. Say you want to replace message 00:00.

Open ladystalker_script_workspace.tsv in Excel, LibreOffice, or another TSV-compatible editor.
Find this row:
message_id: 0x0000
Japanese: その 方向には 何もない<WAIT_INPUT>
Machine English: There's nothing that way.<WAIT_INPUT>
Enter your replacement only in the professional_translation column:
Nothing lies in that direction.<WAIT_INPUT>

Leave the Japanese and machine-reference columns untouched. Blank professional-translation cells automatically retain the machine translation.

Save the file as UTF-8 TSV.
Apply Lady_Stalker_ENG_v10.ips to the original Japanese ROM first. Then, from inside the extracted kit’s deliverables directory, run:
py ladystalker_reinsert.py ^
  "Lady_Stalker_ENG_v10.sfc" ^
  "ladystalker_script_workspace.tsv" ^
  "ladystalker_lookup_workspace.tsv" ^
  --output-ips "Lady_Stalker_Professional_Translation.ips" ^
  --output-rom "Lady_Stalker_Professional_Test.sfc"

or, in Windows PowerShell, run:
py ladystalker_reinsert.py "Lady_Stalker_ENG_v10.sfc" "ladystalker_script_workspace.tsv" "ladystalker_lookup_workspace.tsv" --output-ips "Lady_Stalker_Professional_Translation.ips" --output-rom "Lady_Stalker_Professional_Test.sfc"

That Windows command creates:

Lady_Stalker_Professional_Translation.ips — the distributable overlay patch.
Lady_Stalker_Professional_Test.sfc — a private testing ROM.

The overlay IPS must be applied to the already ENG-v1.0-patched ROM.

Formatting controls

Keep tags such as these exactly where needed:

<SPEAKER>
<INSERT_A>
<NUMBER>
<WAIT>
<WAIT_INPUT>
<PAUSE_30>
<CLEAR>
<LINE>

A real line break inside the spreadsheet cell becomes the normal in-game newline:

This is the first line.
This is the second line.<WAIT_INPUT>

The compiler will refuse accidental changes to important controls. It also rejects unsupported characters instead of silently mangling them.

For names and items, do the same thing in ladystalker_lookup_workspace.tsv. For example:

Japanese: コックス
Machine reference: Cox
Professional translation: Cox

One limitation: the compiler verifies encoding, controls, ROM space, pointers, and checksum, but it cannot know whether a sentence visually overflows the dialogue box. Long lines still need an emulator playtest and manual line breaks. 
