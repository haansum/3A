"""Expression channels on the Genesis 8 face bones, keyed from an event timeline (render stage).

Owner 2026-11-18: "try and see what expressions could sell the effect". Method from the
ko-impact-face-rig skill: offsets in mm in a head-local frame (up, fwd = her face direction,
side = her left), converted every frame into each bone's posed parent space and keyed as the
bone's location on KO_skeleton (the bake leaves face bones unkeyed). Channels, each 0..1:

  knit     inner brows down 2.5 mm and in 1.5 mm, centre brow down 1 mm      (strain)
  raise    all brows up 3 mm                                                   (worry, confusion)
  droop    upper lids down 3 mm                                                (fading, half-lidded)
  squint   lower lids up 1.5 mm, upper cheeks up 1.5 mm                        (effort)
  grimace  lip corners out 3 mm and back 1.5 mm, upper lip up 1.5 mm,
           lower lip down 1.2 mm                                               (clenched teeth)
  press    upper lip down 1 mm, lower lip up 1 mm                              (lips pressed)
  slack    lip corners down 2 mm                                               (out)

Timeline entries: {at: event, dt: s, <channel>: value}; values are smoothstep-interpolated
between entries, per channel, from the entries that name it. Every amount is by eye.
"""
import math

import numpy as np
from mathutils import Vector

# (bones, [(axis, mm)]) per channel; axis in the head frame: 'up', 'fwd', 'in' (toward the midline)
CH = {
    'knit': [(['browInner.L', 'browInner.R'], [('up', -2.5), ('in', 1.5)]), (['centerBrow'], [('up', -1.0)])],
    'raise': [(['browInner.L', 'browInner.R', 'browMid.L', 'browMid.R', 'browOuter.L', 'browOuter.R', 'centerBrow'],
               [('up', 3.0)])],
    'droop': [(['eyelidUpper.L', 'eyelidUpper.R', 'eyelidUpperInner.L', 'eyelidUpperInner.R',
                'eyelidUpperOuter.L', 'eyelidUpperOuter.R'], [('up', -3.0)])],
    'squint': [(['eyelidLower.L', 'eyelidLower.R', 'eyelidLowerInner.L', 'eyelidLowerInner.R',
                 'eyelidLowerOuter.L', 'eyelidLowerOuter.R'], [('up', 1.5)]),
               (['cheekUpper.L', 'cheekUpper.R'], [('up', 1.5)])],
    'grimace': [(['lipCorner.L', 'lipCorner.R'], [('in', -3.0), ('fwd', -1.5)]),
                (['lipUpperMiddle', 'lipUpperInner.L', 'lipUpperInner.R', 'lipUpperOuter.L', 'lipUpperOuter.R'], [('up', 1.5)]),
                (['lipLowerMiddle', 'lipLowerInner.L', 'lipLowerInner.R', 'lipLowerOuter.L', 'lipLowerOuter.R'], [('up', -1.2)])],
    'press': [(['lipUpperMiddle', 'lipUpperInner.L', 'lipUpperInner.R'], [('up', -1.0)]),
              (['lipLowerMiddle', 'lipLowerInner.L', 'lipLowerInner.R'], [('up', 1.0)])],
    'slack': [(['lipCorner.L', 'lipCorner.R'], [('up', -2.0)])],
}


def _curve(pts, t):
    if not pts:
        return 0.0
    if t <= pts[0][0]:
        return pts[0][1]
    for (ta, a), (tb, b) in zip(pts, pts[1:]):
        if t <= tb:
            u = (t - ta) / max(tb - ta, 1e-6)
            return a + (b - a) * u * u * (3 - 2 * u)
    return pts[-1][1]


def apply(sc, skel, root, timeline, events, fps, n):
    """key the channels on `skel` for frames 1..n. -> {channel: max value} actually used"""
    pts = {}
    for e in timeline:
        t0 = 0.0 if e.get('at', 'start') == 'start' else events.get(e['at'])
        if t0 is None:
            continue
        for ch in CH:
            if ch in e:
                pts.setdefault(ch, []).append((t0 + float(e.get('dt', 0.0)), float(e[ch])))
    for v in pts.values():
        v.sort()
    pb = skel.pose.bones
    bones = sorted({b for ch in pts for grp, _ in CH[ch] for b in grp if b in pb})
    head_name = next((nm for nm in ('head', 'DEF-spine.006', 'head.x') if nm in pb), None)
    if not bones or head_name is None:
        return {}
    k_scale = 1.0 / max(skel.matrix_world.to_scale()[0], 1e-9)   # armature units per metre
    used = {ch: max(v for _, v in p) for ch, p in pts.items()}
    rest = {b.name: b.matrix_local.copy() for b in skel.data.bones}
    for f in range(1, n + 1):
        sc.frame_set(f)
        t = (f - 1) / fps
        Hm = pb[head_name].matrix                               # armature space, posed
        up = Vector(Hm.col[1][:3]).normalized()                 # bone Y runs up the head
        mid = Hm.translation
        # face direction: from the head origin toward the eyes, made orthogonal to up
        eyes = [pb[e].head for e in ('eye.L', 'eye.R') if e in pb]
        fwd = ((sum(eyes, Vector()) / len(eyes)) - mid) if eyes else Vector((0, -1, 0))
        fwd = (fwd - fwd.dot(up) * up).normalized()
        left = up.cross(fwd).normalized()
        vals = {ch: _curve(p, t) for ch, p in pts.items()}
        delta = {b: Vector() for b in bones}
        for ch, k in vals.items():
            if abs(k) < 1e-6:
                continue
            for grp, moves in CH[ch]:
                for b in grp:
                    if b not in delta:
                        continue
                    sgn_in = -1.0 if b.endswith('.L') else (1.0 if b.endswith('.R') else 0.0)   # 'in' = toward midline
                    for ax, mm in moves:
                        v = {'up': up, 'fwd': fwd, 'in': left * sgn_in}[ax]
                        delta[b] += v * (mm * 0.001 * k * k_scale)
        for b in bones:
            par = skel.data.bones[b].parent
            P = pb[par.name].matrix if par else rest[b] @ rest[b].inverted()
            rr = (rest[par.name].inverted() @ rest[b]) if par else rest[b]
            loc = (P @ rr).to_3x3().inverted() @ delta[b]
            pb[b].location = loc
            pb[b].keyframe_insert('location', frame=f)
    return used
