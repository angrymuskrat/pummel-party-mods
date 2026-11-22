"""Stationary carnival consoles with a live miniature race beside every puzzle."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import *

NAME = 'Rusted Park Probe - Mascot Carts V3'
START, ROUND = 3., 70.
TRACK, BASE, BOOST, BRAKE = 5.6, .16, .21, -.08
PULSE, COOLDOWN = 1., 1.2
STATIONS = tuple(i*24 for i in range(8))
PALETTE = [RED, TEAL, YELLOW, (.40,.61,.93,1), (.76,.41,.88,1),
           (.96,.54,.23,1), (.48,.80,.31,1), (.93,.76,.74,1)]
TRACK_X, MAP_Z = 1.05, 6.85
TILES = [(-3.65,4.8),(-1.65,4.8),(-3.65,2.25),(-1.65,2.25)]
TILE_SIZE = (1.75, 2.28)


def row_y(lane):
    return 5.72 - .57*lane


def answer_gun(mod):
    visual = mod.add_prefab(obj('AnswerPointerVisual').prop(PROP_SNIPER, collision=Collision.NONE))
    info = copy.deepcopy(DEFAULT_WEAPON_INFO)
    info.update(weaponHitType=0, spawnBulletEffect=True, spawnTrailEffect=True, stunOnHit=False)
    info['basicInfo'] = {'cooldown': COOLDOWN, 'damage': 0}
    info['scanInfo'].update(weaponSpreadType=0, shotCount=1, range=14., hitOnce=True,
                            horizontalSpreadAngle={'x':0,'y':0}, verticalSpreadAngle={'x':0,'y':0})
    weapon = mod.add_prefab(obj('AnswerPointer').item(ItemType.WEAPON, visual.guid,
        weapon_type=WeaponUsage.GUN, weapon_info=info, cooldown=COOLDOWN, slot=ItemSlot.RIGHT_HAND,
        can_drop=False, disappear_when_dropped=True))
    mod.player_triggers['onFirstSpawnTrigger'] = [act_give_minigame_item(weapon.guid),
        act_modify_player_speed(0, flags=Targets.RECEIVER)]


def make_board(station, signs, mats, seat):
    painted(mats, station, 'ArcadeDeck', (0,-.25,.8), (16,.5,16), 'wet_asphalt', ground=True)
    painted(mats, station, 'QuestionCabinet', (-3.75,3.62,7.12), (6.15,6.3,.35), 'paint_teal')
    painted(mats, station, 'RaceCabinet', (3.75,3.65,7.12), (8,6.3,.35), 'old_wood')
    signs.board(station, 'YourLane', f'race_{seat+1}.png', (3.76,6.52,MAP_Z), (4.8,.94))
    for lane, color in enumerate(PALETTE):
        y = row_y(lane)
        cube(station, 'Groove', (TRACK_X+TRACK/2,y,MAP_Z), (TRACK+.4,.10,.14),
             YELLOW if lane==seat else (.52,.43,.33,1), solid=False)
        for j in range(5):
            cube(station,'Tie',(TRACK_X+j*TRACK/4,y,MAP_Z-.07),(.07,.16,.08),color,solid=False)
        cube(station,'LaneColour',(.53,y+.1,MAP_Z),(.32,.27,.15),color,solid=False)
    cube(station,'FinishLine',(TRACK_X+TRACK,3.95,MAP_Z+.08),(.10,4.7,.12),YELLOW,solid=False)
    station.add(obj('CabinetLight',pos=(0,5,2)).light(intensity=2,radius=16))


def build(destination=DEFAULT_OUTPUT):
    deck = json.loads((ASSETS/'arcade_deck.json').read_text())
    mod = Mod(NAME, round_duration=ROUND, placement=Placement.FINISH_ORDER,
        end_conditions=EndCondition.TIMER | EndCondition.FINISH,
        description='Shoot the odd toy. Watch your numbered lane on the race board. / Стреляй в игрушку, отличающуюся от образца. На табло справа твоя дорожка подсвечена. Верно — разгон, ошибка — торможение.',
        settings_overrides={'canPunch':False,'canJump':False,'respawnEnabled':False,'useHealth':False,
                            'showNameTags':False})
    mod.lighting_profile = str(ART/'lighting/overcast-day.json')
    mats, signs = Materials(mod), Signs(mod)
    answer_gun(mod)
    toy = mod.add_file_asset('prop', str(ROOT/'packs/abandoned-park/assets/models/mascot_target.obj'))
    trials = []
    for lane, z in enumerate(STATIONS):
        station = mod.add(obj(f'Station_{lane}', pos=(0,0,z)))
        make_board(station, signs, mats, lane)
        station.add(obj(f'Spawn_{lane}',pos=(0,.3,-2)).player_spawn(shared=False,
            usage=SpawnUsage.INITIAL, allowed_players=1<<lane, advanced=True))
        # One moving parent drives the same runner on every board.
        cruise = mod.add(obj(f'Cruise_{lane}'))
        delta = cruise.add(obj(f'Offset_{lane}'))
        moving = delta.add(obj(f'Racing_{lane}',active=False))
        parked = mod.add(obj(f'Parked_{lane}',active=False))
        for viewer, view_z in enumerate(STATIONS):
            for group, offset in ((moving,0),(parked,TRACK)):
                group.add(obj(f'Toy_{lane}_At_{viewer}',pos=(TRACK_X+offset,row_y(lane)+.02,view_z+MAP_Z-.25),
                              scale=(.39,.32,.42)).prop(toy.guid,tint=PALETTE[lane],collision=Collision.NONE))
        cruise.logic(trig_round_start(act_wait(START),act_play_tween([cruise.transform_guid],
                    end=(BASE*(ROUND-START),0,0),seconds=ROUND-START)))
        # Presence enables only occupied lanes, including riders who never answer.
        station.add(obj('RegisterSeat',pos=(0,1,-2)).trigger(size=(2.5,4,2.5),
            on_enter=[switch(moving)],on_stay=[switch(moving)],one_use_per_player=True))
        play = station.add(obj('PuzzlePanel'))
        finished = station.add(obj('Finished', active=False))
        signs.board(finished,'FinishBanner','finish.png',(-3.8,3.75,6.8),(4,1.5))
        # The player's avatar stays at its console. A gate on the runner touches that
        # same avatar at the end of the lane, preserving the native finish-order event.
        gate = moving.add(obj(f'FinishSensor_{lane}',pos=(-TRACK-.85,1,z-2)))
        done = [act_set_placement(),switch(parked),switch(finished),switch(play,False),switch(moving,False)]
        gate.trigger(size=(.9,4,1.8),on_enter=done,on_stay=done,one_use_per_player=True)
        readout = {}
        for pick in range(4):
            for key in range(4):
                lamp = play.add(obj(f'Pick{pick+1}_Key{key+1}',active=False))
                signs.board(lamp,'Receipt',f'result_{pick+1}_{key+1}.png',(-3.75,6.62,6.85),(4.0,1.1))
                readout[pick,key] = lamp
        clear = act_set_active(ActiveState.DISABLED,[o.transform_guid for o in readout.values()])
        questions=[play.add(obj(f'Question_{lane}_{i}',active=False)) for i in range(len(deck))]
        for i,(task,q) in enumerate(zip(deck,questions)):
            following = questions[(i+1)%len(deck)]
            differing = [j for j,tile in enumerate(task['choices']) if tile!=task['model']]
            key, = differing
            signs.board(q,'Model',task['model']+'_MODEL.png',(-5.73,3.55,6.83),TILE_SIZE)
            buttons=[]
            for j,((x,y), tile) in enumerate(zip(TILES,task['choices'])):
                target=q.add(obj(f'Answer_{j+1}',pos=(x,y,6.75)))
                target.trigger(size=(*TILE_SIZE,.15),on_hit=[
                    act_play_tween([delta.transform_guid],end=(BOOST if j==key else BRAKE,0,0),seconds=PULSE),
                    clear,switch(readout[j,key]),switch(following),switch(q,False)])
                signs.board(target,'Tile',f'{tile}_{j+1}.png',(0,0,-.08),TILE_SIZE)
                buttons.append(target.transform_guid)
            trials.append(dict(lane=lane,trial=i,answer=key,buttons=buttons,question=q.transform_guid,
                               next=following.transform_guid,offset=delta.transform_guid))
        station.logic(trig_round_start(act_wait(START),switch(questions[0])))
    scenery(mod,20,102,84)
    distant_wheel(mod,(19,3,100),1.7)
    return complete(mod,__file__,destination,dict(kind='tabletop_race',trials=trials,
        stations=STATIONS, start=START, round_seconds=ROUND, track=TRACK,base=BASE,boost=BOOST,
        brake=BRAKE,pulse=PULSE,cooldown=COOLDOWN))

if __name__=='__main__':
    print(build(Path(sys.argv[1]) if len(sys.argv)>1 else DEFAULT_OUTPUT))
