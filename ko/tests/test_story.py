"""Story generator: sampler memory, coherence rules, lint and candidate picker."""
import os

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
    assert on['repeated_register_arc_pov_triples'] == 0


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
