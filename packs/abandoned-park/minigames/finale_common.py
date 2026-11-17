"""Six distinct official-editor prototypes for the remaining Rusted Park backlog."""
from pathlib import Path
import contextlib
import io
import json
import math
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from reserve_common import *
from expansion_common import switch, place_player, Cards as OriginalCards
sys.path.insert(0,str(ROOT/'packs/abandoned-park/assets/finale'))
from generate_finale import generate, HERE as ASSETS, NAMES

ROOMS=[(x,z) for z in (-13,13) for x in (-30,-10,10,30)]


class Cards(OriginalCards):
    def __init__(self,mod,slug):
        super().__init__(mod,'broken-clock')
        self.folder=ASSETS/slug


def marker(parent,name,x,z):
    return parent.add(obj(name,pos=(x,.15,z)))


def touch(parent,name,pos,size,actions,one=True,consume=False,active=True):
    return parent.add(obj(name,pos=pos,active=active).trigger(size=size,on_enter=actions,on_stay=actions,
        stay_interval=.03,one_use_per_player=one,disable_after=consume))


def surface(parent,name,x,z,w,d,color=TEAL):
    return cube(parent,name,(x,-.4,z),(w,.8,d),color,ground=True)


def walls(parent,x,z,w,d,height=3):
    for sx in (-1,1): cube(parent,'SideWall',(x+sx*w/2,height/2,z),(.4,height,d),RUST)
    for sz in (-1,1): cube(parent,'EndWall',(x,height/2,z+sz*d/2),(w,height,.4),RUST)


def floor_mark(parent,name,x,z,w,d,color=YELLOW):
    return cube(parent,name,(x,.025,z),(w,.05,d),color,solid=False)


def nav_grid(mod,x0,x1,z0,z1,step=3,blocked=()):
    """Axis-aligned conservative graph, no edge through any permanent wall."""
    def free(x,z): return not any(abs(x-a)<w/2+.55 and abs(z-b)<d/2+.55 for a,b,w,d in blocked)
    nodes={}
    for ix in range(round((x1-x0)/step)+1):
        for iz in range(round((z1-z0)/step)+1):
            x=x0+ix*step; z=z0+iz*step
            if free(x,z): nodes[ix,iz]=mod.add(obj('Nav',pos=(x,.15,z)).ai_node())
    values=list(nodes.values()); indices={id(n):i for i,n in enumerate(values)}; edges=[]
    for (ix,iz),node in nodes.items():
        for dx,dz in ((1,0),(0,1)):
            other=nodes.get((ix+dx,iz+dz))
            if other and all(free(node.pos[0]+dx*step*t/8,node.pos[2]+dz*step*t/8) for t in range(9)):
                a,b=indices[id(node)],indices[id(other)]; edges += [(a,b),(b,a)]
    link_ai_nodes(values,edges)


def new_mod(slug,name,top=False):
    data=generate(slug)
    mod=Mod(name or NAMES[slug],description=f'Rusted Park / {NAMES[slug]}. First prototype. Read the signs; highest score wins.',
        player_type=PlayerType.TOP_DOWN if top else PlayerType.THIRD_PERSON,
        settings_overrides={'canPunch':False,'canJump':False,'respawnEnabled':False,'useHealth':False,
            'movementSpeed':6.0,'playerGravity':25.0,'showNameTags':False,'stepOffset':.2,
            'topDownCameraMode':1,'topDownCameraDistance':30,'topDownCameraViewAngle':70})
    return mod,Cards(mod,slug),data


