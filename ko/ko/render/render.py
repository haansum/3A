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
from mathutils import Matrix, Quaternion, Vector

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


def load_scene_arena(a, root, coll):
    """Owner-supplied arena (e.g. a gym .blend): append every object of one scene and place it
    so its canvas surface sits at the sim canvas (z = 0) and its ring centre on the sim ring
    centre. The sim itself still uses the arena preset's numbers; this is the picture only."""
    sa = a['scene']
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), sa['file'])
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.scenes = [sa.get('scene_name', src.scenes[0])]
    scn = dst.scenes[0]
    gym_root = bpy.data.objects.new('arena_scene_root', None)
    add(gym_root, root, coll)
    cx, cy = sa.get('ring_center', [0.0, 0.0])
    gym_root.location = (-cx + sa.get('offset', [0, 0])[0], -cy + sa.get('offset', [0, 0])[1],
                         -float(sa['canvas_top']))
    gym_root.rotation_euler = (0, 0, math.radians(sa.get('yaw_deg', 0.0)))
    n = 0
    for o in scn.objects:
        if o.type == 'CAMERA':
            continue
        if o.name not in coll.objects:
            coll.objects.link(o)
        if o.parent is None:
            o.parent = gym_root
        n += 1
    # overhead geometry (ceiling, beams, fixtures) above `hide_above` m over the canvas: hidden
    # from render so high camera positions see the ring, not the ceiling tiles
    ha = sa.get('hide_above')
    if ha is not None:
        bpy.context.view_layer.update()
        for o in scn.objects:
            if o.type == 'MESH':
                zmin = min((o.matrix_world @ Vector(c)).z for c in o.bound_box)   # already canvas-relative (parented)
                if zmin > ha:
                    o.visible_camera = False      # still blocks and bounces light
    print(f'[render] arena: hid overhead geometry from camera above {ha} m')
    for name in sa.get('hide', []):
        if name in bpy.data.objects:
            bpy.data.objects[name].hide_render = True
    bpy.data.scenes.remove(scn)
    print(f'[render] arena scene: {n} objects from {sa["file"]}')
    return []


def build_arena(lock, fr, root, coll):
    a = lock['arena']
    if a.get('scene'):
        return load_scene_arena(a, root, coll)
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


