/*
 * Сквозной smoke-тест веб-движка: минимальные заглушки DOM (DOMMatrix, Path2D,
 * контекст канваса), затем decode() + drawFrame() на каждом примере.
 * Печатает JSON-отчёт: {file: {fills, strokes, errors}}.
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const src = fs.readFileSync(path.join(ROOT, "viewer", "kvs-player.js"), "utf8");
const sandbox = {};
new Function("globalThis2", src.replace('typeof window !== "undefined" ? window : globalThis', "globalThis2"))(sandbox);
const KVS = sandbox.KVS;

// ---- заглушки DOM ---- //
class M {
  constructor(init) {
    if (Array.isArray(init)) [this.a, this.b, this.c, this.d, this.e, this.f] = init;
    else if (init && typeof init.toFloat64Array === "function") [this.a, this.b, this.c, this.d, this.e, this.f] = init.toFloat64Array();
    else { this.a = 1; this.b = 0; this.c = 0; this.d = 1; this.e = 0; this.f = 0; }
  }
  toFloat64Array() { return [this.a, this.b, this.c, this.d, this.e, this.f]; }
  translateSelf(x, y) { this.e += this.a * x + this.c * y; this.f += this.b * x + this.d * y; return this; }
  rotateSelf(deg) {
    const r = (deg * Math.PI) / 180, cs = Math.cos(r), sn = Math.sin(r);
    const [a, b, c, d] = [this.a, this.b, this.c, this.d];
    this.a = a * cs + c * sn; this.b = b * cs + d * sn;
    this.c = a * -sn + c * cs; this.d = b * -sn + d * cs;
    return this;
  }
  scaleSelf(sx, sy) { this.a *= sx; this.b *= sx; this.c *= sy; this.d *= sy; return this; }
  multiplySelf(o) {
    const m = new M(this.toFloat64Array());
    this.a = m.a * o.a + m.c * o.b; this.b = m.b * o.a + m.d * o.b;
    this.c = m.a * o.c + m.c * o.d; this.d = m.b * o.c + m.d * o.d;
    this.e = m.a * o.e + m.c * o.f + m.e; this.f = m.b * o.e + m.d * o.f + m.f;
    return this;
  }
}
class P {
  constructor() { this.ops = 0; }
  moveTo() { this.ops++; } lineTo() { this.ops++; }
  bezierCurveTo() { this.ops++; } quadraticCurveTo() { this.ops++; }
  closePath() {} rect() { this.ops++; } ellipse() { this.ops++; }
  arcTo() { this.ops++; } roundRect() { this.ops++; }
}
function mockCtx() {
  const stats = { fills: 0, strokes: 0 };
  const grad = { addColorStop() {} };
  return {
    stats,
    canvas: { width: 512, height: 512 },
    save() {}, restore() {}, setTransform() {}, clearRect() {}, scale() {}, transform() {},
    setLineDash() {}, fill() { stats.fills++; }, stroke() { stats.strokes++; },
    createLinearGradient: () => grad, createRadialGradient: () => grad,
    createConicGradient: () => grad, fillRect() { stats.fills++; },
  };
}
global.DOMMatrix = M;
global.Path2D = P;

(async () => {
  const dir = path.join(ROOT, "examples");
  const report = {};
  for (const name of fs.readdirSync(dir).filter((f) => f.endsWith(".kvs"))) {
    const bytes = new Uint8Array(fs.readFileSync(path.join(dir, name)));
    try {
      const file = await KVS.decode(bytes);
      const player = new KVS.Player(file);
      const ctx = mockCtx();
      for (const t of [0, file.frames * 0.37, file.frames - 1]) {
        player.drawFrame(ctx, t, 1);
      }
      report[name] = { fills: ctx.stats.fills, strokes: ctx.stats.strokes, errors: null };
    } catch (e) {
      report[name] = { fills: 0, strokes: 0, errors: String(e && e.message || e) };
    }
  }
  process.stdout.write(JSON.stringify(report));
})();
