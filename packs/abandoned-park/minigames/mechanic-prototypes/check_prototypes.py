"""Check built event graphs, race timing and barrel clearance; no game launch."""
from pathlib import Path
import json
import math
import zlib
from functools import lru_cache
import struct
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, HERE, DEFAULT_OUTPUT
import pmscene as P
import pmgen as G
import audit_playtest

NAMES = {'counterfeit-carts': 'Rusted Park Probe - Mascot Carts V3',
         'barrel-bends': 'Rusted Park Probe - Barrel Bends V3'}


def decode(r):
    kind = r.u16()
    r.string()
    actions = []
    for _ in range(r.u16()):
        r.u16()
        actions.append(json.loads(r.string()))
    return kind, actions


def logic(ob):
    r = P.Reader(ob.component('ModLogic').prop('Triggers').raw)
    return [decode(r) for _ in range(r.i32())]


def target_ids(action):
    return [v['m_assetGUID']['serializedGuid'] for v in action['m_targets']]


def vec(raw): return struct.unpack('<fff', raw)


def carts(folder):
    spec = json.loads((HERE / 'counterfeit-carts/BUILD.json').read_text())
    scene = P.load(str(folder / NAMES['counterfeit-carts'] / 'Data/MainScene.scene'))
    objects = scene.objects()
    refs = {ob.component('ModTransform').guid: ob for ob in objects}
    spawns = [ob.component('ModPlayerSpawn') for ob in objects if ob.component('ModPlayerSpawn')]
    assert len(spawns) == 8
    assert sorted(struct.unpack('<i', s.prop('AllowedPlayers').raw)[0] for s in spawns) == [1 << i for i in range(8)]
    root = folder / NAMES['counterfeit-carts']
    textures, materials = {}, {}
    for meta in (root/'Assets/Textures').glob('*.png.pmeta'):
        guid = json.loads(meta.read_text())['guid']['serializedGuid']
        textures[guid] = meta.with_suffix('')
    for meta in (root/'Assets/Materials').glob('*.pmat.pmeta'):
        data = json.loads(meta.read_text())
        ids = audit_playtest.UUID.findall(bytes(data['m_shaderData']))
        if len(ids)==1 and ids[0].decode() in textures:
            materials[data['guid']['serializedGuid']] = textures[ids[0].decode()]

    def face_texture(board):
        guid, = audit_playtest.UUID.findall(board.component('ModProp').prop('customMaterials').raw)
        return materials[guid.decode()]

    @lru_cache(None)
    def face_pixels(path):
        # Compare actual character pixels, excluding the number/MODEL caption.
        data = path.read_bytes()
        w,h = struct.unpack('>II',data[16:24])
        assert (w,h)==(180,240)
        at, payload = 8, bytearray()
        while at<len(data):
            size, = struct.unpack_from('>I',data,at)
            if data[at+4:at+8]==b'IDAT':
                payload.extend(data[at+8:at+8+size])
            at+=12+size
        raster=zlib.decompress(payload)
        stride=1+3*w
        assert all(raster[y*stride]==0 for y in range(h))
        return raster[16*stride:195*stride]

    for lane,z in enumerate(spec['stations']):
        rows = [r for r in spec['trials'] if r['lane']==lane]
        assert len(rows)==24
        station=scene.find(f'Station_{lane}')
        assert scene.find(f'Spawn_{lane}') in station.children
        cruise=scene.find(f'Cruise_{lane}')
        offset=scene.find(f'Offset_{lane}')
        moving=scene.find(f'Racing_{lane}')
        parked=scene.find(f'Parked_{lane}')
        assert offset in cruise.children and moving in offset.children
        assert not moving.active and not parked.active
        enter_actions=decode(P.Reader(station.find('RegisterSeat').component('ModTrigger').prop('OnEnterActions').raw))[1]
        assert target_ids(enter_actions[0])==[moving.component('ModTransform').guid]
        for viewer,vz in enumerate(spec['stations']):
            name=f'Toy_{lane}_At_{viewer}'
            start=vec(moving.find(name).component('ModTransform').prop('position').raw)
            end=vec(parked.find(name).component('ModTransform').prop('position').raw)
            assert math.isclose(end[0]-start[0],spec['track'],abs_tol=1e-5)
            assert start[1:]==end[1:] and abs(start[2]-(vz+6.6))<1e-4
        sensor=moving.find(f'FinishSensor_{lane}')
        gate=sensor.component('ModTrigger')
        place=decode(P.Reader(gate.prop('OnEnterActions').raw))[1]
        assert place[0]['m_type']==G.Action.SET_PLACEMENT and place[0]['m_targetFlags']==G.Targets.SOURCE
        assert target_ids(place[1])==[parked.component('ModTransform').guid]
        # Once the miniature moves TRACK, the front edge touches the 0.4 m player capsule.
        cx,cy,cz=vec(sensor.component('ModTransform').prop('position').raw)
        width=vec(gate.prop('Size').raw)[0]
        assert abs(cx+spec['track']+width/2+.4)<1e-5 and cz==z-2
        move=logic(cruise)[0][1][-1]
        assert math.isclose(move['m_endValue']['x']/move['m_time'], spec['base'])
        for i,row in enumerate(rows):
            q=refs[row['question']]
            model=face_pixels(face_texture(q.find('Model')))
            choices=[refs[g] for g in row['buttons']]
            faces=[face_texture(button.find('Tile')) for button in choices]
            key,=[j for j,path in enumerate(faces) if face_pixels(path)!=model]
            assert key==row['answer']
            boxes=[]
            for j,button in enumerate(choices):
                trigger=button.component('ModTrigger')
                tile=button.find('Tile')
                size=vec(trigger.prop('Size').raw)
                assert size[:2]==vec(tile.component('ModTransform').prop('scale').raw)[:2]
                assert vec(tile.component('ModTransform').prop('position').raw)[:2]==(0,0)
                assert faces[j].stem.endswith('_'+str(j+1))
                x,y,_=vec(button.component('ModTransform').prop('position').raw)
                assert all(abs(x-a)>size[0] or abs(y-b)>size[1] for a,b in boxes)
                boxes.append((x,y))
                tween,clear,light,show,hide=decode(P.Reader(trigger.prop('OnHitActions').raw))[1]
                assert target_ids(tween)==[offset.component('ModTransform').guid]
                assert tween['m_endValue']['x']==(spec['boost'] if j==key else spec['brake'])
                assert tween['m_time']==spec['pulse']<spec['cooldown']
                receipt=refs[target_ids(light)[0]].find('Receipt')
                assert face_texture(receipt).stem==f'result_{j+1}_{key+1}'
                assert target_ids(show)==[rows[(i+1)%len(rows)]['question']] and target_ids(hide)==[row['question']]
    duration=spec['round_seconds']-spec['start']
    assert spec['base']+spec['brake']/spec['pulse']>0
    assert spec['base']*duration+math.ceil(duration/spec['cooldown'])*spec['brake']>spec['track']
    return {'visible_answers_checked':len(spec['trials'])*4, 'maps':8, 'moving_figurines_checked':64,
            'full_braking_finishes_before_timeout':True}


