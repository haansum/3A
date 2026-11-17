"""One probe tool: every number the owner asks about, computed from the sim before any render.

    python tools/probe.py all takes/X.yaml            # outcomes + load + settle + organic + endstate
    python tools/probe.py outcomes takes/X.yaml       # the take's beat sheet, claim by claim
    python tools/probe.py load takes/X.yaml           # canvas force per segment, bounces
    python tools/probe.py settle takes/X.yaml         # how the body comes to rest
    python tools/probe.py organic takes/X.yaml        # symmetry, stillness, periodicity
    python tools/probe.py endstate takes/X.yaml       # how she ends: supine / prone / side / seated
    python tools/probe.py ensemble takes/X.yaml -n 20 # seeded perturbations: end states, pass rates
    python tools/probe.py baseline T1.yaml T2.yaml .. --out docs/baseline.json

Builds the take through sim if needed (seconds). No Blender. Render-space probes (ground gap,
framing, look, render cost) are separate subcommands to be added beside these; they need a bake.
A take's beat sheet is `takes/beats/<take>.yaml`, or the path in the take's `sheet:` key.
"""
import argparse
import json
import os
import sys

import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ko import manifest                      # noqa: E402
from ko.beats import check as bcheck         # noqa: E402
from ko.beats.trace import Trace             # noqa: E402

FLESH = ['pelvis', 'chest', 'spine', 'thigh_L', 'thigh_R', 'upper_arm_L', 'upper_arm_R']
BONY = ['head', 'shin_L', 'shin_R', 'forearm_L', 'forearm_R', 'hand_L', 'hand_R', 'foot_L', 'foot_R', 'neck']


def sim_of(take, sets=None):
    """-> (lock, path to sim.npz). Runs the sim directly when overrides are given."""
    from ko import cli
    if not sets:
        lock, dirs, _ = cli.build(take, to='sim')
        return lock, os.path.join(dirs['sim'], 'sim.npz')
    raise NotImplementedError


def _win(x, k):
    c = np.cumsum(np.insert(x, 0, 0.0))
    return (c[k:] - c[:-k]) / k


def load(tr):
    """Canvas force per segment after the KO, in body weights."""
    i0 = tr.i(tr.events.get('ko', 0.0))
    k = max(1, int(0.02 / tr.dt))
    out = {}
    for b in tr.bodies:
        f = tr.load[b][i0:] / tr.weight
        if f.max() <= 0:
            continue
        on = f > 0.05
        hits = int(((~on[:-1]) & on[1:]).sum() + (1 if on[0] else 0))
        out[b] = {'peak_step_bw': round(float(f.max()), 1),
                  'peak_20ms_bw': round(float(_win(f, k).max()) if len(f) > k else float(f.max()), 1),
                  'touchdowns': hits, 'kind': 'flesh' if b in FLESH else 'bony'}
    tot = sum(tr.load[b] for b in tr.bodies)[i0:] / tr.weight
    worst = max(out.items(), key=lambda kv: kv[1]['peak_step_bw'])
    return {'segments': out, 'total_peak_step_bw': round(float(tot.max()), 1),
            'total_peak_20ms_bw': round(float(_win(tot, k).max()), 1),
            'worst_segment': worst[0], 'spikiness': round(float(tot.max() / max(_win(tot, k).max(), 1e-6)), 1)}


def settle(tr):
    """How she comes to rest. Trunk = pelvis and chest; limbs = hands and feet."""
    dt, t = tr.dt, tr.t
    k = max(1, int(0.1 / dt))
    down = tr.events.get('down')
    if down is None:
        return {'down': None}
    sp = {b: tr.speed(b, k) for b in ('pelvis', 'chest', 'head', 'hand_L', 'hand_R', 'foot_L', 'foot_R')}
    last = lambda b, thr=0.10: float(t[np.nonzero(sp[b] > thr)[0][-1]]) if (sp[b] > thr).any() else 0.0
    trunk_still = max(last('pelvis'), last('chest'))
    limb_still = max(last(b) for b in ('hand_L', 'hand_R', 'foot_L', 'foot_R'))
    # vertical rebounds of the pelvis after first canvas contact
    z = tr.pos[:, tr.b('pelvis'), 2]
    i = tr.i(down)
    vz = np.gradient(z[i:], dt)
    up = (vz[:-1] <= 0.05) & (vz[1:] > 0.05)
    jq = np.stack([tr.joints[j] for j in tr.joints], 1)
    jv = np.abs(np.gradient(jq, dt, axis=0))
    still = (jv.max(axis=1) < 3.0)            # every joint under 3 deg/s
    after = still[tr.i(max(trunk_still, down)):]
    return {'ko_to_down_s': round(down - tr.events.get('ko', 0.0), 2),
            'down_to_trunk_still_s': round(trunk_still - down, 2),
            'limbs_move_after_trunk_s': round(max(0.0, limb_still - trunk_still), 2),
            'pelvis_rebounds': int(up.sum()),
            'pelvis_rebound_height_mm': round(float(1000 * (z[i:].max() - z[i:i + int(0.05 / dt)].min())) if up.any() else 0.0, 1),
            'frozen_fraction_after_settle': round(float(after.mean()) if len(after) else 0.0, 2),
            'aftermath_s': round(float(t[-1] - down), 2)}


