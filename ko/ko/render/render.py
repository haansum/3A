"""Stage 7: render and cut. take.blend + rope frames -> scene.blend, per-shot video, final cut.

One locked arena, one locked shot template, one quality switch (lock['render']); draft and
full differ only in samples/resolution/blur/shot count. Cameras are placed from the sim
(start, KO point, rest position) - never by hand - and move smoothly or not at all.

scene.blend is self-contained (textures packed, rope animation as a mesh cache next to it):
it opens and renders in stock Blender with no pipeline installed.

Frames render to PNG per shot, are encoded per shot, then deleted; a rerun skips frames
that already exist, so a killed render resumes where it stopped.
"""
import glob
import json
import math
import os
import struct
import subprocess

import bpy
import numpy as np
from mathutils import Matrix, Vector

RING = 6.0


def principled(mat):
    """Importer materials for VRM/unlit glTF are emission-only (ignore light). Rebuild them as
    lit Principled materials using the same base texture and alpha."""
    nt = mat.node_tree
    if not nt or any(n.type == 'BSDF_PRINCIPLED' for n in nt.nodes):
        return False
    tex = next((n for n in nt.nodes if n.type == 'TEX_IMAGE' and n.image), None)
    if tex is None:
        return False
    img, interp = tex.image, tex.interpolation
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    t = nt.nodes.new('ShaderNodeTexImage')
    t.image, t.interpolation = img, interp
    nt.links.new(t.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(t.outputs['Alpha'], bsdf.inputs['Alpha'])
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    low = mat.name.lower()
    bsdf.inputs['Roughness'].default_value = 0.45 if 'hair' in low else 0.6
    if any(k in low for k in ('skin', 'face', 'body')):
        bsdf.inputs['Subsurface Weight'].default_value = 0.12
        bsdf.inputs['Subsurface Radius'].default_value = (0.8, 0.35, 0.2)
        bsdf.inputs['Subsurface Scale'].default_value = 0.01
    return True


def mat(name, color, rough=0.6, metal=0.0, emit=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    if emit:
        b.inputs['Emission Color'].default_value = (*color, 1)
        b.inputs['Emission Strength'].default_value = emit
    return m


def add(obj, parent, coll):
    coll.objects.link(obj)
    obj.parent = parent
    return obj


def box(name, size, loc, material, parent, coll):
    me = bpy.data.meshes.new(name)
    sx, sy, sz = (s / 2 for s in size)
    v = [(x, y, z) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(v, [], f)
    me.materials.append(material)
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    return add(ob, parent, coll)


def tube_verts(centers, radius, sides=8):
    """centers (F, N, 3) -> (F, N*sides, 3); cross-sections stay in the plane normal to the
    rope's rest axis (x), which is exact at rest and a mild shear under deflection."""
    ang = np.arange(sides) * 2 * np.pi / sides
    ring = np.stack([np.zeros(sides), np.cos(ang), np.sin(ang)], 1) * radius
    return (centers[:, :, None, :] + ring[None, None]).reshape(centers.shape[0], -1, 3)


def tube_faces(n, sides=8, offset=0):
    f = []
    for i in range(n - 1):
        for k in range(sides):
            a = offset + i * sides + k
            b = offset + i * sides + (k + 1) % sides
            f.append((a, b, b + sides, a + sides))
    return f


def write_pc2(path, frames):
    """Point Cache 2: read by Blender's Mesh Cache modifier."""
    F, N, _ = frames.shape
    with open(path, 'wb') as fh:
        fh.write(struct.pack('<12siiffi', b'POINTCACHE2\0', 1, N, 1.0, 1.0, F))
        fh.write(frames.astype('<f4').tobytes())


def build_arena(lock, fr, root, coll):
    a = lock['arena']
    p = a['rope']
    y0 = a['rope_y']                      # simulated side (she faces it); ring extends to +y
    x0, x1, y1 = -RING / 2, RING / 2, y0 + RING
    m_canvas = mat('KO_canvas', (0.30, 0.34, 0.42), 0.9)
    m_apron = mat('KO_apron', (0.03, 0.03, 0.05), 0.5)
    m_rope = [mat(f'KO_rope{i}', c, 0.55) for i, c in
              enumerate([(0.75, 0.04, 0.04), (0.9, 0.9, 0.9), (0.05, 0.1, 0.6), (0.75, 0.04, 0.04)])]
    m_post = mat('KO_post', (0.6, 0.6, 0.62), 0.3, 1.0)
    m_pad = mat('KO_pad', (0.05, 0.08, 0.5), 0.6)
    m_floor = mat('KO_floor', (0.012, 0.012, 0.015), 0.9)
    box('canvas', (RING + 1.2, RING + 1.2, 0.2), (0, (y0 + y1) / 2, -0.1), m_canvas, root, coll)
    box('apron', (RING + 1.3, RING + 1.3, 0.9), (0, (y0 + y1) / 2, -0.66), m_apron, root, coll)
    box('floor', (60, 60, 0.1), (0, 0, -1.15), m_floor, root, coll)
    for cx in (x0, x1):
        for cy in (y0, y1):
            box('post', (0.12, 0.12, 1.55), (cx - 0.12 * np.sign(-cx), cy - 0.12 * np.sign(-cy), 0.775),
                m_post, root, coll)
            box('pad', (0.26, 0.26, 1.05), (cx, cy, 0.92), m_pad, root, coll)
    hs = list(p['heights'])
    r = p.get('radius', 0.0125) * 1.6      # padded rope cover reads thicker than the core
    # static sides
    for i, z in enumerate(hs):
        sides = [((x0, y1), (x1, y1)), ((x0, y0), (x0, y1)), ((x1, y0), (x1, y1))]
        if not fr['rope'].shape[1]:            # no simulated side in this take: draw it static
            sides.append(((x0, y0), (x1, y0)))
        for (ax, ay), (bx, by) in sides:
            me = bpy.data.meshes.new('rope_static')
            L = math.hypot(bx - ax, by - ay)
            c = np.stack([np.linspace(0, L, 2), np.zeros(2), np.zeros(2)], 1)[None]
            me.from_pydata(tube_verts(c, r)[0].tolist(), [], tube_faces(2))
            me.materials.append(m_rope[i % 4])
            ob = bpy.data.objects.new('rope_static', me)
            ob.location = (ax, ay, z)
            ob.rotation_euler = (0, 0, math.atan2(by - ay, bx - ax))
            add(ob, root, coll)
    # simulated side: one mesh per rope, animated by a mesh cache
    rope = fr['rope']
    caches = []
    if rope.shape[1]:
        nseg = rope.shape[1] // len(hs)
        for i, z in enumerate(hs):
            nodes = rope[:, i * nseg:(i + 1) * nseg]
            ends = np.broadcast_to(np.array([x1, y0, z]), (len(nodes), 1, 3))
            start = np.broadcast_to(np.array([x0, y0, z]), (len(nodes), 1, 3))
            cl = np.concatenate([start, nodes[:, 1:], ends], 1)
            v = tube_verts(cl, r)
            me = bpy.data.meshes.new(f'rope_sim{i}')
            me.from_pydata(v[0].tolist(), [], tube_faces(cl.shape[1]))
            me.materials.append(m_rope[i % 4])
            for poly in me.polygons:
                poly.use_smooth = True
            ob = add(bpy.data.objects.new(f'rope_sim{i}', me), root, coll)
            caches.append((ob, v))
    return caches


def look_at(cam, target):
    d = Vector(target) - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def smooth_path(p, fps, sec=0.6):
    k = max(1, int(sec * fps))
    w = np.hanning(2 * k + 1)
    w /= w.sum()
    pad = np.concatenate([np.repeat(p[:1], k, 0), p, np.repeat(p[-1:], k, 0)])
    return np.stack([np.convolve(pad[:, i], w, 'valid') for i in range(3)], 1)


def make_cameras(lock, fr, root, coll, fps):
    """Shot template. Canonical coords: she starts at the origin facing -y, ropes at y = rope_y."""
    y0 = lock['arena']['rope_y']
    pel, head = fr['pelvis'], fr['head']
    rest = pel[-1]
    mid = np.array([0.0, 0.5 * (pel[0][1] + rest[1]), 0.95])     # centre of the action
    track = smooth_path(0.5 * (pel + head), fps)
    shots = {}

    def cam(name, loc, lens, target=None, follow=None, fstop=2.8):
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        ob = add(bpy.data.objects.new('cam_' + name, cd), root, coll)
        ob.location = loc
        if lock['render']['dof']:
            cd.dof.use_dof = True
            cd.dof.aperture_fstop = fstop
        tgt = add(bpy.data.objects.new('aim_' + name, None), root, coll)
        if follow is not None:
            for f, p in enumerate(follow):
                tgt.location = p
                tgt.keyframe_insert('location', frame=f + 1)
        else:
            tgt.location = target
        c = ob.constraints.new('TRACK_TO')
        c.target, c.track_axis, c.up_axis = tgt, 'TRACK_NEGATIVE_Z', 'UP_Y'
        cd.dof.focus_object = tgt
        shots[name] = ob
        return ob

    cam('live', (5.6, mid[1] + 1.0, 2.6), 50, target=mid + [0, 0, -0.3])
    cam('tight', (2.3, mid[1] + 1.6, 1.0), 60, follow=track)
    cam('referee', (-1.6, y0 + 2.4, 1.6), 50, follow=track)
    cam('opponent', (0.5, y0 + 0.25, 1.5), 24, follow=track)
    orb = cam('orbit', (3.0, y0 + 0.4, 1.3), 85, follow=np.repeat(rest[None] + [0, 0, 0.2], len(pel), 0))
    n = len(pel)
    for f in (0, n - 1):                       # quarter orbit around the rest position, eased
        a = math.radians(-20 + 90 * f / max(1, n - 1))
        orb.location = (rest[0] + 3.2 * math.cos(a), rest[1] + 3.2 * math.sin(a), 1.3)
        orb.keyframe_insert('location', frame=f + 1)
    return shots


def lights(root, coll):
    for i, (x, y, col, w) in enumerate([(-2, -2, (1, .96, .9), 420), (2, -2, (1, .96, .9), 420),
                                        (-2, 2.5, (.9, .95, 1), 320), (2, 2.5, (.9, .95, 1), 320),
                                        (0, 0, (1, 1, 1), 220)]):
        ld = bpy.data.lights.new(f'truss{i}', 'AREA')
        ld.energy, ld.color, ld.size = w, col, 1.6
        ld.spread = math.radians(110)
        ob = add(bpy.data.objects.new(f'truss{i}', ld), root, coll)
        ob.location = (x, y, 5.0)
    w = bpy.data.worlds.new('KO_world')
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.004, 0.004, 0.006, 1)
    bpy.context.scene.world = w


def encode(frames_glob, out, fps, lossless):
    codec = ['-c:v', 'ffv1', '-level', '3'] if lossless else \
        ['-c:v', 'libx264', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart']
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(fps), '-pattern_type',
                    'glob', '-i', frames_glob, *codec, out], check=True)


def run(lock, bake_dir, sim_dir, out_dir):
    R = lock['render']
    fps = R['fps']
    fr = np.load(os.path.join(bake_dir, 'frames.npz'))
    skel_dir = os.path.dirname(os.path.dirname(bake_dir))
    bpy.ops.wm.open_mainfile(filepath=os.path.join(bake_dir, 'take.blend'))
    sc = bpy.context.scene
    n = len(fr['t'])
    sc.frame_start, sc.frame_end = 1, n
    converted = [m.name for m in bpy.data.materials if principled(m)]

    lockc = json.load(open(os.path.join(bake_dir, 'take.lock.json'))) if os.path.exists(
        os.path.join(bake_dir, 'take.lock.json')) else lock
    from .. import manifest
    skel = json.load(open(os.path.join(manifest.stage_dir(lock, 'character'), 'skeleton.json')))
    tc = skel['to_canonical']
    coll = bpy.data.collections.new('KO_arena')
    sc.collection.children.link(coll)
    root = bpy.data.objects.new('KO_canonical', None)     # canonical sim frame -> blender world
    coll.objects.link(root)
    root.matrix_world = (Matrix.Translation(Vector(tc['origin'])) @ Matrix.Rotation(tc['yaw'], 4, 'Z')
                         @ Matrix.Scale(1.0 / tc['scale'], 4))
    caches = build_arena(lock, fr, root, coll)
    for i, (ob, v) in enumerate(caches):
        pc = os.path.join(out_dir, f'rope{i}.pc2')
        write_pc2(pc, v)
        md = ob.modifiers.new('sim', 'MESH_CACHE')
        md.cache_format, md.filepath = 'PC2', pc
        md.frame_start, md.forward_axis, md.up_axis = 1, 'POS_Y', 'POS_Z'
    lights(root, coll)
    shots = make_cameras(lock, fr, root, coll, fps)

    sc.render.engine = R['engine']
    sc.render.resolution_x, sc.render.resolution_y = R['res']
    sc.render.resolution_percentage = 100
    sc.render.fps = fps
    sc.render.image_settings.file_format = 'PNG'
    sc.render.use_motion_blur = bool(R['motion_blur'])
    sc.cycles.samples = R['samples']
    sc.cycles.use_adaptive_sampling = True
    try:
        sc.cycles.use_denoising = True
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        sc.cycles.use_denoising = False
    sc.cycles.device = 'CPU'
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.camera = shots[R['shots'][0]]
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, 'scene.blend'), compress=True,
                                relative_remap=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile()

    seg = []
    t_ko = lock['strike']['t'] if lock.get('strike') else 0
    for si, name in enumerate(R['shots']):
        sc.camera = shots[name]
        fdir = os.path.join(out_dir, 'frames', name)
        os.makedirs(fdir, exist_ok=True)
        # live shot runs the whole take; replays start just before the hit
        f0 = 1 if si == 0 else max(1, int((t_ko - 0.5) * fps))
        for f in range(f0, n + 1):
            fp = os.path.join(fdir, f'{f:05d}.png')
            if os.path.exists(fp) and os.path.getsize(fp) > 0:
                continue
            sc.frame_set(f)
            sc.render.filepath = fp
            bpy.ops.render.render(write_still=True)
        vid = os.path.join(out_dir, f'{si:02d}_{name}.' + ('mkv' if lock['quality'] == 'full' else 'mp4'))
        encode(os.path.join(fdir, '*.png'), vid, fps, lock['quality'] == 'full')
        if si == 0:                 # contact sheet for review before anyone watches the video
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-pattern_type', 'glob', '-i',
                            os.path.join(fdir, '*.png'), '-vf',
                            f"select='not(mod(n,{max(1, n // 12)}))',scale=480:-1,tile=4x3",
                            '-frames:v', '1', os.path.join(out_dir, 'contact_sheet.png')], check=True)
        for p in glob.glob(os.path.join(fdir, '*.png')):
            os.remove(p)
        seg.append(vid)
    lst = os.path.join(out_dir, 'cut.txt')
    open(lst, 'w').write(''.join(f"file '{os.path.basename(s)}'\n" for s in seg))
    cut = os.path.join(out_dir, f"{lock['take']}_{lock['quality']}_{lock['hash']}.mp4")
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
                    '-c:v', 'libx264', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags',
                    '+faststart', cut], check=True)
    json.dump({'cut': os.path.basename(cut), 'shots': R['shots'], 'frames': n,
               'materials_rebuilt_as_principled': converted, 'manifest_hash': lock['hash']},
              open(os.path.join(out_dir, 'render.json'), 'w'), indent=1)
    print('[render] cut ->', cut)
