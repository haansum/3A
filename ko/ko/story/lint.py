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
    hi = 1.6 if brief.get('shape') == 'aftermath' else 1.25      # the three-part shape may run long, never short
    add('length', 0.75 * want <= n <= hi * want, f'{n} words, brief asks {want} (allowed {int(0.75 * want)}-{int(hi * want)})')
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
    if brief.get('shape') == 'aftermath':
        parts = [x.strip() for x in re.split(r'\n\s*\*\s*\n', text.strip()) if x.strip()]
        add('three_parts', len(parts) == 3, f'{len(parts)} parts; separate lead-up, finish and aftermath with a line holding only *')
        if len(parts) == 3:
            wc = [len(words(x)) for x in parts]
            tot = max(1, sum(wc))
            sents = len([x for x in re.split(r'(?<=[.!?])\s+', parts[0]) if x.strip()])
            add('lead_up_brief', wc[0] / tot <= 0.20 and sents <= 4, f'{wc[0] / tot:.0%} of words, {sents} sentences (max 20%, 4)')
            add('finish_described', 0.15 <= wc[1] / tot <= 0.45, f'{wc[1] / tot:.0%} of words (15-45%)')
            add('talk_is_the_bulk', wc[2] / tot >= 0.45, f'{wc[2] / tot:.0%} of words (min 45%)')
            frm = (brief['finish']['facts_in_order'][0].get('arrives_from') or '')
            side = 'left' if 'left' in frm else 'right' if 'right' in frm else None
            other = {'left': 'right', 'right': 'left'}.get(side)
            p2 = parts[1].lower()
            add('strike_side_matches', side is None or (re.search(r'\b' + side + r'\b', p2) is not None),
                f'the strike arrives from her {side}; say so in the finish' if side else '')
            fb = [p_ for p_ in bank()['finish_prose']['banned_finish_phrases'] if re.search(r'\b' + re.escape(p_), p2)]
            add('finish_stock_phrases', not fb, ', '.join(fb))
            spoken = len(re.findall(r'["\u201c][^"\u201d]{8,}["\u201d]', parts[2]))
            add('talk_present', spoken >= 3 or 'no quoted speech' in brief.get('pov', ''), f'{spoken} spoken lines in the aftermath (min 3)')
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
