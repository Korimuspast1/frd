/*
 * KVS Web Player -- браузерный декодер и движок рендера формата .kvs.
 *
 * Зеркалит Python-движок (kvs/): тот же контейнер, та же модель сцены,
 * те же easing-кривые и каналы ключевых кадров. Вместо собственного
 * растеризатора использует Canvas2D: кривые Безье отдаются нативному
 * Path2D, поэтому веб-версия ещё и точнее на мелких деталях.
 *
 * Никаких внешних библиотек: распаковка -- через DecompressionStream
 * (gzip/deflate/raw есть в браузере из коробки).
 */
(function (global) {
  "use strict";

  const MAGIC = [0x4b, 0x56, 0x53, 0x1e];
  const HEADER_SIZE = 32;
  const CODEC_NAMES = ["raw", "zlib", "gzip", "lzma", "brotli"];
  const FLAG_PREVIEW = 0x08;

  // --------------------------------------------------------------------- //
  //  easing
  // --------------------------------------------------------------------- //
  function cubicBezier(p1x, p1y, p2x, p2y) {
    const cx = 3 * p1x, bx = 3 * (p2x - p1x) - cx, ax = 1 - cx - bx;
    const cy = 3 * p1y, by = 3 * (p2y - p1y) - cy, ay = 1 - cy - by;
    const sx = (t) => ((ax * t + bx) * t + cx) * t;
    const sy = (t) => ((ay * t + by) * t + cy) * t;
    const dx = (t) => (3 * ax * t + 2 * bx) * t + cx;
    return function (x) {
      if (x <= 0) return 0;
      if (x >= 1) return 1;
      let t = x;
      for (let i = 0; i < 8; i++) {
        const err = sx(t) - x;
        if (Math.abs(err) < 1e-6) return sy(t);
        const d = dx(t);
        if (Math.abs(d) < 1e-9) break;
        t -= err / d;
      }
      let lo = 0, hi = 1;
      t = x;
      for (let i = 0; i < 32; i++) {
        const v = sx(t);
        if (Math.abs(v - x) < 1e-6) break;
        if (v < x) lo = t; else hi = t;
        t = (lo + hi) / 2;
      }
      return sy(t);
    };
  }

  function bounceOut(t) {
    const n1 = 7.5625, d1 = 2.75;
    if (t < 1 / d1) return n1 * t * t;
    if (t < 2 / d1) return n1 * (t -= 1.5 / d1) * t + 0.75;
    if (t < 2.5 / d1) return n1 * (t -= 2.25 / d1) * t + 0.9375;
    return n1 * (t -= 2.625 / d1) * t + 0.984375;
  }

  const EASINGS = {
    "linear": (t) => t,
    "hold": () => 0,
    "step": (t) => (t < 1 ? 0 : 1),
    "in-quad": (t) => t * t,
    "out-quad": (t) => t * (2 - t),
    "in-out-quad": (t) => (t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t),
    "in-cubic": (t) => t ** 3,
    "out-cubic": (t) => 1 - (1 - t) ** 3,
    "in-out-cubic": (t) => (t < 0.5 ? 4 * t ** 3 : 1 - (-2 * t + 2) ** 3 / 2),
    "in-quart": (t) => t ** 4,
    "out-quart": (t) => 1 - (1 - t) ** 4,
    "in-out-quart": (t) => (t < 0.5 ? 8 * t ** 4 : 1 - (-2 * t + 2) ** 4 / 2),
    "in-quint": (t) => t ** 5,
    "out-quint": (t) => 1 - (1 - t) ** 5,
    "in-sine": (t) => 1 - Math.cos((t * Math.PI) / 2),
    "out-sine": (t) => Math.sin((t * Math.PI) / 2),
    "in-out-sine": (t) => -(Math.cos(Math.PI * t) - 1) / 2,
    "in-expo": (t) => (t === 0 ? 0 : 2 ** (10 * t - 10)),
    "out-expo": (t) => (t >= 1 ? 1 : 1 - 2 ** (-10 * t)),
    "in-out-expo": (t) => t === 0 ? 0 : t >= 1 ? 1 : t < 0.5 ? 2 ** (20 * t - 10) / 2 : (2 - 2 ** (-20 * t + 10)) / 2,
    "in-circ": (t) => 1 - Math.sqrt(Math.max(0, 1 - t * t)),
    "out-circ": (t) => Math.sqrt(Math.max(0, 1 - (t - 1) ** 2)),
    "in-out-circ": (t) => t < 0.5 ? (1 - Math.sqrt(Math.max(0, 1 - 4 * t * t))) / 2 : (Math.sqrt(Math.max(0, 1 - (-2 * t + 2) ** 2)) + 1) / 2,
    "in-back": (t) => 2.70158 * t ** 3 - 1.70158 * t ** 2,
    "out-back": (t) => 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2,
    "in-out-back": (t) => t < 0.5 ? (8 * t * t * ((2.5949095 + 1) * 2 * t - 2.5949095)) / 2 : ((2 * t - 2) ** 2 * ((2.5949095 + 1) * (2 * t - 2) + 2.5949095) + 2) / 2,
    "in-elastic": (t) => t === 0 ? 0 : t >= 1 ? 1 : -(2 ** (10 * t - 10)) * Math.sin(((t * 10 - 10.75) * 2 * Math.PI) / 3),
    "out-elastic": (t) => t === 0 ? 0 : t >= 1 ? 1 : 2 ** (-10 * t) * Math.sin(((t * 10 - 0.75) * 2 * Math.PI) / 3) + 1,
    "out-bounce": bounceOut,
    "in-bounce": (t) => 1 - bounceOut(1 - t),
    "in-out-bounce": (t) => (t < 0.5 ? (1 - bounceOut(1 - 2 * t)) / 2 : (1 + bounceOut(2 * t - 1)) / 2),
    "ease": cubicBezier(0.25, 0.1, 0.25, 1.0),
    "ease-in": cubicBezier(0.42, 0, 1, 1),
    "ease-out": cubicBezier(0, 0, 0.58, 1),
    "ease-in-out": cubicBezier(0.42, 0, 0.58, 1),
  };
  const EASING_IDS = Object.keys(EASINGS).sort();

  function easingBySpec(spec) {
    if (spec == null) return EASINGS.linear;
    if (typeof spec === "number") return EASINGS[EASING_IDS[((spec % EASING_IDS.length) + EASING_IDS.length) % EASING_IDS.length]];
    if (typeof spec === "string") return EASINGS[spec] || EASINGS.linear;
    if (Array.isArray(spec) && spec.length === 4) return cubicBezier(...spec);
    return EASINGS.linear;
  }

  // --------------------------------------------------------------------- //
  //  цвета / каналы
  // --------------------------------------------------------------------- //
  function parseColor(c) {
    if (typeof c === "string") {
      let s = c.trim().replace(/^#/, "");
      if (s.length === 3 || s.length === 4) s = s.split("").map((ch) => ch + ch).join("");
      if (s.length === 6) s += "ff";
      return [parseInt(s.slice(0, 2), 16), parseInt(s.slice(2, 4), 16),
              parseInt(s.slice(4, 6), 16), parseInt(s.slice(6, 8), 16)];
    }
    if (Array.isArray(c)) {
      const v = c.slice();
      if (v.length === 3) v.push(255);
      return v.map((x) => Math.max(0, Math.min(255, Math.round(x))));
    }
    return [255, 255, 255, 255];
  }

  function cssColor(c) {
    const [r, g, b, a] = parseColor(c);
    return a >= 255 ? `rgb(${r},${g},${b})` : `rgba(${r},${g},${b},${(a / 255).toFixed(4)})`;
  }

  function mix(a, b, t) {
    if (typeof a === "boolean" || typeof b === "boolean") return t < 0.5 ? a : b;
    if (typeof a === "number" && typeof b === "number") return a + (b - a) * t;
    if (Array.isArray(a) && Array.isArray(b)) return a.map((v, i) => mix(v, b[i], t));
    if (typeof a === "string" && typeof b === "string") {
      const ca = parseColor(a), cb = parseColor(b);
      return `rgb(${ca.map((v, i) => Math.round(v + (cb[i] - v) * t)).slice(0, 3).join(",")})`;
    }
    return t < 0.5 ? a : b;
  }

  function isAnimated(ch) {
    return ch && typeof ch === "object" && !Array.isArray(ch) && Array.isArray(ch.k)
      && ch.k.length && Array.isArray(ch.k[0]);
  }

  function evalChannel(ch, time) {
    if (ch && typeof ch === "object" && !Array.isArray(ch)) {
      if ("k" in ch) {
        const keys = ch.k;
        if (!Array.isArray(keys[0])) return keys;
        if (time <= keys[0][0]) return keys[0][1];
        const last = keys[keys.length - 1];
        if (time >= last[0]) return last[1];
        for (let i = 0; i < keys.length - 1; i++) {
          const k0 = keys[i], k1 = keys[i + 1];
          if (k0[0] <= time && time <= k1[0]) {
            const span = k1[0] - k0[0];
            if (span <= 0) return k1[1];
            const e = easingBySpec(k0.length > 2 ? k0[2] : ch.e);
            return mix(k0[1], k1[1], e((time - k0[0]) / span));
          }
        }
        return last[1];
      }
      if ("v" in ch) return ch.v;
    }
    return ch;
  }

  // --------------------------------------------------------------------- //
  //  контейнер
  // --------------------------------------------------------------------- //
  async function inflate(data, format) {
    if (format === "raw") return data;
    if (format === "lzma" || format === "brotli") {
      throw new Error(`кодек ${format} не поддерживается браузерным плеером (используйте zlib/gzip)`);
    }
    const ds = new DecompressionStream(format === "zlib" ? "deflate" : "gzip");
    const stream = new Blob([data]).stream().pipeThrough(ds);
    const buf = await new Response(stream).arrayBuffer();
    return new Uint8Array(buf);
  }

  function crc32(bytes) {
    let table = crc32.table;
    if (!table) {
      table = crc32.table = new Int32Array(256);
      for (let i = 0; i < 256; i++) {
        let c = i;
        for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
        table[i] = c;
      }
    }
    let crc = -1;
    for (let i = 0; i < bytes.length; i++) crc = (crc >>> 8) ^ table[(crc ^ bytes[i]) & 0xff];
    return (crc ^ -1) >>> 0;
  }

  async function decode(bytes, opts) {
    opts = opts || {};
    if (bytes.length < HEADER_SIZE) throw new Error("файл короче 32-байтного заголовка");
    const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    for (let i = 0; i < 4; i++) {
      if (bytes[i] !== MAGIC[i]) throw new Error("это не .kvs (плохая сигнатура)");
    }
    const version = bytes[4];
    const flags = bytes[5];
    const codecId = flags & 0x07;
    const hasPreview = (flags & FLAG_PREVIEW) !== 0;
    if (version > 1) throw new Error("версия " + version + " новее поддерживаемой");
    const width = dv.getUint16(8, true);
    const height = dv.getUint16(10, true);
    const fps = dv.getUint16(12, true) / 256;
    const frames = dv.getUint16(14, true);
    const payloadSize = dv.getUint32(16, true);
    const crc = dv.getUint32(20, true);
    const payload = bytes.subarray(HEADER_SIZE, HEADER_SIZE + payloadSize);
    if (payload.length !== payloadSize) throw new Error("обрезанный файл");
    if (!opts.skipCrc && crc32(payload) !== crc) throw new Error("CRC-32 не совпал: файл повреждён");

    const codec = CODEC_NAMES[codecId] || "?";
    const raw = await inflate(payload, codec);
    const text = new TextDecoder().decode(raw);
    const scene = JSON.parse(text);
    const preview = hasPreview && bytes.length > HEADER_SIZE + payloadSize
      ? bytes.subarray(HEADER_SIZE + payloadSize) : null;
    return {
      version, codec, width, height, fps, frames, scene, preview,
      rawSize: raw.length, fileSize: bytes.length,
      duration: frames / fps,
    };
  }

  // --------------------------------------------------------------------- //
  //  геометрия -> Path2D
  // --------------------------------------------------------------------- //
  const CAPS = ["butt", "round", "square"];
  const JOINS = ["miter", "round", "bevel"];
  const BLENDS = { 0: "source-over", 1: "multiply", 2: "screen", 3: "overlay", 4: "lighter" };

  function subpathToPath2D(p2d, sp) {
    let items = sp.slice();
    let closed = true;
    if (items.length && typeof items[items.length - 1] === "number") {
      closed = items.pop() !== 0;
    }
    if (!items.length) return closed;
    const first = items[0];
    p2d.moveTo(first[0], first[1]);
    for (let i = 1; i < items.length; i++) {
      const v = items[i];
      if (v.length === 2) p2d.lineTo(v[0], v[1]);
      else if (v.length === 4) p2d.quadraticCurveTo(v[0], v[1], v[2], v[3]);
      else if (v.length === 6) p2d.bezierCurveTo(v[0], v[1], v[2], v[3], v[4], v[5]);
      else if (v.length === 8) p2d.bezierCurveTo(v[2], v[3], v[6], v[7], v[0], v[1]);
    }
    if (closed) p2d.closePath();
    return closed;
  }

  function geomPath(g, t) {
    const p2d = new Path2D();
    const kind = g.t;
    if (kind === "p") {
      const subs = isAnimated(g.s) ? evalChannel(g.s, t) : g.s;
      for (const sp of subs) subpathToPath2D(p2d, sp);
      return p2d;
    }
    if (kind === "r" || kind === "rr" || kind === "e") {
      const p = vec(evalChannel(g.p || [0, 0], t), 2);
      const z = vec(evalChannel(g.z, t), 2);
      const w = Math.abs(z[0]), h = Math.abs(z[1]);
      if (kind === "e") {
        p2d.ellipse(p[0], p[1], w / 2, h / 2, 0, 0, Math.PI * 2);
      } else if (kind === "rr") {
        const r = Math.max(0, Math.min(evalChannel(g.r, t), Math.min(w, h) / 2));
        roundRect(p2d, p[0] - w / 2, p[1] - h / 2, w, h, r);
      } else {
        p2d.rect(p[0] - w / 2, p[1] - h / 2, w, h);
      }
      return p2d;
    }
    if (kind === "ci") {
      const p = vec(evalChannel(g.p || [0, 0], t), 2);
      const r = Math.abs(evalChannel(g.r, t));
      p2d.ellipse(p[0], p[1], r, r, 0, 0, Math.PI * 2);
      return p2d;
    }
    if (kind === "pg") {
      const p = vec(evalChannel(g.p || [0, 0], t), 2);
      const n = Math.max(3, Math.round(evalChannel(g.n, t)));
      const r = Math.abs(evalChannel(g.r, t));
      const rot = (evalChannel(g.rot != null ? g.rot : -90, t) * Math.PI) / 180;
      for (let i = 0; i < n; i++) {
        const a = rot + (i * 2 * Math.PI) / n;
        const x = p[0] + r * Math.cos(a), y = p[1] + r * Math.sin(a);
        if (i === 0) p2d.moveTo(x, y); else p2d.lineTo(x, y);
      }
      p2d.closePath();
      return p2d;
    }
    if (kind === "st") {
      const p = vec(evalChannel(g.p || [0, 0], t), 2);
      const n = Math.max(2, Math.round(evalChannel(g.n, t)));
      const r1 = Math.abs(evalChannel(g.r1, t));
      const r2 = Math.abs(evalChannel(g.r2, t));
      const rot = (evalChannel(g.rot != null ? g.rot : -90, t) * Math.PI) / 180;
      const rd = evalChannel(g.rd || 0, t);
      const m = n * 2;
      const pts = [];
      for (let i = 0; i < m; i++) {
        const r = i % 2 === 0 ? r1 : r2;
        const a = rot + (i * 2 * Math.PI) / m;
        pts.push([p[0] + r * Math.cos(a), p[1] + r * Math.sin(a)]);
      }
      if (rd <= 0.001) {
        pts.forEach((q, i) => (i ? p2d.lineTo(q[0], q[1]) : p2d.moveTo(q[0], q[1])));
      } else {
        const tt = rd * 0.5;
        let first = null;
        for (let i = 0; i < m; i++) {
          const prev = pts[(i - 1 + m) % m], cur = pts[i], next = pts[(i + 1) % m];
          const a = [cur[0] + (prev[0] - cur[0]) * tt, cur[1] + (prev[1] - cur[1]) * tt];
          const b = [cur[0] + (next[0] - cur[0]) * tt, cur[1] + (next[1] - cur[1]) * tt];
          if (i === 0) { p2d.moveTo(a[0], a[1]); first = a; }
          else p2d.lineTo(a[0], a[1]);
          p2d.quadraticCurveTo(cur[0], cur[1], b[0], b[1]);
        }
        if (first) p2d.lineTo(first[0], first[1]);
      }
      p2d.closePath();
      return p2d;
    }
    return p2d;
  }

  function roundRect(p2d, x, y, w, h, r) {
    if (p2d.roundRect) { p2d.roundRect(x, y, w, h, r); return; }
    p2d.moveTo(x + r, y);
    p2d.arcTo(x + w, y, x + w, y + h, r);
    p2d.arcTo(x + w, y + h, x, y + h, r);
    p2d.arcTo(x, y + h, x, y, r);
    p2d.arcTo(x, y, x + w, y, r);
    p2d.closePath();
  }

  function geomBBox(g, t) {
    // грубый bbox по опорным точкам -- достаточно для градиентов в норм. координатах
    const kind = g.t;
    if (kind === "r" || kind === "rr" || kind === "e") {
      const p = vec(evalChannel(g.p || [0, 0], t), 2);
      const z = vec(evalChannel(g.z, t), 2);
      return [p[0] - Math.abs(z[0]) / 2, p[1] - Math.abs(z[1]) / 2,
              p[0] + Math.abs(z[0]) / 2, p[1] + Math.abs(z[1]) / 2];
    }
    if (kind === "ci") {
      const p = vec(evalChannel(g.p || [0, 0], t), 2);
      const r = Math.abs(evalChannel(g.r, t));
      return [p[0] - r, p[1] - r, p[0] + r, p[1] + r];
    }
    if (kind === "pg" || kind === "st") {
      const p = vec(evalChannel(g.p || [0, 0], t), 2);
      const r = Math.abs(evalChannel(kind === "st" ? g.r1 : g.r, t));
      return [p[0] - r, p[1] - r, p[0] + r, p[1] + r];
    }
    const subs = isAnimated(g.s) ? evalChannel(g.s, t) : (g.s || []);
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const sp of subs) {
      let items = sp;
      if (typeof items[items.length - 1] === "number") items = items.slice(0, -1);
      for (const v of items) {
        for (let i = 0; i + 1 < v.length; i += 2) {
          x0 = Math.min(x0, v[i]); x1 = Math.max(x1, v[i]);
          y0 = Math.min(y0, v[i + 1]); y1 = Math.max(y1, v[i + 1]);
        }
      }
    }
    if (!isFinite(x0)) return [0, 0, 1, 1];
    return [x0, y0, x1, y1];
  }

  function vec(v, n) {
    if (typeof v === "number") return new Array(n).fill(v);
    const out = v.slice();
    while (out.length < n) out.push(out[out.length - 1]);
    return out.slice(0, n);
  }

  function norm01(v) {
    if (v > 1.5) v /= 100;
    return v < 0 ? 0 : v > 1 ? 1 : v;
  }

  function scaleVec(v) {
    const out = vec(v, 2);
    if (out.some((x) => Math.abs(x) > 3)) return out.map((x) => x / 100);
    return out;
  }

  // --------------------------------------------------------------------- //
  //  плеер
  // --------------------------------------------------------------------- //
  class Player {
    constructor(file) {
      this.file = file;             // результат decode()
      this.scene = file.scene;
      this.assets = this.scene.a || {};
      this.layers = this.scene.l || [];
      this.frame = 0;
      this.playing = false;
      this.speed = 1;
      this._raf = null;
      this._t0 = 0;
      this._f0 = 0;
    }

    layerMatrix(layer, t) {
      const tr = layer.t || {};
      const p = vec(evalChannel(tr.p || [0, 0], t), 2);
      const a = vec(evalChannel(tr.a || [0, 0], t), 2);
      const s = scaleVec(evalChannel(tr.s || [100, 100], t));
      const r = (evalChannel(tr.r || 0, t) * Math.PI) / 180;
      const k = vec(evalChannel(tr.k || [0, 0], t), 2);
      const m = new DOMMatrix();
      m.translateSelf(p[0], p[1]);
      if (r) m.rotateSelf(r * 180 / Math.PI);
      if (s[0] !== 1 || s[1] !== 1) m.scaleSelf(s[0], s[1]);
      if (k[0] || k[1]) m.multiplySelf(new DOMMatrix([1, Math.tan(k[1] * Math.PI / 180), Math.tan(k[0] * Math.PI / 180), 1, 0, 0]));
      if (a[0] || a[1]) m.translateSelf(-a[0], -a[1]);
      const pi = layer.pi;
      if (pi != null) {
        const parent = this.layers.find((l) => l.i === pi) || this.layers[pi];
        if (parent) {
          // мировая матрица = родительская (уже с его предками) * своя
          const pm = this.layerMatrix(parent, t);
          const combined = new DOMMatrix(pm.toFloat64Array());
          combined.multiplySelf(m);
          return combined;
        }
      }
      return m;
    }

    gradient(spec, bbox) {
      let g = spec;
      if (typeof g === "string") g = this.assets[g];
      if (!g) return null;
      const [x, y, X, Y] = bbox;
      const bw = Math.max(X - x, 1e-6), bh = Math.max(Y - y, 1e-6);
      const ux = (v) => (g.u ? x + v * bw : v);
      const uy = (v) => (g.u ? y + v * bh : v);
      let grad = null;
      const ctx = this._ctx;
      if (g.t === "l") {
        if (g.x0 != null) {
          grad = ctx.createLinearGradient(ux(g.x0), uy(g.y0), ux(g.x1), uy(g.y1));
        } else {
          const ang = ((g.a != null ? g.a : 90) * Math.PI) / 180;
          const cx = x + bw / 2, cy = y + bh / 2;
          const half = (Math.abs(Math.cos(ang)) * bw + Math.abs(Math.sin(ang)) * bh) / 2;
          grad = ctx.createLinearGradient(cx - Math.cos(ang) * half, cy - Math.sin(ang) * half,
                                          cx + Math.cos(ang) * half, cy + Math.sin(ang) * half);
        }
      } else if (g.t === "r") {
        const cx = ux(g.cx != null ? g.cx : (g.u ? 0.5 : 0));
        const cy = uy(g.cy != null ? g.cy : (g.u ? 0.5 : 0));
        const r = g.u ? g.r * Math.max(bw, bh) : g.r;
        const fx = g.fx != null ? ux(g.fx) : cx;
        const fy = g.fy != null ? uy(g.fy) : cy;
        grad = ctx.createRadialGradient(fx, fy, 0, cx, cy, Math.max(1e-6, r));
      } else if (g.t === "c" && ctx.createConicGradient) {
        const cx = ux(g.cx != null ? g.cx : (g.u ? 0.5 : 0));
        const cy = uy(g.cy != null ? g.cy : (g.u ? 0.5 : 0));
        grad = ctx.createConicGradient(((g.a0 || 0) * Math.PI) / 180, cx, cy);
      } else {
        return null;
      }
      for (const [pos, col] of g.s) grad.addColorStop(Math.max(0, Math.min(1, pos)), cssColor(col));
      return grad;
    }

    paintStyle(spec, t, bbox) {
      if (!spec) return null;
      if (spec.c != null) {
        const c = evalChannel(spec.c, t);
        return typeof c === "string" ? cssColor(c) : cssColor(c);
      }
      if (spec.g != null) return this.gradient(spec.g, bbox);
      return "#fff";
    }

    drawFrame(ctx, t, scale) {
      const f = this.file;
      this._ctx = ctx;
      ctx.save();
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
      ctx.scale(scale, scale);
      const bg = f.scene.c && f.scene.c.b;
      if (bg) {
        ctx.fillStyle = cssColor(bg);
        ctx.fillRect(0, 0, f.width, f.height);
      }
      for (const layer of this.layers) {
        if (layer.hd) continue;
        const tr = layer.t || {};
        const op = norm01(evalChannel(tr.o != null ? tr.o : 1, t));
        if (op <= 0.002) continue;
        const g = layer.g;
        if (!g) continue;
        const bbox = geomBBox(g, t);
        const path = geomPath(g, t);
        const m = this.layerMatrix(layer, t);
        ctx.save();
        ctx.transform(m.a, m.b, m.c, m.d, m.e, m.f);
        ctx.globalAlpha = op;
        ctx.globalCompositeOperation = BLENDS[layer.b || 0] || "source-over";
        const fill = layer.f;
        if (fill) {
          const style = this.paintStyle(fill, t, bbox);
          if (style) {
            ctx.fillStyle = style;
            if (fill.o != null) ctx.globalAlpha = op * norm01(evalChannel(fill.o, t));
            ctx.fill(path, fill.ru === 1 ? "evenodd" : "nonzero");
          }
        }
        const st = layer.s;
        if (st) {
          const style = this.paintStyle(st, t, bbox);
          if (style) {
            ctx.strokeStyle = style;
            ctx.lineWidth = Math.abs(evalChannel(st.w != null ? st.w : 1, t));
            ctx.lineCap = CAPS[st.lc != null ? st.lc : 1] || "round";
            ctx.lineJoin = JOINS[st.lj != null ? st.lj : 1] || "round";
            if (st.ml) ctx.miterLimit = st.ml;
            if (st.d) ctx.setLineDash(st.d);
            if (st.do) ctx.lineDashOffset = -evalChannel(st.do, t);
            if (st.o != null) ctx.globalAlpha = op * norm01(evalChannel(st.o, t));
            ctx.stroke(path);
            ctx.setLineDash([]);
          }
        }
        ctx.restore();
      }
      ctx.restore();
    }

    // --- воспроизведение --- //
    attach(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      return this;
    }

    play() {
      if (this.playing) return;
      this.playing = true;
      this._t0 = performance.now();
      this._f0 = this.frame;
      const tick = () => {
        if (!this.playing) return;
        const dt = (performance.now() - this._t0) / 1000;
        this.frame = (this._f0 + dt * this.file.fps * this.speed) % this.file.frames;
        if (this.frame < 0) this.frame += this.file.frames;
        this.onframe && this.onframe(this.frame);
        this._paint();
        this._raf = requestAnimationFrame(tick);
      };
      this._raf = requestAnimationFrame(tick);
    }

    pause() {
      this.playing = false;
      if (this._raf) cancelAnimationFrame(this._raf);
    }

    seek(frame) {
      this.frame = ((frame % this.file.frames) + this.file.frames) % this.file.frames;
      this._f0 = this.frame;
      this._t0 = performance.now();
      this.onframe && this.onframe(this.frame);
      this._paint();
    }

    _paint() {
      if (!this.ctx) return;
      const f = this.file;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const cssW = this.canvas.clientWidth || f.width;
      const scale = (cssW * dpr) / f.width;
      const needW = Math.round(f.width * scale), needH = Math.round(f.height * scale);
      if (this.canvas.width !== needW || this.canvas.height !== needH) {
        this.canvas.width = needW;
        this.canvas.height = needH;
      }
      this.drawFrame(this.ctx, this.frame, scale);
    }
  }

  global.KVS = { decode, Player, EASINGS, parseColor, evalChannel, isAnimated, cssColor, crc32 };
})(typeof window !== "undefined" ? window : globalThis);
