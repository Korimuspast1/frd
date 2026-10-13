"""
KVS container -- бинарная оболочка формата .kvs (Korium Vector Sequence).

Раскладка файла (всё little-endian):

    offset  size  field
    0       4     magic      = b"KVS\\x1E"   (0x4B 0x56 0x53 0x1E)
    4       1     version    = 1
    5       1     flags      bit0-2 : codec (0=raw 1=zlib 2=gzip 3=lzma 4=brotli)
                             bit3   : 1 = в конце файла есть PNG-превью
                             bit4-7 : зарезервировано (0)
    6       2     reserved   = 0
    8       2     width      px
    10      2     height     px
    12      2     fps        Q8.8 fixed point (fps * 256)
    14      2     frames     количество кадров
    16      4     payload_size   размер сжатого тела в байтах
    20      4     payload_crc32  CRC-32 от *сжатого* тела
    24      8     reserved   = 0
    32      N     payload    компактная JSON-сцена (см. docs/SCENE.md)
    32+N    M     preview    PNG-превью (только если flags bit3)

Итого фиксированный заголовок -- 32 байта.
"""

from __future__ import annotations

import gzip
import json
import lzma
import struct
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict

MAGIC = b"KVS\x1e"
VERSION = 1
HEADER_SIZE = 32

CODEC_NAMES = {0: "raw", 1: "zlib", 2: "gzip", 3: "lzma", 4: "brotli"}
CODEC_IDS = {v: k for k, v in CODEC_NAMES.items()}

FLAG_PREVIEW = 0x08

_HEADER = struct.Struct("<4sBBH HH HH II Q")
assert _HEADER.size == HEADER_SIZE, _HEADER.size


class KvsError(Exception):
    """Любая ошибка формата .kvs."""


@dataclass
class KvsFile:
    """Распакованный файл .kvs."""

    width: int
    height: int
    fps: float
    frames: int
    scene: Dict[str, Any]
    codec: str = "zlib"
    version: int = VERSION
    preview: bytes | None = None
    raw_size: int = 0
    file_size: int = 0

    @property
    def duration(self) -> float:
        return self.frames / self.fps if self.fps else 0.0

    def stats(self) -> Dict[str, Any]:
        ratio = (self.raw_size / self.file_size) if self.file_size else 0.0
        return {
            "version": self.version,
            "codec": self.codec,
            "width": self.width,
            "height": self.height,
            "fps": round(self.fps, 4),
            "frames": self.frames,
            "duration_s": round(self.duration, 4),
            "layers": len(self.scene.get("l", []) or []),
            "assets": len(self.scene.get("a", {}) or {}),
            "payload_raw_bytes": self.raw_size,
            "file_bytes": self.file_size,
            "compression_ratio": round(ratio, 3),
            "has_preview": self.preview is not None,
        }


# --------------------------------------------------------------------------- #
#  codecs
# --------------------------------------------------------------------------- #
def _compress(data: bytes, codec: str, level: int = 9) -> bytes:
    if codec == "raw":
        return data
    if codec == "zlib":
        return zlib.compress(data, level)
    if codec == "gzip":
        return gzip.compress(data, compresslevel=level)
    if codec == "lzma":
        return lzma.compress(data, preset=level | lzma.PRESET_EXTREME)
    if codec == "brotli":
        try:
            import brotli  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise KvsError("кодек brotli недоступен в этой системе") from exc
        return brotli.compress(data, quality=level)
    raise KvsError(f"неизвестный кодек: {codec}")


def _decompress(data: bytes, codec: str) -> bytes:
    if codec == "raw":
        return data
    if codec == "zlib":
        return zlib.decompress(data)
    if codec == "gzip":
        return gzip.decompress(data)
    if codec == "lzma":
        return lzma.decompress(data)
    if codec == "brotli":
        try:
            import brotli  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise KvsError("кодек brotli недоступен в этой системе") from exc
        return brotli.decompress(data)
    raise KvsError(f"неизвестный кодек: {codec}")


