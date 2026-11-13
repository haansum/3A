"""The finish as plain facts, taken from the same lever catalog that drives the simulation,
so the prose and the animation describe one event.

With a take: the facts are read off its beat sheet in order.
Without one: a finish is drawn (strike, where it lands, how she falls, what her body does,
how she comes to rest, an optional follow-up) and a one-line description is produced that
`ko.beats.parse` can turn into a beat sheet, so a story can commission its own animation.
"""
import yaml

from ..beats import catalog

FALLS = ['fall.backward', 'fall.forward', 'fall.sideways', 'fall.straight_down']
STYLES = ['fall.timber', 'fall.teeter', 'fall.delayed', 'fall.instant', 'fall.sit_then_back', 'fall.knees_first', 'fall.spin', None, None]
POSTURE = ['arms.fencing', 'arms.both_extended', 'arms.both_flexed', 'arms.drop_limp', 'arms.guard_frozen', 'arms.starfish',
           'legs.extend_stiff', 'legs.buckle', 'legs.scissor', 'legs.ankles_cross', 'legs.one_straight_one_bent', 'legs.folded_under',
           'trunk.rigid_plank', 'trunk.limp', 'trunk.slump_forward', 'trunk.back_curl', 'neck.chin_up', 'neck.limp', 'neck.turn',
           'feet.point', 'toes.curl', 'wrist.flex', 'hand.half_fist', 'dyn.tremor', 'dyn.tremor_upper', 'feet.stay_planted',
           'neck.chin_tuck', 'neck.head_off_mat', 'trunk.back_arch', 'trunk.upper_back_hunch', 'shoulder.roll_forward', 'arms.loose_guard']
# observable effects while she is out, and as she comes round (catalog family ko_effects)
EFFECTS = ['fx.snore', 'fx.snore_late', 'fx.first_breath', 'fx.lip_flutter', 'fx.cheek_puff', 'fx.breath_hitch', 'fx.groan',
           'fx.mouthguard_whistle', 'fx.jaw_work', 'fx.lip_smack', 'fx.tongue_guard', 'fx.mumble', 'fx.slow_blink', 'fx.eyes_open_out',
           'fx.arm_float', 'fx.arm_sink_stages', 'fx.hands_paw', 'fx.fingers_fan', 'fx.fingers_piano', 'fx.wrist_curl_in',
           'fx.guard_ghost', 'fx.glove_tap', 'fx.shrug_hold', 'fx.shudder', 'fx.knee_quiver', 'fx.foot_paddle', 'fx.toes_fan',
           'fx.heel_dig', 'fx.back_bow_release', 'fx.head_lift_drop']
WAKE = ['fx.eyes_come_back', 'fx.track_late', 'wake.grabs_ref', 'wake.fights_ref', 'wake.sits_too_fast', 'wake.legs_dont_answer',
        'wake.wrong_corner', 'wake.asks', 'wake.argues', 'wake.keeps_guard', 'wake.wipes_mouth', 'wake.pushes_help', 'wake.smile',
        'wake.looks_at_gloves']
GROUND = ['ground.head_bounce', 'ground.slide', 'ground.no_head_hit', None]
REST = ['rest.supine', 'rest.prone', 'rest.side', 'rest.seated', 'rest.kneeling_folded']
EYES = ['eyes.gaze_up_corner', 'eyes.vacant_forward', 'eyes.rolled_up', 'eyes.lids_half']
SIDE = {'L': 'her left', 'R': 'her right'}


def _fact(levers, lid, side=None):
    lab = levers[lid]['label'].split(' (')[0].split(': ')[-1] if lid.startswith('tier.') else levers[lid]['label']
    return {'lever': lid, 'fact': lab + (f' ({SIDE[side]})' if side in SIDE and levers[lid].get('side') == 'LR' else '')}