def refine_face_cam(sc, cam_ob, root, fps, n, every=3, dist=0.82):
    """Occlusion-aware face shot: at sampled frames, try camera directions around where her
    face points and keep the clear view (ray-cast against the rendered meshes, to both eyes)
    nearest straight-on and nearest the previous choice; then smooth and key it.
    Eyes come from the eye.L / eye.R deform bones (else a point in front of the head)."""
    import math as _m
    # the animated deform skeleton, never a static control rig that also carries eye bones
    # (2026-11-17: the Genesis control rig was picked, so the face camera aimed at where her head
    # was before the strike on every frame)
    cands = [o for o in bpy.data.objects if o.type == 'ARMATURE' and 'eye.L' in o.pose.bones]
    cands.sort(key=lambda o: (o.name != 'KO_skeleton', not (o.animation_data and o.animation_data.action)))
    arm = cands[0] if cands else None
    if arm is None or cam_ob is None:
        return None
    hb = next((b for b in ('DEF-spine.006', 'head', 'DEF-head') if b in arm.pose.bones), None)
    Rw = root.matrix_world
    Ri = Rw.inverted()
    chosen, prev = {}, None
    report = {'sampled': 0, 'clear': 0}
    for f in range(1, n + 1, every):
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        eL = arm.matrix_world @ arm.pose.bones['eye.L'].head
        eR = arm.matrix_world @ arm.pose.bones['eye.R'].head
        eye = (eL + eR) / 2
        if hb:   # head rotation since rest; at rest she faces -Y with +Z up
            pb_ = arm.pose.bones[hb]
            hm = (arm.matrix_world @ pb_.matrix @ pb_.bone.matrix_local.inverted()).to_3x3()
        else:
            hm = Matrix.Identity(3)
        fwd = (hm @ Vector((0, -1, 0))).normalized()
        up = (hm @ Vector((0, 0, 1))).normalized()
        if abs(fwd.dot(up)) > 0.9:
            up = Vector((0, 0, 1))
        best, best_s = None, 1e9
        for yaw in (0, 25, -25, 50, -50, 75, -75, 100, -100):
            for tilt in (0, 25, 50, 70):
                d = Matrix.Rotation(_m.radians(yaw), 3, up) @ fwd
                ax = d.cross(up)
                if ax.length > 1e-6:
                    d = Matrix.Rotation(_m.radians(tilt), 3, ax.normalized()) @ d
                d.normalize()
                cpos = eye + d * dist
                if cpos.z < 0.1:
                    continue
                seen = 0
                for e_ in (eL, eR):
                    v = cpos - e_
                    L_ = v.length
                    hit, loc, *_ = sc.ray_cast(dg, e_ + v.normalized() * 0.035, v.normalized(), distance=L_)
                    seen += not hit
                if seen == 0:
                    continue
                # both eyes clear beats one; then nearest straight-on, then nearest previous
                s_ = (2 - seen) * 4.0 + (abs(yaw) + tilt) / 50.0 + (0 if prev is None else 3.0 * (d - prev).length)
                if s_ < best_s:
                    best, best_s = d, s_
        report['sampled'] += 1
        if best is not None:
            report['clear'] += 1
            prev = best
        if prev is not None:
            chosen[f] = (Ri @ (eye + prev * dist), Ri @ eye, Ri.to_3x3() @ up)
    if not chosen:
        return report
    fs = np.array(sorted(chosen))
    P = np.array([chosen[f][0][:] for f in fs])
    A = np.array([chosen[f][1][:] for f in fs])
    allf = np.arange(1, n + 1)
    Pi = np.stack([np.interp(allf, fs, P[:, k]) for k in range(3)], 1)
    Ai = np.stack([np.interp(allf, fs, A[:, k]) for k in range(3)], 1)
    U = np.array([chosen[f][2][:] for f in fs])
    Ui = np.stack([np.interp(allf, fs, U[:, k]) for k in range(3)], 1)
    Pi = smooth_path(Pi, fps, 0.3)
    Ai = smooth_path(Ai, fps, 0.12)
    Ui = smooth_path(Ui, fps, 0.3)
    cam_ob.animation_data_clear()
    aim = cam_ob.constraints['Track To'].target if 'Track To' in cam_ob.constraints else None
    # explicit orientation instead of Track To: the frame's up follows the top of her head, so a
    # face seen from straight above (lying on her back) is upright in frame, not upside down
    for c_ in list(cam_ob.constraints):
        cam_ob.constraints.remove(c_)
    cam_ob.rotation_mode = 'QUATERNION'
    for f in allf:
        P_, A_, U_ = Vector(Pi[f - 1]), Vector(Ai[f - 1]), Vector(Ui[f - 1])
        fw = (A_ - P_).normalized()
        upc = (U_ - fw * U_.dot(fw))
        if upc.length < 1e-4:
            upc = Vector((0, 0, 1)) - fw * fw.z
        upc.normalize()
        rt = fw.cross(upc).normalized()
        R_ = Matrix((rt, upc, -fw)).transposed()
        cam_ob.location = tuple(P_)
        cam_ob.rotation_quaternion = R_.to_quaternion()
        cam_ob.keyframe_insert('location', frame=int(f))
        cam_ob.keyframe_insert('rotation_quaternion', frame=int(f))
        if aim is not None:
            aim.location = tuple(A_)
            aim.keyframe_insert('location', frame=int(f))
        if cam_ob.data.dof.use_dof and aim is not None:
            cam_ob.data.dof.focus_object = aim
    cam_ob.data.lens = 50                       # owner 2026-11-12: slightly wider than 60 mm / 0.62 m
    return report


def snap_contact(sc, root, frame, pt, dvec, group='DEF-spine.006', radius=0.035, wmin=0.5):
    """First point of her rendered head skin that a prop travelling along dvec through pt meets.

    The sim's strike point is head COM + an offset on the convex hull: right for the torque arm,
    but several cm off the skinned mesh's chin. For the picture, slide it onto the skin: among
    head-weighted vertices (Body, Face) within `radius` of the strike line, the one met first
    (smallest projection on dvec). Falls back to the nearest head vertex. Root-local coords.
    Returns (point, shift_m)."""
    sc.frame_set(int(round(frame)))
    dg = bpy.context.evaluated_depsgraph_get()
    inv = root.matrix_world.inverted()
    P = []
    groups = [group] if isinstance(group, str) else list(group)
    import re as _re
    skip = _re.compile(r'hair|brow|lash|eyelash|beard|KO_prop|glove_|shin_|mma', _re.I)
    for ob in [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render
               and not skip.search(o.name) and any(g in o.vertex_groups for g in groups)]:
        gis = {ob.vertex_groups[g].index for g in groups if g in ob.vertex_groups}
        sel = [v.index for v in ob.data.vertices
               if sum(g.weight for g in v.groups if g.group in gis) >= wmin]
        saved = [(md, md.show_viewport) for md in ob.modifiers if md.type != 'ARMATURE']
        for md, _ in saved:
            md.show_viewport = False
        dg.update()
        me = ob.evaluated_get(dg).to_mesh()
        mw = inv @ ob.matrix_world
        if len(me.vertices) == len(ob.data.vertices):
            P += [mw @ me.vertices[i].co for i in sel]
        ob.evaluated_get(dg).to_mesh_clear()
        for md, s in saved:
            md.show_viewport = s
    dg.update()
    if not P:
        return pt, 0.0
    A = np.array([p[:] for p in P])
    d = np.array(dvec[:]) / max(dvec.length, 1e-9)
    rel = A - np.array(pt[:])
    s = rel @ d
    lat = np.linalg.norm(rel - np.outer(s, d), axis=1)
    near = lat < radius
    k = int(np.argmin(np.where(near, s, np.inf))) if near.any() else int(np.argmin(np.linalg.norm(rel, axis=1)))
    q = Vector(A[k].tolist())
    return q, float((q - pt).length)


