"""Minimal Source-engine model reader -> .blend (written for this project from the published
file-format layouts on the Valve Developer wiki; no third-party importer code).

    python3 -I tools/source_import.py MODEL.mdl MATERIALS_ROOT OUT.blend [--scale 0.0254]

Reads MDL v48/v49 (bones, textures, body parts / models / meshes, flexes), VVD v4 (vertices,
weights, fixups) and VTX v7 (triangle strips, LOD 0) and builds:
  - an armature at the bind pose (from each bone's poseToBone matrix),
  - one mesh per body-part model, with UVs, normals, bone-weight vertex groups and one material
    per MDL texture (base texture from the matching VMT/VTF: DXT1/3/5, RGB(A)888(8), BGR(A)),
  - shape keys from the MDL flexes (vertex animations), named after the flex descriptors.
Source units are inches; --scale converts to metres. Character facing +X in Source becomes
facing -Y here (the pipeline's convention) by a -90 deg yaw.
"""
import math
import os
import re
import struct
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
mdl_path, mat_root, out = a[:3]
SCALE = float(a[a.index('--scale') + 1]) if '--scale' in a else 0.0254
base = os.path.splitext(mdl_path)[0]


def find(ext):
    d, b = os.path.split(base)
    for f in os.listdir(d):
        if f.lower() == (b + ext).lower():
            return os.path.join(d, f)
    raise FileNotFoundError(base + ext)


M = open(mdl_path, 'rb').read()
V = open(find('.vvd'), 'rb').read()
X = open(find('.dx90.vtx'), 'rb').read()


def i32(b, o):
    return struct.unpack_from('<i', b, o)[0]


def cstr(b, o):
    e = b.index(b'\0', o)
    return b[o:e].decode('latin-1')


# ------------------------------------------------------------------ MDL header
ver = i32(M, 4)
nbones, boneidx = i32(M, 156), i32(M, 160)
ntex, texidx = i32(M, 204), i32(M, 208)
ncd, cdidx = i32(M, 212), i32(M, 216)
nskinref, nskinfam, skinidx = i32(M, 220), i32(M, 224), i32(M, 228)
nbp, bpidx = i32(M, 232), i32(M, 236)
# flexdesc lives further down the v48/49 header
nflexdesc, flexdescidx = i32(M, 0x110 - 0x10 + 0x10 - 0x10 + 0x110 - 0x110 + 0), 0  # placeholder

# Full field list after bodypartindex (studiohdr_t, v48/49), to reach the flex descriptors:
o = 240
fields = ['numlocalattachments', 'localattachmentindex', 'numlocalnodes', 'localnodeindex',
          'localnodenameindex', 'numflexdesc', 'flexdescindex', 'numflexcontrollers',
          'flexcontrollerindex', 'numflexrules', 'flexruleindex', 'numikchains', 'ikchainindex',
          'nummouths', 'mouthindex', 'numlocalposeparameters', 'localposeparamindex',
          'surfacepropindex', 'keyvalueindex', 'keyvaluesize', 'numlocalikautoplaylocks',
          'localikautoplaylockindex']
H = {}
for f in fields:
    H[f] = i32(M, o)
    o += 4
nflexdesc, flexdescidx = H['numflexdesc'], H['flexdescindex']
flexnames = [cstr(M, flexdescidx + k * 4 + i32(M, flexdescidx + k * 4)) for k in range(nflexdesc)]

bones = []
for k in range(nbones):
    b0 = boneidx + k * 216
    name = cstr(M, b0 + i32(M, b0))
    parent = i32(M, b0 + 4)
    p2b = struct.unpack_from('<12f', M, b0 + 96)
    bones.append((name, parent, p2b))

textures = []
for k in range(ntex):
    t0 = texidx + k * 64
    textures.append(cstr(M, t0 + i32(M, t0)))
cdpaths = [cstr(M, i32(M, cdidx + k * 4)) for k in range(ncd)]
skinref = struct.unpack_from(f'<{nskinref}h', M, skinidx) if nskinref else ()