def drawn(rng):
    _, lv = catalog.load()
    strikes = [k for k, v in lv.items() if v.get('kind') == 'strike' and not k.startswith('follow.') and k not in ('strike.slam', 'strike.body_shot')]
    mods = [k for k, v in lv.items() if v.get('kind') == 'strike_mod']
    pick = lambda xs: xs[int(rng.integers(len(xs)))]
    side = 'LR'[int(rng.integers(2))]
    s = pick(strikes)
    facts = [dict(_fact(lv, s), arrives_from=SIDE[side] if lv[s].get('side') == 'LR' else 'in front of her')]
    facts.append(_fact(lv, pick(mods)))
    fall = pick(FALLS)
    facts.append(_fact(lv, fall, 'LR'[int(rng.integers(2))]))
    st = pick(STYLES)
    if st:
        facts.append(_fact(lv, st, 'LR'[int(rng.integers(2))]))
    for p in rng.choice(POSTURE, 2, replace=False):
        facts.append(_fact(lv, str(p), 'LR'[int(rng.integers(2))]))
    g = pick(GROUND)
    if g:
        facts.append(_fact(lv, g))
    rest = {'fall.backward': ['rest.supine', 'rest.supine', 'rest.seated'], 'fall.forward': ['rest.prone', 'rest.prone', 'rest.kneeling_folded'],
            'fall.sideways': ['rest.side', 'rest.supine'], 'fall.straight_down': ['rest.seated', 'rest.kneeling_folded', 'rest.side']}[fall]
    facts.append(_fact(lv, pick(rest), 'LR'[int(rng.integers(2))]))
    facts.append(_fact(lv, pick(EYES), 'LR'[int(rng.integers(2))]))
    for p in rng.choice(EFFECTS, 2, replace=False):
        facts.append(dict(_fact(lv, str(p), 'LR'[int(rng.integers(2))]), when='while she is out'))
    follow = int(rng.choice([0, 0, 0, 1, 1, 2]))
    if follow:
        facts.append({'lever': 'follow.punch', 'fact': f'{follow} follow-up strike{"s" if follow > 1 else ""} on the canvas before the referee arrives'})
    facts.append(dict(_fact(lv, pick(WAKE), 'LR'[int(rng.integers(2))]), when='as she comes round (belongs in the aftermath, not the finish)'))
    words = [lv[f['lever']]['say'][0] + (' from her ' + f['arrives_from'].split()[-1] if 'her ' in f.get('arrives_from', '') else '') for f in facts]
    return {'source': 'drawn', 'facts': facts, 'sim_prose': '. '.join(words) + '.'}


def from_take(path):
    sh = yaml.safe_load(open(path))
    _, lv = catalog.load()
    facts = []
    for st in sh.get('strikes', []):
        f = _fact(lv, st['lever'], st.get('side'))
        if st['name'] == 'ko_strike':
            f['arrives_from'] = SIDE.get(st.get('side'), 'in front of her')
        else:
            f['fact'] = 'follow-up strike on the canvas, about a second after she lands'
        for m in st.get('mods', []):
            f['fact'] += '; ' + lv[m]['label']
        facts.append(f)
    ko = facts[:1]
    rest = facts[1:]
    for b in sh['beats']:
        when = {'ko': 'on her feet, right after the strike', 'touch:head': 'when her head meets the canvas',
                'down': 'when she reaches the canvas', 'rest': 'at rest'}.get(b['on'], 'after the follow-up strike' if b['on'].startswith('followup') else b['on'])
        if b['on'].startswith('followup') and rest:
            ko.append(rest.pop(0))
        for e in b['levers']:
            if e['id'] in lv and not e.get('not') and not e['id'].startswith(('cam.', 'look.', 'face.stylized', 'tone.')):
                f = _fact(lv, e['id'], e.get('side'))
                f['when'] = when
                ko.append(f)
        if any(e['id'] in ('tone.intensify', 'tone.max') for e in b['levers']):
            ko.append({'lever': 'tone', 'fact': 'her whole posture tightens further' if b['on'] != 'ko' else 'she stiffens', 'when': when})
    return {'source': sh.get('take'), 'facts': ko + rest, 'sim_prose': sh.get('prose')}
