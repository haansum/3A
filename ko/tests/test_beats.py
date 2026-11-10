"""Beat system: catalog integrity, predicates on synthetic traces, prose parsing, and the
mutation self-test (needs the prose-driven take simulated once:
  python -m ko.cli build takes/freya_wheel_kick_beats_001.yaml --to qa)"""
import os
import re

import numpy as np
import pytest
import yaml

from ko import manifest
from ko.beats import catalog, check, parse, selftest
from ko.beats.predicates import PRED
from ko.beats.trace import Trace
from ko.character.bonemap import CANON

ROOT = manifest.ROOT


def synth(T=4.0, dt=0.002):
    """She lies on her back, head toward +y, perfectly still. Tests then edit what they need."""
    n = int(T / dt)
    t = np.arange(n) * dt
    pos = np.zeros((n, len(CANON), 3))
    for k, b in enumerate(CANON):
        pos[:, k] = [0.1 if b.endswith('_L') else -0.1 if b.endswith('_R') else 0, 0, 0.1]
    pos[:, CANON.index('head'), 1] = 0.6
    pos[:, CANON.index('foot_L'), 1] = pos[:, CANON.index('foot_R'), 1] = -0.9
    # supine: body up axis (+z) points along world +y, body front (-y) points to world +z
    q = np.tile([np.cos(-np.pi / 4), np.sin(-np.pi / 4), 0, 0], (n, len(CANON), 1))
    joints = {j: np.zeros(n) for j in ('forearm_L_flex', 'forearm_R_flex', 'spine_flex', 'chest_flex', 'neck_twist',
                                       'thigh_L_flex', 'thigh_R_flex', 'shin_L_flex', 'hand_L_flex')}
    tone = {r: np.full(n, 0.5) for r in ('neck', 'trunk', 'arm_L', 'arm_R', 'leg_L', 'leg_R')}
    load = {b: np.zeros(n) for b in CANON}
    return Trace(t, CANON, pos, q, joints, tone, load, {'ko': 0.2}, 500.0)


def test_catalog_is_valid_and_large():
    assert catalog.validate() == []
    fams, levers = catalog.load()
    assert len(levers) >= 300
    for lv in levers.values():                       # every phrase compiles and is not trivially short
        for p in lv['say']:
            assert len(p) >= 3


def test_orientation_predicates():
    tr = synth()
    n = len(tr.t)
    assert PRED['facing'](tr, 0, n, body='chest', toward='up') > 0.99
    assert PRED['facing'](tr, 0, n, body='chest', toward='down') < -0.99
    assert abs(PRED['side_lying'](tr, 0, n)) < 0.01


def test_crossed_ankles_is_in_her_frame():
    tr = synth()
    n = len(tr.t)
    assert PRED['rel_gap'](tr, 0, n, a='foot_L', b='foot_R', axis='x') > 0.15      # apart
    a, b = tr.b('foot_L'), tr.b('foot_R')
    tr.pos[:, [a, b]] = tr.pos[:, [b, a]]
    assert PRED['rel_gap'](tr, 0, n, a='foot_L', b='foot_R', axis='x') < -0.15     # crossed


def test_tremor_band_and_breathing_band_are_separate():
    tr = synth()
    n = len(tr.t)
    tr.joints['forearm_L_flex'] += 2.0 * np.sin(2 * np.pi * 8 * tr.t)
    tr.joints['chest_flex'] += 3.0 * np.sin(2 * np.pi * 0.3 * tr.t)
    assert PRED['oscillation'](tr, 0, n, joints=['forearm_L_flex'], lo_hz=5, hi_hz=14) == pytest.approx(2 / np.sqrt(2), rel=0.2)
    assert PRED['oscillation'](tr, 0, n, joints=['chest_flex'], lo_hz=5, hi_hz=14) < 0.1
    assert PRED['oscillation'](tr, 0, n, joints=['chest_flex'], lo_hz=0.15, hi_hz=0.6) > 1.0


def test_contact_order_and_bounces():
    tr = synth()
    n = len(tr.t)
    tr.load['pelvis'][500:] = 300
    tr.load['head'][600:620] = 400
    tr.load['head'][700:720] = 400
    assert PRED['first_touch_gap'](tr, 0, n, first='glutes', then='head') == pytest.approx(0.2)
    assert PRED['impacts'](tr, 0, n, part='head') == 2
    assert np.isnan(PRED['first_touch_gap'](tr, 0, n, first='knees', then='head'))


