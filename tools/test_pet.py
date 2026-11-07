"""Офлайн-прогон движка: весь жизненный цикл питомца без Android."""
import sys, os, time, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugin"))
import pet_stubs  # noqa: F401  (ставит заглушки SDK)
random.seed(42)

import pet  # noqa: E402

fails = []
def check(name, cond, info=""):
    status = "OK " if cond else "FAIL"
    print("[%s] %s %s" % (status, name, info))
    if not cond:
        fails.append(name)

# --- данные ---
check("SPECIES=10", len(pet.SPECIES) == 10, list(pet.SPECIES))
check("FOODS", len(pet.FOODS) >= 46, len(pet.FOODS))
check("QUESTS", len(pet.QUESTS) >= 43, len(pet.QUESTS))
check("QUIZ", len(pet.QUIZ) >= 60, len(pet.QUIZ))
check("TIPS", len(pet.TIPS) >= 45, len(pet.TIPS))
check("WALK_EVENTS", len(pet.WALK_EVENTS) >= 36, len(pet.WALK_EVENTS))
check("COLLECTIBLES", len(pet.COLLECTIBLES) >= 24, len(pet.COLLECTIBLES))
check("sticker quest target", pet.QUESTS["stickers_all"]["target"] == len(pet.COLLECTIBLES))

# каждая ссылка видов/еды/уникалок валидна
for sid, sp in pet.SPECIES.items():
    check("species %s unique" % sid, sp.get("unique") in pet.UNIQUE_ACTIONS)
    check("species %s stages" % sid, len(sp["stages"]) == 4)
    for f in sp.get("likes", []) + sp.get("dislikes", []):
        check("species %s food ref %s" % (sid, f), f in pet.FOODS)
    check("species %s walk_bonus" % sid, (sp.get("walk_bonus") or ("", 1))[0] in pet.LOCATIONS)
for uid, act in pet.UNIQUE_ACTIONS.items():
    check("unique %s skill" % uid, act.get("skill") in pet.SKILL_KEYS)

# рецепты: ингредиенты существуют
for rid, recipe in pet.RECIPES.items():
    for ing in recipe["inputs"]:
        check("recipe %s ing %s" % (rid, ing), ing in pet.FOODS)
    check("recipe %s info" % rid, pet.food_info(rid) is not None)

# лекарства лечат существующие болезни
for mid, med in pet.MEDICINES.items():
    for ill in med.get("cures", []):
        check("med %s cures %s" % (mid, ill), ill in pet.ILLNESSES)
    for ing in med.get("ingredients", []):
        check("med %s ing %s" % (mid, ing), ing in pet.FOODS)

# квесты: счётчики и награды валидны
for qid, q in pet.QUESTS.items():
    check("quest %s reward" % qid, set(q["reward"]) <= {"coins", "food", "toy", "accessory", "collectible"})
    if "food" in q["reward"]:
        check("quest %s food ref" % qid, pet.food_info(q["reward"]["food"]) is not None)
    if "toy" in q["reward"]:
        check("quest %s toy ref" % qid, q["reward"]["toy"] in pet.TOYS)
    if "accessory" in q["reward"]:
        check("quest %s acc ref" % qid, q["reward"]["accessory"] in pet.ACCESSORIES)
    if "collectible" in q["reward"]:
        check("quest %s coll ref" % qid, q["reward"]["collectible"] in pet.COLLECTIBLES)

# викторина: ровно 4 варианта, индекс ответа корректен
for i, (q, opts, right) in enumerate(pet.QUIZ):
    check("quiz %d" % i, 3 <= len(opts) <= 4 and 0 <= right < len(opts))

# события прогулок: ссылки на еду/стикеры валидны
for eid, ev in pet.WALK_EVENTS.items():
    for f in ev.get("foods", []):
        check("walk %s food %s" % (eid, f), f in pet.FOODS)
    for c in ev.get("collectibles", []):
        check("walk %s coll %s" % (eid, c), c in pet.COLLECTIBLES)

# --- жизненный цикл ---
state = pet.new_state("dragon")
check("new state stage", state["stage"] == 0 and state["needs"]["health"] == 100)

ok, lines = pet.do_care(state, "warm")
check("warm egg", ok, lines)
state["born"] -= 25 * 60
flags = pet.check_evolution(state)
check("hatched", flags.get("hatched") and state["stage"] == 1)

ok, lines = pet.eat_food(state, "kasha")
check("free porridge", ok, lines)
ok, lines = pet.eat_food(state, "cookies")
check("eat w/o inventory fails", not ok)

pet.inv_add(state, "pie", "food", 2)
ok, lines = pet.eat_food(state, "pie")
check("eat from inventory", ok and pet.inv_count(state, "pie") == 1, lines)

state["coins"] = 0
ok, lines = pet.buy(state, "food", "meat")
check("buy needs coins", not ok)
pet.earn(state, 500)
ok, lines = pet.buy(state, "food", "meat")
check("buy steak", ok and state["coins"] < 500, lines)

