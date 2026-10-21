"""Собирает мод Ticket Rush по DESIGN.md в папку WorkshopMods редактора.

Запуск из корня репозитория:  python packs/abandoned-park/minigames/tickets/build_mod.py [имя мода]
По умолчанию пишет «Ticket Rush Gen», чтобы не трогать мод, собранный руками.
"""
import math
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from pmgen import *  # noqa: E402,F403

ASSETS = os.path.join(ROOT, "packs", "abandoned-park", "assets")
WORKSHOP = r"%USERPROFILE%\AppData\LocalLow\Rebuilt Games\Pummel Party\WorkshopMods"


def build(name: str) -> str:
    mod = Mod(name, description="Rusted Park: collect tickets in the ruined fairground. / Билетики: собери больше всех билетов.",
              round_duration=60, end_conditions=EndCondition.TIMER, placement=Placement.MOST_POINTS,
              settings_overrides={"respawnEnabled": True, "respawnTime": 3.0, "respawnInvulnerableTime": 2.0,
                                  "canPunch": True, "useHealth": False})

    # --- ассеты
    ticket_obj = mod.add_file_asset("prop", os.path.join(ASSETS, "models", "ticket.obj"))
    booth_obj = mod.add_file_asset("prop", os.path.join(ASSETS, "models", "booth.obj"))
    wheel_obj = mod.add_file_asset("prop", os.path.join(ASSETS, "models", "ferris_wheel.obj"))
    rust_tex = mod.add_file_asset("texture", os.path.join(ASSETS, "textures", "rust_booth.png"))
    concrete_tex = mod.add_file_asset("texture", os.path.join(ASSETS, "textures", "concrete.png"))
    pickup_wav = mod.add_file_asset("audio", os.path.join(ASSETS, "audio", "ticket_pickup.wav"))
    rust_mat = mod.add_material("RustBooth", rust_tex, tiling=(2.0, 2.0))
    concrete_mat = mod.add_material("Concrete", concrete_tex, tiling=(8.0, 8.0))

    # --- префабы билета: визуал и предмет
    ticket_visual = mod.add_prefab(obj("Ticket Visual").prop(ticket_obj.guid, collision=Collision.NONE, tint=(1.0, 0.85, 0.3, 1)))
    ticket_item = mod.add_prefab(obj("Ticket Item").item(
        ItemType.PICKUP, visual_prefab_guid=ticket_visual.guid,
        on_pickup=[act_change_score(1, Op.ADD, Targets.SOURCE),
                   act_spawn_effect(Effect.SPARKLES, Targets.RECEIVER),
                   act_play_sound(pickup_wav.guid, 0.8, Targets.RECEIVER)],
        can_drop=False, disappear_when_dropped=True, auto_drop=True, drop_after=0.0))

    # --- мир
    world = mod.add(obj("World"))
    world.add(obj("Ground", pos=(0, 0, 0), scale=(4, 1, 4), layer=LAYER_WORLD_GROUND)
              .prop(PROP_PLANE, collision=Collision.MESH, materials=[concrete_mat.guid]))
    for i in range(8):
        a = 2 * math.pi * i / 8 + math.pi / 16
        r = 12.0
        world.add(obj(f"Booth_{i}", pos=(r * math.cos(a), 0, r * math.sin(a)), rot=(0, -math.degrees(a) + 90, 0),
                      layer=LAYER_WORLD_WALL).prop(booth_obj.guid, collision=Collision.BOX, materials=[rust_mat.guid]))
    world.add(obj("FerrisWheel", pos=(0, 7.5, -26), rot=(0, 0, 0))
              .prop(wheel_obj.guid, collision=Collision.NONE, tint=(0.55, 0.3, 0.15, 1))
              .mover(direction_type=4, direction=(0, 0, 0), speed=0.0, rotation_axis_type=1, rotation_axis=(0, 0, 1), rotation_speed=10.0))

    pond = world.add(obj("Pond", pos=(-4, -0.3, 0)).water(width=8, height=8, cell=1.0,
                                                           deep=(0.12, 0.45, 0.08, 0.8), shallow=(0.45, 1.0, 0.2, 0.8), froth=(0.8, 1.0, 0.6, 1)))
    pond.add(obj("KillVolume", pos=(4, -0.6, 4)).trigger(
        TriggerShape.BOX, size=(8, 1, 8),
        on_enter=[act_spawn_effect(Effect.EXPLOSION, Targets.SOURCE), act_kill(Targets.SOURCE)]))
    world.add(obj("PondRim", pos=(0, -0.4, 0), scale=(0.9, 0.4, 0.9), layer=LAYER_WORLD_GROUND)
              .prop(PROP_PLANE, collision=Collision.MESH, tint=(0.3, 0.3, 0.28, 1), enabled=False))

    for i, (x, z) in enumerate(((0, 9), (0, -9), (9, 0), (-9, 0))):
        world.add(obj(f"JumpPad_{i}", pos=(x, 0.1, z)).prop(PROP_CUBE, collision=Collision.BOX, tint=(0.9, 0.2, 0.1, 1))
                  .trigger(TriggerShape.BOX, size=(1.2, 1.5, 1.2), center=(0, 0.8, 0),
                           on_enter=[act_change_velocity(14.0, VelocityDir.UP, Op.SET)]))

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
