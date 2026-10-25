"""Собирает мод Mascot Throne по DESIGN.md в папку WorkshopMods редактора.

Запуск из корня репозитория:  python packs/abandoned-park/minigames/mascot-throne/build_mod.py [имя мода] [папка WorkshopMods]
По умолчанию пишет «Mascot Throne» в WorkshopMods редактора. Сцену, настройки и ассеты пересобирает целиком; превью
(Data/Preview.jpg после сохранения в редакторе), Preview Image мини-игры и данные Workshop сохраняет (pmgen.Mod.write).
"""
import math
import os
import random
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, ".claude", "skills", "pummel-party-level-design", "scripts"))
from pmgen import *  # noqa: E402,F403
import navgen  # noqa: E402
import plan_view  # noqa: E402

ASSETS = os.path.join(ROOT, "packs", "abandoned-park", "assets")
WORKSHOP = r"%USERPROFILE%\AppData\LocalLow\Rebuilt Games\Pummel Party\WorkshopMods"
HERE = os.path.dirname(os.path.abspath(__file__))

HALF = 20.0           # игровой пол 40 × 40
THRONE_R = 13.0       # внешние троны на кольце r 13: до центра 13 м (2.2 с бега), между собой 22.5 м (3.8 с)
DAIS_Y = 0.15         # верх помоста (throne_dais.obj), ниже ступеньки 0.2 — заходят и боты
ZONE_R = 2.4          # радиус зоны очков; кольцо crown_zone.obj — 2.25…2.5
SEAT_OFF = 2.4        # трон стоит на краю помоста с внешней стороны, лицом к центру арены
POND_RECT = (14.5, 18.0, -6.0, -1.0)   # x0, x1, z0, z1 кислотной лужи у трона «Пруд» — дыра в полу
ROUND = 90.0          # Round Duration
FIRST_HOLD = 17.0     # корона на сцене в начале: от кольца спавна до зоны всем одинаково
# эскалация: стоянка короны сжимается линейно с HOLD_START до HOLD_END к FINALE (±1 с от сида), в финале — FINALE_HOLD
HOLD_START, HOLD_END = 16.0, 7.0
FINALE, FINALE_HOLD = 75.0, 5.0   # с первой стоянки после FINALE ещё и двойная корона (+2 в секунду)
MIN_LAST_STAY = 2.5   # последний переезд не позже, чем за столько секунд до конца раунда
WARN = 3.0            # предупреждение до переезда: маяк следующего трона, скрип, сообщение
MOVE = 1.5            # полёт короны к следующему трону
SHRINK = 0.58         # кольцо за стоянку сжимается до r 2.4 · 0.58 ≈ 1.4 (масштаб X/Z зоны) и при переезде расправляется
PUNCH_PUSH, PUNCH_LIFT = 6.0, 4.0   # м/с от удара (схема Death Carousel, проверена плейтестом 2026-10-25): сбить на 2 м
DASH, DASH_TIME = 1.5, 3.0          # после респауна бег ×1.5 на 3 с: из угла до короны быстрее
TRAPS = False         # ловушки у тронов (вагонетка, мишени, обломки) — отключены по решению 2026-10-25, код оставлен
# порядок переездов: заранее не угадать, подряд один трон не повторяется. Случайного выбора направления в редакторе нет
# (случайны только интервалы и выбор префаба), а Wait с диапазоном внутри одного события берёт одно и то же число
# (WaitAction: new Random(modEvent.Seed) при каждом вызове), поэтому и порядок, и паузы зашиты сидом сборки


def polar(r, deg):
    a = math.radians(deg)
    return (r * math.cos(a), r * math.sin(a))


# места тронов: центр — сцена под навесом, внешние — у колеса (север), у тира (юго-запад), у пруда (юго-восток).
# Угол — с какой стороны помоста стоит кресло (снаружи арены; у центрального — юг, туда не идут хорды к другим тронам)
THRONES = {
    "C": {"xz": (0.0, 0.0), "seat": 270, "ru": "сцене", "en": "the stage"},
    "N": {"xz": polar(THRONE_R, 90), "seat": 90, "ru": "колесу", "en": "the Ferris wheel"},
    "SW": {"xz": polar(THRONE_R, 210), "seat": 210, "ru": "тиру", "en": "the shooting gallery"},
    "SE": {"xz": polar(THRONE_R, 330), "seat": 330, "ru": "пруду", "en": "the pond"},
}


