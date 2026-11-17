"""Static format, timing, reward and route checks for backlog entries 17–22."""
from pathlib import Path
import json
import math
import struct
import sys
from collections import deque

from check_expansion import P, G, UUID, decode_trigger, logic_actions
from finale_common import NAMES, ASSETS, ROOMS

HERE=Path(__file__).resolve().parent


def pos(o): return struct.unpack('<fff',o.component('ModTransform').prop('position').raw)
def actions(o,event='OnEnterActions'): return decode_trigger(P.Reader(o.component('ModTrigger').prop(event).raw))[1]
def changes_score(aa): return [a['m_value'] for a in aa if a['m_type']==G.Action.CHANGE_SCORE]
def wait_sum(aa): return sum(a['m_seconds']['min'] for a in aa if a['m_type']==G.Action.WAIT)
def targets(a): return [t['m_assetGUID']['serializedGuid'] for t in a.get('m_targets',[])]


def format_check(folder,slug):
    definitions=[]; used=set(); scene=None
    files=[folder/'Data/MainScene.scene']+list(folder.rglob('*.pfab'))
    for f in files:
        parsed=P.load(str(f)); assert P.serialize(parsed)==f.read_bytes(),f
        if f.suffix=='.scene': scene=parsed
        for o in parsed.objects():
            assert not (o.component('ModLogic') and o.component('ModTrigger')),o.name
            definitions.extend(c.guid for c in o.components)
            for c in o.components:
                for p in c.props: used.update(x.decode() for x in UUID.findall(p.raw))
    assert len(definitions)==len(set(definitions))
    assets=[]
    for p in folder.rglob('*.pmeta'):
        assert p.with_suffix('').is_file(),p
        assets.append(json.loads(p.read_text('utf-8'))['guid']['serializedGuid'])
    known=set(definitions+assets)|{G.GUID_EMPTY,G.ASSET_LOCATION_EXTERNAL}|{v for k,v in vars(G).items() if k.startswith('PROP_')}
    assert not used-known,used-known
    for p in folder.rglob('*.json'): json.loads(p.read_text('utf-8'))
    settings=json.loads((folder/'Data/ModSettings.json').read_text('utf-8'))
    ps=settings['SimpleModPlayerSettings']; mg=settings['SimpleMinigameSettings']
    assert not ps['canJump'] and not ps['respawnEnabled']
    assert ps['canPunch']==(slug=='broken-clock')
    spawns=[o.component('ModPlayerSpawn') for o in scene.objects() if o.component('ModPlayerSpawn')]
    assert len(spawns)==8 and all(s.prop('SharedSpawn').raw==b'\0' for s in spawns)
    assert all(struct.unpack('<i',s.prop('AllowedPlayers').raw)[0]==255 for s in spawns)
    report=json.loads((HERE/slug/'BUILD.json').read_text('utf-8'))
    if slug!='closing-time': assert abs(wait_sum(logic_actions(scene.find('Director')))-report['duration'])<1e-5
    assert report['duration']<=60
    return scene,mg,report,{'objects':len(scene.objects()),'prefabs':len(files)-1,'assets':len(assets)}


def path_length(start,end,blocked,bounds):
    # Half-metre raster, radius .4 m; independent of the generated AI navigation graph.
    def free(p):
        x,z=p[0]/2,p[1]/2
        return bounds[0]<x<bounds[1] and bounds[2]<z<bounds[3] and not any(abs(x-a)<=w/2+.4 and abs(z-b)<=d/2+.4 for a,b,w,d in blocked)
    start=tuple(round(v*2) for v in start); end=tuple(round(v*2) for v in end)
    queue=deque([(start,0)]); seen={start}
    while queue:
        p,n=queue.popleft()
        if p==end: return n/2
        for dx,dz in ((1,0),(-1,0),(0,1),(0,-1)):
            q=p[0]+dx,p[1]+dz
            if q not in seen and free(q): seen.add(q); queue.append((q,n+1))
    raise AssertionError(('No walkable path',start,end))


