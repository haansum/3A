"""Canvas flattening deformer (handoff R7 / E4a, owner 2026-11-17).

The sim body is rigid hulls, so a cheek, hip or shoulder resting on the canvas meets it at a
point and the render mesh either floats on that point or sinks through. Soft tissue flattens
instead. This adds a Geometry Nodes modifier, last in the stack, to every armature-deformed
mesh (skin, clothes, hair) that applies a smooth soft clamp to world height:

    d = z - floor
    z' = z                                 for d >= band
    z' = floor + band * exp((d - band) / band)   for d <  band

The clamp is C1 at d = band (value and slope match), monotone (layer order is kept, so clothing
stays outside skin), and never reaches below the floor: a vertex the rigid hull pushed 1 cm under
the canvas ends up a fraction of a mm above it, packed into a thin flat layer. That packed layer is
the visible flat contact patch. An optional sideways bulge pushes the compressed vertices outward
along their horizontal normal, in proportion to how far they were lifted.

Any such clamp packs the lowest vertices into a layer of thickness ~0.37 band above the floor, which
would read as the body hovering ~3 mm over the canvas. `sink` lowers the clamp's floor by that much
(default 1.5 mm), so the packed layer straddles the canvas surface the way a real contact patch does.

Tuned by eye, not measured: band (default 8 mm), sink (1.5 mm), bulge (0.25). Floor is the sim
canvas, mapped to world by the canonical root."""
import bpy


def _matrix(N, M):
    """constant 4x4 (mathutils Matrix) as a Combine Matrix node; inputs are column-major"""
    n = N.new('FunctionNodeCombineMatrix')
    for c in range(4):
        for r in range(4):
            n.inputs[c * 4 + r].default_value = M[r][c]
    return n.outputs[0]


def _group(floor_z, band, bulge, M):
    # M: the object's world matrix, as a constant. An earlier version read it live through Self
    # Object -> Object Info; that made every mesh depend on itself and cost ~7.5 min of scene sync
    # per frame on the standing frames (measured 2026-11-17: frame 17 463 s with it, 8 s without)
    ng = bpy.data.node_groups.new('KO_canvas_flatten', 'GeometryNodeTree')
    ng.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')

    def math(op, a, b=None):
        n = N.new('ShaderNodeMath')
        n.operation = op
        for k, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[k].default_value = float(v)
            else:
                L.new(v, n.inputs[k])
        return n.outputs[0]

    pos = N.new('GeometryNodeInputPosition').outputs[0]
    nrm = N.new('GeometryNodeInputNormal').outputs[0]
    Mi = M.inverted()
    M = _matrix(N, M)
    inv = _matrix(N, Mi)

    tp = N.new('FunctionNodeTransformPoint')            # local -> world
    L.new(pos, tp.inputs['Vector'])
    L.new(M, tp.inputs['Transform'])
    wp = tp.outputs[0]
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(wp, sep.inputs[0])
    z = sep.outputs['Z']

    d = math('SUBTRACT', z, floor_z)
    # exponent clamped to <= 0: outside the band it is unused, but unclamped it overflowed float32
    # for anything > ~0.7 m up (exp(212) = inf when standing), inf * 0 in the mix gave NaN vertex
    # positions, and Cycles spent ~8 min a frame building its BVH from them (2026-11-17)
    soft = math('ADD', math('MULTIPLY', math('EXPONENT', math('MINIMUM', math('DIVIDE', math('SUBTRACT', d, band), band), 0.0)), band), floor_z)
    below = math('LESS_THAN', d, band)                  # 1 inside the band
    znew = N.new('ShaderNodeMix')                        # float mix: below ? soft : z
    znew.data_type = 'FLOAT'
    L.new(below, znew.inputs['Factor'])
    L.new(z, znew.inputs['A'])
    L.new(soft, znew.inputs['B'])
    zn = znew.outputs['Result']
    lift = math('SUBTRACT', zn, z)                       # >= 0

    # sideways bulge: horizontal part of the world normal, scaled by the lift
    td = N.new('FunctionNodeTransformDirection')
    L.new(nrm, td.inputs['Direction'])
    L.new(M, td.inputs['Transform'])
    sn = N.new('ShaderNodeSeparateXYZ')
    L.new(td.outputs[0], sn.inputs[0])
    k = math('MULTIPLY', lift, bulge)
    comb = N.new('ShaderNodeCombineXYZ')
    L.new(math('ADD', sep.outputs['X'], math('MULTIPLY', sn.outputs['X'], k)), comb.inputs['X'])
    L.new(math('ADD', sep.outputs['Y'], math('MULTIPLY', sn.outputs['Y'], k)), comb.inputs['Y'])
    L.new(zn, comb.inputs['Z'])

    back = N.new('FunctionNodeTransformPoint')          # world -> local
    L.new(comb.outputs[0], back.inputs['Vector'])
    L.new(inv, back.inputs['Transform'])
    sp = N.new('GeometryNodeSetPosition')
    L.new(gi.outputs[0], sp.inputs['Geometry'])
    L.new(back.outputs[0], sp.inputs['Position'])
    L.new(sp.outputs[0], go.inputs[0])
    return ng


def apply(floor_z, band=0.008, bulge=0.25, sink=0.0015, objects=None):
    """Add the deformer to every visible armature-deformed mesh. -> names of the meshes changed.
    Each mesh gets its own group holding its world matrix, which must not change over the take
    (rigged meshes move by their bones, not their object transform): checked at the first and
    last frame, and a moving mesh is skipped with a message rather than flattened wrongly."""
    sc = bpy.context.scene
    f_now = sc.frame_current
    obs = [ob for ob in (objects if objects is not None else bpy.data.objects)
           if ob.type == 'MESH' and not ob.hide_render and any(m.type == 'ARMATURE' for m in ob.modifiers)]
    sc.frame_set(sc.frame_start)
    m0 = {ob.name: ob.matrix_world.copy() for ob in obs}
    sc.frame_set(sc.frame_end)
    m1 = {ob.name: ob.matrix_world.copy() for ob in obs}
    sc.frame_set(f_now)
    done = []
    for ob in obs:
        a_, b_ = m0[ob.name], m1[ob.name]
        if max(abs(a_[r][c] - b_[r][c]) for r in range(4) for c in range(4)) > 1e-6:
            print(f'[flatten] {ob.name}: object transform is animated, not flattened')
            continue
        md = ob.modifiers.new('KO_canvas_flatten', 'NODES')
        md.node_group = _group(floor_z - sink, band, bulge, a_)
        done.append(ob.name)
    return done
