import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
S = 2
W, H = 560, 315
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")
BARS = [
    6, 5, 4, 4, 5, 8, 14, 22, 31, 38, 44, 48, 46, 43, 46, 54, 66, 78, 88, 96, 84, 66, 42, 20,
]
FRAMES = 14
DURATION = 115
COLORS = 96


def font(name, size):
    return ImageFont.truetype(str(FONT_DIR / name), size * S)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def blob(size, cx, cy, rx, ry, strength):
    small = Image.new("L", (120, 120), 0)
    pixels = small.load()
    for y in range(120):
        for x in range(120):
            dx = (x - 60) / 60.0
            dy = (y - 60) / 60.0
            pixels[x, y] = int(max(0.0, 1.0 - math.sqrt(dx * dx + dy * dy)) ** 2 * strength)
    width = int(rx * size[0])
    height = int(ry * size[1])
    layer = Image.new("L", size, 0)
    layer.paste(small.resize((width, height), Image.BICUBIC), (int(cx * size[0] - width / 2), int(cy * size[1] - height / 2)))
    return layer


def background():
    size = (W * S, H * S)
    image = Image.new("RGB", size, (11, 18, 32))
    draw = ImageDraw.Draw(image)
    for y in range(size[1]):
        draw.line([(0, y), (size[0], y)], fill=lerp((14, 22, 40), (8, 13, 24), y / float(size[1])))

    image.paste(Image.new("RGB", size, (26, 96, 138)), (0, 0), blob(size, 0.82, 0.95, 0.95, 1.05, 210))
    image.paste(Image.new("RGB", size, (32, 64, 138)), (0, 0), blob(size, 0.12, 0.02, 0.9, 0.9, 150))
    image.paste(Image.new("RGB", size, (10, 14, 26)), (0, 0), blob(size, 0.5, 0.5, 1.2, 1.2, 40))
    return image


def frame(base, phase):
    size = base.size
    left = 34 * S
    right = W * S - 34 * S
    baseline = 292 * S
    height = 112 * S
    slot = (right - left) / float(len(BARS))
    bar_width = slot * 0.72
    top_value = max(BARS)

    bars = []
    for index, value in enumerate(BARS):
        wave = math.sin(2 * math.pi * (index / float(len(BARS)) - phase))
        scale = 0.84 + 0.16 * wave
        current = max(2, value / float(top_value) * height * scale)
        x0 = left + index * slot + (slot - bar_width) / 2.0
        x1 = x0 + bar_width
        heat = value / float(top_value)
        bars.append((x0, baseline - current, x1, heat))

    halo = Image.new("RGB", size, (0, 0, 0))
    halo_draw = ImageDraw.Draw(halo)
    for x0, y0, x1, heat in bars:
        color = lerp((37, 99, 235), (56, 224, 245), heat ** 0.8)
        halo_draw.rounded_rectangle([x0, min(y0 + 6 * S, baseline - 4 * S), x1, baseline], radius=bar_width * 0.34, fill=color)
    halo = halo.filter(ImageFilter.GaussianBlur(10 * S)).point(lambda value: int(value * 0.5) if value > 14 else 0)
    halo = halo.filter(ImageFilter.GaussianBlur(3 * S))

    image = ImageChops.screen(base, halo)
    draw = ImageDraw.Draw(image, "RGBA")

    title = font("DejaVuSans-Bold.ttf", 36)
    subtitle = font("DejaVuSans.ttf", 14)
    small = font("DejaVuSans.ttf", 11)

    draw.text((35 * S, 38 * S), "Chat Stats", font=title, fill=(255, 255, 255))
    draw.text((36 * S, 92 * S), "статистика чата", font=subtitle, fill=(152, 174, 202))
    draw.text((36 * S, 120 * S), "кто пишет  ·  часы  ·  слова  ·  паузы", font=small, fill=(104, 124, 152))
    handle = "@ox4gg"
    width = draw.textlength(handle, font=small)
    draw.text((W * S - 35 * S - width, 40 * S), handle, font=small, fill=(132, 150, 176))

    for step in (1, 2, 3):
        y = baseline - height * step / 3.0
        draw.line([(left, y), (right, y)], fill=(255, 255, 255, 14), width=max(1, S // 2))
    draw.line([(left, baseline), (right, baseline)], fill=(255, 255, 255, 40), width=max(1, S // 2))

    for x0, y0, x1, heat in bars:
        color = lerp((41, 106, 240), (58, 226, 246), heat ** 0.8)
        alpha = int(150 + 105 * heat)
        draw.rounded_rectangle([x0, y0, x1, baseline - S], radius=bar_width * 0.34, fill=color + (alpha,))
        draw.rounded_rectangle(
            [x0, y0, x1, y0 + max(2 * S, 3 * S)],
            radius=bar_width * 0.34,
            fill=(236, 254, 255, int(60 + 90 * heat)),
        )

    draw.text((left, baseline + 9 * S), "00", font=small, fill=(108, 126, 152))
    stamp = "23"
    width = draw.textlength(stamp, font=small)
    draw.text((right - width, baseline + 9 * S), stamp, font=small, fill=(108, 126, 152))
    return image.resize((W, H), Image.LANCZOS)


def main():
    ASSETS.mkdir(exist_ok=True)
    base = background()
    raw = [frame(base, index / float(FRAMES)) for index in range(FRAMES)]

    samples = raw[::3]
    montage = Image.new("RGB", (W, H * len(samples)))
    for index, sample in enumerate(samples):
        montage.paste(sample, (0, index * H))
    palette_source = montage.quantize(colors=COLORS, method=Image.MEDIANCUT)
    frames = [image.quantize(palette=palette_source, dither=Image.NONE) for image in raw]

    gif_path = ASSETS / "cover.gif"
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=DURATION,
        loop=0,
        optimize=True,
        disposal=2,
    )
    raw[0].save(ASSETS / "cover.png", optimize=True)
    print(gif_path, gif_path.stat().st_size)
    print(ASSETS / "cover.png", (ASSETS / "cover.png").stat().st_size)


if __name__ == "__main__":
    main()
