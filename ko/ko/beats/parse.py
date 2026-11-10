"""Prose -> draft beat sheet. Deterministic (no model call): a lexicon match against the lever
catalog, so the same prose always gives the same sheet and a weaker model has nothing to
invent. Whatever it could not place is listed under `unmatched` for a person or a model to
resolve; nothing is silently dropped. The sheet is a DRAFT until the owner sets approved.

    python -m ko.beats.parse "a hook that stiffens ..." [--seed 3] [--out sheet.yaml]

Rules:
  - a sentence that names a trigger opens a new beat at that event
  - intensity words near a phrase set i (slight .25, default .6, strong .8, max 1)
  - left/right near a phrase set the side; 'one arm ... the other' and unstated sides are
    drawn from the seed and marked `chosen: seed` so the owner can flip them
  - 'no / not / without' before a phrase negates the claim
"""
import argparse
import re
import sys

import numpy as np
import yaml

from . import catalog

TRIGGERS = [    # (regex, event) - first match in a sentence wins by position
    (r'\b(follow[- ]?up|ground[- ]and[- ]pound|ground strike|gnp)\b', 'FOLLOWUP'),
    (r'\bhead\b[^.]{0,40}\b(bounc\w*|hits?|hitting|impact\w*|slams?|strikes?)\b[^.]{0,30}\b(ground|canvas|mat|floor)\b', 'touch:head'),
    (r'\bhead (bounce|impact)\w*', 'touch:head'),
    (r'\b(impact with|hits?|hitting|lands? on|reach\w*|when she\'?s? on) (the )?(ground|canvas|mat|floor)\b', 'down'),
    (r'\b(at rest|final position|comes? to rest|once settled|as the tonic (posture |state )?(fades|relaxes))\b', 'rest'),
]
INTENSITY = [(r'\b(max\w*|fully|full|complete\w*|extreme\w*|climax|as far as)\b', 1.0),
             (r'\b(strong\w*|hard\w*|heav\w+|pronounced|very|deep\w*|violent\w*|a lot|much more|sharply)\b', 0.8),
             (r'\b(moderate\w*|somewhat|partly|partial\w*|halfway)\b', 0.5),
             (r'\b(slight\w*|a little|subtl\w+|mild\w*|barely|gentl\w+|a bit|faint\w*|small|loose\w*)\b', 0.25)]
NEG = r"\b(no|not|without|never|don'?t|doesn'?t|isn'?t|won'?t|stop)\b"
ORD = {'second': 2, '2nd': 2, 'another': 2, 'third': 3, '3rd': 3}


def phrase_re(p):
    ws = re.findall(r"[\w'%-]+", p.lower())
    return re.compile(r'\b' + r"(?:\W+[\w'-]+){0,2}?\W+".join(re.escape(w) + r"[\w']*" for w in ws)), len(ws)


_LEX = None


def lexicon():
    global _LEX
    if _LEX is None:
        fams, levers = catalog.load()
        _LEX = [(lid, *phrase_re(p)) for lid, lv in levers.items() for p in lv['say']]
    return _LEX


def match(sentence):
    """Non-overlapping lever matches, longest phrase first. -> [(start, end, lever id)]"""
    s = sentence.lower()
    cands = []
    for lid, rx, n in lexicon():
        for m in rx.finditer(s):
            cands.append((n, -(m.end() - m.start()), m.start(), m.end(), lid))
    cands.sort(reverse=True)
    taken, out, seen = [], [], set()
    for n, _, a, b, lid in cands:
        if any(a < tb and b > ta for ta, tb in taken):
            continue
        taken.append((a, b))
        out.append((a, b, lid))
    return sorted(out)


def _near(s, a, b, before=28, after=18):
    return s[max(0, a - before):a], s[a:b], s[b:b + after]


