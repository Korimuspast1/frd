#!/usr/bin/env python3
"""
Тесты движка KVS: контейнер, сцена, геометрия, растеризатор, рендер, экспорт
и согласованность Python- и JS-движков.

Запуск:  python3 -m unittest discover -s tests -v   (или просто python3 tests/test_engine.py)
"""

from __future__ import annotations

import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import kvs                                            # noqa: E402
import kvs.api as K                                   # noqa: E402
from kvs import container, geometry as G, raster, scene  # noqa: E402
from kvs.renderer import Renderer                     # noqa: E402


def sample_doc():
    doc = K.animation("unit", 64, 64, fps=30, frames=12, background="#101010")
    K.linear_gradient(doc, "g", ["#ff0000", "#0000ff"], angle=0, normalized=True)
    K.layer(doc, "bg", K.rect([32, 32], [64, 64]), fill=K.fill("#223344"))
    K.layer(doc, "disc", K.circle([32, 32], K.keys([(0, 6), (12, 24)])),
            fill=K.fill(gradient="g"),
            stroke=K.stroke("#ffffff", K.keys([(0, 1), (12, 3)]), dash=[4, 3]),
            transform=K.transform(position=K.keys([(0, [10, 32]), (12, [54, 32])],
                                                  easing="out-bounce"),
                                  rotation=K.keys([(0, 0), (12, 180)]),
                                  opacity=K.keys([(0, 0.2), (12, 1.0)])))
    K.layer(doc, "morph", K.morph([
        (0, [[[10, 10], [50, 10], [50, 50], [10, 50]]]),
        (12, [[[10, 50], [50, 50], [50, 10], [10, 10]]]),
    ]), fill=K.fill("#00ff88", opacity=0.5))
    return doc


class TestContainer(unittest.TestCase):
    def setUp(self):
        self.scene = K.compile_scene(sample_doc())

    def test_roundtrip_all_codecs(self):
        for codec in ("raw", "zlib", "gzip", "lzma"):
            blob = container.encode(self.scene, codec=codec)
            f = container.decode(blob)
            self.assertEqual(f.scene, self.scene, codec)
            self.assertEqual(f.codec, codec)
            self.assertEqual((f.width, f.height), (64, 64))
            self.assertAlmostEqual(f.fps, 30.0)

    def test_magic_and_header(self):
        blob = container.encode(self.scene)
        self.assertEqual(blob[:4], b"KVS\x1e")
        h = container.read_header(self._tmp(blob))
        self.assertEqual(h["width"], 64)
        self.assertEqual(h["frames"], 12)

    def test_crc_detects_corruption(self):
        blob = bytearray(container.encode(self.scene))
        blob[40] ^= 0xFF
        with self.assertRaises(container.KvsError):
            container.decode(bytes(blob))

    def test_bad_magic(self):
        with self.assertRaises(container.KvsError):
            container.decode(b"NOPE" + b"\x00" * 64)

    def test_preview_embedded(self):
        blob = kvs.compile_dict(sample_doc(), preview=True, ss=2)
        f = container.decode(blob)
        self.assertIsNotNone(f.preview)
        self.assertEqual(f.preview[:8], b"\x89PNG\r\n\x1a\n")

    def _tmp(self, blob):
        fd, path = tempfile.mkstemp(suffix=".kvs")
        os.write(fd, blob)
        os.close(fd)
        self.addCleanup(os.remove, path)
        return path


class TestScene(unittest.TestCase):
    def test_easing_bounds(self):
        for name in scene.easing_names():
            if name == "hold":      # hold по определению держит значение до следующего ключа
                continue
            fn = scene.EASINGS[name]
            self.assertAlmostEqual(fn(0.0), 0.0, delta=1e-9, msg=name)
            self.assertAlmostEqual(fn(1.0), 1.0, delta=1e-9, msg=name)

    def test_eval_channel(self):
        ch = {"k": [[0, 0], [10, 100, "linear"]]}
        self.assertEqual(scene.eval_channel(ch, 0), 0)
        self.assertEqual(scene.eval_channel(ch, 5), 50)
        self.assertEqual(scene.eval_channel(ch, 99), 100)
        hold = {"k": [[0, 7, "hold"], [5, 9]]}
        self.assertEqual(scene.eval_channel(hold, 4.9), 7)

    def test_morph_shape_validation(self):
        with self.assertRaises(ValueError):
            K.morph([(0, [[[0, 0], [1, 1]]]), (5, [[[0, 0], [1, 1], [2, 2]]])])

    def test_colors(self):
        self.assertEqual(scene.parse_color("#f0a"), (255, 0, 170, 255))
        self.assertEqual(scene.parse_color("#11223344"), (0x11, 0x22, 0x33, 0x44))
        self.assertEqual(scene.parse_color([1, 2, 3]), (1, 2, 3, 255))


