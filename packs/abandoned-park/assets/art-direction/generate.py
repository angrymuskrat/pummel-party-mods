"""Reproducible park materials, lighting presets and an asymmetric text test. Stdlib only."""
from pathlib import Path
import copy
import hashlib
import json
import math
import random
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from generate_textures import save_png, mix
sys.path.insert(0,str(HERE.parent/'expansion'))
from generate_assets import Canvas, rect, text, generate_screen

SIZE=512
MATERIALS={
    'paint_teal':       ((39,87,85), 'paint',  .25, .12, 310),
    'paint_red':        ((119,49,47),'paint',  .22, .12, 311),
    'paint_cream':      ((157,144,110),'paint',.2,  .10, 312),
    'paint_plum':       ((79,53,88), 'paint',  .23, .12, 313),
    'paint_teal_heavy': ((39,87,85), 'heavy',  .15, .22, 314),
    'paint_red_heavy':  ((119,49,47),'heavy',  .15, .22, 315),
    'rust_iron':        ((93,52,34), 'rust',   .17, .38, 316),
    'old_wood':         ((100,83,61),'wood',   .12, 0,   317),
    'cracked_concrete': ((101,109,105),'stone',.12, 0,   318),
    'wet_asphalt':      ((40,49,53),'asphalt', .58, 0,   319),
}


def periodic_noise(seed,cells):
    rng=random.Random(seed)
    grid=[[rng.random() for _ in range(cells)] for _ in range(cells)]
    def at(x,y):
        # Duplicated border: exactly matching opposing edges, including fine detail.
        u=x*cells/(SIZE-1); v=y*cells/(SIZE-1)
        ix=math.floor(u); iy=math.floor(v); fx=u-ix; fy=v-iy
        fx=fx*fx*(3-2*fx); fy=fy*fy*(3-2*fy)
        return ((grid[iy%cells][ix%cells]*(1-fx)+grid[iy%cells][(ix+1)%cells]*fx)*(1-fy)
                +(grid[(iy+1)%cells][ix%cells]*(1-fx)+grid[(iy+1)%cells][(ix+1)%cells]*fx)*fy)
    return at


def texture(base,kind,seed):
    broad=periodic_noise(seed,7); fine=periodic_noise(seed+1,36)
    grain=periodic_noise(seed+2,91)
    rng=random.Random(seed+3)
    crack_seeds=[(rng.random(),rng.random()) for _ in range(15)]
    rows=[]
    for y in range(SIZE):
        row=[]
        for x in range(SIZE):
            a=broad(x,y); b=fine(x,y); c=grain(x,y)
            variation=.74+.38*b+.13*c
            color=tuple(v*variation for v in base)
            if kind in ('paint','heavy'):
                edge=.34 if kind=='paint' else .49
                mask=.72*a+.28*b
                if mask<edge:
                    color=mix((41,35,31),(152,79,41),.2+.7*b)
                elif mask<edge+.024:
                    color=mix(color,(184,154,101),.55)
                drip=max(0,math.sin(x/(SIZE-1)*math.tau*17+.8*math.sin(y/(SIZE-1)*math.tau)))**20
                color=mix(color,(42,38,33),drip*.32)
            elif kind=='wood':
                line=abs(math.sin(x/(SIZE-1)*math.tau*42+.7*a+.16*math.sin(y/(SIZE-1)*math.tau)))
                color=mix((48,44,32),color,.5+.5*line)
                if abs(math.sin(x/(SIZE-1)*math.tau*2))<.025: color=(28,30,27)
            elif kind=='stone':
                u=(x/(SIZE-1)+.008*b)%1; v=(y/(SIZE-1)+.008*b)%1
                distances=sorted(min(abs(u-p),1-abs(u-p))**2+min(abs(v-q),1-abs(v-q))**2 for p,q in crack_seeds)
                crack=distances[1]-distances[0]
                if crack<.00045: color=(39,48,43)
                else: color=mix(color,(69,86,57),max(0,.39-a)*1.3)
            elif kind=='asphalt':
                color=mix(color,(55,72,77),max(0,a-.56)*1.5)
                if c>.78: color=mix(color,(131,128,105),.32)
            elif kind=='rust':
                color=mix((43,41,38),(150,76,37),.65*a+.35*b)
            row.append(tuple(max(0,min(255,round(v))) for v in color))
        rows.append(row)
    return rows


