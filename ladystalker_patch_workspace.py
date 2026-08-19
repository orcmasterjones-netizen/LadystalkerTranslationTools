#!/usr/bin/env python3
"""Build translator workspaces from Lady Stalker JP and ENG v1.0 ROMs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import ladystalker_extract as jp


PATCHED_ROM_SIZE = 0x400000
PATCHED_ROM_SHA256 = "3a698798b844e248cd3cf612941d18d1837bc6af1805df18b6eff609bc97e3cf"
POINTER_TABLE = 0x281000  # CPU E8:1000
MESSAGE_COUNT = sum(jp.GROUP_COUNTS)
POINTER_ENTRY_COUNT = 1235
BYTE_LOOKUP_BASE = 0x350000  # CPU F5:0000
BYTE_LOOKUP_COUNT = 352
WORD_LOOKUP_BASE = 0x360000  # CPU F6:0000
WORD_LOOKUP_COUNT = 6

ENGLISH_CONTROLS = {
    0xC0: "END",
    0xC1: "NOP",
    0xC2: "NUMBER",
    0xC3: "LINE",
    0xC4: "INSERT_A",
    0xC5: "WAIT",
    0xC6: "PAUSE_60_A",
    0xC7: "PAUSE_30_A",
    0xC8: "NEWLINE",
    0xC9: "WAIT_INPUT",
    0xCA: "INSERT_B",
    0xCB: "PAUSE_60",
    0xCC: "SPEAKER",
    0xCD: "PAUSE_30",
    0xCE: "INSERT_C",
    0xCF: "INSERT_D",
    0xD0: "CLEAR",
    0xD1: "INSERT_BUFFER",
}


def build_system_charset() -> dict[int, str]:
    """Character codes used by names/items and the patched 8x8 font."""
    table = {0x01: " ", 0x0C: "L", 0x0D: "S", 0x0E: "P", 0x0F: "Y"}
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
    return table


SYSTEM_CHARSET = build_system_charset()


@dataclass(frozen=True)
class EnglishMessage:
    ordinal: int
    cpu_pointer: int
    file_offset: int
    raw: bytes
    text: str

    @property
    def group(self) -> int:
        return self.ordinal >> 8

    @property
    def index(self) -> int:
        return self.ordinal & 0xFF


def cpu_to_file(pointer: int) -> int:
    return ((pointer >> 16) & 0x3F) * 0x10000 + (pointer & 0xFFFF)


def render_main(raw: bytes) -> str:
    pieces: list[str] = []
    for code in raw:
        if code == 0xC0:
            break
        if code == 0x01:
            pieces.append(" ")
        elif code == 0xC8:
            pieces.append("\n")
        elif code == 0xD0:
            pieces.append("<CLEAR>")
        elif code == 0xC3:
            pieces.append("<LINE>")
        elif code >= 0xC0:
            pieces.append(f"<{ENGLISH_CONTROLS.get(code, f'CTRL_{code:02X}') }>")
        elif 0x20 <= code <= 0x7E:
            pieces.append(chr(code))
        else:
            pieces.append(f"<GLYPH_{code:02X}>")
    return "".join(pieces)


def extract_main(rom: bytes) -> list[EnglishMessage]:
    messages: list[EnglishMessage] = []
    for ordinal in range(POINTER_ENTRY_COUNT):
        entry = POINTER_TABLE + ordinal * 3
        pointer = int.from_bytes(rom[entry : entry + 2], "little") | rom[entry + 2] << 16
        if ordinal >= MESSAGE_COUNT:
            if pointer != 0xFFFFFF:
                raise ValueError(f"Expected fallback pointer at ordinal {ordinal}, got {pointer:06X}")
            continue
        if pointer == 0xFFFFFF:
            raise ValueError(f"Missing English pointer at ordinal {ordinal}")
        offset = cpu_to_file(pointer)
        end = rom.find(b"\xC0", offset, min(len(rom), offset + 0x10000))
        if end < 0:
            raise ValueError(f"No END byte for English message {ordinal}")
        raw = rom[offset : end + 1]
        messages.append(EnglishMessage(ordinal, pointer, offset, raw, render_main(raw)))
    if len(messages) != MESSAGE_COUNT:
        raise ValueError("English message count mismatch")
    return messages


def render_system(raw: bytes) -> str:
    return "".join(SYSTEM_CHARSET.get(code, f"<GLYPH_{code:02X}>") for code in raw)


def extract_byte_lookups(rom: bytes) -> tuple[list[tuple[bytes, str]], int]:
    records: list[tuple[bytes, str]] = []
    offset = BYTE_LOOKUP_BASE
    for index in range(BYTE_LOOKUP_COUNT):
        size = rom[offset]
        end = offset + size
        if size < 2 or end > len(rom) or rom[end - 1] != 0xFF:
            raise ValueError(f"Invalid patched byte lookup {index} at 0x{offset:06X}")
        raw = rom[offset + 1 : end - 1]
        records.append((raw, render_system(raw)))
        offset = end
    return records, offset


def extract_word_lookups(rom: bytes) -> tuple[list[tuple[tuple[int, ...], str]], int]:
    records: list[tuple[tuple[int, ...], str]] = []
    offset = WORD_LOOKUP_BASE
    for index in range(WORD_LOOKUP_COUNT):
        size = rom[offset]
        end = offset + size
        if size < 3 or not size & 1 or end > len(rom):
            raise ValueError(f"Invalid patched word lookup {index} at 0x{offset:06X}")
        raw = tuple(int.from_bytes(rom[pos : pos + 2], "little") for pos in range(offset + 1, end, 2))
        if not raw or raw[-1] != 0x1C0:
            raise ValueError(f"Patched word lookup {index} has no END code")
        records.append((raw, render_system(bytes(raw[:-1]))))
        offset = end
    return records, offset


def control_signature(raw: bytes) -> str:
    return " ".join(ENGLISH_CONTROLS.get(code, f"CTRL_{code:02X}") for code in raw if code >= 0xC0)


def write_script_workspace(
    japanese: list[jp.Message], english: list[EnglishMessage], output: Path
) -> None:
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, dialect="excel-tab", lineterminator="\n")
        writer.writerow(
            [
                "group",
                "index",
                "message_id",
                "japanese",
                "machine_english_reference",
                "professional_translation",
                "translator_notes",
                "control_signature",
                "english_cpu_pointer",
                "english_bytes",
                "japanese_symbols",
            ]
        )
        for source, reference in zip(japanese, english, strict=True):
            writer.writerow(
                [
                    f"{source.group:02X}",
                    f"{source.index:02X}",
                    f"0x{source.message_id:04X}",
                    jp.render_codes(source.codes),
                    reference.text,
                    "",
                    "",
                    control_signature(reference.raw),
                    f"{reference.cpu_pointer >> 16:02X}:{reference.cpu_pointer & 0xFFFF:04X}",
                    " ".join(f"{code:02X}" for code in reference.raw),
                    " ".join(f"{code:03X}" for code in source.codes),
                ]
            )


def write_lookup_workspace(
    japanese: list[jp.LookupString],
    english_byte: list[tuple[bytes, str]],
    english_word: list[tuple[tuple[int, ...], str]],
    output: Path,
) -> None:
    references = [text for _, text in english_byte] + [text for _, text in english_word]
    raws = [" ".join(f"{code:02X}" for code in raw) for raw, _ in english_byte]
    raws += [" ".join(f"{code:03X}" for code in raw) for raw, _ in english_word]
    if len(japanese) != len(references):
        raise ValueError("Lookup table count mismatch")
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, dialect="excel-tab", lineterminator="\n")
        writer.writerow(
            [
                "table",
                "index",
                "category",
                "japanese",
                "machine_english_reference",
                "professional_translation",
                "translator_notes",
                "english_raw_codes",
            ]
        )
        for source, reference, raw in zip(japanese, references, raws, strict=True):
            writer.writerow(
                [
                    source.table,
                    source.index,
                    source.category,
                    source.text,
                    reference,
                    "",
                    "",
                    raw,
                ]
            )


def write_machine_dump(
    main: list[EnglishMessage],
    byte_lookups: list[tuple[bytes, str]],
    word_lookups: list[tuple[tuple[int, ...], str]],
    output: Path,
) -> None:
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("Lady Stalker ENG v1.0 machine-translation reference dump\n")
        handle.write(f"Patched ROM SHA-256: {PATCHED_ROM_SHA256}\n")
        handle.write(f"Messages: {len(main)}\nLookup strings: {len(byte_lookups) + len(word_lookups)}\n\n")
        for message in main:
            handle.write(
                f"===== MSG {message.group:02X}:{message.index:02X} "
                f"(E{message.cpu_pointer >> 16 & 0xF:X}:{message.cpu_pointer & 0xFFFF:04X}, "
                f"{len(message.raw)} bytes) =====\n{message.text}\n\n"
            )
        handle.write("===== LOOKUP STRINGS =====\n\n")
        for index, (_, text) in enumerate(byte_lookups):
            category = "entity/name" if index < 226 else "item/name"
            handle.write(f"--- BYTE {index:03d} ({category}) ---\n{text or '<EMPTY>'}\n\n")
        for index, (_, text) in enumerate(word_lookups):
            handle.write(f"--- WORD {index:03d} (dynamic phrase) ---\n{text or '<EMPTY>'}\n\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("japanese_rom", type=Path)
    parser.add_argument("patched_rom", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    args = parser.parse_args()

    japanese_rom = args.japanese_rom.read_bytes()
    patched_rom = args.patched_rom.read_bytes()
    if len(japanese_rom) != jp.ROM_SIZE or hashlib.sha256(japanese_rom).hexdigest() != jp.ROM_SHA256:
        raise SystemExit("Unsupported Japanese ROM revision")
    if len(patched_rom) != PATCHED_ROM_SIZE or hashlib.sha256(patched_rom).hexdigest() != PATCHED_ROM_SHA256:
        raise SystemExit("Unsupported patched ROM; expected Lady Stalker ENG v1.0")

    japanese_messages = jp.decode_messages(japanese_rom)
    japanese_lookups = jp.decode_lookup_strings(japanese_rom)
    english_messages = extract_main(patched_rom)
    byte_lookups, byte_end = extract_byte_lookups(patched_rom)
    word_lookups, word_end = extract_word_lookups(patched_rom)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_script_workspace(
        japanese_messages,
        english_messages,
        args.out_dir / "ladystalker_script_workspace.tsv",
    )
    write_lookup_workspace(
        japanese_lookups,
        byte_lookups,
        word_lookups,
        args.out_dir / "ladystalker_lookup_workspace.tsv",
    )
    write_machine_dump(
        english_messages,
        byte_lookups,
        word_lookups,
        args.out_dir / "ladystalker_machine_english_text.txt",
    )
    patch_map = {
        "patched_rom_sha256": PATCHED_ROM_SHA256,
        "message_count": len(english_messages),
        "pointer_table": {"file_offset": "0x281000", "cpu_address": "E8:1000", "entries": 1235},
        "fallback_pointer_entries": {"count": 15, "ids": "04:C4-04:D2", "value": "FF:FFFF"},
        "message_storage": [
            {"cpu_range": "EA:0CF8-EA:FFF6", "messages": 909, "bytes": 62206},
            {"cpu_range": "E9:4000-E9:B78A", "messages": 311, "bytes": 30602},
        ],
        "message_bytes_total": sum(len(message.raw) for message in english_messages),
        "byte_lookup": {"cpu_range": f"F5:0000-F5:{byte_end & 0xFFFF:04X}", "records": 352},
        "word_lookup": {"cpu_range": f"F6:0000-F6:{word_end & 0xFFFF:04X}", "records": 6},
        "dialogue_font_base": {"file_offset": "0x290000", "cpu_address": "E9:0000"},
    }
    (args.out_dir / "ladystalker_patch_map.json").write_text(
        json.dumps(patch_map, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {len(english_messages)} paired messages and "
        f"{len(japanese_lookups)} paired lookup strings."
    )


if __name__ == "__main__":
    main()
