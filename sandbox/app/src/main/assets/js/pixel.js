/* ===========================================================
   ПЕСОЧНИЦА — пиксельный рендер мира
   Общий модуль: используется и в приложении, и в тестах/превью.
   renderPixels(world, outRGBA, outGlowRGBA) заполняет буферы.
   =========================================================== */
(function (global) {
  'use strict';

  var M = global.M, MATS = global.MATS;

  var COLORS = [];
  var SPREAD = 0.34;
  var NOISE = null, NSIZE = 256;
  var ready = false;

  function buildPalette() {
    COLORS = [];
    for (var i = 0; i < MATS.length; i++) {
      var mm = MATS[i];
      if (!mm) { COLORS[i] = null; continue; }
      var cols = mm.color, n = cols.length;
      var mr = 0, mg = 0, mb = 0, k;
      for (k = 0; k < n; k++) { mr += cols[k][0]; mg += cols[k][1]; mb += cols[k][2]; }
      mr /= n; mg /= n; mb /= n;
      var c = [[], [], []];
      for (var j = 0; j < n; j++) {
        c[0].push(mr + (cols[j][0] - mr) * SPREAD);
        c[1].push(mg + (cols[j][1] - mg) * SPREAD);
        c[2].push(mb + (cols[j][2] - mb) * SPREAD);
      }
      COLORS[i] = c;
    }
  }

  function buildNoise() {
    var sz = NSIZE, data = new Float32Array(sz * sz);
    var oct = [{ s: 4, a: 1.0 }, { s: 11, a: 0.45 }, { s: 29, a: 0.2 }];
    for (var g = 0; g < oct.length; g++) {
      var sc = oct[g].s, amp = oct[g].a;
      var grid = new Float32Array(sc * sc);
      for (var q = 0; q < grid.length; q++) grid[q] = Math.random();
      for (var y = 0; y < sz; y++) {
        for (var x = 0; x < sz; x++) {
          var fx = x / sz * sc, fy = y / sz * sc;
          var x0 = Math.floor(fx), y0 = Math.floor(fy);
          var tx = fx - x0, ty = fy - y0;
          tx = tx * tx * (3 - 2 * tx); ty = ty * ty * (3 - 2 * ty);
          var x1 = (x0 + 1) % sc, y1 = (y0 + 1) % sc;
          var a = grid[y0 * sc + x0], b = grid[y0 * sc + x1];
          var c = grid[y1 * sc + x0], d = grid[y1 * sc + x1];
          var v = (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
          data[y * sz + x] += (v - 0.5) * amp;
        }
      }
    }
    NOISE = data;
  }

  function init() {
    if (ready) return;
    buildPalette();
    buildNoise();
    ready = true;
  }

  function nz(x, y) {
    return NOISE[((y & (NSIZE - 1)) << 8) | (x & (NSIZE - 1))];
  }

  function renderPixels(world, d, g) {
    if (!ready) init();
    var W = world.W, H = world.H;
    var mat = world.mat, var8 = world.var8, tmp = world.tmp;
    var frame = world.frame, n = W * H;

    for (var i = 0; i < n; i++) {
      var o = i << 2;
      var m = mat[i];
      var x = i % W, y = (i / W) | 0;

      if (m === 0) {
        var sky = y / H;
        var sr = 8 + sky * 9, sg = 11 + sky * 13, sb = 20 + sky * 20;
        var nn = nz(x + 71, y + 133);
        sr += nn * 4; sg += nn * 5; sb += nn * 7;
        if ((var8[i] & 255) === 7 && y < H * 0.75) {
          var tw = 0.35 + 0.65 * ((var8[i] >> 4 & 15) / 15);
          sr += 120 * tw; sg += 128 * tw; sb += 150 * tw;
        }
        d[o] = sr; d[o + 1] = sg; d[o + 2] = sb; d[o + 3] = 255;
        g[o + 3] = 0;
        continue;
      }

      var col = COLORS[m];
      if (!col) { d[o + 3] = 255; g[o + 3] = 0; continue; }
      var v = var8[i];
      var nc = col[0].length;
      var idx = 0;
      if (nc > 1 && (v & 31) === 0) idx = 1 + ((v >> 5) % (nc - 1));
      var r = col[0][idx], gg = col[1][idx], b = col[2][idx];

      var shade = nz(x, y) * 14 + nz(x + 61, y + 97) * 6;
      r += shade; gg += shade; b += shade;

      if (y + 1 < H && mat[i + W] === 0) { r -= 30; gg -= 30; b -= 32; }
      else if (y > 0 && mat[i - W] === 0) { r += 20; gg += 20; b += 17; }

      var t = tmp[i];
      if (t > 120) {
        var hot = Math.min(1, (t - 120) / 700);
        r = r + (255 - r) * hot * 0.95;
        gg = gg + (150 - gg) * hot * 0.8;
        b = b + (40 - b) * hot * 0.7;
      } else if (t < -6) {
        var cold = Math.min(1, (-6 - t) / 40);
        b = b + (255 - b) * cold * 0.35;
        r = r + (170 - r) * cold * 0.2;
      }

      d[o] = r < 0 ? 0 : r > 255 ? 255 : r;
      d[o + 1] = gg < 0 ? 0 : gg > 255 ? 255 : gg;
      d[o + 2] = b < 0 ? 0 : b > 255 ? 255 : b;
      d[o + 3] = 255;

      var mg = MATS[m].glow, ga = 0;
      if (mg) {
        ga = mg * (0.55 + 0.45 * ((v & 63) / 63));
        if (m === M.FIRE) ga *= 0.55 + 0.45 * Math.sin((v + frame) * 0.5);
        if (m === M.LAVA) ga *= 0.75 + 0.25 * Math.sin((v * 0.3 + frame * 0.08));
      } else if (t > 400) {
        ga = Math.min(1, (t - 400) / 900);
      }
      if (ga > 0) {
        var gc = MATS[m].glowColor || [255, 160, 60];
        g[o] = gc[0]; g[o + 1] = gc[1]; g[o + 2] = gc[2];
        g[o + 3] = Math.min(255, ga * 255);
      } else {
        g[o + 3] = 0;
      }
    }
  }

  global.PixelRender = { renderPixels: renderPixels, init: init };
})(typeof window !== 'undefined' ? window : globalThis);
