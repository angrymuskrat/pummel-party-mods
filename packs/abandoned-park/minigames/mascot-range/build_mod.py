"""Собирает мод Mascot Range по DESIGN.md в папку WorkshopMods редактора.

Запуск из корня репозитория:  python packs/abandoned-park/minigames/mascot-range/build_mod.py [имя мода] [папка WorkshopMods]
По умолчанию пишет «Mascot Range» в WorkshopMods редактора. Сцену, настройки и ассеты пересобирает целиком; превью
(Data/Preview.jpg после сохранения в редакторе), Preview Image мини-игры и данные Workshop сохраняет (pmgen.Mod.write).
"""
import copy
import math
import os
import random
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, ".claude", "skills", "pummel-party-level-design", "scripts"))
from pmgen import *  # noqa: E402,F403
import plan_view  # noqa: E402

ASSETS = os.path.join(ROOT, "packs", "abandoned-park", "assets")
WORKSHOP = r"%USERPROFILE%\AppData\LocalLow\Rebuilt Games\Pummel Party\WorkshopMods"
HERE = os.path.dirname(os.path.abspath(__file__))

GRAVITY, RUN, JUMP = 15.0, 6.0, 6.0   # прыжок 6²/(2·15) = 1.2 м: на балкон (1 м) запрыгивают, через прилавок (0.9 м) тоже
# один раунд: выбывания нет, пауза между раундами только рвала бы темп. Эскалация — этапы по STAGE_TIME (Director)
ROUND, STAGE_TIME = 60.0, 20.0
RESPAWN = 2.0

# галерея стрелков: передний ярус z −5…0 (верх y 0), балкон z −10…−5 (верх y 1), прилавок у края z 0…0.6
HALF, FRONT_BACK, BACK_Z, BALCONY_Y = 13.0, -5.0, -10.0, 1.0
COUNTER_H = 0.9       # ниже ствола (рука ~1.1 м): прилавок не съедает выстрелы по нижнему ряду
WATER_Y = -1.0

# ружьё: HitScan без разброса, урон 0 (без здоровья любой урон убивает). Откат 1.0 с — 60 выстрелов за игру
# (было 0.6 и ~100, бэклог 2026-10-27: решала скорострельность и первый клик, а не выбор ряда)
COOLDOWN, RANGE = 1.0, 60.0
# попадание в игрока: не ранит и не оглушает, а толкает от стрелка (weaponHitTrigger, фильтр Projectile).
# 2.5 м/с вверх дают подскок 0.2 м — через прилавок толчок не перебрасывает, только сбивает прицел и место.
# 3 м/с (было 5): толчок сбивает прицел, но не гоняет по рубежу
SHOVE, SHOVE_LIFT = 3.0, 2.5

# ряды мишеней: z, высота низа стойки (pivot), масштаб, x мишеней, размах ±amp по X, период, очки, сколько ждать возврата.
# Мишеней меньше и они крупнее (бэклог 2026-10-27: 4 + 4 вместо 6 + 5, масштаб 1.25 / 0.95): выбор ряда весит больше клика
ROWS = [
    {"name": "Row_Ducks", "z": 10.0, "y": 0.4, "scale": 1.25, "xs": [-7.5, -2.5, 2.5, 7.5],
     "amp": 3.0, "period": 6.0, "phase": 0.0, "points": 1, "revive": (3.0, 4.0), "tint": (0.95, 0.85, 0.75, 1)},
    {"name": "Row_Back", "z": 18.0, "y": 1.6, "scale": 0.95, "xs": [-6.0, -2.0, 2.0, 6.0],
     "amp": 4.0, "period": 4.4, "phase": 0.5, "points": 2, "revive": (4.0, 5.0), "tint": (0.95, 0.35, 0.25, 1)},
]
# всплывающие маскоты (этап 2): над стеной z 26, всплывают по таймеру и прячутся через POPUP_UP
POPUP = {"z": 26.0, "y": 2.0, "scale": 1.3, "xs": [-9.0, -3.0, 3.0, 9.0], "every": (2.5, 5.0), "points": 3,
         "wall_top": 2.6, "tint": (0.55, 0.85, 1.0, 1)}
