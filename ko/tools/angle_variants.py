"""Camera angle variants per beat for the comic contact map (owner 2026-11-14), derived from the
house camera exported by action_frames --proxy. Pure numpy; writes a --cams file keyed beat@X.

    python3 tools/angle_variants.py PROXY_DIR/proxy.json OUT_cams.json [--ceiling 2.5]

Variants (from the manga-panel study, same date):
  A house       the camera the pipeline already uses
  B worm        low, ~0.25 m off the canvas, looking up: scale and threat (impact, whip, rise)
  C overhead    high three-quarter, looking down: helplessness, the shape of the fall
  D profile     flat side-on at the subject's height: clean silhouette, reads direction of force
  E pov / ring  standing beats: from behind the glove (the opponent's eye, glove only in frame);
                floor beats: ringside, low through the ropes (the onlooker cut)
"""
import json
import sys

import numpy as np

a = sys.argv[1:]
px = json.load(open(a[0]))
out = a[1]
ceil_ = float(a[a.index('--ceiling') + 1]) if '--ceiling' in a else 2.5
CLOSE = {'impact', 'whip', 'snap', 'face', 'gaze', 'gnp'}
FLOOR = {'canvas', 'climax', 'face', 'rebound', 'gaze', 'build', 'still'}


def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


def lens_for(r, d, fill=0.8):
    # vertical fit, 36 mm sensor horizontal-fit, 16:9 -> 20.25 mm tall
    return float(np.clip(10.125 * fill / max(r / max(d, 1e-3), 1e-3), 16.0, 135.0))


def fit(loc, pts, fill=0.75, lo=16.0, hi=135.0):
    """Aim + lens so the points' angular bounding box spans `fill` of a 16:9 frame (36 mm
    sensor, horizontal fit), seen from `loc`. Same rule as the live camera (owner 2026-11-14)."""
    loc = np.asarray(loc, float)
    P = np.asarray(pts, float)
    c = P.mean(0)
    for _ in range(3):
        f_ = unit(c - loc)
        r_ = unit(np.cross(f_, [0.0, 0.0, 1.0]))
        u_ = np.cross(r_, f_)
        v = P - loc
        z = v @ f_
        tx, ty = (v @ r_) / z, (v @ u_) / z
        cx, cy = 0.5 * (tx.min() + tx.max()), 0.5 * (ty.min() + ty.max())
        c = loc + (f_ + r_ * cx + u_ * cy) * np.linalg.norm(c - loc)
    ex, ey = 0.5 * (tx.max() - tx.min()), 0.5 * (ty.max() - ty.min())
    lens = float(np.clip(18.0 * fill / max(ex, ey * 16 / 9, 1e-4), lo, hi))
    return c.tolist(), lens


