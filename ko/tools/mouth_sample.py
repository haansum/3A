"""Face close-up mouth samples (owner 2026-11-15: mouth still a bit uncanny; show the mouthguard
worn). Renders the same frame with mouth variants so they compare side by side.

    python3 tools/mouth_sample.py SCENE.blend OUT_DIR --t 0.69 [--tex-dir D] [--res 960] [--spp 32]
        [--variants base,guard,guard_lips] [--side 35]
Variants: base = as baked; guard = boil-and-bite guard seated on the upper teeth (bone-parented);
lips = lower lip carried down with the jaw, corners drawn in, upper lip lifted a hair, under-mouth
slack morph. Offsets are set by eye.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ko.render import fx as FX  # noqa: E402

a = sys.argv[1:]
src, od = a[:2]
opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d  # noqa: E731
T = float(opt('--t', 0.69))
res = int(opt('--res', 960))
spp = int(opt('--spp', 32))
side_deg = float(opt('--side', 35))
VARS = opt('--variants', 'base,guard,guard_lips').split(',')
os.makedirs(od, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=src)
sc = bpy.context.scene
fps = sc.render.fps / sc.render.fps_base
td = opt('--tex-dir')
if td:
    for im in bpy.data.images:
        base = os.path.basename(bpy.path.abspath(im.filepath or ''))
        alt = os.path.join(td, base)
        if base and os.path.exists(alt):
            if im.packed_file:
                im.unpack(method='REMOVE')
            im.filepath = alt
            im.reload()
sk = bpy.data.objects['KO_skeleton']
body = bpy.data.objects['Genesis 8 Female Mesh']
fr = T * fps + 1.0
sc.frame_set(int(fr), subframe=fr - int(fr))
dg = bpy.context.evaluated_depsgraph_get()


def bw(b, tail=False):
    pb = sk.pose.bones[b]
    return sk.matrix_world @ (pb.tail if tail else pb.head)


# upper teeth from the skinned mesh (armature only, before subsurf)
saved = [(md, md.show_viewport) for md in body.modifiers if md.type != 'ARMATURE']
for md, _ in saved:
    md.show_viewport = False
dg.update()
me = body.evaluated_get(dg).to_mesh()
gi = body.vertex_groups['upperTeeth'].index
P = np.array([(body.matrix_world @ v.co)[:] for v in me.vertices
              if any(g.group == gi and g.weight > 0.6 for g in v.groups)])
body.evaluated_get(dg).to_mesh_clear()
for md, s_ in saved:
    md.show_viewport = s_
dg.update()
head_c = bw('head')
up = (bw('head', True) - head_c).normalized()
tc = Vector(P.mean(0).tolist())
fwd = tc - head_c
fwd = (fwd - up * fwd.dot(up)).normalized()
front = max(P.tolist(), key=lambda p: Vector(p).dot(fwd))
inc = Vector(front)                                     # most forward upper incisor point
print(f'[mouth] {len(P)} upper-teeth verts, arch depth {(inc - tc).dot(fwd) * 1000:.0f} mm')

# camera: front three-quarter on the mouth, slightly below eye line
mouth = inc - up * 0.012
sd = fwd.cross(up).normalized()
d_ = (fwd * math.cos(math.radians(side_deg)) + sd * math.sin(math.radians(side_deg)) - up * 0.08).normalized()
cd = bpy.data.cameras.new('MS_cam')
cd.lens, cd.sensor_width, cd.clip_start = 85.0, 36.0, 0.02
cam = bpy.data.objects.new('MS_cam', cd)
sc.collection.objects.link(cam)
tgt = mouth + up * float(opt("--tgt-up", 0.015))
cam.location = tgt + d_ * float(opt("--dist", 0.8))
cam.rotation_mode = 'QUATERNION'
cam.rotation_quaternion = (tgt - cam.location).to_track_quat('-Z', 'Y')
cd.dof.use_dof, cd.dof.focus_distance, cd.dof.aperture_fstop = True, (tgt - cam.location).length, 4.0
sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = res, res * 9 // 16, 100
sc.render.engine = 'CYCLES'
sc.cycles.samples = spp
sc.render.use_motion_blur = False

# guard seated on the upper arch, riding the upper-teeth bone
coll = bpy.data.collections.new('MS_fx')
sc.collection.children.link(coll)
g = FX.make_mouthguard(coll, name='KO_guard_worn', rgb=(0.02, 0.10, 0.55))
for n_ in g.data.materials[0].node_tree.nodes:      # worn guard: denser plastic than the flying one
    if n_.type == 'BSDF_PRINCIPLED':
        for k_, v_ in (('Transmission Weight', 0.15), ('Roughness', 0.25), ('Coat Weight', 0.4)):
            if k_ in n_.inputs:
                n_.inputs[k_].default_value = v_
ub = sk.pose.bones['upperTeeth']
g.rotation_mode = 'QUATERNION'
g.rotation_quaternion = fwd.to_track_quat('Y', 'Z')
g.location = inc - fwd * 0.036 - up * float(opt('--guard-down', 0.011))             # arch front 1 mm proud of the incisors
bpy.context.view_layer.update()
mw = g.matrix_world.copy()
g.parent, g.parent_type, g.parent_bone = sk, 'BONE', 'upperTeeth'
bpy.context.view_layer.update()
g.matrix_world = mw
g.hide_render = True

LIPS = {   # world-space offsets in mm along (fwd, up), by eye
    'lipLowerMiddle': (1.5, -2.5), 'lipLowerInner.L': (1.2, -2.0), 'lipLowerInner.R': (1.2, -2.0),
    'lipLowerOuter.L': (0.6, -1.0), 'lipLowerOuter.R': (0.6, -1.0),
    'lipUpperMiddle': (1.0, 1.2), 'lipUpperInner.L': (0.8, 1.0), 'lipUpperInner.R': (0.8, 1.0),
}
CORNER = 1.5   # mm, corners drawn in toward the midline


def set_lips(on):
    for b, (f_, u_) in LIPS.items():
        if b not in sk.pose.bones:
            continue
        pb = sk.pose.bones[b]
        R = (sk.matrix_world.to_3x3() @ pb.matrix.to_3x3())
        pb.location = R.inverted() @ ((fwd * f_ + up * u_) / 1000.0) if on else Vector()
    for b, s_ in (('lipCorner.L', 1), ('lipCorner.R', -1)):
        if b in sk.pose.bones:
            pb = sk.pose.bones[b]
            R = (sk.matrix_world.to_3x3() @ pb.matrix.to_3x3())
            # side of the face this corner sits on decides "inward"
            s_ = -1 if (bw(b) - head_c).dot(sd) > 0 else 1
            pb.location = R.inverted() @ (sd * s_ * CORNER / 1000.0 + fwd * 0.0005) if on else Vector()
    kb = body.data.shape_keys.key_blocks.get('PHMUnderMouthSlackHD') if body.data.shape_keys else None
    if kb:
        kb.value = 0.6 if on else 0.0


# jaw retune: scale the baked open/shift at this instant (open axis 0; shift = the other axis
# that moved). Muting the keys lets the tuned value stand for the render.
jb = sk.pose.bones['lowerJaw']
fr0 = (T - 0.2) * fps + 1.0
sc.frame_set(int(fr0), subframe=fr0 - int(fr0))
jbase = jb.rotation_euler.copy()
sc.frame_set(int(fr), subframe=fr - int(fr))
jcur = jb.rotation_euler.copy()
jd = [jcur[i] - jbase[i] for i in range(3)]
print('[mouth] jaw delta deg', [round(math.degrees(x), 1) for x in jd])
OPEN_K, SHIFT_K = float(opt('--open-k', 0.55)), float(opt('--shift-k', 1.6))
act = sk.animation_data.action
try:
    jfc = [fc for fc in act.fcurves if fc.data_path == 'pose.bones["lowerJaw"].rotation_euler']
except Exception:
    jfc = [fc for l_ in act.layers for s_ in l_.strips for cb in s_.channelbags for fc in cb.fcurves
           if fc.data_path == 'pose.bones["lowerJaw"].rotation_euler']


def set_jaw(on):
    for fc in jfc:
        fc.mute = on
    if on:
        e = jbase.copy()
        e[0] = jbase[0] + jd[0] * OPEN_K
        for i in (1, 2):
            e[i] = jbase[i] + jd[i] * SHIFT_K
        jb.rotation_euler = e


for v in VARS:
    g.hide_render = 'guard' not in v
    set_lips('lips' in v)
    set_jaw('jaw' in v)
    sc.frame_set(int(fr), subframe=fr - int(fr))
    if 'jaw' in v:
        set_jaw(True)
    sc.render.filepath = os.path.join(od, f'mouth_{v}.png')
    bpy.ops.render.render(write_still=True)
    print('[mouth] wrote', sc.render.filepath, flush=True)
