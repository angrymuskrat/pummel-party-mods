"""Собирает мод Death Carousel по DESIGN.md в папку WorkshopMods редактора.

Запуск из корня репозитория:  python packs/abandoned-park/minigames/death-carousel/build_mod.py [имя мода] [папка WorkshopMods]
По умолчанию пишет «Death Carousel» в WorkshopMods редактора. Сцену, настройки и ассеты пересобирает целиком; превью
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

DECK_Y = 2.0          # верх пола карусели над водой
DECK_R = 10.0         # внешний радиус карусели (край из секторов carousel_sector.obj)
# разгон: до SPIN_START карусель стоит (игроков ставят на точки появления, пока всё неподвижно), потом каждые
# SPIN_STEP секунд берёт следующую скорость из списка, град/с; последняя держится до конца раунда.
# 45 град/с — край r 7 едет 5.5 м/с при беге 6 м/с
SPIN_START = 1.5
SPIN_STEP = 4.0
SPIN_RAMP = (15.0, 22.0, 30.0, 37.0, 45.0)
# метёлки разгоняются так же, с момента включения: две пары в разные стороны и с разным шагом, чтобы в такт
# не напрыгаться; относительно пола их скорость меняется ещё и вместе с каруселью
SWEEP_A_RAMP = (-30.0, -38.0, -46.0, -54.0, -62.0, -70.0)
SWEEP_C_RAMP = (50.0, 60.0, 70.0, 80.0, 90.0)
SWEEP_PUSH, SWEEP_LIFT = 8.0, 5.0   # м/с от метлы: толкает чуть сильнее удара (7 и 4.5), но добавляет, а не задаёт скорость
SWEEP_FROM = 0.55     # брусья начинаются у колонны (половина её ширины 0.5), чтобы у оси не было безопасного кольца
HORSE_R = 6.5         # кольцо шестов с лошадками
HORSE_LOW = -0.25     # нижняя точка лошадки: седло на 0.8 м над полом — запрыгнуть можно (прыжок 0.98 м)
HORSE_RISE = 0.9      # ход вверх; на подъёме седло 1.7 м — брусья (0.55 м) проходят под стоящим на нём
ROOF_H = 6.0          # высота крыши над полом: камера третьего лица у края смотрит под неё
EDGE_FALL = (18.0, 49.0)   # когда падает каждый из 8 секторов края, с, от начала раунда (у каждого своя случайная задержка)
EDGE_WARN = 1.5       # красный сектор и скрип до падения
# фазы эскалации, с от начала раунда (прожарка 2026-10-25: расписание 90-секундного раунда, сжатое в 0.7 раза)
T_SWEEP_A, T_EDGE, T_SWEEP_C, T_DEBRIS, T_GRAVITY = 7.0, 18.0, 28.0, 35.0, 42.0
PUNCH_PUSH, PUNCH_LIFT = 7.0, 4.5   # м/с от удара: в полёте ~0.36 с при гравитации 25 — отлёт на 2–3 м
# обломки сыплются с конструкции крыши: появляются прямо под ней (низ крыши — ROOF_H), а не над, иначе пролетали
# бы сквозь твёрдую крышу (Mover коллизий не замечает)
DEBRIS = False        # фаза обломков выключена 2026-10-25: случайный стан без метки на полу — смерть, которую не прочитать
DEBRIS_H = 5.6        # высота появления обломков над полом
DEBRIS_SPEED = 4.0    # м/с вниз (Mover Custom): долетает до пола за DEBRIS_H / DEBRIS_SPEED = 1.4 с
POND_HALF = 30.0      # пруд 60 × 60 м вокруг карусели
GRAVITY = 9.81        # Physics.gravity по умолчанию; гравитация игрока = playerGravity · g_новая / 9.81 (SimpleModPlayer)
ROUND = 60.0          # Round Duration: вылетевший первым не смотрит полторы минуты


def spin_chain(target_guid, ramp, duration):
    """Вращение с разгоном: Mover нельзя включить позже или ускорить, поэтому это цепочка твинов «повернуть на угол
    за SPIN_STEP секунд» (RotateAroundWorldAxis вокруг Y, линейно) с Wait той же длины; скорости по очереди из ramp,
    последняя держится, пока не наберётся duration."""
    actions, speeds = [], list(ramp)
    for _ in range(math.ceil(duration / SPIN_STEP)):
        speed = speeds.pop(0) if len(speeds) > 1 else speeds[0]
        actions += [act_play_tween([target_guid], Tween.ROTATE_WORLD_AXIS, axis=(0, 1, 0), degrees=speed * SPIN_STEP,
                                   seconds=SPIN_STEP, ease=Ease.LINEAR),
                    act_wait(SPIN_STEP)]
    return actions


def build(name: str, workshop: str = WORKSHOP) -> str:
    rng = random.Random("death-carousel")
    mod = Mod(name, description="Rusted Park: stay on the spinning carousel above the acid pond and push the others off. "
                                "Last one standing wins. / Карусель смерти: держись на карусели над кислотным прудом и "
                                "сталкивай остальных — побеждает последний.",
              round_duration=ROUND, end_conditions=EndCondition.TIMER | EndCondition.REMAINING_ALIVE,
              # места по выбыванию. Last Man Standing по коду — тоже очки: умерший k-м получает 10·k
              # (SimpleModPlayer, при смерти), дожившие до таймера — 10·(выбывших + 1) (SimpleModController.RoundEnded).
              # Прежние «+1 в секунду и −3 за удар» отменены (прожарка 2026-10-25): раунд кончается сразу после падения
              # предпоследнего, поэтому у двух последних секунд поровну, и места решали удары — чаще всего ботов
              placement=Placement.LAST_MAN_STANDING, min_players_alive=1,
              # удар не убивает, а отталкивает. Без здоровья у игрока 1 HP (SimpleModPlayer.MaxHealth), и удар с уроном 1
              # убивал сразу; урон 0 даёт только анимацию вздрагивания. Своего отброса у удара нет — он в weaponHitTrigger:
              # Source — бьющий, Receiver — получивший, Towards Receiver = от бьющего. m_hitType 1 = Melee; при 0 триггер
              # не срабатывает ни на что. Оглушение выключено: длительность приводится к целым секундам, 0.8 → 0
              settings_overrides={"respawnEnabled": False, "useHealth": False, "showHealthBar": False,
                                  "canPunch": True, "punchDamage": 0, "punchStunsTarget": False,
                                  "weaponHitTrigger": {"m_type": 80, "m_actions": [], "m_hitType": 1}},
              player_triggers={"onDeathTrigger": [act_show_message("Минус один! / One down!", 1.5)],
                               "weaponHitTrigger": [
                                   act_change_velocity(PUNCH_PUSH, VelocityDir.TOWARDS_RECEIVER, Op.ADD, flags=Targets.RECEIVER),
                                   act_change_velocity(PUNCH_LIFT, VelocityDir.UP, Op.ADD, flags=Targets.RECEIVER)]})

    # --- ассеты
    def prop(fn): return mod.add_file_asset("prop", os.path.join(ASSETS, "models", fn))
    def tex(fn): return mod.add_file_asset("texture", os.path.join(ASSETS, "textures", fn))
    def wav(fn): return mod.add_file_asset("audio", os.path.join(ASSETS, "audio", fn))
    deck_obj, roof_obj, debris_obj = prop("carousel_deck.obj"), prop("carousel_roof.obj"), prop("debris.obj")
    sector_obj = prop("carousel_sector.obj")
    creak_wav = wav("creak.wav")
    horse_obj, headless_obj = prop("horse.obj"), prop("horse_headless.obj")
    # колесо из двух моделей: крутится только ротор, опоры стоят (pivot у обеих в ступице)
    rotor_obj, stand_obj = prop("ferris_wheel_rotor.obj"), prop("ferris_wheel_stand.obj")
    lamp_obj, barrel_obj, booth_obj = prop("lamppost.obj"), prop("barrel.obj"), prop("booth.obj")
    tree_obj, hill_obj = prop("dead_tree.obj"), prop("hill.obj")
    sweep_wav = wav("sweep.wav")
    mod.music_guid = wav("carousel_music.wav").guid
    paint_mat = mod.add_material("CarouselPaint", tex("carousel_paint.png"), tiling=(1.0, 1.0))
    metal_mat = mod.add_material("RustMetal", tex("rust_metal.png"), tiling=(1.0, 1.0))
    rust_mat = mod.add_material("RustBooth", tex("rust_booth.png"), tiling=(2.0, 2.0))
    dirt_mat = mod.add_material("Dirt", tex("dirt.png"), tiling=(20.0, 20.0))

    # --- обломок: падает Mover'ом (у props нет физики), сбивает и оглушает, у пола взрывается и исчезает.
    # Источник в триггере — вошедший игрок, получатель — обломок: Towards Source = от обломка к игроку
    if DEBRIS:
        debris_root = (obj("Debris")
                       .mover(MoverDir.CUSTOM, (0, -1, 0), DEBRIS_SPEED)
                       .trigger(TriggerShape.SPHERE, radius=1.1,
                                on_enter=[act_stun(1.5, Targets.SOURCE),
                                          act_change_velocity(9.0, VelocityDir.TOWARDS_SOURCE, Op.SET),
                                          act_change_velocity(5.0, VelocityDir.UP, Op.ADD)])
                       .logic(trig_enable(act_wait(DEBRIS_H / DEBRIS_SPEED),
                                          act_spawn_effect(Effect.EXPLOSION, Targets.RECEIVER),
                                          act_kill(Targets.RECEIVER))))
        debris_root.add(obj("Rock", scale=(1.6, 1.6, 1.6))   # add() возвращает ребёнка, поэтому корень держим отдельно
                        .prop(debris_obj.guid, collision=Collision.NONE, tint=(0.5, 0.45, 0.4, 1)))
        debris = mod.add_prefab(debris_root)

    # --- пруд и зона смерти: всё ниже пола карусели
    world = mod.add(obj("World"))
    # сетка воды центрирована на позиции объекта (LowPolyWater: Width × CellSize метров)
    world.add(obj("Pond").water(
        width=30, height=30, cell=2.0, deep=(0.12, 0.45, 0.08, 0.8), shallow=(0.45, 1.0, 0.2, 0.8), froth=(0.8, 1.0, 0.6, 1)))
    world.add(obj("KillVolume", pos=(0, -0.6, 0)).trigger(
        TriggerShape.BOX, size=(2 * POND_HALF + 4, 1.6, 2 * POND_HALF + 4),
        on_enter=[act_spawn_effect(Effect.EXPLOSION, Targets.SOURCE), act_kill(Targets.SOURCE)]))
    world.add(obj("Axle", pos=(0, DECK_Y / 2 - 0.25, 0), scale=(1.4, DECK_Y + 0.5, 1.4), layer=LAYER_WORLD_WALL)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))

    # --- карусель: всё дочернее вращается вместе с родителем. Стоящего игрока везёт CharacterMover.DoPlatformMovement
    # (переносит вслед за трансформом опоры), если на префабе игрока включён m_movingPlatformImprovements — проверить первым
    carousel = world.add(obj("Carousel", pos=(0, DECK_Y, 0)))
    carousel.add(obj("Deck", layer=LAYER_WORLD_GROUND)
                 .prop(deck_obj.guid, collision=Collision.MESH, materials=[paint_mat.guid]))
    # край r 7…10 — 8 секторов; каждый в свой случайный момент краснеет, скрипит и уходит вниз в пруд вместе с теми,
    # кто на нём стоит. Задержки разные: у каждого события Round Start свой сид (ModEvent.Seed), общий для всех игроков
    for k in range(8):
        sector = carousel.add(obj(f"Edge_{k}", rot=(0, 45 * k, 0), layer=LAYER_WORLD_GROUND)
                              .prop(sector_obj.guid, collision=Collision.MESH, materials=[paint_mat.guid]))
        sector.add(obj("Crumble", pos=(8.5, 0.5, 0)).logic(trig_round_start(   # точка звука — середина сектора
            act_wait(*EDGE_FALL),
            act_set_color((1.0, 0.25, 0.15, 1.0), targets=[sector.transform_guid]),
            act_play_sound(creak_wav.guid, 1.0, Targets.RECEIVER),
            act_wait(EDGE_WARN),
            act_play_tween([sector.transform_guid], Tween.LOCAL_POSITION, end=(0, -8, 0), seconds=1.0, ease=Ease.EASE_IN_QUAD),
            act_set_active(ActiveState.DISABLED, [sector.transform_guid]))))
    carousel.add(obj("Column", pos=(0, ROOF_H / 2, 0), scale=(1.0, ROOF_H, 1.0), layer=LAYER_WORLD_WALL)
                 .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
    # крыша твёрдая по форме конуса (Mesh): Box по габариту сделал бы плоский потолок и плоский верх
    carousel.add(obj("Roof", pos=(0, ROOF_H, 0), scale=(0.9, 0.7, 0.9), layer=LAYER_WORLD_WALL)
                 .prop(roof_obj.guid, collision=Collision.MESH, materials=[paint_mat.guid]))
    for i in range(8):
        # между лучами кольцевого спавна (0°, 45°, …) и вне его радиуса, чтобы никто не появился в лошадке
        a = math.radians(22.5 + 45 * i)
        x, z = HORSE_R * math.cos(a), HORSE_R * math.sin(a)
        carousel.add(obj(f"Pole_{i}", pos=(x, ROOF_H / 2, z), scale=(0.18, ROOF_H, 0.18), layer=LAYER_WORLD_WALL)
                     .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
        # лошадка ходит вверх-вниз по шесту. Коллизия Box по габариту всей модели (с головой) была бы выше прыжка,
        # поэтому твёрдое только седло (Box Collider по верху туловища), ноги и голова проходимы
        model = headless_obj if i == 5 else horse_obj
        carousel.add(obj(f"Horse_{i}", pos=(x, HORSE_LOW, z), rot=(0, -math.degrees(a), 0), layer=LAYER_WORLD_WALL)
                     .prop(model.guid, collision=Collision.NONE, materials=[paint_mat.guid])
                     .box_collider(center=(0, 0.95, 0), size=(0.6, 0.2, 1.3))
                     .simple_animator(anim_move_along_line(0.4, (0, HORSE_RISE, 0)), time_offset=0.3 * i))

    # --- метёлки. Низкие брусья (верх 0.55 м) перепрыгиваются. Движущийся коллайдер игрока не толкает
    # (CharacterController), поэтому брус без коллизии, а толчок даёт триггер: объект Sweeper_* стоит в центре,
    # значит Towards Source направлено от оси наружу
    length, mid = DECK_R - SWEEP_FROM, (DECK_R + SWEEP_FROM) / 2

    def sweeper_ring(name, ramp, enabled_at, angles, tint):
        ring = world.add(obj(name, pos=(0, DECK_Y, 0), active=False))
        # Enable срабатывает, когда Director включает кольцо: с этого момента оно разгоняется
        ring.logic(trig_enable(*spin_chain(ring.transform_guid, ramp, ROUND - enabled_at)))
        for k, deg in enumerate(angles):
            arm = ring.add(obj(f"Sweeper_{k}", rot=(0, deg, 0)).trigger(
                TriggerShape.BOX, size=(0.9, 1.4, length), center=(0, 0.7, mid),
                on_enter=[act_change_velocity(SWEEP_PUSH, VelocityDir.TOWARDS_SOURCE, Op.ADD),
                          act_change_velocity(SWEEP_LIFT, VelocityDir.UP, Op.ADD),
                          act_play_sound(sweep_wav.guid, 0.9, Targets.RECEIVER)]))
            arm.add(obj("Bar", pos=(0, 0.35, mid), scale=(0.35, 0.4, length))
                    .prop(PROP_CUBE, collision=Collision.NONE, tint=tint))
        return ring

    ring_a = sweeper_ring("RingA", SWEEP_A_RAMP, T_SWEEP_A, (0, 180), (0.95, 0.8, 0.15, 1))
    ring_c = sweeper_ring("RingC", SWEEP_C_RAMP, T_SWEEP_C, (90, 270), (0.85, 0.2, 0.15, 1))

    # --- низкие препятствия на внутреннем диске (ниже прыжка): упавшая лошадка и ящики между лучами спавна,
    # целиком внутри r ≈ 3 — до кольца появления (r 4) остаётся больше радиуса игрока при любом числе игроков
    for name, r, deg, y, rot, scale, prop_guid, mat in (
            # лежащая на боку лошадка: ширина туловища 0.45 м становится высотой
            ("FallenHorse", 2.0, 22.5, 0.23, (0, 30, 90), (1, 1, 1), horse_obj.guid, paint_mat),
            ("Crate_0", 2.4, 157.5, 0.25, (0, 20, 0), (0.6, 0.5, 1.4), PROP_CUBE, rust_mat),
            ("Crate_1", 2.3, 292.5, 0.23, (0, -35, 0), (1.2, 0.45, 0.6), PROP_CUBE, rust_mat)):
        a = math.radians(deg)
        carousel.add(obj(name, pos=(r * math.cos(a), y, r * math.sin(a)), rot=rot, scale=scale, layer=LAYER_WORLD_WALL)
                     .prop(prop_guid, collision=Collision.BOX, materials=[mat.guid]))

    # --- фаза 3: обломки. Точки над полом неподвижны (карусель уносит игроков из-под них); спавнер в выключенном RingB
    if DEBRIS:
        points = mod.add(obj("DebrisPoints"))
        point_objs = []
        for k, (r, deg) in enumerate(((1.2, 45), (3.0, 130), (4.5, 250), (5.5, 10), (6.0, 190), (8.5, 310))):   # первая — у колонны
            a = math.radians(deg)
            point_objs.append(points.add(obj(f"Point_{k}", pos=(r * math.cos(a), DECK_Y + DEBRIS_H, r * math.sin(a)))))
        ring_b = world.add(obj("RingB", pos=(0, DECK_Y + DEBRIS_H, 0), active=False).spawner(
            [debris.guid], interval=(2.0, 4.0), kind=SpawnerType.ALWAYS, location=SpawnerLocation.ON_TARGETS,
            spawn_points=[p.transform_guid for p in point_objs], count=1))

    # --- задний план: берег ниже воды, фонари по кромке, мусор в пруду, колесо обозрения, холмы и деревья
    backdrop = mod.add(obj("Backdrop"))
    backdrop.add(obj("OuterGround", pos=(0, -0.4, 0), scale=(18, 1, 18))
                 .prop(PROP_PLANE, collision=Collision.NONE, materials=[dirt_mat.guid]))
    backdrop.add(obj("FallVolume", pos=(0, -8, 0)).trigger(TriggerShape.BOX, size=(400, 4, 400),
                                                           on_enter=[act_kill(Targets.SOURCE)]))
    for i in range(8):
        a = 2 * math.pi * i / 8
        tilt = (0, -math.degrees(a), 0) if i not in (1, 6) else (9, -math.degrees(a), -7)
        backdrop.add(obj(f"Lamppost_{i}", pos=((POND_HALF + 2) * math.cos(a), -0.4, (POND_HALF + 2) * math.sin(a)), rot=tilt)
                     .prop(lamp_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    # мусор в воде без коллизии: иначе сбитый игрок приземлится на бочку выше зоны смерти
    for i in range(7):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(14, 26)
        backdrop.add(obj(f"FloatingBarrel_{i}", pos=(r * math.cos(a), -0.45, r * math.sin(a)),
                         rot=(rng.uniform(60, 100), rng.uniform(0, 360), 0))
                     .prop(barrel_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    backdrop.add(obj("SunkenBooth", pos=(-19, -0.9, 15), rot=(0, 35, 14))
                 .prop(booth_obj.guid, collision=Collision.NONE, materials=[rust_mat.guid]))
    wheel = backdrop.add(obj("FerrisWheel", pos=(0, 7.1, -POND_HALF - 14))
                         .prop(stand_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    wheel.add(obj("Rotor").prop(rotor_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid])
              .mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Z, (0, 0, 1), 10.0))
    for i in range(12):
        a = 2 * math.pi * i / 12 + rng.uniform(-0.1, 0.1)
        r, s = rng.uniform(60, 74), rng.uniform(0.8, 1.6)
        backdrop.add(obj(f"Hill_{i}", pos=(r * math.cos(a), -0.6, r * math.sin(a)), rot=(0, rng.uniform(0, 360), 0),
                         scale=(s, s * rng.uniform(0.8, 1.4), s)).prop(hill_obj.guid, collision=Collision.NONE, materials=[dirt_mat.guid]))
    for i in range(16):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(35, 52)
        backdrop.add(obj(f"DeadTree_{i}", pos=(r * math.cos(a), -0.5, r * math.sin(a)), rot=(0, rng.uniform(0, 360), rng.uniform(-6, 6)),
                         scale=(rng.uniform(0.8, 1.4),) * 3).prop(tree_obj.guid, collision=Collision.NONE, tint=(0.35, 0.28, 0.2, 1)))

    # --- спавн: общий круг r 4 внутри кольца лошадок (валидатору хватает одного общего спавна)
    mod.add(obj("Player Spawnpoints")).add(
        obj("Spawn_Ring", pos=(0, DECK_Y + 1, 0)).player_spawn(SpawnShape.CIRCLE, SpawnUsage.INITIAL, radius=4, shared=True))

    # --- эскалация: Round Start (проверен в Ticket Rush) → Wait → Set Active. Глобальную гравитацию после мини-игры
    # игра возвращает сама (SimpleModController.OnDestroy)
    # --- разгон карусели: до SPIN_START стоит, дальше spin_chain; «Держись!» от Director совпадает с началом
    mod.add(obj("Spinner").logic(trig_round_start(
        act_wait(SPIN_START), *spin_chain(carousel.transform_guid, SPIN_RAMP, ROUND - SPIN_START))))

    debris_phase = [act_wait(T_DEBRIS - T_SWEEP_C),
                    act_show_message("Обломки! / Debris!", 2.0),
                    act_set_active(ActiveState.ENABLED, [ring_b.transform_guid]),
                    act_wait(T_GRAVITY - T_DEBRIS)] if DEBRIS else [act_wait(T_GRAVITY - T_SWEEP_C)]
    mod.add(obj("Director").logic(
        trig_round_start(
            act_show_message("Держись! / Hold on!", 2.0),
            act_wait(T_SWEEP_A),
            act_show_message("Метла! / Sweepers!", 2.0),
            act_set_active(ActiveState.ENABLED, [ring_a.transform_guid]),
            act_wait(T_EDGE - T_SWEEP_A),
            act_show_message("Край осыпается! / The edge is crumbling!", 2.0),   # сами сектора падают по своим таймерам
            act_wait(T_SWEEP_C - T_EDGE),
            act_show_message("Ещё метла! / More sweepers!", 2.0),
            act_set_active(ActiveState.ENABLED, [ring_c.transform_guid]),
            *debris_phase,
            # низкая гравитация вдвое удлиняет полёт от удара (0.36 → 0.72 с, отлёт ~2.5 → ~5 м): на диске r 7
            # почти любой удар становится смертельным — это финальная фаза, после неё раунд обычно кончается за секунды
            act_set_gravity((0, -GRAVITY / 2, 0)),
            act_show_message("Невесомость! / Low gravity!", 2.0))))
    mod.add(obj("Notes").note("Сгенерировано build_mod.py из packs/abandoned-park/minigames/death-carousel/DESIGN.md"))
    out = mod.write(workshop)

    # --- превью для окна Load a saved mod: план сверху
    os.makedirs(os.path.join(HERE, "plan"), exist_ok=True)
    mod.preview_image = os.path.join(HERE, "plan", "preview.png")
    plan_view.render_preview(out, mod.preview_image)
    return mod.write(workshop)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = build(sys.argv[1] if len(sys.argv) > 1 else "Death Carousel", sys.argv[2] if len(sys.argv) > 2 else WORKSHOP)
    print("written:", out)