def private_world(mod,cards,maze=False):
    starts=[]
    for i,(x,z) in enumerate(ROOMS):
        surface(mod,'BoothFloor',x,z,18,24)
        walls(mod,x,z,18,24,2 if maze else 8)
        p=marker(mod,f'Start_{i}',x-6 if maze else x,z-9 if maze else z-5); starts.append(p)
        mod.add(obj(f'Spawn_{i}',pos=(p.pos[0],1,p.pos[2])).player_spawn(shared=False,usage=SpawnUsage.INITIAL))
        floor_mark(mod,'Home',p.pos[0],p.pos[2],3,3,TEAL)
        if not maze: cards.board(mod,f'Title_{i}','title.png',(x,5,z+8),(15,7.5))
    scenery(mod,47,32)
    return starts


def room_reset(mod,n,starts,speed=1):
    group=mod.add(obj(f'Reset_{n}',active=False))
    for i,((x,z),p) in enumerate(zip(ROOMS,starts)):
        touch(group,f'ResetPlayer_{i}',(x,2,z),(17.5,5,23.5),place_player(p,speed))
    return group


def shared_world(mod,w,d,spawn_z=-9):
    surface(mod,'Plaza',0,0,w,d); walls(mod,0,0,w,d)
    for i in range(8):
        angle=2*math.pi*i/8
        mod.add(obj(f'Spawn_{i}',pos=(2*math.cos(angle),1,spawn_z+2*math.sin(angle))).player_spawn(shared=False,usage=SpawnUsage.INITIAL))
    scenery(mod,w/2+9,d/2+9)


def shared_reset(mod,n,dest,w,d):
    g=mod.add(obj(f'Reset_{n}',active=False))
    touch(g,'ResetAll',(0,2,0),(w,5,d),place_player(dest))
    return g


def run_clock(mod,cards,data):
    starts=private_world(mod,cards)
    mod.settings_overrides.update(canPunch=True,punchDamage=0,punchStunsTarget=False)
    # A visible round timer defeats internal timing. No timer flag means no timer UI.
    # The terminal blackout kills everyone together; MostPoints still ranks the earned score.
    mod.end_conditions=EndCondition.REMAINING_ALIVE; mod.min_players_alive=0
    sound=mod.add_file_asset('audio',str(ASSETS/'broken-clock/start.wav'))
    director=[act_wait(.5)]; elapsed=.5
    for n,target in enumerate(data['intervals']):
        reset=room_reset(mod,n,starts,0)
        stage=mod.add(obj(f'Stage_{n}',active=False)); intro=stage.add(obj('IntervalCard')); dark=stage.add(obj('Dark',active=False))
        bands=[(0,target-1.5,0),(target-1.5,target-.9,1),(target-.9,target-.4,2),
               (target-.4,target+.4,3),(target+.4,target+.9,2),(target+.9,target+1.5,1),(target+1.5,target+2,0)]
        # Latches own the hit colliders; time drivers only change collider children.
        buttons=[[] for _ in bands]
        for i,(x,z) in enumerate(ROOMS):
            cards.board(intro,f'Target_{i}',f'target_{n}.png',(x,4,z+3),(14,7))
            cards.board(dark,f'Dark_{i}','dark.png',(x,4,z+3),(14,7))
            latch=stage.add(obj(f'ClockLatch_{i}'))
            for j,(lo,hi,points) in enumerate(bands):
                hit=latch.add(obj(f'ClockButton_{j}_{i}',pos=(x,1,z-3.5),active=False).trigger(size=(3,1.5,.6),
                    on_hit=[switch(latch,False),act_change_score(points),act_show_message(f'{points} points',1,MsgTarget.TARGET)],
                    one_use_per_player=True,disable_after=True))
                cube(hit,'Button',(0,0,0),(3,1.5,.5),YELLOW,solid=False); buttons[j].append(hit)
        actions=[act_wait(1.5),switch(intro,False),switch(dark),act_play_sound(sound.guid)]
        for j,(lo,hi,points) in enumerate(bands):
            actions += [switch(b) for b in buttons[j]]+[act_wait(hi-lo)]+[switch(b,False) for b in buttons[j]]
        stage.logic(trig_enable(*actions))
        length=1.5+target+2
        director += [switch(reset),act_wait(.25),switch(reset,False),switch(stage),act_wait(length),switch(stage,False)]
        elapsed += .25+length
    end=mod.add(obj('TerminalBlackout',active=False))
    for x,z in ROOMS: touch(end,'EndAllPlayers',(x,2,z),(18,6,24),[act_kill()])
    director += [act_show_message('ALL ATTEMPTS COMPLETE / ВСЕ ПОПЫТКИ ЗАВЕРШЕНЫ',2),act_wait(2),switch(end)]
    elapsed+=2
    mod.add(obj('Director').logic(trig_round_start(*director)))
    return {'duration':elapsed,'intervals':data['intervals'],'timer_ui':False}