cams = {}
for beat, b in px.items():
    head, pel, feet = (np.asarray(b[k], float) for k in ('head', 'pelvis', 'feet'))
    glove = np.asarray(b['glove'], float) if b.get('glove') else None
    fwd = unit([b['chest_fwd'][0], b['chest_fwd'][1], 0.0])
    lying = head[2] < 0.6   # any beat with her head near the canvas
    if beat in CLOSE:
        c, r = head + [0, 0, -0.05], 0.32
    else:
        top = max(head[2] + 0.15, pel[2])
        c = np.array([(head[0] + feet[0]) / 2, (head[1] + feet[1]) / 2, (top + min(feet[2], pel[2]) - 0.08) / 2])
        r = max(0.55, 0.5 * np.linalg.norm(head - feet) + 0.25)
    crown = head + [0, 0, 0.12]
    if beat in CLOSE:
        pts = [head + d_ for d_ in ([0.16, 0, 0], [-0.16, 0, 0], [0, 0.16, 0], [0, -0.16, 0], [0, 0, 0.16], [0, 0, -0.22])]
        if glove is not None and np.linalg.norm(glove - head) < 0.6:
            pts.append(glove)
    else:
        pts = [crown, head, pel, feet + [0, 0, -0.08]] + [pel + d_ for d_ in ([0.2, 0, 0], [-0.2, 0, 0], [0, 0.2, 0], [0, -0.2, 0])]
    hc = b['cam']
    az = unit(np.asarray(hc['loc'], float) - c) * [1, 1, 0]
    az = unit(az) if np.linalg.norm(az) > 1e-6 else fwd
    if np.linalg.norm(np.asarray(hc['loc'], float) - head) < 0.05:
        # a planned panel has no house camera (its placeholder sits at her head): work from
        # her body instead - front three-quarter standing, the face side of her long axis lying
        if lying or head[2] < 0.7:
            ax0 = unit((head - feet) * [1, 1, 0])
            az = unit(np.cross([0, 0, 1.0], ax0))
            if np.dot(az, fwd) < 0:
                az = -az
        else:
            az = unit(fwd * 0.8 + unit(np.cross([0, 0, 1.0], fwd)) * 0.6)
    side = unit(np.cross([0, 0, 1.0], az))
    cams[f'{beat}@A'] = {'loc': hc['loc'], 'target': hc['target'], 'lens': hc['lens'], 'roll': 0.0}
    # B worm's-eye
    d = 1.1 if beat in CLOSE else 2.0
    loc = c + az * d
    loc[2] = 0.25
    t_, L_ = fit(loc, pts)
    cams[f'{beat}@B'] = {'loc': loc.tolist(), 'target': t_, 'lens': L_, 'roll': 0.0}
    # C overhead three-quarter
    d = 0.9 if beat in CLOSE else 1.4
    loc = c + az * d * 0.6 + side * d * 0.25
    loc[2] = min(ceil_, c[2] + (1.1 if beat in CLOSE else 2.0))
    t_, L_ = fit(loc, pts)
    cams[f'{beat}@C'] = {'loc': loc.tolist(), 'target': t_, 'lens': L_, 'roll': 0.0}
    # D profile: perpendicular to her facing (standing) or to her long axis (lying)
    ax_ = unit((head - feet) * [1, 1, 0]) if lying else fwd
    pd = unit(np.cross([0, 0, 1.0], ax_))
    if np.dot(pd, az) < 0:
        pd = -pd
    d = 1.3 if beat in CLOSE else 3.0
    loc = c + pd * d
    if not lying:
        loc = loc + fwd * d * 0.45       # profile with a front bias: the face, not the back of the head
    loc[2] = c[2] if not lying else 0.45
    t_, L_ = fit(loc, pts)
    cams[f'{beat}@D'] = {'loc': loc.tolist(), 'target': t_, 'lens': L_, 'roll': 0.0}
    # E opponent's eye (glove in frame) / ringside through the ropes
    if glove is not None and not lying and beat in {'read', 'rise', 'impact', 'whip', 'snap'}:
        g_dir = unit((glove - head) * [1, 1, 0]) if np.linalg.norm((glove - head)[:2]) > 0.05 else -fwd
        loc = head + g_dir * 0.75 + fwd * 0.55
        loc[2] = head[2] + 0.12
        tgt = head * 0.75 + glove * 0.25
        cams[f'{beat}@E'] = {'loc': loc.tolist(), 'target': tgt.tolist(), 'lens': 30.0, 'roll': 0.0}
    else:
        loc = c - pd * 2.3 + az * 0.6    # inside the rope line: from outside, the top rope blurs over her
        loc[2] = 0.6
        t_, L_ = fit(loc, pts, fill=0.6)       # onlooker cut: a little room for the ropes
        cams[f'{beat}@E'] = {'loc': loc.tolist(), 'target': t_, 'lens': L_, 'roll': 0.0}
# keep every camera inside the ropes (gym ring ~ +-3.0 m): one placed outside shot a rope or
# corner pad as a red blur across the frame (2026-11-14). Slide it toward its target.
RING = float(a[a.index('--ring') + 1]) if '--ring' in a else 2.6
for k, cm in cams.items():
    loc, tg = np.asarray(cm['loc'], float), np.asarray(cm['target'], float)
    for _ in range(40):
        if max(abs(loc[0]), abs(loc[1])) <= RING:
            break
        loc = loc + (tg - loc) * 0.08
    cm['loc'] = loc.tolist()
json.dump(cams, open(out, 'w'), indent=1)
print(f'[variants] {len(cams)} cameras for {len(px)} beats -> {out}')