def autoframe(loc, pts, fps, fill=0.75, aspect=16 / 9, lens_rng=(18.0, 120.0), sec=1.2):
    """Full-body framing (owner 2026-11-14: full-body shots fill more of the frame). For a
    fixed camera position, per frame: aim at the centre of her angular bounding box and pick
    the focal length that makes the box span `fill` of the frame (36 mm sensor, horizontal
    fit). Both are smoothed over `sec` so the framing breathes rather than pumps.
    pts: (n_frames, n_points, 3) canonical. Returns (aim points (n, 3), lenses (n,))."""
    loc = np.asarray(loc, float)
    n = len(pts)
    aims, lenses = np.zeros((n, 3)), np.zeros(n)
    for i in range(n):
        P = np.asarray(pts[i], float)
        c = P.mean(0)
        for _ in range(2):
            f_ = c - loc
            f_ /= np.linalg.norm(f_)
            r_ = np.cross(f_, [0.0, 0.0, 1.0])
            r_ /= max(np.linalg.norm(r_), 1e-9)
            u_ = np.cross(r_, f_)
            v = P - loc
            z = v @ f_
            tx, ty = (v @ r_) / z, (v @ u_) / z
            cx, cy = 0.5 * (tx.min() + tx.max()), 0.5 * (ty.min() + ty.max())
            c = loc + (f_ + r_ * cx + u_ * cy) * np.linalg.norm(c - loc)
        ex = 0.5 * (tx.max() - tx.min())
        ey = 0.5 * (ty.max() - ty.min())
        lenses[i] = np.clip(18.0 * fill / max(ex, ey * aspect, 1e-4), *lens_rng)
        aims[i] = c
    k = max(1, int(sec * fps))
    ker = np.ones(k) / k
    pad = lambda a: np.concatenate([np.repeat(a[:1], k, 0), a, np.repeat(a[-1:], k, 0)])  # noqa: E731
    # widest lens needed anywhere in the window first, then smooth: an average of tight and wide
    # framings cropped her while standing (2026-11-17); this never zooms in past what fits
    from scipy.ndimage import minimum_filter1d
    lenses = minimum_filter1d(lenses, size=2 * k + 1, mode='nearest')
    lenses = np.convolve(pad(lenses), ker, 'same')[k:-k]
    aims = np.stack([np.convolve(pad(aims[:, j]), ker, 'same')[k:-k] for j in range(3)], 1)
    return aims, lenses


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

    # arenas with a roof (gym) cap camera height below it: the 4 m live cam sat above the
    # 2.99 m ceiling and saw only ceiling tiles (2026-11-14)
    zmax = lock['arena'].get('cam_max_z')
    if zmax:
        # under a roof the camera cannot clear the ropes from 5.8 m out: come in to just outside
        # them (rope_y + 1 m) and keep below the ceiling
        cz = min(4.0, zmax)
        live_loc = (0.5 * (pel[0][0] + rest[0]) + abs(y0) + 1.0, mid[1] + 1.0, cz)
    else:
        live_loc = (5.8, mid[1] + 1.2, 4.0)
    az_ = lock['render'].get('live_az', 0.0)
    if az_:
        # rotate the live camera about her start position (deg, + = counter-clockwise from above);
        # e.g. a seated hold is filmed from the front three-quarter, not from behind (2026-11-18)
        c_, s_ = math.cos(math.radians(az_)), math.sin(math.radians(az_))
        ox_, oy_ = live_loc[0] - pel[0][0], live_loc[1] - pel[0][1]
        live_loc = (pel[0][0] + c_ * ox_ - s_ * oy_, pel[0][1] + s_ * ox_ + c_ * oy_, live_loc[2])
    if lock['render'].get('live_dist'):     # horizontal distance from her start (inside the ropes)
        ox_, oy_ = live_loc[0] - pel[0][0], live_loc[1] - pel[0][1]
        k_ = float(lock['render']['live_dist']) / max(math.hypot(ox_, oy_), 1e-6)
        live_loc = (pel[0][0] + k_ * ox_, pel[0][1] + k_ * oy_, live_loc[2])
    if lock['render'].get('live_z'):
        live_loc = (live_loc[0], live_loc[1], float(lock['render']['live_z']))
    # full body fills ~75% of the frame (owner 2026-11-14): follow her, zoom keyed per frame.
    # Body points: head (+crown), pelvis, feet, padded for limb volume
    crown = head + np.array([0.0, 0.0, 0.12])
    body_pts = np.stack([crown, head, pel, fr['foot_L'], fr['foot_R']], 1) if 'foot_L' in fr else \
        np.stack([crown, head, pel], 1)
    pad_ = np.array([[0.18, 0, 0], [-0.18, 0, 0], [0, 0.18, 0], [0, -0.18, 0]])
    body_pts = np.concatenate([body_pts] + [body_pts[:, 2:3] + d for d in pad_], 1)
    if 'bodies' in fr:
        # every sim body (hands and forearms included: arms locked overhead were cropped,
        # 2026-11-17), padded by 0.1 m for limb volume
        B_ = np.asarray(fr['bodies'])
        pad2 = np.array([[0.1, 0, 0], [-0.1, 0, 0], [0, 0.1, 0], [0, -0.1, 0], [0, 0, 0.1], [0, 0, -0.06]])
        body_pts = np.concatenate([body_pts] + [B_ + d for d in pad2], 1)
    aims_, lens_ = autoframe(live_loc, body_pts, fps, fill=0.75)
    ob_live = cam('live', live_loc, float(lens_[0]), follow=aims_)
    for f_i, L_ in enumerate(lens_):
        ob_live.data.lens = float(L_)
        ob_live.data.keyframe_insert('lens', frame=f_i + 1)
    cam('tight', (2.3, mid[1] + 1.6, 1.0), 60, follow=track)
    # referee pan (house style): stands beside where she comes to rest, follows the fall, then
    # pans over the body from the feet and ends on her face. Placed on the side her face is
    # turned to, so the face is never hidden behind the body.
    n = len(pel)
    ev = dict(json.loads(str(fr['events']))) if 'events' in fr else {}
    hq = fr['head_quat'][-1] if 'head_quat' in fr else np.array([1.0, 0, 0, 0])
    w_, x_, y_, z_ = hq
    front = -np.array([2 * (x_ * y_ - z_ * w_), 1 - 2 * (x_ * x_ + z_ * z_), 2 * (y_ * z_ + x_ * w_)])
    axis = head[-1] - rest
    axis[2] = 0
    axis /= max(np.linalg.norm(axis), 1e-6)
    nrm = np.array([-axis[1], axis[0], 0.0])
    if front @ nrm < 0 or (abs(front @ nrm) < 0.2 and nrm[0] < 0):
        nrm = -nrm
    feet = 0.5 * (fr['foot_L'][-1] + fr['foot_R'][-1]) if 'foot_L' in fr else rest - axis * 0.8
    body_mid = 0.5 * (feet + head[-1])
    i_pan0 = int(min(n - 2, (ev.get('followup_1', ev.get('head_impact', 0.0)) + 0.9) * fps))
    i_pan1 = max(i_pan0 + 1, n - int(1.0 * fps))
    aim = track.copy()
    for i in range(i_pan0, n):
        u = min(1.0, (i - i_pan0) / max(1, i_pan1 - i_pan0))
        u = u * u * (3 - 2 * u)
        pan = feet + (head[-1] + [0, 0, 0.03] - feet) * u
        b_ = min(1.0, (i - i_pan0) / (0.5 * fps))          # ease from follow into the pan
        aim[i] = (1 - b_) * track[i] + b_ * pan
    cam('ref_pan', tuple(body_mid + nrm * 1.75 + np.array([0, 0, 1.7 - body_mid[2]])), 50,
        follow=smooth_path(aim, fps, 0.25))
    cam('referee', (-1.6, y0 + 2.4, 1.6), 50, follow=track)
    cam('opponent', (0.5, y0 + 0.25, 1.5), 24, follow=track)
    orb = cam('orbit', (3.0, y0 + 0.4, 1.3), 85, follow=np.repeat(rest[None] + [0, 0, 0.2], len(pel), 0))
    # face: follows the direction her face points (head orientation), so her expression reads
    # at the hit, at the canvas impact and once she settles. Direction smoothed over ~0.35 s so
    # the whip plays inside the frame instead of swinging the camera; kept above the canvas
    # when she lands face-down (the camera then looks in from the side her face is turned to).
    if 'head_quat' in fr:
        q_ = np.asarray(fr['head_quat'])
        w_, x_, y_, z_ = q_[:, 0], q_[:, 1], q_[:, 2], q_[:, 3]
        fwd = -np.stack([2 * (x_ * y_ - z_ * w_), 1 - 2 * (x_ * x_ + z_ * z_), 2 * (y_ * z_ + x_ * w_)], 1)
        upv = np.stack([2 * (x_ * z_ + y_ * w_), 2 * (y_ * z_ - x_ * w_), 1 - 2 * (x_ * x_ + y_ * y_)], 1)
        fwd = smooth_path(fwd, fps, 0.35)
        upv = smooth_path(upv, fps, 0.35)
        fwd[:, 2] = np.maximum(fwd[:, 2], -0.15)
        fwd /= np.linalg.norm(fwd, axis=1, keepdims=True) + 1e-9
        upv /= np.linalg.norm(upv, axis=1, keepdims=True) + 1e-9
        hd = smooth_path(head, fps, 0.12)
        eye = hd + upv * 0.06 + fwd * 0.05
        # lying down: also move out past the crown of her head, so her own shoulder, arm and
        # chest never sit between the lens and the face (weight = how horizontal the head is)
        crown = upv.copy()
        crown[:, 2] = 0.0
        lying = np.clip(1.0 - np.abs(upv[:, 2]), 0.0, 1.0)[:, None]
        locs = eye + fwd * (0.75 - 0.2 * lying) + crown * 0.45 * lying + np.array([0, 0, 0.10]) * (1 - lying) \
            + np.array([0, 0, 0.05]) * lying
        locs[:, 2] = np.maximum(locs[:, 2], 0.10)
        fc_ = cam('face', tuple(locs[0]), 50, follow=eye, fstop=4.0)
        for f in range(n):
            fc_.location = tuple(locs[f])
            fc_.keyframe_insert('location', frame=f + 1)
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


