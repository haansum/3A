"""Reject a story that repeats the bank's past or breaks its brief; record one that passes.

    python -m ko.story.lint brief.yaml story.md            # check only
    python -m ko.story.lint brief.yaml story.md --accept   # check, then add to the ledger

Checks (all mechanical, no judgement):
  length          within 25% of the brief
  banned          always-banned phrases, content boundary, this brief's own bans
  names           both drawn names appear; no name from the default-name list
  anchor          the grievance's concrete detail is on the page (a number, object or place)
  opening         first three words differ from every story in the window
  echo            share of this story's 3-word phrases already seen in past stories <= 8%
  self_repeat     no content word used more than 4 times per 100 words
  dialogue_tags   no adverb-laden tags ('she said coldly')
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

import yaml

from .draw import HERE, LEDGER, bank, ledger

DEFAULT_NAMES = ['elias', 'elara', 'mara', 'kael', 'lyra', 'aria', 'luna', 'sarah', 'jake', 'marcus', 'chen', 'thorne', 'vance']
STOP = set('the a an and or but of to in on at for with from by as is was were be been it its her she he his they them their '
           'that this had has have not no so if then than there what when who you your i me my we our said says did do '
           'would could will just out up down into over one two'.split())


def words(t):
    return re.findall(r"[a-z']+", t.lower())


def trigrams(t):
    w = words(t)
    return {' '.join(w[i:i + 3]) for i in range(len(w) - 2)}


def example_trigrams():
    p = os.path.join(HERE, 'examples', 'trash_talk.yaml')
    if not os.path.exists(p):
        return set()
    d = yaml.safe_load(open(p))
    return {t for v in d.values() for e in v for t in trigrams(e['line']) if not set(t.split()) <= STOP}


def stats(text):
    w = words(text)
    tri = Counter(' '.join(w[i:i + 3]) for i in range(len(w) - 2))
    return {'opening_words': ' '.join(w[:3]), 'n_words': len(w),
            'top_phrases': [p for p, n in tri.most_common(8) if n > 1 and not set(p.split()) <= STOP],
            'trigrams': sorted(trigrams(text))}


def check(brief, text, past=None):
    B = bank()['bans']
    past = ledger() if past is None else past
    low = text.lower()
    w = words(text)
    out = []

    def add(name, ok, detail=''):
        out.append({'check': name, 'pass': bool(ok), 'detail': detail})
    n, want = len(w), brief['length_words']
    add('length', abs(n - want) <= 0.25 * want, f'{n} words, brief asks {want}')
    hit = [p for p in B['always'] if re.search(r'\b' + re.escape(p), low)]
    add('banned_always', not hit, ', '.join(hit))
    hit = [p for p in B['boundary'] if re.search(r'\b' + re.escape(p), low)]
    add('content_boundary', not hit, ', '.join(hit))
    hit = [p for p in brief.get('banned_here', []) if re.search(r'\b' + re.escape(p) + r'\b', low)]
    add('banned_in_this_brief', not hit, ', '.join(hit))
    miss = [p['name'].split()[0] for p in brief['people'] if p['name'].split()[0].lower() not in low
            and p['name'].split()[1].lower() not in low]
    add('names_used', not miss, 'missing: ' + ', '.join(miss) if miss else '')
    hit = [x for x in DEFAULT_NAMES if re.search(r'\b' + x + r'\b', low)]
    add('no_default_names', not hit, ', '.join(hit))
    add('concrete_anchor', bool(re.search(r'\d', text)) or any(k in low for k in words(brief['grievance']['what']) if len(k) > 5),
        'needs a number or the grievance object on the page')
    op = ' '.join(w[:3])
    clash = [q['id'] for q in past if q.get('opening_words') == op and q['id'] != brief['id']]
    add('opening_is_new', not clash, f'"{op}" also opens {clash}' if clash else '')
    seen = set(example_trigrams())          # the handoff's own examples count as used text
    for q in past:
        if q['id'] != brief['id']:
            seen |= set(q.get('trigrams', []))
    tri = {t for t in trigrams(text) if not set(t.split()) <= STOP}
    echo = len(tri & seen) / max(1, len(tri))
    add('echo_of_past_stories', echo <= 0.08, f'{echo:.1%} of phrases already used')
    c = Counter(x for x in w if x not in STOP and len(x) > 3
                and x not in ' '.join(p['name'] for p in brief['people']).lower().split())
    worst = c.most_common(1)[0] if c else ('', 0)
    add('self_repeat', worst[1] <= max(3, 4 * n / 100), f'"{worst[0]}" x{worst[1]}')
    tags = re.findall(r'\b(?:said|asked|replied|whispered|muttered)\s+\w+ly\b', low)
    add('dialogue_tags', not tags, ', '.join(tags))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('brief')
    ap.add_argument('story')
    ap.add_argument('--accept', action='store_true')
    a = ap.parse_args(argv)
    brief = yaml.safe_load(open(a.brief))
    text = open(a.story).read()
    res = check(brief, text)
    for r in res:
        print(f"  [{'PASS' if r['pass'] else 'FAIL'}] {r['check']}: {r['detail']}")
    ok = all(r['pass'] for r in res)
    if ok and a.accept:
        rec = {'id': brief['id'], 'axes': brief['axes'], 'names': brief['names'], **stats(text)}
        with open(LEDGER, 'a') as f:
            f.write(json.dumps(rec) + '\n')
        print('  recorded in ledger')
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
