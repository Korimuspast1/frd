"""
Сцена .kvs: компактная модель, авторинг-модель и вычисление анимации.

Компактный JSON (то, что лежит внутри контейнера) намеренно «телеграфный»:
короткие ключи, массивы вместо объектов -- так же, как Lottie/TGS экономят байты.
Полная спецификация: docs/SCENE.md.

Авторинг-формат -- человекочитаемый JSON с длинными ключами;
`compile_scene()` превращает его в компактный.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Sequence, Tuple

# --------------------------------------------------------------------------- #
#  easing
# --------------------------------------------------------------------------- #
def _cubic_bezier(p1x: float, p1y: float, p2x: float, p2y: float) -> Callable[[float], float]:
    """CSS-подобная кривая Безье 3-го порядка из (0,0) в (1,1)."""
    cx, bx, ax = 3.0 * p1x, 3.0 * (p2x - p1x) - 3.0 * p1x, 1.0 - 3.0 * p2x + 3.0 * p1x
    cy, by, ay = 3.0 * p1y, 3.0 * (p2y - p1y) - 3.0 * p1y, 1.0 - 3.0 * p2y + 3.0 * p1y

    def sample_x(t: float) -> float:
        return ((ax * t + bx) * t + cx) * t

    def sample_y(t: float) -> float:
        return ((ay * t + by) * t + cy) * t

    def solve(x: float) -> float:
        t = x
        for _ in range(8):  # Ньютона достаточно для точности ~1e-7
            err = sample_x(t) - x
            if abs(err) < 1e-7:
                return t
            d = (3.0 * ax * t + 2.0 * bx) * t + cx
            if abs(d) < 1e-9:
                break
            t -= err / d
        lo, hi = 0.0, 1.0  # запасной вариант: бинарный поиск
        t = x
        for _ in range(32):
            v = sample_x(t)
            if abs(v - x) < 1e-7:
                return t
            if v < x:
                lo = t
            else:
                hi = t
            t = 0.5 * (lo + hi)
        return t

    return lambda x: 0.0 if x <= 0 else (1.0 if x >= 1 else sample_y(solve(x)))


EASINGS: Dict[str, Callable[[float], float]] = {
    "linear": lambda t: t,
    "hold": lambda t: 0.0,          # значение держится до следующего ключа
    "step": lambda t: 0.0 if t < 1.0 else 1.0,
    "in-quad": lambda t: t * t,
    "out-quad": lambda t: t * (2 - t),
    "in-out-quad": lambda t: 2 * t * t if t < 0.5 else -1 + (4 - 2 * t) * t,
    "in-cubic": lambda t: t ** 3,
    "out-cubic": lambda t: 1 - (1 - t) ** 3,
    "in-out-cubic": lambda t: 4 * t ** 3 if t < 0.5 else 1 - ((-2 * t + 2) ** 3) / 2,
    "in-quart": lambda t: t ** 4,
    "out-quart": lambda t: 1 - (1 - t) ** 4,
    "in-out-quart": lambda t: 8 * t ** 4 if t < 0.5 else 1 - ((-2 * t + 2) ** 4) / 2,
    "in-quint": lambda t: t ** 5,
    "out-quint": lambda t: 1 - (1 - t) ** 5,
    "in-sine": lambda t: 1 - math.cos(t * math.pi / 2),
    "out-sine": lambda t: math.sin(t * math.pi / 2),
    "in-out-sine": lambda t: -(math.cos(math.pi * t) - 1) / 2,
    "in-expo": lambda t: 0.0 if t == 0 else 2.0 ** (10 * t - 10),
    "out-expo": lambda t: 1.0 if t >= 1 else 1 - 2.0 ** (-10 * t),
    "in-out-expo": lambda t: 0.0 if t == 0 else (1.0 if t >= 1 else (
        2.0 ** (20 * t - 10) / 2 if t < 0.5 else (2 - 2.0 ** (-20 * t + 10)) / 2)),
    "in-circ": lambda t: 1 - math.sqrt(max(0.0, 1 - t * t)),
    "out-circ": lambda t: math.sqrt(max(0.0, 1 - (t - 1) ** 2)),
    "in-out-circ": lambda t: (
        (1 - math.sqrt(max(0.0, 1 - 4 * t * t))) / 2 if t < 0.5
        else (math.sqrt(max(0.0, 1 - (-2 * t + 2) ** 2)) + 1) / 2),
    "out-back": lambda t: 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2,
    "in-back": lambda t: 2.70158 * t ** 3 - 1.70158 * t ** 2,
    "in-out-back": lambda t: (
        8 * t * t * ((2.5949095 + 1) * 2 * t - 2.5949095) / 2 if t < 0.5
        else ((2 * t - 2) ** 2 * ((2.5949095 + 1) * (2 * t - 2) + 2.5949095) + 2) / 2),
    "out-elastic": lambda t: 0.0 if t == 0 else (1.0 if t >= 1 else
        2.0 ** (-10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi / 3)) + 1),
    "in-elastic": lambda t: 0.0 if t == 0 else (1.0 if t >= 1 else
        -(2.0 ** (10 * t - 10)) * math.sin((t * 10 - 10.75) * (2 * math.pi / 3))),
    "out-bounce": None,  # заполняется ниже
    "in-bounce": None,
    "in-out-bounce": None,
    # совпадение с популярными CSS-кривыми
    "ease": _cubic_bezier(0.25, 0.1, 0.25, 1.0),
    "ease-in": _cubic_bezier(0.42, 0.0, 1.0, 1.0),
    "ease-out": _cubic_bezier(0.0, 0.0, 0.58, 1.0),
    "ease-in-out": _cubic_bezier(0.42, 0.0, 0.58, 1.0),
}


def _bounce_out(t: float) -> float:
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    if t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


EASINGS["out-bounce"] = _bounce_out
EASINGS["in-bounce"] = lambda t: 1 - _bounce_out(1 - t)
EASINGS["in-out-bounce"] = lambda t: (
    (1 - _bounce_out(1 - 2 * t)) / 2 if t < 0.5 else (1 + _bounce_out(2 * t - 1)) / 2)

_EASING_IDS: List[str] = sorted(EASINGS)
_EASING_ID = {name: i for i, name in enumerate(_EASING_IDS)}


def easing_by_spec(spec: Any) -> Callable[[float], float]:
    """spec: имя строкой | int-id | [x1,y1,x2,y2] кастомная кривая Безье."""
    if spec is None:
        return EASINGS["linear"]
    if isinstance(spec, (int, float)) and not isinstance(spec, bool):
        i = int(spec)
        return EASINGS[_EASING_IDS[i % len(_EASING_IDS)]]
    if isinstance(spec, str):
        fn = EASINGS.get(spec)
        if fn is None:
            raise KeyError(f"неизвестный easing: {spec}")
        return fn
    if isinstance(spec, (list, tuple)) and len(spec) == 4:
        return _cubic_bezier(*[float(v) for v in spec])
    raise TypeError(f"непонятный easing: {spec!r}")


# --------------------------------------------------------------------------- #
#  вычисление анимированных значений
# --------------------------------------------------------------------------- #
Number = float


def _mix(a: Any, b: Any, t: float) -> Any:
    if isinstance(a, bool) or isinstance(b, bool):
        return a if t < 0.5 else b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a + (b - a) * t
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            raise ValueError(f"нельзя интерполировать массивы разной длины: {len(a)} vs {len(b)}")
        return [_mix(x, y, t) for x, y in zip(a, b)]
    if isinstance(a, str) and isinstance(b, str):
        ca, cb = parse_color(a), parse_color(b)
        return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))
    return a if t < 0.5 else b


def eval_channel(ch: Any, time: float) -> Any:
    """
    Канал свойства. Варианты:
      * статика:  {"v": X}
      * ключи:    {"k": [[t0, v0, e0], [t1, v1, e1], ...]}   t -- в кадрах, e -- easing
                  (последний ключ может быть [tN, vN])
      *裸 значение: X
    Возвращает значение в момент `time` (в кадрах).
    """
    if isinstance(ch, dict) and ("k" in ch or "v" in ch):
        if "k" in ch:
            keys = ch["k"]
            if not keys:
                raise ValueError("пустой набор ключевых кадров")
            if not isinstance(keys[0], (list, tuple)):
                return keys  # массив значений без ключей -> статика
            if time <= keys[0][0]:
                return keys[0][1]
            last = keys[-1]
            if time >= last[0]:
                return last[1]
            for i in range(len(keys) - 1):
                k0, k1 = keys[i], keys[i + 1]
                t0, v0 = k0[0], k0[1]
                t1, v1 = k1[0], k1[1]
                if t0 <= time <= t1:
                    span = t1 - t0
                    if span <= 0:
                        return v1
                    e = easing_by_spec(k0[2] if len(k0) > 2 else ch.get("e", "linear"))
                    return _mix(v0, v1, e((time - t0) / span))
            return last[1]
        return ch["v"]
    return ch


def channel_is_animated(ch: Any) -> bool:
    return isinstance(ch, dict) and "k" in ch and isinstance(ch["k"], list) \
        and bool(ch["k"]) and isinstance(ch["k"][0], (list, tuple))


def channel_bounds(ch: Any) -> Tuple[Any, Any]:
    """(min, max) значения канала -- для расчёта габаритов/превью."""
    if not channel_is_animated(ch):
        v = eval_channel(ch, 0.0)
        return v, v
    vals = [k[1] for k in ch["k"]]
    return vals[0], vals[-1]


# --------------------------------------------------------------------------- #
#  цвет
# --------------------------------------------------------------------------- #
def parse_color(c: Any) -> Tuple[int, int, int, int]:
    """
    "#rgb" | "#rrggbb" | "#rrggbbaa" | [r,g,b] | [r,g,b,a] (0..255) -> RGBA
    """
    if isinstance(c, str):
        s = c.strip().lstrip("#")
        if len(s) == 3:
            s = "".join(ch * 2 for ch in s)
        if len(s) == 4:
            s = "".join(ch * 2 for ch in s)
        if len(s) == 6:
            s += "ff"
        if len(s) != 8:
            raise ValueError(f"непонятный цвет: {c!r}")
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))  # type: ignore[return-value]
    if isinstance(c, (list, tuple)):
        vals = [float(v) for v in c]
        if len(vals) == 3:
            vals.append(255.0)
        if len(vals) != 4:
            raise ValueError(f"непонятный цвет: {c!r}")
        return tuple(max(0, min(255, int(round(v)))) for v in vals)  # type: ignore[return-value]
    raise TypeError(f"непонятный цвет: {c!r}")


# --------------------------------------------------------------------------- #
#  авторинг -> компакт
# --------------------------------------------------------------------------- #
_GEOM_KEYS = {
    "path": "p", "rect": "r", "round-rect": "rr", "ellipse": "e",
    "circle": "ci", "polygon": "pg", "star": "st",
}

_FILL_KEYS = {"color": "c", "gradient": "g", "opacity": "o"}
_STROKE_KEYS = {
    "color": "c", "width": "w", "opacity": "o", "cap": "lc", "join": "lj",
    "miter-limit": "ml", "dash": "d",
}
_TRANSFORM_KEYS = {
    "anchor": "a", "position": "p", "scale": "s", "rotation": "r",
    "opacity": "o", "skew": "k", "skew-axis": "ka",
}
_LAYER_KEYS = {
    "name": "nm", "geometry": "g", "fill": "f", "stroke": "s",
    "transform": "t", "blend": "b", "hidden": "hd", "parent": "pi",
}
_CAPS = {"butt": 0, "round": 1, "square": 2}
_JOINS = {"miter": 0, "round": 1, "bevel": 2}
_BLENDS = {"normal": 0, "multiply": 1, "screen": 2, "overlay": 3, "add": 4}
_RULES = {"nonzero": 0, "evenodd": 1}


def _c_channel(value: Any) -> Any:
    """
    Сжать канал: статическое значение остаётся «голым»,
    у анимации easing каждого ключа кодируется коротким id.
    """
    if isinstance(value, dict):
        if "k" not in value:
            return value.get("v") if "v" in value else value
        kfs = []
        for kf in value["k"]:
            kf = list(kf)
            if len(kf) > 2:
                kf[2] = _c_easing(kf[2])
            kfs.append(kf)
        out: Dict[str, Any] = {"k": kfs}
        if "e" in value:
            out["e"] = _c_easing(value["e"])
        return out
    return value


def _c_easing(e: Any) -> Any:
    if isinstance(e, str):
        if e not in EASINGS:
            raise ValueError(f"неизвестный easing: {e}")
        return _EASING_ID[e]
    if isinstance(e, (list, tuple)):
        return [round(float(v), 5) for v in e]
    return e


def _c_color(c: Any) -> Any:
    if isinstance(c, str) and c.startswith("#"):
        r, g, b, a = parse_color(c)
        return f"#{r:02x}{g:02x}{b:02x}" + ("" if a == 255 else f"{a:02x}")
    return c


def _c_geom(g: Dict[str, Any]) -> Dict[str, Any]:
    kind = g.get("type")
    if kind not in _GEOM_KEYS:
        raise ValueError(f"неизвестная геометрия: {kind!r}")
    out: Dict[str, Any] = {"t": _GEOM_KEYS[kind]}
    if kind == "path":
        subs = g["subpaths"]
        if isinstance(subs, dict) and "k" in subs:      # морфинг контура
            out["s"] = {"k": [[kf[0], [_c_subpath(sp) for sp in kf[1]]]
                              + ([_c_easing(kf[2])] if len(kf) > 2 else [])
                              for kf in subs["k"]]}
            if "e" in subs:
                out["e"] = _c_easing(subs["e"])
        else:
            out["s"] = [_c_subpath(sp) for sp in subs]
    elif kind in ("rect", "round-rect"):
        out["p"] = _c_channel(g.get("position", [0, 0]))
        out["z"] = _c_channel(g["size"])
        if kind == "round-rect":
            out["r"] = _c_channel(g.get("radius", 0))
    elif kind == "ellipse":
        out["p"] = _c_channel(g.get("position", [0, 0]))
        out["z"] = _c_channel(g["size"])
    elif kind == "circle":
        out["p"] = _c_channel(g.get("position", [0, 0]))
        out["r"] = _c_channel(g["radius"])
    elif kind == "polygon":
        out["p"] = _c_channel(g.get("position", [0, 0]))
        out["n"] = _c_channel(g["sides"])
        out["r"] = _c_channel(g["radius"])
        out["rot"] = _c_channel(g.get("rotation", -90))
    elif kind == "star":
        out["p"] = _c_channel(g.get("position", [0, 0]))
        out["n"] = _c_channel(g["points"])
        out["r1"] = _c_channel(g["outer"])
        out["r2"] = _c_channel(g["inner"])
        out["rot"] = _c_channel(g.get("rotation", -90))
        out["rd"] = _c_channel(g.get("roundness", 0))
    if "rule" in g:
        out["ru"] = _RULES[g["rule"]]
    return out


def _as_point_list(sp: Sequence[Any]) -> List[Sequence[float]]:
    """
    Нормализует «список точек». Терпит лишнюю вложенность:
      [[x,y],...]           -> как есть
      [[[x,y],...]]         -> снимает один уровень (один subpath вместо списка)
    """
    items = list(sp)
    while items and isinstance(items[0], (list, tuple)) and items[0] \
            and isinstance(items[0][0], (list, tuple)) \
            and all(isinstance(v, (list, tuple)) for v in items[0][0]):
        if len(items) == 1:
            items = list(items[0])
            continue
        break
    return items


def _c_subpath(sp: Any) -> List[Any]:
    if isinstance(sp, dict):
        pts = sp["points"]
        closed = bool(sp.get("closed", True))
    else:
        pts = _as_point_list(sp)
        closed = True
    if not pts:
        raise ValueError("пустой subpath")
    out: List[Any] = [[round(float(v), 4) for v in p] for p in pts]
    if not closed:
        out.append(0)
    return out


def _c_gradient(g: Dict[str, Any]) -> Dict[str, Any]:
    kind = {"linear": "l", "radial": "r", "conic": "c"}.get(g.get("type", "linear"))
    if kind is None:
        raise ValueError(f"неизвестный градиент: {g['type']!r}")
    out: Dict[str, Any] = {"t": kind}
    if kind == "l":
        if "from" in g and "to" in g:
            out["x0"], out["y0"] = g["from"][0], g["from"][1]
            out["x1"], out["y1"] = g["to"][0], g["to"][1]
        else:
            out["a"] = g.get("angle", 90)
    elif kind == "r":
        cx, cy = g.get("center", [0, 0])
        out["cx"], out["cy"] = cx, cy
        out["r"] = g.get("radius", 100)
        if "focus" in g:
            out["fx"], out["fy"] = g["focus"]
    else:
        cx, cy = g.get("center", [0, 0])
        out["cx"], out["cy"] = cx, cy
        out["a0"] = g.get("angle", 0)
    out["s"] = [[round(float(st["position"]), 5), _c_color(st["color"])] for st in g["stops"]]
    if g.get("normalized"):
        out["u"] = 1
    if g.get("spread") and g["spread"] != "pad":
        out["sp"] = {"reflect": 1, "repeat": 2}[g["spread"]]
    return out


def _c_fill(f: Any) -> Dict[str, Any]:
    if isinstance(f, str):
        return {"c": _c_color(f)} if f.startswith("#") else {"g": f}
    out: Dict[str, Any] = {}
    if "color" in f:
        out["c"] = _c_channel_color(f["color"])
    if "gradient" in f:
        g = f["gradient"]
        out["g"] = g if isinstance(g, str) else _c_gradient(g)
    if "opacity" in f:
        out["o"] = _c_channel(f["opacity"])
    if "rule" in f:
        out["ru"] = _RULES[f["rule"]]
    if not out:
        out["c"] = "#ffffff"
    return out


def _c_channel_color(c: Any) -> Any:
    if isinstance(c, dict) and "k" in c:
        kfs = []
        for kf in c["k"]:
            kf = list(kf)
            kf[1] = _c_color(kf[1])
            if len(kf) > 2:
                kf[2] = _c_easing(kf[2])
            kfs.append(kf)
        out: Dict[str, Any] = {"k": kfs}
        if "e" in c:
            out["e"] = _c_easing(c["e"])
        return out
    return _c_color(c)


def _c_stroke(st: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["c"] = _c_channel_color(st.get("color", "#000000"))
    if "width" in st:
        out["w"] = _c_channel(st["width"])
    if "opacity" in st:
        out["o"] = _c_channel(st["opacity"])
    out["lc"] = _CAPS[st.get("cap", "round")]
    out["lj"] = _JOINS[st.get("join", "round")]
    if "miter-limit" in st:
        out["ml"] = float(st["miter-limit"])
    if "dash" in st:
        d = st["dash"]
        out["d"] = [float(x) for x in (d.get("pattern") if isinstance(d, dict) else d)]
        if isinstance(d, dict) and "offset" in d:
            out["do"] = _c_channel(d["offset"])
    return out


def compile_scene(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Авторинг-JSON -> компактная сцена .kvs."""
    meta = doc.get("meta", {})
    canvas = doc["canvas"]
    compact: Dict[str, Any] = {
        "v": 1,
        "c": {
            "w": int(canvas["width"]),
            "h": int(canvas["height"]),
            "r": float(canvas["fps"]),
            "n": int(canvas["frames"]),
        },
    }
    name = doc.get("name") or meta.get("name")
    if name:
        compact["nm"] = name
    if meta.get("author"):
        compact["au"] = meta["author"]
    if meta.get("generator"):
        compact["gn"] = meta["generator"]
    if canvas.get("background") is not None:
        compact["c"]["b"] = _c_color(canvas["background"])

    assets: Dict[str, Any] = {}
    gradient_types = {"linear", "radial", "conic"}
    for a in doc.get("assets", []):
        kind = a.get("type")
        aid = a.get("id")
        if not aid:
            raise ValueError("ассет без id")
        if kind in gradient_types or kind == "gradient":
            if kind == "gradient":
                a = dict(a, type=a.get("gradient", "linear"))
            assets[aid] = _c_gradient(a)
        elif kind == "path":
            assets[aid] = {"t": "p", "s": [_c_subpath(sp) for sp in a["subpaths"]]}
        else:
            raise ValueError(f"неизвестный ассет: {kind!r}")
    if assets:
        compact["a"] = assets

    layers: List[Dict[str, Any]] = []
    for i, layer in enumerate(doc.get("layers", [])):
        cl: Dict[str, Any] = {"i": i}
        if layer.get("name"):
            cl["nm"] = layer["name"]
        if layer.get("hidden"):
            cl["hd"] = 1
        if layer.get("blend", "normal") != "normal":
            cl["b"] = _BLENDS[layer["blend"]]
        if "parent" in layer:
            cl["pi"] = int(layer["parent"])

        geom = layer["geometry"]
        cl["g"] = geom if isinstance(geom, str) else _c_geom(geom)

        fill = layer.get("fill")
        if fill is not None:
            cl["f"] = _c_fill(fill)
        stroke = layer.get("stroke")
        if stroke is not None:
            cl["s"] = _c_stroke(stroke)

        tr = layer.get("transform")
        if tr:
            ct: Dict[str, Any] = {}
            for long_key, short_key in _TRANSFORM_KEYS.items():
                if long_key not in tr:
                    continue
                val = tr[long_key]
                if long_key == "anchor" and not isinstance(val, dict):
                    val = [float(x) for x in val]
                ct[short_key] = _c_channel(val)
            if ct:
                cl["t"] = ct
        layers.append(cl)

    compact["l"] = layers
    return compact


