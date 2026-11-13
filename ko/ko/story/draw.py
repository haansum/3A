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
  3. names are retired for 40 stories (the pool holds 90 given and 80 family names)
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
HARD_WINDOW, SOFT_WINDOW, NAME_WINDOW = 3, 12, 40
# (axis, value) pairs that cannot share a story; the later-drawn axis is redrawn around it
CLASH = [
    ('pov', 'a transcript with stage directions (no interior at all)', 'register', 'whisper'),
    ('pov', 'a transcript with stage directions (no interior at all)', 'counter_register', 'whisper'),
    ('pov', 'a camera operator who only sees what is in frame', 'register', 'whisper'),
    ('pov', 'a camera operator who only sees what is in frame', 'counter_register', 'whisper'),
    ('form', 'no quoted speech at all; everything reported', 'opening_move', 'a line of speech'),
    ('form', 'dialogue-heavy, almost no description', 'register', 'silence'),
    ('form', 'starts mid-sentence in the argument', 'opening_move', 'a rule being read aloud'),
    ('register', 'translator_gap', 'pov', 'a transcript with stage directions (no interior at all)'),
    ('setting', 'group_chat', 'register', 'whisper'), ('setting', 'voicemail', 'register', 'whisper'),
    ('setting', 'video_call', 'register', 'whisper'), ('setting', 'group_chat', 'counter_register', 'whisper'),
    ('setting', 'voicemail', 'counter_register', 'whisper'), ('setting', 'video_call', 'counter_register', 'whisper'),
]
# When each place is, relative to the fight. Everything else follows from this: the moment,
# which situations can occur, who can be watching.
NIGHT = {  # at the venue on fight night: setting -> moment
    'tunnel': 'the walk', 'ramp': 'the walk', 'backstage_curtain': 'the walk', 'ring_steps': 'the walk',
    'warmup_room': 'warm-up', 'locker_room': 'warm-up', 'prefight_prayer': 'warm-up', 'cutman_table': 'warm-up',
    'cage_door': 'entering the cage', 'cage_walkaround': 'entering the cage', 'ring_apron': 'entering the ring',
    'ring_center': 'referee instructions', 'introductions': 'the introductions',
    'between_rounds': 'between rounds', 'neutral_corner': 'mid-fight, during a count', 'clinch': 'mid-fight',
    'judges_table': 'after the final bell, before the decision', 'parking_lot': 'fight night, before doors',
    **{k: 'the fight itself, opening seconds' for k in (
        'barn_show', 'ballroom_show', 'warehouse_show', 'beach_show', 'armory', 'rodeo_arena', 'theater', 'studio',
        'stadium_undercard', 'main_event_arena')}}
WEEK = {   # fight week with a fixed moment
    'weighin_gym': 'weigh-in', 'weighin_casino': 'weigh-in', 'scale_check': 'weigh-in', 'ceremonial_weighin': 'weigh-in',
    'doping_room': 'after the weigh-in', 'sauna': 'the weight cut', 'ice_bath': 'the weight cut', 'hotel_gym': 'the weight cut',
    'presser_hotel': 'media day', 'presser_dealership': 'media day', 'media_scrum': 'media day',
    'faceoff_rooftop': 'first face-off', 'staredown_stage': 'final staredown', 'hallway_medical': 'pre-fight checks',
    'commission_physicals': 'pre-fight checks', 'rules_meeting': 'the rules meeting', 'glove_selection': 'the day before',
    'walkthrough': 'the day before', 'diner': 'after weigh-ins', 'elevator': 'morning of', 'breakfast': 'morning of',
    'bus': 'fight week'}
# places that only make sense well before fight week
EARLY = {'gym_reunion', 'old_gym', 'new_gym', 'garage_gym', 'sponsor_shoot', 'school_visit', 'autograph_table',
         'podcast_kitchen', 'radio_booth', 'video_call', 'group_chat', 'voicemail', 'commission_office', 'airport',
         'open_workout_mall', 'storage_unit', 'tattoo_shop', 'laundromat', 'church_hall', 'physio_office', 'print_shop',
         'kids_class', 'ferry', 'wedding_reception', 'funeral_tea', 'car_wash', 'tv_green_room', 'amateur_show',
         'gym_closing_sale', 'seminar', 'court_corridor', 'train_platform', 'supermarket'}
