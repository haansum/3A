"""Stage 2: body model. skeleton.json + skin.npz -> body.json (the sim body spec).

Every sim body frame is world-aligned in the rig's rest pose and sits on the bone head, so
a body's world rotation IS the bone's rotation away from rest. That makes the retarget back to
the rig convention-free (and is checked numerically by the round-trip test in bake).

Collision shapes are convex hulls of the skin vertices each bone owns, unshrunk, so sim contact
happens at the rendered surface (old pipeline lesson: shrunk hulls clip in render).

Numbers and their status:
  MASS_FRACTION  literature (de Leva 1996, female), quoted from memory - verify before citing
  ROM            textbook-typical ranges of motion, approximate
  TORQUE         order-of-magnitude isometric strengths for a ~60 kg athlete, tuned by eye
  PASSIVE_DAMP   eyeballed
"""
import json
import os

import numpy as np
from scipy.spatial import ConvexHull

from ..character.bonemap import CANON, PARENT

MASS_FRACTION = {'pelvis': .1247, 'spine': .1465, 'chest': .1545, 'neck': .012, 'head': .0548,
                 'upper_arm': .0255, 'forearm': .0138, 'hand': .0056,
                 'thigh': .1478, 'shin': .0481, 'foot': .0129}
REGION = {'pelvis': 'trunk', 'spine': 'trunk', 'chest': 'trunk', 'neck': 'neck', 'head': 'neck',
          'upper_arm': 'arm', 'forearm': 'arm', 'hand': 'arm',
          'thigh': 'leg', 'shin': 'leg', 'foot': 'leg'}
PASSIVE_DAMP = {'trunk': 3.0, 'neck': 0.4, 'arm': 0.3, 'leg': 1.0}   # N m s/rad
MAX_HULL = 96


def unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def palm_normal(hull, side):
    """Unit normal out of the palm, from the hand's own shape: the thin axis of its hull,
    signed toward down/medial (true for every T- and A-pose rest). None if there is no hull."""
    if hull is None or len(hull) < 8:
        return None
    H = np.asarray(hull) - np.mean(hull, axis=0)
    n = np.linalg.eigh(H.T @ H)[1][:, 0]
    s = 1.0 if side == 'L' else -1.0
    return n if n @ np.array([-s, 0.0, -1.0]) > 0 else -n


def joint_table(stem, side, d, fwd, palm=None):
    """[(dof name, axis, lo, hi deg, torque N m, rest offset deg)] for the joint above `stem`.
    Positive angle = the anatomical motion in the dof name. d = rest limb direction."""
    s = 1.0 if side == 'L' else -1.0
    X, Y, Z = np.eye(3)
    if stem in ('spine', 'chest'):
        lo = (-20, 45, 20, 15) if stem == 'spine' else (-15, 30, 20, 30)
        return [('flex', X, lo[0], lo[1], 180, 0), ('lat', Y, -lo[2], lo[2], 120, 0),
                ('twist', Z, -lo[3], lo[3], 70, 0)]
    if stem == 'neck':
        return [('flex', X, -40, 45, 30, 0), ('lat', Y, -35, 35, 25, 0), ('twist', Z, -60, 60, 15, 0)]
    if stem == 'head':
        return [('flex', X, -20, 20, 15, 0), ('lat', Y, -15, 15, 12, 0)]
    if stem == 'thigh':
        return [('flex', -X, -20, 120, 150, 0), ('abd', -s * Y, -30, 45, 100, 0),
                ('twist', s * Z, -40, 40, 50, 0)]
    if stem == 'shin':
        return [('flex', X, 0, 150, 150, 0)]
    if stem == 'foot':
        return [('dorsi', -X, -45, 25, 100, 0), ('inv', s * Y, -20, 20, 30, 0)]
    elbow = unit(np.cross(d, fwd))             # moves the distal segment toward the front
    if stem == 'upper_arm':
        elev = np.degrees(np.arctan2(d[2], abs(d[0])))   # 0 = T-pose, -45 = A-pose
        # 'abd' is expressed as absolute elevation (-90 hanging, 0 horizontal): offset = rest
        return [('abd', s * fwd, -110, 80, 60, elev), ('flex', elbow, -45, 140, 60, 0),
                ('twist', s * d, -80, 80, 30, 0)]
    if stem == 'forearm':
        return [('flex', elbow, 0, 150, 50, 0)]
    if stem == 'hand':
        # anatomical wrist axes from the palm itself (measured: the elbow axis is the
        # deviation axis on a palm-down rest pose, so it must not be reused here).
        # flex + = palmar flexion (fingers toward the palm side), dev + = toward the thumb...
        # thumb side is not known from shape, so dev + = toward her front at rest.
        if palm is None:
            palm = -Z
        palm = unit(palm - (palm @ d) * d)
        fax = unit(np.cross(d, palm))                  # rotates d toward the palm normal
        dax = palm if np.cross(palm, d) @ fwd > 0 else -palm
        return [('flex', fax, -70, 70, 10, 0), ('dev', dax, -25, 25, 8, 0),
                ('twist', s * d, -80, 80, 8, 0)]
    raise KeyError(stem)


