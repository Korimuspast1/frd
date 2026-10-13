#!/usr/bin/env python3
"""
Сборка примеров .kvs.

    python3 examples/build.py            # собрать все примеры
    python3 examples/build.py heart gear # только выбранные

Для каждого примера создаются:
    examples/<name>.kvs         -- сам файл формата (с PNG-превью внутри)
    examples/src/<name>.json    -- авторинг-JSON, из которого он собран
    renders/<name>.gif          -- быстрый предпросмотр (для README)
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import kvs                                    # noqa: E402
import kvs.api as K                           # noqa: E402

EX_DIR = os.path.join(ROOT, "examples")
SRC_DIR = os.path.join(EX_DIR, "src")
RENDER_DIR = os.path.join(ROOT, "renders")


# --------------------------------------------------------------------------- #
#  1. HEART -- пульсирующее сердце, градиенты, частицы, аддитивное свечение
# --------------------------------------------------------------------------- #
def build_heart() -> dict:
    W = H = 512
    FR, N = 60, 90
    doc = K.animation("Pulsing Heart", W, H, fps=FR, frames=N, background="#12001f",
                      author="KVS examples")
    K.linear_gradient(doc, "bg", ["#2a0a3d", "#0a0213"], angle=90)
    K.linear_gradient(doc, "heart", ["#ff5f8f", "#c81d55", "#7a0f3a"], angle=115)
    K.radial_gradient(doc, "glow", ["#ff9ec4", "#ff2d6f", "#3a0018"], center=(0.5, 0.42),
                      radius=0.55)

    K.layer(doc, "background", K.rect([W / 2, H / 2], [W, H]), fill=K.fill(gradient="bg"))

    # мягкое свечение за сердцем (аддитивный режим)
    K.layer(doc, "glow", K.circle([256, 250], 190),
            fill=K.fill(gradient="glow", opacity=0.85),
            blend="add",
            transform=K.transform(anchor=[256, 250], position=[256, 250],
                                  scale=K.keys([(0, [92, 92]), (22, [112, 112]),
                                                (45, [96, 96]), (67, [110, 110]),
                                                (N, [92, 92])], easing="in-out-sine"),
                                opacity=K.keys([(0, 0.45), (22, 0.85), (45, 0.5),
                                                (67, 0.8), (N, 0.45)], easing="in-out-sine")))

    hp = K.heart_points(256, 252, 300)
    K.layer(doc, "heart", K.path([hp]),
            fill=K.fill(gradient="heart"),
            stroke=K.stroke("#ffd9e6", 3, opacity=0.35),
            transform=K.transform(anchor=[256, 252], position=[256, 252],
                                  scale=K.keys([(0, [100, 100]), (20, [113, 113]),
                                                (40, [99, 99]), (60, [111, 111]),
                                                (N, [100, 100])], easing="in-out-sine"),
                                  rotation=K.keys([(0, -2.0), (45, 2.0), (N, -2.0)],
                                                  easing="in-out-sine")))

    # блик
    K.layer(doc, "shine", K.ellipse([200, 190], [86, 54]),
            fill=K.fill("#ffffff", opacity=0.22),
            transform=K.transform(anchor=[200, 190], position=[200, 190], rotation=-28,
                                  scale=K.keys([(0, [100, 100]), (30, [112, 104]),
                                                (N, [100, 100])], easing="in-out-sine")))

    # всплывающие частицы
    rng = _rng(7)
    for i in range(16):
        x = 40 + rng() * (W - 80)
        r = 3 + rng() * 7
        dur = 50 + rng() * 40
        y0 = H + 30 - rng() * (H + 90)
        drift = (rng() - 0.5) * 90
        K.layer(doc, f"spark{i}", K.circle([x, H + 30], r),
                fill=K.fill("#ffb3d1", opacity=0.75),
                blend="add",
                transform=K.transform(anchor=[x, H + 30],
                    position=K.keys([(0, [x, y0]), (N, [x + drift, y0 - (H + 90)])],
                                    easing="linear"),
                    scale=K.keys([(0, [40, 40]), (N // 2, [130, 130]), (N, [30, 30])],
                                 easing="in-out-sine"),
                    opacity=K.keys([(0, 0.0), (N * 0.25, 0.9), (N * 0.7, 0.5), (N, 0.0)],
                                   easing="in-out-sine")))
    return doc


# --------------------------------------------------------------------------- #
#  2. GEARS -- две сцепленные шестерни, пунктирные обводки, металл
# --------------------------------------------------------------------------- #
def build_gears() -> dict:
    W = H = 512
    FR, N = 60, 180
    doc = K.animation("Meshing Gears", W, H, fps=FR, frames=N, background="#0d1117")
    K.linear_gradient(doc, "steel", ["#e8eef5", "#9fb0c3", "#5d6b7d"], angle=135)
    K.linear_gradient(doc, "brass", ["#ffe6a7", "#e0a63c", "#8a5c14"], angle=135)
    K.radial_gradient(doc, "floor", ["#1b2431", "#0b0f15"], center=(0.5, 0.5), radius=0.7)

    K.layer(doc, "backdrop", K.rect([W / 2, H / 2], [W, H]), fill=K.fill(gradient="floor"))

    def gear(name, cx, cy, radius, teeth, color, edge, spin, phase=0.0, hub=0.34):
        rim_w = radius * 0.20
        ring_r = radius - rim_w / 2
        dash = math.pi * 2 * ring_r / teeth
        K.layer(doc, name + "-teeth", K.circle([cx, cy], ring_r),
                stroke=K.stroke(edge, rim_w, cap="butt", dash=[dash * 0.62, dash * 0.38]),
                transform=K.transform(anchor=[cx, cy], position=[cx, cy],
                                      rotation=K.keys([(0, phase), (N, phase + spin)],
                                                      easing="linear")))
        K.layer(doc, name + "-body", K.circle([cx, cy], radius * 0.78),
                fill=K.fill(gradient=color),
                stroke=K.stroke("#0d1117", 3, opacity=0.55),
                transform=K.transform(anchor=[cx, cy], position=[cx, cy],
                                      rotation=K.keys([(0, phase), (N, phase + spin)],
                                                      easing="linear")))
        # спицы-вырезы
        for s in range(5):
            a = phase + s * 72
            K.layer(doc, f"{name}-hole{s}", K.circle([cx, cy], radius * 0.16),
                    fill=K.fill("#0d1117", opacity=0.85),
                    transform=K.transform(anchor=[cx, cy], rotation=a,
                                          position=[0, 0])) if False else None
        K.layer(doc, name + "-hub", K.circle([cx, cy], radius * hub),
                fill=K.fill("#0d1117"),
                stroke=K.stroke(edge, radius * 0.07))
        K.layer(doc, name + "-axle", K.circle([cx, cy], radius * hub * 0.36),
                fill=K.fill(gradient=color))

    # вырезы в теле шестерни -- отдельным слоем с вращением (родитель = тело)
    # передаточное отношение: зубчатый венец B крутится быстрее и в обратную сторону
    gear("A", 190, 250, 128, 14, "steel", "#b9c8d8", 360.0)
    gear("B", 372, 268, 86, 10, "brass", "#e8b45c", -360.0 * (14 / 10), phase=18.0)

    # отверстия в шестерне A (вращаются вместе с ней через parent)
    body_index = _index_of(doc, "A-body")
    for s in range(5):
        a = s * 72.0
        rad = math.radians(a)
        K.layer(doc, f"A-vent{s}", K.circle([190 + 74 * math.cos(rad), 250 + 74 * math.sin(rad)], 24),
                fill=K.fill("#0d1117", opacity=0.9), parent=body_index)

    K.layer(doc, "title-dot", K.circle([256, 470], 5),
            fill=K.fill("#9fb0c3", opacity=0.6))
    return doc


# --------------------------------------------------------------------------- #
#  3. BALL -- прыгающий мяч: squash & stretch, тень, hold-ключи
# --------------------------------------------------------------------------- #
def build_ball() -> dict:
    W, H = 512, 384
    FR, N = 60, 90
    doc = K.animation("Bouncing Ball", W, H, fps=FR, frames=N, background="#f2ede4")
    K.linear_gradient(doc, "bgw", ["#fdfaf4", "#e7dfd2"], angle=90)
    K.radial_gradient(doc, "ball", ["#ff9d7a", "#f2542d", "#8f1d0c"],
                      center=(0.36, 0.3), radius=0.72)

    K.layer(doc, "wall", K.rect([W / 2, H / 2], [W, H]), fill=K.fill(gradient="bgw"))
    K.layer(doc, "floor", K.rect([W / 2, 330], [W, 108]), fill=K.fill("#ded4c4"))
    K.layer(doc, "line", K.rect([W / 2, 276], [W, 3]), fill=K.fill("#c3b7a4"))

    # тень
    K.layer(doc, "shadow", K.ellipse([256, 322], [150, 26]),
            fill=K.fill("#6b5f52", opacity=0.35),
            transform=K.transform(anchor=[256, 322], position=[256, 322],
                                  scale=K.keys([(0, [70, 70]), (28, [135, 135]),
                                                (45, [70, 70]), (73, [135, 135]),
                                                (N, [70, 70])], easing="in-out-sine"),
                                  opacity=K.keys([(0, 0.15), (28, 0.45), (45, 0.15),
                                                  (73, 0.45), (N, 0.15)],
                                                 easing="in-out-sine")))

    # мяч: позиция -- out-bounce, деформация -- hold-ключи (мгновенный «удар»)
    K.layer(doc, "ball", K.circle([256, 0], 56),
            fill=K.fill(gradient="ball"),
            transform=K.transform(anchor=[256, 0],
                                  position=K.keys([(0, [256, 90]), (45, [256, 258]),
                                                   (N, [256, 90])], easing="in-out-sine"),
                                  scale=K.keys([
                                      (0, [100, 100], "hold"),
                                      (40, [100, 100], "hold"),
                                      (43, [122, 78], "in-out-quad"),
                                      (48, [92, 108], "out-quad"),
                                      (54, [100, 100], "hold"),
                                      (85, [100, 100], "hold"),
                                      (88, [118, 82], "in-out-quad"),
                                      (N, [100, 100], "out-quad"),
                                  ])))
    # блик на мяче
    K.layer(doc, "gloss", K.ellipse([238, -18], [30, 20]),
            fill=K.fill("#ffffff", opacity=0.55),
            transform=K.transform(anchor=[256, 0], rotation=-25,
                                  position=K.keys([(0, [256, 90]), (45, [256, 232]),
                                                   (N, [256, 90])], easing="in-out-sine")))
    return doc


# --------------------------------------------------------------------------- #
#  4. ORBIT -- планетарная система: родительские слои, аддитивное свечение
# --------------------------------------------------------------------------- #
def build_orbit() -> dict:
    W = H = 512
    FR, N = 60, 240
    doc = K.animation("Orbit", W, H, fps=FR, frames=N, background="#03040c")
    K.radial_gradient(doc, "space", ["#0b1030", "#03040c"], center=(0.5, 0.5), radius=0.75)
    K.radial_gradient(doc, "sun", ["#fff8d6", "#ffc63c", "#ff7a18"], center=(0.5, 0.5),
                      radius=0.5)
    K.radial_gradient(doc, "halo", ["#ffd27a", "#ff8c1a", "#00000000"], center=(0.5, 0.5),
                      radius=0.5)
    K.radial_gradient(doc, "earth", ["#9fd8ff", "#2f7fd4", "#0d2b5e"], center=(0.35, 0.3),
                      radius=0.75)
    K.radial_gradient(doc, "mars", ["#ffc39a", "#e0653a", "#6d2312"], center=(0.35, 0.3),
                      radius=0.75)

    K.layer(doc, "space", K.rect([W / 2, H / 2], [W, H]), fill=K.fill(gradient="space"))

    rng = _rng(11)
    for i in range(70):
        x, y = rng() * W, rng() * H
        r = 0.7 + rng() * 1.6
        ph = rng() * N
        K.layer(doc, f"star{i}", K.circle([x, y], r),
                fill=K.fill("#ffffff"),
                blend="add",
                transform=K.transform(opacity=K.keys([(0, 0.25), (ph, 1.0), (N, 0.25)],
                                                     easing="in-out-sine")))

    # орбиты
    for name, rx, ry, rot in (("orbit1", 118, 46, -18), ("orbit2", 186, 72, -18)):
        K.layer(doc, name, K.circle([256, 256], rx),
                stroke=K.stroke("#4a5f9a", 1.6, opacity=0.55, dash=[5, 7]),
                transform=K.transform(anchor=[256, 256], position=[256, 256],
                                      rotation=rot, scale=[100, ry / rx * 100]))

    K.layer(doc, "halo", K.circle([256, 256], 128), fill=K.fill(gradient="halo"),
            blend="add",
            transform=K.transform(anchor=[256, 256], position=[256, 256],
                                  scale=K.keys([(0, [96, 96]), (N // 2, [108, 108]),
                                                (N, [96, 96])], easing="in-out-sine")))
    K.layer(doc, "sun", K.circle([256, 256], 46), fill=K.fill(gradient="sun"),
            transform=K.transform(anchor=[256, 256], position=[256, 256],
                                  scale=K.keys([(0, [100, 100]), (N // 2, [104, 104]),
                                                (N, [100, 100])], easing="in-out-sine")))

    def planet(name, radius, size, gradient, period, tilt=-18.0, phase=0.0, ring=False):
        # «кривошип»: невидимый слой, который вращается вокруг солнца.
        # Планета и её кольцо наследуют его матрицу через parent -- так работает
        # иерархия трансформ в KVS.
        spin = 360.0 * (N / period)
        px, py = 256 + radius, 256
        K.layer(doc, name + "-arm", K.circle([256, 256], 1.0),
                transform=K.transform(anchor=[256, 256], position=[256, 256],
                                      rotation=tilt),
                hidden=True)
        arm_index = len(doc["layers"]) - 1
        K.layer(doc, name + "-spin", K.circle([256, 256], 1.0), parent=arm_index,
                transform=K.transform(anchor=[256, 256], position=[256, 256],
                                      rotation=K.keys([(0, phase), (N, phase + spin)],
                                                      easing="linear")),
                hidden=True)
        spin_index = len(doc["layers"]) - 1
        if ring:
            K.layer(doc, name + "-ring", K.circle([px, py], size * 1.9),
                    stroke=K.stroke("#cfe3ff", 3, opacity=0.45), parent=spin_index,
                    transform=K.transform(anchor=[px, py], position=[px, py],
                                          scale=[100, 34]))
        # планета: контр-вращение, чтобы «освещение» градиента не крутилось с орбитой
        K.layer(doc, name, K.circle([px, py], size),
                fill=K.fill(gradient=gradient), parent=spin_index,
                transform=K.transform(anchor=[px, py], position=[px, py],
                                      rotation=K.keys([(0, -(phase + tilt)),
                                                       (N, -(phase + tilt + spin))],
                                                      easing="linear")))

    planet("earth", 118, 15, "earth", period=N / 2, tilt=-18, phase=0)
    planet("mars", 186, 11, "mars", period=N, tilt=-18, phase=140)
    return doc


# --------------------------------------------------------------------------- #
#  5. SPINNER -- индикатор загрузки: конический градиент + вращение
# --------------------------------------------------------------------------- #
def build_spinner() -> dict:
    W = H = 256
    FR, N = 60, 60
    doc = K.animation("Spinner", W, H, fps=FR, frames=N, background="#0f1220")
    K.linear_gradient(doc, "card", ["#1a1f36", "#10131f"], angle=135)
    K.conic_gradient(doc, "arc", ["#00e5ff00", "#00e5ff", "#7c4dff"], center=(0.5, 0.5))

    K.layer(doc, "card", K.round_rect([W / 2, H / 2], [220, 220], 44),
            fill=K.fill(gradient="card"))
    K.layer(doc, "track", K.circle([W / 2, H / 2], 62),
            stroke=K.stroke("#2c3352", 12, opacity=0.9))
    K.layer(doc, "arc", K.circle([W / 2, H / 2], 62),
            stroke=K.stroke("#00e5ff", 12, cap="round", dash=[230, 160]),
            transform=K.transform(anchor=[W / 2, H / 2], position=[W / 2, H / 2],
                                  rotation=K.keys([(0, 0), (N, 360)], easing="linear")))
    K.layer(doc, "arc2", K.circle([W / 2, H / 2], 62),
            stroke=K.stroke("#7c4dff", 12, cap="round", dash=[70, 320], opacity=0.85),
            blend="add",
            transform=K.transform(anchor=[W / 2, H / 2], position=[W / 2, H / 2],
                                  rotation=K.keys([(0, 180), (N, 540)], easing="linear")))
    K.layer(doc, "core", K.circle([W / 2, H / 2], 20),
            fill=K.fill("#e8f6ff"),
            transform=K.transform(anchor=[W / 2, H / 2], position=[W / 2, H / 2],
                                  scale=K.keys([(0, [90, 90]), (N // 2, [112, 112]),
                                                (N, [90, 90])], easing="in-out-sine"),
                                  opacity=K.keys([(0, 0.7), (N // 2, 1.0), (N, 0.7)],
                                                 easing="in-out-sine")))
    return doc


# --------------------------------------------------------------------------- #
#  6. FLAG -- морфинг контура: развевающийся флаг
# --------------------------------------------------------------------------- #
def build_flag() -> dict:
    W, H = 512, 320
    FR, N = 60, 120
    doc = K.animation("Waving Flag", W, H, fps=FR, frames=N, background="#0a1a2b")
    K.linear_gradient(doc, "sky", ["#123a5c", "#06121f"], angle=90)
    K.linear_gradient(doc, "cloth", ["#ffd166", "#ef476f", "#8b1e3f"], angle=20)

    K.layer(doc, "sky", K.rect([W / 2, H / 2], [W, H]), fill=K.fill(gradient="sky"))
    K.layer(doc, "pole", K.path([[[96, 40], [96, 300]]], closed=False),
            stroke=K.stroke("#dfe7ee", 8, cap="round"))
    K.layer(doc, "knob", K.circle([96, 36], 9), fill=K.fill("#ffd166"))

    waves = [_flag_frame(i) for i in range(6)]
    K.layer(doc, "cloth",
            K.morph([(i * (N / 6), [waves[i]]) for i in range(6)] + [(N, [waves[0]])],
                    easing="linear"),
            fill=K.fill(gradient="cloth"),
            stroke=K.stroke("#ffe6a7", 1.5, opacity=0.25))
    # складки
    for j, off in enumerate((0.33, 0.66)):
        folds = [_flag_fold(i, off) for i in range(6)]
        K.layer(doc, f"fold{j}",
                K.morph([(i * (N / 6), [folds[i]]) for i in range(6)] + [(N, [folds[0]])],
                        easing="linear"),
                stroke=K.stroke("#000000", 6, cap="round", opacity=0.12))
    return doc


def _flag_frame(i: int) -> list:
    """Один кадр контура флага: 4 сегмента Безье сверху и снизу."""
    phase = i * math.pi / 3.0
    x0, y0, w, h = 100.0, 70.0, 300.0, 150.0
    top, bottom = [], []
    seg = 4
    for s in range(seg + 1):
        x = x0 + w * s / seg
        dy = 26.0 * math.sin(phase + s * 1.15) * (s / seg) ** 0.7
        top.append([x, y0 + dy])
        bottom.append([x, y0 + h + dy])
    pts: list = []
    # верхняя кромка слева направо (с управляющими точками)
    for s in range(seg):
        x_a, y_a = top[s]
        x_b, y_b = top[s + 1]
        mx = (x_a + x_b) / 2
        pts.append([x_a, y_a, mx, y_a, mx, y_b])
    pts.append(list(top[-1]))
    # правый край вниз
    pts.append(list(bottom[-1]))
    # нижняя кромка справа налево
    for s in range(seg, 0, -1):
        x_a, y_a = bottom[s]
        x_b, y_b = bottom[s - 1]
        mx = (x_a + x_b) / 2
        pts.append([x_a, y_a, mx, y_a, mx, y_b])
    return pts


def _flag_fold(i: int, frac: float) -> list:
    phase = i * math.pi / 3.0
    x0, y0, w, h = 100.0, 70.0, 300.0, 150.0
    x = x0 + w * frac
    seg = frac * 4
    dy_t = 26.0 * math.sin(phase + seg * 1.15) * frac ** 0.7
    return [[x, y0 + dy_t + 6], [x, y0 + h + dy_t - 6]]


# --------------------------------------------------------------------------- #
BUILDERS = {
    "heart": build_heart,
    "gears": build_gears,
    "ball": build_ball,
    "orbit": build_orbit,
    "spinner": build_spinner,
    "flag": build_flag,
}


def _rng(seed: int):
    """Крошечный детерминированный PRNG (чтобы примеры были воспроизводимы)."""
    state = seed * 1103515245 + 12345

    def nxt():
        nonlocal state
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        return state / 0x7FFFFFFF
    return nxt


def _index_of(doc, name):
    for i, layer in enumerate(doc["layers"]):
        if layer.get("name") == name:
            return i
    return None


def build_one(name: str, *, preview_gif: bool = True, ss: int = 3) -> None:
    doc = BUILDERS[name]()
    os.makedirs(SRC_DIR, exist_ok=True)
    os.makedirs(EX_DIR, exist_ok=True)
    with open(os.path.join(SRC_DIR, name + ".json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    out = os.path.join(EX_DIR, name + ".kvs")
    t0 = time.time()
    blob = K.pack(doc, out, codec="zlib", preview=True, ss=2)
    hdr = kvs.read_header(out)
    print(f"  {name:8s} -> {out}  {len(blob)/1024:6.1f} KiB  "
          f"{hdr['width']}x{hdr['height']} {hdr['frames']}f @ {hdr['fps']:g}fps  "
          f"({time.time()-t0:.2f}s)")
    if preview_gif:
        os.makedirs(RENDER_DIR, exist_ok=True)
        gif = os.path.join(RENDER_DIR, name + ".gif")
        t0 = time.time()
        step = 2 if name in ("orbit", "gears") else 1
        frames = list(range(0, hdr["frames"], step))
        kvs.export(out, gif, fmt="gif", ss=ss, frames=frames,
                   fps=hdr["fps"] / step)
        print(f"           -> {gif}  {os.path.getsize(gif)/1024:.0f} KiB "
              f"({time.time()-t0:.1f}s, {len(frames)} кадров)")


def main(argv):
    args = list(argv[1:])
    ss = 2 if "--fast" in args else 3
    gif = "--no-gif" not in args
    names = [a for a in args if not a.startswith("--")] or list(BUILDERS)
    for name in names:
        if name not in BUILDERS:
            print(f"неизвестный пример: {name} (доступны: {', '.join(BUILDERS)})")
            continue
        build_one(name, preview_gif=gif, ss=ss)


if __name__ == "__main__":
    main(sys.argv)
