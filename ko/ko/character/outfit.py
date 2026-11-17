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
    objs = append_objects(cfg['file'], [g['object'] for g in cfg['garments']]) if cfg.get('garments') else []
    report = {'crotch_z': round(crotch_z, 3), 'bust_z': round(bust_z, 3), 'garments': []}
    fitted = []
    for ob, g in zip(objs, cfg.get('garments', [])):
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
                            crotch_z - 0.006 + g.get('z_offset', 0.0) + 0.5 * size[2] * sz])
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
            # 'outside' only pushes fabric out of the skin, so fabric already floating stays
            # where it is (a seat that bridges and sags); 'on_surface' pulls every vertex onto
            # the skin at the offset: a skin-tight fit
            md.wrap_mode = 'ON_SURFACE' if g.get('wrap') == 'on_surface' else 'OUTSIDE_SURFACE'
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
        for _ in range(g.get('relax_passes', 1)):   # extra relax/wrap cycles iron out folds
            sm = ob.modifiers.new('relax', 'SMOOTH')
            sm.iterations, sm.factor = g.get('relax', 6), 0.5
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

        if g.get('bridge_cleft') and g['region'] == 'hips':
            pushed = max(pushed, bridge_cleft(me, co, torso, crotch_z, off))
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

    for sg in cfg.get('skin_garments', []):
        ob = skin_garment(arm, body, joints_w, sg, coll, owner, gown, co, no)
        fitted.append(ob)
        report['garments'].append({'object': ob.name, 'region': sg.get('region', 'hips'),
                                   'kind': 'skin_garment', 'vertices': len(ob.data.vertices)})

    # garments that ship with the character, already rigged (owner 2026-11-14: Izzy's own
    # leotard): no fitting, but they face the same coverage gate, on their evaluated shape
    native = [bpy.data.objects[n] for n in cfg.get('native_garments', []) if n in bpy.data.objects]
    for ob in native:
        report['garments'].append({'object': ob.name, 'kind': 'native', 'vertices': len(ob.data.vertices)})

    # coverage gate ------------------------------------------------------------------------
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    trees = []
    for ob in fitted:
        me = ob.data
        vv = [ob.matrix_world @ x.co for x in me.vertices]
        trees.append(BVHTree.FromPolygons(vv, [tuple(p.vertices) for p in me.polygons]))
    for ob in native:
        oe = ob.evaluated_get(dg)
        me = oe.to_mesh()
        vv = [oe.matrix_world @ x.co for x in me.vertices]
        trees.append(BVHTree.FromPolygons(vv, [tuple(p.vertices) for p in me.polygons]))
        oe.to_mesh_clear()
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
    # vertices removed by an active MASK modifier on the body cannot render; the visual check
    # (renders from several angles) confirms the fabric spans that area with no hole
    masked = set()
    for md in body.modifiers:
        if md.type == 'MASK' and md.show_render and md.invert_vertex_group and md.vertex_group in gidx:
            gm = gidx[md.vertex_group]
            masked |= {v.index for v in body.data.vertices if any(e.group == gm and e.weight > 0 for e in v.groups)}
    report['masked_skipped'] = 0
    for vtx in body.data.vertices:
        gs = [e.group for e in vtx.groups if e.group in want and e.weight > 0.5]
        if not gs:
            continue
        if vtx.index in masked:
            report['masked_skipped'] += 1
            continue
        p = Vector(co[vtx.index])
        free = [d for d in dirs if btree.ray_cast(p + d * 0.003, d, 0.6)[0] is None]
        if len(free) < 4:
            continue
        total += 1
        near = min((t.find_nearest(p)[3] or 9.0) for t in trees)
        hit = near <= 0.015
        if not hit:
            # fabric spanning a hollow sits further out but still occludes the skin:
            # covered when every escaping ray passes through fabric within 10 cm
            hit = all(any(t.ray_cast(p + d * 0.003, d, 0.1)[0] is not None for t in trees)
                      for d in free)
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


