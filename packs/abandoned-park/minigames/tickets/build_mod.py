"""Собирает мод Ticket Rush по DESIGN.md в папку WorkshopMods редактора.

Запуск из корня репозитория:  python packs/abandoned-park/minigames/tickets/build_mod.py [имя мода] [папка WorkshopMods]
По умолчанию пишет «Ticket Rush» в WorkshopMods редактора. Сцену, настройки и ассеты пересобирает целиком; превью
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
HALF = 20.0  # игровой пол 40×40
POND_RECT = (-4.0, 4.0, 0.0, 8.0)   # x0, x1, z0, z1 пруда — дыра в полу; под него расставлены бочки и ящики у кромки
CORNERS = ((1, 1), (-1, 1), (1, -1), (-1, -1))  # знаки x/z угловых сцен, совпадают с Respawn_0..3
CAROUSEL = (4.0, 0.0, -5.0)                     # центр самой большой пустой площадки по plan_view
BARRIER_AT = (-7.0, 6.0)                        # где ящики режут коридор вдоль каждой стороны забора
BOOTH_TOP = 2.36          # верх коллизии Box киоска (габарит booth.obj)
PAD_SPEED = 16.0          # батут: Set Up 16 м/с → подъём v²/2g = 5.1 м при гравитации игрока 25
PAD_R = (9.6,) * 7 + (9.8,)   # батут перед каждым киоском; седьмой дальше, чтобы лошадки карусели его не задевали
CAROUSEL_ROOF_Y = 2.6     # низ крыши карусели; верх коллизии = 2.6 + 4.35·0.25 ≈ 3.69
TICKET_DELAY = (6.0, 11.0)    # секунд до нового билета после подбора (было 4–8)
# дефицит (прожарка 2026-10-25): было 14 билетов одновременно на 4–6 игроков — каждый собирал свои и не встречал
# соперников. Теперь 8: крыши через одну, 2 у карусели, 2 случайных
ROOF_TICKETS = (0, 2, 4, 6)   # киоски, на крыше которых может появиться билет
# на крышах одновременно ROOF_COUNT билетов из 4 мест, каждый новый — в случайной свободной точке (разбор 2026-10-25):
# с постоянными точками круг по крышам заучивался за 2–3 матча и решал раунд. Пустая крыша видна снизу — билет ×1.5
ROOF_COUNT = 3
# батуты только к крышам с билетом и к крыше карусели (седьмой): батут к пустой крыше обещал награду и не давал её.
# На месте убранных — низкий ящик, чтобы кольцо между киосками не стало прямой дорожкой (прожарка 2026-10-25, Q2)
PADS = ROOF_TICKETS + (7,)
LOOT_VALUE = 1                # выпадает из умершего: убийство окупается (Q1). Не больше 1: у жертвы с 0–3 билетами
LOOT_LIFT = 0.9               # отнимается 0–1, и +2 сделали бы выгодной охоту на бедных
RANDOM_COUNT = 3              # на полу; всего одновременно ROOF_COUNT + 2 у карусели + RANDOM_COUNT = 8, как было
JACKPOT_AT = 40.0             # с этой секунды у пруда появляется большой билет +3 — разгон к концу раунда
JACKPOT_VALUE = 3
JACKPOT_DELAY = (8.0, 12.0)
JACKPOT_POINTS = ((2.0, -0.9), (5.0, 4.0), (-5.0, 4.0), (1.5, 8.9))   # у кромки пруда: риск рядом с наградой


def booth_angle(i):
    return 2 * math.pi * i / 8 + math.pi / 16


HERE = os.path.dirname(os.path.abspath(__file__))


def build(name: str, workshop: str = WORKSHOP) -> str:
    rng = random.Random("ticket-rush")
    rng2 = random.Random("ticket-rush-space")  # для объектов из раздела «Пространство», чтобы не сдвигать прежнюю раскладку
    mod = Mod(name, description="Rusted Park: collect tickets in the ruined fairground. / Билетики: собери больше всех билетов.",
              round_duration=60, end_conditions=EndCondition.TIMER, placement=Placement.MOST_POINTS,
              settings_overrides={"respawnEnabled": True, "respawnTime": 3.0, "respawnInvulnerableTime": 2.0,
                                  "canPunch": True, "useHealth": True, "health": 3, "punchDamage": 1, "showHealthBar": True},
              # смерть (3 удара или пруд) отнимает ⌈¼⌉ билетов: score·3 и деление нацело на 4 (Divide = (int)(i / 4f))
              # дают ⌊3s/4⌋ = s − ⌈s/4⌉; Receiver в событии смерти — умерший
              player_triggers={"onDeathTrigger": [
                  act_change_score(3, Op.MUL, Targets.RECEIVER),
                  act_change_score(4, Op.DIV, Targets.RECEIVER),
                  act_show_message("-1/4 билетов / lost 1/4 of tickets", 2.0, MsgTarget.TARGET, Targets.RECEIVER)]})

    # --- ассеты
    def prop(fn): return mod.add_file_asset("prop", os.path.join(ASSETS, "models", fn))
    def tex(fn): return mod.add_file_asset("texture", os.path.join(ASSETS, "textures", fn))
    ticket_obj, booth_obj = prop("ticket.obj"), prop("booth.obj")
    # колесо из двух моделей: крутится только ротор, опоры стоят (pivot у обеих в ступице)
    rotor_obj, stand_obj = prop("ferris_wheel_rotor.obj"), prop("ferris_wheel_stand.obj")
    lamp_obj, fence_obj, barrel_obj = prop("lamppost.obj"), prop("fence_segment.obj"), prop("barrel.obj")
    tree_obj, hill_obj, trestle_obj = prop("dead_tree.obj"), prop("hill.obj"), prop("coaster_trestle.obj")
    rail_obj, debris_obj = prop("rail_segment.obj"), prop("debris.obj")
    horse_obj, roof_obj, cart_obj = prop("horse.obj"), prop("carousel_roof.obj"), prop("cart.obj")
    pickup_wav = mod.add_file_asset("audio", os.path.join(ASSETS, "audio", "ticket_pickup.wav"))
    rust_mat = mod.add_material("RustBooth", tex("rust_booth.png"), tiling=(2.0, 2.0))
    concrete_tex = tex("concrete.png")
    metal_mat = mod.add_material("RustMetal", tex("rust_metal.png"), tiling=(1.0, 1.0))
    dirt_mat = mod.add_material("Dirt", tex("dirt.png"), tiling=(20.0, 20.0))
    paint_mat = mod.add_material("CarouselPaint", tex("carousel_paint.png"), tiling=(1.0, 1.0))

    # --- добыча: на месте смерти выпадает билет. Pickup, а не Weapon: боты его не видят — иначе бот, погибший в пруду,
    # оставлял бы над кислотой приманку для следующего бота. Висит на LOOT_LIFT над точкой смерти (предмет кинематический)
    loot_visual = mod.add_prefab(obj("Loot Visual", pos=(0, 0.3, 0), rot=(90, 0, 15), scale=(1.5, 1.5, 1.5))
                                 .prop(ticket_obj.guid, collision=Collision.NONE, tint=(1.0, 0.55, 0.15, 1)))
    loot_item = mod.add_prefab(obj("Loot Item").item(
        ItemType.PICKUP, visual_prefab_guid=loot_visual.guid,
        on_pickup=[act_change_score(LOOT_VALUE, Op.ADD, Targets.SOURCE),
                   act_spawn_effect(Effect.SPARKLES, Targets.RECEIVER),
                   act_play_sound(pickup_wav.guid, 0.8, Targets.RECEIVER)]))
    mod.player_triggers["onDeathTrigger"].append(act_spawn_prefab([loot_item.guid], Targets.RECEIVER, offset=(0, LOOT_LIFT, 0)))

    # --- префабы билета: визуал (вертикально, с наклоном 15°) и предмет. Визуал ×1.5 и чуть выше (было ×1 на 0.15):
    # билет на крыше киоска должен читаться снизу, иначе батут уводит на пустую крышу
    ticket_visual = mod.add_prefab(obj("Ticket Visual", pos=(0, 0.3, 0), rot=(90, 0, 15), scale=(1.5, 1.5, 1.5))
                                   .prop(ticket_obj.guid, collision=Collision.NONE, tint=(1.0, 0.85, 0.3, 1)))
    # билет — «оружие», которое исчезает в следующем кадре после подбора. Боты без оружия идут к ближайшему свободному
    # оружию (SimpleModPlayer.UpdateTargetType), а Pickup не ищут вовсе — так боты собирают билеты. Урон обнулён:
    # бот, успевший замахнуться билетом за этот кадр, не должен никого бить
    ticket_weapon = copy.deepcopy(DEFAULT_WEAPON_INFO)
    ticket_weapon["basicInfo"]["damage"] = 0
    ticket_weapon["meleeInfo"]["damage"] = 0
    ticket_item = mod.add_prefab(obj("Ticket Item").item(
        ItemType.WEAPON, visual_prefab_guid=ticket_visual.guid, weapon_info=ticket_weapon,
        on_pickup=[act_change_score(1, Op.ADD, Targets.SOURCE),
                   act_spawn_effect(Effect.SPARKLES, Targets.RECEIVER),
                   act_play_sound(pickup_wav.guid, 0.8, Targets.RECEIVER)],
        can_drop=False, disappear_when_dropped=True, auto_drop=True, drop_after=0.0))
    # большой билет: тот же механизм, ×2.5 и красный, +3 и конфетти
    jackpot_visual = mod.add_prefab(obj("Jackpot Visual", pos=(0, 0.5, 0), rot=(90, 0, 15), scale=(2.5, 2.5, 2.5))
                                    .prop(ticket_obj.guid, collision=Collision.NONE, tint=(1.0, 0.2, 0.12, 1)))
    jackpot_item = mod.add_prefab(obj("Jackpot Item").item(
        ItemType.WEAPON, visual_prefab_guid=jackpot_visual.guid, weapon_info=ticket_weapon,
        on_pickup=[act_change_score(JACKPOT_VALUE, Op.ADD, Targets.SOURCE),
                   act_spawn_effect(Effect.CONFETTI, Targets.RECEIVER),
                   act_play_sound(pickup_wav.guid, 1.0, Targets.RECEIVER)],
        can_drop=False, disappear_when_dropped=True, auto_drop=True, drop_after=0.0))

    # --- игровой пол и киоски
    world = mod.add(obj("World"))
    # пол 40 × 40 из четырёх плит вокруг дыры под пруд: сплошной пол закрывал воду и не пускал к зоне смерти.
    # У каждой плиты своя плитка текстуры, чтобы бетон шёл с тем же шагом 5 м, что у прежнего цельного пола
    x0, x1, z0, z1 = POND_RECT
    for name, (ax, bx, az, bz) in (("W", (-HALF, x0, -HALF, HALF)), ("E", (x1, HALF, -HALF, HALF)),
                                   ("S", (x0, x1, -HALF, z0)), ("N", (x0, x1, z1, HALF))):
        w, d = bx - ax, bz - az
        mat = mod.add_material(f"Concrete_{name}", concrete_tex, tiling=(w / 5, d / 5))
        world.add(obj(f"Ground_{name}", pos=((ax + bx) / 2, 0, (az + bz) / 2), scale=(w / 10, 1, d / 10), layer=LAYER_WORLD_GROUND)
                  .prop(PROP_PLANE, collision=Collision.MESH, materials=[mat.guid]))
    for i in range(8):
        a = 2 * math.pi * i / 8 + math.pi / 16
        world.add(obj(f"Booth_{i}", pos=(12 * math.cos(a), 0, 12 * math.sin(a)), rot=(0, -math.degrees(a) + 90, 0),
                      layer=LAYER_WORLD_WALL).prop(booth_obj.guid, collision=Collision.BOX, materials=[rust_mat.guid]))

    # колесо обозрения: за южным забором на земле задника, крутится вокруг мировой оси Z. На полу (z −17) оно стояло в 2 м
    # за спиной игрока, которого кольцевой спавн ставит в (0, −15) лицом к центру, и камера оказывалась внутри колеса
    wheel = world.add(obj("FerrisWheel", pos=(0, 7.1, -28))
                      .prop(stand_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    wheel.add(obj("Rotor").prop(rotor_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid])
              .mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Z, (0, 0, 1), 10.0))

    # пруд в дыре пола: вода центрирована на позиции объекта (LowPolyWater), зона смерти — сразу под её поверхностью.
    # Бортик без коллизии — видимая кромка, в пруд с него падают
    pond_c = ((x0 + x1) / 2, (z0 + z1) / 2)
    pond = world.add(obj("Pond", pos=(pond_c[0], -0.3, pond_c[1])).water(
        width=int(x1 - x0), height=int(z1 - z0), cell=1.0,
        deep=(0.12, 0.45, 0.08, 0.8), shallow=(0.45, 1.0, 0.2, 0.8), froth=(0.8, 1.0, 0.6, 1)))
    pond.add(obj("KillVolume", pos=(0, -0.6, 0)).trigger(
        TriggerShape.BOX, size=(x1 - x0, 1, z1 - z0),
        on_enter=[act_spawn_effect(Effect.EXPLOSION, Targets.SOURCE), act_kill(Targets.SOURCE)]))
    for name, pos, size in (("S", (pond_c[0], z0 - 0.15), (x1 - x0 + 0.6, 0.3)), ("N", (pond_c[0], z1 + 0.15), (x1 - x0 + 0.6, 0.3)),
                            ("W", (x0 - 0.15, pond_c[1]), (0.3, z1 - z0)), ("E", (x1 + 0.15, pond_c[1]), (0.3, z1 - z0))):
        world.add(obj(f"PondCurb_{name}", pos=(pos[0], 0.06, pos[1]), scale=(size[0], 0.12, size[1]))
                  .prop(PROP_CUBE, collision=Collision.NONE, tint=(0.35, 0.36, 0.33, 1)))

    # батуты: по одному перед каждым киоском (с крыши — билет), седьмой ещё и к крыше карусели. Подбрасывают вверх,
    # на крышу игрок доруливает в воздухе. Плита 2.2 м — бот «доходит» до узла в 1.6 м и в этот момент уже на батуте
    pads = {}
    for i in range(8):
        a = booth_angle(i)
        pos = (PAD_R[i] * math.cos(a), 0, PAD_R[i] * math.sin(a))
        if i not in PADS:   # перед киоском без билета на крыше — низкий ящик поперёк кольца вместо батута
            world.add(obj(f"PadCrate_{i}", pos=(pos[0], 0.35, pos[2]), rot=(0, -math.degrees(a), 0), scale=(1.0, 0.7, 2.4),
                          layer=LAYER_WORLD_WALL).prop(PROP_CUBE, collision=Collision.BOX, materials=[rust_mat.guid]))
            continue
        pad = world.add(obj(f"JumpPad_{i}", pos=pos).trigger(
            TriggerShape.BOX, size=(2.2, 1.5, 2.2), center=(0, 0.8, 0),
            on_enter=[act_change_velocity(PAD_SPEED, VelocityDir.UP, Op.SET)]))
        pad.add(obj("Plate", pos=(0, 0.1, 0), scale=(2.2, 0.2, 2.2))
                .prop(PROP_CUBE, collision=Collision.BOX, tint=(0.9, 0.2, 0.1, 1)))
        pads[i] = pad

    # карусель на самой большой пустой площадке: стойка, крыша и 4 лошадки вращаются вместе (Simple Animator),
    # билет внутри круга лошадок — надо проскочить между ними
    carousel = world.add(obj("Carousel", pos=CAROUSEL).simple_animator(anim_rotate_around_axis(0.12)))
    carousel.add(obj("Pole", pos=(0, CAROUSEL_ROOF_Y / 2, 0), scale=(0.25, CAROUSEL_ROOF_Y, 0.25), layer=LAYER_WORLD_WALL)
                 .prop(PROP_CUBE, collision=Collision.BOX, materials=[metal_mat.guid]))
    # крыша с коллизией Box (плоский верх ≈3.4 × 3.4 м на высоте ≈3.69): на неё запрыгивают с батута JumpPad_7
    carousel.add(obj("Roof", pos=(0, CAROUSEL_ROOF_Y, 0), scale=(0.17, 0.25, 0.17), layer=LAYER_WORLD_WALL)
                 .prop(roof_obj.guid, collision=Collision.BOX, materials=[paint_mat.guid]))
    for i in range(4):
        a = 2 * math.pi * i / 4
        carousel.add(obj(f"Horse_{i}", pos=(2.0 * math.cos(a), 0, 2.0 * math.sin(a)), rot=(0, -math.degrees(a), 0),
                         layer=LAYER_WORLD_WALL).prop(horse_obj.guid, collision=Collision.BOX, materials=[paint_mat.guid]))

    # --- декор на игровом поле
    decor = mod.add(obj("Decor"))
    # угловые сцены у респаунов: развалившийся киоск, бочки, обломки (спавнер билета — в Ticket Spawners)
    for i, (sx, sz) in enumerate(CORNERS):
        corner = decor.add(obj(f"Corner_{i}"))
        corner.add(obj("BrokenBooth", pos=(sx * 16.3, 0, sz * 13.2), rot=(0, rng2.uniform(0, 360), sx * sz * 9),
                       layer=LAYER_WORLD_WALL).prop(booth_obj.guid, collision=Collision.BOX, materials=[rust_mat.guid]))
        for k, (bx, bz) in enumerate(((13.6, 16.9), (14.5, 17.6), (12.7, 17.4))):
            corner.add(obj(f"Barrel_{k}", pos=(sx * bx, 0, sz * bz), rot=(0, rng2.uniform(0, 360), 0), layer=LAYER_WORLD_WALL)
                       .prop(barrel_obj.guid, collision=Collision.BOX, materials=[metal_mat.guid]))
        corner.add(obj("Debris", pos=(sx * 15.2, 0.2, sz * 15.0), rot=(rng2.uniform(0, 360), rng2.uniform(0, 360), 0))
                   .prop(debris_obj.guid, collision=Collision.NONE, tint=(0.5, 0.48, 0.45, 1)))
    # оси через центр: вагонетка сошла с рельсов на западной площадке, ящики у южного края пруда
    decor.add(obj("DerailedCart", pos=(-7.6, 0, -4.4), rot=(0, 75, 12), layer=LAYER_WORLD_WALL)
              .prop(cart_obj.guid, collision=Collision.BOX, materials=[metal_mat.guid]))
    decor.add(obj("Crates_Pond", pos=(-1.0, 0.35, -2.3), rot=(0, 4, 0), scale=(1.0, 0.7, 4.4), layer=LAYER_WORLD_WALL)
              .prop(PROP_CUBE, collision=Collision.BOX, materials=[rust_mat.guid]))
    for k, (bx, bz) in enumerate(((-7.4, 8.5), (-6.5, 9.3), (-5.0, 12.4))):   # кромки пруда: ряд z≈8 и колонка x≈−5
        decor.add(obj(f"Barrel_Pond_{k}", pos=(bx, 0, bz), rot=(0, rng2.uniform(0, 360), 0), layer=LAYER_WORLD_WALL)
                  .prop(barrel_obj.guid, collision=Collision.BOX, materials=[metal_mat.guid]))
    for k, (bx, bz) in enumerate(((8.4, -13.4), (9.3, -14.1))):   # колонка x≈8 от забора до Booth_1
        decor.add(obj(f"Barrel_Booth7_{k}", pos=(bx, 0, bz), rot=(0, rng2.uniform(0, 360), 0), layer=LAYER_WORLD_WALL)
                  .prop(barrel_obj.guid, collision=Collision.BOX, materials=[metal_mat.guid]))
    # низкие ящики поперёк коридора вдоль забора: ниже прыжка, рвут прямой пробег по периметру
    for i, t in enumerate(BARRIER_AT):
        d = HALF - 2.8   # ряд ящиков 5 м от забора до кольца фонарей
        for name, pos, rot in ((f"N{i}", (t, 0.35, d), (0, 0, 0)), (f"S{i}", (-t, 0.35, -d), (0, 0, 0)),
                               (f"E{i}", (d, 0.35, -t), (0, 90, 0)), (f"W{i}", (-d, 0.35, t), (0, 90, 0))):
            decor.add(obj(f"Crates_{name}", pos=pos, rot=(rot[0], rot[1] + rng2.uniform(-6, 6), 0), scale=(1.0, 0.7, 5.0),
                          layer=LAYER_WORLD_WALL).prop(PROP_CUBE, collision=Collision.BOX, materials=[rust_mat.guid]))
    for i in range(8):  # фонари между киосками, два покосились
        a = 2 * math.pi * i / 8
        tilt = (0, -math.degrees(a), 0) if i not in (2, 5) else (8, -math.degrees(a), -6)
        decor.add(obj(f"Lamppost_{i}", pos=(16 * math.cos(a), 0, 16 * math.sin(a)), rot=tilt, layer=LAYER_WORLD_WALL)
                  .prop(lamp_obj.guid, collision=Collision.BOX, materials=[metal_mat.guid]))
    for i in range(10):  # бочки кучками у киосков
        a = 2 * math.pi * (i % 8) / 8 + math.pi / 16 + rng.uniform(-0.25, 0.25)
        r = 12 + rng.uniform(2.2, 3.2)
        decor.add(obj(f"Barrel_{i}", pos=(r * math.cos(a), 0, r * math.sin(a)), rot=(0, rng.uniform(0, 360), 0), layer=LAYER_WORLD_WALL)
                  .prop(barrel_obj.guid, collision=Collision.BOX, materials=[metal_mat.guid]))
    for i in range(12):  # обломки
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(5, 18)
        decor.add(obj(f"Debris_{i}", pos=(r * math.cos(a), 0.2, r * math.sin(a)), rot=(rng.uniform(0, 360), rng.uniform(0, 360), 0),
                      scale=(rng.uniform(0.5, 1.2),) * 3).prop(debris_obj.guid, collision=Collision.NONE, tint=(0.5, 0.48, 0.45, 1)))
    # забор по периметру пола, секции по 3 м
    fence = decor.add(obj("Fence"))
    n = 13
    for i in range(n):
        t = -HALF + 1.5 + 3.0 * i
        for name, pos, rot in ((f"N_{i}", (t, 0, HALF - 0.5), (0, 0, 0)), (f"S_{i}", (t, 0, -HALF + 0.5), (0, 0, 0)),
                               (f"E_{i}", (HALF - 0.5, 0, t), (0, 90, 0)), (f"W_{i}", (-HALF + 0.5, 0, t), (0, 90, 0))):
            fence.add(obj(f"Fence_{name}", pos=pos, rot=rot, layer=LAYER_WORLD_WALL)
                      .prop(fence_obj.guid, collision=Collision.BOX, materials=[metal_mat.guid]))

    # --- задний план: земля без коллизии, холмы, деревья, руины горок, зона смерти под всем
    backdrop = mod.add(obj("Backdrop"))
    backdrop.add(obj("OuterGround", pos=(0, -0.6, 0), scale=(18, 1, 18))   # ниже воды (−0.3): иначе закрыла бы пруд в дыре пола
                 .prop(PROP_PLANE, collision=Collision.NONE, materials=[dirt_mat.guid]))
    backdrop.add(obj("FallVolume", pos=(0, -8, 0)).trigger(TriggerShape.BOX, size=(400, 4, 400),
                                                           on_enter=[act_kill(Targets.SOURCE)]))
    for i in range(12):
        a = 2 * math.pi * i / 12 + rng.uniform(-0.1, 0.1)
        r = rng.uniform(58, 72)
        s = rng.uniform(0.8, 1.6)
        backdrop.add(obj(f"Hill_{i}", pos=(r * math.cos(a), -0.2, r * math.sin(a)), rot=(0, rng.uniform(0, 360), 0),
                         scale=(s, s * rng.uniform(0.8, 1.4), s)).prop(hill_obj.guid, collision=Collision.NONE, materials=[dirt_mat.guid]))
    for i in range(16):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(26, 48)
        backdrop.add(obj(f"DeadTree_{i}", pos=(r * math.cos(a), -0.1, r * math.sin(a)), rot=(0, rng.uniform(0, 360), rng.uniform(-6, 6)),
                         scale=(rng.uniform(0.8, 1.4),) * 3).prop(tree_obj.guid, collision=Collision.NONE, tint=(0.35, 0.28, 0.2, 1)))
    coaster = backdrop.add(obj("RuinedCoaster", pos=(0, -0.1, -40)))
    for i in range(7):  # опоры в ряд за колесом, рельсы сверху, в середине пролёт обрушен
        x = -18 + 6 * i
        coaster.add(obj(f"Trestle_{i}", pos=(x, 0, 0)).prop(trestle_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
        if i < 6 and i != 3:
            coaster.add(obj(f"Rail_{i}", pos=(x + 3, 10.3, 0), rot=(0, 90, 0))
                        .prop(rail_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))
    coaster.add(obj("FallenRail", pos=(3, 1.2, 2), rot=(25, 70, 0)).prop(rail_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid]))

    # --- спавны
    spawns = mod.add(obj("Player Spawnpoints"))
    # shared=True: необщий спавн после первого игрока выбывает из списка (ModPlayerSpawn.DetermineInitialSpawnPoints),
    # и валидатор требует 8 необщих или хотя бы один общий. Кольцо ставит N игроков через 1/N круга от +X лицом к центру
    spawns.add(obj("Spawn_Ring", pos=(0, 1, 0)).player_spawn(SpawnShape.CIRCLE, SpawnUsage.INITIAL, radius=15, shared=True))
    for i, (x, z) in enumerate(((17, 17), (-17, 17), (17, -17), (-17, -17))):
        spawns.add(obj(f"Respawn_{i}", pos=(x, 1, z)).player_spawn(SpawnShape.POINT, SpawnUsage.RESPAWN))

    # --- билеты: 3 на 4 крышах киосков, 2 у карусели (внутри круга лошадок и на крыше), 3 в 12 случайных точках пола
    spawners = mod.add(obj("Ticket Spawners"))
    specials = []   # особые узлы сетки ботов: точка каждого билета, батуты, крыши

    def ticket_spawner(name, pos, item=ticket_item, delay=TICKET_DELAY, active=True, **kw):
        kw.setdefault("location", SpawnerLocation.ON_SPAWNER)
        return spawners.add(obj(name, pos=pos, active=active).spawner(
            [item.guid], interval=(1.0, None), delay=delay, kind=SpawnerType.ON_DESTRUCTION, **kw))

    roof_targets = spawners.add(obj("Roof_Points"))
    roof_objs = []
    for i in ROOF_TICKETS:
        a, r = booth_angle(i), 12.3   # центр крыши (козырёк смещает габарит киоска наружу)
        roof = (r * math.cos(a), BOOTH_TOP + 0.6, r * math.sin(a))
        roof_objs.append(roof_targets.add(obj(f"Roof_{i}", pos=roof)))
        specials += [{"name": f"Nav_Pad_{i}", "pos": (pads[i].pos[0], 0.5, pads[i].pos[2]), "kind": "pad"},
                     {"name": f"Nav_Roof_{i}", "pos": (roof[0], BOOTH_TOP + 0.5, roof[2]), "kind": "roof", "pad": f"Nav_Pad_{i}"}]
    ticket_spawner("Roofs", (0, BOOTH_TOP + 0.6, 0), location=SpawnerLocation.ON_TARGETS,
                   spawn_points=[p.transform_guid for p in roof_objs], count=ROOF_COUNT)
    # батут 7 ведёт ещё и на крышу карусели — его узел нужен, даже если на киоске 7 билета нет
    if 7 not in ROOF_TICKETS:
        specials.append({"name": "Nav_Pad_7", "pos": (pads[7].pos[0], 0.5, pads[7].pos[2]), "kind": "pad"})
    inner = (CAROUSEL[0] + 1.0, 0.6, CAROUSEL[2])
    ticket_spawner("Carousel_Inner", inner)
    top = (CAROUSEL[0], CAROUSEL_ROOF_Y + 4.35 * 0.25 + 0.6, CAROUSEL[2])   # над осью: точка на вращающейся крыше не движется
    ticket_spawner("Carousel_Roof", top)
    specials += [{"name": "Nav_CarouselInner", "pos": (inner[0], 0.5, inner[2]), "kind": "ground"},
                 {"name": "Nav_CarouselRoof", "pos": (top[0], top[1] - 0.1, top[2]), "kind": "roof", "pad": "Nav_Pad_7"}]
    # случайные: один спавнер держит RANDOM_COUNT билетов, каждый раз в свободной из 12 точек (ModSpawner.Spawn)
    points = [(sx * 15.0, sz * 15.6) for sx, sz in CORNERS]                                   # угловые сцены
    points += [(10.5, 0.0), (0.0, 10.5), (-10.5, 0.0), (0.0, -10.5)]                          # между батутами
    points += [(14.5 * math.cos(math.radians(33.75 + 90 * k)), 14.5 * math.sin(math.radians(33.75 + 90 * k)))
               for k in range(4)]                                                             # за киосками
    targets = spawners.add(obj("Random_Points"))
    point_objs = [targets.add(obj(f"Point_{k}", pos=(x, 0.6, z))) for k, (x, z) in enumerate(points)]
    ticket_spawner("Random", (0, 0.6, 0), location=SpawnerLocation.ON_TARGETS,
                   spawn_points=[p.transform_guid for p in point_objs], count=RANDOM_COUNT)
    specials += [{"name": f"Nav_Point_{k}", "pos": (x, 0.5, z), "kind": "ground"} for k, (x, z) in enumerate(points)]
    # большой билет: спавнер выключен до JACKPOT_AT. Spawn On Destruction в первом же Update после включения ставит
    # предмет сразу (m_lastAliveTimes = MinValue, ModSpawner.DoSpawn), дальше — через JACKPOT_DELAY после подбора
    jp_targets = spawners.add(obj("Jackpot_Points"))
    jp_objs = [jp_targets.add(obj(f"Point_{k}", pos=(x, 0.6, z))) for k, (x, z) in enumerate(JACKPOT_POINTS)]
    jackpot = ticket_spawner("Jackpot", (0, 0.6, -1.0), item=jackpot_item, delay=JACKPOT_DELAY, active=False,
                             location=SpawnerLocation.ON_TARGETS, spawn_points=[p.transform_guid for p in jp_objs], count=1)
    specials += [{"name": f"Nav_Jackpot_{k}", "pos": (x, 0.5, z), "kind": "ground"} for k, (x, z) in enumerate(JACKPOT_POINTS)]

    mod.add(obj("Director").logic(trig_round_start(
        act_show_message("Собери билеты! / Grab the tickets!", 3.0),
        act_wait(JACKPOT_AT),
        act_set_active(ActiveState.ENABLED, [jackpot.transform_guid]),
        act_play_sound(pickup_wav.guid, 1.0, Targets.RECEIVER),
        act_show_message(f"Большой билет у пруда: +{JACKPOT_VALUE}! / Jackpot by the pond: +{JACKPOT_VALUE}!", 3.0))))
    mod.add(obj("Notes").note("Сгенерировано build_mod.py из packs/abandoned-park/minigames/tickets/DESIGN.md"))
    out = mod.write(workshop)

    # --- превью для окна Load a saved mod: план сверху по первому проходу (сетка ботов на нём не рисуется)
    os.makedirs(os.path.join(HERE, "plan"), exist_ok=True)
    mod.preview_image = os.path.join(HERE, "plan", "preview.png")
    plan_view.render_preview(out, mod.preview_image)

    # --- сетка ботов: второй проход по записанной сцене (карта занятости plan_view), затем запись ещё раз
    nodes, edges, warnings = navgen.generate(out, specials)
    nav = mod.add(obj("AI Navigation"))
    node_objs = [nav.add(obj(name, pos=pos).ai_node()) for name, pos in nodes]
    link_ai_nodes(node_objs, edges)
    for w in warnings:
        print("сетка ботов:", w)
    print(f"сетка ботов: {len(nodes)} узлов, {len(edges)} связей")
    return mod.write(workshop)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = build(sys.argv[1] if len(sys.argv) > 1 else "Ticket Rush", sys.argv[2] if len(sys.argv) > 2 else WORKSHOP)
    print("written:", out)