# an official is only present where there is officiating
OFFICIAL_OK = set(NIGHT) - {'parking_lot', 'prefight_prayer', 'locker_room', 'warmup_room', 'tunnel', 'ramp', 'backstage_curtain'} | {
    'weighin_gym', 'weighin_casino', 'scale_check', 'ceremonial_weighin', 'doping_room', 'hallway_medical',
    'commission_physicals', 'rules_meeting', 'glove_selection', 'staredown_stage', 'commission_office', 'amateur_show'}
# a camera only where there is a shoot or a broadcast
NO_CAMERA = {'elevator', 'sauna', 'group_chat', 'voicemail', 'scale_check', 'diner', 'breakfast', 'airport', 'bus',
             'locker_room', 'warmup_room', 'parking_lot', 'gym_reunion', 'old_gym', 'garage_gym', 'storage_unit',
             'tattoo_shop', 'laundromat', 'church_hall', 'physio_office', 'print_shop', 'kids_class', 'ferry',
             'funeral_tea', 'car_wash', 'court_corridor', 'train_platform', 'supermarket', 'hotel_gym', 'hotel_laundry',
             'stairwell', 'pool_deck', 'commission_physicals', 'barbershop', 'taxi_rank', 'ice_bath', 'doping_room',
             'prefight_prayer', 'gym_closing_sale', 'seminar', 'rules_meeting', 'glove_selection'}


