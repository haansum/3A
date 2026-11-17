"""Impact FX that live in the 3D scene (so they are lit, motion-blurred and in focus like the rest
of the render): a mouthguard ejected on a strike, and a spray of spit droplets from the mouth.

Both follow analytic ballistic paths keyframed per frame (gravity, one damped bounce on the
canvas, sliding friction). Launch speeds, spread and counts are authored by eye; nothing here is
measured. No blood, ever (house rule).
"""
import math
import random

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

G = 9.81
_LIPS = {}


def _mat(name, rgb, rough, transmission=0.0, ior=1.45, alpha=1.0, emit=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['IOR'].default_value = ior
    for k in ('Transmission Weight', 'Transmission'):
        if k in b.inputs:
            b.inputs[k].default_value = transmission
            break
    b.inputs['Alpha'].default_value = alpha
    if emit:          # a touch of self-light so clear droplets still read against a dark arena
        b.inputs['Emission Color'].default_value = (*rgb, 1.0)
        b.inputs['Emission Strength'].default_value = emit
    return m


def lip_indices(face, key='mouth_surprised', frac=0.35):
    """Face vertices that move most in the mouth-open shape key = the lips."""
    if face.name in _LIPS:
        return _LIPS[face.name]
    kb = face.data.shape_keys.key_blocks
    base = np.array([v.co[:] for v in kb['base'].data])
    sk = np.array([v.co[:] for v in kb[key].data])
    d = np.linalg.norm(sk - base, axis=1)
    idx = np.where(d > d.max() * frac)[0]
    _LIPS[face.name] = idx
    return idx


def _lip_bone_indices(ob):
    """Rigs with face bones (Daz Genesis): vertices weighted mostly to *lip* bones."""
    if ob.name in _LIPS:
        return _LIPS[ob.name]
    lg = {g.index for g in ob.vertex_groups if 'lip' in g.name.lower() and 'eyelid' not in g.name.lower()}
    idx = np.array([v.index for v in ob.data.vertices
                    if sum(e.weight for e in v.groups if e.group in lg) >= 0.5], dtype=int)
    _LIPS[ob.name] = idx
    return idx


def mouth_point(sc, frame, face_name='Face'):
    """World position of the mouth (lip centroid) at a frame, armature deformation only.
    Shape-key faces: the vertices the mouth-open key moves; bone faces: lip-bone weights."""
    face = bpy.data.objects.get(face_name)
    if face is not None and face.data.shape_keys and 'mouth_surprised' in face.data.shape_keys.key_blocks:
        idx = lip_indices(face)
    else:
        cands = [o for o in bpy.data.objects if o.type == 'MESH' and not o.hide_render
                 and any('lip' in g.name.lower() for g in o.vertex_groups)]
        face = max(cands, key=lambda o: len(_lip_bone_indices(o)))
        idx = _lip_bone_indices(face)
    sc.frame_set(int(round(frame)))
    saved = [(md, md.show_viewport) for md in face.modifiers if md.type != 'ARMATURE']
    for md, _ in saved:
        md.show_viewport = False
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = face.evaluated_get(dg).to_mesh()
    P = np.array([me.vertices[i].co[:] for i in idx])
    face.evaluated_get(dg).to_mesh_clear()
    for md, s in saved:
        md.show_viewport = s
    return face.matrix_world @ Vector(P.mean(0).tolist())


def canvas_top():
    cv = bpy.data.objects.get('canvas')
    if cv is None:
        return 0.0
    return max((cv.matrix_world @ Vector(c)).z for c in cv.bound_box)


def ballistic(p0, v0, t, floor, rest=0.32, mu=0.6, radius=0.0):
    """Position at time t after launch: projectile, bounces on z=floor with restitution `rest`,
    slides with friction once the bounce is spent. Returns (pos, landed)."""
    p, v, tt = Vector(p0), Vector(v0), 0.0
    for _ in range(4):
        # time to floor
        a, b, c = -0.5 * G, v.z, p.z - floor - radius
        disc = b * b - 4 * a * c
        th = (-b - math.sqrt(max(disc, 0))) / (2 * a) if disc >= 0 else 1e9
        if tt + th >= t:
            dtl = t - tt
            return p + v * dtl + Vector((0, 0, -0.5 * G * dtl * dtl)), False
        p = p + v * th + Vector((0, 0, -0.5 * G * th * th))
        p.z = floor + radius
        v = Vector((v.x * 0.7, v.y * 0.7, -(v.z - G * th) * rest))
        tt += th
        if v.z < 0.25:
            break
    # sliding to rest
    vh = Vector((v.x, v.y, 0))
    sp = vh.length
    if sp < 1e-6:
        return p, True
    ts = sp / (mu * G)
    dtl = min(t - tt, ts)
    s = sp * dtl - 0.5 * mu * G * dtl * dtl
    return p + vh.normalized() * s, True


def make_mouthguard(coll, name='KO_mouthguard', rgb=(0.10, 0.35, 0.85)):
    """Boil-and-bite guard: a U-shaped arch (local +Y = toward the front teeth), ~5.6 cm wide,
    4.6 cm deep, 2 cm tall, translucent."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    nu, nv = 28, 10
    W, D, H, th = 0.028, 0.046, 0.020, 0.006
    rows = []
    for i in range(nu + 1):
        a = math.pi * i / nu                         # 0..pi around the arch
        cx, cy = W * math.cos(a), D * (math.sin(a) ** 0.8) - 0.012
        nx, ny = math.cos(a), math.sin(a)
        ring = []
        for j in range(nv):
            b = 2 * math.pi * j / nv                  # cross-section: rounded slab
            ox, oz = th * math.cos(b), (H / 2) * math.sin(b)
            ring.append(bm.verts.new((cx + nx * ox, cy + ny * ox, oz)))
        rows.append(ring)
    for i in range(nu):
        for j in range(nv):
            bm.faces.new((rows[i][j], rows[i][(j + 1) % nv], rows[i + 1][(j + 1) % nv], rows[i + 1][j]))
    bm.faces.new(list(reversed(rows[0])))
    bm.faces.new(rows[-1])
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(_mat('KO_fx_mouthguard', rgb, 0.18, transmission=0.55))
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    sd = ob.modifiers.new('round', 'SUBSURF')
    sd.levels = sd.render_levels = 1
    return ob


def eject_mouthguard(sc, coll, t0, v0, fps, frames, seed=0, spin=(14.0, 6.0, 9.0)):
    """Mouthguard leaves the mouth at t0 (s) with velocity v0 (world, m/s) and tumbles."""
    ob = make_mouthguard(coll)
    f0 = t0 * fps + 1
    p0 = mouth_point(sc, f0)
    floor = canvas_top()
    rnd = random.Random(seed)
    w = Vector(spin) * rnd.uniform(0.8, 1.2)
    ob.rotation_mode = 'XYZ'
    landed_rot = None
    for f in range(max(1, int(f0) - 1), frames + 1):
        t = (f - f0) / fps
        if t < 0:
            ob.location = p0
            ob.rotation_euler = (0, 0, 0)
        else:
            p, landed = ballistic(p0, v0, t, floor, radius=0.01)
            ob.location = p
            if landed:
                landed_rot = landed_rot or Euler((0, 0, ob.rotation_euler.z))
                ob.rotation_euler = landed_rot   # lies flat once it has come down
            else:
                ob.rotation_euler = (w.x * t, w.y * t, w.z * t)
        ob.keyframe_insert('location', frame=f)
        ob.keyframe_insert('rotation_euler', frame=f)
    for f, hide in ((1, True), (f0, False)):
        ob.hide_render = hide
        ob.keyframe_insert('hide_render', frame=max(1, f))
    return ob


def spit_spray(sc, coll, t0, v_dir, v_head, fps, n=46, seed=1, speed=(1.6, 4.2), cone_deg=28,
               life=0.45, name='KO_spit'):
    """A burst of saliva droplets from the mouth at t0, thrown along v_dir (world unit vector)
    on top of the head's own velocity; a few elongated strands. Clear water material."""
    rnd = random.Random(seed)
    mat = _mat('KO_fx_spit', (0.92, 0.94, 0.97), 0.04, transmission=0.6, ior=1.33, emit=0.35)
    f0 = t0 * fps + 1
    p0 = mouth_point(sc, f0)
    floor = canvas_top()
    d = Vector(v_dir).normalized()
    a1 = d.orthogonal().normalized()
    a2 = d.cross(a1)
    obs = []
    for k in range(n):
        r = rnd.uniform(0.0006, 0.0024) if k % 7 else rnd.uniform(0.0025, 0.004)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=10, ring_count=6, radius=1.0)
        ob = bpy.context.active_object
        ob.name = f'{name}_{k:02d}'
        for c in ob.users_collection:
            c.objects.unlink(ob)
        coll.objects.link(ob)
        ob.data.materials.append(mat)
        for p in ob.data.polygons:
            p.use_smooth = True
        th = math.radians(cone_deg) * math.sqrt(rnd.random())
        ph = rnd.uniform(0, 2 * math.pi)
        dirk = (d * math.cos(th) + (a1 * math.cos(ph) + a2 * math.sin(ph)) * math.sin(th)).normalized()
        v0 = Vector(v_head) + dirk * rnd.uniform(*speed)
        strand = k % 9 == 0
        lk = life * rnd.uniform(0.6, 1.0)
        ob.rotation_mode = 'QUATERNION'
        ob.rotation_quaternion = v0.to_track_quat('Z', 'Y')
        for f in range(max(1, int(f0) - 1), int(f0 + lk * fps) + 2):
            t = (f - f0) / fps
            tt = max(t, 0.0)
            p, landed = ballistic(p0, v0, tt, floor, rest=0.0, mu=3.0)
            ob.location = p
            stretch = 1.0 if landed or t <= 0 else (3.5 if strand else 1.4)
            s = r if t <= lk * 0.8 else r * max(0.0, (lk - t) / (lk * 0.2))
            ob.scale = (s, s, s * stretch) if t >= 0 else (1e-5, 1e-5, 1e-5)
            if landed:
                ob.scale = (s * 1.6, s * 1.6, s * 0.35)      # a flattened bead on the canvas
            ob.keyframe_insert('location', frame=f)
            ob.keyframe_insert('scale', frame=f)
        obs.append(ob)
    return obs


