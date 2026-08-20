# QA report — Lady Stalker exact Landstalker font overlay v1.1

## Source verification

- Landstalker USA ROM size: `0x200000`
- Landstalker USA ROM SHA-256: `ad9f49cf2d528ee40fab74f8687ed908036873e54a7dd30c5dc32286c29fc614`
- Internal product code: `GM MK-1353-00`
- Font pointer at ROM `0x022E84`: `0x0002A884`
- Extracted font size: `85 × 30 = 2550` bytes
- Extracted font SHA-256: `732edc07d7a8486803ab20e8f054db75b8a36e5967484728a7483b9644aa5b6c`
- The extracted bytes are identical to `assets_packed/graphics/fonts/mainfont.1bpp` in the open Landstalker disassembly.

## Conversion verification

- Source and target both use 16×15 one-bit glyphs stored as fifteen 16-bit rows.
- Conversion changes row byte order only: Mega Drive big-endian → SNES little-endian.
- No glyph was scaled, traced, filtered, redrawn, cropped, or horizontally shifted.
- 81 source glyphs have direct printable ASCII targets and were imported.
- Every printable character used by the released Lady Stalker ENG v1.0 dialogue exists in the Landstalker source font.
- The fourteen unavailable ASCII symbols remain unchanged ENG-v1.0 fallbacks:

```text
$ + ; @ [ \ ] ^ _ ` { | } ~
```

## Static line-fit verification

The 1,220 released message records were divided at explicit newline, wait, speaker, clear, line, input-wait, and end controls, producing 3,961 literal rendered segments.

- Released ENG-v1.0 maximum literal width: 240 units
- Exact Landstalker glyphs with ENG-v1.0's 12-unit spaces: 262 units maximum
- Exact Landstalker glyphs with fit-safe 7-unit spaces: 240 units maximum
- Fit-safe literal segments over 240 units: 0
- Text bytes changed: 0
- Explicit line breaks changed: 0
- Control bytes changed: 0
- Message pointers changed: 0

Dynamic runtime inserts and later edited translations still require ordinary emulator testing.

## Battle-message diagnosis and fix

- Reported symptom: Japanese-looking text at the bottom of the battle screen.
- Screenshot tile match: the complete 18-cell line matches the ENG ROM's 8×8 system font at ROM `0x045576`.
- Underlying direct-message bytes decode as `Tomaton attacked!`.
- Root cause: ENG v1.0's direct-text path supplied ASCII bytes to the original battle renderer, which stored each low byte as a Japanese 8×8 tile number.
- Original write site: CPU `C1:F895`, ROM `0x01F895`, `SEP #$30 / STA [$34],Y`.
- v1.1 hook: `JSL $E82000`.
- Conversion routine: ROM `0x282000`; 256-byte conversion table: ROM `0x282040`.
- The conversion is enabled only when the direct-message sentinel at WRAM `$1C4C` is `$FFFF`.
- Original compressed/fallback messages are written unchanged.
- Symbols at or above `0x0100` bypass the table and are written unchanged.
- Every printable ASCII byte `0x20`–`0x7E` has a valid ENG-v1.0 system-font mapping.
- Example conversion: `Tomaton attacked!` → `36 50 4E 42 55 50 4F 01 42 55 55 42 44 4C 46 45 10`.

The screenshot, message data, renderer code, and system-font tiles establish the fault and conversion statically. The exact reported encounter was not replayed during automated QA, so an ordinary in-game retest is still recommended.

## Emulator verification

- Emulator/core: Snes9x 1.63
- Automated test length: 3,600 frames
- Tested from an existing game-state transition through multiple first-room dialogue pages
- Observed glyph classes: uppercase, lowercase, digits, apostrophe, comma, period, ellipsis, question mark, exclamation mark, hyphen, and colon
- Observed dynamic speaker names: Lady and Yoshio
- Visible clipping or row overlap observed: none
- Boot or execution failure observed: none
- This no-regression run used the final v1.1 ROM containing the battle hook.

## Patch reconstruction

- IPS size: 2,182 bytes
- IPS records: 84
- Actual changed ROM bytes: 1,048
  - font pixels: 751 bytes
  - fit-safe spacing instruction: 1 byte
  - battle write-site hook: 4 bytes
  - battle conversion routine: 33 bytes differing from the empty area
  - battle conversion table: 255 bytes differing from the empty area
  - SNES checksum/complement: 4 bytes
- Reapplying the IPS to the exact ENG-v1.0 base reproduces output SHA-256:
  `c127b04160416c62c0c049543a2badfc52c4bea839cded8221decf1284e12964`
