"""Impact frames for every strike that has a prop (glove / shin guard).

    python3 tools/impact_frame.py SCENE.blend SIM.npz OUT_DIR NAME [--res 960] [--samples 48]

For each strike: the frame where the prop touches her (clean render), the frames just before and
after, plus two stylised versions of the hit frame: manga ink (screentone, speed lines, burst,
sound effect) and an anime 'impact flash' (inverted, two-tone, radial lines).
Camera: side-on to the strike direction, close, on the contact point.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga_fx as MF  # noqa: E402

a = sys.argv[1:]
src, simp, outd, name = a[:4]
res = int(a[a.index('--res') + 1]) if '--res' in a else 960
spp = int(a[a.index('--samples') + 1]) if '--samples' in a else 48
os.makedirs(outd, exist_ok=True)
z = np.load(simp, allow_pickle=True)
strikes = [s for s in json.loads(str(z['strikes'])) if s.get('prop')]
bn = [str(b) for b in z['body_names']]
SFX = {'ko_strike': 'ゴッ', 'followup_1': 'ドゴッ', 'followup_2': 'ドゴッ'}

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
sc.render.use_motion_blur = False
root = bpy.data.objects.get('KO_canonical')
M = root.matrix_world.copy()
cd = bpy.data.cameras.new('impact_cam')
cd.lens = 40
cd.clip_start = 0.02
cam = bpy.data.objects.new('impact_cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
report = []
for st in strikes:
    gob = bpy.data.objects.get(f"{st['prop']}_{st['name']}")
    pt = M @ Vector(gob['contact'] if gob is not None and 'contact' in gob else st['point'])
    dv = (M.to_3x3() @ Vector(st['dir'])).normalized()
    side = dv.cross(Vector((0, 0, 1)))
    if side.length < 0.35:            # near-vertical strike (uppercut): use her left-right axis
        i = int(round(st['t'] / float(z['dt'])))
        w_, x_, y_, z_ = z['xquat'][i, bn.index('chest')]
        side = M.to_3x3() @ Vector((1 - 2 * (y_ * y_ + z_ * z_), 2 * (x_ * y_ + z_ * w_), 2 * (x_ * z_ - y_ * w_)))
    side.normalize()
    i = int(round(st['t'] / float(z['dt'])))      # stay on her front side: the prop and her face read
    w_, x_, y_, z_ = z['xquat'][i, bn.index('head')]
    fwd = -(M.to_3x3() @ Vector((2 * (x_ * y_ - z_ * w_), 1 - 2 * (x_ * x_ + z_ * z_), 2 * (y_ * z_ + x_ * w_))))
    if side.dot(fwd) < 0:
        side = -side
    cam.location = pt + side * 0.85 - dv * 0.18 + Vector((0, 0, 0.06))
    cam.rotation_euler = (pt + dv * 0.03 - cam.location).to_track_quat('-Z', 'Y').to_euler()
    fhit = int(round(st['t'] * fps)) + 1
    tiles = {}
    for lab, f in (('before', fhit - 2), ('hit', fhit), ('after', fhit + 2)):
        sc.frame_set(f)
        p = os.path.join(outd, f'{name}_{st["name"]}_{lab}.png')
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        tiles[lab] = p
    sc.frame_set(fhit)
    uv = world_to_camera_view(sc, cam, pt)
    W, H = sc.render.resolution_x, sc.render.resolution_y
    cpx = (uv.x * W, (1 - uv.y) * H)
    hit = Image.open(tiles['hit']).convert('RGB')
    ink = MF.to_manga(hit, cell=5)
    MF.speed_lines(ink, cpx, n=120, inner=0.16, seed=7)
    MF.burst(ink, cpx, 0.035 * W, 0.085 * W, spikes=16, seed=2)
    ink.paste(MF.to_manga(hit.crop((int(cpx[0] - 0.03 * W), int(cpx[1] - 0.03 * W),
                                    int(cpx[0] + 0.03 * W), int(cpx[1] + 0.03 * W)))),
              (int(cpx[0] - 0.03 * W), int(cpx[1] - 0.03 * W)))
    MF.sfx(ink, SFX.get(st['name'], 'ドッ'), (cpx[0] + 0.06 * W, max(10, cpx[1] - 0.30 * H)), int(0.13 * H), angle=-14)
    ink.save(os.path.join(outd, f'{name}_{st["name"]}_hit_manga.png'))
    flash = MF.impact_flash(hit, cpx)
    flash.save(os.path.join(outd, f'{name}_{st["name"]}_hit_flash.png'))
    # strip: before | hit | after | manga | flash
    ims = [Image.open(tiles[k]).convert('RGB') for k in ('before', 'hit', 'after')] + [ink, flash]
    tw, th = W // 2, H // 2
    strip = Image.new('RGB', (len(ims) * (tw + 6) + 6, th + 12), (255, 255, 255))
    for k, im in enumerate(ims):
        strip.paste(im.resize((tw, th)), (6 + k * (tw + 6), 6))
    strip.save(os.path.join(outd, f'{name}_{st["name"]}_impact_strip.jpg'), quality=90)
    report.append({'strike': st['name'], 'prop': st['prop'], 't': st['t'], 'frame': fhit,
                   'contact_px': [round(cpx[0]), round(cpx[1])]})
json.dump(report, open(os.path.join(outd, f'{name}_impacts.json'), 'w'), indent=1)
print('impacts', report)