def head_velocity(X, bn, t, dt, M3):
    """Head velocity (world) from the sim's recorded positions, transformed by the root."""
    i = int(round(t / dt))
    h = bn.index('head')
    v = (X[min(i + 2, len(X) - 1), h] - X[max(i - 2, 0), h]) / (4 * dt)
    return M3 @ Vector(v.tolist())


def face_impact(sc, arm_name, cfg, pt_world, d_world, f_hit, name='ko'):
    """Impact on the face (owner 2026-11-12: the face must react while spit and the mouthguard
    fly). Two parts, both keyed around the hit frame:
      1. the mouth opens partway: shape keys from cfg['open'] {key: value};
      2. a dent at the contact: a new shape key that pushes skin near the contact point along
         the blow (Gaussian falloff, cfg['dent_mm'] deep, cfg['radius_m'] wide), springing back.
    The dent is built in each mesh's rest space through the dominant deform bone's inverse
    (small-displacement approximation). Depths and timing are authored by eye."""
    arm = bpy.data.objects.get(arm_name)
    meshes = [bpy.data.objects[m] for m in cfg.get('meshes', ['Face']) if m in bpy.data.objects]
    dent = cfg.get('dent_mm', 6.0) / 1000.0
    rad = cfg.get('radius_m', 0.045)
    t_open = cfg.get('open', {})
    fps = sc.render.fps / sc.render.fps_base
    # mouth timing (owner 2026-11-13): closed at contact, then forced open by the blow - partway
    # and shoved sideways on the first frame after contact, fullest during the whip. Opening it
    # before or at contact read as a mouth that was already hanging open.
    keys_open = [(-0.01, 0.0), (0.0, 0.0), (0.033, 0.45), (0.09, 1.0), (0.16, 0.85), (0.40, 0.45)]
    keys_shift = [(-0.01, 0.0), (0.0, 0.0), (0.033, 1.0), (0.07, 0.8), (0.16, 0.3), (0.35, 0.0)]
    keys_dent = [(-0.01, 0.0), (0.015, 1.0), (0.06, 0.55), (0.14, 0.0)]

    def _w(keys, t):
        if t <= keys[0][0]:
            return keys[0][1]
        for (t0, w0), (t1, w1) in zip(keys, keys[1:]):
            if t <= t1:
                return w0 + (w1 - w0) * (t - t0) / max(t1 - t0, 1e-9)
        return keys[-1][1]
    # bone-driven faces (Daz Genesis): open the jaw by rotating its deform bone, and shove it
    # sideways along the blow (cfg['shift_deg'], axis and sign found by probing the bone)
    sc.frame_set(int(round(f_hit)))
    for bname, deg in (cfg.get('open_bones') or {}).items():
        if arm and bname in arm.pose.bones:
            pb = arm.pose.bones[bname]
            pb.rotation_mode = 'XYZ'
            base = pb.rotation_euler.copy()
            ax = cfg.get('open_axis', 0)
            shift = math.radians(cfg.get('shift_deg', 7.0))
            axs, sgn = None, 1.0
            dlat = Vector(d_world).normalized()
            if shift:
                best = 0.0
                tip0 = arm.matrix_world @ pb.tail
                for cand in (i for i in range(3) if i != ax):
                    e = base.copy()
                    e[cand] += math.radians(5.0)
                    pb.rotation_euler = e
                    bpy.context.view_layer.update()
                    mv = (arm.matrix_world @ pb.tail) - tip0
                    pb.rotation_euler = base
                    bpy.context.view_layer.update()
                    if mv.length < 1e-6:
                        continue
                    # yaw-like axes move the chin sideways; prefer the one best aligned with the blow
                    al = mv.normalized().dot(dlat)
                    if abs(al) > abs(best):
                        best, axs, sgn = al, cand, (1.0 if al > 0 else -1.0)
            for dt_ in sorted({k[0] for k in keys_open} | {k[0] for k in keys_shift}):
                e = base.copy()
                e[ax] = base[ax] + math.radians(deg) * _w(keys_open, dt_)
                if axs is not None:
                    e[axs] = base[axs] + sgn * shift * _w(keys_shift, dt_)
                pb.rotation_euler = e
                pb.keyframe_insert('rotation_euler', frame=f_hit + dt_ * fps)
            pb.rotation_euler = base
            print(f'[fx] face_impact jaw {bname}: open {deg} deg axis {ax}, shift {math.degrees(shift):.0f} deg '
                  f'axis {axs} sign {sgn:+.0f}')
    sc.frame_set(int(round(f_hit)))
    dg = bpy.context.evaluated_depsgraph_get()
    rep = {}
    for ob in meshes:
        kb = ob.data.shape_keys.key_blocks if ob.data.shape_keys else None
        # 1. mouth open
        for k, v in t_open.items():
            if kb and k in kb:
                for dt_, w in keys_open:
                    kb[k].value = v * w
                    kb[k].keyframe_insert('value', frame=f_hit + dt_ * fps)
        # 2. dent (posed positions with the armature only: solidify/subsurf change the count)
        saved = [(md, md.show_viewport) for md in ob.modifiers if md.type != 'ARMATURE']
        for md, _ in saved:
            md.show_viewport = False
        dg.update()
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        ok = len(me.vertices) == len(ob.data.vertices)
        Pw = np.array([(ob.matrix_world @ v.co)[:] for v in me.vertices]) if ok else None
        ev.to_mesh_clear()
        for md, s_ in saved:
            md.show_viewport = s_
        dg.update()
        if not ok:
            continue
        dist = np.linalg.norm(Pw - np.array(pt_world[:]), axis=1)
        sel = np.where(dist < 2.5 * rad)[0]
        if not len(sel):
            continue
        if not ob.data.shape_keys:
            ob.shape_key_add(name='Basis', from_mix=False)
        sk = ob.shape_key_add(name=f'KO_dent_{name}', from_mix=False)
        gname = {g.index: g.name for g in ob.vertex_groups}
        d = Vector(d_world).normalized() * dent
        for i in sel:
            w = math.exp(-0.5 * (dist[i] / rad) ** 2)
            v = ob.data.vertices[i]
            bone = None
            if arm and v.groups:
                gmax = max(v.groups, key=lambda g: g.weight)
                bone = gname.get(gmax.group)
            R = ob.matrix_world.to_3x3()
            if bone and bone in arm.pose.bones:
                pb = arm.pose.bones[bone]
                Mdef = (arm.matrix_world.to_3x3() @ (pb.matrix.to_3x3() @ pb.bone.matrix_local.to_3x3().inverted())
                        @ arm.matrix_world.to_3x3().inverted())
                R = Mdef @ R
            sk.data[i].co = sk.data[i].co + R.inverted() @ (d * w)
        for dt_, w in keys_dent:
            sk.value = w
            sk.keyframe_insert('value', frame=f_hit + dt_ * fps)
        rep[ob.name] = int(len(sel))
    return rep


