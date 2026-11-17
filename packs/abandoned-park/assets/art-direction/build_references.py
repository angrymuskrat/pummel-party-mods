"""Build separate appearance references; original minigame names are never overwritten.

python packs/abandoned-park/assets/art-direction/build_references.py local/appearance-builds
"""
import importlib.util
import copy
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'packs/abandoned-park/minigames'))
from pmgen import *
from reserve_common import cube
from expansion_common import build_quiz, STATIONS
sys.path.insert(0,str(ROOT/'.claude/skills/pummel-party-level-design/scripts'))
import plan_view

REFERENCE_NAMES=('Rusted Park Art - Mascots','Rusted Park Art - Balloons','Rusted Park Text Check')


class Materials:
    def __init__(self,mod):
        self.mod=mod; self.catalog=json.loads((HERE/'materials.json').read_text()); self.textures={}; self.materials={}
        self.surface_cube=None

    def get(self,name,tiling=(1,1)):
        key=(name,tiling)
        if key not in self.materials:
            spec=self.catalog[name]
            if name not in self.textures:
                self.textures[name]=self.mod.add_file_asset('texture',str(HERE/spec['albedo']))
            suffix='_'.join(f'{v:g}' for v in tiling)
            self.materials[key]=self.mod.add_material(name+'_'+suffix,self.textures[name],
                smoothness=spec['smoothness'],metallic=spec['metallic'],tiling=tiling).guid
        return self.materials[key]

    def apply(self,ob,name):
        scale=sorted(ob.scale,reverse=True)
        tile=self.catalog[name]['tile_metres']
        mat=self.get(name,(round(max(1,scale[0]/tile),2),round(max(1,scale[1]/tile),2)))
        for comp in ob.components:
            if comp.type_name!='ModProp': continue
            if comp.prop('prop').raw==enc_ref(PROP_CUBE):
                if self.surface_cube is None:
                    self.surface_cube=self.mod.add_file_asset('prop',str(HERE/'surface_cube.obj'))
                comp.set('prop',enc_ref(self.surface_cube.guid))
            for prop in comp.props:
                if prop.name=='customMaterials': prop.raw=enc_ref_array([mat])
                elif prop.name=='tintColor': prop.raw=enc_color((1,1,1,1))


def walk(objects):
    for ob in objects:
        yield ob
        yield from walk(ob.children)


def checked_decoration(decorator):
    def apply(mod):
        roots=list(mod.roots)
        def mechanics():
            scene=copy.deepcopy(P.Scene(1,0,[o.to_gameobject() for o in roots]))
            for o in scene.objects():
                for c in o.components:
                    if c.type_name=='ModProp':
                        # Mesh, albedo/tint may change; collider and shadow settings must not.
                        c.props=[p for p in c.props if p.name not in ('prop','tintColor','customMaterials')]
            return P.serialize(scene)
        before=mechanics()
        decorator(mod)
        assert mechanics()==before, 'Appearance changed original gameplay or transforms'
    return apply


def distant_wheel(mod,pos,scale=1):
    back=mod.add(obj('ArtBackdropWheel',pos=pos,scale=(scale,)*3))
    for name,rotation in (('ferris_wheel_stand',False),('ferris_wheel_rotor',True)):
        model=mod.add_file_asset('prop',str(HERE.parent/'models'/f'{name}.obj'))
        part=back.add(obj(name).prop(model.guid,tint=(.39,.22,.17,1),collision=Collision.NONE))
        if rotation: part.mover(rotation_axis_type=MoverAxis.Z,rotation_speed=5)


def dress_mascots(mod):
    mod.lighting_profile=str(HERE/'lighting/neon-night.json')
    mats=Materials(mod)
    mapping={'Floor':'wet_asphalt','PrivacyWall':'paint_teal','BackWall':'paint_teal_heavy',
             'AnswerLockPartition':'paint_plum','ScreenWall':'paint_teal','Mast':'rust_iron'}
    for ob in walk(mod.roots):
        if ob.name in mapping: mats.apply(ob,mapping[ob.name])
    for i,(x,z) in enumerate(STATIONS):
        trim=mod.add(obj(f'ArtMarquee_{i}',pos=(x,0,z)))
        fascia=cube(trim,'WornMarquee',(0,10.6,9.8),(21,1.2,.3),solid=False)
        mats.apply(fascia,'paint_cream')
        for dx in (-9.6,9.6):
            pole=cube(trim,'SignFrame',(dx,5.5,9.8),(.35,10,.4),solid=False)
            mats.apply(pole,'rust_iron')
        # Neutral fill illuminates text; colored lights stay on the outer frame.
        trim.add(obj('CardFill',pos=(0,6,1)).light(color=(.88,.92,1,1),intensity=3,radius=16))
        trim.add(obj('VioletMarqueeLight',pos=(-8,9,8)).light(color=(.62,.28,1,1),intensity=1.2,radius=5))
        trim.add(obj('GreenServiceLight',pos=(8,9,8)).light(color=(.25,.85,.57,1),intensity=.8,radius=4))
        for j in range(9):
            cube(trim,'MarqueeBulb',(-8+j*2,10.6,9.5),(.18,.18,.18),(.92,.77,.45,1),solid=False)
    distant_wheel(mod,(0,15,74),2.5)


