"""Reproducible signs and three mascot puzzles for the mechanic probes (stdlib)."""
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'expansion'))
from generate_assets import card, rect, text, centered, mascot, INK, GOLD, RED, WHITE


def make_arcade_tiles(tasks):
    """One physical target per picture. Its filename records exactly what was drawn."""
    deck = []
    for task in tasks:
        ears, buttons = task['ears'], task['buttons']
        model = f'{ears}_{buttons}'
        choices = [model]*4
        different = ('square' if ears=='round' else 'round', buttons) if task['difference']=='ears' else (ears, buttons%3+1)
        choices[task['answer']] = f'{different[0]}_{different[1]}'
        deck.append(dict(model=model, choices=choices))
    for ears in ('round', 'square'):
        for buttons in (1, 2, 3):
            for label in ('MODEL','1','2','3','4'):
                c = card('', 180, 240)
                mascot(c, 90, 104, buttons, ears, scale=1.5)
                for i in range(buttons):
                    c.disk((90, 104+(14+i*13)*1.5), 7, WHITE)
                centered(c, label, 198, 6)
                c.save(str(HERE / f'{ears}_{buttons}_{label}.png'))
    for pick in range(1,5):
        for key in range(1,5):
            c = card('', 400, 110)
            rect(c, 7, 8, 386, 94, (28,83,65) if pick==key else (114,48,44))
            centered(c, f'PICK {pick}   FAKE {key}', 19, 5)
            centered(c, 'BOOST' if pick==key else 'BRAKE', 62, 5)
            c.save(str(HERE / f'result_{pick}_{key}.png'))
    for seat in range(1,9):
        c = card('', 420, 98)
        centered(c, f'TOY RACE   YOU {seat}', 28, 6)
        c.save(str(HERE / f'race_{seat}.png'))
    (HERE / 'arcade_deck.json').write_text(json.dumps(deck, indent=2)+'\n', encoding='utf-8')


def generate():
    source = json.loads((HERE.parent / 'expansion/counterfeit-mascots/manifest.json').read_text())
    tasks = source['tasks']
    make_arcade_tiles(tasks)
    for i, task in enumerate(tasks):
        c = card('FIND THE FAKE')
        text(c, 'MODEL', 12, 93, 4)
        rect(c, 10, 120, 98, 220, (35, 46, 57))
        specs = [(59, 210, 1, task['buttons'], task['ears'])]
        for j in range(4):
            buttons, ears = task['buttons'], task['ears']
            if j == task['answer']:
                if task['difference'] == 'buttons': buttons = buttons % 3 + 1
                else: ears = 'square' if ears == 'round' else 'round'
            specs.append((168 + j * 144, 203, 1.3, buttons, ears))
        for x, y, s, buttons, ears in specs:
            mascot(c, x, y, buttons, ears, scale=s)
            # Identical costume detail on every figure; ears/buttons remain the only difference.
            for dx in (-17, 17):
                rect(c, x + (dx-5)*s, y+56*s, 10*s, 13*s, (113, 76, 49))
            c.line((x-10*s, y-7*s), (x+10*s, y-7*s), (32, 39, 46), max(1, int(2*s)))
            for dy in (12, 24, 36, 48):
                c.line((x-18*s, y+dy*s), (x-13*s, y+(dy+3)*s), INK, 1)
        c.save(str(HERE / f'question_{i}.png'))
    for name, lines in {
        'ride': ['FIND THE FAKE', 'SHOOT ITS PICTURE', 'BOOST OR BRAKE'],
        'locked': ['ANSWER LOCKED', 'NEXT QUESTION SOON'],
        'boost': ['BOOST +'], 'miss': ['BRAKE'], 'finish': ['FINISH'],
        'roll': ['ROLL', 'JUMP OR DODGE'], 'hop': ['HOP', 'WATCH THE LANDING'],
        'bounce': ['BOUNCE', 'WATCH THE WALL'], 'shelter': ['SHELTER'],
    }.items():
        c = card('', 512, 192)
        for j, line in enumerate(lines):
            scale = min(6, 480 // (4 * len(line)))
            centered(c, line, 30 + j*48, scale)
        c.save(str(HERE / f'{name}.png'))
    for number in range(1, 5):
        c = card('', 128, 128)
        centered(c, str(number), 31, 13)
        c.save(str(HERE / f'option_{number}.png'))
    (HERE / 'questions.json').write_text(json.dumps(tasks, indent=2) + '\n', encoding='utf-8')
    return tasks


if __name__ == '__main__': generate()
