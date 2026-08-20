#!/usr/bin/env python3
"""Compile a professional Lady Stalker script into an ENG-v1.0 overlay IPS.

The output IPS targets the exact 4 MiB ROM produced by Lady_Stalker_ENG_v10.ips.
By default it contains the replacement script, lookup tables, pointers, and
checksum.  --fix-battle-messages corrects ENG v1.0's battle-log ASCII renderer.
Supplying --landstalker-rom also imports the exact Landstalker USA dialogue
font, enables fit-safe word spacing, and automatically includes that renderer
fix before calculating one final checksum.  The output never contains either
supplied ROM.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import ladystalker_patch_workspace as patch


SCRIPT_START = 0x2B0000  # CPU EB:0000
SCRIPT_END = 0x300000  # before CPU F0:0000
BYTE_LOOKUP_LIMIT = 0x351FF0
WORD_LOOKUP_LIMIT = 0x361FF0
CHECKSUM_OFFSET = 0x00FFDC

LANDSTALKER_SIZE = 0x200000
LANDSTALKER_SHA256 = "ad9f49cf2d528ee40fab74f8687ed908036873e54a7dd30c5dc32286c29fc614"
LANDSTALKER_FONT_POINTER_OFFSET = 0x022E84
LANDSTALKER_FONT_OFFSET = 0x02A884
LANDSTALKER_FONT_GLYPHS = 85
LANDSTALKER_FONT_SHA256 = "732edc07d7a8486803ab20e8f054db75b8a36e5967484728a7483b9644aa5b6c"
LANDSTALKER_CHARSET = (
    " "
    "0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "*.,?!/<>:-\'\"%#&()="
    "↖↗↘↙"
)

DIALOGUE_FONT_BASE = 0x290000  # CPU E9:0000
BYTES_PER_GLYPH = 30
SPACE_ADVANCE_IMMEDIATE_OFFSET = 0x0502B1
BATTLE_RENDER_HOOK_OFFSET = 0x01F895  # CPU C1:F895
BATTLE_RENDER_ROUTINE_OFFSET = 0x282000  # CPU E8:2000
BATTLE_RENDER_TABLE_OFFSET = 0x282040  # CPU E8:2040

TAG_TO_CODE = {
    f"<{name}>": code
    for code, name in patch.ENGLISH_CONTROLS.items()
    if name not in ("END", "NEWLINE")
}
SYSTEM_REVERSE = {character: code for code, character in patch.SYSTEM_CHARSET.items()}
STRUCTURAL_CONTROLS = set(range(0xC1, 0xD2)) - {0xC3, 0xC8}


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


def extract_landstalker_font(rom: bytes) -> dict[str, bytes]:
    pointer = int.from_bytes(
        rom[
            LANDSTALKER_FONT_POINTER_OFFSET : LANDSTALKER_FONT_POINTER_OFFSET + 4
        ],
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
        glyphs[character] = b"".join(
            source[row : row + 2][::-1]
            for row in range(0, BYTES_PER_GLYPH, 2)
        )
    return glyphs


def install_battle_renderer_fix(rom: bytearray) -> None:
    """Map direct-message ASCII to ENG v1.0's 8x8 battle font."""
    expected_hook = bytes.fromhex("E2 30 97 34")  # SEP #$30 / STA [$34],Y
    actual_hook = bytes(
        rom[BATTLE_RENDER_HOOK_OFFSET : BATTLE_RENDER_HOOK_OFFSET + 4]
    )
    if actual_hook != expected_hook:
        raise ValueError(
            "Unexpected battle-render write site: "
            f"expected {expected_hook.hex()}, found {actual_hook.hex()}"
        )

    # A is a 16-bit decoded symbol on entry. The routine maps bytes only while
    # the direct-message sentinel at $1C4C is $FFFF, preserves Japanese and
    # fallback symbols, and returns in the original M=8/X=8 state.
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
    mapping[0x20] = SYSTEM_REVERSE[" "]
    for code in range(0x21, 0x7F):
        mapping[code] = SYSTEM_REVERSE[chr(code)]

    routine_area = rom[
        BATTLE_RENDER_ROUTINE_OFFSET : BATTLE_RENDER_ROUTINE_OFFSET + len(routine)
    ]
    table_area = rom[
        BATTLE_RENDER_TABLE_OFFSET : BATTLE_RENDER_TABLE_OFFSET + len(mapping)
    ]
    if any(value != 0xFF for value in routine_area + table_area):
        raise ValueError("ENG v1.0 battle-fix expansion area is not empty")

    rom[BATTLE_RENDER_HOOK_OFFSET : BATTLE_RENDER_HOOK_OFFSET + 4] = bytes.fromhex(
        "22 00 20 E8"  # JSL $E82000
    )
    rom[
        BATTLE_RENDER_ROUTINE_OFFSET : BATTLE_RENDER_ROUTINE_OFFSET + len(routine)
    ] = routine
    rom[
        BATTLE_RENDER_TABLE_OFFSET : BATTLE_RENDER_TABLE_OFFSET + len(mapping)
    ] = mapping