def parse(prose, seed=0, name='take'):
    fams, levers = catalog.load()
    rng = np.random.default_rng(seed)
    sents = [x.strip() for x in re.split(r'(?<=[.;!?\n])\s+|\n+', prose) if x.strip()]
    beats = [{'id': 'b1', 'on': 'ko', 'say': '', 'levers': []}]
    strikes, unmatched, n_follow = [], [], 0
    pair_side = None
    for sent in sents:
        s = sent.lower()
        pair_side = None
        trig = None
        for rx, ev in TRIGGERS:
            m = re.search(rx, s)
            if m and (trig is None or m.start() < trig[0]):
                trig = (m.start(), m.end(), ev)
        if trig:
            ev = trig[2]
            if ev == 'FOLLOWUP':
                k = next((v for w, v in ORD.items() if re.search(rf'\b{w}\b', s)), None)
                n_follow = k or max(n_follow, 1)
                ev = f'followup_{n_follow}'
            b = next((x for x in beats if x['on'] == ev), None)
            if b is None:
                b = {'id': f'b{len(beats) + 1}', 'on': ev, 'say': '', 'levers': []}
                beats.append(b)
                if ev.startswith('followup_'):
                    strikes.append({'lever': 'follow.punch', 'name': ev, 'i': 0.5})
            cur = b
            if trig[0] > 25:
                cur.setdefault('review', []).append('trigger is mid-sentence: check which claims belong before it')
        else:
            cur = beats[-1]
        cur['say'] = (cur['say'] + ' ' + sent).strip()
        ms = match(sent)
        covered = np.zeros(len(s), bool)
        if trig:
            covered[trig[0]:trig[1]] = True
        for a, bnd, lid in ms:
            covered[a:bnd] = True
            lv = levers[lid]
            pre, mid, post = _near(s, a, bnd)
            ctx = pre + ' ' + post
            near = ' '.join(re.findall(r"[\w'-]+", pre)[-2:] + [mid] + re.findall(r"[\w'-]+", post)[:1])
            i = next((v for rx, v in INTENSITY if re.search(rx, near)), 0.6)
            e = {'id': lid, 'i': i}
            if re.search(NEG + r'\W+(\w+\W+){0,2}$', pre):
                e['not'] = True
            if lv.get('side') == 'LR':
                loc = pre[-26:] + ' ' + mid + ' ' + post
                sd = 'both' if re.search(r'\bboth\b', loc) else 'L' if re.search(r'\bleft\b', loc) else \
                    'R' if re.search(r'\bright\b', loc) else None
                if sd is None and re.search(r'\bone (arm|leg|hand|side|elbow|knee)\b', pre[-20:] + mid):
                    sd = 'LR'[int(rng.integers(2))]
                    e['chosen'] = 'seed'
                    pair_side = sd
                if sd is None and re.search(r'\bthe other\b', pre[-20:] + mid) and pair_side:
                    sd = {'L': 'R', 'R': 'L'}[pair_side]
                    e['chosen'] = 'opposite of the first'
                if sd is None:
                    sd = lv.get('default_side')
                if sd is None:
                    sd = 'LR'[int(rng.integers(2))]
                    e['chosen'] = 'seed'
                e['side'] = sd
                if sd in ('L', 'R') and lv.get('kind') != 'strike':
                    pair_side = pair_side or sd
            if lv.get('kind') == 'strike' and not lid.startswith('follow.'):
                strikes.insert(0, {'lever': lid, 'name': 'ko_strike', 'i': i, **{k: e[k] for k in ('side', 'chosen') if k in e}})
                continue
            if lid == 'follow.punch':
                continue
            if lv.get('kind') == 'strike_mod':
                tgt = next((x for x in strikes if x['name'] == (cur['on'] if cur['on'].startswith('followup') else 'ko_strike')), None)
                if tgt is not None:
                    tgt.setdefault('mods', []).append(lid)
                    continue
            if not any(x['id'] == lid and x.get('side') == e.get('side') for x in cur['levers']):
                cur['levers'].append(e)
        rest = ''.join(c if not k else '|' for c, k in zip(sent, covered))
        for frag in re.split(r'\|+|,| and | so that | as | while ', rest):
            words = [w for w in re.findall(r'[a-z]+', frag.lower()) if w not in STOP]
            if len(words) >= 2:
                unmatched.append({'beat': cur['id'], 'text': frag.strip(' ,.')})
    sheet = {'take': name, 'approved': False, 'seed': seed, 'prose': prose.strip(), 'strikes': strikes,
             'beats': beats, 'unmatched': unmatched}
    return sheet


STOP = set('a an the of to in on at her she he his is are be as it its that this which with for from by then '
           'so i want we you me my make made keep also please should would could will can do does did '
           'more less very just into onto off up down out when while after before upon during until and or but '
           'if not no body fighter model take render replay she\'s starts start begin begins causing cause leading '
           'lead still like there their them has have had was were being been per'.split())


def summary(sheet, file=sys.stdout):
    fams, levers = catalog.load()
    for st in sheet['strikes']:
        print(f"  strike {st['name']}: {st['lever']} {st.get('side', '')} i={st['i']} {st.get('mods', '')}"
              f"{' [side chosen by ' + st['chosen'] + ']' if st.get('chosen') else ''}", file=file)
    for b in sheet['beats']:
        print(f"  beat {b['id']} on {b['on']}", file=file)
        for e in b['levers']:
            st = catalog.status(levers[e['id']], levers)
            print(f"     {e['id']:28s} {e.get('side', ''):4s} i={e['i']:.2f} {'NOT ' if e.get('not') else ''}"
                  f"{'[' + e['chosen'] + '] ' if e.get('chosen') else ''}({st})", file=file)
        for r in b.get('review', []):
            print('     review:', r, file=file)
    for u in sheet['unmatched']:
        print(f"  UNMATCHED ({u['beat']}): {u['text']}", file=file)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('prose')
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--name', default='take')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    text = open(a.prose).read() if a.prose.endswith('.txt') else a.prose
    sheet = parse(text, a.seed, a.name)
    summary(sheet)
    if a.out:
        yaml.safe_dump(sheet, open(a.out, 'w'), sort_keys=False, width=110)


if __name__ == '__main__':
    main()
