"""
Минимальный PNG-кодер (stdlib only): RGB / RGBA / grayscale, 8 бит, filter 0/1/2.
Нужен движку, чтобы выдавать картинку без единой внешней зависимости.
"""

from __future__ import annotations

import struct
import zlib
from typing import Sequence

_SIG = b"\x89PNG\r\n\x1a\n"
_COLOR_TYPES = {1: 0, 2: 4, 3: 2, 4: 6}   # channels -> PNG colour type


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def encode_png(width: int, height: int, rgba: Sequence[int], level: int = 9) -> bytes:
    """rgba -- плоский массив байт R,G,B,A длиной w*h*4."""
    if len(rgba) != width * height * 4:
        raise ValueError(f"ожидалось {width * height * 4} байт, дано {len(rgba)}")
    stride = width * 4
    rows = bytearray()
    prev = bytes(stride)
    src = bytes(rgba)
    for y in range(height):
        line = src[y * stride:(y + 1) * stride]
        # выбираем фильтр с минимальной суммой абсолютных отклонений (эвристика PNG)
        best, best_score = 0, None
        for f in (0, 1, 2):
            if f == 0:
                out = line
            elif f == 1:
                out = bytes([line[i] - (line[i - 4] if i >= 4 else 0) & 0xFF for i in range(stride)])
            else:
                out = bytes([line[i] - prev[i] & 0xFF for i in range(stride)])
            score = sum(b if b < 128 else 256 - b for b in out)
            if best_score is None or score < best_score:
                best, best_score = f, score
                best_out = out
        rows.append(best)
        rows += best_out
        prev = line
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (_SIG + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(rows), level))
            + _chunk(b"IEND", b""))


def encode_gray_png(width: int, height: int, gray: Sequence[int], level: int = 9) -> bytes:
    stride = width
    rows = bytearray()
    src = bytes(gray)
    for y in range(height):
        rows.append(0)
        rows += src[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return (_SIG + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(rows), level))
            + _chunk(b"IEND", b""))


def write_png(path: str, width: int, height: int, rgba: Sequence[int]) -> str:
    with open(path, "wb") as fh:
        fh.write(encode_png(width, height, rgba))
    return path
