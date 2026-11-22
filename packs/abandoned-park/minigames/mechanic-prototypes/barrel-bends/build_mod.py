"""Switchback climb with random downhill barrel traffic."""
from pathlib import Path
import math
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import *

def hazard(mod, mesh, route):
    root = obj(route['name'] + 'Barrel')
    lift = root.add(obj('HopHeight'))
    lift.add(obj('Contact').trigger(TriggerShape.SPHERE, radius=.7,
        on_enter=[act_stun(.45), act_change_velocity(5, VelocityDir.CUSTOM, Op.SET, custom=route['push'])]))
    color = YELLOW if route['kind'] == 'hop' else TEAL if route['kind'] == 'bounce' else RED
    dx, _, dz = route['push']
    wobble = lift.add(obj('Precession').mover(rotation_axis_type=MoverAxis.Y, rotation_speed=75))
    spin = wobble.add(obj('Tumble').mover(rotation_axis_type=MoverAxis.CUSTOM,
        rotation_axis=(dz+.55*dx, .28, -dx+.55*dz), rotation_speed=245))
    # Centre the bottom-pivot mesh and keep its sweeping corners inside the contact sphere.
    spin.add(obj('BarrelMesh', pos=(.48, 0, 0), rot=(0, 0, 90), scale=(1.15,.96,1.15))
        .prop(mesh.guid, tint=color, collision=Collision.NONE))
    cube(spin, 'LidPaint', (.485,.09,0), (.02,.09,.65), YELLOW if route['kind']=='bounce' else TEAL,
         solid=False)
    move_actions = []
    for p, q, seconds in zip(route['points'], route['points'][1:], route['times']):
        delta = tuple(b-a for a, b in zip(p, q))
        move_actions += [act_play_tween([], end=delta, seconds=seconds, flags=Targets.RECEIVER), act_wait(seconds)]
    move_actions += [act_kill(Targets.RECEIVER)]
    root.logic(trig_enable(*move_actions))
    if route.get('hops'):
        actions, elapsed = [], 0
        for at, up, down, height in route['hops']:
            actions += [act_wait(at-elapsed),
                act_play_tween([], end=(0, height, 0), seconds=up, ease=Ease.EASE_OUT_QUAD, flags=Targets.RECEIVER),
                act_wait(up), act_play_tween([], end=(0, -height, 0), seconds=down,
                                           ease=Ease.EASE_IN_QUAD, flags=Targets.RECEIVER), act_wait(down)]
            elapsed = at+up+down
        lift.logic(trig_enable(*actions))
    return mod.add_prefab(root)




NAME = 'Rusted Park Probe - Barrel Bends V3'
CORNERS = [(0, 0), (0, 36), (36, 36), (36, 76), (-6, 76), (-6, 120)]
HALF = 5.5
GRADE = .20
ANGLE = math.degrees(math.atan(GRADE))


