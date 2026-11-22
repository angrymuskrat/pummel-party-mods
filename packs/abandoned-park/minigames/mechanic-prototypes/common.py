"""Small shared asset/build helpers for the two isolated mechanic probes."""
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from reserve_common import *
from expansion_common import Cards, switch
sys.path.insert(0, str(ROOT / 'packs/abandoned-park/assets/art-direction'))
from build_references import Materials, distant_wheel

ASSETS = ROOT / 'packs/abandoned-park/assets/mechanic-prototypes'
ART = ROOT / 'packs/abandoned-park/assets/art-direction'
DEFAULT_OUTPUT = ROOT / 'local/mechanic-prototypes-ready'


class Signs(Cards):
    def __init__(self, mod):
        super().__init__(mod, 'counterfeit-mascots')
        self.folder = ASSETS


def painted(mats, parent, name, pos, size, material='paint_teal', **kw):
    ob = cube(parent, name, pos, size, **kw)
    mats.apply(ob, material)
    return ob


def complete(mod, source, destination, manifest):
    if (Path(destination) / mod.name).exists():
        raise FileExistsError('Choose an unused staging directory; existing editor projects are not overwritten.')
    path = finish(mod, source, mod.name, str(destination))
    folder = Path(source).resolve().parent
    # Reports are portable and have no ASCII-map trailing whitespace.
    report = folder / 'plan/plan.txt'
    report.write_text('\n'.join(line.rstrip() for line in report.read_text(encoding='utf-8')
                               .replace(str(ROOT), '<repo>').splitlines()) + '\n', encoding='utf-8')
    manifest.update(name=mod.name, runtime_status='pending user playtest')
    (folder / 'BUILD.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return path
