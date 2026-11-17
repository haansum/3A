"""Plan a KO sequence as panels (owner 2026-11-14): at least 70% of panels on the knockdown,
descent and aftermath; angle per panel by the manga-panel rules (skill: ko-sequence-framing).

    python3 tools/plan_sequence.py SIM.npz OUT_DIR [--fps 30]
writes OUT_DIR/beats.json (for action_frames --beats) and OUT_DIR/plan.json (angle, size, act,
why, per panel). Then:
    action_frames ... --beats beats.json --proxy OUT_DIR/proxy     -> poses + house cameras
    angle_variants OUT_DIR/proxy/proxy.json OUT_DIR/variants.json -> five angles per panel
    plan_sequence --cams OUT_DIR                                   -> OUT_DIR/cams.json
    action_frames ... --beats beats.json --cams cams.json          -> the panels

Angles: A house, B worm's-eye, C overhead, D profile, E glove-side (standing) / ringside (floor).
"""
import json
import os
import sys

import numpy as np

a = sys.argv[1:]

# panel template, relative to sim events. act: setup | strike | knockdown | descent | aftermath
# size: s (compressed tension), m, l (release), xl (the KO's landing), w (wide, quiet)
TEMPLATE = [
    # name     anchor         dt      act          angle size marks                 why
    ('read',   'ko_strike',  -0.20,  'setup',     'E',  's', [],                   'opponent-eye: the glove looms, she looks the wrong way'),
    ('rise',   'ko_strike',  -0.067, 'setup',     'A',  's', [],                   'hands dropping to the feint; compressed, small'),
    ('impact', 'ko_strike',  None,   'strike',    'C',  'l', [],                   'overhead: glove buried in the jaw, focus lines on contact'),
    ('whip',   'ko_strike',  0.067,  'strike',    'A',  'm', [],                   'the head whips; jaw forced open; spit only here'),
    ('snap',   'ko_strike',  0.13,   'knockdown', 'A',  'm', [],                   'front quarter: the face snapped away from the glove (a profile from the glove side only sees the back of the head)'),
    ('slump',  'ko_strike',  0.65,   'knockdown', 'C',  'm', ['twitch'],           'overhead: out on her feet, head dropped, small in the ring'),
    ('fall',   'down',       -0.30,  'descent',   'E',  'l', ['streak_head'],      'ringside: the onlooker sees her go back like a plank'),
    ('drop',   'down',       -0.07,  'descent',   'B',  'l', ['streak_head'],      "mat level: the limp head lags, the canvas rushes up"),
    ('canvas', 'head_impact', 0.02,  'descent',   'A',  'xl', [],                  'the release panel: head into the canvas, focus lines'),
    ('rebound', 'head_impact', 0.25, 'aftermath', 'C',  'm', ['twitch'],           'overhead: the bounce settles, limbs splayed'),
    ('gaze',   'head_impact', 0.80,  'aftermath', 'B',  'm', [],                   'close at mat level: glazed eyes, nobody home'),
    ('build',  'head_impact', 1.20,  'aftermath', 'D',  'm', ['twitch'],           'profile: the tonic build starts, fists closing'),
    ('climax', 'head_impact', 3.00,  'aftermath', 'C',  'l', ['twitch'],           'overhead: fists clenched, legs up - the involuntary peak'),
    ('still',  'end',        -0.30,  'aftermath', 'E',  'w', [],                   'ringside, wide and quiet: no lines, just the body'),
]
# never put a profile next to a worm's-eye: the viewpoint jump reads as a jump in space
FORBID = {('D', 'B'), ('B', 'D')}

if '--cams' in a:
    od = a[a.index('--cams') + 1]
    plan = json.load(open(os.path.join(od, 'plan.json')))
    var = json.load(open(os.path.join(od, 'variants.json')))
    cams = {}
    for p in plan:
        if p['angle'] != 'A':
            cams[p['name']] = var[f"{p['name']}@{p['angle']}"]
    json.dump(cams, open(os.path.join(od, 'cams.json'), 'w'), indent=1)
    print(f'[plan] cams for {len(cams)} panels (house camera for the rest) -> {od}/cams.json')
    sys.exit(0)

simp, od = a[:2]
fps = float(a[a.index('--fps') + 1]) if '--fps' in a else 30.0
z = np.load(simp, allow_pickle=True)
ev = dict(json.loads(str(z['events'])))
ev['end'] = float(z['t'][-1])
ko = ev.get('ko_strike', float(z['t_ko']))
plan, beats = [], []
for name, anchor, dt, act, angle, size, marks, why in TEMPLATE:
    t0 = ev.get(anchor)
    if t0 is None:
        continue
    t = t0 + (dt if dt is not None else 1.0 / fps)
    t = float(min(max(t, 0.0), ev['end'] - 0.05))
    if plan and (plan[-1]['angle'], angle) in FORBID:
        angle = 'E' if plan[-1]['angle'] != 'E' else 'C'
    plan.append({'name': name, 't': round(t, 3), 'act': act, 'angle': angle, 'size': size,
                 'marks': marks, 'why': why})
    beats.append({'name': name, 't': round(t, 3), 'marks': marks})
plan.sort(key=lambda p: p['t'])
beats.sort(key=lambda b: b['t'])
focus = sum(p['act'] in ('knockdown', 'descent', 'aftermath') for p in plan) / len(plan)
assert focus >= 0.70, f'only {focus:.0%} of panels on the knockdown/descent/aftermath'
os.makedirs(od, exist_ok=True)
json.dump(beats, open(os.path.join(od, 'beats.json'), 'w'), indent=1)
json.dump(plan, open(os.path.join(od, 'plan.json'), 'w'), indent=1)
print(f'[plan] {len(plan)} panels, {focus:.0%} on knockdown/descent/aftermath -> {od}')
for p in plan:
    print(f"  {p['t']:6.3f}s  {p['name']:8s} {p['act']:10s} {p['angle']} {p['size']}")