def organic(tr):
    """Does the aftermath read as a body or as a paused rig?"""
    dt = tr.dt
    i0 = tr.i(tr.events.get('down', tr.events.get('ko', 0.0)))
    pairs = [(j, j.replace('_L_', '_R_')) for j in tr.joints if '_L_' in j and j.replace('_L_', '_R_') in tr.joints]
    sym = float(np.mean([np.abs(tr.joints[a][i0:] - tr.joints[b][i0:]).mean() for a, b in pairs]))
    jq = np.stack([tr.joints[j][i0:] for j in tr.joints], 1)
    step = max(1, int(1 / 30 / dt))
    d30 = np.abs(np.diff(jq[::step], axis=0))          # degrees per 30 fps frame
    still_frames = float((d30.max(axis=1) < 0.1).mean())
    # longest window with no joint moving more than 0.1 deg per frame
    s = (d30.max(axis=1) < 0.1).astype(int)
    run = best = 0
    for v in s:
        run = run + 1 if v else 0
        best = max(best, run)
    # periodicity: strongest autocorrelation peak of chest flexion between 1 and 6 s
    x = tr.joints['chest_flex'][i0:][::step]
    x = x - np.polyval(np.polyfit(np.arange(len(x)), x, 2), np.arange(len(x)))
    ac = np.correlate(x, x, 'full')[len(x) - 1:]
    ac = ac / max(ac[0], 1e-9)
    lo, hi = 30, min(len(ac) - 1, 180)
    peak = float(ac[lo:hi].max()) if hi > lo else 0.0
    return {'asymmetry_deg': round(sym, 1), 'still_frame_fraction': round(still_frames, 2),
            'longest_dead_window_s': round(best / 30.0, 2), 'breath_periodicity': round(peak, 2),
            'chest_motion_deg_p2p': round(float(np.ptp(tr.joints['chest_flex'][tr.i(tr.events.get('rest', tr.t[-1]) - 0.0) - int(2 / dt):])), 2)}


def endstate(tr):
    i = len(tr.t) - 1
    c = tr.axis('chest', 'front')[i]
    left = tr.axis('chest', 'left')[i]
    up = tr.axis('chest', 'up')[i]
    hz, pz = tr.pos[i, tr.b('chest'), 2], tr.pos[i, tr.b('pelvis'), 2]
    if up[2] > 0.6 and hz > 0.3:
        s = 'seated_or_propped'
    elif c[2] > 0.5:
        s = 'supine'
    elif c[2] < -0.5:
        s = 'prone'
    else:
        s = 'side_L' if left[2] < 0 else 'side_R'
    H = tr.heading()
    d = tr.pos[i, tr.b('pelvis')] - tr.pos[tr.i(tr.events.get('ko', 0.0)), tr.b('pelvis')]
    return {'state': s, 'travel_back_m': round(float(-d @ H[:, 0]), 2), 'travel_left_m': round(float(d @ H[:, 1]), 2),
            'head_yaw_deg': round(float(tr.joints['neck_twist'][i]), 0),
            'max_foot_height_m': round(float(max(tr.pos[i, tr.b('foot_L'), 2], tr.pos[i, tr.b('foot_R'), 2])), 2)}


def sheet_for(take, lock=None):
    t = yaml.safe_load(open(take))
    p = t.get('sheet') or os.path.join('takes', 'beats', os.path.splitext(os.path.basename(take))[0] + '.yaml')
    p = p if os.path.isabs(p) else os.path.join(ROOT, p)
    return yaml.safe_load(open(p)) if os.path.exists(p) else None


def outcomes(tr, sheet):
    if sheet is None:
        return {'sheet': None}
    rep = bcheck.check(tr, sheet)
    return {'summary': rep['summary'],
            'fails': [f"{r['beat']} {r['lever']}{'/' + r['side'] if r['side'] else ''}: {r['value']} (want {r['want']})"
                      for r in rep['rows'] if r['pass'] is False],
            'unverified': sorted({r['lever'] for r in rep['rows'] if r['pass'] is None}), 'report': rep}


def everything(take):
    lock, path = sim_of(take)
    tr = Trace.load(path)
    oc = outcomes(tr, sheet_for(take))
    oc.pop('report', None)
    return {'take': lock['take'], 'events': {k: round(v, 3) for k, v in tr.events.items()},
            'outcomes': oc, 'load': load(tr), 'settle': settle(tr), 'organic': organic(tr), 'endstate': endstate(tr)}


