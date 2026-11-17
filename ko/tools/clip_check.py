"""Render-level ground clipping: how far each visible character mesh goes below the canvas
surface, frame by frame, on the baked scene (what the camera sees, not the sim hulls).

    python3 tools/clip_check.py SCENE.blend OUT.json [--every 1] [--tol_mm 3]
"""
import json
import sys

import bpy
import numpy as np

a = sys.argv[1:]
src, out = a[0], a[1]
every = int(a[a.index('--every') + 1]) if '--every' in a else 1
tol = float(a[a.index('--tol_mm') + 1]) if '--tol_mm' in a else 3.0
bpy.ops.wm.open_mainfile(filepath=src, use_scripts=False)
sc = bpy.context.scene
root = bpy.data.objects.get('KO_canonical')
skel = bpy.data.objects.get('KO_skeleton')
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render and
          any(m.type == 'ARMATURE' for m in o.modifiers)]
z0 = root.matrix_world.translation.z if root else 0.0          # canvas surface (root sits on it)
rows, worst = [], {}
for f in range(sc.frame_start, sc.frame_end + 1, every):
    sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    row = {'frame': f}
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        n = len(me.vertices)
        co = np.empty(n * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        M = np.array(o.matrix_world)
        zw = co @ M[2, :3] + M[2, 3]
        ev.to_mesh_clear()
        pen = float(max(0.0, z0 - zw.min())) * 1000
        row[o.name] = round(pen, 1)
        if pen > worst.get(o.name, (0, 0))[0]:
            worst[o.name] = (round(pen, 1), f)
    rows.append(row)
bad = [r for r in rows if any(v > tol for k, v in r.items() if k != 'frame')]
json.dump({'tol_mm': tol, 'worst': worst, 'frames_over_tol': [r['frame'] for r in bad], 'rows': rows},
          open(out, 'w'), indent=1)
print('[clip] worst below canvas (mm, frame):', worst)
print('[clip] frames over', tol, 'mm:', len(bad), [r['frame'] for r in bad][:30])