def install_landstalker_font(
    rom: bytearray, landstalker_rom: bytes
) -> set[str]:
    """Install exact glyphs and fit-safe spacing."""
    glyphs = extract_landstalker_font(landstalker_rom)
    imported: set[str] = set()
    for character, glyph in glyphs.items():
        if len(character) == 1 and 0x20 <= ord(character) <= 0x7E:
            start = DIALOGUE_FONT_BASE + ord(character) * BYTES_PER_GLYPH
            rom[start : start + BYTES_PER_GLYPH] = glyph
            imported.add(character)

    expected_spacing = b"\x0B\x00"
    actual_spacing = bytes(
        rom[
            SPACE_ADVANCE_IMMEDIATE_OFFSET : SPACE_ADVANCE_IMMEDIATE_OFFSET + 2
        ]
    )
    if actual_spacing != expected_spacing:
        raise ValueError(
            "Unexpected Lady Stalker space-advance instruction: "
            f"expected {expected_spacing.hex()}, found {actual_spacing.hex()}"
        )
    rom[
        SPACE_ADVANCE_IMMEDIATE_OFFSET : SPACE_ADVANCE_IMMEDIATE_OFFSET + 2
    ] = b"\x06\x00"

    return imported


def selected_text(row: dict[str, str]) -> str:
    professional = row["professional_translation"]
    return professional if professional != "" else row["machine_english_reference"]


def compile_main(text: str) -> bytes:
    if text == "<EMPTY>":
        return b"\xC0"
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    output = bytearray()
    index = 0
    while index < len(text):
        character = text[index]
        if character == "\n":
            output.append(0xC8)
            index += 1
            continue
        if character == "<":
            close = text.find(">", index + 1)
            if close >= 0:
                token = text[index : close + 1]
                if token in TAG_TO_CODE:
                    output.append(TAG_TO_CODE[token])
                    index = close + 1
                    continue
                if token.startswith(("<CTRL_", "<GLYPH_")):
                    raise ValueError(f"Unsupported raw token {token}")
        if character == " ":
            output.append(0x01)
        elif 0x21 <= ord(character) <= 0x7E:
            output.append(ord(character))
        else:
            raise ValueError(f"Character {character!r} is not present in the ENG v1.0 dialogue font")
        index += 1
    output.append(0xC0)
    return bytes(output)


def compile_system(text: str) -> bytes:
    if text == "<EMPTY>":
        return b""
    output = bytearray()
    for character in text:
        try:
            output.append(SYSTEM_REVERSE[character])
        except KeyError as error:
            raise ValueError(
                f"Character {character!r} is not present in the ENG v1.0 system font"
            ) from error
    return bytes(output)


def essential_controls(raw: bytes) -> tuple[int, ...]:
    return tuple(code for code in raw if code in STRUCTURAL_CONTROLS)


def read_rows(path: Path, expected_count: int, label: str) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, dialect="excel-tab"))
    if len(rows) != expected_count:
        raise ValueError(f"Expected {expected_count} {label} rows, got {len(rows)}")
    return rows