def run_alarm(mod,cards,data):
    starts=private_world(mod,cards)
    sectors=[(-4,0),(0,0),(4,0),(0,-5)]
    for x,z in ROOMS:
        for j,(dx,dz) in enumerate(sectors):
            floor_mark(mod,f'Sector_{j}',x+dx,z+dz,3,3,[YELLOW,RUST,TEAL,TEAL][j])
            cards.board(mod,'SectorSign',f'sector_{j}.png' if j<3 else 'home.png',(x+dx,1.3,z+dz+1.6),(3,1.5))
    director=[act_wait(.5)]
    for n,(go,target) in enumerate(data['signals']):
        reset=room_reset(mod,n,starts)
        stage=mod.add(obj(f'Stage_{n}',active=False)); freeze=stage.add(obj('Freeze',active=False)); score=stage.add(obj('Score',active=False))
        for i,(x,z) in enumerate(ROOMS):
            cards.board(stage,f'Command_{i}',f'command_{n}.png',(x,4,z+3),(14,7))
            touch(freeze,f'Freeze_{i}',(x,2,z),(17.5,5,23.5),[act_modify_player_speed(0),act_change_velocity(0,VelocityDir.CUSTOM,Op.SET)])
            dx,dz=sectors[target if go else 3]
            touch(score,f'PositionScore_{i}',(x+dx,1,z+dz),(2.8,3,2.8),[act_change_score(1)])
        stage.logic(trig_enable(act_wait(4.5),switch(freeze),act_wait(.15),switch(score),act_wait(.15),switch(score,False)))
        director += [switch(reset),act_wait(.25),switch(reset,False),switch(stage),act_wait(5.4),switch(stage,False)]
    mod.add(obj('Director').logic(trig_round_start(*director)))
    return {'duration':57,'signals':data['signals'],'freeze_before_scoring':.15}


def maze_walls(x,z):
    # Always-open serpentine route around alternating ends, plus two central shortcuts.
    result=[]
    for row in (-1,1):
        zz=z+row*4
        bounds=(-9,4.5) if row==-1 else (-4.5,9)
        for a,b in ((bounds[0],-1.5),(1.5,bounds[1])):
            result.append((x+(a+b)/2,zz,b-a,.5))
    return result


