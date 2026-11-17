"""Private answer booths and timed trials for the first six expansion prototypes."""
from pathlib import Path
import contextlib
import io
import json
import shutil
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from reserve_common import ROOT, WORKSHOP, cube, scenery, RUST, RED, YELLOW, TEAL
sys.path.insert(0,str(ROOT/'tools'))
from pmgen import *
sys.path.insert(0,str(ROOT/'packs/abandoned-park/assets/expansion'))
from generate_assets import generate, HERE as ASSET_ROOT

STATIONS=[(x,z) for z in (-20,20) for x in (-36,-12,12,36)]


def switch(group,on=True):
    return act_set_active(ActiveState.ENABLED if on else ActiveState.DISABLED,[group.transform_guid])


def place_player(marker,multiplier=1):
    return [act_modify_player_speed(0),act_match_transform(marker.transform_guid,flags=Targets.SOURCE),
            act_change_velocity(0,VelocityDir.CUSTOM,Op.SET),act_modify_player_speed(multiplier)]


class Cards:
    def __init__(self,mod,slug):
        self.mod=mod; self.folder=ASSET_ROOT/slug; self.materials={}; self.models={}
        self.screen=mod.add_file_asset('prop',str(ASSET_ROOT/'screen.obj')).guid

    def board(self,parent,name,file,pos=(0,4.5,5),size=(16,8)):
        if file not in self.materials:
            tex=self.mod.add_file_asset('texture',str(self.folder/file))
            self.materials[file]=self.mod.add_material(Path(file).stem,tex,smoothness=0).guid
        return parent.add(obj(name,pos=pos,scale=(size[0],size[1],1)).prop(
            self.screen,collision=Collision.NONE,materials=[self.materials[file]],shadow=Shadow.OFF))

    def model(self,file):
        if file not in self.models: self.models[file]=self.mod.add_file_asset('prop',str(self.folder/file)).guid
        return self.models[file]


def make_world(name,description,slug):
    mod=Mod(name,description=description,round_duration=60,placement=Placement.MOST_POINTS,
        settings_overrides={'canPunch':False,'canJump':False,'respawnEnabled':False,'useHealth':False,
                            'movementSpeed':6.0,'playerGravity':25.0,'showNameTags':False})
    cards=Cards(mod,slug)
    starts=[]
    for i,(x,z) in enumerate(STATIONS):
        room=mod.add(obj(f'Booth_{i}',pos=(x,0,z)))
        cube(room,'Floor',(0,-.4,-7.5),(21,.8,36),TEAL,ground=True)
        for sx in (-10.5,10.5): cube(room,'PrivacyWall',(sx,5,-7.5),(.4,10,36),RUST)
        cube(room,'BackWall',(0,5,-25.5),(21,10,.4),RUST)
        cube(room,'AnswerLockPartition',(0,5,-13),(21,10,.4),RUST)
        cube(room,'ScreenWall',(0,5,10.5),(21,10,.4),RUST)
        cube(room,'StageTrim',(0,.03,3),(20,.06,.2),YELLOW,solid=False)
        cube(room,'WaitMark',(0,.03,-18),(18,.06,1),YELLOW,solid=False)
        cards.board(room,'WaitingNotice','LOCKED.png',(0,2,-14),(8,2))
        start=mod.add(obj(f'Start_{i}',pos=(x,.15,z-3)))
        starts.append(start)
        mod.add(obj(f'Spawn_{i}',pos=(x,1,z-3)).player_spawn(shared=False,usage=SpawnUsage.INITIAL))
    scenery(mod,58,50,-7.5)
    return mod,cards,starts


def reset_group(mod,trial,starts):
    group=mod.add(obj(f'Reset_{trial}',active=False))
    for i,((x,z),start) in enumerate(zip(STATIONS,starts)):
        group.add(obj(f'ResetPlayer_{i}',pos=(x,2,z-7.5)).trigger(size=(20,5,35),
            on_stay=place_player(start),stay_interval=.05,one_use_per_player=True))
    return group