def check(slug,folder):
    scene,mg,report,counts=format_check(folder,slug); objects=scene.objects()
    if slug=='broken-clock':
        assert mg['EndConditions']==G.EndCondition.REMAINING_ALIVE and mg['MinPlayersAlive']==0
        assert mg['MusicVolume']==0 and mg['AmbienceVolume']==0
        assert len([o for o in scene.find('TerminalBlackout').walk() if o.component('ModTrigger')])==8
        for n,interval in enumerate(report['intervals']):
            stage=scene.find(f'Stage_{n}'); timeline=logic_actions(stage)
            bands=[]; t=-1.5  # first wait displays the target before the start chime
            for a in timeline:
                if a['m_type']==G.Action.WAIT: t+=a['m_seconds']['min']
                if a['m_type']==G.Action.SET_ACTIVE and a['m_newState']==0:
                    for guid in targets(a):
                        o=next(o for o in objects if o.transform_guid==guid)
                        if o.name.startswith('ClockButton_') and o.name.endswith('_0'):
                            bands.append((round(t,5),changes_score(actions(o,'OnHitActions'))[0]))
            for delta in (-2,-1.49,-.89,-.39,0,.39,.89,1.49,1.7):
                time=interval+delta
                score=[score for start,score in bands if start<=time][-1]
                expected=3 if abs(delta)<.4 else 2 if abs(delta)<.9 else 1 if abs(delta)<1.5 else 0
                assert score==expected,(n,delta,bands)
            for latch in [o for o in stage.children if o.name.startswith('ClockLatch_')]:
                assert len(latch.children)==7
                assert all(actions(b,'OnHitActions')[0]['m_newState']==1 and targets(actions(b,'OnHitActions')[0])==[latch.transform_guid] for b in latch.children)
                assert not any(latch.transform_guid in targets(a) and a.get('m_newState')==0 for a in timeline)
    elif slug=='false-alarm':
        assert len(report['signals'])==10 and sum(go for go,t in report['signals'])==5
        for n,(go,target) in enumerate(report['signals']):
            stage=scene.find(f'Stage_{n}'); aa=logic_actions(stage)
            assert abs(wait_sum(aa)-4.8)<1e-6
            assert targets(aa[1])==[stage.find('Freeze').transform_guid]
            assert targets(aa[3])==[stage.find('Score').transform_guid]
            assert all(changes_score(actions(o))==[1] for o in stage.find('Score').children)
    elif slug=='last-sale':
        for n,offers in enumerate(report['offers']):
            assert sorted(offers)==[[2,5],[3,3],[8,1]]
            stage=scene.find(f'Stage_{n}'); aa=logic_actions(stage)
            assert targets(aa[1])==[stage.find('CommitEntries').transform_guid] and aa[1]['m_newState']==1
            assert targets(aa[2])==[stage.find('Prizes').transform_guid] and aa[2]['m_newState']==0
            for p in stage.find('Prizes').children:
                a=actions(p); assert changes_score(a) in ([1],[3],[5])
                assert any(x['m_type']==G.Action.MATCH_TRANSFORM for x in a)
                assert p.component('ModTrigger').prop('OneUsePerPlayer').raw==b'\1'
                if changes_score(a)!=[1]: assert p.component('ModTrigger').prop('DisableAfterTriggered').raw==b'\1'
    elif slug=='closing-time':
        assert counts['prefabs']==3
        best=[]
        for v,rides in enumerate(report['schedules']):
            trips=[]
            for r,route in enumerate(rides):
                for k,(depart,duration) in enumerate(route):
                    group=scene.find(f'Schedule_{v}').find(f'Boarding_{r}_{k}')
                    a=actions(group.children[0]); reward=changes_score(a)
                    assert reward==([report['rewards'][r]] if depart+duration<=60 else [])
                    assert any(x['m_type']==G.Action.MODIFY_PLAYER and x.get('m_movementSpeed')==0 for x in a)
                    assert depart+wait_sum(a)<59.7
                    if reward: trips.append((depart,depart+duration,r,reward[0]))
            # Optimal chains with walking time between return and boarding rectangles.
            trips.sort(); scores=[]; chains=[]
            for i,(depart,end,r,value) in enumerate(trips):
                candidates=[(0,[])]
                for j,prev in enumerate(trips[:i]):
                    walking=math.hypot(13*(r-prev[2]),6)/6+.15
                    if prev[1]+walking<depart: candidates.append((scores[j],chains[j]))
                prior,chain=max(candidates,key=lambda p:p[0]); scores.append(prior+value); chains.append(chain+[r])
            highest=max(scores); best.append(highest)
            assert len(set(chains[scores.index(highest)]))>=2,'one ride dominates every useful decision'
        counts['best_schedule_scores']=best
    elif slug=='emergency-exit':
        blocked=[(-2.25,-4,13.5,.5),(2.25,4,13.5,.5)]
        distance=path_length((-6,-9),(6,9),blocked,(-8.5,8.5,-11.5,11.5))
        assert distance/6<16
        counts['closed_gate_route_metres']=distance
        for n in range(3):
            stage=scene.find(f'Stage_{n}')
            assert len([o for o in stage.walk() if o.name.startswith('ExitScore_')])==8
            assert len([o for o in stage.walk() if o.name.startswith('SideToken_')])==8
    else:
        for i in range(3):
            aa=actions(scene.find(f'Control_{i}')); waits=[a['m_seconds']['min'] for a in aa if a['m_type']==G.Action.WAIT]
            assert waits==[1.5,1,8]
            assert not changes_score(aa) and not changes_score(actions(scene.find(f'ReturnHazard_{i}')))
        safe=path_length((-4,-8),(-4,18),[(0,5,4,20),(-4.9,7,5.8,3)],(-7.5,7.5,-11,21))
        assert safe/6<9.5
        counts['safe_detour_metres']=safe
        assert len(report['sequence'])==6
    return counts


if __name__=='__main__':
    folder=Path(sys.argv[1]) if len(sys.argv)>1 else Path.home()/'AppData/LocalLow/Rebuilt Games/Pummel Party/WorkshopMods'
    for slug,name in NAMES.items(): print(name,'PASS',check(slug,folder/name))
