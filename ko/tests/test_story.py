"""Story generator: sampler memory, coherence rules, lint and candidate picker."""
import os
import re

import yaml

from ko import manifest
from ko.story import choose, draw, lint, measure

OUT = os.path.join(manifest.ROOT, 'ko', 'story', 'out')


def test_bank_is_well_formed():
    B = draw.bank()
    assert all(len(v) == 2 for v in B['settings']['items'].values())
    assert all(d['phase'] and d['what'] for d in B['situations']['items'].values())
    known = set(B['settings']['items'])
    assert (set(draw.NIGHT) | set(draw.WEEK) | draw.EARLY | draw.NO_CAMERA | draw.OFFICIAL_OK) <= known
    assert len(known) >= 85 and len(B['situations']['items']) >= 50 and len(B['conflict']['grievance']) >= 65


def test_draw_is_deterministic_and_complete():
    a, b = draw.draw(5, past=[]), draw.draw(5, past=[])
    assert a == b
    for k in ('setting', 'situation', 'people', 'grievance', 'talk', 'arc', 'pov', 'form', 'first_sentence_is', 'ending', 'result'):
        assert a[k]
    assert a['people'][0]['name'] != a['people'][1]['name']
    assert a['grievance']['done_by'] != a['grievance']['done_to']
    assert len(a['banned_here']) == 6


def test_memory_prevents_close_repeats():
    off, on = measure.run(50, memory=False), measure.run(50, memory=True)
    assert min(off[a]['closest_repeat'] or 99 for a in ('register', 'arc', 'form', 'pov')) == 1
    for axis in ('setting', 'grievance', 'register', 'arc', 'form', 'pov'):
        assert on[axis]['closest_repeat'] >= 4
        assert on[axis]['most_used'] <= off[axis]['most_used'] + 1
    assert on["repeated_register_arc_pov_triples"] <= 1


def test_coherence_rules_hold_over_many_seeds():
    for s in range(300):
        b = draw.draw(s, past=[])
        ax = b['axes']
        if ax['pov'].startswith('a transcript'):
            assert 'whisper' not in (ax['register'], ax['counter_register'])
        if ax['pov'].startswith('the referee'):
            assert ax['setting'] in draw.OFFICIAL_OK
        if ax['pov'].startswith('a camera operator'):
            assert ax['setting'] not in draw.NO_CAMERA
        if ax['setting'] in draw.EARLY:
            assert 'out' in ax['moment'] or 'week' in ax['moment']
        assert draw.phase_of(ax['setting']) in draw.bank()['situations']['items'][ax['situation']]['phase']
        if ax['pov'].startswith('the interpreter'):
            assert ax['relationship'] == 'translator'
        if ax['form'].startswith('no quoted speech'):
            assert ax['opening_move'] != 'a line of speech'


def test_take_link_carries_strike_side():
    b = draw.draw(13, take=os.path.join(manifest.ROOT, 'takes', 'beats', 'freya_wheel_kick_gnp_001.yaml'), past=[])
    assert 'heel kick' in b['result']['strike'] and b['result']['strike_from_her'] == 'right'


def test_worked_examples_pass_lint():
    for sid in ('s00011', 's00012', 's00013'):
        brief = yaml.safe_load(open(os.path.join(OUT, sid + '.brief.yaml')))
        res = lint.check(brief, open(os.path.join(OUT, sid + '.md')).read(), past=[])
        assert all(r['pass'] for r in res), [r for r in res if not r['pass']]


def test_lint_rejects_cliche_boundary_and_copies():
    brief = yaml.safe_load(open(os.path.join(OUT, 's00011.brief.yaml')))
    good = open(os.path.join(OUT, 's00011.md')).read()
    fails = lambda text, past=[]: {r['check'] for r in lint.check(brief, text, past) if not r['pass']}
    assert 'banned_always' in fails(good + ' The crowd roared.')
    assert 'content_boundary' in fails(good + ' There was blood on the canvas.')
    assert 'banned_in_this_brief' in fails(good + ' It was cold.')
    assert 'no_default_names' in fails(good.replace('Yara', 'Elara'))
    assert 'length' in fails(good * 3)
    other = dict(lint.stats(good), id='s99999')
    assert {'opening_is_new', 'echo_of_past_stories'} <= fails(good, [other])
    line = yaml.safe_load(open(os.path.join(manifest.ROOT, 'ko', 'story', 'examples', 'trash_talk.yaml')))['ledger'][0]['line']
    assert 'echo_of_past_stories' in fails(line + ' Yara and Wren, dancing, filmed.' + ' Wren waited.' * 20)


def test_choose_never_returns_the_likeliest_or_a_banned_line():
    c = [{'p': 0.5, 'text': 'You were late to every lesson I gave you.'},
         {'p': 0.2, 'text': 'The crowd roared for you once, in a town nobody visits.'},
         {'p': 0.15, 'text': 'I still have the bus ticket you made me buy.'},
         {'p': 0.1, 'text': 'Your corner counts your rounds on borrowed fingers.'},
         {'p': 0.05, 'text': 'Ask the scale who you are.'}]
    got = {choose.choose(c, s, past=[])['text'] for s in range(40)}
    assert c[0]['text'] not in got and c[1]['text'] not in got and len(got) >= 2


