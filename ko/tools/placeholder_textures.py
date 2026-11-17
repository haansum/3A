"""Write generic PLACEHOLDER textures for every image a .blend references but does not have, under the same relative
paths, so the file renders readably until the real textures are copied over them (same names -> drop-in replacement).

    python placeholder_textures.py --blend klukai/Klukai_1_4.blend [--size 1024]

Not a reproduction of any artwork: flat, neutral colours chosen per texture role, UV-rasterised so only used areas are
painted. Diffuse: skin / hair / cloth / metal by name. Normal maps: flat (0.5, 0.5, 1). Spec: dark. Eye atlas: white
sclera, a neutral grey-brown iris and a black pupil at the UV centre (lets gaze direction read on camera). Face sheet:
skin, with the brows' UV area painted dark so expressions read. Overlays (blush, eye shading): transparent.
"""
import argparse, os, sys, numpy as np, bpy
from PIL import Image, ImageDraw

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
ap = argparse.ArgumentParser(); ap.add_argument("--blend", required=True); ap.add_argument("--size", type=int, default=1024); ap.add_argument("--hair", default="196,192,188"); ap.add_argument("--iris", default="92,78,70")
a = ap.parse_args(argv)
bpy.ops.wm.open_mainfile(filepath=a.blend)
SKIN, CLOTH, METAL, LIGHT = (232, 200, 184), (52, 54, 60), (110, 112, 118), (226, 224, 220)
HAIR = tuple(int(x) for x in a.hair.split(",")); IRIS = tuple(int(x) for x in a.iris.split(","))
def role(name):
    n = name.lower()
    if "norm" in n: return "normal"
    if "spec" in n: return "spec"
    if "eyes_blend" in n or "emoji" in n or "tint" in n: return "clear"
    if "eyes" in n: return "eye"
    if "face" in n: return "face"
    if any(k in n for k in ("body", "neck", "nails", "skin")): return "skin"
    if "hair" in n: return "hair"
    if any(k in n for k in ("glock", "suppr", "watch", "truncheon", "holster")): return "metal"
    if "flower" in n: return "light"
    return "cloth"
# which (object, material slot) polygons use each image
use = {}
for o in bpy.data.objects:
    if o.type != "MESH" or not o.data.uv_layers: continue
    for i, s in enumerate(o.material_slots):
        m = s.material
        if not m or not m.node_tree: continue
        for nd in m.node_tree.nodes:
            if nd.type == "TEX_IMAGE" and nd.image and nd.image.source == "FILE" and not nd.image.packed_file:
                use.setdefault(nd.image.name, []).append((o, i, m.name))
blend_dir = os.path.dirname(bpy.path.abspath(a.blend))
made = []
for img in bpy.data.images:
    if img.source != "FILE" or img.packed_file: continue
    path = bpy.path.abspath(img.filepath, start=os.path.dirname(a.blend) + "/")
    if os.path.exists(path): continue
    r, S = role(img.name), a.size
    if r == "normal": im = Image.new("RGBA", (S, S), (128, 128, 255, 255))
    elif r == "spec": im = Image.new("RGBA", (S, S), (24, 24, 24, 255))
    elif r == "clear": im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    elif r == "eye":
        im = Image.new("RGBA", (S, S), (240, 238, 236, 255)); d = ImageDraw.Draw(im); c = S / 2
        d.ellipse([c - 0.30 * S, c - 0.33 * S, c + 0.30 * S, c + 0.33 * S], fill=IRIS + (255,))      # iris (anime eyes run tall)
        d.ellipse([c - 0.22 * S, c - 0.25 * S, c + 0.22 * S, c + 0.25 * S], fill=tuple(int(c * 0.75) for c in IRIS) + (255,))      # darker inner ring
        d.ellipse([c - 0.11 * S, c - 0.13 * S, c + 0.11 * S, c + 0.13 * S], fill=(16, 14, 14, 255))      # pupil
    else:
        base = {"face": SKIN, "skin": SKIN, "hair": HAIR, "metal": METAL, "light": LIGHT}.get(r, CLOTH)
        im = Image.new("RGBA", (S, S), base + (255,))
        if r == "face":   # brows: paint the brow material's UV area dark so the brows read
            d = ImageDraw.Draw(im)
            for o, mi, mn in use.get(img.name, []):
                if "brow" not in mn.lower(): continue
                uv = o.data.uv_layers.active.data
                for p in o.data.polygons:
                    if p.material_index != mi: continue
                    d.polygon([(uv[l].uv[0] * S, (1 - uv[l].uv[1]) * S) for l in p.loop_indices], fill=(70, 60, 58, 255))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = im.convert('RGB') if path.lower().endswith(('.jpg', '.jpeg')) else im
    try:
        im.save(path); made.append((os.path.basename(path), r))
    except (ValueError, OSError):
        pass   # formats PIL cannot write (.hdr, .exr): left missing
print(f"wrote {len(made)} placeholder textures into {os.path.dirname(path) if made else '-'}")
for n, r in made: print(f"  {r:6s} {n}")
