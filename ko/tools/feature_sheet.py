"""Feature catalog renders for a baked take: key moments of the head-kick timeline from fixed
sample angles, so variants and seeds can be compared like for like.

    python3 tools/feature_sheet.py SCENE.blend SIM.npz OUT_DIR NAME [--moments all|peak]
            [--res 512] [--samples 16]

Writes OUT_DIR/NAME_features.jpg (rows: angles, columns: moments) and one PNG per tile
(OUT_DIR/tiles/NAME__<moment>__<angle>.png) for cross-variant sheets.
Angles are fixed world-space offsets aimed at her chest-pelvis midpoint, identical across
variants: 'close 3/4' (front-right, 35 deg up, 2.3 m) and 'overhead' (75 deg up, 2.6 m).
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont

a = sys.argv[1:]
src, simp, outd, name = a[:4]
which = a[a.index('--moments') + 1] if '--moments' in a else 'all'
res = int(a[a.index('--res') + 1]) if '--res' in a else 512
spp = int(a[a.index('--samples') + 1]) if '--samples' in a else 16
os.makedirs(os.path.join(outd, 'tiles'), exist_ok=True)

z = np.load(simp, allow_pickle=True)
ev = dict(json.loads(str(z['events'])))
t_sim = z['t']
bn = [str(b) for b in z['body_names']]
X = z['xpos']
hi = ev['head_impact']
r0 = min(ev.get('head_impact_2', 1e9), ev.get('followup_1', 1e9), hi + 0.9) + 0.02
MOM = [('whip', ev['ko_strike'] + 0.06), ('snap back', ev['ko_strike'] + 0.26),
       ('slump', ev['ko_strike'] + 0.75), ('head impact', hi + 0.05),
       ('crescendo', hi + 0.5), ('peak', hi + 1.3), ('ratchet', r0 + 0.7), ('fade', hi + 4.0)]
if which == 'peak':
    MOM = [m for m in MOM if m[0] in ('crescendo', 'peak', 'ratchet', 'fade')]
MOM = [(n, min(tt, t_sim[-1] - 0.05)) for n, tt in MOM]
if '--only' in a:
    MOM = [m for m in MOM if m[0] in a[a.index('--only') + 1].split(',')]
ALL_ANG = {'close 3/4': Vector((-0.55, -0.75, 0.62)).normalized() * 2.3,
           'overhead': Vector((-0.12, -0.25, 0.96)).normalized() * 2.6,
           # low from her right side and a little ahead: reads arms and face when she lies prone
           'side low': Vector((-0.92, -0.38, 0.22)).normalized() * 2.0,
           'front low': Vector((-0.25, -0.95, 0.25)).normalized() * 2.1}
names_ = a[a.index('--angles') + 1].split(',') if '--angles' in a else ['close 3/4', 'overhead']
ANG = [(n_, ALL_ANG[n_]) for n_ in names_]


bpy.ops.wm.open_mainfile(filepath=src, use_scripts=False)
sc = bpy.context.scene
fps = sc.render.fps / sc.render.fps_base
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = spp
try:
    sc.cycles.use_denoising = True
except Exception:
    pass
sc.render.resolution_x, sc.render.resolution_y = res, int(res * 2 / 3)
sc.render.resolution_percentage = 100
sc.render.use_compositing = False
sc.render.use_sequencer = False
cd = bpy.data.cameras.new('feat_cam')
cd.lens = 40
cd.clip_start = 0.05
cam = bpy.data.objects.new('feat_cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam

tiles = {}
for mname, tt in MOM:
    i = int(np.clip(round(tt / float(z['dt'])), 0, len(t_sim) - 1))
    tgt = Vector(((X[i, bn.index('chest')] + X[i, bn.index('pelvis')]) / 2).tolist())
    sc.frame_set(int(round(tt * fps)) + 1)
    for aname, off in ANG:
        cam.location = tgt + off
        cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
        p = os.path.join(outd, 'tiles', f'{name}__{mname.replace(" ", "_")}__{aname.replace(" ", "_").replace("/", "")}.png')
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        tiles[(mname, aname)] = (p, tt)

tw, th = sc.render.resolution_x, sc.render.resolution_y
pad, lab, head, side = 6, 22, 40, 92
W = Image.new('RGB', (side + len(MOM) * (tw + pad) + pad, head + len(ANG) * (th + lab + pad) + pad), (250, 250, 248))
d = ImageDraw.Draw(W)
try:
    F = ImageFont.truetype('DejaVuSans.ttf', 14)
    FB = ImageFont.truetype('DejaVuSans-Bold.ttf', 18)
except Exception:
    F = FB = ImageFont.load_default()
d.text((pad, 10), f'{name}  ·  feature catalog  ·  fixed sample angles', fill=(30, 30, 28), font=FB)
for r, (aname, _) in enumerate(ANG):
    d.text((pad, head + pad + r * (th + lab + pad) + th // 2), aname, fill=(74, 74, 70), font=F)
    for c, (mname, _) in enumerate(MOM):
        p, tt = tiles[(mname, aname)]
        x = side + pad + c * (tw + pad)
        y = head + pad + r * (th + lab + pad)
        W.paste(Image.open(p).convert('RGB'), (x, y))
        d.text((x + 2, y + th + 3), f'{mname}  ·  {tt:4.2f} s', fill=(74, 74, 70), font=F)
out = os.path.join(outd, f'{name}_features{a[a.index("--tag") + 1] if "--tag" in a else ""}.jpg')
W.save(out, quality=88)
print('features', out)