# --------------------------------------------------------------------------- #
#  encode / decode
# --------------------------------------------------------------------------- #
def encode(
    scene: Dict[str, Any],
    *,
    width: int | None = None,
    height: int | None = None,
    fps: float | None = None,
    frames: int | None = None,
    codec: str = "zlib",
    preview: bytes | None = None,
) -> bytes:
    """Собрать .kvs из компактной сцены (dict)."""
    canvas = scene.get("c") or {}
    width = width if width is not None else int(canvas.get("w", 0))
    height = height if height is not None else int(canvas.get("h", 0))
    fps = fps if fps is not None else float(canvas.get("r", 0))
    frames = frames if frames is not None else int(canvas.get("n", 0))

    if not (0 < width <= 0xFFFF and 0 < height <= 0xFFFF):
        raise KvsError("размер холста должен быть в диапазоне 1..65535 px")
    if not (0 < fps < 256):
        raise KvsError("fps должен быть в диапазоне (0, 256)")
    if not (0 < frames <= 0xFFFF):
        raise KvsError("число кадров должно быть в диапазоне 1..65535")
    if codec not in CODEC_IDS:
        raise KvsError(f"неизвестный кодек: {codec}")

    body = json.dumps(scene, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    payload = _compress(body, codec)
    if len(payload) > 0xFFFFFFFF:
        raise KvsError("тело файла больше 4 GiB")

    flags = CODEC_IDS[codec]
    if preview:
        flags |= FLAG_PREVIEW

    head = _HEADER.pack(
        MAGIC,
        VERSION,
        flags,
        0,
        width,
        height,
        int(round(fps * 256)),
        frames,
        len(payload),
        zlib.crc32(payload) & 0xFFFFFFFF,
        0,
    )
    out = bytearray(head)
    out += payload
    if preview:
        out += preview
    return bytes(out)


def decode(data: bytes, *, strict_crc: bool = True) -> KvsFile:
    """Разобрать .kvs и вернуть KvsFile (полностью в памяти)."""
    if len(data) < HEADER_SIZE:
        raise KvsError("файл короче 32-байтного заголовка")
    (
        magic,
        version,
        flags,
        _res0,
        width,
        height,
        fps_q8,
        frames,
        payload_size,
        crc,
        _res1,
    ) = _HEADER.unpack_from(data, 0)

    if magic != MAGIC:
        raise KvsError(
            "это не .kvs (ожидалась сигнатура KVS\\x1E, получено %r)" % magic[:4]
        )
    if version > VERSION:
        raise KvsError(f"версия {version} новее поддерживаемой {VERSION}")

    codec_id = flags & 0x07
    codec = CODEC_NAMES.get(codec_id)
    if codec is None:
        raise KvsError(f"неизвестный кодек id={codec_id}")

    end = HEADER_SIZE + payload_size
    if end > len(data):
        raise KvsError("обрезанный файл: тела не хватает")
    payload = data[HEADER_SIZE:end]

    if strict_crc and (zlib.crc32(payload) & 0xFFFFFFFF) != crc:
        raise KvsError("CRC-32 тела не совпал -- файл повреждён")

    preview = None
    if flags & FLAG_PREVIEW:
        preview = data[end:] or None

    try:
        body = _decompress(payload, codec)
    except Exception as exc:
        raise KvsError(f"не удалось распаковать тело ({codec}): {exc}") from exc

    try:
        scene = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise KvsError(f"тело не является валидным JSON: {exc}") from exc

    if not isinstance(scene, dict):
        raise KvsError("сцена должна быть JSON-объектом")

    return KvsFile(
        width=width,
        height=height,
        fps=fps_q8 / 256.0,
        frames=frames,
        scene=scene,
        codec=codec,
        version=version,
        preview=preview,
        raw_size=len(body),
        file_size=len(data),
    )


def open_kvs(path: str, **kw) -> KvsFile:
    with open(path, "rb") as fh:
        return decode(fh.read(), **kw)


def save_kvs(path: str, blob: bytes) -> None:
    with open(path, "wb") as fh:
        fh.write(blob)


def read_header(path: str) -> Dict[str, Any]:
    """Быстрое чтение заголовка без распаковки тела (для превью в файловых менеджерах)."""
    with open(path, "rb") as fh:
        head = fh.read(HEADER_SIZE)
    if len(head) < HEADER_SIZE:
        raise KvsError("файл короче заголовка")
    magic, version, flags, _r0, w, h, fps_q8, frames, psize, crc, _r1 = _HEADER.unpack(head)
    if magic != MAGIC:
        raise KvsError("это не .kvs")
    return {
        "version": version,
        "codec": CODEC_NAMES.get(flags & 0x07, "?"),
        "has_preview": bool(flags & FLAG_PREVIEW),
        "width": w,
        "height": h,
        "fps": fps_q8 / 256.0,
        "frames": frames,
        "payload_size": psize,
        "payload_crc32": crc,
    }