ok, lines = pet.cook(state, "royal_sandwich")
check("cook w/o ingredients", not ok)
pet.inv_add(state, "bread", "food", 1)
pet.inv_add(state, "cheese", "food", 1)
pet.inv_add(state, "sausage", "food", 1)
ok, lines = pet.cook(state, "royal_sandwich")
check("cook sandwich", ok, lines)
ok, lines = pet.eat_food(state, "royal_sandwich")
check("eat cooked dish", ok, lines)

ok, lines = pet.play_with_toy(state, "ball")
check("toy w/o toy", not ok)
pet.inv_add(state, "ball", "toy", 1, uses=10)
ok, lines = pet.play_with_toy(state, "ball")
check("play ball", ok, lines)

ok, lines = pet.equip_accessory(state, "crown")
check("equip w/o item", not ok)
pet.inv_add(state, "crown", "accessory", 1)
ok, lines = pet.equip_accessory(state, "crown")
check("equip crown", ok, lines)
ok, lines = pet.unequip_slot(state, "head")
check("unequip", ok, lines)

ok, lines = pet.start_walk(state, "yard")
check("start walk", ok, lines)
state["walk"]["started"] -= 40 * 60
fresh, done = pet.walk_tick(state)
ok, lines = pet.finish_walk(state, early=False)
check("finish walk", ok, lines)

ok, lines = pet.start_job(state, "courier")
check("start job", ok, lines)
state["job"]["started"] -= 2 * 60 * 60
ok, lines = pet.finish_job(state)
check("finish job", ok, lines)

# болезнь и лечение
state["illness"] = "cold"
pet.inv_add(state, "syrup", "medicine", 1)
ok, lines = pet.use_medicine(state, "syrup")
check("cure cold", ok and state.get("illness") is None, lines)

# уникальное действие
ok, lines = pet.do_unique(state)
check("unique action", ok, lines)
ok, lines = pet.do_unique(state)
check("unique cooldown", not ok)

# распад и смерть
state["needs"]["satiety"] = 0
state["seen"] = time.time() - 6 * 3600
lines = pet.apply_decay(state)
check("decay hurts", state["needs"]["health"] < 100)

# чат-кормление
before = state["needs"]["satiety"]
pet.chat_feed(state)
check("chat feed", state["needs"]["satiety"] >= before)

# дейлики
pet.daily_check(state)
check("daily streak", state["daily"]["streak"] >= 1)

# сохранение/миграция
saved = json.dumps(state) if (json := __import__("json")) else None
migrated = pet.migrate_state({"species": "cat"})
check("migrate minimal", migrated["species"] == "cat" and "needs" in migrated)

# --- проводка DLC-счётчиков ---
state = pet.new_state("cat")
pet.do_care(state, "warm")
state["born"] -= 25 * 60
pet.check_evolution(state)
pet.inv_add(state, "tiramisu", "food", 1)
ok, _ = pet.eat_food(state, "tiramisu")
check("sweets counter", state["counters"].get("sweets_eaten") == 1, state["counters"].get("sweets_eaten"))
check("foods tried", state["counters"].get("foods_tried") == 1)
pet.earn(state, 100)
ok, _ = pet.buy(state, "accessory", "top_hat")
check("accessories bought", state["counters"].get("accessorys_bought", 0) == 1, state["counters"].get("accessorys_bought"))
ok, _ = pet.equip_accessory(state, "top_hat")
pet.inv_add(state, "silk_scarf", "accessory", 1)
ok, _ = pet.equip_accessory(state, "silk_scarf")
pet.inv_add(state, "cape", "accessory", 1)
ok, _ = pet.equip_accessory(state, "cape")
check("full outfit", state["counters"].get("full_outfits") == 1)
pet.earn(state, 600)
ok, lines = pet.buy(state, "food", "avocado")
check("healthy food buy", ok)
ok, _ = pet.eat_food(state, "avocado")
check("healthy eaten", state["counters"].get("healthy_eaten") == 1)
pet.inv_add(state, "bread", "food", 1)
pet.inv_add(state, "cheese", "food", 1)
pet.inv_add(state, "sausage", "food", 1)
ok, _ = pet.cook(state, "royal_sandwich")
check("recipes used", state["counters"].get("recipes_used") == 1)
ok, _ = pet.start_job(state, "courier")
check("jobs tried", state["counters"].get("jobs_tried") == 1)
state["job"]["started"] -= 3600
ok, _ = pet.finish_job(state)
check("jobs done", state["counters"].get("jobs_done") == 1)
pet.daily_check(state)
check("max streak", state["counters"].get("max_streak", 0) >= 1)
check("care points", state["counters"].get("care_points", 0) >= 1)
ok, _ = pet.do_unique(state)
check("uniques done", state["counters"].get("uniques_done") == 1)

# инстанс плагина строит настройки без Android
plugin = pet.TamagochiPlugin()
rows = plugin.create_settings()
check("settings rows", isinstance(rows, list) and len(rows) >= 4, len(rows))
plugin._settings["pet"] = json.dumps(state)
rows2 = plugin.create_settings()
check("settings rows with pet", len(rows2) > len(rows), len(rows2))

print()
print("FAILS:", fails if fails else "none — все проверки зелёные")
sys.exit(1 if fails else 0)
