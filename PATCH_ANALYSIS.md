# Lady Stalker ENG v1.0 patch analysis

## Bottom line

The existing patch is an excellent technical base for a human retranslation.
It replaces the original context-adaptive Huffman reader with a direct byte
reader. Every translated message has a 24-bit pointer, and every printable
English character or control occupies one byte. A replacement script therefore
does not need to reproduce the Japanese compression.

The included `ladystalker_reinsert.py` compiles edited TSV workspaces into a
text-only overlay IPS. The overlay targets the exact ROM produced by
`Lady_Stalker_ENG_v10.ips`; it does not contain or redistribute that base patch.

## Verified ROMs

| Image | Size | SHA-256 |
| --- | ---: | --- |
| Japanese, headerless | `0x280000` | `d0275f6fdc38f26b53b017bdd7fe26e13b9871a93671c76f48800e4f733b2385` |
| ENG v1.0 patched | `0x400000` | `3a698798b844e248cd3cf612941d18d1837bc6af1805df18b6eff609bc97e3cf` |

The patched digest exactly matches the supplied patch README.

## IPS structure

- 5,114 IPS records: 3,383 literal and 1,731 RLE.
- The patch writes 1,574,660 payload bytes.
- Only 1,796 bytes inside the original `0x280000`-byte image actually change.
- The remaining `0x180000` bytes are a clean expansion to 4 MiB.
- The patch adds code, fonts, translated text, UI data, and opening assets in
  CPU banks `E8` through `F8`; several other expansion banks remain unused.

Important hooks include:

| Original address | New target | Purpose |
| --- | --- | --- |
| `C2:00A4` | `E8:0300` | Select message and load its direct pointer |
| `C2:00A0` | `E8:0340` | Read the next direct byte/control |
| `C5:0389` | `E8:0380` | Select the English proportional font |
| `C0:20F0` | `F4:0000` | UI/VRAM interception |
| `C0:0570` | `F8:0000` | Boot/DMA interception for replaced assets |

## Main message format

The pointer table is at ROM `0x281000`, CPU `E8:1000`, with three little-endian
bytes per entry. The first 1,220 entries are direct pointers. The final fifteen
entries are `FF FF FF`, which asks the new code to fall back to the old decoder.
Those fifteen IDs (`04:C4`-`04:D2`) are not real messages: in the Japanese ROM,
`04:C4` begins at CPU code rather than compressed text.

The existing English script occupies:

| CPU range | Messages | Bytes |
| --- | ---: | ---: |
| `EA:0CF8`-`EA:FFF6` | 909 | 62,206 |
| `E9:4000`-`E9:B78A` | 311 | 30,602 |
| Total | 1,220 | 92,808 |

Byte `01` is a space. Printable dialogue uses ordinary ASCII byte values.
Bytes `C0`-`D1` represent the same controls as Japanese symbols `1C0`-`1D1`;
`C0` ends a record. The proportional English font begins at `E9:0000`.

The reinsert tool deliberately packs replacement messages into unused banks
`EB`-`EF` and updates the pointer table. A record is never allowed to cross a
64 KiB bank boundary. This reserves 320 KiB for the new script, far above the
92.8 KiB used by the machine translation.

## Runtime lookup strings

The 352 entity/item names use the patched 8x8 system-font encoding and remain
length-prefixed records at `F5:0000`-`F5:0E44`. Six dynamic phrases use 16-bit
codes at `F6:0000`-`F6:0060`. Both tables are included in the translator
workspace and rebuilt by the reinsert tool.

## Proof performed

1. Applied the supplied IPS to the verified Japanese ROM and reproduced the
   README's patched SHA-256 exactly.
2. Extracted all 1,220 English pointers and confirmed that each record reaches
   its `C0` terminator within its bank.
3. Extracted 352 byte lookup strings and six word lookup strings.
4. Recompiled the untouched workspaces into banks `EB`-`EF`.
5. Decoded the result and verified every message and lookup string byte-for-byte
   against the original machine-patched data.
6. Applied the generated overlay IPS independently and reproduced the compiled
   ROM exactly.
7. Verified and rewrote the SNES checksum/complement.
8. Booted both the original patched ROM and the repacked ROM in Snes9x 1.63.
9. Repeated the process with one edited message and one edited name, then
   decoded both changes from the generated ROM successfully.

## Scope and remaining work

The workspaces cover the full dialogue/message bank plus all 358 runtime names,
items, and dynamic phrases. Some fixed menu labels, screen layouts, graphics,
and opening assets are embedded elsewhere in the existing patch. They can stay
as-is for a dialogue retranslation. If every UI phrase must receive a fresh
human review, those fixed assets need a separate inventory and reinsertion pass.

The supplied patch README does not state a reuse license. Before publishing a
derivative that depends on its engine/font/UI work, contact the patch author for
permission. A conservative release design is an overlay IPS that users apply
after obtaining and applying the author's original v1.0 patch themselves.

