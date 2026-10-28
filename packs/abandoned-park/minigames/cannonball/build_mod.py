"""Собирает мод Human Cannonball по DESIGN.md в папку WorkshopMods редактора.

Запуск из корня репозитория:  python packs/abandoned-park/minigames/cannonball/build_mod.py [имя мода] [папка WorkshopMods]
По умолчанию пишет «Human Cannonball» в WorkshopMods редактора. Сцену, настройки и ассеты пересобирает целиком; превью
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

# Движение игрока (ModSettings). В воздухе CharacterMover гасит горизонтальную скорость к «ввод × бег» с темпом
# midAirMovementAcceleration (он же airDeceleration, SimpleModPlayer.ApplyModSettings), поэтому дальность выстрела
# и подруливание задаются им. 4 м/с²: вбок долетают на ±2.5…3 м, вперёд-назад полёт почти не управляется
GRAVITY, AIR_ACCEL, RUN, JUMP = 15.0, 4.0, 6.0, 6.0   # прыжок 6²/(2·15) = 1.2 м
# один раунд: здесь не выбывают и не ждут, поэтому пауза между раундами только рвала бы темп (решение 2026-10-25).
# Эскалация — три этапа по STAGE_TIME внутри раунда, их переключает Director цепочкой Wait → Set Active
ROUND, ROUNDS, STAGE_TIME = 60.0, 1, 20.0

DECK_FRONT, DECK_BACK, DECK_HALF = 0.0, -12.0, 15.0   # пирс: верх y 0, передний край над кислотой
WATER_Y, RAFT_TOP = -1.0, -0.6
PIVOT_Z = -2.5        # ось поворотного круга пушки
MUZZLE = (0.0, 3.2, 2.7)   # куда ставит игрока Match Transform: чуть впереди дула, в локальных осях оси качания
PAD = 3.2             # зона входа 3.2 × 3.2: бот останавливается в 1.5 м от узла-цели и должен уже стоять внутри
# выстрел — вектор скорости в локальных осях зоны входа (Change Player Velocity: Set, Space Local, Receiver; Custom
# не нормализуется). Зона — ребёнок качающейся оси, поэтому направление — куда смотрит ствол в момент входа
SHOTS = {"short": (0.0, 10.5, 11.0), "long": (0.0, 14.0, 15.0)}
# пушки: x, тип, базовый поворот (+ — к центру пирса), размах качания ±, период, фаза (доля цикла), цвет шеста
CANNONS = [
    {"name": "Cannon_W", "x": -9.0, "kind": "short", "yaw": 12.0, "amp": 28.0, "period": 4.5, "phase": 0.0, "tint": (0.95, 0.25, 0.15, 1)},
    {"name": "Cannon_CW", "x": -3.0, "kind": "long", "yaw": 5.0, "amp": 25.0, "period": 5.5, "phase": 0.3, "tint": (1.0, 0.8, 0.1, 1)},
    {"name": "Cannon_CE", "x": 3.0, "kind": "long", "yaw": -5.0, "amp": 25.0, "period": 5.0, "phase": 0.6, "tint": (0.2, 0.75, 1.0, 1)},
    {"name": "Cannon_E", "x": 9.0, "kind": "short", "yaw": -12.0, "amp": 28.0, "period": 4.0, "phase": 0.85, "tint": (0.6, 1.0, 0.2, 1)},
]
BOT_CANNON = "Cannon_W"
# мишени: полуразмер внешнего квадрата, среднего, яблочка и прибавки очков. Зоны вложены, поэтому очки складываются:
# ближняя 1 / 3 / 5, дальняя 2 / 4 / 6. Квадраты, а не круги: у триггера нет цилиндра, а у капсулы купола засчитали бы пролёт.
# Дальняя не 2 / 5 / 8: окно у неё лишь на четверть уже, полёт дольше на 0.4 с, а пушек к ней две — при 8 за яблочко
# ближние плоты никому не нужны (разбор 2026-10-25)
NEAR = {"half": (2.8, 1.7, 0.8), "add": (1, 2, 2)}
FAR = {"half": (2.4, 1.4, 0.7), "add": (2, 2, 2)}
SLAB = (0.3, 1.5)     # высота зон очков над палубой плота; ниже, от −0.1 до 0.3, — зона возврата на пирс
# этапы: смещение по X туда-обратно (Move Along Line, 0 — стоит), период и масштаб квадратов. Ближние плывут вместе,
# как утки в тире, дальняя — навстречу (сдвиг фазы на полцикла). Сложность растёт от размера: дрейф окна попадания
# не сужает (ствол всё равно проходит через плот), он только сдвигает момент. Периоды плотов не кратны периодам
# пушек и дают биения короче этапа — иначе фаза «ствол — плот» застывает и лучшая пушка зашита сборкой
# (cannonball/plan/windows.txt, считает windows.py)
STAGES = [{"near": (0.0, 0.0), "far": (0.0, 0.0), "size": 1.0},
          {"near": (2.5, 6.5), "far": (5.0, 8.0), "size": 0.75},
          {"near": (3.5, 3.3), "far": (7.0, 8.3), "size": 0.65}]
NEAR_ANGLE = 15.4     # ближние мишени — на дуге боковых пушек под этим углом от их оси
PUNCH_PUSH, PUNCH_LIFT = 6.0, 3.0
RESPAWN = 2.0
# дефицит яблочка (бэклог 2026-10-27): игра была параллельной — соперник не нужен. Теперь яблочко берёт первый, и на
# BULLSEYE_LOCK секунд зона и краска яблочка пропадают (Disable After Triggered; таймер плота включает их обратно) —
# следующие получают только внешние квадраты, и за плот появляется гонка. Периоды качания не трогал: с плотами 3.3 с
# любое ускорение ×0.75…0.85 даёт биения 30–150 с, дольше этапа, и фаза «ствол — плот» застывает (windows.py)
BULLSEYE_LOCK = 5.0


def flight(shot, steer=0.0, dt=1 / 60):
    """Полёт по правилам CharacterMover (декомпиляция 2026-10-25): в кадр выстрела скорость только задаётся (m_velocityWasSet),
    дальше y −= g·dt, горизонталь тянется к steer·RUN поперёк выстрела с темпом AIR_ACCEL вдоль нормали разности.
    Возвращает (вбок, вперёд, время) от точки MUZZLE до высоты RAFT_TOP."""
    x, y, z = 0.0, MUZZLE[1], 0.0
    vx, vy, vz = shot
    t, first = 0.0, True
    while True:
        if not first:
            vy -= GRAVITY * dt
            tx, tz = steer * RUN, 0.0
            dx, dz = tx - vx, tz - vz
            n = math.hypot(dx, dz)
            if n > 1e-9:
                sx, sz = dx / n * AIR_ACCEL * dt, dz / n * AIR_ACCEL * dt
                vx = vx + sx if abs(dx) > abs(sx) else tx
                vz = vz + sz if abs(dz) > abs(sz) else tz
        first = False
        x, y, z, t = x + vx * dt, y + vy * dt, z + vz * dt, t + dt
        if vy < 0 and y <= RAFT_TOP:
            return x, z, t


def reach(kind):
    """Дальность от оси пушки до точки падения без подруливания."""
    return MUZZLE[2] + flight(SHOTS[kind])[1]


def raft_points():
    """Центры плотов (x, z): ближние — на дуге боковых пушек под NEAR_ANGLE к центру, дальний — на пересечении дуг центральных."""
    west, east, cw = CANNONS[0], CANNONS[3], CANNONS[1]
    a = math.radians(NEAR_ANGLE)
    near_l = (west["x"] + reach(west["kind"]) * math.sin(a), PIVOT_Z + reach(west["kind"]) * math.cos(a))
    near_r = (east["x"] - reach(east["kind"]) * math.sin(a), near_l[1])
    far = (0.0, PIVOT_Z + math.sqrt(reach(cw["kind"]) ** 2 - cw["x"] ** 2))
    return near_l, near_r, far


def build(name: str, workshop: str = WORKSHOP) -> str:
    rng = random.Random("cannonball-v1")
    mod = Mod(name, description="Rusted Park: four swinging circus cannons by an acid lake. Jump into a barrel when it points "
                                "at a raft, steer in the air, land in the bullseye. Three rounds, the rafts drift faster. / "
                                "Человек-ядро: прыгни в качающуюся пушку, когда она смотрит на плот, подрули в полёте и "
                                "попади в яблочко. Три раунда, плоты плывут всё быстрее.",
              rounds=ROUNDS, round_duration=ROUND, end_conditions=EndCondition.TIMER, placement=Placement.MOST_POINTS,
              # удар не ранит (punchDamage 0 — без здоровья иначе любой удар убивает), а толкает: отбор пушки и сбивание в полёте.
              # weaponHitTrigger, m_hitType 1 = Melee: Source — бьющий, Receiver — получивший (схема Mascot Throne)
              settings_overrides={"respawnEnabled": True, "respawnTime": RESPAWN, "respawnInvulnerableTime": 1.0,
                                  "canPunch": True, "useHealth": False, "punchDamage": 0, "punchStunsTarget": False,
                                  "playerGravity": GRAVITY, "jumpSpeed": JUMP, "movementSpeed": RUN,
                                  "midAirMovementAcceleration": AIR_ACCEL,
                                  "weaponHitTrigger": {"m_type": 80, "m_actions": [], "m_hitType": 1}},
              player_triggers={"weaponHitTrigger": [
                  act_change_velocity(PUNCH_PUSH, VelocityDir.TOWARDS_RECEIVER, Op.ADD, flags=Targets.RECEIVER),
                  act_change_velocity(PUNCH_LIFT, VelocityDir.UP, Op.ADD, flags=Targets.RECEIVER)]})

    # --- ассеты
    def prop(fn): return mod.add_file_asset("prop", os.path.join(ASSETS, "models", fn))
    def tex(fn): return mod.add_file_asset("texture", os.path.join(ASSETS, "textures", fn))
    def wav(fn): return mod.add_file_asset("audio", os.path.join(ASSETS, "audio", fn))
    barrel_cannon_obj, dais_obj, barrel_obj = prop("cannon_barrel.obj"), prop("throne_dais.obj"), prop("barrel.obj")
    booth_obj, mascot_obj, lamp_obj, fence_obj = prop("booth.obj"), prop("mascot_headless.obj"), prop("lamppost.obj"), prop("fence_segment.obj")
    rotor_obj, stand_obj, roof_obj = prop("ferris_wheel_rotor.obj"), prop("ferris_wheel_stand.obj"), prop("carousel_roof.obj")
    tree_obj, hill_obj, trestle_obj = prop("dead_tree.obj"), prop("hill.obj"), prop("coaster_trestle.obj")
    rail_obj, debris_obj, cart_obj = prop("rail_segment.obj"), prop("debris.obj"), prop("cart.obj")
    boom_wav, ding_wav, finish_wav = wav("cannon_boom.wav"), wav("ticket_pickup.wav"), wav("finish.wav")
    concrete_tex = tex("concrete.png")
    paint_mat = mod.add_material("CarouselPaint", tex("carousel_paint.png"), tiling=(1.0, 1.0))
    rust_mat = mod.add_material("RustBooth", tex("rust_booth.png"), tiling=(2.0, 2.0))
    metal_mat = mod.add_material("RustMetal", tex("rust_metal.png"), tiling=(1.0, 1.0))
    dirt_mat = mod.add_material("Dirt", tex("dirt.png"), tiling=(20.0, 20.0))
    deck_mat = mod.add_material("Concrete_Deck", concrete_tex, tiling=(6.0, 3.0))
    dais_mat = mod.add_material("Concrete_Dais", concrete_tex, tiling=(1.0, 1.0))

    def wall(parent, name, pos, model, rot=(0, 0, 0), scale=(1, 1, 1), mat=None, tint=(1, 1, 1, 1)):
        return parent.add(obj(name, pos=pos, rot=rot, scale=scale, layer=LAYER_WORLD_WALL)
                          .prop(model, collision=Collision.BOX, materials=[mat.guid] if mat else None, tint=tint))

    def deco(parent, name, pos, model, rot=(0, 0, 0), scale=(1, 1, 1), mat=None, tint=(1, 1, 1, 1), shadow=Shadow.ON):
        return parent.add(obj(name, pos=pos, rot=rot, scale=scale)
                          .prop(model, collision=Collision.NONE, shadow=shadow, materials=[mat.guid] if mat else None, tint=tint))

    # --- пирс и кислотное озеро. Сетка воды центрирована на позиции; под пирсом её не видно
    world = mod.add(obj("World"))
    depth = DECK_FRONT - DECK_BACK
    world.add(obj("Deck", pos=(0, -0.5, (DECK_FRONT + DECK_BACK) / 2), scale=(2 * DECK_HALF, 1.0, depth), layer=LAYER_WORLD_GROUND)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[deck_mat.guid]))
    world.add(obj("Lake", pos=(0, WATER_Y, 18)).water(
        width=34, height=24, cell=2.0, deep=(0.12, 0.45, 0.08, 0.8), shallow=(0.45, 1.0, 0.2, 0.8), froth=(0.8, 1.0, 0.6, 1)))
    # верх зоны смерти на −1.4, под плотами (низ плота −1.2): промахнувшийся уходит в кислоту и взрывается
    world.add(obj("KillVolume", pos=(0, -1.9, 18)).trigger(
        TriggerShape.BOX, size=(90, 1, 70), on_enter=[act_spawn_effect(Effect.EXPLOSION, Targets.SOURCE), act_kill(Targets.SOURCE)]))
    # дно озера под зоной смерти (верх −2.6). После конца раунда игра не убивает (KillPlayer пропускает m_isBetweenRounds),
    # а физика идёт: летевший в последнюю секунду падал сквозь кислоту в пустоту (плейтест трёхраундовой версии).
    # Раунд теперь один, но та же пауза есть и перед итогами — дно оставлено. Слой Default, не WorldGround: для plan_view это не пол
    world.add(obj("LakeBed", pos=(0, -3.1, 18), scale=(90, 1, 70))
              .prop(PROP_CUBE, collision=Collision.BOX, shadow=Shadow.OFF, materials=[dirt_mat.guid], tint=(0.2, 0.25, 0.15, 1)))

    # --- возврат на пирс: попавший на плот переносится к своей точке у задней стены лицом к озеру
    returns = mod.add(obj("Return Points"))
    ret = {side: returns.add(obj(f"Return_{side}", pos=(x, 1.0, -8.5))) for side, x in (("W", -5.0), ("C", 0.0), ("E", 5.0))}

    # --- пушки. Ось качания (Simple Animator, Custom, поворот вокруг Y поверх базового) несёт ствол, лафет, зону входа,
    # метку дула и шест прицела на точке падения. Коллизии на качающихся частях нет: движущийся коллайдер игрока не толкает
    cannons = mod.add(obj("Cannons"))
    pads = {}
    for c in CANNONS:
        x, d = c["x"], reach(c["kind"])
        root = cannons.add(obj(c["name"], pos=(x, 0, PIVOT_Z)))
        root.add(obj("Turntable", scale=(1.7 / 3.0, 1.0, 1.7 / 3.0), layer=LAYER_WORLD_GROUND)
                 .prop(dais_obj.guid, collision=Collision.MESH, materials=[dais_mat.guid]))
        pivot = root.add(obj("Swing", rot=(0, c["yaw"], 0)).simple_animator(
            anim_swing(1.0 / c["period"], c["amp"], offset=c["phase"])))
        for side in (-1, 1):
            pivot.add(obj(f"Cheek_{'L' if side < 0 else 'R'}", pos=(0.75 * side, 0.75, 0.1), scale=(0.25, 1.3, 1.8))
                      .prop(PROP_CUBE, collision=Collision.NONE, materials=[metal_mat.guid]))
        pivot.add(obj("Barrel", pos=(0, 1.3, 0.3), rot=(-40, 0, 0))
                  .prop(barrel_cannon_obj.guid, collision=Collision.NONE, materials=[paint_mat.guid]))
        muzzle = pivot.add(obj("Muzzle", pos=MUZZLE))
        pole = pivot.add(obj("AimPole", pos=(0, RAFT_TOP + 0.4, d)))
        pole.add(obj("Pole", scale=(0.16, 2.6, 0.16)).prop(PROP_CUBE, collision=Collision.NONE, shadow=Shadow.OFF, tint=c["tint"]))
        pole.add(obj("Bob", pos=(0, 1.45, 0), scale=(0.5, 0.5, 0.5))
                 .prop(PROP_SPHERE, collision=Collision.NONE, shadow=Shadow.OFF, tint=c["tint"]))
        # шар того же цвета на стволе — по нему видно, чей шест
        pivot.add(obj("Badge", pos=(0, 2.0, -0.3), scale=(0.45, 0.45, 0.45))
                  .prop(PROP_SPHERE, collision=Collision.NONE, shadow=Shadow.OFF, tint=c["tint"]))
        # вход: телепорт в дуло (позиция и поворот по Y — камера смотрит по выстрелу), затем скорость. Match Transform —
        # ServerRelay: клиент ждёт ретрансляции и только потом выполняет следующее действие (ModActionRunner)
        pads[c["name"]] = pivot.add(obj("Pad", pos=(0, 0, 0)).trigger(
            TriggerShape.BOX, size=(PAD, 2.0, PAD), center=(0, 1.0, 0),
            on_enter=[act_match_transform(muzzle.transform_guid, values=1 | 2 | 4 | 16, flags=Targets.SOURCE),
                      act_change_velocity(1.0, VelocityDir.CUSTOM, Op.SET, space=1, custom=SHOTS[c["kind"]]),
                      act_spawn_effect(Effect.EXPLOSION, Targets.ADVANCED, [muzzle.transform_guid]),
                      act_play_sound(boom_wav.guid, 1.0, Targets.RECEIVER)]))
        c["reach"] = d
    # цель ботов — центр зоны входа западной пушки (неподвижный узел на пирсе, не на качающейся оси)
    bot = next(c for c in CANNONS if c["name"] == BOT_CANNON)
    mod.add(obj("AI Navigation")).add(obj("AIGoal_Cannon", pos=(bot["x"], 0.35, PIVOT_Z)).ai_node(is_goal=True))

    # --- мишени
    near_l, near_r, far = raft_points()
    tints = ((0.95, 0.92, 0.85, 1), (0.8, 0.15, 0.1, 1), (1.0, 0.82, 0.1, 1))

    def raft(parent, name, xz, spec, side, drift, size):
        """Плот-мишень: корпус с полом WorldGround, три крашеных квадрата, флажок над яблочком, вложенные зоны очков
        и зона возврата под ними. size — масштаб квадратов этапа."""
        amp, period = drift
        halves = [h * size for h in spec["half"]]
        root = parent.add(obj(name, pos=(xz[0] - amp, RAFT_TOP, xz[1])))
        if amp:
            root.simple_animator(anim_move_along_line(1.0 / period, (2 * amp, 0, 0)), local_position=False,
                                 time_offset=period / 2 if spec is FAR else 0.0)
        h0 = halves[0]
        root.add(obj("Body", pos=(0, -0.3, 0), scale=(2 * h0, 0.6, 2 * h0), layer=LAYER_WORLD_GROUND)
                 .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
        # флажок над яблочком: с пирса палуба видна под 8–13°, квадраты сжаты в полоски; без коллизии и вне зон очков
        # не мешает — зоны триггеры, а не стены. Белое древко с жёлтым флагом не спутать с шестами прицела (цвет пушки + шар)
        flag = root.add(obj("Flag"))
        flag.add(obj("Staff", pos=(0, 1.1, 0), scale=(0.08, 2.2, 0.08))
                 .prop(PROP_CUBE, collision=Collision.NONE, shadow=Shadow.OFF, tint=(0.95, 0.95, 0.9, 1)))
        flag.add(obj("Cloth", pos=(0.33, 1.95, 0), scale=(0.6, 0.4, 0.03))
                 .prop(PROP_CUBE, collision=Collision.NONE, shadow=Shadow.OFF, tint=tints[2]))
        paints = []
        for k, (h, tint) in enumerate(zip(halves, tints)):
            inset = 0.15 if k == 0 else 0.0
            paints.append(root.add(obj(f"Paint_{k}", pos=(0, 0.01 + 0.015 * k, 0), scale=(2 * (h - inset), 0.02, 2 * (h - inset)))
                                   .prop(PROP_CUBE, collision=Collision.NONE, shadow=Shadow.OFF, tint=tint)))
        slab_h = SLAB[1] - SLAB[0]
        for k, (h, add) in enumerate(zip(halves, spec["add"])):
            acts = [act_change_score(add, Op.ADD, Targets.SOURCE)]
            if k == 0:
                acts.append(act_play_sound(ding_wav.guid, 1.0, Targets.RECEIVER))
            if k == 2:
                total = sum(spec["add"])
                acts += [act_spawn_effect(Effect.CONFETTI, Targets.SOURCE), act_play_sound(finish_wav.guid, 1.0, Targets.RECEIVER),
                         act_show_message(f"В яблочко! +{total} / Bullseye! +{total}", 1.5, MsgTarget.TARGET, Targets.SOURCE),
                         act_set_active(ActiveState.DISABLED, [paints[2].transform_guid])]   # краска пропала — яблочко занято
            zone = root.add(obj(f"Score_{k}").trigger(TriggerShape.BOX, size=(2 * h, slab_h, 2 * h),
                                                      center=(0, SLAB[0] + slab_h / 2, 0), on_enter=acts, disable_after=(k == 2)))
            if k == 2:
                # таймер плота возвращает зону и краску яблочка (включение включённого безвредно); у выключенного набора
                # этапа таймер не идёт, с включением набора — идёт
                root.logic(trig_timer(BULLSEYE_LOCK, act_set_active(ActiveState.ENABLED, [zone.transform_guid, paints[2].transform_guid])))
        root.add(obj("Catch").trigger(TriggerShape.BOX, size=(2 * h0 + 0.4, 0.4, 2 * h0 + 0.4), center=(0, 0.1, 0),
                                      on_enter=[act_match_transform(ret[side].transform_guid, values=1 | 2 | 4 | 16,
                                                                    flags=Targets.SOURCE)]))
        return root

    targets = mod.add(obj("Targets"))
    sets = []
    for r, st in enumerate(STAGES):
        s = targets.add(obj(f"Stage_{r + 1}", active=(r == 0)))
        raft(s, "Raft_NearW", near_l, NEAR, "W", st["near"], st["size"])
        raft(s, "Raft_NearE", near_r, NEAR, "E", st["near"], st["size"])
        raft(s, "Raft_Far", far, FAR, "C", st["far"], st["size"])
        sets.append(s)

    # --- средний план пирса: ящики с порохом и бочки между пушками у перил (низкие, у края), кассы у задней стены.
    # Проход от точек возврата и респаунов к каждой зоне входа свободен
    mid = mod.add(obj("Midground"))
    for k, x in enumerate((-6.0, 0.0, 6.0)):
        wall(mid, f"PowderCrate_{k}", (x, 0.3, -1.4), PROP_CUBE, rot=(0, rng.uniform(-8, 8), 0), scale=(1.6, 0.6, 1.0), mat=rust_mat)
        for j in range(2):
            wall(mid, f"PowderBarrel_{k}_{j}", (x + rng.uniform(-0.8, 0.8), 0, -2.6 - 0.6 * j), barrel_obj.guid,
                 rot=(0, rng.uniform(0, 360), 0), mat=metal_mat)
    for k, x in enumerate((-12.5, 12.5)):
        wall(mid, f"Booth_{k}", (x, 0, -9.8), booth_obj.guid, rot=(0, 180 + (-20 if x < 0 else 20), 0), mat=rust_mat)

    # --- мелочь: ядра у пушек, плакат-маскот у задней стены, фонари, обломки; в кислоте качаются бочки
    decor = mod.add(obj("Decor"))
    for c in CANNONS:
        for j in range(3):
            deco(decor, f"Ball_{c['name']}_{j}", (c["x"] + 2.0 + 0.45 * j, 0.22, PIVOT_Z - 1.4 + 0.2 * (j % 2)), PROP_SPHERE,
                 scale=(0.44, 0.44, 0.44), tint=(0.15, 0.15, 0.17, 1))
    deco(decor, "Mascot_Poster", (0, 0, -11.3), mascot_obj.guid, rot=(0, 0, 0), scale=(1.3, 1.3, 1.3), tint=(0.95, 0.6, 0.2, 1))
    for k, (x, z) in enumerate(((-14.2, -0.8), (14.2, -0.8), (-14.2, -11.2), (14.2, -11.2))):
        wall(decor, f"Lamppost_{k}", (x, 0, z), lamp_obj.guid, rot=(0, rng.uniform(-30, 30), 0 if k % 2 else 5), mat=metal_mat)
    for k in range(4):
        deco(decor, f"Debris_{k}", (rng.uniform(-13, 13), 0.08, rng.uniform(-11.5, -10.5)), debris_obj.guid,
             rot=(rng.uniform(0, 360), rng.uniform(0, 360), 0), scale=(rng.uniform(0.3, 0.6),) * 3, tint=(0.5, 0.48, 0.45, 1))
    for k, (x, z, ph) in enumerate(((-14, 7, 0.0), (13, 16, 1.1), (-11, 28, 0.6), (16, 30, 2.0), (-20, 17, 1.6))):
        deco(decor, f"FloatingBarrel_{k}", (x, WATER_Y - 0.25, z), barrel_obj.guid, rot=(85, rng.uniform(0, 360), 0),
             mat=metal_mat).simple_animator(anim_move_along_line(0.3, (0, 0.25, 0)), time_offset=ph)
    deco(decor, "SunkenCart", (-6, WATER_Y - 0.4, 33), cart_obj.guid, rot=(0, 30, 160), mat=metal_mat)
    fence = decor.add(obj("Fence"))
    n = int(2 * DECK_HALF / 3.0)
    for i in range(n):   # перила вдоль переднего края и задней стены; пушки стреляют над перилами
        x = -DECK_HALF + 1.5 + 3.0 * i
        wall(fence, f"Front_{i}", (x, 0, DECK_FRONT - 0.2), fence_obj.guid, mat=metal_mat)
        wall(fence, f"Back_{i}", (x, 0, DECK_BACK + 0.2), fence_obj.guid, mat=metal_mat)
    for i in range(int(depth / 3.0)):
        z = DECK_BACK + 1.5 + 3.0 * i
        for sx in (-1, 1):
            wall(fence, f"Side_{'W' if sx < 0 else 'E'}_{i}", (sx * (DECK_HALF - 0.2), 0, z), fence_obj.guid, rot=(0, 90, 0), mat=metal_mat)

    # --- задний план: дальний берег за озером — безголовый маскот-великан на оси пирса (по нему целятся в дальний плот),
    # за ним колесо обозрения; шатры по бокам, руины горок вдоль озера, холмы и деревья по кругу
    backdrop = mod.add(obj("Backdrop"))
    backdrop.add(obj("OuterGround", pos=(0, -1.3, 10), scale=(18, 1, 18))
                 .prop(PROP_PLANE, collision=Collision.NONE, materials=[dirt_mat.guid]))
    backdrop.add(obj("FallVolume", pos=(0, -8, 0)).trigger(TriggerShape.BOX, size=(400, 4, 400), on_enter=[act_kill(Targets.SOURCE)]))
    backdrop.add(obj("FarShore", pos=(0, -0.2, 47), scale=(70, 1.6, 12))
                 .prop(PROP_CUBE, collision=Collision.NONE, materials=[dirt_mat.guid]))
    deco(backdrop, "GiantMascot", (0, 0.6, 43), mascot_obj.guid, rot=(0, 180, 0), scale=(4.5, 4.5, 4.5), tint=(0.95, 0.75, 0.3, 1))
    wheel = backdrop.add(obj("FerrisWheel", pos=(0, 7.9, 52)).prop(stand_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    wheel.add(obj("Rotor").prop(rotor_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid])
              .mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Z, (0, 0, 1), 10.0))
    for k, (x, z, s) in enumerate(((-22, 45, 1.3), (21, 46, 1.1))):
        deco(backdrop, f"Tent_{k}", (x, 6.0 * s, z), roof_obj.guid, scale=(s, s * 1.4, s), mat=paint_mat)
    for sx in (-1, 1):
        coaster = backdrop.add(obj(f"RuinedCoaster_{'W' if sx < 0 else 'E'}", pos=(sx * 30, -1.2, 0)))
        for i in range(7):
            z = -4 + 7 * i
            coaster.add(obj(f"Trestle_{i}", pos=(0, 0, z), rot=(0, 90, 0)).prop(trestle_obj.guid, collision=Collision.NONE,
                                                                               materials=[metal_mat.guid]))
            if i < 6 and i != (2 if sx < 0 else 4):
                coaster.add(obj(f"Rail_{i}", pos=(0, 10.3, z + 3.5)).prop(rail_obj.guid, collision=Collision.NONE,
                                                                         materials=[metal_mat.guid]))
    for i in range(12):
        ang = 2 * math.pi * i / 12 + rng.uniform(-0.1, 0.1)
        r, s = rng.uniform(62, 76), rng.uniform(0.8, 1.6)
        backdrop.add(obj(f"Hill_{i}", pos=(r * math.cos(ang), -0.2, 10 + r * math.sin(ang)), rot=(0, rng.uniform(0, 360), 0),
                         scale=(s, s * rng.uniform(0.8, 1.4), s)).prop(hill_obj.guid, collision=Collision.NONE, materials=[dirt_mat.guid]))
    for i in range(14):
        x, z = rng.choice((-1, 1)) * rng.uniform(34, 46), rng.uniform(-20, 45)
        backdrop.add(obj(f"DeadTree_{i}", pos=(x, -1.2, z), rot=(0, rng.uniform(0, 360), rng.uniform(-6, 6)),
                         scale=(rng.uniform(0.8, 1.4),) * 3).prop(tree_obj.guid, collision=Collision.NONE, tint=(0.35, 0.28, 0.2, 1)))

    # --- спавны: общий отрезок у задней стены лицом к озеру (вдоль локальной X), респауны там же
    spawns = mod.add(obj("Player Spawnpoints"))
    spawns.add(obj("Spawn_Line", pos=(0, 1, -7.0)).player_spawn(SpawnShape.LINE, SpawnUsage.INITIAL, line_length=16.0, shared=True))
    for i, x in enumerate((-8.0, 0.0, 8.0)):
        spawns.add(obj(f"Respawn_{i}", pos=(x, 1, -10.0)).player_spawn(SpawnShape.POINT, SpawnUsage.RESPAWN))

    # --- этапы внутри одного раунда: цепочка Wait → Set Active, как в Death Carousel. Старый набор плотов выключается
    # до включения нового: ближние плоты соседних этапов стоят в одном месте, и падающий вошёл бы в зоны обоих
    msgs = ["Прыгай в пушку, когда шест под плотом! В полёте рули влево-вправо. / "
            "Jump in when the pole is under a raft! Steer left-right mid-air.",
            "Плоты поплыли — стреляй на упреждение! / Rafts drift — lead your shot!",
            "Финал: плоты меньше и быстрее! / Final: smaller, faster rafts!"]
    acts = [act_show_message(msgs[0], 5.0)]
    for r in range(1, len(STAGES)):
        acts += [act_wait(STAGE_TIME),
                 act_set_active(ActiveState.DISABLED, [sets[r - 1].transform_guid]),
                 act_set_active(ActiveState.ENABLED, [sets[r].transform_guid]),
                 act_show_message(msgs[r], 4.0)]
    mod.add(obj("Director")).logic(trig_round_start(*acts))

    table = []
    for c in CANNONS:
        side, fwd, t = flight(SHOTS[c["kind"]], steer=1.0)
        table.append(f"{c['name']} ({c['kind']}): дальность {c['reach']:.1f} м от оси, полёт {t:.2f} с, подруливание ±{side:.1f} м, "
                     f"качание {c['yaw'] - c['amp']:+.0f}…{c['yaw'] + c['amp']:+.0f}° за {c['period']} с")
    table.append(f"плоты: ближние ({near_l[0]:.1f}, {near_l[1]:.1f}) и ({near_r[0]:.1f}, {near_r[1]:.1f}), "
                 f"дальний ({far[0]:.1f}, {far[1]:.1f})")
    mod.add(obj("Notes").note("Сгенерировано build_mod.py из packs/abandoned-park/minigames/cannonball/DESIGN.md\n" + "\n".join(table)))
    out = mod.write(workshop)

    os.makedirs(os.path.join(HERE, "plan"), exist_ok=True)
    mod.preview_image = os.path.join(HERE, "plan", "preview.png")
    plan_view.render_preview(out, mod.preview_image)
    for line in table:
        print(line)
    return mod.write(workshop)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = build(sys.argv[1] if len(sys.argv) > 1 else "Human Cannonball", sys.argv[2] if len(sys.argv) > 2 else WORKSHOP)
    print("written:", out)