def phase_of(setting):
    return 'night' if setting in NIGHT else 'pre' if setting in EARLY else 'week'


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
        options = list(options)
        bad = {vb for a, va, b, vb in CLASH if b == axis and ax.get(a) == va} | \
              {va for a, va, b, vb in CLASH if a == axis and ax.get(b) == vb}
        options = [o for o in options if o not in bad] or options
        ax[axis] = sets[axis] if axis in sets else pick(rng, options, axis, past)
        return ax[axis]
    v, c, p = B['voice'], B['conflict'], B['people']
    choose('setting', B['settings']['items'])
    choose('relationship', c['relationship'])
    choose('grievance', c['grievance'])
    choose('stakes', c['stakes'])
    choose('arc', v['arc'])
    ph = phase_of(ax['setting'])
    fixed = NIGHT.get(ax['setting']) or WEEK.get(ax['setting'])
    if fixed and 'moment' not in sets:
        ax['moment'] = fixed            # the place already says when this is
    elif ph == 'pre':
        choose('moment', ['the week the contract is signed', 'six weeks out', 'two weeks out', 'the Monday of fight week'])
    else:
        choose('moment', ['fight week', 'two days before', 'the night before', 'morning of'])
    sit = B['situations']['items']
    choose('situation', [k for k, d in sit.items() if ph in d['phase']])
    povs = [x for x in v['pov']
            if not ((x.startswith('the referee') or 'official holding' in x) and ax['setting'] not in OFFICIAL_OK)
            and not (x.startswith('a camera operator') and ax['setting'] in NO_CAMERA)
            and not (x.startswith('the interpreter') and ax.get('relationship') != 'translator')]
    choose('pov', povs)
    choose('form', v['form'])
    choose('register', v['register'])
    choose('counter_register', [r for r in v['register'] if r != ax['register']])
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
        gv, fm = p['given'] + p.get('given_more', []), p['family'] + p.get('family_more', [])
        g = pick(rng, [x for x in gv if x not in used and x not in names] or gv, 'given', [])
        f = pick(rng, [x for x in fm if x not in used and x not in names] or fm, 'family', [])
        names += [g, f]
    people = []
    for k, role in enumerate(('talker', 'target')):
        people.append({'role': role, 'name': f'{names[2 * k]} {names[2 * k + 1]}',
                       'style': choose(role + '_style', [x for x in p['style'] if x != ax.get('talker_style')]),
                       'temperament': choose(role + '_temperament', [x for x in p['temperament'] if x != ax.get('talker_temperament')]),
                       'nickname': choose(role + '_nickname', [x for x in p['nickname_style'] if x == 'none' or x != ax.get('talker_nickname')])})
    ax['wrong_done_by'] = sets.get('wrong_done_by') or ('talker', 'target')[int(rng.integers(2))]
    doer = people[0 if ax['wrong_done_by'] == 'talker' else 1]['name']
    other = people[1 if ax['wrong_done_by'] == 'talker' else 0]['name']
    bans = [str(x) for x in rng.choice(B['bans']['crutch'], 6, replace=False)]
    recent_open = [q['opening_words'] for q in past[-SOFT_WINDOW:] if q.get('opening_words')]
    recent_phr = sorted({ph for q in past[-SOFT_WINDOW:] for ph in q.get('top_phrases', [])})[:12]
    place, detail = B['settings']['items'][ax['setting']]
    brief = {
        'id': f's{seed:05d}', 'seed': seed, 'axes': ax, 'names': names,
        'setting': {'place': place, 'detail': detail},
        'situation': sit[ax['situation']]['what'],
        'people': people,
        'relationship': c['relationship'][ax['relationship']],
        'grievance': {'done_by': doer, 'done_to': other, 'what': c['grievance'][ax['grievance']],
                      'note': '"she" in the text is done_by; "the other" is done_to. The aggrieved one need not be the talker.'},
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


FIGHT = [k for k, m in NIGHT.items() if m.startswith('the fight itself')] + ['cage_door', 'ring_center', 'clinch', 'neutral_corner']
LEAD_ONLY_POV = ('the interpreter', 'a sponsor', 'first person, a child', 'first person plural')


def draw_aftermath(seed, sets=None, take=None, past=None):
    """Brief for the 'aftermath' shape: a few sentences of lead-up, the finish as the sim
    shows it, the immediate aftermath, and the talk. The talk is the point."""
    from . import finish
    B = bank()
    past = ledger() if past is None else past
    rng = np.random.default_rng(seed)
    sets = dict(sets or {})
    ax = {'shape': 'aftermath'}
    v, c, p, A = B['voice'], B['conflict'], B['people'], B['aftermath']

    def choose(axis, options):
        ax[axis] = sets[axis] if axis in sets else pick(rng, list(options), axis, past)
        return ax[axis]
    choose('setting', FIGHT)
    choose('relationship', [r for r in c['relationship'] if r != 'translator'])
    choose('grievance', c['grievance'])
    choose('stakes', c['stakes'])
    sp = list(A['speaker'])
    ax['speaker'] = sets.get('speaker') or sp[int(rng.choice(len(sp), p=[A['speaker'][k] for k in sp]))]
    tn = list(A['tone'])
    ax['tone'] = sets.get('tone') or tn[int(rng.choice(len(tn), p=[A['tone'][k] for k in tn]))]
    if ax['speaker'] == 'caller':
        ax['register'] = 'house_mic'
    else:
        ug = ('roast_the_pose', 'receipts')
        choose('register', [r for r in v['register'] if r != 'house_mic' and (ax['tone'] == 'underground' or r not in ug)])
    ax['counter_register'] = None
    late = ax['speaker'] == 'loser_later'
    choose('aimed_at', [x for x in A['aimed_at'] if not (late and 'down on the canvas' in x)])
    choose('delivery', A['delivery'] if ax['speaker'] == 'winner' else ['standing at the ropes', 'from the stool', 'at the foot of the ring steps'])
    choose('timing', [x for x in A['timing'] if not late or 'sitting up' in x or 'microphone' in x or 'way out' in x])
    choose('closer_ends_on', A['closer_ends_on'])
    choose('pov', [x for x in v['pov'] if not x.startswith(LEAD_ONLY_POV) and not x.startswith('a transcript')])
    choose('sensory_anchor', v['sensory_anchor'])
    choose('result_meaning', v['result_meaning']['target_falls'] + v['result_meaning']['talker_falls'])
    choose('length_words', [360, 420, 480, 540])
    used = {n for q in past[-NAME_WINDOW:] for n in q.get('names', [])}
    gv, fm = p['given'] + p.get('given_more', []), p['family'] + p.get('family_more', [])
    names = []
    for _ in range(2):
        g = pick(rng, [x for x in gv if x not in used and x not in names] or gv, 'given', [])
        f_ = pick(rng, [x for x in fm if x not in used and x not in names] or fm, 'family', [])
        names += [g, f_]
    people = []
    for k, role in enumerate(('winner', 'loser')):
        people.append({'role': role, 'name': f'{names[2 * k]} {names[2 * k + 1]}',
                       'style': choose(role + '_style', [x for x in p['style'] if x != ax.get('winner_style')]),
                       'temperament': choose(role + '_temperament', [x for x in p['temperament'] if x != ax.get('winner_temperament')]),
                       'nickname': choose(role + '_nickname', [x for x in p['nickname_style'] if x == 'none' or x != ax.get('winner_nickname')])})
    ax['wrong_done_by'] = sets.get('wrong_done_by') or ('winner', 'loser')[int(rng.integers(2))]
    doer = people[0 if ax['wrong_done_by'] == 'winner' else 1]['name']
    other = people[1 if ax['wrong_done_by'] == 'winner' else 0]['name']
    fin = finish.from_take(take) if take else finish.drawn(rng)
    ax['finish'] = '+'.join(f['lever'] for f in fin['facts'][:3])
    FP = B['finish_prose']
    choose('lens', FP['lenses'])
    seeds = {ph: choose('seed_' + ph, opts) for ph, opts in FP['phases'].items()}
    choose('finish_sound', FP['sounds'])
    for f_ in fin['facts']:                 # one way of seeing each fact, rotated by memory
        opts = FP['renderings'].get(f_['lever'])
        if opts:
            f_['looks_like'] = choose('render:' + f_['lever'], opts)
    det = {}
    for grp, opts in A['details'].items():
        det[grp] = choose('detail_' + grp, opts)
    bans = [str(x) for x in rng.choice(B['bans']['crutch'], 6, replace=False)]
    place, detail = B['settings']['items'][ax['setting']]
    who = {'winner': people[0]['name'], 'caller': "the circuit's caller on the house mic (give him a handle); " + people[0]['name'] + ' lets him talk and adds at most one line', 'loser_corner': f"{people[1]['name']}'s cornerman (name him)",
           'loser_later': people[1]['name'] + ', once she is upright again', 'winner_corner': f"{people[0]['name']}'s cornerman (name him); she herself says nothing"}[ax['speaker']]
    return {
        'id': f's{seed:05d}', 'seed': seed, 'shape': 'aftermath', 'axes': ax, 'names': names,
        'setting': {'place': place, 'detail': detail},
        'people': people,
        'relationship': c['relationship'][ax['relationship']],
        'grievance': {'done_by': doer, 'done_to': other, 'what': c['grievance'][ax['grievance']],
                      'note': '"she" in the text is done_by; "the other" is done_to. Either may be the winner.'},
        'stakes': ax['stakes'],
        'finish': {'who_falls': people[1]['name'], 'facts_in_order': fin['facts'], 'source': fin['source'],
                   'note': "Left and right are the FALLING fighter's own. Render every fact, in this order. 'looks_like' is one way a "
                           "ringside viewer might see it: use the image, not the wording.",
                   'lens': f"{ax['lens']}: {FP['lenses'][ax['lens']]}",
                   'seeds': seeds, 'sound': ax['finish_sound']},
        'tone': ax['tone'],
        'meaning': ax['result_meaning'],
        'aftermath': {'speaker': who, 'register': f"{ax['register']}: {v['register'][ax['register']]}",
                      'aimed_at': ax['aimed_at'], 'delivery': ax['delivery'], 'timing': ax['timing'], 'ends_on': ax['closer_ends_on']},
        'details_to_use': det,
        'pov': ax['pov'], 'sensory_anchor': ax['sensory_anchor'],
        'budget': {'lead_up': 'at most 3 sentences, under 15% of the words', 'finish': 'about 30%', 'aftermath_and_talk': 'at least 50%'},
        'length_words': ax['length_words'],
        'sim_prose': fin.get('sim_prose'),
        'banned_here': bans, 'do_not_open_with': [q['opening_words'] for q in past[-SOFT_WINDOW:] if q.get('opening_words')],
        'recent_phrases_to_avoid': sorted({ph for q in past[-SOFT_WINDOW:] for ph in q.get('top_phrases', [])})[:12],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--seed', type=int, required=True)
    ap.add_argument('--take')
    ap.add_argument('--set', action='append', default=[])
    ap.add_argument('--out')
    ap.add_argument('--shape', choices=['aftermath', 'leadup'], default='aftermath')
    a = ap.parse_args(argv)
    b = (draw_aftermath if a.shape == 'aftermath' else draw)(a.seed, dict(s.split('=', 1) for s in a.set), a.take)
    text = yaml.safe_dump(b, sort_keys=False, width=110, allow_unicode=True)
    if a.out:
        open(a.out, 'w').write(text)
    print(text)


if __name__ == '__main__':
    main()
