# Translator guide

## Files to edit

- `ladystalker_script_workspace.tsv`: 1,220 dialogue/system messages.
- `ladystalker_lookup_workspace.tsv`: 352 names/items and six dynamic phrases.

Both are UTF-8 tab-separated files. Use a spreadsheet program that preserves
UTF-8, tabs, multiline cells, and exact column names.

`LadyStalker_Translation_Workspace_Corrected.xlsx` contains the same two
workspaces as formatted `Dialogue` and `Lookups` sheets, plus a
`Glyph Corrections` audit sheet. It is convenient for Excel or importing into
Google Sheets. The TSV files remain the compiler inputs; after editing the
workbook online, export the two workspace sheets as UTF-8 TSV with their exact
headers before running the compiler.

Translate into `professional_translation`. A blank cell deliberately falls
back to `machine_english_reference`, so the project can be compiled and tested
before every line is finished. Put discussion, context, or uncertainties in
`translator_notes`.

## Controls

Keep runtime tags intact unless you understand the engine behavior. Important
examples include:

- `<SPEAKER>`: insert the current speaker name.
- `<INSERT_A>` through `<INSERT_D>`: insert a runtime-selected name or phrase.
- `<NUMBER>`: insert a runtime number.
- `<WAIT>` and `<WAIT_INPUT>`: pause or wait for input.
- `<PAUSE_30>` and `<PAUSE_60>`: timed pauses.
- `<CLEAR>`: clear/reset the text area.
- `<LINE>`: the original patch's `C3` line control.

A literal newline in a message compiles to the normal `C8` newline control.
The compiler rejects changed structural controls by default. Use
`--allow-control-changes` only for a deliberate, tested edit. To intentionally
compile an empty record or lookup value, enter `<EMPTY>` by itself.

The dialogue font accepts printable ASCII. The smaller system font used by the
lookup table supports the characters present in its reference strings. The
compiler reports unsupported characters rather than silently corrupting them.

## Build an overlay IPS

First apply `Lady_Stalker_ENG_v10.ips` to the exact headerless Japanese ROM.
The resulting 4 MiB ROM must have SHA-256:

`3a698798b844e248cd3cf612941d18d1837bc6af1805df18b6eff609bc97e3cf`

Then run:

```bash
python3 ladystalker_reinsert.py \
  Lady_Stalker_ENG_v10.sfc \
  ladystalker_script_workspace.tsv \
  ladystalker_lookup_workspace.tsv \
  --output-ips Lady_Stalker_Professional_Translation.ips
```

The output is an overlay: apply it to the ENG v1.0 patched ROM, not directly to
the Japanese ROM. `--output-rom test.sfc` may also be used for a private test
build; do not distribute ROM images.

## Optional combined Landstalker-font build

To include the exact Landstalker USA dialogue font, fit-safe spacing, and the
ENG-v1.0 battle-message fix in the same professionally translated overlay, add
`--landstalker-rom`:

```bash
python3 ladystalker_reinsert.py \
  Lady_Stalker_ENG_v10.sfc \
  ladystalker_script_workspace.tsv \
  ladystalker_lookup_workspace.tsv \
  --landstalker-rom "Landstalker (USA).md" \
  --output-ips Lady_Stalker_Professional_Landstalker_Font.ips \
  --output-rom Lady_Stalker_Professional_Landstalker_Test.sfc
```

The required Landstalker ROM is the USA release `GM MK-1353-00`, exactly
`0x200000` bytes, with SHA-256:

`ad9f49cf2d528ee40fab74f8687ed908036873e54a7dd30c5dc32286c29fc614`

The reinserter validates both ROMs, performs all script and add-on edits, and
then calculates one correct final SNES checksum. The resulting IPS is applied
directly to the exact ENG v1.0 base; do not apply the separate Landstalker-font
v1.1 IPS afterward.

The exact font supplies 81 printable-ASCII glyphs. If an edited dialogue uses
one of Landstalker's unavailable symbols, the build succeeds but reports it in
`landstalker_font_fallbacks_used`; that symbol retains its ENG-v1.0 glyph.
Custom dialogue still needs manual line breaks and emulator testing even with
the fit-safe seven-unit word spacing.

To retain the ENG-v1.0 dialogue font and spacing while fixing only the inherited
battle-notice rendering bug, add `--fix-battle-messages` instead. It requires no
Landstalker ROM and is included automatically when `--landstalker-rom` is used.

## QA checklist

- Test each story branch, optional NPC, shop, battle, save/config screen, and
  dynamic insert.
- Check manual line breaks and all long messages on-screen; the compiler does
  not automatically word-wrap prose.
- Confirm names/items fit every narrow menu field.
- Test waits, page clears, speaker changes, and numeric inserts.
- Keep a terminology sheet for character names, locations, items, and recurring
  jokes.
- Run on at least one accurate emulator and, ideally, real hardware or a flash
  cartridge before release.
