/* ===========================================================
   ПЕСОЧНИЦА — рендер, ввод, интерфейс
   =========================================================== */
(function () {
  'use strict';

  var M = window.M, MATS = window.MATS, MT = window.MT, RECIPES = window.RECIPES;

  var view = document.getElementById('view');
  var glow = document.getElementById('glow');
  var stage = document.getElementById('stage');
  var vctx = view.getContext('2d', { alpha: false });
  var gctx = glow.getContext('2d');

  var SIM_X = 176, SIM_Y = 320;     // логическое разрешение мира
  var world = null;
  var cellImg = null, cellData = null;
  var glowImg = null, glowData = null;
  var cssScale = 1;                  // сколько CSS-пикселей на клетку

  var brushR = 4;
  var current = M.SAND;
  var category = 'earth';
  var tool = 'paint';                // paint | erase
  var anchor = false;
  var paused = false;
  var stepAcc = 0, lastT = 0, fpsAcc = 0, fpsFrames = 0, fpsShown = 0;
  var STEPS_PER_SEC = 60;

  var CATS = [
    { id: 'earth', name: 'Земля', color: '#d9b06a' },
    { id: 'water', name: 'Вода', color: '#4aa3ef' },
    { id: 'fire', name: 'Огонь', color: '#ff7a2f' },
    { id: 'life', name: 'Жизнь', color: '#6fcf5a' },
    { id: 'solid', name: 'Блоки', color: '#a8b0bd' }
  ];

  /* ---------- инициализация ---------- */
  function resize() {
    var r = stage.getBoundingClientRect();
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = Math.max(1, Math.floor(r.width * dpr));
    var h = Math.max(1, Math.floor(r.height * dpr));
    if (view.width !== w || view.height !== h) {
      view.width = w; view.height = h;
      glow.width = w; glow.height = h;
    }
    // размер мира под аспект экрана, с ограничением по числу клеток
    var aspect = r.height / Math.max(1, r.width);
    var sy = Math.round(SIM_X * aspect);
    var maxCells = 62000;
    if (SIM_X * sy > maxCells) {
      var k = Math.sqrt(maxCells / (SIM_X * sy));
      SIM_X = Math.max(120, Math.round(SIM_X * k));
      sy = Math.round(SIM_Y * k);
    }
    cssScale = r.width / SIM_X;

    if (!world || Math.abs(world.W - SIM_X) > 2 || world.H !== sy) {
      var old = world ? world.serialize() : null;
      world = new World(SIM_X, sy);
      world.onRecipe = onRecipe;
      world.onEvent = onEvent;
      if (old) world.deserialize(old);
      else world.generate('island');
      allocBuffers();
    }
  }

  function allocBuffers() {
    cellImg = document.createElement('canvas');
    cellImg.width = world.W; cellImg.height = world.H;
    var c = cellImg.getContext('2d');
    cellData = c.createImageData(world.W, world.H);

    glowImg = document.createElement('canvas');
    glowImg.width = world.W; glowImg.height = world.H;
    var g = glowImg.getContext('2d');
    glowData = g.createImageData(world.W, world.H);
    world.dirty = true;
  }

  /* ---------- палитра: цвет материала с вариацией ---------- */
  function render() {
    var W = world.W, H = world.H;
    if (!cellData || cellData.width !== W) allocBuffers();
    PixelRender.renderPixels(world, cellData.data, glowData.data);
    cellImg.getContext('2d').putImageData(cellData, 0, 0);
    glowImg.getContext('2d').putImageData(glowData, 0, 0);

    vctx.imageSmoothingEnabled = false;
    vctx.drawImage(cellImg, 0, 0, view.width, view.height);

    gctx.clearRect(0, 0, glow.width, glow.height);
    gctx.imageSmoothingEnabled = true;
    gctx.globalCompositeOperation = 'lighter';
    gctx.filter = 'blur(' + Math.max(1.5, cssScale * 2.2) + 'px)';
    gctx.drawImage(glowImg, 0, 0, glow.width, glow.height);
    gctx.filter = 'none';
    gctx.globalCompositeOperation = 'source-over';

    drawCursor();
  }

  function drawCursor() {
    if (!pointer.active) return;
    var px = pointer.x * cssScale, py = pointer.y * cssScale;
    var rr = brushR * cssScale;
    vctx.save();
    vctx.strokeStyle = tool === 'erase' ? 'rgba(255,110,100,.95)' : 'rgba(255,255,255,.85)';
    vctx.lineWidth = Math.max(1.5, cssScale * 0.6);
    vctx.beginPath();
    vctx.arc(px, py, rr, 0, Math.PI * 2);
    vctx.stroke();
    vctx.strokeStyle = 'rgba(0,0,0,.45)';
    vctx.lineWidth = Math.max(2.5, cssScale * 1.2);
    vctx.globalAlpha = .5;
    vctx.beginPath();
    vctx.arc(px, py, rr + 1.2, 0, Math.PI * 2);
    vctx.stroke();
    vctx.restore();
  }

  /* ---------- основной цикл ---------- */
  function loop(t) {
    requestAnimationFrame(loop);
    if (!lastT) lastT = t;
    var dt = Math.min(80, t - lastT);
    lastT = t;

    if (!paused) {
      stepAcc += dt;
      var stepMs = 1000 / STEPS_PER_SEC;
      var guard = 0;
      while (stepAcc >= stepMs && guard < 3) {
        world.step();
        stepAcc -= stepMs;
        guard++;
      }
      if (stepAcc > stepMs * 3) stepAcc = 0;
    }

    if (world.dirty) {
      render();
      world.dirty = false;
    } else if (pointer.active) {
      render();
    }

    fpsAcc += dt; fpsFrames++;
    if (fpsAcc >= 500) {
      fpsShown = Math.round(fpsFrames * 1000 / fpsAcc);
      fpsAcc = 0; fpsFrames = 0;
      document.getElementById('fps').innerHTML = '<b>' + fpsShown + '</b> FPS · ' + countAlive();
    }
  }

  function countAlive() {
    var c = 0, mat = world.mat;
    for (var i = 0; i < world.n; i++) if (mat[i] !== 0) c++;
    if (c > 99999) return '∞ частиц';
    return (c / 1000).toFixed(1).replace('.0', '') + 'к частиц';
  }

  /* ---------- ввод ---------- */
  var pointer = { active: false, x: 0, y: 0, id: null };

  function stageToCell(clientX, clientY) {
    var r = stage.getBoundingClientRect();
    var x = Math.floor((clientX - r.left) / cssScale);
    var y = Math.floor((clientY - r.top) / cssScale);
    return {
      x: Math.max(0, Math.min(world.W - 1, x)),
      y: Math.max(0, Math.min(world.H - 1, y))
    };
  }

  function applyBrush(cx, cy) {
    if (tool === 'erase') world.erase(cx, cy, brushR);
    else world.paint(cx, cy, brushR, current, anchor);
  }

  function onDown(e) {
    if (e.button !== undefined && e.button !== 0) return;
    var p = stageToCell(e.clientX, e.clientY);
    pointer.active = true; pointer.iX = p.x; pointer.iY = p.y;
    pointer.x = p.x; pointer.y = p.y;
    applyBrush(p.x, p.y);
    e.preventDefault();
  }

  function onMove(e) {
    var p = stageToCell(e.clientX, e.clientY);
    pointer.x = p.x; pointer.y = p.y;
    if (!pointer.active) { world.dirty = true; return; }
    // линия от прошлой точки
    var x0 = pointer.iX, y0 = pointer.iY, x1 = p.x, y1 = p.y;
    var dx = x1 - x0, dy = y1 - y0;
    var steps = Math.max(Math.abs(dx), Math.abs(dy));
    if (steps > 0) {
      for (var s = 1; s <= steps; s++) {
        applyBrush(Math.round(x0 + dx * s / steps), Math.round(y0 + dy * s / steps));
      }
    } else applyBrush(x1, y1);
    pointer.iX = x1; pointer.iY = y1;
    e.preventDefault();
  }

  function onUp() {
    pointer.active = false;
    world.dirty = true;
  }

  stage.addEventListener('pointerdown', onDown);
  stage.addEventListener('pointermove', function (e) {
    if (e.pointerType === 'mouse' && !(e.buttons & 1)) {
      var p = stageToCell(e.clientX, e.clientY);
      pointer.x = p.x; pointer.y = p.y; world.dirty = true; return;
    }
    onMove(e);
  });
  window.addEventListener('pointerup', onUp);
  window.addEventListener('pointercancel', onUp);
  stage.addEventListener('pointerleave', function () { if (!pointer.active) { pointer.active = false; world.dirty = true; } });
  stage.addEventListener('contextmenu', function (e) { e.preventDefault(); });

  window.addEventListener('keydown', function (e) {
    if (e.key === ' ') { e.preventDefault(); togglePause(); }
    if (e.key === 'e' || e.key === 'E') setErase(!(tool === 'erase'));
    if (e.key === 'a' || e.key === 'A') toggleAnchor();
    if (e.key === '[') setBrush(brushR - 1);
    if (e.key === ']') setBrush(brushR + 1);
  });

  /* ---------- панель материалов ---------- */
  function catMaterials(id) {
    var out = [];
    for (var i = 1; i < MATS.length; i++) {
      var m = MATS[i];
      if (m && m.build && m.cat === id) out.push(i);
    }
    return out;
  }

  function materialIcon(id, size) {
    var m = MATS[id];
    var c = document.createElement('canvas');
    c.width = size; c.height = size;
    var g = c.getContext('2d');
    var cols = m.color;
    var cell = size / 7;
    g.fillStyle = '#151a21';
    g.fillRect(0, 0, size, size);
    for (var y = 0; y < 7; y++) {
      for (var x = 0; x < 7; x++) {
        // мягкий круглый силуэт — узнаваемый «образец»
        var dx = x - 3, dy = y - 3;
        if (dx * dx + dy * dy > 11 && m.type !== MT.SOLID) continue;
        var col = cols[(Math.random() * cols.length) | 0];
        if (m.type === MT.SOLID) col = cols[(x + y * 3 + ((Math.random() * 2) | 0)) % cols.length];
        var sh = (Math.random() - 0.5) * 26;
        g.fillStyle = 'rgb(' + clamp8(col[0] + sh) + ',' + clamp8(col[1] + sh) + ',' + clamp8(col[2] + sh) + ')';
        g.fillRect(x * cell, y * cell, Math.ceil(cell), Math.ceil(cell));
      }
    }
    // блик
    g.globalAlpha = .22;
    g.fillStyle = '#fff';
    g.beginPath();
    g.arc(size * 0.34, size * 0.3, size * 0.2, 0, Math.PI * 2);
    g.fill();
    g.globalAlpha = 1;
    return c;
  }

  function clamp8(v) { return v < 0 ? 0 : v > 255 ? 255 : v | 0; }

  function buildCats() {
    var box = document.getElementById('cats');
    box.innerHTML = '';
    CATS.forEach(function (c) {
      var el = document.createElement('div');
      el.className = 'cat' + (c.id === category ? ' on' : '');
      el.dataset.cat = c.id;
      el.innerHTML = '<span class="dot" style="background:' + c.color + '"></span>' + c.name;
      el.addEventListener('click', function () {
        category = c.id;
        if (catMaterials(category).indexOf(current) < 0) current = catMaterials(category)[0];
        buildCats(); buildMats(); setErase(false);
      });
      box.appendChild(el);
    });
  }

  function buildMats() {
    var box = document.getElementById('mats');
    box.innerHTML = '';
    var list = catMaterials(category);
    if (list.indexOf(current) < 0) current = list[0];
    list.forEach(function (id) {
      var m = MATS[id];
      var el = document.createElement('div');
      el.className = 'mat' + (id === current ? ' on' : '');
      el.dataset.mat = id;
      var ic = materialIcon(id, 68);
      el.appendChild(ic);
      var sp = document.createElement('span');
      sp.textContent = m.name;
      el.appendChild(sp);
      el.addEventListener('click', function () {
        current = id;
        setErase(false);
        var nodes = box.querySelectorAll('.mat');
        for (var k = 0; k < nodes.length; k++) nodes[k].classList.toggle('on', +nodes[k].dataset.mat === id);
      });
      box.appendChild(el);
    });
  }

  /* ---------- инструменты ---------- */
  function setBrush(v) {
    brushR = Math.max(1, Math.min(14, v | 0));
    document.getElementById('brush').value = brushR;
    document.getElementById('brush-val').textContent = brushR;
    world.dirty = true;
  }

  function togglePause() {
    paused = !paused;
    document.getElementById('pause-lbl').textContent = paused ? 'Дальше' : 'Пауза';
    document.getElementById('ico-pause').innerHTML = paused
      ? '<path d="M7 4.5v15l13-7.5z" fill="currentColor" stroke="none"/>'
      : '<path d="M9 5v14M15 5v14"/>';
    document.getElementById('tool-pause').classList.toggle('on', paused);
  }

  function setErase(on) {
    tool = on ? 'erase' : 'paint';
    document.getElementById('tool-erase').classList.toggle('on', on);
    world.dirty = true;
  }

  function toggleAnchor() {
    anchor = !anchor;
    document.getElementById('tool-anchor').classList.toggle('on', anchor);
  }

  document.getElementById('tool-pause').addEventListener('click', togglePause);
  document.getElementById('tool-erase').addEventListener('click', function () { setErase(tool !== 'erase'); });
  document.getElementById('tool-anchor').addEventListener('click', toggleAnchor);
  document.getElementById('brush').addEventListener('input', function (e) { setBrush(+e.target.value); });

  /* ---------- модалки ---------- */
  function openSheet(id) { document.getElementById(id).classList.add('show'); }
  function closeSheet(id) { document.getElementById(id).classList.remove('show'); }

  document.querySelectorAll('[data-close]').forEach(function (b) {
    b.addEventListener('click', function () { closeSheet(b.dataset.close); });
  });
  document.querySelectorAll('.overlay').forEach(function (ov) {
    ov.addEventListener('click', function (e) { if (e.target === ov) ov.classList.remove('show'); });
  });

  document.getElementById('btn-recipe').addEventListener('click', function () {
    buildRecipeList(); openSheet('ov-recipe');
  });
  document.getElementById('btn-settings').addEventListener('click', function () { openSheet('ov-world'); });

  document.querySelectorAll('[data-world]').forEach(function (b) {
    b.addEventListener('click', function () {
      world.generate(b.dataset.world);
      world.recipesSeen = world.recipesSeen || {};
      closeSheet('ov-world');
      showToast('🌍', 'Мир создан: ' + b.textContent.trim().slice(2));
    });
  });

  document.querySelector('[data-action="save"]').addEventListener('click', function () {
    try {
      localStorage.setItem('sandbox.world', JSON.stringify(world.serialize()));
      showToast('💾', 'Мир сохранён');
    } catch (err) { showToast('⚠️', 'Не удалось сохранить'); }
    closeSheet('ov-world');
  });

  document.querySelector('[data-action="load"]').addEventListener('click', function () {
    try {
      var raw = localStorage.getItem('sandbox.world');
      if (!raw) { showToast('📂', 'Сохранений пока нет'); return; }
      world.deserialize(JSON.parse(raw));
      showToast('📂', 'Мир загружен');
    } catch (err) { showToast('⚠️', 'Файл повреждён'); }
    closeSheet('ov-world');
  });

  /* ---------- реакции ---------- */
  function loadSeen() {
    try {
      var s = localStorage.getItem('sandbox.recipes');
      if (s) world.recipesSeen = JSON.parse(s) || {};
    } catch (e) { }
    if (window.__seen) world.recipesSeen = window.__seen;
  }

  function onRecipe(id) {
    var r = RECIPES.filter(function (x) { return x.id === id; })[0];
    try { localStorage.setItem('sandbox.recipes', JSON.stringify(world.recipesSeen)); } catch (e) { }
    if (r) showToast('⚗️', 'Новое: ' + r.text);
  }

  var toastTimer = null;
  function showToast(em, text) {
    var t = document.getElementById('toast');
    t.querySelector('.em').textContent = em;
    document.getElementById('toast-txt').textContent = text;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.classList.remove('show'); }, 2600);
  }

  function buildRecipeList() {
    var box = document.getElementById('rec-list');
    box.innerHTML = '';
    var found = 0;
    RECIPES.forEach(function (r) {
      var seen = !!world.recipesSeen[r.id];
      if (seen) found++;
      var el = document.createElement('div');
      el.className = 'rec ' + (seen ? 'found' : 'locked');
      el.innerHTML = '<div class="badge">' + (seen ? '✓' : '?') + '</div>' +
        '<div class="txt"><b>' + (seen ? r.title : 'Не открыто') + '</b>' +
        '<small>' + (seen ? r.text : 'Смешай материалы, чтобы узнать') + '</small></div>';
      box.appendChild(el);
    });
    document.getElementById('rec-count').textContent = found;
    document.getElementById('rec-total').textContent = RECIPES.length;
  }

  function onEvent(kind, x, y, p) {
    if (kind === 'boom' && navigator.vibrate) {
      try { navigator.vibrate(24); } catch (e) { }
    }
  }

  /* ---------- старт ---------- */
  function boot() {
    PixelRender.init();
    window.__sandbox = {
      world: function () { return world; },
      render: function () { render(); },
      setBrush: setBrush,
      pick: function (m) { current = m; },
      canvas: function () { return cellImg; },
      glowCanvas: function () { return glowImg; },
      step: function (n2) { for (var q = 0; q < (n2 || 1); q++) world.step(); }
    };
    buildCats();
    resize();
    buildMats();
    setBrush(4);
    loadSeen();
    window.world = world;
    window.requestAnimationFrame(loop);
    setTimeout(function () {
      document.getElementById('boot').classList.add('hide');
      showToast('👋', 'Ставь блоки пальцем. Смешивай — получишь реакции');
    }, 320);

    var rt = null;
    window.addEventListener('resize', function () {
      clearTimeout(rt);
      rt = setTimeout(function () { resize(); buildMats(); }, 140);
    });
    window.addEventListener('orientationchange', function () {
      setTimeout(function () { resize(); buildMats(); }, 260);
    });

    // сохраняем мир при уходе в фон
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) {
        try { localStorage.setItem('sandbox.world', JSON.stringify(world.serialize())); } catch (e) { }
      }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
