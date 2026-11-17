"""Preview materials for a Daz character whose textures were not supplied: flat, neutral
Principled materials by slot role (skin, lips, eyes, teeth, nails, hair), so stills read until the
real textures arrive (then the character points back at the textured file). Not the character's
look; never final.
    python3 tools/preview_skin.py SRC.blend OUT.blend [--skin 0.62,0.42,0.33]
"""
import sys

import bpy

src, out = sys.argv[-2], sys.argv[-1] if not sys.argv[-1].startswith('--') else sys.argv[-3]
bpy.ops.wm.open_mainfile(filepath=src, use_scripts=False)
SK = (0.47, 0.30, 0.22)


def mat(name, rgb, rough=0.5, sss=0.0, alpha=1.0, trans=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    if sss:
        b.inputs['Subsurface Weight'].default_value = sss
        b.inputs['Subsurface Radius'].default_value = (1.0, 0.35, 0.2)
        b.inputs['Subsurface Scale'].default_value = 0.01
    if trans:
        b.inputs['Transmission Weight'].default_value = trans
    b.inputs['Alpha'].default_value = alpha
    return m


R = {
    'skin': mat('KO_prev_skin', SK, 0.45, 0.05),
    'lips': mat('KO_prev_lips', (0.55, 0.28, 0.26), 0.35, 0.1),
    'mouth': mat('KO_prev_mouth', (0.35, 0.10, 0.10), 0.4),
    'teeth': mat('KO_prev_teeth', (0.85, 0.82, 0.76), 0.3),
    'nails': mat('KO_prev_nails', (0.75, 0.55, 0.50), 0.3),
    'sclera': mat('KO_prev_sclera', (0.88, 0.86, 0.84), 0.3),
    'iris': mat('KO_prev_iris', (0.18, 0.28, 0.36), 0.3),
    'pupil': mat('KO_prev_pupil', (0.01, 0.01, 0.01), 0.3),
    'clear': mat('KO_prev_clear', (1, 1, 1), 0.02, alpha=0.0),
    'hair': mat('KO_prev_hair', (0.09, 0.055, 0.035), 0.45),
    'brow': mat('KO_prev_brow', (0.06, 0.04, 0.03), 0.6),
    'lash': mat('KO_prev_lash', (0.01, 0.01, 0.01), 0.6),
}
for m in R.values():
    m.blend_method = 'HASHED' if hasattr(m, 'blend_method') else None


def role(obname, mname):
    o, n = obname.lower(), mname.lower()
    if 'hair' in o:
        return 'hair'
    if 'brow' in o:
        return 'brow'
    if 'lash' in o:
        return 'lash'
    for k, r in (('cornea', 'clear'), ('eyemoisture', 'clear'), ('sclera', 'sclera'),
                 ('iris', 'iris'), ('pupil', 'pupil'), ('teeth', 'teeth'), ('mouth', 'mouth'),
                 ('lips', 'lips'), ('nail', 'nails'), ('eyesocket', 'skin')):
        if k in n:
            return r
    return 'skin'


arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and o.name.startswith('Genesis'))
done = []
for o in bpy.data.objects:
    if o.type != 'MESH' or o.parent != arm:
        continue
    for s in o.material_slots:
        if s.material is None:
            continue
        r = role(o.name, s.material.name)
        s.material = R[r]
        done.append((o.name, r))
bpy.ops.wm.save_as_mainfile(filepath=out)
print('preview materials', len(done))
