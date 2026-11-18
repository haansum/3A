"""A hold's attacker on screen (handoff track G5): another character's real arms, posed from the sim.

Owner 2026-11-18: first Mosin's arms, then "use Izzy's hands instead" with an alternate texture.
The character's main mesh and KO_skeleton are appended from its built character stage; the mesh is masked down to the arms (vertices weighted
>= 0.5 to her upper-arm, forearm, hand and finger deform bones), and every frame her arm chain is
swung so each bone points along its sim segment (shoulder -> elbow -> wrist -> knuckles). The rest
of her rig stays at rest and nothing else of her renders. Only the swing is matched: the twist
about each bone's own axis is whatever the minimal rotation gives (not simulated).
"""
import glob
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


def attacker_arms(fr, root, coll, char_dir, fps, texture_dir=None):
    """Append another character's arms (any rig the pipeline imported: bones come from its
    bone_map) and pose them on the sim's arm segments every frame. texture_dir: a folder of
    replacement textures; any image of the arm materials whose file name is found there (UDIM
    sets included) is swapped for that file on a copy of the material. -> (armature, mesh, n)"""
    skel = json.load(open(os.path.join(char_dir, 'skeleton.json')))
    bm = skel['bone_map']
    with bpy.data.libraries.load(os.path.join(char_dir, 'character.blend'), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in set(skel['character_meshes']) | {skel['armature']}]
    arm = next(o for o in dst.objects if o.type == 'ARMATURE')
    meshes = [o for o in dst.objects if o.type == 'MESH' and bm['hand_L'] in o.vertex_groups]
    body = max(meshes, key=lambda o: len(o.data.vertices))
    for o in dst.objects:
        if o in (arm, body):
            coll.objects.link(o)
        else:
            bpy.data.objects.remove(o)
    body.name, arm.name = 'ATK_body', 'ATK_skeleton'
    # mask to the arms and shoulders: the clavicle and every bone from the upper arm down
    arm_bones = set()
    for sd in ('L', 'R'):
        # owner 2026-11-18: include the shoulders (the clavicle bone the arm hangs from)
        par_ = arm.data.bones[bm['upper_arm_' + sd]].parent
        if par_ is not None:
            arm_bones.add(par_.name)
        stack = [arm.data.bones[bm['upper_arm_' + sd]]]
        while stack:
            b_ = stack.pop()
            arm_bones.add(b_.name)
            stack += list(b_.children)
    vg = body.vertex_groups.new(name='KO_atk_arm')
    gidx = {g.index for g in body.vertex_groups if g.name in arm_bones or g.name.startswith(ARM_GROUPS)}
    keep = [v.index for v in body.data.vertices if sum(g.weight for g in v.groups if g.group in gidx) >= 0.5]
    vg.add(keep, 1.0, 'REPLACE')
    for m in list(body.modifiers):
        if m.type in ('MASK', 'SHRINKWRAP', 'SURFACE_DEFORM', 'SOLIDIFY'):
            body.modifiers.remove(m)
    mk = body.modifiers.new('KO_arms_only', 'MASK')
    mk.vertex_group = 'KO_atk_arm'
    body.modifiers.move(len(body.modifiers) - 1, 0)          # mask first: fewer vertices to deform
    swapped = []
    for s in body.material_slots:
        if s.material and s.material.name.startswith('outline'):
            s.material = None
        elif s.material and texture_dir and s.material.use_nodes:
            m_ = s.material.copy()
            m_.name = 'ATK_' + s.material.name
            for n_ in m_.node_tree.nodes:
                if n_.type == 'TEX_IMAGE' and n_.image:
                    base_ = os.path.basename(n_.image.filepath)
                    cand = os.path.join(texture_dir, base_)
                    if glob.glob(cand.replace('<UDIM>', '*')):
                        im_ = n_.image.copy()
                        im_.filepath = cand
                        im_.reload()
                        n_.image = im_
                        swapped.append(base_)
            s.material = m_
    if texture_dir:
        print(f'[attacker] alternate textures from {texture_dir}: {sorted(set(swapped))}')

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
        """bones from the upper arm down to the hand, intermediate twist bones included"""
        top, hand = bm['upper_arm_' + side], bm['hand_' + side]
        c, b_ = [], arm.data.bones[hand]
        while b_ is not None:
            c.append(b_.name)
            if b_.name == top:
                break
            b_ = b_.parent
        return c[::-1]

    # gripping hands (one on the biceps, one behind her head): fingers curled, not splayed at rest.
    # Finger bones bend about their local X on these rigs. Angles by eye.
    for b in pb:
        nm = b.name.split('-')[-1]
        if nm.startswith('f_') and b.name.rsplit('.', 1)[-1] in ('L', 'R'):
            seg_ = nm.split('.')[1] if '.' in nm else '01'
            b.rotation_quaternion = Quaternion((1, 0, 0), math.radians({'01': 55, '02': 70, '03': 50}.get(seg_, 50)))
            b.keyframe_insert('rotation_quaternion', frame=1)
        elif nm.startswith('thumb'):
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
        for side in ('L', 'R'):
            tgt = {bm['upper_arm_' + side]: (inv @ ends[f'upper_arm_{side}'][1], bm['forearm_' + side]),
                   bm['forearm_' + side]: (inv @ ends[f'forearm_{side}'][1], bm['hand_' + side]),
                   bm['hand_' + side]: (inv @ ends[f'hand_{side}'][1], None)}
            c = chain(side)
            posed = {}
            par = arm.data.bones[c[0]].parent.name
            posed[par] = rest[par]
            for n in c:
                prn = arm.data.bones[n].parent.name
                base = posed[prn] @ (rest[prn].inverted() @ rest[n])     # rest pose under the posed parent
                if n in tgt:
                    target, nxt = tgt[n]
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


mosin_arms = attacker_arms          # first caller's name (2026-11-18)
