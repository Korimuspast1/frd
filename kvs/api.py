"""
Высокоуровневый API автора: собираем .kvs кодом, а не руками в JSON.

    import kvs.api as K

    doc = K.animation("Heart", 512, 512, fps=60, frames=90, background="#12001f")
    K.linear_gradient(doc, "sky", ["#2b0b3a", "#0b0316"], angle=90, normalized=True)
    bg = K.layer(doc, "bg", K.rect([256, 256], [512, 512], fill="sky"))
    heart = K.layer(doc, "heart",
                    K.path([HEART], fill="#ff3b6b",
                           transform=K.transform(scale=K.keys([(0, [80, 80]), (45, [110, 110])],
                                                              easing="in-out-sine"))))
    blob = K.pack(doc, "heart.kvs")

Все ключевые кадры задаются как `K.keys([(кадр, значение, easing), ...])`
или `K.loop(...)` для бесшовной петли.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

from .container import encode
from .scene import EASINGS, compile_scene

__all__ = [
    "animation", "layer", "transform", "keys", "loop", "path", "rect", "round_rect",
    "ellipse", "circle", "polygon", "star", "fill", "stroke", "dash",
    "linear_gradient", "radial_gradient", "conic_gradient",
    "heart_points", "morph", "pack", "save", "easings", "GENERATOR",
]

GENERATOR = "kvs-python/1.0"


# --------------------------------------------------------------------------- #
#  документ
# --------------------------------------------------------------------------- #
def animation(name: str, width: int, height: int, *, fps: float = 60.0,
              frames: int = 60, background: str | None = None,
              author: str | None = None) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "name": name,
        "meta": {"generator": GENERATOR, "format": "kvs/1"},
        "canvas": {"width": width, "height": height, "fps": fps, "frames": frames},
        "assets": [],
        "layers": [],
    }
    if author:
        doc["meta"]["author"] = author
    if background is not None:
        doc["canvas"]["background"] = background
    return doc


def layer(doc: Dict[str, Any], name: str, geometry: Dict[str, Any], *,
          fill: Any = None, stroke: Dict[str, Any] | None = None,
          transform: Dict[str, Any] | None = None,
          blend: str = "normal", hidden: bool = False,
          parent: int | None = None) -> Dict[str, Any]:
    """Добавить слой в документ и вернуть его."""
    item: Dict[str, Any] = {"name": name, "geometry": geometry}
    if fill is not None:
        item["fill"] = fill
    if stroke is not None:
        item["stroke"] = stroke
    if transform is not None:
        item["transform"] = transform
    if blend != "normal":
        item["blend"] = blend
    if hidden:
        item["hidden"] = True
    if parent is not None:
        item["parent"] = parent
    doc.setdefault("layers", []).append(item)
    return item


# --------------------------------------------------------------------------- #
#  ключевые кадры
# --------------------------------------------------------------------------- #
def keys(kfs: Sequence[Sequence[Any]], *, easing: str = "linear",
         loop: bool = False) -> Dict[str, Any]:
    """
    kfs: [(кадр, значение), (кадр, значение, easing), ...]
    loop=True дублирует первый ключ в конце -- получается бесшовная петля.
    """
    out: List[List[Any]] = []
    for kf in kfs:
        t, v = kf[0], kf[1]
        e = kf[2] if len(kf) > 2 else easing
        out.append([t, v, e])
    if loop and len(out) > 1 and out[-1][1] != out[0][1]:
        out.append([out[-1][0], out[0][1], out[-1][2]])
    return {"k": out, "e": easing}


def loop(frames: int, values: Sequence[Any], *, easing: str = "in-out-sine") -> Dict[str, Any]:
    """Равномерно разложить значения на `frames` кадров и замкнуть петлю."""
    n = len(values)
    step = frames / n
    kfs = [[round(i * step, 4), values[i], easing] for i in range(n)]
    kfs.append([frames, values[0], easing])
    return {"k": kfs, "e": easing}


def easings() -> List[str]:
    return sorted(EASINGS)


# --------------------------------------------------------------------------- #
#  геометрия
# --------------------------------------------------------------------------- #
def path(subpaths: Sequence[Any], *, closed: bool = True,
         rule: str = "nonzero") -> Dict[str, Any]:
    """subpaths: список списков точек. Точка = [x,y] | [x,y,cx1,cy1,cx2,cy2] | [x,y,cx,cy] | [cx1,cy1,cx2,cy2,x,y]."""
    norm = []
    for sp in subpaths:
        if isinstance(sp, dict):
            norm.append(sp)
        else:
            norm.append({"points": [list(p) for p in sp], "closed": closed})
    g: Dict[str, Any] = {"type": "path", "subpaths": norm}
    if rule != "nonzero":
        g["rule"] = rule
    return g


def morph(frames_values: Sequence[Any], *, closed: bool = True, rule: str = "nonzero",
          easing: str = "linear") -> Dict[str, Any]:
    """
    Морфинг контура: frames_values = [(кадр, [subpath, ...]), ...].
    Subpath -- список точек; точка = [x,y] | [cx1,cy1,cx2,cy2,x,y] | [cx,cy,x,y].
    Количество и структура точек во всех ключах должны совпадать.
    """
    kfs = []
    ref = None
    for t, v in frames_values:
        subs = [list(sp) for sp in v]
        shape = [[len(p) for p in sp] for sp in subs]
        if ref is None:
            ref = shape
        elif shape != ref:
            raise ValueError(
                f"морфинг: структура точек в кадре {t} не совпадает с первым ключом "
                f"({shape} != {ref})")
        kfs.append([t, subs, easing])
    g: Dict[str, Any] = {"type": "path", "subpaths": {"k": kfs, "e": easing}}
    if rule != "nonzero":
        g["rule"] = rule
    return g


def rect(position=(0, 0), size=(100, 100), *, radius: Any = 0) -> Dict[str, Any]:
    g = {"type": "round-rect" if radius else "rect",
         "position": _v(position), "size": _v(size)}
    if radius:
        g["radius"] = radius
    return g


def round_rect(position=(0, 0), size=(100, 100), radius: Any = 10) -> Dict[str, Any]:
    return {"type": "round-rect", "position": _v(position),
            "size": _v(size), "radius": radius}


def ellipse(position=(0, 0), size=(100, 100)) -> Dict[str, Any]:
    return {"type": "ellipse", "position": _v(position), "size": _v(size)}


def circle(position=(0, 0), radius: Any = 50) -> Dict[str, Any]:
    return {"type": "circle", "position": _v(position), "radius": radius}


def polygon(position=(0, 0), sides: Any = 3, radius: Any = 50,
            rotation: Any = -90) -> Dict[str, Any]:
    return {"type": "polygon", "position": _v(position), "sides": sides,
            "radius": radius, "rotation": rotation}


def star(position=(0, 0), points: Any = 5, outer: Any = 100, inner: Any = 45,
         rotation: Any = -90, roundness: Any = 0) -> Dict[str, Any]:
    return {"type": "star", "position": _v(position), "points": points,
            "outer": outer, "inner": inner, "rotation": rotation,
            "roundness": roundness}


# --------------------------------------------------------------------------- #
#  краски
# --------------------------------------------------------------------------- #
def fill(color: str | None = None, *, opacity: Any = 1.0,
         gradient: str | None = None, rule: str = "nonzero") -> Dict[str, Any]:
    f: Dict[str, Any] = {}
    if gradient:
        f["gradient"] = gradient
    elif color is not None:
        f["color"] = color
    if opacity != 1.0:
        f["opacity"] = opacity
    if rule != "nonzero":
        f["rule"] = rule
    return f


def stroke(color: str, width: Any = 2.0, *, cap: str = "round", join: str = "round",
           opacity: Any = 1.0, miter_limit: float = 4.0,
           dash: Sequence[float] | None = None, dash_offset: Any = 0.0) -> Dict[str, Any]:
    s: Dict[str, Any] = {"color": color, "width": width, "cap": cap, "join": join}
    if opacity != 1.0:
        s["opacity"] = opacity
    if join == "miter":
        s["miter-limit"] = miter_limit
    if dash:
        s["dash"] = {"pattern": list(dash), "offset": dash_offset} if dash_offset else list(dash)
    return s


def _v(value: Any) -> Any:
    """Вектор: канал-словарь (ключевые кадры) не трогаем, список/кортеж копируем."""
    if isinstance(value, dict):
        return value
    if isinstance(value, (list, tuple)):
        return list(value)
    return value


def transform(*, anchor=(0, 0), position=(0, 0), scale: Any = (100, 100),
              rotation: Any = 0.0, opacity: Any = 1.0, skew: Any = (0, 0)) -> Dict[str, Any]:
    t: Dict[str, Any] = {"anchor": _v(anchor), "position": _v(position)}
    if scale != (100, 100):
        t["scale"] = scale
    if rotation != 0.0:
        t["rotation"] = rotation
    if opacity != 1.0:
        t["opacity"] = opacity
    if skew != (0, 0):
        t["skew"] = skew
    return t


# --------------------------------------------------------------------------- #
#  градиенты
# --------------------------------------------------------------------------- #
def _stops(colors: Sequence[Any]) -> List[Dict[str, Any]]:
    out = []
    n = len(colors)
    for i, c in enumerate(colors):
        if isinstance(c, (list, tuple)) and len(c) == 2 and isinstance(c[0], (int, float)):
            out.append({"position": float(c[0]), "color": c[1]})
        else:
            out.append({"position": i / max(1, n - 1), "color": c})
    return out


def linear_gradient(doc: Dict[str, Any], gid: str, colors: Sequence[Any], *,
                    angle: float = 90.0, from_to: Tuple[Tuple[float, float],
                                                         Tuple[float, float]] | None = None,
                    normalized: bool = True, spread: str = "pad") -> str:
    g: Dict[str, Any] = {"id": gid, "type": "linear", "stops": _stops(colors)}
    if from_to:
        g["from"] = _v(from_to[0])
        g["to"] = _v(from_to[1])
    else:
        g["angle"] = angle
    if normalized:
        g["normalized"] = True
    if spread != "pad":
        g["spread"] = spread
    doc.setdefault("assets", []).append(g)
    return gid


def radial_gradient(doc: Dict[str, Any], gid: str, colors: Sequence[Any], *,
                    center=(0.5, 0.5), radius: float = 0.5, normalized: bool = True,
                    spread: str = "pad", focus=None) -> str:
    g: Dict[str, Any] = {"id": gid, "type": "radial", "stops": _stops(colors),
                         "center": _v(center), "radius": radius}
    if normalized:
        g["normalized"] = True
    if spread != "pad":
        g["spread"] = spread
    if focus is not None:
        g["focus"] = _v(focus)
    doc.setdefault("assets", []).append(g)
    return gid


def conic_gradient(doc: Dict[str, Any], gid: str, colors: Sequence[Any], *,
                   center=(0.5, 0.5), angle: float = 0.0, normalized: bool = True) -> str:
    g: Dict[str, Any] = {"id": gid, "type": "conic", "stops": _stops(colors),
                         "center": _v(center), "angle": angle}
    if normalized:
        g["normalized"] = True
    doc.setdefault("assets", []).append(g)
    return gid


# --------------------------------------------------------------------------- #
#  готовые формы
# --------------------------------------------------------------------------- #
def heart_points(cx: float = 0.0, cy: float = 0.0, size: float = 100.0) -> List[List[float]]:
    """
    Классическое сердце из шести кубических Безье.
    Формат точек: первый -- [x, y], остальные -- [cx1, cy1, cx2, cy2, x, y].
    """
    # базовый контур в системе 100x90 с центром в (50, 45)
    base = [
        [50, 30],
        [50, 22, 44, 12, 34, 12],
        [21, 12, 12, 23, 12, 35],
        [12, 52, 28, 62, 50, 80],
        [72, 62, 88, 52, 88, 35],
        [88, 23, 79, 12, 66, 12],
        [56, 12, 50, 22, 50, 30],
    ]
    k = size / 76.0
    out: List[List[float]] = []
    for i, p in enumerate(base):
        v = [round(cx + (p[j] - 50) * k, 3) if j % 2 == 0 else round(cy + (p[j] - 45) * k, 3)
             for j in range(len(p))]
        out.append(v)
    return out


def blob_points(cx: float, cy: float, radii: Sequence[float], phase: float = 0.0,
                closed: bool = True) -> List[List[float]]:
    """Замкнутая гладкая «капля» по списку радиусов (для морфинга)."""
    n = len(radii)
    pts: List[List[float]] = []
    for i, r in enumerate(radii):
        a = phase + i * 2 * math.pi / n
        a_next = phase + (i + 1) * 2 * math.pi / n
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        # касательные для гладкой стыковки
        tan = r * (2 * math.pi / n) * 0.5522847498
        pts.append([x, y,
                    x - tan * math.sin(a), y + tan * math.cos(a),
                    ])
    return pts


# --------------------------------------------------------------------------- #
#  упаковка
# --------------------------------------------------------------------------- #
def pack(doc: Dict[str, Any], out: str | None = None, *, codec: str = "zlib",
         preview: bool = True, ss: int = 3) -> bytes:
    from . import compile_dict
    return compile_dict(doc, codec=codec, preview=preview, out=out, ss=ss)


def save(doc: Dict[str, Any], out: str, **kw) -> str:
    pack(doc, out, **kw)
    return out
