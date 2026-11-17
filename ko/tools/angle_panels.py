"""Render a take's beats from computed camera angles, in A/B/C angle sets (owner 2026-11-16:
"generate additional views and angles. give me ABC versions to choose from").

    python3 tools/angle_panels.py SCENE.blend SIM.npz SHOTS.json OUT_DIR [--res 960] [--samples 16]

SHOTS.json: [{id, variant, t, subject: body|head|feet|hands|upper, az: [x, y] (direction from
subject to camera, world XY), el (deg), lens (mm), pad (frame margin, x radius)}]
The camera frames the subject's sim body points (sphere fit) from that direction, so it follows
her wherever she ends up. Writes OUT_DIR/<id>.png and OUT_DIR/shots_done.json.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ko.render import fx as FX  # noqa: E402

a = sys.argv[1:]
src, simp, shotp, outd = a[:4]
res = int(a[a.index('--res') + 1]) if '--res' in a else 960
spp = int(a[a.index('--samples') + 1]) if '--samples' in a else 16
os.makedirs(outd, exist_ok=True)
shots = json.load(open(shotp))

z = np.load(simp, allow_pickle=True)
bn = [str(b) for b in z['body_names']]
XP, T = z['xpos'], z['t']
SUBJ = {
    'body': bn,
    'upper': ['chest', 'neck', 'head', 'upper_arm_L', 'upper_arm_R', 'forearm_L', 'forearm_R', 'hand_L', 'hand_R'],
    'head': ['head', 'neck'],
    'feet': ['shin_L', 'shin_R', 'foot_L', 'foot_R'],
    'hands': ['forearm_L', 'forearm_R', 'hand_L', 'hand_R', 'upper_arm_L', 'upper_arm_R'],
}
EXTRA = {'head': 0.13, 'foot_L': 0.14, 'foot_R': 0.14, 'hand_L': 0.09, 'hand_R': 0.09}   # segment beyond the origin

bpy.ops.wm.open_mainfile(filepath=src, use_scripts=False)
sc = bpy.context.scene
fps = sc.render.fps / sc.render.fps_base
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = spp
try:
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception:
    pass
sc.render.resolution_x, sc.render.resolution_y = res, int(res * 9 / 16)
sc.render.resolution_percentage = 100
sc.render.use_compositing = False
sc.render.use_sequencer = False
cd = bpy.data.cameras.new('cam_angles')
cd.sensor_fit = 'HORIZONTAL'
cd.sensor_width = 36.0
cd.clip_start = 0.02
# sim -> scene world (the baked root's transform), as in action_frames
_root = bpy.data.objects.get('KO_canonical')
if _root is not None:
    _Mw = np.array(_root.matrix_world)
    XP = XP @ _Mw[:3, :3].T + _Mw[:3, 3]
# mouthguard (owner 2026-11-16): worn; --guard-eject followup_1 knocks it out on the follow-up
_ge = a[a.index('--guard-eject') + 1] if '--guard-eject' in a else 'none'
_coll = bpy.data.collections.new('KO_fx')
sc.collection.children.link(_coll)
_st = {s_['name']: s_ for s_ in json.loads(str(z['strikes']))}
_M3 = (_root.matrix_world.to_3x3() if _root is not None else None)
if _ge == 'followup_1' and 'followup_1' in _st:
    fu = _st['followup_1']
    d_fu = (_M3 @ Vector(fu['dir'])).normalized()
    # lets go ~0.14 s after contact, flung by the head's whip at that moment plus a little of the blow
    vh_fu = FX.head_velocity(z['xpos'], bn, fu['t'] + 0.14, float(z['dt']), _M3)
    FX.guard_knocked_out(sc, _coll, fu['t'], vh_fu * 1.1 + d_fu * 0.8 + Vector((0, 0, 0.6)), fps,
                         sc.frame_end, seed=3)
elif _ge == 'none':
    FX.worn_guard(sc, _coll)
co = bpy.data.objects.new('cam_angles', cd)
sc.collection.objects.link(co)
sc.camera = co

done = []
for s in shots:
    p_out = os.path.join(outd, f"{s['id']}.png")
    i = int(np.searchsorted(T, s['t']))
    names = SUBJ[s.get('subject', 'body')]
    pts = []
    for b in names:
        p = XP[i, bn.index(b)]
        pts.append(p)
        if b in EXTRA:          # rough far end of the segment so heads/feet/hands are not cut off
            pts.append(p + np.array([0, 0, EXTRA[b] if b == 'head' else 0.0]))
    P = np.array(pts)
    c = 0.5 * (P.min(0) + P.max(0))
    r = max(0.12, float(np.linalg.norm(P - c, axis=1).max())) * s.get('pad', 1.15)
    lens = float(s.get('lens', 50))
    az = np.array(s.get('az', [0, -1]), float)
    az /= np.linalg.norm(az)
    el = math.radians(s.get('el', 10))
    dvec = np.array([az[0] * math.cos(el), az[1] * math.cos(el), math.sin(el)])
    # fit the projected extents, not a sphere (v2: a body lying flat seen from canvas level is
    # wide and short; the sphere fit put the camera 6 m away, outside the ropes)
    fwd = -dvec
    rt = np.cross(fwd, [0, 0, 1.0])
    rt = rt / np.linalg.norm(rt) if np.linalg.norm(rt) > 1e-6 else np.array([1.0, 0, 0])
    up = np.cross(rt, fwd)
    tx, ty = 18.0 / lens, 18.0 * 9 / 16 / lens         # tan of half fov
    pad = s.get('pad', 1.15)
    Q = P - c                                           # camera at c - fwd*D; each point must sit inside
    e = Q @ fwd                                         # the frustum: |a| <= tx (D + e) / pad
    dist = float(max((pad * np.abs(Q @ rt) / tx - e).max(), (pad * np.abs(Q @ up) / ty - e).max(), 0.35))
    loc = c + dvec * dist
    loc[2] = max(loc[2], 0.06)         # never under the canvas
    cd.lens = lens
    co.location = Vector(loc.tolist())
    co.rotation_euler = (Vector(c.tolist()) - co.location).to_track_quat('-Z', 'Y').to_euler()
    if os.path.exists(p_out):
        done.append(s)
        continue
    fr = s['t'] * fps + 1.0
    sc.frame_set(int(fr), subframe=fr - int(fr))
    sc.render.filepath = p_out
    bpy.ops.render.render(write_still=True)
    s = dict(s, loc=loc.round(3).tolist(), target=c.round(3).tolist())
    done.append(s)
    print('[angles]', s['id'], flush=True)
json.dump(done, open(os.path.join(outd, 'shots_done.json'), 'w'), indent=1)
