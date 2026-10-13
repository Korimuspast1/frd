"""
Движок рендера .kvs: сцена + момент времени -> пиксели.

Пайплайн кадра:
  1. вычислить анимированные свойства каждого слоя (scene.eval_channel);
  2. собрать геометрию слоя и «расплющить» кривые Безье в полилинии;
  3. применить матрицу слоя;
  4. обводку превратить в заполняемый аутлайн (geometry.stroke_outline);
  5. растеризовать в карту покрытия (raster.coverage);
  6. покрасить покрытие (цвет или градиент) и смешать с кадром.

Только stdlib -- никаких внешних зависимостей.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Sequence, Tuple

from . import geometry as G
from .paint import LinearGradient, Paint, SolidPaint, build_gradient, build_paint
from .raster import Framebuffer, coverage
from .scene import channel_is_animated, eval_channel, parse_color

CAP_NAMES = {0: "butt", 1: "round", 2: "square"}
JOIN_NAMES = {0: "miter", 1: "round", 2: "bevel"}
BLEND_NAMES = {0: "normal", 1: "multiply", 2: "screen", 3: "overlay", 4: "add"}


class RenderError(Exception):
    pass


# --------------------------------------------------------------------------- #
#  хелперы
# --------------------------------------------------------------------------- #
def _vec(v: Any, n: int) -> List[float]:
    if isinstance(v, (int, float)):
        return [float(v)] * n
    out = [float(x) for x in v]
    if not out:
        return [0.0] * n
    while len(out) < n:
        out.append(out[-1])
    return out[:n]


def _norm01(v: float) -> float:
    """Непрозрачность: принимаем и 0..1, и 0..100 (как в After Effects)."""
    if v > 1.5:
        v = v / 100.0
    return 0.0 if v < 0 else (1.0 if v > 1 else v)


def _scale_vec(v: Any) -> List[float]:
    """Масштаб: 100 = 1.0 (проценты) либо 1.0 = 1.0. Порог -- 3.0."""
    out = _vec(v, 2)
    if any(abs(x) > 3.0 for x in out):
        out = [x / 100.0 for x in out]
    return out


def _invert(m: G.Matrix) -> G.Matrix:
    det = m.a * m.d - m.b * m.c
    if abs(det) < 1e-12:
        return G.Matrix()
    ia, ib = m.d / det, -m.b / det
    ic, idd = -m.c / det, m.a / det
    return G.Matrix(ia, ib, ic, idd, -(ia * m.e + ic * m.f), -(ib * m.e + idd * m.f))


def _build_subpaths(subs: Sequence[Any]) -> G.Path:
    out: G.Path = []
    for sp in subs or []:
        pts, closed = G.compact_subpath_to_points(sp)
        if len(pts) >= 2:
            out.append((pts, closed))
    return out


def _multiply(dst: int, src: int) -> int:
    return (dst * src) // 255


def _screen(dst: int, src: int) -> int:
    return 255 - ((255 - dst) * (255 - src)) // 255


def _overlay(dst: int, src: int) -> int:
    if dst < 128:
        return (dst * src) // 128
    return 255 - ((255 - dst) * (255 - src)) // 128


def _add(dst: int, src: int) -> int:
    v = dst + src
    return 255 if v > 255 else v


_BLEND_FN: Dict[str, Callable[[int, int], int]] = {
    "multiply": _multiply,
    "screen": _screen,
    "overlay": _overlay,
    "add": _add,
}


# --------------------------------------------------------------------------- #
#  смешивание покрытия с кадром
# --------------------------------------------------------------------------- #
def _blit_solid(fb: Framebuffer, cov: bytearray, x0: int, y0: int, x1: int, y1: int,
                color: Sequence[int], alpha: float, blend: str) -> None:
    cr, cg, cb, ca = color
    ca = (ca / 255.0) * alpha
    if ca <= 0:
        return
    px = fb.px
    w = fb.w
    row_w = x1 - x0
    fn = _BLEND_FN.get(blend) if blend != "normal" else None
    for py in range(y1 - y0):
        base = ((y0 + py) * w + x0) * 4
        crow = py * row_w
        for x in range(row_w):
            av = cov[crow + x]
            if not av:
                continue
            i = base + x * 4
            sa = ca * av * (1.0 / 255.0)
            da = px[i + 3] * (1.0 / 255.0)
            if fn is not None:
                if da <= 0:
                    continue
                px[i] = fn(px[i], cr)
                px[i + 1] = fn(px[i + 1], cg)
                px[i + 2] = fn(px[i + 2], cb)
                px[i + 3] = int((sa + da * (1.0 - sa)) * 255.0)
                continue
            oa = sa + da * (1.0 - sa)
            if oa <= 0:
                continue
            k = (1.0 - sa) / oa
            inv_oa = sa / oa
            px[i] = int(cr * inv_oa + px[i] * da * k)
            px[i + 1] = int(cg * inv_oa + px[i + 1] * da * k)
            px[i + 2] = int(cb * inv_oa + px[i + 2] * da * k)
            px[i + 3] = int(oa * 255.0)


def _blit_gradient(fb: Framebuffer, cov: bytearray, x0: int, y0: int, x1: int, y1: int,
                   paint: Paint, inv: G.Matrix, alpha: float, blend: str) -> None:
    lut = paint.lut
    px = fb.px
    w = fb.w
    row_w = x1 - x0
    a, b, c, d, e, f = inv.a, inv.b, inv.c, inv.d, inv.e, inv.f
    fn = _BLEND_FN.get(blend) if blend != "normal" else None
    lut_index = paint.lut_index

    for py in range(y1 - y0):
        wy = y0 + py + 0.5
        base = ((y0 + py) * w + x0) * 4
        crow = py * row_w
        # линейная часть преобразования, зависящая только от y
        ox = c * wy + e
        oy = d * wy + f
        for x in range(row_w):
            av = cov[crow + x]
            if not av:
                continue
            wx = x0 + x + 0.5
            cr, cg, cb, ca = lut[lut_index(a * wx + ox, b * wx + oy)]
            i = base + x * 4
            sa = ca * alpha * av * (1.0 / 65025.0)
            if sa <= 0:
                continue
            da = px[i + 3] * (1.0 / 255.0)
            if fn is not None:
                if da <= 0:
                    continue
                px[i] = fn(px[i], cr)
                px[i + 1] = fn(px[i + 1], cg)
                px[i + 2] = fn(px[i + 2], cb)
                px[i + 3] = int((sa + da * (1.0 - sa)) * 255.0)
                continue
            oa = sa + da * (1.0 - sa)
            if oa <= 0:
                continue
            k = (1.0 - sa) / oa
            s = sa / oa
            px[i] = int(cr * s + px[i] * da * k)
            px[i + 1] = int(cg * s + px[i + 1] * da * k)
            px[i + 2] = int(cb * s + px[i + 2] * da * k)
            px[i + 3] = int(oa * 255.0)


# --------------------------------------------------------------------------- #
#  рендерер
# --------------------------------------------------------------------------- #
class Renderer:
    """Движок: держит сцену и рисует любой её кадр."""

    def __init__(self, scene: Dict[str, Any], ss: int = 4, flat_tol: float = 0.15):
        self.scene = scene
        c = scene.get("c", {})
        self.width = int(c.get("w", 0))
        self.height = int(c.get("h", 0))
        self.fps = float(c.get("r", 0))
        self.frames = int(c.get("n", 0))
        self.background = c.get("b")
        self.assets: Dict[str, Any] = scene.get("a", {}) or {}
        self.layers: List[Dict[str, Any]] = scene.get("l", []) or []
        self.ss = max(1, int(ss))
        self.flat_tol = float(flat_tol)
        self._geom_cache: Dict[int, G.Path] = {}

    # ------------------------------------------------------------------ #
    @classmethod
    def from_file(cls, path: str, **kw) -> "Renderer":
        from .container import open_kvs
        return cls(open_kvs(path).scene, **kw)

    def duration(self) -> float:
        return self.frames / self.fps if self.fps else 0.0

    def render(self, frame: float) -> Framebuffer:
        """Кадр по (возможно дробному) индексу."""
        bg = parse_color(self.background) if self.background is not None else (0, 0, 0, 0)
        fb = Framebuffer(self.width, self.height, bg)
        t = float(frame)
        for layer in self.layers:
            if layer.get("hd"):
                continue
            self.draw_layer(fb, layer, t)
        return fb

    def render_index(self, index: int) -> Framebuffer:
        return self.render(float(index))

    # ------------------------------------------------------------------ #
    def draw_layer(self, fb: Framebuffer, layer: Dict[str, Any], t: float) -> None:
        tr = layer.get("t", {}) or {}
        pos = _vec(eval_channel(tr.get("p", [0.0, 0.0]), t), 2)
        anchor = _vec(eval_channel(tr.get("a", [0.0, 0.0]), t), 2)
        scale = _scale_vec(eval_channel(tr.get("s", [100.0, 100.0]), t))
        rot = float(eval_channel(tr.get("r", 0.0), t))
        skew = _vec(eval_channel(tr.get("k", [0.0, 0.0]), t), 2)
        opacity = _norm01(float(eval_channel(tr.get("o", 1.0), t)))
        if opacity <= 0.002:
            return

        geom = layer.get("g")
        if geom is None:
            return
        local, local_bbox = self.local_geometry(layer, geom, t)
        if not local:
            return

        m = G.layer_matrix(pos, anchor, scale, rot, skew)
        parent = self._parent_matrix(layer, t)
        if parent is not None:
            m = parent.multiply(m)
        world = m.apply_path(local)
        ls = m.length_scale()
        blend = BLEND_NAMES.get(layer.get("b", 0), "normal")
        inv = _invert(m)

        stroke = layer.get("s")
        if stroke:
            width = float(eval_channel(stroke.get("w", 1.0), t)) * ls
            if width > 1e-4:
                cap = CAP_NAMES.get(stroke.get("lc", 1), "round")
                join = JOIN_NAMES.get(stroke.get("lj", 1), "round")
                miter = float(stroke.get("ml", 4.0))
                dash = stroke.get("d")
                dash_off = float(eval_channel(stroke.get("do", 0.0), t)) if "do" in stroke else 0.0
                polys: G.Path = []
                for pts, closed in world:
                    if dash:
                        pat = [max(1e-6, float(dv) * ls) for dv in dash]
                        for seg in G.dash_polyline(pts, pat, dash_off * ls):
                            if len(seg) >= 2:
                                polys += G.stroke_outline(seg, False, width, cap, join,
                                                          miter, self.flat_tol)
                    else:
                        polys += G.stroke_outline(pts, closed, width, cap, join,
                                                  miter, self.flat_tol)
                if polys:
                    self._paint(fb, polys, stroke, t, opacity, local_bbox, inv, blend,
                                "nonzero")

        fill = layer.get("f")
        if fill:
            rule = "evenodd" if fill.get("ru", 0) == 1 else "nonzero"
            self._paint(fb, world, fill, t, opacity, local_bbox, inv, blend, rule)

    # ------------------------------------------------------------------ #
    def _paint(self, fb: Framebuffer, polys: G.Path, spec: Dict[str, Any], t: float,
               layer_opacity: float, local_bbox, inv: G.Matrix, blend: str,
               rule: str) -> None:
        alpha = layer_opacity * _norm01(float(eval_channel(spec.get("o", 1.0), t)))
        if alpha <= 0.002:
            return
        cov, x0, y0, x1, y1 = coverage(polys, fb.w, fb.h, self.ss, rule)
        if not cov:
            return
        if "c" in spec:
            color = parse_color(eval_channel(spec["c"], t))
            _blit_solid(fb, cov, x0, y0, x1, y1, color, alpha, blend)
            return
        gspec = spec.get("g")
        if gspec is None:
            _blit_solid(fb, cov, x0, y0, x1, y1, (255, 255, 255, 255), alpha, blend)
            return
        if isinstance(gspec, str):
            gid = gspec
            gspec = self.assets.get(gid)
            if gspec is None:
                raise RenderError(f"ассет градиента не найден: {gid!r}")
        paint = build_gradient(gspec, local_bbox)
        if isinstance(paint, SolidPaint):
            _blit_solid(fb, cov, x0, y0, x1, y1, paint.rgba, alpha, blend)
        else:
            _blit_gradient(fb, cov, x0, y0, x1, y1, paint, inv, alpha, blend)

    # ------------------------------------------------------------------ #
    def local_geometry(self, layer: Dict[str, Any], geom: Any,
                       t: float) -> Tuple[G.Path, Tuple[float, float, float, float]]:
        """Геометрия слоя в локальных координатах + её bbox (для градиентов)."""
        if isinstance(geom, str):
            gid = geom
            geom = self.assets.get(gid)
            if geom is None:
                raise RenderError(f"ассет геометрии не найден: {gid!r}")
        kind = geom.get("t")

        if kind == "p":
            subs = geom.get("s")
            if isinstance(subs, dict) and channel_is_animated(subs):   # морфинг пути
                path = _build_subpaths(eval_channel(subs, t))
                return path, G.path_bbox(path)
            key = id(geom)
            cached = self._geom_cache.get(key)
            if cached is None:
                cached = _build_subpaths(subs)
                self._geom_cache[key] = cached
            return cached, G.path_bbox(cached)

        if kind in ("r", "rr"):
            pos = _vec(eval_channel(geom.get("p", [0, 0]), t), 2)
            size = _vec(eval_channel(geom["z"], t), 2)
            rad = max(0.0, float(eval_channel(geom.get("r", 0), t))) if kind == "rr" else 0.0
            path = G.rect_path(pos[0], pos[1], abs(size[0]), abs(size[1]), rad)
            return path, (pos[0] - abs(size[0]) / 2, pos[1] - abs(size[1]) / 2,
                          pos[0] + abs(size[0]) / 2, pos[1] + abs(size[1]) / 2)

        if kind == "e":
            pos = _vec(eval_channel(geom.get("p", [0, 0]), t), 2)
            size = _vec(eval_channel(geom["z"], t), 2)
            rx, ry = abs(size[0]) / 2, abs(size[1]) / 2
            path = G.ellipse_path(pos[0], pos[1], rx, ry)
            return path, (pos[0] - rx, pos[1] - ry, pos[0] + rx, pos[1] + ry)

        if kind == "ci":
            pos = _vec(eval_channel(geom.get("p", [0, 0]), t), 2)
            r = abs(float(eval_channel(geom["r"], t)))
            path = G.ellipse_path(pos[0], pos[1], r, r)
            return path, (pos[0] - r, pos[1] - r, pos[0] + r, pos[1] + r)

        if kind == "pg":
            pos = _vec(eval_channel(geom.get("p", [0, 0]), t), 2)
            sides = max(3, int(round(float(eval_channel(geom["n"], t)))))
            r = abs(float(eval_channel(geom["r"], t)))
            rot = float(eval_channel(geom.get("rot", -90), t))
            path = G.polygon_path(pos[0], pos[1], r, sides, rot)
            return path, (pos[0] - r, pos[1] - r, pos[0] + r, pos[1] + r)

        if kind == "st":
            pos = _vec(eval_channel(geom.get("p", [0, 0]), t), 2)
            n = max(2, int(round(float(eval_channel(geom["n"], t)))))
            r1 = abs(float(eval_channel(geom["r1"], t)))
            r2 = abs(float(eval_channel(geom["r2"], t)))
            rot = float(eval_channel(geom.get("rot", -90), t))
            rd = float(eval_channel(geom.get("rd", 0), t))
            path = G.star_path(pos[0], pos[1], r1, r2, n, rot, rd)
            return path, (pos[0] - r1, pos[1] - r1, pos[0] + r1, pos[1] + r1)

        raise RenderError(f"неизвестный тип геометрии: {kind!r}")

    # ------------------------------------------------------------------ #
    def _parent_matrix(self, layer: Dict[str, Any], t: float) -> G.Matrix | None:
        """Слой может иметь родителя: его матрица применяется поверх собственной."""
        chain: List[G.Matrix] = []
        seen = set()
        cur = layer
        for _ in range(16):
            pi = cur.get("pi")
            if pi is None or pi in seen:
                break
            seen.add(pi)
            parent = self._layer_by_index(pi)
            if parent is None:
                break
            tr = parent.get("t", {}) or {}
            pos = _vec(eval_channel(tr.get("p", [0.0, 0.0]), t), 2)
            anchor = _vec(eval_channel(tr.get("a", [0.0, 0.0]), t), 2)
            scale = _scale_vec(eval_channel(tr.get("s", [100.0, 100.0]), t))
            rot = float(eval_channel(tr.get("r", 0.0), t))
            skew = _vec(eval_channel(tr.get("k", [0.0, 0.0]), t), 2)
            chain.append(G.layer_matrix(pos, anchor, scale, rot, skew))
            cur = parent
        if not chain:
            return None
        m = chain[-1]
        for c in reversed(chain[:-1]):
            m = m.multiply(c)
        return m

    def _layer_by_index(self, index: int) -> Dict[str, Any] | None:
        for layer in self.layers:
            if layer.get("i") == index:
                return layer
        if 0 <= index < len(self.layers):
            return self.layers[index]
        return None

    # ------------------------------------------------------------------ #
    def layer_report(self) -> List[Dict[str, Any]]:
        """Короткая сводка по слоям (для inspect)."""
        out = []
        for layer in self.layers:
            geom = layer.get("g")
            if isinstance(geom, str):
                kind = f"ref:{geom}"
            else:
                kind = {"p": "path", "r": "rect", "rr": "round-rect", "e": "ellipse",
                        "ci": "circle", "pg": "polygon", "st": "star"}.get(geom.get("t"), "?")
            animated = []
            tr = layer.get("t", {}) or {}
            names = {"p": "position", "a": "anchor", "s": "scale", "r": "rotation",
                     "o": "opacity", "k": "skew"}
            for key, label in names.items():
                if key in tr and channel_is_animated(tr[key]):
                    animated.append(label)
            if layer.get("f") and channel_is_animated(layer["f"].get("c")):
                animated.append("fill.color")
            if layer.get("s"):
                if channel_is_animated(layer["s"].get("c")):
                    animated.append("stroke.color")
                if channel_is_animated(layer["s"].get("w")):
                    animated.append("stroke.width")
            if not isinstance(geom, str) and geom.get("t") == "p" \
                    and isinstance(geom.get("s"), dict):
                animated.append("path.morph")
            out.append({
                "index": layer.get("i"),
                "name": layer.get("nm"),
                "geometry": kind,
                "fill": "yes" if layer.get("f") else "no",
                "stroke": "yes" if layer.get("s") else "no",
                "blend": BLEND_NAMES.get(layer.get("b", 0), "normal"),
                "animated": animated or ["-"],
            })
        return out


# --------------------------------------------------------------------------- #
#  пост-обработка
# --------------------------------------------------------------------------- #
def downscale(fb: Framebuffer, factor: int) -> Framebuffer:
    """Усредняющий даунскейл в `factor` раз -- для превью и маленьких рендеров."""
    if factor <= 1:
        return fb
    w, h = fb.w // factor, fb.h // factor
    if w < 1 or h < 1:
        return fb
    out = Framebuffer(w, h)
    src = fb.px
    sw = fb.w
    n = factor * factor
    for y in range(h):
        for x in range(w):
            r = g = b = a = 0
            for dy in range(factor):
                row = ((y * factor + dy) * sw + x * factor) * 4
                for dx in range(factor):
                    i = row + dx * 4
                    r += src[i]
                    g += src[i + 1]
                    b += src[i + 2]
                    a += src[i + 3]
            o = (y * w + x) * 4
            out.px[o] = r // n
            out.px[o + 1] = g // n
            out.px[o + 2] = b // n
            out.px[o + 3] = a // n
    return out


def resize(fb: Framebuffer, width: int, height: int) -> Framebuffer:
    """Билинейное масштабирование кадра (чтобы рендерить в любой размер)."""
    if width == fb.w and height == fb.h:
        return fb
    out = Framebuffer(max(1, width), max(1, height))
    sx = fb.w / max(1, width)
    sy = fb.h / max(1, height)
    src = fb.px
    sw, sh = fb.w, fb.h
    for y in range(height):
        fy = min(sh - 1.001, (y + 0.5) * sy - 0.5)
        y0 = int(fy)
        y1 = min(sh - 1, y0 + 1)
        wy = fy - y0
        for x in range(width):
            fx = min(sw - 1.001, (x + 0.5) * sx - 0.5)
            x0 = int(fx)
            x1 = min(sw - 1, x0 + 1)
            wx = fx - x0
            i00 = (y0 * sw + x0) * 4
            i10 = (y0 * sw + x1) * 4
            i01 = (y1 * sw + x0) * 4
            i11 = (y1 * sw + x1) * 4
            o = (y * width + x) * 4
            for ch in range(4):
                top = src[i00 + ch] * (1 - wx) + src[i10 + ch] * wx
                bot = src[i01 + ch] * (1 - wx) + src[i11 + ch] * wx
                out.px[o + ch] = int(top * (1 - wy) + bot * wy)
    return out
