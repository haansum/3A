"""Stage 1: character lock. Any humanoid rig (.blend/.vrm/.glb/.gltf/.fbx) ->
  character.blend   the rig, textures packed, untouched otherwise (source file is never edited)
  skeleton.json     canonical bone map, joint positions in the canonical sim frame
  skin.npz          rest-pose skin vertices in the canonical frame + owning sim body per vertex

Canonical frame: metres, Z up, character faces -Y, +X is her left, feet on z=0, pelvis over origin.

Run inside Blender's Python (bpy):  python -m ko.character.import_rig SRC --out DIR [--map m.json]
"""
import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile

import bpy
import numpy as np
from mathutils import Matrix, Vector

from .bonemap import CANON, SECONDARY, auto_map, owner_of_every_bone


def load(src):
    ext = os.path.splitext(src)[1].lower()
    if ext == '.blend':
        bpy.ops.wm.open_mainfile(filepath=src, use_scripts=False)   # never run embedded scripts
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if ext in ('.vrm', '.glb', '.gltf'):
        if ext == '.vrm':   # a VRM is a binary glTF; the stock importer reads it under .glb
            tmp = os.path.join(tempfile.mkdtemp(), 'model.glb')
            shutil.copy(src, tmp)
            src = tmp
        bpy.ops.import_scene.gltf(filepath=src)
    elif ext == '.fbx':
        bpy.ops.import_scene.fbx(filepath=src)
    else:
        raise SystemExit(f'unsupported character file type: {ext}')


def skinned_meshes(arm):
    return [o for o in bpy.data.objects if o.type == 'MESH' and
            any(m.type == 'ARMATURE' and m.object == arm for m in o.modifiers)]


def visible_vertices(ob):
    """Boolean per vertex: False where the surface is cut away by texture alpha.
    Character generators (VRoid) ship whole garment templates and hide the unused parts with
    a transparent texture; that invisible geometry must not shape the collision body."""
    me = ob.data
    vis = np.zeros(len(me.vertices), dtype=bool)
    if not me.uv_layers:
        vis[:] = True
        return vis
    uv = np.empty(len(me.loops) * 2, dtype=np.float32)
    me.uv_layers.active.data.foreach_get('uv', uv)
    uv = uv.reshape(-1, 2)
    lv = np.empty(len(me.loops), dtype=np.int32)
    me.loops.foreach_get('vertex_index', lv)
    lmat = np.empty(len(me.loops), dtype=np.int32)
    pm = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get('material_index', pm)
    ls = np.empty(len(me.polygons), dtype=np.int32)
    lt = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get('loop_start', ls)
    me.polygons.foreach_get('loop_total', lt)
    lmat = np.repeat(pm, lt)
    for mi, slot in enumerate(ob.material_slots):
        sel = lmat == mi
        if not sel.any():
            continue
        img = None
        mat = slot.material
        if mat and mat.node_tree:      # any image whose alpha output drives the shader
            for n in mat.node_tree.nodes:
                if n.type == 'TEX_IMAGE' and n.image and n.outputs['Alpha'].is_linked:
                    img = n.image
        if img is None or img.channels < 4 or img.size[0] == 0:
            vis[lv[sel]] = True
            continue
        w, h = img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        alpha = px.reshape(h, w, 4)[:, :, 3]
        u = np.clip((uv[sel, 0] % 1.0) * w, 0, w - 1).astype(int)
        v = np.clip((uv[sel, 1] % 1.0) * h, 0, h - 1).astype(int)
        vis[lv[sel][alpha[v, u] > 0.5]] = True
    return vis


def pick_armature():
    arms = [o for o in bpy.data.objects if o.type == 'ARMATURE']
    if not arms:
        raise SystemExit('no armature in file')
    return max(arms, key=lambda a: (len(skinned_meshes(a)), len(a.data.bones)))


