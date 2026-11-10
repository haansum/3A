"""ko sweep: run a grid of overrides through sim + QA in parallel and rank the variants.
Tuning happens here, in seconds of CPU, not in renders.

  python -m ko.sweep takes/slice_001.yaml --set arena.rope_distance=1.0,1.2 \\
         --set controller.ko.phases.1.tone=0.3,0.5 --seeds 1,2,3
"""
import argparse
import itertools
import json
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor

import yaml

from . import manifest


def set_path(d, path, val):
    ks = path.split('.')
    for k in ks[:-1]:
        d = d[int(k)] if isinstance(d, list) else d.setdefault(k, {})
    k = ks[-1]
    if isinstance(d, list):
        d[int(k)] = val
    else:
        d[k] = val


def one(args):
    take, combo, seed = args
    from .qa import gates
    from .sim import run
    lock = manifest.resolve(take)
    for p, v in combo:
        set_path(lock, p, v)
    lock['arena']['rope_y'] = -float(lock['arena']['rope_distance'])
    lock['sim']['seed'] = seed
    body = manifest.stage_dir(manifest.resolve(take), 'body')
    tmp = tempfile.mkdtemp()
    out = run.run(lock, body, tmp)
    rep = gates.check(os.path.join(tmp, 'sim.npz'), lock)
    os.remove(os.path.join(tmp, 'sim.npz'))
    fails = [c['name'] for c in rep['checks'] if c['pass'] is False]
    oc = next((c for c in rep['checks'] if c['name'].startswith('outcome')), None)
    return dict(combo=dict(combo), seed=seed, outcome=bool(oc and oc['pass']), fails=fails,
                value=oc and oc['value'], metrics=rep['metrics'])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('take')
    ap.add_argument('--set', action='append', default=[])
    ap.add_argument('--seeds', default='1')
    ap.add_argument('--jobs', type=int, default=os.cpu_count())
    ap.add_argument('--json')
    ap.add_argument('--top', type=int, default=12)
    a = ap.parse_args(argv)
    axes = []
    for s in a.set:
        p, vs = s.split('=', 1)
        axes.append([(p, yaml.safe_load(v)) for v in vs.split(';' if ';' in vs else ',')])  # ';' separates list values
    jobs = [(a.take, c, int(sd)) for c in itertools.product(*axes) for sd in a.seeds.split(',')]
    with ProcessPoolExecutor(a.jobs) as ex:
        res = list(ex.map(one, jobs))
    res.sort(key=lambda r: (not r['outcome'], len(r['fails'])))
    for r in res[:a.top]:
        print('OK  ' if r['outcome'] else 'miss', r['combo'], 'seed', r['seed'], r['value'],
              'fails:', ','.join(r['fails']) or '-')
    print(f"{sum(r['outcome'] for r in res)}/{len(res)} variants reach the intended outcome")
    if a.json:
        json.dump(res, open(a.json, 'w'), indent=1)


if __name__ == '__main__':
    main()
