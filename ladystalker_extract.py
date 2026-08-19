#!/usr/bin/env python3
"""Extract the complete compressed message bank from Lady Stalker (SFC, Japan).

This extractor is for the headerless No-Intro ROM whose SHA-256 is recorded in
ROM_SHA256.  It decodes the game's context-adaptive 9-bit Huffman stream and
maps proportional-font glyph IDs to Unicode.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


ROM_SHA256 = "d0275f6fdc38f26b53b017bdd7fe26e13b9871a93671c76f48800e4f733b2385"
ROM_SIZE = 0x280000
TREE_BASE = 0x0201AA
TEXT_BASE = 0x022287
TEXT_END = 0x02A2D4
# The fifth group has 196 messages.  Bytes at 0x02A2D4 and later are 65C816
# program code, not additional compressed records.  This boundary is also
# independently confirmed by the v1.0 English patch's 1,220-entry pointer set.
GROUP_COUNTS = (256, 256, 256, 256, 196)
INITIAL_CONTEXT = 0x1C0
END_CODE = 0x1C0
BYTE_LOOKUP_BASE = 0x0D8091
BYTE_LOOKUP_END = 0x0D8B8B
WORD_LOOKUP_BASE = 0x0D91CA
WORD_LOOKUP_END = 0x0D9212


def build_glyph_table() -> dict[int, str]:
    table: dict[int, str] = {
        0x000: "",
        0x001: " ",
        0x00C: "L",
        0x00D: "S",
        0x00E: "P",
        0x00F: "Y",
        0x089: "※",
    }
    for index, character in enumerate("0123456789", 0x002):
        table[index] = character

    rows = {
        0x010: "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんっゃゅょ",
        0x042: "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンッャュョァィェォー?!ぁぃ「」ぅぇ・ぉ",
        0x08A: "島物城行入説見人伝何金宝古来書気魔生北石化代話中売館博場聞昔買世査審大情報一旅行水屋活悪目学下方言険千真側明娘写装前備天賞道発町年武巨名多謎歩連子持心地死墓嬢様部考神実芸内音券自間食研史究財鏡歴国銀奥命秘体外遠験以受作不先続誰取感客解立引料紀界苦高出力付商才鉱山戦声思火預用囚交枚換噴読落録記掘炉会寄日泊教使具基申玉上店器品主呪通所十意敵印封返官毒強息本兵土帰度乗休白残営早全護板父観光民能寝長深今防文字塔王空法岩像建正知進役階図家海由時理然口風回術待分刻AB",
        0x175: "殿領手変利難覚花樹逆倍黒愛宿経探熱効維巻二最復過去単仕男絵勝謝位掛異新流値匠船題耳色置",
        0x1A4: "果続後岬埋好奇向集宮司",
        0x1B0: "村産沿員士急迷台遺頭身脳冬眠悲惨",
    }
    for start, characters in rows.items():
        for index, character in enumerate(characters, start):
            table[index] = character

    # These glyphs are pictures or deliberately unused font cells.
    for glyph_id in range(0x1C0):
        table.setdefault(glyph_id, f"<GLYPH_{glyph_id:03X}>")
    for glyph_id in (0x170, 0x171, 0x172, 0x173, 0x174, 0x1AF):
        table[glyph_id] = f"<ICON_{glyph_id:03X}>"
    table.update({0x1A0: "↘", 0x1A1: "↖", 0x1A2: "↙", 0x1A3: "↗"})
    return table


GLYPHS = build_glyph_table()
COMBINING_MARKS = {0x083: "\u309a", 0x084: "\u3099"}  # handakuten, dakuten
CONTROL_NAMES = {
    0x1C0: "END",
    0x1C1: "NOP",
    0x1C2: "NUMBER",
    0x1C3: "LINE",
    0x1C4: "INSERT_A",
    0x1C5: "WAIT",
    0x1C6: "PAUSE_60_A",
    0x1C7: "PAUSE_30_A",
    0x1C8: "NEWLINE",
    0x1C9: "WAIT_INPUT",
    0x1CA: "INSERT_B",
    0x1CB: "PAUSE_60",
    0x1CC: "SPEAKER",
    0x1CD: "PAUSE_30",
    0x1CE: "INSERT_C",
    0x1CF: "INSERT_D",
    0x1D0: "CLEAR",
    0x1D1: "INSERT_BUFFER",
}


@dataclass(frozen=True)
class Message:
    group: int
    index: int
    prefix_offset: int
    data_offset: int
    compressed_length: int
    bits_consumed: int
    codes: tuple[int, ...]

    @property
    def message_id(self) -> int:
        return (self.group << 8) | self.index


@dataclass(frozen=True)
class LookupString:
    table: str
    index: int
    category: str
    prefix_offset: int
    data_offset: int
    stored_length: int
    raw_symbols: tuple[int, ...]
    text: str


class Decoder:
    def __init__(self, rom: bytes):
        self.rom = rom

    def rom_bit(self, offset: int, bit_index: int) -> int:
        return (self.rom[offset + bit_index // 8] >> (7 - bit_index % 8)) & 1

    @lru_cache(maxsize=None)
    def model(self, context: int):
        pointer_offset = TREE_BASE + context * 2
        model_offset = int.from_bytes(self.rom[pointer_offset : pointer_offset + 2], "little")
        if model_offset == 0xFFFF:
            raise ValueError(f"No Huffman model for context 0x{context:03X}")

        topology_bit = 0
        leaf_count = 0

        def parse_node():
            nonlocal topology_bit, leaf_count
            value = self.rom_bit(TREE_BASE + model_offset, topology_bit)
            topology_bit += 1
            if value:
                leaf_number = leaf_count
                leaf_count += 1
                return leaf_number
            return (parse_node(), parse_node())

        root = parse_node()
        leaves: list[int] = []
        for leaf_number in range(leaf_count):
            byte_distance, shift = divmod(leaf_number * 9, 8)
            x = model_offset - byte_distance
            word = int.from_bytes(self.rom[TREE_BASE - 2 + x : TREE_BASE + x], "little")
            word = ((word & 0xFF) << 8) | (word >> 8)
            leaves.append((word >> shift) & 0x1FF)
        return root, tuple(leaves)

    def decode(self, data_offset: int) -> tuple[tuple[int, ...], int]:
        bit_index = 0
        context = INITIAL_CONTEXT
        output: list[int] = []
        while True:
            root, leaves = self.model(context)
            node = root
            while isinstance(node, tuple):
                if data_offset + bit_index // 8 >= TEXT_END:
                    raise ValueError("Compressed message ran beyond the verified text bank")
                branch = self.rom_bit(data_offset, bit_index)
                bit_index += 1
                node = node[branch]
            context = leaves[node]
            output.append(context)
            if context == END_CODE:
                return tuple(output), bit_index
            if len(output) > 4096:
                raise ValueError("Compressed message exceeded the safety limit")


def decode_messages(rom: bytes) -> list[Message]:
    decoder = Decoder(rom)
    group_offsets = [int.from_bytes(rom[TEXT_BASE + n * 2 : TEXT_BASE + n * 2 + 2], "little") for n in range(5)]
    messages: list[Message] = []
    for group, count in enumerate(GROUP_COUNTS):
        prefix_offset = TEXT_BASE + group_offsets[group]
        for index in range(count):
            compressed_length = rom[prefix_offset]
            data_offset = prefix_offset + 1
            codes, bits_consumed = decoder.decode(data_offset)
            messages.append(
                Message(group, index, prefix_offset, data_offset, compressed_length, bits_consumed, codes)
            )
            prefix_offset += compressed_length + 1
        if group < len(GROUP_COUNTS) - 1:
            expected = TEXT_BASE + group_offsets[group + 1]
            if prefix_offset != expected:
                raise ValueError(f"Group {group} ended at 0x{prefix_offset:X}, expected 0x{expected:X}")
    if prefix_offset != TEXT_END:
        raise ValueError(f"Text bank ended at 0x{prefix_offset:X}, expected 0x{TEXT_END:X}")
    return messages


def render_codes(codes: tuple[int, ...]) -> str:
    pieces: list[str] = []
    pending_mark = ""

    def emit(text: str) -> None:
        nonlocal pending_mark
        if pending_mark:
            text = unicodedata.normalize("NFC", text + pending_mark)
            pending_mark = ""
        pieces.append(text)

    for code in codes:
        if code == END_CODE:
            break
        if code in COMBINING_MARKS:
            if pending_mark:
                pieces.append(pending_mark)
            pending_mark = COMBINING_MARKS[code]
            continue
        if code < 0x1C0:
            emit(GLYPHS[code])
            continue

        if pending_mark:
            pieces.append(pending_mark)
            pending_mark = ""
        if code in (0x1C3, 0x1C8):
            pieces.append("\n")
        elif code == 0x1CC:
            pieces.append("<SPEAKER>「")
        elif code == 0x1D0:
            pieces.append("\n<CLEAR>\n")
        else:
            pieces.append(f"<{CONTROL_NAMES.get(code, f'CTRL_{code:03X}')}>")

    if pending_mark:
        pieces.append(pending_mark)
    return "".join(pieces).strip("\n")


def render_byte_codes(codes: tuple[int, ...]) -> str:
    pieces: list[str] = []
    pending_mark = ""
    for code in codes:
        if code in COMBINING_MARKS:
            pending_mark = COMBINING_MARKS[code]
            continue
        character = GLYPHS.get(code, f"<BYTE_{code:02X}>")
        if pending_mark:
            character = unicodedata.normalize("NFC", character + pending_mark)
            pending_mark = ""
        pieces.append(character)
    if pending_mark:
        pieces.append(pending_mark)
    return "".join(pieces)


def decode_lookup_strings(rom: bytes) -> list[LookupString]:
    strings: list[LookupString] = []

    offset = BYTE_LOOKUP_BASE
    index = 0
    while offset < BYTE_LOOKUP_END:
        stored_length = rom[offset]
        end = offset + stored_length
        if stored_length < 2 or end > BYTE_LOOKUP_END or rom[end - 1] != 0xFF:
            raise ValueError(f"Invalid byte lookup record at 0x{offset:X}")
        symbols = tuple(rom[offset + 1 : end - 1])
        category = "entity/name" if index < 226 else "item/name"
        strings.append(
            LookupString(
                "byte",
                index,
                category,
                offset,
                offset + 1,
                stored_length,
                symbols,
                render_byte_codes(symbols),
            )
        )
        offset = end
        index += 1
    if offset != BYTE_LOOKUP_END or index != 352:
        raise ValueError("Byte lookup table did not end at its verified boundary")

    offset = WORD_LOOKUP_BASE
    index = 0
    while offset < WORD_LOOKUP_END:
        stored_length = rom[offset]
        end = offset + stored_length
        if stored_length < 3 or not stored_length & 1 or end > WORD_LOOKUP_END:
            raise ValueError(f"Invalid word lookup record at 0x{offset:X}")
        symbols = tuple(
            int.from_bytes(rom[position : position + 2], "little")
            for position in range(offset + 1, end, 2)
        )
        if not symbols or symbols[-1] != END_CODE:
            raise ValueError(f"Word lookup record at 0x{offset:X} has no END code")
        strings.append(
            LookupString(
                "word",
                index,
                "dynamic phrase",
                offset,
                offset + 1,
                stored_length,
                symbols,
                render_codes(symbols),
            )
        )
        offset = end
        index += 1
    if offset != WORD_LOOKUP_END or index != 6:
        raise ValueError("Word lookup table did not end at its verified boundary")
    return strings


def write_text(messages: list[Message], lookup_strings: list[LookupString], output: Path) -> None:
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("Lady Stalker - Kako kara no Chousen (Japan)\n")
        handle.write("Complete engine text dump (UTF-8)\n")
        handle.write(f"ROM SHA-256: {ROM_SHA256}\n")
        handle.write(f"Messages: {len(messages)}\n")
        handle.write(f"Dynamic lookup strings: {len(lookup_strings)}\n\n")
        for message in messages:
            handle.write(
                f"===== MSG {message.group:02X}:{message.index:02X} "
                f"(ID 0x{message.message_id:04X}, ROM 0x{message.data_offset:06X}, "
                f"{message.compressed_length} bytes) =====\n"
            )
            handle.write(render_codes(message.codes))
            handle.write("\n\n")

        handle.write("===== DYNAMIC LOOKUP STRINGS =====\n")
        handle.write("These names and short phrases are inserted by message control codes.\n\n")
        for string in lookup_strings:
            handle.write(
                f"--- {string.table.upper()} LOOKUP {string.index:03d} "
                f"({string.category}, ROM 0x{string.data_offset:06X}) ---\n"
            )
            handle.write(string.text if string.text else "<EMPTY>")
            handle.write("\n\n")


def write_tsv(messages: list[Message], output: Path) -> None:
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, dialect="excel-tab", lineterminator="\n")
        writer.writerow(
            [
                "group",
                "index",
                "message_id",
                "prefix_rom_offset",
                "data_rom_offset",
                "compressed_bytes",
                "bits_consumed",
                "symbol_count",
                "raw_symbols",
                "text",
            ]
        )
        for message in messages:
            writer.writerow(
                [
                    f"{message.group:02X}",
                    f"{message.index:02X}",
                    f"0x{message.message_id:04X}",
                    f"0x{message.prefix_offset:06X}",
                    f"0x{message.data_offset:06X}",
                    message.compressed_length,
                    message.bits_consumed,
                    len(message.codes),
                    " ".join(f"{code:03X}" for code in message.codes),
                    render_codes(message.codes),
                ]
            )


def write_glyphs(messages: list[Message], output: Path) -> None:
    usage = Counter(code for message in messages for code in message.codes if code < 0x1C0)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, dialect="excel-tab", lineterminator="\n")
        writer.writerow(["glyph_id", "unicode_or_tag", "usage_count"])
        for glyph_id in range(0x1C0):
            if glyph_id in COMBINING_MARKS:
                character = "COMBINING HANDAKUTEN" if glyph_id == 0x083 else "COMBINING DAKUTEN"
            else:
                character = GLYPHS[glyph_id]
            writer.writerow([f"0x{glyph_id:03X}", character, usage[glyph_id]])


def write_lookups(lookup_strings: list[LookupString], output: Path) -> None:
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, dialect="excel-tab", lineterminator="\n")
        writer.writerow(
            [
                "table",
                "index",
                "category",
                "prefix_rom_offset",
                "data_rom_offset",
                "stored_bytes",
                "raw_symbols",
                "text",
            ]
        )
        for string in lookup_strings:
            width = 2 if string.table == "word" else 1
            writer.writerow(
                [
                    string.table,
                    string.index,
                    string.category,
                    f"0x{string.prefix_offset:06X}",
                    f"0x{string.data_offset:06X}",
                    string.stored_length,
                    " ".join(f"{code:0{width * 2}X}" for code in string.raw_symbols),
                    string.text,
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path, help="headerless Japanese .sfc ROM")
    parser.add_argument("--out-dir", type=Path, default=Path("."))
    args = parser.parse_args()

    rom = args.rom.read_bytes()
    digest = hashlib.sha256(rom).hexdigest()
    if len(rom) != ROM_SIZE or digest != ROM_SHA256:
        raise SystemExit(
            "Unsupported ROM. Expected the headerless Japanese ROM:\n"
            f"  size: {ROM_SIZE} bytes\n"
            f"  SHA-256: {ROM_SHA256}\n"
            f"Got size {len(rom)} and SHA-256 {digest}."
        )

    messages = decode_messages(rom)
    lookup_strings = decode_lookup_strings(rom)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_text(messages, lookup_strings, args.out_dir / "ladystalker_japanese_text.txt")
    write_tsv(messages, args.out_dir / "ladystalker_japanese_text.tsv")
    write_glyphs(messages, args.out_dir / "ladystalker_glyph_table.tsv")
    write_lookups(lookup_strings, args.out_dir / "ladystalker_lookup_strings.tsv")
    print(
        f"Decoded {len(messages)} messages ({sum(len(m.codes) for m in messages):,} symbols) "
        f"and {len(lookup_strings)} lookup strings."
    )


if __name__ == "__main__":
    main()