POPUP_UP = 1.6
# золотой маскот (этап 3): летит зигзагом над полем — X туда-обратно и покачивание по Y, возвращается через GOLD_REVIVE
GOLD = {"z": 22.0, "y": 4.5, "scale": 0.9, "amp": 9.0, "period": 5.5, "bob": 1.5, "bob_period": 2.3, "points": 5}
GOLD_REVIVE = 3.0
FACE_R, FACE_Y = 0.45, 1.05   # mascot_target.obj: радиус лица и высота его центра над pivot (с ушами по X ±0.54, вверх +0.54)


def rifle_info() -> dict:
    """ModWeaponInfo ружья: HitScan, урон 0, без разброса, трассер (видно, куда ушёл выстрел)."""
    w = copy.deepcopy(DEFAULT_WEAPON_INFO)
    w.update(weaponHitType=0, spawnBulletEffect=True, bulletColor={"r": 1.0, "g": 0.85, "b": 0.3, "a": 1.0},
             spawnTrailEffect=True, trailStartColor={"r": 1.0, "g": 0.95, "b": 0.7, "a": 0.6},
             trailEndColor={"r": 1.0, "g": 0.95, "b": 0.7, "a": 0.15}, trailWidth=0.12, trailLength=RANGE, fireSound=1,
             stunOnHit=False)
    w["basicInfo"] = {"cooldown": COOLDOWN, "damage": 0}
    w["scanInfo"].update(weaponSpreadType=0, shotCount=1, range=RANGE, hitOnce=True)
    return w


def target_box(scale):
    """Размер и центр зоны попадания (Box, On Hit) — лицо с ушами плюс 10%: что видно, в то и попадаешь."""
    w, h = 2 * 0.54 * scale * 1.1, (FACE_R + 0.54) * scale * 1.1
    return (w, h, 0.3), (0, (FACE_Y - FACE_R) * scale + h / 2 / 1.1, 0)