def test_unmeasurable_never_passes():
    from ko.beats.predicates import judge
    assert judge(float('nan'), {'min': 0})[0] is False


def test_sporadic_tone_is_detected():
    tr = synth()
    n = len(tr.t)
    assert PRED['tone_envelope_bumps'](tr, 0, n) == 0
    tr.tone['arm_L'][800:900] = 0.9
    tr.tone['arm_L'][1200:1300] = 0.9
    assert PRED['tone_envelope_bumps'](tr, 0, n) >= 1


PROSE = open(os.path.join(ROOT, 'takes', 'beats', 'freya_wheel_kick_gnp_001.txt')).read()


def test_parse_wheel_kick_prose():
    sh = parse.parse(PROSE, seed=2)
    assert [b['on'] for b in sh['beats']] == ['ko', 'touch:head', 'followup_1']
    assert sh['strikes'][0]['lever'] == 'strike.wheel_kick' and 'hit.clips_jaw' in sh['strikes'][0]['mods']
    ids = [{e['id']: e for e in b['levers']} for b in sh['beats']]
    assert {'arms.loose_guard', 'arms.fencing', 'wrist.flex', 'trunk.slump_forward', 'fall.backward'} <= set(ids[0])
    assert ids[0]['trunk.slump_forward']['i'] == 0.25 and ids[0]['arms.fencing']['chosen'] == 'seed'
    assert {'tone.intensify', 'dyn.tremor', 'legs.scissor', 'shoulder.roll_forward'} <= set(ids[1])
    assert ids[1]['dyn.tremor']['i'] == 0.25
    assert {'tone.max', 'toes.curl', 'legs.ankles_cross', 'dyn.tremor_upper', 'face.stylized_default'} <= set(ids[2])
    assert sh['approved'] is False
    assert parse.parse(PROSE, seed=2) == sh                     # deterministic


def test_parse_side_negation_intensity():
    sh = parse.parse('A left hook. Her right arm locks out fully and there is no tremor. She ends on her back, not on her side.')
    e = {x['id']: x for b in sh['beats'] for x in b['levers']}
    assert sh['strikes'][0]['side'] == 'L'
    assert e['elbow.lock']['side'] == 'R' and e['elbow.lock']['i'] == 1.0
    assert 'dyn.no_tremor' in e and 'rest.supine' in e and 'rest.not_side' in e


def test_logged_notes_are_covered():
    """Every clause of the owner's 73 logged notes should hit the catalog, except pure
    workflow remarks ('good.', 'please examine')."""
    tot = hit = 0
    for line in open(os.path.join(ROOT, 'tests', 'data', 'log_notes.tsv')):
        for clause in [x.strip() for x in re.split(r'(?<=[.;])\s+', line.split('\t')[1]) if x.strip()]:
            sh = parse.parse(clause)
            tot += 1
            hit += bool(sh['strikes'] or any(b['levers'] for b in sh['beats']))
    assert tot > 140 and hit / tot >= 0.88


SHEET = os.path.join(ROOT, 'takes', 'beats', 'freya_wheel_kick_gnp_001.yaml')
SIM = os.path.join(manifest.stage_dir(manifest.resolve(os.path.join(ROOT, 'takes', 'freya_wheel_kick_beats_001.yaml')), 'sim'), 'sim.npz')
needs_sim = pytest.mark.skipif(not os.path.exists(SIM), reason='prose-driven take not simulated')


@needs_sim
def test_compiled_take_reaches_most_of_the_prose():
    rep = check.check(Trace.load(SIM), yaml.safe_load(open(SHEET)))
    n = rep['summary']
    assert n['pass'] >= 14 and n['fail'] <= 5


@needs_sim
def test_checker_catches_every_applicable_mutation():
    res = selftest.run(yaml.safe_load(open(SHEET)), Trace.load(SIM))
    assert [r for r in res if r['result'] == 'MISSED'] == []
    assert sum(r['result'] == 'caught' for r in res) >= 10
