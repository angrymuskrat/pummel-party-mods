"""Build Barrel Alley; optional arguments: mod name, WorkshopMods directory."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reserve_common import *


def build(name='Barrel Alley', workshop=WORKSHOP):
    mod = base(name, 'Barrel Alley / Бочковой подъём: run uphill, dodge rolling barrels, reach the arch first.', race=True)
    angle = -math.degrees(math.atan2(6, 48))
    cube(mod, 'Uphill', (0, 2.7, 24), (14, .6, math.hypot(48,6)), TEAL, ground=True, rot=(angle,0,0))
    spawn(mod, (0, 1.1, 2), 5, line=True)
    scenery(mod,20,35,24)
    for z in range(4,48,4):
        for x in (-2.25,2.25):
            cube(mod,'LaneDash',(x,z/8+.025,z),(.12,.04,1),YELLOW,solid=False,rot=(angle,0,0))
    for x in (-7,7):
        cube(mod,'FinishPost',(x,9,45),(.7,6,.7),RED,solid=False)
    cube(mod,'FinishArch',(0,12,45),(15,.7,.7),YELLOW,solid=False)
    for x in (-7,7):
        cube(mod, 'SideRail', (x, 3.7, 24), (.4, 2, math.hypot(48,6)), RUST, rot=(angle,0,0))
    for z in (10,20,30,40):
        mod.add(obj(f'Progress_{z}', pos=(0,z/8+1,z)).trigger(size=(14,3,.4),
            on_enter=[act_change_score(1)], one_use_per_player=True))
    mod.add(obj('Finish', pos=(0,6.6,45)).trigger(size=(14,3,1),
        on_enter=[act_set_placement()], one_use_per_player=True))
    barrel = obj('RollingBarrel').mover(direction=(0,-.125,-1), speed=6)
    barrel.add(obj('Contact').trigger(TriggerShape.SPHERE, radius=.85, on_enter=[act_stun(1),
        act_change_velocity(7, VelocityDir.CUSTOM, Op.SET, custom=(0,.25,-1))]))
    barrel.logic(trig_enable(act_wait(9), act_kill(Targets.RECEIVER)))
    barrel_mesh=mod.add_file_asset('prop',str(ROOT/'packs/abandoned-park/assets/models/barrel.obj'))
    barrel.add(obj('Barrel', pos=(.8,0,0), rot=(0,0,90), scale=(1.6,)*3).prop(barrel_mesh.guid, tint=RUST, collision=Collision.NONE)
               .mover(rotation_axis_type=MoverAxis.X, rotation_speed=180))
    prefab = mod.add_prefab(barrel)
    # Nine possible tracks cover the full width: no permanent safe strip between three fixed tracks.
    points = [mod.add(obj(f'BarrelLane_{x}', pos=(x,6.8,47))) for x in (-6,-4.5,-3,-1.5,0,1.5,3,4.5,6)]
    sp = mod.add(obj('BarrelSpawner', active=False).spawner([prefab.guid], interval=(.65,1.05),
        location=SpawnerLocation.ON_TARGETS, spawn_points=[p.transform_guid for p in points]))
    mod.add(obj('Director').logic(trig_round_start(act_wait(1), act_set_active(targets=[sp.transform_guid]))))
    nav_line(mod, [(0,z/8+.2,z) for z in range(2,47,4)], goal=True)
    pond(mod, 45, 80, 24)
    return finish(mod, __file__, name, workshop)


if __name__ == '__main__':
    cli(build, 'Barrel Alley')
