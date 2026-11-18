"""Close-ups of one detail at 0 / 25 / 50 / 75 / 100 % of its way to the final position.

    python3 tools/detail_closeups.py TAKE.yaml OUT_DIR [--details eyes,face,fading,arms,legs] [--res 512] [--reuse]

Progress is measured, not assumed:
  eyes   angle of the baked eye.L rotation (its own, relative to the head) away from where it was
         0.6 s before `out`, over its value on the last frame (the roll-up); the overshoot peak
         gets its own panel
  fading the eyes at each face-timeline key while she fades (the transient drifts)
  face   same frames as eyes, framed wider (brows, lids, mouth)
  arms   her arm joint angles projected onto the line from the pose at `out` to the last frame
  legs   the same for her leg joints
The first frame at or past each step is shown. Cameras look at her from the front of the part.
Renders through the render stage's scene (same look as the stills).
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from ko import cli  # noqa: E402

a = sys.argv[1:]
take, outd = a[0], a[1]
details = (a[a.index('--details') + 1] if '--details' in a else 'eyes,face,fading,arms,legs').split(',')
res = int(a[a.index('--res') + 1]) if '--res' in a else 512
os.makedirs(outd, exist_ok=True)
lock, dirs, _ = cli.build(take, None, 'bake', ['noqa'])
z = np.load(os.path.join(dirs['sim'], 'sim.npz'))
fr = np.load(os.path.join(dirs['bake'], 'frames.npz'))
fps = lock['render']['fps']
ev = json.loads(str(z['events']))
t_sim = z['t']
ft = fr['t']
n = len(ft)
names = [str(x) for x in z['body_names']]
jn = [str(j) for j in z['joint_names']]
STEPS = (0.0, 0.25, 0.5, 0.75, 1.0)


def joint_progress(prefixes, t0):
    idx = [k for k, j in enumerate(jn) if j.startswith(prefixes)]
    q = np.degrees(np.stack([z['qpos'][:, z['joint_qadr'][k]] for k in idx], 1))
    i0 = int(np.searchsorted(t_sim, t0))
    d = q[-1] - q[i0]
    p = (q - q[i0]) @ d / max(d @ d, 1e-9)
    return t_sim, p, i0


def first_cross(t, p, i0):
    out = []
    for s in STEPS:
        k = i0 + int(np.argmax(p[i0:] >= s - 1e-9)) if s > 0 else i0
        if s > 0 and p[k] < s - 1e-9:
            k = len(p) - 1
        out.append((s, float(t[k])))
    return out


plans = {}
if 'arms' in details:
    plans['arms'] = first_cross(*joint_progress(('upper_arm', 'forearm', 'hand'), ev['out']))
if 'legs' in details:
    plans['legs'] = first_cross(*joint_progress(('thigh', 'shin', 'foot'), ev['out']))

# render the scene once (one still) so scene.blend exists, then work in it
lock_r = dict(lock, render=dict(lock['render'], still_times=[ev['out']], still_shots=['live']))
if not ('--reuse' in a and os.path.exists(os.path.join(outd, 'scene.blend'))):
    from ko.render import render  # noqa: E402
    render.run(lock_r, dirs['bake'], dirs['sim'], outd, stills=True)
import bpy  # noqa: E402
from mathutils import Matrix, Quaternion, Vector  # noqa: E402

bpy.ops.wm.open_mainfile(filepath=os.path.join(outd, 'scene.blend'))
sc = bpy.context.scene
root = bpy.data.objects['KO_canonical']
skel = bpy.data.objects['KO_skeleton']

if 'eyes' in details or 'face' in details:
    # measured eye roll: angle of eye.L's pose rotation from its pose 0.6 s before going out
    eb = skel.pose.bones['eye.L']
    f0 = max(1, int((ev['out'] - 0.6) * fps) + 1)
    sc.frame_set(f0)
    q0 = eb.matrix_basis.to_quaternion()          # the eye's own rotation, not the head's
    ang = np.zeros(n)
    for f in range(f0, n + 1):
        sc.frame_set(f)
        ang[f - 1] = math.degrees(q0.rotation_difference(eb.matrix_basis.to_quaternion()).angle)
    pe = ang / max(ang[-1], 1e-6)
    pl = first_cross(ft, pe, f0 - 1)
    kpk = int(np.argmax(ang))
    if ang[kpk] > ang[-1] * 1.03:
        pl.append(('peak', float(ft[kpk])))
    for d_ in ('eyes', 'face'):
        if d_ in details:
            plans[d_] = pl
    if 'fading' in details:                         # transient drifts: the timeline's fading keys
        tl_ = (lock.get('bake') or {}).get('face_timeline') or []
        plans['fading'] = [(f"+{e.get('dt', 0.0):.1f}", ev['fading'] + float(e.get('dt', 0.0)))
                           for e in tl_ if e.get('at') == 'fading']
    print('[closeups] eye roll measured: final %.1f deg, peak %.1f deg at %.2f s' % (ang[-1], ang[kpk], ft[kpk]))

cd = bpy.data.cameras.new('closeup')
cam = bpy.data.objects.new('cam_closeup', cd)
sc.collection.objects.link(cam)
cam.parent = root
sc.camera = cam
sc.render.resolution_x = sc.render.resolution_y = res
for o in bpy.data.objects:                   # no stray FX/other cameras in view
    if o.type == 'CAMERA' and o is not cam:
        o.hide_render = True
bodies = np.asarray(fr['bodies'])
hq = np.asarray(fr['head_quat'])


def B(name, f):
    return Vector(bodies[f, names.index(name)])


def aim(loc, tgt):
    cam.location = loc
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (tgt - loc).to_track_quat('-Z', 'Y')


def place(detail, f):
    head = B('head', f)
    fwd_h = Quaternion(hq[f]).to_matrix() @ Vector((0, -1, 0))      # her face direction
    if detail in ('eyes', 'face', 'fading'):
        eye_c = head + Quaternion(hq[f]).to_matrix() @ Vector((0, -0.07, 0.07))
        dist, cd.lens = (0.32, 105) if detail in ('eyes', 'fading') else (0.55, 85)
        aim(eye_c + fwd_h * dist + Vector((0, 0, 0.02)), eye_c)
    elif detail == 'arms':
        pts = [B(k, f) for k in ('upper_arm_L', 'forearm_L', 'hand_L', 'upper_arm_R', 'forearm_R', 'hand_R')]
        c = sum(pts, Vector()) / len(pts)
        span = max((p - c).length for p in pts)
        side = (B('upper_arm_L', f) - B('upper_arm_R', f)).normalized()
        fwd = side.cross(Vector((0, 0, 1)))
        cd.lens = 50
        lying = B('head', f).z - B('pelvis', f).z < 0.25
        # upright: from her front-left; lying: from above her left shoulder, never down the body
        dir_ = (side * 0.55 + Vector((0, 0, 0.85))) if lying else (fwd * 0.8 + side * 0.35 + Vector((0, 0, 0.35)))
        aim(c + dir_.normalized() * (0.9 + 2.2 * span), c)
    elif detail == 'legs':
        pts = [B(k, f) for k in ('thigh_L', 'shin_L', 'foot_L', 'thigh_R', 'shin_R', 'foot_R')]
        c = sum(pts, Vector()) / len(pts)
        span = max((p - c).length for p in pts)
        side = (B('thigh_L', f) - B('thigh_R', f)).normalized()
        cd.lens = 45
        aim(c + (side * 0.9 + Vector((0, 0, 0.45))).normalized() * (1.0 + 2.0 * span), c)


tiles = {}
for detail, pl in plans.items():
    for step, t in pl:
        f = min(n, int(round(t * fps)) + 1)
        sc.frame_set(f)
        place(detail, f - 1)
        p = os.path.join(outd, f'{detail}_{step}.png')
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        tiles.setdefault(detail, []).append((step, t, p))

cols = max(len(v) for v in tiles.values())
pad, lab, head = 8, 26, 44
W = Image.new('RGB', (pad + cols * (res + pad), head + len(tiles) * (res + lab + pad) + pad), (250, 250, 248))
d = ImageDraw.Draw(W)
try:
    F, FB = ImageFont.truetype('DejaVuSans.ttf', 16), ImageFont.truetype('DejaVuSans-Bold.ttf', 20)
except Exception:
    F = FB = ImageFont.load_default()
d.text((pad, 12), f"{lock['take']}  ·  details at 0/25/50/75/100% of the way to the final position (measured)  ·  out at {ev['out']:.2f} s",
       fill=(30, 30, 28), font=FB)
for r, (detail, row) in enumerate(tiles.items()):
    for c, (step, t, p) in enumerate(row):
        x, y = pad + c * (res + pad), head + r * (res + lab + pad)
        W.paste(Image.open(p).convert('RGB'), (x, y))
        lbl = (f'{detail}  peak overshoot  {t:.2f} s' if step == 'peak' else
               f'eyes while fading  fading{step} s = {t:.2f} s' if isinstance(step, str) else
               f'{detail}  {int(step * 100)}%  {t:.2f} s')
        d.text((x + 2, y + res + 4), lbl, fill=(60, 60, 56), font=F)
sheet = os.path.join(outd, f"{lock['take']}_details.jpg")
W.save(sheet, quality=92)
print('sheet', sheet)
