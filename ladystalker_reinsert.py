#!/usr/bin/env python3
"""Compile a professional Lady Stalker script into an ENG-v1.0 overlay IPS.

The output IPS targets the exact 4 MiB ROM produced by Lady_Stalker_ENG_v10.ips.
It contains only the replacement script, lookup tables, pointers, and checksum;
it does not contain the existing patch itself.
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

TAG_TO_CODE = {
    f"<{name}>": code
    for code, name in patch.ENGLISH_CONTROLS.items()
    if name not in ("END", "NEWLINE")
}
SYSTEM_REVERSE = {character: code for code, character in patch.SYSTEM_CHARSET.items()}
STRUCTURAL_CONTROLS = set(range(0xC1, 0xD2)) - {0xC3, 0xC8}


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
    checksum = sum(rom) & 0xFFFF
    complement = checksum ^ 0xFFFF
    rom[CHECKSUM_OFFSET : CHECKSUM_OFFSET + 2] = complement.to_bytes(2, "little")
    rom[CHECKSUM_OFFSET + 2 : CHECKSUM_OFFSET + 4] = checksum.to_bytes(2, "little")
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
        "--allow-control-changes",
        action="store_true",
        help="permit changes to runtime inserts, waits, speaker, clear, and pause controls",
    )
    args = parser.parse_args()

    base = args.patched_rom.read_bytes()
    digest = hashlib.sha256(base).hexdigest()
    if len(base) != patch.PATCHED_ROM_SIZE or digest != patch.PATCHED_ROM_SHA256:
        raise SystemExit("Unsupported base; apply Lady_Stalker_ENG_v10.ips first")

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