def run_exit(mod,cards,data):
    starts=private_world(mod,cards,maze=True)
    for i,(x,z) in enumerate(ROOMS):
        blocked=maze_walls(x,z)
        for a,b,w,d in blocked: cube(mod,'MazeWall',(a,1,b),(w,2,d),RUST)
        nav_grid(mod,x-6,x+6,z-9,z+9,3,blocked+[(x,z-4,3,.5),(x,z+4,3,.5)])
        cards.board(mod,'Rules','rules.png',(x,5,z+11),(14,7))
    director=[act_wait(.4)]
    layouts=[]
    for n in range(3):
        # Alternate direction: three route problems using the same legible maze shell.
        reverse=n==1
        targets=[marker(mod,f'MazeStart_{n}_{i}',x+6 if reverse else x-6,z+9 if reverse else z-9) for i,(x,z) in enumerate(ROOMS)]
        reset=room_reset(mod,n,targets,0)
        release=mod.add(obj(f'Release_{n}',active=False))
        stage=mod.add(obj(f'Stage_{n}',active=False)); play=stage.add(obj('MazePlay',active=False))
        gates=[]
        for i,(x,z) in enumerate(ROOMS):
            touch(release,'ReleasePlayer',(x,2,z),(17.5,5,23.5),[act_modify_player_speed(1)])
            dest=marker(mod,f'ExitWait_{n}_{i}',x+6 if not reverse else x-6,z+9 if not reverse else z-9)
            exitpos=(dest.pos[0],1,dest.pos[2])
            touch(play,f'ExitScore_{i}',exitpos,(3,3,3),[act_change_score(3)]+place_player(dest,0))
            floor_mark(stage,'ExitMark',exitpos[0],exitpos[2],3,3,TEAL)
            cards.board(stage,'ExitSign','exit.png',(exitpos[0],2,exitpos[2]+1.5),(4,2))
            tx=x+(6 if n!=2 else -6); tz=z+(0 if n!=2 else 9)
            token=touch(play,f'SideToken_{i}',(tx,1,tz),(2,2,2),[act_change_score(1)],consume=True)
            token.add(obj('Token',scale=(.8,.8,.8)).prop(PROP_SPHERE,tint=YELLOW,collision=Collision.NONE))
            for k in (-1,1):
                g=cube(stage,f'TimedGate_{i}_{k}',(x,1,z+k*4),(3,2,.5),RED); gates.append(g)
        actions=[act_wait(2.5),switch(play),switch(release),act_wait(.2),switch(release,False)]
        # Five equal windows; a closed shortcut never blocks the permanent outer route.
        for cycle in range(5):
            actions += [switch(g,(cycle+n+k)%2==0) for k,g in enumerate(gates)]+[act_wait(3.2)]
        actions += [switch(play,False)]
        stage.logic(trig_enable(*actions))
        director += [switch(reset),act_wait(.25),switch(reset,False),switch(stage),act_wait(19.25),switch(stage,False)]
        layouts.append({'reverse':reverse,'token':n,'play_seconds':16.2})
    mod.add(obj('Director').logic(trig_round_start(*director)))
    return {'duration':58.9,'layouts':layouts,'safe_route_metres':52}


def run_sale(mod,cards,data):
    shared_world(mod,48,42,-10)
    lobby=marker(mod,'LobbyReset',0,-10); wait=marker(mod,'PrizeWait',0,-18)
    cube(mod,'WaitingPartition',(0,2,-15),(48,4,.4),RUST)
    shops=[-16,0,16]
    for x in shops:
        walls(mod,x,8,14,20)
        floor_mark(mod,'Entrance',x,-4,3,2)
        nav_grid(mod,x-4,x+4,2,14,4)
    nav_grid(mod,-20,20,-12,-4,4)
    director=[act_wait(.5)]
    for n,offers in enumerate(data['offers']):
        reset=shared_reset(mod,n,lobby,47,41)
        stage=mod.add(obj(f'Stage_{n}',active=False)); entries=stage.add(obj('CommitEntries')); prizes=stage.add(obj('Prizes',active=False))
        for j,(x,(stock,value)) in enumerate(zip(shops,offers)):
            queue=marker(mod,f'Queue_{n}_{j}',x,1)
            cards.board(stage,'Offer',f'offer_{n}_{j}.png',(x,4,-1.6),(12,6))
            cards.board(stage,'LockedRules','locked.png',(x,4,16),(12,6))
            touch(entries,f'Commit_{j}',(x,1,-4),(3,3,2),place_player(queue))
            for k in range(stock if stock<8 else 1):
                dx=(k-(stock-1)/2)*3 if stock<8 else 0
                prize=touch(prizes,f'Prize_{j}_{k}',(x+dx,1,8),(2.2,3,2.2),[act_change_score(value)]+place_player(wait,0),consume=stock<8)
                prize.add(obj('PrizeVisual',scale=(.8,1,.8)).prop(PROP_SPHERE,tint=YELLOW,collision=Collision.NONE))
        stage.logic(trig_enable(act_wait(5),switch(entries,False),switch(prizes),act_show_message('PRIZES OPEN / ПРИЗЫ ОТКРЫТЫ',1.5),
                               act_wait(5.5),switch(prizes,False)))
        director += [switch(reset),act_wait(.25),switch(reset,False),switch(stage),act_wait(11),switch(stage,False)]
    mod.add(obj('Director').logic(trig_round_start(*director)))
    return {'duration':56.75,'offers':data['offers'],'prizes_per_player_per_wave':1}