def interpolate(route, t):
    elapsed = 0
    for p, q, duration in zip(route['points'], route['points'][1:], route['times']):
        if t <= elapsed+duration+1e-8:
            f = min(1, (t-elapsed)/duration)
            position = [a + (b-a)*f for a,b in zip(p,q)]
            break
        elapsed += duration
    for at, up, down, height in route.get('hops', []):
        if at <= t <= at+up:
            u = (t-at)/up
            position[1] += height*(1-(1-u)**2)
        elif at+up < t <= at+up+down:
            u = (t-at-up)/down
            position[1] += height*(1-u*u)
    return position


def barrels(folder):
    spec = json.loads((HERE / 'barrel-bends/BUILD.json').read_text())
    root = folder / NAMES['barrel-bends']
    scene = P.load(str(root / 'Data/MainScene.scene'))
    emitters = [ob for ob in scene.objects() if ob.component('ModSpawner')]
    assert len(emitters)==2*len(spec['legs'])
    samples=0
    for route in spec['hazards']:
        prefab=P.load(str(root/'Assets/Prefabs'/(route['name']+'Barrel.pfab')))
        actions=logic(prefab.roots[0])[0][1]
        assert actions[-1]['m_type']==G.Action.KILL
        wobble=prefab.find('Precession').component('ModMover')
        spin=prefab.find('Tumble').component('ModMover')
        assert struct.unpack('<i',wobble.prop('RotationAxisType').raw)[0]==G.MoverAxis.Y
        axis=vec(spin.prop('RotationAxis').raw)
        assert all(abs(v)>.1 for v in axis) and spin.prop('RotationSpeed').raw!=bytes(4)
        assert prefab.find('Tumble') in prefab.find('Precession').children
        moves=[a for a in actions if a['m_type']==G.Action.PLAY_TWEEN]
        assert len(moves)==len(route['times'])
        for move,p,q in zip(moves,route['points'],route['points'][1:]):
            delta=[q[i]-p[i] for i in range(3)]
            assert math.dist(delta, [move['m_endValue'][k] for k in 'xyz'])<1e-5
        leg=spec['legs'][route['leg']]
        half=spec['half_width']
        span=sum(route['times'])
        for i in range(201):
            x,y,z=interpolate(route,span*i/200)
            x-=leg['start'][0]
            z-=leg['start'][1]
            along=x*leg['dx']+z*leg['dz']-half
            side=x*leg['dz']-z*leg['dx']
            assert 0 <= along <= leg['length']
            assert abs(side)+.7 <= half+1e-5
            floor=leg['height']+along*spec['grade']
            assert y-floor >= .7*math.hypot(1,spec['grade'])-1e-5
            samples+=1
    for emitter in emitters:
        sp=emitter.component('ModSpawner')
        assert P.Reader(sp.prop('Prefabs').raw).i32()==3
        interval=json.loads(P.Reader(sp.prop('Interval1').raw).string())
        assert (interval['min'], interval['max'])==(.9,1.85)
    return {'trajectories_checked':len(spec['hazards']), 'swept_sphere_samples':samples,
            'random_emitters':len(emitters),'rise':spec['rise']}


def main():
    folder = Path(sys.argv[1]) if len(sys.argv)>1 else DEFAULT_OUTPUT
    audit_playtest.NAMES = list(NAMES.values())
    audit = audit_playtest.audit(folder)
    assert not any(r['errors'] for r in audit), audit
    report = {'structural':audit, 'carts':carts(folder), 'barrels':barrels(folder),
              'runtime':'Not exercised: finish sensors, camera, network and bot behaviour need playtest.'}
    (HERE / 'CHECKS.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
