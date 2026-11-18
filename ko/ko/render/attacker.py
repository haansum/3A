"""A hold's attacker on screen (handoff track G5): another character's real arms, posed from the sim.

Owner 2026-11-18: "I want the arms to come from mosin". Mosin's Body mesh and KO_skeleton are
appended from her built character stage; the mesh is masked down to the arms (vertices weighted
>= 0.5 to her upper-arm, forearm, hand and finger deform bones), and every frame her arm chain is
swung so each bone points along its sim segment (shoulder -> elbow -> wrist -> knuckles). The rest
of her rig stays at rest and nothing else of her renders. Only the swing is matched: the twist
about each bone's own axis is whatever the minimal rotation gives (not simulated).
"""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

ARM_GROUPS = ('DEF-upper_arm', 'DEF-forearm', 'DEF-hand', 'DEF-f_', 'DEF-thumb', 'DEF-palm')


def _seg_ends(pos, quat, length):
    R = Quaternion(quat).to_matrix()
    ax = Vector(R.col[2])
    c = Vector(pos)
    return c - ax * (length / 2), c + ax * (length / 2)


def mosin_arms(fr, root, coll, char_dir, fps):
    skel = json.load(open(os.path.join(char_dir, 'skeleton.json')))
    with bpy.data.libraries.load(os.path.join(char_dir, 'character.blend'), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in ('Body', skel['armature'])]
    body = arm = None
    for ob in dst.objects:
        coll.objects.link(ob)
        if ob.type == 'ARMATURE':
            arm = ob
        else:
            body = ob
    body.name, arm.name = 'ATK_body', 'ATK_skeleton'
    # mask to the arms
    vg = body.vertex_groups.new(name='KO_atk_arm')
    gidx = {g.index for g in body.vertex_groups if g.name.startswith(ARM_GROUPS)}
    keep = [v.index for v in body.data.vertices if sum(g.weight for g in v.groups if g.group in gidx) >= 0.5]
    vg.add(keep, 1.0, 'REPLACE')
    for m in list(body.modifiers):
        if m.type in ('MASK', 'SHRINKWRAP', 'SURFACE_DEFORM', 'SOLIDIFY'):
            body.modifiers.remove(m)
    mk = body.modifiers.new('KO_arms_only', 'MASK')
    mk.vertex_group = 'KO_atk_arm'
    body.modifiers.move(len(body.modifiers) - 1, 0)          # mask first: fewer vertices to deform
    for s in body.material_slots:
        if s.material and s.material.name.startswith('outline'):
            s.material = None

    # place her: shoulders on the sim's shoulders, facing the way the hold faces
    tc = skel['to_canonical']
    Rm = Matrix.Translation(Vector(tc['origin'])) @ Matrix.Rotation(tc['yaw'], 4, 'Z') @ Matrix.Scale(1.0 / tc['scale'], 4)
    Wm = arm.matrix_world.copy()
    Wb = body.matrix_world.copy()
    s_c = 0.5 * (Vector(skel['joints']['upper_arm_L']) + Vector(skel['joints']['upper_arm_R']))
    body.parent = arm                                         # keep the mesh where it sat on her rig
    body.matrix_parent_inverse = Matrix.Identity(4)
    body.matrix_basis = Wm.inverted() @ Wb
    arm.parent = root
    arm.matrix_parent_inverse = Matrix.Identity(4)

    names = [str(x) for x in fr['grapple_names']]
    gp, gq, gl = np.asarray(fr['grapple_pos']), np.asarray(fr['grapple_quat']), np.asarray(fr['grapple_len'])
    pb = arm.pose.bones
    for b in pb:
        b.rotation_mode = 'QUATERNION'
    rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}

    def chain(side):
        return [f'DEF-upper_arm.{side}', f'DEF-upper_arm.{side}.001', f'DEF-forearm.{side}',
                f'DEF-forearm.{side}.001', f'DEF-hand.{side}']

    # her hands grip (one on her biceps, one behind the head): fingers curled, not splayed at rest.
    # Rigify finger bones bend about their local X. Angles by eye.
    for b in pb:
        if b.name.startswith('DEF-f_'):
            seg_ = b.name.split('.')[1]
            b.rotation_quaternion = Quaternion((1, 0, 0), math.radians({'01': 55, '02': 70, '03': 50}.get(seg_, 50)))
            b.keyframe_insert('rotation_quaternion', frame=1)
        elif b.name.startswith('DEF-thumb'):
            b.rotation_quaternion = Quaternion((1, 0, 0), math.radians(25))
            b.keyframe_insert('rotation_quaternion', frame=1)

    for f in range(len(gp)):
        ends = {n: _seg_ends(gp[f, k], gq[f, k], gl[k]) for k, n in enumerate(names)}
        sR, sL = ends['upper_arm_R'][0], ends['upper_arm_L'][0]
        left = sL - sR
        left.z = 0.0
        left.normalize()
        fwd = left.cross(Vector((0, 0, 1)))
        psi = math.atan2(fwd.y, fwd.x) - math.atan2(-1.0, 0.0)
        Rz = Matrix.Rotation(psi, 4, 'Z')
        p = 0.5 * (sR + sL)
        place = Matrix.Translation(p - (Rz @ s_c)) @ Rz
        basis_obj = place @ Rm.inverted() @ Wm
        arm.matrix_basis = basis_obj
        arm.keyframe_insert('location', frame=f + 1)
        arm.keyframe_insert('rotation_quaternion' if arm.rotation_mode == 'QUATERNION' else 'rotation_euler', frame=f + 1)
        arm.keyframe_insert('scale', frame=f + 1)
        inv = basis_obj.inverted()
        for side, tag in (('L', 'L'), ('R', 'R')):
            E = inv @ ends[f'upper_arm_{tag}'][1]
            Wr = inv @ ends[f'forearm_{tag}'][1]
            H = inv @ ends[f'hand_{tag}'][1]
            c = chain(side)
            if any(n not in rest for n in c):
                continue
            posed = {}
            par = arm.data.bones[c[0]].parent.name
            posed[par] = rest[par]
            for n, target in ((c[0], E), (c[1], None), (c[2], Wr), (c[3], None), (c[4], H)):
                prn = arm.data.bones[n].parent.name
                base = posed[prn] @ (rest[prn].inverted() @ rest[n])     # rest pose under the posed parent
                if target is not None:
                    nxt = {c[0]: c[2], c[2]: c[4]}.get(n)
                    if nxt is not None:      # where the next joint sits, carried by this bone
                        tip = base @ (rest[n].inverted() @ rest[nxt].translation)
                    else:
                        tip = base @ (rest[n].inverted() @ (arm.data.bones[n].tail_local))
                    head = base.translation
                    q = (tip - head).rotation_difference(target - head)
                    M = Matrix.Translation(head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-head) @ base
                else:
                    M = base
                posed[n] = M
                basis = (rest[prn].inverted() @ rest[n]).inverted() @ posed[prn].inverted() @ M
                pb[n].matrix_basis = basis
                pb[n].keyframe_insert('rotation_quaternion', frame=f + 1)
                pb[n].keyframe_insert('location', frame=f + 1)
    return arm, body, len(keep)
