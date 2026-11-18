"""Brief face clips at different levels of consciousness (owner 2026-11-18).

    python3 tools/face_levels.py TAKE.yaml OUT_DIR [--fps 12] [--secs 1.0] [--res 480] [--reuse]

Moments are read from the sim: fighting (L = 1), L crossing 0.75 / 0.5 / 0.25 while fading,
just out, the tonic peak (the release), waking, groggy. Each clip is `secs` long, centred on
the moment, from a face camera that tracks her head every frame (front of her face, 0.55 m,
85 mm). Writes one mp4 per moment, a joined clip with captions, and a contact strip of the
middle frames.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from ko import cli  # noqa: E402

a = sys.argv[1:]
take, outd = a[0], a[1]
cfps = int(a[a.index('--fps') + 1]) if '--fps' in a else 12
secs = float(a[a.index('--secs') + 1]) if '--secs' in a else 1.0
res = int(a[a.index('--res') + 1]) if '--res' in a else 480
os.makedirs(outd, exist_ok=True)
lock, dirs, _ = cli.build(take, None, 'bake', ['noqa'])
z = np.load(os.path.join(dirs['sim'], 'sim.npz'))
fr = np.load(os.path.join(dirs['bake'], 'frames.npz'))
fps = lock['render']['fps']
ev = json.loads(str(z['events']))
t, L = z['t'], z['L']


def cross(level, after=0.0):
    i = np.nonzero((t >= after) & (L <= level))[0]
    return float(t[i[0]]) if len(i) else None


moments = [('fighting  L=1.00', 1.0)]
for lv in (0.75, 0.5, 0.25):
    tt = cross(lv)
    if tt is not None:
        moments.append((f'fading  L={lv:.2f}', tt))
if 'out' in ev:
    moments.append(('out  L=0.00', ev['out'] + 0.8))
if 'release' in ev:
    moments.append(('tonic peak (release)', ev['release'] - 0.3))
if 'waking' in ev:
    moments.append(('waking', ev['waking'] + 0.4))
if 'groggy' in ev:
    moments.append(('groggy', ev['groggy'] + 1.5))

lock_r = dict(lock, render=dict(lock['render'], still_times=[moments[0][1]], still_shots=['live']))
if not ('--reuse' in a and os.path.exists(os.path.join(outd, 'scene.blend'))):
    from ko.render import render  # noqa: E402
    render.run(lock_r, dirs['bake'], dirs['sim'], outd, stills=True)
import bpy  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

bpy.ops.wm.open_mainfile(filepath=os.path.join(outd, 'scene.blend'))
sc = bpy.context.scene
root = bpy.data.objects['KO_canonical']
cd = bpy.data.cameras.new('facecam')
cam = bpy.data.objects.new('cam_facelevels', cd)
sc.collection.objects.link(cam)
cam.parent = root
sc.camera = cam
cd.lens = 85
for o in bpy.data.objects:
    if o.type == 'CAMERA' and o is not cam:
        o.hide_render = True
sc.render.resolution_x = sc.render.resolution_y = res
names = [str(x) for x in z['body_names']]
bodies, hq = np.asarray(fr['bodies']), np.asarray(fr['head_quat'])
n = len(fr['t'])
try:
    F = ImageFont.truetype('DejaVuSans-Bold.ttf', max(14, res // 26))
except Exception:
    F = ImageFont.load_default()
clips, mids = [], []
for k, (label, tc) in enumerate(moments):
    fdir = os.path.join(outd, f'clip_{k:02d}')
    os.makedirs(fdir, exist_ok=True)
    m = int(round(secs * cfps))
    times = tc - secs / 2 + np.arange(m) / cfps
    for j, tt in enumerate(times):
        f = int(min(n, max(1, round(tt * fps) + 1)))
        sc.frame_set(f)
        head = Vector(bodies[f - 1, names.index('head')])
        R = Quaternion(hq[f - 1]).to_matrix()
        eye_c = head + R @ Vector((0, -0.07, 0.07))
        fwd = R @ Vector((0, -1, 0))
        cam.location = eye_c + fwd * 0.55 + Vector((0, 0, 0.02))
        # camera up = her head's up, so the face is upright on screen even when she lies down
        from mathutils import Matrix as _M
        zc = (cam.location - eye_c).normalized()
        yc = (R @ Vector((0, 0, 1)))
        yc = (yc - yc.dot(zc) * zc).normalized()
        xc = yc.cross(zc)
        cam.rotation_mode = 'QUATERNION'
        cam.rotation_quaternion = _M((xc, yc, zc)).transposed().to_quaternion()
        p = os.path.join(fdir, f'{j:03d}.png')
        sc.render.filepath = p
        bpy.ops.render.render(write_still=True)
        im = Image.open(p).convert('RGB')
        d = ImageDraw.Draw(im)
        txt = f'{label}   t={tt:5.2f} s'
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                d.text((10 + dx, 10 + dy), txt, fill=(0, 0, 0), font=F)
        d.text((10, 10), txt, fill=(255, 235, 120), font=F)
        im.save(p)
        if j == m // 2:
            mids.append((label, im.copy()))
    clip = os.path.join(outd, f'face_{k:02d}.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(cfps), '-i', os.path.join(fdir, '%03d.png'),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', clip], check=True)
    clips.append(clip)
lst = os.path.join(outd, 'clips.txt')
open(lst, 'w').write(''.join(f"file '{c}'\n" for c in clips))
joined = os.path.join(outd, f"{lock['take']}_face_levels.mp4")
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', joined], check=True)
cols = 4
rows = (len(mids) + cols - 1) // cols
W = Image.new('RGB', (cols * res, rows * res), 'white')
for i, (_, im) in enumerate(mids):
    W.paste(im, ((i % cols) * res, (i // cols) * res))
strip = os.path.join(outd, f"{lock['take']}_face_levels.jpg")
W.save(strip, quality=90)
print('clips', joined, '\nstrip', strip)
