"""Replace Mosin's flat painted eyes with rotatable spherical eyeballs.

Mosin_painted.blend -> Mosin_eyes.blend (input untouched).
 1. per socket, fit a sphere to the sclera bowl (robust LSQ, mirrored to be symmetric);
    shrink it until every lid-edge vertex clears it in the rest, blink and wide keys
 2. delete the flat sclera islands, the iris patch and its lid-shadow overlay from Face
 3. build KO_eye_L / KO_eye_R: UV sphere, pole on the gaze axis (-Y), equal-angle UVs into a
    painted texture (blue iris, limbal ring, collarette, pupil, sclera with faint vessels);
    iris disc recessed 0.8 mm (anterior chamber); a clear cornea shell (transparent + glossy,
    no refraction) over the whole ball
 4. origin at sphere centre, bone-parented to `head` so object rotation = gaze in her axes
usage: python3 tools/eyeballs_mosin.py
"""
import collections
import math
import os

import bpy  # noqa (must precede bmesh)
import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'assets_cache/mosin/Mosin_painted.blend')
DST = os.path.join(ROOT, 'assets_cache/mosin/Mosin_eyes.blend')
TEX = os.path.join(ROOT, 'assets_cache/mosin/textures_ko/eye_ko.png')

IRIS_DEG = 33.0          # angular radius of the iris (human ~30-34 deg for a 12 mm ball)
PUPIL_DEG = 11.0
RECESS = 0.0008
CLEAR = 0.0004           # lid edge must clear the ball by this much
IRIS_BLUE = np.array([58, 118, 196]) / 255
IRIS_DEEP = np.array([22, 52, 108]) / 255
COLLARETTE = np.array([150, 186, 222]) / 255
LIMBUS = np.array([16, 30, 58]) / 255
SCLERA = np.array([240, 236, 232]) / 255
SCLERA_EDGE = np.array([222, 200, 196]) / 255

bpy.ops.wm.open_mainfile(filepath=SRC)
face = bpy.data.objects['Face']
arm = face.parent
me = face.data
M = face.matrix_world
co = np.array([(M @ v.co)[:] for v in me.vertices])
pmat = np.array([p.material_index for p in me.polygons])
pcen = np.array([co[list(p.vertices)].mean(0) for p in me.polygons])

# UV islands (same rule as paint_mosin)
uv = me.uv_layers.active.data
parent = list(range(len(me.polygons)))