def add_question(cards,parent,task,slug):
    study=parent.add(obj('Study',active=slug in ('lost-and-found','midnight-parade')))
    question=parent.add(obj('Question',active=slug not in ('lost-and-found','midnight-parade')))
    if slug in ('lost-and-found','midnight-parade'):
        cards.board(study,'StudyCard',task['stem']+'_study.png')
    cards.board(question,'QuestionCard',task['stem']+'_question.png')
    if slug=='shadow-theatre':
        # Front-view reference is above four genuinely three-dimensional turning objects.
        question.children[0].pos=(0,6.6,6)
        question.children[0].scale=(10,5,1)
        for i in range(4):
            pivot=question.add(obj(f'ShapePivot_{i}',pos=((i-1.5)*3,1.5,4))
                              .simple_animator(anim_rotate_around_axis(1/8)))
            pivot.add(obj('Shape',pos=(-1.1,0,-.55)).prop(cards.model(f"{task['stem']}_shape_{i}.obj"),
                       tint=YELLOW,collision=Collision.NONE))
    if slug=='midnight-parade':
        # Separate figures stay within this booth; a long strip would protrude into its neighbour.
        cards.board(study,'ParadeInstructions',task['stem']+'_study.png',(0,7,6),(16,4))
        study.children[0].active=False
        for i in range(task['figures']):
            mover=study.add(obj(f'ParadeFigure_{i}',pos=(-3,2.5,4)))
            visual=cards.board(mover,'Figure',f'figure_{int(i in task["flags"])}_{int(i in task["hats"])}.png',
                               (0,0,0),(2.2,3.45))
            visual.active=False
            delay=i*5/(task['figures']-1)
            mover.logic(trig_enable(act_wait(delay),switch(visual),
                act_play_tween([mover.transform_guid],Tween.LOCAL_POSITION,end=(6,0,0),seconds=.8),
                act_wait(.8),switch(visual,False)))
        for sx in (-6,6): cube(study,'Curtain',(sx,2.5,3.8),(9.6,4,.2),(.07,.1,.13,1),solid=False)
    return study,question


