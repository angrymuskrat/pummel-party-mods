"""Build Counterfeit Mascots; optional arguments: mod name, WorkshopMods directory."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from expansion_common import WORKSHOP, build_quiz, build_boiler, run

def build(name='Counterfeit Mascots',workshop=WORKSHOP):
    return build_quiz('counterfeit-mascots',name,__file__,workshop)

if __name__=='__main__':
    run(build,'Counterfeit Mascots')
