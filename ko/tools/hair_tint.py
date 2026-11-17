"""Recolour a character's hair materials without touching the source textures.

usage: python3 tools/hair_tint.py IN.blend OUT.blend MESH [--albedo r,g,b] [--contrast 1.6] [--spec 0.35] [--rough 0.42]

Each hair material's base colour texture is reduced to luminance, normalised by that texture's
median luminance (linear), and multiplied by the target albedo, so near-white braids and mid-grey
haircards land on the same blond. Materials with no base colour texture (or the wrong one, e.g.
Izzy's caps sampling the leotard) get the flat albedo. Specular and roughness are set so the hair
does not clip under the gym's overheads (owner 2026-11-13: blond, not overexposed).
"""
import sys

import bpy
import numpy as np

a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
src, out, mesh = a[0], a[1], a[2]
opt = lambda k, d: a[a.index(k) + 1] if k in a else d  # noqa: E731
albedo = [float(x) for x in opt('--albedo', '0.25,0.165,0.065').split(',')]
contrast = float(opt('--contrast', '1.6'))
spec = float(opt('--spec', '0.35'))
rough = float(opt('--rough', '0.42'))
flat = ('Caps',)                                  # materials coloured flat, not from their texture

bpy.ops.wm.open_mainfile(filepath=src, use_scripts=False)
ob = bpy.data.objects[mesh]


def median_lum(img):
    """Median linear luminance of the opaque texels (sRGB decoded by Blender's float pixels)."""
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    if img.colorspace_settings.name == 'sRGB':
        # foreach_get returns the stored (display-referred) values for 8-bit images: decode
        c = px[:, :3]
        px[:, :3] = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = px[:, 3] > 0.5 if px[:, 3].min() < 0.99 else np.ones(len(px), bool)
    lum = px[m, :3] @ np.array([0.2126, 0.7152, 0.0722])
    lum = lum[lum > 0.02]                          # ignore the black gaps between strands
    return float(np.median(lum)) if len(lum) else 0.5


for m in {s.material for s in ob.material_slots if s.material}:
    nt = m.node_tree
    bsdf = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        continue
    bc = bsdf.inputs['Base Color']
    tex = bc.links[0].from_node if bc.is_linked else None
    for l in list(bc.links):
        nt.links.remove(l)
    rgb = nt.nodes.new('ShaderNodeRGB')
    rgb.name = rgb.label = 'KO hair albedo'
    if tex is not None and tex.type == 'TEX_IMAGE' and tex.image and not m.name.startswith(flat):
        med = max(median_lum(tex.image), 0.05)
        gain = 1.0
        rgb.outputs[0].default_value = (*albedo, 1.0)
        bw0 = nt.nodes.new('ShaderNodeRGBToBW')
        nrm = nt.nodes.new('ShaderNodeMath')
        nrm.operation = 'DIVIDE'
        nrm.inputs[1].default_value = med
        bw = nt.nodes.new('ShaderNodeMath')          # strand contrast: (lum / median) ^ gamma
        bw.operation = 'POWER'
        bw.inputs[1].default_value = contrast
        nt.links.new(bw0.outputs['Val'], nrm.inputs[0])
        nt.links.new(nrm.outputs[0], bw.inputs[0])
        tex_out = tex.outputs['Color']
        mul = nt.nodes.new('ShaderNodeMix')
        mul.data_type = 'RGBA'
        mul.blend_type = 'MULTIPLY'
        mul.clamp_result = False
        mul.inputs['Factor'].default_value = 1.0
        nt.links.new(tex_out, bw0.inputs['Color'])
        nt.links.new(bw.outputs[0], mul.inputs[6])         # A (colour)
        nt.links.new(rgb.outputs[0], mul.inputs[7])        # B (colour)
        nt.links.new(mul.outputs[2], bc)
        print(f'[hair] {m.name}: texture {tex.image.name} median lum {med:.3f} contrast {contrast}')
    else:
        rgb.outputs[0].default_value = (*albedo, 1.0)
        nt.links.new(rgb.outputs[0], bc)
        print(f'[hair] {m.name}: flat albedo')
    for k, v in (('Specular IOR Level', spec), ('Roughness', rough)):
        s = bsdf.inputs.get(k)
        if s is not None and not s.is_linked:
            s.default_value = max(s.default_value, v) if k == 'Roughness' else min(s.default_value, v)
    for k in ('Coat Weight', 'Sheen Weight'):
        s = bsdf.inputs.get(k)
        if s is not None and not s.is_linked:
            s.default_value = min(s.default_value, 0.1)
bpy.ops.wm.save_as_mainfile(filepath=out)
print('[hair] saved', out)
