#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ВО ДВОРЕ / Серия 02 — сборка на движке build_episode.py.

Переопределяет только данные выпуска: сценарий, карточки, производные кадры,
путь к ассетам и имя выходного файла. Вся типографика, Ken Burns, саунд-дизайн,
линейный loudnorm и QC берутся из общего движка без изменений.

Запуск: /home/user/venv/bin/python build_episode_02.py
"""
import os
import math
import random
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

import build_episode as b

# --- директория ассетов и метаданные выпуска ---
b.R = os.path.join(b.ROOT, "render2")
os.makedirs(b.R, exist_ok=True)
b.OUT_NAME = "episode_02_courtyard.mp4"
b.INTRO_IMG = "img00_title2.png"
b.OUTRO_IMG = "img13_finale2.png"
b.META_TITLE = "ВО ДВОРЕ — Серия 02"
b.META_COMMENT = "Инструкция по выживанию в зомби-апокалипсисе в РФ — правила 09–16"

b.CARD = dict(
    intro_title="ВО ДВОРЕ",
    intro_sub="СЕРИЯ 02  ·  ОТ ПОДЪЕЗДА ДО ГАРАЖЕЙ",
    intro_line="ИНСТРУКЦИЯ ПО ВЫЖИВАНИЮ В РФ   ·   ПРАВИЛА 09–16   ·   3 МИНУТЫ",
    intro_footer="ПРОСТО СМОТРИ",
    outro_title="КОНЕЦ ВТОРОЙ СЕРИИ",
    outro_sub="ДАЛЬШЕ — СПУСК В ПОДВАЛ",
    outro_line="16 ПРАВИЛ  ·  1 ДЕНЬ  ·  ПРОДОЛЖЕНИЕ СЛЕДУЕТ",
    outro_footer="ПЕРВЫЙ ДЕНЬ   ·   СЕРИЯ 02",
    series_tag="ПЕРВЫЙ ДЕНЬ   •   СЕРИЯ 02",
)


def clip(f, lines, lead=0.30, tail=0.40, kind="voice"):
    return dict(file=f, lines=lines, lead=lead, tail=tail, kind=kind)


# --- сценарий: правила 09–16 ---
b.SCENES = [
    dict(
        badge="ПРАВИЛО 09", title="ПЕРЕД ВЫХОДОМ", idx=1,
        clips=[clip("vo2_01.mp3", [
            "Серия вторая. Во дворе.",
            "Я стою у двери подъезда, и впервые за сутки мне страшно не от звука, а от тишины.",
            "Правило девятое: перед выходом — разведка.",
            "Смотри в щель, слушай этажи, считай до ста.",
            "Уходи на рассвете: днём их больше, ночью ты их не увидишь.",
        ])],
        shots=[("img01_stairwell2.png", 0.50), ("img02_peephole2.png", 0.50)],
    ),
    dict(
        badge="ПРАВИЛО 10", title="ЛЕСТНИЦА", idx=2,
        clips=[clip("vo2_02.mp3", [
            "Правило десятое: лестница.",
            "Лифт — ловушка, в нём нет связи и нет выхода.",
            "Спускайся, прижимаясь к стене, проверяя каждую площадку.",
            "Не свети фонариком в окна и не зови лифт.",
            "Считай пролёты: если на трёх этажах тихо — это уже подозрительно.",
        ])],
        shots=[("img10_stairs2.png", 1.0)],
    ),
    dict(
        badge="ПРАВИЛО 11", title="ДВЕРЬ ПОДЪЕЗДА", idx=3,
        clips=[clip("vo2_03.mp3", [
            "Правило одиннадцатое: открывай дверь медленно.",
            "Сначала щель, потом шаг.",
            "Закрой за собой, чтобы не захлопнуло — обратного хода может не быть.",
            "Защити шею и руки: шарф, куртка, перчатки.",
            "Укус в кисть или в шею — приговор быстрее, чем ты думаешь.",
        ])],
        shots=[("img03_exit2.png", 1.0)],
    ),
    dict(
        badge="ПРАВИЛО 12", title="ДВОР", idx=4,
        clips=[
            clip("vo2_04a.mp3", [
                "Правило двенадцатое: двор.",
                "Не беги по центру — ты на ладони.",
                "Двигайся по краю, от машины к машине, от дерева к дереву.",
            ], tail=0.85),
            clip("vo2_radio.mp3", [
                "Внимание. Говорит радио МЧС.",
                "Пункты сбора работают в школах и поликлиниках.",
                "Не подходите к скоплениям людей с открытыми ранами.",
                "Держите дистанцию. Повторяю — держите дистанцию.",
            ], lead=0.55, tail=0.60, kind="radio"),
            clip("vo2_04b.mp3", [
                "Шаги мягкие, дыхание ровное, телефон выключен.",
                "Один шумный шаг — и весь двор повернётся к тебе.",
            ], lead=0.20),
        ],
        shots=[("img04_courtyard2.png", 0.55), ("img05_cars2.png", 0.45)],
    ),
    dict(
        badge="ПРАВИЛО 13", title="ДРУГИЕ ЛЮДИ", idx=5,
        clips=[clip("vo2_05.mp3", [
            "Правило тринадцатое: живые опаснее мёртвых, потому что умеют врать.",
            "Держи дистанцию в два метра.",
            "Смотри на руки, на шею, на глаза.",
            "Не поворачивайся спиной, даже когда помогаешь.",
            "И запомни: группа — это сила, но и лишний шум.",
        ])],
        shots=[("img08_survivor2.png", 1.0)],
    ),
    dict(
        badge="ПРАВИЛО 14", title="АПТЕЧКА И УКУС", idx=6,
        clips=[clip("vo2_06.mp3", [
            "Правило четырнадцатое: если укусили — не скрывай.",
            "Останови кровь, промой, закрой стерильной повязкой.",
            "Жгут — только при сильном кровотечении и не больше часа.",
            "Антисептик, пластырь, свои лекарства — всё в кармане, а не в рюкзаке.",
            "Сто двенадцать набирай сразу.",
        ])],
        shots=[("img07_firstaid2.png", 0.55), ("img11_med2.png", 0.45)],
    ),
    dict(
        badge="ПРАВИЛО 15", title="ХОЛОД И НОЧЬ", idx=7,
        clips=[clip("vo2_07.mp3", [
            "Правило пятнадцатое: к вечеру прячься.",
            "В нашу зиму холод убивает быстрее инфекции.",
            "Подвал, гаражный кооператив, подъезд с закрытой дверью.",
            "Не разводи костёр на виду — дым видно за квартал.",
            "Греться нужно тихо: слои одежды, газета под куртку, термос с горячей водой.",
        ])],
        shots=[("img09_dusk2.png", 0.55), ("img12_frost2.png", 0.45)],
    ),
    dict(
        badge="ПРАВИЛО 16", title="СИГНАЛ", idx=8,
        clips=[clip("vo2_08.mp3", [
            "Правило шестнадцатое: подай сигнал правильно.",
            "Три удара, пауза, три удара, пауза, три удара — это СОС.",
            "Не кричи: крик привлечёт их, ритм привлечёт людей.",
            "И держи радио включённым.",
            "Я дохожу до гаражей, и в эфире впервые слышу живой голос.",
            "Это была вторая серия. В следующей — подвал.",
        ])],
        shots=[("img06_garages2.png", 0.55), ("img13_finale2.png", 0.45)],
    ),
]


# --- производные кадры (цветокоррекция + иней) из уже сгенерированных ---
def derived():
    W, H, R = b.W, b.H, b.R

    im = b.load_fit("img01_stairwell2.png")
    im = b.grade(im, (70, 108, 148), (152, 184, 204), 0.30)
    im = b.glow(im, W * 0.30, H * 0.26, W * 0.55, (172, 208, 238), 0.35)
    im = b.vignette(im, 0.45)
    im.save(os.path.join(R, "img10_stairs2.png"))

    im = b.load_fit("img07_firstaid2.png")
    im = b.grade(im, (56, 72, 92), (196, 140, 78), 0.26)
    im = b.glow(im, W * 0.68, H * 0.36, W * 0.60, (255, 190, 110), 0.40)
    im = b.vignette(im, 0.42)
    im.save(os.path.join(R, "img11_med2.png"))

    im = b.load_fit("img09_dusk2.png")
    im = b.grade(im, (104, 146, 186), (166, 196, 216), 0.28)
    im = ImageEnhance.Contrast(im).enhance(1.06)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    rng = random.Random(29)
    for edge in range(4):
        for _ in range(130):
            if edge == 0:
                x, y, ang = rng.uniform(0, W), rng.uniform(-8, 12), math.pi / 2
            elif edge == 1:
                x, y, ang = rng.uniform(W - 12, W + 8), rng.uniform(0, H), math.pi
            elif edge == 2:
                x, y, ang = rng.uniform(0, W), rng.uniform(H - 12, H + 8), -math.pi / 2
            else:
                x, y, ang = rng.uniform(-8, 12), rng.uniform(0, H), 0.0
            ln = rng.uniform(18, 108)
            alpha = rng.randint(18, 72)
            ex, ey = x + math.cos(ang) * ln, y + math.sin(ang) * ln
            d.line([(x, y), (ex, ey)], fill=(216, 240, 255, alpha),
                   width=rng.choice([1, 1, 2]))
            for _ in range(3):
                f = rng.uniform(0.25, 0.8)
                bx, by = x + (ex - x) * f, y + (ey - y) * f
                ba = ang + rng.choice([-1, 1]) * rng.uniform(0.5, 1.1)
                bl = ln * rng.uniform(0.12, 0.32)
                d.line([(bx, by), (bx + math.cos(ba) * bl, by + math.sin(ba) * bl)],
                       fill=(216, 240, 255, max(10, alpha - 18)), width=1)
    ov = ov.filter(ImageFilter.GaussianBlur(0.5))
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    im = b.vignette(im, 0.42)
    im.save(os.path.join(R, "img12_frost2.png"))

    im = b.load_fit("img06_garages2.png")
    im = b.grade(im, (48, 64, 88), (222, 152, 80), 0.34)
    im = b.glow(im, W * 0.52, H * 0.44, W * 0.66, (255, 196, 118), 0.52)
    im = b.vignette(im, 0.46)
    im.save(os.path.join(R, "img13_finale2.png"))


b.make_derived = derived


if __name__ == "__main__":
    b.main()
    plate = Image.open(os.path.join(b.R, "plate_000.png")).convert("RGBA")
    hud = Image.open(os.path.join(b.R, "hud_000.png")).convert("RGBA")
    cover = os.path.join(b.ROOT, "episode_02_cover.png")
    Image.alpha_composite(plate, hud).convert("RGB").save(cover)
    print("[cover] %s (%.0f KB)" % (cover, os.path.getsize(cover) / 1024))
