/* ===========================================================
   ПЕСОЧНИЦА — движок симуляции
   Клеточный автомат: гравитация, текучесть, тепло, фазовые
   переходы и химические реакции. Работает в браузере и в Node.
   =========================================================== */
(function (global) {
  'use strict';

  var M = global.M, MATS = global.MATS, MT = global.MT, AMBIENT = global.AMBIENT;

  var F_ANCHOR = 1, F_MOVED = 2, F_BURN = 4;
  var DIR_R = 16, DIR_L = 32;

  function World(w, h) {
    this.W = w; this.H = h;
    this.n = w * h;
    this.mat = new Uint8Array(this.n);
    this.tmp = new Float32Array(this.n);
    this.aux = new Uint16Array(this.n);
    this.var8 = new Uint8Array(this.n);
    this.flags = new Uint8Array(this.n);
    this.tmp.fill(AMBIENT);
    this.frame = 0;
    this.recipesSeen = {};
    this.onRecipe = null;
    this.onEvent = null;
    this.dirty = true;
    for (var i = 0; i < this.n; i++) this.var8[i] = (Math.random() * 255) | 0;
  }

  function hash8(x, y) {
    var h = (x * 374761393 + y * 668265263) | 0;
    h = (h ^ (h >> 13)) * 1274126177 | 0;
    return (h ^ (h >> 16)) & 255;
  }

  World.prototype.inside = function (x, y) {
    return x >= 0 && y >= 0 && x < this.W && y < this.H;
  };

  World.prototype.get = function (x, y) {
    if (x < 0 || y < 0 || x >= this.W || y >= this.H) return M.STONE;
    return this.mat[y * this.W + x];
  };

  World.prototype.set = function (x, y, m, temp, keepFlags) {
    if (!this.inside(x, y)) return;
    var i = y * this.W + x;
    this.mat[i] = m;
    this.var8[i] = hash8(x >> 2, y >> 2);
    var base = MATS[m] ? (MATS[m].heat || AMBIENT) : AMBIENT;
    this.tmp[i] = temp === undefined ? base : temp;
    if (!keepFlags) this.flags[i] = 0;
    if (m === M.FIRE) this.aux[i] = 40 + ((Math.random() * 40) | 0);
    else if (m === M.PLANT) this.aux[i] = 40 + ((Math.random() * 80) | 0);
    else if (m !== M.GUNPOWDER) this.aux[i] = 0;
    this.dirty = true;
  };

  World.prototype.place = function (x, y, m, anchor) {
    if (!this.inside(x, y)) return;
    var i = y * this.W + x;
    this.mat[i] = m;
    this.var8[i] = hash8(x >> 2, y >> 2);
    var base = MATS[m] ? (MATS[m].heat || AMBIENT) : AMBIENT;
    this.tmp[i] = base + (Math.random() - 0.5) * 30;
    this.flags[i] = anchor ? F_ANCHOR : 0;
    if (m === M.FIRE) this.aux[i] = 45 + ((Math.random() * 40) | 0);
    else if (m === M.PLANT) this.aux[i] = 40 + ((Math.random() * 80) | 0);
    else this.aux[i] = 0;
    this.dirty = true;
  };

  World.prototype.paint = function (cx, cy, r, m, anchor) {
    var r2 = r * r, W = this.W, H = this.H;
    for (var dy = -r; dy <= r; dy++) {
      for (var dx = -r; dx <= r; dx++) {
        var dd = dx * dx + dy * dy;
        if (dd > r2) continue;
        var x = cx + dx, y = cy + dy;
        if (x < 0 || y < 0 || x >= W || y >= H) continue;
        if (dd > (r - 1) * (r - 1) && Math.random() < 0.55) continue;
        if (Math.random() < 0.08) continue;
        var i = y * W + x, cur = this.mat[i];
        if (cur !== M.EMPTY) {
          if (m === M.EMPTY) { this.set(x, y, M.EMPTY); continue; }
          if (MATS[cur].type === MT.GAS || MATS[cur].type === MT.FIRE) { this.place(x, y, m, anchor); continue; }
          if (Math.random() < 0.3) this.place(x, y, m, anchor);
          continue;
        }
        this.place(x, y, m, anchor);
      }
    }
    this.dirty = true;
  };

  World.prototype.erase = function (cx, cy, r) {
    var r2 = r * r;
    for (var dy = -r; dy <= r; dy++) {
      for (var dx = -r; dx <= r; dx++) {
        if (dx * dx + dy * dy > r2) continue;
        var x = cx + dx, y = cy + dy;
        if (!this.inside(x, y)) continue;
        if (Math.random() < 0.06) continue;
        this.set(x, y, M.EMPTY);
      }
    }
    this.dirty = true;
  };

  /* ---------------- физика ---------------- */

  // Может ли клетка j быть занята материалом с плотностью dens?
  World.prototype.canEnter = function (j, dens, allowLiquidSwap) {
    var m = this.mat[j];
    if (m === M.EMPTY) return true;
    var mt = MATS[m];
    if (mt.type === MT.GAS || mt.type === MT.FIRE) return true;
    if (allowLiquidSwap && mt.type === MT.LIQUID) return mt.density < dens;
    return false;
  };

  World.prototype.swapCells = function (i, j, dirBits) {
    var m = this.mat[i], t = this.tmp[i], a = this.aux[i], v = this.var8[i], f = this.flags[i];
    this.mat[i] = this.mat[j]; this.tmp[i] = this.tmp[j];
    this.aux[i] = this.aux[j]; this.var8[i] = this.var8[j];
    this.flags[i] = (this.flags[j] & F_ANCHOR) | F_MOVED;
    this.mat[j] = m; this.tmp[j] = t; this.aux[j] = a; this.var8[j] = v;
    this.flags[j] = (f & F_ANCHOR) | F_MOVED | (dirBits || 0);
    this.dirty = true;
  };

  World.prototype.doPowder = function (i, x, y) {
    var W = this.W, H = this.H, d = y * W + x;
    var m = this.mat[i], dens = MATS[m].density, fric = MATS[m].fric;
    if (y === H - 1) return false;   // дно мира — опора
    if (y + 1 < H) {
      var j = d + W;
      if (this.canEnter(j, dens, true)) { this.swapCells(i, j); return true; }
      var dir = (this.flags[i] & DIR_R) ? 1 : (this.flags[i] & DIR_L) ? -1 : (Math.random() < 0.5 ? -1 : 1);
      if (Math.random() < 1 - fric) {
        for (var k = 0; k < 2; k++) {
          var dd = k === 0 ? dir : -dir;
          var nx = x + dd;
          if (nx < 0 || nx >= W) continue;
          var diag = j + dd, side = d + dd;
          if (this.canEnter(diag, dens, true) && this.canEnter(side, dens, true)) {
            this.swapCells(i, diag, dd > 0 ? DIR_R : DIR_L);
            return true;
          }
        }
      }
    }
    return false;
  };

  World.prototype.doLiquid = function (i, x, y) {
    var W = this.W, H = this.H, d = y * W + x;
    var md = MATS[this.mat[i]].density, mp = MATS[this.mat[i]].disp;

    if (y === this.H - 1) return false;  // дно мира

    // всплытие под более плотной жидкостью
    if (y > 0) {
      var up = d - W, um = this.mat[up];
      if (um !== this.mat[i] && MATS[um].type === MT.LIQUID && MATS[um].density > md) {
        this.swapCells(i, up); return true;
      }
    }

    if (y + 1 < H) {
      var j = d + W;
      if (this.canEnter(j, md, true)) { this.swapCells(i, j); return true; }
      var s = Math.random() < 0.5 ? -1 : 1;
      for (var k = 0; k < 2; k++) {
        var dd = k === 0 ? s : -s;
        var nx = x + dd;
        if (nx < 0 || nx >= W) continue;
        var j2 = j + dd;
        if (this.canEnter(j2, md, true) && this.canEnter(d + dd, md, true)) {
          this.swapCells(i, j2, dd > 0 ? DIR_R : DIR_L);
          return true;
        }
      }
    }

    // растекание вбок
    var dir = (this.flags[i] & DIR_R) ? 1 : (this.flags[i] & DIR_L) ? -1 : (Math.random() < 0.5 ? -1 : 1);
    var moved = false;
    for (var n = 0; n < mp; n++) {
      var nx2 = x + dir;
      if (nx2 < 0 || nx2 >= W) { dir = -dir; continue; }
      var j3 = d + dir;
      if (this.canEnter(j3, md, true)) {
        this.swapCells(i, j3, dir > 0 ? DIR_R : DIR_L);
        i = j3; d = j3; x = nx2; moved = true;
      } else break;
    }
    return moved;
  };

  World.prototype.doGas = function (i, x, y) {
    var W = this.W, d = y * W + x;
    var dens = MATS[this.mat[i]].density;
    var up = d - W;
    if (y > 0) {
      if (this.mat[up] === M.EMPTY) { this.swapCells(i, up); return true; }
      var sx = Math.random() < 0.5 ? -1 : 1;
      var nx = x + sx;
      if (nx >= 0 && nx < W) {
        var j = up + sx;
        if (this.mat[j] === M.EMPTY) { this.swapCells(i, j); return true; }
      }
      // газ всплывает сквозь жидкость
      if (y > 1 && MATS[this.mat[up]].type === MT.LIQUID && Math.random() < 0.7) {
        this.swapCells(i, up); return true;
      }
    }
    if (Math.random() < 0.4) {
      for (var k = 0; k < 2; k++) {
        var xx = x + (k ? 1 : -1);
        if (xx >= 0 && xx < W && this.mat[d + (k ? 1 : -1)] === M.EMPTY) {
          this.swapCells(i, d + (k ? 1 : -1)); return true;
        }
      }
    }
    return false;
  };

  /* ---------------- реакции ---------------- */

  World.prototype.neighborFuel = function (x, y) {
    var W = this.W, H = this.H;
    for (var k = 0; k < 4; k++) {
      var nx = x + (k === 0 ? 1 : k === 1 ? -1 : 0);
      var ny = y + (k === 2 ? 1 : k === 3 ? -1 : 0);
      if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
      var m = this.mat[ny * W + nx];
      if (m !== M.EMPTY && MATS[m].flam > 0 && m !== M.FIRE) return true;
    }
    return false;
  };

  World.prototype.igniteNeighbors = function (x, y, chance) {
    var W = this.W, H = this.H;
    for (var k = 0; k < 4; k++) {
      if (Math.random() > chance) continue;
      var nx = x + (k === 0 ? 1 : k === 1 ? -1 : 0);
      var ny = y + (k === 2 ? 1 : k === 3 ? -1 : 0);
      if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
      var m = this.mat[ny * W + nx];
      if (m === M.EMPTY || m === M.FIRE) continue;
      if (m === M.WATER || m === M.ICE || m === M.SNOW || m === M.SALTWATER) continue;
      var mm = MATS[m];
      if (!mm.flam) continue;
      if (m === M.GUNPOWDER) { this.explode(nx, ny, 7); continue; }
      if (Math.random() < mm.flam) this.set(nx, ny, M.FIRE, Math.max(this.tmp[ny * W + nx], 620));
    }
  };

  World.prototype.noteRecipe = function (id) {
    if (!this.recipesSeen[id]) {
      this.recipesSeen[id] = true;
      if (this.onRecipe) this.onRecipe(id);
    }
  };

  World.prototype.explode = function (cx, cy, power) {
    var W = this.W, H = this.H, r = power, x, y, dx, dy;
    for (dy = -r; dy <= r; dy++) {
      for (dx = -r; dx <= r; dx++) {
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > r) continue;
        x = cx + dx; y = cy + dy;
        if (x < 0 || y < 0 || x >= W || y >= H) continue;
        var i = y * W + x, m = this.mat[i];
        if (m === M.EMPTY) { if (Math.random() < 0.4) this.set(x, y, M.FIRE, 900); continue; }
        var mm = MATS[m];
        if (mm.acidRes >= 0.9) continue;
        var chance = 1 - dist / r;
        if (Math.random() < chance * 0.95) {
          if (mm.flam && Math.random() < 0.5) this.set(x, y, M.FIRE, 950);
          else if (Math.random() < 0.3) this.set(x, y, M.SMOKE, 500);
          else this.set(x, y, M.EMPTY, 700);
        }
      }
    }
    for (var k = 0; k < 20; k++) {
      var a = Math.random() * Math.PI * 2, rr = r + 1 + Math.random() * 4;
      var px = Math.round(cx + Math.cos(a) * rr), py = Math.round(cy + Math.sin(a) * rr);
      if (this.inside(px, py) && MATS[this.mat[py * W + px]].flam && Math.random() < 0.5) {
        this.set(px, py, M.FIRE, 800);
      }
    }
    if (this.onEvent) this.onEvent('boom', cx, cy, power);
    this.dirty = true;
  };

  World.prototype.tryIgnite = function (x, y) {
    var i = y * this.W + x, m = this.mat[i];
    if (m === M.WATER || m === M.ICE || m === M.SNOW || m === M.EMPTY) return;
    var mm = MATS[m];
    if (m === M.GUNPOWDER) { this.explode(x, y, 7); return; }
    if (!mm.flam) return;
    if (Math.random() > mm.flam + 0.15) return;
    this.set(x, y, M.FIRE, Math.max(this.tmp[i], 620));
    this.igniteNeighbors(x, y, 0.45);
  };

  World.prototype.reactAt = function (i, x, y) {
    var W = this.W, H = this.H;
    var mat = this.mat[i], mt = MATS[mat], t = this.tmp[i];

    /* --- фазовые переходы --- */
    if (mat === M.WATER) {
      if (t < -4 && Math.random() < 0.3) { this.set(x, y, M.ICE, t); return; }
      if (t > 100) { this.set(x, y, M.STEAM, Math.min(t, 320)); return; }
    } else if (mat === M.SALTWATER) {
      if (t < -10 && Math.random() < 0.4) { this.set(x, y, M.ICE, t); return; }
      if (t > 104) {
        if (Math.random() < 0.3) this.set(x, y, M.SALT, t);
        else this.set(x, y, M.STEAM, 170);
        this.noteRecipe('salt');
        return;
      }
    } else if (mat === M.ICE) {
      if (t > 1 && Math.random() < 0.22) { this.set(x, y, M.WATER, Math.max(t, 1)); return; }
    } else if (mat === M.SNOW) {
      if (t > -0.5 && Math.random() < 0.25) { this.set(x, y, M.WATER, Math.max(t, 1)); return; }
    } else if (mat === M.STEAM) {
      if (t < 90 && Math.random() < 0.015) { this.set(x, y, M.WATER, Math.max(t, 2)); return; }
    } else if (mat === M.LAVA) {
      if (t < 760) { this.set(x, y, M.STONE, t); return; }
    } else if (mat === M.MOLTEN_METAL) {
      if (t < 900) { this.set(x, y, M.METAL, t); return; }
    } else if (mat === M.MOLTEN_GLASS) {
      if (t < 800) { this.set(x, y, M.GLASS, t); return; }
    } else if (mat === M.METAL) {
      if (t > 1150) { this.set(x, y, M.MOLTEN_METAL, t); this.noteRecipe('melt_metal'); return; }
    } else if (mat === M.GLASS) {
      if (t > 1320) { this.set(x, y, M.MOLTEN_GLASS, t); return; }
    } else if (mat === M.STONE) {
      if (t > 1380) { this.set(x, y, M.LAVA, t); return; }
    } else if (mt.flam && t > 230 && Math.random() < 0.1) {
      this.tryIgnite(x, y); return;
    }

    if (mat === M.MUD && t > 85 && Math.random() < 0.02) { this.set(x, y, M.DIRT, t); return; }

    if (mat === M.SEED) {
      var dirt = false, wet = false;
      for (var k = 0; k < 4; k++) {
        var nx = x + (k === 0 ? 1 : k === 1 ? -1 : 0);
        var ny = y + (k === 2 ? 1 : k === 3 ? -1 : 0);
        if (!this.inside(nx, ny)) continue;
        var nm = this.mat[ny * W + nx];
        if (nm === M.DIRT || nm === M.MUD) dirt = true;
        if (nm === M.WATER || nm === M.MUD) wet = true;
      }
      if (dirt && wet && Math.random() < 0.04) {
        this.set(x, y, M.PLANT, t);
        this.aux[i] = 50 + ((Math.random() * 90) | 0);
        this.noteRecipe('plant');
      }
      return;
    }

    if (mat === M.PLANT) {
      var wet2 = false;
      for (var k2 = 0; k2 < 4; k2++) {
        var ax = x + (k2 === 0 ? 1 : k2 === 1 ? -1 : 0);
        var ay = y + (k2 === 2 ? 1 : k2 === 3 ? -1 : 0);
        if (!this.inside(ax, ay)) continue;
        var am = this.mat[ay * W + ax];
        if (am === M.WATER || am === M.MUD) wet2 = true;
      }
      if (wet2 && y > 1 && this.mat[i - W] === M.EMPTY && this.aux[i] > 0 && Math.random() < 0.05) {
        var life = this.aux[i] - 1;
        this.set(x, y, M.PLANT, t, true);
        this.aux[i] = life;
        this.set(x, y - 1, M.PLANT, t);
        this.aux[y * W + x - W] = life;
        this.noteRecipe('grow');
      }
      return;
    }

    if (mat === M.CRYSTAL) {
      if (t < 20 && Math.random() < 0.03) {
        var cx = x + (Math.random() < 0.5 ? 1 : -1), cy = y + (Math.random() < 0.5 ? 1 : -1);
        if (this.inside(cx, cy)) {
          var ci = cy * W + cx;
          if ((this.mat[ci] === M.WATER || this.mat[ci] === M.STONE) && Math.random() < 0.2) {
            this.set(cx, cy, M.CRYSTAL, t);
            this.noteRecipe('crystal');
          }
        }
      }
      return;
    }

    /* --- контактные реакции: 2 случайных соседа --- */
    if (mt.type === MT.SOLID && ((x * 7 + y * 13 + this.frame) & 3) !== 0) return;
    for (var c = 0; c < 2; c++) {
      var d = (Math.random() * 4) | 0;
      var ox = d === 0 ? 1 : d === 1 ? -1 : 0;
      var oy = d === 2 ? 1 : d === 3 ? -1 : 0;
      var nx2 = x + ox, ny2 = y + oy;
      if (nx2 < 0 || ny2 < 0 || nx2 >= W || ny2 >= H) continue;
      var j = ny2 * W + nx2, om = this.mat[j], ot = MATS[om];
      if (om === M.EMPTY || om === mat) continue;

      if (mat === M.LAVA) {
        if (om === M.WATER || om === M.SALTWATER) {
          this.set(nx2, ny2, M.STEAM, 210);
          this.tmp[i] -= 90;
          if (Math.random() < 0.16) { this.set(x, y, M.OBSIDIAN, 420); this.noteRecipe('obsidian'); }
          else { this.set(x, y, M.STONE, 520); this.noteRecipe('steam_stone'); }
          return;
        }
        if (om === M.ICE || om === M.SNOW) {
          this.set(nx2, ny2, M.STEAM, 150); this.tmp[i] -= 60; this.noteRecipe('melt_ice'); continue;
        }
        if (om === M.SAND || om === M.GLASS) { this.set(nx2, ny2, M.GLASS, 980); this.noteRecipe('glass'); continue; }
        if (om === M.DIRT || om === M.MUD) { this.set(nx2, ny2, M.BRICK, 760); this.noteRecipe('brick'); continue; }
        if (om === M.METAL) { this.set(nx2, ny2, M.MOLTEN_METAL, 1250); this.noteRecipe('melt_metal'); continue; }
        if (om === M.WOOD || om === M.PLANT || om === M.OIL) { this.tryIgnite(nx2, ny2); continue; }
        if (om === M.GUNPOWDER) { this.explode(nx2, ny2, 7); return; }
        continue;
      }

      if (mat === M.WATER) {
        if (om === M.LAVA) {
          this.set(x, y, M.STEAM, 170);
          if (Math.random() < 0.18) { this.set(nx2, ny2, M.OBSIDIAN, 420); this.noteRecipe('obsidian'); }
          else { this.set(nx2, ny2, M.STONE, 520); this.noteRecipe('steam_stone'); }
          return;
        }
        if (om === M.FIRE) { this.set(x, y, M.STEAM, 130); this.set(nx2, ny2, M.STEAM, 150); return; }
        if (om === M.DIRT && Math.random() < 0.05) { this.set(nx2, ny2, M.MUD, 30); this.noteRecipe('mud'); continue; }
        if (om === M.ASH && Math.random() < 0.05) { this.set(nx2, ny2, M.MUD, 30); this.noteRecipe('ash'); continue; }
        if (om === M.SALT && Math.random() < 0.5) { this.set(nx2, ny2, M.SALTWATER, 25); this.noteRecipe('saltwater'); continue; }
        if (om === M.ICE && Math.random() < 0.03) { this.set(x, y, M.ICE, -2); continue; }
        if (om === M.MUD && Math.random() < 0.003) { this.set(nx2, ny2, M.DIRT, 30); continue; }
        if (om === M.STONE && t < 2 && Math.random() < 0.0008) {
          this.set(nx2, ny2, M.CRYSTAL, t); this.noteRecipe('crystal'); continue;
        }
        continue;
      }

      if (mat === M.FIRE) {
        if (om === M.WATER || om === M.SALTWATER) {
          this.set(x, y, M.STEAM, 150); this.set(nx2, ny2, M.STEAM, 130); return;
        }
        if (om === M.ICE || om === M.SNOW) {
          this.set(nx2, ny2, M.WATER, 12); this.set(x, y, M.STEAM, 120); this.noteRecipe('melt_ice'); continue;
        }
        if (ot.flam) { if (Math.random() < ot.flam * 0.5) this.tryIgnite(nx2, ny2); }
        continue;
      }

      if (mat === M.ACID) {
        if (om === M.SMOKE || om === M.STEAM) continue;
        var res = ot.acidRes || 0;
        if (Math.random() < (1 - res) * 0.5) {
          this.set(nx2, ny2, M.SMOKE, 90);
          if (Math.random() < 0.5) this.set(x, y, M.EMPTY);
          this.noteRecipe('acid');
          return;
        }
        continue;
      }

      if (mat === M.STEAM) {
        if ((om === M.ICE || om === M.SNOW) && Math.random() < 0.14) { this.set(x, y, M.WATER, 10); continue; }
      }
      if (mat === M.MUD && om === M.LAVA) { this.set(x, y, M.BRICK, 650); this.noteRecipe('brick'); continue; }
      if (mat === M.ASH && om === M.LAVA) { this.set(x, y, M.STONE, 800); continue; }
      if (mat === M.WOOD && om === M.LAVA) { this.set(x, y, M.FIRE, 700); continue; }
      if (mat === M.GUNPOWDER && (om === M.FIRE || om === M.LAVA)) { this.explode(x, y, 7); return; }
      if (mat === M.SNOW && om === M.LAVA) { this.set(x, y, M.STEAM, 160); continue; }
    }
  };

  /* ---------------- тепло ---------------- */

  World.prototype.conduct = function (i, x, y) {
    var W = this.W, H = this.H, t = this.tmp[i], mt = MATS[this.mat[i]];
    if (t > AMBIENT - 0.4 && t < AMBIENT + 0.4) {
      var hot = false;
      if (x > 0 && Math.abs(this.tmp[i - 1] - AMBIENT) > 6) hot = true;
      else if (x + 1 < W && Math.abs(this.tmp[i + 1] - AMBIENT) > 6) hot = true;
      else if (y > 0 && Math.abs(this.tmp[i - W] - AMBIENT) > 6) hot = true;
      else if (y + 1 < H && Math.abs(this.tmp[i + W] - AMBIENT) > 6) hot = true;
      if (!hot) { this.tmp[i] = AMBIENT; return; }
    }
    var cap = mt.hcap || 1;
    for (var k = 0; k < 2; k++) {
      var d = (Math.random() * 4) | 0;
      var nx = x + (d === 0 ? 1 : d === 1 ? -1 : 0);
      var ny = y + (d === 2 ? 1 : d === 3 ? -1 : 0);
      if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
      var j = ny * W + nx, om = this.mat[j];
      if (om === M.EMPTY) {
        // воздух хранит тепло; потеря — только малой долей за шаг
        t += (AMBIENT - t) * 0.00035;
        continue;
      }
      var oc = MATS[om].cond < mt.cond ? MATS[om].cond : mt.cond;
      var ocap = MATS[om].hcap || 1;
      var flow = (this.tmp[j] - t) * oc * 0.16;
      // ограничение перепада за шаг
      var maxD = 26;
      if (flow > maxD) flow = maxD;
      if (flow < -maxD) flow = -maxD;
      t += flow / cap;
      this.tmp[j] -= flow / ocap * 0.9;
    }
    // остывание: у лавы/расплавов почти нулевое, у обычных — слабое
    t += (AMBIENT - t) * mt.cool;
    if (t > 1600) t = 1600;
    if (t < -60) t = -60;
    this.tmp[i] = t;
  };

  /* ---------------- шаг ---------------- */

  World.prototype.step = function () {
    this.frame++;
    var W = this.W, H = this.H, n = this.n;
    var mat = this.mat, flags = this.flags, mt = MATS;
    var i, x, y, m, prop;

    for (i = 0; i < n; i++) flags[i] &= ~F_MOVED;

    var ltr = (this.frame & 1) === 0;
    for (y = H - 1; y >= 0; y--) {
      var row = y * W;
      var start = ltr ? 0 : W - 1;
      var end = ltr ? W : -1;
      var inc = ltr ? 1 : -1;
      for (x = start; x !== end; x += inc) {
        i = row + x;
        m = mat[i];
        if (m === M.EMPTY) continue;
        if (flags[i] & F_MOVED) continue;
        prop = mt[m];

        if (((x + y + this.frame) & 1) === 0) this.conduct(i, x, y);

        var anchored = flags[i] & F_ANCHOR;
        var type = prop.type;

        if (m === M.FIRE) {
          var life = this.aux[i];
          if (life > 0) { this.aux[i] = life - 1; }
          this.tmp[i] = Math.max(this.tmp[i], 520);
          if (life <= 1) {
            this.set(x, y, Math.random() < 0.12 ? M.SMOKE : M.EMPTY, 110);
            continue;
          }
          // сначала поджигаем соседей — иначе пламя успевает улететь вверх
          this.reactAt(i, x, y);
          if (this.mat[i] !== M.FIRE) continue;
          var fuelNear = this.neighborFuel(x, y);
          if (fuelNear) {
            // есть что гореть — пламя держится на месте и жрёт топливо
            this.igniteNeighbors(x, y, 0.55);
            this.tmp[i] = Math.max(this.tmp[i], 640);
            continue;
          }
          // топлива нет — язык пламени поднимается вверх и гаснет
          if (Math.random() < 0.55) this.doGas(i, x, y);
          if ((this.flags[i] & F_MOVED) === 0) this.aux[i] = life > 6 ? life - 2 : life;
          continue;
        }

        if (anchored) {
          this.reactAt(i, x, y);
          continue;
        }

        if (type === MT.POWDER) {
          if (this.doPowder(i, x, y)) continue;
        } else if (type === MT.LIQUID) {
          if (this.doLiquid(i, x, y)) continue;
        } else if (type === MT.GAS) {
          this.doGas(i, x, y);
          if (flags[i] & F_MOVED) continue;
        }

        this.reactAt(i, x, y);
      }
    }
    this.dirty = true;
  };

  /* ---------------- сохранение ---------------- */

  World.prototype.serialize = function () {
    var out = [], n = this.n, mat = this.mat;
    var run = mat[0], len = 1;
    for (var i = 1; i < n; i++) {
      if (mat[i] === run && len < 65535) { len++; continue; }
      out.push(run, len); run = mat[i]; len = 1;
    }
    out.push(run, len);
    var bytes = new Uint8Array(out.length * 2);
    for (var k = 0; k < out.length; k++) {
      bytes[k] = out[k] & 255;
      bytes[out.length + k] = (out[k] >> 8) & 255;
    }
    var s = '';
    for (var b = 0; b < bytes.length; b += 0x8000) {
      s += String.fromCharCode.apply(null, bytes.subarray(b, b + 0x8000));
    }
    return { w: this.W, h: this.H, data: btoa(s) };
  };

  World.prototype.deserialize = function (obj) {
    if (!obj || obj.w !== this.W || obj.h !== this.H) return false;
    var bin = atob(obj.data), bytes = new Uint8Array(bin.length);
    for (var q = 0; q < bin.length; q++) bytes[q] = bin.charCodeAt(q);
    var n = this.n, mat = this.mat, p = 0;
    var half = bytes.length >> 1;
    for (var i = 0; i < half; i += 2) {
      var m = bytes[i] | (bytes[half + i] << 8);
      var val = bytes[i + 1] | (bytes[half + i + 1] << 8);
      for (var k = 0; k < val && p < n; k++) mat[p++] = m;
    }
    while (p < n) mat[p++] = M.EMPTY;
    for (var j = 0; j < n; j++) {
      if (mat[j] !== M.EMPTY && !MATS[mat[j]]) mat[j] = M.EMPTY;
      this.tmp[j] = mat[j] !== M.EMPTY ? (MATS[mat[j]].heat || AMBIENT) : AMBIENT;
      this.flags[j] = 0;
      this.aux[j] = 0;
      this.var8[j] = hash8((j % this.W) >> 2, ((j / this.W) | 0) >> 2);
    }
    this.dirty = true;
    return true;
  };

  /* ---------------- генерация мира ---------------- */

  function noise1(x, f, s) {
    return Math.sin(x * f + s) * 0.5 + Math.sin(x * f * 2.31 + s * 1.7) * 0.3 + Math.sin(x * f * 4.07 + s * 0.4) * 0.2;
  }

  // Настоящий 2D value-noise: жилы, пятна, облака
  function hash2(x, y, s) {
    var h = (x * 374761393 + y * 668265263 + s * 1442695041) | 0;
    h = (h ^ (h >> 13)) * 1274126177 | 0;
    return ((h ^ (h >> 16)) >>> 0) / 4294967295;
  }

  function vnoise(x, y, s) {
    var xi = Math.floor(x), yi = Math.floor(y);
    var xf = x - xi, yf = y - yi;
    var u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    var a = hash2(xi, yi, s), b = hash2(xi + 1, yi, s);
    var c = hash2(xi, yi + 1, s), d = hash2(xi + 1, yi + 1, s);
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v;
  }

  function fbm2(x, y, s) {
    return vnoise(x, y, s) * 0.55 + vnoise(x * 2.13, y * 2.13, s + 17) * 0.28 + vnoise(x * 4.31, y * 4.31, s + 41) * 0.17;
  }

  // fbm2 реально живёт в диапазоне ~0.10..0.40 — растягиваем на [0..1]
  function fbmSpread(x, y, s) {
    var v = fbm2(x, y, s);
    return Math.max(0, Math.min(1, (v - 0.115) / 0.265));
  }

  World.prototype.generate = function (kind) {
    var W = this.W, H = this.H, x, y;
    this.mat.fill(M.EMPTY);
    this.flags.fill(0);
    this.aux.fill(0);
    this.tmp.fill(AMBIENT);
    var seed = Math.random() * 1000;

    if (kind === 'empty') {
      for (x = 0; x < W; x++) {
        for (y = H - 3; y < H; y++) this.set(x, y, M.STONE);
      }
      this.dirty = true;
      return;
    }

    if (kind === 'volcano') {
      var ground = H * 0.74;
      for (x = 0; x < W; x++) {
        var ridge = ground + noise1(x, 0.02, seed) * 16;
        var coneTop = H * 0.30 + Math.abs(x - W * 0.5) * (H * 0.85 / W);
        var top = Math.floor(Math.min(ridge, coneTop));
        for (y = top; y < H; y++) {
          var dep = y - top;
          var mm = dep < 4 ? M.DIRT : M.STONE;
          if (dep > 8 && Math.random() < 0.02) mm = M.GRAVEL;
          this.set(x, y, mm);
        }
        if (Math.abs(x - W * 0.5) < 3) {
          for (y = top; y < top + 24; y++) this.set(x, y, M.LAVA, 1300);
        }
      }
      this.dirty = true;
      return;
    }

    if (kind === 'desert') {
      for (x = 0; x < W; x++) {
        var dune = H * 0.6 + noise1(x, 0.014, seed) * 26;
        for (y = Math.floor(dune); y < H; y++) {
          var dd = y - dune;
          this.set(x, y, dd < 12 ? M.SAND : M.STONE);
        }
      }
      this.dirty = true;
      return;
    }

    if (kind === 'ice') {
      for (x = 0; x < W; x++) {
        var icy = H * 0.55 + noise1(x, 0.016, seed) * 20;
        for (y = Math.floor(icy); y < H; y++) {
          var di = y - icy;
          this.set(x, y, di < 3 ? M.SNOW : di < 8 ? M.ICE : M.STONE, -14);
        }
      }
      for (var w2 = 0; w2 < 3; w2++) {
        var wx = (W * (0.2 + Math.random() * 0.6)) | 0;
        var wy = (H * 0.5) | 0;
        this.paint(wx, wy, 14, M.WATER, false);
      }
      this.dirty = true;
      return;
    }

    // ---------- остров (по умолчанию) ----------
    var surf = Math.floor(H * 0.55);      // средний уровень земли
    var baseY = new Array(W);
    var land = new Array(W);              // 1 = суша
    var i, k;

    for (x = 0; x < W; x++) {
      // лёгкие холмы: ±5% высоты
      var h = noise1(x, 0.018, seed) * (H * 0.035) + noise1(x, 0.045, seed * 2.3) * (H * 0.012);
      baseY[x] = Math.round(surf - h);
      land[x] = 1;
    }

    // пара гор — конус с плавными склонами
    var peaks = 1 + ((Math.random() * 2) | 0);
    for (var pk = 0; pk < peaks; pk++) {
      var pc = Math.floor(W * (0.18 + Math.random() * 0.64));
      var ph = H * (0.10 + Math.random() * 0.08);
      var pw = W * (0.13 + Math.random() * 0.08);
      for (x = 0; x < W; x++) {
        var dxp = (x - pc) / pw;
        if (Math.abs(dxp) > 3) continue;
        var prof = Math.exp(-dxp * dxp * 1.15) * ph;
        baseY[x] -= Math.round(prof);
      }
    }

    // чаша озера, вырезанная в суше
    var lakeW = W * (0.14 + Math.random() * 0.05);
    var lakeC = W * (0.3 + Math.random() * 0.4);
    var waterLevel = surf + Math.round(H * 0.012);
    var lakeDepth = H * 0.13;
    var isLake = new Array(W);
    for (x = 0; x < W; x++) {
      var lx = (x - lakeC) / lakeW;
      if (Math.abs(lx) < 1.25) {
        // берег и дно: плавная парабола, без вертикальных стенок
        var t = Math.min(1, Math.abs(lx) / 1.15);
        var bowl = Math.max(0, 1 - t * t);
        var bed = waterLevel + Math.round(Math.pow(bowl, 1.35) * lakeDepth);
        if (baseY[x] < bed) baseY[x] = bed;
        if (Math.abs(lx) < 1) isLake[x] = 1;
      }
    }

    // генерация породы (гравий — жилами, а не одиночными крупинками)
    for (x = 0; x < W; x++) {
      var topY = baseY[x];
      var inLake = !!isLake[x];
      for (y = topY; y < H; y++) {
        var dy = y - topY;
        var mm;
        if (inLake && dy < 4) mm = M.SAND;         // песчаное дно
        else if (dy < 6) mm = inLake ? M.SAND : M.DIRT;
        else mm = M.STONE;
        if (dy > 10) {
          // тонкие гравийные жилы: линия уровня шума, а не пятна
          var vx = x * 0.045, vy = y * 0.045;
          var vv = fbmSpread(vx, vy, seed * 7.3);
          if (Math.abs(vv - 0.5) < 0.035) mm = M.GRAVEL;
        }
        this.set(x, y, mm);
      }
    }

    // вода в чаше (до уровня)
    for (x = 0; x < W; x++) {
      if (!isLake[x]) continue;
      for (y = waterLevel; y < baseY[x]; y++) {
        if (y >= 0 && y < H) this.set(x, y, M.WATER, 3);
      }
    }

    // деревья на суше
    var trees = 2 + ((Math.random() * 2) | 0);
    for (var t2 = 0; t2 < trees; t2++) {
      var tx = Math.floor(W * (0.05 + Math.random() * 0.9));
      if (tx < 6 || tx >= W - 6 || isLake[tx]) continue;
      var clear = true;
      for (var q = -3; q <= 3; q++) if (isLake[tx + q]) clear = false;
      if (!clear) continue;
      var ty = baseY[tx] - 1;
      var th = 13 + ((Math.random() * 11) | 0);
      for (var hh = 1; hh <= th; hh++) {
        if (ty - hh < 2) break;
        this.set(tx, ty - hh, M.WOOD);
      }
      var crownY = ty - th;
      var cr = 5 + ((Math.random() * 2) | 0);
      for (var dy2 = -cr - 1; dy2 <= cr; dy2++) {
        for (var dx2 = -cr; dx2 <= cr; dx2++) {
          var dist = dx2 * dx2 * 0.85 + dy2 * dy2;
          if (dist > cr * cr) continue;
          var px = tx + dx2, py = crownY + dy2;
          if (this.inside(px, py) && this.mat[py * W + px] === M.EMPTY) {
            this.set(px, py, M.PLANT);
          }
        }
      }
    }

    // снег на самых высоких вершинах
    var highest = H;
    for (x = 0; x < W; x++) if (baseY[x] < highest) highest = baseY[x];
    if (surf - highest > H * 0.09) {
      for (x = 0; x < W; x++) {
        if (baseY[x] < highest + H * 0.05) {
          this.set(x, baseY[x], M.SNOW, -10);
          if (Math.random() < 0.45) this.set(x, baseY[x] - 1, M.SNOW, -10);
        }
      }
    }
    this.dirty = true;
  };

  /* Статистика по материалам  /* Статистика по материалам  /* Статистика по материалам — для HUD и тестов */
  World.prototype.count = function () {
    var c = {}, n = this.n, mat = this.mat;
    for (var i = 0; i < n; i++) { var m = mat[i]; c[m] = (c[m] || 0) + 1; }
    return c;
  };

  global.World = World;
  global.F_ANCHOR = F_ANCHOR;
})(typeof window !== 'undefined' ? window : globalThis);
