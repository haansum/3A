"""Checker self-test by mutation: take a real sim, break it in a known way, and require the
checker to notice. A checker that passes a broken take is worse than none (that is how the
jackknifed, face-down 'stiff back' take once passed its gate).

    python -m ko.beats.selftest <sheet.yaml> <sim.npz>

Each mutation names the claims it must turn from PASS to FAIL. A mutation is only meaningful
for claims that pass on the unbroken take, so those are reported as 'not applicable' rather
than counted either way.
"""
import copy
import sys

import numpy as np
import yaml

from .check import check
from .trace import Trace

RX180 = np.diag([1.0, -1.0, -1.0])


def _clone(tr):
    c = copy.copy(tr)
    c.pos, c.R = tr.pos.copy(), tr.R.copy()
    c.joints = {k: v.copy() for k, v in tr.joints.items()}
    c.tone = {k: v.copy() for k, v in tr.tone.items()}
    c.load = {k: v.copy() for k, v in tr.load.items()}
    c.events = dict(tr.events)
    return c


def face_down(tr):
    """Turn every body over about her long axis after the KO: lying on her back -> prone."""
    c = _clone(tr)
    i = c.i(c.events.get('down', c.events.get('ko', 0)))
    c.R[i:] = np.einsum('ij,tbjk->tbik', RX180, c.R[i:])
    return c


def no_escalation(tr):
    c = _clone(tr)
    for r in c.tone:
        c.tone[r][:] = 0.7
    return c


def swap_arms(tr):
    c = _clone(tr)
    for j in list(c.joints):
        if '_L_' in j and j.split('_')[0] in ('upper', 'forearm', 'hand'):
            o = j.replace('_L_', '_R_')
            c.joints[j], c.joints[o] = c.joints[o], c.joints[j]
    return c


def uncross_feet(tr):
    c = _clone(tr)
    a, b = c.b('foot_L'), c.b('foot_R')
    c.pos[:, [a, b]] = c.pos[:, [b, a]]
    return c


def no_tremor(tr):
    """Low-pass every joint at ~3 Hz."""
    c = _clone(tr)
    k = int(0.17 / c.dt)
    ker = np.ones(2 * k + 1) / (2 * k + 1)
    for j in c.joints:
        c.joints[j] = np.convolve(np.pad(c.joints[j], k, mode='edge'), ker, 'valid')
    return c


def frozen_pose(tr):
    """Joints never leave the pose she had at the KO: no posturing happened at all."""
    c = _clone(tr)
    i = c.i(c.events.get('ko', 0))
    for j in c.joints:
        c.joints[j][i:] = c.joints[j][i]
    return c


def drop_last_event(tr):
    c = _clone(tr)
    last = max((k for k in c.events if k.startswith('followup_')), default=None)
    if last:
        del c.events[last]
    return c


def legs_up(tr):
    c = _clone(tr)
    i = c.i(c.events.get('down', 0))
    for f in ('foot_L', 'foot_R'):
        c.pos[i:, c.b(f), 2] += 0.6
    return c


def no_head_contact(tr):
    c = _clone(tr)
    c.load['head'][:] = 0.0
    for k in ('touch:head', 'head_impact'):
        c.events.pop(k, None)
    return c


# mutation -> lever ids it must break (any that pass on the clean take)
MUTATIONS = {
    'face_down': (face_down, ['rest.supine', 'hips.flat']),
    'no_escalation': (no_escalation, ['tone.intensify', 'tone.max']),
    'swap_arms': (swap_arms, ['arms.fencing']),
    'uncross_feet': (uncross_feet, ['legs.ankles_cross']),
    'no_tremor': (no_tremor, ['dyn.tremor', 'dyn.tremor_upper']),
    'frozen_pose': (frozen_pose, ['wrist.flex', 'legs.scissor', 'shoulder.roll_forward', 'arms.fencing']),
    'drop_last_event': (drop_last_event, ['tone.max']),
    'legs_up': (legs_up, ['legs.stay_down']),
    'no_head_contact': (no_head_contact, ['ground.head_bounce']),
}
EXTRA = [{'id': 'rest.supine'}, {'id': 'hips.flat'}, {'id': 'legs.stay_down'}]   # claims added for the test


def run(sheet, tr):
    sheet = copy.deepcopy(sheet)
    sheet['beats'][-1]['levers'] = sheet['beats'][-1]['levers'] + EXTRA
    base = check(tr, sheet)
    ok0 = {}
    for r in base['rows']:
        ok0.setdefault(r['lever'], []).append(r['pass'])
    clean = {k for k, v in ok0.items() if all(x is True for x in v)}
    out = []
    for name, (fn, targets) in MUTATIONS.items():
        rep = check(fn(tr), sheet)
        failed = {r['lever'] for r in rep['rows'] if r['pass'] is False}
        for t in targets:
            out.append({'mutation': name, 'lever': t,
                        'result': 'n/a' if t not in clean else 'caught' if t in failed else 'MISSED'})
    return out


def main(argv=None):
    a = argv or sys.argv[1:]
    res = run(yaml.safe_load(open(a[0])), Trace.load(a[1]))
    for r in res:
        print(f"  {r['result']:7s} {r['mutation']:16s} {r['lever']}")
    n = [r['result'] for r in res]
    print(f"  {n.count('caught')} caught, {n.count('MISSED')} missed, {n.count('n/a')} not applicable")
    return 1 if 'MISSED' in n else 0


if __name__ == '__main__':
    raise SystemExit(main())
