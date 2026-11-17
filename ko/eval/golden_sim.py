"""Golden-master check for controller refactors: existing takes must reproduce their sim.

    python3 -m eval.golden_sim capture TAKE...   # store qpos/events from the current code
    python3 -m eval.golden_sim check TAKE...     # rerun with the current code and compare
"""
import json
import os
import sys

import numpy as np

from ko import manifest
from ko.sim import run

GDIR = os.path.join(manifest.ROOT, 'eval', 'golden')


def sim(take):
    lock = manifest.resolve(take)
    return run.run(lock, manifest.stage_dir(lock, 'body'), None, record=False)


def main(argv):
    mode, takes = argv[0], argv[1:]
    os.makedirs(GDIR, exist_ok=True)
    bad = 0
    for tk in takes:
        name = os.path.splitext(os.path.basename(tk))[0]
        out = sim(tk)
        p = os.path.join(GDIR, name + '.npz')
        if mode == 'capture':
            np.savez_compressed(p, qpos=out['qpos'], events=out['events'], t_ko=out['t_ko'])
            print('captured', name, out['qpos'].shape)
        else:
            g = np.load(p)
            n = min(len(g['qpos']), len(out['qpos']))
            err = float(np.abs(g['qpos'][:n] - out['qpos'][:n]).max()) if n else np.inf
            ge, oe = json.loads(str(g['events'])), json.loads(str(out['events']))
            same_ev = all(oe.get(k) == v for k, v in ge.items())   # new events are additive
            if set(oe) - set(ge):
                print('   new events (additive):', sorted(set(oe) - set(ge)))
            ok = err < 1e-9 and same_ev and len(g['qpos']) == len(out['qpos'])
            bad += not ok
            print(f'{"PASS" if ok else "FAIL"} {name}: max|dqpos|={err:.3g} events_equal={same_ev}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main(sys.argv[1:])