def run_closing(mod,cards,data):
    mod.description+=' TIMER on each sign means seconds LEFT on the round countdown. Stand in a boarding rectangle at that time; rides ending after closing pay nothing.'
    shared_world(mod,42,40,-8)
    # Ride compartments behind a full partition are unreachable by foot.
    cube(mod,'RidePartition',(0,2,9),(42,4,.4),RUST)
    for x in (-7,7): cube(mod,'RideBayWall',(x,2,14.5),(.4,4,11),RUST)
    islands=[(-6,-10,4,4),(6,-10,4,4)]
    for x,z,w,d in islands:
        cube(mod,'ClosedKiosk',(x,1.5,z),(w,3,d),RUST)
        cube(mod,'KioskAwning',(x,3.2,z),(w+1,.3,d+1),YELLOW,solid=False)
    nav_grid(mod,-18,18,-15,6,3,islands+[(x+dx,2,.35,6) for x in (-13,0,13) for dx in (-4,4)])
    destinations=[]; bays=[]
    for r,x in enumerate((-13,0,13)):
        destinations.append(marker(mod,f'RideReturn_{r}',x,-4)); bays.append(marker(mod,f'RideBay_{r}',x,14))
        floor_mark(mod,f'BoardingMark_{r}',x,2,7,5)
        for dx in (-4,4):
            cube(mod,'QueueRail',(x+dx,.8,2),(.15,1.6,5),RUST)
            for zz in (0,4): cube(mod,'QueuePost',(x+dx,1,zz),(.35,2,.35),YELLOW)
        wheel=mod.add(obj(f'RideWheel_{r}',pos=(x,4,17)).mover(rotation_axis_type=MoverAxis.Z,rotation_speed=30/(r+1)))
        for angle in (0,60,120): cube(wheel,'Spoke',(0,0,0),(5,.2,.2),YELLOW,solid=False,rot=(0,0,angle))
    anchor=marker(mod,'ScheduleSelector',0,-30); selectors=[]
    for v,rides in enumerate(data['schedules']):
        variant=mod.add(obj(f'Schedule_{v}',active=False))
        for r,(x,trips) in enumerate(zip((-13,0,13),rides)):
            signs=[]
            for k,(depart,duration) in enumerate(trips):
                sign=variant.add(obj(f'Sign_{r}_{k}',active=k==0)); signs.append(sign)
                cards.board(sign,'Timetable',f'schedule_{v}_{r}_{k}.png',(x,4,7),(12,6))
                boarding=variant.add(obj(f'Boarding_{r}_{k}',active=False))
                pay=depart+duration<=60
                actions=place_player(bays[r],0)+[act_wait(duration if pay else 59.4-depart)]
                if pay: actions += [act_change_score(data['rewards'][r])]
                actions += place_player(destinations[r])
                touch(boarding,'Passenger',(x,1,2),(6.8,3,4.8),actions)
                controller=variant.add(obj(f'Departure_{r}_{k}'))
                # Open only at departure, sampling all players already inside the boarding rectangle.
                controller.logic(trig_enable(act_wait(depart),switch(boarding),act_wait(.12),switch(boarding,False)))
            closed=variant.add(obj(f'Closed_{r}',active=False)); cards.board(closed,'Closed','closed.png',(x,4,7),(12,6))
            actions=[]; previous=0
            for k,(depart,duration) in enumerate(trips):
                actions += [act_wait(depart-previous),switch(signs[k],False),switch(signs[k+1] if k+1<len(signs) else closed)]
                previous=depart
            variant.add(obj(f'Timetable_{r}').logic(trig_enable(*actions)))
        selector=mod.add_prefab(obj(f'SelectSchedule_{v}').logic(trig_enable(switch(variant),act_kill(Targets.RECEIVER))))
        selectors.append(selector.guid)
    mod.add(obj('Director').logic(trig_round_start(act_spawn_prefab(selectors,Targets.ADVANCED,[anchor.transform_guid]))))
    return {'duration':60,'schedules':data['schedules'],'rewards':data['rewards'],'boarding_window':.12}