def rgba(rgb):
    return dict(zip(('r','g','b','a'),[round(x/255,6) for x in rgb]+[1.0]))


def lighting():
    # Actual ModLightingSettings schema, exported by Minimal Third Person.
    base=json.loads((HERE/'lighting_base.json').read_text(encoding='utf-8-sig'))
    # sky / horizon / ground / ambient sky / ambient equator / ambient ground / sun / fog / strength / fog span
    values={
        'neon-night': ((16,19,43),(57,43,76),(24,31,37),(90,102,139),(65,77,100),(36,43,56),(142,161,211),(48,47,70),.32,(55,170)),
        'overcast-day': ((98,117,128),(152,159,153),(63,72,66),(153,164,171),(120,132,137),(74,83,83),(202,213,216),(126,145,147),.52,(80,230)),
        'rust-dusk': ((48,44,69),(168,104,72),(48,43,40),(124,116,138),(100,94,104),(50,47,52),(238,165,113),(116,87,83),.56,(70,220)),
        'fog-night': ((21,31,40),(60,80,87),(29,42,44),(93,119,131),(66,89,99),(37,51,58),(145,181,194),(65,86,91),.35,(45,145)),
        'damp-service': ((32,46,49),(77,96,91),(31,44,43),(110,128,128),(77,101,100),(41,59,57),(179,199,185),(66,85,80),.42,(55,175)),
    }
    result={}
    for name,vals in values.items():
        p=copy.deepcopy(base)
        keys=('topColor','horizonColor','groundColor','ambientSkyColor','ambientEquatorColor','ambientGroundColor','globalLightColor','fogColor')
        p.update({key:rgba(value) for key,value in zip(keys,vals[:8])})
        p.update(presetName='Custom',stars=name=='neon-night',ambientMode=1,ambientIntensity=1.,
                 globalLightIntensity=vals[8],fog=True,fogMode=1,fogStartDistance=float(vals[9][0]),
                 fogEndDistance=float(vals[9][1]),haloStrength=.18,cloudShadows=True,cloudSpeed1=.025,
                 cloudSpeed2=.034,cloudIntensity=.24,cloudStrength=.35,cloudScale=140.,
                 reflectionIntensity=.35,globalShadowItensity=.65)
        p['globalLightRotation']={'x':145. if name=='rust-dusk' else 130.,'y':25.,'z':0.}
        result[name]=p
    return result


def diagnostic():
    c=Canvas(1024,512,(23,31,40))
    for x,color in ((0,(179,62,50)),(1008,(55,148,110))): rect(c,x,0,16,512,color)
    text(c,'LEFT  F R 2 5 7  RIGHT',55,35,10)
    text(c,'01234567',290,140,14)
    c.line((150,300),(850,300),(245,222,165),12)
    c.line((850,300),(780,255),(245,222,165),12)
    c.line((850,300),(780,345),(245,222,165),12)
    text(c,'F R 2 5 7',80,385,8)
    text(c,'F R 2 5 7',520,395,6)
    text(c,'F R 2 5 7',800,405,4)
    text(c,'40 PX',90,455,5); text(c,'30 PX',530,455,5); text(c,'20 PX',800,455,5)
    c.save(str(HERE/'text-check.png'))


