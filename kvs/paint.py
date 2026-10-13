"""
Краски .kvs: сплошной цвет, линейный / радиальный / конический градиенты.

Градиент отдаёт LUT из 256 RGBA-значений, а дальше два режима выборки:
  * `row_lut`  -- для линейного градиента: цвета в строке меняются линейно по x,
                  поэтому строим 256-цветную таблицу один раз на строку;
  * `pixel_lut`-- для радиального/конического: индекс считается на каждый пиксель.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

from .scene import parse_color

RGBA = Tuple[int, int, int, int]


class Paint:
    """База краски: умеет отдавать цвет в точке (x, y) локальных координат слоя."""

    solid = False

    def color_at(self, x: float, y: float) -> RGBA:
        raise NotImplementedError

    def bbox(self) -> Tuple[float, float, float, float] | None:
        return None


class SolidPaint(Paint):
    solid = True

    __slots__ = ("rgba",)

    def __init__(self, rgba: RGBA):
        self.rgba = rgba

    def color_at(self, x: float, y: float) -> RGBA:
        return self.rgba


class GradientPaint(Paint):
    """Градиент с LUT на 256 шагов."""

    def __init__(self, stops: Sequence[Tuple[float, RGBA]], spread: str = "pad"):
        if not stops:
            raise ValueError("градиент без стопов")
        pts = sorted(((float(p), c) for p, c in stops), key=lambda s: s[0])
        if pts[0][0] > 0:
            pts.insert(0, (0.0, pts[0][1]))
        if pts[-1][0] < 1:
            pts.append((1.0, pts[-1][1]))
        self.stops = pts
        self.spread = spread
        self.lut: List[RGBA] = [self._sample(i / 255.0) for i in range(256)]

    def _sample(self, t: float) -> RGBA:
        if self.spread == "reflect":
            t = abs(t) % 2.0
            if t > 1.0:
                t = 2.0 - t
        elif self.spread == "repeat":
            t = t % 1.0
        else:
            t = 0.0 if t < 0 else (1.0 if t > 1 else t)
        stops = self.stops
        if t <= stops[0][0]:
            return stops[0][1]
        if t >= stops[-1][0]:
            return stops[-1][1]
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                span = p1 - p0
                k = 0.0 if span <= 1e-9 else (t - p0) / span
                return tuple(round(a + (b - a) * k) for a, b in zip(c0, c1))  # type: ignore[return-value]
        return stops[-1][1]

    def lut_index(self, x: float, y: float) -> int:
        raise NotImplementedError

    def color_at(self, x: float, y: float) -> RGBA:
        return self.lut[self.lut_index(x, y)]


class LinearGradient(GradientPaint):
    def __init__(self, stops, x0=0.0, y0=0.0, x1=0.0, y1=1.0, spread="pad"):
        super().__init__(stops, spread)
        dx, dy = x1 - x0, y1 - y0
        self.len2 = dx * dx + dy * dy
        if self.len2 < 1e-9:
            dx, dy, self.len2 = 0.0, 1.0, 1.0
        self.x0, self.y0 = x0, y0
        self.dx, self.dy = dx / self.len2, dy / self.len2

    def t_at(self, x: float, y: float) -> float:
        return ((x - self.x0) * self.dx + (y - self.y0) * self.dy)

    def lut_index(self, x: float, y: float) -> int:
        t = self.t_at(x, y)
        if self.spread == "pad":
            t = 0.0 if t < 0 else (1.0 if t > 1 else t)
        return max(0, min(255, int(t * 255.0)))

    def bbox(self):
        return None


class RadialGradient(GradientPaint):
    def __init__(self, stops, cx=0.0, cy=0.0, r=1.0, fx=None, fy=None, spread="pad"):
        super().__init__(stops, spread)
        self.cx, self.cy, self.r = cx, cy, max(1e-6, r)
        self.fx = cx if fx is None else fx
        self.fy = cy if fy is None else fy

    def lut_index(self, x: float, y: float) -> int:
        t = math.hypot(x - self.cx, y - self.cy) / self.r
        if self.spread == "pad":
            t = 0.0 if t < 0 else (1.0 if t > 1 else t)
        return max(0, min(255, int(t * 255.0)))


class ConicGradient(GradientPaint):
    def __init__(self, stops, cx=0.0, cy=0.0, a0=0.0, spread="pad"):
        super().__init__(stops, spread)
        self.cx, self.cy = cx, cy
        self.a0 = math.radians(a0)

    def lut_index(self, x: float, y: float) -> int:
        a = math.atan2(y - self.cy, x - self.cx) - self.a0
        a = (a % (2 * math.pi)) / (2 * math.pi)
        return max(0, min(255, int(a * 255.0)))


def build_paint(spec: Any, assets: Dict[str, Any],
                bbox: Tuple[float, float, float, float] | None = None) -> Paint:
    """
    spec -- компактная краска слоя:
      {"c": "#rrggbb"}                      сплошной цвет
      {"g": "<asset-id>"}                   ссылка на градиент-ассет
      {"g": {...}}                          встроенный градиент
    """
    if spec is None:
        return SolidPaint((255, 255, 255, 255))
    if isinstance(spec, str):
        return SolidPaint(parse_color(spec))
    if "c" in spec:
        return SolidPaint(parse_color(spec["c"]))
    g = spec.get("g")
    if g is None:
        return SolidPaint((255, 255, 255, 255))
    if isinstance(g, str):
        gid = g
        g = assets.get(gid)
        if g is None:
            raise KeyError(f"ассет градиента не найден: {gid!r}")
    return build_gradient(g, bbox)


def build_gradient(g: Dict[str, Any],
                   bbox: Tuple[float, float, float, float] | None = None) -> GradientPaint:
    """
    Координаты градиента по умолчанию заданы в локальной системе слоя.
    Флаг `u: 1` -- нормализованные координаты (0..1) относительно bbox фигуры,
    `a` (угол) у линейного градиента тоже раскрывается через bbox.
    """
    stops = [(float(p), parse_color(c)) for p, c in g["s"]]
    spread = {0: "pad", 1: "reflect", 2: "repeat"}.get(g.get("sp", 0), "pad")
    box = bbox or (0.0, 0.0, 1.0, 1.0)
    x, y, X, Y = box
    bw, bh = max(X - x, 1e-6), max(Y - y, 1e-6)

    def ux(v: float) -> float:
        return x + v * bw if g.get("u") else float(v)

    def uy(v: float) -> float:
        return y + v * bh if g.get("u") else float(v)

    t = g.get("t", "l")
    if t == "l":
        if "x0" in g:
            return LinearGradient(stops, ux(g["x0"]), uy(g["y0"]), ux(g["x1"]), uy(g["y1"]), spread)
        ang = math.radians(float(g.get("a", 90)))
        cx, cy = x + bw / 2.0, y + bh / 2.0
        half = (abs(math.cos(ang)) * bw + abs(math.sin(ang)) * bh) / 2.0
        return LinearGradient(stops, cx - math.cos(ang) * half, cy - math.sin(ang) * half,
                              cx + math.cos(ang) * half, cy + math.sin(ang) * half, spread)
    if t == "r":
        r = g["r"]
        if g.get("u"):
            r = float(r) * max(bw, bh)
        return RadialGradient(stops, ux(g.get("cx", 0.5 if g.get("u") else 0)),
                              uy(g.get("cy", 0.5 if g.get("u") else 0)), float(r),
                              g.get("fx"), g.get("fy"), spread)
    if t == "c":
        return ConicGradient(stops, ux(g.get("cx", 0.5 if g.get("u") else 0)),
                             uy(g.get("cy", 0.5 if g.get("u") else 0)),
                             float(g.get("a0", 0)), spread)
    raise ValueError(f"неизвестный тип градиента: {t!r}")
