"""Prepared signs, schedules and a start chime for backlog entries 17–22 (stdlib)."""
from pathlib import Path
import json
import math
import random
import struct
import sys
import wave

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'expansion'))
from generate_assets import card, centered, rect, GOLD, WHITE, RED, BG, text, FONT
FONT['.']='000000000000010'

NAMES={'broken-clock':'Broken Clock','emergency-exit':'Emergency Exit','last-sale':'Last Sale',
       'closing-time':'Closing Time','false-alarm':'False Alarm','trap-operators':'Trap Operators'}
CLOCK=[4,6,5,7,4.5]
SIGNALS=[(True,0),(False,2),(True,1),(False,0),(False,1),(True,2),(True,0),(False,2),(True,1),(False,0)]
SCHEDULES=[
    [[(5,4),(14,4),(24,4),(34,4),(44,4),(54,4)],[(8,8),(23,8),(38,8),(53,8)],[(12,13),(32,13),(50,13)]],
    [[(6,4),(16,4),(26,4),(36,4),(46,4),(55,4)],[(10,8),(25,8),(40,8),(54,8)],[(8,13),(29,13),(48,13)]],
    [[(4,4),(13,4),(23,4),(33,4),(43,4),(53,4)],[(7,8),(22,8),(37,8),(51,8)],[(14,13),(34,13),(51,13)]]]


def sign(folder,name,lines):
    c=card(lines[0])
    for i,line in enumerate(lines[1:]):
        centered(c,line,105+i*64,min(8, max(3,170//max(1,len(line)))))
    c.save(str(folder/(name+'.png')))


def generate(slug):
    folder=HERE/slug; folder.mkdir(parents=True,exist_ok=True)
    sign(folder,'title',[NAMES[slug].upper(),'RUSTED PARK','ONE ROUND 60 SECONDS'])
    sign(folder,'wait',['WAIT','NEXT STAGE SOON'])
    if slug=='broken-clock':
        for n,t in enumerate(CLOCK): sign(folder,f'target_{n}',['REMEMBER THE INTERVAL',f'{t:g} SECONDS','HIT THE BUTTON ONCE'])
        sign(folder,'dark',['COUNT SILENTLY','HIT WHEN TIME IS UP'])
        sign(folder,'rules',['ONE HIT PER ATTEMPT','ERROR 0 TO 0.4   3 POINTS','0.9   2       1.5   1'])
        with wave.open(str(folder/'start.wav'),'wb') as f:
            f.setparams((1,2,22050,0,'NONE','not compressed'))
            f.writeframes(b''.join(struct.pack('<h',int(12000*math.sin(2*math.pi*660*i/22050)*(1-i/4410))) for i in range(4410)))
        data={'intervals':CLOCK,'bands':[[-1.5,-.9,1],[-.9,-.4,2],[-.4,.4,3],[.4,.9,2],[.9,1.5,1]]}
    elif slug=='false-alarm':
        words=['WHEEL','MASCOT','TICKET']
        for i,w in enumerate(words): sign(folder,f'sector_{i}',[w,'STAND INSIDE'])
        sign(folder,'home',['HOME','STOP MEANS STAY HERE'])
        for i,(go,target) in enumerate(SIGNALS):
            c=card('GO' if go else 'STOP')
            if go: c.poly_outline([(70,105),(140,145),(70,185)],(70,220,120),12)
            else: rect(c,70,110,70,70,RED)
            centered(c,words[target],135,12)
            centered(c,'DISTRACTION '+words[(target+1)%3],280,5)
            c.save(str(folder/f'command_{i}.png'))
        data={'signals':SIGNALS,'response_seconds':4.5}
    elif slug=='last-sale':
        offers=[]
        for i in range(5):
            row=[(2,5),(3,3),(8,1)]; random.Random(190+i).shuffle(row); offers.append(row)
            for j,(stock,value) in enumerate(row): sign(folder,f'offer_{i}_{j}',[f'SHOP {j+1}',f'{stock} PRIZES   {value} POINTS','ENTER TO COMMIT'])
        sign(folder,'locked',['CHOICE LOCKED','PRIZES OPEN AT THE SIGNAL','ONE PRIZE PER WAVE'])
        data={'offers':offers,'choice_seconds':5,'collect_seconds':5.5}
    elif slug=='closing-time':
        for v,rides in enumerate(SCHEDULES):
            for r,trips in enumerate(rides):
                for k,(depart,duration) in enumerate(trips):
                    more=trips[k+1][0] if k+1<len(trips) else 0
                    sign(folder,f'schedule_{v}_{r}_{k}',[f'RIDE {r+1}   {[2,4,7][r]} POINTS',f'TIMER {60-depart}   RIDE {duration} SEC',
                         'NO PAY AFTER CLOSING' if depart+duration>60 else f'NEXT TIMER {60-more}' if more else 'LAST DEPARTURE'])
        sign(folder,'closed',['CLOSED','NO MORE DEPARTURES'])
        data={'schedules':SCHEDULES,'rewards':[2,4,7]}
    elif slug=='emergency-exit':
        sign(folder,'rules',['FIND THE EXIT','EXIT 3   SIDE TOKEN 1','GATES OPEN AND CLOSE'])
        sign(folder,'exit',['EXIT','3 POINTS'])
        sign(folder,'token',['SIDE TOKEN','1 POINT'])
        data={'stages':3,'stage_seconds':19.5,'preview_seconds':2.5}
    else:
        for i in range(3): sign(folder,f'platform_{i}',[f'PLATFORM {i+1}','TOKEN 3 POINTS'])
        sign(folder,'control',['TRAP CONTROL','WARNING 1.5 SEC','COOLDOWN 8 SEC'])
        sign(folder,'rules',['PREDICT THE NEXT TOKEN','SHORT TRAP OR SAFE DETOUR','TRAPS NEVER GIVE POINTS'])
        data={'sequence':[0,2,1,0,2,1],'warning_seconds':1.5,'hazard_seconds':1,'cooldown_seconds':8}
    (folder/'manifest.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    return data


if __name__=='__main__':
    for slug in sys.argv[1:] or NAMES: generate(slug); print(slug)
