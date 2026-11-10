"""Map an arbitrary humanoid rig's bone names onto the canonical sim skeleton.

Pure Python (no bpy) so it is unit-testable. Works from names plus hierarchy:
limbs, hips and head are found by name; spine, chest and neck by topology
(the chain between hips and head), which is what differs most between rigs.

Covers VRoid/VRM (J_Bip_*), Mixamo (mixamorig:*), Rigify (DEF-*), Unreal/Daz-style
names. Anything else: pass an explicit override map {canonical: bone_name}.
"""
import re

CANON = ['pelvis', 'spine', 'chest', 'neck', 'head',
         'upper_arm_L', 'forearm_L', 'hand_L', 'upper_arm_R', 'forearm_R', 'hand_R',
         'thigh_L', 'shin_L', 'foot_L', 'thigh_R', 'shin_R', 'foot_R']
PARENT = {'pelvis': None, 'spine': 'pelvis', 'chest': 'spine', 'neck': 'chest', 'head': 'neck',
          'upper_arm_L': 'chest', 'forearm_L': 'upper_arm_L', 'hand_L': 'forearm_L',
          'upper_arm_R': 'chest', 'forearm_R': 'upper_arm_R', 'hand_R': 'forearm_R',
          'thigh_L': 'pelvis', 'shin_L': 'thigh_L', 'foot_L': 'shin_L',
          'thigh_R': 'pelvis', 'shin_R': 'thigh_R', 'foot_R': 'shin_R'}

# bones (and meshes/materials) that are secondary motion, never part of the sim body
SECONDARY = re.compile(r'(hair|skirt|cloth|coat|cape|tail|ribbon|sec_|_sec|spring|'
                       r'(^|[-_. ])ears?([-_. ]|$)|accessor|hood|sleeve|wing)', re.I)
HELPER = re.compile(r'^(ik|mch|org|ctrl|wgt|vis|pole|target)[-_.]|[-_.](ik|pole|target)\b', re.I)

LIMB = [  # (canonical stem, patterns tried in order against the normalised name)
    ('upper_arm', [r'upper_?arm', r'^arm$', r'arm_?upper', r'shoulder_?01$']),
    ('forearm', [r'fore_?arm', r'lower_?arm', r'arm_?lower', r'elbow']),
    ('hand', [r'^hand$', r'wrist']),
    ('thigh', [r'thigh', r'upper_?leg', r'up_?leg', r'leg_?upper']),
    ('shin', [r'shin', r'lower_?leg', r'calf', r'leg_?lower', r'^leg$', r'knee']),
    ('foot', [r'^foot$', r'ankle']),
    ('clavicle', [r'clavicle', r'collar', r'^shoulder$']),
    ('toe', [r'^toe', r'ball']),
]


def split_side(name):
    """-> (stem, 'L'|'R'|None). Handles Left/Right words and _L/.L/-l style affixes."""
    n = name
    n = re.sub(r'^(mixamorig\d*[:_]|def[-_.]|j_bip_|j_adj_|bip\d*[ _]?|b_|bn_|cc_base_)', '', n,
               flags=re.I)
    side = None
    m = re.search(r'(left|right)', n, re.I)
    if m:
        side = 'L' if m.group(1).lower() == 'left' else 'R'
        n = n[:m.start()] + n[m.end():]
    else:
        m = (re.search(r'(^|[-_. ])([lr])([-_. ]|$)', n, re.I)
             or re.search(r'[a-z0-9]([LR])$', n))
        if m:
            g = m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1)
            side = g.upper()
            n = n[:m.start()] + '_' + n[m.end():] if m.lastindex and m.lastindex >= 2 \
                else n[:-1]
    n = re.sub(r'[-. ]', '_', n).strip('_').lower()
    n = re.sub(r'_+', '_', n)
    return n, side


