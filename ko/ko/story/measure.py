"""How repetitive is the sampler? Draw N briefs in sequence, each seeing the ones before it,
and report how often any value recurs. Run with and without memory to see what the ledger buys.

    python -m ko.story.measure [N]
"""
import sys
from collections import Counter

from .draw import draw

AXES = ['setting', 'situation', 'relationship', 'grievance', 'stakes', 'register', 'counter_register', 'arc', 'pov', 'form',
        'opening_move', 'ending', 'sensory_anchor', 'talker_style']


def run(n=50, memory=True, seed0=1000):
    past = []
    for k in range(n):
        b = draw(seed0 + k, past=past if memory else [])
        past.append({'id': b['id'], 'axes': b['axes'], 'names': b['names']})
    out = {}
    for a in AXES:
        vals = [p['axes'][a] for p in past]
        gaps = [j - max(i for i in range(j) if vals[i] == vals[j]) for j in range(n) if vals[j] in vals[:j]]
        out[a] = {'distinct': len(set(vals)), 'most_used': Counter(vals).most_common(1)[0][1],
                  'closest_repeat': min(gaps) if gaps else None}
    names = [x for p in past for x in p['names']]
    out['names'] = {'distinct': len(set(names)), 'most_used': Counter(names).most_common(1)[0][1]}
    pairs = Counter((p['axes']['setting'], p['axes']['grievance']) for p in past)
    trip = Counter((p['axes']['register'], p['axes']['arc'], p['axes']['pov']) for p in past)
    out['repeated_setting_grievance_pairs'] = sum(1 for v in pairs.values() if v > 1)
    out['repeated_register_arc_pov_triples'] = sum(1 for v in trip.values() if v > 1)
    return out


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    for mem in (False, True):
        r = run(n, mem)
        print(f'\n{n} briefs, memory {"ON" if mem else "OFF"}')
        for k, v in r.items():
            print(f'  {k:36s} {v}')
