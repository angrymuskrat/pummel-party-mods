"""Build Ghost Train; optional arguments: mod name, WorkshopMods directory."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reserve_common import *


def build(name='Ghost Train', workshop=WORKSHOP):
    mod = base(name, 'Ghost Train / Паровозик: stay on the train, dodge red gantries. Last survivor wins.', survival=True)
    pond(mod, 50, 90, 23)
    train = mod.add(obj('Train'))
    cube(train, 'TrainDeck', (0, -.4, 0), (12, .8, 14), TEAL, ground=True)
    # Train waits for the countdown and a three-second reading window.
    train.logic(trig_round_start(act_wait(3), act_play_tween([train.transform_guid],
        Tween.LOCAL_POSITION, end=(0, 0, 40), seconds=54)))
    spawn(mod, (0, 1, -2), 4)
    scenery(mod,24,43,23)
    for side in (-1,1):
        cube(train,'EdgeStripe',(side*5.8,.02,0),(.2,.04,14),YELLOW,solid=False)
        for z in (-5,0,5):
            train.add(obj('WheelVisual',pos=(side*5.5,-.65,z),scale=(.5,1.4,1.4))
                .prop(PROP_SPHERE,tint=RUST,collision=Collision.NONE)
                .mover(rotation_axis_type=MoverAxis.X,rotation_speed=90))
    cube(train,'Boiler',(0,1,5.5),(2,2,2),RUST,solid=False)
    cube(train,'Chimney',(0,3,5.5),(.7,3,.7),RUST,solid=False)
    for i, z in enumerate((13, 21, 29, 37, 45)):
        x = -3 if i % 2 == 0 else 3
        gate = mod.add(obj(f'RedGate_{i}', pos=(x, 1.5, z)))
        cube(gate, 'VisibleHazard', (0, 0, 0), (5.5, 3, .65), RED, solid=False)
        gate.trigger(size=(5.5, 3, .65), on_enter=[act_kill()])
        cube(mod, f'Gantry_{i}', (0, 5, z), (17, .5, .5), YELLOW, solid=False)
        for sx in (-8,8):
            cube(mod,'GantryPost',(sx,2.5,z),(.5,5,.5),RUST,solid=False)
    # Side changes are possible across the entire deck; no fixed AI goal beyond the moving train.
    return finish(mod, __file__, name, workshop)


if __name__ == '__main__':
    cli(build, 'Ghost Train')
