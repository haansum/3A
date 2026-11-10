"""Beat sheet -> sim/bake config (the same shape as a hand-written archetype).

Every number here is a starting value tuned by eye, not measured. The compiler never claims
a lever it cannot drive: anything skipped is listed in `notes`, and the checker reports the
matching claims as FAIL or UNVERIFIED.

    python -m ko.beats.compile takes/beats/x.yaml        # print the config and notes
"""
import copy
import sys

import yaml

from . import catalog
from .check import lerp, pose_of, resolve

REGIONS = ['neck', 'trunk', 'arm_L', 'arm_R', 'leg_L', 'leg_R']
RUNTIME_EVENT = {'ko': None, 'touch:head': 'head_impact', 'down': 'down'}
BASE = {
    'sim': {'dt': 0.002, 'settle': 0.6},
    'motion': {'assist_cap': 0.15},
    'controller': {'track_hz': 3.0, 'zeta': 1.0, 'breath': {'period': 4.0, 'amp_deg': 2.0},
                   'ko': {'off_ramp': 0.04, 'residual': {'neck': 0.20, 'trunk': 0.08, 'arm': 0.035, 'leg': 0.035}}},
}
T_STRIKE = 0.58


def region_of(joint):
    stem = joint.split('_')[0]
    if stem in ('neck', 'head'):
        return 'neck'
    if stem in ('spine', 'chest'):
        return 'trunk'
    side = 'L' if '_L_' in joint else 'R'
    return ('arm_' if stem in ('upper', 'forearm', 'hand') else 'leg_') + side


def lever_regions(lv, side):
    r = lv.get('region')
    if r in ('arm', 'leg'):
        return [f'{r}_{side}'] if side in ('L', 'R') else [f'{r}_L', f'{r}_R']
    return [r] if r else []


def mirror(v, side):
    return [-v[0], v[1], v[2]] if side == 'R' else list(v)