# ------------------------------------------------------------------ VVD
nlods = i32(V, 12)
nverts0 = i32(V, 16)
nfix, fixidx, vdata = i32(V, 48), i32(V, 52), i32(V, 56)
raw = np.frombuffer(V, dtype=np.dtype([('w', '<f4', 3), ('b', 'i1', 3), ('n', 'u1'),
                                        ('p', '<f4', 3), ('nrm', '<f4', 3), ('uv', '<f4', 2)]),
                    count=(len(V) - vdata) // 48, offset=vdata)
if nfix:
    order = []
    for k in range(nfix):
        lod, src, num = struct.unpack_from('<3i', V, fixidx + k * 12)
        if lod >= 0:
            order.extend(range(src, src + num))
    verts = raw[np.array(order)]
else:
    verts = raw[:nverts0]

# ------------------------------------------------------------------ VTX + mesh assembly
vt_nbp, vt_bpo = i32(X, 28), i32(X, 32)


def strip_group_size():
    """v49 models from newer compilers carry 8 extra bytes (topology) per strip group/strip."""
    bp0 = vt_bpo
    m0 = bp0 + i32(X, bp0 + 4)
    l0 = m0 + i32(X, m0 + 4)
    me0 = l0 + i32(X, l0 + 4)
    sg0 = me0 + i32(X, me0 + 4)
    nv, vo, ni, io_, ns, so = struct.unpack_from('<6i', X, sg0)
    for size in (25, 33):
        # the next strip group (if any) or sane offsets decide; check the strips' own header
        st = sg0 + so
        sni = i32(X, st)
        if 0 < sni <= ni and 0 <= so < len(X):
            return size, (27 if size == 25 else 35)
    return 25, 27


SG, ST = strip_group_size()
fig = []        # per model: dict(name, faces[], mat[])
mdl_vstart = 0
for bpi in range(nbp):
    bp = bpidx + bpi * 16
    bp_name = cstr(M, bp + i32(M, bp))
    nmodels, mi0 = i32(M, bp + 4), i32(M, bp + 12)
    xbp = vt_bpo + bpi * 8
    xnm, xmo = i32(X, xbp), i32(X, xbp + 4)
    for mi in range(nmodels):
        md = bp + mi0 + mi * 148
        mname = M[md:md + 64].split(b'\0')[0].decode('latin-1')
        nmesh, meshidx = i32(M, md + 72), i32(M, md + 76)
        nmv, vindex = i32(M, md + 80), i32(M, md + 84)
        vstart = vindex // 48
        xm = xbp + xmo + mi * 8
        xl = xm + i32(X, xm + 4)                       # LOD 0
        xnmesh, xmeo = i32(X, xl), i32(X, xl + 4)
        faces, fmat = [], []
        flexes = []
        for me in range(nmesh):
            ms = md + meshidx + me * 116
            mat, vofs = i32(M, ms), i32(M, ms + 12)
            nflex, flexidx = i32(M, ms + 16), i32(M, ms + 20)
            for fk in range(nflex):
                fo = ms + flexidx + fk * 60
                fdesc = i32(M, fo)
                numverts, vertindex = i32(M, fo + 28), i32(M, fo + 32)
                vatype = M[fo + 44] if fo + 44 < len(M) else 0
                vsz = 16 if vatype == 0 else 18
                for vi in range(numverts):
                    va = fo + vertindex + vi * vsz
                    idx = struct.unpack_from('<H', M, va)[0]
                    dx, dy, dz = np.frombuffer(M[va + 4:va + 10], dtype='<f2').astype(np.float32)
                    flexes.append((fdesc, vstart + vofs + idx, (dx, dy, dz)))
            xme = xl + xmeo + me * 9
            nsg, sgo = i32(X, xme), i32(X, xme + 4)
            for g in range(nsg):
                sg = xme + sgo + g * SG
                nv, vo, ni, io_, ns, so = struct.unpack_from('<6i', X, sg)
                sgv = [struct.unpack_from('<H', X, sg + vo + k * 9 + 4)[0] for k in range(nv)]
                idx = struct.unpack_from(f'<{ni}H', X, sg + io_)
                for s in range(ns):
                    sh = sg + so + s * ST
                    sni, sio = i32(X, sh), i32(X, sh + 4)
                    flags = X[sh + 18]
                    seq = idx[sio:sio + sni]
                    if flags & 2:      # strip
                        for k in range(len(seq) - 2):
                            t = (seq[k], seq[k + 1], seq[k + 2]) if k % 2 == 0 else (seq[k + 1], seq[k], seq[k + 2])
                            faces.append(tuple(vstart + vofs + sgv[i] for i in t))
                            fmat.append(mat)
                    else:              # triangle list
                        for k in range(0, len(seq) - 2, 3):
                            faces.append(tuple(vstart + vofs + sgv[i] for i in (seq[k], seq[k + 1], seq[k + 2])))
                            fmat.append(mat)
        fig.append({'name': f'{bp_name}_{mname}'.strip('_') or bp_name, 'faces': faces, 'mat': fmat,
                    'flex': flexes})

# ------------------------------------------------------------------ textures (VMT -> VTF)


def find_vmt(tex):
    cands = [os.path.join(mat_root, p, tex + '.vmt') for p in cdpaths] + [os.path.join(mat_root, tex + '.vmt')]
    for c in cands:
        c2 = c.replace('\\', '/')
        d, f = os.path.split(c2)
        if os.path.isdir(d):
            for g in os.listdir(d):
                if g.lower() == f.lower():
                    return os.path.join(d, g)
    # case-insensitive walk
    tl = os.path.basename(tex).lower() + '.vmt'
    for r, _, fs in os.walk(mat_root):
        for g in fs:
            if g.lower() == tl:
                return os.path.join(r, g)
    return None


def vmt_params(path):
    s = open(path, encoding='latin-1', errors='ignore').read()
    return {k.lower(): v for k, v in re.findall(r'"?\$(\w+)"?\s+"?([^"\n]+)"?', s)}


def resolve_vtf(name):
    name = name.strip().replace('\\', '/')
    tl = name.lower().split('/')
    cur = mat_root
    for part in tl[:-1]:
        nxt = [g for g in os.listdir(cur) if g.lower() == part] if os.path.isdir(cur) else []
        if not nxt:
            cur = None
            break
        cur = os.path.join(cur, nxt[0])
    if cur and os.path.isdir(cur):
        for g in os.listdir(cur):
            if g.lower() == tl[-1] + '.vtf':
                return os.path.join(cur, g)
    return None


def _565(c):
    r = ((c >> 11) & 31) * 255 // 31
    g = ((c >> 5) & 63) * 255 // 63
    b = (c & 31) * 255 // 31
    return np.stack([r, g, b], -1).astype(np.int32)


def dxt(data, w, h, kind):
    bw, bh = max(1, (w + 3) // 4), max(1, (h + 3) // 4)
    bs = 8 if kind == 1 else 16
    blk = np.frombuffer(data[:bw * bh * bs], dtype=np.uint8).reshape(bh * bw, bs)
    col = blk[:, -8:]
    c0 = col[:, 0].astype(np.int32) | (col[:, 1].astype(np.int32) << 8)
    c1 = col[:, 2].astype(np.int32) | (col[:, 3].astype(np.int32) << 8)
    p0, p1 = _565(c0), _565(c1)
    four = (kind != 1) | (c0 > c1)
    p2 = np.where(four[:, None], (2 * p0 + p1) // 3, (p0 + p1) // 2)
    p3 = np.where(four[:, None], (p0 + 2 * p1) // 3, 0)
    pal = np.stack([p0, p1, p2, p3], 1)                         # N,4,3
    bits = col[:, 4:8].astype(np.uint32)
    bits = bits[:, 0] | (bits[:, 1] << 8) | (bits[:, 2] << 16) | (bits[:, 3] << 24)
    sel = (bits[:, None] >> (2 * np.arange(16, dtype=np.uint32))) & 3   # N,16
    rgb = np.take_along_axis(pal, sel[:, :, None].astype(np.int64).repeat(3, 2), 1)  # N,16,3
    alpha = np.full((len(blk), 16), 255, np.int32)
    if kind == 1:
        alpha = np.where((~four[:, None]) & (sel == 3), 0, 255)
    elif kind == 3:
        ab = blk[:, :8]
        nib = np.stack([ab & 15, ab >> 4], -1).reshape(len(blk), 16)
        alpha = nib.astype(np.int32) * 17
    elif kind == 5:
        a0, a1 = blk[:, 0].astype(np.int32), blk[:, 1].astype(np.int32)
        ab = blk[:, 2:8].astype(np.uint64)
        abits = sum(ab[:, k] << np.uint64(8 * k) for k in range(6))
        asel = ((abits[:, None] >> (3 * np.arange(16, dtype=np.uint64))) & np.uint64(7)).astype(np.int64)
        ap = np.zeros((len(blk), 8), np.int32)
        ap[:, 0], ap[:, 1] = a0, a1
        big = a0 > a1
        for k in range(2, 8):
            ap[:, k] = np.where(big, ((8 - k) * a0 + (k - 1) * a1) // 7, 0)
        for k in range(2, 6):
            ap[:, k] = np.where(big, ap[:, k], ((6 - k) * a0 + (k - 1) * a1) // 5)
        ap[:, 6] = np.where(big, ap[:, 6], 0)
        ap[:, 7] = np.where(big, ap[:, 7], 255)
        alpha = np.take_along_axis(ap, asel, 1)
    px = np.concatenate([rgb, alpha[:, :, None]], 2).reshape(bh, bw, 4, 4, 4)
    img = px.transpose(0, 2, 1, 3, 4).reshape(bh * 4, bw * 4, 4)[:h, :w]
    return img.astype(np.uint8)


def read_vtf(path):
    b = open(path, 'rb').read()
    if b[:4] != b'VTF\0':
        return None
    vmaj, vmin = struct.unpack_from('<2i', b, 4)
    hsize = i32(b, 12)
    w, h = struct.unpack_from('<2H', b, 16)
    fmt = i32(b, 52)
    mips = b[56]
    lfmt = i32(b, 57)
    lw, lh = b[61], b[62]
    frames = struct.unpack_from('<H', b, 24)[0]
    bpp = {0: 4, 1: 4, 2: 3, 3: 3, 12: 4, 13: 0.5, 14: 1, 15: 1, 16: 4}
    if fmt not in bpp:
        return None
    # the data block is mips from smallest to largest; the largest is last
    def size(fm, ww, hh):
        if fm in (13, 14, 15):
            return max(1, (ww + 3) // 4) * max(1, (hh + 3) // 4) * (8 if fm == 13 else 16)
        return int(ww * hh * bpp[fm])
    full = size(fmt, w, h) * max(1, frames)
    start = len(b) - full
    data = b[start:start + size(fmt, w, h)]
    if fmt == 13:
        img = dxt(data, w, h, 1)
    elif fmt == 14:
        img = dxt(data, w, h, 3)
    elif fmt == 15:
        img = dxt(data, w, h, 5)
    else:
        arr = np.frombuffer(data, np.uint8).reshape(h, w, int(bpp[fmt]))
        if fmt in (2,):
            img = np.concatenate([arr, np.full((h, w, 1), 255, np.uint8)], 2)
        elif fmt in (3,):
            img = np.concatenate([arr[..., ::-1], np.full((h, w, 1), 255, np.uint8)], 2)
        elif fmt in (12, 16):
            img = arr[..., [2, 1, 0, 3]]
        else:
            img = arr
    return img


img_cache = {}


def image_for(vtf_name, label):
    p = resolve_vtf(vtf_name)
    if not p:
        return None
    if p in img_cache:
        return img_cache[p]
    arr = read_vtf(p)
    if arr is None:
        return None
    h, w = arr.shape[:2]
    im = bpy.data.images.new(label, w, h, alpha=True)
    im.pixels.foreach_set((arr[::-1].astype(np.float32) / 255.0).ravel())
    im.pack()
    img_cache[p] = im
    return im


bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
mats = []
for t in textures:
    m = bpy.data.materials.new(os.path.basename(t))
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes['Principled BSDF']
    vmt = find_vmt(t)
    params = vmt_params(vmt) if vmt else {}
    bt = params.get('basetexture')
    if bt:
        im = image_for(bt, os.path.basename(bt))
        if im is not None:
            tn = nt.nodes.new('ShaderNodeTexImage')
            tn.image = im
            nt.links.new(tn.outputs['Color'], bsdf.inputs['Base Color'])
            if params.get('translucent') == '1' or params.get('alphatest') == '1':
                nt.links.new(tn.outputs['Alpha'], bsdf.inputs['Alpha'])
                try:
                    m.blend_method = 'HASHED'
                except Exception:
                    pass
    bsdf.inputs['Roughness'].default_value = 0.6
    m['vmt'] = vmt or ''
    mats.append(m)

# ------------------------------------------------------------------ armature
R = Matrix.Rotation(math.radians(-90), 4, 'Z') @ Matrix.Scale(SCALE, 4)
arm_d = bpy.data.armatures.new('skeleton')
arm = bpy.data.objects.new('skeleton', arm_d)
sc.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
world = []
for name, parent, p2b in bones:
    m34 = np.array(p2b, dtype=np.float64).reshape(3, 4)
    m4 = np.eye(4)
    m4[:3, :] = m34
    bw_ = np.linalg.inv(m4)                       # bone-to-model = inverse(pose-to-bone)
    world.append(bw_)
for k, (name, parent, p2b) in enumerate(bones):
    eb = arm_d.edit_bones.new(name)
    Mw = R @ Matrix(world[k].tolist())
    eb.head = Mw.to_translation()
    kids = [j for j, (_, p, _) in enumerate(bones) if p == k]
    if kids:
        tgt = sum(((R @ Matrix(world[j].tolist())).to_translation() for j in kids), Vector()) / len(kids)
        ln = max((tgt - eb.head).length, 0.01)
    else:
        ln = 0.03
    # Source bones point along +X of their frame
    ax = (Mw.to_3x3() @ Vector((1, 0, 0))).normalized()
    eb.tail = eb.head + ax * ln
    eb.align_roll(Mw.to_3x3() @ Vector((0, 0, 1)))
for k, (name, parent, _) in enumerate(bones):
    if parent >= 0:
        arm_d.edit_bones[name].parent = arm_d.edit_bones[bones[parent][0]]
bpy.ops.object.mode_set(mode='OBJECT')

# ------------------------------------------------------------------ meshes
P = np.array([(R @ Vector(v.tolist())).to_tuple() for v in verts['p']])
N = np.array([(R.to_3x3() @ Vector(v.tolist())).normalized().to_tuple() for v in verts['nrm']])
UV = verts['uv'].copy()
UV[:, 1] = 1.0 - UV[:, 1]
report = []
for part in fig:
    if not part['faces']:
        continue
    used = sorted({i for f in part['faces'] for i in f})
    remap = {g: l for l, g in enumerate(used)}
    me = bpy.data.meshes.new(part['name'])
    me.from_pydata(P[used].tolist(), [], [tuple(remap[i] for i in f) for f in part['faces']])
    mused = sorted(set(part['mat']))
    mslot = {m_: s for s, m_ in enumerate(mused)}
    for m_ in mused:
        me.materials.append(mats[skinref[m_] if skinref and m_ < len(skinref) else m_])
    me.polygons.foreach_set('material_index', [mslot[m_] for m_ in part['mat']])
    uvl = me.uv_layers.new(name='UVMap')
    loop_v = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get('vertex_index', loop_v)
    gl = np.array(used)[loop_v]
    uvl.data.foreach_set('uv', UV[gl].ravel())
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    try:
        me.normals_split_custom_set_from_vertices(N[used].tolist())
    except Exception:
        pass
    ob = bpy.data.objects.new(part['name'], me)
    sc.collection.objects.link(ob)
    ob.parent = arm
    md = ob.modifiers.new('Armature', 'ARMATURE')
    md.object = arm
    groups = {}
    for l, g in enumerate(used):
        v = verts[g]
        for j in range(int(v['n'])):
            bi = int(v['b'][j])
            w = float(v['w'][j])
            if w <= 0 or bi < 0 or bi >= len(bones):
                continue
            nm = bones[bi][0]
            if nm not in groups:
                groups[nm] = ob.vertex_groups.new(name=nm)
            groups[nm].add([l], w, 'REPLACE')
    # shape keys from flexes
    fl = [(fd, remap[g], d) for fd, g, d in part['flex'] if g in remap]
    if fl:
        ob.shape_key_add(name='Basis', from_mix=False)
        byname = {}
        for fd, l, d in fl:
            byname.setdefault(flexnames[fd] if fd < len(flexnames) else f'flex{fd}', []).append((l, d))
        for nm, lst in byname.items():
            sk = ob.shape_key_add(name=nm, from_mix=False)
            for l, d in lst:
                sk.data[l].co = sk.data[l].co + R.to_3x3() @ Vector((float(d[0]), float(d[1]), float(d[2])))
    report.append((part['name'], len(used), len(part['faces']), len(mused), len(fl)))

bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(out), compress=True)
print('[source_import] mdl v%d bones %d textures %d bodyparts %d flexdesc %d sg/strip %d/%d'
      % (ver, nbones, ntex, nbp, nflexdesc, SG, ST))
for r in report:
    print('  mesh %-40s verts %6d tris %6d mats %d flexverts %d' % r)
print('  textures:', textures)
print('  images loaded:', len(img_cache))
