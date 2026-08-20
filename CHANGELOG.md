# Changelog

## 2026-08-19 — combined retranslation and Landstalker-font builder

- Added `--landstalker-rom` to `ladystalker_reinsert.py`.
- Added independent `--fix-battle-messages` mode for users who want to correct
  ENG v1.0's direct-English battle notices without changing its dialogue font
  or spacing. `--landstalker-rom` includes this fix automatically.
- The optional mode imports 81 exact dialogue glyphs from the verified
  Landstalker USA ROM, enables the seven-unit fit-safe word spacing, and
  installs the conditional ENG-v1.0 battle-message ASCII renderer fix.
- Combined builds now perform script, lookup, pointer, font, spacing, and
  renderer edits before calculating one final valid SNES checksum.
- Added reporting for any edited dialogue characters that must retain their
  ENG-v1.0 fallback glyphs.
- Verified that the retranslation pointer table ends at ROM `0x281E79`, before
  the battle-fix routine at `0x282000`, so the two features do not overlap.
- Verified that a freshly generated combined IPS reconstructs its test ROM
  byte-for-byte from the exact ENG-v1.0 base.
- Smoke-tested the combined ROM in Snes9x 1.63: it booted at the expected frame
  rate and freshly rendered repacked English dialogue with the imported font.

## 2026-08-19 — corrected Japanese glyph map

- Corrected eleven low-resolution kanji glyph labels: `行→動`, `昔→者`,
  `苦→昔`, `言→冒`, `落→溶`, `土→士`, `士→土`, `営→管`, `寝→侵`,
  `刻→剣`, and `続→継`.
- Regenerated the complete Japanese dump and paired translator workspace from
  the verified Japanese and ENG v1.0 ROMs.
- Confirmed that exactly 77 of 1,220 dialogue rows received corrected Japanese
  rendering. No lookup rows changed.
- Confirmed that message IDs, ROM offsets, raw symbol codes, controls, English
  references, lookup data, and row alignment remain byte-for-byte unchanged.
- Added a formatted Excel/Google Sheets workbook with a visible correction
  audit sheet.
- Corrected the README's final-group count from 211 to 196.
