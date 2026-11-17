"""Strike props: the only parts of the opponent ever rendered (house rule: glove only).

Local frame of every prop: +Z is the striking face's outward normal (the direction of travel),
the striking face sits on the origin, +Y is 'up' for the prop. So placing the origin on the
strike point at the hit frame puts the prop in contact with her, which is what an impact frame
needs. All dimensions are approximate (an MMA 4 oz glove; a typical sock-style shin guard).
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector


def _mat(name, rgb, rough=0.45, sheen=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1.0)
    b.inputs['Roughness'].default_value = rough
    if sheen:
        b.inputs['Sheen Weight'].default_value = sheen
    return m


def _rounded_box(bm, size, center, bevel, segs=4):
    r = bmesh.ops.create_cube(bm, size=1.0)
    vs = r['verts']
    bmesh.ops.scale(bm, vec=Vector(size), verts=vs)
    bmesh.ops.translate(bm, vec=Vector(center), verts=vs)
    es = list({e for v in vs for e in v.link_edges})
    bmesh.ops.bevel(bm, geom=vs + es, offset=bevel, segments=segs, affect='EDGES', profile=0.5)
    return vs


def _cyl(bm, radius, depth, center, axis='Z', segs=24, caps=True, radius2=None):
    r = bmesh.ops.create_cone(bm, cap_ends=caps, segments=segs, radius1=radius,
                              radius2=radius if radius2 is None else radius2, depth=depth)
    vs = r['verts']
    if axis == 'X':
        bmesh.ops.rotate(bm, verts=vs, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'Y'))
    bmesh.ops.translate(bm, vec=Vector(center), verts=vs)
    return vs


def _obj(name, parts, coll):
    """parts: [(bmesh builder fn, material)]: one object, one material slot per part."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    mats = []
    for k, (fn, mat) in enumerate(parts):
        before = set(bm.faces)
        fn(bm)
        for f in set(bm.faces) - before:
            f.material_index = k
            f.smooth = True
        mats.append(mat)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    sd = ob.modifiers.new('round', 'SUBSURF')
    sd.levels = sd.render_levels = 1
    return ob


def make_glove(name, coll):
    """MMA glove, closed fist, knuckles forward (+Z), back of the hand up (+Y)."""
    red = _mat('KO_prop_glove', (0.32, 0.012, 0.014), 0.38, 0.2)
    blk = _mat('KO_prop_black', (0.015, 0.015, 0.017), 0.5)
    wht = _mat('KO_prop_strap', (0.82, 0.82, 0.80), 0.55)
    return _obj(name, [
        (lambda bm: _rounded_box(bm, (0.092, 0.078, 0.095), (0, 0.004, -0.0475), 0.024), red),   # fist + padding
        (lambda bm: _rounded_box(bm, (0.026, 0.03, 0.06), (-0.052, -0.018, -0.055), 0.011), red),  # thumb
        (lambda bm: _cyl(bm, 0.041, 0.075, (0, 0, -0.13)), blk),                                   # cuff
        (lambda bm: _cyl(bm, 0.044, 0.026, (0, 0, -0.118)), wht),                                  # wrist strap
    ], coll)


def make_shin_guard(name, coll):
    """Shin guard: curved shell along the shin (local X, knee at -X, foot at +X), striking face
    +Z, instep pad at the foot end, two straps."""
    shell = _mat('KO_prop_shin', (0.03, 0.03, 0.035), 0.42)
    trim = _mat('KO_prop_glove', (0.32, 0.012, 0.014), 0.38, 0.2)
    strap = _mat('KO_prop_black', (0.015, 0.015, 0.017), 0.5)

    def shell_fn(bm, r=0.058, L=0.32, arc=110, th=0.014, nu=20, nv=10):
        rows = []
        for i in range(nv + 1):
            x = -L / 2 + L * i / nv
            row = []
            for j in range(nu + 1):
                a = math.radians(-arc + 2 * arc * j / nu)
                bulge = 1.0 + 0.08 * math.cos(math.pi * (x / L))      # fuller mid-shin
                row.append(bm.verts.new((x, r * bulge * math.sin(a), r * bulge * (math.cos(a) - 1.0))))
            rows.append(row)
        outer = []
        for i in range(nv):
            for j in range(nu):
                outer.append(bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j])))
        bmesh.ops.solidify(bm, geom=outer, thickness=th)

    def instep(bm):
        _rounded_box(bm, (0.10, 0.085, 0.032), (0.215, 0.0, -0.022), 0.012)

    def straps(bm):
        for x in (-0.085, 0.085):
            _cyl(bm, 0.062, 0.03, (x, 0.0, -0.058), axis='X')

    return _obj(name, [(shell_fn, shell), (instep, trim), (straps, strap)], coll)


