"""Build Ferris Hold; optional arguments: mod name, WorkshopMods directory."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reserve_common import *


def build(name='Ferris Hold', workshop=WORKSHOP):
    mod = base(name, 'Ferris Hold / Колесо: board a gondola, stay above the yellow line to earn points. Falls respawn.')
    pond(mod, 50, 40)
    cube(mod, 'BoardingDeck', (0, -.4, 0), (21,.8,10), TEAL, ground=True)
    spawn(mod, (0,1,3.2), 2.8, line=True)
    scenery(mod,19,16)
    for x in (-4,4):
        cube(mod,'WheelStand',(x,4,-2.5),(.7,9,.7),RUST,solid=False,rot=(0,0,25 if x<0 else -25))
    # Equal and opposite rotations keep each gondola floor horizontal.
    wheel = mod.add(obj('Wheel', pos=(0,8,0)).simple_animator(anim_rotate_around_axis(1/24, (0,0,1))))
    for i in range(8):
        a=math.tau*i/8
        cube(wheel,'Spoke',(3.65*math.cos(a),3.65*math.sin(a),-2),
             (7.3,.2,.2),RUST,solid=False,rot=(0,0,math.degrees(a)))
        gondola=wheel.add(obj(f'Gondola_{i}', pos=(7.3*math.cos(a),7.3*math.sin(a),0))
            .simple_animator(anim_rotate_around_axis(1/24,(0,0,-1))))
        cube(gondola,'GondolaFloor',(0,-.2,0),(4.2,.4,3.6),YELLOW if i%2 else RED,ground=True)
        # Front is open for boarding; low rear lip reads as a cabin, not a sealed box.
        cube(gondola,'RearLip',(0,.25,-1.7),(4.2,.5,.2),RUST)
    mod.add(obj('UpperScoreZone',pos=(0,14,0)).trigger(size=(21,8,4),
        on_stay=[act_change_score(1)],stay_interval=1))
    cube(mod,'ScoreLine',(0,10,-2.3),(22,.15,.15),YELLOW,solid=False)
    nav_line(mod,[(-6,.2,2),(-3,.2,2),(0,.2,2),(3,.2,2),(6,.2,2)])
    return finish(mod, __file__, name, workshop)


if __name__ == '__main__':
    cli(build, 'Ferris Hold')
