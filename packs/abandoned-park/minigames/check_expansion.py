"""Check generated puzzles and serialized expansion projects, without launching the game.

Usage: python packs/abandoned-park/minigames/check_expansion.py [WorkshopMods folder]
"""
import json
from pathlib import Path
import re
import struct
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import pmscene as P
import pmgen as G

NAMES={'lost-and-found':'Lost & Found','counterfeit-mascots':'Counterfeit Mascots',
       'shadow-theatre':'Shadow Theatre','midnight-parade':'Midnight Parade',
       'crossed-wires':'Crossed Wires','boiler-jackpot':'Boiler Jackpot'}
UUID=re.compile(rb'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}')


def decode_trigger(reader):
    kind=reader.u16(); reader.string()
    actions=[]
    for _ in range(reader.u16()):
        reader.u16(); actions.append(json.loads(reader.string()))
    return kind,actions


def logic_actions(obj):
    r=P.Reader(obj.component('ModLogic').prop('Triggers').raw)
    return [decode_trigger(r) for _ in range(r.i32())][0][1]


def normalized_projection(cells,turn):
    points=[]
    for x,y,z in cells:
        for _ in range(turn): x,z=-z,x
        points.append((x,y))
    minx=min(x for x,y in points); miny=min(y for x,y in points)
    return {(x-minx,y-miny) for x,y in points}


def check_tasks(slug):
    data=json.loads((ROOT/'packs/abandoned-park/assets/expansion'/slug/'manifest.json').read_text('utf-8'))
    if slug=='boiler-jackpot': return 0
    tasks=data['tasks']
    assert len(tasks)==data['trials']*4
    for t in tasks:
        scores=t['scores']; answer=t['answer']
        assert len(scores)==len(t['options']) and scores.count(max(scores))==1
        assert scores[answer]==max(scores)
        if slug=='lost-and-found':
            assert len(set(t['layout']))==len(t['layout'])
            assert t['layout'][answer]==t['query']
        elif slug=='shadow-theatre':
            reference={tuple(p) for p in t['silhouette']}
            matching={i for i,shape in enumerate(t['shapes']) for turn in range(4)
                      if normalized_projection(shape,turn)==reference}
            assert matching=={answer}, (t['stem'],'ambiguous rotated silhouette',matching)
        elif slug=='midnight-parade':
            count=sum(i in t['flags'] and (not t['exclude_hat'] or i not in t['hats']) for i in range(t['figures']))
            assert t['options'][answer]==count
            assert scores==[3 if value==count else 1 if abs(value-count)==1 else 0 for value in t['options']]
        elif slug=='crossed-wires':
            assert all(sorted(col)==[0,1,2,3] for col in t['columns'])
            edges={(c,r):(c+1,t['columns'][c+1].index(t['columns'][c][r])) for c in range(5) for r in range(4)}
            node=(0,t['columns'][0].index(t['wire']))
            for _ in range(5): node=edges[node]
            assert node==(5,answer)
    return len(tasks)