def compile_sheet(sheet):
    fams, levers = catalog.load()
    cfg = copy.deepcopy(BASE)
    notes = []
    flat = []           # (beat index, lever, side, i, neg)
    for k, b in enumerate(sheet['beats']):
        for e in b.get('levers', []):
            if e['id'] in levers and not e.get('not'):
                flat += [(k, lv, s, i) for lv, s, i, _, _ in resolve(e, levers)]
    first = [x for x in flat if x[0] == 0]

    # ---- setup: reference motion before the strike -----------------------------------------
    adv = 0.0
    for _, lv, s, i in flat:
        st = (lv.get('layer') or {}).get('setup') or {}
        if 'advance' in st:
            adv = lerp(st['advance'], i)
    ids0 = {lv['id'] for _, lv, _, _ in flat}
    if adv == 0.0 and 'fall.backward' in ids0:
        adv = -0.30
        notes.append('fall.backward asked with no stated footwork: assumed she is giving ground (advance -0.30 m)')
    if adv == 0.0 and 'fall.forward' in ids0:
        adv = 0.30
        notes.append('fall.forward asked with no stated footwork: assumed she is stepping in (advance +0.30 m)')
    pose = 'retreat' if adv < 0 else 'lunge' if adv > 0 else 'stance'
    cfg['motion']['reference'] = {'type': 'procedural', 'keys': [
        {'t': 0.0, 'pose': 'stance', 'advance': 0.0}, {'t': 0.30, 'pose': 'stance', 'advance': 0.0},
        {'t': 0.75, 'pose': pose, 'advance': adv}, {'t': 1.5, 'pose': pose, 'advance': adv}]}

    # ---- strikes ---------------------------------------------------------------------------
    strikes, n_follow = [], 0
    for st in sheet.get('strikes', []):
        lv = levers[st['lever']]
        d = dict(lv['layer']['strike'])
        side = st.get('side') or 'L'
        out = {'name': st['name'], 'body': d.get('body', 'head'), 'duration': d.get('duration', 0.012),
               'frame': 'world', 'dir': mirror(d['dir'], side) if lv.get('side') == 'LR' else list(d['dir']),
               'offset': list(d['offset']), 'impulse': lerp(d['impulse'], st.get('i', 0.6)), 'ko': d.get('ko', st['name'] == 'ko_strike')}
        if d.get('prop'):
            out['prop'] = d['prop']
        if st['name'] == 'ko_strike':
            out['t'] = T_STRIKE
        else:
            n_follow += 1
            out['after'] = 'head_impact' if n_follow == 1 else f'followup_{n_follow - 1}'
            out['t'] = sheet.get('follow_delay_s', 1.0)
        for mid in st.get('mods', []):
            mod = levers[mid]['layer'].get('strike_mod', {})
            if 'offset' in mod:
                out['offset'] = list(mod['offset'])
            if 'impulse_scale' in mod:
                out['impulse'] *= mod['impulse_scale']
            if 'prop' in mod:
                out['prop'] = mod['prop']
            if 'dir_add' in mod:
                out['dir'] = [a + b for a, b in zip(out['dir'], mod['dir_add'])]
        out['impulse'] = round(out['impulse'], 2)
        strikes.append(out)
    if not strikes:
        notes.append('no strike recognised in the prose: nothing will knock her out')
    cfg['strikes'] = strikes

    # ---- phases: one per beat per region ---------------------------------------------------
    phases, tremor, bake = [], [], {}
    level = 0.7
    rise, hold, fade = 0.10, 3.0, 2.5
    nb = len(sheet['beats'])
    for k, b in enumerate(sheet['beats']):
        mine = [x for x in flat if x[0] == k]
        after = RUNTIME_EVENT.get(b['on'], b['on'] if b['on'].startswith('followup_') else 'UNSUPPORTED')
        if after == 'UNSUPPORTED':
            notes.append(f'beat {b["id"]}: event {b["on"]} cannot clock the controller yet; its levers are checked, not driven')
            continue
        reg_tone, reg_pose, delay = {}, {r: {} for r in REGIONS}, 0.0
        for _, lv, s, i in mine:
            L = lv.get('layer') or {}
            if 'tier' in L:
                level, hold, fade = L['tier']['tone'], L['tier']['hold_s'], L['tier']['fade_s']
            if 'tone_step' in L:
                level = min(1.0, level + lerp(L['tone_step'], i))
            if 'tone_all' in L:
                level = lerp(L['tone_all'], i)
            for key in ('rise_s', 'hold_s', 'fade_s', 'phase_delay_s'):
                if key in L:
                    v = lerp(L[key], i)
                    rise, hold, fade, delay = (v if key == 'rise_s' else rise, v if key == 'hold_s' else hold,
                                               v if key == 'fade_s' else fade, v if key == 'phase_delay_s' else delay)
        for _, lv, s, i in mine:
            L = lv.get('layer') or {}
            if 'tone' in L:
                for r in lever_regions(lv, s):
                    reg_tone[r] = lerp(L['tone'], i)
            for j, tgt in pose_of(lv, s, i).items():
                r = region_of(j)
                if j in reg_pose[r] and reg_pose[r][j] != tgt:
                    notes.append(f'beat {b["id"]}: {j} set by more than one lever; {lv["id"]} wins')
                reg_pose[r][j] = tgt
            if 'tremor' in L:
                t = L['tremor']
                if 'joints' in t or 'grow_s' in t:
                    notes.append(f'{lv["id"]}: joint-specific / growing tremor not driven yet')
                else:
                    e = {'hz': lerp(t['hz'], i), 'amp_deg': round(lerp(t['amp_deg'], i), 2), 'onset': lerp(t.get('onset', [0.4, 0.4]), i)}
                    if after:
                        e['after'] = after
                    if t.get('regions'):
                        e['regions'] = t['regions']
                    tremor.append(e)
            if 'breath' in L and 'amp_deg' in L['breath']:
                cfg['controller']['breath'] = {'period': lerp(L['breath']['period'], i), 'amp_deg': lerp(L['breath']['amp_deg'], i)}
            if 'toes' in L and 'deg' in L['toes']:
                bake['toe_curl'] = {'after': after or 'ko', 'rise': 0.25, 'deg': lerp(L['toes']['deg'], i)}
            if 'gaze' in L:
                bake['gaze'] = {'after': 'ko', 'rise': 0.12, 'up_deg': lerp(L['gaze']['up_deg'], i),
                                'side_deg': lerp(L['gaze']['side_deg'], i), 'side': 'her_right' if s == 'R' else 'her_left'}
            if 'arena' in L:
                cfg.setdefault('arena_overrides', {}).update({a: lerp(v, i) if isinstance(v, list) else v for a, v in L['arena'].items()})
            unsupported = set(L) - catalog.DRIVEN
            if unsupported and not lv.get('pose'):
                notes.append(f'{lv["id"]}: layer {sorted(unsupported)} is not driven yet')
        last = k == nb - 1
        for r in REGIONS:
            ph = {'t': 0.03 + delay if after else delay, 'rise': rise, 'hold': hold if last else 60.0, 'fade': fade,
                  'regions': [r], 'tone': round(float(reg_tone.get(r, level)), 3), 'replace': True}
            if after:
                ph['after'] = after
            if reg_pose[r]:
                ph['pose_rel'] = reg_pose[r]
            phases.append(ph)
    cfg['controller']['ko']['phases'] = phases
    cfg['controller']['ko']['tremor'] = tremor
    cfg['bake'] = bake
    cfg['sim']['duration'] = round(T_STRIKE + 1.3 + 1.0 * n_follow + 0.6 + hold + min(fade, 2.0), 1)
    cfg['outcome'] = {'name': 'beats', 'sheet': sheet}
    cfg['name'] = 'beats:' + sheet.get('take', 'take')
    return cfg, notes


def main(argv=None):
    sheet = yaml.safe_load(open((argv or sys.argv[1:])[0]))
    cfg, notes = compile_sheet(sheet)
    cfg['outcome'] = {'name': 'beats', 'sheet': '(embedded)'}
    print(yaml.safe_dump(cfg, sort_keys=False, width=140, default_flow_style=None))
    for n in notes:
        print('NOTE', n)


if __name__ == '__main__':
    main()
