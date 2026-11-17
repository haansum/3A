"""Self-contained .blend deliverable (owner 2026-11-15): the baked take scene with every texture
packed, plus one camera per cut of an edit cut list, switched by timeline markers so scrubbing
the timeline plays the edit exactly as rendered.

    python3 tools/export_blend.py SCENE.blend CUTS.json OUT.blend [--tex-dir DIR] [--prefix EDIT]
Render-time extras from action_frames (comic marks, spit/mouthguard props) are not in the scene.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

a = sys.argv[1:]
src, cuts_p, out = a[:3]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d  # noqa: E731
td = opt('--tex-dir')
pre = opt('--prefix', 'EDIT')
bpy.ops.wm.open_mainfile(filepath=src)
sc = bpy.context.scene
fps = sc.render.fps / sc.render.fps_base

if td:                                             # full-res textures in place of the draft set
    for im in bpy.data.images:
        base = os.path.basename(bpy.path.abspath(im.filepath or ''))
        alt = os.path.join(td, base)
        if base and os.path.exists(alt):
            if im.packed_file:
                im.unpack(method='REMOVE')
            im.filepath = alt
            im.reload()

coll = bpy.data.collections.new(f'{pre}_cams')
sc.collection.children.link(coll)
for m in [m for m in sc.timeline_markers if m.name.startswith(pre)]:
    sc.timeline_markers.remove(m)
cuts = json.load(open(cuts_p))
for i, c in enumerate(cuts):
    nm = f"{pre}_{i + 1:02d}_{c.get('shot', 'cut')}"
    if 'scene_cam' in c:
        ob = bpy.data.objects[c['scene_cam']]
    elif 'cam' in c:
        cm = c['cam']
        cd = bpy.data.cameras.new(nm)
        cd.lens, cd.sensor_width = float(cm['lens']), 36.0
        cd.clip_start = 0.02
        ob = bpy.data.objects.new(nm, cd)
        coll.objects.link(ob)
        loc, tgt = Vector(cm['loc']), Vector(cm['target'])
        ob.location = loc
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = (tgt - loc).to_track_quat('-Z', 'Y') @ \
            Quaternion((0, 0, 1), math.radians(float(cm.get('roll', 0.0))))
    else:
        print(f'[blend] cut {i + 1}: tracking cut not exported, skipped')
        continue
    mk = sc.timeline_markers.new(nm, frame=int(round(float(c['t0']) * fps)) + 1)
    mk.camera = ob
    if i == 0:
        sc.camera = ob
sc.frame_end = max(sc.frame_end, int(round(float(cuts[-1]['t1']) * fps)))
bpy.ops.file.pack_all()
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True, copy=True)
print(f'[blend] {len(cuts)} cuts, {len(bpy.data.images)} images packed -> {out} '
      f'({os.path.getsize(out) / 1e6:.0f} MB)')
