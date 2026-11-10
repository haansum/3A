"""Check a take against its beat sheet. Scenario-independent: all knowledge of what a claim
means lives in the lever catalog and the predicate library.

Beat sheet (YAML), written by ko.beats.parse from prose and approved by the owner:

    take: name
    approved: true
    beats:
      - id: b1
        on: ko                      # event that opens the beat (ko, down, touch:head,
        levers:                     #   <strike name>, rest, start)
          - {id: elbow.extend, side: L, i: 0.25}
          - {id: fall.spin, not: true}

A beat's window runs from its event (+ settle) to the next beat's event. A lever's check may
choose another window with `when:` (onset, fall, fall_end, ground, rest, take).
Outcome per claim: PASS, FAIL, or UNVERIFIED (nothing can measure it yet). UNVERIFIED is
reported, never counted as a pass.
"""
import json
import os
import sys

import numpy as np
import yaml

from . import catalog
from .predicates import PRED, judge
from .trace import Trace

WORDS = [(0.0, 'none'), (0.25, 'slight'), (0.5, 'moderate'), (0.75, 'strong'), (1.0, 'max')]
POSE_TOL = 0.3          # a pose lever passes when reached within this much of the asked intensity
SETTLE = 0.35           # s after a beat opens before its held posture is judged


def word(i):
    return min(WORDS, key=lambda w: abs(w[0] - i))[1]


def lerp(v, i):
    return v[0] + (v[1] - v[0]) * i if isinstance(v, list) else v


def resolve(entry, levers, _depth=0, _judge=True):
    """Beat entry -> flat list of (lever, side, intensity, negated, judged), macros expanded.
    Parts of a macro that has its own check are driven but not judged one by one."""
    lv = levers[entry['id']]
    i = float(entry.get('i', 0.6))
    side = entry.get('side') or lv.get('default_side')
    sides = ['L', 'R'] if side == 'both' else [side]
    out = []
    for s in sides:
        out.append((lv, s, i, bool(entry.get('not')), _judge))
        own = bool(lv.get('check'))
        for kind in ('expands', 'also'):
            for e in (lv.get(kind) or []) if _depth < 3 else []:
                es = {'$S': s, '$O': {'L': 'R', 'R': 'L'}.get(s)}.get(e.get('side'), e.get('side'))
                out += resolve({'id': e['id'], 'side': es, 'i': i * e.get('i', 1.0)}, levers, _depth + 1,
                               _judge and not (own and kind == 'expands'))
    return out


def pose_of(lv, side, i):
    """{joint: [extreme angle deg, fraction of the way to go]} for a pose lever: relative to
    wherever the joint is when the beat opens, so 'slightly' means the same in any scenario."""
    sgn = -1.0 if (lv.get('mirror') and side == 'R') else 1.0
    out = {}
    for j, (a0, a1) in (lv.get('pose') or {}).items():
        j = j.replace('$S', side or '').replace('$O', {'L': 'R', 'R': 'L'}.get(side, ''))
        out[j] = [sgn * a1, float(i)]
    return out


def windows(tr, sheet):
    ev = tr.events
    beats = sheet['beats']
    t_on = []
    for b in beats:
        t_on.append(ev.get(b['on']))
    out = []
    for k, b in enumerate(beats):
        nxt = next((t for t in t_on[k + 1:] if t is not None), ev['end'])
        out.append((t_on[k], nxt))
    return out


def named_window(tr, when, t0, t1):
    ev = tr.events
    ko, end = ev.get('ko', 0.0), ev['end']
    down, rest = ev.get('down'), ev.get('rest', end)
    rest = min(rest, end - 0.5)
    w = {'beat': (min(t0 + SETTLE, max(t0, t1 - 0.1)), t1), 'onset': (t0, min(t0 + 0.3, t1)),
         'whole_beat': (t0, t1), 'take': (ko, end), 'rest': (rest, end),
         'fall': (ko, down) if down is not None else None,
         'fall_end': (ko, rest), 'ground': (down, end) if down is not None else None}[when]
    return w


