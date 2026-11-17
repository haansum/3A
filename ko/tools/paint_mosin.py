"""Paint original textures for Mosin's rig and rebuild her materials for Cycles.

The upload came without its textures/ folder, and its materials are EEVEE toon networks
(Shader-to-RGB) that Cycles cannot evaluate. This script paints new textures from the mesh
itself (UV islands classified by their 3D position, colours interpolated from per-vertex
values computed in 3D), writes them to assets_cache/mosin/textures_ko/, and replaces each
material with a Principled-based one so the framework's render stage keeps them as they are.
It is not a reproduction of the original artwork; colours follow her usual scheme
(silver-white hair, red eyes, fair skin).

    python tools/paint_mosin.py IN.blend OUT.blend [--res 2048]
"""
import os
import sys
import collections

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
SRC, OUT = argv[0], argv[1]
RES = int(argv[argv.index('--res') + 1]) if '--res' in argv else 2048
bpy.ops.wm.open_mainfile(filepath=SRC, use_scripts=False)
TEXDIR = os.path.join(os.path.dirname(os.path.abspath(OUT)), 'textures_ko')
os.makedirs(TEXDIR, exist_ok=True)
rng = np.random.default_rng(7)

SKIN = np.array([246, 222, 208]) / 255.0       # fair, slightly warm
SKIN_PINK = np.array([238, 170, 160]) / 255.0  # knuckles, knees, elbows, cheeks
LIP = np.array([214, 132, 132]) / 255.0
HAIR = np.array([220, 222, 232]) / 255.0       # silver-white, faint cool cast
HAIR_DEEP = np.array([142, 144, 164]) / 255.0  # inner layers and roots
IRIS_HI = np.array([236, 70, 62]) / 255.0
IRIS_LO = np.array([120, 10, 22]) / 255.0