def build_quiz(slug,name,here,workshop=WORKSHOP,decorate=None,output_dir=None):
    data=generate(slug)
    mod,cards,starts=make_world(name,
        f'Rusted Park: {name}. Walk into a numbered gate to lock one answer. Wait for the result. No speed bonus.',slug)
    reveal=4 if slug=='lost-and-found' else 6 if slug=='midnight-parade' else 0
    answer_time=6 if slug=='lost-and-found' else 4.5 if slug=='midnight-parade' else 8.5 if slug=='counterfeit-mascots' else 10.5
    duration=reveal+answer_time+.6+.2
    director=[act_wait(1)]
    anchor=mod.add(obj('DrawAnchor',pos=(0,-50,0)))
    manifest={'slug':slug,'name':name,'trials':data['trials'],'reveal':reveal,'answer_time':answer_time,
              'total_duration':1+data['trials']*(.4+duration),'trial_variants':[]}
    for trial in range(data['trials']):
        reset=reset_group(mod,trial,starts)
        variants=mod.add(obj(f'Trial_{trial}',active=False))
        selectors=[]
        for task in [t for t in data['tasks'] if t['trial']==trial]:
            variant=variants.add(obj(f'Variant_{task["variant"]}',active=False))
            answers=variant.add(obj('AnswerGates',active=False))
            scores=variant.add(obj('DelayedScores',active=False))
            studies=[]; questions=[]
            n=len(task['options'])
            for station,(x,z) in enumerate(STATIONS):
                display=variant.add(obj(f'Display_{station}',pos=(x,0,z)))
                study,question=add_question(cards,display,task,slug)
                studies.append(study); questions.append(question)
                for j,value in enumerate(task['options']):
                    dx=(j-(n-1)/2)*3
                    cards.board(display,f'Option_{j}',f'option_{value}.png',(dx,1.3,1.4),(1.7,1.7))
                    marker=mod.add(obj(f'Locked_{trial}_{task["variant"]}_{station}_{j}',pos=(x+dx,.15,z-18)))
                    answers.add(obj(f'Answer_{station}_{j}',pos=(x+dx,1,z)).trigger(size=(2,2,.9),
                        on_enter=place_player(marker,0),on_stay=place_player(marker,0),
                        stay_interval=.05,one_use_per_player=True))
                    if task['scores'][j]:
                        scores.add(obj(f'Score_{station}_{j}',pos=(x+dx,1,z-18)).trigger(size=(2,3,2),
                            on_stay=[act_change_score(task['scores'][j])],stay_interval=.05,one_use_per_player=True))
            actions=[]
            if reveal:
                instruction=('WATCH / ЗАПОМИНАЙ' if slug=='lost-and-found' else
                             'FLAGS WITHOUT HATS / ФЛАЖКИ БЕЗ ШЛЯП' if task.get('exclude_hat') else
                             'COUNT THE FLAGS / СЧИТАЙ ФЛАЖКИ')
                actions += [act_show_message(instruction,2),act_wait(reveal)]
                actions += [switch(g,False) for g in studies]+[switch(g) for g in questions]
            actions += [switch(answers)]
            # The permanent FIND THE FAKE heading already gives this instruction.
            # A central HUD message masks buttons/ears during the open answer window.
            if slug!='counterfeit-mascots':
                actions += [act_show_message('CHOOSE ONE / ВЫБЕРИ ОДИН ОТВЕТ',1.5)]
            actions += [act_wait(answer_time),
                        switch(answers,False),switch(scores),act_wait(.2),
                        act_show_message(f'Answer / Ответ: {task["options"][task["answer"]]}',.6),
                        act_wait(.4),switch(variant,False)]
            variant.logic(trig_enable(*actions))
            selector=mod.add_prefab(obj(f'Select_{trial}_{task["variant"]}').logic(trig_enable(
                switch(variant),act_kill(Targets.RECEIVER))))
            selectors.append(selector.guid)
            manifest['trial_variants'].append({'trial':trial,'variant':task['variant'],'scores':task['scores'],
                'options':task['options'],'selector':selector.guid,'variant_transform':variant.transform_guid,
                'answer_group':answers.transform_guid,'score_group':scores.transform_guid})
        director += [switch(reset),act_wait(.4),switch(reset,False),switch(variants),
                     act_spawn_prefab(selectors,Targets.ADVANCED,[anchor.transform_guid]),act_wait(duration),switch(variants,False)]
    mod.add(obj('Director').logic(trig_round_start(*director)))
    assert manifest['total_duration']<60
    if decorate:
        decorate(mod)
    return finish_expansion(mod,here,workshop,manifest,output_dir=output_dir)