def worn_guard(sc, coll, frame=1, sk_name='KO_skeleton', body_name='Genesis 8 Female Mesh',
               rgb=(0.02, 0.10, 0.55), name='KO_guard_worn', down=0.011):
    """Boil-and-bite guard seated on the upper teeth and parented to the upperTeeth bone, so it
    stays in through every hit until hidden (owner 2026-11-16: "I want her mouthguard to stay
    in"). Seating as in tools/mouth_sample.py: arch front 1 mm proud of the incisors, by eye."""
    import numpy as np
    sk = bpy.data.objects[sk_name]
    body = bpy.data.objects[body_name]
    sc.frame_set(int(frame))
    dg = bpy.context.evaluated_depsgraph_get()
    saved = [(md, md.show_viewport) for md in body.modifiers if md.type != 'ARMATURE']
    for md, _ in saved:
        md.show_viewport = False
    dg.update()
    me = body.evaluated_get(dg).to_mesh()
    gi = body.vertex_groups['upperTeeth'].index
    P = np.array([(body.matrix_world @ v.co)[:] for v in me.vertices
                  if any(g.group == gi and g.weight > 0.6 for g in v.groups)])
    body.evaluated_get(dg).to_mesh_clear()
    for md, s_ in saved:
        md.show_viewport = s_
    dg.update()
    pb = sk.pose.bones['head']
    head_c = sk.matrix_world @ pb.head
    up = ((sk.matrix_world @ pb.tail) - head_c).normalized()
    tc = Vector(P.mean(0).tolist())
    fwd = tc - head_c
    fwd = (fwd - up * fwd.dot(up)).normalized()
    inc = Vector(max(P.tolist(), key=lambda p: Vector(p).dot(fwd)))
    g = make_mouthguard(coll, name=name, rgb=rgb)
    for n_ in g.data.materials[0].node_tree.nodes:      # worn: denser plastic than the flying one
        if n_.type == 'BSDF_PRINCIPLED':
            for k_, v_ in (('Transmission Weight', 0.15), ('Roughness', 0.25), ('Coat Weight', 0.4)):
                if k_ in n_.inputs:
                    n_.inputs[k_].default_value = v_
    g.rotation_mode = 'QUATERNION'
    g.rotation_quaternion = fwd.to_track_quat('Y', 'Z')
    g.location = inc - fwd * 0.036 - up * down
    bpy.context.view_layer.update()
    mw = g.matrix_world.copy()
    g.parent, g.parent_type, g.parent_bone = sk, 'BONE', 'upperTeeth'
    bpy.context.view_layer.update()
    g.matrix_world = mw
    return g


