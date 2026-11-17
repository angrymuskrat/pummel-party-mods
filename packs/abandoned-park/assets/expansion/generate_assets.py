"""Deterministic puzzle cards and voxel props; stdlib only. Outputs live beside this script."""
from pathlib import Path
import json
import math
import random
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT/'.claude/skills/pummel-party-level-design/scripts'))
from plan_view import Canvas

FONT = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ', [
    '010101111101101','110101110101110','011100100100011','110101101101110',
    '111100110100111','111100110100100','011100101101011','101101111101101',
    '111010010010111','001001001101010','101101110101101','100100100100111',
    '101111111101101','101111111111101','010101101101010','110101110100100',
    '010101101111011','110101110101101','011100010001110','111010010010010',
    '101101101101111','101101101101010','101101111111101','101101010101101',
    '101101010010010','111001010100111']))
FONT.update(dict(zip('0123456789', ['111101101101111','010110010010111','111001111100111',
    '111001111001111','101101111001001','111100111001111','111100111101111',
    '111001001001001','111101111101111','111101111001111'])))
BG=(23,31,40); INK=(245,222,165); GOLD=(247,185,52); RED=(219,85,66); WHITE=(230,236,231)


def rect(c,x,y,w,h,color):
    for py in range(int(y),int(y+h)): c.span(py,int(x),int(x+w-1),color)