def file_to_cpu(offset: int) -> int:
    return ((0xC0 + offset // 0x10000) << 16) | (offset & 0xFFFF)


def pack_main(rom: bytearray, records: list[bytes]) -> tuple[int, int]:
    if any(value != 0xFF for value in rom[SCRIPT_START:SCRIPT_END]):
        raise ValueError("Reserved EB-EF script banks are not empty in this patched ROM")
    position = SCRIPT_START
    for ordinal, raw in enumerate(records):
        if len(raw) > 0x10000:
            raise ValueError(f"Message {ordinal} is too long for one ROM bank")
        bank_end = (position & ~0xFFFF) + 0x10000
        if position + len(raw) > bank_end:
            position = bank_end
        if position + len(raw) > SCRIPT_END:
            raise ValueError("Professional script exceeds the reserved EB-EF capacity")
        rom[position : position + len(raw)] = raw
        pointer = file_to_cpu(position)
        entry = patch.POINTER_TABLE + ordinal * 3
        rom[entry : entry + 3] = bytes(
            (pointer & 0xFF, (pointer >> 8) & 0xFF, (pointer >> 16) & 0xFF)
        )
        position += len(raw)
    return SCRIPT_START, position


def pack_byte_lookups(rom: bytearray, records: list[bytes], old_end: int) -> tuple[int, int]:
    payload = bytearray()
    for index, raw in enumerate(records):
        size = len(raw) + 2
        if size > 0xFF:
            raise ValueError(f"Byte lookup {index} is too long")
        payload += bytes((size,)) + raw + b"\xFF"
    end = patch.BYTE_LOOKUP_BASE + len(payload)
    if end > BYTE_LOOKUP_LIMIT:
        raise ValueError("Byte lookup table overlaps the F5 helper data/code")
    clear_end = max(old_end, end)
    rom[patch.BYTE_LOOKUP_BASE:clear_end] = b"\xFF" * (clear_end - patch.BYTE_LOOKUP_BASE)
    rom[patch.BYTE_LOOKUP_BASE:end] = payload
    return patch.BYTE_LOOKUP_BASE, end


def pack_word_lookups(rom: bytearray, records: list[bytes], old_end: int) -> tuple[int, int]:
    payload = bytearray()
    for index, raw in enumerate(records):
        size = 1 + 2 * (len(raw) + 1)
        if size > 0xFF:
            raise ValueError(f"Word lookup {index} is too long")
        payload.append(size)
        for code in raw:
            payload += code.to_bytes(2, "little")
        payload += (0x1C0).to_bytes(2, "little")
    end = patch.WORD_LOOKUP_BASE + len(payload)
    if end > WORD_LOOKUP_LIMIT:
        raise ValueError("Word lookup table overlaps the F6 helper data/code")
    clear_end = max(old_end, end)
    rom[patch.WORD_LOOKUP_BASE:clear_end] = b"\xFF" * (clear_end - patch.WORD_LOOKUP_BASE)
    rom[patch.WORD_LOOKUP_BASE:end] = payload
    return patch.WORD_LOOKUP_BASE, end


def update_checksum(rom: bytearray) -> tuple[int, int]:
    rom[CHECKSUM_OFFSET : CHECKSUM_OFFSET + 4] = b"\x00\x00\x00\x00"
    # The final checksum and complement bytes contribute 510 to the byte sum.
    checksum = (sum(rom) + 510) & 0xFFFF
    complement = checksum ^ 0xFFFF
    rom[CHECKSUM_OFFSET : CHECKSUM_OFFSET + 2] = complement.to_bytes(2, "little")
    rom[CHECKSUM_OFFSET + 2 : CHECKSUM_OFFSET + 4] = checksum.to_bytes(2, "little")
    if sum(rom) & 0xFFFF != checksum:
        raise ValueError("Internal SNES checksum verification failed")
    return complement, checksum


def write_ips(base: bytes, target: bytes, output: Path) -> int:
    if len(base) != len(target):
        raise ValueError("Overlay IPS requires equal-size source and target ROMs")
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
    parser.add_argument("patched_rom", type=Path)
    parser.add_argument("script_workspace", type=Path)
    parser.add_argument("lookup_workspace", type=Path)
    parser.add_argument("--output-ips", type=Path, required=True)
    parser.add_argument("--output-rom", type=Path)
    parser.add_argument(
        "--landstalker-rom",
        type=Path,
        help=(
            "optional exact Landstalker USA ROM; imports its dialogue font, "
            "enables fit-safe spacing, and fixes ENG v1.0 battle notices"
        ),
    )
    parser.add_argument(
        "--fix-battle-messages",
        action="store_true",
        help=(
            "fix ENG v1.0's direct-English 8x8 battle notices without "
            "changing the dialogue font; implied by --landstalker-rom"
        ),
    )
    parser.add_argument(
        "--allow-control-changes",
        action="store_true",
        help="permit changes to runtime inserts, waits, speaker, clear, and pause controls",
    )
    args = parser.parse_args()

    base = args.patched_rom.read_bytes()
    digest = hashlib.sha256(base).hexdigest()
    if len(base) != patch.PATCHED_ROM_SIZE or digest != patch.PATCHED_ROM_SHA256:
        raise SystemExit("Unsupported base; apply Lady_Stalker_ENG_v10.ips first")

    landstalker_rom = None
    if args.landstalker_rom:
        landstalker_rom = checked_read(
            args.landstalker_rom,
            LANDSTALKER_SIZE,
            LANDSTALKER_SHA256,
            "Landstalker USA ROM",
        )

    script_rows = read_rows(args.script_workspace, patch.MESSAGE_COUNT, "script")
    lookup_rows = read_rows(
        args.lookup_workspace,
        patch.BYTE_LOOKUP_COUNT + patch.WORD_LOOKUP_COUNT,
        "lookup",
    )

    main_records: list[bytes] = []
    changed_messages = 0
    for ordinal, row in enumerate(script_rows):
        expected_id = f"0x{ordinal // 256:02X}{ordinal % 256:02X}"
        if row["message_id"] != expected_id:
            raise ValueError(f"Script row {ordinal} has ID {row['message_id']}, expected {expected_id}")
        reference = compile_main(row["machine_english_reference"])
        selected = compile_main(selected_text(row))
        if not args.allow_control_changes and essential_controls(reference) != essential_controls(selected):
            raise ValueError(
                f"Message {row['message_id']} changes structural controls; "
                "restore its tags or use --allow-control-changes"
            )
        changed_messages += selected != reference
        main_records.append(selected)

    byte_records: list[bytes] = []
    word_records: list[bytes] = []
    changed_lookups = 0
    for ordinal, row in enumerate(lookup_rows):
        expected_table = "byte" if ordinal < patch.BYTE_LOOKUP_COUNT else "word"
        if row["table"] != expected_table:
            raise ValueError(f"Lookup row {ordinal} is out of order")
        reference = compile_system(row["machine_english_reference"])
        selected = compile_system(selected_text(row))
        changed_lookups += selected != reference
        (byte_records if expected_table == "byte" else word_records).append(selected)

    old_byte_records, old_byte_end = patch.extract_byte_lookups(base)
    old_word_records, old_word_end = patch.extract_word_lookups(base)
    if len(old_byte_records) != len(byte_records) or len(old_word_records) != len(word_records):
        raise ValueError("Lookup count mismatch")

    output_rom = bytearray(base)
    script_start, script_end = pack_main(output_rom, main_records)
    byte_start, byte_end = pack_byte_lookups(output_rom, byte_records, old_byte_end)
    word_start, word_end = pack_word_lookups(output_rom, word_records, old_word_end)

    imported_glyphs: set[str] = set()
    font_fallbacks_used = ""
    if landstalker_rom is not None:
        imported_glyphs = install_landstalker_font(output_rom, landstalker_rom)
        used_ascii = {
            chr(code)
            for raw in main_records
            for code in raw
            if 0x20 <= code <= 0x7E
        }
        font_fallbacks_used = "".join(sorted(used_ascii - imported_glyphs))

    battle_renderer_fix = args.fix_battle_messages or landstalker_rom is not None
    if battle_renderer_fix:
        install_battle_renderer_fix(output_rom)

    complement, checksum = update_checksum(output_rom)

    record_count = write_ips(base, bytes(output_rom), args.output_ips)
    if args.output_rom:
        args.output_rom.parent.mkdir(parents=True, exist_ok=True)
        args.output_rom.write_bytes(output_rom)

    result = {
        "base_sha256": digest,
        "output_sha256": hashlib.sha256(output_rom).hexdigest(),
        "changed_messages": changed_messages,
        "changed_lookups": changed_lookups,
        "landstalker_addon": landstalker_rom is not None,
        "landstalker_glyphs_imported": len(imported_glyphs),
        "landstalker_font_fallbacks_used": font_fallbacks_used,
        "battle_renderer_fix": battle_renderer_fix,
        "script_cpu_range": f"EB:0000-{file_to_cpu(script_end):06X}",
        "script_bytes_with_bank_padding": script_end - script_start,
        "byte_lookup_file_range": f"0x{byte_start:06X}-0x{byte_end:06X}",
        "word_lookup_file_range": f"0x{word_start:06X}-0x{word_end:06X}",
        "checksum": f"0x{checksum:04X}",
        "checksum_complement": f"0x{complement:04X}",
        "ips_records": record_count,
        "ips_bytes": args.output_ips.stat().st_size,
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