def floor_chains(sc, skel, pattern, floor_z, radius, n):
    """Floor collision for dangling chains the sim does not model (braids, ponytails): per
    frame, root to tip, any bone whose tail would sit below floor_z + radius is swung about its
    head so the tail rests on that height (children follow). Keyed per frame. Returns the worst
    correction in degrees and how many keys were set."""
    import re as _re
    rx = _re.compile(pattern, _re.I)
    bones = [pb for pb in skel.pose.bones if rx.search(pb.name)]
    if not bones:
        return 0.0, 0

    def depth(pb):
        d_, p_ = 0, pb.parent
        while p_ is not None:
            d_, p_ = d_ + 1, p_.parent
        return d_
    bones.sort(key=depth)
    for pb in bones:
        pb.rotation_mode = 'QUATERNION'
    M = skel.matrix_world
    Minv = M.inverted()
    worst, keys = 0.0, 0
    lim = floor_z + radius
    for f in range(1, n + 1):
        sc.frame_set(f)
        for pb in bones:                 # reset to the baked (rest) rotation first
            pb.rotation_quaternion = (1, 0, 0, 0)
        bpy.context.view_layer.update()
        for pb in bones:
            h, t = M @ pb.head, M @ pb.tail
            if t.z >= lim:
                pb.keyframe_insert('rotation_quaternion', frame=f)
                continue
            L = (t - h).length
            dz = lim - h.z
            if abs(dz) >= L:
                dz = max(-L * 0.999, min(L * 0.999, dz))
            hor = Vector((t.x - h.x, t.y - h.y, 0.0))
            if hor.length < 1e-6:
                hor = Vector((1.0, 0.0, 0.0))
            want = hor.normalized() * math.sqrt(max(L * L - dz * dz, 0.0)) + Vector((0, 0, dz))
            q = (t - h).rotation_difference(want)
            worst = max(worst, math.degrees(q.angle))
            R3 = Minv.to_3x3() @ q.to_matrix() @ M.to_3x3()
            hl = pb.head.copy()
            mat = Matrix.Translation(hl) @ R3.to_4x4() @ Matrix.Translation(-hl) @ pb.matrix
            pb.matrix = mat
            bpy.context.view_layer.update()
            pb.keyframe_insert('rotation_quaternion', frame=f)
            keys += 1
    return worst, keys