def build(destination=DEFAULT_OUTPUT):
    mod = Mod(NAME, round_duration=70, placement=Placement.FINISH_ORDER,
        end_conditions=EndCondition.TIMER | EndCondition.FINISH,
        description='Race uphill through the broken switchbacks. Gold barrels leap, teal barrels rebound. / Беги вверх по серпантину. Золотые бочки скачут, бирюзовые отскакивают от стен.',
        settings_overrides={'canPunch': False, 'canJump': True, 'jumpSpeed': 9., 'playerGravity': 25.,
                            'movementSpeed': 6., 'respawnEnabled': True, 'respawnTime': 1.,
                            'respawnInvulnerableTime': 1., 'stunImmunityLength': 2., 'useHealth': False})
    mod.lighting_profile = str(ART / 'lighting/rust-dusk.json')
    mats, signs = Materials(mod), Signs(mod)
    mesh = mod.add_file_asset('prop', str(ROOT / 'packs/abandoned-park/assets/models/barrel.obj'))
    height, nav, routes, legs = 0., [], [], []
    directions = []
    for leg, ((x,z), (nx,nz)) in enumerate(zip(CORNERS, CORNERS[1:])):
        span = math.hypot(nx-x,nz-z)
        dx, dz = (nx-x)/span, (nz-z)/span
        directions.append((dx,dz))
        length = span - 2*HALF
        yaw = math.degrees(math.atan2(dx,dz))
        def point(s, side=0, lift=0):
            return (x+dx*(HALF+s)+dz*side, height+s*GRADE+lift, z+dz*(HALF+s)-dx*side)
        slant = length*math.hypot(1,GRADE)
        # The top face, rather than the box centre, ends flush with each landing.
        floor_center = point(length/2+.3*math.sin(math.radians(ANGLE)), lift=-.3*math.hypot(1,GRADE))
        painted(mats, mod, f'Ramp_{leg}', floor_center, (2*HALF,.6,slant+.03),
                'cracked_concrete', ground=True, rot=(-ANGLE,yaw,0))
        for side in (-1,1):
            painted(mats, mod, f'AlleyWall_{leg}_{side}', point(length/2, side*(HALF+.2),1.2),
                    (.4,2.9,slant+.6), 'old_wood', rot=(-ANGLE,yaw,0))
        nav.extend([point(i*length/6, lift=.18) for i in range(7)])
        # Each chute randomly selects a bouncing, hopping or rolling barrel per release.
        for flank in (-1,1):
            lateral = flank*3.2
            pool = []
            for kind in ('hop','bounce','roll'):
                top, bottom = length-.6, .6
                def pos(f, side):
                    return point(top+(bottom-top)*f, side, .73)
                if kind=='bounce':
                    coords = [(0,lateral),(.22,flank*(HALF-.7)),(.68,-flank*(HALF-.7)),(1,flank*.6)]
                else:
                    coords = [(0,lateral),(1,-flank*1.9 if kind=='hop' else flank*.6)]
                points = [pos(f,side) for f,side in coords]
                duration = (top-bottom)/6.8
                route = dict(name=f'L{leg}_{flank}_{kind}', kind=kind, points=points,
                             times=[(b[0]-a[0])*duration for a,b in zip(coords,coords[1:])],
                             push=(-dx,.25,-dz), leg=leg)
                if kind=='hop':
                    route['hops'] = [(duration*f,.32,.32,1.9) for f in (.12,.51,.77)]
                prefab = hazard(mod, mesh, route)
                pool.append(prefab.guid)
                routes.append(route)
            mod.add(obj(f'Chute_{leg}_{flank}', pos=pos(0,lateral)).spawner(pool,
                interval=(.9,1.85)))
            painted(mats, mod, 'ChuteStripe', point(length-.6,lateral,.045), (1.8,.06,1.2),
                    'paint_cream', solid=False, rot=(-ANGLE,yaw,0))
        legs.append(dict(start=[x,z], dx=dx,dz=dz, length=length, height=height))
        height += length*GRADE

    for i,(x,z) in enumerate(CORNERS):
        y = legs[i]['height'] if i<len(legs) else height
        painted(mats, mod, f'Landing_{i}', (x,y-.3,z), (2*HALF,.6,2*HALF),
                'cracked_concrete', ground=True)
        openings = set()
        if i: openings.add(tuple(-v for v in directions[i-1]))
        if i<len(legs): openings.add(directions[i])
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            if (dx,dz) in openings: continue
            painted(mats,mod,'TurnWall',(x+dx*(HALF+.2),y+1.3,z+dz*(HALF+.2)),
                    ((.4 if dx else 2*HALF+.8),2.6,(.4 if dz else 2*HALF+.8)), 'old_wood')
        if 0<i<len(legs):
            mod.add(obj(f'Progress_{i}',pos=(x,y+1,z)).trigger(size=(2*HALF,3,2*HALF),
                    on_enter=[act_change_score(1)],one_use_per_player=True))
    x,z=CORNERS[-1]
    spawn(mod,(0,.4,0),4,line=True)
    nav_line(mod,[(0,.18,0),*nav,(x,height+.18,z)],goal=True)
    finish_trigger=mod.add(obj('Finish',pos=(x,height+1,z)).trigger(size=(2*HALF,3,1),
                              on_enter=[act_set_placement()],one_use_per_player=True))
    for side in (-1,1):
        painted(mats, mod, 'FinishPillar', (x+side*HALF,height+3,z), (.5,6,.5), 'paint_red')
    signs.board(mod,'FinishSign','finish.png',(x,height+5.5,z),(8,3))
    mod.add(obj('FallReset',pos=(15,-2,60)).trigger(size=(95,1,155),on_enter=[act_kill()]))
    cube(mod,'FallSafetyBed',(15,-3,60),(95,1,155),RUST,solid=True)
    scenery(mod,60,83,60)
    distant_wheel(mod,(x+16,height+2,z+17),2)
    return complete(mod,__file__,destination,dict(kind='barrel_probe',legs=legs,half_width=HALF,
        grade=GRADE,rise=height,hazards=routes,finish=finish_trigger.transform_guid,
        route_metres=sum(math.dist(a,b) for a,b in zip(CORNERS,CORNERS[1:])),
        jump_height=9**2/(2*25)))

if __name__ == '__main__':
    print(build(Path(sys.argv[1]) if len(sys.argv)>1 else DEFAULT_OUTPUT))
