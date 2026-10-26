"""Собирает мод Bumper Cars по DESIGN.md в папку WorkshopMods редактора.

Запуск из корня репозитория:  python packs/abandoned-park/minigames/bumper-cars/build_mod.py [имя мода] [папка WorkshopMods]
По умолчанию пишет «Bumper Cars» в WorkshopMods редактора. Сцену, настройки и ассеты пересобирает целиком; превью
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

ROUND = 60.0
FLOOR_Y = 1.5          # верх пола автодрома над кислотой (y 0); зона смерти — до y 0.2, пола не касается
TILE = 4.0             # плита пола 4 × 4 м; поле 6 × 4 плиты = 24 × 16 м
COLS, ROWS = 6, 4      # крайние плиты (16 шт.) осыпаются, внутренние 4 × 2 (16 × 8 м) стоят до конца
TILE_GAP = 0.08        # шов между плитами — сетка видна сверху
# борт: резиновый брус по внешнему краю крайних плит. 0.35 м выше ступеньки (0.279) — не перешагнуть, а выстрел
# из пушки на высоте GUN_Y проходит над ним. Прыжка нет, подброс от удара KNOCK_LIFT — 0.18 м: борт держит.
# В «пробоинах» борта нет на половине стороны плиты — там можно вылететь в кислоту с самого начала
RAIL_H, RAIL_W = 0.35, 0.3
# (столбец, ряд) → (сторона, какая половина борта пропала: +1 — по +X/+Z, −1 — по −X/−Z); расставлены симметрично
# относительно центра
RAIL_GAPS = {(1, 3): ("north", 1), (4, 0): ("south", -1), (0, 1): ("west", -1), (5, 2): ("east", 1)}
# стопки шин на крайних плитах: (столбец, ряд, x и z от центра плиты). Пары симметричны относительно центра поля:
# у пробоин — сбоку от дыры, в двух углах и посередине длинных сторон
TIRES = [(1, 3, -1.2, 1.0), (4, 0, 1.2, -1.0), (0, 1, -1.0, 1.2), (5, 2, 1.0, -1.2),
         (0, 3, -1.0, 1.0), (5, 0, 1.0, -1.0), (2, 0, 0.5, -0.9), (3, 3, -0.5, 0.9)]
# пушка-перчатка: hitscan с уроном 0, отброс — в weaponHitTrigger игрока (Source — сама пушка у стрелка, Receiver — получивший)
GUN_RANGE = 10.0       # бот стреляет с ≤ 0.8 · дальности и останавливается в 7 м от цели (SimpleModPlayer.GetAIInput): 8 ≥ 7
GUN_COOLDOWN = 0.8     # ModItem.Cooldown — пауза между выстрелами
GUN_Y = 0.62           # высота пушки над полом на машинке (слот Body = корень модели машинки)
KNOCK_PUSH, KNOCK_LIFT = 11.0, 3.0   # м/с: Add от пушки к получившему + вверх; в воздухе 0.24 с, дальше скольжение — отлёт ~3.5 м
# машинки без водителя: едут по эллипсам вокруг будки, бьют бампером. Периоды 9 и 7 с — не кратны (правило пака).
# Размеры подобраны расчётом по габариту машинки 1.3 × 1.85 с учётом отклонения носа от касательной (до 27°):
# B проходит будку и шины у неё с зазором 0.03–0.14 м, A и B перекрываются 0.16% времени, A заходит на крайний ряд
# плит на 0.45 м
GHOST_A = dict(rx=7.2, rz=3.7, period=9.0, clockwise=True, offset=0.0)
GHOST_B = dict(rx=4.8, rz=2.0, period=7.0, clockwise=False, offset=3.5)
GHOST_PUSH, GHOST_LIFT = 10.0, 3.0
# будка под током (финал): каждые SHOCK_EVERY с отталкивает всех в радиусе SHOCK_R от центра
SHOCK_R, SHOCK_EVERY, SHOCK_PUSH, SHOCK_LIFT = 2.6, 1.5, 8.0, 3.0
EDGE_FALL = (16.0, 48.0)   # у каждой крайней плиты своя случайная задержка от начала раунда
EDGE_WARN = 1.5
T_GHOST_A, T_EDGE, T_GHOST_B, T_SHOCK = 8.0, 16.0, 26.0, 40.0
POND_HALF = 30.0
# камера: статичная, видно всё поле (по коду: позиция = offset + поворот(угол) · назад · дистанция, SimpleModPlayerSettings).
# При вертикальном угле обзора 60° нижний край кадра у z ≈ −9.5 (поле до −8), верхний — у z ≈ 17
CAM_ANGLE, CAM_DIST, CAM_OFFSET = 60.0, 18.0, (0.0, 0.0, -0.5)


def tile_center(col, row):
    return ((col - (COLS - 1) / 2) * TILE, (row - (ROWS - 1) / 2) * TILE)


def is_edge(col, row):
    return col in (0, COLS - 1) or row in (0, ROWS - 1)


def outer_sides(col, row):
    """Стороны крайней плиты, которые смотрят наружу поля: north +Z, south −Z, east +X, west −X."""
    sides = []
    if row == ROWS - 1: sides.append("north")
    if row == 0: sides.append("south")
    if col == COLS - 1: sides.append("east")
    if col == 0: sides.append("west")
    return sides


def build(name: str, workshop: str = WORKSHOP) -> str:
    rng = random.Random("bumper-cars")
    mod = Mod(name, description="Rusted Park: a top-down bumper car brawl. Your spring-glove cannon doesn't hurt — it shoves. "
                                "Knock the others through the broken rails into the acid; last car on the rink wins. / "
                                "Автодром: перчатка-пушка не ранит, а отбрасывает. Выбей остальных через пробитые борта в "
                                "кислоту — побеждает последняя машинка.",
              round_duration=ROUND, end_conditions=EndCondition.TIMER | EndCondition.REMAINING_ALIVE,
              placement=Placement.LAST_MAN_STANDING, min_players_alive=1, player_type=PlayerType.TWIN_STICK)

    # --- ассеты
    def prop(fn): return mod.add_file_asset("prop", os.path.join(ASSETS, "models", fn))
    def tex(fn): return mod.add_file_asset("texture", os.path.join(ASSETS, "textures", fn))
    def wav(fn): return mod.add_file_asset("audio", os.path.join(ASSETS, "audio", fn))
    car_obj, skirt_obj, pole_obj = prop("bumper_car.obj"), prop("bumper_skirt.obj"), prop("car_pole.obj")
    gun_obj, glove_obj, tires_obj = prop("glove_gun.obj"), prop("boxing_glove.obj"), prop("tire_stack.obj")
    booth_obj, barrel_obj, lamp_obj, zone_obj = prop("booth.obj"), prop("barrel.obj"), prop("lamppost.obj"), prop("crown_zone.obj")
    rotor_obj, stand_obj = prop("ferris_wheel_rotor.obj"), prop("ferris_wheel_stand.obj")
    tree_obj, hill_obj = prop("dead_tree.obj"), prop("hill.obj")
    bump_wav, shot_wav, creak_wav = wav("bump.wav"), wav("glove_shot.wav"), wav("creak.wav")
    mod.music_guid = wav("carousel_music.wav").guid
    plate_mat = mod.add_material("RinkPlate", tex("rink_plate.png"), tiling=(1.0, 1.0))
    metal_mat = mod.add_material("RustMetal", tex("rust_metal.png"), tiling=(1.0, 1.0))
    booth_mat = mod.add_material("RustBooth", tex("rust_booth.png"), tiling=(2.0, 2.0))
    dirt_mat = mod.add_material("Dirt", tex("dirt.png"), tiling=(20.0, 20.0))
    concrete_mat = mod.add_material("Concrete", tex("concrete.png"), tiling=(4.0, 1.0))
    rubber_mat = mod.add_material("Rubber", None, color=(0.09, 0.09, 0.1, 1), smoothness=0.15)
    glove_mat = mod.add_material("GloveRed", None, color=(0.8, 0.08, 0.06, 1), smoothness=0.6)
    wreck_mat = mod.add_material("WreckPaint", tex("rust_booth.png"), tiling=(1.0, 1.0))

    def car_parts(root, body_tint=(1, 1, 1, 1), body_mat=None, pole_tilt=0.0, solid=False):
        """Машинка: корпус (без материала — его красит цвет игрока), резиновый бампер и штанга со своими материалами.
        solid — твёрдый корпус (Box по габариту модели, 1.0 × 0.84 × 1.5) для разбитых машинок-укрытий."""
        root.add(obj("Body", layer=LAYER_WORLD_WALL if solid else LAYER_DEFAULT)
                 .prop(car_obj.guid, collision=Collision.BOX if solid else Collision.NONE, tint=body_tint,
                                  materials=[body_mat.guid] if body_mat else None))
        root.add(obj("Skirt").prop(skirt_obj.guid, collision=Collision.NONE, materials=[rubber_mat.guid]))
        root.add(obj("Pole", rot=(pole_tilt, 0, 0)).prop(pole_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
        return root

    # --- машинка игрока (Set Player Visual). Рост и радиус контроллера игра берёт из габарита не-триггерных коллайдеров
    # префаба: Box Collider 1.2 × 0.9 × 1.7 от пола даёт рост 0.9 и радиус 0.45 (SimpleModPlayer.SetCustomPlayerModel)
    car_visual = mod.add_prefab(car_parts(obj("BumperCar").box_collider(center=(0, 0.45, 0), size=(1.2, 0.9, 1.7))))

    # --- пушка-перчатка: визуал + предмет. Слот Body — корень модели машинки; пушка над капотом, перчатка за бампером.
    # Выстрел идёт из позиции предмета вдоль взгляда игрока (вид сверху — transform.rotation, горизонтально)
    gun_visual_root = obj("GloveGunVisual")
    gun_visual_root.add(obj("Gun").prop(gun_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    gun_visual_root.add(obj("Glove").prop(glove_obj.guid, collision=Collision.NONE, materials=[glove_mat.guid]))
    gun_visual = mod.add_prefab(gun_visual_root)
    weapon = dict(DEFAULT_WEAPON_INFO)
    weapon.update(bulletColor={"r": 1.0, "g": 0.25, "b": 0.15, "a": 1.0}, spawnTrailEffect=True,
                  trailStartColor={"r": 1.0, "g": 0.85, "b": 0.3, "a": 1.0}, trailEndColor={"r": 1.0, "g": 0.2, "b": 0.1, "a": 0.0},
                  trailWidth=0.2, trailLength=GUN_RANGE, fireSound=4,   # WeaponFireSound.Custom
                  customFireSound={"m_assetGUID": {"serializedGuid": shot_wav.guid}},
                  basicInfo={"cooldown": GUN_COOLDOWN, "damage": 0},
                  scanInfo=dict(DEFAULT_WEAPON_INFO["scanInfo"], weaponSpreadType=0, range=GUN_RANGE, shotCount=1))
    gun_item = mod.add_prefab(obj("GloveGun").item(
        ItemType.WEAPON, gun_visual.guid, weapon_type=1, weapon_info=weapon, cooldown=GUN_COOLDOWN,
        can_drop=False, disappear_when_dropped=True, drop_on_death=False, slot=4, held_offset=(0, GUN_Y, 0)))

    # --- игроки: машинка и пушка при первом появлении (образец выдачи — InbuiltMods/Pummel Punch, onFirstSpawnTrigger).
    # Удар пушки не ранит (урон 0 → ChangeHealth(0) только вздрагивание), а отбрасывает: weaponHitTrigger с фильтром
    # Projectile (m_hitType 2; при 0 не срабатывает ни на что). Source в нём — предмет-пушка (WeaponComponent.SendHitEvents),
    # она в руках у стрелка, поэтому Towards Receiver — от стрелка к получившему
    mod.settings_overrides = {
        "respawnEnabled": False, "useHealth": False, "showHealthBar": False, "canJump": False, "canPunch": False,
        "weaponHitTrigger": {"m_type": 80, "m_actions": [], "m_hitType": 2},
        "topDownCameraMode": 0, "topDownCameraViewAngle": CAM_ANGLE, "topDownCameraDistance": CAM_DIST,
        "topDownCameraPositionOffset": {"x": CAM_OFFSET[0], "y": CAM_OFFSET[1], "z": CAM_OFFSET[2]}}
    mod.player_triggers = {
        "onFirstSpawnTrigger": [act_set_player_visual(car_visual.guid), act_give_minigame_item(gun_item.guid)],
        "weaponHitTrigger": [act_change_velocity(KNOCK_PUSH, VelocityDir.TOWARDS_RECEIVER, Op.ADD, flags=Targets.RECEIVER),
                             act_change_velocity(KNOCK_LIFT, VelocityDir.UP, Op.ADD, flags=Targets.RECEIVER),
                             act_play_sound(bump_wav.guid, 0.8, Targets.RECEIVER)],
        "onDeathTrigger": [act_show_message("Минус машинка! / Car down!", 1.5)]}

    # --- кислота и зоны смерти
    world = mod.add(obj("World"))
    world.add(obj("Pond").water(
        width=30, height=30, cell=2.0, deep=(0.12, 0.45, 0.08, 0.8), shallow=(0.45, 1.0, 0.2, 0.8), froth=(0.8, 1.0, 0.6, 1)))
    world.add(obj("KillVolume", pos=(0, -0.6, 0)).trigger(
        TriggerShape.BOX, size=(2 * POND_HALF + 4, 1.6, 2 * POND_HALF + 4),
        on_enter=[act_spawn_effect(Effect.EXPLOSION, Targets.SOURCE), act_kill(Targets.SOURCE)]))

    # --- поле: плиты 4 × 4. Крайние — родитель на центре плиты (масштаб 1), под ним плита-куб и борта; родитель уезжает
    # вниз твином и выключается вместе с бортами. Стоящий на плите падает в кислоту
    rink = world.add(obj("Rink"))
    half = TILE / 2
    for row in range(ROWS):
        for col in range(COLS):
            x, z = tile_center(col, row)
            if not is_edge(col, row):
                rink.add(obj(f"Core_{col}_{row}", pos=(x, FLOOR_Y - 0.25, z), scale=(TILE - TILE_GAP, 0.5, TILE - TILE_GAP),
                             layer=LAYER_WORLD_GROUND).prop(PROP_CUBE, collision=Collision.BOX, materials=[plate_mat.guid]))
                continue
            edge = rink.add(obj(f"Edge_{col}_{row}", pos=(x, FLOOR_Y, z)))
            plate = edge.add(obj("Plate", pos=(0, -0.25, 0), scale=(TILE - TILE_GAP, 0.5, TILE - TILE_GAP),
                                 layer=LAYER_WORLD_GROUND).prop(PROP_CUBE, collision=Collision.BOX, materials=[plate_mat.guid]))
            for side in outer_sides(col, row):
                along_x = side in ("north", "south")
                sx = {"east": 1, "west": -1}.get(side, 0)
                sz = {"north": 1, "south": -1}.get(side, 0)
                length, shift = TILE, 0.0
                gap_side, gap_half = RAIL_GAPS.get((col, row), (None, 0))
                if gap_side == side:
                    length, shift = TILE / 2, -gap_half * TILE / 4   # остаётся половина напротив пробоины
                rail_pos = (sx * (half - RAIL_W / 2) + (shift if along_x else 0), RAIL_H / 2,
                            sz * (half - RAIL_W / 2) + (0 if along_x else shift))
                edge.add(obj(f"Rail_{side}", pos=rail_pos,
                             scale=(length, RAIL_H, RAIL_W) if along_x else (RAIL_W, RAIL_H, length), layer=LAYER_WORLD_WALL)
                         .prop(PROP_CUBE, collision=Collision.BOX, materials=[rubber_mat.guid], tint=(1, 1, 1, 1)))
            edge.add(obj("Crumble", pos=(0, 0.5, 0)).logic(trig_round_start(
                act_wait(*EDGE_FALL),
                act_set_color((1.0, 0.25, 0.15, 1.0), targets=[plate.transform_guid]),
                act_play_sound(creak_wav.guid, 1.0, Targets.RECEIVER),
                act_wait(EDGE_WARN),
                act_play_tween([edge.transform_guid], Tween.LOCAL_POSITION, end=(0, -8, 0), seconds=1.0, ease=Ease.EASE_IN_QUAD),
                act_set_active(ActiveState.DISABLED, [edge.transform_guid]))))

    # --- будка в центре: укрытие от выстрелов, вокруг неё ездят машинки; прилавком к +X — вдоль длинной оси эллипсов
    booth = world.add(obj("ControlBooth", pos=(0, FLOOR_Y, 0), rot=(0, 90, 0), scale=(0.9, 0.8, 0.9), layer=LAYER_WORLD_WALL)
                      .prop(booth_obj.guid, collision=Collision.BOX, materials=[booth_mat.guid]))
    # будка под током (финал): неподвижный триггер на оси, выключен до T_SHOCK; Towards Source — от будки наружу
    shock = world.add(obj("BoothShock", pos=(0, FLOOR_Y, 0), active=False).trigger(
        TriggerShape.CAPSULE, radius=SHOCK_R, height=3.0, center=(0, 1.2, 0), stay_interval=SHOCK_EVERY,
        on_stay=[act_change_velocity(SHOCK_PUSH, VelocityDir.TOWARDS_SOURCE, Op.ADD),
                 act_change_velocity(SHOCK_LIFT, VelocityDir.UP, Op.ADD),
                 act_play_sound(bump_wav.guid, 0.7, Targets.RECEIVER)]))
    ring_k = SHOCK_R / 2.4   # crown_zone.obj — кольцо r 2.25…2.5 под r 2.4
    shock.add(obj("Ring", pos=(0, 0.03, 0), scale=(ring_k, 1, ring_k))
              .prop(zone_obj.guid, collision=Collision.NONE, shadow=Shadow.OFF, tint=(1.0, 0.15, 0.1, 1)))

    # --- укрытия. Твёрдые (Box) на слое стен — выстрел в них упирается (маска пушки 3329: слои 0, 8, 10, 11).
    # Внутри малого эллипса у будки — две стопки шин (стоят до конца; разбитая машинка там не помещается рядом с
    # машинкой B), на крайних плитах — две разбитые машинки (падают вместе с плитой)
    for wname, (col, row), (wx, wz), yaw, tilt in (("Wreck_SW", (1, 0), (-0.6, 0.4), 35, -25),
                                                   ("Wreck_NE", (4, 3), (0.6, -0.4), 215, 20)):
        parent = next(c for c in rink.children if c.name == f"Edge_{col}_{row}")
        car_parts(parent.add(obj(wname, pos=(wx, 0, wz), rot=(0, yaw, 0))), body_mat=wreck_mat, pole_tilt=tilt, solid=True)
    for side in (1, -1):
        world.add(obj("CoreTires_" + ("E" if side > 0 else "W"), pos=(3.0 * side, FLOOR_Y, 0), rot=(0, rng.uniform(0, 360), 0),
                      layer=LAYER_WORLD_WALL).prop(tires_obj.guid, collision=Collision.BOX, materials=[rubber_mat.guid]))
    # стопки шин — укрытия на крайних плитах, у пробоин и в углах (падают вместе с плитой); парами, симметрично
    # относительно центра. Высота 0.84 м выше пушки (GUN_Y) — выстрел в них упирается
    for col, row, lx, lz in TIRES:
        parent = next(c for c in rink.children if c.name == f"Edge_{col}_{row}")
        parent.add(obj(f"Tires_{col}_{row}", pos=(lx, 0, lz), rot=(0, rng.uniform(0, 360), 0), layer=LAYER_WORLD_WALL)
                   .prop(tires_obj.guid, collision=Collision.BOX, materials=[rubber_mat.guid]))

    # --- машинки без водителя: Simple Animator везёт по эллипсу (anim_ellipse); корпус без коллизии, толчок даёт
    # триггер (движущийся коллайдер игрока не толкает): Towards Source — от машинки к игроку
    def ghost(gname, p):
        g = world.add(obj(gname, pos=(0, FLOOR_Y, 0), rot=(0, 0 if p["clockwise"] else 180, 0), active=False)
                      .simple_animator(anim_ellipse(p["period"], p["rx"], p["rz"], p["clockwise"]), time_offset=p["offset"]))
        car_parts(g, body_tint=(0.75, 0.75, 0.7, 1), body_mat=wreck_mat, pole_tilt=-15)
        g.add(obj("Bumper").trigger(TriggerShape.BOX, size=(1.5, 1.2, 2.0), center=(0, 0.6, -0.1),
                                    on_enter=[act_change_velocity(GHOST_PUSH, VelocityDir.TOWARDS_SOURCE, Op.ADD),
                                              act_change_velocity(GHOST_LIFT, VelocityDir.UP, Op.ADD),
                                              act_play_sound(bump_wav.guid, 1.0, Targets.RECEIVER)]))
        return g

    ghost_a, ghost_b = ghost("GhostCar_A", GHOST_A), ghost("GhostCar_B", GHOST_B)

    # --- задний план. Статичная камера сверху видит землю примерно до z 17 и x ±18: высокое за полем всё равно обрезано,
    # поэтому мелочь — в кислоте и на бетонной площадке у северного края; колесо и холмы — для редактора и наклона камеры
    backdrop = mod.add(obj("Backdrop"))
    backdrop.add(obj("OuterGround", pos=(0, -0.4, 0), scale=(18, 1, 18))
                 .prop(PROP_PLANE, collision=Collision.NONE, materials=[dirt_mat.guid]))
    backdrop.add(obj("FallVolume", pos=(0, -8, 0)).trigger(TriggerShape.BOX, size=(400, 4, 400),
                                                           on_enter=[act_kill(Targets.SOURCE)]))
    # бетонный перрон автодрома к северу за кислотой: касса, фонари, бочки (без коллизии — туда не долететь)
    backdrop.add(obj("Apron", pos=(0, 0.15, 15.5), scale=(36, 0.5, 5))
                 .prop(PROP_CUBE, collision=Collision.NONE, materials=[concrete_mat.guid]))
    for i, (bx, yaw) in enumerate(((-9, 170), (8.5, 195))):
        backdrop.add(obj(f"TicketBooth_{i}", pos=(bx, 0.4, 16.2), rot=(0, yaw, rng.uniform(-4, 4)))
                     .prop(booth_obj.guid, collision=Collision.NONE, materials=[booth_mat.guid]))
    for i, lx in enumerate((-15, -3, 4, 15)):
        tilt = (0, 0, 0) if i != 2 else (8, 0, -6)
        backdrop.add(obj(f"Lamppost_{i}", pos=(lx, 0.4, 14.2), rot=tilt)
                     .prop(lamp_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    for i in range(5):
        bx = rng.uniform(-14, 14)
        backdrop.add(obj(f"ApronBarrel_{i}", pos=(bx, 0.4, rng.uniform(14.5, 17)), rot=(0, rng.uniform(0, 360), 0))
                     .prop(barrel_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    # бочки и утонувшая машинка в кислоте, качаются на волнах (фоновое движение)
    for i in range(9):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(15, 22)
        x, z = 1.3 * r * math.cos(a), 0.75 * r * math.sin(a)
        backdrop.add(obj(f"FloatingBarrel_{i}", pos=(x, -0.45, z), rot=(rng.uniform(60, 100), rng.uniform(0, 360), 0))
                     .prop(barrel_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid])
                     .simple_animator(anim_move_along_line(rng.uniform(0.2, 0.35), (0, 0.25, 0)), time_offset=rng.uniform(0, 3)))
    sunk = backdrop.add(obj("SunkenCar", pos=(-16.5, -0.35, -3.0), rot=(18, 60, -12)))
    car_parts(sunk, body_mat=wreck_mat, pole_tilt=30)
    sunk.simple_animator(anim_move_along_line(0.18, (0, 0.2, 0)), time_offset=1.0)
    wheel = backdrop.add(obj("FerrisWheel", pos=(0, 7.1, POND_HALF + 14), rot=(0, 180, 0))
                         .prop(stand_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    wheel.add(obj("Rotor").prop(rotor_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid])
              .mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Z, (0, 0, 1), 10.0))
    for i in range(12):
        a = 2 * math.pi * i / 12 + rng.uniform(-0.1, 0.1)
        r, s = rng.uniform(60, 74), rng.uniform(0.8, 1.6)
        backdrop.add(obj(f"Hill_{i}", pos=(r * math.cos(a), -0.6, r * math.sin(a)), rot=(0, rng.uniform(0, 360), 0),
                         scale=(s, s * rng.uniform(0.8, 1.4), s)).prop(hill_obj.guid, collision=Collision.NONE, materials=[dirt_mat.guid]))
    for i in range(10):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(35, 50)
        backdrop.add(obj(f"DeadTree_{i}", pos=(r * math.cos(a), -0.5, r * math.sin(a)), rot=(0, rng.uniform(0, 360), rng.uniform(-6, 6)),
                         scale=(rng.uniform(0.8, 1.4),) * 3).prop(tree_obj.guid, collision=Collision.NONE, tint=(0.35, 0.28, 0.2, 1)))

    # --- спавн: общий круг r 5.5 вокруг будки, снаружи шин у будки (r 3); машинки без водителя ещё выключены
    mod.add(obj("Player Spawnpoints")).add(
        obj("Spawn_Ring", pos=(0, FLOOR_Y + 1, 0)).player_spawn(SpawnShape.CIRCLE, SpawnUsage.INITIAL, radius=5.5, shared=True))

    # --- эскалация: Round Start → Wait → Set Active (как в Death Carousel)
    mod.add(obj("Director").logic(trig_round_start(
        act_show_message("Автодром открыт! Сбивай перчаткой! / The rink is open! Shove with the glove!", 2.5),
        act_wait(T_GHOST_A),
        act_show_message("Машинка без водителя! / A driverless car!", 2.0),
        act_set_active(ActiveState.ENABLED, [ghost_a.transform_guid]),
        act_wait(T_EDGE - T_GHOST_A),
        act_show_message("Края проседают! / The edges are giving way!", 2.0),   # сами плиты падают по своим таймерам
        act_wait(T_GHOST_B - T_EDGE),
        act_show_message("Ещё одна! / Another one!", 2.0),
        act_set_active(ActiveState.ENABLED, [ghost_b.transform_guid]),
        act_wait(T_SHOCK - T_GHOST_B),
        act_show_message("Будка под током! / The booth is live!", 2.5),
        act_set_color((1.0, 0.2, 0.1, 1.0), targets=[booth.transform_guid]),
        act_set_active(ActiveState.ENABLED, [shock.transform_guid]))))
    mod.add(obj("Notes").note("Сгенерировано build_mod.py из packs/abandoned-park/minigames/bumper-cars/DESIGN.md"))
    out = mod.write(workshop)

    # --- превью для окна Load a saved mod: план сверху
    os.makedirs(os.path.join(HERE, "plan"), exist_ok=True)
    mod.preview_image = os.path.join(HERE, "plan", "preview.png")
    plan_view.render_preview(out, mod.preview_image)
    return mod.write(workshop)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = build(sys.argv[1] if len(sys.argv) > 1 else "Bumper Cars", sys.argv[2] if len(sys.argv) > 2 else WORKSHOP)
    print("written:", out)