def decode_scene(compact: Dict[str, Any]) -> Dict[str, Any]:
    """Компактная сцена -> человекочитаемый JSON (для inspect/dump)."""
    c = compact.get("c", {})
    inv_geom = {v: k for k, v in _GEOM_KEYS.items()}
    inv_cap = {v: k for k, v in _CAPS.items()}
    inv_join = {v: k for k, v in _JOINS.items()}
    inv_blend = {v: k for k, v in _BLENDS.items()}
    inv_rule = {v: k for k, v in _RULES.items()}
    inv_tf = {v: k for k, v in _TRANSFORM_KEYS.items()}

    def dec_geom(g: Any) -> Any:
        if isinstance(g, str):
            return {"ref": g}
        out: Dict[str, Any] = {"type": inv_geom[g["t"]]}
        for k, v in g.items():
            if k == "t":
                continue
            if k == "s":
                out["subpaths"] = [
                    {"points": [list(p) for p in sp[:-1]], "closed": sp[-1] != 0}
                    if isinstance(sp[-1], int) else {"points": [list(p) for p in sp], "closed": True}
                    for sp in v
                ]
            elif k == "ru":
                out["rule"] = inv_rule[v]
            else:
                out[{"p": "position", "z": "size", "r": "radius", "n": "sides/points",
                    "rot": "rotation", "r1": "outer", "r2": "inner", "rd": "roundness"}
                   .get(k, k)] = v
        return out

    def dec_paint(p: Dict[str, Any], inv: Dict[str, str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in p.items():
            long = inv.get(k, k)
            if k == "lc":
                v = inv_cap.get(v, v)
            elif k == "lj":
                v = inv_join.get(v, v)
            elif k == "b":
                v = inv_blend.get(v, v)
            out[long] = v
        return out

    layers = []
    for cl in compact.get("l", []):
        layer: Dict[str, Any] = {"index": cl.get("i")}
        for k, v in cl.items():
            if k == "i":
                continue
            if k == "g":
                layer["geometry"] = dec_geom(v)
            elif k == "f":
                layer["fill"] = dec_paint(v, {vv: kk for kk, vv in _FILL_KEYS.items()})
            elif k == "s":
                layer["stroke"] = dec_paint(v, {vv: kk for kk, vv in _STROKE_KEYS.items()})
            elif k == "t":
                layer["transform"] = {inv_tf.get(kk, kk): vv for kk, vv in v.items()}
            elif k == "b":
                layer["blend"] = inv_blend.get(v, v)
            elif k == "hd":
                layer["hidden"] = bool(v)
            elif k == "nm":
                layer["name"] = v
            elif k == "pi":
                layer["parent"] = v
            else:
                layer[k] = v
        layers.append(layer)

    return {
        "name": compact.get("nm"),
        "author": compact.get("au"),
        "generator": compact.get("gn"),
        "canvas": {
            "width": c.get("w"), "height": c.get("h"),
            "fps": c.get("r"), "frames": c.get("n"),
            "background": c.get("b"),
        },
        "assets": compact.get("a", {}),
        "layers": layers,
    }


def easing_names() -> List[str]:
    return list(_EASING_IDS)
