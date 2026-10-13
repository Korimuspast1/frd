"""
Геометрия .kvs: превращение примитивов сцены в плоские полигональные контуры
(subpaths) и построение аутлайна обводки (stroke -> fill).

Всё считается в локальных координатах слоя; матрицу слоя применяет renderer.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

Point = Tuple[float, float]
Subpath = Tuple[List[Point], bool]      # (точки, замкнут?)
Path = List[Subpath]

TAU = math.pi * 2.0
FLAT_TOLERANCE = 0.15   # px, допуск аппроксимации кривых
MIN_SEGMENTS = 8


# --------------------------------------------------------------------------- #
#  матрица 2D (affine)
# --------------------------------------------------------------------------- #
class Matrix:
    """[a c e; b d f] -- как в SVG/Canvas."""

    __slots__ = ("a", "b", "c", "d", "e", "f")

    def __init__(self, a=1.0, b=0.0, c=0.0, d=1.0, e=0.0, f=0.0):
        self.a, self.b, self.c, self.d, self.e, self.f = a, b, c, d, e, f

    @staticmethod
    def identity() -> "Matrix":
        return Matrix()

    def multiply(self, o: "Matrix") -> "Matrix":
        a, b, c, d, e, f = self.a, self.b, self.c, self.d, self.e, self.f
        return Matrix(
            a * o.a + c * o.b,
            b * o.a + d * o.b,
            a * o.c + c * o.d,
            b * o.c + d * o.d,
            a * o.e + c * o.f + e,
            b * o.e + d * o.f + f,
        )

    @staticmethod
    def translate(x: float, y: float) -> "Matrix":
        return Matrix(1, 0, 0, 1, x, y)

    @staticmethod
    def scale(sx: float, sy: float) -> "Matrix":
        return Matrix(sx, 0, 0, sy, 0, 0)

    @staticmethod
    def rotate(deg: float) -> "Matrix":
        r = math.radians(deg)
        cs, sn = math.cos(r), math.sin(r)
        return Matrix(cs, sn, -sn, cs, 0, 0)

    @staticmethod
    def skew(ax: float, ay: float) -> "Matrix":
        return Matrix(1, math.tan(math.radians(ay)), math.tan(math.radians(ax)), 1, 0, 0)

    def apply(self, x: float, y: float) -> Point:
        return (self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    def apply_path(self, path: Path) -> Path:
        a, b, c, d, e, f = self.a, self.b, self.c, self.d, self.e, self.f
        out: Path = []
        for pts, closed in path:
            out.append(([(a * x + c * y + e, b * x + d * y + f) for x, y in pts], closed))
        return out

    def length_scale(self) -> float:
        """Средний масштаб -- чтобы толщину обводки считать в мировых px."""
        return math.sqrt(abs(self.a * self.d - self.b * self.c)) or 1e-6

    def as_tuple(self) -> Tuple[float, ...]:
        return (self.a, self.b, self.c, self.d, self.e, self.f)


def layer_matrix(
    position: Sequence[float],
    anchor: Sequence[float],
    scale: Sequence[float],
    rotation: float,
    skew: Sequence[float] = (0.0, 0.0),
) -> Matrix:
    """T(position) * R * S * Skew * T(-anchor) -- классический порядок Lottie/AE."""
    m = Matrix.translate(position[0], position[1])
    if rotation:
        m = m.multiply(Matrix.rotate(rotation))
    if scale[0] != 1.0 or scale[1] != 1.0:
        m = m.multiply(Matrix.scale(scale[0], scale[1]))
    if skew[0] or skew[1]:
        m = m.multiply(Matrix.skew(skew[0], skew[1]))
    if anchor[0] or anchor[1]:
        m = m.multiply(Matrix.translate(-anchor[0], -anchor[1]))
    return m


# --------------------------------------------------------------------------- #
#  Безье
# --------------------------------------------------------------------------- #
def flatten_cubic(p0: Point, p1: Point, p2: Point, p3: Point,
                  tol: float = FLAT_TOLERANCE) -> List[Point]:
    """Аппроксимация кубической кривой polyline (без первой точки p0)."""
    out: List[Point] = []

    def sub(p0, p1, p2, p3, depth):
        # оценка отклонения хорды
        ux = 3.0 * p1[0] - 2.0 * p0[0] - p3[0]
        uy = 3.0 * p1[1] - 2.0 * p0[1] - p3[1]
        vx = 3.0 * p2[0] - p0[0] - 2.0 * p3[0]
        vy = 3.0 * p2[1] - p0[1] - 2.0 * p3[1]
        err = max(ux * ux, vx * vx) + max(uy * uy, vy * vy)
        if depth >= 12 or err <= 16.0 * tol * tol:
            out.append(p3)
            return
        a = _mid(p0, p1); b = _mid(p1, p2); c = _mid(p2, p3)
        ab = _mid(a, b); bc = _mid(b, c); m = _mid(ab, bc)
        sub(p0, a, ab, m, depth + 1)
        sub(m, bc, c, p3, depth + 1)

    sub(tuple(p0), tuple(p1), tuple(p2), tuple(p3), 0)
    return out


def flatten_quadratic(p0: Point, p1: Point, p2: Point, tol: float = FLAT_TOLERANCE) -> List[Point]:
    # квадрат -> кубика
    c1 = (p0[0] + 2 / 3 * (p1[0] - p0[0]), p0[1] + 2 / 3 * (p1[1] - p0[1]))
    c2 = (p2[0] + 2 / 3 * (p1[0] - p2[0]), p2[1] + 2 / 3 * (p1[1] - p2[1]))
    return flatten_cubic(p0, c1, c2, p2, tol)


def _mid(p: Point, q: Point) -> Point:
    return ((p[0] + q[0]) * 0.5, (p[1] + q[1]) * 0.5)


def arc_points(cx: float, cy: float, r: float, a0: float, a1: float,
               segments: int | None = None) -> List[Point]:
    """Точки дуги (углы в радианах), включая a0, исключая a1."""
    span = a1 - a0
    n = segments or max(MIN_SEGMENTS, int(math.ceil(abs(span) / (TAU / 64.0))))
    return [(cx + r * math.cos(a0 + span * i / n), cy + r * math.sin(a0 + span * i / n))
            for i in range(n)]


# --------------------------------------------------------------------------- #
#  примитивы -> Path
# --------------------------------------------------------------------------- #
def rect_path(x: float, y: float, w: float, h: float, r: float = 0.0) -> Path:
    """Прямоугольник с центром (x,y); r>0 -- скругление углов кубическими дугами."""
    x0, y0 = x - w / 2.0, y - h / 2.0
    r = max(0.0, min(r, min(w, h) / 2.0))
    if r <= 0.001:
        pts = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
        return [(pts, True)]
    k = r * 0.5522847498
    pts: List[Point] = [(x0 + r, y0)]
    # верхний правый угол
    pts += flatten_cubic((x0 + r, y0), (x0 + w - r + k, y0), (x0 + w, y0 + r - k), (x0 + w, y0 + r))
    pts.append((x0 + w, y0 + h - r))
    # нижний правый
    pts += flatten_cubic((x0 + w, y0 + h - r), (x0 + w, y0 + h - r + k),
                         (x0 + w - r + k, y0 + h), (x0 + w - r, y0 + h))
    pts.append((x0 + r, y0 + h))
    # нижний левый
    pts += flatten_cubic((x0 + r, y0 + h), (x0 + r - k, y0 + h),
                         (x0, y0 + h - r + k), (x0, y0 + h - r))
    pts.append((x0, y0 + r))
    # верхний левый
    pts += flatten_cubic((x0, y0 + r), (x0, y0 + r - k), (x0 + r - k, y0), (x0 + r, y0))
    return [(pts, True)]


def ellipse_path(cx: float, cy: float, rx: float, ry: float) -> Path:
    k = 0.5522847498
    ox, oy = rx * k, ry * k
    pts = [(cx + rx, cy)]
    pts += flatten_cubic((cx + rx, cy), (cx + rx, cy + oy), (cx + ox, cy + ry), (cx, cy + ry))
    pts += flatten_cubic((cx, cy + ry), (cx - ox, cy + ry), (cx - rx, cy + oy), (cx - rx, cy))
    pts += flatten_cubic((cx - rx, cy), (cx - rx, cy - oy), (cx - ox, cy - ry), (cx, cy - ry))
    pts += flatten_cubic((cx, cy - ry), (cx + ox, cy - ry), (cx + rx, cy - oy), (cx + rx, cy))
    return [(pts, True)]


def polygon_path(cx: float, cy: float, r: float, sides: int, rot_deg: float = -90.0) -> Path:
    sides = max(3, int(round(sides)))
    a0 = math.radians(rot_deg)
    pts = [(cx + r * math.cos(a0 + i * TAU / sides), cy + r * math.sin(a0 + i * TAU / sides))
           for i in range(sides)]
    return [(pts, True)]


def star_path(cx: float, cy: float, r1: float, r2: float, points_n: int,
              rot_deg: float = -90.0, roundness: float = 0.0) -> Path:
    points_n = max(2, int(round(points_n)))
    a0 = math.radians(rot_deg)
    n = points_n * 2
    raw = []
    for i in range(n):
        r = r1 if i % 2 == 0 else r2
        a = a0 + i * TAU / n
        raw.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    if roundness <= 0.001:
        return [(raw, True)]
    # скругление углов: срезаем долю `roundness` каждого ребра и вставляем quadratic
    pts: List[Point] = []
    m = len(raw)
    for i in range(m):
        prev, cur, nxt = raw[i - 1], raw[i], raw[(i + 1) % m]
        t = roundness * 0.5
        a = (cur[0] + (prev[0] - cur[0]) * t, cur[1] + (prev[1] - cur[1]) * t)
        b = (cur[0] + (nxt[0] - cur[0]) * t, cur[1] + (nxt[1] - cur[1]) * t)
        if i == 0:
            pts.append(a)
        else:
            pts.append(a)
        pts += flatten_quadratic(a, cur, b)
    return [(pts, True)]


def compact_subpath_to_points(sp: Sequence[Any], tol: float = FLAT_TOLERANCE) -> Tuple[List[Point], bool]:
    """
    Компактный subpath -> полилиния.

    Точка может быть:
      [x, y]                             -- линейный сегмент (lineTo)
      [cx1, cy1, cx2, cy2, x, y]         -- кубическая Безье от предыдущей точки
      [cx, cy, x, y]                     -- квадратичная Безье
      [x, y, ox, oy, ix2, iy2]           -- вершина + исходящая/входящая ручки (SVG-like)
    Последний элемент `0` вместо точки означает «контур не замкнут».
    """
    closed = True
    items = list(sp)
    if items and isinstance(items[-1], (int, float)) and not isinstance(items[-1], (list, tuple)):
        closed = bool(items[-1])
        items = items[:-1]
    if not items:
        return [], closed

    pts: List[Point] = []
    prev: Point = (float(items[0][0]), float(items[0][1])) if len(items[0]) in (2, 8) \
        else (float(items[0][-2]), float(items[0][-1]))
    pts.append(prev)
    for it in items[1:]:
        v = [float(x) for x in it]
        if len(v) == 2:
            p = (v[0], v[1])
            pts.append(p)
        elif len(v) == 4:
            pts += flatten_quadratic(prev, (v[0], v[1]), (v[2], v[3]), tol)
        elif len(v) == 6:
            pts += flatten_cubic(prev, (v[0], v[1]), (v[2], v[3]), (v[4], v[5]), tol)
        elif len(v) == 8:
            pts += flatten_cubic(prev, (v[2], v[3]), (v[6], v[7]), (v[0], v[1]), tol)
        else:
            raise ValueError(f"непонятная точка пути: {it!r}")
        prev = pts[-1]
    if closed and len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) < 1e-9 \
            and abs(pts[0][1] - pts[-1][1]) < 1e-9:
        pts.pop()
    return pts, closed


# --------------------------------------------------------------------------- #
#  обводка -> заполняемый аутлайн
# --------------------------------------------------------------------------- #
def _unit(dx: float, dy: float) -> Tuple[float, float]:
    ln = math.hypot(dx, dy)
    if ln < 1e-12:
        return (0.0, 0.0)
    return (dx / ln, dy / ln)


def _arc_sweep(cx: float, cy: float, r: float, a0: float, a1: float, ccw: bool,
               tol: float = FLAT_TOLERANCE) -> List[Point]:
    """Дуга от a0 до a1 в нужном направлении (без первой точки, с последней)."""
    if ccw:
        while a1 <= a0 + 1e-9:
            a1 += TAU
    else:
        while a1 >= a0 - 1e-9:
            a1 -= TAU
    span = a1 - a0
    n = max(1, int(math.ceil(abs(span) / max(1e-3, math.sqrt(8.0 * tol / max(r, 1e-6))))))
    n = min(n, 48)
    return [(cx + r * math.cos(a0 + span * i / n), cy + r * math.sin(a0 + span * i / n))
            for i in range(1, n + 1)]


def _ang_dist(a: float, b: float) -> float:
    d = (a - b) % TAU
    return min(d, TAU - d)


def _short_arc_ccw(a0: float, a1: float) -> bool:
    """Направление «короткой» дуги из a0 в a1."""
    return ((a1 - a0) % TAU) <= math.pi


def _cap_arc_ccw(a_from: float, outward: float) -> bool:
    """
    Торцевая полуокружность: из двух вариантов выбираем ту, что смотрит
    наружу (содержит направление `outward`).
    """
    mid_ccw = a_from + math.pi / 2.0
    return _ang_dist(mid_ccw, outward) < math.pi / 2.0 - 1e-9


def _join_point(x0: float, y0: float, x1: float, y1: float,
                x2: float, y2: float) -> int:
    """>0 -- поворот против часовой (screen), <0 -- по часовой, 0 -- коллинеарно."""
    cross = (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)
    if abs(cross) < 1e-9:
        return 0
    return 1 if cross > 0 else -1


def stroke_outline(pts: Sequence[Point], closed: bool, width: float,
                   cap: str = "round", join: str = "round",
                   miter_limit: float = 4.0, tol: float = FLAT_TOLERANCE) -> Path:
    """
    Полилиния -> замкнутый контур обводки (fill-эквивалент stroke).

    cap : butt | round | square
    join: round | bevel | miter

    Контур: «+нормальная» сторона от начала к концу -> торец ->
    «-нормальная» сторона обратно -> второй торец. Ориентация согласована,
    поэтому корректно работает и nonzero, и evenodd.
    """
    pts = _dedup(list(pts))
    n = len(pts)
    if width <= 1e-6:
        return []
    if closed:
        if n < 3:
            closed = False
    if n < 2:
        return []
    w = width * 0.5

    # рёбра: (x0, y0, x1, y1, nx, ny), нормаль = повёрнутый на +90° единичный вектор
    edges: List[Tuple[float, float, float, float, float, float]] = []
    count = n if closed else n - 1
    for i in range(count):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        if math.hypot(dx, dy) < 1e-9:
            continue
        ux, uy = _unit(dx, dy)
        edges.append((x0, y0, x1, y1, -uy, ux))
    if not edges:
        return []
    m = len(edges)

    plus: List[Point] = []
    minus: List[Point] = []

    def offsets(e) -> Tuple[Point, Point, Point, Point]:
        x0, y0, x1, y1, nx, ny = e
        return ((x0 + nx * w, y0 + ny * w), (x1 + nx * w, y1 + ny * w),
                (x0 - nx * w, y0 - ny * w), (x1 - nx * w, y1 - ny * w))

    def join_at(vertex_idx: int) -> None:
        """Вершина pts[vertex_idx] -- стык ребра (vertex_idx-1) и ребра vertex_idx."""
        e_prev = edges[(vertex_idx - 1) % m]
        e_next = edges[vertex_idx % m]
        vx, vy = pts[vertex_idx]
        _, p_prev, _, m_prev = offsets(e_prev)
        p_next, _, m_next, _ = offsets(e_next)
        nx0, ny0 = e_prev[4], e_prev[5]
        nx1, ny1 = e_next[4], e_next[5]
        turn = _join_point(e_prev[0], e_prev[1], vx, vy, e_next[2], e_next[3])
        if turn == 0 or join == "bevel":
            plus.extend((p_prev, p_next))
            minus.extend((m_prev, m_next))
            return
        sides = ((plus, p_prev, p_next), (minus, m_prev, m_next))
        (outer, o_from, o_to), (inner, i_from, i_to) = sides if turn > 0 else sides[::-1]
        if join == "round":
            a0 = math.atan2(o_from[1] - vy, o_from[0] - vx)
            a1 = math.atan2(o_to[1] - vy, o_to[0] - vx)
            outer.append(o_from)
            outer.extend(_arc_sweep(vx, vy, w, a0, a1, _short_arc_ccw(a0, a1), tol))
        elif join == "miter":
            mm = _miter_point(vx, vy, nx0, ny0, nx1, ny1, w, miter_limit)
            if mm is None:
                outer.extend((o_from, o_to))
            else:
                outer.append(mm)
        else:
            outer.extend((o_from, o_to))
        inner.extend((i_from, i_to))

    if closed:
        for v in range(n):
            join_at(v)
        poly = plus + minus[::-1]
        return [(_dedup(poly), True)]

    # открытый контур
    p0s, p0e, m0s, m0e = offsets(edges[0])
    plus.append(p0s)
    minus.append(m0s)
    for v in range(1, n - 1):
        join_at(v)
    plus.append(offsets(edges[-1])[1])
    minus.append(offsets(edges[-1])[3])

    e_last = edges[-1]
    e_first = edges[0]
    ex, ey = e_last[2], e_last[3]
    sx, sy = e_first[0], e_first[1]
    end_p, end_m = plus[-1], minus[-1]
    start_m, start_p = minus[0], plus[0]

    if cap == "round":
        u_end = _unit(e_last[2] - e_last[0], e_last[3] - e_last[1])
        u_beg = _unit(e_first[2] - e_first[0], e_first[3] - e_first[1])
        a0 = math.atan2(end_p[1] - ey, end_p[0] - ex)
        a1 = math.atan2(end_m[1] - ey, end_m[0] - ex)
        tail = _arc_sweep(ex, ey, w, a0, a1,
                          _cap_arc_ccw(a0, math.atan2(u_end[1], u_end[0])), tol)
        b0 = math.atan2(start_m[1] - sy, start_m[0] - sx)
        b1 = math.atan2(start_p[1] - sy, start_p[0] - sx)
        head = _arc_sweep(sx, sy, w, b0, b1,
                          _cap_arc_ccw(b0, math.atan2(-u_beg[1], -u_beg[0])), tol)
        poly = plus + tail + minus[::-1] + head
    elif cap == "square":
        ux, uy = _unit(ex - e_last[0], ey - e_last[1])
        vx, vy = _unit(e_first[2] - sx, e_first[3] - sy)
        poly = (plus + [(end_p[0] + ux * w, end_p[1] + uy * w),
                        (end_m[0] + ux * w, end_m[1] + uy * w)]
                + minus[::-1]
                + [(start_m[0] - vx * w, start_m[1] - vy * w),
                   (start_p[0] - vx * w, start_p[1] - vy * w)])
    else:
        poly = plus + minus[::-1]
    return [(_dedup(poly), True)]


def _dedup(poly: Sequence[Point], eps: float = 1e-7) -> List[Point]:
    out: List[Point] = []
    for p in poly:
        if not out or abs(p[0] - out[-1][0]) > eps or abs(p[1] - out[-1][1]) > eps:
            out.append((p[0], p[1]))
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < eps and abs(out[0][1] - out[-1][1]) < eps:
        out.pop()
    return out


def _miter_point(x: float, y: float, n0x: float, n0y: float, n1x: float, n1y: float,
                 w: float, limit: float) -> Point | None:
    """Точка пересечения смещённых прямых на ВНЕШНЕЙ стороне угла."""
    dir0 = (n0y, -n0x)
    dir1 = (n1y, -n1x)
    p0 = (x + n0x * w, y + n0y * w)
    p1 = (x + n1x * w, y + n1y * w)
    den = dir0[0] * dir1[1] - dir0[1] * dir1[0]
    if abs(den) < 1e-9:
        return None
    t = ((p1[0] - p0[0]) * dir1[1] - (p1[1] - p0[1]) * dir1[0]) / den
    m = (p0[0] + dir0[0] * t, p0[1] + dir0[1] * t)
    if math.hypot(m[0] - x, m[1] - y) / max(w, 1e-9) > limit:
        return None
    return m


def dash_polyline(pts: Sequence[Point], pattern: Sequence[float],
                  offset: float = 0.0) -> List[List[Point]]:
    """Разбить полилинию на отрезки по штриховому паттерну [dash, gap, ...]."""
    if not pattern:
        return [list(pts)]
    pat = [max(1e-6, float(p)) for p in pattern]
    if len(pat) % 2 == 1:
        pat = pat + pat
    total = sum(pat)
    segs: List[List[Point]] = []
    cur: List[Point] = []
    pos = offset % total
    drawing = _dash_state(pat, pos)
    idx = _dash_index(pat, pos)
    remaining = pat[idx] - pos
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        seg_len = math.hypot(x1 - x0, y1 - y0)
        if seg_len < 1e-9:
            continue
        t = 0.0
        while t < seg_len - 1e-9:
            step = min(remaining, seg_len - t)
            px = x0 + (x1 - x0) * (t / seg_len)
            py = y0 + (y1 - y0) * (t / seg_len)
            qx = x0 + (x1 - x0) * ((t + step) / seg_len)
            qy = y0 + (y1 - y0) * ((t + step) / seg_len)
            if drawing:
                if not cur:
                    cur = [(px, py)]
                cur.append((qx, qy))
            else:
                if cur:
                    segs.append(cur)
                    cur = []
            t += step
            remaining -= step
            if remaining <= 1e-9:
                idx = (idx + 1) % len(pat)
                drawing = (idx % 2 == 0)
                remaining = pat[idx]
    if cur:
        segs.append(cur)
    return segs


def _dash_index(pat: Sequence[float], pos: float) -> int:
    acc = 0.0
    for i, p in enumerate(pat):
        acc += p
        if pos < acc:
            return i
    return len(pat) - 1


def _dash_state(pat: Sequence[float], pos: float) -> bool:
    return _dash_index(pat, pos) % 2 == 0


# --------------------------------------------------------------------------- #
#  габариты
# --------------------------------------------------------------------------- #
def path_bbox(path: Path) -> Tuple[float, float, float, float]:
    xs: List[float] = []
    ys: List[float] = []
    for pts, _ in path:
        for x, y in pts:
            xs.append(x); ys.append(y)
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))
