from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from finale_common import build, WORKSHOP
if __name__=='__main__':
    print(build('emergency-exit',__file__,sys.argv[1] if len(sys.argv)>1 else None,sys.argv[2] if len(sys.argv)>2 else WORKSHOP))
