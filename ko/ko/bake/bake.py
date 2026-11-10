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

    # ---- directed layers on bones the sim does not own (eyes, toes) ----------------------
    # Each is a rotation given in HER axes (x = her left, -y = her front, z = up) at the
    # neutral pose, converted per bone, so no rig-specific axis or sign is ever guessed.
    bcfg = lock.get('bake') or {}
    events = dict(json.loads(str(z['events'])))
    events['ko'] = float(z['t_ko'])
    Carm = (Wa_inv @ Cinv).to_3x3()                   # canonical axes -> armature space

    def local_delta(bone, axis_canon, angle):
        if abs(angle) < 1e-6:
            return Quaternion()
        ax = (Carm @ Vector(axis_canon)).normalized()
        N = neutral[bone].to_3x3().normalized()
        return (N.inverted() @ Matrix.Rotation(angle, 3, ax) @ N).to_quaternion()

    def ramp(cfg_, tt):
        t0 = events.get(cfg_.get('after', 'ko'))
        if t0 is None or tt < t0:
            return 0.0
        return min(1.0, (tt - t0) / max(cfg_.get('rise', 0.2), 1e-3))

    extra = {}                                        # bone -> f(t) -> local quaternion
    layers_used = []
    g = bcfg.get('gaze')
    eye_bones = (lock['character'].get('face') or {}).get('eye_bones') or \
        [b.name for b in order if re.match(r'^(left|right)eye$|^eye[._]?[lr]$|.*faceeye$', b.name, re.I)]
    eye_bones = [b for b in eye_bones if b in pbs]
    # Prefer the rig's own eye-look shape keys when it has them (flat anime eyes do not respond
    # to rotating an eye bone). Which key is 'up' and which is 'her left' is measured from what
    # each key does to the mesh, never read off its name. Drivers on keys we animate are
    # removed in this working copy, otherwise they override the keyframes.
    face_cfg = lock['character'].get('face') or {}
    gaze_keys = []
    if g:
        Cw = Cinv.to_3x3().inverted()                 # blender world -> her axes
        for ob in bpy.data.objects:
            if ob.type != 'MESH' or not ob.data.shape_keys:
                continue
            kbs = ob.data.shape_keys.key_blocks
            base = np.array([v.co for v in kbs[0].data])
            Mw = np.array(ob.matrix_world)[:3, :3]
            for kb in kbs:
                if not re.search(r'look', kb.name, re.I):
                    continue
                dlt = np.array([v.co for v in kb.data]) - base
                mv = np.linalg.norm(dlt, axis=1) > 1e-5
                if not mv.any():
                    continue
                d_her = np.array(Cw) @ (Mw @ dlt[mv].mean(0))
                want_side = 1.0 if g.get('side', 'her_left') == 'her_left' else -1.0
                if d_her[2] > 0.6 * np.linalg.norm(d_her):
                    gaze_keys.append((ob, kb.name, face_cfg.get('gaze_up', 0.6)))
                elif want_side * d_her[0] > 0.6 * np.linalg.norm(d_her):
                    gaze_keys.append((ob, kb.name, face_cfg.get('gaze_side', 0.35)))
    if gaze_keys:
        layers_used.append({'gaze_keys': [k for _, k, _ in gaze_keys]})
    elif g and eye_bones:
        sgn = 1.0 if g.get('side', 'her_left') == 'her_left' else -1.0
        up, side = math.radians(g['up_deg']), sgn * math.radians(g['side_deg'])
        for eb_ in eye_bones:
            def f(tt, eb_=eb_):
                w_ = ramp(g, tt)
                return local_delta(eb_, (0, 0, 1), side * w_) @ local_delta(eb_, (1, 0, 0), -up * w_)
            extra[eb_] = f
        layers_used.append({'gaze': eye_bones})
    tc_ = bcfg.get('toe_curl')
    if tc_:
        toes = []
        for key in ('toe_L', 'toe_R'):
            base = (skel.get('aux_bones') or {}).get(key)
            if base in pbs:
                stack = [(arm.data.bones[base], 0)]
                while stack:
                    b_, depth = stack.pop()
                    toes.append((b_.name, depth))
                    stack += [(c, depth + 1) for c in b_.children if not c.children or 'toe' in c.name.lower()]
        for name_, depth in toes:
            def f(tt, name_=name_, depth=depth):
                ang = math.radians(tc_['deg']) * (0.4 if depth == 0 else 0.5) * ramp(tc_, tt)
                return local_delta(name_, (1, 0, 0), ang)     # about her left axis = curl under
            extra[name_] = f
        layers_used.append({'toe_curl': len(toes)})
    for n_ in extra:
        pbs[n_].rotation_mode = 'QUATERNION'
        for c in pbs[n_].constraints:
            c.mute = True

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
            elif n in extra:
                qd = extra[n](ft[fi])
                B = basis0[n] @ qd.to_matrix().to_4x4()
                pb = pbs[n]
                pb.rotation_quaternion = B.to_quaternion()
                pb.keyframe_insert('rotation_quaternion', frame=fi + 1)
                P[n] = Pp @ Lrest[n] @ B
            else:
                P[n] = Pp @ Lrest[n] @ basis0[n]

    # face: shape keys named in the manifest, ramped in at the KO. Eyes stay open (house rule).
    t_ko = float(z['t_ko'])
    face_keys = []
    if t_ko >= 0:
        fk = int(t_ko * fps) + 1
        for ob in bpy.data.objects:
            if ob.type != 'MESH' or not ob.data.shape_keys:
                continue
            want_keys = dict(bcfg.get('face_keys') or {})
            want_keys.update(face_cfg.get('ko_keys') or {})
            want_keys.update({k: v for o_, k, v in gaze_keys if o_ == ob})
            ad = ob.data.shape_keys.animation_data
            for kname, val in want_keys.items():
                kb = ob.data.shape_keys.key_blocks.get(kname)
                if kb is None:
                    continue
                if ad:
                    for drv in [d for d in ad.drivers if d.data_path == f'key_blocks["{kname}"].value']:
                        ad.drivers.remove(drv)
                kb.value = 0.0
                kb.keyframe_insert('value', frame=max(1, fk))
                kb.value = val
                kb.keyframe_insert('value', frame=fk + max(1, int(0.15 * fps)))
                face_keys.append(f'{ob.name}:{kname}')

    rep = {'action': act.name, 'frames': len(ft), 'fps': fps,
           'round_trip_max_rotation_error_deg': round(err_deg, 4),
           'round_trip_max_joint_position_error_mm': round(err_mm, 2),
           'face_shape_keys_driven': face_keys, 'directed_layers': layers_used,
           'not_baked_yet': ['fingers', 'spring-bone hair', 'soft tissue', 'cloth']}
    np.savez_compressed(os.path.join(out_dir, 'frames.npz'), t=ft, rope=rope, tone=tone,
                        pelvis=pos[:, names.index('pelvis')], head=pos[:, names.index('head')],
                        head_quat=quat[:, names.index('head')],
                        foot_L=pos[:, names.index('foot_L')], foot_R=pos[:, names.index('foot_R')],
                        t_ko=z['t_ko'], events=z['events'], strikes=z['strikes'])
    json.dump(rep, open(os.path.join(out_dir, 'bake.json'), 'w'), indent=1)
    sc.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, 'take.blend'), compress=True)
    print('[bake]', json.dumps(rep))
    return rep