class TestGeometry(unittest.TestCase):
    def test_stroke_outline_is_closed_and_bounded(self):
        poly = G.stroke_outline([(0, 0), (100, 0)], False, 10, "round", "round")[0]
        pts, closed = poly
        self.assertTrue(closed)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        self.assertLess(min(xs), -4)     # round cap выступает за конец
        self.assertGreater(max(xs), 104)
        self.assertAlmostEqual(min(ys), -5, delta=0.3)
        self.assertAlmostEqual(max(ys), 5, delta=0.3)

    def test_miter_square(self):
        ring = G.stroke_outline([(0, 0), (100, 0), (100, 100), (0, 100)], True,
                                8, "butt", "miter")[0][0]
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        self.assertAlmostEqual(min(xs), -4, delta=1e-6)
        self.assertAlmostEqual(max(xs), 104, delta=1e-6)
        self.assertAlmostEqual(min(ys), -4, delta=1e-6)

    def test_dash_pattern(self):
        segs = G.dash_polyline([(0, 0), (100, 0)], [10, 10])
        self.assertEqual(len(segs), 5)
        self.assertAlmostEqual(segs[0][1][0], 10)
        self.assertAlmostEqual(segs[1][0][0], 20)

    def test_star_and_polygon(self):
        self.assertEqual(len(G.star_path(0, 0, 10, 4, 5)[0][0]), 10)
        self.assertEqual(len(G.polygon_path(0, 0, 10, 6)[0][0]), 6)

    def test_roundrect(self):
        pts = G.rect_path(0, 0, 40, 20, 6)[0][0]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        self.assertAlmostEqual(min(xs), -20, delta=0.2)
        self.assertAlmostEqual(max(ys), 10, delta=0.2)


class TestRaster(unittest.TestCase):
    def test_full_coverage_inside(self):
        cov, x0, y0, x1, y1 = raster.coverage(G.rect_path(20, 20, 20, 20, 0), 40, 40, ss=4)
        self.assertEqual(cov[(20 - y0) * (x1 - x0) + (20 - x0)], 255)

    def test_antialiased_edge(self):
        cov, x0, y0, x1, y1 = raster.coverage(G.ellipse_path(20, 20, 15, 15), 40, 40, ss=4)
        rw = x1 - x0
        edge = cov[(20 - y0) * rw + (5 - x0)]
        self.assertGreater(edge, 0)
        self.assertLess(edge, 255)

    def test_evenodd_hole(self):
        outer = G.rect_path(20, 20, 30, 30, 0)[0]
        inner = G.rect_path(20, 20, 10, 10, 0)[0]
        cov, x0, y0, x1, y1 = raster.coverage([outer, inner], 40, 40, ss=4, rule="evenodd")
        rw = x1 - x0
        self.assertEqual(cov[(20 - y0) * rw + (20 - x0)], 0)      # дырка
        self.assertEqual(cov[(8 - y0) * rw + (20 - x0)], 255)     # рамка