def clean_points(pts, a, b, side, keep=2.0):
    """Drop stray vertices (hidden template geometry, loose garment hems) that would inflate
    the hull: anything much farther from the bone axis than the bulk. Then keep left/right
    limbs on their own side of the sagittal plane so the legs do not start interpenetrating."""
    if len(pts) < 8:
        return pts
    if b is not None:
        ab = b - a
        t = np.clip((pts - a) @ ab / (ab @ ab), -0.15, 1.15)
        dist = np.linalg.norm(pts - (a + t[:, None] * ab), axis=1)
    else:
        dist = np.linalg.norm(pts - np.median(pts, axis=0), axis=1)
    pts = pts[dist <= keep * np.percentile(dist, 80) + 1e-6]
    if side and b is not None and abs(b[0] - a[0]) < 0.5 * abs(b[2] - a[2]):   # legs only
        sgn = 1.0 if side == 'L' else -1.0
        pts = pts.copy()
        pts[:, 0] = sgn * np.maximum(sgn * pts[:, 0], 0.001)
    return pts


def hull_points(pts):
    if len(pts) < 8:
        return None
    try:
        h = ConvexHull(pts)
    except Exception:
        return None
    p = pts[h.vertices]
    if len(p) > MAX_HULL:                      # farthest-point subsample keeps the extremes
        idx = [int(np.argmax(np.linalg.norm(p - p.mean(0), axis=1)))]
        dist = np.linalg.norm(p - p[idx[0]], axis=1)
        while len(idx) < MAX_HULL:
            i = int(np.argmax(dist))
            idx.append(i)
            dist = np.minimum(dist, np.linalg.norm(p - p[i], axis=1))
        p = p[idx]
    return p