def bridge_cleft(me, co, torso, crotch_z, off, z_top=0.22, dz=0.01):
    """Fabric stretched over the seat spans the cleft between the glutes like a membrane; a
    nearest-surface wrap instead pulls it into the cleft from both sides and bunches it. Per
    1 cm horizontal slab, fabric behind the body centre that lies inside the convex hull of
    the body's cross-section is moved out onto that hull (plus the fit offset), along the ray
    from the slab centre. Returns the number of fabric vertices moved."""
    from scipy.spatial import ConvexHull
    v = np.array([x.co[:] for x in me.vertices])
    moved = 0
    zs = np.arange(crotch_z, crotch_z + z_top, dz)
    for z0 in zs:
        sel_b = torso & (co[:, 2] >= z0) & (co[:, 2] < z0 + dz)
        pts = co[sel_b][:, :2]
        if len(pts) < 12:
            continue
        hull = ConvexHull(pts)
        poly = pts[hull.vertices]
        c = pts.mean(0)
        idx = np.nonzero((v[:, 2] >= z0) & (v[:, 2] < z0 + dz) & (v[:, 1] > c[1]))[0]
        for i in idx:
            p = v[i, :2]
            d = p - c
            if np.linalg.norm(d) < 1e-6:
                continue
            d = d / np.linalg.norm(d)
            best = None
            for k in range(len(poly)):          # ray / hull-edge intersection
                a, b = poly[k], poly[(k + 1) % len(poly)]
                e = b - a
                den = d[0] * (-e[1]) - d[1] * (-e[0])
                if abs(den) < 1e-12:
                    continue
                w = a - c
                t = (w[0] * (-e[1]) - w[1] * (-e[0])) / den
                u = (d[0] * w[1] - d[1] * w[0]) / den
                if t > 0 and -1e-9 <= u <= 1 + 1e-9:
                    best = t if best is None else min(best, t)
            if best is None:
                continue
            r_hull = best + off
            if np.linalg.norm(p - c) < r_hull:
                v[i, :2] = c + d * r_hull
                moved += 1
    me.vertices.foreach_set('co', v.ravel())
    me.update()
    return moved


def _membrane(bm, sg):
    """Tight fabric is a membrane under tension resting on the body (a one-sided
    constraint): it spans concavities (glute cleft, crotch contour, lumbar hollow) and
    never sinks into them. 1) cap interior holes (every boundary loop except the
    `keep_loops` largest: waist + two leg openings); 2) outward-only Laplacian: a vertex
    moves to its neighbour mean only when that move points along the outward normal."""
    import bmesh
    # boundary loops
    bnd = [e for e in bm.edges if e.is_boundary]
    seen, loops = set(), []
    for e0 in bnd:
        if e0.index in seen:
            continue
        loop, stack = [], [e0]
        seen.add(e0.index)
        while stack:
            e = stack.pop()
            loop.append(e)
            for v in e.verts:
                for f in v.link_edges:
                    if f.is_boundary and f.index not in seen:
                        seen.add(f.index)
                        stack.append(f)
        loops.append(loop)
    loops.sort(key=len, reverse=True)
    for loop in loops[sg.get('keep_loops', 3):]:
        res = bmesh.ops.holes_fill(bm, edges=loop, sides=0)
        if res['faces']:
            bmesh.ops.triangulate(bm, faces=res['faces'])
    bm.normal_update()
    bm.verts.ensure_lookup_table()
    n0 = np.array([v.normal[:] for v in bm.verts])
    P = np.array([v.co[:] for v in bm.verts])
    nb = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
    # 'outward' judged against a heavily smoothed normal field: inside the cleft the
    # raw normals face each other, the smoothed one points out of the cleft
    for _ in range(sg.get('membrane_normal_smooth', 25)):
        n0 = np.array([n0[n].mean(0) if n else n0[i] for i, n in enumerate(nb)])
        n0 /= np.linalg.norm(n0, axis=1, keepdims=True) + 1e-9
    fixed = np.array([v.is_boundary for v in bm.verts]) if sg.get('membrane_fix_hem', True) \
        else np.zeros(len(P), bool)
    f = sg.get('membrane_factor', 0.5)
    for _ in range(int(sg['membrane'])):
        M = np.array([P[n].mean(0) if n else P[i] for i, n in enumerate(nb)])
        d = M - P
        out = (d * n0).sum(1) > 0
        mv = out & ~fixed
        P[mv] += f * d[mv]
    for v, p in zip(bm.verts, P):
        v.co = p