def schedule(rng):
    """[(трон, прибытие, уход)] в секундах; первая стоянка — сцена, последняя длится до конца раунда."""
    out, leave = [["C", 0.0, FIRST_HOLD]], FIRST_HOLD
    while leave + MOVE <= ROUND - MIN_LAST_STAY:
        arrive = leave + MOVE
        if arrive >= FINALE:
            hold = FINALE_HOLD
        else:
            hold = HOLD_START + (HOLD_END - HOLD_START) * arrive / FINALE + rng.uniform(-1.0, 1.0)
            hold = max(WARN + 1.0, round(hold * 2) / 2)
        cur = rng.choice([k for k in THRONES if k != out[-1][0]])
        leave = arrive + hold
        out.append([cur, arrive, leave])
    out[-1][2] = ROUND
    return [tuple(s) for s in out]


def build_traps(mod, cart_obj, mascot_obj, rail_obj, debris_obj, metal_mat, sweep_wav, deco):
    """Ловушки у тронов; возвращает {трон: объект}, который режиссёр включает, пока корона на этом троне."""
    # --- ловушки у тронов. Группа ловушки стоит в центре помоста и повёрнута так, что её +Z смотрит на кресло (наружу),
    # +X — вдоль края помоста: θ = 90° − угол кресла (поворот Y на θ переводит +Z в (sin θ, cos θ)).
    # Ездящие ловушки — без коллизии (движущийся коллайдер игрока не толкает), толкает триггер: Towards Source — от
    # ловушки к вошедшему. Работают всегда, а не только при короне: правило одно и то же, и нужны они там, где толпа
    traps = mod.add(obj("Traps"))

    def trap_group(key):
        x, z = THRONES[key]["xz"]
        return traps.add(obj(f"Trap_{key}", pos=(x, 0, z), rot=(0, 90 - THRONES[key]["seat"], 0)))

    def sweeper(parent, name, z, start_x, travel, freq, phase, size, push, lift):
        """Ездит по прямой поперёк помоста (Simple Animator Move Along Line, локальная ось X группы) и толкает."""
        rig = parent.add(obj(name, pos=(start_x, DAIS_Y, z))
                         .simple_animator(anim_move_along_line(freq, (travel, 0, 0)), time_offset=phase)
                         .trigger(TriggerShape.BOX, size=size, center=(0, size[1] / 2, 0),
                                  on_enter=[act_change_velocity(push, VelocityDir.TOWARDS_SOURCE, Op.ADD),
                                            act_change_velocity(lift, VelocityDir.UP, Op.ADD),
                                            act_play_sound(sweep_wav.guid, 0.8, Targets.RECEIVER)]))
        for k, rx in enumerate((-3.0, 3.0)):   # рельсы под ловушкой — видно, где она ездит
            deco(parent, f"{name}_Rail_{k}", (rx, DAIS_Y + 0.02, z), rail_obj.guid, rot=(0, 90, 0), scale=(1, 0.3, 1),
                 mat=metal_mat)
        return rig

    # «Колесо»: сорвавшаяся вагонетка катается поперёк передней половины помоста, 5 с туда-обратно. Высота 0.6 м —
    # перепрыгивается; у кресла (задняя половина) не достаёт
    cart = sweeper(trap_group("N"), "Cart", -0.8, -4.5, 9.0, 0.2, 0.0, (2.4, 0.7, 1.5), 8.0, 4.0)
    cart.add(obj("CartModel", rot=(0, 90, 0), scale=(1, 0.6, 1)).prop(cart_obj.guid, collision=Collision.NONE,
                                                                     materials=[metal_mat.guid]))
    # «Тир»: две мишени-маскота навстречу друг другу по двум линиям, разный темп; выше прыжка — уворачиваться
    tir = trap_group("SW")
    for k, (z, sx, travel, freq) in enumerate(((-1.0, -4.5, 9.0, 0.15), (0.7, 4.5, -9.0, 0.12))):
        target = sweeper(tir, f"Target_{k}", z, sx, travel, freq, 0.0, (1.2, 2.2, 1.2), 7.0, 3.0)
        target.add(obj("Mascot", rot=(0, 90, 0)).prop(mascot_obj.guid, collision=Collision.NONE, tint=(0.95, 0.75, 0.3, 1)))

    # «Сцена»: пока корона на сцене, с навеса сыплются обломки (префаб как в Death Carousel: Mover вниз, удар оглушает
    # и отталкивает, у пола взрыв и исчезновение). Спавнер в выключенной группе, её включает и выключает режиссёр
    fall_h = 3.9   # точки под навесом (низ навеса 4.2): над ним обломок пролетел бы сквозь крышу без коллизии — не важно, но так видно
    debris_root = (obj("Debris")
                   .mover(MoverDir.CUSTOM, (0, -1, 0), 4.0)
                   .trigger(TriggerShape.SPHERE, radius=0.9,
                            on_enter=[act_stun(1.0, Targets.SOURCE),
                                      act_change_velocity(6.0, VelocityDir.TOWARDS_SOURCE, Op.ADD),
                                      act_change_velocity(3.0, VelocityDir.UP, Op.ADD)])
                   .logic(trig_enable(act_wait(fall_h / 4.0),
                                      act_spawn_effect(Effect.EXPLOSION, Targets.RECEIVER),
                                      act_kill(Targets.RECEIVER))))
    debris_root.add(obj("Rock", scale=(1.2, 1.2, 1.2)).prop(debris_obj.guid, collision=Collision.NONE, tint=(0.55, 0.3, 0.2, 1)))
    debris_prefab = mod.add_prefab(debris_root)
    stage_points = traps.add(obj("StageDebrisPoints"))
    points = [stage_points.add(obj(f"Point_{k}", pos=(px, DAIS_Y + fall_h, pz)))
              for k, (px, pz) in enumerate(((0.0, 0.3), *[polar(1.6, 72 * i + 10) for i in range(5)]))]
    stage_debris = traps.add(obj("StageDebris", pos=(0, DAIS_Y + fall_h, 0), active=False).spawner(
        [debris_prefab.guid], interval=(1.2, 2.5), kind=SpawnerType.ALWAYS, location=SpawnerLocation.ON_TARGETS,
        spawn_points=[p.transform_guid for p in points], count=1))
    return {"C": stage_debris}


