# Experimental Lady Stalker extraction and retranslation kit

Credit to **RetchErezzed** for the English machine-translation patch for
*Lady Stalker: Kako kara no Chousen* (Super Famicom/SNES):

- [Lady Stalker ENG v1.0 on ROMhacking.net](https://www.romhacking.net/translations/7687/)

A viewable spreadsheet comparing the machine translation with the corrected
Japanese text is also available:

- [Lady Stalker translation workspace on Google Sheets](https://docs.google.com/spreadsheets/d/1r9tgzWNMF61ixo1x2PMF-ePCaV6QFM3urqfz5nA3llY/edit?gid=510070301#gid=510070301)

This package extracts the Japanese text from the exact headerless Super Famicom
ROM `Lady Stalker - Kako kara no Chousen (Japan).sfc`. It also analyzes the
existing ENG v1.0 patch, pairs its English with the Japanese source, and can
compile edited workspaces into an overlay IPS containing replacement script,
lookup-table, pointer, and checksum data.

The goal is to provide a practical starting point for a human translation or
human-edited retranslation. The toolkit is experimental and has not been
exhaustively tested, so translators should verify the Japanese rip, preserve
control tags, and carefully playtest every generated build. No guarantees are
made about translation accuracy, line fit, or complete in-game coverage of
every visual text element.

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

The extractor does not copy the original ROM into its output. The reinsertion
tool can optionally create a complete ROM for private testing; do not distribute
ROM images.

## Japanese glyph-map correction

The current files correct eleven visually similar kanji that were mislabeled in
the first generated Unicode dump: `行→動`, `昔→者`, `苦→昔`, `言→冒`, `落→溶`,
`土→士`, `士→土`, `営→管`, `寝→侵`, `刻→剣`, and `続→継`. Corrected examples
include `自動`, `学者`, `冒険`, `溶岩`, `兵士`, `水道管`, `侵入`, and `後継者`.

This correction changes only the human-readable Unicode rendering. Message IDs,
ROM offsets, raw symbol codes, controls, row alignment, and English references
are unchanged.

## Files

| File | Purpose |
| --- | --- |
| `LadyStalker_Retranslation_Kit.zip` | Downloadable copy of the complete toolkit |
| `LadyStalker_Translation_Workspace_Corrected.xlsx` | Formatted workbook containing the dialogue, lookups, and glyph-correction audit |
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
| `PATCH_ANALYSIS.md` | Reverse-engineering findings and supporting evidence |
| `TRANSLATOR_GUIDE.md` | Editing, compilation, and QA workflow |
| `CHANGELOG.md` | Package correction and release notes |

## Retranslation quick start

The compiler reads these two UTF-8 TSV files:

- `ladystalker_script_workspace.tsv`: dialogue and system messages
- `ladystalker_lookup_workspace.tsv`: names, items, and dynamic phrases

Enter new text only in `professional_translation`. Leave the Japanese and
machine-reference columns unchanged. A blank professional-translation cell
deliberately falls back to `machine_english_reference`, allowing partially
translated builds to be compiled and tested.

For example, message `0x0000` initially contains:

| Field | Text |
| --- | --- |
| Japanese | `その 方向には 何もない<WAIT_INPUT>` |
| Machine English | `There's nothing that way.<WAIT_INPUT>` |
| Professional translation | `Nothing lies in that direction.<WAIT_INPUT>` |

Keep identifier fields such as `message_id` unchanged, including their leading
zeroes. If a spreadsheet program automatically reformats identifiers, import
those columns as text. Preserve the exact column names and row order.

`LadyStalker_Translation_Workspace_Corrected.xlsx` contains the same workspaces
as formatted `Dialogue` and `Lookups` sheets, plus a `Glyph Corrections` audit
sheet. It is convenient for Excel or Google Sheets. The compiler still requires
TSV input, so export the two workspace sheets as UTF-8 TSV files with their
original headers and filenames before compiling.

### Controls and supported characters

Keep runtime tags intact and in the same order unless you deliberately intend
to change engine behavior. Important examples include:

- `<SPEAKER>`: insert the current speaker's name
- `<INSERT_A>` through `<INSERT_D>`: insert a runtime-selected name or phrase
- `<NUMBER>`: insert a runtime number
- `<WAIT>` and `<WAIT_INPUT>`: pause or wait for input
- `<PAUSE_30>` and `<PAUSE_60>`: timed pauses
- `<CLEAR>`: clear/reset the text area
- `<LINE>`: the original patch's explicit line control

A real newline inside a spreadsheet cell becomes the normal in-game newline:

```text
This is the first line.
This is the second line.<WAIT_INPUT>
```

The compiler rejects accidental changes to structural controls by default. Use
`--allow-control-changes` only for a deliberate, tested edit. To intentionally
compile an empty record or lookup value, enter `<EMPTY>` by itself.

The dialogue font supports printable ASCII. Use straight quotes and apostrophes;
curly characters such as `’`, `“`, and `”`, as well as em dashes and Unicode
ellipsis characters, are unsupported. The smaller system font used for names,
items, and other lookup strings has a more limited character set. The compiler
reports unsupported characters instead of silently corrupting them.

### Build the overlay IPS

First apply `Lady_Stalker_ENG_v10.ips` to the exact headerless Japanese ROM.
The resulting 4 MiB ENG v1.0 ROM must have this SHA-256:

```text
3a698798b844e248cd3cf612941d18d1837bc6af1805df18b6eff609bc97e3cf
```

Run the compiler from the directory containing the scripts and workspaces.

Windows Command Prompt:

```bat
py ladystalker_reinsert.py ^
  "Lady_Stalker_ENG_v10.sfc" ^
  "ladystalker_script_workspace.tsv" ^
  "ladystalker_lookup_workspace.tsv" ^
  --output-ips "Lady_Stalker_Professional_Translation.ips" ^
  --output-rom "Lady_Stalker_Professional_Test.sfc"
```

There must be a real line break immediately after each caret, with no trailing
spaces after it.

Windows PowerShell:

```powershell
py ladystalker_reinsert.py "Lady_Stalker_ENG_v10.sfc" "ladystalker_script_workspace.tsv" "ladystalker_lookup_workspace.tsv" --output-ips "Lady_Stalker_Professional_Translation.ips" --output-rom "Lady_Stalker_Professional_Test.sfc"
```

Linux or macOS:

```bash
python3 ladystalker_reinsert.py \
  "Lady_Stalker_ENG_v10.sfc" \
  "ladystalker_script_workspace.tsv" \
  "ladystalker_lookup_workspace.tsv" \
  --output-ips "Lady_Stalker_Professional_Translation.ips" \
  --output-rom "Lady_Stalker_Professional_Test.sfc"
```

The command creates:

- `Lady_Stalker_Professional_Translation.ips`: the distributable overlay patch
- `Lady_Stalker_Professional_Test.sfc`: a private ROM for emulator testing

The overlay IPS must be applied to the already ENG-v1.0-patched ROM, not
directly to the original Japanese ROM. The optional test ROM must not be
distributed.

The compiler verifies the base-ROM hash, workspace row counts and IDs, supported
characters, structural controls, available ROM space, pointers, and checksum.
It cannot determine whether a sentence visually overflows a dialogue box or
menu field. Long text still requires emulator playtesting and manual line
breaks.

For names and items, use the same process in
`ladystalker_lookup_workspace.tsv`. For example:

| Field | Text |
| --- | --- |
| Japanese | `コックス` |
| Machine English | `Cox` |
| Professional translation | `Cox` |

See `TRANSLATOR_GUIDE.md` for the complete editing and QA workflow.

## Running the extractor

```bash
python3 ladystalker_extract.py "Lady Stalker - Kako kara no Chousen (Japan).sfc" --out-dir output
```

The extractor intentionally validates the exact input before decoding it:

- Size: `0x280000` bytes (2,621,440 bytes), with no copier header
- SHA-256: `d0275f6fdc38f26b53b017bdd7fe26e13b9871a93671c76f48800e4f733b2385`
- Internal title: `LADY STALKER`

## Text format

Message IDs are written as `GG:II`. `GG` selects one of five compressed groups,
and `II` is the record index within that group. The final group has **196** valid
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

The arrow glyphs are represented as `↘`, `↖`, `↙`, and `↗`.

## Compression and storage notes

The main text uses a context-adaptive Huffman code over 9-bit symbols:

1. The five group offsets begin at ROM offset `0x022287`.
2. Records are byte-length-prefixed. The valid record area ends exactly at
   `0x02A2D4`, where executable code resumes. The five group counts are
   `256, 256, 256, 256, 196`.
3. The previous decoded symbol is the context. Context `0x1C0` starts a message.
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
VRAM, message state, and PPU state were captured. The first-room line at message
`04:B3` independently renders in-game as:

```text
<SPEAKER>「行くわよ デスランド島へ!
ああ 体がうずく! ああ
はやく あばれまわりたい!
```

That observation verifies the Huffman traversal, glyph ordering, dakuten
handling, line control, and message-index calculation together.

The ENG v1.0 patch independently confirms the `0x02A2D4` boundary: its
direct-text pointer table supplies 1,220 translated records, then uses fifteen
`FF:FFFF` fallback entries for IDs `04:C4` through `04:D2`. Those IDs point into
executable code in the Japanese ROM and are not script messages.

Decorative text baked into artwork, such as the title logo, is not OCR output
and lies outside the engine text stores. The dump covers the complete
engine-readable message and dynamic-name stores for this exact ROM revision.

## Publishing and testing

- Distribute patches and documentation only, never ROM images.
- Apply the generated overlay only after applying ENG v1.0 to the supported
  headerless Japanese ROM.
- Credit and coordinate with RetchErezzed before publicly releasing a derived
  translation that depends on the existing hack.
- Playtest story branches, optional NPCs, shops, battles, menus, saves, dynamic
  inserts, waits, page clears, and long lines.
- Keep a terminology sheet for names, locations, items, and recurring jokes.
- Test on an accurate emulator and, ideally, real hardware or a flash cartridge.