class TestRender(unittest.TestCase):
    def setUp(self):
        self.doc = sample_doc()
        self.renderer = Renderer(K.compile_scene(self.doc))

    def test_render_all_frames(self):
        for i in range(self.renderer.frames):
            fb = self.renderer.render_index(i)
            self.assertEqual((fb.w, fb.h), (64, 64))

    def test_background_and_opacity(self):
        fb = self.renderer.render(0)
        self.assertEqual(fb.get(1, 1), (0x22, 0x33, 0x44, 255))   # фон слоя bg
        # слой morph с opacity 0.5 поверх фона -> не чистый #00ff88
        px = fb.get(30, 30)
        self.assertNotEqual(px[:3], (0, 255, 136))

    def test_layer_order(self):
        doc = K.animation("order", 16, 16, fps=10, frames=1)
        K.layer(doc, "red", K.rect([8, 8], [16, 16]), fill="#ff0000")
        K.layer(doc, "blue", K.rect([8, 8], [8, 16]), fill="#0000ff")
        fb = Renderer(K.compile_scene(doc)).render(0)
        self.assertEqual(fb.get(8, 8)[:3], (0, 0, 255))

    def test_blend_add(self):
        doc = K.animation("add", 16, 16, fps=10, frames=1)
        K.layer(doc, "a", K.rect([8, 8], [16, 16]), fill="#800000")
        K.layer(doc, "b", K.rect([8, 8], [16, 16]), fill="#008000", blend="add")
        fb = Renderer(K.compile_scene(doc)).render(0)
        self.assertEqual(fb.get(8, 8)[:3], (128, 128, 0))

    def test_parent_hierarchy(self):
        doc = K.animation("parent", 64, 64, fps=10, frames=4)
        K.layer(doc, "pivot", K.circle([32, 32], 1),
                transform=K.transform(anchor=[32, 32], position=[32, 32],
                                      rotation=K.keys([(0, 0), (4, 90)])),
                hidden=True)
        parent_idx = 0
        K.layer(doc, "sat", K.circle([52, 32], 4), fill="#ffffff", parent=parent_idx)
        fb = Renderer(K.compile_scene(doc)).render(4)
        # после поворота на 90° спутник должен оказаться около (32, 52)
        self.assertEqual(fb.get(32, 52)[3], 255)
        self.assertEqual(fb.get(52, 32)[3], 0)


class TestExport(unittest.TestCase):
    def test_exports(self):
        path = os.path.join(ROOT, "examples", "spinner.kvs")
        if not os.path.exists(path):
            self.skipTest("примеры не собраны")
        with tempfile.TemporaryDirectory() as td:
            gif = os.path.join(td, "a.gif")
            kvs.export(path, gif, fmt="gif", ss=2, frames=range(0, 20, 4))
            with open(gif, "rb") as fh:
                head = fh.read(6)
            self.assertEqual(head, b"GIF89a")
            apng = os.path.join(td, "a.png")
            kvs.export(path, apng, fmt="apng", ss=2, frames=range(0, 20, 4))
            with open(apng, "rb") as fh:
                data = fh.read()
            self.assertIn(b"acTL", data)
            self.assertIn(b"fcTL", data)
            self.assertIn(b"fdAT", data)


@unittest.skipUnless(_node_ok := subprocess.run(["node", "-v"], capture_output=True).returncode == 0,
                     "node недоступен")
class TestCrossEngine(unittest.TestCase):
    """Python- и JS-движки обязаны одинаково вычислять каналы и трансформы."""

    def test_eval_parity(self):
        script = os.path.join(ROOT, "tests", "parity.js")
        doc = K.compile_scene(sample_doc())
        payload = json.dumps({"scene": doc, "times": [0, 3.5, 7, 11.99]})
        res = subprocess.run(["node", script], input=payload, capture_output=True,
                             text=True, cwd=ROOT)
        self.assertEqual(res.returncode, 0, res.stderr)
        js = json.loads(res.stdout)
        for t, channels in js.items():
            for path, value in channels.items():
                node = doc
                for key in path.split("."):
                    node = node[int(key)] if key.isdigit() else node[key]
                py = scene.eval_channel(node, float(t))
                if isinstance(py, (int, float)):
                    self.assertAlmostEqual(py, value, delta=1e-6, msg=(t, path))
                elif isinstance(py, list):
                    for a, b in zip(py, value):
                        self.assertAlmostEqual(a, b, delta=1e-6, msg=(t, path))


@unittest.skipUnless(subprocess.run(["node", "-v"], capture_output=True).returncode == 0,
                     "node недоступен")
class TestJsEngine(unittest.TestCase):
    """Веб-движок обязан без ошибок отрисовать каждый пример (мок-канвас)."""

    def test_smoke_all_examples(self):
        script = os.path.join(ROOT, "tests", "js_smoke.js")
        res = subprocess.run(["node", script], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(res.returncode, 0, res.stderr)
        report = json.loads(res.stdout)
        self.assertTrue(report, "нет примеров для проверки")
        for name, rep in report.items():
            self.assertIsNone(rep["errors"], f"{name}: {rep['errors']}")
            self.assertGreater(rep["fills"] + rep["strokes"], 0, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