def build(name: str, workshop: str = WORKSHOP) -> str:
    rng = random.Random("mascot-range-v1")
    mod = Mod(name, description="Rusted Park: a rusty shooting gallery over an acid moat. Shoot tin mascot heads on moving "
                                "rails, pop-up mascots and the flying golden mascot. Hitting a rival shoves them. / "
                                "Тир: стреляй по жестяным головам маскотов на ржавых дорожках, по всплывающим маскотам и "
                                "летучему золотому. Попадание в соперника его толкает.",
              rounds=1, round_duration=ROUND, end_conditions=EndCondition.TIMER, placement=Placement.MOST_POINTS,
              settings_overrides={"respawnEnabled": True, "respawnTime": RESPAWN, "respawnInvulnerableTime": 1.0,
                                  "canPunch": True, "useHealth": False, "punchDamage": 0, "punchStunsTarget": False,
                                  "playerGravity": GRAVITY, "jumpSpeed": JUMP, "movementSpeed": RUN,
                                  "weaponHitTrigger": {"m_type": 80, "m_actions": [], "m_hitType": WeaponHitKind.PROJECTILE}})

    # --- ассеты
    def prop(fn): return mod.add_file_asset("prop", os.path.join(ASSETS, "models", fn))
    def tex(fn): return mod.add_file_asset("texture", os.path.join(ASSETS, "textures", fn))
    def wav(fn): return mod.add_file_asset("audio", os.path.join(ASSETS, "audio", fn))
    target_obj, mascot_obj, booth_obj, barrel_obj = prop("mascot_target.obj"), prop("mascot_headless.obj"), prop("booth.obj"), prop("barrel.obj")
    lamp_obj, fence_obj, rotor_obj, stand_obj = prop("lamppost.obj"), prop("fence_segment.obj"), prop("ferris_wheel_rotor.obj"), prop("ferris_wheel_stand.obj")
    roof_obj, tree_obj, hill_obj, trestle_obj = prop("carousel_roof.obj"), prop("dead_tree.obj"), prop("hill.obj"), prop("coaster_trestle.obj")
    rail_obj, debris_obj, cart_obj = prop("rail_segment.obj"), prop("debris.obj"), prop("cart.obj")
    clang_wav, finish_wav, sweep_wav = wav("target_clang.wav"), wav("finish.wav"), wav("sweep.wav")
    concrete_tex = tex("concrete.png")
    paint_mat = mod.add_material("CarouselPaint", tex("carousel_paint.png"), tiling=(1.0, 1.0))
    rust_mat = mod.add_material("RustBooth", tex("rust_booth.png"), tiling=(2.0, 2.0))
    metal_mat = mod.add_material("RustMetal", tex("rust_metal.png"), tiling=(1.0, 1.0))
    dirt_mat = mod.add_material("Dirt", tex("dirt.png"), tiling=(20.0, 20.0))
    deck_mat = mod.add_material("Concrete_Deck", concrete_tex, tiling=(6.0, 2.0))

    # --- ружьё: визуальный префаб (винтовка шаблона Third Person Shooter) и префаб предмета с Item Component на корне
    rifle_visual = obj("Rifle")
    rifle_visual.prop(PROP_SNIPER, collision=Collision.NONE, tint=(0.75, 0.5, 0.3, 1))
    rifle_visual.add(obj("Scope", pos=(-0.005, 0.178, 0.122)).prop(PROP_SNIPER_SCOPE, collision=Collision.NONE))
    rifle_visual_asset = mod.add_prefab(rifle_visual)
    rifle_item = mod.add_prefab(obj("RifleItem").item(
        ItemType.WEAPON, rifle_visual_asset.guid, weapon_type=WeaponUsage.GUN, weapon_info=rifle_info(), cooldown=COOLDOWN,
        can_drop=False, disappear_when_dropped=True, drop_on_death=True))
    # ружьё выдаётся при первом появлении и после каждого респауна (при смерти оно исчезает: Drop On Death + Disappear)
    give = [act_give_minigame_item(rifle_item.guid)]
    mod.player_triggers = {
        "onFirstSpawnTrigger": give, "onRespawnTrigger": give,
        "weaponHitTrigger": [act_change_velocity(SHOVE, VelocityDir.TOWARDS_RECEIVER, Op.ADD, flags=Targets.RECEIVER),
                             act_change_velocity(SHOVE_LIFT, VelocityDir.UP, Op.ADD, flags=Targets.RECEIVER)]}

    def wall(parent, name, pos, model, rot=(0, 0, 0), scale=(1, 1, 1), mat=None, tint=(1, 1, 1, 1), layer=LAYER_WORLD_WALL):
        return parent.add(obj(name, pos=pos, rot=rot, scale=scale, layer=layer)
                          .prop(model, collision=Collision.BOX, materials=[mat.guid] if mat else None, tint=tint))

    def deco(parent, name, pos, model, rot=(0, 0, 0), scale=(1, 1, 1), mat=None, tint=(1, 1, 1, 1), shadow=Shadow.ON):
        return parent.add(obj(name, pos=pos, rot=rot, scale=scale)
                          .prop(model, collision=Collision.NONE, shadow=shadow, materials=[mat.guid] if mat else None, tint=tint))

    # --- галерея: передний ярус, балкон, два пандуса по краям, прилавок; кислотный ров и поле мишеней за ним
    world = mod.add(obj("World"))
    world.add(obj("Deck_Front", pos=(0, -0.5, FRONT_BACK / 2), scale=(2 * HALF, 1.0, -FRONT_BACK), layer=LAYER_WORLD_GROUND)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[deck_mat.guid]))
    world.add(obj("Deck_Balcony", pos=(0, (BALCONY_Y - 1.0) / 2, (FRONT_BACK + BACK_Z) / 2),
                  scale=(2 * HALF, BALCONY_Y + 1.0, FRONT_BACK - BACK_Z), layer=LAYER_WORLD_GROUND)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[deck_mat.guid]))
    # пандус 2.4 м на балкон у каждого края: верх от (z −2, y 0) до (z −5, y 1), наклон 18.4° (+Z конец ниже)
    ang = math.atan2(BALCONY_Y, 3.0)
    for sx in (-1, 1):
        world.add(obj(f"Ramp_{'W' if sx < 0 else 'E'}", pos=(sx * (HALF - 1.4), 0.5 - 0.15 * math.cos(ang), -3.5 - 0.15 * math.sin(ang)),
                      rot=(math.degrees(ang), 0, 0), scale=(2.4, 0.3, math.hypot(3.0, BALCONY_Y) + 0.1), layer=LAYER_WORLD_GROUND)
                  .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
    # прилавок от воды до 0.9 м над ярусом: снизу не висит в воздухе
    wall(world, "Counter", (0, (COUNTER_H + WATER_Y) / 2, 0.3), PROP_CUBE, scale=(2 * HALF, COUNTER_H - WATER_Y, 0.6), mat=rust_mat)
    world.add(obj("Acid", pos=(0, WATER_Y, 20)).water(
        width=24, height=21, cell=2.0, deep=(0.12, 0.45, 0.08, 0.8), shallow=(0.45, 1.0, 0.2, 0.8), froth=(0.8, 1.0, 0.6, 1)))
    world.add(obj("KillVolume", pos=(0, -1.9, 20)).trigger(
        TriggerShape.BOX, size=(90, 1, 70), on_enter=[act_spawn_effect(Effect.EXPLOSION, Targets.SOURCE), act_kill(Targets.SOURCE)]))
    # дно под зоной смерти: в паузе перед итогами игра не убивает, а физика идёт (Human Cannonball, плейтест 2026-10-25)
    world.add(obj("AcidBed", pos=(0, -3.1, 20), scale=(90, 1, 70))
              .prop(PROP_CUBE, collision=Collision.BOX, shadow=Shadow.OFF, materials=[dirt_mat.guid], tint=(0.2, 0.25, 0.15, 1)))

    # --- мишени. Зона попадания — Trigger On Hit (становится твёрдым коробом), картинка — ребёнок без коллизии.
    # Выстрел шлёт событие всем IEventReceiver в родителях задетого коллайдера (WeaponComponent.FireHitScan), поэтому
    # других триггеров и Logic с Hit/Weapon Hit выше мишени нет. Disable After Triggered прячет мишень у всех клиентов
    def target(parent, name, pos, scale, tint, points, active=True, extra=None):
        size, center = target_box(scale)
        acts = [act_change_score(points, Op.ADD, Targets.SOURCE),
                act_spawn_effect(Effect.SPARKLES, Targets.RECEIVER),
                act_play_sound(clang_wav.guid, 0.8, Targets.RECEIVER)] + (extra or [])
        t = parent.add(obj(name, pos=pos, active=active).trigger(TriggerShape.BOX, size=size, center=center, on_hit=acts,
                                                                 disable_after=True))
        t.add(obj("Tin", scale=(scale,) * 3).prop(target_obj.guid, collision=Collision.NONE, tint=tint))
        return t

    targets = mod.add(obj("Targets"))
    row_info = []
    for row in ROWS:
        r = targets.add(obj(row["name"]))
        # дорожка на сваях из кислоты; без коллизии — не загораживает выстрелы
        deco(r, "Rail", (0, row["y"] - 0.12, row["z"]), PROP_CUBE, scale=(2 * HALF + 2, 0.2, 0.35), mat=metal_mat)
        for k, x in enumerate((-12.0, -4.0, 4.0, 12.0)):
            h = row["y"] - WATER_Y + 0.5
            deco(r, f"Stilt_{k}", (x, WATER_Y - 0.5 + h / 2, row["z"] + 0.25), PROP_CUBE, scale=(0.25, h, 0.25), mat=metal_mat)
        # каретка едет туда-обратно по X; мишени — её дети. Периоды рядов разные и не кратные — ряды не ходят строем
        carriage = r.add(obj("Carriage", pos=(-row["amp"], row["y"], row["z"])).simple_animator(
            anim_move_along_line(1.0 / row["period"], (2 * row["amp"], 0, 0)), local_position=False,
            time_offset=row["period"] * row["phase"]))
        tgts = [target(carriage, f"Target_{k}", (x, 0, 0), row["scale"], row["tint"], row["points"])
                for k, x in enumerate(row["xs"])]
        # сбитые мишени ряда возвращаются разом по таймеру (случайный интервал — у каждого матча свой ритм)
        r.logic(trig_timer(row["revive"][0], act_set_active(ActiveState.ENABLED, [t.transform_guid for t in tgts]),
                           max_interval=row["revive"][1]))
        row_info.append((row, len(tgts)))

    # всплывающие маскоты: стена-ширма, за ней четыре мишени. Таймер PopUp_k включает мишень, мишень по Enable
    # прячется сама через POPUP_UP. Цепочки действий идут в корутине GameManager (ModActionRunner), так что сбитая
    # и выключенная мишень свою цепочку не обрывает — выключение повторно ничего не делает
    popups = targets.add(obj("PopUps", active=False))
    wall(popups, "Screen", (0, (POPUP["wall_top"] + WATER_Y - 0.5) / 2, POPUP["z"] - 0.4), PROP_CUBE,
         scale=(2 * HALF, POPUP["wall_top"] - WATER_Y + 0.5, 0.3), mat=rust_mat)
    for k, x in enumerate(POPUP["xs"]):
        p = popups.add(obj(f"PopUp_{k}"))
        t = target(p, "Target", (x, POPUP["y"], POPUP["z"]), POPUP["scale"], POPUP["tint"], POPUP["points"], active=False)
        t.logic(trig_enable(act_wait(POPUP_UP), act_set_active(ActiveState.DISABLED, [t.transform_guid])))
        p.logic(trig_timer(POPUP["every"][0], act_set_active(ActiveState.ENABLED, [t.transform_guid]),
                           max_interval=POPUP["every"][1]))

    # золотой маскот: каретка по X, внутри покачивание по Y; таймер возвращает сбитого
    gold = targets.add(obj("Golden", active=False))
    fly = gold.add(obj("Flight", pos=(-GOLD["amp"], GOLD["y"], GOLD["z"])).simple_animator(
        anim_move_along_line(1.0 / GOLD["period"], (2 * GOLD["amp"], 0, 0)), local_position=False))
    bob = fly.add(obj("Bob").simple_animator(anim_move_along_line(1.0 / GOLD["bob_period"], (0, GOLD["bob"], 0))))
    gold_t = target(bob, "Target", (0, 0, 0), GOLD["scale"], (1.0, 0.8, 0.1, 1), GOLD["points"],
                    extra=[act_spawn_effect(Effect.CONFETTI, Targets.RECEIVER), act_play_sound(finish_wav.guid, 1.0, Targets.RECEIVER),
                           act_show_message(f"Золотой маскот! +{GOLD['points']} / Golden mascot! +{GOLD['points']}", 1.5,
                                            MsgTarget.TARGET, Targets.SOURCE)])
    gold.logic(trig_timer(GOLD_REVIVE, act_set_active(ActiveState.ENABLED, [gold_t.transform_guid])))

    # --- средний план галереи: ящики у края балкона (0.6 м, перепрыгиваются, прикрывают от толчков), кассы в углах
    mid = mod.add(obj("Midground"))
    for k, x in enumerate((-7.0, 0.0, 7.0)):
        wall(mid, f"AmmoCrate_{k}", (x + rng.uniform(-0.5, 0.5), 0.3, FRONT_BACK + 0.6), PROP_CUBE,
             rot=(0, rng.uniform(-10, 10), 0), scale=(1.4, 0.6, 0.9), mat=rust_mat)
    for k, x in enumerate((-HALF + 2.0, HALF - 2.0)):
        wall(mid, f"Booth_{k}", (x, BALCONY_Y, BACK_Z + 1.6), booth_obj.guid, rot=(0, 180 + (-10 if x < 0 else 10), 0), mat=rust_mat)

    # --- мелочь: призы на задней стене (головы-мишени и бочки), гильзы-ядра у ящиков, фонари, обломки; бочки в кислоте
    decor = mod.add(obj("Decor"))
    for k in range(7):
        x = -9 + 3 * k
        deco(decor, f"Prize_{k}", (x, BALCONY_Y + 1.6 + 0.3 * (k % 2), BACK_Z + 0.15), target_obj.guid, rot=(0, 0, rng.uniform(-12, 12)),
             scale=(0.55,) * 3, tint=((0.95, 0.35, 0.25, 1), (0.55, 0.85, 1.0, 1), (1.0, 0.8, 0.1, 1))[k % 3])
    for k, x in enumerate((-4.0, 4.0)):
        wall(decor, f"Barrel_{k}", (x, BALCONY_Y, BACK_Z + 0.8), barrel_obj.guid, rot=(0, rng.uniform(0, 360), 0), mat=metal_mat)
    for k, (x, z) in enumerate(((-HALF + 0.4, -0.6), (HALF - 0.4, -0.6))):
        wall(decor, f"Lamppost_{k}", (x, 0, z), lamp_obj.guid, rot=(0, rng.uniform(-30, 30), 0 if k else 4), mat=metal_mat)
    for k in range(3):
        deco(decor, f"Debris_{k}", (rng.uniform(-10, 10), BALCONY_Y + 0.08, rng.uniform(BACK_Z + 0.5, BACK_Z + 1.2)), debris_obj.guid,
             rot=(rng.uniform(0, 360), rng.uniform(0, 360), 0), scale=(rng.uniform(0.25, 0.45),) * 3, tint=(0.5, 0.48, 0.45, 1))
    for k, (x, z, ph) in enumerate(((-15, 6, 0.0), (14, 13, 1.1), (-6, 30, 0.6), (17, 31, 2.0), (-18, 22, 1.6))):
        deco(decor, f"FloatingBarrel_{k}", (x, WATER_Y - 0.25, z), barrel_obj.guid, rot=(85, rng.uniform(0, 360), 0),
             mat=metal_mat).simple_animator(anim_move_along_line(0.3, (0, 0.25, 0)), time_offset=ph)
    deco(decor, "SunkenCart", (10, WATER_Y - 0.4, 33), cart_obj.guid, rot=(0, -30, 160), mat=metal_mat)
    # арка над прилавком: две стойки и перекладина с лампочками (выше линии взгляда на золотого маскота)
    arch = decor.add(obj("Arch"))
    for sx in (-1, 1):
        wall(arch, f"Post_{'W' if sx < 0 else 'E'}", (sx * (HALF + 0.3), 2.75, 0.3), PROP_CUBE, scale=(0.4, 5.5, 0.4), mat=paint_mat)
    deco(arch, "Beam", (0, 5.3, 0.3), PROP_CUBE, scale=(2 * HALF + 1.0, 0.8, 0.4), mat=paint_mat)
    for i in range(14):
        deco(arch, f"Bulb_{i}", (-HALF + 2 * i, 5.3, 0.05), PROP_SPHERE, scale=(0.25,) * 3, shadow=Shadow.OFF,
             tint=(1.0, 0.85, 0.3, 1) if i % 2 else (1.0, 0.4, 0.3, 1))
    fence = decor.add(obj("Fence"))
    for i in range(int(2 * HALF / 3.0)):
        wall(fence, f"Back_{i}", (-HALF + 1.5 + 3.0 * i, BALCONY_Y, BACK_Z + 0.2), fence_obj.guid, mat=metal_mat)
    # бока: на балконе две секции, на переднем ярусе две (до прилавка) — с края не упасть
    for i, (z, y) in enumerate(((BACK_Z + 1.5, BALCONY_Y), (BACK_Z + 3.5, BALCONY_Y), (FRONT_BACK + 1.5, 0.0), (-0.5, 0.0))):
        for sx in (-1, 1):
            wall(fence, f"Side_{'W' if sx < 0 else 'E'}_{i}", (sx * (HALF - 0.2), y, z), fence_obj.guid, rot=(0, 90, 0), mat=metal_mat)

    # --- задний план: дальний берег — маскот-великан на оси (ориентир) и колесо обозрения за ним, шатры по бокам,
    # руины горок вдоль рва, холмы и сухие деревья по кругу
    backdrop = mod.add(obj("Backdrop"))
    backdrop.add(obj("OuterGround", pos=(0, -1.3, 10), scale=(18, 1, 18))
                 .prop(PROP_PLANE, collision=Collision.NONE, materials=[dirt_mat.guid]))
    backdrop.add(obj("FallVolume", pos=(0, -8, 0)).trigger(TriggerShape.BOX, size=(400, 4, 400), on_enter=[act_kill(Targets.SOURCE)]))
    backdrop.add(obj("FarShore", pos=(0, -0.2, 45), scale=(70, 1.6, 10))
                 .prop(PROP_CUBE, collision=Collision.NONE, materials=[dirt_mat.guid]))
    deco(backdrop, "GiantMascot", (0, 0.6, 42), mascot_obj.guid, rot=(0, 180, 0), scale=(4.5, 4.5, 4.5), tint=(0.95, 0.75, 0.3, 1))
    wheel = backdrop.add(obj("FerrisWheel", pos=(14, 7.9, 50)).prop(stand_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    wheel.add(obj("Rotor").prop(rotor_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid])
              .mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Z, (0, 0, 1), 10.0))
    for k, (x, z, s) in enumerate(((-20, 44, 1.3), (-8, 48, 0.9))):
        deco(backdrop, f"Tent_{k}", (x, 6.0 * s, z), roof_obj.guid, scale=(s, s * 1.4, s), mat=paint_mat)
    for sx in (-1, 1):
        coaster = backdrop.add(obj(f"RuinedCoaster_{'W' if sx < 0 else 'E'}", pos=(sx * 26, -1.2, 0)))
        for i in range(7):
            z = -6 + 7 * i
            coaster.add(obj(f"Trestle_{i}", pos=(0, 0, z), rot=(0, 90, 0)).prop(trestle_obj.guid, collision=Collision.NONE,
                                                                               materials=[metal_mat.guid]))
            if i < 6 and i != (3 if sx < 0 else 1):
                coaster.add(obj(f"Rail_{i}", pos=(0, 10.3, z + 3.5)).prop(rail_obj.guid, collision=Collision.NONE,
                                                                         materials=[metal_mat.guid]))
    for i in range(12):
        a = 2 * math.pi * i / 12 + rng.uniform(-0.1, 0.1)
        r, s = rng.uniform(62, 76), rng.uniform(0.8, 1.6)
        backdrop.add(obj(f"Hill_{i}", pos=(r * math.cos(a), -0.2, 10 + r * math.sin(a)), rot=(0, rng.uniform(0, 360), 0),
                         scale=(s, s * rng.uniform(0.8, 1.4), s)).prop(hill_obj.guid, collision=Collision.NONE, materials=[dirt_mat.guid]))
    for i in range(14):
        x, z = rng.choice((-1, 1)) * rng.uniform(32, 44), rng.uniform(-22, 42)
        backdrop.add(obj(f"DeadTree_{i}", pos=(x, -1.2, z), rot=(0, rng.uniform(0, 360), rng.uniform(-6, 6)),
                         scale=(rng.uniform(0.8, 1.4),) * 3).prop(tree_obj.guid, collision=Collision.NONE, tint=(0.35, 0.28, 0.2, 1)))

    # --- спавны: общий отрезок на переднем ярусе лицом к полю, респауны на балконе
    spawns = mod.add(obj("Player Spawnpoints"))
    spawns.add(obj("Spawn_Line", pos=(0, 1, -2.5)).player_spawn(SpawnShape.LINE, SpawnUsage.INITIAL, line_length=18.0, shared=True))
    for i, x in enumerate((-8.0, 0.0, 8.0)):
        spawns.add(obj(f"Respawn_{i}", pos=(x, BALCONY_Y + 1, -8.0)).player_spawn(SpawnShape.POINT, SpawnUsage.RESPAWN))

    # --- сетка ботов: бот с ружьём гонится за случайным игроком и стреляет с 7 м (SimpleModPlayer.GetAIInput); узлы
    # нужны, чтобы он поднимался на балкон пандусом, а не упирался в ступень. Узла-цели нет: с ним бот не стреляет
    nav = mod.add(obj("AI Navigation"))
    pts = [(x, 0.35, z) for z in (-1.3, -3.0) for x in (-9.0, -4.5, 0.0, 4.5, 9.0)]                     # 0–9 передний ярус
    pts += [(sx * (HALF - 1.4), 0.35, -1.0) for sx in (-1, 1)]                                            # 10, 11 низ пандусов
    pts += [(sx * (HALF - 1.4), BALCONY_Y + 0.35, -6.0) for sx in (-1, 1)]                                # 12, 13 верх пандусов
    pts += [(x, BALCONY_Y + 0.35, -7.5) for x in (-9.0, -3.0, 3.0, 9.0)]                                  # 14–17 балкон
    nodes = [nav.add(obj(f"Node_{i}", pos=p).ai_node()) for i, p in enumerate(pts)]
    edges = []
    for row0 in (0, 5):
        edges += [(row0 + i, row0 + i + 1) for i in range(4)]
    edges += [(i, i + 5) for i in range(5)]
    edges += [(0, 10), (5, 10), (4, 11), (9, 11), (10, 12), (11, 13), (12, 14), (13, 17), (14, 15), (15, 16), (16, 17)]
    link_ai_nodes(nodes, edges + [(j, i) for i, j in edges])

    # --- этапы внутри одного раунда: Wait → Set Active (схема Death Carousel / Human Cannonball)
    msgs = ["Стреляй по маскотам! Ближний ряд +1, дальний +2. Попадание в соперника его толкает. / "
            "Shoot the mascots! Near row +1, far row +2. Hitting a rival shoves them.",
            "Всплывают маскоты за ширмой: +3! / Pop-up mascots: +3!",
            "Финал: золотой маскот летит, +5! / Final: golden mascot, +5!"]
    mod.add(obj("Director")).logic(trig_round_start(
        act_show_message(msgs[0], 5.0),
        act_wait(STAGE_TIME), act_set_active(ActiveState.ENABLED, [popups.transform_guid]),
        act_play_sound(sweep_wav.guid, 1.0, Targets.RECEIVER), act_show_message(msgs[1], 4.0),
        act_wait(STAGE_TIME), act_set_active(ActiveState.ENABLED, [gold.transform_guid]),
        act_play_sound(finish_wav.guid, 1.0, Targets.RECEIVER), act_show_message(msgs[2], 4.0)))

    # сводка: сколько очков поле выдаёт за игру, если всё сбивать сразу (потолок дефицита целей)
    table = []
    total = 0.0
    for row, n in row_info:
        per_game = n * row["points"] * ROUND / (sum(row["revive"]) / 2)
        total += per_game
        table.append(f"{row['name']}: {n} мишеней по {row['points']}, z {row['z']}, ±{row['amp']} м за {row['period']} с, "
                     f"возврат {row['revive'][0]}–{row['revive'][1]} с → потолок ~{per_game:.0f} очков за игру")
    pop = len(POPUP["xs"]) * POPUP["points"] * (ROUND - STAGE_TIME) / (sum(POPUP["every"]) / 2)
    gld = GOLD["points"] * (ROUND - 2 * STAGE_TIME) / GOLD_REVIVE
    total += pop + gld
    table.append(f"PopUps (с {STAGE_TIME:.0f} с): {len(POPUP['xs'])} по {POPUP['points']}, всплывают раз в {POPUP['every'][0]}–"
                 f"{POPUP['every'][1]} с на {POPUP_UP} с → ~{pop:.0f}")
    table.append(f"Golden (с {2 * STAGE_TIME:.0f} с): {GOLD['points']} очков, возврат {GOLD_REVIVE} с → ~{gld:.0f}")
    table.append(f"всего ~{total:.0f} очков за игру; выстрелов у одного игрока ≤ {ROUND / COOLDOWN:.0f}")
    mod.add(obj("Notes").note("Сгенерировано build_mod.py из packs/abandoned-park/minigames/mascot-range/DESIGN.md\n" + "\n".join(table)))
    out = mod.write(workshop)

    os.makedirs(os.path.join(HERE, "plan"), exist_ok=True)
    mod.preview_image = os.path.join(HERE, "plan", "preview.png")
    plan_view.render_preview(out, mod.preview_image)
    for line in table:
        print(line)
    return mod.write(workshop)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = build(sys.argv[1] if len(sys.argv) > 1 else "Mascot Range", sys.argv[2] if len(sys.argv) > 2 else WORKSHOP)
    print("written:", out)