def build(char_dir, mass=60.0, hull_opts=None):
    """hull_opts: {'keep': {stem: factor}} widens the stray-vertex filter per segment. Dense
    toe meshes (Daz) pull the foot's median forward so the default (2.0) drops the heel
    (Izzy, 2026-11-13: heels 37 mm through the canvas in render)."""
    keep_f = (hull_opts or {}).get('keep', {})
    skel = json.load(open(os.path.join(char_dir, 'skeleton.json')))
    skin = np.load(os.path.join(char_dir, 'skin.npz'))
    J = {k: np.array(v) for k, v in skel['joints'].items()}
    fwd = np.array([0.0, -1.0, 0.0])
    bodies = []
    for name in CANON:
        stem, _, side = name.partition('_L') if name.endswith('_L') else \
            name.partition('_R') if name.endswith('_R') else (name, '', '')
        side = 'L' if name.endswith('_L') else 'R' if name.endswith('_R') else ''
        child = {'upper_arm': 'forearm', 'forearm': 'hand', 'thigh': 'shin', 'shin': 'foot'}.get(stem)
        if child:
            d = unit(J[f'{child}_{side}'] - J[name])
        elif stem == 'hand':
            d = unit(J[name] - J[f'forearm_{side}'])
        else:
            d = np.array([0, 0, 1.0])
        pts = skin['verts'][skin['owner'] == CANON.index(name)].astype(float)
        pts = clean_points(pts, J[name], J[f'{child}_{side}'] if child else None, side,
                           keep=float(keep_f.get(stem, 2.0)))
        hp = hull_points(pts)
        b = {'name': name, 'parent': PARENT[name], 'stem': stem, 'side': side,
             'region': REGION[stem] + (f'_{side}' if side else ''),
             'pos': J[name].tolist(),
             'mass': mass * MASS_FRACTION[stem],
             'hull': (hp - J[name]).round(5).tolist() if hp is not None else None,
             'limb_dir': d.tolist(), 'joints': []}
        # soft tissue the rigid segment hull cannot represent on its own: a separate convex
        # hull per breast (vertices weighted >= 0.5 to the rig's breast bones, garment included).
        # Massless and collision-free unless a take pairs it explicitly (sim.self_pairs).
        if 'soft' in skin.files and name == 'chest':
            for lab, nm in ((1, 'bust_L'), (2, 'bust_R')):
                sp_ = skin['verts'][(skin['soft'] == lab) & (skin['owner'] == CANON.index(name))].astype(float)
                if len(sp_) >= 30:
                    hs = hull_points(sp_)
                    if hs is not None:
                        b.setdefault('soft', []).append({'name': nm, 'hull': (hs - J[name]).round(5).tolist(),
                                                         'n_vertices': int(len(sp_))})
        if name != 'pelvis':
            pn = palm_normal(hp, side) if stem == 'hand' else None
            for dof, axis, lo, hi, tq, off in joint_table(stem, side, d, fwd, pn):
                b['joints'].append({'name': f'{name}_{dof}', 'dof': dof,
                                    'axis': np.asarray(axis, float).round(6).tolist(),
                                    'range': [lo - off, hi - off], 'offset': off,
                                    'torque': tq * mass / 60.0,
                                    'damping': PASSIVE_DAMP[REGION[stem]]})
        bodies.append(b)
    spec = {'character': skel['name'], 'mass': mass, 'height': skel['height'],
            'status': {'mass_fraction': 'literature, from memory', 'rom': 'approximate',
                       'torque': 'tuned by eye', 'passive_damping': 'tuned by eye'},
            'bodies': bodies}
    return spec


