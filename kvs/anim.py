"""
Экспорт анимации .kvs в популярные контейнеры -- снова только stdlib.

  * APNG  -- анимированный PNG (acTL/fcTL/fdAT), lossless, поддерживает альфу;
  * GIF   -- анимированный GIF с глобальной палитрой (median-cut, 256 цветов);
  * WEBM/MP4 -- не делаем: для этого есть ffmpeg, движок отдаёт ему PNG-секвенцию.
"""

from __future__ import annotations

import io
import math
import struct
import zlib
from typing import List, Sequence, Tuple

from .png import _chunk, _SIG
from .raster import Framebuffer


# --------------------------------------------------------------------------- #
#  APNG
# --------------------------------------------------------------------------- #
def write_apng(path: str, frames: Sequence[Tuple[int, Framebuffer]],
               fps: float | None = None, level: int = 9,
               default_fps: float = 30.0) -> str:
    """
    frames -- последовательность (index, Framebuffer).
    fps берётся из аргумента, иначе 30 (или общий для всех кадров).
    """
    items = [(fb) for _, fb in frames]
    if not items:
        raise ValueError("нет кадров для экспорта")
    w, h = items[0].w, items[0].h
    rate = fps or default_fps
    delay_den = 1000
    delay_num = int(round(delay_den / rate))
    if delay_num <= 0:
        delay_num, delay_den = 1, 1

    out = io.BytesIO()
    out.write(_SIG)
    out.write(_chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)))
    out.write(_chunk(b"acTL", struct.pack(">II", len(items), 0)))

    seq = 0
    for i, fb in enumerate(items):
        raw = _filtered_rows(fb)
        if i == 0:
            out.write(_chunk(b"fcTL", struct.pack(">IIIIIHHBB", seq, w, h, 0, 0,
                                                  delay_num, delay_den, 0, 0)))
            seq += 1
            out.write(_chunk(b"IDAT", zlib.compress(raw, level)))
        else:
            out.write(_chunk(b"fcTL", struct.pack(">IIIIIHHBB", seq, w, h, 0, 0,
                                                  delay_num, delay_den, 0, 0)))
            seq += 1
            out.write(_chunk(b"fdAT", struct.pack(">I", seq)
                             + zlib.compress(raw, level)))
            seq += 1
    out.write(_chunk(b"IEND", b""))
    with io.open(path, "wb") as fh:
        fh.write(out.getvalue())
    return path


def _filtered_rows(fb: Framebuffer) -> bytes:
    stride = fb.w * 4
    src = bytes(fb.px)
    rows = bytearray()
    prev = bytes(stride)
    for y in range(fb.h):
        line = src[y * stride:(y + 1) * stride]
        # фильтр Sub обычно лучше всего на плавных градиентах
        sub = bytes([line[i] - (line[i - 4] if i >= 4 else 0) & 0xFF for i in range(stride)])
        up = bytes([line[i] - prev[i] & 0xFF for i in range(stride)])
        s_sub = sum(b if b < 128 else 256 - b for b in sub)
        s_up = sum(b if b < 128 else 256 - b for b in up)
        s_none = sum(b if b < 128 else 256 - b for b in line)
        best = min((s_none, 0, line), (s_sub, 1, sub), (s_up, 2, up))
        rows.append(best[1])
        rows += best[2]
        prev = line
    return bytes(rows)


# --------------------------------------------------------------------------- #
#  GIF
# --------------------------------------------------------------------------- #
def write_gif(path: str, frames: Sequence[Tuple[int, Framebuffer]],
              fps: float | None = None, default_fps: float = 30.0,
              background: Tuple[int, int, int] = (0, 0, 0),
              transparent_index: int | None = 255) -> str:
    """
    GIF с глобальной палитрой. Кадр с альфой кладётся на `background`,
    полностью прозрачные пиксели помечаются индексом transparent_index.
    """
    items = [fb for _, fb in frames]
    if not items:
        raise ValueError("нет кадров для экспорта")
    w, h = items[0].w, items[0].h
    rate = fps or default_fps
    delay = max(1, int(round(100.0 / rate)))   # в сотых долях секунды

    palette, inv = _build_palette(items, background, reserved=transparent_index is not None)

    out = io.BytesIO()
    out.write(b"GIF89a")
    out.write(struct.pack("<HH", w, h))
    out.write(bytes([0xF7, 0x00, 0x00]))        # global colour table, 256 entries
    out.write(bytes(palette))                   # 256 * 3 байта
    out.write(b"\x21\xFF\x0BNETSCAPE2.0\x03\x01")
    out.write(struct.pack("<H", 0))             # loop forever
    out.write(b"\x00")

    for fb in items:
        idx = _quantize(fb, inv, background, transparent_index)
        if transparent_index is not None:
            out.write(b"\x21\xF9\x04")
            out.write(bytes([0x01, delay & 0xFF, (delay >> 8) & 0xFF, transparent_index]))
            out.write(b"\x00")
        else:
            out.write(b"\x21\xF9\x04")
            out.write(bytes([0x00, delay & 0xFF, (delay >> 8) & 0xFF, 0x00]))
            out.write(b"\x00")
        out.write(b"\x2C")
        out.write(struct.pack("<HHHH", 0, 0, w, h))
        out.write(bytes([0x00]))
        out.write(_lzw(idx, 8))
    out.write(b"\x3B")
    with io.open(path, "wb") as fh:
        fh.write(out.getvalue())
    return path