def build(name: str, workshop: str = WORKSHOP) -> str:
    rng = random.Random("mascot-throne")
    mod = Mod(name, description="Rusted Park: the crown hops between four thrones. Stand in its ring to score every second, "
                                "punch the others out. / Трон маскота: корона перелетает между четырьмя тронами — стой в её "
                                "кольце, очко каждую секунду, выбивай остальных.",
              round_duration=ROUND, end_conditions=EndCondition.TIMER, placement=Placement.MOST_POINTS,
              # бой как в Ticket Rush (проверен плейтестом): 3 удара — смерть и респаун через 3 с в углу арены.
              # Плюс отброс от удара по схеме Death Carousel: weaponHitTrigger, m_hitType 1 = Melee,
              # Source — бьющий, Receiver — получивший, Towards Receiver = от бьющего
              settings_overrides={"respawnEnabled": True, "respawnTime": 3.0, "respawnInvulnerableTime": 2.0,
                                  "canPunch": True, "useHealth": True, "health": 3, "punchDamage": 1, "showHealthBar": True,
                                  "weaponHitTrigger": {"m_type": 80, "m_actions": [], "m_hitType": 1}},
              player_triggers={"weaponHitTrigger": [
                  act_change_velocity(PUNCH_PUSH, VelocityDir.TOWARDS_RECEIVER, Op.ADD, flags=Targets.RECEIVER),
                  act_change_velocity(PUNCH_LIFT, VelocityDir.UP, Op.ADD, flags=Targets.RECEIVER)],
                  # рывок после респауна. SimpleModPlayer сбрасывает множитель в 1 перед FireRespawnEvent, событие шлёт
                  # владелец игрока, Source = Receiver = сам игрок; при новой смерти до конца рывка респаун снова даст 1
                  "onRespawnTrigger": [act_modify_player_speed(DASH), act_wait(DASH_TIME), act_modify_player_speed(1.0)]})

    # --- ассеты
    def prop(fn): return mod.add_file_asset("prop", os.path.join(ASSETS, "models", fn))
    def tex(fn): return mod.add_file_asset("texture", os.path.join(ASSETS, "textures", fn))
    throne_obj, dais_obj, crown_obj, zone_obj = prop("throne.obj"), prop("throne_dais.obj"), prop("crown.obj"), prop("crown_zone.obj")
    booth_obj, mascot_obj, barrel_obj = prop("booth.obj"), prop("mascot_headless.obj"), prop("barrel.obj")
    rotor_obj, stand_obj = prop("ferris_wheel_rotor.obj"), prop("ferris_wheel_stand.obj")
    lamp_obj, fence_obj, roof_obj = prop("lamppost.obj"), prop("fence_segment.obj"), prop("carousel_roof.obj")
    tree_obj, hill_obj, trestle_obj = prop("dead_tree.obj"), prop("hill.obj"), prop("coaster_trestle.obj")
    rail_obj, debris_obj, cart_obj = prop("rail_segment.obj"), prop("debris.obj"), prop("cart.obj")
    creak_wav = mod.add_file_asset("audio", os.path.join(ASSETS, "audio", "creak.wav"))
    sweep_wav = mod.add_file_asset("audio", os.path.join(ASSETS, "audio", "sweep.wav"))
    concrete_tex = tex("concrete.png")
    paint_mat = mod.add_material("CarouselPaint", tex("carousel_paint.png"), tiling=(1.0, 1.0))
    rust_mat = mod.add_material("RustBooth", tex("rust_booth.png"), tiling=(2.0, 2.0))
    metal_mat = mod.add_material("RustMetal", tex("rust_metal.png"), tiling=(1.0, 1.0))
    dirt_mat = mod.add_material("Dirt", tex("dirt.png"), tiling=(20.0, 20.0))
    dais_mat = mod.add_material("Concrete_Dais", concrete_tex, tiling=(1.0, 1.0))

    def wall(parent, name, pos, model, rot=(0, 0, 0), scale=(1, 1, 1), mat=None, tint=(1, 1, 1, 1)):
        return parent.add(obj(name, pos=pos, rot=rot, scale=scale, layer=LAYER_WORLD_WALL)
                          .prop(model, collision=Collision.BOX, materials=[mat.guid] if mat else None, tint=tint))

    def deco(parent, name, pos, model, rot=(0, 0, 0), scale=(1, 1, 1), mat=None, tint=(1, 1, 1, 1)):
        return parent.add(obj(name, pos=pos, rot=rot, scale=scale)
                          .prop(model, collision=Collision.NONE, materials=[mat.guid] if mat else None, tint=tint))

    # --- пол 40 × 40 из четырёх плит вокруг дыры под лужу (как в Ticket Rush: сплошной пол закрыл бы воду)
    world = mod.add(obj("World"))
    x0, x1, z0, z1 = POND_RECT
    for key, (ax, bx, az, bz) in (("W", (-HALF, x0, -HALF, HALF)), ("E", (x1, HALF, -HALF, HALF)),
                                  ("S", (x0, x1, -HALF, z0)), ("N", (x0, x1, z1, HALF))):
        w, d = bx - ax, bz - az
        mat = mod.add_material(f"Concrete_{key}", concrete_tex, tiling=(w / 5, d / 5))
        world.add(obj(f"Ground_{key}", pos=((ax + bx) / 2, 0, (az + bz) / 2), scale=(w / 10, 1, d / 10), layer=LAYER_WORLD_GROUND)
                  .prop(PROP_PLANE, collision=Collision.MESH, materials=[mat.guid]))
    pond_c = ((x0 + x1) / 2, (z0 + z1) / 2)
    pond = world.add(obj("Pond", pos=(pond_c[0], -0.3, pond_c[1])).water(
        width=int(round(x1 - x0)), height=int(z1 - z0), cell=1.0,
        deep=(0.12, 0.45, 0.08, 0.8), shallow=(0.45, 1.0, 0.2, 0.8), froth=(0.8, 1.0, 0.6, 1)))
    pond.add(obj("KillVolume", pos=(0, -0.6, 0)).trigger(
        TriggerShape.BOX, size=(x1 - x0, 1, z1 - z0),
        on_enter=[act_spawn_effect(Effect.EXPLOSION, Targets.SOURCE), act_kill(Targets.SOURCE)]))

    # --- троны: помост (пол), кресло (стена), маяк — луч и лампы по краю помоста, горит, пока корона здесь или летит сюда
    thrones = mod.add(obj("Thrones"))
    beacons = {}
    for key, t in THRONES.items():
        x, z = t["xz"]
        group = thrones.add(obj(f"Throne_{key}", pos=(x, 0, z)))
        group.add(obj("Dais", layer=LAYER_WORLD_GROUND).prop(dais_obj.guid, collision=Collision.MESH, materials=[dais_mat.guid]))
        sx, sz = polar(SEAT_OFF, t["seat"])
        # модель смотрит в +Z; поворот Y на θ даёт направление (sin θ, cos θ) — разворачиваем лицом к центру помоста
        yaw = math.degrees(math.atan2(-sx, -sz))
        group.add(obj("Seat", pos=(sx, DAIS_Y, sz), rot=(0, yaw, 0), layer=LAYER_WORLD_WALL)
                  .prop(throne_obj.guid, collision=Collision.BOX, materials=[paint_mat.guid]))
        beacon = group.add(obj("Beacon", active=(key == "C")))
        beacon.add(obj("Beam", pos=(0, 6.0, 0), scale=(0.35, 12.0, 0.35))
                   .prop(PROP_CUBE, collision=Collision.NONE, shadow=Shadow.OFF, tint=(1.0, 0.85, 0.2, 1)))
        for k in range(10):
            bx, bz = polar(2.85, 36 * k + 18)
            beacon.add(obj(f"Bulb_{k}", pos=(bx, DAIS_Y + 0.12, bz), scale=(0.25, 0.25, 0.25))
                       .prop(PROP_SPHERE, collision=Collision.NONE, shadow=Shadow.OFF, tint=(1.0, 0.95, 0.4, 1)))
        beacons[key] = beacon

    # --- корона: кольцо зоны на полу, зона очков и цель ботов летят вместе (Play Tween Animation на корне).
    # On Stay: интервал общий на триггер (m_lastTriggerTime), но проверка идёт до его сброса в Update, поэтому в кадре
    # срабатывания очко получают все, кто внутри (ModTrigger.OnEvent). Источник — стоящий в зоне игрок.
    # Зона — отдельный ребёнок: её масштаб X/Z сжимается твином за стоянку (коллайдер Unity масштабируется вместе с
    # трансформом), корона и узел-цель не меняются
    crown = mod.add(obj("Crown", pos=(0, DAIS_Y, 0)))
    zone = crown.add(obj("Zone").trigger(
        TriggerShape.CAPSULE, radius=ZONE_R, height=8.0, stay_interval=1.0,
        on_stay=[act_change_score(1, Op.ADD, Targets.SOURCE)]))
    zone.add(obj("Ring", pos=(0, 0.01, 0)).prop(zone_obj.guid, collision=Collision.NONE, shadow=Shadow.OFF,
                                                 tint=(1.0, 0.8, 0.15, 1)))
    # двойная корона в финале: второй такой же триггер (+1 ещё раз) и красное кольцо чуть шире; включает режиссёр
    double = zone.add(obj("DoubleZone", active=False).trigger(
        TriggerShape.CAPSULE, radius=ZONE_R, height=8.0, stay_interval=1.0,
        on_stay=[act_change_score(1, Op.ADD, Targets.SOURCE)]))
    double.add(obj("DoubleRing", pos=(0, 0.02, 0), scale=(1.08, 1, 1.08))
               .prop(zone_obj.guid, collision=Collision.NONE, shadow=Shadow.OFF, tint=(1.0, 0.25, 0.1, 1)))
    crown.add(obj("CrownModel", pos=(0, 3.4, 0), scale=(1.3, 1.3, 1.3))
              .prop(crown_obj.guid, collision=Collision.NONE, tint=(1.0, 0.78, 0.1, 1))
              .mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Y, (0, 1, 0), 90.0))
    # цель ботов: первый узел с Is AI Goal (ModAINavigation.GetAIGoalNode, активность не проверяется). Позицию бот
    # читает каждый кадр (m_aiGoal.transform.position), поэтому узел просто летит с короной. Kill/Destroy узел не
    # убирает из списка (KillAction выключает объект, OnDestroy не вызывается) — переключать цель так нельзя
    goal = crown.add(obj("AIGoal", pos=(0, 0.35, 0)).ai_node(is_goal=True))

    # --- центр: сцена под навесом. Три столба — между хордами к внешним тронам, чтобы путь по прямой был свободен
    stage = world.add(obj("Stage"))
    for k, deg in enumerate((30, 150, 270)):
        px, pz = polar(3.4, deg)
        wall(stage, f"Post_{k}", (px, 2.1, pz), PROP_CUBE, scale=(0.25, 4.2, 0.25), mat=metal_mat)
    deco(stage, "Canopy", (0, 4.2, 0), roof_obj.guid, scale=(0.36, 0.4, 0.36), mat=paint_mat)
    on_crown = build_traps(mod, cart_obj, mascot_obj, rail_obj, debris_obj, metal_mat, sweep_wav, deco) if TRAPS else {}

    # --- средний план. Хорды между всеми тронами (спицы от центра и стороны треугольника) свободны: бот идёт по сетке к
    # ближайшему трону и дальше по прямой к короне. Укрытия — киоски снаружи треугольника, низкие ящики (0.5 м,
    # перепрыгиваются) — внутри треугольников и поперёк внешнего кольца
    mid = mod.add(obj("Midground"))
    for k, deg in enumerate((30, 150, 270)):
        bx, bz = polar(THRONE_R, deg)
        wall(mid, f"Booth_{k}", (bx, 0, bz), booth_obj.guid, rot=(0, -deg + 90 + rng.uniform(-8, 8), 0), mat=rust_mat)
    for k, (px, pz) in enumerate(((3.75, 2.17), (-3.75, 2.17))):   # центроиды треугольников сцена — север — юго-запад/восток
        wall(mid, f"Crate_Inner_{k}", (px, 0.25, pz), PROP_CUBE, rot=(0, rng.uniform(0, 90), 0), scale=(1.3, 0.5, 1.3), mat=rust_mat)
    for k, deg in enumerate((60, 120, 180, 240, 300)):
        cx_, cz_ = polar(16.0, deg)
        wall(mid, f"Crate_Ring_{k}", (cx_, 0.3, cz_), PROP_CUBE, rot=(0, -deg + rng.uniform(-6, 6), 0), scale=(2.6, 0.6, 1.0),
             mat=rust_mat)

    # --- мелочь у точек интереса: у колеса бочки и фонари, у тира мишени-маскоты и киоск, у пруда бочки на берегу
    decor = mod.add(obj("Decor"))
    for k, (dx, dz) in enumerate(((-4.2, 15.6), (-4.9, 16.3), (4.4, 15.8), (5.2, 15.2))):
        wall(decor, f"Barrel_N_{k}", (dx, 0, dz), barrel_obj.guid, rot=(0, rng.uniform(0, 360), 0), mat=metal_mat)
    gx, gz = polar(17.6, 210)
    wall(decor, "Gallery", (gx, 0, gz), booth_obj.guid, rot=(0, -210 + 90, 0), scale=(1.4, 1.1, 1.0), mat=rust_mat)
    for k, deg in enumerate((196, 224)):
        mx, mz = polar(16.3, deg)
        wall(decor, f"Target_{k}", (mx, 0, mz), mascot_obj.guid, rot=(0, rng.uniform(0, 360), rng.uniform(-8, 8)),
             tint=(0.95, 0.75, 0.3, 1))
    fx, fz = polar(9.2, 222)   # упавшая мишень у помоста — лежит, ниже прыжка
    deco(decor, "FallenTarget", (fx, 0.45, fz), mascot_obj.guid, rot=(90, rng.uniform(0, 360), 0), tint=(0.95, 0.75, 0.3, 1))
    for k, (dx, dz) in enumerate(((x1 + 0.8, z0 - 0.6), (x1 + 0.5, z1 + 0.9), (x0 + 0.6, z0 - 1.0))):
        wall(decor, f"Barrel_Pond_{k}", (dx, 0, dz), barrel_obj.guid, rot=(0, rng.uniform(0, 360), 0), mat=metal_mat)
    deco(decor, "SunkenBarrel", (pond_c[0] + 0.7, -0.45, pond_c[1] - 1.2), barrel_obj.guid, rot=(75, 30, 0), mat=metal_mat)
    # «Пруд»: две бочки покачиваются в кислоте — фоновое движение у самой опасной точки
    for k, (dx, dz, ph) in enumerate(((-0.8, 1.0, 0.0), (0.6, -0.1, 1.3))):
        deco(decor, f"FloatingBarrel_{k}", (pond_c[0] + dx, -0.55, pond_c[1] + dz), barrel_obj.guid,
             rot=(85, 60 * k + 20, 0), mat=metal_mat).simple_animator(anim_move_along_line(0.3, (0, 0.25, 0)), time_offset=ph)
    # кучки бочек на пустых площадках между хордами (≥ 3.5 м от хорд, бочка 1 м — низкая) и у забора, где вдоль
    # ограды шёл пробег 38 м; рядом обломки без коллизии
    for k, (bx, bz) in enumerate(((-6.8, 9.8), (6.8, 9.8), (-6.5, -11.2), (6.5, -11.2), (-7.0, -18.6), (7.5, -18.7),
                                  (-18.6, -9.5), (-18.7, 9.0), (-10.0, 18.7), (10.0, 18.6), (18.7, 12.0))):
        for j in range(2 if k < 4 else 1):
            wall(decor, f"Barrel_Pile_{k}_{j}", (bx + 0.9 * j, 0, bz + 0.5 * j), barrel_obj.guid,
                 rot=(0, rng.uniform(0, 360), 0), mat=metal_mat)
        if k < 4:
            deco(decor, f"Debris_Pile_{k}", (bx - 0.8, 0.15, bz - 0.9), debris_obj.guid,
                 rot=(rng.uniform(0, 360), rng.uniform(0, 360), 0), scale=(0.6,) * 3, tint=(0.5, 0.48, 0.45, 1))
    for k in range(8):   # фонари кольцом r 17.5, два покосились
        a = 45 * k + 22.5
        lx, lz = polar(17.5, a)
        tilt = (0, -a, 0) if k not in (2, 6) else (8, -a, -6)
        wall(decor, f"Lamppost_{k}", (lx, 0, lz), lamp_obj.guid, rot=tilt, mat=metal_mat)
    for k in range(12):  # обломки кучками у помостов внешних тронов
        key = ("N", "SW", "SE")[k % 3]
        tx, tz = THRONES[key]["xz"]
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(3.4, 4.6)
        deco(decor, f"Debris_{k}", (tx + r * math.cos(a), 0.15, tz + r * math.sin(a)), debris_obj.guid,
             rot=(rng.uniform(0, 360), rng.uniform(0, 360), 0), scale=(rng.uniform(0.4, 0.8),) * 3, tint=(0.5, 0.48, 0.45, 1))
    fence = decor.add(obj("Fence"))
    for i in range(13):
        t = -HALF + 1.5 + 3.0 * i
        for key, pos, rot in ((f"N_{i}", (t, 0, HALF - 0.5), (0, 0, 0)), (f"S_{i}", (t, 0, -HALF + 0.5), (0, 0, 0)),
                              (f"E_{i}", (HALF - 0.5, 0, t), (0, 90, 0)), (f"W_{i}", (-HALF + 0.5, 0, t), (0, 90, 0))):
            wall(fence, f"Fence_{key}", pos, fence_obj.guid, rot=rot, mat=metal_mat)

    # --- задний план: колесо обозрения за северным забором (ориентир трона «Колесо»), руины горок на юге, холмы, деревья
    backdrop = mod.add(obj("Backdrop"))
    backdrop.add(obj("OuterGround", pos=(0, -0.6, 0), scale=(18, 1, 18))
                 .prop(PROP_PLANE, collision=Collision.NONE, materials=[dirt_mat.guid]))
    backdrop.add(obj("FallVolume", pos=(0, -8, 0)).trigger(TriggerShape.BOX, size=(400, 4, 400), on_enter=[act_kill(Targets.SOURCE)]))
    wheel = backdrop.add(obj("FerrisWheel", pos=(0, 7.1, 29))
                         .prop(stand_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    wheel.add(obj("Rotor").prop(rotor_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid])
              .mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Z, (0, 0, 1), 10.0))
    coaster = backdrop.add(obj("RuinedCoaster", pos=(0, -0.1, -36)))
    for i in range(7):
        x = -18 + 6 * i
        coaster.add(obj(f"Trestle_{i}", pos=(x, 0, 0)).prop(trestle_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
        if i < 6 and i != 2:
            coaster.add(obj(f"Rail_{i}", pos=(x + 3, 10.3, 0), rot=(0, 90, 0))
                        .prop(rail_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    for i in range(12):
        a = 2 * math.pi * i / 12 + rng.uniform(-0.1, 0.1)
        r, s = rng.uniform(58, 72), rng.uniform(0.8, 1.6)
        backdrop.add(obj(f"Hill_{i}", pos=(r * math.cos(a), -0.2, r * math.sin(a)), rot=(0, rng.uniform(0, 360), 0),
                         scale=(s, s * rng.uniform(0.8, 1.4), s)).prop(hill_obj.guid, collision=Collision.NONE, materials=[dirt_mat.guid]))
    for i in range(16):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(26, 48)
        backdrop.add(obj(f"DeadTree_{i}", pos=(r * math.cos(a), -0.1, r * math.sin(a)), rot=(0, rng.uniform(0, 360), rng.uniform(-6, 6)),
                         scale=(rng.uniform(0.8, 1.4),) * 3).prop(tree_obj.guid, collision=Collision.NONE, tint=(0.35, 0.28, 0.2, 1)))

    # --- спавны: общий круг r 6.5 вокруг сцены (до первой зоны всем 4.1 м), респауны в углах — далеко от всех тронов
    spawns = mod.add(obj("Player Spawnpoints"))
    spawns.add(obj("Spawn_Ring", pos=(0, 1, 0)).player_spawn(SpawnShape.CIRCLE, SpawnUsage.INITIAL, radius=6.5, shared=True))
    for i, (x, z) in enumerate(((16.5, 16.5), (-16.5, 16.5), (16.5, -16.5), (-16.5, -16.5))):
        spawns.add(obj(f"Respawn_{i}", pos=(x, 1, z)).player_spawn(SpawnShape.POINT, SpawnUsage.RESPAWN))

    # --- режиссёр. На каждой стоянке: кольцо сжимается (твин масштаба зоны на всю стоянку), включается ловушка трона;
    # за WARN секунд до ухода — маяк следующего трона, скрип и сообщение; на уходе кольцо расправляется за время полёта,
    # ловушка гаснет; маяк прежнего трона гаснет, когда корона долетела. С первой стоянки после FINALE — двойная корона.
    # Твины не ждут: следующее действие идёт сразу, паузы дают только Wait
    plan = schedule(random.Random("mascot-throne-schedule"))
    chain = [act_show_message("Займи трон с короной! / Take the crowned throne!", 3.0)]
    now, finale_on = 0.0, False
    for i, (cur, arrive, leave) in enumerate(plan):
        chain.append(act_play_tween([zone.transform_guid], Tween.LOCAL_SCALE, end=(SHRINK, 1, SHRINK),
                                    end_type=TweenValue.SPECIFIC, seconds=leave - arrive - 0.2, ease=Ease.LINEAR))
        if cur in on_crown:
            chain.append(act_set_active(ActiveState.ENABLED, [on_crown[cur].transform_guid]))
        if arrive >= FINALE and not finale_on:
            finale_on = True
            chain += [act_set_active(ActiveState.ENABLED, [double.transform_guid]),
                      act_show_message("Двойная корона! / Double crown!", 2.5)]
        if i + 1 == len(plan):
            break
        nxt = plan[i + 1][0]
        t = THRONES[nxt]
        nx, nz = t["xz"]
        chain += [act_wait(leave - WARN - now),
                  act_set_active(ActiveState.ENABLED, [beacons[nxt].transform_guid]),
                  act_play_sound(creak_wav.guid, 1.0, Targets.RECEIVER),
                  act_show_message(f"Корона летит к {t['ru']}! / The crown flies to {t['en']}!", WARN),
                  act_wait(WARN),
                  act_play_tween([zone.transform_guid], Tween.LOCAL_SCALE, end=(1, 1, 1), end_type=TweenValue.SPECIFIC,
                                 seconds=MOVE, ease=Ease.EASE_OUT_QUAD),
                  act_play_tween([crown.transform_guid], Tween.LOCAL_POSITION, end=(nx, DAIS_Y, nz), end_type=TweenValue.SPECIFIC,
                                 seconds=MOVE, ease=Ease.EASE_IN_OUT_QUAD)]
        if cur in on_crown:
            chain.append(act_set_active(ActiveState.DISABLED, [on_crown[cur].transform_guid]))
        chain += [act_wait(MOVE), act_set_active(ActiveState.DISABLED, [beacons[cur].transform_guid])]
        now = plan[i + 1][1]
    mod.add(obj("Director").logic(trig_round_start(*chain)))
    mod.add(obj("Notes").note("Сгенерировано build_mod.py из packs/abandoned-park/minigames/mascot-throne/DESIGN.md\n"
                              "Расписание короны (трон, прибытие–уход, с): "
                              + ", ".join(f"{k} {a:.1f}–{b:.1f}" for k, a, b in plan)))
    out = mod.write(workshop)

    os.makedirs(os.path.join(HERE, "plan"), exist_ok=True)
    mod.preview_image = os.path.join(HERE, "plan", "preview.png")
    plan_view.render_preview(out, mod.preview_image)

    # --- сетка ботов: второй проход. Узел в центре каждого помоста; в узел-цель короны ведут связи только от них.
    # Поиск пути (ModAINavigation.GetPath) помечает узел при первой постановке в очередь, поэтому корону «займёт»
    # ближайший к боту помост — с него бот идёт к короне по прямой по свободной хорде
    specials = [{"name": f"Nav_Throne_{k}", "pos": (t["xz"][0], DAIS_Y + 0.35, t["xz"][1]), "kind": "ground"}
                for k, t in THRONES.items()]
    nodes, edges, warnings = navgen.generate(out, specials)
    nav = mod.add(obj("AI Navigation"))
    node_objs = [nav.add(obj(n, pos=pos).ai_node()) for n, pos in nodes]
    link_ai_nodes(node_objs + [goal], edges + [(i, len(nodes)) for i, (n, _) in enumerate(nodes) if n.startswith("Nav_Throne_")]
                  + [(len(nodes), i) for i, (n, _) in enumerate(nodes) if n.startswith("Nav_Throne_")])
    for w in warnings:
        print("сетка ботов:", w)
    print(f"сетка ботов: {len(nodes)} узлов + цель, {len(edges)} связей")
    print("расписание короны:", ", ".join(f"{k} {a:.1f}–{b:.1f}" for k, a, b in plan))
    return mod.write(workshop)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = build(sys.argv[1] if len(sys.argv) > 1 else "Mascot Throne", sys.argv[2] if len(sys.argv) > 2 else WORKSHOP)
    print("written:", out)
