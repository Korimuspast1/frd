"""
KVS -- Korium Vector Sequence.

Собственный контейнер векторной анимации (аналог .tgs) + движок,
который сам расшифровывает файл и выдаёт картинку.

Быстрый старт:

    import kvs

    # 1. собрать файл из авторинг-JSON
    blob = kvs.compile_file("heart.kvs.json", out="heart.kvs")

    # 2. расшифровать и нарисовать кадр
    r = kvs.load("heart.kvs")
    fb = r.render(0)                  # Framebuffer (RGBA)
    kvs.write_png("frame.png", fb)    # картинка на диске

    # 3. экспортировать всю анимацию
    kvs.export("heart.kvs", "out/", fmt="png")     # секвенция
    kvs.export("heart.kvs", "heart.gif", fmt="gif")
    kvs.export("heart.kvs", "heart.png", fmt="apng")
"""

from __future__ import annotations

import io
import json
import os

from . import container, geometry, paint, raster, scene
from .container import (CODEC_NAMES, KvsError, KvsFile, decode, encode, open_kvs,
                        read_header, save_kvs)
from .raster import Framebuffer
from .renderer import Renderer, RenderError, downscale, resize
from .scene import compile_scene, decode_scene, easing_names, eval_channel

FORMAT_NAME = "Korium Vector Sequence"
EXTENSION = ".kvs"
__version__ = "1.0.0"

__all__ = [
    "FORMAT_NAME", "EXTENSION", "__version__",
    "KvsFile", "KvsError", "Renderer", "RenderError", "Framebuffer",
    "encode", "decode", "open_kvs", "save_kvs", "read_header", "load", "save",
    "compile_scene", "decode_scene", "compile_file", "compile_dict",
    "load_json", "dump_json",
    "easing_names", "eval_channel", "downscale", "resize",
    "export", "render_frames", "write_png", "make_preview",
    "container", "geometry", "paint", "raster", "scene",
]


# --------------------------------------------------------------------------- #
#  высокоуровневый API
# --------------------------------------------------------------------------- #
def load(path: str, ss: int = 4) -> Renderer:
    """Открыть .kvs и вернуть готовый к работе движок (рендерер)."""
    return Renderer(open_kvs(path).scene, ss=ss)


def compile_dict(doc: dict, *, codec: str = "zlib", preview: bool = True,
                 out: str | None = None, ss: int = 3) -> bytes:
    """Авторинг-словарь -> байты .kvs (с компиляцией в компактную сцену)."""
    compact = compile_scene(doc)
    prev = None
    if preview:
        try:
            prev = make_preview(compact, size=64, ss=ss)
        except Exception:
            prev = None
    blob = encode(compact, codec=codec, preview=prev)
    if out:
        save_kvs(out, blob)
    return blob


def compile_file(path: str, *, out: str | None = None, codec: str = "zlib",
                 preview: bool = True) -> bytes:
    """Авторинг-JSON (.kvs.json) -> .kvs."""
    return compile_dict(load_json(path), codec=codec, preview=preview, out=out)


def load_json(path: str) -> dict:
    with io.open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path: str, data: dict) -> str:
    with io.open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return path


def save(path: str, blob: bytes) -> str:
    save_kvs(path, blob)
    return path


def write_png(path: str, fb: Framebuffer) -> str:
    from .png import encode_png
    with io.open(path, "wb") as fh:
        fh.write(encode_png(fb.w, fb.h, fb.px))
    return path


def make_preview(scene_or_doc, size: int = 64, ss: int = 3) -> bytes:
    """PNG-превью первого кадра (вкладывается в контейнер)."""
    from .png import encode_png
    compact = scene_or_doc if "c" in scene_or_doc and "l" in scene_or_doc \
        else compile_scene(scene_or_doc)
    r = Renderer(compact, ss=ss)
    fb = r.render(0)
    if fb.w == 0 or fb.h == 0:
        raise RenderError("пустой холст")
    small = resize(fb, max(1, size), max(1, round(size * fb.h / fb.w)))
    return encode_png(small.w, small.h, small.px)


def render_frames(path_or_scene, frames=None, ss: int = 4, size: int | None = None):
    """Генератор (index, Framebuffer) по кадрам анимации."""
    r = path_or_scene if isinstance(path_or_scene, Renderer) else load(path_or_scene, ss=ss)
    if frames is None:
        frames = range(r.frames)
    for i in frames:
        fb = r.render_index(int(i))
        if size and size != r.width:
            fb = resize(fb, size, max(1, round(size * r.height / r.width)))
        yield int(i), fb


def export(src: str, dest: str, *, fmt: str = "png", ss: int = 4, fps: float | None = None,
           size: int | None = None, frames=None, quality: int = 9) -> str:
    """
    Экспорт анимации:
      fmt="png"  -- секвенция dest/frame_0000.png ...
      fmt="apng" -- один анимированный PNG
      fmt="gif"  -- анимированный GIF (256 цветов, палитра по первому кадру)
    """
    from .anim import write_apng, write_gif
    if fmt == "png":
        os.makedirs(dest, exist_ok=True)
        from .png import encode_png
        for i, fb in render_frames(src, frames=frames, ss=ss, size=size):
            with io.open(os.path.join(dest, f"frame_{i:04d}.png"), "wb") as fh:
                fh.write(encode_png(fb.w, fb.h, fb.px, level=quality))
        return dest
    if fmt == "apng":
        write_apng(dest, list(render_frames(src, frames=frames, ss=ss, size=size)),
                   fps=fps, level=quality)
        return dest
    if fmt == "gif":
        write_gif(dest, list(render_frames(src, frames=frames, ss=ss, size=size)),
                  fps=fps)
        return dest
    raise ValueError(f"неизвестный формат экспорта: {fmt!r}")