def _flatten(fb: Framebuffer, background: Tuple[int, int, int]) -> bytearray:
    br, bg_, bb = background
    out = bytearray(fb.w * fb.h * 3)
    px = fb.px
    for i in range(fb.w * fb.h):
        j = i * 4
        a = px[j + 3] / 255.0
        k = i * 3
        out[k] = int(px[j] * a + br * (1 - a))
        out[k + 1] = int(px[j + 1] * a + bg_ * (1 - a))
        out[k + 2] = int(px[j + 2] * a + bb * (1 - a))
    return out


def _build_palette(items: Sequence[Framebuffer], background, reserved: bool,
                   max_colors: int = 255) -> Tuple[bytes, dict]:
    """Глобальная палитра: сэмплируем цвета всех кадров и кластеризуем."""
    samples: List[Tuple[int, int, int]] = []
    step = max(1, (len(items) * items[0].w * items[0].h) // 40000)
    flat = []
    for fb in items:
        f = _flatten(fb, background)
        flat.append(f)
    idx = 0
    for f in flat:
        for i in range(0, len(f) // 3, step):
            samples.append((f[i * 3] >> 3, f[i * 3 + 1] >> 3, f[i * 3 + 2] >> 3))
    counts: dict = {}
    for s in samples:
        counts[s] = counts.get(s, 0) + 1
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:max_colors]
    palette = [(r << 3, g << 3, b << 3) for (r, g, b), _ in top]
    while len(palette) < 256:
        palette.append((0, 0, 0))
    inv = {c: i for i, c in enumerate(palette[:len(top)])}
    data = bytearray()
    for c in palette:
        data += bytes(c)
    return bytes(data), inv


def _quantize(fb: Framebuffer, inv: dict, background, transparent_index) -> bytearray:
    f = _flatten(fb, background)
    px = fb.px
    out = bytearray(fb.w * fb.h)
    keys = list(inv)
    # быстрый поиск ближайшего: кэш по 5-битному ключу
    cache: dict = {}
    for i in range(fb.w * fb.h):
        r, g, b = f[i * 3], f[i * 3 + 1], f[i * 3 + 2]
        if transparent_index is not None and px[i * 4 + 3] < 128:
            out[i] = transparent_index
            continue
        key = (r >> 3, g >> 3, b >> 3)
        ci = cache.get(key)
        if ci is None:
            best, bestd = None, 1 << 30
            for c in keys:
                d = ((c[0] << 3) - r) ** 2 + ((c[1] << 3) - g) ** 2 + ((c[2] << 3) - b) ** 2
                if d < bestd:
                    bestd, best = d, c
            ci = inv[best]
            cache[key] = ci
        out[i] = ci
    return out


def _lzw(data: bytes, min_code_size: int = 8) -> bytes:
    """Классический GIF-LZW с упаковкой в субблоки."""
    clear = 1 << min_code_size
    eoi = clear + 1
    code_size = min_code_size + 1
    next_code = eoi + 1
    table = {bytes([i]): i for i in range(clear)}

    bits = 0
    nbits = 0
    out = bytearray()

    def emit(code: int):
        nonlocal bits, nbits, code_size
        bits |= code << nbits
        nbits += code_size
        while nbits >= 8:
            out.append(bits & 0xFF)
            bits >>= 8
            nbits -= 8

    emit(clear)
    if not data:
        emit(eoi)
    else:
        cur = bytes([data[0]])
        for byte in data[1:]:
            nxt = cur + bytes([byte])
            if nxt in table:
                cur = nxt
                continue
            emit(table[cur])
            if next_code < 4096:
                table[nxt] = next_code
                next_code += 1
                if next_code > (1 << code_size) and code_size < 12:
                    code_size += 1
            else:
                emit(clear)
                table = {bytes([i]): i for i in range(clear)}
                next_code = eoi + 1
                code_size = min_code_size + 1
            cur = bytes([byte])
        emit(table[cur])
    emit(eoi)
    if nbits:
        out.append(bits & 0xFF)

    # субблоки по 255 байт
    res = bytearray([min_code_size])
    i = 0
    while i < len(out):
        n = min(255, len(out) - i)
        res.append(n)
        res += out[i:i + n]
        i += n
    res.append(0)
    return bytes(res)