def check(tr, sheet):
    fams, levers = catalog.load()
    rows = []
    wins = windows(tr, sheet)
    prev_tone = None
    for b, (t0, t1) in zip(sheet['beats'], wins):
        def row(lv, side, what, value, want, ok, note=''):
            rows.append({'beat': b['id'], 'on': b['on'], 'lever': lv['id'], 'side': side or '', 'check': what,
                         'value': None if value is None or not np.isfinite(value) else round(float(value), 3),
                         'want': want, 'pass': ok, 'note': note})
        if t0 is None:
            for entry in b.get('levers', []) or [{'id': '-'}]:      # every claim of a beat that never opened fails
                rows.append({'beat': b['id'], 'on': b['on'], 'lever': entry['id'], 'side': entry.get('side', ''),
                             'check': 'event happened', 'value': None, 'want': b['on'], 'pass': False,
                             'note': f'event {b["on"]} never occurred'})
            continue
        bw = named_window(tr, 'beat', t0, t1)
        tone_now = PRED['tone'](tr, tr.i(bw[0]), max(tr.i(bw[1]), tr.i(bw[0]) + 1), agg='p90')
        seen = set()
        for entry in b.get('levers', []):
            if entry['id'] not in levers:
                rows.append({'beat': b['id'], 'on': b['on'], 'lever': entry['id'], 'side': '', 'check': 'known lever',
                             'value': None, 'want': 'in catalog', 'pass': False, 'note': 'unknown lever id'})
                continue
            for lv, side, i, neg, judged in resolve(entry, levers):
                if not judged or (lv['id'], side) in seen:
                    continue
                seen.add((lv['id'], side))
                if lv.get('side') == 'LR' and side not in ('L', 'R'):
                    row(lv, side, 'side given', None, 'L or R', False, 'no side chosen')
                    continue
                did = False
                if lv.get('pose') and not catalog.checks_of(lv):
                    pj = {j: v[0] for j, v in pose_of(lv, side, i).items()}
                    got = PRED['intensity'](tr, tr.i(bw[0]), max(tr.i(bw[1]), tr.i(bw[0]) + 1), joints=pj,
                                            i_ref=tr.i(t0))
                    ok = bool(np.isfinite(got) and abs(got - i) <= POSE_TOL and got >= 0.4 * i)   # some of it must happen
                    if neg:
                        ok = bool(np.isfinite(got) and got < 0.25)
                    row(lv, side, 'pose reached', got, ('< 0.25 (absent)' if neg else f'{i:.2f} +-{POSE_TOL} ({word(i)})'), ok,
                        f'reads as {word(max(0, min(1, got)))}' if np.isfinite(got) else '')
                    did = True
                for c in catalog.checks_of(lv):
                    c = dict(c)
                    when = c.pop('when', 'beat')
                    w = named_window(tr, when, t0, t1)
                    name = c.pop('pred')
                    lim = {k: lerp(c.pop(k), i) for k in ('min', 'max') if k in c}
                    sbs = c.pop('sign_by_side', None)
                    vs = c.pop('vs_prev', None)
                    if w is None:
                        row(lv, side, f'{name} [{when}]', None, 'window exists', False, 'she never went down')
                        did = True
                        continue
                    i0, i1 = tr.i(w[0]), max(tr.i(w[1]), tr.i(w[0]) + 1)
                    args = {k: (v.replace('$S', side or '').replace('$O', {'L': 'R', 'R': 'L'}.get(side, ''))
                                if isinstance(v, str) else v) for k, v in c.items()}
                    if 'side' in PRED[name].__code__.co_varnames:
                        args['side'] = side
                    val = PRED[name](tr, i0, i1, **args)
                    if sbs:
                        val = val * sbs * (1.0 if side == 'L' else -1.0)
                    if vs:
                        if prev_tone is None:
                            ok, want = True, 'first beat'
                        else:
                            ok = val > prev_tone + 0.03 if vs == 'gt' else val <= prev_tone + 0.03
                            want = f'{">" if vs == "gt" else "<="} previous beat ({prev_tone:.2f})'
                    else:
                        ok, want = judge(val, lim)
                    if neg:
                        ok = not ok
                        want = 'NOT ' + want
                    row(lv, side, f'{name} [{when}]', val, want, ok)
                    did = True
                if not did and not lv.get('expands'):
                    row(lv, side, '-', None, '-', None, lv.get('note') or 'no measurement exists yet')
        prev_tone = tone_now
    n = {'pass': sum(r['pass'] is True for r in rows), 'fail': sum(r['pass'] is False for r in rows),
         'unverified': sum(r['pass'] is None for r in rows)}
    return {'rows': rows, 'summary': n, 'pass': n['fail'] == 0, 'events': {k: round(v, 3) for k, v in tr.events.items()},
            'approved': bool(sheet.get('approved'))}


def show(rep, file=sys.stdout):
    cur = None
    for r in rep['rows']:
        if r['beat'] != cur:
            cur = r['beat']
            print(f"\n  beat {cur}  (on {r['on']} = {rep['events'].get(r['on'], '?')} s)", file=file)
        s = {True: 'PASS', False: 'FAIL', None: 'UNVERIFIED'}[r['pass']]
        v = '' if r['value'] is None else f"{r['value']:g}"
        print(f"    [{s:10s}] {r['lever']}{'/' + r['side'] if r['side'] else '':3s} {r['check']}: {v} (want {r['want']}) {r['note']}", file=file)
    n = rep['summary']
    print(f"\n  {n['pass']} pass, {n['fail']} fail, {n['unverified']} unverified"
          + ('' if rep['approved'] else '   [beat sheet NOT yet approved by owner]'), file=file)


def main(argv=None):
    a = argv or sys.argv[1:]
    sheet = yaml.safe_load(open(a[0]))
    rep = check(Trace.load(a[1]), sheet)
    show(rep)
    if len(a) > 2:
        json.dump(rep, open(a[2], 'w'), indent=1)
    return 0 if rep['pass'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
