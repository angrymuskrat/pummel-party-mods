"""Собирает мод Tilt House по DESIGN.md в папку WorkshopMods редактора.

Запуск из корня репозитория:  python packs/abandoned-park/minigames/tilt-house/build_mod.py [имя мода] [папка WorkshopMods]
По умолчанию пишет «Tilt House» в WorkshopMods редактора. Сцену, настройки и ассеты пересобирает целиком; превью
(Data/Preview.jpg после сохранения в редакторе), Preview Image мини-игры и данные Workshop сохраняет (pmgen.Mod.write).
Печатает расписание кренов (самое раннее и самое позднее время каждого). Скольжение по кадрам считает slide.py.
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

# --- игрок. Боковая гравитация на земле (CharacterMover.CalculateVelocity, декомпиляция 2026-10-25): каждый кадр к
# скорости прибавляется g · playerGravity / 9.81 · dt, потом горизонталь по каждой оси шагает к «ввод × бег» с темпом
# Acceleration (ввод по оси есть) или Deceleration (ввода по оси нет), а если шаг перекрывает разницу — встаёт ровно на
# цель. Поэтому боковая тяга P ниже темпа не видна совсем, а выше — разгоняет на P − темп без предела. Отсюда
# DECEL < P_LIGHT < ACCEL < P_HEAVY: в лёгком крене стоящего и бегущего поперёк сносит, бегущий в гору держится;
# в тяжёлом сносит всех, бегущего в гору — медленнее всех. В воздухе темп — MID_AIR (он же airDeceleration)
RUN, ACCEL, DECEL, MID_AIR = 6.0, 30.0, 12.0, 8.0   # в шаблоне 6 / 50 / 50 / 8; торможение 12 — «натёртый паркет»
PLAYER_GRAVITY, JUMP = 25.0, 7.0                   # как в шаблоне: прыжок 7² / 50 = 0.98 м
P_LIGHT, P_HEAVY = 20.0, 36.0                      # боковая тяга, м/с², в единицах игрока
G = 9.81                                           # Physics.gravity при старте: m_gravityProportion = playerGravity / 9.81
assert DECEL < P_LIGHT < ACCEL < P_HEAVY

# --- дом. Корень House стоит в центре пола на высоте FLOOR_Y; всё дочернее кренится вместе с ним
FLOOR_Y = 2.5          # верх пола над землёй; под полом подвал с кислотой
TILE = 2.0             # пол из плит 2 × 2 м, 8 × 8
N_TILES = 8
HALF = TILE * N_TILES / 2   # 8 м: внутренний размер комнаты 16 × 16
WALL_T, WALL_H = 1.0, 2.6   # стена выше прыжка с ударом (0.98 + 0.4 м); толщина 1 м — запас против скорости, накопленной у стены
KILL_TOP = 0.6         # верх зоны смерти в подвале; нижний край накренённого пола (9°) — 2.5 − 8·sin 9° = 1.25 м
# плиты (x, z центра). Яма в центре — с начала раунда; у стен 4 дыры с начала, 16 плит осыпаются по своим таймерам,
# 8 не осыпаются никогда: углы, под шкафом и часами и две с ковриками — их видно, на них и надо выезжать
PIT = {(-1, -1), (-1, 1), (1, -1), (1, 1)}
HOLES = {(7, 1), (-3, 7), (-7, 5), (3, -7)}
SOLID = {(-7, -7), (-7, 7), (7, -7), (7, 7), (3, 7), (-7, -3), (7, -5), (-5, -7)}
RUGS = {(-7, -7), (-7, 7), (7, -7), (7, 7), (7, -5), (-5, -7)}   # постоянные плиты без мебели
CRUMBLE = (21.0, 52.0)  # когда осыпается каждая из 16 плит у стен, с от начала раунда
CRUMBLE_WARN = 1.5

# --- крен. Направление — к какой стене съезжают. Визуальный наклон дома: RotateAroundWorldAxis вокруг его центра.
# Знак: поворот вокруг +Z на +θ поднимает сторону +X, вокруг +X на +θ опускает сторону +Z (Unity, Quaternion.AngleAxis);
# что LeanTween.rotateAround не меняет знак, в игре не проверено — если низ окажется у противоположной стены, TILT_SIGN = −1
TILT_SIGN = 1
DIRS = {"E": ((1, 0), (0, 0, 1), -1), "W": ((-1, 0), (0, 0, 1), 1),
        "N": ((0, 1), (1, 0, 0), 1), "S": ((0, -1), (1, 0, 0), -1)}   # (куда тянет по x, z), ось поворота, знак угла
TILT_DEG = {False: 6.0, True: 9.0}       # лёгкий / тяжёлый: край пола опускается на 0.84 / 1.25 м
TILT_TIME = 0.8        # твин наклона и возврата
WARN = 1.2             # стена краснеет и скрипит, через WARN — крен
HOLD = {False: 3.0, True: 2.2}   # сколько держится тяга. Тяжёлый короче: кто разбежался в гору за WARN, к концу
#                                  крена вернулся на своё место (slide.py), остальных уносит к нижней стене
GAP = {False: (1.5, 3.0), True: (1.2, 2.2)}   # пауза после возврата (случайная в каждом матче)
LEVEL_RESET = 0.3      # сколько живёт Leveler: гасит горизонтальную скорость, накопленную у стены, когда дом выровнялся
START_WAIT = 3.0
# порядок: сначала четыре лёгких в разные стороны (первые два — навстречу друг другу), потом тяжёлые вперемешку
SCHEDULE = [("E", False), ("W", False), ("N", False), ("S", False), ("E", True), ("N", False),
            ("W", True), ("S", True), ("N", True), ("E", True), ("S", True), ("W", True)]
T_CRACK = 20.0         # сообщение «Пол трещит!» перед окном осыпания
ROUND = 60.0
PUNCH_PUSH, PUNCH_LIFT = 6.0, 4.5   # м/с от удара; при торможении 12 после приземления доезжаешь ещё ~0.5 м: всего ~2 м
SPAWN_R = 4.2          # кольцо спавна посередине между ямой (|x|, |z| < 2) и полосой у стен (6…8)
BOT_ORBIT_R, BOT_ORBIT_SPEED = 3.6, 20.0   # цель ботов ходит по кругу вокруг ямы: 1.3 м/с
RED, WHITE = (1.0, 0.25, 0.15, 1.0), (1.0, 1.0, 1.0, 1.0)


def lateral_gravity(d, heavy):
    """Вектор Set Gravity: вертикаль та же −9.81 (гравитация игрока 25), горизонталь = P · 9.81 / playerGravity."""
    (dx, dz), _, _ = DIRS[d]
    gh = (P_HEAVY if heavy else P_LIGHT) * G / PLAYER_GRAVITY
    return (round(dx * gh, 3), -G, round(dz * gh, 3))


def schedule_times():
    """Самое раннее и самое позднее начало каждого крена (момент, когда стена краснеет), с от начала раунда."""
    lo = hi = START_WAIT
    out = []
    for d, heavy in SCHEDULE:
        out.append((d, heavy, lo, hi))
        g0, g1 = GAP[heavy]
        lo, hi = lo + WARN + HOLD[heavy] + g0, hi + WARN + HOLD[heavy] + g1
    return out, lo


def build(name: str, workshop: str = WORKSHOP) -> str:
    rng = random.Random("tilt-house")
    mod = Mod(name, description="Rusted Park: the crooked funhouse tilts toward the red wall. Run uphill, dodge the holes "
                                "and punch the others into the acid. Last one standing wins. / Кривой дом: дом кренится к "
                                "красной стене — беги в гору, не съезжай в дыры и сталкивай остальных. Побеждает последний.",
              round_duration=ROUND, end_conditions=EndCondition.TIMER | EndCondition.REMAINING_ALIVE,
              placement=Placement.LAST_MAN_STANDING, min_players_alive=1,
              # удар толкает, а не убивает (схема Death Carousel): урон 0, отброс в weaponHitTrigger (m_hitType 1 = Melee)
              settings_overrides={"respawnEnabled": False, "useHealth": False, "showHealthBar": False,
                                  "canPunch": True, "punchDamage": 0, "punchStunsTarget": False,
                                  "movementSpeed": RUN, "movementAcceleration": ACCEL, "movementDecelaration": DECEL,
                                  "midAirMovementAcceleration": MID_AIR, "playerGravity": PLAYER_GRAVITY, "jumpSpeed": JUMP,
                                  "weaponHitTrigger": {"m_type": 80, "m_actions": [], "m_hitType": 1}},
              player_triggers={"onDeathTrigger": [act_show_message("Съехал! / Slid out!", 1.5)],
                               "weaponHitTrigger": [
                                   act_change_velocity(PUNCH_PUSH, VelocityDir.TOWARDS_RECEIVER, Op.ADD, flags=Targets.RECEIVER),
                                   act_change_velocity(PUNCH_LIFT, VelocityDir.UP, Op.ADD, flags=Targets.RECEIVER)]})

    # --- ассеты
    def prop(fn): return mod.add_file_asset("prop", os.path.join(ASSETS, "models", fn))
    def tex(fn): return mod.add_file_asset("texture", os.path.join(ASSETS, "textures", fn))
    def wav(fn): return mod.add_file_asset("audio", os.path.join(ASSETS, "audio", fn))
    rotor_obj, stand_obj = prop("ferris_wheel_rotor.obj"), prop("ferris_wheel_stand.obj")
    lamp_obj, barrel_obj, booth_obj = prop("lamppost.obj"), prop("barrel.obj"), prop("booth.obj")
    tree_obj, hill_obj, fence_obj = prop("dead_tree.obj"), prop("hill.obj"), prop("fence_segment.obj")
    headless_obj = prop("mascot_headless.obj")
    creak_wav = wav("creak.wav")
    mod.music_guid = wav("carousel_music.wav").guid
    floor_mat = mod.add_material("Floorboards", tex("floorboards.png"), tiling=(0.5, 0.5))
    paper_mat = mod.add_material("Wallpaper", tex("wallpaper.png"), tiling=(4.0, 1.0))
    stripes_mat = mod.add_material("RustBooth", tex("rust_booth.png"), tiling=(1.0, 1.0))
    metal_mat = mod.add_material("RustMetal", tex("rust_metal.png"), tiling=(1.0, 1.0))
    concrete_mat = mod.add_material("Concrete", tex("concrete.png"), tiling=(4.0, 1.0))
    dirt_mat = mod.add_material("Dirt", tex("dirt.png"), tiling=(20.0, 20.0))

    def cube(name, pos, scale, rot=(0, 0, 0), collision=Collision.BOX, layer=LAYER_WORLD_WALL, tint=WHITE, mat=None):
        return obj(name, pos=pos, rot=rot, scale=scale, layer=layer if collision != Collision.NONE else LAYER_DEFAULT).prop(
            PROP_CUBE, tint=tint, collision=collision, materials=[mat.guid] if mat else None)

    # --- подвал: фундамент, кислота и зона смерти под всем домом. Не кренится
    world = mod.add(obj("World"))
    found_h = FLOOR_Y - 0.4
    for k, (x, z, sx, sz) in enumerate(((HALF + WALL_T / 2, 0, WALL_T, 2 * HALF + 2 * WALL_T),
                                        (-HALF - WALL_T / 2, 0, WALL_T, 2 * HALF + 2 * WALL_T),
                                        (0, HALF + WALL_T / 2, 2 * HALF, WALL_T), (0, -HALF - WALL_T / 2, 2 * HALF, WALL_T))):
        world.add(cube(f"Foundation_{k}", (x, found_h / 2, z), (sx, found_h, sz), mat=concrete_mat))
    world.add(obj("Acid", pos=(0, 0.3, 0)).water(
        width=8, height=8, cell=2.0, deep=(0.12, 0.45, 0.08, 0.8), shallow=(0.45, 1.0, 0.2, 0.8), froth=(0.8, 1.0, 0.6, 1)))
    world.add(obj("KillVolume", pos=(0, KILL_TOP - 0.5, 0)).trigger(
        TriggerShape.BOX, size=(2 * HALF, 1.0, 2 * HALF),
        on_enter=[act_spawn_effect(Effect.EXPLOSION, Targets.SOURCE), act_kill(Targets.SOURCE)]))

    # --- дом
    house = world.add(obj("House", pos=(0, FLOOR_Y, 0)))
    for i in range(N_TILES):
        for j in range(N_TILES):
            x, z = int(-HALF + TILE / 2 + TILE * i), int(-HALF + TILE / 2 + TILE * j)
            if (x, z) in PIT or (x, z) in HOLES:
                continue
            tile = house.add(cube(f"Tile_{x}_{z}", (x, -0.2, z), (TILE, 0.4, TILE), layer=LAYER_WORLD_GROUND,
                                  tint=(rng.uniform(0.85, 1.0),) * 3 + (1,), mat=floor_mat))
            edge = abs(x) == HALF - 1 or abs(z) == HALF - 1
            if edge and (x, z) not in SOLID:
                # как сектор края Death Carousel: краснеет, скрипит, через 1.5 с уходит вниз вместе со стоящими
                tile.add(obj("Crumble", pos=(0, 0.5, 0)).logic(trig_round_start(
                    act_wait(*CRUMBLE),
                    act_set_color(RED, targets=[tile.transform_guid]),
                    act_play_sound(creak_wav.guid, 0.6, Targets.RECEIVER),
                    act_wait(CRUMBLE_WARN),
                    act_play_tween([tile.transform_guid], Tween.LOCAL_POSITION, end=(0, -6, 0), seconds=1.0, ease=Ease.EASE_IN_QUAD),
                    act_set_active(ActiveState.DISABLED, [tile.transform_guid]))))
    for x, z in sorted(RUGS):   # коврик — «здесь пол держит»; плоский, без коллизии
        house.add(cube(f"Rug_{x}_{z}", (x, 0.015, z), (1.6, 0.03, 1.6), rot=(0, rng.uniform(-8, 8), 0),
                       collision=Collision.NONE, tint=(0.75, 0.85, 1.0, 1), mat=stripes_mat))
    # сломанные доски по краю ямы и начальных дыр: торчат вниз, без коллизии
    for k, (x, z) in enumerate(sorted(PIT | HOLES)):
        for s in range(2):
            a = rng.uniform(0, 2 * math.pi)
            house.add(cube(f"Splinter_{k}_{s}", (x + 0.8 * math.cos(a), -0.35, z + 0.8 * math.sin(a)), (0.25, 0.06, 1.1),
                           rot=(rng.uniform(25, 45), math.degrees(a), 0), collision=Collision.NONE, mat=floor_mat))

    # стены: у каждой своя, чтобы краснела только та, к которой съезжают. Северная и южная — во всю длину с углами
    walls = {}
    for d, (x, z, sx, sz) in {"E": (HALF + WALL_T / 2, 0, WALL_T, 2 * HALF), "W": (-HALF - WALL_T / 2, 0, WALL_T, 2 * HALF),
                              "N": (0, HALF + WALL_T / 2, 2 * HALF + 2 * WALL_T, WALL_T),
                              "S": (0, -HALF - WALL_T / 2, 2 * HALF + 2 * WALL_T, WALL_T)}.items():
        walls[d] = house.add(cube(f"Wall_{d}", (x, (WALL_H - 0.4) / 2, z), (sx, WALL_H + 0.4, sz), mat=paper_mat))
    # кривые картины на стенах — по две, внутрь комнаты, без коллизии
    for d, (nx, nz) in {"E": (-1, 0), "W": (1, 0), "N": (0, -1), "S": (0, 1)}.items():
        for s in (-1, 1):
            along = s * rng.uniform(2.5, 5.5)
            px, pz = (HALF - 0.04) * -nx + (along if nx == 0 else 0), (HALF - 0.04) * -nz + (along if nz == 0 else 0)
            yaw = math.degrees(math.atan2(nx, nz))   # локальная +Z смотрит в комнату
            w, h = rng.uniform(0.7, 1.2), rng.uniform(0.6, 0.9)
            picture = house.add(obj(f"Picture_{d}_{s}", pos=(px, rng.uniform(1.4, 1.9), pz), rot=(0, yaw, rng.uniform(-14, 14))))
            picture.add(cube("Frame", (0, 0, 0), (w, h, 0.06), collision=Collision.NONE, tint=(0.45, 0.3, 0.15, 1)))
            picture.add(cube("Canvas", (0, 0, 0.03), (w - 0.16, h - 0.16, 0.03), collision=Collision.NONE,
                             tint=(rng.uniform(0.3, 0.9), rng.uniform(0.3, 0.7), rng.uniform(0.2, 0.5), 1)))
    # труба — ориентир, кренится вместе с домом и показывает наклон издалека
    house.add(cube("Chimney", (-HALF - 0.5, 4.0, HALF + 0.5), (1.4, 8.4, 1.4), rot=(0, 0, 4), mat=concrete_mat))

    # --- мебель. Выше прыжка — укрытие от крена с одной стороны; ниже — перепрыгивается, но тоже останавливает съезд.
    # Между лучами спавна (0°, 45°, …) и не на круге цели ботов
    def polar(r, deg): return r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg))
    sx, sz = polar(5.0, 112.5)
    sofa = house.add(obj("Sofa", pos=(sx, 0, sz)))   # сиденье 0.5 м — на него запрыгивают; спинка 1.2 м — со стороны стены
    sofa.add(cube("Seat", (0, 0.25, 0), (2.0, 0.5, 0.9), tint=(0.55, 0.2, 0.25, 1), mat=stripes_mat))
    sofa.add(cube("Back", (0, 0.85, 0.33), (2.0, 0.7, 0.25), tint=(0.55, 0.2, 0.25, 1), mat=stripes_mat))
    for s in (-1, 1):
        sofa.add(cube(f"Arm_{s}", (s * 0.95, 0.62, 0), (0.15, 0.25, 0.9), collision=Collision.NONE, tint=(0.4, 0.15, 0.2, 1)))
    px, pz = polar(5.2, -22.5)
    piano = house.add(obj("Piano", pos=(px, 0, pz), rot=(0, 20, 0)))   # 1.1 м — выше прыжка
    piano.add(cube("Body", (0, 0.55, 0), (1.4, 1.1, 1.2), tint=(0.12, 0.1, 0.1, 1)))
    piano.add(cube("Lid", (0, 1.3, 0.2), (1.3, 0.04, 0.9), rot=(-25, 0, 0), collision=Collision.NONE, tint=(0.15, 0.12, 0.12, 1)))
    piano.add(cube("Keys", (0, 0.75, -0.66), (1.2, 0.06, 0.15), collision=Collision.NONE, tint=(0.95, 0.92, 0.85, 1)))
    cx, cz = polar(5.0, 202.5)
    house.add(cube("FallenChair", (cx, 0.25, cz), (0.9, 0.5, 0.5), rot=(0, 35, 0), tint=(0.5, 0.35, 0.2, 1), mat=floor_mat))
    tx, tz = polar(4.9, 292.5)
    house.add(cube("Trunk", (tx, 0.3, tz), (1.0, 0.6, 0.6), rot=(0, -15, 0), tint=(0.6, 0.45, 0.3, 1), mat=metal_mat))
    house.add(cube("Wardrobe", (-HALF + 0.45, 1.1, -3), (0.9, 2.2, 1.8), tint=(0.45, 0.3, 0.2, 1), mat=floor_mat))
    # часы у северной стены: маятник качается (фоновое движение внутри дома)
    clock = house.add(obj("Clock", pos=(3, 0, HALF - 0.3), rot=(0, 0, -3)))
    clock.add(cube("Case", (0, 1.1, 0), (0.8, 2.2, 0.5), tint=(0.4, 0.25, 0.12, 1)))
    clock.add(cube("Face", (0, 1.8, -0.26), (0.55, 0.55, 0.03), collision=Collision.NONE, tint=(0.95, 0.9, 0.75, 1)))
    pendulum = house.add(obj("Pendulum", pos=(3, 1.55, HALF - 0.58)).simple_animator(anim_swing(0.5, 14, axis=(0, 0, 1))))
    pendulum.add(cube("Rod", (0, -0.4, 0), (0.04, 0.8, 0.02), collision=Collision.NONE, tint=(0.8, 0.65, 0.2, 1)))
    pendulum.add(obj("Bob", pos=(0, -0.85, 0), scale=(0.22, 0.22, 0.06)).prop(PROP_SPHERE, collision=Collision.NONE,
                                                                                 tint=(0.85, 0.7, 0.25, 1)))
    # люстра, упавшая в яму: лежит в кислоте, видна сквозь яму
    chandelier = world.add(obj("FallenChandelier", pos=(0.3, 0.45, -0.2), rot=(20, 30, 10)))
    chandelier.add(obj("Ball", scale=(0.9, 0.6, 0.9)).prop(PROP_SPHERE, collision=Collision.NONE, tint=(0.7, 0.55, 0.2, 1)))
    for k in range(5):
        a = 2 * math.pi * k / 5
        chandelier.add(cube(f"Arm_{k}", (0.6 * math.cos(a), 0.1, 0.6 * math.sin(a)), (0.7, 0.05, 0.05),
                            rot=(0, -math.degrees(a), 15), collision=Collision.NONE, tint=(0.7, 0.55, 0.2, 1)))

    # --- Leveler: когда дом выравнивается, гасит горизонтальную скорость всем в доме (вертикаль × 1). У стены тяга
    # копится в скорости — контроллер её не обнуляет при упоре, — и без сброса после крена игрока ещё секунду-две
    # прижимало бы к стене. On Stay сработает в первом же кадре: интервал меньше времени жизни
    leveler = world.add(obj("Leveler", pos=(0, FLOOR_Y + 1.5, 0), active=False).trigger(
        TriggerShape.BOX, size=(2 * HALF, 4.0, 2 * HALF), stay_interval=0.1,
        on_stay=[act_change_velocity(1.0, VelocityDir.CUSTOM, Op.MUL, custom=(0, 1, 0))]))

    # --- цель ботов: узел Is AI Goal на кольце вокруг ямы, кружит (Mover). Без цели бот бежит в случайную точку, в том
    # числе через яму; за целью он ходит по кольцу, а в крен давит туда же — то есть иногда в гору
    bot_goal = world.add(obj("BotGoal", pos=(0, FLOOR_Y + 0.5, 0)).mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Y,
                                                                          (0, 1, 0), BOT_ORBIT_SPEED))
    bot_goal.add(obj("Node", pos=(BOT_ORBIT_R, 0, 0)).ai_node(is_goal=True))

    # --- задний план: двор парка вокруг дома
    backdrop = mod.add(obj("Backdrop"))
    backdrop.add(obj("Ground", pos=(0, 0, 0), scale=(14, 1, 14)).prop(PROP_PLANE, collision=Collision.NONE, materials=[dirt_mat.guid]))
    backdrop.add(obj("FallVolume", pos=(0, -8, 0)).trigger(TriggerShape.BOX, size=(400, 4, 400), on_enter=[act_kill(Targets.SOURCE)]))
    wheel = backdrop.add(obj("FerrisWheel", pos=(6, 7.1, 34)).prop(stand_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    wheel.add(obj("Rotor").prop(rotor_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid])
              .mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Z, (0, 0, 1), 10.0))
    # вывеска на мачте перед южной стеной качается на ветру
    backdrop.add(cube("SignMast", (-3, 3.5, -HALF - 3.5), (0.3, 7.0, 0.3), rot=(4, 0, 0), collision=Collision.NONE, mat=metal_mat))
    sign = backdrop.add(obj("Sign", pos=(-3, 6.6, -HALF - 3.7)).simple_animator(anim_swing(0.35, 6, axis=(1, 0, 0))))
    sign.add(cube("Board", (0, -0.9, 0), (3.2, 1.4, 0.12), rot=(0, 0, 7), collision=Collision.NONE, mat=stripes_mat))
    for i in range(10):   # забор двора с прорехами
        a = 2 * math.pi * i / 10 + rng.uniform(-0.05, 0.05)
        backdrop.add(obj(f"Fence_{i}", pos=(18 * math.cos(a), 0, 18 * math.sin(a)), rot=(0, 90 - math.degrees(a), rng.uniform(-6, 6)))
                     .prop(fence_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    for i, (x, z, rot) in enumerate(((13, -4, 30), (-12, 9, 200), (11, 12, 120))):
        backdrop.add(obj(f"Booth_{i}", pos=(x, 0, z), rot=(0, rot, rng.uniform(-5, 5)))
                     .prop(booth_obj.guid, collision=Collision.NONE, materials=[stripes_mat.guid]))
    for i, (x, z) in enumerate(((12, -10), (-13, -8), (-11, 13), (14, 6))):
        backdrop.add(obj(f"Lamppost_{i}", pos=(x, 0, z), rot=(rng.uniform(-6, 6), rng.uniform(0, 360), 0))
                     .prop(lamp_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    for i in range(6):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(10.5, 15)
        backdrop.add(obj(f"Barrel_{i}", pos=(r * math.cos(a), 0, r * math.sin(a)), rot=(rng.choice((0, 90)), rng.uniform(0, 360), 0))
                     .prop(barrel_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    backdrop.add(obj("Mascot", pos=(-9.5, 0, -11), rot=(0, 40, 12)).prop(headless_obj.guid, collision=Collision.NONE,
                                                                        tint=(0.9, 0.6, 0.2, 1)))
    for i in range(12):
        a = 2 * math.pi * i / 12 + rng.uniform(-0.1, 0.1)
        r, s = rng.uniform(55, 70), rng.uniform(0.8, 1.6)
        backdrop.add(obj(f"Hill_{i}", pos=(r * math.cos(a), -0.6, r * math.sin(a)), rot=(0, rng.uniform(0, 360), 0),
                         scale=(s, s * rng.uniform(0.8, 1.4), s)).prop(hill_obj.guid, collision=Collision.NONE, materials=[dirt_mat.guid]))
    for i in range(14):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(24, 45)
        backdrop.add(obj(f"DeadTree_{i}", pos=(r * math.cos(a), 0, r * math.sin(a)), rot=(0, rng.uniform(0, 360), rng.uniform(-6, 6)),
                         scale=(rng.uniform(0.8, 1.4),) * 3).prop(tree_obj.guid, collision=Collision.NONE, tint=(0.35, 0.28, 0.2, 1)))

    # --- спавн: общий круг между ямой и стенами, лицом к центру
    mod.add(obj("Player Spawnpoints")).add(
        obj("Spawn_Ring", pos=(0, FLOOR_Y + 1, 0)).player_spawn(SpawnShape.CIRCLE, SpawnUsage.INITIAL, radius=SPAWN_R, shared=True))

    # --- Director: крены по расписанию. Каждый: стена краснеет и скрипит → WARN → боковая гравитация и наклон дома →
    # HOLD → гравитация обычная, Leveler на LEVEL_RESET, дом обратно → пауза. Director стоит в центре: скрип — оттуда
    def tilt(d, heavy):
        _, axis, sign = DIRS[d]
        deg = TILT_SIGN * sign * TILT_DEG[heavy]
        wall = walls[d].transform_guid
        return [act_set_color(RED, targets=[wall]),
                act_play_sound(creak_wav.guid, 1.0, Targets.RECEIVER),
                act_wait(WARN),
                act_set_gravity(lateral_gravity(d, heavy)),
                act_play_tween([house.transform_guid], Tween.ROTATE_WORLD_AXIS, axis=axis, degrees=deg, seconds=TILT_TIME,
                               ease=Ease.EASE_IN_OUT_QUAD),
                act_wait(HOLD[heavy]),
                act_set_gravity((0, -G, 0)),
                act_set_active(ActiveState.ENABLED, [leveler.transform_guid]),
                act_play_tween([house.transform_guid], Tween.ROTATE_WORLD_AXIS, axis=axis, degrees=-deg, seconds=TILT_TIME,
                               ease=Ease.EASE_IN_OUT_QUAD),
                act_wait(LEVEL_RESET),
                act_set_active(ActiveState.DISABLED, [leveler.transform_guid]),
                act_set_color(WHITE, targets=[wall]),
                act_wait(*GAP[heavy])]

    chain = [act_show_message("Дом кренится к красной стене — беги в гору! / The house tilts toward the red wall — run uphill!", 3.0),
             act_wait(START_WAIT)]
    first_heavy = True
    for d, heavy in SCHEDULE:
        if heavy and first_heavy:
            chain.append(act_show_message("Дом рушится! / The house is collapsing!", 2.0))
            first_heavy = False
        chain += tilt(d, heavy)
    director = mod.add(obj("Director", pos=(0, FLOOR_Y + 1, 0)))
    director.logic(trig_round_start(*chain))
    mod.add(obj("Announcer").logic(trig_round_start(
        act_wait(T_CRACK), act_show_message("Пол у стен трещит! / The floor by the walls is cracking!", 2.0))))
    mod.add(obj("Notes").note("Сгенерировано build_mod.py из packs/abandoned-park/minigames/tilt-house/DESIGN.md"))
    out = mod.write(workshop)

    os.makedirs(os.path.join(HERE, "plan"), exist_ok=True)
    mod.preview_image = os.path.join(HERE, "plan", "preview.png")
    plan_view.render_preview(out, mod.preview_image)
    return mod.write(workshop)


def print_schedule():
    times, end = schedule_times()
    print("| # | К стене | Крен | Тяга, м/с² | Set Gravity | Начало, с |")
    print("| --- | --- | --- | --- | --- | --- |")
    for k, (d, heavy, lo, hi) in enumerate(times, 1):
        print(f"| {k} | {d} | {'тяжёлый' if heavy else 'лёгкий'} | {P_HEAVY if heavy else P_LIGHT:g} | "
              f"{lateral_gravity(d, heavy)} | {lo:.1f}–{hi:.1f} |")
    print(f"Цепочка кончается не раньше {end:.1f} с (раунд {ROUND:g} с)")
    assert end >= ROUND, "кренов не хватает до конца раунда"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print_schedule()
    out = build(sys.argv[1] if len(sys.argv) > 1 else "Tilt House", sys.argv[2] if len(sys.argv) > 2 else WORKSHOP)
    print("written:", out)