def _bridge_fill(bm, bridge, body, co, no, sg):
    """Fabric spans anatomy instead of following it: delete every garment face touching the
    bridged region (and any interior pieces left floating), fill the hole with new geometry,
    relax it into a smooth spanning surface with the rim fixed, then push any part that dips
    under the skin back out to the fabric offset (nearest-skin test against the body surface
    outside the bridged region). Weights for new vertices are copied from the nearest rim
    vertex by the caller's weight transfer (they keep the deform layer of the rim)."""
    import bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    lay = bm.verts.layers.int.get('ko_src')
    dfl = bm.verts.layers.deform.active
    dead = [f for f in bm.faces if any(v[lay] in bridge for v in f.verts)]
    bmesh.ops.delete(bm, geom=dead, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    # largest connected piece only
    bm.verts.ensure_lookup_table()
    seen, best = set(), []
    for v0 in bm.verts:
        if v0.index in seen:
            continue
        comp, st = [], [v0]
        seen.add(v0.index)
        while st:
            v = st.pop()
            comp.append(v)
            for e in v.link_edges:
                w = e.other_vert(v)
                if w.index not in seen:
                    seen.add(w.index)
                    st.append(w)
        if len(comp) > len(best):
            best = comp
    keep = set(best)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v not in keep], context='VERTS')
    # boundary loops; the hole is the loop nearest the bridged region's centre
    Minv = body.matrix_world.inverted()
    bpts = np.array([co[i] for i in bridge])
    centre = Minv @ Vector(bpts.mean(0).tolist())
    bedges = [e for e in bm.edges if e.is_boundary]
    loops, used = [], set()
    for e0 in bedges:
        if e0 in used:
            continue
        loop, st = [], [e0]
        used.add(e0)
        while st:
            e = st.pop()
            loop.append(e)
            for v in e.verts:
                for e2 in v.link_edges:
                    if e2.is_boundary and e2 not in used:
                        used.add(e2)
                        st.append(e2)
        loops.append(loop)
    def dist(loop):
        pts = [v.co for e in loop for v in e.verts]
        return (sum(pts, Vector()) / len(pts) - centre).length
    hole = [l for l in loops if dist(l) < 0.06] or [min(loops, key=dist)]
    rim = {v for l in hole for e in l for v in e.verts}
    before = set(bm.faces)
    bmesh.ops.holes_fill(bm, edges=[e for l in hole for e in l], sides=0)
    new_faces = [f for f in bm.faces if f not in before]
    bmesh.ops.triangulate(bm, faces=new_faces, quad_method='BEAUTY', ngon_method='BEAUTY')
    new_faces = [f for f in bm.faces if f not in before]
    for _ in range(sg.get('bridge_subdiv', 3)):
        nf_ = set(new_faces)
        inner = list({e for f in new_faces for e in f.edges if all(g in nf_ for g in e.link_faces)})
        bmesh.ops.subdivide_edges(bm, edges=inner, cuts=1, use_grid_fill=True)
        new_faces = [f for f in bm.faces if f not in before]
        bmesh.ops.triangulate(bm, faces=new_faces, quad_method='BEAUTY', ngon_method='BEAUTY')
        new_faces = [f for f in bm.faces if f not in before]
    old_v = {v for f in before if f.is_valid for v in f.verts}
    rim = [v for v in {v for f in new_faces for v in f.verts} if v in old_v]
    fill_v = [v for v in {v for f in new_faces for v in f.verts} if v not in old_v]
    # harmonic relax (rim fixed), vectorised
    bm.verts.ensure_lookup_table()
    idx = {v: i for i, v in enumerate(bm.verts)}
    P = np.array([v.co[:] for v in bm.verts])
    F = [idx[v] for v in fill_v]
    nbr = [[idx[e.other_vert(v)] for e in v.link_edges] for v in fill_v]
    for _ in range(sg.get('bridge_iters', 600)):
        P[F] = np.array([P[n].mean(0) for n in nbr])
    # keep the fabric outside the skin: nearest body point outside the bridged region
    bme = body.data
    ok = np.ones(len(co), bool)
    ok[list(bridge)] = False
    loc_co = np.array([(Minv @ Vector(c.tolist()))[:] for c in co])
    faces = [tuple(p.vertices) for p in bme.polygons if all(ok[i] for i in p.vertices)]
    tree = BVHTree.FromPolygons([Vector(c) for c in loc_co], faces)
    off = 0.0006                 # only stop it sinking in; the Displace modifier adds the offset
    for i in F:
        q = Vector(P[i].tolist())
        hit, nrm, _, d = tree.find_nearest(q)
        if hit is not None and (q - hit).dot(nrm) < off:
            P[i] = (hit + nrm * off)[:]
    for v in fill_v:
        v.co = P[idx[v]]
    # blend the seam: relax two rings of the original fabric around the rim toward the fill
    band = set(rim)
    for _ in range(2):
        band |= {e.other_vert(v) for v in list(band) for e in v.link_edges}
    band = [v for v in band if v not in set(fill_v) and not v.is_boundary]
    for _ in range(sg.get('seam_relax', 0)):
        bmesh.ops.smooth_vert(bm, verts=band, factor=0.5, use_axis_x=True, use_axis_y=True,
                              use_axis_z=True)
    for v in fill_v:
        if dfl is not None:
            # weights from the nearest rim vertex
            r = min(rim, key=lambda w: (w.co - v.co).length_squared)
            v[dfl].clear()
            for k_, w_ in r[dfl].items():
                v[dfl][k_] = w_
        v[lay] = -1