def ensemble(take, n=20, perturb=0.08):
    """Seeded perturbations of the same take (strike impulse, direction, timing, tremor phase).
    Reports what the sim does when nobody tunes it: end states, QA pass rate, outcome pass rate."""
    from ko.qa import gates
    from ko.sim import run as simrun
    from ko import cli
    lock, dirs, _ = cli.build(take, to='body')
    sheet = sheet_for(take)
    rows = []
    mh_ = [b['mass'] for b in json.load(open(os.path.join(dirs['body'], 'body.json')))['bodies'] if b['name'] == 'head'][0]

    def head_support(o):
        # share of the head's weight the canvas carries over the last 1.5 s: ~1 = resting on it,
        # <1 = the neck holds part of it up, >1 = the neck pushes it down (props the trunk on it)
        gn_ = [str(g) for g in o['geom_names']]; C_ = o['contacts']; t_ = o['t']
        i0_ = int(np.searchsorted(t_, t_[-1] - 1.5)); cv_, hg_ = gn_.index('canvas'), gn_.index('g_head')
        m_ = (C_[:, 0] >= i0_) & (((C_[:, 1] == cv_) & (C_[:, 2] == hg_)) | ((C_[:, 2] == cv_) & (C_[:, 1] == hg_)))
        return round(float(C_[m_, 4].sum() / (len(t_) - i0_) / (mh_ * 9.81)), 2)
    for s in range(n):
        cfg = json.loads(json.dumps(lock, default=str))
        cfg['sim']['seed'] = 100 + s
        cfg['sim']['perturb'] = perturb
        out = simrun.run(cfg, dirs['body'], None, record=False)
        tmp = os.path.join(ROOT, 'build', f'_probe_tmp_{os.getpid()}.npz')   # parallel runs
        np.savez(tmp, **out)
        tr = Trace.load(tmp)
        qa = gates.check(tmp, cfg)
        qfail = [c['name'] for c in qa['checks'] if c['pass'] is False and not c['name'].startswith('outcome') and c['name'] not in ('beats', 'beat_sheet_approved_by_owner')]
        o = outcomes(tr, sheet)
        rows.append({'seed': 100 + s, **endstate(tr), 'qa_fails': qfail,
                     'outcome_fails': len(o.get('fails', [])) if sheet else None,
                     'head_support': head_support(out),
                     'peak_20ms_bw': load(tr)['total_peak_20ms_bw'], 'peak_step_bw': load(tr)['total_peak_step_bw'],
                     'auto_side': [v['side'] for k, v in json.loads(str(out['event_data'])).items() if k.startswith('auto_side')], **{k: settle(tr).get(k) for k in ('ko_to_down_s', 'pelvis_rebounds')}})
    from collections import Counter
    st = Counter(r['state'] for r in rows)
    return {'take': lock['take'], 'n': n, 'perturb': perturb, 'end_states': dict(st),
            'qa_clean_rate': round(sum(not r['qa_fails'] for r in rows) / n, 2),
            'qa_fail_causes': dict(Counter(c for r in rows for c in r['qa_fails'])),
            'outcome_pass_rate': None if sheet is None else round(sum(r['outcome_fails'] == 0 for r in rows) / n, 2),
            'ko_to_down_s': [round(float(np.percentile([r['ko_to_down_s'] for r in rows if r['ko_to_down_s'] is not None], q)), 2) for q in (10, 50, 90)],
            'peak_20ms_bw': [round(float(np.percentile([r['peak_20ms_bw'] for r in rows], q)), 1) for q in (10, 50, 90)],
            'peak_step_bw': [round(float(np.percentile([r['peak_step_bw'] for r in rows], q)), 1) for q in (10, 50, 90)],
            'auto_side': dict(Counter(x for r in rows for x in r['auto_side'])),
            'head_support': [round(float(np.percentile([r['head_support'] for r in rows], q)), 2) for q in (10, 50, 90)],
            'rows': rows}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['all', 'outcomes', 'load', 'settle', 'organic', 'endstate', 'ensemble', 'baseline'])
    ap.add_argument('takes', nargs='+')
    ap.add_argument('-n', type=int, default=20)
    ap.add_argument('--perturb', type=float, default=0.08)
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    if a.cmd == 'baseline':
        res = {os.path.basename(t)[:-5]: everything(t) for t in a.takes}
    elif a.cmd == 'ensemble':
        res = ensemble(a.takes[0], a.n, a.perturb)
        res_print = {k: v for k, v in res.items() if k != 'rows'}
        print(json.dumps(res_print, indent=1))
        if a.out:
            json.dump(res, open(a.out, 'w'), indent=1)
        return
    elif a.cmd == 'all':
        res = everything(a.takes[0])
    else:
        lock, path = sim_of(a.takes[0])
        tr = Trace.load(path)
        if a.cmd == 'outcomes':
            o = outcomes(tr, sheet_for(a.takes[0]))
            if o.get('report'):
                bcheck.show(o['report'])
            return
        res = {'load': load, 'settle': settle, 'organic': organic, 'endstate': endstate}[a.cmd](tr)
    print(json.dumps(res, indent=1))
    if a.out:
        json.dump(res, open(a.out, 'w'), indent=1)


if __name__ == '__main__':
    main()
