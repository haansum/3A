"""Stage 6: bake. sim.npz -> a named action on the untouched character rig, saved as take.blend.

Retarget rule: every sim body frame is world-aligned in the rig's neutral pose, so
    bone_world(t) = R_sim(t) * bone_world_neutral
with no per-rig axis or sign conventions. The stage measures its own round-trip error
(bone orientation and joint position vs the sim, every baked frame) and writes it to
bake.json; a convention bug shows up there as tens of degrees, not as a visual hunch.

The sim action sits on its own named action so hand tweaks can be layered on top in the NLA.
Not baked yet: fingers, spring-bone hair, soft tissue (they stay rigid) - listed in bake.json.
"""
import json
import math
import os
import re

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector


def resample(z, fps):
    t, dt = z['t'], float(z['dt'])
    n = int(t[-1] * fps) + 1
    ft = np.arange(n) / fps
    i0 = np.minimum((ft / dt).astype(int), len(t) - 1)
    i1 = np.minimum(i0 + 1, len(t) - 1)
    a = (ft / dt - i0)[:, None, None]
    pos = (1 - a) * z['xpos'][i0] + a * z['xpos'][i1]
    q0, q1 = z['xquat'][i0], z['xquat'][i1]
    q1 = np.where((q0 * q1).sum(-1, keepdims=True) < 0, -q1, q1)
    quat = (1 - a) * q0 + a * q1
    quat /= np.linalg.norm(quat, axis=-1, keepdims=True)
    rope = (1 - a) * z['rope'][i0] + a * z['rope'][i1] if z['rope'].shape[1] else z['rope'][i0]
    tone = z['tone'][i0]
    return ft, pos, quat, rope, tone, i0


def run(lock, char_dir, sim_dir, out_dir, fps=None):
    fps = fps or lock['render']['fps']
    skel = json.load(open(os.path.join(char_dir, 'skeleton.json')))
    z = np.load(os.path.join(sim_dir, 'sim.npz'))
    ft, pos, quat, rope, tone, _ = resample(z, fps)
    names = [str(n) for n in z['body_names']]

    bpy.ops.wm.open_mainfile(filepath=os.path.join(char_dir, 'character.blend'))
    sc = bpy.context.scene
    sc.render.fps = fps
    sc.frame_start, sc.frame_end = 1, len(ft)
    arm = bpy.data.objects[skel['armature']]
    tc = skel['to_canonical']
    Cinv = Matrix.Rotation(tc['yaw'], 4, 'Z')            # canonical -> blender world rotation
    origin = Vector(tc['origin'])
    s = tc['scale']
    Wa = arm.matrix_world.copy()
    Wa_inv = Wa.inverted()

    bone_of = skel['bone_map']
    body_of = {v: k for k, v in bone_of.items()}
    order = []                                           # parents before children

    def visit(b):
        order.append(b)
        for c in b.children:
            visit(c)

    for b in arm.data.bones:
        if b.parent is None:
            visit(b)
    pbs = arm.pose.bones
    neutral = {b.name: pbs[b.name].matrix.copy() for b in order}           # armature space
    basis0 = {b.name: pbs[b.name].matrix_basis.copy() for b in order}
    Lrest = {b.name: (b.parent.matrix_local.inverted() @ b.matrix_local) if b.parent
             else b.matrix_local.copy() for b in order}
    head_w = {k: Wa @ neutral[v].to_translation() for k, v in bone_of.items()}
    for v in bone_of.values():
        pbs[v].rotation_mode = 'QUATERNION'
        for c in pbs[v].constraints:
            c.mute = True

    arm.animation_data_create()
    act = bpy.data.actions.new(f"KO_{lock['take']}_{lock['keys']['sim']}")
    arm.animation_data.action = act

    last_q = {}
    err_deg, err_mm = 0.0, 0.0
    for fi in range(len(ft)):
        P = {}
        for b in order:
            n = b.name
            Pp = P[b.parent.name] if b.parent else Matrix.Identity(4)
            if n in body_of:
                k = names.index(body_of[n])
                Rs = Quaternion(quat[fi, k]).to_matrix().to_4x4()
                Rw = Cinv @ Rs @ Cinv.inverted()
                pw = Cinv @ (Vector(pos[fi, k]) / s) + origin
                des = Matrix.Translation(pw) @ Rw @ Matrix.Translation(-head_w[body_of[n]]) \
                    @ Wa @ neutral[n]
                des = Wa_inv @ des
                basis = (Pp @ Lrest[n]).inverted() @ des
                q = basis.to_quaternion()
                if n in last_q and last_q[n].dot(q) < 0:
                    q.negate()
                last_q[n] = q
                pb = pbs[n]
                pb.rotation_quaternion = q
                pb.keyframe_insert('rotation_quaternion', frame=fi + 1)
                if body_of[n] == 'pelvis':
                    pb.location = basis.to_translation()
                    pb.keyframe_insert('location', frame=fi + 1)
                    B = Matrix.Translation(pb.location) @ q.to_matrix().to_4x4()
                else:
                    B = Matrix.Translation(basis0[n].to_translation()) @ q.to_matrix().to_4x4()
                P[n] = Pp @ Lrest[n] @ B
                # round trip: what the rig will really do vs what the sim did
                got = Wa @ P[n]
                dq = (Wa @ des).to_quaternion().rotation_difference(got.to_quaternion())
                err_deg = max(err_deg, math.degrees(dq.angle))
                err_mm = max(err_mm, (got.to_translation() - pw).length * s * 1000)
            else:
                P[n] = Pp @ Lrest[n] @ basis0[n]

    # face: slack, half-lidded after the KO, driven by tone (generic shape-key name match)
    t_ko = float(z['t_ko'])
    face_keys = []
    if t_ko >= 0:
        fk = int(t_ko * fps) + 1
        want = [(re.compile(r'(eye.*clos|blink)(?!.*(_l|_r|left|right)$)', re.I), 0.45),
                (re.compile(r'(mth_a$|mouth.*open|jaw.*open|(^|[._])a$|aa$)', re.I), 0.30)]
        for ob in bpy.data.objects:
            if ob.type != 'MESH' or not ob.data.shape_keys:
                continue
            for kb in ob.data.shape_keys.key_blocks:
                for rx, val in want:
                    if rx.search(kb.name) and kb.name not in face_keys:
                        kb.value = 0.0
                        kb.keyframe_insert('value', frame=max(1, fk))
                        kb.value = val
                        kb.keyframe_insert('value', frame=fk + int(0.15 * fps))
                        face_keys.append(kb.name)
                        break

    rep = {'action': act.name, 'frames': len(ft), 'fps': fps,
           'round_trip_max_rotation_error_deg': round(err_deg, 4),
           'round_trip_max_joint_position_error_mm': round(err_mm, 2),
           'face_shape_keys_driven': face_keys,
           'not_baked_yet': ['fingers', 'spring-bone hair', 'soft tissue', 'cloth']}
    np.savez_compressed(os.path.join(out_dir, 'frames.npz'), t=ft, rope=rope, tone=tone,
                        pelvis=pos[:, names.index('pelvis')], head=pos[:, names.index('head')])
    json.dump(rep, open(os.path.join(out_dir, 'bake.json'), 'w'), indent=1)
    sc.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, 'take.blend'), compress=True)
    print('[bake]', json.dumps(rep))
    return rep