def guard_knocked_out(sc, coll, t_hit, v_release, fps, frames, seed=0, rgb=(0.02, 0.10, 0.55),
                      loosen=0.03, release=0.14, slide=0.024, tilt_deg=28.0):
    """Worn from the start; the follow-up knocks it loose (owner 2026-11-16: "0.02 s seems too
    instant to look organic"). Three stages, all by eye:
      t_hit + loosen .. t_hit + release: the guard works out of the mouth, sliding forward off the
        teeth (`slide` m) and tipping down at the front (`tilt_deg`), still riding the head, so it
        hangs half out of the lips while the head whips;
      t_hit + release: it lets go with v_release (world; the caller takes the head's whip velocity
        at that moment), tumbles and settles on the canvas.
    """
    from mathutils import Matrix
    g = worn_guard(sc, coll, rgb=rgb)
    f_l, f_r = (t_hit + loosen) * fps + 1, (t_hit + release) * fps + 1
    L0 = g.matrix_basis.copy()
    g.rotation_mode = 'QUATERNION'
    for f in range(max(1, int(f_l) - 1), int(f_r) + 1):
        u = min(max((f - f_l) / max(f_r - f_l, 1e-6), 0.0), 1.0)
        u = u * u * (3 - 2 * u)                      # eases out, then picks up as the head turns
        g.matrix_basis = L0 @ Matrix.Translation((0, slide * u, -0.004 * u)) @ Matrix.Rotation(
            math.radians(-tilt_deg * u), 4, 'X')
        g.keyframe_insert('location', frame=f)
        g.keyframe_insert('rotation_quaternion', frame=f)
    for f, hide in ((1, False), (int(f_r) + 1, True)):
        g.hide_render = hide
        g.keyframe_insert('hide_render', frame=max(1, f))
    fly = eject_mouthguard(sc, coll, t_hit + release + 1.0 / fps, v_release, fps, frames, seed=seed)
    fly.data.materials[0] = g.data.materials[0]
    return g, fly
