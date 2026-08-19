# Lady Stalker extraction and retranslation kit

This package extracts the Japanese text from the headerless Super Famicom ROM
`Lady Stalker - Kako kara no Chousen (Japan).sfc`. It also analyzes the existing
ENG v1.0 machine-translation patch, pairs its English with the Japanese source,
and can compile edited workspaces into a text-only overlay IPS.

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
