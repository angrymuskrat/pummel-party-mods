"""Собирает мод Sugar Rush по DESIGN.md в папку WorkshopMods редактора.

Запуск из корня репозитория:  python packs/abandoned-park/minigames/sugar-rush/build_mod.py [имя мода] [папка WorkshopMods]
По умолчанию пишет «Sugar Rush» в WorkshopMods редактора. Сцену, настройки и ассеты пересобирает целиком; превью
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
import navgen  # noqa: E402
import plan_view  # noqa: E402

ASSETS = os.path.join(ROOT, "packs", "abandoned-park", "assets")
WORKSHOP = r"%USERPROFILE%\AppData\LocalLow\Rebuilt Games\Pummel Party\WorkshopMods"
HERE = os.path.dirname(os.path.abspath(__file__))

# Арена — брошенный цирковой шатёр. Кислоты нет и стены глухие: вата, выбитая из рук, летит вперёд-вверх
# (SimpleModPlayer.BeginDropItem: 6 м/с вдоль (forward + up) плюс скорость игрока) и падает под тяжестью 25 м/с²,
# пока не ляжет на опору с нормалью вверх (ModItem.HandleThrownItemCollision). Если бы она упала в кислоту или на
# недоступную крышу, игра встала бы. Поэтому в шатре нет плоских верхов от 1.5 до 5 м: всё либо ниже прыжка и
# досягаемо, либо выше полёта ваты (пик ≈ 4.5 м, если владелец был в прыжке), либо трибуна с пандусом
TENT_R = 17.0         # внутренняя грань стены шатра
WALL_H = 6.5          # выше пика полёта ваты
WALL_PANELS = 16
FLOOR_R = 17.6
DAIS_H = 0.15         # throne_dais.obj: диск r 3, h 0.15, низ на y 0
RING_R0, RING_R1, RING_H = 5.6, 6.2, 0.45   # бортик манежа: перепрыгивается (прыжок 0.98 м), боты идут через проходы
RING_GAPS = (45.0, 135.0, 225.0, 315.0)      # проходы в бортике; по ним сетка ботов входит в манеж
COLUMN_R, COLUMN_DEGS = 11.5, (22.5, 112.5, 202.5, 292.5)
COLUMN_W, COLUMN_H = 1.8, 5.5   # афишные тумбы: петли для погони, верх выше полёта ваты
STAND_W, STAND_D, STAND_H = 7.0, 2.8, 1.4   # трибуны у северной и южной стены: площадка выше прыжка, пандус к манежу
RAMP_W, RAMP_LEN = 2.4, 3.6                  # 1.4 м на 3.6 м — 21° (Mascot Throne бегается на 21.8°)
SPAWN_R = 9.0         # общий круг старта вокруг манежа: до первой ваты в центре всем 9 м
ROUND = 60.0
CARRY_SPEED = 0.8     # с ватой бег ×0.8 (4.8 м/с): догоняющий сокращает разрыв на 1.2 м/с — 3 м за 2.5 с
PUNCH_STUN = 1.0      # удар оглушает на 1 с: вата успевает упасть впереди, ударивший — добежать (DESIGN.md, «Отбор»)
STUN_IMMUNITY = 1.5   # после оглушения 1.5 с неуязвимости к нему — без цепных станов (вату ронять всё равно можно)
SWAT_COOLDOWN = 1.2   # взмах ватой: оглушает на 1 с, перезарядка 1.2 с
FLOSS2_POINTS = ((14.0, 0.0), (-14.0, 0.0), (13.5, 67.5), (13.5, 247.5))   # (r, угол°) для второй ваты: у края на полу
T_SWEEP_A, T_FLOSS2, T_SWEEP_B = 15.0, 30.0, 45.0
SWEEP_A_SPEED, SWEEP_B_SPEED = 40.0, -55.0   # °/с: 9 с и 6.5 с на оборот — периоды не кратны
SWEEP_FROM, SWEEP_TO = 0.6, 5.5
SWEEP_PUSH, SWEEP_LIFT = 8.0, 5.0            # толчок метлы — как в Death Carousel (проверен плейтестом)
PINK, BLUE = (1.0, 0.55, 0.78, 1), (0.5, 0.78, 1.0, 1)


def polar(r, deg):
    a = math.radians(deg)
    return (r * math.cos(a), r * math.sin(a))


def build(name: str, workshop: str = WORKSHOP) -> str:
    rng = random.Random("sugar-rush")
    mod = Mod(name, description="Rusted Park: one cotton candy, everyone wants it. Hold it to score every second, punch "
                                "the holder to knock it loose. / Сахарная лихорадка: держи вату — очко в секунду; ударь "
                                "того, у кого вата, и она вылетит из рук.",
              round_duration=ROUND, end_conditions=EndCondition.TIMER, placement=Placement.MOST_POINTS,
              # удар не ранит и не убивает (useHealth выкл., урон 0 — SimpleModPlayer: MaxHealth 1, ChangeHealth −0),
              # но оглушает. Отбор — в weaponHitTrigger: Drop Minigame Item на получившем удар (Receiver). m_hitType 1 =
              # Melee: и кулак, и взмах ватой (SimpleModPlayer.MeleeAttack → WeaponHitEventType.Melee)
              settings_overrides={"respawnEnabled": True, "respawnTime": 2.0, "respawnInvulnerableTime": 1.0,
                                  "canPunch": True, "useHealth": False, "showHealthBar": False, "punchDamage": 0,
                                  "punchStunsTarget": True, "punchStunDuration": PUNCH_STUN,
                                  "stunImmunityLength": STUN_IMMUNITY,
                                  "weaponHitTrigger": {"m_type": 80, "m_actions": [], "m_hitType": 1}},
              player_triggers={"weaponHitTrigger": [act_drop_minigame_item(drop_all=True, flags=Targets.RECEIVER)]})

    # --- ассеты
    def prop(fn): return mod.add_file_asset("prop", os.path.join(ASSETS, "models", fn))
    def tex(fn): return mod.add_file_asset("texture", os.path.join(ASSETS, "textures", fn))
    candy_obj, dais_obj, roof_obj, barrel_obj = prop("cotton_candy.obj"), prop("throne_dais.obj"), prop("carousel_roof.obj"), prop("barrel.obj")
    mascot_obj, debris_obj, booth_obj = prop("mascot_headless.obj"), prop("debris.obj"), prop("booth.obj")
    rotor_obj, stand_obj = prop("ferris_wheel_rotor.obj"), prop("ferris_wheel_stand.obj")
    tree_obj, hill_obj, trestle_obj, rail_obj = prop("dead_tree.obj"), prop("hill.obj"), prop("coaster_trestle.obj"), prop("rail_segment.obj")
    pickup_wav = mod.add_file_asset("audio", os.path.join(ASSETS, "audio", "ticket_pickup.wav"))
    creak_wav = mod.add_file_asset("audio", os.path.join(ASSETS, "audio", "creak.wav"))
    sweep_wav = mod.add_file_asset("audio", os.path.join(ASSETS, "audio", "sweep.wav"))
    dirt_tex = tex("dirt.png")
    canvas_mat = mod.add_material("TentCanvas", tex("rust_booth.png"), tiling=(3.0, 3.0))
    paint_mat = mod.add_material("CarouselPaint", tex("carousel_paint.png"), tiling=(1.0, 1.0))
    metal_mat = mod.add_material("RustMetal", tex("rust_metal.png"), tiling=(1.0, 1.0))
    sawdust_mat = mod.add_material("Sawdust", dirt_tex, tiling=(8.0, 8.0), color=(1.0, 0.86, 0.62, 1))
    ring_mat = mod.add_material("RingFloor", dirt_tex, tiling=(3.0, 3.0), color=(1.0, 0.62, 0.5, 1))
    dirt_mat = mod.add_material("Dirt", dirt_tex, tiling=(20.0, 20.0))

    def wall(parent, name, pos, model, rot=(0, 0, 0), scale=(1, 1, 1), mat=None, tint=(1, 1, 1, 1)):
        return parent.add(obj(name, pos=pos, rot=rot, scale=scale, layer=LAYER_WORLD_WALL)
                          .prop(model, collision=Collision.BOX, materials=[mat.guid] if mat else None, tint=tint))

    def deco(parent, name, pos, model, rot=(0, 0, 0), scale=(1, 1, 1), mat=None, tint=(1, 1, 1, 1), shadow=Shadow.ON):
        return parent.add(obj(name, pos=pos, rot=rot, scale=scale)
                          .prop(model, collision=Collision.NONE, materials=[mat.guid] if mat else None, tint=tint,
                                shadow=shadow))

    def disc(parent, name, r, top, mat):
        """Диск из throne_dais.obj (r 3, h 0.15) с верхом на top."""
        h = max(DAIS_H, top)
        return parent.add(obj(name, pos=(0, top - h, 0), scale=(r / 3.0, h / DAIS_H, r / 3.0), layer=LAYER_WORLD_GROUND)
                          .prop(dais_obj.guid, collision=Collision.MESH, materials=[mat.guid]))

    def slab(parent, name, p0, p1, width, thick, mat=None, layer=LAYER_WORLD_WALL, collision=Collision.BOX,
             shadow=Shadow.ON, tint=(1, 1, 1, 1)):
        """Наклонный куб: верхняя грань от p0 до p1 (середины торцов) — как пандус башни в Mascot Throne."""
        dx, dy, dz = (p1[i] - p0[i] for i in range(3))
        flat = math.hypot(dx, dz)
        yaw, pitch = math.atan2(dx, dz), -math.atan2(dy, flat)
        up = (math.sin(yaw) * math.sin(pitch), math.cos(pitch), math.cos(yaw) * math.sin(pitch))
        mid = [(p0[i] + p1[i]) / 2 - up[i] * thick / 2 for i in range(3)]
        return parent.add(obj(name, pos=mid, rot=(math.degrees(pitch), math.degrees(yaw), 0),
                              scale=(width, thick, math.hypot(flat, dy)), layer=layer)
                          .prop(PROP_CUBE, collision=collision, materials=[mat.guid] if mat else None, shadow=shadow,
                                tint=tint))

    # --- сахарная вата: визуал (палочка + облако) и предмет. Weapon, а не Carried: боты без оружия бегут к ближайшему
    # свободному оружию (SimpleModPlayer.UpdateTargetType → GetWeapon), Carried они не видят. С оружием в руках удар
    # кулаком заменяется взмахом этого оружия (SimpleModPlayer.Update: flag = false) — владелец отмахивается ватой
    def floss_visual(vname, tint):
        root = obj(vname, pos=(0, 0.15, 0))
        root.add(obj("Stick", pos=(0, 0.35, 0), scale=(0.05, 0.7, 0.05))
                 .prop(PROP_CUBE, collision=Collision.NONE, tint=(0.95, 0.9, 0.78, 1)))
        root.add(obj("Fluff", pos=(0, 0.62, 0), scale=(0.95, 0.95, 0.95)).prop(candy_obj.guid, collision=Collision.NONE, tint=tint))
        return mod.add_prefab(root)

    swat = copy.deepcopy(DEFAULT_WEAPON_INFO)
    swat["basicInfo"].update(damage=0, cooldown=SWAT_COOLDOWN)
    swat["meleeInfo"].update(damage=0, range=2.0, attackAnimation=1)   # Swing
    swat.update(stunOnHit=True, stunDuration=PUNCH_STUN)

    def floss_item(iname, visual, tint):
        # очки — 'While Held' раз в секунду владельцу (ModItem.UpdateHeld: Source — держащий игрок, выполняет владелец).
        # Подбор — касанием (ModItemTrigger.OnTriggerEnter на сервере). UniquePickup: держащий вторую вату не берёт.
        # CanBeDropped выкл. — кнопкой сброса вату не выбросить; Drop Minigame Item этот флаг не проверяет
        return mod.add_prefab(obj(iname).item(
            ItemType.WEAPON, visual_prefab_guid=visual.guid, weapon_info=swat, cooldown=SWAT_COOLDOWN,
            while_held=[act_change_score(1, Op.ADD, Targets.SOURCE)],
            on_pickup=[act_modify_player_speed(CARRY_SPEED, Targets.SOURCE),
                       act_spawn_effect(Effect.SPARKLES, Targets.SOURCE),
                       act_play_sound(pickup_wav.guid, 0.8, Targets.RECEIVER)],
            on_drop=[act_modify_player_speed(1.0, Targets.SOURCE)],
            unique_pickup=True, can_drop=False, disappear_when_dropped=False, auto_drop=False, drop_on_death=True))

    floss1 = floss_item("Floss Item", floss_visual("Floss Visual", PINK), PINK)
    floss2 = floss_item("Floss Item Blue", floss_visual("Floss Visual Blue", BLUE), BLUE)

    # --- пол, манеж, стены шатра
    world = mod.add(obj("World"))
    disc(world, "Floor", FLOOR_R, 0.0, sawdust_mat)
    disc(world, "RingFloor", RING_R0, 0.03, ring_mat)   # выше пола на 3 см — ниже ступеньки, заходят все
    ring = world.add(obj("RingCurb"))
    n_seg = 24
    for i in range(n_seg):
        deg = 360.0 * (i + 0.5) / n_seg
        if any(abs((deg - g + 180) % 360 - 180) < 360.0 / n_seg for g in RING_GAPS):
            continue
        cx, cz = polar((RING_R0 + RING_R1) / 2, deg)
        seg = 2 * RING_R1 * math.sin(math.pi / n_seg) + 0.05
        wall(ring, f"Curb_{i}", (cx, RING_H / 2, cz), PROP_CUBE, rot=(0, -deg, 0), scale=(RING_R1 - RING_R0, RING_H, seg),
             mat=paint_mat)
    tent = world.add(obj("TentWall"))
    panel = 2 * (TENT_R + 0.4) * math.tan(math.pi / WALL_PANELS) + 0.1
    for i in range(WALL_PANELS):
        deg = 360.0 * i / WALL_PANELS
        cx, cz = polar(TENT_R + 0.2, deg)
        wall(tent, f"Wall_{i}", (cx, WALL_H / 2, cz), PROP_CUBE, rot=(0, -deg, 0), scale=(0.4, WALL_H, panel), mat=canvas_mat)

    # --- средний план: афишные тумбы (петли для погони), трибуны с пандусом, низкие скамьи и ящики
    mid = mod.add(obj("Midground"))
    for k, deg in enumerate(COLUMN_DEGS):
        cx, cz = polar(COLUMN_R, deg)
        wall(mid, f"Column_{k}", (cx, COLUMN_H / 2, cz), PROP_CUBE, rot=(0, 45 - deg, 0), scale=(COLUMN_W, COLUMN_H, COLUMN_W),
             mat=canvas_mat if k % 2 else paint_mat)
        ox, oz = polar(COLUMN_R + 1.9, deg + 8)   # ящик снаружи тумбы, у стены — перепрыгнуть или обежать
        wall(mid, f"Crate_{k}", (ox, 0.25, oz), PROP_CUBE, rot=(0, -deg + rng.uniform(-12, 12), 0), scale=(0.9, 0.5, 1.6),
             mat=metal_mat)
    stands = []
    for k, side in enumerate((1, -1)):   # север (+Z) и юг (−Z); пандус у южной трибуны зеркален
        st = mid.add(obj(f"Stand_{'N' if side > 0 else 'S'}"))
        z_front, z_back = side * (TENT_R - 0.2 - STAND_D), side * (TENT_R - 0.2)
        wall(st, "Platform", (0, STAND_H / 2, (z_front + z_back) / 2), PROP_CUBE, scale=(STAND_W, STAND_H, STAND_D), mat=metal_mat)
        rx = side * (STAND_W / 2 - RAMP_W / 2)
        slab(st, "Ramp", (rx, STAND_H, z_front), (rx, 0.0, z_front - side * RAMP_LEN), RAMP_W, 0.4, metal_mat)
        for r in range(3):   # ряды сидений — декор на площадке
            deco(st, f"Bench_{r}", (-0.9 * side, STAND_H + 0.2, z_front + side * (0.5 + 0.8 * r)), PROP_CUBE,
                 scale=(4.6, 0.12, 0.35), tint=(0.62, 0.2, 0.15, 1))
        deco(st, "Mascot", (-2.6 * side, STAND_H, z_front + side * 1.7), mascot_obj.guid, rot=(0, 0 if side < 0 else 180, 0),
             tint=(0.9, 0.7, 0.35, 1))
        stands.append(st)
    for k, deg in enumerate((0.0, 180.0)):   # скамьи у восточной и западной стены, перед точками второй ваты
        for j, off in enumerate((-2.2, 2.2)):
            bx, bz = polar(15.6, deg + math.degrees(off / 15.6))
            wall(mid, f"Bench_{k}_{j}", (bx, 0.225, bz), PROP_CUBE, rot=(0, -deg + rng.uniform(-5, 5), 0), scale=(0.6, 0.45, 3.0),
                 mat=metal_mat)
    # низкие тюки между манежем и краем — рвут длинные прямые (plan_view: 29 м вдоль Z у x ±8.2, 26 м вдоль X у z ±6.7)
    for k, (r, deg) in enumerate(((7.3, 80.0), (7.3, 260.0), (13.2, 160.0), (13.2, 340.0), (8.3, 190.0), (8.3, 10.0))):
        hx, hz = polar(r, deg)
        wall(mid, f"Bale_{k}", (hx, 0.3, hz), PROP_CUBE, rot=(0, -deg + 90 + rng.uniform(-10, 10), 0), scale=(0.9, 0.6, 1.5),
             tint=(0.85, 0.72, 0.38, 1))

    # --- метлы в манеже: брус без коллизии + триггер (движущийся коллайдер не толкает CharacterController), объект
    # метлы стоит на оси, поэтому Towards Source направлен наружу (схема Death Carousel). Сначала выбивает вату
    # (Drop Minigame Item на вошедшем), потом толкает: иначе к броску ваты добавилась бы скорость толчка
    def sweeper(sname, speed, start_deg, tint):
        s = world.add(obj(sname, active=False).mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Y, (0, 1, 0), speed))
        arm = s.add(obj("Arm", rot=(0, start_deg, 0)))
        length, mid_z = SWEEP_TO - SWEEP_FROM, (SWEEP_TO + SWEEP_FROM) / 2
        arm.add(obj("Hit").trigger(
            TriggerShape.BOX, size=(0.9, 1.4, length), center=(0, 0.7, mid_z),
            on_enter=[act_drop_minigame_item(drop_all=True, flags=Targets.SOURCE),
                      act_change_velocity(SWEEP_PUSH, VelocityDir.TOWARDS_SOURCE, Op.ADD),
                      act_change_velocity(SWEEP_LIFT, VelocityDir.UP, Op.ADD),
                      act_play_sound(sweep_wav.guid, 0.9, Targets.RECEIVER)]))
        arm.add(obj("Bar", pos=(0, 0.35, mid_z), scale=(0.35, 0.4, length)).prop(PROP_CUBE, collision=Collision.NONE, tint=tint))
        s.add(obj("Hub", pos=(0, 0.3, 0), scale=(0.7, 0.6, 0.7)).prop(PROP_CUBE, collision=Collision.NONE, tint=tint))
        return s

    sweep_a = sweeper("Sweeper_A", SWEEP_A_SPEED, 0.0, (1.0, 0.82, 0.2, 1))
    sweep_b = sweeper("Sweeper_B", SWEEP_B_SPEED, 180.0, (0.9, 0.25, 0.2, 1))

    # --- верх шатра: рваные полотнища от кольца-короны (13 м) к стенам, гигантская вата крутится под куполом,
    # трапеция качается — всё без коллизии и без тени (полосы тени прятали бы игроков)
    top = mod.add(obj("TentTop"))
    for k in range(8):
        if k in (2, 5):   # двух полотнищ нет — купол порван
            continue
        deg = 45.0 * k + 22.5
        a0, a1 = polar(2.2, deg), polar(TENT_R + 0.3, deg)
        slab(top, f"Canvas_{k}", (a0[0], 13.0, a0[1]), (a1[0], WALL_H + 0.1, a1[1]), 4.0 if k % 2 else 3.2, 0.06,
             canvas_mat, layer=LAYER_DEFAULT, collision=Collision.NONE, shadow=Shadow.OFF)
    deco(top, "CrownRing", (0, 12.7, 0), roof_obj.guid, scale=(0.22, 0.25, 0.22), mat=paint_mat, shadow=Shadow.OFF)
    deco(top, "Rope", (0, 11.3, 0), PROP_CUBE, scale=(0.08, 2.8, 0.08), tint=(0.3, 0.25, 0.2, 1), shadow=Shadow.OFF)
    giant = top.add(obj("GiantCandy", pos=(0, 6.2, 0)).mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Y, (0, 1, 0), 15.0))
    giant.add(obj("Fluff", scale=(4.2, 4.2, 4.2)).prop(candy_obj.guid, collision=Collision.NONE, tint=PINK, shadow=Shadow.OFF))
    tx, tz = polar(9.0, 200.0)
    trapeze = top.add(obj("Trapeze", pos=(tx, 11.5, tz), rot=(0, -200.0, 0))
                      .simple_animator(anim_swing(0.23, 22.0, axis=(1, 0, 0))))
    for sx in (-0.7, 0.7):
        trapeze.add(obj(f"Rope_{'L' if sx < 0 else 'R'}", pos=(sx, -1.6, 0), scale=(0.05, 3.2, 0.05))
                    .prop(PROP_CUBE, collision=Collision.NONE, tint=(0.3, 0.25, 0.2, 1), shadow=Shadow.OFF))
    trapeze.add(obj("Bar", pos=(0, -3.2, 0), scale=(1.6, 0.08, 0.08))
                .prop(PROP_CUBE, collision=Collision.NONE, tint=(0.85, 0.75, 0.3, 1), shadow=Shadow.OFF))

    # --- мелочь: бочки и обломки у стен и тумб, у точек второй ваты — разбитые ларьки сладостей
    decor = mod.add(obj("Decor"))
    for k, deg in enumerate((40, 50, 140, 220, 230, 320)):
        bx, bz = polar(15.9 + rng.uniform(-0.3, 0.3), deg + rng.uniform(-2, 2))
        wall(decor, f"Barrel_{k}", (bx, 0, bz), barrel_obj.guid, rot=(0, rng.uniform(0, 360), 0), mat=metal_mat)
    for k in range(8):
        deg = COLUMN_DEGS[k % 4] + rng.uniform(-25, 25)
        dx, dz = polar(COLUMN_R + rng.uniform(-2.5, 2.5), deg)
        deco(decor, f"Debris_{k}", (dx, 0.1, dz), debris_obj.guid, rot=(rng.uniform(0, 360), rng.uniform(0, 360), 0),
             scale=(rng.uniform(0.3, 0.6),) * 3, tint=(0.55, 0.5, 0.42, 1))
    for k, (r, deg) in enumerate(FLOSS2_POINTS):   # ларёк сладостей за точкой второй ваты, у стены (за стену не выходит)
        bx, bz = polar(r + 2.2, deg)
        deco(decor, f"CandyStall_{k}", (bx, -0.4, bz), booth_obj.guid, rot=(10 if k % 2 else -8, -deg - 90, 0),
             scale=(0.8, 0.8, 0.8), mat=paint_mat)

    # --- задний план за стенами: колесо обозрения выше шатра, руины горок, холмы и деревья
    backdrop = mod.add(obj("Backdrop"))
    backdrop.add(obj("OuterGround", pos=(0, -0.05, 0), scale=(18, 1, 18))
                 .prop(PROP_PLANE, collision=Collision.NONE, materials=[dirt_mat.guid]))
    backdrop.add(obj("FallVolume", pos=(0, -8, 0)).trigger(TriggerShape.BOX, size=(400, 4, 400), on_enter=[act_kill(Targets.SOURCE)]))
    wheel = backdrop.add(obj("FerrisWheel", pos=(-6, 9.0, 28), scale=(1.3, 1.3, 1.3))
                         .prop(stand_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    wheel.add(obj("Rotor").prop(rotor_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid])
              .mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Z, (0, 0, 1), 10.0))
    coaster = backdrop.add(obj("RuinedCoaster", pos=(0, -0.1, -34)))
    for i in range(7):
        x = -18 + 6 * i
        coaster.add(obj(f"Trestle_{i}", pos=(x, 0, 0)).prop(trestle_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
        if i < 6 and i != 4:
            coaster.add(obj(f"Rail_{i}", pos=(x + 3, 10.3, 0), rot=(0, 90, 0))
                        .prop(rail_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    for i in range(12):
        a = 2 * math.pi * i / 12 + rng.uniform(-0.1, 0.1)
        r, s = rng.uniform(58, 72), rng.uniform(0.8, 1.6)
        backdrop.add(obj(f"Hill_{i}", pos=(r * math.cos(a), -0.2, r * math.sin(a)), rot=(0, rng.uniform(0, 360), 0),
                         scale=(s, s * rng.uniform(0.8, 1.4), s)).prop(hill_obj.guid, collision=Collision.NONE, materials=[dirt_mat.guid]))
    for i in range(14):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(24, 46)
        backdrop.add(obj(f"DeadTree_{i}", pos=(r * math.cos(a), -0.1, r * math.sin(a)), rot=(0, rng.uniform(0, 360), rng.uniform(-6, 6)),
                         scale=(rng.uniform(0.8, 1.4),) * 3).prop(tree_obj.guid, collision=Collision.NONE, tint=(0.35, 0.28, 0.2, 1)))

    # --- спавны: общий круг вокруг манежа (до первой ваты в центре всем поровну); респауны у края — только на случай
    # падения в FallVolume (смертей в игре нет)
    spawns = mod.add(obj("Player Spawnpoints"))
    spawns.add(obj("Spawn_Ring", pos=(0, 1, 0)).player_spawn(SpawnShape.CIRCLE, SpawnUsage.INITIAL, radius=SPAWN_R, shared=True))
    for i, deg in enumerate((45, 135, 225, 315)):
        x, z = polar(14.0, deg)
        spawns.add(obj(f"Respawn_{i}", pos=(x, 1, z)).player_spawn(SpawnShape.POINT, SpawnUsage.RESPAWN))

    # --- вата появляется спавнером Spawn On Destruction: в первом Update после включения — сразу (ModSpawner.DoSpawn),
    # дальше — только если предмет уничтожен. Наша вата при сбросе не исчезает, так что спавнер ставит её один раз;
    # повтор через 3 с — страховка, если игра уничтожит предмет сама (DropAndDestroyAllItems)
    spawners = mod.add(obj("Floss Spawners"))
    spawners.add(obj("Floss_1", pos=(0, 1.0, 0)).spawner([floss1.guid], interval=(1.0, None), delay=(3.0, None),
                                                          kind=SpawnerType.ON_DESTRUCTION))
    pts = spawners.add(obj("Floss_2_Points"))
    point_objs = []
    for k, (r, deg) in enumerate(FLOSS2_POINTS):
        x, z = polar(r, deg)
        point_objs.append(pts.add(obj(f"Point_{k}", pos=(x, 1.0, z))))
    floss2_spawner = spawners.add(obj("Floss_2", pos=(0, 1.0, 0), active=False).spawner(
        [floss2.guid], interval=(1.0, None), delay=(3.0, None), kind=SpawnerType.ON_DESTRUCTION,
        location=SpawnerLocation.ON_TARGETS, spawn_points=[p.transform_guid for p in point_objs], count=1))

    mod.add(obj("Director").logic(trig_round_start(
        act_show_message("Хватай вату! Держишь — очко в секунду. Бей того, у кого вата! / "
                         "Grab the candy! Hold it to score. Punch the holder!", 4.0),
        act_wait(T_SWEEP_A),
        act_set_active(ActiveState.ENABLED, [sweep_a.transform_guid]),
        act_play_sound(creak_wav.guid, 1.0, Targets.RECEIVER),
        act_show_message("В манеже метла — выбивает вату! / A broom in the ring knocks the candy loose!", 3.0),
        act_wait(T_FLOSS2 - T_SWEEP_A),
        act_set_active(ActiveState.ENABLED, [floss2_spawner.transform_guid]),
        act_play_sound(pickup_wav.guid, 1.0, Targets.RECEIVER),
        act_show_message("Вторая вата — голубая, у края! / A second, blue candy by the wall!", 3.0),
        act_wait(T_SWEEP_B - T_FLOSS2),
        act_set_active(ActiveState.ENABLED, [sweep_b.transform_guid]),
        act_play_sound(creak_wav.guid, 1.0, Targets.RECEIVER),
        act_show_message("Вторая метла! / A second broom!", 3.0))))
    mod.add(obj("Notes").note("Сгенерировано build_mod.py из packs/abandoned-park/minigames/sugar-rush/DESIGN.md"))
    out = mod.write(workshop)

    os.makedirs(os.path.join(HERE, "plan"), exist_ok=True)
    mod.preview_image = os.path.join(HERE, "plan", "preview.png")
    plan_view.render_preview(out, mod.preview_image)

    # --- сетка ботов: узлы в точках появления ваты; через бортик манежа связи идут только по проходам
    specials = [{"name": "Nav_Floss_1", "pos": (0.0, 0.5, 0.0), "kind": "ground"}]
    specials += [{"name": f"Nav_Floss_2_{k}", "pos": (p.pos[0], 0.5, p.pos[2]), "kind": "ground"} for k, p in enumerate(point_objs)]
    nodes, edges, warnings = navgen.generate(out, specials)
    nav = mod.add(obj("AI Navigation"))
    node_objs = [nav.add(obj(n, pos=pos).ai_node()) for n, pos in nodes]
    link_ai_nodes(node_objs, edges)
    for w in warnings:
        print("сетка ботов:", w)
    print(f"сетка ботов: {len(nodes)} узлов, {len(edges)} связей")
    return mod.write(workshop)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = build(sys.argv[1] if len(sys.argv) > 1 else "Sugar Rush", sys.argv[2] if len(sys.argv) > 2 else WORKSHOP)
    print("written:", out)
