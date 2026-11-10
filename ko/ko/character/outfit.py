"""Fit unrigged garments from another .blend onto a character and bind them to its skeleton.

  1. append the garment objects, bake their transforms
  2. affine pre-fit: scale to the body's measured width/depth at the garment's region
     (bust or hips) and move it there
  3. shrink-wrap onto the skin with a small outward offset, relax, wrap again
  4. copy skin weights from the body (nearest surface) and add an armature modifier
  5. coverage gate: every body vertex in the listed cover groups must have fabric within a
     few centimetres along its normal, otherwise the fit is rejected

Runs inside the importer, before the skin is sampled, so the sim's collision hulls and the
rendered surface both include the garments.
"""
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def body_coords(body, dg):
    ev = body.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    no = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('normal', no)
    ev.to_mesh_clear()
    M = np.array(body.matrix_world)
    return co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3], no.reshape(-1, 3) @ M[:3, :3].T


def append_objects(path, names):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        missing = [n for n in names if n not in src.objects]
        if missing:
            raise SystemExit(f'outfit: {missing} not in {path}; has {list(src.objects)}')
        dst.objects = list(names)
    return list(dst.objects)


def fit(arm, body, joints_w, cfg, coll, owner):
    """joints_w: canonical joint name -> world position (Vector). Returns report dict."""
    only_arm = []
    for md in body.modifiers:
        if md.type != 'ARMATURE' and md.show_viewport:
            md.show_viewport = False
            only_arm.append(md)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    co, no = body_coords(body, dg)
    cx = joints_w['pelvis'].x
    # torso = vertices owned by the pelvis/spine/chest bodies (a width cut-off would clip a
    # bust wider than the shoulder joints; hands hang at hip height in an A-pose)
    gown = {vg.index: owner.get(vg.name) for vg in body.vertex_groups if vg.name in owner}
    torso = np.zeros(len(co), bool)
    for vtx in body.data.vertices:
        acc = {}
        for e in vtx.groups:
            o = gown.get(e.group)
            if o:
                acc[o] = acc.get(o, 0.0) + e.weight
        if acc and max(acc, key=acc.get) in ('pelvis', 'spine', 'chest'):
            torso[vtx.index] = True
    knee_z = joints_w['shin_L'].z
    mid = (np.abs(co[:, 0] - cx) < 0.012) & (co[:, 2] > knee_z + 0.1) & (co[:, 2] < joints_w['chest'].z)
    crotch_z = float(co[mid, 2].min())
    bust_z = float(arm.data.bones[cfg['bust_bone']].head_local.z + arm.matrix_world.translation.z) \
        if cfg.get('bust_bone') in arm.data.bones else \
        float(joints_w['chest'].z + 0.55 * (joints_w['neck'].z - joints_w['chest'].z))

    def slab(z0, z1):
        m = torso & (co[:, 2] > z0) & (co[:, 2] < z1)
        return co[m]

    skin_tree = BVHTree.FromPolygons([Vector(c) for c in co],
                                     [tuple(p.vertices) for p in body.data.polygons])
    objs = append_objects(cfg['file'], [g['object'] for g in cfg['garments']])
    report = {'crotch_z': round(crotch_z, 3), 'bust_z': round(bust_z, 3), 'garments': []}
    fitted = []
    for ob, g in zip(objs, cfg['garments']):
        coll.objects.link(ob)
        for md in list(ob.modifiers):
            ob.modifiers.remove(md)
        me = ob.data
        me.transform(ob.matrix_world)
        ob.matrix_world.identity()
        v = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', v)
        v = v.reshape(-1, 3)
        lo, hi = v.min(0), v.max(0)
        size, ctr = hi - lo, 0.5 * (lo + hi)
        if g['region'] == 'hips':
            s = slab(crotch_z + 0.05, crotch_z + 0.13)
            w_t, d_t = np.ptp(s[:, 0]), np.ptp(s[:, 1])
            sx = w_t / size[0] * g.get('ease', 1.03)
            sy = d_t / size[1] * g.get('ease', 1.03)
            sz = g.get('height_scale', 0.5 * (sx + sy) * 0.85)
            tgt = np.array([cx, 0.5 * (s[:, 1].min() + s[:, 1].max()),
                            crotch_z - 0.006 + 0.5 * size[2] * sz])
        else:  # bust
            s = slab(bust_z - 0.10, bust_z + 0.06)
            w_t, d_t = np.ptp(s[:, 0]), np.ptp(s[:, 1])
            sx = w_t / size[0] * g.get('ease', 1.02)
            sy = d_t / size[1] * g.get('ease', 1.02)
            sz = g.get('height_scale', 0.5 * (sx + sy) * 0.95)
            tgt = np.array([cx, 0.5 * (s[:, 1].min() + s[:, 1].max()),
                            bust_z + g.get('z_offset', -0.02)])
        v = (v - ctr) * np.array([sx, sy, sz]) + tgt
        me.vertices.foreach_set('co', v.ravel())
        me.update()

        def wrap(offset):
            md = ob.modifiers.new('fit', 'SHRINKWRAP')
            md.target = body
            md.wrap_method = 'NEAREST_SURFACEPOINT'
            md.wrap_mode = 'OUTSIDE_SURFACE'
            md.offset = offset
            return md

        def apply_all():
            bpy.context.view_layer.update()
            d2 = bpy.context.evaluated_depsgraph_get()
            ev = ob.evaluated_get(d2)
            m2 = ev.to_mesh()
            c2 = np.empty(len(m2.vertices) * 3)
            m2.vertices.foreach_get('co', c2)
            ev.to_mesh_clear()
            for md in list(ob.modifiers):
                ob.modifiers.remove(md)
            me.vertices.foreach_set('co', c2)
            me.update()

        off = g.get('offset', 0.006)
        wrap(off)
        apply_all()
        sm = ob.modifiers.new('relax', 'SMOOTH')
        sm.iterations, sm.factor = 6, 0.5
        wrap(off)
        apply_all()
        # push-out: shrink-wrap can leave fabric folded under the skin on strongly curved
        # bodies. No fabric vertex may end closer than `off` to the skin, measured along the
        # skin normal at its nearest point.
        pushed = 0
        for _ in range(4):
            moved = 0
            for vtx in me.vertices:
                hit = skin_tree.find_nearest(vtx.co)
                if hit[0] is None:
                    continue
                pnt, nrm = hit[0], hit[1]
                if (vtx.co - pnt).dot(nrm) < off:
                    vtx.co = pnt + nrm * off
                    moved += 1
            pushed = max(pushed, moved)
            if not moved:
                break
        me.update()

        # skin weights from the body, then bind
        for vg in list(ob.vertex_groups):
            ob.vertex_groups.remove(vg)
        dt = ob.modifiers.new('w', 'DATA_TRANSFER')
        dt.object = body
        dt.use_vert_data = True
        dt.data_types_verts = {'VGROUP_WEIGHTS'}
        dt.vert_mapping = 'POLYINTERP_NEAREST'
        dt.layers_vgroup_select_src = 'ALL'
        dt.layers_vgroup_select_dst = 'NAME'
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.datalayout_transfer(modifier='w')
        bpy.ops.object.modifier_apply(modifier='w')
        bones = {b.name for b in arm.data.bones}
        for vg in list(ob.vertex_groups):
            if vg.name not in bones:
                ob.vertex_groups.remove(vg)
        am = ob.modifiers.new('Armature', 'ARMATURE')
        am.object = arm
        ob.parent = body.parent
        fitted.append(ob)
        report['garments'].append({'object': ob.name, 'region': g['region'],
                                   'scale': [round(float(x), 3) for x in (sx, sy, sz)],
                                   'vertices': len(me.vertices), 'pushed_out': pushed,
                                   'weight_groups': len(ob.vertex_groups)})

    # coverage gate ------------------------------------------------------------------------
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    trees = []
    for ob in fitted:
        me = ob.data
        vv = [ob.matrix_world @ x.co for x in me.vertices]
        trees.append(BVHTree.FromPolygons(vv, [tuple(p.vertices) for p in me.polygons]))
    gidx = {vg.name: vg.index for vg in body.vertex_groups}
    want = [gidx[n] for n in cfg.get('cover_groups', []) if n in gidx]
    total = covered = 0
    per = {}
    miss = []
    names = {i: n for n, i in gidx.items()}
    # only skin that can actually be seen from outside counts (these rigs carry interior
    # geometry in the same groups): the outward ray must not hit the body itself first
    bme = body.data
    btree = BVHTree.FromPolygons([Vector(c) for c in co], [tuple(p.vertices) for p in bme.polygons])
    # Coverage test, independent of the (often folded) local normal:
    #  - a vertex with fewer than 4 of 26 ray directions free of the body is interior
    #    geometry (these rigs carry internal anatomy; meshes are not watertight) and is skipped
    #  - an exterior vertex is covered when fabric lies within 15 mm of it in any direction
    # Skin fully under fabric is additionally masked out below, so it cannot render at all.
    dirs = [Vector((x, y, z)).normalized() for x in (-1, 0, 1) for y in (-1, 0, 1)
            for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)]
    for vtx in body.data.vertices:
        gs = [e.group for e in vtx.groups if e.group in want and e.weight > 0.5]
        if not gs:
            continue
        p = Vector(co[vtx.index])
        free = [d for d in dirs if btree.ray_cast(p + d * 0.003, d, 0.6)[0] is None]
        if len(free) < 4:
            continue
        total += 1
        near = min((t.find_nearest(p)[3] or 9.0) for t in trees)
        hit = near <= 0.015
        covered += hit
        n = Vector(no[vtx.index])
        for gname_ in gs:
            c = per.setdefault(names[gname_], [0, 0])
            c[0] += 1
            c[1] += hit
        if not hit:
            miss.append((round(p.x, 3), round(p.y, 3), round(p.z, 3), len(free)))
    report['coverage_by_group'] = {k: [v[0], round(v[1] / v[0], 3)] for k, v in per.items()}
    report['uncovered_sample_pos_normal'] = miss[::max(1, len(miss) // 14)]
    report['cover_groups_found'] = [n for n in cfg.get('cover_groups', []) if n in gidx]
    report['cover_vertices'] = total
    report['covered_fraction'] = round(covered / total, 4) if total else None
    report['coverage_ok'] = bool(total == 0 or covered / total >= cfg.get('min_coverage', 0.98))
    # hide the skin that lies fully under fabric (inset two edge rings from every garment
    # border) so nothing can poke through when the body deforms or is subdivided
    cov = np.zeros(len(co), bool)
    for vtx in body.data.vertices:
        p, n = Vector(co[vtx.index]), Vector(no[vtx.index]).normalized()
        cov[vtx.index] = any(t.ray_cast(p - n * 0.004, n, 0.016)[0] is not None for t in trees)
    ed = np.empty(len(body.data.edges) * 2, dtype=np.int32)
    body.data.edges.foreach_get('vertices', ed)
    ed = ed.reshape(-1, 2)
    inner = cov.copy()
    for _ in range(3):
        bad = ~inner
        nb = np.zeros(len(co), bool)
        nb[ed[bad[ed[:, 1]], 0]] = True
        nb[ed[bad[ed[:, 0]], 1]] = True
        inner &= ~nb
    vg = body.vertex_groups.new(name='KO_under_garment')
    vg.add([int(i) for i in np.nonzero(inner)[0]], 1.0, 'REPLACE')
    mk = body.modifiers.new('KO_under_garment', 'MASK')
    mk.vertex_group = vg.name
    mk.invert_vertex_group = True
    with bpy.context.temp_override(object=body):
        bpy.ops.object.modifier_move_to_index(modifier=mk.name, index=0)
    report['skin_vertices_masked_under_fabric'] = int(inner.sum())
    for md in only_arm:
        md.show_viewport = True
    return report, fitted