def surface_cube():
    """Unit box with independent 0..1 UVs and outward normals on all six faces.

    LowPolyCube is useful for flat colors, but its UVs are not a supported
    texture contract. Keep identical bounds and use an explicit mesh for surfaces.
    """
    faces=[
        ((0,0,-1),[(-1,-1,-1),(-1,1,-1),(1,1,-1),(1,-1,-1)]),
        ((0,0,1),[(1,-1,1),(1,1,1),(-1,1,1),(-1,-1,1)]),
        ((-1,0,0),[(-1,-1,1),(-1,1,1),(-1,1,-1),(-1,-1,-1)]),
        ((1,0,0),[(1,-1,-1),(1,1,-1),(1,1,1),(1,-1,1)]),
        ((0,1,0),[(-1,1,-1),(-1,1,1),(1,1,1),(1,1,-1)]),
        ((0,-1,0),[(-1,-1,1),(-1,-1,-1),(1,-1,-1),(1,-1,1)]),
    ]
    lines=['# Unit box: six explicit UV islands. Not for readable text.']
    for normal,corners in faces:
        lines.extend('v '+' '.join(str(v*.5) for v in corner) for corner in corners)
    for _ in faces:
        lines.extend(('vt 0 0','vt 0 1','vt 1 1','vt 1 0'))
    lines.extend('vn '+' '.join(map(str,normal)) for normal,_ in faces)
    for i in range(len(faces)):
        lines.append('f '+' '.join(f'{i*4+j+1}/{i*4+j+1}/{i+1}' for j in range(4)))
    (HERE/'surface_cube.obj').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def generate():
    (HERE/'textures').mkdir(exist_ok=True)
    (HERE/'lighting').mkdir(exist_ok=True)
    sheet=Canvas(1280,1000,(20,25,29))
    text(sheet,'RUSTED PARK  MATERIAL STUDIES',32,24,7)
    catalog={}
    for i,(name,(base,kind,smoothness,metallic,seed)) in enumerate(MATERIALS.items()):
        pixels=texture(base,kind,seed)
        save_png(str(HERE/'textures'/f'{name}.png'),pixels)
        x=24+(i%5)*252; y=96+(i//5)*292
        for yy in range(224):
            for xx in range(224): sheet.px(x+xx,y+yy,pixels[yy*2][xx*2])
        text(sheet,name.replace('_',' '),x,y+236,3)
        catalog[name]={'albedo':f'textures/{name}.png','smoothness':smoothness,'metallic':metallic,
                       'tile_metres':4 if kind in ('stone','asphalt') else 2,'seed':seed}
    profiles=lighting()
    text(sheet,'LIGHTING PALETTES  NOT GAME SCREENSHOTS',24,700,5)
    for i,(name,profile) in enumerate(profiles.items()):
        x=24+i*252
        text(sheet,name.replace('-',' '),x,750,3)
        for j,key in enumerate(('topColor','horizonColor','ambientSkyColor','globalLightColor','fogColor')):
            color=tuple(round(profile[key][ch]*255) for ch in 'rgb')
            rect(sheet,x+j*44,785,44,100,color)
        (HERE/'lighting'/f'{name}.json').write_text(json.dumps(profile,indent=2)+'\n')
    text(sheet,'TEXTURE SCALE  2 M WALLS  4 M GROUND',24,930,5)
    sheet.save(str(HERE/'contact-sheet.png'))
    (HERE/'materials.json').write_text(json.dumps(catalog,indent=2)+'\n')
    diagnostic(); generate_screen(); surface_cube()
    outputs=sorted([*HERE.glob('textures/*.png'),*HERE.glob('lighting/*.json'),HERE/'text-check.png',HERE/'contact-sheet.png',HERE/'materials.json',HERE/'surface_cube.obj'])
    hashes={p.relative_to(HERE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in outputs}
    (HERE/'checksums.json').write_text(json.dumps(hashes,indent=2)+'\n')
    print(f'{len(catalog)} materials, {len(profiles)} lighting profiles, diagnostic card and contact sheet')


if __name__=='__main__': generate()
