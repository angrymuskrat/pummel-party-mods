"""Build Rusty Teacups; optional arguments: mod name, WorkshopMods directory."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reserve_common import *


def build(name='Rusty Teacups', workshop=WORKSHOP):
    mod=base(name, 'Rusty Teacups / Чашки: shoot gold targets from spinning cups; fall and respawn. Most points wins.')
    mod.settings_overrides['weaponHitTrigger']['m_hitType']=WeaponHitKind.PROJECTILE
    rifle(mod)
    pond(mod,55,55)
    scenery(mod,22,22)
    # Every start and respawn is on a cup, so shooting always involves a moving floor.
    for i,(x,z) in enumerate(((-6,0),(6,0),(0,-6),(0,6))):
        cup=mod.add(obj(f'Cup_{i}',pos=(x,0,z)).simple_animator(
            anim_rotate_around_axis((1 if i%2 else -1)/(9.5+i*1.3))))
        cube(cup,'CupFloor',(0,-.35,0),(5,.7,5),RED if i%2 else YELLOW,ground=True)
        for dx in (-2.3,2.3):
            cube(cup,'CupRim',(dx,.3,0),(.3,.6,5),TEAL)
        # Open handle silhouette, behind the low rim, with no hidden collision.
        for dz in (-1,1):
            cube(cup,'HandleLink',(2.8,.4,dz),(1,.25,.25),RUST,solid=False)
        cube(cup,'HandleOuter',(3.3,.4,0),(.25,.25,2),RUST,solid=False)
        for dz in (-.8,.8):
            mod.add(obj(f'Start_{i}_{dz}',pos=(x,1,z+dz)).player_spawn(shared=False,usage=SpawnUsage.INITIAL))
        mod.add(obj(f'Respawn_{i}',pos=(x,1,z)).player_spawn(usage=SpawnUsage.RESPAWN))
    for i in range(12):
        a=math.tau*i/12
        target(mod,f'TinTarget_{i}',(12*math.cos(a),2,12*math.sin(a)),points=2,delay=4.5,
               color=YELLOW,radius=.75)
    return finish(mod, __file__, name, workshop)


if __name__ == '__main__':
    cli(build, 'Rusty Teacups')