def run_traps(mod,cards,data):
    shared_world(mod,48,44,-15)
    restart=marker(mod,'CollectorReturn',0,-15)
    lanes=(-16,0,16); returns=[]; goals=[]
    for i,x in enumerate(lanes):
        blocked=[(x,5,4,20)]
        cube(mod,'RouteDivider',(x,1.5,5),(4,3,20),RUST)
        returns.append(marker(mod,f'TrapReturn_{i}',x-4,-8))
        goals.append((x-4,18))
        nav_grid(mod,x-4,x+4,-8,18,2,blocked)
        cards.board(mod,'PlatformSign',f'platform_{i}.png',(x,5,21),(12,6))
        cards.board(mod,'ControlSign','control.png',(x+4,2,-8),(5,2.5))
        floor_mark(mod,'ShortRoute',x-4,5,3,20,TEAL)
        floor_mark(mod,'LongRoute',x+4,5,3,20,YELLOW)
        hazard=mod.add(obj(f'Hazard_{i}',active=False))
        touch(hazard,f'ReturnHazard_{i}',(x-4.9,1,7),(5.8,3,3),place_player(returns[i]),one=False)
        warning=mod.add(obj(f'Warning_{i}',active=False)); floor_mark(warning,'WarningStrip',x-4.9,7,5.8,3,RED)
        sweep=hazard.add(obj('TrapArm',pos=(x-4,1,7)).simple_animator(anim_swing(2,80)))
        cube(sweep,'Arm',(0,0,0),(5.5,.2,.3),RED,solid=False)
        control=mod.add(obj(f'Control_{i}',pos=(x+4,1,-10)))
        control.trigger(size=(2.5,3,2.5),disable_after=True,on_enter=[switch(warning),act_wait(1.5),
            switch(warning,False),switch(hazard),act_wait(1),switch(hazard,False),act_wait(8),switch(control)])
        cube(control,'Button',(0,-.5,0),(2,.7,2),YELLOW,solid=False)
    nav_grid(mod,-22,22,-18,-10,2)
    nav_grid(mod,-22,22,16,20,2)
    obstacles=[(x,5,4,20) for x in lanes]+[(x,3.5,.4,21) for x in (-8,8)]
    for x in (-8,8): cube(mod,'LaneWall',(x,1.5,3.5),(.4,3,21),RUST)
    nodes=[o for o in mod.roots if any(c.type_name=='ModAINavigation' for c in o.components)]
    edges=[]
    for i,a in enumerate(nodes):
        for j,b in enumerate(nodes[:i]):
            if math.hypot(a.pos[0]-b.pos[0],a.pos[2]-b.pos[2])>3: continue
            if any(abs(a.pos[0]+(b.pos[0]-a.pos[0])*t/10-x)<w/2+.55 and
                   abs(a.pos[2]+(b.pos[2]-a.pos[2])*t/10-z)<d/2+.55
                   for t in range(11) for x,z,w,d in obstacles): continue
            edges += [(i,j),(j,i)]
    link_ai_nodes(nodes,edges)
    director=[act_wait(.5)]
    for n,lane in enumerate(data['sequence']):
        stage=mod.add(obj(f'Stage_{n}',active=False)); hint=stage.add(obj('NextHint')); prizegroup=stage.add(obj('Token',active=False))
        x,z=goals[lane]
        beacon=hint.add(obj('NextBeacon',pos=(x,3,z)).mover(rotation_axis_type=MoverAxis.Y,rotation_speed=80))
        cube(beacon,'Arrow',(0,0,0),(1.5,.5,1.5),YELLOW,solid=False)
        prize=touch(prizegroup,'Prize',(x,1,z),(3,3,3),[act_change_score(3)]+place_player(restart),consume=True)
        prize.add(obj('TokenVisual',scale=(1,1,1)).prop(PROP_SPHERE,tint=YELLOW,collision=Collision.NONE))
        stage.logic(trig_enable(act_show_message(f'NEXT PLATFORM {lane+1} / СЛЕДУЮЩАЯ ПЛОЩАДКА {lane+1}',1.5),
                               act_wait(2),switch(prizegroup),act_wait(7.5),switch(prizegroup,False)))
        director += [switch(stage),act_wait(9.5),switch(stage,False)]
    mod.add(obj('Director').logic(trig_round_start(*director)))
    return {'duration':57.5,'sequence':data['sequence'],'control_cycle':10.5,'hazard_duration':1}


