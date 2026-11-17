"""Render one shot (or a chest close-up check) at named moments of a baked take, as a strip.

    python3 tools/shot_frames.py SCENE.blend SIM.npz OUT.jpg --shot face \
        --at "pre-hit:ko_strike-0.1,kick:ko_strike+0.03,whip:ko_strike+0.07,snap:ko_strike+0.25,\
canvas:head_impact+0.02,after:head_impact+0.6,settled:end-0.1" [--res 640] [--samples 24]
    --shot chest_L | chest_R : a close camera on her chest from her left/right, for clipping checks
"""
import json
import os
import sys

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont

a = sys.argv[1:]
src, simp, out = a[:3]
shot = a[a.index('--shot') + 1]
res = int(a[a.index('--res') + 1]) if '--res' in a else 640
spp = int(a[a.index('--samples') + 1]) if '--samples' in a else 24
z = np.load(simp, allow_pickle=True)
ev = dict(json.loads(str(z['events'])))
T = float(z['t'][-1])
ev['end'] = T
X = z['xpos']
bn = [str(b) for b in z['body_names']]
dt = float(z['dt'])
moms = []
for item in a[a.index('--at') + 1].split(','):
    lab, expr = item.split(':')
    for op in ('+', '-'):
        if op in expr:
            k, v = expr.split(op)
            tt = ev[k] + (float(v) if op == '+' else -float(v))
            break
    else:
        tt = ev[expr]
    moms.append((lab, min(max(tt, 0.0), T - 0.02)))

bpy.ops.wm.open_mainfile(filepath=src, use_scripts=False)
sc = bpy.context.scene
fps = sc.render.fps / sc.render.fps_base
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = spp
sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = res, int(res * 9 / 16)
sc.render.resolution_percentage = 100
sc.render.use_compositing = False
sc.render.use_sequencer = False
root = bpy.data.objects.get('KO_canonical')
M = root.matrix_world.copy() if root else None
if shot in ('chest_under', 'face_under'):       # from below, through a hidden canvas
    for o in bpy.data.objects:
        if o.type == 'MESH' and any(k_ in o.name.lower() for k_ in ('canvas', 'floor', 'apron')):
            o.hide_render = True
if shot.startswith('chest') or shot in ('face_under', 'profile'):
    cd = bpy.data.cameras.new('chk')
    cd.lens = 50
    cd.clip_start = 0.02
    cam = bpy.data.objects.new('chk', cd)
    sc.collection.objects.link(cam)
else:
    cam = bpy.data.objects['cam_' + shot]
    cam.data.dof.use_dof = False
sc.camera = cam
tiles = []
tmpd = os.path.splitext(out)[0] + '_tiles'
os.makedirs(tmpd, exist_ok=True)
for lab, tt in moms:
    sc.frame_set(int(round(tt * fps)) + 1)
    if shot.startswith('chest') or shot in ('face_under', 'profile'):
        i = int(round(tt / dt))
        c = Vector(X[i, bn.index('chest')].tolist())
        R = np.array(z['xquat'][i, bn.index('chest')])
        w_, x_, y_, z_ = R
        side = np.array([1 - 2 * (y_ * y_ + z_ * z_), 2 * (x_ * y_ + z_ * w_), 2 * (x_ * z_ - y_ * w_)])  # her +x (left)
        fwd = -np.array([2 * (x_ * y_ - z_ * w_), 1 - 2 * (x_ * x_ + z_ * z_), 2 * (y_ * z_ + x_ * w_)])
        s_ = 1.0 if shot == 'chest_L' else -1.0
        off = Vector((s_ * side * 0.55 + fwd * 0.45).tolist()) + Vector((0, 0, 0.18))
        if shot == 'chest_under':
            off = Vector((0.0, 0.0, -0.75))
        tgt = c + Vector((fwd * 0.08).tolist())
        if shot == 'profile':      # canvas level, side-on to her body axis: lift off the mat reads
            ax_ = X[i, bn.index('head')] - X[i, bn.index('pelvis')]
            ax_[2] = 0.0
            ax_ /= max(np.linalg.norm(ax_), 1e-6)
            perp = np.array([-ax_[1], ax_[0], 0.0])
            tgt = Vector(((X[i, bn.index('chest')] + X[i, bn.index('pelvis')]) / 2).tolist()) + Vector((0, 0, 0.05))
            off = Vector((perp * 2.3).tolist()) + Vector((0.0, 0.0, 0.12))
        if shot == 'face_under':
            hq = np.array(z['xquat'][i, bn.index('head')])
            w2, x2, y2, z2 = hq
            hf = -np.array([2 * (x2 * y2 - z2 * w2), 1 - 2 * (x2 * x2 + z2 * z2), 2 * (y2 * z2 + x2 * w2)])
            tgt = Vector(X[i, bn.index('head')].tolist()) + Vector((hf * 0.08).tolist())
            off = Vector((hf * 0.25).tolist()) + Vector((0.0, 0.0, -0.55))
        if M is not None:
            tgt = M @ tgt
        cam.location = tgt + off
        if cam.location.z < 0.08 and shot not in ('chest_under', 'face_under'):
            cam.location.z = 0.08
        cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    p = os.path.join(tmpd, f'{lab}.png')
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    tiles.append((p, lab, tt))
tw, th = sc.render.resolution_x // 2, sc.render.resolution_y // 2
cols = min(4, len(tiles))
rows = (len(tiles) + cols - 1) // cols
W = Image.new('RGB', (cols * (tw + 4) + 4, 34 + rows * (th + 22)), (250, 250, 248))
d = ImageDraw.Draw(W)
try:
    F = ImageFont.truetype('DejaVuSans.ttf', 13)
    FB = ImageFont.truetype('DejaVuSans-Bold.ttf', 15)
except Exception:
    F = FB = ImageFont.load_default()
d.text((4, 8), f'{os.path.basename(out)} · shot: {shot}', fill=(30, 30, 28), font=FB)
for k, (p, lab, tt) in enumerate(tiles):
    x = 4 + (k % cols) * (tw + 4)
    y = 34 + (k // cols) * (th + 22)
    W.paste(Image.open(p).convert('RGB').resize((tw, th)), (x, y))
    d.text((x + 2, y + th + 3), f'{lab} · {tt:.2f} s', fill=(74, 74, 70), font=F)
W.save(out, quality=90)
print('wrote', out)
