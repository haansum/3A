"""Draw a story brief: one seeded combination of bank values, steered away from anything
used recently. The brief is the whole creative constraint for one story; the writing model
adds prose, not choices.

    python -m ko.story.draw --seed 7                      # print a brief
    python -m ko.story.draw --seed 7 --take takes/beats/x.yaml   # tie the ending to a real take
    python -m ko.story.draw --seed 7 --set register=ledger --set talker_falls=true

Anti-repetition, in order of strength:
  1. every axis is drawn independently, so the space is ~1e17 combinations
  2. values used in the last 3 stories are excluded; values used in the last 12 are
     down-weighted (ledger: ko/story/ledger.jsonl)
  3. names are retired for 30 stories
  4. each brief carries its own word bans (a rotating sample of ordinary crutch words plus
     the opening words and commonest phrases of recent stories)
  5. the first sentence type, point of view, form and ending are drawn, not left to habit
"""
import argparse
import glob
import json
import os
import re
import sys

import numpy as np
import yaml

HERE = os.path.dirname(__file__)
LEDGER = os.path.join(HERE, 'ledger.jsonl')
HARD_WINDOW, SOFT_WINDOW, NAME_WINDOW = 3, 12, 30
IMPLIED_MOMENT = [('weighin', 'weigh-in'), ('scale_check', 'weigh-in'), ('sauna', 'the weight cut'), ('presser', 'media day'),
                  ('faceoff', 'first face-off'), ('staredown_stage', 'final staredown'), ('tunnel', 'the walk'),
                  ('warmup_room', 'warm-up'), ('locker_room', 'warm-up'), ('cage_door', 'entering the cage'),
                  ('ring_center', 'referee instructions'), ('between_rounds', 'between rounds'),
                  ('hallway_medical', 'pre-fight checks'), ('_show', 'the fight itself, opening seconds'),
                  ('armory', 'the fight itself, opening seconds'), ('rodeo_arena', 'the fight itself, opening seconds'),
                  ('theater', 'the fight itself, opening seconds'), ('studio', 'the fight itself, opening seconds'),
                  ('stadium_undercard', 'the fight itself, opening seconds'), ('main_event_arena', 'the fight itself, opening seconds'),
                  ('diner', 'after weigh-ins'), ('elevator', 'morning of'), ('breakfast', 'morning of')]


def bank():
    out = {}
    for f in sorted(glob.glob(os.path.join(HERE, 'bank', '*.yaml'))):
        out[os.path.basename(f)[:-5]] = yaml.safe_load(open(f))
    return out


def ledger():
    if not os.path.exists(LEDGER):
        return []
    return [json.loads(x) for x in open(LEDGER) if x.strip()]


def pick(rng, options, axis, past):
    """Weighted choice: never a value from the last 3 briefs, rarely one from the last 12."""
    options = list(options)
    recent = [p['axes'].get(axis) for p in past]
    hard = set(recent[-HARD_WINDOW:])
    w = np.array([0.0 if (o in hard and len(options) > HARD_WINDOW + 1)
                  else 1.0 / (1.0 + 4.0 * recent[-SOFT_WINDOW:].count(o)) for o in options])
    return options[int(rng.choice(len(options), p=w / w.sum()))]


def from_take(path):
    """Closing image from a real beat sheet: the strike and how she falls."""
    sh = yaml.safe_load(open(path))
    from ..beats import catalog
    _, levers = catalog.load()
    st = (sh.get('strikes') or [{}])[0]
    ids = [e['id'] for b in sh['beats'] for e in b['levers']]
    fall = next((levers[i]['label'] for i in ids if i.startswith('fall.')), None)
    tier = next((levers[i]['label'] for i in ids if i.startswith('tier.')), None)
    return {'take': sh.get('take'), 'strike': levers[st['lever']]['label'] if st.get('lever') else None,
            'strike_from_her': {'L': 'left', 'R': 'right'}.get(st.get('side')), 'fall': fall, 'tier': tier,
            'followups': sum(1 for s in sh.get('strikes', []) if s['name'].startswith('followup'))}


