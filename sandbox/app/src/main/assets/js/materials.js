/* ===========================================================
   ПЕСОЧНИЦА — материалы и их свойства
   Классический falling-sand автомат: типы клеток, плотности
   (всплытие/утопание), теплоёмкость и химические реакции.
   =========================================================== */
(function (global) {
  'use strict';

  var T_EMPTY = 0, T_SOLID = 1, T_POWDER = 2, T_LIQUID = 3, T_GAS = 4, T_FIRE = 5;

  var M = {
    EMPTY: 0, STONE: 1, DIRT: 2, SAND: 3, GRAVEL: 4, SNOW: 5, SALT: 6, ASH: 7,
    GUNPOWDER: 8, SEED: 9, WOOD: 10, METAL: 11, GLASS: 12, OBSIDIAN: 13,
    CRYSTAL: 14, BRICK: 15, ICE: 16, PLANT: 17, WATER: 18, SALTWATER: 19,
    OIL: 20, ACID: 21, LAVA: 22, MOLTEN_METAL: 23, MOLTEN_GLASS: 24, MUD: 25,
    STEAM: 26, SMOKE: 27, FIRE: 28
  };

  var MATS = [];

  MATS[0] = {
    id: 0, key: 'empty', name: 'Пусто', type: T_EMPTY, density: 0.001,
    disp: 0, fric: 0, flam: 0, cond: 0.25, hcap: 1, heat: 0, cool: 0.01,
    color: [[20, 22, 28]], glow: 0, glowColor: null, burnTime: 0, ashChance: 0,
    acidRes: 1, build: false, cat: 'none', hint: ''
  };

  function def(id, key, name, type, o) {
    MATS[id] = {
      id: id, key: key, name: name, type: type,
      density: o.d || 1,
      disp: o.disp || 0,
      fric: o.fric === undefined ? 0.1 : o.fric,
      flam: o.flam || 0,
      cond: o.cond === undefined ? 0.1 : o.cond,
      hcap: o.hcap || 1,
      heat: o.heat || 0,
      cool: o.cool === undefined ? 0.0002 : o.cool,
      color: o.color || [[200, 200, 200]],
      glow: o.glow || 0,
      glowColor: o.glowColor || null,
      burnTime: o.burnTime || 0,
      ashChance: o.ashChance || 0,
      acidRes: o.acidRes || 0,
      build: !!o.build,
      cat: o.cat || 'earth',
      hint: o.hint || ''
    };
  }

  /* ---------- Твёрдые ---------- */
  def(M.STONE, 'stone', 'Камень', T_SOLID, {
    d: 2.6, cond: 0.35, hcap: 2.6, acidRes: 0.45,
    color: [[124, 128, 142], [138, 142, 156], [110, 114, 128], [150, 153, 166]],
    build: true, cat: 'solid', hint: 'Основа гор. Плавится только в лаве.'
  });
  def(M.WOOD, 'wood', 'Дерево', T_SOLID, {
    d: 0.8, cond: 0.12, hcap: 2.0, flam: 0.55, burnTime: 90, ashChance: 0.25, acidRes: 0.2,
    color: [[176, 120, 58], [160, 106, 48], [190, 134, 68], [146, 94, 40]],
    build: true, cat: 'solid', hint: 'Горит и превращается в пепел.'
  });
  def(M.METAL, 'metal', 'Металл', T_SOLID, {
    d: 3.0, cond: 0.95, hcap: 1.4, acidRes: 0.55,
    color: [[205, 212, 224], [186, 194, 208], [222, 229, 240], [166, 175, 190]],
    build: true, cat: 'solid', hint: 'Отлично проводит тепло. Плавится в лаве.'
  });
  def(M.GLASS, 'glass', 'Стекло', T_SOLID, {
    d: 2.4, cond: 0.22, hcap: 2.2, acidRes: 0.8,
    color: [[168, 224, 238], [196, 238, 248], [142, 206, 226], [216, 248, 252]],
    build: true, cat: 'solid', hint: 'Песок + лава. Плавится при сильном жаре.'
  });
  def(M.OBSIDIAN, 'obsidian', 'Обсидиан', T_SOLID, {
    d: 2.8, cond: 0.2, hcap: 3.0, acidRes: 0.95,
    color: [[52, 44, 68], [64, 54, 82], [40, 34, 54], [78, 66, 98]],
    build: true, cat: 'solid', hint: 'Лава, залитая водой. Не растворяется.'
  });
  def(M.CRYSTAL, 'crystal', 'Кристалл', T_SOLID, {
    d: 2.5, cond: 0.45, hcap: 2.0, acidRes: 0.6, glow: 0.25, glowColor: [90, 200, 235],
    color: [[126, 226, 246], [168, 240, 252], [96, 206, 232], [196, 250, 255]],
    build: true, cat: 'solid', hint: 'Растёт в холодной воде рядом с камнем.'
  });
  def(M.BRICK, 'brick', 'Кирпич', T_SOLID, {
    d: 2.4, cond: 0.3, hcap: 2.0, acidRes: 0.4,
    color: [[192, 92, 72], [172, 78, 60], [210, 110, 88], [156, 66, 50]],
    build: true, cat: 'solid', hint: 'Земля, запечённая лавой.'
  });
  def(M.ICE, 'ice', 'Лёд', T_SOLID, {
    d: 0.92, cond: 0.55, hcap: 2.1, heat: -14, cool: 0.00006, acidRes: 0.3,
    color: [[196, 238, 252], [176, 226, 246], [220, 248, 255], [160, 212, 240]],
    build: true, cat: 'water', hint: 'Замораживает воду вокруг. Тает от тепла.'
  });
  def(M.PLANT, 'plant', 'Растение', T_SOLID, {
    d: 0.7, cond: 0.1, hcap: 1.2, flam: 0.9, burnTime: 30, acidRes: 0.05,
    color: [[96, 196, 72], [118, 214, 88], [78, 176, 58], [136, 228, 104]],
    build: true, cat: 'life', hint: 'Растёт вверх, если рядом вода.'
  });

  /* ---------- Сыпучие ---------- */
  def(M.DIRT, 'dirt', 'Земля', T_POWDER, {
    d: 1.45, fric: 0.35, cond: 0.14, hcap: 1.8, acidRes: 0.05,
    color: [[138, 96, 58], [152, 108, 66], [122, 84, 50], [164, 120, 76]],
    build: true, cat: 'earth', hint: 'С водой превращается в грязь.'
  });
  def(M.SAND, 'sand', 'Песок', T_POWDER, {
    d: 1.65, fric: 0.06, cond: 0.16, hcap: 1.6, acidRes: 0.02,
    color: [[240, 214, 140], [250, 228, 158], [228, 200, 124], [255, 238, 178]],
    build: true, cat: 'earth', hint: 'Лава плавит его в стекло.'
  });
  def(M.GRAVEL, 'gravel', 'Гравий', T_POWDER, {
    d: 1.9, fric: 0.45, cond: 0.2, hcap: 1.7, acidRes: 0.2,
    color: [[158, 156, 162], [142, 140, 148], [174, 172, 178], [128, 126, 134]],
    build: true, cat: 'earth', hint: 'Лежит крутыми горками. Тонет в воде.'
  });
  def(M.SNOW, 'snow', 'Снег', T_POWDER, {
    d: 0.32, fric: 0.08, cond: 0.25, hcap: 1.9, heat: -6, cool: 0.0016, acidRes: 0.02,
    color: [[248, 252, 255], [236, 244, 255], [255, 255, 255], [226, 238, 252]],
    build: true, cat: 'water', hint: 'Тает в воду, плавает на ней.'
  });
  def(M.SALT, 'salt', 'Соль', T_POWDER, {
    d: 1.3, fric: 0.2, cond: 0.2, hcap: 1.5, acidRes: 0.02,
    color: [[244, 244, 248], [232, 232, 240], [252, 252, 255], [220, 220, 232]],
    build: true, cat: 'earth', hint: 'Растворяется в воде — получается солёная вода.'
  });
  def(M.ASH, 'ash', 'Пепел', T_POWDER, {
    d: 0.45, fric: 0.02, cond: 0.1, hcap: 0.9, acidRes: 0.01,
    color: [[104, 102, 108], [118, 116, 112], [90, 88, 94], [132, 130, 126]],
    build: true, cat: 'earth', hint: 'Остаётся от сгоревшего дерева.'
  });
  def(M.GUNPOWDER, 'gunpowder', 'Порох', T_POWDER, {
    d: 1.2, fric: 0.18, cond: 0.12, hcap: 1.1, flam: 1, acidRes: 0.01,
    color: [[62, 62, 70], [76, 76, 84], [50, 50, 58], [88, 88, 96]],
    build: true, cat: 'fire', hint: 'Одна искра — и большой бум.'
  });
  def(M.SEED, 'seed', 'Семена', T_POWDER, {
    d: 0.62, fric: 0.28, cond: 0.08, hcap: 1.1, acidRes: 0.02,
    color: [[182, 142, 72], [196, 158, 80], [166, 128, 62], [210, 174, 96]],
    build: true, cat: 'life', hint: 'На земле и рядом с водой прорастают.'
  });

  /* ---------- Жидкости ---------- */
  def(M.WATER, 'water', 'Вода', T_LIQUID, {
    d: 1.0, disp: 6, cond: 0.55, hcap: 4.2, acidRes: 0,
    color: [[58, 140, 232], [70, 156, 244], [46, 124, 214], [84, 172, 250]],
    build: true, cat: 'water', hint: 'Тушит огонь, остывает лаву, замерзает на морозе.'
  });
  def(M.SALTWATER, 'saltwater', 'Солёная вода', T_LIQUID, {
    d: 1.08, disp: 5, cond: 0.5, hcap: 3.9, acidRes: 0,
    color: [[48, 146, 182], [58, 162, 198], [40, 130, 164], [70, 180, 212]],
    build: true, cat: 'water', hint: 'Выкипает в соль и пар. Замерзает хуже обычной воды.'
  });
  def(M.OIL, 'oil', 'Нефть', T_LIQUID, {
    d: 0.78, disp: 4, cond: 0.15, hcap: 1.9, flam: 0.85, burnTime: 60, acidRes: 0.1,
    color: [[58, 54, 48], [72, 68, 60], [46, 42, 38], [86, 80, 70]],
    build: true, cat: 'fire', hint: 'Плавает на воде и отлично горит.'
  });
  def(M.ACID, 'acid', 'Кислота', T_LIQUID, {
    d: 1.12, disp: 5, cond: 0.35, hcap: 2.4, acidRes: 0,
    color: [[150, 236, 58], [172, 248, 80], [126, 212, 44], [194, 255, 110]],
    glow: 0.2, glowColor: [140, 230, 60],
    build: true, cat: 'fire', hint: 'Растворяет почти всё. Не берёт обсидиан и стекло.'
  });
  def(M.LAVA, 'lava', 'Лава', T_LIQUID, {
    d: 2.1, disp: 2, cond: 0.22, hcap: 11, heat: 1250, cool: 0.00002, acidRes: 0.9,
    color: [[255, 138, 36], [255, 172, 64], [255, 104, 12], [255, 200, 92]],
    glow: 1, glowColor: [255, 120, 30],
    build: true, cat: 'fire', hint: 'Плавит песок в стекло, металл — в расплав. Вода делает её камнем.'
  });
  def(M.MOLTEN_METAL, 'molten_metal', 'Расплав металла', T_LIQUID, {
    d: 2.9, disp: 2, cond: 0.5, hcap: 8, heat: 1450, cool: 0.00004, acidRes: 0.9,
    color: [[255, 190, 120], [255, 210, 156], [255, 166, 88], [255, 228, 186]],
    glow: 0.9, glowColor: [255, 160, 80], build: false, cat: 'fire', hint: ''
  });
  def(M.MOLTEN_GLASS, 'molten_glass', 'Расплав стекла', T_LIQUID, {
    d: 2.3, disp: 1.5, cond: 0.35, hcap: 8, heat: 1350, cool: 0.00004, acidRes: 0.9,
    color: [[255, 226, 176], [255, 240, 210], [255, 208, 140], [255, 250, 232]],
    glow: 0.85, glowColor: [255, 200, 120], build: false, cat: 'fire', hint: ''
  });
  def(M.MUD, 'mud', 'Грязь', T_LIQUID, {
    d: 1.5, disp: 1.2, cond: 0.2, hcap: 2.2, acidRes: 0.02,
    color: [[104, 76, 48], [118, 88, 56], [90, 66, 40], [132, 100, 66]],
    build: true, cat: 'earth', hint: 'Земля + вода. Сохнет обратно в землю.'
  });

  /* ---------- Газы и огонь ---------- */
  def(M.STEAM, 'steam', 'Пар', T_GAS, {
    d: 0.12, cond: 0.3, hcap: 2.0, acidRes: 0,
    color: [[226, 232, 240], [240, 246, 252], [212, 220, 232], [250, 252, 255]],
    build: true, cat: 'water', hint: 'Поднимается вверх и конденсируется в воду.'
  });
  def(M.SMOKE, 'smoke', 'Дым', T_GAS, {
    d: 0.1, cond: 0.12, hcap: 1.4, acidRes: 0,
    color: [[96, 96, 104], [112, 112, 120], [82, 82, 90], [128, 128, 136]],
    build: true, cat: 'fire', hint: 'Продукт горения, рассеивается.'
  });
  def(M.FIRE, 'fire', 'Огонь', T_FIRE, {
    d: 0.05, cond: 0.5, hcap: 0.6, heat: 700, cool: 0.004, glow: 1, acidRes: 0,
    color: [[255, 214, 72], [255, 168, 32], [255, 120, 8], [255, 240, 140]],
    build: true, cat: 'fire', hint: 'Жжёт всё горючее. Боится воды.'
  });

  var AMBIENT = 20;

  /* ---------- Книга реакций ---------- */
  var RECIPES = [
    { id: 'steam_stone', title: 'Пар и камень', text: 'Вода + Лава → Пар + Камень' },
    { id: 'obsidian', title: 'Обсидиан', text: 'Вода + Лава (иногда) → Обсидиан' },
    { id: 'glass', title: 'Стекло', text: 'Песок + Лава → Стекло' },
    { id: 'melt_metal', title: 'Расплав', text: 'Металл + Лава → Расплав металла' },
    { id: 'brick', title: 'Кирпич', text: 'Земля + Лава → Кирпич' },
    { id: 'mud', title: 'Грязь', text: 'Земля + Вода → Грязь' },
    { id: 'saltwater', title: 'Солёная вода', text: 'Соль + Вода → Солёная вода' },
    { id: 'salt', title: 'Соль', text: 'Солёная вода + Жар → Соль + Пар' },
    { id: 'ice', title: 'Лёд', text: 'Вода + Мороз (лёд/снег) → Лёд' },
    { id: 'melt_ice', title: 'Таяние', text: 'Лёд/Снег + Огонь или Лава → Вода' },
    { id: 'steam_cond', title: 'Конденсат', text: 'Пар + Холод → Вода' },
    { id: 'burn', title: 'Костёр', text: 'Дерево + Огонь → Огонь + Пепел' },
    { id: 'oil_fire', title: 'Горящая нефть', text: 'Нефть + Огонь → Пламя' },
    { id: 'boom', title: 'Взрыв', text: 'Порох + Огонь → Взрыв' },
    { id: 'acid', title: 'Растворение', text: 'Кислота + Материал → Дым + Пустота' },
    { id: 'plant', title: 'Росток', text: 'Семена + Земля + Вода → Растение' },
    { id: 'grow', title: 'Буйство зелени', text: 'Растение + Вода → Растёт вверх' },
    { id: 'crystal', title: 'Кристаллизация', text: 'Камень + Холодная вода → Кристалл' },
    { id: 'ash', title: 'Ил', text: 'Пепел + Вода → Грязь' }
  ];

  global.M = M;
  global.MATS = MATS;
  global.MT = { EMPTY: T_EMPTY, SOLID: T_SOLID, POWDER: T_POWDER, LIQUID: T_LIQUID, GAS: T_GAS, FIRE: T_FIRE };
  global.AMBIENT = AMBIENT;
  global.RECIPES = RECIPES;
})(typeof window !== 'undefined' ? window : globalThis);
