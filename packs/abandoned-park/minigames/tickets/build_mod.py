"""Собирает мод Ticket Rush по DESIGN.md в папку WorkshopMods редактора.

Запуск из корня репозитория:  python packs/abandoned-park/minigames/tickets/build_mod.py [имя мода]
По умолчанию пишет «Ticket Rush Gen», чтобы не трогать мод, собранный руками.
"""
import math
import os
import random
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from pmgen import *  # noqa: E402,F403

ASSETS = os.path.join(ROOT, "packs", "abandoned-park", "assets")
WORKSHOP = r"%USERPROFILE%\AppData\LocalLow\Rebuilt Games\Pummel Party\WorkshopMods"
HALF = 20.0  # игровой пол 40×40


def build(name: str) -> str:
    rng = random.Random("ticket-rush")
    mod = Mod(name, description="Rusted Park: collect tickets in the ruined fairground. / Билетики: собери больше всех билетов.",
              round_duration=60, end_conditions=EndCondition.TIMER, placement=Placement.MOST_POINTS,
              settings_overrides={"respawnEnabled": True, "respawnTime": 3.0, "respawnInvulnerableTime": 2.0,
                                  "canPunch": True, "useHealth": False})

    # --- ассеты
    def prop(fn): return mod.add_file_asset("prop", os.path.join(ASSETS, "models", fn))
    def tex(fn): return mod.add_file_asset("texture", os.path.join(ASSETS, "textures", fn))
    ticket_obj, booth_obj, wheel_obj = prop("ticket.obj"), prop("booth.obj"), prop("ferris_wheel.obj")
    lamp_obj, fence_obj, barrel_obj = prop("lamppost.obj"), prop("fence_segment.obj"), prop("barrel.obj")
    tree_obj, hill_obj, trestle_obj = prop("dead_tree.obj"), prop("hill.obj"), prop("coaster_trestle.obj")
    rail_obj, debris_obj = prop("rail_segment.obj"), prop("debris.obj")
    pickup_wav = mod.add_file_asset("audio", os.path.join(ASSETS, "audio", "ticket_pickup.wav"))
    rust_mat = mod.add_material("RustBooth", tex("rust_booth.png"), tiling=(2.0, 2.0))
    concrete_mat = mod.add_material("Concrete", tex("concrete.png"), tiling=(8.0, 8.0))
    metal_mat = mod.add_material("RustMetal", tex("rust_metal.png"), tiling=(1.0, 1.0))
    dirt_mat = mod.add_material("Dirt", tex("dirt.png"), tiling=(20.0, 20.0))

    # --- префабы билета: визуал (вертикально, с наклоном 15°) и предмет
    ticket_visual = mod.add_prefab(obj("Ticket Visual", pos=(0, 0.15, 0), rot=(90, 0, 15))
                                   .prop(ticket_obj.guid, collision=Collision.NONE, tint=(1.0, 0.85, 0.3, 1)))
    ticket_item = mod.add_prefab(obj("Ticket Item").item(
        ItemType.PICKUP, visual_prefab_guid=ticket_visual.guid,
        on_pickup=[act_change_score(1, Op.ADD, Targets.SOURCE),
                   act_spawn_effect(Effect.SPARKLES, Targets.RECEIVER),
                   act_play_sound(pickup_wav.guid, 0.8, Targets.RECEIVER)],
        can_drop=False, disappear_when_dropped=True, auto_drop=True, drop_after=0.0))

    # --- игровой пол и киоски
    world = mod.add(obj("World"))
    world.add(obj("Ground", scale=(4, 1, 4), layer=LAYER_WORLD_GROUND)
              .prop(PROP_PLANE, collision=Collision.MESH, materials=[concrete_mat.guid]))
    for i in range(8):
        a = 2 * math.pi * i / 8 + math.pi / 16
        world.add(obj(f"Booth_{i}", pos=(12 * math.cos(a), 0, 12 * math.sin(a)), rot=(0, -math.degrees(a) + 90, 0),
                      layer=LAYER_WORLD_WALL).prop(booth_obj.guid, collision=Collision.BOX, materials=[rust_mat.guid]))

    # колесо обозрения: стоит на полу у дальнего края, крутится вокруг мировой оси Z
    world.add(obj("FerrisWheel", pos=(0, 7.25, -17))
              .prop(wheel_obj.guid, collision=Collision.NONE, materials=[metal_mat.guid])
              .mover(MoverDir.CUSTOM, (0, 0, 0), 0.0, MoverAxis.Z, (0, 0, 1), 10.0))

    # пруд и зона смерти
    pond = world.add(obj("Pond", pos=(-4, -0.3, 0)).water(width=8, height=8, cell=1.0,
                                                           deep=(0.12, 0.45, 0.08, 0.8), shallow=(0.45, 1.0, 0.2, 0.8), froth=(0.8, 1.0, 0.6, 1)))
    pond.add(obj("KillVolume", pos=(4, -0.6, 4)).trigger(
        TriggerShape.BOX, size=(8, 1, 8),
        on_enter=[act_spawn_effect(Effect.EXPLOSION, Targets.SOURCE), act_kill(Targets.SOURCE)]))

    # jump pad
    for i, (x, z) in enumerate(((0, 9), (0, -9), (9, 0), (-9, 0))):
        world.add(obj(f"JumpPad_{i}", pos=(x, 0.1, z)).prop(PROP_CUBE, collision=Collision.BOX, tint=(0.9, 0.2, 0.1, 1))
                  .trigger(TriggerShape.BOX, size=(1.2, 1.5, 1.2), center=(0, 0.8, 0),
                           on_enter=[act_change_velocity(14.0, VelocityDir.UP, Op.SET)]))

    # --- декор на игровом поле
    decor = mod.add(obj("Decor"))
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
    backdrop.add(obj("OuterGround", pos=(0, -0.15, 0), scale=(18, 1, 18))
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
    spawns.add(obj("Spawn_Ring", pos=(0, 1, 0)).player_spawn(SpawnShape.CIRCLE, SpawnUsage.INITIAL, radius=15, shared=False))
    for i, (x, z) in enumerate(((17, 17), (-17, 17), (17, -17), (-17, -17))):
        spawns.add(obj(f"Respawn_{i}", pos=(x, 1, z)).player_spawn(SpawnShape.POINT, SpawnUsage.RESPAWN))

    # --- спавнеры билетов
    spawners = mod.add(obj("Ticket Spawners"))
    for i in range(12):
        a = 2 * math.pi * i / 12
        r = 7.0 if i % 2 else 15.0
        spawners.add(obj(f"TicketSpawner_{i}", pos=(r * math.cos(a), 0.6, r * math.sin(a))).spawner(
            [ticket_item.guid], interval=(1.0, None), delay=(4.0, 8.0), kind=SpawnerType.ON_DESTRUCTION,
            location=SpawnerLocation.ON_SPAWNER, count=1))

    mod.add(obj("Director").logic(trig_round_start(act_show_message("Собери билеты! / Grab the tickets!", 3.0))))
    mod.add(obj("Notes").note("Сгенерировано build_mod.py из packs/abandoned-park/minigames/tickets/DESIGN.md"))
    return mod.write(WORKSHOP)


if __name__ == "__main__":
    out = build(sys.argv[1] if len(sys.argv) > 1 else "Ticket Rush Gen")
    print("written:", out)