def dress_balloons(mod):
    mod.lighting_profile=str(HERE/'lighting/rust-dusk.json')
    mats=Materials(mod)
    mapping={'Fairground':'cracked_concrete','PrizeStall':'paint_red','StallRoof':'paint_cream',
             'Fence':'old_wood','Mast':'rust_iron'}
    for ob in walk(mod.roots):
        if ob.name in mapping: mats.apply(ob,mapping[ob.name])
    lamp=mod.add_file_asset('prop',str(HERE.parent/'models/lamppost.obj'))
    for x in (-12,12):
        for z in (-12,12):
            post=mod.add(obj('ArtLantern',pos=(x,0,z)))
            post.prop(lamp.guid,tint=(.28,.24,.19,1),collision=Collision.NONE)
            post.add(obj('WarmLamp',pos=(.9,4.7,0)).light(color=(1,.67,.36,1),intensity=1.6,radius=9))
    distant_wheel(mod,(0,9,30),1.5)


def text_check(destination):
    mod=Mod(REFERENCE_NAMES[2],round_duration=180,
            description='Text/UV diagnostic: LEFT is red, RIGHT is green; arrow points right. No score test.',
            settings_overrides={'canPunch':False,'canJump':False,'movementSpeed':6.,'respawnEnabled':True})
    mod.lighting_profile=str(HERE/'lighting/overcast-day.json')
    mats=Materials(mod)
    floor=cube(mod,'DiagnosticFloor',(0,-.5,-5),(30,1,30),ground=True)
    mats.apply(floor,'cracked_concrete')
    screen=mod.add_file_asset('prop',str(HERE.parent/'expansion/screen.obj'))
    tex=mod.add_file_asset('texture',str(HERE/'text-check.png'))
    material=mod.add_material('DiagnosticInk',tex,smoothness=0)
    mod.add(obj('ActualBoothSize',pos=(0,4.5,5),scale=(16,8,1)).prop(screen.guid,collision=Collision.NONE,materials=[material.guid],shadow=Shadow.OFF))
    mod.add(obj('FloorSign',pos=(0,.035,-12),rot=(90,0,0),scale=(8,4,1)).prop(screen.guid,collision=Collision.NONE,materials=[material.guid],shadow=Shadow.OFF))
    for i in range(8):
        mod.add(obj(f'Spawn_{i}',pos=((i-3.5)*1.5,1,-3)).player_spawn(shared=False,usage=SpawnUsage.BOTH))
    mod.add(obj('ReadabilityFill',pos=(0,6,1)).light(intensity=1,radius=15))
    out=mod.write(str(destination))
    plan_view.main([out,'--out',str(HERE/'references/text-check/plan'),'--px','850'])
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    destination=Path(sys.argv[1] if len(sys.argv)>1 else ROOT/'local/appearance-builds').resolve()
    refs=HERE/'references'
    build_quiz('counterfeit-mascots',REFERENCE_NAMES[0],str(ROOT/'packs/abandoned-park/minigames/counterfeit-mascots/build_mod.py'),
               str(destination),decorate=checked_decoration(dress_mascots),output_dir=refs/'mascots')
    spec=importlib.util.spec_from_file_location('balloon_reference',ROOT/'packs/abandoned-park/minigames/balloon-pop/build_mod.py')
    balloon=importlib.util.module_from_spec(spec); spec.loader.exec_module(balloon)
    balloon.build(REFERENCE_NAMES[1],str(destination),decorate=checked_decoration(dress_balloons),output_dir=refs/'balloons')
    text_check(destination)
    for report in refs.rglob('*.txt'):
        report.write_text(report.read_text(encoding='utf-8').replace(str(ROOT),'<repo>'),encoding='utf-8')
    print('Built: '+', '.join(REFERENCE_NAMES))


if __name__=='__main__': main()