def fnd(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


seen = {}
for p in me.polygons:
    for li in p.loop_indices:
        k = (me.loops[li].vertex_index, round(uv[li].uv[0], 4), round(uv[li].uv[1], 4))
        if k in seen:
            parent[fnd(p.index)] = fnd(seen[k])
        else:
            seen[k] = p.index
isl = np.array([fnd(p.index) for p in me.polygons])
groups = collections.defaultdict(list)
for i, g in enumerate(isl):
    groups[g].append(i)
main = max((g for g in groups if pmat[groups[g][0]] == 0), key=lambda g: len(groups[g]))
ez = pcen[pmat == 3][:, 2].mean()
ex = np.abs(pcen[pmat == 3][:, 0]).mean()
sclera_polys = [p for g, ps in groups.items() if pmat[ps[0]] == 0 and g != main
                and abs(pcen[ps].mean(0)[2] - ez) < 0.01
                and abs(abs(pcen[ps].mean(0)[0]) - ex) < 0.01 for p in ps]


def fit_sphere(P):
    keep = np.ones(len(P), bool)
    for _ in range(4):
        Q = P[keep]
        A = np.c_[2 * Q, np.ones(len(Q))]
        s = np.linalg.lstsq(A, (Q ** 2).sum(1), rcond=None)[0]
        C = s[:3]
        R = math.sqrt(s[3] + C @ C)
        res = np.linalg.norm(P - C, axis=1) - R
        keep = np.abs(res) < max(2.5 * np.sqrt((res[keep] ** 2).mean()), 0.0008)
    return C, R


svs = sorted({v for p in sclera_polys for v in me.polygons[p].vertices})
S = co[svs]
mir = S * np.array([-1, 1, 1])
C, R = fit_sphere(np.vstack([S[S[:, 0] > 0], mir[mir[:, 0] > 0]]))
print('sphere fit', np.round(C, 4), round(R, 4))

# lid edge = main-face boundary vertices around the sockets, checked across the lid keys
bm = bmesh.new()
bm.from_mesh(me)
mainset = set(groups[main])
lid = set()
for e in bm.edges:
    if sum(f.index in mainset for f in e.link_faces) == 1:
        lid |= {e.verts[0].index, e.verts[1].index}
bm.free()
lid = np.array(sorted(lid))
lid = lid[(np.abs(co[lid, 2] - ez) < 0.03) & (np.abs(np.abs(co[lid, 0]) - ex) < 0.03)
          & (co[lid, 1] < C[1])]
kbs = me.shape_keys.key_blocks
Mn = np.array(M)
clear = {}
for kn in ('base', 'eye_blink_left', 'eyes_surprised', 'eyes_shrink'):
    if kn not in kbs:
        continue
    for w in (0.25, 0.5, 0.75, 1.0) if kn != 'base' else (1.0,):
        b0 = np.array([v.co[:] for v in kbs['base'].data])[lid]
        k1 = np.array([v.co[:] for v in kbs[kn].data])[lid]
        p = b0 + w * (k1 - b0)
        pw = p @ Mn[:3, :3].T + Mn[:3, 3]
        pw[:, 0] = np.abs(pw[:, 0])
        clear[(kn, w)] = (np.linalg.norm(pw - C, axis=1) - R).min()
# rest pose decides the radius; blink path is reported (lids may brush the ball when closing)
R_eye = R + min(0.0, clear[('base', 1.0)] - CLEAR)
print('lid clearance (mm):', {f'{k}@{w}': round(1000 * v, 2) for (k, w), v in clear.items()})
print('eye radius fit %.2f mm -> used %.2f mm' % (R * 1000, R_eye * 1000))

# ---------------------------------------------------------------- remove flat eye geometry
bm = bmesh.new()
bm.from_mesh(me)
bm.faces.ensure_lookup_table()
kill = set(sclera_polys) | set(np.where((pmat == 3) | (pmat == 2))[0].tolist())
bmesh.ops.delete(bm, geom=[bm.faces[i] for i in kill], context='FACES')
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
bm.to_mesh(me)
bm.free()
me.update()
print('removed faces', len(kill))

# ---------------------------------------------------------------- texture (equal-angle disc)
N = 2048
yy, xx = (np.mgrid[0:N, 0:N] + 0.5) / N
dx, dy = xx - 0.5, yy - 0.5
th = np.hypot(dx, dy) * 2 * 180.0          # deg from the gaze axis (rim = 180)
ph = np.arctan2(dy, dx)
rng = np.random.default_rng(7)
r = np.clip(th / IRIS_DEG, 0, 2)
img = np.tile(SCLERA, (N, N, 1)).astype(float)
edge = np.clip((th - 55) / 70, 0, 1)[..., None]
img = img * (1 - 0.6 * edge) + SCLERA_EDGE * 0.6 * edge
# faint vessels creeping in from the canthi
ves = np.zeros((N, N))
for k in range(26):
    a0 = rng.choice([0.0, math.pi]) + rng.normal(0, 0.5)
    w = rng.uniform(2.5, 5.0)
    f = rng.uniform(3, 9)
    lane = np.abs(np.angle(np.exp(1j * (ph - a0 - 0.08 * np.sin(f * th / 30 + k)))))
    ves += np.exp(-(lane * th / w) ** 2) * np.clip((th - 45) / 60, 0, 1) * rng.uniform(0.2, 0.5)
img = img * (1 - 0.35 * np.clip(ves, 0, 1)[..., None]) + np.array([200, 90, 90]) / 255 * 0.35 * np.clip(ves, 0, 1)[..., None]
# iris
fib = 0.5 + 0.5 * np.sin(ph * 72 + 4 * np.sin(ph * 9)) * np.sin(ph * 31 + 2.0)
crypt = np.clip(np.sin(ph * 17 + 6 * r) * np.sin(r * 14), 0, 1) ** 3
base = IRIS_DEEP + (IRIS_BLUE - IRIS_DEEP) * np.clip(r * 1.15, 0, 1)[..., None]
irs = base * (0.78 + 0.32 * fib[..., None]) * (1 - 0.25 * crypt[..., None])
col = np.exp(-((r - PUPIL_DEG / IRIS_DEG - 0.12) / 0.08) ** 2)[..., None]
irs = irs * (1 - 0.55 * col) + COLLARETTE * 0.55 * col
lim = np.clip((r - 0.86) / 0.12, 0, 1)[..., None]
irs = irs * (1 - 0.85 * lim) + LIMBUS * 0.85 * lim
pup = np.clip((PUPIL_DEG / IRIS_DEG - r) / 0.03 + 0.5, 0, 1)[..., None]
irs = irs * (1 - pup) + np.array([6, 7, 10]) / 255 * pup
inside = np.clip((1.0 - r) / 0.025 + 0.5, 0, 1)[..., None]
img = img * (1 - inside) + irs * inside
Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(TEX)


def lin(c):
    c = np.asarray(c, float)
    return tuple(np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)) + (1.0,)


