"""Собирает мод Coaster Run по DESIGN.md в папку WorkshopMods редактора.

Запуск из корня репозитория:  python packs/abandoned-park/minigames/coaster-run/build_mod.py [имя мода] [папка WorkshopMods]
По умолчанию пишет «Coaster Run» в WorkshopMods редактора. Сцену, настройки и ассеты пересобирает целиком; превью
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
import plan_view  # noqa: E402

ASSETS = os.path.join(ROOT, "packs", "abandoned-park", "assets")
WORKSHOP = r"%USERPROFILE%\AppData\LocalLow\Rebuilt Games\Pummel Party\WorkshopMods"
HERE = os.path.dirname(os.path.abspath(__file__))

# Игрок по ModSettings шаблона: бег 6 м/с, прыжок 7 м/с при гравитации 25 → 0.98 м вверх, 3.4 м в длину, ступенька 0.5.
TRACK_Y = 4.0         # верх станции, балок S2 и полотна S3; ров под ними на y 0
LANES = (-2.6, 0.0, 2.6)   # x трёх балок S2; между краями 1.3 м — перескакиваются
RAIL_TOP = 0.18       # верх коллизии rail_segment.obj над его pivot (рельсы), низ — −0.5
# S2: куски балок по z, (начало, конец, ржавый?). Левая — два разрыва 2.4 м; средняя — сплошная, но с ржавыми
# пролётами по 4 м (пропав, не перепрыгиваются — ждать или уйти на соседнюю); правая — разрыв 3.0 м на пределе прыжка
LANE_SEGMENTS = (
    ((8.0, 16.0, False), (18.4, 28.0, False), (30.4, 40.0, False)),
    ((8.0, 14.0, False), (14.0, 18.0, True), (18.0, 26.0, False), (26.0, 30.0, True), (30.0, 40.0, False)),
    ((8.0, 12.0, False), (13.8, 20.0, False), (23.0, 30.0, False), (31.6, 40.0, False)),
)
DITCH = (-8.0, 8.0, 8.0, 39.0)   # x0, x1, z0, z1 рва под S2
# упал в ров — телепорт, как в остальных секциях (прожарка 2026-10-25): пешком назад по лестнице выходило 8–10 с,
# дороже, чем падение с петли. До DITCH_SPLIT — на станцию, дальше — на левую балку у z 20 (сплошной кусок 18.4–28)
DITCH_SPLIT = 24.0
STAIR_X = (5.6, 8.0)  # лестница из рва на станцию вдоль правой стены, 9 ступеней по 0.44 м: z 20 → 8
STAIR_Z0, STAIR_N = 20.0, 9
BED = (40.0, 60.0, 5.2)    # полотно вагонеток: z0, z1, ширина
# полотно сдвинуто влево (x −3.9…1.3), чтобы правая балка S2 продолжалась обходом вагонеток: риск правой дорожки
# (разрыв 3 м) окупается — по обходу вагонеток нет, но он шириной в балку, над кислотой и с разрывом 2.4 м
BED_X = -1.3
CARTS = ((-3.05, 0.14, 0.0), (-1.3, 0.11, 2.5), (0.45, 0.17, 1.2))   # x, циклов/с, сдвиг фазы с
BYPASS = ((40.0, 47.6), (50.0, 60.0))   # куски обхода по z на x LANES[2]
CART_RUN = 14.0       # ход вагонетки навстречу от z 57
LIFT_TOP = (72.0, 9.0)     # подъём: от конца полотна (z 60, y 4) до площадки CP4
CP4 = (-3.0, 3.0, 72.0, 78.0)
LOOP_C, LOOP_R = (14.0, 78.0), 14.0   # дуга сломанной петли: от (0, 78) по +Z до (14, 92) по +X
PLATE = 1.8
PLATE_TOPS = (9.3, 9.6, 9.4, 9.8, 10.0, 9.7)   # перепад соседних ≤ 0.4 м
PLATE_BOB = {1: 0.7, 4: 0.7}   # качаются вверх на столько, 0.3 цикла/с; в верхней точке на них не запрыгнуть
PLATE_RUST = (2, 5)
CP5 = (14.0, 19.0, 89.0, 95.0, 9.5)   # x0, x1, z0, z1, верх
DROP_END = (31.0, 5.0)     # спуск до x 31, y 5
PAD_X = (32.0, 34.2)       # батут на нижней площадке у края; разрыв до финиша 1.8 м, но финиш на 2 м выше
PAD_SPEED = 13.0           # Set Up: пик 3.4 м, до высоты +2 м за 0.85 с — 5.1 м вперёд на бегу
DECK = (36.0, 46.0, 7.0)   # финишная площадка x0, x1, верх
TRACK_Z = 92.0             # ось S5
FINISH_X = 40.0
PODIUM_X = 42.5
# Ловушка падения с петли — сразу под плитами (верх ниже самого низкого дна плиты 8.85), а не у воды: за 7 м падения
# игрок по инерции пролетает вперёд 4–5 м и попадал в зону S5 — переносило на следующий этап (плейтест 2026-10-24)
LOOP_CATCH = (-6.0, 16.0, 76.0, 97.0, 8.3)   # x0, x1, z0, z1, верх
WARN_BLINK = 0.25     # перед исчезновением 4 смены цвета красный/жёлтый по 0.25 с — ровно секунда            # ложа финишировавших: x 42.5…46 со стенами 2.2 м
PUNCH_PUSH, PUNCH_LIFT = 5.0, 3.0   # м/с от удара: сбить с балки можно, улететь с полотна — вряд ли
ROUND = 45.0          # чистый бег ≈ 23 с: первый ждёт в ложе ≤ ~20 с (было 60, прожарка 2026-10-25); кто не добежал — по рубежам


def ramp(name, p0, p1, width, thick, **kw):
    """Наклонный куб: верхняя грань от p0 до p1 (середины торцов), Box-коллизия поворачивается вместе с объектом."""
    dx, dy, dz = (p1[i] - p0[i] for i in range(3))
    flat = math.hypot(dx, dz)
    length = math.hypot(flat, dy)
    yaw, pitch = math.atan2(dx, dz), -math.atan2(dy, flat)
    up = (math.sin(yaw) * math.sin(pitch), math.cos(pitch), math.cos(yaw) * math.sin(pitch))
    mid = [(p0[i] + p1[i]) / 2 - up[i] * thick / 2 for i in range(3)]
    return obj(name, pos=mid, rot=(math.degrees(pitch), math.degrees(yaw), 0), scale=(width, thick, length), **kw)


def slab(name, x0, x1, z0, z1, top, thick=0.5, **kw):
    return obj(name, pos=((x0 + x1) / 2, top - thick / 2, (z0 + z1) / 2), scale=(x1 - x0, thick, z1 - z0), **kw)


def build(name: str, workshop: str = WORKSHOP) -> str:
    rng = random.Random("coaster-run")
    mod = Mod(name, template="Third Person Obstacle Course",
              description="Rusted Park: race across the collapsed roller coaster — rails over a ditch, runaway carts, "
                          "a broken loop above the acid pond. / Горки без рельс: гонка по обрушенным американским горкам.",
              round_duration=ROUND, end_conditions=EndCondition.TIMER | EndCondition.FINISH,
              # Finish Order = по очкам: Set Placement прибавляет 100·(N − k), рубежи — по +1, кто не добежал — ниже всех
              placement=Placement.FINISH_ORDER,
              # удар не убивает (без здоровья у игрока 1 HP), а отталкивает через weaponHitTrigger (m_hitType 1 = Melee).
              # Респаун включён только ради страховочной зоны смерти: падения с трассы — телепорт на чекпоинт
              settings_overrides={"respawnEnabled": True, "respawnTime": 2.0, "respawnInvulnerableTime": 1.0,
                                  "useHealth": False, "showHealthBar": False,
                                  "canPunch": True, "punchDamage": 0, "punchStunsTarget": False,
                                  "weaponHitTrigger": {"m_type": 80, "m_actions": [], "m_hitType": 1}},
              player_triggers={"weaponHitTrigger": [
                  act_change_velocity(PUNCH_PUSH, VelocityDir.TOWARDS_RECEIVER, Op.ADD, flags=Targets.RECEIVER),
                  act_change_velocity(PUNCH_LIFT, VelocityDir.UP, Op.ADD, flags=Targets.RECEIVER)]})

    # --- ассеты
    def prop(fn): return mod.add_file_asset("prop", os.path.join(ASSETS, "models", fn))
    def tex(fn): return mod.add_file_asset("texture", os.path.join(ASSETS, "textures", fn))
    def wav(fn): return mod.add_file_asset("audio", os.path.join(ASSETS, "audio", fn))
    rail_obj, cart_obj, trestle_obj = prop("rail_segment.obj"), prop("cart.obj"), prop("coaster_trestle.obj")
    mascot_obj, barrel_obj = prop("mascot_headless.obj"), prop("barrel.obj")
    # колесо из двух моделей: крутится только ротор, опоры стоят (pivot у обеих в ступице)
    rotor_obj, stand_obj = prop("ferris_wheel_rotor.obj"), prop("ferris_wheel_stand.obj")
    lamp_obj, hill_obj, tree_obj = prop("lamppost.obj"), prop("hill.obj"), prop("dead_tree.obj")
    finish_wav, rumble_wav, creak_wav = wav("finish.wav"), wav("cart_rumble.wav"), wav("creak.wav")
    metal_mat = mod.add_material("RustMetal", tex("rust_metal.png"), tiling=(1.0, 1.0))
    paint_mat = mod.add_material("RustBooth", tex("rust_booth.png"), tiling=(1.0, 1.0))
    concrete_mat = mod.add_material("Concrete", tex("concrete.png"), tiling=(4.0, 4.0))
    dirt_mat = mod.add_material("Dirt", tex("dirt.png"), tiling=(20.0, 20.0))
    # исчезающие куски без текстуры: tint умножается на альбедо (ModProp.SetColor → _Color), и на тёмной rust_metal
    # переход рыжий → красный почти не виден. Чистый цвет читается издалека и сам говорит «этот кусок опасный»
    rust_tint = (0.85, 0.42, 0.12, 1.0)
    warn_tints = ((1.0, 0.05, 0.03, 1.0), (1.0, 0.9, 0.1, 1.0))

    track = mod.add(obj("Track"))
    checkpoints = mod.add(obj("Checkpoints"))
    logic = mod.add(obj("Logic"))
    decor = mod.add(obj("Decor"))
    nav_points = []   # (имя, (x, y, z)) — узлы ботов по ходу трассы; связи задаются ниже

    def crumbling(name, target, period=(6.0, 9.0), pos=(0, 0, 0), restore=rust_tint):
        """Ржавый пролёт: по таймеру скрипит и секунду мигает красным/жёлтым, пропадает на 2.5 с и возвращается.
        Logic на отдельном объекте, иначе таймер выключился бы вместе с пролётом. Цепочка 3.5 с короче интервала."""
        blink = []
        for k in range(4):
            blink += [act_set_color(warn_tints[k % 2], targets=[target.transform_guid]), act_wait(WARN_BLINK)]
        logic.add(obj(name, pos=pos).logic(trig_timer(
            period[0],
            act_play_sound(creak_wav.guid, 1.0, Targets.RECEIVER),
            *blink,
            act_set_active(ActiveState.DISABLED, [target.transform_guid]),
            act_wait(2.5),
            act_set_active(ActiveState.ENABLED, [target.transform_guid]),
            act_set_color(restore, targets=[target.transform_guid]),
            max_interval=period[1])))

    def checkpoint(name, pos, yaw):
        return checkpoints.add(obj(name, pos=pos, rot=(0, yaw, 0)))

    def fall_zone(name, x0, x1, z0, z1, cp, top=2.0, height=3.0):
        """Триггер под трассой: всплеск у места падения, перенос на чекпоинт лицом по трассе, искры уже там.
        Match Transform по игроку вызывает SimpleModPlayer.TeleportPlayer (поворот камеры по Y)."""
        logic.add(obj(name, pos=((x0 + x1) / 2, top - height / 2, (z0 + z1) / 2)).trigger(
            TriggerShape.BOX, size=(x1 - x0, height, z1 - z0),
            on_enter=[act_spawn_effect(Effect.EXPLOSION, Targets.SOURCE),
                      act_match_transform(cp.transform_guid, values=1 | 2 | 4 | 16, flags=Targets.SOURCE),
                      act_spawn_effect(Effect.SPARKLES, Targets.SOURCE)]))

    def gate(name, pos, size):
        """Рубеж: +1 очко один раз — дальность для тех, кто не добежит (Finish Order считает по очкам)."""
        logic.add(obj(name, pos=pos).trigger(TriggerShape.BOX, size=size, one_use_per_player=True,
                                             on_enter=[act_change_score(1, Op.ADD, Targets.SOURCE)]))

    # --- S1 станция: сплошной блок до дна рва, бортики выше прыжка по бокам и сзади
    track.add(slab("Station", -8.0, 8.0, -4.0, 8.0, TRACK_Y, thick=TRACK_Y, layer=LAYER_WORLD_GROUND)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[concrete_mat.guid]))
    for nm, x0, x1, z0, z1 in (("Rail_L", -8.0, -7.7, -4.0, 8.0), ("Rail_R", 7.7, 8.0, -4.0, 8.0),
                               ("Rail_Back", -8.0, 8.0, -4.0, -3.7)):
        track.add(slab(nm, x0, x1, z0, z1, TRACK_Y + 1.4, thick=1.4, layer=LAYER_WORLD_WALL)
                  .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
    mod.add(obj("Player Spawnpoints")).add(
        obj("Spawn_Line", pos=(0, TRACK_Y + 1, 1.0)).player_spawn(SpawnShape.LINE, SpawnUsage.BOTH, line_length=10.0))
    nav_points.append(("Nav_Station", (0, TRACK_Y + 0.5, 3.0)))

    # --- S2 рельсы: rail_segment.obj 6 м, Box по габариту 1.3 × 0.68 (верх — рельсы)
    lanes_nav = []
    for li, (x, segs) in enumerate(zip(LANES, LANE_SEGMENTS)):
        nodes = []
        for si, (z0, z1, rusty) in enumerate(segs):
            seg = track.add(obj(f"Lane_{'LCR'[li]}_{si}", pos=(x, TRACK_Y - RAIL_TOP, (z0 + z1) / 2),
                                scale=(1, 1, (z1 - z0) / 6.0), layer=LAYER_WORLD_GROUND)
                            .prop(rail_obj.guid, collision=Collision.BOX, materials=[] if rusty else [metal_mat.guid],
                                  tint=rust_tint if rusty else (1, 1, 1, 1)))
            if rusty:
                crumbling(f"RustLogic_{'LCR'[li]}_{si}", seg, pos=(x, TRACK_Y, (z0 + z1) / 2))
            nodes += [(x, TRACK_Y + 0.5, z0 + 1.0), (x, TRACK_Y + 0.5, z1 - 0.6)]
        lanes_nav.append(nodes)
    # боты идут по левой: разрывы 2.4 м они берут сами (прыгают, сбегая с края), ржавые пролёты и 3 м — нет
    nav_points += [(f"Nav_L_{i}", p) for i, p in enumerate(lanes_nav[0])]

    # --- ров под S2: пол y 0, стены 4 м (наверх не выбраться), лестница вдоль правой стены назад к станции
    x0, x1, z0, z1 = DITCH
    track.add(slab("Ditch", x0, x1, z0, z1, 0.0, thick=1.0, layer=LAYER_WORLD_GROUND)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[dirt_mat.guid], tint=(0.75, 0.7, 0.6, 1)))
    for nm, a0, a1, b0, b1, top in (("DitchWall_L", x0 - 0.5, x0, z0, z1 + 0.5, TRACK_Y),
                                    ("DitchWall_R", x1, x1 + 0.5, z0, z1 + 0.5, TRACK_Y),
                                    ("DitchWall_End", x0, x1, z1, z1 + 0.5, TRACK_Y - 0.5)):
        track.add(slab(nm, a0, a1, b0, b1, top, thick=top, layer=LAYER_WORLD_WALL)
                  .prop(PROP_CUBE, collision=Collision.BOX, materials=[concrete_mat.guid]))
    step_len = (STAIR_Z0 - z0) / STAIR_N
    for i in range(1, STAIR_N + 1):
        top = TRACK_Y * i / STAIR_N
        za = STAIR_Z0 - i * step_len
        track.add(slab(f"Stairs_{i}", STAIR_X[0], STAIR_X[1], za, za + step_len, top, thick=top, layer=LAYER_WORLD_GROUND)
                  .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
    ditch_nav = [(f"Nav_Ditch_{i}", (x, 0.5, z)) for i, (x, z) in enumerate(
        (x, z) for z in (11.0, 17.0, 23.0, 29.0, 35.0) for x in (-5.5, -1.3, 3.0))]
    stair_nav = [("Nav_DitchHub", (4.4, 0.5, STAIR_Z0 + 2.5)), ("Nav_StairsBottom", (6.8, 0.5, STAIR_Z0 + 2.5)),
                 ("Nav_StairsMid", (6.8, TRACK_Y / 2 + 0.5, (STAIR_Z0 + z0) / 2)), ("Nav_StairsTop", (6.8, TRACK_Y + 0.5, z0 + 0.6))]

    # --- S3 вагонетки: полотно над прудом, 3 вагонетки катаются навстречу (Move Along Line по локальной −Z).
    # Движущийся коллайдер игрока не толкает, поэтому у вагонетки только триггер: оглушить и отбросить от неё
    bz0, bz1, bw = BED
    track.add(slab("CartBed", BED_X - bw / 2, BED_X + bw / 2, bz0, bz1, TRACK_Y, layer=LAYER_WORLD_GROUND)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid], tint=(0.7, 0.6, 0.5, 1)))
    # обход вагонеток — продолжение правой балки S2
    for si, (z0, z1) in enumerate(BYPASS):
        track.add(obj(f"Bypass_{si}", pos=(LANES[2], TRACK_Y - RAIL_TOP, (z0 + z1) / 2), scale=(1, 1, (z1 - z0) / 6.0),
                      layer=LAYER_WORLD_GROUND).prop(rail_obj.guid, collision=Collision.BOX, materials=[metal_mat.guid]))
    for x, _, _ in CARTS:   # рельсы под вагонетками — декор, без коллизии
        for k in range(3):
            track.add(obj("BedRail", pos=(x, TRACK_Y - RAIL_TOP + 0.08, bz0 + 3.4 + 6.6 * k), scale=(0.9, 1, 1.1))
                      .prop(rail_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    carts = track.add(obj("Carts"))
    for k, (x, freq, phase) in enumerate(CARTS):
        cart = carts.add(obj(f"Cart_{k}", pos=(x, TRACK_Y, bz1 - 3.0))
                         .trigger(TriggerShape.BOX, size=(1.5, 1.4, 2.3), center=(0, 0.7, 0),
                                  on_enter=[act_stun(0.8, Targets.SOURCE),
                                            act_change_velocity(6.0, VelocityDir.TOWARDS_SOURCE, Op.ADD),
                                            act_change_velocity(4.0, VelocityDir.UP, Op.ADD),
                                            act_play_sound(rumble_wav.guid, 0.8, Targets.RECEIVER)])
                         .simple_animator(anim_move_along_line(freq, (0, 0, -CART_RUN)), time_offset=phase))
        cart.add(obj("Body").prop(cart_obj.guid, collision=Collision.NONE, materials=[paint_mat.guid]))
    g0, g1 = BED_X - bw / 2, LANES[2] + 0.65   # рубеж на полотне и на обходе
    gate("Gate_S3", ((g0 + g1) / 2, TRACK_Y + 1.5, bz0 + 1.0), (g1 - g0, 3.0, 1.0))
    cp3 = checkpoint("CP3", (0, TRACK_Y + 1.5, bz0 + 1.5), 0)
    nav_points += [("Nav_Bed_0", (0, TRACK_Y + 0.5, 42.0)), ("Nav_Bed_1", (0, TRACK_Y + 0.5, 50.0)),
                   ("Nav_Bed_2", (0, TRACK_Y + 0.5, 58.0))]

    # --- S4 подъём (узкое место 2.6 м) и площадка CP4
    lz, ly = LIFT_TOP
    track.add(ramp("Lift", (0, TRACK_Y, bz1), (0, ly, lz), 2.6, 0.5, layer=LAYER_WORLD_GROUND)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
    cx0, cx1, cz0, cz1 = CP4
    track.add(slab("CP4Deck", cx0, cx1, cz0, cz1, ly, layer=LAYER_WORLD_GROUND)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
    cp_lift = checkpoint("CP_Lift", (0, TRACK_Y + 1.5, bz1 - 2.0), 0)
    cp4 = checkpoint("CP4", (0, ly + 1.5, cz0 + 2.0), 0)
    gate("Gate_S4", (0, ly + 1.5, cz0 + 1.5), (cx1 - cx0, 3.0, 1.0))
    nav_points += [("Nav_LiftBottom", (0, TRACK_Y + 0.5, bz1 + 1.0)), ("Nav_LiftTop", (0, ly + 0.5, cz0 + 1.0)),
                   ("Nav_CP4", (0, ly + 0.5, cz1 - 0.8))]

    # --- сломанная петля: 6 плит по дуге, две качаются (возят стоящего), две ржавые
    for i, top in enumerate(PLATE_TOPS):
        th = math.radians(90.0 * (i + 1) / (len(PLATE_TOPS) + 1))
        px, pz = LOOP_C[0] - LOOP_R * math.cos(th), LOOP_C[1] + LOOP_R * math.sin(th)
        bob = PLATE_BOB.get(i, 0.0)
        base = top - bob / 2 if bob else top   # качается вокруг заданной высоты
        plate = track.add(obj(f"Loop_{i}", pos=(px, base - 0.2, pz), rot=(0, math.degrees(th), 0),
                              scale=(PLATE, 0.4, PLATE), layer=LAYER_WORLD_GROUND)
                          .prop(PROP_CUBE, collision=Collision.BOX, materials=[] if i in PLATE_RUST else [metal_mat.guid],
                                tint=rust_tint if i in PLATE_RUST else (0.85, 0.85, 0.85, 1)))
        if bob:
            plate.simple_animator(anim_move_along_line(0.3, (0, bob, 0)), time_offset=1.1 * i)
        if i in PLATE_RUST:
            crumbling(f"RustLogic_Loop_{i}", plate, period=(5.0, 8.0), pos=(px, top, pz))
        else:   # под качающимися стойка мешала бы ходу вниз — только под неподвижными
            if not bob:
                decor.add(obj(f"LoopPost_{i}", pos=(px, (base - 0.4) / 2, pz), scale=(0.3, base - 0.4, 0.3))
                          .prop(PROP_CUBE, collision=Collision.NONE, materials=[metal_mat.guid]))
        nav_points.append((f"Nav_Loop_{i}", (px, top + 0.5, pz)))

    # --- S5 площадка CP5, спуск с барьерами, батут, финиш
    px0, px1, pz0, pz1, ptop = CP5
    track.add(slab("CP5Deck", px0, px1, pz0, pz1, ptop, layer=LAYER_WORLD_GROUND)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
    cp5 = checkpoint("CP5", (px0 + 1.5, ptop + 1.5, TRACK_Z), 90)
    gate("Gate_S5", (px0 + 1.0, ptop + 1.5, TRACK_Z), (1.0, 3.0, pz1 - pz0))
    dx, dy = DROP_END
    track.add(ramp("Drop", (px1, ptop, TRACK_Z), (dx, dy, TRACK_Z), 3.2, 0.5, layer=LAYER_WORLD_GROUND)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
    slope = (ptop - dy) / (dx - px1)
    for k, hx in enumerate((23.0, 27.0)):   # низкие барьеры-шпалы поперёк спуска, 0.4 м
        hy = ptop - (hx - px1) * slope
        track.add(obj(f"Hurdle_{k}", pos=(hx, hy + 0.2, TRACK_Z), rot=(0, 0, -math.degrees(math.atan(slope))),
                      scale=(0.3, 0.4, 3.2), layer=LAYER_WORLD_WALL)
                  .prop(PROP_CUBE, collision=Collision.BOX, materials=[paint_mat.guid]))
    track.add(slab("PadDeck", dx, PAD_X[1], TRACK_Z - 1.6, TRACK_Z + 1.6, dy, layer=LAYER_WORLD_GROUND)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
    pad = track.add(obj("JumpPad", pos=((PAD_X[0] + PAD_X[1]) / 2, dy, TRACK_Z)).trigger(
        TriggerShape.BOX, size=(PAD_X[1] - PAD_X[0], 1.5, 3.2), center=(0, 0.8, 0),
        on_enter=[act_change_velocity(PAD_SPEED, VelocityDir.UP, Op.SET)]))
    pad.add(obj("Plate", pos=(0, 0.05, 0), scale=(PAD_X[1] - PAD_X[0], 0.1, 3.0))
            .prop(PROP_CUBE, collision=Collision.NONE, tint=(0.9, 0.2, 0.1, 1)))
    fx0, fx1, ftop = DECK
    track.add(slab("FinishDeck", fx0, fx1, TRACK_Z - 3.0, TRACK_Z + 3.0, ftop, layer=LAYER_WORLD_GROUND)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[concrete_mat.guid]))
    nav_points += [("Nav_CP5", (px0 + 1.5, ptop + 0.5, TRACK_Z)), ("Nav_DropTop", (px1 + 0.5, ptop + 0.5, TRACK_Z)),
                   ("Nav_DropMid", (25.0, ptop - (25.0 - px1) * slope + 0.5, TRACK_Z)),
                   ("Nav_Pad", ((PAD_X[0] + PAD_X[1]) / 2, dy + 0.5, TRACK_Z)), ("Nav_Deck", (fx0 + 2.0, ftop + 0.5, TRACK_Z))]

    # финишная арка: два столба и шахматная перекладина; триггер — по всей ширине площадки
    arch = track.add(obj("FinishArch", pos=(FINISH_X, ftop, TRACK_Z)))
    for side in (-1, 1):
        arch.add(obj("Post", pos=(0, 1.75, side * 2.85), scale=(0.3, 3.5, 0.3), layer=LAYER_WORLD_WALL)
                 .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
    for k in range(12):
        for row in range(2):
            white = (k + row) % 2 == 0
            arch.add(obj("Checker", pos=(0, 3.3 + 0.25 * row, -2.75 + 0.5 * k), scale=(0.2, 0.25, 0.5))
                     .prop(PROP_CUBE, collision=Collision.NONE, tint=(0.95, 0.95, 0.9, 1) if white else (0.1, 0.1, 0.1, 1)))
    podium_point = checkpoint("PodiumPoint", ((PODIUM_X + fx1) / 2, ftop + 1.5, TRACK_Z), 270)
    logic.add(obj("FinishTrigger", pos=(FINISH_X, ftop + 1.5, TRACK_Z)).trigger(
        TriggerShape.BOX, size=(1.0, 3.0, 5.4), one_use_per_player=True,
        on_enter=[act_set_placement(Targets.SOURCE),
                  act_spawn_effect(Effect.CONFETTI, Targets.SOURCE),
                  act_play_sound(finish_wav.guid, 1.0, Targets.RECEIVER),
                  act_match_transform(podium_point.transform_guid, values=1 | 2 | 4 | 16, flags=Targets.SOURCE)]))
    # ложа: стены 2.2 м (прыжок 0.98) — финишировавшие смотрят гонку и больше не мешают
    for nm, a0, a1, b0, b1 in (("Podium_Front", PODIUM_X, PODIUM_X + 0.3, TRACK_Z - 3.0, TRACK_Z + 3.0),
                               ("Podium_Back", fx1 - 0.3, fx1, TRACK_Z - 3.0, TRACK_Z + 3.0),
                               ("Podium_L", PODIUM_X, fx1, TRACK_Z - 3.0, TRACK_Z - 2.7),
                               ("Podium_R", PODIUM_X, fx1, TRACK_Z + 2.7, TRACK_Z + 3.0)):
        track.add(slab(nm, a0, a1, b0, b1, ftop + 2.2, thick=2.2, layer=LAYER_WORLD_WALL)
                  .prop(PROP_CUBE, collision=Collision.BOX, materials=[paint_mat.guid]))
    nav_points.append(("Nav_Goal", (FINISH_X + 1.2, ftop + 0.5, TRACK_Z)))

    # --- падения: ров S2 и пруд под S3–S5, по триггеру на секцию. Лестница во рву осталась: на неё может упасть
    # сбитый с правой балки (верх ступеней выше зоны) — тогда выход прежний, пешком на станцию
    x0, x1, z0, _ = DITCH
    cp_station = checkpoint("CP_Station", (0, TRACK_Y + 1.5, 6.0), 0)
    cp_s2 = checkpoint("CP_S2", (LANES[0], TRACK_Y + 1.5, 20.0), 0)
    fall_zone("Fall_S2a", x0, x1, z0, DITCH_SPLIT, cp_station)
    fall_zone("Fall_S2b", x0, x1, DITCH_SPLIT, DITCH[3], cp_s2)
    fall_zone("Fall_S3", -12.0, 12.0, 39.5, 61.0, cp3)
    # граница подъём/петля там же, где начинается ловушка петли: упавший с верха подъёма долетал до z > 73.5 → CP4
    fall_zone("Fall_Lift", -12.0, 12.0, 61.0, LOOP_CATCH[2], cp_lift)
    fall_zone("Fall_S4", -12.0, 14.0, LOOP_CATCH[2], 104.0, cp4)
    lx0, lx1, lz0, lz1, ltop = LOOP_CATCH
    fall_zone("Catch_Loop", lx0, lx1, lz0, lz1, cp4, top=ltop, height=1.0)
    fall_zone("Fall_S5", 14.0, 60.0, 80.0, 104.0, cp5)
    # вода центрирована на позиции (LowPolyWater): x −24…60, z 40…106 — до рва (z ≤ 39) не доходит
    decor.add(obj("Pond", pos=(18.0, 0.0, 73.0)).water(
        width=42, height=33, cell=2.0, deep=(0.12, 0.45, 0.08, 0.8), shallow=(0.45, 1.0, 0.2, 0.8), froth=(0.8, 1.0, 0.6, 1)))
    logic.add(obj("KillVolume", pos=(0, -10.0, 50.0)).trigger(TriggerShape.BOX, size=(400, 4, 400),
                                                              on_enter=[act_kill(Targets.SOURCE)]))

    # --- декор: опоры горок под трассой (без коллизии), скелет петли, мелочь во рву, колесо, задник
    def trestle(name, x, z, top, yaw=0.0, width=1.0):
        decor.add(obj(name, pos=(x, -0.2, z), rot=(0, yaw, 0), scale=(width, (top + 0.2) / 10.25, 1))
                  .prop(trestle_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    for z in (12.0, 22.0, 32.0):
        trestle(f"Trestle_S2_{z:.0f}", 0, z, TRACK_Y - 0.6, width=2.6)
    for z in (44.0, 52.0, 59.0):
        trestle(f"Trestle_S3_{z:.0f}", BED_X, z, TRACK_Y - 0.5, width=1.8)
    trestle("Trestle_Lift", 0, 66.0, 6.3)
    trestle("Trestle_CP4", 0, 75.0, ly - 0.5, width=1.5)
    trestle("Trestle_CP5", 16.5, TRACK_Z, ptop - 0.5, yaw=90, width=1.5)
    trestle("Trestle_Drop", 25.0, TRACK_Z, ptop - (25.0 - px1) * slope - 0.6, yaw=90, width=1.4)
    trestle("Trestle_Pad", 33.0, TRACK_Z, dy - 0.5, yaw=90, width=1.4)
    for x in (38.5, 44.0):
        trestle(f"Trestle_Deck_{x:.0f}", x, TRACK_Z, ftop - 0.5, yaw=90, width=2.0)

    # скелет петли у поворота: вертикальное кольцо из rail_segment в плоскости XY — лицом к бегущим по +Z на S1–S4
    # (в плоскости YZ его видно ребром). Рельсы внутрь, верх обрушен, один кусок висит.
    # Точка φ: (cx + r cos φ, cy + r sin φ); Euler (−(φ + 90°), 90°, 0) кладёт локальную Z по касательной
    ring_c, ring_r = (-10.0, ly + 6.5, 86.0), 6.5   # правый край x −3.5 — левее плит петли (x ≥ 0.35)
    seg_scale = 2 * math.pi * ring_r / 12 / 6.0 * 1.02
    for k in range(12):
        if k in (2, 3, 4):
            continue
        phi = math.radians(30.0 * k)
        x, y = ring_c[0] + ring_r * math.cos(phi), ring_c[1] + ring_r * math.sin(phi)
        decor.add(obj(f"LoopRing_{k}", pos=(x, y, ring_c[2]), rot=(-(30.0 * k + 90.0), 90, 0), scale=(1, 1, seg_scale))
                  .prop(rail_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    decor.add(obj("LoopRing_Hanging", pos=(ring_c[0] - 2.4, ring_c[1] + ring_r - 2.0, ring_c[2] + 0.3), rot=(-15, 90, 25),
                  scale=(1, 1, seg_scale)).prop(rail_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    trestle("Trestle_Ring", ring_c[0], ring_c[2], ring_c[1] - ring_r - 0.3, width=1.2)

    # во рву: маскоты и бочки у стен и у подножия лестницы — «здесь работали», перевёрнутая вагонетка
    for k, (x, z, yaw, lying) in enumerate(((-7.0, 14.0, 70, False), (-7.1, 30.5, 110, True), (4.6, 24.0, -150, False),
                                            (-6.6, 37.5, 160, False))):
        rot = (0, yaw, 88) if lying else (0, yaw, rng.uniform(-6, 6))
        decor.add(obj(f"Mascot_{k}", pos=(x, 0.45 if lying else 0.0, z), rot=rot)
                  .prop(mascot_obj.guid, collision=Collision.NONE, tint=(0.95, 0.8, 0.3, 1) if k % 2 else (0.75, 0.3, 0.6, 1)))
    for k, (x, z) in enumerate(((-7.2, 16.0), (-6.6, 16.6), (7.3, 24.6), (-7.2, 27.5), (6.9, 36.0), (6.2, 37.3))):
        decor.add(obj(f"Barrel_{k}", pos=(x, 0.0, z), rot=(0, rng.uniform(0, 360), rng.uniform(-8, 8)))
                  .prop(barrel_obj.guid, collision=Collision.BOX, materials=[metal_mat.guid]))
    decor.add(obj("WreckedCart", pos=(-6.2, 1.2, 33.5), rot=(0, 25, 165))
              .prop(cart_obj.guid, collision=Collision.NONE, materials=[paint_mat.guid]))
    for k, (x, z) in enumerate(((-7.6, -3.6), (7.6, -3.6), (-7.6, 7.6), (7.6, 4.8))):
        decor.add(obj(f"Lamppost_{k}", pos=(x, TRACK_Y, z), rot=(0, 45 + 90 * k, rng.uniform(-5, 5)))
                  .prop(lamp_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    # ориентир: колесо впереди справа — видно со старта (по +Z) и со спуска (по +X)
    wheel = decor.add(obj("FerrisWheel", pos=(46.0, 10.5, 128.0), scale=(1.5, 1.5, 1.5))
                      .prop(stand_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    wheel.add(obj("Rotor").prop(rotor_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid])
              .mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Z, (0, 0, 1), 8.0))
    decor.add(obj("OuterGround", pos=(15.0, -0.6, 55.0), scale=(26, 1, 26))
              .prop(PROP_PLANE, collision=Collision.NONE, materials=[dirt_mat.guid]))
    for i in range(14):
        a = 2 * math.pi * i / 14 + rng.uniform(-0.1, 0.1)
        r, s = rng.uniform(95, 110), rng.uniform(0.9, 1.7)
        decor.add(obj(f"Hill_{i}", pos=(15 + r * math.cos(a), -0.8, 55 + r * math.sin(a)), rot=(0, rng.uniform(0, 360), 0),
                      scale=(s, s * rng.uniform(0.8, 1.4), s)).prop(hill_obj.guid, collision=Collision.NONE, materials=[dirt_mat.guid]))
    for i in range(18):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(62, 85)
        decor.add(obj(f"DeadTree_{i}", pos=(15 + r * math.cos(a), -0.6, 55 + r * math.sin(a)),
                      rot=(0, rng.uniform(0, 360), rng.uniform(-6, 6)), scale=(rng.uniform(0.8, 1.4),) * 3)
                  .prop(tree_obj.guid, collision=Collision.NONE, tint=(0.35, 0.28, 0.2, 1)))
    for k, (x, z, top) in enumerate(((-18.0, 30.0, 7.0), (-22.0, 62.0, 12.0), (24.0, 20.0, 9.0), (34.0, 64.0, 14.0),
                                     (58.0, 100.0, 8.0))):   # руины других горок по краям — без рельсов
        trestle(f"Ruin_{k}", x, z, top, yaw=rng.uniform(0, 180))

    mod.add(obj("Director").logic(trig_round_start(act_show_message("Рельсов нет. Беги! / No rails. Run!", 3.0))))
    mod.add(obj("Notes").note("Сгенерировано build_mod.py из packs/abandoned-park/minigames/coaster-run/DESIGN.md"))

    # --- сетка ботов. Узел финиша — Is AI Goal: все боты идут к нему по кратчайшему пути. Связи направленные,
    # только вперёд; из рва — к лестнице и через станцию снова на балки
    nav = mod.add(obj("AI Navigation"))
    main = [nav.add(obj(n, pos=p).ai_node(is_goal=(n == "Nav_Goal"))) for n, p in nav_points]
    side = [nav.add(obj(n, pos=p).ai_node()) for n, p in ditch_nav + stair_nav]
    nodes = main + side
    edges = [(i, i + 1) for i in range(len(main) - 1)]
    hub = len(main) + len(ditch_nav)
    edges += [(len(main) + k, hub) for k in range(len(ditch_nav))]
    edges += [(hub, hub + 1), (hub + 1, hub + 2), (hub + 2, hub + 3), (hub + 3, 0)]
    link_ai_nodes(nodes, edges)
    out = mod.write(workshop)

    # --- превью для окна Load a saved mod: план сверху
    os.makedirs(os.path.join(HERE, "plan"), exist_ok=True)
    mod.preview_image = os.path.join(HERE, "plan", "preview.png")
    plan_view.render_preview(out, mod.preview_image)
    print(f"сетка ботов: {len(nodes)} узлов, {len(edges)} связей")
    return mod.write(workshop)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = build(sys.argv[1] if len(sys.argv) > 1 else "Coaster Run", sys.argv[2] if len(sys.argv) > 2 else WORKSHOP)
    print("written:", out)
