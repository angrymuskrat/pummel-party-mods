"""Build Balloon Pop; optional arguments: mod name, WorkshopMods directory."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reserve_common import *


def build(name='Balloon Pop', workshop=WORKSHOP,decorate=None,output_dir=None):
    mod = base(name, 'Balloon Pop / Шарики: punch balloons. Gold is worth three points. Most points in 60 seconds wins.')
    cube(mod, 'Fairground', (0, -.5, 0), (22, 1, 22), TEAL, ground=True)
    spawn(mod, radius=8.5)
    scenery(mod,18,18)
    for x in (-10,10):
        for z in (-10,10):
            cube(mod,'PrizeStall',(x,1.1,z),(2,2.2,2),RED)
            cube(mod,'StallRoof',(x,2.3,z),(2.5,.2,2.5),YELLOW,solid=False)
    for i in range(8):
        a = math.tau*i/8
        p = (5.8*math.cos(a), 1.1, 5.8*math.sin(a))
        cube(mod,'TargetMark',(p[0],.02,p[2]),(1.5,.04,1.5),YELLOW,solid=False)
        t = target(mod, f'Balloon_{i}', p, delay=3.5, color=RED if i%2 else YELLOW)
        t.simple_animator(anim_move_along_line(1/(3.1+i*.17), (0, .35, 0)))
    gold = target(mod, 'GoldBalloon', (0, 1.1, 0), points=3, delay=6, color=YELLOW)
    gold.simple_animator(anim_move_along_line(1/5.3, (2, 0, 0)))
    patrol=mod.add(obj('BotTargetPatrol').simple_animator(anim_rotate_around_axis(1/32)))
    patrol.add(obj('MovingGoal',pos=(5.8,.2,0)).ai_node(is_goal=True))
    for x, z, sx, sz in ((-11,0,.4,22),(11,0,.4,22),(0,-11,22,.4),(0,11,22,.4)):
        cube(mod, 'Fence', (x, 1, z), (sx, 2, sz))
    # Bots follow the moving goal around the target ring and use their ordinary punches.
    if decorate:
        decorate(mod)
    return finish(mod, __file__, name, workshop,output_dir=output_dir)


if __name__ == '__main__':
    cli(build, 'Balloon Pop')
