"""Make a cleaned working copy of Mosin's rig file (the upload is never edited).
Removes: both outfits (Default, Siberian slide), the rifle prop, demo camera/light, the Rigify
metarig. Turns off the body masks that hid skin under the removed outfit, except the one that
hides the genital geometry. Adds KO_bust_apex (the forward-most 3 cm of each breast) for the
outfit coverage gate. Purges data left unused.
    python tools/prep_mosin.py SRC.blend OUT.blend
"""
import sys, bpy, numpy as np
src, out = sys.argv[-2], sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=src, use_scripts=False)
removed = []
for cname in ('Default outfit', 'Siberian slide outfit', 'Props', 'Demo', 'Utility'):
    c = bpy.data.collections.get(cname)
    if not c: continue
    for o in list(c.objects):
        removed.append(o.name); bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(c)
body = bpy.data.objects['Body']
off = []
for m in body.modifiers:
    if m.type == 'MASK' and m.vertex_group in ('default legs', 'default gloves', 'default tits', 'siberian pants'):
        m.show_viewport = m.show_render = False; off.append(m.name)
# toon outlines are inverted-hull Solidify shells with a black material; they rely on backface
# culling, which Cycles ignores, so in Cycles they paint the whole character black. Off for render.
solid_off = []
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    for m in o.modifiers:
        if m.type == 'SOLIDIFY' and m.use_flip_normals:
            m.show_render = False; solid_off.append(f'{o.name}:{m.name}')
# physics proxies (cloth/collision helpers) never render; one (TailHairPhys) was left visible in the file
hidden = []
for o in bpy.data.objects:
    if o.type == 'MESH' and ('Phys' in o.name or 'collision' in o.name.lower()):
        if not o.hide_render: hidden.append(o.name)
        o.hide_render = True
# the file's own jiggle/hair physics: cloth proxies drive Hair and Body through Surface Deform.
# Re-simulated at bake they stretch the hair into long streaks, so they are off; secondary motion
# is the framework's job (to-do 16), not the rig's cloth cache.
sd_off = []
for o in bpy.data.objects:
    if o.type != 'MESH' or 'Phys' in o.name: continue
    for m in o.modifiers:
        if m.type == 'SURFACE_DEFORM' and m.target and 'Phys' in m.target.name:
            m.show_render = m.show_viewport = False; sd_off.append(f'{o.name}:{m.name}')
    for m in o.modifiers:
        if m.type == 'CLOTH': m.show_render = m.show_viewport = False
# shape keys that existed only to fit the removed garments
if body.data.shape_keys:
    for k in body.data.shape_keys.key_blocks:
        if k.name in ('For default boots', 'Cleavage for siberian top'): k.value = 0.0
# bust apex group: per side, skin owned mostly by DEF-breast.X, forward-most (min y) 3 cm
me = body.data
co = np.array([body.matrix_world @ v.co for v in me.vertices])
gi = {g.name: g.index for g in body.vertex_groups}
apex = []
for side in 'LR':
    gidx = gi.get(f'DEF-breast.{side}')
    w = np.zeros(len(co))
    for v in me.vertices:
        for e in v.groups:
            if e.group == gidx: w[v.index] = e.weight
    sel = np.nonzero(w > 0.6)[0]
    tip = co[sel[np.argmin(co[sel, 1])]]
    apex += [int(i) for i in sel if np.linalg.norm(co[i] - tip) < 0.03]
vg = body.vertex_groups.new(name='KO_bust_apex'); vg.add(apex, 1.0, 'REPLACE')
# crotch coverage group: the genitals group minus recessed interior geometry. A vertex counts as
# outer skin when at least 9 of 26 ray directions leave the body without hitting it (the outfit
# gate itself treats 4+ as exterior; recessed slit geometry, hidden by the genital mask anyway,
# sits at 4-7 and can never have fabric within 15 mm).
from mathutils import Vector
from mathutils.bvhtree import BVHTree
saved = [(m, m.show_viewport) for m in body.modifiers if m.type != 'ARMATURE']
for m, _ in saved: m.show_viewport = False
bpy.context.view_layer.update()
ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get()); em = ev.to_mesh()
ec = [body.matrix_world @ v.co for v in em.vertices]; ev.to_mesh_clear()
for m, sv in saved: m.show_viewport = sv
tree = BVHTree.FromPolygons(ec, [tuple(p.vertices) for p in me.polygons])
dirs = [Vector((x, y, z)).normalized() for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)]
gg = gi['genitals']; outer = []
for v in me.vertices:
    if not any(e.group == gg and e.weight > 0.5 for e in v.groups): continue
    p = ec[v.index]
    if sum(tree.ray_cast(p + d * 0.003, d, 0.6)[0] is None for d in dirs) >= 9: outer.append(v.index)
vg2 = body.vertex_groups.new(name='KO_crotch_outer'); vg2.add(outer, 1.0, 'REPLACE')
print('crotch outer verts', len(outer))
for _ in range(3): bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=out)
print('removed', len(removed), removed); print('masks off', off); print('surface deform off', sd_off); print('proxies hidden', hidden); print('outline shells off', solid_off); print('bust apex verts', len(apex))
print('remaining meshes', sorted(o.name for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('WGT')))
