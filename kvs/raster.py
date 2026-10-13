"""
Программный растеризатор .kvs -- чистый Python, ноль зависимостей.

Алгоритм: сканлайн с вертикальным суперсэмплингом (ss раз на пиксель) и
чётным/нечётным (evenodd) или ненулевым (nonzero) правилом заполнения.
Для каждой строки субпикселей считается список пересечений с рёбрами, он
сортируется, и промежутки заливаются «пачками» (по 64 пикселя за один срез) --
это даёт приемлемую скорость без C-расширений и numpy.
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence, Tuple

from .geometry import Path, path_bbox

# вес субстроки в покрытии пикселя
_INV = 1.0


class Framebuffer:
    """Прямоугольный RGBA-буфер (bytes, premultiplied-нет, straight alpha)."""

    __slots__ = ("w", "h", "px")

    def __init__(self, w: int, h: int, color: Sequence[int] = (0, 0, 0, 0)):
        self.w, self.h = w, h
        r, g, b, a = color
        self.px = bytearray(bytes((r, g, b, a)) * (w * h))

    def clear(self, color: Sequence[int] = (0, 0, 0, 0)) -> None:
        r, g, b, a = color
        self.px = bytearray(bytes((r, g, b, a)) * (self.w * self.h))

    def copy(self) -> "Framebuffer":
        fb = Framebuffer.__new__(Framebuffer)
        fb.w, fb.h = self.w, self.h
        fb.px = bytearray(self.px)
        return fb

    def get(self, x: int, y: int) -> Tuple[int, int, int, int]:
        i = (y * self.w + x) * 4
        return self.px[i], self.px[i + 1], self.px[i + 2], self.px[i + 3]

    def blend_rect(self, x0: int, y0: int, x1: int, y1: int,
                   color: Sequence[int], alpha_scale: float = 1.0) -> None:
        """Залить прямоугольник [x0,x1) x [y0,y1) сплошным цветом (source-over)."""
        if alpha_scale <= 0:
            return
        cr, cg, cb, ca = color
        ca = ca * alpha_scale
        if ca <= 0:
            return
        w = self.w
        px = self.px
        for y in range(max(0, y0), min(self.h, y1)):
            row = y * w * 4
            for x in range(max(0, x0), min(w, x1)):
                i = row + x * 4
                da = px[i + 3] / 255.0
                sa = ca / 255.0
                oa = sa + da * (1 - sa)
                if oa <= 0:
                    continue
                px[i] = int((cr * sa + px[i] * da * (1 - sa)) / oa)
                px[i + 1] = int((cg * sa + px[i + 1] * da * (1 - sa)) / oa)
                px[i + 2] = int((cb * sa + px[i + 2] * da * (1 - sa)) / oa)
                px[i + 3] = int(oa * 255)


class _Edge:
    __slots__ = ("y0", "y1", "x0", "dx")

    def __init__(self, y0: float, y1: float, x0: float, x1: float):
        if y0 > y1:
            y0, y1, x0, x1 = y1, y0, x1, x0
        self.y0 = y0
        self.y1 = y1
        self.x0 = x0
        span = y1 - y0
        self.dx = (x1 - x0) / span if span > 1e-12 else 0.0


def build_edges(path: Path) -> List[_Edge]:
    """Path (мировые координаты) -> список ненаправленных рёбер."""
    edges: List[_Edge] = []
    for pts, closed in path:
        n = len(pts)
        if n < 2:
            continue
        limit = n if closed else n - 1
        for i in range(limit):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            if abs(y1 - y0) < 1e-9:
                continue
            edges.append(_Edge(y0, y1, x0, x1))
    return edges


def directed_edges(path: Path) -> Tuple[List[_Edge], List[int]]:
    """Рёбра + знак направления (для nonzero)."""
    edges: List[_Edge] = []
    dirs: List[int] = []
    for pts, closed in path:
        n = len(pts)
        if n < 2:
            continue
        limit = n if closed else n - 1
        for i in range(limit):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            dy = y1 - y0
            if abs(dy) < 1e-9:
                continue
            edges.append(_Edge(y0, y1, x0, x1))
            dirs.append(1 if dy > 0 else -1)
    return edges, dirs


def path_bounds(path: Path) -> Tuple[float, float, float, float]:
    return path_bbox(path)


# --------------------------------------------------------------------------- #
#  основная функция: покрытие
# --------------------------------------------------------------------------- #
def coverage(path: Path, width: int, height: int, ss: int = 4,
             rule: str = "nonzero") -> Tuple[bytearray, int, int, int, int]:
    """
    Возвращает (cov, x0, y0, x1, y1):
      cov -- bytearray покрытия 0..255 для пикселей [x0,x1) x [y0,y1);
      x0,y0,x1,y1 -- целочисленный bbox в пределах кадра.
    """
    if not path:
        return bytearray(), 0, 0, 0, 0
    bx0, by0, bx1, by1 = path_bbox(path)
    ix0 = max(0, int(math.floor(bx0)))
    iy0 = max(0, int(math.floor(by0)))
    ix1 = min(width, int(math.ceil(bx1)))
    iy1 = min(height, int(math.ceil(by1)))
    if ix1 <= ix0 or iy1 <= iy0:
        return bytearray(), 0, 0, 0, 0

    if rule == "evenodd":
        edges = build_edges(path)
        dirs = None
    else:
        edges, dirs = directed_edges(path)
    if not edges:
        return bytearray(), 0, 0, 0, 0

    # таблица активных рёбер на каждую субстроку
    nsub = (iy1 - iy0) * ss
    aet: List[List[int]] = [[] for _ in range(nsub)]
    inv_ss = 1.0 / ss
    for ei, e in enumerate(edges):
        r0 = int((e.y0 - iy0) * ss)
        r1 = int((e.y1 - iy0) * ss)
        if r0 > r1:
            r0, r1 = r1, r0
        if r1 <= 0 or r0 >= nsub:
            continue
        for r in range(max(0, r0), min(nsub, r1)):
            aet[r].append(ei)

    acc = bytearray((ix1 - ix0) * nsub)
    row_w = ix1 - ix0
    # веса субстрок подобраны так, чтобы сумма была ровно 255
    weights = [255 // ss] * ss
    for i in range(255 - sum(weights)):
        weights[i] += 1

    for r in range(nsub):
        active = aet[r]
        if not active:
            continue
        weight = weights[r % ss]
        y = iy0 + (r + 0.5) * inv_ss
        if dirs is None:
            xs: List[float] = []
            for ei in active:
                e = edges[ei]
                xs.append(e.x0 + (y - e.y0) * e.dx)
            xs.sort()
            base = r * row_w
            for k in range(0, len(xs) - 1, 2):
                _fill_span(acc, base, xs[k], xs[k + 1], ix0, ix1, weight)
        else:
            pairs: List[Tuple[float, int]] = []
            for ei in active:
                e = edges[ei]
                pairs.append((e.x0 + (y - e.y0) * e.dx, dirs[ei]))
            pairs.sort(key=lambda p: p[0])
            base = r * row_w
            winding = 0
            prev_x = 0.0
            for x, d in pairs:
                if winding != 0 and x > prev_x:
                    _fill_span(acc, base, prev_x, x, ix0, ix1, weight)
                winding += d
                prev_x = x

    # бокс-фильтр ss субстрок -> строка пикселей
    if ss == 1:
        return acc, ix0, iy0, ix1, iy1
    # бокс-фильтр: сумма ss субстрок уже нормирована в 0..255
    rows = iy1 - iy0
    out = bytearray(row_w * rows)
    for py in range(rows):
        src = py * ss * row_w
        dst = py * row_w
        for x in range(row_w):
            total = 0
            i = src + x
            for _ in range(ss):
                total += acc[i]
                i += row_w
            out[dst + x] = 255 if total > 255 else total
    return out, ix0, iy0, ix1, iy1


_BYTES_CACHE: Dict[Tuple[int, int], bytes] = {}


def _filled(n: int, weight: int) -> bytes:
    """bytes из n байт со значением weight (с кэшем, чтобы не строить повторно)."""
    key = (n, weight)
    b = _BYTES_CACHE.get(key)
    if b is None:
        b = bytes((weight,)) * n
        if len(_BYTES_CACHE) < 4096:
            _BYTES_CACHE[key] = b
    return b


def _fill_span(acc: bytearray, base: int, xa: float, xb: float,
               ix0: int, ix1: int, weight: int) -> None:
    """
    Накопить покрытие субстроки в промежутке [xa, xb).
    Крайние пиксели получают долю покрытия -- горизонтальное сглаживание.
    """
    if xb <= xa or xb <= ix0 or xa >= ix1:
        return
    if xa < ix0:
        xa = float(ix0)
    if xb > ix1:
        xb = float(ix1)
    start = int(xa) - ix0
    end = int(xb - 1e-9) - ix0
    if end < start:
        return
    row = base
    frac_a = xa - (start + ix0)
    frac_b = xb - (end + ix0)
    if start == end:
        v = int((xb - xa) * weight)
        if v:
            acc[row + start] += v
        return
    v = int((1.0 - frac_a) * weight)
    if v:
        acc[row + start] += v
    inner = end - start - 1
    if inner > 0:
        i = start + 1
        while inner:
            n = inner if inner < 64 else 64
            acc[row + i: row + i + n] = _filled(n, weight)
            i += n
            inner -= n
    v = int(frac_b * weight)
    if v:
        acc[row + end] += v
