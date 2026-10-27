#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ПЕРВЫЙ ДЕНЬ / Серия 01 — сборка 3-минутного эпизода.

Всё делается локально: изображения -> типографика -> Ken Burns -> H.264,
озвучка -> саунд-дизайн -> loudnorm -> AAC, затем multiplex в один MP4.
Никакого интерактива: на выходе обычный видеофайл, который просто смотрят.

Запуск: /home/user/venv/bin/python build_episode.py
"""
import os
import re
import sys
import json
import wave
import math
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter, ImageEnhance
import imageio_ffmpeg
import matplotlib

FF = imageio_ffmpeg.get_ffmpeg_exe()
ROOT = os.path.dirname(os.path.abspath(__file__))
R = os.path.join(ROOT, "render")
os.makedirs(R, exist_ok=True)

W, H = 1280, 720
FPS = 25
SR = 48000
TOTAL_FRAMES = 180 * FPS          # ровно 3:00
INTRO_F = 112                     # 4.48 c
OUTRO_TARGET_F = 112              # ~4.5 c

FONT_DIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
F_BOLD = os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")
F_REG = os.path.join(FONT_DIR, "DejaVuSans.ttf")
F_MONO = os.path.join(FONT_DIR, "DejaVuSansMono-Bold.ttf")

AMBER = (224, 166, 84)
ICE = (232, 240, 244)
INK = (9, 16, 22)

# --- Параметры выпуска (переопределяются в build_episode_02.py) ---
OUT_NAME = "episode_01_first_day.mp4"
META_TITLE = "ПЕРВЫЙ ДЕНЬ — Серия 01"
META_COMMENT = "Инструкция по выживанию в зомби-апокалипсисе в РФ"
INTRO_IMG = "img00_title.png"
OUTRO_IMG = "img12_finale.png"
CARD = dict(
    intro_title="ПЕРВЫЙ ДЕНЬ",
    intro_sub="СЕРИЯ 01  ·  УТРО, КОГДА ГОРОД ЗАБОЛЕЛ",
    intro_line="ИНСТРУКЦИЯ ПО ВЫЖИВАНИЮ В РФ   ·   8 ПРАВИЛ   ·   3 МИНУТЫ",
    intro_footer="ПРОСТО СМОТРИ",
    outro_title="КОНЕЦ ПЕРВОЙ СЕРИИ",
    outro_sub="ДАЛЬШЕ — ВЫХОД ВО ДВОР",
    outro_line="8 ПРАВИЛ  ·  1 ДЕНЬ  ·  ПРОДОЛЖЕНИЕ СЛЕДУЕТ",
    outro_footer="ПЕРВЫЙ ДЕНЬ   ·   СЕРИЯ 01",
    series_tag="ПЕРВЫЙ ДЕНЬ   •   СЕРИЯ 01",
)

# ----------------------------------------------------------------------------
# СЦЕНАРИЙ / ТАЙМКОДЫ
# ----------------------------------------------------------------------------

def clip(f, lines, lead=0.30, tail=0.40, kind="voice"):
    return dict(file=f, lines=lines, lead=lead, tail=tail, kind=kind)


SCENES = [
    dict(
        badge="ПРАВИЛО 01", title="ДЕВЯНОСТО СЕКУНД ТИШИНЫ", idx=1,
        clips=[clip("vo_01.mp3", [
            "Серия первая. Утро, когда город заболел.",
            "Семь двенадцать. Я просыпаюсь в квартире на пятом этаже обычной хрущёвки и не понимаю, что происходит.",
            "За окном воет сирена, телефон без сети, а из подъезда доносится скрежет, будто кто-то ведёт ногтями по двери.",
            "Первое правило: девяносто секунд тишины. Не беги, не кричи, просто слушай.",
            "Паника тратит воду, силы и время, а это теперь валюта.",
        ])],
        shots=[("img01_establishing.png", 0.44), ("img02_bedroom.png", 0.56)],
    ),
    dict(
        badge="ПРАВИЛО 02", title="ДВЕРЬ — ТВОЯ ГРАНИЦА", idx=2,
        clips=[clip("vo_02.mp3", [
            "Правило второе: дверь — твоя граница.",
            "Проверь замок, задвижку и цепочку.",
            "Подопри её шкафом: заражённые не умеют открывать, но умеют давить массой.",
            "Не смотри в глазок дольше двух секунд.",
            "Никогда не открывай на голос соседа, если не видишь его глаза.",
            "Запомни: этаж пятый, лифт не работает, а лестница — твой единственный выход.",
        ])],
        shots=[("img03_door.png", 1.0)],
    ),
    dict(
        badge="ПРАВИЛО 03", title="СВЕТ И ЗВУК — ЭТО МАЯК", idx=3,
        clips=[clip("vo_03.mp3", [
            "Правило третье: свет и звук — это маяк.",
            "Задёрни шторы, выключи люстру.",
            "Заклей стёкла скотчем и плёнкой, чтобы они не звенели и не разлетелись.",
            "К окну подходи сбоку, не в полный рост.",
            "Внизу, во дворе, я вижу их: идут медленно, но всегда на шум.",
            "Поэтому телефон на беззвук, шаги в носках, разговоры шёпотом.",
        ])],
        shots=[("img04_window.png", 1.0)],
    ),
    dict(
        badge="ПРАВИЛО 04", title="ВОДА И ГАЗ", idx=4,
        clips=[clip("vo_04.mp3", [
            "Правило четвёртое: вода и газ.",
            "Пока труба жива, набери ванну, кастрюли и бутылки.",
            "Три литра на человека в сутки — минимум, и ещё столько же про запас.",
            "Обязательно перекрой газовый кран на кухне.",
            "Один прорыв, и пятый этаж вспыхнет раньше, чем приедут пожарные.",
            "Воду потом не включишь, а сухая батарея отопления зимой опаснее любого зомби.",
        ])],
        shots=[("img05_water.png", 1.0)],
    ),
    dict(
        badge="ПРАВИЛО 05", title="СВЯЗЬ И ЭФИР", idx=5,
        clips=[
            clip("vo_05a.mp3", [
                "Правило пятое: связь. Заряди телефон и пауэрбанк.",
                "Но главное — найди старый приёмник на батарейках.",
                "Соты лягут первыми, эфир живёт дольше. Слушай эфир.",
            ], tail=0.85),
            clip("vo_radio.mp3", [
                "Внимание. Говорит радио МЧС.",
                "Оставайтесь в помещениях, закройте окна и двери, запаситесь водой.",
                "Не подходите к окнам. Сохраняйте спокойствие.",
                "Повторяю — сохраняйте спокойствие.",
            ], lead=0.55, tail=0.60, kind="radio"),
            clip("vo_05b.mp3", [
                "Сто двенадцать набирай только при пожаре, ране или прорыве — сеть перегружена.",
                "Запиши частоту на бумаге: электроника сядет, бумага останется.",
            ], lead=0.20),
        ],
        shots=[("img06_radio.png", 1.0)],
    ),
    dict(
        badge="ПРАВИЛО 06", title="ТРЕВОЖНЫЙ РЮКЗАК", idx=6,
        clips=[clip("vo_06.mp3", [
            "Правило шестое: тревожный рюкзак.",
            "Аптечка: бинты, антисептик, пластырь, свои лекарства.",
            "Документы в пакет, нож, спички, фонарик, батарейки, еда на три дня и термос.",
            "И одежда слоями: в нашу зиму холод убивает быстрее инфекции.",
            "Всё это должно стоять у двери, а не в шкафу. Счёт пойдёт на минуты.",
        ])],
        shots=[("img07_backpack.png", 0.54), ("img10_frost.png", 0.46)],
    ),
    dict(
        badge="ПРАВИЛО 07", title="ВЫЖДИ СУТКИ", idx=7,
        clips=[clip("vo_07.mp3", [
            "Правило седьмое: выжди сутки.",
            "Не выходи, даже если стало тихо.",
            "Тишина — не безопасность, это просто пауза между волнами.",
            "Отметь соседей через стену, но дверь не открывай. Слушай лестничную клетку.",
            "Если на площадке слышны шаги, сиди в ванной с закрытой дверью.",
            "Там меньше эха и нет окон.",
        ])],
        shots=[("img08_darkness.png", 0.55), ("img09_stairwell.png", 0.45)],
    ),
    dict(
        badge="ПРАВИЛО 08", title="ЭВАКУАЦИЯ", idx=8,
        clips=[clip("vo_08.mp3", [
            "Правило восьмое: эвакуация.",
            "Уходи только если пожар, газ или прорыв.",
            "Лифт исключён. Спускайся по лестнице, прижимаясь к стене, на рассвете, когда двор пуст.",
            "Двигайся тихо, коротко, без криков. Один рюкзак, одна дорога, одна цель.",
            "Я открываю дверь подъезда. Город молчит.",
            "Это была первая серия, в следующей мы выйдем во двор.",
        ])],
        shots=[("img11_exit.png", 0.55), ("img12_finale.png", 0.45)],
    ),
]

# ----------------------------------------------------------------------------
# УТИЛИТЫ
# ----------------------------------------------------------------------------

def run(args, quiet=True):
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        sys.stderr.write(" ".join(args) + "\n")
        sys.stderr.write(p.stderr.decode("utf-8", "replace")[-4000:] + "\n")
        raise RuntimeError("ffmpeg failed: %s" % args[:4])
    return p.stdout, p.stderr


def read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getframerate() == SR and w.getnchannels() == 1
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    return x


def write_wav(path, x):
    x = np.clip(x, -1.0, 1.0)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767.0).astype("<i2").tobytes())


def trim_silence(x, pad=0.14, thresh=0.012):
    peak = float(np.max(np.abs(x))) + 1e-9
    active = np.flatnonzero(np.abs(x) > peak * thresh)
    if len(active) == 0:
        return x
    a = max(0, int(active[0] - pad * SR))
    b = min(len(x), int(active[-1] + pad * SR))
    return x[a:b]


def font(size, bold=True, mono=False):
    return ImageFont.truetype(F_MONO if mono else (F_BOLD if bold else F_REG), size)


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ----------------------------------------------------------------------------
# ШАГ 1 — ОЗВУЧКА: декод, обрезка тишины, лёгкое ускорение под хронометраж
# ----------------------------------------------------------------------------

def prepare_voice():
    files = sorted({c["file"] for s in SCENES for c in s["clips"]})
    raw = {}
    for i, f in enumerate(files):
        src = os.path.join(R, f)
        dec = os.path.join(R, "_dec_%02d.wav" % i)
        trim = os.path.join(R, "_trim_%02d.wav" % i)
        run([FF, "-y", "-v", "error", "-i", src, "-ar", str(SR), "-ac", "1",
             "-c:a", "pcm_s16le", dec])
        x = trim_silence(read_wav(dec))
        write_wav(trim, x)
        raw[f] = len(x) / SR
        os.remove(dec)
    print("[voice] сырая длительность речи: %.2f c" % sum(raw.values()))
    return files, raw


def solve_factor(raw):
    def frames(factor):
        n = INTRO_F
        for s in SCENES:
            for c in s["clips"]:
                n += (round(c["lead"] * FPS)
                      + round(raw[c["file"]] / factor * FPS)
                      + round(c["tail"] * FPS))
        return n

    target = TOTAL_FRAMES - OUTRO_TARGET_F
    lo, hi = 0.80, 1.60
    for _ in range(70):
        mid = (lo + hi) / 2
        if frames(mid) > target:
            lo = mid          # надо быстрее
        else:
            hi = mid
    factor = round((lo + hi) / 2, 4)
    factor = min(max(factor, 0.90), 1.35)
    print("[voice] atempo = %.4f" % factor)
    return factor


def process_voice(files, raw, factor):
    out = {}
    for i, f in enumerate(files):
        trim = os.path.join(R, "_trim_%02d.wav" % i)
        dst = os.path.join(R, "_vo_%02d.wav" % i)
        run([FF, "-y", "-v", "error", "-i", trim,
             "-af", "atempo=%.5f" % factor, "-ar", str(SR), "-ac", "1",
             "-c:a", "pcm_s16le", dst])
        data = read_wav(dst)
        out[f] = dict(path=dst, data=data, dur=len(data) / SR)
        os.remove(trim)
    return out


# ----------------------------------------------------------------------------
# ШАГ 2 — ТАЙМЛАЙН (всё в кадрах, чтобы A/V совпали покадрово)
# ----------------------------------------------------------------------------

def build_timeline(voice):
    events = []           # (start_f, end_f, text, kind)
    scenes_tl = []
    cur = INTRO_F
    for sc in SCENES:
        start = cur
        for c in sc["clips"]:
            lead_f = round(c["lead"] * FPS)
            dur_f = round(voice[c["file"]]["dur"] * FPS)
            tail_f = round(c["tail"] * FPS)
            cs = cur + lead_f
            lines = c["lines"]
            gap = 2
            usable = max(len(lines), dur_f - gap * (len(lines) - 1))
            weights = [max(1.0, len(t) ** 0.85) for t in lines]
            alloc = [max(1, int(round(usable * w / sum(weights)))) for w in weights]
            # выровнять сумму ровно до dur_f
            diff = (dur_f - gap * (len(lines) - 1)) - sum(alloc)
            alloc[-1] += diff
            p = cs
            for text, n in zip(lines, alloc):
                events.append((p, p + n, text, c["kind"]))
                p += n + gap
            cur = cs + dur_f + tail_f
        scenes_tl.append(dict(start=start, end=cur, spec=sc))

    used = cur
    outro_f = TOTAL_FRAMES - used
    if outro_f < 50:
        raise RuntimeError("Хронометраж не сходится: outro=%d кадров" % outro_f)

    shots = []
    shots.append(dict(start=0, end=INTRO_F, img=INTRO_IMG,
                      card="intro", progress=0.0, fade_in=("in", 0.8), fade_out=("out", 0.35)))
    for st in scenes_tl:
        sc = st["spec"]
        total = st["end"] - st["start"]
        ws = [w for _, w in sc["shots"]]
        counts = [int(round(total * w)) for w in ws[:-1]]
        counts.append(total - sum(counts))
        p = st["start"]
        for i, ((img, _), n) in enumerate(zip(sc["shots"], counts)):
            shots.append(dict(start=p, end=p + n, img=img, card=None,
                              badge=sc["badge"], title=sc["title"],
                              progress=(sc["idx"] - 1 + (i + 1) / len(counts)) / 8.0,
                              fade_in=("in", 0.25) if i == 0 else None,
                              fade_out=None))
            p += n
    shots.append(dict(start=used, end=TOTAL_FRAMES, img=OUTRO_IMG,
                      card="outro", progress=1.0,
                      fade_in=("in", 0.30), fade_out=("out", 1.0)))
    print("[timeline] сцен: %d, кадров: %d, outro: %.2f c, титров: %d"
          % (len(scenes_tl), TOTAL_FRAMES, outro_f / FPS, len(events)))
    return dict(events=events, shots=shots, scenes=scenes_tl, outro_f=outro_f)


# ----------------------------------------------------------------------------
# ШАГ 3 — САУНД-ДИЗАЙН
# ----------------------------------------------------------------------------

def shaped_noise(n, seed, lo, hi):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal(n).astype(np.float32)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    X[(f < lo) | (f > hi)] = 0
    y = np.fft.irfft(X, n=n).astype(np.float32)
    return y / (np.max(np.abs(y)) + 1e-9)


def adsr(n, a_s, r_s, curve=1.6):
    e = np.ones(n, np.float32)
    a, r = int(a_s * SR), int(r_s * SR)
    if a > 0:
        e[:a] = np.linspace(0, 1, a, dtype=np.float32) ** curve
    if r > 0:
        e[-r:] *= np.linspace(1, 0, r, dtype=np.float32) ** curve
    return e


def put(arr, buf, t):
    i = int(t * SR)
    j = min(len(arr), i + len(buf))
    if i >= len(arr) or j <= i:
        return
    arr[i:j] += buf[: j - i]


def thud(dur=0.60, f0=78, f1=36, seed=1, gain=1.0):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    freq = f1 + (f0 - f1) * np.exp(-t * 15)
    body = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-t * 7)
    crack = shaped_noise(n, seed, 180, 2800) * np.exp(-t * 48) * 0.30
    return (body + crack) * adsr(n, 0.002, 0.22) * gain


def siren(dur=8.0, seed=3):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f = 645 + 155 * np.sin(2 * np.pi * 0.28 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = (0.6 * np.sin(ph) + 0.22 * np.sin(2 * ph)) * (0.68 + 0.32 * np.sin(2 * np.pi * 0.28 * t))
    x *= adsr(n, 0.9, 1.4)
    d = int(0.43 * SR)
    x[d:] += 0.22 * x[:-d]
    d2 = int(0.91 * SR)
    x[d2:] += 0.10 * x[:-d2]
    return x


def scratch(dur=2.4, seed=5):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    x = shaped_noise(n, seed, 700, 4200)
    mod = np.clip(np.sin(2 * np.pi * 6.3 * t) * 0.5 + 0.5, 0, 1) ** 2
    gate = (np.sin(2 * np.pi * 0.85 * t) > -0.25).astype(np.float32)
    return x * mod * gate * adsr(n, 0.18, 0.45)


def glass(dur=1.3, seed=7):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    x = np.zeros(n, np.float32)
    for f in (1850, 2470, 3310, 4180, 5300):
        x += np.sin(2 * np.pi * f * t + f * 0.0007 * t) * np.exp(-t * (6 + f / 900)) / math.sqrt(f)
    x += shaped_noise(n, seed, 2800, 11000) * np.exp(-t * 15) * 0.35
    return x * adsr(n, 0.003, 0.5)


def water(dur=7.0, seed=9):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    x = shaped_noise(n, seed, 250, 4500)
    return x * (0.75 + 0.25 * np.sin(2 * np.pi * 0.7 * t)) * adsr(n, 0.6, 1.3)


def click(seed=11):
    n = int(0.08 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    return shaped_noise(n, seed, 900, 9000) * np.exp(-t * 95)


def static(dur=1.35, seed=13):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    gate = (np.sin(2 * np.pi * 11 * t) > 0.05).astype(np.float32)
    return shaped_noise(n, seed, 180, 6500) * gate * adsr(n, 0.01, 0.3)


def tuning(dur=0.9, seed=15):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f = 420 + 1250 * (t / dur)
    x = 0.35 * np.sin(2 * np.pi * np.cumsum(f) / SR)
    x += shaped_noise(n, seed, 300, 5000) * 0.5
    return x * adsr(n, 0.02, 0.2)


def heartbeat(dur=14.0, bpm=66):
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    t, k = 0.0, 0
    while t < dur - 0.6:
        put(out, thud(0.34, 70, 38, 100 + k, 1.0), t)
        put(out, thud(0.30, 64, 34, 150 + k, 0.58), t + 0.21)
        t += 60.0 / bpm
        k += 1
    return out * adsr(n, 0.7, 1.2)


def footsteps(dur=10.0, step=0.70, seed=21):
    n = int(dur * SR)
    out = np.zeros(n, np.float32)
    t, k = 0.0, 0
    sc_n = int(0.18 * SR)
    while t < dur - 0.4:
        put(out, thud(0.28, 110, 52, 200 + k, 0.52), t)
        sc = shaped_noise(sc_n, 300 + k, 600, 3200) * np.exp(-np.arange(sc_n, dtype=np.float32) / SR * 24) * 0.22
        put(out, sc, t + 0.01)
        t += step
        k += 1
    return out * adsr(n, 0.5, 0.9)


def riser(dur=1.7, seed=31):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f = 110 + 540 * (t / dur) ** 2
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.45
    x += shaped_noise(n, seed, 200, 1700) * (t / dur) * 0.35
    return x * adsr(n, 0.35, 0.05, curve=1.0) * (t / dur) ** 1.4


def creak(dur=1.7, seed=41):
    n = int(dur * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f = 175 + 95 * np.sin(2 * np.pi * 1.6 * t)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.3 + 0.7 * np.abs(np.sin(2 * np.pi * 2.2 * t)))
    x += shaped_noise(n, seed, 400, 2200) * 0.12
    return x * adsr(n, 0.12, 0.45) * 0.55


def radio_process(x):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    X[(f < 380) | (f > 3400)] = 0
    y = np.fft.irfft(X, n=len(x)).astype(np.float32)
    y = np.tanh(y * 3.0) / np.tanh(3.0)
    y /= (np.max(np.abs(y)) + 1e-9)
    t = np.arange(len(y), dtype=np.float32) / SR
    y *= 0.93 + 0.07 * np.sin(2 * np.pi * 3.1 * t)
    y += 0.012 * np.sin(2 * np.pi * 1000 * t)
    return y


def build_audio(tl, voice):
    n = int(round(TOTAL_FRAMES / FPS * SR))
    L = np.zeros(n, np.float32)
    AR = np.zeros(n, np.float32)

    def mix(buf, t, gain=1.0, pan=0.0):
        if t < 0:
            skip = int(-t * SR)
            if skip >= len(buf):
                return
            buf, t = buf[skip:], 0.0
        i = int(t * SR)
        j = min(n, i + len(buf))
        if i >= n or j <= i:
            return
        seg = buf[: j - i] * gain
        gl, gr = math.sqrt(max(0.0, 1.0 - pan)), math.sqrt(max(0.0, 1.0 + pan))
        L[i:j] += seg * gl
        AR[i:j] += seg * gr

    # --- постоянные слои: низкий гул, ветер, комнатный тон (кусками по 30 c) ---
    chunk_n = 4 * SR
    wind_chunk = shaped_noise(chunk_n, 51, 35, 430)
    rumble_chunk = shaped_noise(chunk_n, 52, 20, 130)
    rng = np.random.default_rng(77)
    for off in range(0, n, 30 * SR):
        m = min(30 * SR, n - off)
        t = (np.arange(m, dtype=np.float32) + off) / SR
        d = np.zeros(m, np.float32)
        for f, a in ((43.0, 0.50), (57.3, 0.28), (86.0, 0.12)):
            d += a * np.sin(2 * np.pi * f * t + 0.4 * np.sin(2 * np.pi * 0.05 * t))
        d *= 0.80 + 0.20 * np.sin(2 * np.pi * 0.07 * t)
        L[off:off + m] += d * 0.052
        AR[off:off + m] += d * 0.052

        reps = int(np.ceil(m / chunk_n))
        wc = np.tile(wind_chunk, reps)[:m]
        rc = np.tile(rumble_chunk, reps)[:m]
        ctrl = rng.uniform(0.30, 1.0, max(3, m // (SR // 2) + 2)).astype(np.float32)
        lfo = np.interp(np.arange(m), np.linspace(0, m, len(ctrl)), ctrl).astype(np.float32)
        k = SR // 2
        cs = np.cumsum(np.pad(lfo, (k, k), mode="edge"), dtype=np.float64)
        lfo = ((cs[2 * k:2 * k + m] - cs[:m]) / (2 * k)).astype(np.float32)
        L[off:off + m] += (wc * lfo * 0.042 + rc * lfo * 0.030)
        AR[off:off + m] += (wc * lfo * 0.046 + rc * lfo * 0.028)

    # --- голоса ---
    marks = {}
    for st in tl["scenes"]:
        marks.setdefault(st["spec"]["idx"], st["start"] / FPS)
    radio_start = None
    for st in tl["scenes"]:
        sc = st["spec"]
        p = st["start"]
        for c in sc["clips"]:
            p += round(c["lead"] * FPS)
            d = voice[c["file"]]["dur"]
            if c["kind"] == "radio":
                radio_start = p / FPS
                mix(static(0.9, 61), radio_start - 0.75, 0.20, -0.15)
                mix(tuning(0.9, 62), radio_start - 0.55, 0.16, 0.15)
                mix(radio_process(voice[c["file"]]["data"]), p / FPS, 0.66, 0.0)
                mix(static(d + 0.4, 63), p / FPS - 0.1, 0.045, 0.0)
            else:
                mix(voice[c["file"]]["data"], p / FPS, 0.92, 0.0)
            p += round(d * FPS) + round(c["tail"] * FPS)

    # --- событийные звуки, привязанные к сценам ---
    s = {i: v for i, v in marks.items()}
    mix(siren(9.0), 1.0, 0.085, -0.25)
    mix(siren(6.0, 4), s[2] - 3.2, 0.045, 0.30)
    mix(scratch(2.6), s[1] + 5.0, 0.16, 0.35)
    mix(scratch(2.2, 6), s[2] + 2.2, 0.13, -0.30)
    for t, g in ((0.8, 0.30), (2.0, 0.24), (2.9, 0.34)):
        mix(thud(0.62, 86, 38, 70 + int(t * 10), g), s[2] + t, 1.0, 0.0)
    mix(glass(1.4), s[3] + 1.4, 0.14, -0.20)
    mix(shaped_noise(int(3.2 * SR), 81, 60, 900) * np.exp(-np.arange(int(3.2 * SR), dtype=np.float32) / SR * 1.1), s[3] + 4.0, 0.055, 0.10)
    mix(water(7.5), s[4] + 1.2, 0.075, 0.25)
    mix(click(), s[4] + 8.4, 0.22, -0.10)
    mix(thud(0.5, 60, 30, 83, 0.5), s[4] + 8.45, 0.35, 0.0)
    mix(heartbeat(14.0), s[7] + 1.0, 0.30, 0.0)
    mix(footsteps(10.0), s[8] + 1.5, 0.27, 0.10)
    mix(creak(1.8), s[8] + 12.5, 0.30, -0.25)
    mix(thud(2.4, 48, 26, 91, 0.7), TOTAL_FRAMES / FPS - 4.5, 0.16, 0.0)

    for i in range(2, 9):
        mix(riser(1.7, 90 + i), s[i] - 1.55, 0.055, 0.0)

    # --- мастер-обработка ---
    y = np.stack([L, AR], axis=1)
    y = np.tanh(y * 1.15) / np.tanh(1.15)          # мягкий лимитер
    fade = int(0.9 * SR)
    y[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)[:, None]
    y[-int(1.4 * SR):] *= np.linspace(1, 0, int(1.4 * SR), dtype=np.float32)[:, None]
    peak = float(np.max(np.abs(y))) + 1e-9
    y *= (10 ** (-1.6 / 20)) / peak

    raw_path = os.path.join(R, "_mix_raw.wav")
    with wave.open(raw_path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())

    norm_path = os.path.join(R, "_mix_norm.wav")
    # Двухпроходная ЛИНЕЙНАЯ нормализация. Однопроходный dynamic-режим
    # подтягивает тихие места на +10 dB и делает фоны громче голоса — не берём.
    p1 = subprocess.run(
        [FF, "-hide_banner", "-nostats", "-i", raw_path,
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    blocks = re.findall(r"\{[^{}]+\}", p1.stderr.decode("utf-8", "replace"), re.S)
    m = json.loads(blocks[-1])
    keys = ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
    mi, mtp, mlra, mth, moff = (m[k] for k in keys)
    af = ("loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=%s:measured_TP=%s:"
          "measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true:print_format=summary"
          % (mi, mtp, mlra, mth, moff))
    run([FF, "-y", "-v", "error", "-i", raw_path, "-af", af,
         "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", norm_path])
    print("[audio] готово: %.2f c, input_I=%s LUFS, линейный гейн (без накачки)"
          % (n / SR, mi))
    return norm_path


# ----------------------------------------------------------------------------
# ШАГ 4 — ИЗОБРАЖЕНИЯ: производные кадры, типографика, субтитры
# ----------------------------------------------------------------------------

def load_fit(name):
    im = Image.open(os.path.join(R, name)).convert("RGB")
    return ImageOps.fit(im, (W, H), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def grade(im, top, bottom, strength):
    a = np.asarray(im, dtype=np.float32)
    g = np.zeros((H, W, 3), np.float32)
    for c in range(3):
        g[:, :, c] = np.linspace(top[c], bottom[c], H, dtype=np.float32)[:, None]
    a = a * (1 - strength) + g * strength
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def vignette(im, power=0.45):
    a = np.asarray(im, dtype=np.float32)
    yy = np.linspace(-1, 1, H, dtype=np.float32)[:, None]
    xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :]
    m = 1.0 - power * np.clip(xx * xx + yy * yy, 0, 1.5) / 1.5
    return Image.fromarray(np.clip(a * m[:, :, None], 0, 255).astype(np.uint8), "RGB")


def glow(im, cx, cy, radius, color, strength):
    a = np.asarray(im, dtype=np.float32)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / radius
    m = np.clip(1.0 - d, 0, 1) ** 2
    for c in range(3):
        a[:, :, c] += m * color[c] * strength
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def make_derived():
    # Морозное окно — из спальни: холодный грейд + иней по краям кадра
    im = load_fit("img02_bedroom.png")
    im = grade(im, (120, 160, 195), (176, 202, 218), 0.22)
    im = ImageEnhance.Contrast(im).enhance(1.08)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    rng = random.Random(17)
    for edge in range(4):
        for _ in range(120):
            if edge == 0:
                x, y, ang = rng.uniform(0, W), rng.uniform(-8, 12), math.pi / 2
            elif edge == 1:
                x, y, ang = rng.uniform(W - 12, W + 8), rng.uniform(0, H), math.pi
            elif edge == 2:
                x, y, ang = rng.uniform(0, W), rng.uniform(H - 12, H + 8), -math.pi / 2
            else:
                x, y, ang = rng.uniform(-8, 12), rng.uniform(0, H), 0.0
            ln = rng.uniform(18, 105)
            alpha = rng.randint(18, 70)
            ex = x + math.cos(ang) * ln
            ey = y + math.sin(ang) * ln
            d.line([(x, y), (ex, ey)], fill=(214, 238, 255, alpha), width=rng.choice([1, 1, 2]))
            for b in range(3):
                f = rng.uniform(0.25, 0.8)
                bx, by = x + (ex - x) * f, y + (ey - y) * f
                ba = ang + rng.choice([-1, 1]) * rng.uniform(0.5, 1.1)
                bl = ln * rng.uniform(0.12, 0.32)
                d.line([(bx, by), (bx + math.cos(ba) * bl, by + math.sin(ba) * bl)],
                       fill=(214, 238, 255, max(10, alpha - 18)), width=1)
    ov = ov.filter(ImageFilter.GaussianBlur(0.5))
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    im = vignette(im, 0.38)
    im.save(os.path.join(R, "img10_frost.png"))

    # Рассветный подъезд — тёплый свет на лестничной клетке
    im = load_fit("img09_stairwell.png")
    im = grade(im, (58, 74, 96), (214, 150, 78), 0.30)
    im = glow(im, W * 0.74, H * 0.30, W * 0.62, (255, 186, 104), 0.42)
    im = vignette(im, 0.42)
    im.save(os.path.join(R, "img11_exit.png"))

    # Финал — тот же двор, но с рассветом
    im = load_fit("img01_establishing.png")
    im = grade(im, (46, 64, 92), (236, 162, 84), 0.36)
    im = glow(im, W * 0.58, H * 0.46, W * 0.70, (255, 196, 116), 0.55)
    im = vignette(im, 0.44)
    im.save(os.path.join(R, "img12_finale.png"))


def draw_shade(d):
    """Верхняя и нижняя зоны затемнения — строго горизонтальные линии."""
    for y in range(120):
        d.line([(0, y), (W, y)], fill=(6, 12, 18, int(155 * (1 - y / 120) ** 1.3)))
    for y in range(230):
        yy = H - 230 + y
        d.line([(0, yy), (W, yy)], fill=(6, 12, 18, int(190 * (y / 230) ** 1.5)))


def make_plate(shot, out_path):
    """Только картинка. Ни одной буквы: зум не должен двигать типографику."""
    im = load_fit(shot["img"])
    im = ImageEnhance.Color(im).enhance(0.90).convert("RGBA")
    if shot["card"]:
        im = Image.alpha_composite(im, Image.new("RGBA", (W, H), (6, 12, 18, 175)))
    im.convert("RGB").save(out_path)


def make_hud(shot, out_path):
    """Вся статика лежит поверх зумированного кадра и никогда не смещается."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if shot["card"] == "intro":
        d.text((W // 2, 268), CARD["intro_title"], font=font(86), fill=ICE, anchor="mm",
               stroke_width=2, stroke_fill=(0, 0, 0, 160))
        d.line([(W // 2 - 205, 338), (W // 2 + 205, 338)], fill=AMBER + (230,), width=3)
        d.text((W // 2, 392), CARD["intro_sub"],
               font=font(27), fill=AMBER, anchor="mm")
        d.text((W // 2, 452), CARD["intro_line"],
               font=font(18), fill=(206, 218, 226), anchor="mm")
        d.text((W // 2, H - 46), CARD["intro_footer"], font=font(16), fill=(160, 176, 188), anchor="mm")
    elif shot["card"] == "outro":
        d.text((W // 2, 250), CARD["outro_title"], font=font(64), fill=ICE, anchor="mm",
               stroke_width=2, stroke_fill=(0, 0, 0, 160))
        d.line([(W // 2 - 190, 318), (W // 2 + 190, 318)], fill=AMBER + (230,), width=3)
        d.text((W // 2, 372), CARD["outro_sub"], font=font(30), fill=AMBER, anchor="mm")
        d.text((W // 2, 430), CARD["outro_line"],
               font=font(19), fill=(214, 226, 234), anchor="mm")
        d.text((W // 2, H - 46), CARD["outro_footer"], font=font(16),
               fill=(160, 176, 188), anchor="mm")
    else:
        draw_shade(d)
        f_badge, f_title, f_tag = font(21), font(24), font(17)
        label = shot["badge"]
        tw = d.textlength(label, font=f_badge)
        bx0, by0, bw, bh = 40, 36, int(tw + 44), 40
        d.rounded_rectangle([bx0, by0, bx0 + bw, by0 + bh], radius=6,
                            fill=(12, 22, 30, 214), outline=AMBER + (220,), width=2)
        d.text((bx0 + bw / 2, by0 + bh / 2), label, font=f_badge, fill=AMBER, anchor="mm")
        d.text((bx0 + bw + 20, by0 + bh / 2), shot["title"], font=f_title, fill=ICE, anchor="lm")
        d.text((W - 40, 56), CARD["series_tag"], font=f_tag,
               fill=(206, 218, 226, 220), anchor="rm")
        px0, px1, py = 40, W - 40, H - 22
        d.rounded_rectangle([px0, py, px1, py + 4], radius=2, fill=(255, 255, 255, 38))
        d.rounded_rectangle([px0, py, int(px0 + (px1 - px0) * shot["progress"]), py + 4],
                            radius=2, fill=AMBER + (235,))
        for i in range(1, 8):
            x = int(px0 + (px1 - px0) * i / 8)
            d.line([(x, py - 3), (x, py + 7)], fill=(255, 255, 255, 85), width=1)
    im.save(out_path)


def make_caption(text, kind, out_path, index):
    """Субтитр: строго по центру, строго горизонтально, без поворотов."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f = font(31 if kind == "voice" else 29, bold=True, mono=(kind == "radio"))
    max_w = 1070
    lines = wrap(d, text, f, max_w)[:3]
    line_w = max(d.textlength(t, font=f) for t in lines)
    pad_x, pad_y, lh = 34, 20, 44
    bw = int(min(W - 80, line_w + 2 * pad_x))
    if bw % 2:                      # чётная ширина => идеальное центрирование
        bw += 1
    bh = 2 * pad_y + lh * len(lines)
    bx0 = (W - bw) // 2
    by0 = 646 - bh
    accent = AMBER if kind == "voice" else (255, 196, 120)
    d.rounded_rectangle([bx0, by0, bx0 + bw, by0 + bh], radius=10,
                        fill=(8, 16, 23, 214), outline=accent + (150,), width=2)
    d.rounded_rectangle([bx0 + 12, by0 + 12, bx0 + 17, by0 + bh - 12], radius=2,
                        fill=accent + (235,))
    if kind == "radio":
        d.rounded_rectangle([bx0 + bw - 158, by0 - 15, bx0 + bw, by0 + 12], radius=5,
                            fill=(70, 42, 18, 235), outline=accent + (200,), width=1)
        d.text((bx0 + bw - 79, by0 - 1), "РАДИО МЧС", font=font(15),
               fill=accent, anchor="mm")
    for i, line in enumerate(lines):
        cy = by0 + pad_y + i * lh + lh // 2
        d.text((W // 2 + 2, cy + 2), line, font=f, fill=(0, 0, 0, 170), anchor="mm")
        d.text((W // 2, cy), line, font=f,
               fill=(246, 249, 251) if kind == "voice" else (255, 224, 178), anchor="mm")
    im.save(out_path)
    return dict(index=index, box_x=bx0, box_y=by0, box_w=bw, box_h=bh,
                centered=(bx0 * 2 + bw == W), lines=len(lines), kind=kind)


def build_graphics(tl):
    make_derived()
    cap_cache, cap_meta = {}, []
    for i, (s, e, text, kind) in enumerate(tl["events"]):
        key = (text, kind)
        if key not in cap_cache:
            p = os.path.join(R, "cap_%03d.png" % len(cap_cache))
            meta = make_caption(text, kind, p, len(cap_cache))
            cap_meta.append(meta)
            cap_cache[key] = p
    for i, sh in enumerate(tl["shots"]):
        plate = os.path.join(R, "plate_%03d.png" % i)
        hud = os.path.join(R, "hud_%03d.png" % i)
        make_plate(sh, plate)
        make_hud(sh, hud)
        sh["plate"] = plate
        sh["hud"] = hud
        sh["caps"] = []
        for (s, e, text, kind) in tl["events"]:
            a, b = max(s, sh["start"]), min(e, sh["end"])
            if b - a < 2:
                continue
            sh["caps"].append((cap_cache[(text, kind)], (a - sh["start"]) / FPS,
                              (b - sh["start"]) / FPS))
    # QC: все плашки субтитров центрированы по X и лежат на одной линии по Y
    assert all(abs(m["box_x"] * 2 + m["box_w"] - W) <= 1 for m in cap_meta), "Субтитр не отцентрирован"
    print("[graphics] кадров: %d, уникальных титров: %d, все центрированы: OK"
          % (len(tl["shots"]), len(cap_meta)))
    return cap_meta


# ----------------------------------------------------------------------------
# ШАГ 5 — РЕНДЕР ВИДЕО
# ----------------------------------------------------------------------------

def render_shot(args):
    i, sh = args
    N = sh["end"] - sh["start"]
    D = N / FPS
    out = os.path.join(R, "shot_%03d.mp4" % i)
    cmd = [FF, "-y", "-v", "error",
           "-loop", "1", "-framerate", str(FPS), "-t", "%.3f" % (D + 0.2), "-i", sh["plate"],
           "-loop", "1", "-framerate", str(FPS), "-t", "%.3f" % (D + 0.2), "-i", sh["hud"]]
    for cap, _, _ in sh["caps"]:
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", "%.3f" % (D + 0.2), "-i", cap]

    rate = 0.00022 + (i % 5) * 0.000045
    if i % 2 == 0:
        z = "min(pzoom+%.6f,1.13)" % rate
    else:
        z = "if(lte(on,1),1.13,max(pzoom-%.6f,1.0))" % rate
    x = "clip(iw/2-(iw/zoom/2)+sin(on/%d)*%d,0,iw-iw/zoom)" % (80 + i * 9, 8 + i % 3 * 4)
    y = "clip(ih/2-(ih/zoom/2)+cos(on/%d)*6,0,ih-ih/zoom)" % (100 + i * 7)
    zp = ("zoompan=z='%s':d=1:x='%s':y='%s':s=%dx%d:fps=%d" % (z, x, y, W, H, FPS))

    parts = ["[0:v]%s,setsar=1,format=rgba[v0]" % zp,
             "[1:v]format=rgba,setsar=1[hud]",
             "[v0][hud]overlay=0:0[v1]"]
    prev = "v1"
    for k, (cap, a, b) in enumerate(sh["caps"]):
        parts.append("[%d:v]format=rgba,setsar=1[c%d]" % (k + 2, k))
        parts.append("[%s][c%d]overlay=0:0:enable='between(t,%.3f,%.3f)'[v%d]"
                     % (prev, k, max(0.0, a), min(D, b), k + 2))
        prev = "v%d" % (k + 2)
    last = prev
    tail = []
    if sh["fade_in"]:
        tail.append("fade=t=in:st=0:d=%.2f" % sh["fade_in"][1])
    if sh["fade_out"]:
        tail.append("fade=t=out:st=%.3f:d=%.2f" % (max(0, D - sh["fade_out"][1]), sh["fade_out"][1]))
    tail += ["format=yuv420p", "setsar=1"]
    parts.append("[%s]%s[out]" % (last, ",".join(tail)))

    cmd += ["-filter_complex", ";".join(parts), "-map", "[out]",
            "-frames:v", str(N), "-an", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "20", "-profile:v", "high", "-pix_fmt", "yuv420p",
            "-r", str(FPS), "-threads", "1", out]
    run(cmd)
    return out


def render_video(tl):
    with ThreadPoolExecutor(max_workers=2) as ex:
        files = list(ex.map(render_shot, list(enumerate(tl["shots"]))))
    lst = os.path.join(R, "_concat.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for p in files:
            f.write("file '%s'\n" % os.path.abspath(p))
    joined = os.path.join(R, "_video_only.mp4")
    run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
         "-c", "copy", "-movflags", "+faststart", joined])
    print("[video] склеено кадров: %d" % len(files))
    return joined


# ----------------------------------------------------------------------------
# ШАГ 6 — МУЛЬТИПЛЕКС И QC
# ----------------------------------------------------------------------------

def probe(path):
    p = subprocess.run([FF, "-hide_banner", "-i", path],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    txt = p.stderr.decode("utf-8", "replace")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", txt)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else -1
    return dur, txt


def qc(final, cap_meta):
    dur, info = probe(final)
    _, vol = run([FF, "-hide_banner", "-i", final, "-af", "volumedetect",
                  "-f", "null", "-"])
    vtxt = vol.decode("utf-8", "replace")
    mean = re.search(r"mean_volume: ([-\d.]+) dB", vtxt)
    peak = re.search(r"max_volume: ([-\d.]+) dB", vtxt)

    times = [2.5, 9, 26, 48, 70, 92, 112, 132, 152, 168, 177]
    thumbs = []
    for i, t in enumerate(times):
        p = os.path.join(R, "qc_%02d.png" % i)
        run([FF, "-y", "-v", "error", "-ss", str(t), "-i", final,
             "-frames:v", "1", p])
        im = Image.open(p).convert("RGB").resize((426, 240), Image.Resampling.LANCZOS)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 74, 20], fill=(8, 16, 22))
        d.text((37, 10), "%02d:%02d" % (int(t) // 60, int(t) % 60),
               font=font(12), fill=AMBER, anchor="mm")
        thumbs.append(im)
    sheet = Image.new("RGB", (426 * 3 + 16, 240 * 4 + 20), (10, 16, 22))
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % 3) * (426 + 8), (i // 3) * (240 + 6)))
    sheet.save(os.path.join(R, "qc_contact_sheet.png"))

    report = dict(
        duration_sec=round(dur, 3),
        target_sec=180.0,
        resolution="%dx%d" % (W, H),
        fps=FPS,
        shots=len([f for f in os.listdir(R) if f.startswith("shot_") and f.endswith(".mp4")]),
        captions=len(cap_meta),
        captions_centered=all(m["centered"] for m in cap_meta),
        caption_box_y=sorted(set(m["box_y"] for m in cap_meta))[:6],
        mean_volume_db=mean.group(1) if mean else None,
        max_volume_db=peak.group(1) if peak else None,
        streams=("Video: h264" in info) and ("Audio: aac" in info),
    )
    with open(os.path.join(R, "qc_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("[QC] " + json.dumps(report, ensure_ascii=False))
    return report


def main():
    files, raw = prepare_voice()
    factor = solve_factor(raw)
    voice = process_voice(files, raw, factor)
    tl = build_timeline(voice)
    audio = build_audio(tl, voice)
    cap_meta = build_graphics(tl)
    video = render_video(tl)
    final = os.path.join(ROOT, OUT_NAME)
    run([FF, "-y", "-v", "error", "-i", video, "-i", audio,
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
         "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
         "-t", "180", "-metadata", "title=" + META_TITLE,
         "-metadata", "comment=" + META_COMMENT,
         final])
    print("[mux] %s (%.1f MB)" % (final, os.path.getsize(final) / 1e6))
    qc(final, cap_meta)


if __name__ == "__main__":
    main()
