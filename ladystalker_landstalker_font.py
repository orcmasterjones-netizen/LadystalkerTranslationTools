#!/usr/bin/env python3
"""Build a fit-safe Lady Stalker overlay using exact Landstalker USA glyphs.

This builder requires both original ROMs.  It extracts Landstalker's dialogue
font directly from the verified USA ROM, converts only the row endianness,
maps the available characters into Lady Stalker ENG v1.0, narrows word spacing
to keep the released script within its existing line budget, fixes ENG v1.0's
ASCII battle-log rendering path, and writes an IPS.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


LANDSTALKER_SIZE = 0x200000
LANDSTALKER_SHA256 = "ad9f49cf2d528ee40fab74f8687ed908036873e54a7dd30c5dc32286c29fc614"
LANDSTALKER_FONT_POINTER_OFFSET = 0x022E84
LANDSTALKER_FONT_OFFSET = 0x02A884
LANDSTALKER_FONT_GLYPHS = 85
LANDSTALKER_FONT_SHA256 = "732edc07d7a8486803ab20e8f054db75b8a36e5967484728a7483b9644aa5b6c"

LADY_STALKER_SIZE = 0x400000
LADY_STALKER_SHA256 = "3a698798b844e248cd3cf612941d18d1837bc6af1805df18b6eff609bc97e3cf"
EXPECTED_OUTPUT_SHA256 = "c127b04160416c62c0c049543a2badfc52c4bea839cded8221decf1284e12964"
LADY_STALKER_FONT_OFFSET = 0x290000
SPACE_ADVANCE_IMMEDIATE_OFFSET = 0x0502B1
BATTLE_RENDER_HOOK_OFFSET = 0x01F895  # CPU C1:F895
BATTLE_RENDER_ROUTINE_OFFSET = 0x282000  # CPU E8:2000
BATTLE_RENDER_TABLE_OFFSET = 0x282040  # CPU E8:2040
CHECKSUM_OFFSET = 0x00FFDC
BYTES_PER_GLYPH = 30

LANDSTALKER_CHARSET = (
    " "
    "0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "*.,?!/<>:-\'\"%#&()="
    "↖↗↘↙"
)


def build_system_reverse() -> dict[str, int]:
    """Return ENG v1.0's printable-character to 8x8 tile-code mapping."""
    table: dict[int, str] = {0x01: " ", 0x0C: "L", 0x0D: "S", 0x0E: "P", 0x0F: "Y"}
    for code, character in enumerate("0123456789", 0x02):
        table[code] = character
    for code, character in enumerate("!\"#$%&'()*+,-./", 0x10):
        table[code] = character
    for code, character in enumerate(":;<=>?@", 0x1F):
        table[code] = character

    capital_codes = [
        *range(0x26, 0x31),
        0x0C,
        *range(0x31, 0x34),
        0x0E,
        *range(0x34, 0x36),
        0x0D,
        *range(0x36, 0x3B),
        0x0F,
        0x3B,
    ]
    for code, character in zip(capital_codes, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", strict=True):
        table[code] = character
    for code, character in enumerate("[\\]^_`", 0x3C):
        table[code] = character
    for code, character in enumerate("abcdefghijklmnopqrstuvwxyz", 0x42):
        table[code] = character
    for code, character in enumerate("{|}~", 0x5C):
        table[code] = character
    return {character: code for code, character in table.items()}


def install_battle_renderer_fix(rom: bytearray) -> None:
    """Map direct-message ASCII to the patched 8x8 font in battle notices.

    ENG v1.0 sends direct ASCII through the original C1:F883 battle-buffer
    builder.  That routine historically stored the low byte as a Japanese tile
    number, producing strings such as ``Tomaton attacked!`` as Japanese-looking
    garbage.  The hook maps bytes only while the direct-message sentinel at
    $1C4C is $FFFF; original compressed/fallback text keeps its old behavior.
    """
    expected_hook = bytes.fromhex("E2 30 97 34")  # SEP #$30 / STA [$34],Y
    actual_hook = bytes(rom[BATTLE_RENDER_HOOK_OFFSET : BATTLE_RENDER_HOOK_OFFSET + 4])
    if actual_hook != expected_hook:
        raise ValueError(
            "Unexpected battle-render write site: "
            f"expected {expected_hook.hex()}, found {actual_hook.hex()}"
        )

    # A is a 16-bit decoded symbol on entry. Preserve Japanese/fallback symbols,
    # guard the 256-byte table, and return in the original M=8/X=8 state after
    # performing the displaced STA [$34],Y.
    routine = bytes.fromhex(
        "48"          # PHA
        "AD 4C 1C"    # LDA $1C4C
        "C9 FF FF"    # CMP #$FFFF
        "D0 14"       # BNE raw_with_stack
        "68"          # PLA
        "C9 00 01"    # CMP #$0100
        "B0 0F"       # BCS raw
        "DA"          # PHX
        "AA"          # TAX
        "E2 20"       # SEP #$20 (A=8, X/Y still 16)
        "BF 40 20 E8" # LDA $E82040,X
        "FA"          # PLX
        "E2 10"       # SEP #$10 (X/Y=8)
        "97 34"       # STA [$34],Y
        "6B"          # RTL
        "68"          # raw_with_stack: PLA
        "E2 30"       # raw: SEP #$30
        "97 34"       # STA [$34],Y
        "6B"          # RTL
    )
    mapping = bytearray(range(0x100))
    reverse = build_system_reverse()
    mapping[0x20] = reverse[" "]
    for code in range(0x21, 0x7F):
        mapping[code] = reverse[chr(code)]

    routine_area = rom[
        BATTLE_RENDER_ROUTINE_OFFSET : BATTLE_RENDER_ROUTINE_OFFSET + len(routine)
    ]
    table_area = rom[BATTLE_RENDER_TABLE_OFFSET : BATTLE_RENDER_TABLE_OFFSET + len(mapping)]
    if any(value != 0xFF for value in routine_area + table_area):
        raise ValueError("ENG v1.0 battle-fix expansion area is not empty")

    rom[BATTLE_RENDER_HOOK_OFFSET : BATTLE_RENDER_HOOK_OFFSET + 4] = bytes.fromhex(
        "22 00 20 E8"  # JSL $E82000
    )
    rom[
        BATTLE_RENDER_ROUTINE_OFFSET : BATTLE_RENDER_ROUTINE_OFFSET + len(routine)
    ] = routine
    rom[BATTLE_RENDER_TABLE_OFFSET : BATTLE_RENDER_TABLE_OFFSET + len(mapping)] = mapping


def checked_read(path: Path, expected_size: int, expected_sha256: str, label: str) -> bytes:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != expected_size or digest != expected_sha256:
        raise ValueError(
            f"{label} did not match the required ROM.\n"
            f"Expected size 0x{expected_size:X}, SHA-256 {expected_sha256}\n"
            f"Received size 0x{len(data):X}, SHA-256 {digest}"
        )
    return data


def extract_font(rom: bytes) -> dict[str, bytes]:
    pointer = int.from_bytes(
        rom[LANDSTALKER_FONT_POINTER_OFFSET : LANDSTALKER_FONT_POINTER_OFFSET + 4],
        "big",
    )
    if pointer != LANDSTALKER_FONT_OFFSET:
        raise ValueError(f"Unexpected Landstalker font pointer 0x{pointer:06X}")

    size = LANDSTALKER_FONT_GLYPHS * BYTES_PER_GLYPH
    raw = rom[pointer : pointer + size]
    if hashlib.sha256(raw).hexdigest() != LANDSTALKER_FONT_SHA256:
        raise ValueError("Extracted Landstalker font failed its integrity check")
    if len(LANDSTALKER_CHARSET) != LANDSTALKER_FONT_GLYPHS:
        raise AssertionError("Landstalker character map and glyph count disagree")

    glyphs: dict[str, bytes] = {}
    for index, character in enumerate(LANDSTALKER_CHARSET):
        source = raw[index * BYTES_PER_GLYPH : (index + 1) * BYTES_PER_GLYPH]
        # The row masks are otherwise directly compatible. Mega Drive 68000
        # words are big-endian; the SNES 65C816 reads them little-endian.
        glyphs[character] = b"".join(
            source[row : row + 2][::-1] for row in range(0, BYTES_PER_GLYPH, 2)
        )
    return glyphs


def update_checksum(rom: bytearray) -> tuple[int, int]:
    rom[CHECKSUM_OFFSET : CHECKSUM_OFFSET + 4] = b"\x00\x00\x00\x00"
    checksum = (sum(rom) + 510) & 0xFFFF
    complement = checksum ^ 0xFFFF
    rom[CHECKSUM_OFFSET : CHECKSUM_OFFSET + 2] = complement.to_bytes(2, "little")
    rom[CHECKSUM_OFFSET + 2 : CHECKSUM_OFFSET + 4] = checksum.to_bytes(2, "little")
    if sum(rom) & 0xFFFF != checksum:
        raise ValueError("Internal SNES checksum verification failed")
    return complement, checksum


def write_ips(base: bytes, target: bytes, output: Path) -> int:
    if len(base) != len(target):
        raise ValueError("IPS source and target ROMs must have equal sizes")

    records: list[tuple[int, bytes]] = []
    offset = 0
    while offset < len(base):
        if base[offset] == target[offset]:
            offset += 1
            continue
        start = offset
        last_difference = offset
        offset += 1
        while offset < len(base):
            if base[offset] != target[offset]:
                last_difference = offset
            elif offset - last_difference > 8:
                break
            offset += 1
        end = last_difference + 1
        position = start
        while position < end:
            chunk_end = min(end, position + 0xFFFF)
            records.append((position, target[position:chunk_end]))
            position = chunk_end

    payload = bytearray(b"PATCH")
    for position, data in records:
        payload += position.to_bytes(3, "big")
        payload += len(data).to_bytes(2, "big")
        payload += data
    payload += b"EOF"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lady_stalker_eng_rom", type=Path, help="exact ENG v1.0 patched ROM")
    parser.add_argument("landstalker_usa_rom", type=Path, help="exact GM MK-1353-00 USA ROM")
    parser.add_argument("--output-ips", type=Path, required=True)
    parser.add_argument("--output-rom", type=Path, help="optional private test ROM")
    args = parser.parse_args()

    base = checked_read(
        args.lady_stalker_eng_rom,
        LADY_STALKER_SIZE,
        LADY_STALKER_SHA256,
        "Lady Stalker ENG v1.0 ROM",
    )
    landstalker = checked_read(
        args.landstalker_usa_rom,
        LANDSTALKER_SIZE,
        LANDSTALKER_SHA256,
        "Landstalker USA ROM",
    )
    glyphs = extract_font(landstalker)

    target = bytearray(base)
    replaced: list[str] = []
    for character, glyph in glyphs.items():
        if len(character) == 1 and 0x20 <= ord(character) <= 0x7E:
            start = LADY_STALKER_FONT_OFFSET + ord(character) * BYTES_PER_GLYPH
            target[start : start + BYTES_PER_GLYPH] = glyph
            replaced.append(character)

    # In ENG v1.0, LDX #$000B followed by SEC/ADC advances a space by twelve
    # internal horizontal units. LDX #$0006 makes that advance seven units.
    # This leaves every literal released line at or below its 240-unit budget.
    expected_instruction = b"\x0B\x00"
    actual_instruction = bytes(
        target[SPACE_ADVANCE_IMMEDIATE_OFFSET : SPACE_ADVANCE_IMMEDIATE_OFFSET + 2]
    )
    if actual_instruction != expected_instruction:
        raise ValueError(
            "Unexpected Lady Stalker space-advance instruction: "
            f"expected {expected_instruction.hex()}, found {actual_instruction.hex()}"
        )
    target[SPACE_ADVANCE_IMMEDIATE_OFFSET : SPACE_ADVANCE_IMMEDIATE_OFFSET + 2] = b"\x06\x00"

    install_battle_renderer_fix(target)

    complement, checksum = update_checksum(target)
    output_digest = hashlib.sha256(target).hexdigest()
    if output_digest != EXPECTED_OUTPUT_SHA256:
        raise ValueError(
            "Generated ROM failed its reproducibility check: "
            f"expected {EXPECTED_OUTPUT_SHA256}, got {output_digest}"
        )

    records = write_ips(base, target, args.output_ips)
    if args.output_rom:
        args.output_rom.parent.mkdir(parents=True, exist_ok=True)
        args.output_rom.write_bytes(target)

    printable_fallbacks = "".join(
        character for character in (chr(code) for code in range(0x20, 0x7F))
        if character not in glyphs
    )
    print(f"Imported exact Landstalker glyphs: {len(replaced)}")
    print(f"Unchanged fallback symbols: {printable_fallbacks!r}")
    print("Installed ENG v1.0 battle-log ASCII renderer fix")
    print(f"Wrote: {args.output_ips}")
    print(f"IPS records: {records}")
    if args.output_rom:
        print(f"Wrote private test ROM: {args.output_rom}")
    print(f"Output ROM SHA-256: {output_digest}")
    print(f"SNES checksum/complement: 0x{checksum:04X}/0x{complement:04X}")


if __name__ == "__main__":
    main()
