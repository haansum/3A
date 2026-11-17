"""Editable .blend + rendered contact sheet for one baked take.

    python3 tools/contact_sheet.py SCENE.blend SIM.npz OUT_DIR NAME [--n 16] [--res 480] [--samples 16]

1. saves OUT_DIR/NAME.blend: the baked scene (textures packed), live camera active, sim events
   as timeline markers, compressed.
2. renders N evenly spaced frames from the live camera (Cycles CPU) and tiles them 4 across,
   each labelled with time and the most recent sim event.
"""
import json
import os
import sys

import bpy
import numpy as np
from PIL import Image, ImageDraw, ImageFont

a = sys.argv[1:]
src, simp, outd, name = a[:4]
n = int(a[a.index('--n') + 1]) if '--n' in a else 16
res = int(a[a.index('--res') + 1]) if '--res' in a else 480
spp = int(a[a.index('--samples') + 1]) if '--samples' in a else 16
os.makedirs(outd, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=src, use_scripts=False)
sc = bpy.context.scene
fps = sc.render.fps / sc.render.fps_base
z = np.load(simp, allow_pickle=True)
ev = dict(json.loads(str(z['events'])))
ev['ko'] = float(z['t_ko'])
NICE = {'ko_strike': 'KO strike', 'ko': 'KO', 'down': 'down', 'head_impact': 'head impact'}
for m in list(sc.timeline_markers):
    sc.timeline_markers.remove(m)
for k, t in sorted(ev.items(), key=lambda x: x[1]):
    sc.timeline_markers.new(NICE.get(k, k), frame=int(round(t * fps)) + 1)
if 'cam_live' in bpy.data.objects:
    sc.camera = bpy.data.objects['cam_live']
try:
    bpy.ops.file.pack_all()
except Exception as e:
    print('pack_all:', e)
blend_out = os.path.join(outd, f'{name}.blend')
bpy.ops.wm.save_as_mainfile(filepath=blend_out, compress=True, copy=True)
print('saved', blend_out, os.path.getsize(blend_out) // 1024, 'KB')

# ---- render the sheet
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = spp
try:
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception:
    sc.cycles.use_denoising = False
sc.render.resolution_x, sc.render.resolution_y = res, int(res * 9 / 16)
sc.render.resolution_percentage = 100
sc.render.use_compositing = False
sc.render.use_sequencer = False
f0, f1 = sc.frame_start, sc.frame_end
frames = np.linspace(f0, f1, n).round().astype(int)
if '--times' in a:      # explicit seconds, e.g. weighted toward the knockdown (owner 2026-11-15)
    frames = np.array([int(round(float(s) * fps)) + 1 for s in a[a.index('--times') + 1].split(',')])
tiles = []
for i, fr in enumerate(frames):
    sc.frame_set(int(fr))
    p = os.path.join(outd, f'_{name}_{i:02d}.png')
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    t = (fr - 1) / fps
    last = [NICE.get(k, k) for k, v in sorted(ev.items(), key=lambda x: x[1]) if v <= t + 1e-6]
    tiles.append((p, fr, t, last[-1] if last else 'pre-KO'))

cols = 4
rows = (len(tiles) + cols - 1) // cols
tw, th = sc.render.resolution_x, sc.render.resolution_y
pad, lab, head = 6, 22, 40
W = Image.new('RGB', (cols * (tw + pad) + pad, rows * (th + lab + pad) + pad + head), (250, 250, 248))
d = ImageDraw.Draw(W)
try:
    F = ImageFont.truetype('DejaVuSans.ttf', 14)
    FB = ImageFont.truetype('DejaVuSans-Bold.ttf', 18)
except Exception:
    F = FB = ImageFont.load_default()
d.text((pad, 10), f'{name}  ·  live camera  ·  {len(tiles)} frames, {f0}–{f1} @ {fps:.0f} fps', fill=(30, 30, 28), font=FB)
for i, (p, fr, t, e) in enumerate(tiles):
    x = pad + (i % cols) * (tw + pad)
    y = head + pad + (i // cols) * (th + lab + pad)
    W.paste(Image.open(p).convert('RGB'), (x, y))
    d.text((x + 2, y + th + 3), f'f{fr:>3}   {t:5.2f} s   after: {e}', fill=(74, 74, 70), font=F)
    os.remove(p)
sheet = os.path.join(outd, f'{name}_contact_sheet.jpg')
W.save(sheet, quality=90)
print('sheet', sheet)
