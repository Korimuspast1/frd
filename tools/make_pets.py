"""Генератор анимированных персонажей для плагина «Тамагочи».

Рисует 40 гифок (10 видов × 4 стадии: яйцо, малыш, подросток, взрослый)
в плоском каваий-стиле: пастельные цвета, крупные глаза, пружинистая
анимация, моргание. Каждая гифка — карточка с фоном цвета вида, чтобы
не возиться с прозрачностью GIF. Дополнительно собирает preview.png —
контактный лист, чтобы смотреть результат глазами.

python3 tools/make_pets.py
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "pets"

S = 2                     # суперсэмплинг
W = H = 160               # итоговый размер карточки
CW = CH = W * S           # холст рисования
FRAMES = 8
DURATION = 110
COLORS = 48
STAGE_SCALE = (1.0, 0.60, 0.75, 0.90)   # яйцо рисуется отдельно; малыш/подросток/взрослый

# Пастельная палитра: body / belly / line (обводка) / bg (карточка) / blush
SPECIES = {
    "dragon": {
        "label": "Дракончик",
        "body": (108, 207, 148),
        "belly": (255, 219, 150),
        "line": (46, 112, 78),
        "bg": (231, 248, 239),
        "blush": (255, 138, 128),
    },
    "cat": {
        "label": "Котик",
        "body": (255, 189, 112),
        "belly": (255, 241, 217),
        "line": (150, 94, 42),
        "bg": (254, 244, 229),
        "blush": (255, 133, 133),
    },
    "penguin": {
        "label": "Пингвинчик",
        "body": (72, 84, 120),
        "belly": (245, 248, 255),
        "line": (38, 46, 70),
        "bg": (228, 235, 252),
        "blush": (255, 143, 143),
    },
    "ghost": {
        "label": "Призрак",
        "body": (233, 233, 255),
        "belly": (248, 248, 255),
        "line": (120, 118, 190),
        "bg": (240, 238, 252),
        "blush": (255, 148, 172),
    },
    "alien": {
        "label": "Пришелец",
        "body": (148, 224, 188),
        "belly": (206, 247, 226),
        "line": (44, 118, 86),
        "bg": (229, 249, 239),
        "blush": (255, 138, 158),
    },
    "fox": {
        "label": "Лисёнок",
        "body": (255, 148, 92),
        "belly": (255, 240, 224),
        "line": (156, 74, 30),
        "bg": (255, 240, 232),
        "blush": (255, 124, 124),
    },
    "bunny": {
        "label": "Крольчонок",
        "body": (255, 224, 214),
        "belly": (255, 246, 242),
        "line": (172, 118, 110),
        "bg": (253, 241, 244),
        "blush": (255, 143, 160),
    },
    "robot": {
        "label": "Робот",
        "body": (164, 182, 208),
        "belly": (224, 234, 248),
        "line": (66, 82, 108),
        "bg": (233, 240, 250),
        "blush": (150, 170, 210),
    },
    "owl": {
        "label": "Совёнок",
        "body": (172, 146, 108),
        "belly": (248, 238, 216),
        "line": (96, 76, 46),
        "bg": (247, 240, 226),
        "blush": (255, 138, 128),
    },
    "bear": {
        "label": "Медвежонок",
        "body": (198, 148, 106),
        "belly": (242, 220, 190),
        "line": (106, 72, 42),
        "bg": (248, 238, 226),
        "blush": (255, 133, 133),
    },
}

STAGES = ("egg", "baby", "teen", "adult")
OUTLINE = max(2, S)


def darker(color, factor=0.55):
    return tuple(int(channel * factor) for channel in color)


def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def ellipse_box(cx, cy, rx, ry):
    return [cx - rx, cy - ry, cx + rx, cy + ry]


def draw_star(draw, cx, cy, r, color):
    points = []
    for index in range(10):
        radius = r if index % 2 == 0 else r * 0.4
        angle = math.pi / 2 + index * math.pi / 5
        points.append((cx + radius * math.cos(angle), cy - radius * math.sin(angle)))
    draw.polygon(points, fill=color)


def draw_eye(draw, cx, cy, r, blink, line, square=False):
    """Глаз: кружок с бликом; blink=1 → открыт, 0 → закрыт."""
    if square:
        half = r * 1.05
        if blink > 0.25:
            height = half * blink
            draw.rectangle([cx - half, cy - height, cx + half, cy + height], fill=(30, 36, 52), outline=line, width=OUTLINE)
            if blink > 0.7:
                draw.rectangle([cx + half * 0.2, cy - height * 0.55, cx + half * 0.75, cy], fill=(120, 255, 190))
        else:
            draw.line([(cx - half, cy), (cx + half, cy)], fill=(30, 36, 52), width=max(2, OUTLINE))
        return
    if blink > 0.25:
        ry = r * blink
        draw.ellipse(ellipse_box(cx, cy, r, ry), fill=(38, 34, 48), outline=line, width=OUTLINE)
        if blink > 0.7:
            draw.ellipse(ellipse_box(cx + r * 0.35, cy - ry * 0.4, r * 0.3, ry * 0.3), fill=(255, 255, 255))
    else:
        half = r * 0.9
        draw.line([(cx - half, cy), (cx + half, cy)], fill=(38, 34, 48), width=max(2, OUTLINE))


def draw_mouth(draw, cx, cy, s, kind, line):
    if kind == "cat":
        w = 7 * s
        draw.arc([cx - w, cy - 4 * s, cx, cy + 5 * s], 20, 160, fill=line, width=OUTLINE)
        draw.arc([cx, cy - 4 * s, cx + w, cy + 5 * s], 20, 160, fill=line, width=OUTLINE)
    elif kind == "beak":
        draw.polygon([(cx - 6 * s, cy - 3 * s), (cx + 6 * s, cy - 3 * s), (cx, cy + 6 * s)],
                     fill=(255, 150, 70), outline=line)
    elif kind == "flat":
        draw.line([(cx - 7 * s, cy), (cx + 7 * s, cy)], fill=line, width=max(2, OUTLINE))
    else:
        w = 10 * s
        draw.arc([cx - w, cy - 6 * s, cx + w, cy + 6 * s], 20, 160, fill=line, width=OUTLINE)


# ---- видовые детали: крылья, уши, хвосты, антенны ----

def draw_dragon(draw, species, cx, cy, s, phase, adult):
    body, line = species["body"], species["line"]

    flap = math.sin(phase * 2 * math.pi) * 0.35
    for side in (-1, 1):
        if adult:
            wing = [
                (cx + side * 40 * s, cy - 16 * s),
                (cx + side * (66 + 6 * math.sin(flap * 3)) * s, cy - (26 + 10 * flap) * s),
                (cx + side * 58 * s, cy + 8 * s),
                (cx + side * 38 * s, cy + 2 * s),
            ]
            draw.polygon(wing, fill=mix(body, (255, 255, 255), 0.25), outline=line)
            for i in range(1, len(wing) - 1):
                draw.line([wing[0], wing[i]], fill=line, width=OUTLINE)

    tail_wag = math.sin(phase * 2 * math.pi) * 5 * s
    draw.line(
        [(cx + 30 * s, cy + 20 * s), (cx + 48 * s, cy + 14 * s + tail_wag), (cx + 58 * s, cy + 26 * s + tail_wag)],
        fill=line,
        width=max(3, int(4 * s)),
    )
    draw.line(
        [(cx + 30 * s, cy + 20 * s), (cx + 46 * s, cy + 12 * s + tail_wag)],
        fill=body,
        width=max(2, int(3 * s)),
    )

    for side in (-1, 1):
        base_x = cx + side * 14 * s
        top_x = cx + side * (20 if adult else 17) * s
        draw.polygon(
            [(base_x - 5 * s, cy - 30 * s), (base_x + 5 * s, cy - 30 * s),
             (top_x, cy - (46 if adult else 40) * s)],
            fill=mix(species["belly"], (255, 255, 255), 0.35),
            outline=line,
        )


def draw_cat(draw, species, cx, cy, s, phase, adult):
    body, line = species["body"], species["line"]

    ear_wag = math.sin(phase * 2 * math.pi) * 2 * s
    for side in (-1, 1):
        top = cy - 44 * s - (2 if adult else 1) * s + (ear_wag if side > 0 else -ear_wag)
        draw.polygon(
            [(cx + side * 12 * s, cy - 30 * s), (cx + side * 28 * s, cy - 32 * s),
             (cx + side * 24 * s, top)],
            fill=body,
            outline=line,
        )
        draw.polygon(
            [(cx + side * 16 * s, cy - 31 * s), (cx + side * 25 * s, cy - 31.5 * s),
             (cx + side * 22 * s, top + 5 * s)],
            fill=(255, 170, 170),
        )

    wag = math.sin(phase * 2 * math.pi) * 8 * s
    draw.arc(
        [cx + 26 * s, cy + 4 * s + wag * 0.4, cx + 68 * s, cy + 46 * s + wag * 0.4],
        200 if wag >= 0 else 160,
        330,
        fill=line,
        width=max(3, int(5 * s)),
    )

    if adult:
        for side in (-1, 1):
            for step in (-1, 0, 1):
                draw.line(
                    [(cx + side * 26 * s, cy + 2 * s + step * 4 * s),
                     (cx + side * 44 * s, cy + step * 7 * s + wag * 0.2)],
                    fill=line,
                    width=S,
                )


def draw_penguin(draw, species, cx, cy, s, phase, adult):
    body, line = species["body"], species["line"]
    orange = (255, 150, 70)

    for side in (-1, 1):
        draw.ellipse(ellipse_box(cx + side * 16 * s, cy + 38 * s, 9 * s, 5 * s), fill=orange, outline=line)

    flap = math.sin(phase * 2 * math.pi) * 4 * s
    for side in (-1, 1):
        draw.ellipse(
            ellipse_box(cx + side * 44 * s, cy + 2 * s + flap * side, 10 * s, 22 * s),
            fill=darker(body, 0.85),
            outline=line,
        )


def draw_ghost(draw, species, cx, cy, s, phase, adult):
    glow = species["bg"]
    radius = (52 + math.sin(phase * 4 * math.pi) * 3) * s
    draw.ellipse(ellipse_box(cx, cy + 4 * s, radius, radius * 0.8), outline=mix(glow, (255, 255, 255), 0.5), width=S)


def draw_alien(draw, species, cx, cy, s, phase, adult):
    body, line = species["body"], species["line"]
    sway = math.sin(phase * 2 * math.pi) * 4 * s
    draw.line([(cx, cy - 32 * s), (cx + sway, cy - 48 * s)], fill=line, width=max(2, OUTLINE))
    draw.ellipse(ellipse_box(cx + sway, cy - 52 * s, 6 * s, 6 * s), fill=(255, 120, 140), outline=line)


def draw_fox(draw, species, cx, cy, s, phase, adult):
    body, line, belly = species["body"], species["line"], species["belly"]

    ear_wag = math.sin(phase * 2 * math.pi) * 2.5 * s
    for side in (-1, 1):
        top = cy - 48 * s + (ear_wag if side > 0 else -ear_wag)
        draw.polygon(
            [(cx + side * 10 * s, cy - 28 * s), (cx + side * 30 * s, cy - 34 * s), (cx + side * 22 * s, top)],
            fill=body, outline=line,
        )
        draw.polygon(
            [(cx + side * 15 * s, cy - 31 * s), (cx + side * 26 * s, cy - 33 * s), (cx + side * 21 * s, top + 6 * s)],
            fill=(255, 240, 224),
        )

    wag = math.sin(phase * 2 * math.pi) * 6 * s
    draw.polygon(
        [(cx + 28 * s, cy + 22 * s), (cx + 56 * s, cy + 2 * s + wag), (cx + 62 * s, cy + 24 * s + wag)],
        fill=body, outline=line,
    )
    draw.polygon(
        [(cx + 48 * s, cy + 8 * s + wag), (cx + 58 * s, cy + 6 * s + wag), (cx + 57 * s, cy + 18 * s + wag)],
        fill=(255, 255, 255),
    )


def draw_bunny(draw, species, cx, cy, s, phase, adult):
    body, line = species["body"], species["line"]
    ear_sway = math.sin(phase * 2 * math.pi) * 3 * s
    ear_h = (52 if adult else 42) * s
    for side in (-1, 1):
        tilt = ear_sway * side
        draw.polygon(
            [(cx + side * 10 * s, cy - 28 * s), (cx + side * 22 * s, cy - 30 * s),
             (cx + side * 20 * s + tilt, cy - 28 * s - ear_h)],
            fill=body, outline=line,
        )
        draw.polygon(
            [(cx + side * 13 * s, cy - 30 * s), (cx + side * 20 * s, cy - 30.5 * s),
             (cx + side * 19 * s + tilt * 0.8, cy - 30 * s - ear_h * 0.82)],
            fill=(255, 178, 195),
        )
    draw.ellipse(ellipse_box(cx + 34 * s, cy + 26 * s, 8 * s, 8 * s), fill=(255, 255, 255), outline=line)


def draw_robot(draw, species, cx, cy, s, phase, adult):
    body, line = species["body"], species["line"]
    sway = math.sin(phase * 2 * math.pi) * 3 * s
    draw.line([(cx, cy - 32 * s), (cx + sway, cy - 44 * s)], fill=line, width=max(2, OUTLINE))
    blink_led = (120, 255, 190) if math.sin(phase * 4 * math.pi) >= 0 else (60, 140, 110)
    draw.ellipse(ellipse_box(cx + sway, cy - 48 * s, 5 * s, 5 * s), fill=blink_led, outline=line)
    # батарейка-пузо с бегущей полоской
    level = int((math.sin(phase * 2 * math.pi) + 1) / 2 * 4) + 1
    for step in range(level):
        draw.rectangle(
            [cx - 18 * s + step * 9 * s, cy + 10 * s, cx - 11 * s + step * 9 * s, cy + 20 * s],
            fill=(120, 255, 190), outline=line,
        )


def draw_owl(draw, species, cx, cy, s, phase, adult):
    body, line = species["body"], species["line"]
    # кисточки на ушах
    for side in (-1, 1):
        draw.polygon(
            [(cx + side * 16 * s, cy - 34 * s), (cx + side * 26 * s, cy - 38 * s), (cx + side * 20 * s, cy - 28 * s)],
            fill=body, outline=line,
        )
    # крылья
    flap = math.sin(phase * 2 * math.pi) * 3 * s
    for side in (-1, 1):
        draw.ellipse(
            ellipse_box(cx + side * 40 * s, cy + 4 * s + flap * side, 9 * s, 20 * s),
            fill=darker(body, 0.8), outline=line,
        )
    # лапки
    orange = (255, 150, 70)
    for side in (-1, 1):
        draw.ellipse(ellipse_box(cx + side * 14 * s, cy + 36 * s, 8 * s, 4 * s), fill=orange, outline=line)


def draw_bear(draw, species, cx, cy, s, phase, adult):
    body, line = species["body"], species["line"]
    ear_wag = math.sin(phase * 2 * math.pi) * 2 * s
    for side in (-1, 1):
        center = (cx + side * 30 * s, cy - 30 * s + (ear_wag if side > 0 else -ear_wag))
        draw.ellipse(ellipse_box(center[0], center[1], 12 * s, 12 * s), fill=body, outline=line)
        draw.ellipse(ellipse_box(center[0], center[1], 6 * s, 6 * s), fill=darker(species["belly"], 0.92))


EXTRAS = {
    "dragon": draw_dragon,
    "cat": draw_cat,
    "penguin": draw_penguin,
    "ghost": draw_ghost,
    "alien": draw_alien,
    "fox": draw_fox,
    "bunny": draw_bunny,
    "robot": draw_robot,
    "owl": draw_owl,
    "bear": draw_bear,
}

MOUTH = {
    "dragon": "smile",
    "cat": "cat",
    "penguin": "beak",
    "ghost": "smile",
    "alien": "smile",
    "fox": "cat",
    "bunny": "cat",
    "robot": "flat",
    "owl": "beak",
    "bear": "smile",
}


def species_key(species):
    for key, value in SPECIES.items():
        if value is species:
            return key
    return "dragon"


def body_shape(draw, species, cx, cy, s, phase):
    """Тело: у призрака — волнистый низ, у робота — скруглённый прямоугольник, у остальных — овал."""
    body, line = species["body"], species["line"]
    key = species_key(species)
    rx, ry = 34 * s, 30 * s
    if key == "ghost":
        top = cy - ry
        points = [(cx - rx, cy)]
        steps = 10
        for index in range(steps + 1):
            t = index / steps
            points.append((cx - rx * math.cos(t * math.pi / 2), top + (cy - top) * math.sin(t * math.pi / 2)))
        for index in range(steps + 1):
            t = index / steps
            points.append((cx + rx * math.sin(t * math.pi / 2), top + (cy - top) * math.cos(t * math.pi / 2)))
        waves = 5
        for index in range(waves * 4 + 1):
            t = index / (waves * 4)
            x = cx + rx - 2 * rx * t
            y = cy + 6 * s + math.sin(t * math.pi * waves + phase * 2 * math.pi) * 6 * s
            points.append((x, y))
        draw.polygon(points, fill=body, outline=line)
        return rx, ry
    if key == "robot":
        box = [cx - rx, cy - ry, cx + rx, cy + ry]
        draw.rounded_rectangle(box, radius=16 * s, fill=body, outline=line, width=OUTLINE)
        return rx, ry
    draw.ellipse(ellipse_box(cx, cy, rx, ry), fill=body, outline=line)
    return rx, ry


def draw_creature(draw, species, cx, cy, s, phase, stage, blink):
    body, belly, line, blush = species["body"], species["belly"], species["line"], species["blush"]
    adult = stage == 3
    key = species_key(species)

    EXTRAS[key](draw, species, cx, cy, s, phase, adult)
    rx, ry = body_shape(draw, species, cx, cy, s, phase)

    if key not in ("ghost",):
        draw.ellipse(ellipse_box(cx, cy + 8 * s, rx * 0.62, ry * 0.55), fill=belly)

    eye_r = (11 if stage == 1 else 9 if stage == 2 else 8) * s
    if key == "owl":
        # у совы глаза-тарелки в светлых кольцах
        for side in (-1, 1):
            ex = cx + side * rx * 0.42
            draw.ellipse(ellipse_box(ex, cy - 4 * s, 13 * s, 13 * s), fill=belly, outline=line)
        for side in (-1, 1):
            ex = cx + side * rx * 0.42
            draw_eye(draw, ex, cy - 4 * s, eye_r * 0.85, blink, line)
    else:
        spread = rx * 0.42
        draw_eye(draw, cx - spread, cy - 4 * s, eye_r, blink, line, square=(key == "robot"))
        draw_eye(draw, cx + spread, cy - 4 * s, eye_r, blink, line, square=(key == "robot"))

    draw_mouth(draw, cx, cy + 8 * s, s, MOUTH[key], line)
    if key == "bear":
        draw.ellipse(ellipse_box(cx, cy + 6 * s, 12 * s, 9 * s), fill=belly, outline=None)
        draw.ellipse(ellipse_box(cx, cy + 3 * s, 3.5 * s, 3 * s), fill=(56, 40, 30))
    for side in (-1, 1):
        draw.ellipse(ellipse_box(cx + side * rx * 0.72, cy + 4 * s, 6 * s, 4 * s), fill=blush)

    if stage == 1:
        shell = mix((255, 245, 220), (255, 255, 255), 0.3)
        draw.polygon(
            [(cx - rx * 0.8, cy - ry * 0.75), (cx + rx * 0.8, cy - ry * 0.75),
             (cx + rx * 0.5, cy - ry * 1.45), (cx - rx * 0.45, cy - ry * 1.5)],
            fill=shell,
            outline=darker(shell, 0.6),
        )
        draw.line([(cx - rx * 0.2, cy - ry * 1.42), (cx - rx * 0.1, cy - ry * 0.9)], fill=darker(shell, 0.6), width=S)


def draw_egg(draw, species, cx, cy, s, phase):
    shell = mix((255, 250, 240), species["bg"], 0.35)
    edge = darker(shell, 0.62)
    rx, ry = 30 * s, 38 * s
    wobble = math.sin(phase * 2 * math.pi) * 5
    tilt = wobble * s * 0.12

    layer = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.ellipse(ellipse_box(cx, cy, rx, ry), fill=shell, outline=edge)
    for (dx, dy, r) in ((-10, -12, 5), (12, -4, 6), (-4, 14, 4), (14, 18, 3.5)):
        layer_draw.ellipse(ellipse_box(cx + dx * s, cy + dy * s, r * s, r * s), fill=mix(species["body"], shell, 0.35))
    layer_draw.line(
        [(cx - 8 * s, cy - 20 * s), (cx + 2 * s, cy - 12 * s), (cx - 4 * s, cy - 6 * s), (cx + 6 * s, cy + 2 * s)],
        fill=edge,
        width=S,
    )
    return layer.rotate(tilt, center=(cx, cy + ry), resample=Image.BICUBIC)


def frame(species, stage, phase):
    image = Image.new("RGB", (CW, CH), species["bg"])
    draw = ImageDraw.Draw(image, "RGBA")

    blink = 1.0
    if 0.62 <= phase <= 0.78:
        blink = 0.12

    if stage == 0:
        egg_layer = draw_egg(draw, species, CW / 2, CH / 2 - 10 * S, S, phase)
        image.paste(egg_layer, (0, 0), egg_layer)
        draw.ellipse(ellipse_box(CW / 2, CH / 2 + 36 * S, 34 * S, 7 * S), fill=mix(species["bg"], (0, 0, 0), 0.08))
        star = (255, 214, 120) if math.sin(phase * 2 * math.pi) >= 0 else (255, 255, 255)
        draw_star(draw, CW / 2 + 46 * S, CH / 2 - 40 * S, 7 * S, star)
        draw_star(draw, CW / 2 - 50 * S, CH / 2 - 18 * S, 5 * S, mix(star, species["bg"], 0.3))
    else:
        bounce = abs(math.sin(phase * 2 * math.pi)) * (7 if stage == 1 else 5) * S
        cy = CH / 2 + (10 if stage == 1 else 6) * S - bounce
        scale = STAGE_SCALE[stage]
        draw.ellipse(ellipse_box(CW / 2, CH / 2 + 44 * S, 40 * S * scale, 8 * S), fill=mix(species["bg"], (0, 0, 0), 0.08))
        draw_creature(draw, species, CW / 2, cy, S * scale, phase, stage, blink)

    return image.resize((W, H), Image.LANCZOS)


def build(species_key_name, stage_index):
    species = SPECIES[species_key_name]
    raw = [frame(species, stage_index, index / float(FRAMES)) for index in range(FRAMES)]

    montage = Image.new("RGB", (W, H * 3))
    for index, sample in enumerate(raw[::3]):
        montage.paste(sample, (0, index * H))
    palette_source = montage.quantize(colors=COLORS, method=Image.MEDIANCUT)
    frames = [image.quantize(palette=palette_source, dither=Image.NONE) for image in raw]

    path = ASSETS / f"{species_key_name}_{stage_index}.gif"
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=DURATION,
        loop=0,
        optimize=True,
        disposal=2,
    )
    return path, raw


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    samples = []
    total = 0
    for species_key_name in SPECIES:
        for stage_index in range(4):
            path, raw = build(species_key_name, stage_index)
            size = path.stat().st_size
            total += size
            print(f"{path.name:18s} {size:6d} bytes")
            if stage_index == 3:
                samples.append(raw[2])

    preview = ASSETS / "preview.png"
    if preview.exists():
        preview.unlink()
    sheet = Image.new("RGB", (W * 5, H * 2), (250, 250, 250))
    for index, sample in enumerate(samples):
        column = index % 5
        row = index // 5
        sheet.paste(sample, (column * W, row * H))
    sheet.save(preview, optimize=True)
    print(f"total {total} bytes, preview {preview.stat().st_size} bytes")


if __name__ == "__main__":
    main()