BUILDERS={'broken-clock':run_clock,'emergency-exit':run_exit,'last-sale':run_sale,
          'closing-time':run_closing,'false-alarm':run_alarm,'trap-operators':run_traps}


def finish(mod,slug,here,workshop,report):
    out=Path(here).resolve().parent
    mod.add(obj('Playtest checklist').note('First prototype: test host/client boundaries, 4/6/8 players, readability, bots and repeated play.'))
    path=Path(mod.write(workshop))
    # These verified controller fields have no pmgen convenience wrapper.
    def tune():
        p=path/'Data/ModSettings.json'; settings=json.loads(p.read_text('utf-8'))
        if slug=='broken-clock': settings['SimpleMinigameSettings'].update(MusicVolume=0,AmbienceVolume=0)
        p.write_text(json.dumps(settings,indent=2,ensure_ascii=False),encoding='utf-8')
    tune()
    snapshot=ROOT/'local/finale-views'/slug; shutil.copytree(path,snapshot,dirs_exist_ok=True)
    scene=P.load(str(snapshot/'Data/MainScene.scene'))
    stage=scene.find('Stage_0') or scene.find('Schedule_0')
    if stage: stage.active=True
    for label in ('Prizes','MazePlay','Token'):
        found=stage.find(label) if stage else None
        if found: found.active=True
    if stage:
        for o in stage.walk():
            if o.name.startswith('ClockButton_0_') or o.name.startswith('Boarding_') and o.name.endswith('_0'): o.active=True
    P.save(scene,str(snapshot/'Data/MainScene.scene'))
    sys.path.insert(0,str(ROOT/'.claude/skills/pummel-party-level-design/scripts'))
    import plan_view
    with contextlib.redirect_stdout(io.StringIO()): plan_view.main([str(snapshot),'--out',str(out/'plan'),'--px','850'])
    plan_view.render_preview(str(snapshot),str(out/'plan/preview.png'))
    mod.preview_image=str(out/'plan/preview.png'); mod.write(workshop); tune()
    report.update(slug=slug,name=mod.name,objects=len(P.load(str(path/'Data/MainScene.scene')).objects()))
    (out/'BUILD.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return str(path)


def build(slug,here,name=None,workshop=WORKSHOP):
    mod,cards,data=new_mod(slug,name,top=slug in ('emergency-exit','trap-operators'))
    report=BUILDERS[slug](mod,cards,data)
    return finish(mod,slug,here,workshop,report)
