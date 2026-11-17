"""A/B/C camera options per panel (owner 2026-11-14), body and face panels.

    python3 tools/abc_variants.py PLAN.json PROXY.json VARIANTS.json OUT_cams.json [--ceiling 2.5]

Body panels: A = the planned angle, B and C = the next two by a per-act preference order
(catalogue letters from tools/angle_variants.py: A house, B worm, C overhead, D profile,
E glove-side/ringside). Panels whose house camera is a placeholder never use catalogue A.
Face panels (name starts with face_): A front three-quarter, B profile, C a third angle
(standing: under the chin looking up; down: past the crown, looking onto an upside-down face).
Writes cams keyed 'panel@A|B|C' for action_frames --cams ... --variant X.
"""
import json
import sys

import numpy as np

a = sys.argv[1:]
plan, px, var = (json.load(open(p)) for p in a[:3])
out = a[3]
ceil_ = float(a[a.index('--ceiling') + 1]) if '--ceiling' in a else 2.5

PREF = {   # alternatives tried in order after the planned angle
    'impact': 'CEDB', 'chair': 'ECBA', 'tipback': 'DBCA', 'torso': 'DCEA', 'laid': 'DBEA',
    'gnp': 'CEDA', 'post1': 'DEBA', 'post2': 'CEBA', 'post3': 'DCBA', 'post4': 'BCEA', 'post5': 'EDBA',
}


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def fit(loc, pts, fill):
    loc = np.asarray(loc, float)
    P = np.asarray(pts, float)
    c = P.mean(0)
    for _ in range(3):
        f_ = unit(c - loc)
        r_ = unit(np.cross(f_, [0.0, 0.0, 1.0])) if abs(f_[2]) < 0.98 else unit(np.cross(f_, [0.0, 1.0, 0.0]))
        u_ = np.cross(r_, f_)
        v = P - loc
        z = v @ f_
        tx, ty = (v @ r_) / z, (v @ u_) / z
        cx, cy = 0.5 * (tx.min() + tx.max()), 0.5 * (ty.min() + ty.max())
        c = loc + (f_ + r_ * cx + u_ * cy) * np.linalg.norm(c - loc)
    ex, ey = 0.5 * (tx.max() - tx.min()), 0.5 * (ty.max() - ty.min())
    return c.tolist(), float(np.clip(18.0 * fill / max(ex, ey * 16 / 9, 1e-4), 18.0, 135.0))


def house_ok(b):
    return np.linalg.norm(np.asarray(b['cam']['loc']) - np.asarray(b['head'])) > 0.05


cams = {}
for p in plan:
    nm = p['name']
    b = px[nm]
    if nm.startswith('face_'):
        head = np.asarray(b['head'], float)
        fwd, up = unit(b['head_fwd']), unit(b['head_up'])
        ctr = head + up * 0.09 + fwd * 0.03                    # face centre, from the head origin
        side = np.cross(fwd, up)
        lying = head[2] < 0.5 or abs(fwd[2]) > 0.6               # down on the canvas (a curled-up head still counts)
        dirs = {'A': unit(fwd * np.cos(np.radians(35)) + side * np.sin(np.radians(35))),
                'B': unit(side if np.dot(side, [0, 0, 1]) > -0.3 else -side),
                'C': unit(fwd * 0.85 + up * 0.52) if lying else unit(fwd * 0.75 - np.array([0, 0, 0.66]))}
        pts = [ctr + d_ for d_ in (up * 0.13, -up * 0.14, side * 0.10, -side * 0.10, fwd * 0.10)]
        for X, d_ in dirs.items():
            loc = ctr + d_ * (0.75 if X == 'C' else 0.55)
            if max(abs(loc[0]), abs(loc[1])) > 2.6:
                loc = ctr + d_ * 0.45
            loc[2] = float(np.clip(loc[2], 0.08, ceil_))
            t_, L_ = fit(loc, pts, fill=0.62)
            cams[f'{nm}@{X}'] = {'loc': loc.tolist(), 'target': t_, 'lens': L_, 'roll': 0.0}
        continue
    order = [p['angle']] + [x for x in PREF.get(nm, 'CDEB') if x != p['angle']]
    if not house_ok(b):
        order = [x for x in order if x != 'A']
    for X, src in zip('ABC', order[:3]):
        if src == 'A':
            cams[f'{nm}@{X}'] = None                             # house camera: no override
        else:
            cams[f'{nm}@{X}'] = var[f'{nm}@{src}']
        p.setdefault('abc', {})[X] = src
cams = {k: v for k, v in cams.items() if v is not None}
json.dump(cams, open(out, 'w'), indent=1)
json.dump(plan, open(a[0], 'w'), indent=1)
print(f'[abc] {len(cams)} cameras for {len(plan)} panels -> {out}')