# ---------------------------------------------------------------- materials
def eye_mat():
    m = bpy.data.materials.new('KO_eyeball')
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image = bpy.data.images.load(TEX)
    nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.35
    b.inputs['Subsurface Weight'].default_value = 0.08
    b.inputs['Subsurface Radius'].default_value = (0.9, 0.4, 0.3)
    b.inputs['Subsurface Scale'].default_value = 0.002
    return m


def cornea_mat():
    m = bpy.data.materials.new('KO_cornea')
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']          # Principled so render.principled() leaves it alone
    b.inputs['Base Color'].default_value = (1, 1, 1, 1)
    b.inputs['Roughness'].default_value = 0.02
    b.inputs['Specular IOR Level'].default_value = 0.7
    b.inputs['Alpha'].default_value = 0.0
    b.inputs['Coat Weight'].default_value = 1.0
    b.inputs['Coat Roughness'].default_value = 0.01
    # alpha 0 removes the base; keep only the glossy reflection via a mix with transparency
    out = nt.nodes['Material Output']
    tr = nt.nodes.new('ShaderNodeBsdfTransparent')
    gl = nt.nodes.new('ShaderNodeBsdfGlossy')
    gl.inputs['Roughness'].default_value = 0.015
    fr = nt.nodes.new('ShaderNodeFresnel')
    fr.inputs['IOR'].default_value = 1.376
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(fr.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(gl.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return m


m_eye, m_cor = eye_mat(), cornea_mat()
coll = face.users_collection[0]


HEAD_BONE = 'DEF-spine.006'      # the deform bone the face is skinned to


def add_eye_bones():
    """Deform bones eye.L / eye.R at the sphere centres under the head deform bone, so the
    character stage's extracted deform skeleton keeps them and the bake's gaze layer rotates
    them (it matches ^eye[._]?[lr]$)."""
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.selected_objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    Ai = arm.matrix_world.inverted()
    for side, nm in ((1, 'L'), (-1, 'R')):
        b = eb.new(f'eye.{nm}')
        h = Ai @ Vector((side * abs(C[0]), C[1], C[2]))
        b.head, b.tail = h, h + Ai.to_3x3() @ Vector((0, -0.02, 0))
        b.roll = 0.0
        b.parent = eb[HEAD_BONE]
        b.use_deform = True
    bpy.ops.object.mode_set(mode='OBJECT')


def make_ball(name, Cw, radius, mat, recess, uvs, bone):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=96, v_segments=64, radius=radius)
    # pole (+Z) -> gaze axis (-Y)
    bmesh.ops.rotate(bm, verts=bm.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, 'X'))
    lay = bm.loops.layers.uv.new('UVMap')
    for v in bm.verts:
        d = v.co.normalized()
        th_ = math.degrees(math.acos(max(-1, min(1, -d.y))))
        if recess and th_ < IRIS_DEG:
            v.co -= d * recess * math.cos(math.radians(th_ / IRIS_DEG * 90)) ** 0.5
    if uvs:
        for f in bm.faces:
            for lp in f.loops:
                d = lp.vert.co.normalized()
                th_ = math.acos(max(-1, min(1, -d.y)))
                ph_ = math.atan2(d.z, d.x)
                rr = th_ / math.pi * 0.5
                lp[lay].uv = (0.5 + rr * math.cos(ph_), 0.5 + rr * math.sin(ph_))
    bmesh.ops.translate(bm, verts=bm.verts, vec=Vector(Cw))
    for f in bm.faces:
        f.smooth = True
    m_ = bpy.data.meshes.new(name)
    bm.to_mesh(m_)
    bm.free()
    m_.materials.append(mat)
    ob = bpy.data.objects.new(name, m_)
    coll.objects.link(ob)
    ob.parent = arm                               # mesh in world coordinates, like Face
    ob.matrix_parent_inverse = arm.matrix_world.inverted()
    vg = ob.vertex_groups.new(name=bone)
    vg.add(list(range(len(m_.vertices))), 1.0, 'REPLACE')
    md = ob.modifiers.new('Armature', 'ARMATURE')
    md.object = arm
    return ob


add_eye_bones()
for side, nm in ((1, 'L'), (-1, 'R')):          # +X = her left
    Cw = (side * abs(C[0]), C[1], C[2])
    make_ball(f'KO_eye_{nm}', Cw, R_eye, m_eye, RECESS, True, f'eye.{nm}')
    make_ball(f'KO_cornea_{nm}', Cw, R_eye + 0.00012, m_cor, 0.0, False, f'eye.{nm}')

bpy.ops.wm.save_as_mainfile(filepath=DST)
print('saved', DST)