# ---------------------------------------------------------------- rasteriser
def raster(img, tris_uv, tris_col, alpha=None):
    """img: HxWx4 float. tris_uv: (N,3,2) in UV 0..1. tris_col: (N,3,3) per-corner colour.
    Barycentric interpolation, written where the triangle covers the pixel centre."""
    H, W = img.shape[:2]
    P = tris_uv * np.array([W, H])
    P[..., 1] = H - P[..., 1]
    for t in range(len(P)):
        p, c = P[t], tris_col[t]
        x0, y0 = np.floor(p.min(0)).astype(int)
        x1, y1 = np.ceil(p.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, W - 1), min(y1, H - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        a, b, cc = p
        den = (b[1] - cc[1]) * (a[0] - cc[0]) + (cc[0] - b[0]) * (a[1] - cc[1])
        if abs(den) < 1e-12:
            continue
        l1 = ((b[1] - cc[1]) * (xs - cc[0]) + (cc[0] - b[0]) * (ys - cc[1])) / den
        l2 = ((cc[1] - a[1]) * (xs - cc[0]) + (a[0] - cc[0]) * (ys - cc[1])) / den
        l3 = 1 - l1 - l2
        m = (l1 >= -0.01) & (l2 >= -0.01) & (l3 >= -0.01)
        if not m.any():
            continue
        col = l1[..., None] * c[0] + l2[..., None] * c[1] + l3[..., None] * c[2]
        sub = img[y0:y1 + 1, x0:x1 + 1]
        sub[m, :3] = col[m]
        sub[m, 3] = 1.0 if alpha is None else alpha
    return img


def pad(img, px=8):
    """Bleed island colours outward so mip-mapping and filtering never pick up background."""
    a = img[..., 3] > 0
    if not a.any():
        return img
    _, idx = ndimage.distance_transform_edt(~a, return_indices=True)
    dist = ndimage.distance_transform_edt(~a)
    near = img[idx[0], idx[1]]
    out = img.copy()
    fill = (~a) & (dist <= px)
    out[fill, :3] = near[fill, :3]
    return out


def save(img, name, keep_alpha=False):
    im = np.clip(img, 0, 1)
    if not keep_alpha:
        im = pad(im)
        im[..., 3] = 1.0
    Image.fromarray((im * 255 + 0.5).astype(np.uint8), 'RGBA').save(os.path.join(TEXDIR, name))
    return os.path.join(TEXDIR, name)


def gauss(d, s):
    return np.exp(-0.5 * (d / s) ** 2)


def mesh_tris(ob, mat_index=None):
    """Evaluated-free rest mesh: (faces as triangles) -> uv (N,3,2), vertex ids (N,3)."""
    me = ob.data
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    T_uv, T_v, T_poly = [], [], []
    for lt in me.loop_triangles:
        if mat_index is not None and lt.material_index not in mat_index:
            continue
        T_uv.append([uv[l].uv[:] for l in lt.loops])
        T_v.append(list(lt.vertices))
        T_poly.append(lt.polygon_index)
    return np.array(T_uv), np.array(T_v), np.array(T_poly)


def world_co(ob):
    M = np.array(ob.matrix_world)
    co = np.array([v.co[:] for v in ob.data.vertices])
    no = np.array([v.normal[:] for v in ob.data.vertices])
    return co @ M[:3, :3].T + M[:3, 3], no @ M[:3, :3].T


def islands(ob):
    """Polygon index -> island id, by shared vertex + identical UV."""
    me = ob.data
    uv = me.uv_layers.active.data
    parent = list(range(len(me.polygons)))

    def f(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    seen = {}
    for p in me.polygons:
        for l in p.loop_indices:
            k = (me.loops[l].vertex_index, round(uv[l].uv[0], 4), round(uv[l].uv[1], 4))
            if k in seen:
                parent[f(p.index)] = f(seen[k])
            else:
                seen[k] = p.index
    return np.array([f(p.index) for p in me.polygons])


# ---------------------------------------------------------------- face sheet (mn_face)
face = bpy.data.objects['Face']
fco, fno = world_co(face)
fme = face.data
isl = islands(face)
pmat = np.array([p.material_index for p in fme.polygons])
pcen = np.array([np.mean([fco[v] for v in p.vertices], 0) for p in fme.polygons])
pnorm = np.array([(face.matrix_world.to_3x3() @ p.normal)[:] for p in fme.polygons])
groups = collections.defaultdict(list)
for i, g in enumerate(isl):
    groups[g].append(i)
main_face = max((g for g in groups if pmat[groups[g][0]] == 0), key=lambda g: len(groups[g]))
eye_z = float(np.mean([pcen[p][2] for p in range(len(pcen)) if pmat[p] == 3]))
eye_x = float(np.mean([abs(pcen[p][0]) for p in range(len(pcen)) if pmat[p] == 3]))
eye_y = float(np.mean([pcen[p][1] for p in range(len(pcen)) if pmat[p] == 3]))


def classify(g):
    ps = groups[g]
    m = pmat[ps[0]]
    c = pcen[ps].mean(0)
    n = pnorm[ps].mean(0)
    if m == 1:                                  # lash / brow / lid-line geometry
        if c[2] > eye_z + 0.015:
            return 'brow'
        if n[2] > 0.5:
            return 'lid_low'
        return 'lash'
    if m != 0:
        return None
    if g == main_face:
        return 'face'
    if abs(c[2] - eye_z) < 0.01 and abs(abs(c[0]) - eye_x) < 0.01:
        return 'sclera'
    if c[2] < eye_z - 0.03:                     # mouth parts
        if len(ps) == 20:
            return 'teeth'
        if n[1] > 0.2:
            return 'mouth_back'
        if len(ps) >= 100:
            return 'mouth_roof'
        return 'tongue'
    return 'skin'


cls = {g: classify(g) for g in groups}
print('face islands:', collections.Counter(v for v in cls.values()))

# per-vertex colour on the main face, computed in 3D
vcol = np.tile(SKIN, (len(fco), 1)).astype(float)
cheek = gauss(np.hypot(np.abs(fco[:, 0]) - (eye_x + 0.006), fco[:, 2] - (eye_z - 0.022)), 0.012)
vcol = vcol * (1 - 0.45 * cheek[:, None]) + SKIN_PINK * 0.45 * cheek[:, None]
nose = gauss(np.hypot(fco[:, 0], fco[:, 2] - (eye_z - 0.03)), 0.006) * (fco[:, 1] < eye_y - 0.015)
vcol = vcol * (1 - 0.25 * nose[:, None]) + SKIN_PINK * 0.25 * nose[:, None]
mouth_z = float(np.mean([pcen[p][2] for g, c in cls.items() if c == 'teeth' for p in groups[g]]))
lips = gauss(np.hypot(fco[:, 0] / 2.2, fco[:, 2] - mouth_z), 0.0045) * (np.abs(fco[:, 0]) < 0.016)
vcol = vcol * (1 - 0.55 * lips[:, None]) + LIP * 0.55 * lips[:, None]
# eye socket: faint warm shadow above and below the opening
sock = gauss(np.hypot(np.abs(fco[:, 0]) - eye_x, (fco[:, 2] - eye_z) * 0.8), 0.011)
vcol *= (1 - 0.07 * sock[:, None])

img = np.zeros((RES, RES, 4))
UVt, Vt, Pt = mesh_tris(face)
col = {
    'face': None, 'skin': SKIN,
    'brow': np.array([150, 150, 162]) / 255, 'lash': np.array([46, 38, 44]) / 255,
    'lid_low': np.array([120, 92, 92]) / 255,
    'sclera': None, 'teeth': np.array([242, 240, 236]) / 255,
    'mouth_back': np.array([92, 32, 40]) / 255, 'mouth_roof': np.array([150, 66, 76]) / 255,
    'tongue': np.array([200, 104, 110]) / 255,
}
for c in ('face', 'skin', 'brow', 'lash', 'lid_low', 'sclera', 'teeth', 'mouth_back', 'mouth_roof', 'tongue'):
    sel = np.array([cls.get(isl[p]) == c for p in Pt])
    if not sel.any():
        continue
    if c == 'face':
        C = vcol[Vt[sel]]
    elif c == 'sclera':
        z = fco[Vt[sel]][..., 2]
        top = np.clip((z - (eye_z - 0.004)) / 0.012, 0, 1)[..., None]     # upper lid shadow
        C = np.array([250, 248, 248]) / 255 * (1 - 0.32 * top) + np.array([170, 172, 196]) / 255 * 0.32 * top
    else:
        C = np.tile(col[c], (sel.sum(), 3, 1))
    raster(img, UVt[sel], C)

# eyeliner: the boundary edges of the main face around each eye opening, drawn in UV
bm = bmesh.new()
bm.from_mesh(fme)
uvl = bm.loops.layers.uv.active
bm.faces.ensure_lookup_table()
liner = Image.new('L', (RES * 2, RES * 2), 0)
dl = ImageDraw.Draw(liner)
for e in bm.edges:
    if not e.is_boundary:
        continue
    fa = e.link_faces[0]
    if isl[fa.index] != main_face:
        continue
    a, b = (fco[v.index] for v in e.verts)
    mid = 0.5 * (a + b)
    if abs(mid[2] - eye_z) > 0.02 or abs(abs(mid[0]) - eye_x) > 0.025:
        continue
    upper = mid[2] > eye_z - 0.001
    outer = np.clip((abs(mid[0]) - eye_x) / 0.012, 0, 1)   # wing toward the outer corner
    w = (14 + 10 * outer) if upper else 5
    pts = []
    for l in fa.loops:
        if l.vert in e.verts:
            u, v = l[uvl].uv
            pts.append((u * RES * 2, (1 - v) * RES * 2))
    if len(pts) == 2:
        dl.line(pts, fill=255 if upper else 150, width=int(w * RES / 2048))
liner = np.array(liner.filter(ImageFilter.GaussianBlur(2)).resize((RES, RES), Image.LANCZOS)) / 255.0
lc = np.array([52, 34, 40]) / 255
img[..., :3] = img[..., :3] * (1 - liner[..., None]) + lc * liner[..., None]
face_png = save(img, 'mn_face_ko.png')

# ---------------------------------------------------------------- iris (mn_eyes_diff): one disc
S = RES
yy, xx = (np.mgrid[0:S, 0:S] + 0.5) / S
cx, cy, R = 0.503, 0.506, 0.488
dx, dy = xx - cx, (yy - cy)
r = np.hypot(dx, dy) / R
th = np.arctan2(dy, dx)
t = np.clip((yy - (cy - R)) / (2 * R), 0, 1)[..., None]     # 0 top .. 1 bottom (image rows)
iris = IRIS_LO * (1 - t) + IRIS_HI * t                       # darker under the lid, bright below
stri = 0.5 + 0.5 * np.sin(th * 46 + 3 * np.sin(th * 7)) * np.clip(1.2 - r, 0, 1)
iris = iris * (0.86 + 0.18 * stri[..., None])
ring = np.clip((r - 0.80) / 0.15, 0, 1)[..., None]
iris = iris * (1 - 0.75 * ring) + np.array([40, 4, 10]) / 255 * 0.75 * ring
glow = gauss(np.hypot(dx, dy - 0.18 * R), 0.22 * R)[..., None]      # warm glow in the lower iris
iris = iris + 0.18 * glow * np.array([1.0, 0.55, 0.3])
pup = np.clip((0.36 - r) / 0.03, 0, 1)[..., None]
iris = iris * (1 - pup) + np.array([24, 4, 8]) / 255 * pup
for hx, hy, hr, a in ((-0.22, -0.26, 0.13, 1.0), (0.2, 0.25, 0.06, 0.8), (0.28, -0.1, 0.035, 0.6)):
    h = np.clip((hr * R - np.hypot(dx - hx * R, dy - hy * R)) / (0.015 * R), 0, 1)[..., None] * a
    iris = iris * (1 - h) + h
eyes = np.dstack([np.clip(iris, 0, 1), np.ones((S, S))])
eyes_png = save(eyes, 'mn_eyes_ko.png')

# ---------------------------------------------------------------- lid shadow overlay (mn_eyes_blend)
ov = np.zeros((S, S, 4))
UVb, _, Pb = mesh_tris(face, {2})
ub = UVb.reshape(-1, 2)
bc = 0.5 * (ub.min(0) + ub.max(0))
br = 0.5 * (ub.max(0) - ub.min(0)).max()
dx2, dy2 = xx - bc[0], (1 - yy) - bc[1]
top = np.clip((dy2 / br - 0.15) / 0.75, 0, 1)                 # upper part of the disc
inside = np.hypot(dx2, dy2) < br
ov[..., :3] = np.array([40, 10, 20]) / 255
ov[..., 3] = 0.55 * top * inside
blend_png = save(ov, 'mn_eyes_blend_ko.png', keep_alpha=True)

# ---------------------------------------------------------------- blush decal (emoji)
bl = np.zeros((S, S, 4))
UVc, _, _ = mesh_tris(face, {4})
uc = UVc.reshape(-1, 2)
c0, c1 = uc.min(0), uc.max(0)
cc = 0.5 * (c0 + c1)
hw = 0.5 * (c1 - c0)
ex = ((xx - cc[0]) / hw[0]) ** 2 + (((1 - yy) - cc[1]) / hw[1]) ** 2
bl[..., :3] = np.array([236, 120, 128]) / 255
bl[..., 3] = 0.42 * np.exp(-2.6 * ex)
hatch = (np.sin((xx * 0.8 + (1 - yy)) * 2 * np.pi / (hw[0] * 0.28)) > 0.86) & (ex < 0.55)
bl[..., 3] = np.maximum(bl[..., 3], 0.55 * hatch * np.exp(-1.5 * ex))
blush_png = save(bl, 'mn_blush_ko.png', keep_alpha=True)

# ---------------------------------------------------------------- hair (mn_hair_diff)
hair = bpy.data.objects['Hair']
hco, hno = world_co(hair)
head_c = np.array([0.0, eye_y + 0.07, eye_z + 0.02])
d = np.linalg.norm(hco - head_c, axis=1)
depth = np.clip((0.115 - d) / 0.04, 0, 1)              # inner layers sit closer to the skull
under = np.clip(-hno[:, 2], 0, 1) * 0.5
hv = np.clip(depth + under, 0, 1)[:, None]
hcol = HAIR * (1 - 0.75 * hv) + HAIR_DEEP * 0.75 * hv
img = np.zeros((S, S, 4))
UVh, Vh, Ph = mesh_tris(hair, {1})
raster(img, UVh, hcol[Vh])
UVr, Vr, _ = mesh_tris(hair, {0})
raster(img, UVr, np.tile(np.array([34, 34, 46]) / 255, (len(UVr), 3, 1)))      # ribbon / ties
# strands: fine streak noise elongated along UV v, dimmed slightly
n = rng.standard_normal((S // 2, 48))
n = ndimage.gaussian_filter(n, (6, 0.6))
n = np.array(Image.fromarray(((n - n.min()) / np.ptp(n) * 255).astype(np.uint8)).resize((S, S), Image.BICUBIC)) / 255.0
img[..., :3] *= (0.86 + 0.2 * n[..., None])
hair_png = save(img, 'mn_hair_ko.png')

# ---------------------------------------------------------------- body skin (body_diff)
body = bpy.data.objects['Body']
arm = bpy.data.objects['Mosin Nagant']
bco, bno = world_co(body)


def bone_head(name):
    b = arm.data.bones.get(name)
    return np.array((arm.matrix_world @ b.head_local)[:]) if b else None


tint = np.zeros(len(bco))
for nm, s, a in (('DEF-forearm.L', 0.025, 0.5), ('DEF-forearm.R', 0.025, 0.5),
                 ('DEF-shin.L', 0.03, 0.55), ('DEF-shin.R', 0.03, 0.55),
                 ('DEF-hand.L', 0.05, 0.25), ('DEF-hand.R', 0.05, 0.25),
                 ('DEF-toe.L', 0.04, 0.35), ('DEF-toe.R', 0.04, 0.35),
                 ('DEF-foot.L', 0.03, 0.2), ('DEF-foot.R', 0.03, 0.2)):
    p = bone_head(nm)
    if p is not None:
        tint = np.maximum(tint, a * gauss(np.linalg.norm(bco - p, axis=1), s))
for side in (1, -1):    # shoulder caps
    p = bone_head('DEF-upper_arm.L' if side > 0 else 'DEF-upper_arm.R')
    if p is not None:
        tint = np.maximum(tint, 0.18 * gauss(np.linalg.norm(bco - p, axis=1), 0.04))
bcol = SKIN * (1 - tint[:, None]) + SKIN_PINK * tint[:, None]
# very low-amplitude mottling so large areas are not dead flat
mot = rng.standard_normal(len(bco)) * 0.008
bcol = np.clip(bcol + mot[:, None], 0, 1)
img = np.zeros((S, S, 4))
UVb2, Vb2, _ = mesh_tris(body, {0})
raster(img, UVb2, bcol[Vb2])
body_png = save(img, 'body_ko.png')
img = np.zeros((512, 512, 4))
UVn, Vn, _ = mesh_tris(body, {1})
raster(img, UVn, np.tile(np.array([244, 196, 196]) / 255, (len(UVn), 3, 1)))
nails_png = save(img, 'nails_ko.png')


# ---------------------------------------------------------------- materials (Cycles)
def load(path):
    im = bpy.data.images.load(path, check_existing=True)
    im.pack()
    return im


def new_mat(name, tex=None, base=None, rough=0.5, sss=0.0, emit=0.0, alpha_from_tex=False,
            coat=0.0, spec=0.5, sheen=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(b.outputs['BSDF'], out.inputs['Surface'])
    b.inputs['Roughness'].default_value = rough
    b.inputs['Specular IOR Level'].default_value = spec
    if tex is not None:
        t = nt.nodes.new('ShaderNodeTexImage')
        t.image = tex
        nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
        if alpha_from_tex:
            nt.links.new(t.outputs['Alpha'], b.inputs['Alpha'])
        if emit:
            nt.links.new(t.outputs['Color'], b.inputs['Emission Color'])
            b.inputs['Emission Strength'].default_value = emit
    elif base is not None:
        b.inputs['Base Color'].default_value = (*base, 1)
    if sss:
        b.inputs['Subsurface Weight'].default_value = sss
        b.inputs['Subsurface Radius'].default_value = (1.0, 0.42, 0.25)
        b.inputs['Subsurface Scale'].default_value = 0.008
    if coat:
        b.inputs['Coat Weight'].default_value = coat
        b.inputs['Coat Roughness'].default_value = 0.05
    if sheen:
        b.inputs['Sheen Weight'].default_value = sheen
        b.inputs['Sheen Roughness'].default_value = 0.35
    if alpha_from_tex:
        m.blend_method = 'BLEND' if hasattr(m, 'blend_method') else None
    return m


def srgb_to_lin(c):
    c = np.asarray(c, float)
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4))


t_face, t_eyes, t_blend, t_blush = load(face_png), load(eyes_png), load(blend_png), load(blush_png)
t_hair, t_body, t_nails = load(hair_png), load(body_png), load(nails_png)
M = {
    'Mosin face': new_mat('KO_face', t_face, rough=0.48, sss=0.18, spec=0.35),
    'Mosin_brows': new_mat('KO_brows', t_face, rough=0.7, spec=0.2),
    'Mosin_eyes': new_mat('KO_iris', t_eyes, rough=0.08, emit=0.55, coat=1.0, spec=0.6),
    'Mosin_eyes_blend': new_mat('KO_lid_shadow', t_blend, rough=0.9, alpha_from_tex=True, spec=0.0),
    'Mosin_blush': new_mat('KO_blush', t_blush, rough=0.6, alpha_from_tex=True, spec=0.0),
    'Mosin_hair': new_mat('KO_hair', t_hair, rough=0.36, spec=0.55, sheen=0.25),
    'Default_cloth2': new_mat('KO_ribbon', base=srgb_to_lin((34 / 255, 34 / 255, 46 / 255)), rough=0.55),
    'Body_skin': new_mat('KO_skin', t_body, rough=0.5, sss=0.18, spec=0.35),
    'Nails': new_mat('KO_nails', t_nails, rough=0.25, spec=0.6, coat=0.5),
}
swapped = []
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    for s in o.material_slots:
        if s.material and s.material.name in M:
            swapped.append(f'{o.name}:{s.material.name}->{M[s.material.name].name}')
            s.material = M[s.material.name]
for _ in range(3):
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(OUT))
print('textures:', sorted(os.listdir(TEXDIR)))
print('materials swapped:', swapped)