def auto_map(bones, override=None):
    """bones: {name: parent_name|None} for every bone of the armature.
    Returns ({canonical: bone_name}, report dict). Raises ValueError listing what is missing."""
    override = dict(override or {})
    cand = {n: split_side(n) for n in bones
            if not HELPER.search(n) and not SECONDARY.search(n)}
    depth = {}

    def d(n):
        if n not in depth:
            depth[n] = 0 if bones[n] is None else d(bones[n]) + 1
        return depth[n]

    out, aux = {}, {}
    for stem, pats in LIMB:
        for side in 'LR':
            key = f'{stem}_{side}'
            hits = []
            for pi, p in enumerate(pats):
                hits = [n for n, (s, sd) in cand.items() if sd == side and re.search(p, s)
                        and not re.search(r'twist|roll|\d{2,}$|_0*[2-9]$', s)]
                if hits:
                    break
            if hits:
                best = min(hits, key=lambda n: (d(n), len(n)))
                (aux if stem in ('clavicle', 'toe') else out)[key] = best

    def find_center(pats):
        for p in pats:
            hits = [n for n, (s, sd) in cand.items() if sd is None and re.search(p, s)]
            if hits:
                return min(hits, key=lambda n: (d(n), len(n)))
        return None

    out['pelvis'] = find_center([r'^c?_?hips?$', r'pelvis', r'hips?', r'^spine$', r'root'])
    out['head'] = find_center([r'^c?_?head$', r'head'])
    out.update({k: v for k, v in override.items() if k in CANON})
    if not out.get('head') and out.get('pelvis'):
        # Rigify-style numbered spine (spine, spine.001 ... spine.006): the head is the end of
        # the main chain. Follow, from the pelvis, the spine-named child with the deepest
        # subtree (side branches such as belly helpers are shallow).
        kids = {}
        for n, par in bones.items():
            kids.setdefault(par, []).append(n)

        def depth_below(n):
            return 1 + max((depth_below(c) for c in kids.get(n, [])), default=0)

        cur = out['pelvis']
        while True:
            nxt = [c for c in kids.get(cur, []) if c in cand and cand[c][1] is None
                   and cand[c][0].startswith('spine')]
            if not nxt:
                break
            cur = max(nxt, key=depth_below)
        if cur != out['pelvis']:
            out['head'] = cur

    missing = [k for k in CANON if k not in ('spine', 'chest', 'neck') and not out.get(k)]
    if missing:
        raise ValueError(f'could not map {missing}; pass an override map. Bones: {sorted(bones)}')

    # the pelvis must be an ancestor of both thighs; climb if the name match was too deep/shallow
    def ancestors(n):
        r = []
        while n is not None:
            r.append(n)
            n = bones[n]
        return r

    common = [a for a in ancestors(out['thigh_L']) if a in ancestors(out['thigh_R'])]
    chain = ancestors(out['head'])            # head ... root
    if out['pelvis'] not in chain or out['pelvis'] not in common:
        out['pelvis'] = next(a for a in common if a in chain)
    between = chain[1:chain.index(out['pelvis'])][::-1]   # pelvis-exclusive .. head-exclusive
    if not between:
        raise ValueError('no bones between pelvis and head; cannot place spine/chest/neck')
    arm_anc = ancestors(out['upper_arm_L'])
    fork = next((b for b in between[::-1] if b in arm_anc), between[-1])  # where arms attach
    fi = between.index(fork)
    neck_bones = between[fi + 1:]
    trunk = between[:fi + 1]
    topo = {'neck': neck_bones[0] if neck_bones else None,
            'spine': trunk[0],
            # chest = the trunk bone nearest the middle of the remaining chain, else the fork
            'chest': trunk[max(1, len(trunk) // 2)] if len(trunk) > 1 else None}
    for k, v in topo.items():
        out.setdefault(k, v) if k not in override else None
        if out.get(k) is None:
            out[k] = v
    report = {'spine_chain': between, 'fork': fork, 'aux': aux,
              'merged': [k for k in ('spine', 'chest', 'neck') if out.get(k) is None]}
    return out, report


def owner_of_every_bone(bones, cmap):
    """Each rig bone -> the canonical body that carries it (nearest mapped ancestor), or None
    for secondary chains (hair, skirt...) which must not shape the collision body."""
    inv = {v: k for k, v in cmap.items() if v}
    own = {}

    def f(n):
        if n in own:
            return own[n]
        if n in inv:
            own[n] = inv[n]
        elif SECONDARY.search(n):
            own[n] = None
        elif bones[n] is None:
            own[n] = None
        else:
            own[n] = f(bones[n])
        return own[n]

    for n in bones:
        f(n)
    return own
