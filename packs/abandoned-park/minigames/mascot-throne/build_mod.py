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

# Арена v3 (разбор 2026-10-25): круглая площадь над кислотой вместо квадрата 40 × 40 — прежняя повторяла Ticket Rush,
# и «Колесо» с «Тиром» без ловушек ничем не отличались. Теперь у каждого трона свой рельеф:
#   сцена (центр) — открытый помост в две ступени, драка со всех сторон;
#   башня (север) — площадка 2.2 м, один пандус от центра и батут сбоку: сверху сбивают тех, кто лезет;
#   тир (юго-запад) — двор за стенами выше прыжка, две двери: держать вход;
#   остров (юго-восток) — за краем площади в кислоте, два моста: удар с кольца сбрасывает в кислоту.
PLAZA_R = 16.5        # радиус площади; за краем — кислота, забор везде, кроме выхода к мостам острова
FENCE_R = 16.0
DAIS_H = 0.15         # throne_dais.obj: диск r 3, h 0.15, низ на y 0
STAGE = ((3.6, 0.2),)   # сцена: (радиус, верх) ступеней; одна ступень 0.2 — заходят и боты (ступенька игрока 0.2)
TOWER_C, TOWER_HALF, TOWER_TOP = (0.0, 12.0), 2.5, 2.2
RAMP_BOTTOM_Z = 4.0   # пандус с южной грани башни к сцене: 5.5 м на 2.2 м — 21.8° (подъём Coaster Run 22.6° бегается)
RAMP_W = 2.6
PAD_SPEED = 14.0      # батут у восточной грани башни: пик 3.9 м при гравитации 25, на площадку 2.2 м доруливают
GALLERY_R, GALLERY_DEG, GALLERY_HALF = 11.0, 210.0, 3.8
GALLERY_WALL, GALLERY_DOOR = 2.4, 2.4   # стены выше прыжка (0.98 м); двери на грани к центру и на грани к респауну
ISLAND_R, ISLAND_DEG, ISLAND_SIZE = 22.6, 330.0, 3.4   # зазор кислоты до площади 2.7 м — прыжок на пределе
BRIDGE_W, BRIDGE_SHIFT = 1.2, 2.6   # мост по лучу от центра и второй, сдвинутый вбок
ZONE_R = 2.0          # радиус зоны очков; кольцо crown_zone.obj (r 2.25…2.5) масштабируется на ZONE_R / 2.4
SHRINK = 0.5          # кольцо за стоянку сжимается до r 1.0 (было 0.6 → r 1.2; бэклог 2026-10-27: толпа стояла в кольце
#                       и не дралась — теперь вмещает одного-двух) и при переезде расправляется
ROUND = 60.0
FIRST_HOLD = 10.0     # корона на сцене в начале: со спавна до зоны всем одинаково
# стоянки до финала: номинальная длина, с; в игре — случайно ±HOLD_JITTER. Сид события берётся во время матча
# (ModEvent: GameManager.rand, засеянный Guid при запуске игры), и каждое Wait в цепочке получает своё число
# (ModEvent.GetActionRandomness пропускает CurrentActionIndex значений) — паузы разные в каждом матче.
# Порядок тронов зашит сидом сборки: случайного выбора направления в редакторе нет
PRE_HOLDS = (8.0, 7.0, 6.0, 5.0)
HOLD_JITTER = 1.0
WARN = 3.0            # предупреждение до переезда: маяк следующего трона, скрип, сообщение
MOVE = 1.5            # полёт короны
# финал: с прилёта короны после стоянок PRE_HOLDS (номинально 43.5 с, в игре 39.5–47.5) появляется вторая, красная
# корона на другом троне. Обе по FINAL_HOLD с; красная сдвинута на полцикла, чтобы предупреждения не накладывались.
# Вместо прежней двойной короны (+2 тому, кто в кольце, — чаще лидеру): две зоны делят толпу, у отстающих появляется
# кольцо без лидера. Боты идут только к золотой (цель ботов одна)
FINAL_HOLD = 4.5
FINAL_SPAN = 24.0     # на сколько секунд расписан финал (раунд оборвёт его по таймеру)
PUNCH_PUSH, PUNCH_LIFT = 6.0, 4.0   # м/с от удара (схема Death Carousel, проверена плейтестом 2026-10-25)
DASH, DASH_TIME = 1.5, 3.0          # после респауна бег ×1.5 на 3 с


def polar(r, deg):
    a = math.radians(deg)
    return (r * math.cos(a), r * math.sin(a))