def draw(seed, sets=None, take=None, past=None):
    B = bank()
    past = ledger() if past is None else past
    rng = np.random.default_rng(seed)
    sets = dict(sets or {})
    ax = {}

    def choose(axis, options):
        ax[axis] = sets[axis] if axis in sets else pick(rng, options, axis, past)
        return ax[axis]
    v, c, p = B['voice'], B['conflict'], B['people']
    choose('setting', B['settings']['items'])
    choose('relationship', c['relationship'])
    choose('grievance', c['grievance'])
    choose('stakes', c['stakes'])
    choose('register', v['register'])
    choose('counter_register', [r for r in v['register'] if r != ax['register']])
    choose('arc', v['arc'])
    fixed = next((m for k, m in IMPLIED_MOMENT if ax['setting'].startswith(k) or ax['setting'].endswith(k)), None)
    if fixed and 'moment' not in sets:
        ax['moment'] = fixed            # the place already says when this is
    else:
        choose('moment', ['contract signing', 'media day', 'open workout', 'the night before', 'morning of'])
    choose('pov', v['pov'])
    choose('form', v['form'])
    choose('opening_move', v['opening_move'])
    choose('ending', v['ending'])
    choose('sensory_anchor', v['sensory_anchor'])
    falls = sets.get('talker_falls')
    falls = bool(rng.integers(2)) if falls is None else str(falls).lower() in ('1', 'true', 'yes')
    ax['who_falls'] = 'talker' if falls else 'target'
    choose('result_meaning', v['result_meaning']['talker_falls' if falls else 'target_falls'])
    choose('length_words', [120, 160, 200, 260, 320])
    used = {n for q in past[-NAME_WINDOW:] for n in q.get('names', [])}
    names = []
    for _ in range(2):
        g = pick(rng, [x for x in p['given'] if x not in used and x not in names] or p['given'], 'given', [])
        f = pick(rng, [x for x in p['family'] if x not in used and x not in names] or p['family'], 'family', [])
        names += [g, f]
    people = []
    for k, role in enumerate(('talker', 'target')):
        people.append({'role': role, 'name': f'{names[2 * k]} {names[2 * k + 1]}',
                       'style': choose(role + '_style', [x for x in p['style'] if x != ax.get('talker_style')]),
                       'temperament': choose(role + '_temperament', [x for x in p['temperament'] if x != ax.get('talker_temperament')]),
                       'nickname': p['nickname_style'][int(rng.integers(len(p['nickname_style'])))]})
    bans = [str(x) for x in rng.choice(B['bans']['crutch'], 6, replace=False)]
    recent_open = [q['opening_words'] for q in past[-SOFT_WINDOW:] if q.get('opening_words')]
    recent_phr = sorted({ph for q in past[-SOFT_WINDOW:] for ph in q.get('top_phrases', [])})[:12]
    place, detail = B['settings']['items'][ax['setting']]
    brief = {
        'id': f's{seed:05d}', 'seed': seed, 'axes': ax, 'names': names,
        'setting': {'place': place, 'detail': detail},
        'people': people,
        'relationship': c['relationship'][ax['relationship']],
        'grievance': c['grievance'][ax['grievance']],
        'stakes': ax['stakes'],
        'talk': {'talker_register': f"{ax['register']}: {v['register'][ax['register']]}",
                 'target_register': f"{ax['counter_register']}: {v['register'][ax['counter_register']]}"},
        'arc': {'name': ax['arc'], 'beats': v['arc'][ax['arc']]},
        'moment': ax['moment'], 'pov': ax['pov'], 'form': ax['form'],
        'first_sentence_is': ax['opening_move'], 'ending': ax['ending'],
        'sensory_anchor': ax['sensory_anchor'],
        'result': {'who_falls': ax['who_falls'], 'meaning': ax['result_meaning'], **(from_take(take) if take else {})},
        'length_words': ax['length_words'],
        'banned_here': bans, 'do_not_open_with': recent_open, 'recent_phrases_to_avoid': recent_phr,
    }
    return brief


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--take')
    ap.add_argument('--set', action='append', default=[])
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    b = draw(a.seed, dict(s.split('=', 1) for s in a.set), a.take)
    text = yaml.safe_dump(b, sort_keys=False, width=110, allow_unicode=True)
    if a.out:
        open(a.out, 'w').write(text)
    print(text)


if __name__ == '__main__':
    main()
