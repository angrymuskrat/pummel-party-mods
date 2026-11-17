"""Small scene helpers shared by the five reserve prototypes (stdlib only)."""
import copy
import contextlib
import io
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from pmgen import *

WORKSHOP = r'%USERPROFILE%\AppData\LocalLow\Rebuilt Games\Pummel Party\WorkshopMods'
RUST = (.55, .24, .12, 1)
RED = (.75, .15, .12, 1)
YELLOW = (.95, .75, .15, 1)
TEAL = (.15, .55, .5, 1)


def cube(parent, name, pos, size, color=RUST, ground=False, solid=True, rot=(0, 0, 0)):
    return parent.add(obj(name, pos=pos, scale=size, rot=rot,
                          layer=LAYER_WORLD_GROUND if ground else LAYER_DEFAULT)
                      .prop(PROP_CUBE, tint=color, collision=Collision.BOX if solid else Collision.NONE))


def base(name, description, survival=False, race=False):
    return Mod(name, description=description, round_duration=60,
               placement=Placement.LAST_MAN_STANDING if survival else Placement.FINISH_ORDER if race else Placement.MOST_POINTS,
               end_conditions=EndCondition.TIMER | (EndCondition.REMAINING_ALIVE if survival else EndCondition.FINISH if race else 0),
               settings_overrides={'respawnEnabled': not survival, 'respawnTime': 1.5,
                                   'respawnInvulnerableTime': 1.0, 'useHealth': False,
                                   'canPunch': True, 'punchDamage': 0, 'punchStunsTarget': False,
                                   'movementSpeed': 6.0, 'playerGravity': 25.0, 'jumpSpeed': 7.0,
                                   'weaponHitTrigger': {'m_type': 80, 'm_actions': [], 'm_hitType': 1}},
               player_triggers={'weaponHitTrigger': [
                   act_change_velocity(5, VelocityDir.TOWARDS_RECEIVER, Op.ADD, flags=Targets.RECEIVER),
                   act_change_velocity(3, VelocityDir.UP, Op.ADD, flags=Targets.RECEIVER)]})


def pond(mod, width=50, depth=50, z=0):
    mod.add(obj('Acid', pos=(0, -2, z)).water(width=int(width / 2), height=int(depth / 2), cell=2,
            deep=(.1, .3, .03, 1), shallow=(.4, .8, .1, 1)))
    mod.add(obj('Fall', pos=(0, -2.4, z)).trigger(size=(width, 1, depth), on_enter=[act_kill()]))
    cube(mod, 'SafetyBed', (0, -3.5, z), (width, 1, depth), (.12, .2, .1, 1))


def spawn(mod, pos=(0, 1, 0), radius=5, line=False):
    mod.add(obj('Player Spawnpoints', pos=pos).player_spawn(
        shape=SpawnShape.LINE if line else SpawnShape.CIRCLE, radius=radius, line_length=radius * 2))


def nav_line(mod, positions, goal=False):
    nodes = [mod.add(obj(f'Nav_{i}', pos=p).ai_node(is_goal=goal and i == len(positions)-1))
             for i, p in enumerate(positions)]
    link_ai_nodes(nodes, [(i, i+1) for i in range(len(nodes)-1)] + [(i+1, i) for i in range(len(nodes)-1)])


def rifle(mod):
    visual = mod.add_prefab(obj('GalleryRifle').prop(PROP_SNIPER, collision=Collision.NONE))
    info = copy.deepcopy(DEFAULT_WEAPON_INFO)
    info.update(weaponHitType=0, spawnBulletEffect=True, spawnTrailEffect=True, fireSound=1, stunOnHit=False)
    info['basicInfo'] = {'cooldown': .6, 'damage': 0}
    info['scanInfo'].update(weaponSpreadType=0, shotCount=1, range=45.0, hitOnce=True)
    item = mod.add_prefab(obj('GalleryRifleItem').item(ItemType.WEAPON, visual.guid,
        weapon_type=WeaponUsage.GUN, weapon_info=info, cooldown=.6, can_drop=False,
        disappear_when_dropped=True, slot=ItemSlot.RIGHT_HAND))
    give = [act_give_minigame_item(item.guid)]
    mod.player_triggers.update(onFirstSpawnTrigger=give, onRespawnTrigger=give)


