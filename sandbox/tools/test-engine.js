#!/usr/bin/env node
/* Тесты движка: физика, реакции, генерация, сохранение, производительность.
   Запуск: node tools/test-engine.js                                      */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const JS = path.join(__dirname, '..', 'app', 'src', 'main', 'assets', 'js');
const ctx = { console, Math, Uint8Array, Uint16Array, Float32Array, btoa, atob };
ctx.globalThis = ctx;
vm.createContext(ctx);
for (const f of ['materials.js', 'world.js', 'pixel.js']) {
  vm.runInContext(fs.readFileSync(path.join(JS, f), 'utf8'), ctx);
}
const M = ctx.M, MATS = ctx.MATS;
let pass = 0, fail = 0;
function check(name, ok, extra) {
  if (ok) { pass++; console.log('  ✓ ' + name + (extra ? ' — ' + extra : '')); }
  else { fail++; console.log('  ✗ ' + name + (extra ? ' — ' + extra : '')); }
}
const W = 120, H = 100;
function fresh() {
  const w = new ctx.World(W, H);
  w.mat.fill(0); w.flags.fill(0); w.aux.fill(0); w.tmp.fill(20);
  return w;
}
function run(w, n) { for (let i = 0; i < n; i++) w.step(); }

console.log('ФИЗИКА');
{
  const w = fresh();
  w.paint(60, 10, 5, M.SAND, false);
  const painted = w.count()[M.SAND];
  run(w, 200);
  const c = w.count();
  check('песок падает и остаётся', (c[M.SAND] || 0) > painted * 0.6, 'было ' + painted + ', стало ' + (c[M.SAND] || 0));
  let bottom = 0;
  for (let x = 0; x < W; x++) if (w.mat[(H - 1) * W + x] === M.SAND) bottom++;
  check('песок лежит на дне', bottom > 10, bottom + ' клеток в нижнем ряду');
}
{
  const w = fresh();
  w.paint(60, 10, 6, M.WATER, false);
  run(w, 250);
  const c = w.count()[M.WATER] || 0;
  let spread = 0;
  for (let x = 0; x < W; x++) if (w.mat[(H - 1) * W + x] === M.WATER) spread++;
  check('вода растекается', spread > 30, spread + ' клеток в нижнем ряду');
}
{
  const w = fresh();
  w.paint(60, 60, 6, M.OIL, false);
  w.paint(60, 80, 8, M.WATER, false);
  run(w, 150);
  const c = w.count();
  check('нефть плавает на воде', (c[M.OIL] || 0) > 20 && (c[M.WATER] || 0) > 100);
}
{
  const w = fresh();
  w.paint(60, 20, 5, M.SAND, true);
  run(w, 80);
  let stayed = 0;
  for (let y = 15; y < 26; y++) for (let x = 55; x < 66; x++) if (w.mat[y * W + x] === M.SAND) stayed++;
  check('«Фикс» держит блок в воздухе', stayed > 40, stayed + ' клеток осталось');
}

console.log('\nРЕАКЦИИ');
function reaction(name, setup, checkFn) {
  const w = fresh();
  setup(w);
  run(w, 220);
  const c = w.count();
  check(name, checkFn(c, w), Object.entries(w.recipesSeen).map(([k]) => k).join(',') || 'нет открытий');
}
reaction('лава + вода → камень и пар',
  (w) => { w.paint(60, 60, 6, M.LAVA, false); w.paint(60, 40, 6, M.WATER, false); },
  (c) => (c[M.STONE] || 0) > 5 || (c[M.STEAM] || 0) > 10);
reaction('песок + лава → стекло',
  (w) => { w.paint(60, 60, 6, M.LAVA, false); w.paint(60, 45, 5, M.SAND, false); },
  (c) => (c[M.GLASS] || 0) > 2);
reaction('земля + вода → грязь',
  (w) => { for (let y = 60; y < 80; y++) for (let x = 40; x < 80; x++) w.set(x, y, M.DIRT); w.paint(60, 50, 6, M.WATER, false); },
  (c) => (c[M.MUD] || 0) > 5);
reaction('огонь сжигает дерево',
  (w) => { for (let y = 60; y < 75; y++) for (let x = 30; x < 90; x++) w.set(x, y, M.WOOD); w.set(60, 59, M.FIRE); },
  (c, w) => (c[M.WOOD] || 0) < 300);
reaction('порох взрывается от огня',
  (w) => {
    w.paint(60, 60, 4, M.GUNPOWDER, false);
    // искра прямо над порохом (клетки пороха начинаются выше центра кисти)
    let top = H;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) if (w.mat[y * W + x] === M.GUNPOWDER && y < top) top = y;
    w.paint(60, top - 1, 1, M.FIRE, false);
  },
  (c) => (c[M.GUNPOWDER] || 0) < 20);
reaction('кислота растворяет камень',
  (w) => { for (let y = 60; y < 80; y++) for (let x = 40; x < 80; x++) w.set(x, y, M.STONE); w.paint(60, 50, 6, M.ACID, false); },
  (c) => (c[M.STONE] || 0) < 800);
reaction('соль + вода → солёная вода',
  (w) => { w.paint(60, 60, 4, M.SALT, false); w.paint(60, 50, 5, M.WATER, false); },
  (c) => (c[M.SALTWATER] || 0) > 3);
reaction('снег тает в воду',
  (w) => { for (let y = 70; y < 85; y++) for (let x = 30; x < 90; x++) w.set(x, y, M.SNOW, -8); },
  (c) => (c[M.WATER] || 0) > 100);

console.log('\nСИСТЕМНОЕ');
{
  for (const kind of ['island', 'volcano', 'desert', 'ice', 'empty']) {
    const w = new ctx.World(W, H);
    w.generate(kind);
    const c = w.count();
    const filled = Object.entries(c).filter(([k]) => k != 0).reduce((a, [, v]) => a + v, 0);
    check('мир «' + kind + '» генерируется', filled > 200, filled + ' клеток');
  }
}
{
  const w = fresh();
  w.paint(30, 40, 5, M.LAVA);
  w.paint(80, 20, 6, M.WATER);
  const snap = JSON.parse(JSON.stringify(w.serialize()));
  const w2 = fresh();
  w2.deserialize(snap);
  let diff = 0;
  for (let i = 0; i < w.n; i++) if (w.mat[i] !== w2.mat[i]) diff++;
  check('сохранение и загрузка', diff === 0, (snap.data.length / 1024).toFixed(1) + ' КБ, расхождений ' + diff);
}
{
  const d = new Uint8ClampedArray(W * H * 4), g = new Uint8ClampedArray(W * H * 4);
  const w = fresh();
  w.generate('island');
  ctx.PixelRender.renderPixels(w, d, g);
  let painted = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i] === 255) painted++;
  check('рендер заполняет буфер', painted === W * H, painted + ' пикселей');
}
{
  const perf = new ctx.World(176, 320);
  perf.generate('island');
  const t0 = Date.now();
  for (let i = 0; i < 60; i++) perf.step();
  const ms = (Date.now() - t0) / 60;
  check('скорость симуляции', ms < 25, ms.toFixed(2) + ' мс на шаг (нужно < 25)');
}

console.log('\n' + (fail === 0 ? '✅ ВСЁ ПРОШЛО' : '❌ ПРОВАЛОВ: ' + fail) + ' — тестов: ' + (pass + fail) + ', успешно: ' + pass);
process.exit(fail === 0 ? 0 : 1);
