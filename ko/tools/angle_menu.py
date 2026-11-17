"""Camera-angle menu for a baked take: every existing shot plus candidate auxiliary angles,
rendered at the take's key moments, each labelled with an ID to pick for the full render.

    python3 tools/angle_menu.py SCENE.blend SIM.npz OUT_DIR NAME [--res 480] [--samples 16]

Existing shots are rendered where their own animation puts them at that frame. Candidates are
placed per moment around her (chest-pelvis midpoint, or the head for face shots), through the
scene's canonical->world transform; picked ones become real animated shots in the render stage.
"""
import json
import os
import sys

import bpy
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFont

a = sys.argv[1:]
src, simp, outd, name = a[:4]
res = int(a[a.index('--res') + 1]) if '--res' in a else 480
spp = int(a[a.index('--samples') + 1]) if '--samples' in a else 16
tdir = os.path.join(outd, 'angle_tiles')
os.makedirs(tdir, exist_ok=True)

z = np.load(simp, allow_pickle=True)
ev = dict(json.loads(str(z['events'])))
dt = float(z['dt'])
T = z['t'][-1]
bn = [str(b) for b in z['body_names']]
X = z['xpos']
hi = ev['head_impact']
r0 = min(ev.get('head_impact_2', 1e9), ev.get('followup_1', 1e9), hi + 0.9) + 0.02
MOM = [('whip', ev['ko_strike'] + 0.06), ('snap back', ev['ko_strike'] + 0.26),
       ('fold', ev['ko_strike'] + 0.75), ('head impact', hi + 0.05), ('crescendo', hi + 0.5),
       ('peak', hi + 1.3), ('ratchet', r0 + 0.7), ('fade', min(hi + 4.0, T - 0.05))]

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
sc.render.resolution_x, sc.render.resolution_y = res, int(res * 9 / 16)
sc.render.resolution_percentage = 100
sc.render.use_compositing = False
sc.render.use_sequencer = False
for ob in bpy.data.objects:                       # depth of field off: a menu, not a look
    if ob.type == 'CAMERA':
        ob.data.dof.use_dof = False
root = bpy.data.objects.get('KO_canonical')
M = root.matrix_world.copy() if root else None


def W(p):
    v = Vector(p.tolist() if hasattr(p, 'tolist') else p)
    return (M @ v) if M is not None else v


EXIST = [o.name[4:] for o in bpy.data.objects if o.type == 'CAMERA' and o.name.startswith('cam_')
         and o.name[4:] in ('live', 'tight', 'ref_pan', 'referee', 'opponent', 'orbit')]
# candidates: (id, label, aim ('body'|'head'|'legs'), offset from aim in metres, lens)
CAND = [('side_low', 'side low (her right)', 'body', (-1.85, -0.75, 0.42), 35),
        ('front_low', 'front low, canvas level', 'head', (-0.35, -1.7, 0.18), 50),
        ('overhead', 'overhead', 'body', (-0.3, -0.6, 2.6), 30),
        ('underground', 'underground (through canvas)', 'body', (-0.4, -0.9, -1.7), 24),
        ('face_close', 'face close-up', 'head', (-0.45, -0.55, 0.32), 85),
        ('legs_low', 'legs and feet, low behind', 'legs', (0.55, 1.35, 0.3), 45),
        ('crane_34', 'high 3/4 crane', 'body', (-2.4, -2.6, 2.3), 40)]

cd = bpy.data.cameras.new('menu_cam')
mcam = bpy.data.objects.new('menu_cam', cd)
sc.collection.objects.link(mcam)
canvas_like = [o for o in bpy.data.objects if o.type == 'MESH' and
               any(k in o.name.lower() for k in ('canvas', 'floor', 'apron', 'mat'))]

ROWS = [(e, e.replace('_', ' ') + ' (existing shot)') for e in EXIST] + [(c[0], c[1]) for c in CAND]
tiles = {}
for mname, tt in MOM:
    i = int(np.clip(round(tt / dt), 0, len(X) - 1))
    body = (X[i, bn.index('chest')] + X[i, bn.index('pelvis')]) / 2
    aims = {'body': body, 'head': X[i, bn.index('head')],
            'legs': (X[i, bn.index('shin_L')] + X[i, bn.index('shin_R')]) / 2}
    sc.frame_set(int(round(tt * fps)) + 1)
    for e in EXIST:
        sc.camera = bpy.data.objects['cam_' + e]
        p = os.path.join(tdir, f'{name}__{e}__{mname.replace(" ", "_")}.png')
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        tiles[(e, mname)] = p
    for cid, lab, aim, off, lens in CAND:
        tgt = W(aims[aim])
        mcam.location = tgt + Vector(off)
        mcam.rotation_euler = (tgt - mcam.location).to_track_quat('-Z', 'Y').to_euler()
        cd.lens = lens
        cd.clip_start = 0.02
        sc.camera = mcam
        hide = cid == 'underground'
        for o in canvas_like:
            o.hide_render = hide
        p = os.path.join(tdir, f'{name}__{cid}__{mname.replace(" ", "_")}.png')
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        tiles[(cid, mname)] = p
    for o in canvas_like:
        o.hide_render = False

tw, th = sc.render.resolution_x, sc.render.resolution_y
s_ = 0.5
tw, th = int(tw * s_), int(th * s_)
pad, side, head = 4, 210, 50
img = Image.new('RGB', (side + len(MOM) * (tw + pad) + pad, head + len(ROWS) * (th + pad) + pad), (250, 250, 248))
d = ImageDraw.Draw(img)
try:
    F = ImageFont.truetype('DejaVuSans.ttf', 13)
    FB = ImageFont.truetype('DejaVuSans-Bold.ttf', 17)
except Exception:
    F = FB = ImageFont.load_default()
d.text((pad, 6), f'{name} · camera angle menu · pick by ID', fill=(30, 30, 28), font=FB)
for c, (mname, tt) in enumerate(MOM):
    d.text((side + pad + c * (tw + pad) + 2, 30), f'{mname} · {tt:.2f} s', fill=(74, 74, 70), font=F)
for r, (cid, lab) in enumerate(ROWS):
    y = head + pad + r * (th + pad)
    d.text((pad, y + th // 2 - 16), cid, fill=(30, 30, 28), font=FB)
    d.text((pad, y + th // 2 + 4), lab, fill=(110, 110, 104), font=F)
    for c, (mname, _) in enumerate(MOM):
        img.paste(Image.open(tiles[(cid, mname)]).convert('RGB').resize((tw, th)),
                  (side + pad + c * (tw + pad), y))
out = os.path.join(outd, f'{name}_angle_menu.jpg')
img.save(out, quality=88)
json.dump({'existing': EXIST, 'candidates': {c[0]: {'label': c[1], 'aim': c[2], 'offset': c[3], 'lens': c[4]} for c in CAND},
           'moments': dict(MOM)}, open(os.path.join(outd, f'{name}_angle_menu.json'), 'w'), indent=1)
print('menu', out)
