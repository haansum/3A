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


def _group(floor_z, band, bulge):
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
    selfo = N.new('GeometryNodeSelfObject')
    oi = N.new('GeometryNodeObjectInfo')
    oi.transform_space = 'ORIGINAL'
    L.new(selfo.outputs[0], oi.inputs['Object'])
    M = oi.outputs['Transform']
    inv = N.new('FunctionNodeInvertMatrix')
    L.new(M, inv.inputs[0])

    tp = N.new('FunctionNodeTransformPoint')            # local -> world
    L.new(pos, tp.inputs['Vector'])
    L.new(M, tp.inputs['Transform'])
    wp = tp.outputs[0]
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(wp, sep.inputs[0])
    z = sep.outputs['Z']

    d = math('SUBTRACT', z, floor_z)
    soft = math('ADD', math('MULTIPLY', math('EXPONENT', math('DIVIDE', math('SUBTRACT', d, band), band)), band), floor_z)
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
    L.new(inv.outputs[0], back.inputs['Transform'])
    sp = N.new('GeometryNodeSetPosition')
    L.new(gi.outputs[0], sp.inputs['Geometry'])
    L.new(back.outputs[0], sp.inputs['Position'])
    L.new(sp.outputs[0], go.inputs[0])
    return ng


def apply(floor_z, band=0.008, bulge=0.25, sink=0.0015, objects=None):
    """Add the deformer to every visible armature-deformed mesh. -> names of the meshes changed."""
    ng = _group(floor_z - sink, band, bulge)
    done = []
    for ob in objects if objects is not None else bpy.data.objects:
        if ob.type != 'MESH' or ob.hide_render:
            continue
        if not any(m.type == 'ARMATURE' for m in ob.modifiers):
            continue
        md = ob.modifiers.new('KO_canvas_flatten', 'NODES')
        md.node_group = ng
        done.append(ob.name)
    return done
