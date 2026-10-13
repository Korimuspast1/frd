/*
 * Кросс-проверка: читает {scene, times} из stdin, вычисляет те же каналы,
 * что и Python-движок, и печатает результат в JSON.
 * Запускается тестом tests/test_engine.py::TestCrossEngine.
 */
const fs = require("fs");
const src = fs.readFileSync(require("path").join(__dirname, "..", "viewer", "kvs-player.js"), "utf8");
const sandbox = { window: undefined };
new Function("globalThis2", src.replace("typeof window !== \"undefined\" ? window : globalThis", "globalThis2"))(sandbox);
const KVS = sandbox.KVS;

const input = JSON.parse(fs.readFileSync(0, "utf8"));
const out = {};
for (const tRaw of input.times) {
  const t = parseFloat(tRaw);
  const per = {};
  input.scene.l.forEach((layer, i) => {
    const tr = layer.t || {};
    for (const key of ["p", "a", "s", "r", "o", "k"]) {
      if (!(key in tr)) continue;
      const v = KVS.evalChannel(tr[key], t);
      per[`l.${i}.t.${key}`] = typeof v === "number" ? v : v;
    }
  });
  out[String(t)] = per;
}
process.stdout.write(JSON.stringify(out));