def text(c,word,x,y,scale=6,color=INK):
    for ch in word.upper():
        bits=FONT.get(ch,'0'*15)
        for i,b in enumerate(bits):
            if b=='1': rect(c,x+(i%3)*scale,y+(i//3)*scale,scale,scale,color)
        x+=4*scale


def centered(c,word,y,scale=6):
    text(c,word,(c.w-len(word)*4*scale)/2,y,scale)


def card(title,w=768,h=384):
    c=Canvas(w,h,BG)
    rect(c,4,4,w-8,6,GOLD); rect(c,4,h-10,w-8,6,GOLD)
    centered(c,title,20,6)
    return c


def icon(c,kind,x,y,s=1):
    r=int(24*s)
    if kind==0: # key
        c.circle((x-r,y),r*.7,GOLD, max(2,int(7*s)))
        c.line((x,y),(x+r*1.6,y),GOLD,max(2,int(8*s)))
        c.line((x+r,y),(x+r,y+r*.6),GOLD,max(2,int(7*s)))
    elif kind==1: # hat
        rect(c,x-r,y-r,r*2,r*1.5,RED); rect(c,x-r*1.5,y+r*.4,r*3,r*.3,WHITE)
    elif kind==2: # ticket
        rect(c,x-r*1.4,y-r,r*2.8,r*2,GOLD)
        for dx in (-1,1): c.disk((x+dx*r*1.4,y),r*.4,BG)
        c.line((x-r*.3,y-r*.7),(x-r*.3,y+r*.7),BG,max(2,int(3*s)))
    elif kind==3: # balloon
        c.disk((x,y-r*.3),r,RED); c.line((x,y+r*.7),(x-r*.3,y+r*1.8),WHITE,2)
    elif kind==4: # star, five clearly visible tips
        pts=[(x+math.sin(i*math.pi/5)*(r if i%2==0 else r*.4),
              y-math.cos(i*math.pi/5)*(r if i%2==0 else r*.4)) for i in range(10)]
        c.poly_outline(pts,GOLD,max(3,int(7*s)))


def draw_icon(c,kind,x,y,s=1):
    if kind==5:
        r=24*s; rect(c,x-r,y-r,r,r*2,WHITE); rect(c,x-r,y+r*.5,r*2.5,r*.5,WHITE)
    else: icon(c,kind,x,y,s)


def mascot(c,x,y,buttons,ears,flag=False,hat=False,scale=1):
    s=scale
    c.disk((x,y-20*s),24*s,GOLD)
    for dx in (-18,18):
        if ears=='round': c.disk((x+dx*s,y-43*s),11*s,GOLD)
        else: rect(c,x+(dx-7)*s,y-57*s,14*s,24*s,GOLD)
    rect(c,x-22*s,y+6*s,44*s,50*s,RED)
    for i in range(buttons): c.disk((x,y+(14+i*13)*s),3*s,WHITE)
    for dx in (-8,8): c.disk((x+dx*s,y-23*s),3*s,BG)
    if flag:
        c.line((x+36*s,y-55*s),(x+36*s,y+45*s),WHITE, max(2,int(3*s)))
        rect(c,x+36*s,y-55*s,24*s,18*s,WHITE)
    if hat: rect(c,x-23*s,y-65*s,46*s,12*s,WHITE)


def voxel_obj(path,cells):
    lines=[]; index=1
    for x,y,z in cells:
        for dx,dy,dz in ((0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)):
            # Importer reflects X; keep the in-game front view aligned with the card.
            lines.append(f'v {-(x+dx)*.55} {(y+dy)*.55} {(z+dz)*.55}')
        for face in ((0,3,2,1),(4,5,6,7),(0,4,7,3),(1,2,6,5),(3,7,6,2),(0,1,5,4)):
            lines.append('f '+' '.join(str(index+i) for i in reversed(face)))
        index+=8
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')


def generate_screen():
    # PummelOBJImporter reflects X (ModCreatedVersion >= 1) but leaves UV alone.
    # Compensate U on this symmetric plane; PNGs and puzzle coordinates stay unchanged.
    (HERE/'screen.obj').write_text('v -0.5 -0.5 0\nv -0.5 0.5 0\nv 0.5 0.5 0\nv 0.5 -0.5 0\nvt 1 0\nvt 1 1\nvt 0 1\nvt 0 0\nvn 0 0 -1\nf 1/1/1 2/2/1 3/3/1 4/4/1\n',encoding='utf-8')


def generate(slug):
    out=HERE/slug; out.mkdir(parents=True,exist_ok=True)
    generate_screen()
    for i in range(8):
        # One large number per physical answer sign; the title used to duplicate it.
        c=card('',128,128); centered(c,str(i),31,13); c.save(str(out/f'option_{i}.png'))
    for label in ('WAIT','CHOOSE','LOCKED','BUST','CASH 1','CASH 3','CASH 6'):
        c=card(label,512,128); c.save(str(out/(label.replace(' ','_')+'.png')))
    if slug=='boiler-jackpot':
        (out/'manifest.json').write_text(json.dumps({'slug':slug,'trials':4,'failure_window':[2,11],'tiers':[[0,1],[4,3],[8,6]]},indent=2))
        return json.loads((out/'manifest.json').read_text())
    if slug=='midnight-parade':
        for flag in (0,1):
            for hat in (0,1):
                c=Canvas(140,220,BG)
                mascot(c,60,115,2,'round',flag=flag,hat=hat,scale=1.2)
                c.save(str(out/f'figure_{flag}_{hat}.png'))
    rounds=6 if slug=='counterfeit-mascots' else 5
    tasks=[]
    for trial in range(rounds):
        for variant in range(4):
            rng=random.Random(f'{slug}:{trial}:{variant}:v1')
            stem=f't{trial}_v{variant}'
            task={'trial':trial,'variant':variant,'stem':stem,'options':list(range(1,5))}
            c=card('CHOOSE ONE')
            if slug=='lost-and-found':
                n=4 if trial<2 else 6
                layout=rng.sample(range(6),n); answer=rng.randrange(n)
                c=card('MEMORIZE')
                for i,kind in enumerate(layout):
                    x=384+(i-(n-1)/2)*112
                    rect(c,x-48,100,96,215,(47,58,66)); draw_icon(c,kind,x,195,1.25)
                    text(c,str(i+1),x-12,280,6)
                c.save(str(out/f'{stem}_study.png'))
                c=card('WHERE WAS THIS')
                draw_icon(c,layout[answer],384,215,2.5)
                task.update(options=list(range(1,n+1)),answer=answer,layout=layout,query=layout[answer])
            elif slug=='counterfeit-mascots':
                buttons=rng.choice([1,2,3]); ears=rng.choice(['round','square']); answer=rng.randrange(4)
                c=card('FIND THE FAKE'); text(c,'MODEL',12,93,4)
                rect(c,10,120,98,182,(35,46,57))
                mascot(c,59,210,buttons,ears,scale=1)
                difference='buttons' if (trial+variant)%2 else 'ears'
                for i in range(4):
                    b=(buttons%3)+1 if i==answer and difference=='buttons' else buttons
                    e=('square' if ears=='round' else 'round') if i==answer and difference=='ears' else ears
                    # 768 px across a 16 m board: x=168/312/456/600 maps to
                    # the unchanged answer-gate axes -4.5/-1.5/1.5/4.5 m.
                    # Numbers live on the foreground signs, not behind those signs too.
                    mascot(c,168+i*144,203,b,e,scale=1.3)
                task.update(answer=answer,buttons=buttons,ears=ears,difference=difference)
            elif slug=='shadow-theatre':
                # Columns have distinct heights; depth adds spatial structure without a second matching silhouette.
                heights=rng.sample(range(1,5),4)
                shapes=[]
                for i in range(4):
                    h=heights[i:]+heights[:i]
                    cells=[(x,y,0) for x,top in enumerate(h) for y in range(top)]
                    cells += [(0,0,1),(1,0,1)]
                    shapes.append(cells); voxel_obj(out/f'{stem}_shape_{i}.obj',cells)
                answer=rng.randrange(4); silhouette=sorted(set((x,y) for x,y,z in shapes[answer]))
                c=card('MATCH THE FRONT VIEW')
                for x,y in silhouette: rect(c,264+x*60,310-y*55,58,53,WHITE)
                task.update(answer=answer,shapes=shapes,silhouette=silhouette)
            elif slug=='midnight-parade':
                n=rng.randint(8,11); flags=set(rng.sample(range(n),rng.randint(2,7)))
                hats=set(rng.sample(range(n),rng.randint(2,5)))
                exclude_hat=trial>=3
                count=len(flags-hats if exclude_hat else flags)
                # Keep six fixed answer gates 0..5 or 2..7, ensuring answer and neighbours are represented.
                low=max(0,min(2,count-2)); opts=list(range(low,low+6))
                c=card('COUNT FLAGS NO HATS' if exclude_hat else 'COUNT THE FLAGS')
                task.update(options=opts,answer=opts.index(count),count=count,flags=sorted(flags),hats=sorted(hats),figures=n,exclude_hat=exclude_hat)
                # One strip travels behind a fixed aperture; each large figure crosses once.
                strip=Canvas(n*140,220,BG)
                for i in range(n): mascot(strip,i*140+60,115,2,'round',flag=i in flags,hat=i in hats,scale=1.2)
                strip.save(str(out/f'{stem}_parade.png'))
                c.save(str(out/f'{stem}_study.png'))
                c=card('HOW MANY')
            elif slug=='crossed-wires':
                order=list(range(4)); columns=[order[:]]
                for step in range(5):
                    order=rng.sample(order,4); columns.append(order[:])
                wire=rng.randrange(4); answer=columns[-1].index(wire)
                c=card('FOLLOW THE MARKED WIRE')
                colors=[GOLD]*4  # trace the route, not a unique colour at its endpoints
                for w in range(4):
                    segments=[]
                    for col in range(5):
                        p=(110+col*108,125+columns[col].index(w)*55)
                        q=(110+(col+1)*108,125+columns[col+1].index(w)*55)
                        segments.append((p,q))
                    # Outline the whole path before its fill, keeping its own joints continuous.
                    for p,q in segments: c.line(p,q,BG,14)
                    for p,q in segments: c.line(p,q,colors[w],6)
                for row,w in enumerate(columns[0]):
                    if w==wire: c.poly_outline([(55,115+row*55),(80,125+row*55),(55,135+row*55)],WHITE,5)
                for row in range(4): text(c,str(row+1),690,112+row*55,5)
                task.update(answer=answer,columns=columns,wire=wire)
            c.save(str(out/f'{stem}_question.png'))
            task['scores']=[(3 if i==task['answer'] else (1 if slug=='midnight-parade' and abs(v-task['count'])==1 else 0)) for i,v in enumerate(task['options'])]
            if slug=='counterfeit-mascots': task['scores']=[2 if i==task['answer'] else 0 for i in range(4)]
            tasks.append(task)
    manifest={'slug':slug,'trials':rounds,'variants_per_trial':4,'tasks':tasks}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    slugs=sys.argv[1:] or ['lost-and-found','counterfeit-mascots','shadow-theatre','midnight-parade','crossed-wires','boiler-jackpot']
    for slug in slugs:
        data=generate(slug)
        print(slug, data['trials'],'trials')
