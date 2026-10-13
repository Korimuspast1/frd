#!/usr/bin/env python3
"""
kvsc -- компилятор и плеер формата .kvs (Korium Vector Sequence).

Подкоманды:

  kvsc compile  src.json [-o out.kvs] [--codec zlib|gzip|lzma|raw] [--no-preview]
  kvsc info     file.kvs                 заголовок без распаковки
  kvsc inspect  file.kvs [--json]        человекочитаемая сводка по сцене
  kvsc render   file.kvs -o out.png [--frame N] [--size W]
  kvsc export   file.kvs -o out.gif|out.apng|dir/ [--fmt gif|apng|png]
                          [--fps N] [--size W] [--every N] [--ss N]
  kvsc dump     file.kvs [-o scene.json] компактная сцена как JSON
  kvsc strip    file.kvs -o strip.png    «плёнка» из кадров для быстрого просмотра
  kvsc codecs                             список доступных кодеков сжатия

Примеры:
  kvsc compile examples/src/heart.json -o /tmp/heart.kvs
  kvsc render  examples/heart.kvs -o /tmp/f.png --frame 22
  kvsc export  examples/heart.kvs -o /tmp/heart.gif --every 2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import kvs                                            # noqa: E402
from kvs.container import CODEC_NAMES                 # noqa: E402
from kvs.png import encode_png                        # noqa: E402
from kvs.renderer import resize                       # noqa: E402


def _renderer(args, ss: int = 4) -> kvs.Renderer:
    return kvs.load(args.file, ss=args.ss if hasattr(args, "ss") and args.ss else ss)


def cmd_compile(args) -> int:
    t0 = time.time()
    blob = kvs.compile_file(args.src, codec=args.codec, preview=not args.no_preview,
                            out=args.out)
    info = kvs.read_header(args.out)
    print(f"{args.src} -> {args.out}")
    print(f"  кодек {info['codec']}, {info['width']}x{info['height']}, "
          f"{info['frames']} кадров @ {info['fps']:g} fps, "
          f"тело {info['payload_size']} Б, файл {len(blob)} Б "
          f"({time.time() - t0:.2f} c)")
    return 0


def cmd_info(args) -> int:
    h = kvs.read_header(args.file)
    print(f"{args.file}: .kvs v{h['version']}")
    for k, v in h.items():
        print(f"  {k:14s} {v}")
    return 0


def cmd_inspect(args) -> int:
    f = kvs.open_kvs(args.file)
    if args.json:
        print(json.dumps(kvs.decode_scene(f.scene), ensure_ascii=False, indent=2))
        return 0
    st = f.stats()
    print(f"{args.file} -- {f.scene.get('nm', '(без имени)')}")
    print(f"  автор/генератор : {f.scene.get('au', '-')} / {f.scene.get('gn', '-')}")
    print(f"  холст           : {st['width']}x{st['height']} px, "
          f"{st['frames']} кадров @ {st['fps']:g} fps ({st['duration_s']:.2f} c)")
    print(f"  сжатие          : {st['codec']}, {st['payload_raw_bytes']} -> "
          f"{st['file_bytes']} Б (x{st['compression_ratio']})")
    print(f"  превью в файле  : {'да' if st['has_preview'] else 'нет'}")
    print(f"  слоёв           : {st['layers']}, ассетов: {st['assets']}")
    r = kvs.Renderer(f.scene)
    for rep in r.layer_report():
        anim = ", ".join(rep["animated"])
        print(f"    [{rep['index']:>2}] {str(rep['name'])[:22]:22s} "
              f"{rep['geometry']:10s} fill={rep['fill']} stroke={rep['stroke']} "
              f"blend={rep['blend']:8s} аним: {anim}")
    return 0


def cmd_render(args) -> int:
    r = _renderer(args)
    frame = args.frame if args.frame is not None else 0
    fb = r.render(float(frame))
    if args.size and args.size != fb.w:
        fb = resize(fb, args.size, max(1, round(args.size * fb.h / fb.w)))
    with open(args.out, "wb") as fh:
        fh.write(encode_png(fb.w, fb.h, fb.px))
    print(f"кадр {frame} -> {args.out} ({fb.w}x{fb.h})")
    return 0


def cmd_export(args) -> int:
    fmt = args.fmt
    if fmt is None:
        ext = os.path.splitext(args.out)[1].lower()
        fmt = {"gif": "gif", ".apng": "apng", ".png": "apng"}.get(ext,
              "png" if not ext or os.path.sep in args.out or args.out.endswith("/") else "apng")
        if ext == ".png" and not args.out.endswith(("/", os.sep)):
            fmt = "apng"
    r = _renderer(args)
    every = args.every or 1
    frames = list(range(0, r.frames, every))
    fps = args.fps or (r.fps / every)
    t0 = time.time()
    kvs.export(args.file, args.out, fmt=fmt, ss=args.ss, fps=fps,
               size=args.size, frames=frames)
    n = len(frames) if fmt == "png" else 1
    print(f"{args.file} -> {args.out} [{fmt}, {len(frames)} кадров, "
          f"{time.time() - t0:.1f} c]")
    return 0


def cmd_dump(args) -> int:
    f = kvs.open_kvs(args.file)
    text = json.dumps(f.scene, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"сцена -> {args.out}")
    else:
        print(text)
    return 0


def cmd_strip(args) -> int:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from strip import strip
    strip(args.file, args.out, count=args.count, ss=args.ss)
    return 0


def cmd_codecs(args) -> int:
    print("кодеки сжатия тела .kvs:")
    for cid, name in CODEC_NAMES.items():
        print(f"  {cid} = {name}")
    from kvs.scene import easing_names
    print("easing-кривые:", ", ".join(easing_names()))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="kvsc", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("compile", help="авторинг-JSON -> .kvs")
    sp.add_argument("src")
    sp.add_argument("-o", "--out", required=True)
    sp.add_argument("--codec", default="zlib", choices=sorted(CODEC_NAMES.values()))
    sp.add_argument("--no-preview", action="store_true")
    sp.set_defaults(fn=cmd_compile)

    sp = sub.add_parser("info", help="заголовок файла")
    sp.add_argument("file")
    sp.set_defaults(fn=cmd_info)

    sp = sub.add_parser("inspect", help="сводка по сцене")
    sp.add_argument("file")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(fn=cmd_inspect)

    sp = sub.add_parser("render", help="один кадр -> PNG")
    sp.add_argument("file")
    sp.add_argument("-o", "--out", required=True)
    sp.add_argument("--frame", type=float, default=0)
    sp.add_argument("--size", type=int, default=0)
    sp.add_argument("--ss", type=int, default=4)
    sp.set_defaults(fn=cmd_render)

    sp = sub.add_parser("export", help="анимация -> gif/apng/png-секвенция")
    sp.add_argument("file")
    sp.add_argument("-o", "--out", required=True)
    sp.add_argument("--fmt", choices=["gif", "apng", "png"])
    sp.add_argument("--fps", type=float)
    sp.add_argument("--size", type=int, default=0)
    sp.add_argument("--every", type=int, default=1)
    sp.add_argument("--ss", type=int, default=3)
    sp.set_defaults(fn=cmd_export)

    sp = sub.add_parser("dump", help="компактная сцена -> JSON")
    sp.add_argument("file")
    sp.add_argument("-o", "--out")
    sp.set_defaults(fn=cmd_dump)

    sp = sub.add_parser("strip", help="плёнка кадров -> PNG")
    sp.add_argument("file")
    sp.add_argument("-o", "--out", required=True)
    sp.add_argument("--count", type=int, default=6)
    sp.add_argument("--ss", type=int, default=3)
    sp.set_defaults(fn=cmd_strip)

    sp = sub.add_parser("codecs", help="кодеки и easing-кривые")
    sp.set_defaults(fn=cmd_codecs)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
