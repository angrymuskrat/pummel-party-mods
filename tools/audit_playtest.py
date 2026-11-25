"""Read-only structural audit of the Rusted Park editor projects.

NAMES lists every game the pack has shipped; projects moved out of the
workshop folder (WorkshopMods_archive) are reported as skipped, not failed.
"""
from pathlib import Path
import hashlib, json, re, struct, sys, wave, zlib
import pmscene as P
import pmgen as G

NAMES=['Ticket Rush','Death Carousel','Coaster Run','Mascot Throne','Human Cannonball','Mascot Range','Sugar Rush','Tilt House','Searchlights','Bumper Cars','Ghost Train','Balloon Pop','Barrel Alley','Ferris Hold','Rusty Teacups','Lost & Found','Counterfeit Mascots','Shadow Theatre','Midnight Parade','Crossed Wires','Boiler Jackpot','Broken Clock','Emergency Exit','Last Sale','Closing Time','False Alarm','Trap Operators']
UUID=re.compile(rb'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}')

def asset_check(path):
    if path.suffix.lower()=='.png':
        raw=path.read_bytes(); assert raw[:8]==G.PNG_SIGNATURE,path
        offset=8; compressed=b''; ended=False
        while offset<len(raw):
            size=struct.unpack('>I',raw[offset:offset+4])[0]; kind=raw[offset+4:offset+8]
            data=raw[offset+8:offset+8+size]; crc=struct.unpack('>I',raw[offset+8+size:offset+12+size])[0]
            assert zlib.crc32(kind+data)&0xffffffff==crc,path
            if kind==b'IDAT': compressed+=data
            if kind==b'IEND': ended=True
            offset+=12+size
        assert ended and zlib.decompress(compressed),path
    elif path.suffix.lower()=='.wav':
        with wave.open(str(path),'rb') as f:
            assert f.getnframes()>0 and len(f.readframes(f.getnframes()))==f.getnframes()*f.getnchannels()*f.getsampwidth(),path
    elif path.suffix.lower()=='.obj':
        counts=[0,0,0]
        for line in path.read_text('utf-8-sig').splitlines():
            parts=line.split()
            if not parts: continue
            if parts[0] in ('v','vt','vn'): counts[('v','vt','vn').index(parts[0])]+=1
            elif parts[0]=='f':
                assert len(parts)>=4,path
                for token in parts[1:]:
                    for i,index in enumerate(token.split('/')):
                        if index: assert 0<abs(int(index))<=counts[i],(path,token)
        assert 0<counts[0]<=65535,path

def audit(folder, overlay=None):
    official=Path(G.GAME_TEMPLATES).parents[1]
    builtin={G.GUID_EMPTY,G.ASSET_LOCATION_EXTERNAL}|{v for k,v in vars(G).items() if k.startswith('PROP_')}
    for p in official.rglob('*'):
        if p.suffix in ('.scene','.pfab','.json','.pmeta'): builtin.update(v.decode() for v in UUID.findall(p.read_bytes()))
    results=[]
    for name in NAMES:
        root=overlay/name if overlay and (overlay/name).exists() else folder/name
        if not (root/'Data/MainScene.scene').exists(): continue
        errors=[]; warnings=[]; defs=[]; refs=set(); objects=[]
        for f in [root/'Data/MainScene.scene']+list(root.rglob('*.pfab')):
            s=P.load(str(f)); assert P.serialize(s)==f.read_bytes(),f
            if f.suffix=='.scene': objects=s.objects()
            for o in s.objects():
                defs.extend(c.guid for c in o.components)
                if o.component('ModLogic') and o.component('ModTrigger'): errors.append(f'Logic + Trigger: {f.name}/{o.name}')
                scale=struct.unpack('<fff',o.component('ModTransform').prop('scale').raw)
                if not all(0<v<=1000 for v in scale): errors.append('invalid scale: '+o.name)
                for c in o.components:
                    for p in c.props: refs.update(v.decode() for v in UUID.findall(p.raw))
        if len(defs)!=len(set(defs)): errors.append('duplicate component GUID')
        assets=set()
        for p in root.rglob('*.pmeta'):
            if not p.with_suffix('').exists(): errors.append('missing asset: '+p.name)
            meta=json.loads(p.read_text('utf-8-sig'))
            assets.add(meta['guid']['serializedGuid'])
            if isinstance(meta.get('m_shaderData'),list): refs.update(v.decode() for v in UUID.findall(bytes(meta['m_shaderData'])))
        for p in root.rglob('*.json'): json.loads(p.read_text('utf-8-sig'))
        for p in (root/'Assets').rglob('*'):
            if p.suffix.lower() in ('.png','.wav','.obj'): asset_check(p)
        settings=json.loads((root/'Data/ModSettings.json').read_text('utf-8-sig'))
        # Action references in settings are every bit as important as scene references.
        for entry in settings.get('references',{}).get('RefIds',[]): refs.update(v.decode() for v in UUID.findall(json.dumps(entry).encode()))
        missing=refs-set(defs)-assets-builtin
        if missing: errors.append('unresolved references: '+','.join(sorted(missing)))
        spawns=[o.component('ModPlayerSpawn') for o in objects if o.component('ModPlayerSpawn')]
        initial=[c for c in spawns if struct.unpack('<i',c.prop('SpawnUsageType').raw)[0]&1]
        if not any(c.prop('SharedSpawn').raw==b'\1' for c in initial) and len(initial)<8: errors.append('insufficient initial spawns')
        ps=settings['SimpleModPlayerSettings']; mg=settings['SimpleMinigameSettings']
        if ps.get('respawnEnabled') and not any(struct.unpack('<i',c.prop('SpawnUsageType').raw)[0]&2 for c in spawns): errors.append('respawn enabled without respawn spawn')
        if mg['NumberOfRounds']>1: warnings.append('multi-round state needs runtime verification')
        results.append(dict(name=name,objects=len(objects),prefabs=len(list(root.rglob('*.pfab'))),assets=len(assets),scene_sha256=hashlib.sha256((root/'Data/MainScene.scene').read_bytes()).hexdigest(),errors=errors,warnings=warnings))
    return results

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    folder=Path(sys.argv[1]) if len(sys.argv)>1 else Path.home()/'AppData/LocalLow/Rebuilt Games/Pummel Party/WorkshopMods'
    results=audit(folder)
    if len(sys.argv)>2: Path(sys.argv[2]).write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')
    for r in results: print(r['name'], 'FAIL' if r['errors'] else 'PASS', '; '.join(r['errors']+r['warnings']))
    audited={r['name'] for r in results}
    for name in NAMES:
        if name not in audited: print(name, 'SKIP', 'not in', folder)
    sys.exit(int(any(r['errors'] for r in results)))