def extract_deform_skeleton(arm):
    """Control rigs (Rigify and relatives) deform the mesh through DEF bones that are driven by
    hundreds of constraint/helper bones. Baking a simulation onto that is rig-specific, so
    build a plain skeleton from the deform bones only (same rest pose, same names, so the
    existing vertex groups bind unchanged), parent each bone to its nearest deform ancestor,
    and point the meshes at it. The original rig stays in the file, untouched and unposed,
    so shape-key drivers that read it keep their neutral values."""
    src = arm.data.bones
    deform = [b for b in src if b.use_deform]
    names = {b.name for b in deform}

    def parent_of(b):
        a = b.parent
        while a is not None:
            if a.name in names:
                return a.name
            if a.name.startswith('ORG-') and 'DEF-' + a.name[4:] in names \
                    and 'DEF-' + a.name[4:] != b.name:
                return 'DEF-' + a.name[4:]
            a = a.parent
        return None

    data = bpy.data.armatures.new('KO_skeleton')
    ob = bpy.data.objects.new('KO_skeleton', data)
    (arm.users_collection[0] if arm.users_collection else bpy.context.scene.collection).objects.link(ob)
    ob.matrix_world = arm.matrix_world.copy()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.hide_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = data.edit_bones
    for b in deform:
        e = eb.new(b.name)
        e.head, e.tail = b.head_local, b.tail_local
        e.matrix = b.matrix_local
        e.length = b.length
    for b in deform:
        p = parent_of(b)
        if p:
            eb[b.name].parent = eb[p]
            eb[b.name].use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    # how far the rig's displayed pose is from its rest pose (should be ~0 for a neutral file)
    dev = max(((arm.pose.bones[b.name].matrix.to_translation()
                - b.matrix_local.to_translation()).length for b in deform), default=0.0)
    for o in bpy.data.objects:
        if o.type == 'MESH':
            for m in o.modifiers:
                if m.type == 'ARMATURE' and m.object == arm:
                    m.object = ob
        if o.parent == arm and o.parent_type == 'BONE' and o.parent_bone in names:
            mw = o.matrix_world.copy()
            o.parent = ob
            o.matrix_world = mw
    return ob, dev