def skin_garment(arm, body, joints_w, sg, coll, owner, gown, co, no):
    """A skin-tight garment cut from the body surface itself: the body faces inside a
    briefs-shaped region are copied, pushed out along the skin normal by `offset`, given a
    fabric thickness, and keep the body's own skin weights (same vertices), so the fabric
    follows every pose exactly and can never sag away from the skin.
    Region (hips): faces whose vertices are owned by the pelvis body, below the waistline
    (pelvis joint + `waist` m) and above the leg line, which rises from the crotch toward the
    hip bone by `leg_cut` (0 = full brief, 1 = high-cut bikini)."""
    import bmesh
    pel = joints_w['pelvis']
    hipL, hipR = joints_w.get('thigh_L'), joints_w.get('thigh_R')
    z_waist = pel.z + sg.get('waist', 0.05)
    hip_x = abs(hipL.x - pel.x) if hipL is not None else 0.09
    me = body.data
    own = np.empty(len(me.vertices), dtype=object)
    for vtx in me.vertices:
        acc = {}
        for e in vtx.groups:
            o = gown.get(e.group)
            if o:
                acc[o] = acc.get(o, 0.0) + e.weight
        own[vtx.index] = max(acc, key=acc.get) if acc else None
    hip_z = hipL.z if hipL is not None else pel.z - 0.05
    crotch = min(co[(own == 'pelvis')][:, 2]) if (own == 'pelvis').any() else hip_z - 0.1
    cut = sg.get('leg_cut', 0.4)
    back_y = pel.y
    def inside(i):
        p = co[i]
        if own[i] is None or own[i].startswith(('upper_arm', 'forearm', 'hand', 'shin', 'foot',
                                                 'chest', 'neck', 'head')):
            return False
        if p[2] > z_waist:
            return False
        r = min(1.0, abs(p[0] - pel.x) / max(hip_x * 1.5, 1e-3))
        if p[1] < back_y:                            # front: diagonal cut toward the hip bone
            z_leg = crotch + (hip_z + 0.02 - crotch) * cut * r ** 1.5
        else:                                        # back: follows the glute fold
            z_leg = crotch - 0.012 + (hip_z - crotch) * 0.35 * cut * r ** 2
        return p[2] >= z_leg
    keep = np.array([inside(i) for i in range(len(me.vertices))])
    import os as _os
    if _os.environ.get('KO_DEBUG_OUTFIT'):
        gi_ = {vg.name: vg.index for vg in body.vertex_groups}
        if 'KO_crotch_outer' in gi_:
            ids = [v.index for v in me.vertices if any(e.group == gi_['KO_crotch_outer'] for e in v.groups)]
            from collections import Counter
            print('[dbg] crotch_outer', len(ids), 'keep', int(keep[ids].sum()),
                  'owners', Counter(str(own[i]) for i in ids), 'z_waist', round(z_waist, 3),
                  'crotch', round(float(crotch), 3), 'hip_z', round(float(hip_z), 3), 'pel', [round(float(c), 3) for c in pel])
            bad = [i for i in ids if not keep[i]][:8]
            print('[dbg] not kept sample', [(i, [round(float(c), 3) for c in co[i]], str(own[i])) for i in bad])
    # anatomy the fabric must bridge, not follow: dropped here, the hole is filled flat below
    bridge = set()
    gi = {vg.name: vg.index for vg in body.vertex_groups}
    for gname in sg.get('bridge_groups', []):
        if gname in gi:
            for vtx in me.vertices:
                if any(e.group == gi[gname] and e.weight > 0.3 for e in vtx.groups):
                    bridge.add(vtx.index)
    # bridged vertices stay in the cut (they are inside the brief) and are smoothed flat below
    faces_keep = [p.index for p in me.polygons if all(keep[v] for v in p.vertices)]
    bm = bmesh.new()
    bm.from_mesh(me)
    lay = bm.verts.layers.int.new('ko_src')
    # start from the skin as it renders (active shape keys / body morphs), not the basis
    # coordinates: Daz bodies carry morphs that move the skin by centimetres (Izzy, 2026-11-12)
    Minv = np.array(body.matrix_world.inverted())
    if len(co) == len(bm.verts):
        loc = co @ Minv[:3, :3].T + Minv[:3, 3]
        for v in bm.verts:
            v.co = loc[v.index]
    for v in bm.verts:
        v[lay] = v.index
    bm.faces.ensure_lookup_table()
    drop = set(range(len(bm.faces))) - set(faces_keep)
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in drop], context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    # keep only the largest connected piece (stray interior geometry)
    bm.verts.ensure_lookup_table()
    seen, best = set(), []
    for v0 in bm.verts:
        if v0.index in seen:
            continue
        comp, stack = [], [v0]
        seen.add(v0.index)
        while stack:
            v = stack.pop()
            comp.append(v)
            for e in v.link_edges:
                w = e.other_vert(v)
                if w.index not in seen:
                    seen.add(w.index)
                    stack.append(w)
        if len(comp) > len(best):
            best = comp
    keepv = {v.index for v in best}
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.index not in keepv], context='VERTS')
    if sg.get('membrane', 0) > 0:
        _membrane(bm, sg)
    if bridge and sg.get('bridge_mode') == 'fill':
        _bridge_fill(bm, bridge, body, co, no, sg)
    elif bridge:
        lay = bm.verts.layers.int.get('ko_src')
        bv = [v for v in bm.verts if v[lay] in bridge]
        ring = {w for v in bv for e in v.link_edges for w in (e.other_vert(v),)} | set(bv)
        for _ in range(sg.get('bridge_relax', 60)):
            bmesh.ops.smooth_vert(bm, verts=list(ring), factor=0.8, use_axis_x=True,
                                  use_axis_y=True, use_axis_z=True)
        # smoothing pulls a concave patch inward; lift it back to the convex hull of its rim
        rim = [w for w in ring if w not in set(bv)]
        if rim:
            import numpy as _np
            rimp = _np.array([w.co[:] for w in rim])
            front = rimp[:, 1].min()
            for v in bv:
                if v.co.y > front:
                    v.co.y = front
    # hems: relax the stair-stepped boundary loops along themselves
    for _ in range(sg.get('hem_relax', 12)):
        bv = [v for v in bm.verts if v.is_boundary]
        bmesh.ops.smooth_vert(bm, verts=bv, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    # smoothing collapses some bridged faces to zero area; Solidify's even offset
    # divides by their angles and throws spikes metres out. Merge and dissolve them.
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=sg.get('merge_dist', 0.0008))
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=sg.get('merge_dist', 0.0008))
    nm = bpy.data.meshes.new(sg.get('name', 'KO_briefs'))
    bm.to_mesh(nm)
    bm.free()
    ob = bpy.data.objects.new(sg.get('name', 'KO_briefs'), nm)
    coll.objects.link(ob)
    ob.matrix_world = body.matrix_world.copy()
    for vg in body.vertex_groups:
        ob.vertex_groups.new(name=vg.name)
    # vertex groups came across with the mesh data (deform weights live on the mesh)
    bones = {b.name for b in arm.data.bones}
    for vg in list(ob.vertex_groups):
        if vg.name not in bones:
            ob.vertex_groups.remove(vg)
    nm.materials.clear()
    m = bpy.data.materials.new(sg.get('name', 'KO_briefs') + '_mat')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*sg.get('color', (0.012, 0.012, 0.014)), 1)
    b.inputs['Roughness'].default_value = 0.55
    b.inputs['Sheen Weight'].default_value = sg.get('sheen', 0.12)
    b.inputs['Sheen Roughness'].default_value = 0.3
    nm.materials.append(m)
    for p in nm.polygons:
        p.material_index = 0
    # stack: Armature -> CorrectiveSmooth (must see the 1:1 base mesh, else its rest
    # vertex count mismatches and it spikes) -> Displace -> Subsurf -> Solidify
    sm = ob.modifiers.new('hem', 'CORRECTIVE_SMOOTH')
    sm.iterations = 4
    sm.rest_source = 'ORCO'
    # push out along the skin normal, then give the fabric thickness (outward)
    disp = ob.modifiers.new('offset', 'DISPLACE')
    disp.direction = 'NORMAL'
    disp.mid_level = 0.0
    disp.strength = sg.get('offset', 0.0025)
    ss = ob.modifiers.new('smooth_surface', 'SUBSURF')
    ss.levels = ss.render_levels = 1
    sol = ob.modifiers.new('thickness', 'SOLIDIFY')
    sol.thickness = sg.get('thickness', 0.0015)
    sol.offset = 1.0
    sol.use_even_offset = False
    am = ob.modifiers.new('Armature', 'ARMATURE')
    am.object = arm
    with bpy.context.temp_override(object=ob):
        bpy.ops.object.modifier_move_to_index(modifier='Armature', index=0)
    ob.parent = body.parent
    if body.parent is not None:
        ob.matrix_parent_inverse = body.matrix_parent_inverse.copy()
    return ob
