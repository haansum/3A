"""Lever catalog: load, validate, compute status, render the review list.

    python -m ko.beats.catalog            # validate + write docs/LEVERS.md
"""
import glob
import os
import re

import yaml

from .predicates import PRED

HERE = os.path.dirname(__file__)
KEYS = {'id', 'label', 'say', 'side', 'default_side', 'region', 'pose', 'mirror', 'check', 'layer',
        'expands', 'also', 'src', 'approved', 'note', 'kind'}
# layer keys the compiler turns into sim/bake config today (see compile.py)
DRIVEN = {'tone', 'tone_all', 'tone_step', 'tier', 'tremor', 'breath', 'strike', 'strike_mod',
          'toes', 'gaze', 'fade_s', 'hold_s', 'rise_s', 'setup', 'arena', 'follow_count', 'follow_delay',
          'phase_delay_s'}
JOINT = re.compile(r'^(spine|chest|neck|head)_(flex|lat|twist)$|^(upper_arm|forearm|hand|thigh|shin|foot)_(\$S|\$O|L|R)_'
                   r'(flex|abd|twist|dev|dorsi|inv)$')
_cache = None


def load():
    global _cache
    if _cache is not None:
        return _cache
    fams, levers = [], {}
    for f in sorted(glob.glob(os.path.join(HERE, 'catalog', '*.yaml'))):
        d = yaml.safe_load(open(f))
        fam = {'family': d['family'], 'title': d['title'], 'ids': []}
        for lv in d['levers']:
            lv['family'] = d['family']
            if lv['id'] in levers:
                raise ValueError(f'duplicate lever id {lv["id"]}')
            levers[lv['id']] = lv
            fam['ids'].append(lv['id'])
        fams.append(fam)
    _cache = (fams, levers)
    return _cache


def checks_of(lv):
    c = lv.get('check')
    return [] if not c else c if isinstance(c, list) else [c]


def status(lv, levers):
    if lv.get('expands'):
        subs = {status(levers[e['id']], levers) for e in lv['expands']}
        return 'drives+checks' if subs == {'drives+checks'} or (checks_of(lv) and 'planned' not in subs) else \
            'planned' if subs == {'planned'} else 'partial'
    drives = bool(lv.get('pose')) or bool(set(lv.get('layer') or {}) & DRIVEN)
    chk = bool(lv.get('pose') and any(abs(a1 - a0) > 1e-6 for a0, a1 in lv['pose'].values())) or bool(checks_of(lv))
    return 'drives+checks' if drives and chk else 'drives' if drives else 'checks' if chk else 'planned'


def validate():
    """Every structural mistake a hand-edited catalog can contain. Returns a list of problems."""
    fams, levers = load()
    bad = []
    for lid, lv in levers.items():
        extra = set(lv) - KEYS - {'family'}
        if extra:
            bad.append(f'{lid}: unknown keys {sorted(extra)} (unquoted comma in a label?)')
        for k in ('label', 'say', 'src'):
            if not lv.get(k):
                bad.append(f'{lid}: missing {k}')
        if not isinstance(lv.get('label'), str):
            bad.append(f'{lid}: label is not text')
        for j, v in (lv.get('pose') or {}).items():
            if not JOINT.match(j):
                bad.append(f'{lid}: unknown joint {j}')
            if not (isinstance(v, list) and len(v) == 2):
                bad.append(f'{lid}: pose {j} must be [at 0, at 1]')
            if ('$S' in j or '$O' in j) and lv.get('side') != 'LR':
                bad.append(f'{lid}: uses $S without side: LR')
        for c in checks_of(lv):
            if c.get('pred') not in PRED:
                bad.append(f'{lid}: unknown predicate {c.get("pred")}')
        for e in (lv.get('expands') or []) + (lv.get('also') or []):
            if e['id'] not in levers:
                bad.append(f'{lid}: expands unknown lever {e["id"]}')
    return bad


def doc():
    fams, levers = load()
    n = len(levers)
    st = {}
    for lv in levers.values():
        st[status(lv, levers)] = st.get(status(lv, levers), 0) + 1
    out = ['# Lever catalog: review list', '',
           'Generated from `ko/beats/catalog/*.yaml` by `python -m ko.beats.catalog`. Do not edit here.',
           '', f'{n} levers. ' + ', '.join(f'{v} {k}' for k, v in sorted(st.items())) + '.', '',
           '- **drives+checks**: prose sets it, the sim is driven toward it, the checker measures it.',
           '- **drives**: set and driven, not measured yet.',
           '- **checks**: an outcome. Measured; reached by tuning strike/stance and sweeping seeds.',
           '- **partial**: a named posture whose parts are a mix of the above.',
           '- **planned**: recognised in prose and reported as UNVERIFIED. Needs build work (see note).',
           '', 'Source: **log** = from your instruction log, **bible** = Animation Bible vocabulary, '
           '**new** = proposed here. To approve, strike out or reword anything, then say which '
           'ids (or whole families) are approved; `approved: true` is then set in the YAML.', '']
    for fam in fams:
        out += [f'## {fam["title"]}', '', '| OK | id | What it is | Phrases that trigger it | Status | Src | Note |',
                '| --- | --- | --- | --- | --- | --- | --- |']
        for lid in fam['ids']:
            lv = levers[lid]
            side = ' (L/R)' if lv.get('side') == 'LR' else ''
            out.append(f'| {"x" if lv.get("approved") else " "} | `{lid}` | {lv["label"]}{side} | '
                       f'{"; ".join(lv["say"][:4])} | {status(lv, levers)} | {lv["src"]} | {lv.get("note", "")} |')
        out.append('')
    return '\n'.join(out)


if __name__ == '__main__':
    problems = validate()
    for p in problems:
        print('BAD', p)
    root = os.path.dirname(os.path.dirname(HERE))
    os.makedirs(os.path.join(root, 'docs'), exist_ok=True)
    open(os.path.join(root, 'docs', 'LEVERS.md'), 'w').write(doc())
    fams, levers = load()
    print(len(levers), 'levers;', len(problems), 'problems')
    raise SystemExit(1 if problems else 0)