GX, GZ = polar(GALLERY_R, GALLERY_DEG)
IX, IZ = polar(ISLAND_R, ISLAND_DEG)
# top — верх пола под короной; seat — с какой стороны кресло (снаружи арены); ru/en — для сообщений
THRONES = {
    "C": {"xz": (0.0, 0.0), "top": STAGE[-1][1], "seat": 270, "ru": "сцене", "en": "the stage"},
    "N": {"xz": TOWER_C, "top": TOWER_TOP, "seat": 90, "ru": "башне у колеса", "en": "the wheel tower"},
    "SW": {"xz": (GX, GZ), "top": DAIS_H, "seat": GALLERY_DEG, "ru": "тиру", "en": "the shooting gallery"},
    "SE": {"xz": (IX, IZ), "top": 0.0, "seat": ISLAND_DEG, "ru": "острову", "en": "the island"},
}


def schedule(rng):
    """Расписание: pre — [(трон, номинальная стоянка)] до финала, первая — сцена; gold, red — [(трон, прилёт, уход)]
    в секундах от начала финала. В финале короны не бывают на одном троне, включая полёт к нему."""
    pre = [("C", FIRST_HOLD)]
    for hold in PRE_HOLDS:
        pre.append((rng.choice([k for k in THRONES if k != pre[-1][0]]), hold))
    cycle = FINAL_HOLD + MOVE
    while True:
        gold, prev = [], pre[-1][0]
        for i in range(int(FINAL_SPAN // cycle) + 1):
            prev = rng.choice([k for k in THRONES if k != prev])
            gold.append((prev, i * cycle, i * cycle + FINAL_HOLD))
        # красная: первая стоянка длиннее на полцикла, дальше тот же ритм
        red, t, prev = [], 0.0, None
        while t < FINAL_SPAN:
            leave = t + FINAL_HOLD + (cycle / 2 if not red else 0.0)
            prev = rng.choice([k for k in THRONES if k != prev])
            red.append((prev, t, leave))
            t = leave + MOVE
        busy = lambda s: [(k, a - MOVE, b + MOVE) for k, a, b in s]   # noqa: E731
        if all(k1 != k2 or b1 <= a2 or b2 <= a1 for k1, a1, b1 in busy(gold) for k2, a2, b2 in busy(red)):
            return pre, gold, red


def build(name: str, workshop: str = WORKSHOP) -> str:
    rng = random.Random("mascot-throne-v3")
    mod = Mod(name, description="Rusted Park: the crown hops between four thrones — an open stage, a tower, a walled "
                                "gallery and an island in the acid. Stand in its ring to score every second, punch the "
                                "others out. / Трон маскота: корона перелетает между четырьмя тронами — стой в её кольце, "
                                "очко каждую секунду, выбивай остальных.",
              round_duration=ROUND, end_conditions=EndCondition.TIMER, placement=Placement.MOST_POINTS,
              # удар только толкает (бэклог 2026-10-27; было 3 HP и смерть от трёх ударов): смерть стоила 10% раунда и
              # доставалась тому, кого лидер выбил из кольца, — снежный ком. Умирают теперь только в кислоте (остров,
              # выход к мостам), респаун через 3 с у края площади. Без здоровья у игрока 1 HP, поэтому punchDamage 0.
              # Отброс от удара: weaponHitTrigger, m_hitType 1 = Melee, Source — бьющий, Receiver — получивший
              settings_overrides={"respawnEnabled": True, "respawnTime": 3.0, "respawnInvulnerableTime": 2.0,
                                  "canPunch": True, "useHealth": False, "punchDamage": 0, "showHealthBar": False,
                                  "punchStunsTarget": False,
                                  "weaponHitTrigger": {"m_type": 80, "m_actions": [], "m_hitType": 1}},
              player_triggers={"weaponHitTrigger": [
                  act_change_velocity(PUNCH_PUSH, VelocityDir.TOWARDS_RECEIVER, Op.ADD, flags=Targets.RECEIVER),
                  act_change_velocity(PUNCH_LIFT, VelocityDir.UP, Op.ADD, flags=Targets.RECEIVER)],
                  # рывок после респауна. SimpleModPlayer сбрасывает множитель в 1 перед FireRespawnEvent
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
    concrete_tex = tex("concrete.png")
    paint_mat = mod.add_material("CarouselPaint", tex("carousel_paint.png"), tiling=(1.0, 1.0))
    rust_mat = mod.add_material("RustBooth", tex("rust_booth.png"), tiling=(2.0, 2.0))
    metal_mat = mod.add_material("RustMetal", tex("rust_metal.png"), tiling=(1.0, 1.0))
    dirt_mat = mod.add_material("Dirt", tex("dirt.png"), tiling=(20.0, 20.0))
    plaza_mat = mod.add_material("Concrete_Plaza", concrete_tex, tiling=(5.0, 5.0))
    dais_mat = mod.add_material("Concrete_Dais", concrete_tex, tiling=(1.0, 1.0))

    def wall(parent, name, pos, model, rot=(0, 0, 0), scale=(1, 1, 1), mat=None, tint=(1, 1, 1, 1)):
        return parent.add(obj(name, pos=pos, rot=rot, scale=scale, layer=LAYER_WORLD_WALL)
                          .prop(model, collision=Collision.BOX, materials=[mat.guid] if mat else None, tint=tint))

    def deco(parent, name, pos, model, rot=(0, 0, 0), scale=(1, 1, 1), mat=None, tint=(1, 1, 1, 1)):
        return parent.add(obj(name, pos=pos, rot=rot, scale=scale)
                          .prop(model, collision=Collision.NONE, materials=[mat.guid] if mat else None, tint=tint))

    def disc(parent, name, xz, r, top, mat):
        """Диск из throne_dais.obj (r 3, h 0.15): масштаб по радиусу, по высоте — до верха top от y 0 или чуть ниже."""
        h = max(DAIS_H, top) if top > 0 else DAIS_H
        return parent.add(obj(name, pos=(xz[0], top - h, xz[1]), scale=(r / 3.0, h / DAIS_H, r / 3.0), layer=LAYER_WORLD_GROUND)
                          .prop(dais_obj.guid, collision=Collision.MESH, materials=[mat.guid]))

    def ramp(parent, name, p0, p1, width, thick, mat, layer=LAYER_WORLD_WALL):
        """Наклонный куб: верхняя грань от p0 до p1 (середины торцов) — как в Coaster Run."""
        dx, dy, dz = (p1[i] - p0[i] for i in range(3))
        flat = math.hypot(dx, dz)
        yaw, pitch = math.atan2(dx, dz), -math.atan2(dy, flat)
        up = (math.sin(yaw) * math.sin(pitch), math.cos(pitch), math.cos(yaw) * math.sin(pitch))
        mid = [(p0[i] + p1[i]) / 2 - up[i] * thick / 2 for i in range(3)]
        return parent.add(obj(name, pos=mid, rot=(math.degrees(pitch), math.degrees(yaw), 0),
                              scale=(width, thick, math.hypot(flat, dy)), layer=layer)
                          .prop(PROP_CUBE, collision=Collision.BOX, materials=[mat.guid]))

    def seat(parent, key, center_xz, top, local=False):
        """Кресло на краю помоста с внешней стороны, лицом к его центру (модель смотрит в +Z)."""
        sx, sz = (0.0, -2.4) if local else polar(2.4, THRONES[key]["seat"])
        yaw = 0.0 if local else math.degrees(math.atan2(-sx, -sz))
        x0, z0 = (0.0, 0.0) if local else center_xz
        return parent.add(obj("Seat", pos=(x0 + sx, top, z0 + sz), rot=(0, yaw, 0), layer=LAYER_WORLD_WALL)
                          .prop(throne_obj.guid, collision=Collision.BOX, materials=[paint_mat.guid]))

    # --- площадь и кислота вокруг. Сетка воды центрирована на позиции; под площадью вода не видна (как в Death Carousel).
    # Кислота на 1 м ниже площади: край читается бортиком, а plan_view не принимает воду под полом за воду на полу
    world = mod.add(obj("World"))
    disc(world, "Plaza", (0, 0), PLAZA_R, 0.0, plaza_mat)
    world.add(obj("Moat", pos=(0, -1.0, 0)).water(
        width=34, height=34, cell=2.0, deep=(0.12, 0.45, 0.08, 0.8), shallow=(0.45, 1.0, 0.2, 0.8), froth=(0.8, 1.0, 0.6, 1)))
    # верх зоны смерти на −1.4: упавший с края уходит в кислоту на 0.4 м и взрывается. Выше (−0.4) зона лежала бы
    # в 0.4 м под площадью — plan_view и navgen считают такое опасностью на полу
    world.add(obj("KillVolume", pos=(0, -1.9, 0)).trigger(
        TriggerShape.BOX, size=(72, 1, 72),
        on_enter=[act_spawn_effect(Effect.EXPLOSION, Targets.SOURCE), act_kill(Targets.SOURCE)]))

    thrones = mod.add(obj("Thrones"))
    beacons = {}

    def beacon(group, key, center, top, radius):
        b = group.add(obj("Beacon", pos=(center[0], 0, center[1]), active=(key == "C")))
        b.add(obj("Beam", pos=(0, top + 6.0, 0), scale=(0.35, 12.0, 0.35))
              .prop(PROP_CUBE, collision=Collision.NONE, shadow=Shadow.OFF, tint=(1.0, 0.85, 0.2, 1)))
        for k in range(10):
            bx, bz = polar(radius, 36 * k + 18)
            b.add(obj(f"Bulb_{k}", pos=(bx, top + 0.12, bz), scale=(0.25, 0.25, 0.25))
                  .prop(PROP_SPHERE, collision=Collision.NONE, shadow=Shadow.OFF, tint=(1.0, 0.95, 0.4, 1)))
        beacons[key] = b

    # сцена: две ступени по 0.2 м, навес на трёх столбах (между лучами к остальным тронам: 90°, 210°, 330°)
    stage = thrones.add(obj("Throne_C"))
    for k, (r, top) in enumerate(STAGE):
        disc(stage, f"Step_{k}", (0, 0), r, top, dais_mat)
    seat(stage, "C", (0, 0), STAGE[-1][1])
    for k, deg in enumerate((30, 150, 270)):
        px, pz = polar(3.4, deg)
        wall(stage, f"Post_{k}", (px, 2.1, pz), PROP_CUBE, scale=(0.25, 4.2, 0.25), mat=metal_mat)
    deco(stage, "Canopy", (0, 4.2, 0), roof_obj.guid, scale=(0.36, 0.4, 0.36), mat=paint_mat)
    beacon(stage, "C", (0, 0), STAGE[-1][1], 3.3)

    # башня у колеса: площадка 5 × 5 на 2.2 м, пандус к сцене по лучу от центра (по нему же ходят боты), батут сбоку.
    # Слой WorldWall, как у крыш киосков Ticket Rush, на которых стоят: plan_view и сетка ботов видят её стеной
    tx, tz = TOWER_C
    tower = thrones.add(obj("Throne_N"))
    wall(tower, "Platform", (tx, TOWER_TOP / 2, tz), PROP_CUBE, scale=(2 * TOWER_HALF, TOWER_TOP, 2 * TOWER_HALF), mat=metal_mat)
    ramp(tower, "Ramp", (tx, TOWER_TOP, tz - TOWER_HALF), (tx, 0.0, RAMP_BOTTOM_Z), RAMP_W, 0.4, rust_mat)
    seat(tower, "N", TOWER_C, TOWER_TOP)
    pad_x = tx + TOWER_HALF + 0.3 + 1.1
    pad = tower.add(obj("JumpPad", pos=(pad_x, 0, tz)).trigger(
        TriggerShape.BOX, size=(2.2, 1.5, 2.2), center=(0, 0.8, 0),
        on_enter=[act_change_velocity(PAD_SPEED, VelocityDir.UP, Op.SET)]))
    pad.add(obj("Plate", pos=(0, 0.1, 0), scale=(2.2, 0.2, 2.2)).prop(PROP_CUBE, collision=Collision.BOX, tint=(0.9, 0.2, 0.1, 1)))
    beacon(tower, "N", TOWER_C, TOWER_TOP, 2.2)

    # тир: двор за стенами выше прыжка. Группа повёрнута так, что локальная +Z смотрит на центр площади, +X — к респауну
    # на юге. Двери — посередине граней +Z (к центру, по лучу — путь ботов) и +X
    yaw = math.degrees(math.atan2(-math.cos(math.radians(GALLERY_DEG)), -math.sin(math.radians(GALLERY_DEG))))
    gallery = thrones.add(obj("Throne_SW", pos=(GX, 0, GZ), rot=(0, yaw, 0)))
    gallery.add(obj("Dais", layer=LAYER_WORLD_GROUND).prop(dais_obj.guid, collision=Collision.MESH, materials=[dais_mat.guid]))
    seat(gallery, "SW", None, DAIS_H, local=True)
    h, t, seg = GALLERY_HALF, 0.4, (2 * GALLERY_HALF - GALLERY_DOOR) / 2
    for face, (cx, cz, along_x, door) in {"In": (0, h, True, True), "Out": (0, -h, True, False),
                                          "Side": (h, 0, False, True), "Back": (-h, 0, False, False)}.items():
        parts = ((-(GALLERY_DOOR / 2 + seg / 2), seg), (GALLERY_DOOR / 2 + seg / 2, seg)) if door else ((0.0, 2 * h + t),)
        for k, (off, length) in enumerate(parts):
            px, pz = (cx + off, cz) if along_x else (cx, cz + off)
            size = (length, GALLERY_WALL, t) if along_x else (t, GALLERY_WALL, length)
            wall(gallery, f"Wall_{face}_{k}", (px, GALLERY_WALL / 2, pz), PROP_CUBE, scale=size, mat=rust_mat)
    for k, sx in enumerate((-2.7, 2.7)):   # мишени-маскоты у задней стены — декор тира
        deco(gallery, f"Target_{k}", (sx, 0, -3.0), mascot_obj.guid, rot=(0, 180 + 20 * sx, 0), tint=(0.95, 0.75, 0.3, 1))
    beacon(thrones.add(obj("Throne_SW_Beacon")), "SW", (GX, GZ), DAIS_H, 2.7)

    # остров в кислоте за краем площади: два моста — по лучу от центра (путь ботов) и сдвинутый вбок
    island = thrones.add(obj("Throne_SE"))
    disc(island, "Island", (IX, IZ), ISLAND_SIZE, 0.0, dais_mat)
    seat(island, "SE", (IX, IZ), 0.0)
    ux, uz = math.cos(math.radians(ISLAND_DEG)), math.sin(math.radians(ISLAND_DEG))   # луч к острову
    vx, vz = -uz, ux                                                                   # поперёк луча
    for k, shift in enumerate((0.0, -BRIDGE_SHIFT)):
        r0 = math.sqrt(PLAZA_R ** 2 - shift ** 2) - 0.6
        r1 = ISLAND_R - math.sqrt(ISLAND_SIZE ** 2 - shift ** 2) + 0.6
        mx, mz = ux * (r0 + r1) / 2 + vx * shift, uz * (r0 + r1) / 2 + vz * shift
        island.add(obj(f"Bridge_{k}", pos=(mx, -0.15, mz), rot=(0, math.degrees(math.atan2(ux, uz)), 0),
                       scale=(BRIDGE_W, 0.3, r1 - r0), layer=LAYER_WORLD_GROUND)
                   .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
    wall(island, "Barrel", (IX + 2.3 * vx, 0, IZ + 2.3 * vz), barrel_obj.guid, rot=(0, rng.uniform(0, 360), 0), mat=metal_mat)
    beacon(island, "SE", (IX, IZ), 0.0, 3.1)

    # --- короны. Зона — отдельный ребёнок: её масштаб X/Z сжимается твином за стоянку. On Stay с интервалом даёт очко
    # каждому, кто внутри, в кадре срабатывания (ModTrigger.OnEvent); Source — стоящий в зоне игрок
    ring_k = ZONE_R / 2.4

    def make_crown(name, start_key, tint, ring_tint, active):
        sx_, sz_ = THRONES[start_key]["xz"]
        root = mod.add(obj(name, pos=(sx_, THRONES[start_key]["top"], sz_), active=active))
        z = root.add(obj("Zone").trigger(TriggerShape.CAPSULE, radius=ZONE_R, height=8.0, stay_interval=1.0,
                                         on_stay=[act_change_score(1, Op.ADD, Targets.SOURCE)]))
        z.add(obj("Ring", pos=(0, 0.02, 0), scale=(ring_k, 1, ring_k))
              .prop(zone_obj.guid, collision=Collision.NONE, shadow=Shadow.OFF, tint=ring_tint))
        root.add(obj("CrownModel", pos=(0, 3.4, 0), scale=(1.3, 1.3, 1.3))
                 .prop(crown_obj.guid, collision=Collision.NONE, tint=tint)
                 .mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Y, (0, 1, 0), 90.0))
        return root, z

    pre, gold, red = schedule(random.Random("mascot-throne-schedule-v3"))
    crown, zone = make_crown("Crown", "C", (1.0, 0.78, 0.1, 1), (1.0, 0.8, 0.15, 1), True)
    # цель ботов: первый узел с Is AI Goal; позицию бот читает каждый кадр, поэтому узел летит с короной
    goal = crown.add(obj("AIGoal", pos=(0, 0.35, 0)).ai_node(is_goal=True))
    crown2, zone2 = make_crown("Crown2", red[0][0], (0.95, 0.15, 0.1, 1), (1.0, 0.2, 0.1, 1), False)
    crown2.add(obj("Beam", pos=(0, 6.0, 0), scale=(0.35, 12.0, 0.35))
               .prop(PROP_CUBE, collision=Collision.NONE, shadow=Shadow.OFF, tint=(1.0, 0.2, 0.1, 1)))

    # --- средний план: киоски-укрытия между тронами, низкие ящики (0.5 м) на кольце r 7.5 между лучами.
    # Лучи от центра к тронам (90°, 210°, 330°) свободны — по ним идут боты
    mid = mod.add(obj("Midground"))
    for k, deg in enumerate((52, 128, 250, 292)):
        bx, bz = polar(12.5, deg)
        wall(mid, f"Booth_{k}", (bx, 0, bz), booth_obj.guid, rot=(0, -deg + 90 + rng.uniform(-8, 8), 0), mat=rust_mat)
    for k, deg in enumerate((30, 150, 270)):
        cx_, cz_ = polar(7.5, deg)
        wall(mid, f"Crate_{k}", (cx_, 0.25, cz_), PROP_CUBE, rot=(0, -deg + rng.uniform(-10, 10), 0), scale=(2.4, 0.5, 1.0),
             mat=rust_mat)
    # бульвар к острову (plan_view: пустая площадка r 6.8 и пробег 29 м у луча 330°): ящик и бочки по бокам луча,
    # в 3–4 м от него — сам луч свободен, по нему идут боты
    cx_, cz_ = polar(8.5, 352)
    wall(mid, "Crate_Island", (cx_, 0.25, cz_), PROP_CUBE, rot=(0, -352 + 90, 0), scale=(2.4, 0.5, 1.0), mat=rust_mat)
    for k, (r, deg) in enumerate(((10.0, 306), (10.6, 302), (9.6, 300))):
        bx, bz = polar(r, deg)
        wall(mid, f"Barrel_Island_{k}", (bx, 0, bz), barrel_obj.guid, rot=(0, rng.uniform(0, 360), 0), mat=metal_mat)
    for k, deg in enumerate((0, 180)):
        cx_, cz_ = polar(14.0, deg)
        wall(mid, f"Crate_Ring_{k}", (cx_, 0.3, cz_), PROP_CUBE, rot=(0, -deg + rng.uniform(-6, 6), 0), scale=(1.0, 0.6, 2.6),
             mat=rust_mat)

    # --- мелочь: бочки у подножия башни (не на пандусе), обломки у тира и у мостов, бочки в кислоте качаются
    decor = mod.add(obj("Decor"))
    for k, (dx, dz) in enumerate(((-3.6, 10.2), (-4.3, 10.9), (-3.4, 14.8))):
        wall(decor, f"Barrel_Tower_{k}", (tx + dx, 0, dz), barrel_obj.guid, rot=(0, rng.uniform(0, 360), 0), mat=metal_mat)
    for k in range(5):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(4.6, 5.6)
        deco(decor, f"Debris_Gallery_{k}", (GX + r * math.cos(a), 0.1, GZ + r * math.sin(a)), debris_obj.guid,
             rot=(rng.uniform(0, 360), rng.uniform(0, 360), 0), scale=(rng.uniform(0.4, 0.8),) * 3, tint=(0.5, 0.48, 0.45, 1))
    for k, (dr, ds, ph) in enumerate(((19.5, 3.4, 0.0), (20.5, -5.0, 1.3), (26.8, 1.5, 0.6), (18.8, -7.5, 2.1))):
        fx, fz = ux * dr + vx * ds, uz * dr + vz * ds
        deco(decor, f"FloatingBarrel_{k}", (fx, -1.25, fz), barrel_obj.guid, rot=(85, rng.uniform(0, 360), 0),
             mat=metal_mat).simple_animator(anim_move_along_line(0.3, (0, 0.25, 0)), time_offset=ph)
    deco(decor, "SunkenCart", (ux * 21 - vx * 6, -1.4, uz * 21 - vz * 6), cart_obj.guid, rot=(0, 40, 160), mat=metal_mat)
    for k, deg in enumerate((22.5, 67.5, 112.5, 157.5, 247.5, 292.5)):   # фонари у забора; у мостов и за тиром — нет
        lx, lz = polar(15.2, deg)
        tilt = (0, -deg, 0) if k not in (2, 5) else (8, -deg, -6)
        wall(decor, f"Lamppost_{k}", (lx, 0, lz), lamp_obj.guid, rot=tilt, mat=metal_mat)
    fence = decor.add(obj("Fence"))
    n = round(2 * math.pi * FENCE_R / 3.0)
    for i in range(n):
        deg = 360.0 * i / n
        if abs((deg - ISLAND_DEG + 180) % 360 - 180) < 22:   # выход к мостам — край открыт, за ним кислота
            continue
        fx, fz = polar(FENCE_R, deg)
        wall(fence, f"Fence_{i}", (fx, 0, fz), fence_obj.guid, rot=(0, -(deg + 90), 0), mat=metal_mat)

    # --- задний план: колесо обозрения за башней (по нему её и называют), руины горок на юге, холмы, деревья
    backdrop = mod.add(obj("Backdrop"))
    backdrop.add(obj("OuterGround", pos=(0, -1.3, 0), scale=(18, 1, 18))
                 .prop(PROP_PLANE, collision=Collision.NONE, materials=[dirt_mat.guid]))
    backdrop.add(obj("FallVolume", pos=(0, -8, 0)).trigger(TriggerShape.BOX, size=(400, 4, 400), on_enter=[act_kill(Targets.SOURCE)]))
    wheel = backdrop.add(obj("FerrisWheel", pos=(0, 7.1, 30))
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
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(30, 48)
        backdrop.add(obj(f"DeadTree_{i}", pos=(r * math.cos(a), -0.1, r * math.sin(a)), rot=(0, rng.uniform(0, 360), rng.uniform(-6, 6)),
                         scale=(rng.uniform(0.8, 1.4),) * 3).prop(tree_obj.guid, collision=Collision.NONE, tint=(0.35, 0.28, 0.2, 1)))

    # --- спавны: общий круг r 6 вокруг сцены (до зоны всем одинаково), респауны у края между тронами
    spawns = mod.add(obj("Player Spawnpoints"))
    spawns.add(obj("Spawn_Ring", pos=(0, 1, 0)).player_spawn(SpawnShape.CIRCLE, SpawnUsage.INITIAL, radius=6.0, shared=True))
    for i, deg in enumerate((30, 150, 270)):
        x, z = polar(13.5, deg)
        spawns.add(obj(f"Respawn_{i}", pos=(x, 1, z)).player_spawn(SpawnShape.POINT, SpawnUsage.RESPAWN))

    # --- режиссёр. Твины не ждут: следующее действие идёт сразу, паузы дают только Wait
    def place(key):
        x, z = THRONES[key]["xz"]
        return (x, THRONES[key]["top"], z)

    def depart(root, z, key, seconds=MOVE):
        return [act_play_tween([z.transform_guid], Tween.LOCAL_SCALE, end=(1, 1, 1), end_type=TweenValue.SPECIFIC,
                               seconds=seconds, ease=Ease.EASE_OUT_QUAD),
                act_play_tween([root.transform_guid], Tween.LOCAL_POSITION, end=place(key), end_type=TweenValue.SPECIFIC,
                               seconds=seconds, ease=Ease.EASE_IN_OUT_QUAD)]

    def shrink(z, seconds):
        return act_play_tween([z.transform_guid], Tween.LOCAL_SCALE, end=(SHRINK, 1, SHRINK), end_type=TweenValue.SPECIFIC,
                              seconds=seconds, ease=Ease.LINEAR)

    def warn_gold(key):
        t = THRONES[key]
        return [act_set_active(ActiveState.ENABLED, [beacons[key].transform_guid]),
                act_play_sound(creak_wav.guid, 1.0, Targets.RECEIVER),
                act_show_message(f"Корона летит к {t['ru']}! / The crown flies to {t['en']}!", WARN)]

    # до финала: случайные паузы (Wait с диапазоном), длина сжатия — по самой короткой стоянке
    chain = [act_show_message("Займи трон с короной! / Take the crowned throne!", 3.0)]
    for i, (key, hold) in enumerate(pre):
        jitter = 0.0 if i == 0 else HOLD_JITTER
        nxt = pre[i + 1][0] if i + 1 < len(pre) else gold[0][0]
        chain += [shrink(zone, hold - jitter - 0.2),
                  act_wait(hold - jitter - WARN, hold + jitter - WARN if jitter else None),
                  *warn_gold(nxt), act_wait(WARN), *depart(crown, zone, nxt), act_wait(MOVE),
                  act_set_active(ActiveState.DISABLED, [beacons[key].transform_guid])]
    # финал: события обеих корон по общему времени, паузы — константы (иначе короны могли бы сойтись на одном троне)
    events = [(0.0, 0, [act_set_active(ActiveState.ENABLED, [crown2.transform_guid]),
                        act_play_sound(creak_wav.guid, 1.0, Targets.RECEIVER),
                        act_show_message("Вторая корона — красная! / A second crown — the red one!", 2.5)])]
    for seq, root, z, is_gold in ((gold, crown, zone, True), (red, crown2, zone2, False)):
        for i, (key, arrive, leave) in enumerate(seq):
            events.append((arrive, 1, [shrink(z, leave - arrive - 0.2)]))
            if i + 1 == len(seq):
                break
            nxt = seq[i + 1][0]
            if is_gold:
                events.append((leave - WARN, 2, warn_gold(nxt)))
                events.append((leave + MOVE, 4, [act_set_active(ActiveState.DISABLED, [beacons[key].transform_guid])]))
            else:
                t = THRONES[nxt]
                events.append((leave - WARN, 2, [act_play_sound(creak_wav.guid, 1.0, Targets.RECEIVER),
                                                 act_show_message(f"Красная корона летит к {t['ru']}! / "
                                                                  f"The red crown flies to {t['en']}!", WARN)]))
            events.append((leave, 3, depart(root, z, nxt)))
    now = 0.0
    for at, _, acts in sorted(events, key=lambda e: (e[0], e[1])):
        if at > FINAL_SPAN:
            continue
        if at > now:
            chain.append(act_wait(at - now))
            now = at
        chain += acts
    mod.add(obj("Director").logic(trig_round_start(*chain)))

    finale_at = FIRST_HOLD + sum(PRE_HOLDS) + MOVE * len(PRE_HOLDS) + MOVE
    plan_text = ("до финала: " + " → ".join(f"{k} {h:.0f}±{HOLD_JITTER:.0f} с" if i else f"{k} {h:.0f} с" for i, (k, h) in enumerate(pre))
                 + f"; финал с ~{finale_at:.1f} с: золотая " + ", ".join(f"{k} +{a:.1f}–{b:.1f}" for k, a, b in gold)
                 + "; красная " + ", ".join(f"{k} +{a:.1f}–{b:.1f}" for k, a, b in red))
    mod.add(obj("Notes").note("Сгенерировано build_mod.py из packs/abandoned-park/minigames/mascot-throne/DESIGN.md\n"
                              "Расписание корон: " + plan_text))
    out = mod.write(workshop)

    os.makedirs(os.path.join(HERE, "plan"), exist_ok=True)
    mod.preview_image = os.path.join(HERE, "plan", "preview.png")
    plan_view.render_preview(out, mod.preview_image)

    # --- сетка ботов. Поиск пути (ModAINavigation.GetPath) помечает узел при постановке в очередь, поэтому узел-цель
    # достаётся первому из узлов, у которых есть связь с ним, — ближайшему к боту. Связь в цель — только из узла в
    # центре сцены: от него к каждому трону прямая проходима (пандус башни, дверь тира и мост острова лежат на лучах).
    # Узлы на тронах ведут в центр: бот, стоящий у трона, к которому прилетела корона, уже в 1.5 м от цели и стоит.
    # Узлы решётки внутри тира и на острове убраны — иначе бот у короны шёл бы к ней через центр
    hub_y = STAGE[-1][1] + 0.35
    nodes, edges, warnings = navgen.generate(out, [{"name": "Nav_Hub", "pos": (0.0, hub_y, 0.0), "kind": "ground"}])
    inside = lambda p: math.dist((p[0], p[2]), (GX, GZ)) < GALLERY_HALF + 0.6 or math.dist((p[0], p[2]), (IX, IZ)) < ISLAND_SIZE + 0.6  # noqa: E731
    keep = [i for i, (n, p) in enumerate(nodes) if n == "Nav_Hub" or not inside(p)]
    linked = {i for e in edges for i in e if all(j in keep for j in e)}
    keep = [i for i in keep if i in linked or nodes[i][0] == "Nav_Hub"]   # узлы, у которых убрали всех соседей
    remap = {old: new for new, old in enumerate(keep)}
    nodes = [nodes[i] for i in keep]
    edges = [(remap[a], remap[b]) for a, b in edges if a in remap and b in remap]
    hub = next(i for i, (n, _) in enumerate(nodes) if n == "Nav_Hub")
    nav = mod.add(obj("AI Navigation"))
    node_objs = [nav.add(obj(n, pos=pos).ai_node()) for n, pos in nodes]
    for key in ("N", "SW", "SE"):
        x, top, z = place(key)
        node_objs.append(nav.add(obj(f"Nav_Throne_{key}", pos=(x, top + 0.35, z)).ai_node()))
        edges.append((len(node_objs) - 1, hub))
    node_objs.append(goal)
    edges.append((hub, len(node_objs) - 1))
    link_ai_nodes(node_objs, edges)
    for w in warnings:
        print("сетка ботов:", w)
    print(f"сетка ботов: {len(node_objs) - 1} узлов + цель, {len(edges)} связей")
    print("расписание корон:", plan_text)
    return mod.write(workshop)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = build(sys.argv[1] if len(sys.argv) > 1 else "Mascot Throne", sys.argv[2] if len(sys.argv) > 2 else WORKSHOP)
    print("written:", out)