def bone_table(arm):
    """{bone: parent}. For control rigs (Rigify) only the deform skeleton is considered,
    re-parented through the non-deform helpers."""
    bones = arm.data.bones
    deform_only = sum(b.name.startswith('DEF-') for b in bones) > 10
    keep = {b.name for b in bones if (b.use_deform or not deform_only)}
    table = {}
    for b in bones:
        if b.name not in keep:
            continue
        p = b.parent
        while p is not None and p.name not in keep:
            p = p.parent
        table[b.name] = p.name if p else None
    return table


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('--out', required=True)
    ap.add_argument('--map', help='json {canonical: bone name} overrides')
    ap.add_argument('--name')
    ap.add_argument('--preview-failed-outfit', action='store_true',
                    help='save even if the coverage gate fails (for inspection only)')
    ap.add_argument('--outfit', help='json: garments to fit and what to hide (see outfit.py)')
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    src_hash = hashlib.sha256(open(a.src, 'rb').read()).hexdigest()
    load(os.path.abspath(a.src))

    arm = pick_armature()
    rig_note = None
    nb = len(arm.data.bones)
    nd = sum(b.use_deform for b in arm.data.bones)
    if nb > 150 and nd < 0.6 * nb:              # a control rig, not a plain skeleton
        src_name = arm.name
        arm, dev = extract_deform_skeleton(arm)
        rig_note = {'control_rig': src_name, 'bones': nb, 'deform_bones': nd,
                    'pose_vs_rest_max_m': round(dev, 4)}
    table = bone_table(arm)
    override = json.load(open(a.map)) if a.map else None
    cmap, report = auto_map(table, override)
    if report['merged']:
        raise SystemExit(f"rig has too few trunk bones for {report['merged']}; "
                         f"chain was {report['spine_chain']}. Not supported yet.")
    owner = owner_of_every_bone({b.name: (b.parent.name if b.parent else None)
                                 for b in arm.data.bones}, cmap)

    # The neutral pose is the pose the file is saved in, NOT the armature rest pose: importers
    # (glTF/VRM) leave rest = bind pose and put the real T-pose in the pose bones. Nothing in
    # the rig is edited; bake composes sim rotations onto this same neutral pose.
    arm.data.pose_position = 'POSE'
    bpy.context.view_layer.update()
    W = arm.matrix_world
    head = {k: W @ arm.pose.bones[v].head for k, v in cmap.items()}
    tail = {k: W @ arm.pose.bones[v].tail for k, v in cmap.items()}

    # --- canonical frame -------------------------------------------------------------------
    left = (head['upper_arm_L'] - head['upper_arm_R'])
    left.z = 0
    yaw = math.atan2(left.y, left.x)
    C = Matrix.Rotation(-yaw, 4, 'Z')

    outfit_rep = None
    if a.outfit:
        from . import outfit as outfit_mod
        ocfg = json.load(open(a.outfit))
        # Remove the outfit being replaced from this working copy (the source file is never
        # touched). Hiding is not enough: such rigs drive hide flags from their own UI drivers.
        doomed = []
        for cname in ocfg.get('hide_collections', []):
            if cname in bpy.data.collections:
                doomed += list(bpy.data.collections[cname].objects)
        doomed += [bpy.data.objects[n] for n in ocfg.get('hide_objects', []) if n in bpy.data.objects]
        for o in set(doomed):
            bpy.data.objects.remove(o, do_unlink=True)
        cand = [o for o in skinned_meshes(arm) if not o.hide_render]
        body = bpy.data.objects[ocfg['body']] if ocfg.get('body') else \
            max(cand, key=lambda o: len(o.data.vertices))
        outfit_rep, _ = outfit_mod.fit(arm, body, head, ocfg, body.users_collection[0], owner)
        print('[outfit]', json.dumps(outfit_rep))
        if not outfit_rep['coverage_ok'] and not a.preview_failed_outfit:
            raise SystemExit('outfit: coverage gate failed; garments do not cover the listed '
                             'groups. Not saving this character.')
    char_meshes = [o for o in skinned_meshes(arm) if not o.hide_render]
    disabled = []
    for ob in char_meshes:      # skin = shape keys + armature only (no subsurf/solidify shell)
        for md in ob.modifiers:
            if md.type != 'ARMATURE' and md.show_viewport:
                md.show_viewport = False
                disabled.append(md)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    verts, owners, mesh_names = [], [], []
    hidden = 0
    for ob in skinned_meshes(arm):
        if SECONDARY.search(ob.name):
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        if len(me.vertices) != len(ob.data.vertices):
            ev.to_mesh_clear()
            me, ev = ob.data, None
        gname = {g.index: g.name for g in ob.vertex_groups}
        co = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        M = np.array(ob.matrix_world)
        co = co @ M[:3, :3].T + M[:3, 3]
        own = np.full(len(co), -1, dtype=np.int16)
        vis = visible_vertices(ob)
        hidden += int((~vis).sum())
        for v in ob.data.vertices:
            if not vis[v.index]:
                continue
            acc = {}
            sec = 0.0
            for g in v.groups:
                gn_ = gname.get(g.group)
                if gn_ not in owner:        # mask / selection groups are not bones: ignore
                    continue
                o = owner[gn_]
                if o is None:
                    sec += g.weight
                else:
                    acc[o] = acc.get(o, 0.0) + g.weight
            if acc:
                best = max(acc, key=acc.get)
                if acc[best] >= sec:
                    own[v.index] = CANON.index(best)
        verts.append(co)
        owners.append(own)
        mesh_names.append(ob.name)
        if ev:
            ev.to_mesh_clear()
    for md in disabled:
        md.show_viewport = True
    # everything that is not the character (rig widgets, helper shapes) must never render
    keep = set(o.name for o in char_meshes)
    hidden_objs = []
    for o in bpy.data.objects:
        if o.type in ('MESH', 'CURVE', 'SURFACE', 'FONT', 'META') and o.name not in keep \
                and not o.hide_render:
            anc, is_child = o.parent, False
            while anc is not None:
                if anc == arm or anc.name in keep:
                    is_child = True
                    break
                anc = anc.parent
            if not is_child:
                o.hide_render = True
                hidden_objs.append(o.name)
    verts = np.concatenate(verts)
    owners = np.concatenate(owners)
    body = verts[owners >= 0]
    if len(body) < 100:
        raise SystemExit('no skin vertices weighted to the mapped skeleton')

    height_raw = body[:, 2].max() - body[:, 2].min()
    scale = 1.0
    for s in (1.0, 0.01, 0.001, 100.0, 0.0254):       # m, cm, mm, 1/100, inches
        if 1.2 <= height_raw * s <= 2.4:
            scale = s
            break
    origin = np.array([head['pelvis'].x, head['pelvis'].y, body[:, 2].min()])
    Cn = np.array(C)[:3, :3]

    def canon(p):
        return (scale * (Cn @ (np.asarray(p, dtype=float) - origin))).tolist()

    cverts = scale * ((verts - origin) @ Cn.T)
    joints = {k: canon(head[k]) for k in CANON}
    ends = {k: canon(tail[k]) for k in CANON}

    # facing cross-check from the feet (toes should point to -Y)
    toe = report['aux'].get('toe_L')
    foot_dir = (np.array(canon(W @ arm.pose.bones[toe].head)) - np.array(joints['foot_L'])
                if toe else np.array(ends['foot_L']) - np.array(joints['foot_L']))
    facing_ok = bool(foot_dir[1] < 0)

    skel = {
        'name': a.name or os.path.splitext(os.path.basename(a.src))[0],
        'source': {'file': os.path.basename(a.src), 'sha256': src_hash},
        'blender': bpy.app.version_string,
        'armature': arm.name,
        'bone_map': cmap,
        'aux_bones': report['aux'],
        'spine_chain': report['spine_chain'],
        'joints': joints,
        'bone_tails': ends,
        'height': float(cverts[owners >= 0][:, 2].max()),
        'to_canonical': {'yaw': yaw, 'origin': origin.tolist(), 'scale': scale},
        'rig': rig_note,
        'outfit': outfit_rep,
        'character_meshes': sorted(keep),
        'checks': {'facing_from_feet_agrees': facing_ok, 'meshes': mesh_names,
                   'hidden_non_character_objects': len(hidden_objs),
                   'n_vertices': int(len(cverts)), 'n_body_vertices': int((owners >= 0).sum()),
                   'alpha_hidden_vertices': hidden},
    }
    if not facing_ok:
        print('WARNING: feet point to +Y after canonicalising from the shoulders; '
              'left/right bone names may be swapped on this rig', file=sys.stderr)
    json.dump(skel, open(os.path.join(a.out, 'skeleton.json'), 'w'), indent=1)
    np.savez_compressed(os.path.join(a.out, 'skin.npz'), verts=cverts.astype(np.float32),
                        owner=owners)

    try:
        bpy.ops.file.pack_all()
    except RuntimeError as e:
        print('pack_all:', e, file=sys.stderr)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(a.out, 'character.blend')),
                                compress=True)
    print(json.dumps({'name': skel['name'], 'height_m': round(skel['height'], 3),
                      'scale': scale, 'yaw_deg': round(math.degrees(yaw), 1),
                      'facing_ok': facing_ok, 'bone_map': cmap, 'rig': rig_note,
                      'spine_chain': report['spine_chain'],
                      'hidden_non_character_objects': len(hidden_objs),
                      'verts_per_body': {CANON[i]: int((owners == i).sum())
                                         for i in range(len(CANON))},
                      'unowned_vertices': int((owners < 0).sum()),
                      'alpha_hidden_vertices': hidden}, indent=1))


if __name__ == '__main__':
    main()