def check_mod(folder,slug):
    files=[folder/'Data/MainScene.scene']+list(folder.rglob('*.pfab'))
    defined=[]; used=set(); objects=[]
    for file in files:
        s=P.load(str(file)); assert P.serialize(s)==file.read_bytes(),file
        for o in s.objects():
            assert not (o.component('ModLogic') and o.component('ModTrigger')),o.name
            defined.extend(c.guid for c in o.components)
            for c in o.components:
                for p in c.props: used.update(v.decode() for v in UUID.findall(p.raw))
        if file.suffix=='.scene': objects=s.objects(); scene=s
    assert len(defined)==len(set(defined)),'duplicate component GUID'
    assets=set()
    for p in folder.rglob('*.pmeta'):
        assert p.with_suffix('').exists(),p
        assets.add(json.loads(p.read_text('utf-8'))['guid']['serializedGuid'])
    known=set(defined)|assets|{G.GUID_EMPTY,G.ASSET_LOCATION_EXTERNAL}|{v for k,v in vars(G).items() if k.startswith('PROP_')}
    assert not used-known,('unresolved scene/prefab reference',used-known)
    for p in folder.rglob('*.json'): json.loads(p.read_text('utf-8'))
    settings=json.loads((folder/'Data/ModSettings.json').read_text('utf-8'))
    ps=settings['SimpleModPlayerSettings']
    assert not ps['canPunch'] and not ps['canJump'] and not ps['showNameTags']
    spawns=[o.component('ModPlayerSpawn') for o in objects if o.component('ModPlayerSpawn')]
    assert len(spawns)==8 and all(c.prop('SharedSpawn').raw==b'\x00' for c in spawns)
    assert all(struct.unpack('<i',c.prop('AllowedPlayers').raw)[0]==255 for c in spawns)
    assert all(struct.unpack('<i',c.prop('PlayerCountMask').raw)[0]==255 for c in spawns)
    report=json.loads((HERE/slug/'BUILD.json').read_text('utf-8'))
    director=logic_actions(scene.find('Director'))
    duration=sum(a['m_seconds']['min'] for a in director if a['m_type']==G.Action.WAIT)
    assert abs(duration-report['total_duration'])<.001 and duration<60
    for o in objects:
        if o.name.startswith(('Answer_','Score_','CashOut_','ResetPlayer_')):
            trigger=o.component('ModTrigger')
            assert trigger.prop('OneUsePerPlayer').raw==b'\x01',o.name
    if slug!='boiler-jackpot':
        by_guid={o.transform_guid:o for o in objects}
        for v in report['trial_variants']:
            variant=by_guid[v['variant_transform']]
            gates=by_guid[v['answer_group']]; scores=by_guid[v['score_group']]
            assert not variant.active and not gates.active and not scores.active
            assert len(gates.children)==8*len(v['options'])
            actions=logic_actions(variant)
            closing=next(i for i,a in enumerate(actions) if a['m_type']==G.Action.SET_ACTIVE and a['m_newState']==1
                         and a['m_targets'][0]['m_assetGUID']['serializedGuid']==gates.transform_guid)
            scoring=next(i for i,a in enumerate(actions) if a['m_type']==G.Action.SET_ACTIVE and a['m_newState']==0
                         and a['m_targets'][0]['m_assetGUID']['serializedGuid']==scores.transform_guid)
            assert closing<scoring
            for gate in gates.children:
                _,aa=decode_trigger(P.Reader(gate.component('ModTrigger').prop('OnEnterActions').raw))
                assert not any(a['m_type']==G.Action.CHANGE_SCORE for a in aa),'early answer leak'
                destination=next(a for a in aa if a['m_type']==G.Action.MATCH_TRANSFORM)['m_transformToMatch']['m_assetGUID']['serializedGuid']
                target=by_guid[destination]
                gp=struct.unpack('<fff',gate.component('ModTransform').prop('position').raw)
                tp=struct.unpack('<fff',target.component('ModTransform').prop('position').raw)
                assert abs(gp[2]-tp[2]-18)<.001,'answer must enter locked compartment'
        assert len(files)-1==report['trials']*4
    else:
        for stage in [r for r in scene.roots if r.name.startswith('Attempt_')]:
            bank=stage.find('CashBank')
            failure=logic_actions(stage.find('FailureClock'))
            assert failure[0]['m_seconds']=={'valueType':1,'min':2.0,'max':11.0}
            assert failure[1]['m_targets'][0]['m_assetGUID']['serializedGuid']==bank.transform_guid
            assert failure[1]['m_newState']==1
            for latch in [o for o in bank.children if o.name.startswith('CashLatch_')]:
                assert len(latch.children)==3
                for gate in latch.children:
                    _,aa=decode_trigger(P.Reader(gate.component('ModTrigger').prop('OnEnterActions').raw))
                    assert aa[0]['m_type']==G.Action.SET_ACTIVE and aa[0]['m_newState']==1
                    assert aa[0]['m_targets'][0]['m_assetGUID']['serializedGuid']==latch.transform_guid
                # No later tier action is permitted to reopen the station latch.
                assert all(latch.transform_guid not in json.dumps(a) for a in logic_actions(stage))
    return {'objects':len(objects),'prefabs':len(files)-1,'assets':len(assets),'duration':duration}


def main():
    folder=Path(sys.argv[1]) if len(sys.argv)>1 else Path.home()/'AppData/LocalLow/Rebuilt Games/Pummel Party/WorkshopMods'
    for slug,name in NAMES.items():
        tasks=check_tasks(slug)
        result=check_mod(folder/name,slug)
        print(name,'PASS',tasks,'tasks',result)


if __name__=='__main__': main()