# ---- aftermath shape: brief lead-up, the finish, the talk ---------------------------------
def test_aftermath_brief_is_complete_and_coherent():
    B = draw.bank()
    speakers = []
    for seed in range(200):
        b = draw.draw_aftermath(seed, past=[])
        ax = b['axes']
        speakers.append(ax['speaker'])
        assert ax['setting'] in draw.FIGHT
        facts = b['finish']['facts_in_order']
        assert facts[0].get('arrives_from') and len(facts) >= 8
        assert all('fact' in f for f in facts)
        assert sum('looks_like' in f for f in facts) >= len(facts) - 2          # nearly every fact has an image
        assert set(b['finish']['seeds']) == set(B['finish_prose']['phases'])
        assert len(b['details_to_use']) == 5
        assert (ax['register'] == 'house_mic') == (ax['speaker'] == 'caller')
        if ax['tone'] == 'measured':
            assert ax['register'] not in ('roast_the_pose', 'receipts')
    assert 0.74 <= speakers.count('winner') / 200 <= 0.93                       # winner almost always
    assert draw.draw_aftermath(9, past=[]) == draw.draw_aftermath(9, past=[])


def test_finish_bank_covers_every_drawable_fact():
    from ko.beats import catalog
    from ko.story import finish
    _, lv = catalog.load()
    fp = draw.bank()['finish_prose']
    pools = finish.FALLS + [x for x in finish.STYLES if x] + finish.POSTURE + finish.EFFECTS + finish.WAKE + \
        [x for x in finish.GROUND if x] + finish.REST + finish.EYES
    strikes = [k for k, v in lv.items() if v.get('kind') in ('strike', 'strike_mod') and k not in ('strike.slam', 'strike.body_shot')
               and not (k.startswith('follow.') and k != 'follow.punch')]
    missing = [k for k in pools + strikes if k not in fp['renderings']]
    assert missing == [], missing
    assert all(k in lv for k in pools)
    assert all(isinstance(x, str) for v in fp['renderings'].values() for x in v) and all(len(v) >= 3 for v in fp['renderings'].values())
    assert len(fp['lenses']) >= 15 and len(fp['banned_finish_phrases']) >= 45


def test_finish_from_take_matches_the_sheet():
    from ko.story import finish
    f = finish.from_take(os.path.join(manifest.ROOT, 'takes', 'beats', 'freya_wheel_kick_gnp_001.yaml'))
    assert f['facts'][0]['arrives_from'] == 'her right' and 'heel' in f['facts'][0]['fact'].lower()
    assert any(x['lever'] == 'legs.ankles_cross' for x in f['facts'])


AFTER = """Ana Ruiz owed Bea Kovac ninety dollars for a camp.

*

The hook came from her left and Bea went over her heels. Her toes clenched. A long sawing breath started.

*

The referee knelt. Ana crouched beside her.

"Ninety dollars, Bea. Receipt 114. I kept it."

Nobody in the corner moved.

"You still owe for the camp. I wrote it on my tape."

A cup rolled down the steps.

"Keep it. Buy yourself a guard."

She left before the result was read.
"""


def test_aftermath_lint_enforces_shape_side_and_stock_phrases():
    b = draw.draw_aftermath(3, past=[])
    b['people'][0]['name'], b['people'][1]['name'] = 'Ana Ruiz', 'Bea Kovac'
    b['finish']['facts_in_order'][0]['arrives_from'] = 'her left'
    b['length_words'], b['banned_here'] = 80, []
    fails = lambda t: {r['check'] for r in lint.check(b, t, past=[]) if not r['pass']}
    assert fails(AFTER) == set(), fails(AFTER)
    assert 'three_parts' in fails(AFTER.replace('*', '', 1))
    assert 'strike_side_matches' in fails(AFTER.replace('from her left', 'from her right'))
    assert 'finish_stock_phrases' in fails(AFTER.replace('went over her heels', 'went down like a tree'))
    assert 'talk_present' in fails(AFTER.replace('"', ''))
    long_lead = AFTER.replace('for a camp.', 'for a camp. ' + 'It had been years. ' * 12)
    assert 'lead_up_brief' in fails(long_lead)


def test_trash_talk_bank_is_large_and_tagged():
    d = yaml.safe_load(open(os.path.join(manifest.ROOT, 'ko', 'story', 'examples', 'trash_talk.yaml')))
    lines = [e for v in d.values() for e in v]
    assert len(lines) >= 380 and len(d) >= 29
    assert all(e['when'] in ('before', 'after') and e['tone'] in ('measured', 'underground') and e['ctx'] and e['line'] for e in lines)
    assert sum(e['tone'] == 'underground' for e in lines) >= 120
    assert len({e['line'] for e in lines}) == len(lines)
    low = ' '.join(e['line'].lower() for e in lines)
    assert not any(re.search(r'\b' + w, low) for w in draw.bank()['bans']['boundary'])
    assert set(d) <= set(draw.bank()['voice']['register'])