def _ellipsoid(bm, size, center, segs=24, rings=14):
    r = bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=0.5)
    vs = r['verts']
    bmesh.ops.scale(bm, vec=Vector(size), verts=vs)
    bmesh.ops.translate(bm, vec=Vector(center), verts=vs)
    return vs


def _bend_x(vs, radius):
    """Wrap verts around the Y axis: x becomes arc length on a circle of `radius` whose centre
    sits behind the face (-Z), so a flat pad curves round the fist."""
    for v in vs:
        x, y, z = v.co
        a = x / radius
        r = radius + z
        v.co = Vector((r * math.sin(a), y, r * math.cos(a) - radius))


def _fused(builders, voxel, smooth_iters=8):
    """Build several overlapping primitives, voxel-remesh them into one smooth closed surface
    and return a new bmesh (one organic shell instead of stacked blobs)."""
    me = bpy.data.meshes.new('_tmp')
    bm = bmesh.new()
    for fn in builders:
        fn(bm)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('_tmp', me)
    bpy.context.scene.collection.objects.link(ob)
    rm = ob.modifiers.new('rm', 'REMESH')
    rm.mode = 'VOXEL'
    rm.voxel_size = voxel
    sm = ob.modifiers.new('sm', 'SMOOTH')
    sm.factor = 0.6
    sm.iterations = smooth_iters
    dg = bpy.context.evaluated_depsgraph_get()
    out = bmesh.new()
    out.from_mesh(ob.evaluated_get(dg).to_mesh())
    ob.evaluated_get(dg).to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    return out


def make_mma_glove(name, coll):
    """4 oz MMA glove, closed fist, knuckles forward (+Z), back of the hand up (+Y): one fused
    leather shell (knuckle pad, back-of-hand padding, thumb), curled fingers on the palm side,
    a flat wrist wrap with white hems. Black leather, red wrap. Original design; sizes
    approximate."""
    blk = _mat('KO_mma_leather', (0.014, 0.014, 0.016), 0.30, 0.0)
    liner = _mat('KO_mma_liner', (0.045, 0.045, 0.05), 0.8)
    red = _mat('KO_mma_strap', (0.32, 0.012, 0.014), 0.45)
    wht = _mat('KO_mma_piping', (0.82, 0.82, 0.80), 0.5)
    shell = _fused([
        lambda bm: _ellipsoid(bm, (0.088, 0.074, 0.096), (0, -0.002, -0.054), 28, 16),   # fist
        lambda bm: _ellipsoid(bm, (0.098, 0.056, 0.050), (0, 0.010, -0.024), 32, 18),   # knuckle pad
        lambda bm: _ellipsoid(bm, (0.088, 0.036, 0.090), (0, 0.030, -0.062), 28, 14),   # back pad
        lambda bm: _ellipsoid(bm, (0.026, 0.030, 0.060), (-0.046, -0.012, -0.054), 16, 10),  # thumb
        lambda bm: _ellipsoid(bm, (0.066, 0.056, 0.060), (0, 0.000, -0.105), 20, 12),   # wrist taper
    ], 0.0028)
    fing = _fused([lambda bm, x=x: _ellipsoid(bm, (0.020, 0.024, 0.026), (x, -0.033, -0.024), 14, 9)
                   for x in (-0.027, -0.009, 0.009, 0.027)], 0.0018, 4)

    def add(bm_src):
        return lambda bm: bm_src.to_mesh(_tmp_me) or bm.from_mesh(_tmp_me)

    _tmp_me = bpy.data.meshes.new('_tmp2')

    def put(src):
        def f(bm):
            src.to_mesh(_tmp_me)
            bm.from_mesh(_tmp_me)
        return f

    def wrap(bm):                               # flat wrist wrap: open tube, slight taper
        _cyl(bm, 0.036, 0.060, (0, -0.002, -0.140), segs=48, caps=False, radius2=0.033)

    def hems(bm):
        for zc, r in ((-0.111, 0.0364), (-0.169, 0.0334)):
            _cyl(bm, r, 0.006, (0, -0.002, zc), segs=48, caps=False)

    def cap(bm):                                # closes the cut end of the wrap
        _cyl(bm, 0.0325, 0.004, (0, -0.002, -0.168), segs=48)

    ob = _obj(name, [(put(shell), blk), (put(fing), liner), (wrap, red), (hems, wht), (cap, liner)], coll)
    shell.free()
    fing.free()
    bpy.data.meshes.remove(_tmp_me)
    ob.modifiers['round'].levels = ob.modifiers['round'].render_levels = 1
    return ob


PROPS = {'glove': make_mma_glove, 'glove_box': make_glove, 'mma_glove': make_mma_glove, 'shin': make_shin_guard}