def to_mjcf(spec, pos=(0, 0, 0), contact='solref="0.005 1" solimp="0.95 0.99 0.001"',
            friction=0.9, self_pairs=None, exclude_pairs=None):
    """-> (asset xml, worldbody xml, actuator xml, contact-exclude xml). Root body is placed at `pos` (+ rest height)."""
    by = {b['name']: b for b in spec['bodies']}
    wanted = {n_ for pr in (self_pairs or []) for n_ in pr}
    kids = {}
    for b in spec['bodies']:
        kids.setdefault(b['parent'], []).append(b['name'])
    assets, acts = [], []

    def emit(name):
        b = by[name]
        if b['parent'] is None:
            p = np.array(b['pos']) + np.array(pos)
            x = [f'<body name="{name}" pos="{p[0]} {p[1]} {p[2]}"><freejoint name="root"/>']
        else:
            p = np.array(b['pos']) - np.array(by[b['parent']]['pos'])
            x = [f'<body name="{name}" pos="{p[0]:.5f} {p[1]:.5f} {p[2]:.5f}">']
        for j in b['joints']:
            x.append(f'<joint name="{j["name"]}" type="hinge" axis="{j["axis"][0]} {j["axis"][1]} '
                     f'{j["axis"][2]}" range="{j["range"][0]:.2f} {j["range"][1]:.2f}" '
                     f'damping="{j["damping"]}" armature="0.005" solreflimit="0.008 1"/>')
            acts.append(f'<general name="a_{j["name"]}" joint="{j["name"]}" gaintype="fixed" '
                        f'biastype="affine" gainprm="1" biasprm="0 -1 0" '
                        f'forcerange="-{j["torque"]:.2f} {j["torque"]:.2f}" ctrllimited="false"/>')
        if b['hull']:
            v = ' '.join(f'{c:.5f}' for p_ in b['hull'] for c in p_)
            assets.append(f'<mesh name="m_{name}" vertex="{v}"/>')
            x.append(f'<geom name="g_{name}" type="mesh" mesh="m_{name}" mass="{b["mass"]:.4f}" '
                     f'friction="{friction}" {contact}/>')
        else:
            x.append(f'<geom name="g_{name}" type="sphere" size="0.04" mass="{b["mass"]:.4f}" '
                     f'friction="{friction}" {contact}/>')
        for sg in b.get('soft', []):
            if sg['name'] in wanted:       # emitted only when used: old takes keep their geom ids
                v = ' '.join(f'{c:.5f}' for p_ in sg['hull'] for c in p_)
                assets.append(f'<mesh name="m_{sg["name"]}" vertex="{v}"/>')
                x.append(f'<geom name="g_{sg["name"]}" type="mesh" mesh="m_{sg["name"]}" mass="0" '
                         f'contype="0" conaffinity="0" friction="{friction}" {contact}/>')
        for k in kids.get(name, []):
            x.append(emit(k))
        x.append('</body>')
        return ''.join(x)

    body = emit('pelvis')
    excl = []
    for b in spec['bodies']:
        gp = by[b['parent']]['parent'] if b['parent'] else None
        if gp:
            excl.append(f'<exclude body1="{gp}" body2="{b["name"]}"/>')
        for o in spec['bodies']:       # siblings (thigh-thigh stays: handled by the midline clip)
            if o['name'] < b['name'] and o['parent'] == b['parent'] and b['parent'] \
                    and not (b['stem'] == o['stem'] == 'thigh'):
                excl.append(f'<exclude body1="{o["name"]}" body2="{b["name"]}"/>')
    # take-level exclusions (owner 2026-11-16, crossed ankles): the midline-clipped thigh hulls are
    # rigid, so two adducted thighs lock at the midline and ankles can never cross; real inner
    # thighs compress there. Shin/foot contacts stay, so the crossed lower legs still rest on each other.
    for a_, b_ in (exclude_pairs or []):
        excl.append(f'<exclude body1="{a_}" body2="{b_}"/>')
    # explicit self-contacts that the exclusions above would otherwise drop (e.g. a forearm
    # folded across the chest is a grandchild of the chest). A <pair> always collides.
    names = {b['name'] for b in spec['bodies']} | {sg['name'] for b in spec['bodies']
                                                   for sg in b.get('soft', []) if sg['name'] in wanted}
    for a_, b_ in (self_pairs or []):
        if a_ in names and b_ in names:
            excl.append(f'<pair geom1="g_{a_}" geom2="g_{b_}" condim="3" '
                        f'friction="{friction * 0.7:.2f} {friction * 0.7:.2f} 0.005 0.0001 0.0001" {contact}/>')
    return ''.join(assets), body, ''.join(acts), ''.join(excl)


if __name__ == '__main__':
    import sys
    spec = build(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 60.0)
    json.dump(spec, open(os.path.join(sys.argv[1], 'body.json'), 'w'))
    print('bodies', len(spec['bodies']), 'dofs', sum(len(b['joints']) for b in spec['bodies']),
          'hull-less', [b['name'] for b in spec['bodies'] if not b['hull']])
