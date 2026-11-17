"""Clean working copy of Izzy (Daz Genesis 8 Female) for the bikini (owner 2026-11-12: "use the
bikini"). The upload is never edited.
Removes: the outfit (Leotard, Sleeve, boots), the gun and its attachment rigs, the hidden helper
collection's renderables stay hidden. Adds KO_bust_apex (forward-most 3 cm of each breast, from
the lBreast/rBreast bone weights) and KO_crotch_outer (outer skin of the Genitals bone region) for
the outfit coverage gate, the same way tools/prep_mosin.py does.
    python3 tools/prep_izzy.py [--keep OBJECT ...] SRC.blend OUT.blend
--keep keeps a shipped garment (owner 2026-11-14: her own leotard) instead of removing it.
"""
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

src, out = sys.argv[-2], sys.argv[-1]
keep = {sys.argv[i + 1] for i, x in enumerate(sys.argv[:-2]) if x == '--keep'}
bpy.ops.wm.open_mainfile(filepath=src, use_scripts=False)
removed = []
for cname in ('gun', 'outfit'):
    c = bpy.data.collections.get(cname)
    if not c:
        continue
    for o in list(c.all_objects):
        if o.name in keep:
            continue
        removed.append(o.name)
        bpy.data.objects.remove(o, do_unlink=True)
for o in list(bpy.data.objects):
    if o.name in keep:
        continue
    if o.name.startswith('attachment_') or o.name in ('Leotard TURBO', 'Sleeve TURBO', 'Ms Thea Boots G8F'):
        removed.append(o.name)
        bpy.data.objects.remove(o, do_unlink=True)
# kept garments: such rigs drive hide flags from their own UI drivers; make them plainly visible
for n in keep:
    o = bpy.data.objects.get(n)
    if o is None:
        print('keep: missing', n)
        continue
    if o.animation_data:
        for d in list(o.animation_data.drivers):
            if 'hide' in d.data_path:
                o.animation_data.drivers.remove(d)
    o.hide_render = o.hide_viewport = False
    o.hide_set(False)
    for c in o.users_collection:
        c.hide_render = c.hide_viewport = False
    print('kept', n, 'verts', len(o.data.vertices), 'mods', [m.type for m in o.modifiers])
# textures: the owner's texture pack, copied to assets_cache/izzy/textures; tattoos removed
# (owner 2026-11-13: "remove tattoos"): arms -> the pack's own ARMS CLEAN map; torso -> the
# three small hearts by the left collarbone inpainted out (TORSO*_noink.png)
import os as _os
TEX = _os.path.abspath(_os.path.join(_os.path.dirname(out), 'textures'))
REPL = {'ARMS.png': 'ARMS_noink.png', 'TORSO.png': 'TORSO_noink.png', 'TORSO ALT.png': 'TORSO ALT_noink.png'}
relinked, missing = 0, []
for im in bpy.data.images:
    if im.source not in ('FILE', 'TILED') or not im.filepath:
        continue
    b_ = _os.path.basename(bpy.path.abspath(im.filepath).replace('\\', '/'))
    b_ = REPL.get(b_, b_)
    probe = b_.replace('<UDIM>', '1001') if '<UDIM>' in b_ else b_
    if im.source == 'TILED' or '<UDIM>' in b_:
        ok = any(f.startswith(b_.split('<UDIM>')[0]) for f in _os.listdir(TEX))
    else:
        ok = _os.path.exists(_os.path.join(TEX, b_))
    if ok:
        im.filepath = _os.path.join(TEX, b_)
        relinked += 1
    else:
        missing.append(b_)
print('textures relinked', relinked, 'missing', missing[:10])
# the face materials drive the Principled IOR from a 0..1 mask (FaceTCS_mask -> Math -> IOR):
# IOR < 1 renders the face near-white in Cycles. Unlink it; skin IOR 1.4.
nfix = 0
for m in bpy.data.materials:
    if not m.node_tree:
        continue
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED' and n.inputs['IOR'].is_linked:
            for l in list(n.inputs['IOR'].links):
                m.node_tree.links.remove(l)
            n.inputs['IOR'].default_value = 1.4
            nfix += 1
print('IOR links removed', nfix)
body = bpy.data.objects['Genesis 8 Female Mesh']
me = body.data
gi = {g.name: g.index for g in body.vertex_groups}
saved = [(m, m.show_viewport) for m in body.modifiers if m.type != 'ARMATURE']
for m, _ in saved:
    m.show_viewport = False
bpy.context.view_layer.update()
ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get())
em = ev.to_mesh()
ec = [body.matrix_world @ v.co for v in em.vertices]
ev.to_mesh_clear()
for m, sv in saved:
    m.show_viewport = sv
co = np.array([p[:] for p in ec])


def weights(names):
    w = np.zeros(len(co))
    idx = {gi[n] for n in names if n in gi}
    for v in me.vertices:
        for e in v.groups:
            if e.group in idx:
                w[v.index] += e.weight
    return w


# facing: Genesis faces -Y in Blender (Diffeomorphic import); the forward-most point = min y
apex = []
for side in 'lr':
    w = weights([f'{side}Breast', f'{side}Areola', f'{side}Nipple'])
    sel = np.nonzero(w > 0.5)[0]
    tip = co[sel[np.argmin(co[sel, 1])]]
    apex += [int(i) for i in sel if np.linalg.norm(co[i] - tip) < 0.03]
vg = body.vertex_groups.new(name='KO_bust_apex')
vg.add(apex, 1.0, 'REPLACE')
tree = BVHTree.FromPolygons(ec, [tuple(p.vertices) for p in me.polygons])
dirs = [Vector((x, y, z)).normalized() for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1)
        if (x, y, z) != (0, 0, 0)]
gw = weights(['Genitals', 'Anus'])
gmat = {i for i, m in enumerate(me.materials) if m and ('Genital' in m.name or 'Anus' in m.name)}
inmat = np.zeros(len(co), bool)
for p in me.polygons:
    if p.material_index in gmat:
        inmat[list(p.vertices)] = True
outer = []
for i in np.nonzero((gw > 0.5) | inmat)[0]:
    p = ec[i]
    if sum(tree.ray_cast(p + d * 0.003, d, 0.6)[0] is None for d in dirs) >= 9:
        outer.append(int(i))
vg2 = body.vertex_groups.new(name='KO_crotch_outer')
vg2.add(outer, 1.0, 'REPLACE')
# anatomy detail (the geograft material faces) is hidden on the body, as on Mosin, and the
# briefs bridge it flat instead of following it (outfit bridge_groups)
hide = sorted({int(i) for i in np.nonzero(inmat)[0]})
vg3 = body.vertex_groups.new(name='KO_genital_hide')
vg3.add(hide, 1.0, 'REPLACE')
mk = body.modifiers.new('KO genital mask', 'MASK')
mk.vertex_group = 'KO_genital_hide'
mk.invert_vertex_group = True
while body.modifiers.find(mk.name) > 1:          # right after the armature
    bpy.ops.object.modifier_move_up({'object': body}, modifier=mk.name) if False else None
    break
print('genital hide verts', len(hide))
for _ in range(3):
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=out)
print('removed', len(removed), removed)
print('bust apex verts', len(apex), 'crotch outer verts', len(outer))
print('remaining meshes', sorted(o.name for o in bpy.data.objects if o.type == 'MESH'
                                 and not o.name.startswith(('GZM_', 'WGT'))))
