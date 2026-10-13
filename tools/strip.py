#!/usr/bin/env python3
"""Служебная утилита: собрать «плёнку» из кадров .kvs в один PNG (для проверки глазами)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import kvs                                    # noqa: E402
from kvs.png import encode_png                # noqa: E402


def strip(src: str, out: str, count: int = 6, ss: int = 3, cell: int = 160,
          pad: int = 6, bg=(12, 12, 18, 255)):
    r = kvs.load(src, ss=ss)
    n = r.frames
    idxs = [round(i * (n - 1) / max(1, count - 1)) for i in range(count)]
    from kvs.renderer import resize
    cells = []
    for i in idxs:
        fb = r.render_index(int(i))
        cells.append(resize(fb, cell, max(1, round(cell * fb.h / fb.w))))
    h = max(c.h for c in cells) + pad * 2
    w = sum(c.w for c in cells) + pad * (len(cells) + 1)
    canvas = kvs.Framebuffer(w, h, bg)
    x = pad
    for c in cells:
        for y in range(c.h):
            for xx in range(c.w):
                cr, cg, cb, ca = c.get(xx, y)
                if ca == 0:
                    continue
                sa = ca / 255.0
                i2 = ((y + pad) * canvas.w + x + xx) * 4
                da = canvas.px[i2 + 3] / 255.0
                oa = sa + da * (1 - sa)
                canvas.px[i2] = int((cr * sa + canvas.px[i2] * da * (1 - sa)) / oa)
                canvas.px[i2 + 1] = int((cg * sa + canvas.px[i2 + 1] * da * (1 - sa)) / oa)
                canvas.px[i2 + 2] = int((cb * sa + canvas.px[i2 + 2] * da * (1 - sa)) / oa)
                canvas.px[i2 + 3] = int(oa * 255)
        x += c.w + pad
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(encode_png(canvas.w, canvas.h, canvas.px))
    print(f"{src} -> {out} ({canvas.w}x{canvas.h}, кадры {idxs})")


if __name__ == "__main__":
    args = sys.argv[1:]
    ss = 3
    if "--fast" in args:
        args.remove("--fast")
        ss = 2
    for a in args:
        name = os.path.splitext(os.path.basename(a))[0]
        strip(a, os.path.join(ROOT, "renders", name + "_strip.png"), ss=ss)