def run(lock, bake_dir, sim_dir, out_dir, stills=False):
    bpy.context.preferences.filepaths.save_version = 0   # no .blend1 backups (filled the disk 2026-11-14)
    R = lock['render']
    fps = R['fps']
    fr = np.load(os.path.join(bake_dir, 'frames.npz'))
    skel_dir = os.path.dirname(os.path.dirname(bake_dir))
    bpy.ops.wm.open_mainfile(filepath=os.path.join(bake_dir, 'take.blend'))
    sc = bpy.context.scene
    n = len(fr['t'])
    sc.frame_start, sc.frame_end = 1, n
    converted = [m.name for m in bpy.data.materials if principled(m)]
    # a character file brings its own scene baggage: none of it belongs in the locked look
    sc.render.use_compositing = False
    sc.render.use_sequencer = False
    try:
        sc.render.use_freestyle = False
    except Exception:
        pass
    for o in bpy.data.objects:
        if o.type in ('LIGHT', 'CAMERA', 'GREASEPENCIL', 'GPENCIL'):
            o.hide_render = True

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
    if lock['arena'].get('scene') and not lock['arena']['scene'].get('rig_lights', True):
        w_ = bpy.data.worlds.new('KO_world')
        w_.use_nodes = True
        w_.node_tree.nodes['Background'].inputs[0].default_value = (0.004, 0.004, 0.006, 1)
        bpy.context.scene.world = w_
    else:
        lights(root, coll)
    fc_ = lock['character'].get('floor_chains')
    if fc_:
        skel_o = bpy.data.objects.get('KO_skeleton')
        if skel_o is not None:
            w_, k_ = floor_chains(sc, skel_o, fc_['pattern'], root.matrix_world.translation.z,
                                  fc_.get('radius', 0.02), n)
            print(f'[render] floor chains ({fc_["pattern"]}): {k_} corrections, worst {w_:.0f} deg')
    # cheek, hip and shoulder flatten where they meet the canvas instead of resting on a rigid point
    # (handoff R7, owner 2026-11-17). On by default; render.canvas_flatten: false turns it off,
    # or a dict sets band (m), sink (m) and bulge.
    cf_ = R.get('canvas_flatten', True)
    if cf_:
        from . import flatten as FL
        cf_ = cf_ if isinstance(cf_, dict) else {}
        s_ = root.matrix_world.to_scale().z                 # sim metres -> world units
        fl_ = FL.apply(root.matrix_world.translation.z, cf_.get('band', 0.008) * s_, cf_.get('bulge', 0.25),
                       cf_.get('sink', 0.0015) * s_)
        print(f'[render] canvas flatten on {len(fl_)} meshes, band {cf_.get("band", 0.008) * 1000:.0f} mm')
    # a hold (track G): his arms only, keyed from the sim every frame; the torso anchor stays unseen
    if 'grapple_pos' in fr and lock.get('attacker'):
        # the arms come from another character (owner 2026-11-18: Mosin's)
        from . import attacker as AT_
        _, _, nv_ = AT_.mosin_arms(fr, root, coll, lock['attacker']['dir'], fps)
        print(f"[render] hold: {lock['attacker']['character']['name']}'s arms ({nv_} vertices) posed over {len(fr['grapple_pos'])} frames")
    elif 'grapple_pos' in fr:
        from . import props as PR_
        gp_, gq_ = np.asarray(fr['grapple_pos']), np.asarray(fr['grapple_quat'])
        for k_, nm_ in enumerate(str(x) for x in fr['grapple_names']):
            if nm_ == 'torso':
                continue
            kind_ = nm_.rsplit('_', 1)[0]
            ob_ = PR_.make_attacker_segment('atk_' + nm_, coll, kind_, float(fr['grapple_len'][k_]),
                                            float(fr['grapple_radius'][k_]))
            ob_.parent = root
            ob_.rotation_mode = 'QUATERNION'
            for f_ in range(len(gp_)):
                ob_.location = Vector(gp_[f_, k_])
                ob_.rotation_quaternion = Quaternion(gq_[f_, k_])
                ob_.keyframe_insert('location', frame=f_ + 1)
                ob_.keyframe_insert('rotation_quaternion', frame=f_ + 1)
        print(f'[render] hold: {len(gp_[0]) - 1} attacker segments keyed over {len(gp_)} frames')
    shots = make_cameras(lock, fr, root, coll, fps)
    if 'face' in shots:
        rep_ = refine_face_cam(sc, shots['face'], root, fps, n)
        print('[render] face shot line-of-sight:', rep_)
    # opponent: only the strike prop is ever rendered (house rule), one per strike that asks for
    # it: prop 'glove' (punches) or 'shin' (kicks), modelled in props.py with the striking face
    # on the origin. At the hit frame the face sits on the strike point (an impact frame shows
    # real contact); for ~60 ms it rides along with her head, then pulls back.
    from . import props as PR
    hd_ = np.asarray(fr['head'])
    for st in (json.loads(str(fr['strikes'])) if 'strikes' in fr else []):
        kind = st.get('prop')
        if kind not in PR.PROPS:
            continue
        gl = PR.PROPS[kind](f'{kind}_' + st['name'], coll)
        gl.parent = root
        dvec = Vector(st['dir']).normalized()
        pt = Vector(st['point'])
        gl.rotation_mode = 'QUATERNION'
        gl.rotation_quaternion = dvec.to_track_quat('Z', 'Y')
        fhit = st['t'] * fps + 1
        head_bone = ((lock['character'].get('bone_map') or {}).get('head')
                     or ('DEF-spine.006' if 'DEF-spine.006' in {g.name for o in bpy.data.objects if o.type == 'MESH' for g in o.vertex_groups} else 'head'))
        skel_ = bpy.data.objects.get('KO_skeleton')
        if skel_ is not None and head_bone in skel_.data.bones:
            hb_ = skel_.data.bones[head_bone]
            head_bone = [hb_.name] + [c.name for c in hb_.children_recursive]
        pt, shift = snap_contact(sc, root, fhit, pt, dvec, group=head_bone)
        gl['contact'] = list(pt)                 # root-local; impact_frame.py reads it
        fcfg = (lock['character'].get('face') or {}).get('impact')
        if fcfg:
            from . import fx as FXR
            arm_ = next((o for o in bpy.data.objects if o.type == 'ARMATURE' and o.name == 'KO_skeleton'), None)
            rep_f = FXR.face_impact(sc, arm_.name if arm_ else '', fcfg, root.matrix_world @ pt,
                                    root.matrix_world.to_3x3() @ dvec, fhit, name=st['name'])
            print(f'[render] face impact {st["name"]}: {rep_f}')
        print(f'[render] {kind} {st["name"]}: contact snapped {shift * 1000:.0f} mm onto the skin')
        ih = int(min(len(hd_) - 1, max(0, round(st['t'] * fps))))
        rel = pt - Vector(hd_[ih])               # contact point relative to her head at the hit
        # authored approach path (presentation only): [[dt, back along the strike line, up], ...]
        scfg = lock.get('strike') if st['name'] == 'ko_strike' else next(
            (s_ for s_ in (lock.get('strikes') or []) if s_.get('name') == st['name']), {})
        ppath = (scfg or {}).get('prop_path')
        if ppath:
            # optional 4th value: out in front of her (her facing at the hit, horizontal), so a
            # path can swing around her body instead of through it
            ih_ = int(min(len(hd_) - 1, max(0, round(st['t'] * fps))))
            fwd_ = Vector((0.0, -1.0, 0.0))
            if 'chest_fwd' in fr:
                fwd_ = Vector(fr['chest_fwd'][ih_].tolist())
            fwd_.z = 0.0
            fwd_.normalize()
            # optional 5th value: out to her side, on the side the blow came from (hook arcs)
            side_ = Vector((0.0, 0.0, 1.0)).cross(fwd_)
            if side_.dot(-dvec) < 0:
                side_ = -side_
            keys = [(float(e_[0]), pt - dvec * float(e_[1]) + Vector((0, 0, float(e_[2])))
                     + fwd_ * (float(e_[3]) if len(e_) > 3 else 0.0)
                     + side_ * (float(e_[4]) if len(e_) > 4 else 0.0)) for e_ in ppath]
            keys.append((0.0, pt))
        else:
            keys = [(-0.10, pt - dvec * 0.55), (-0.04, pt - dvec * 0.16), (0.0, pt)]
        t_show = min(k_[0] for k_ in keys) - 0.01
        for dts in (0.03, 0.06):                 # follow-through: stay on the moving chin
            j = int(min(len(hd_) - 1, ih + round(dts * fps)))
            keys.append((dts, Vector(hd_[j]) + rel - dvec * 0.004))
        j = int(min(len(hd_) - 1, ih + round(0.06 * fps)))
        keys.append((0.30, Vector(hd_[j]) + rel - dvec * 0.45))
        for dts, loc in keys:
            gl.location = loc
            gl.keyframe_insert('location', frame=fhit + dts * fps)
        for fch, hide in ((1, True), (fhit + t_show * fps, False), (fhit + 0.32 * fps, True)):
            gl.hide_render = hide
            gl.keyframe_insert('hide_render', frame=max(1, fch))
        if gl.animation_data and gl.animation_data.action:
            for fc in getattr(gl.animation_data.action, 'fcurves', []):
                if fc.data_path == 'location':
                    for kp in fc.keyframe_points:
                        kp.interpolation = 'LINEAR'

    sc.render.engine = R['engine']
    sc.render.resolution_x, sc.render.resolution_y = R['res']
    sc.render.resolution_percentage = 100
    sc.render.fps = fps
    sc.render.image_settings.file_format = 'PNG'
    sc.render.use_motion_blur = bool(R['motion_blur'])
    sc.cycles.samples = R['samples']
    # memory: 4K Daz texture sets plus a full gym exceed the workspace (OOM 2026-11-13); cap
    # textures for drafts (Simplify > texture limit). Finals: R['texture_limit'] = 'OFF'.
    tl = str(R.get('texture_limit', '2048'))
    if tl != 'OFF':
        sc.render.use_simplify = True
        sc.cycles.texture_limit_render = tl
        sc.cycles.texture_limit = tl
    sc.render.use_persistent_data = True     # keep textures and static geometry between frames
    if R.get('max_subdiv') is not None:
        sc.render.use_simplify = True
        sc.render.simplify_subdivision_render = R['max_subdiv']
    step = int(R.get('frame_step', 1))
    sc.cycles.use_adaptive_sampling = True
    try:
        sc.cycles.use_denoising = True
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        sc.cycles.use_denoising = False
    sc.cycles.device = 'CPU'
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Medium High Contrast'
    sc.view_settings.exposure = float((lock['arena'].get('scene') or {}).get('exposure', 0.0))
    sc.camera = shots[R['shots'][0]]
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, 'scene.blend'), compress=True,
                                relative_remap=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile()

    seg = []
    ev_t = dict(json.loads(str(fr['events']))) if 'events' in fr else {}
    t_ko = float(fr['t_ko']) if 't_ko' in fr else 0.0
    if stills:
        # look check: a handful of stills per shot at the take's key moments, minutes not tens
        # of minutes. Catches framing, occlusion, face and prop problems before the video.
        keys_t = [t_ko + 0.45] + [ev_t[k] + d for k, d in (('head_impact', 0.25), ('head_impact', 1.2), ('followup_1', -0.03),
                                                           ('followup_1', 1.6)) if k in ev_t] + [n / fps - 0.1]
        # explicit times / shots (comic and contact sheets: the same fast path, ~10 s a frame)
        keys_t = R.get('still_times') or keys_t
        tiles = []
        for name in R.get('still_shots') or R['shots']:
            sc.camera = shots[name]
            for kt in keys_t:
                f = int(min(n, max(1, kt * fps + 1)))
                fp = os.path.join(out_dir, f'still_{name}_{f:04d}.png')
                sc.frame_set(f)
                sc.render.filepath = fp
                bpy.ops.render.render(write_still=True)
                tiles.append(fp)
        R = dict(R, shots=[])
    for si, name in enumerate(R['shots']):
        sc.camera = shots[name]
        fdir = os.path.join(out_dir, 'frames', name)
        os.makedirs(fdir, exist_ok=True)
        # live shot runs the whole take; replays start just before the hit
        f0 = 1 if si == 0 else max(1, int((t_ko - 0.5) * fps))
        for f in range(f0, n + 1, step):
            fp = os.path.join(fdir, f'{f:05d}.png')
            if os.path.exists(fp) and os.path.getsize(fp) > 0:
                continue
            sc.frame_set(f)
            sc.render.filepath = fp
            bpy.ops.render.render(write_still=True)
        vid = os.path.join(out_dir, f'{si:02d}_{name}.' + ('mkv' if lock['quality'] == 'full' else 'mp4'))
        encode(os.path.join(fdir, '*.png'), vid, fps / step, lock['quality'] == 'full')
        if si == 0:                 # contact sheet for review before anyone watches the video
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-pattern_type', 'glob', '-i',
                            os.path.join(fdir, '*.png'), '-vf',
                            f"select='not(mod(n,{max(1, (n // step) // 12)}))',scale=480:-1,tile=4x3",
                            '-frames:v', '1', os.path.join(out_dir, 'contact_sheet.png')], check=True)
        for p in glob.glob(os.path.join(fdir, '*.png')):
            os.remove(p)
        seg.append(vid)
    # face check (house rule: the face must be readable; ~30% of the pupil showing): one frame
    # straight down her line of sight, late in the hold
    if 'head_quat' in fr:
        fi = min(n - 1, int((ev_t.get('followup_1', ev_t.get('head_impact', t_ko)) + 1.2) * fps))
        w_, x_, y_, z_ = fr['head_quat'][fi]
        front = -np.array([2 * (x_ * y_ - z_ * w_), 1 - 2 * (x_ * x_ + z_ * z_), 2 * (y_ * z_ + x_ * w_)])
        up_h = np.array([2 * (x_ * z_ + y_ * w_), 2 * (y_ * z_ - x_ * w_), 1 - 2 * (x_ * x_ + y_ * y_)])
        cd = bpy.data.cameras.new('face_check')
        cd.lens = 85
        fc = add(bpy.data.objects.new('cam_face_check', cd), root, coll)
        eye_pt = fr['head'][fi] + up_h * 0.07 + front * 0.05
        fc.location = tuple(eye_pt + front * 0.6)
        look_at(fc, tuple(eye_pt))
        sc.camera = fc
        sc.frame_set(fi + 1)
        sc.render.filepath = os.path.join(out_dir, 'face_check.png')
        bpy.ops.render.render(write_still=True)
    if stills:
        cols = len(keys_t)
        ins = sum([['-i', t_] for t_ in tiles], [])
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', *ins, '-filter_complex',
                        f"concat=n={len(tiles)}:v=1:a=0,scale=480:-1,tile={cols}x{len(tiles) // cols}",
                        '-frames:v', '1', os.path.join(out_dir, 'stills_sheet.png')], check=True)
        return
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