def target(parent, name, pos, points=1, delay=3, color=YELLOW, radius=.65):
    t = parent.add(obj(name, pos=pos))
    t.trigger(TriggerShape.SPHERE, radius=radius, disable_after=True, on_hit=[
        act_change_score(points), act_spawn_effect(Effect.CONFETTI, Targets.RECEIVER),
        act_wait(delay), act_set_active(targets=[t.transform_guid])])
    t.add(obj('Balloon', scale=(radius*2,)*3).prop(PROP_SPHERE, tint=color, collision=Collision.NONE))
    return t


def finish(mod, here, name, workshop,output_dir=None):
    mod.add(obj('Prototype notes').note('Reserve prototype. Validate locally, then playtest with 4/6/8 players and 1-2 bots.'))
    path = mod.write(workshop)
    sys.path.insert(0, str(ROOT / '.claude/skills/pummel-party-level-design/scripts'))
    import plan_view
    out = (Path(output_dir) if output_dir else Path(here).resolve().parent) / 'plan'
    with contextlib.redirect_stdout(io.StringIO()):
        plan_view.main([path, '--out', str(out), '--px', '800'])
    plan_view.render_preview(path, str(out / 'preview.png'))
    if Path(here).parent.name == 'ferris-hold':
        # Generic analysis takes the highest floor as ground; retain that report,
        # but also render the complete wheel from the boarding-deck datum.
        things = plan_view.collect(P.load(str(Path(path)/'Data/MainScene.scene')), plan_view.ModFiles(path))
        mg, ps = plan_view.read_settings(path)
        analysis = plan_view.analyse(things, mg, ps, 4)
        analysis['floor_y'] = 0
        for facing in ('north', 'south'):
            plan_view.draw_elevation(things, analysis, str(out/f'elevation_boarding_{facing}.png'), 14, facing=facing)
    mod.preview_image = str(out / 'preview.png')
    return mod.write(workshop)


def scenery(mod, half_x=16, half_z=16, center_z=0):
    """Existing generated park models; backdrop has no collision with gameplay."""
    models = ROOT / 'packs/abandoned-park/assets/models'
    assets = {n: mod.add_file_asset('prop', str(models / (n+'.obj'))).guid
              for n in ('hill', 'dead_tree')}
    back = mod.add(obj('Backdrop'))
    for side in (-1,1):
        for i in range(7):
            x = -half_x + 2*half_x*i/6
            z = -half_z + 2*half_z*i/6
            for px,pz in ((x,side*half_z),(side*half_x,z)):
                back.add(obj(f'Hill_{side}_{i}_{px}',pos=(px,-2,center_z+pz),scale=(.25,1,.25))
                         .prop(assets['hill'],tint=(.24,.3,.15,1),collision=Collision.NONE))
        for i in range(5):
            z=center_z-half_z+2*half_z*i/4
            back.add(obj(f'Tree_{side}_{i}',pos=(side*(half_x-2),0,z),rot=(0,i*31,5))
                     .prop(assets['dead_tree'],tint=RUST,collision=Collision.NONE))
    # A tall striped signal tower and its slowly rotating cross are visible above the hills.
    tower=mod.add(obj('SignalTower',pos=(-half_x+2,0,center_z+half_z-2)))
    cube(tower,'Mast',(0,5,0),(1,10,1),RUST,solid=False)
    rotor=tower.add(obj('WindSign',pos=(0,10,0)).mover(rotation_axis_type=MoverAxis.Z,rotation_speed=24))
    cube(rotor,'SignA',(0,0,0),(5,.4,.3),YELLOW,solid=False)
    cube(rotor,'SignB',(0,0,0),(.4,5,.3),RED,solid=False)
    return assets


def cli(build, name):
    print(build(sys.argv[1] if len(sys.argv)>1 else name, sys.argv[2] if len(sys.argv)>2 else WORKSHOP))