def build_boiler(name,here,workshop=WORKSHOP):
    slug='boiler-jackpot'; data=generate(slug)
    mod,cards,starts=make_world(name,
        'Boiler Jackpot / Котёл удачи: cash 1 now, 3 after four seconds or 6 after eight. Failure is random between 2 and 11 seconds. Four attempts.',slug)
    director=[act_wait(1)]
    for trial in range(4):
        reset=reset_group(mod,trial,starts)
        stage=mod.add(obj(f'Attempt_{trial}',active=False))
        bank=stage.add(obj('CashBank'))
        bust=stage.add(obj('BustNotice',active=False))
        tiers=[]
        latches=[bank.add(obj(f'CashLatch_{i}')) for i in range(8)]
        gates=[[],[],[]]
        for tier,value in enumerate((1,3,6)):
            group=bank.add(obj(f'Cash_{value}',active=tier==0)); tiers.append(group)
            for i,(x,z) in enumerate(STATIONS):
                board=group.add(obj(f'Board_{i}',pos=(x,0,z)))
                cards.board(board,'Reward',f'CASH_{value}.png',(0,4.5,5),(14,3.5))
                locked=mod.add(obj(f'CashWait_{trial}_{tier}_{i}',pos=(x,.15,z-18)))
                actions=[switch(latches[i],False),act_change_score(value)]+place_player(locked,0)
                gate=latches[i].add(obj(f'CashOut_{tier}_{i}',pos=(x,1,z),active=tier==0).trigger(size=(3,2,1),
                    on_enter=actions,on_stay=actions,disable_after=True,
                    stay_interval=.05,one_use_per_player=True))
                gates[tier].append(gate)
        for i,(x,z) in enumerate(STATIONS):
            board=bust.add(obj(f'Bust_{i}',pos=(x,0,z)))
            cards.board(board,'Bust','BUST.png',(0,4.5,5),(14,3.5))
            # The boiler is scenery, outside the walk-to-cashout route.
            boiler=stage.add(obj(f'Boiler_{i}',pos=(x,1,z+7)))
            boiler.add(obj('Tank',scale=(4,4,3)).prop(PROP_SPHERE,tint=RUST,collision=Collision.NONE))
            rotor=boiler.add(obj('PressureNeedle',pos=(0,3,-1.7)).simple_animator(anim_swing(1/3,65)))
            cube(rotor,'Needle',(0,.4,0),(.15,1,.15),YELLOW,solid=False)
        stage.logic(trig_enable(act_show_message('CASH OUT BEFORE THE FAILURE / ЗАБЕРИ ПРИЗ ДО АВАРИИ',2),
            act_wait(4),switch(tiers[0],False),*[switch(g,False) for g in gates[0]],
            switch(tiers[1]),*[switch(g) for g in gates[1]],
            act_wait(4),switch(tiers[1],False),*[switch(g,False) for g in gates[1]],
            switch(tiers[2]),*[switch(g) for g in gates[2]]))
        # Disabling the parent bank prevents a later tier action reopening cashout after failure.
        stage.add(obj('FailureClock').logic(trig_enable(act_wait(2,11),switch(bank,False),switch(bust))))
        director += [switch(reset),act_wait(.4),switch(reset,False),switch(stage),act_wait(13.6),switch(stage,False)]
    mod.add(obj('Director').logic(trig_round_start(*director)))
    return finish_expansion(mod,here,workshop,{'slug':slug,'name':name,'trials':4,'total_duration':57,'tiers':data['tiers'],'failure_window':[2,11]})


def finish_expansion(mod,here,workshop,manifest,output_dir=None):
    out=Path(output_dir) if output_dir else Path(here).resolve().parent
    out.mkdir(parents=True,exist_ok=True)
    mod.add(obj('Read before playtest').note('Prototype: verify random prefab selector, answer lock, deferred scoring and private camera in multiplayer. Bots do not solve puzzles.'))
    path=mod.write(workshop)
    render_layout(path,out)
    mod.preview_image=str(out/'plan/preview.png')
    mod.write(workshop)
    (out/'BUILD.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return path


def render_layout(path,out):
    """Render a first-question snapshot; shipped scenes retain their timed activation states."""
    sys.path.insert(0,str(ROOT/'.claude/skills/pummel-party-level-design/scripts'))
    import plan_view
    snapshot=ROOT/'local/expansion-views'/out.name
    shutil.copytree(path,snapshot,dirs_exist_ok=True)
    scene=P.load(str(snapshot/'Data/MainScene.scene'))
    trial=scene.find('Trial_0') or scene.find('Attempt_0')
    trial.active=True
    if trial.find('Variant_0'):
        trial.find('Variant_0').active=True
        trial.find('Variant_0').find('AnswerGates').active=True
    P.save(scene,str(snapshot/'Data/MainScene.scene'))
    with contextlib.redirect_stdout(io.StringIO()): plan_view.main([str(snapshot),'--out',str(out/'plan'),'--px','850'])
    plan_view.render_preview(str(snapshot),str(out/'plan/preview.png'))
    things=plan_view.collect(scene,plan_view.ModFiles(str(snapshot)))
    mg,ps=plan_view.read_settings(str(snapshot))
    an=plan_view.analyse(things,mg,ps,4)
    x,z=STATIONS[0]
    plan_view.draw_plan(things,an,plan_view.View(x-11,x+11,z-26,z+11,20),str(out/'plan/plan_booth.png'))
    report=out/'plan/plan.txt'
    report.write_text(report.read_text('utf-8')+'\nКадр проверки: первый вариант первого этапа с видимыми зонами выбора. В поставляемой сцене этап включается Director во время раунда.\n',encoding='utf-8')


def run(build,name):
    print(build(sys.argv[1] if len(sys.argv)>1 else name,sys.argv[2] if len(sys.argv)>2 else WORKSHOP))
