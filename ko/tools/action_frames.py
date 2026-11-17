"""Full-size action frames: the take's key beats as regular Cycles renders, each framed on the
action (dutch tilt, depth of field, motion blur), with in-scene FX (mouthguard ejected by the KO
strike, spit spray on each strike) and comic action marks drawn on top (speed lines, motion
streaks, twitch marks, shock lines, impact bloom).

    python3 tools/action_frames.py SCENE.blend SIM.npz OUT_DIR NAME [--res 1920] [--samples 48]
        [--only impact,snap,...] [--no-marks]

Writes OUT_DIR/NAME_<beat>.png (with marks), NAME_<beat>_clean.png, NAME_frames.json and
NAME_fx.blend (the scene with the FX objects, for editing). Framing, FX launch speeds and mark
placement are authored by eye; times and contact points come from the sim.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import action_fx as AF  # noqa: E402
from ko.render import fx as FX  # noqa: E402
from PIL import Image  # noqa: E402

a = sys.argv[1:]
src, simp, outd, name = a[:4]
opt = lambda k, d: a[a.index(k) + 1] if k in a else d  # noqa: E731
res = int(opt('--res', 1920))
spp = int(opt('--samples', 48))
only = set(opt('--only', '').split(',')) - {''}
marks = '--no-marks' not in a
os.makedirs(outd, exist_ok=True)

z = np.load(simp, allow_pickle=True)
ev = dict(json.loads(str(z['events'])))
strikes = {s['name']: s for s in json.loads(str(z['strikes']))}
bn = [str(b) for b in z['body_names']]
X, Q, T, dt = z['xpos'], z['xquat'], z['t'], float(z['dt'])
Tend = float(T[-1])


def idx(t):
    return int(min(len(T) - 1, max(0, round(t / dt))))


def P(body, t):
    return np.array(X[idx(t), bn.index(body)])


def axes(body, t):
    w, x, y, zz = Q[idx(t), bn.index(body)]
    R = np.array([[1 - 2 * (y * y + zz * zz), 2 * (x * y - zz * w), 2 * (x * zz + y * w)],
                  [2 * (x * y + zz * w), 1 - 2 * (x * x + zz * zz), 2 * (y * zz - x * w)],
                  [2 * (x * zz - y * w), 2 * (y * zz + x * w), 1 - 2 * (x * x + y * y)]])
    return R[:, 0], R[:, 1], R[:, 2]


def head_turn(t):
    """(yaw, pitch) of the head relative to the chest, degrees; yaw + = toward her left,
    pitch + = chin up."""
    Rc = np.column_stack(axes('chest', t))
    Rh = np.column_stack(axes('head', t))
    f = (Rc.T @ Rh) @ np.array([0.0, -1.0, 0.0])
    return (math.degrees(math.atan2(-f[0], -f[1])), math.degrees(math.atan2(f[2], math.hypot(f[0], f[1]))))


def whip_dev(st, t):
    """How far the head is turned away from where it was just before this strike (deg)."""
    y0, p0 = head_turn(st['t'] - 0.01)
    y1, p1 = head_turn(t)
    return math.hypot(y1 - y0, p1 - p0)


WHIP_DEG = float(opt('--whip-deg', 20.0))


EXTREMITIES = ['hand_L', 'hand_R', 'foot_L', 'foot_R']


def twitchiest(t, win=0.15):
    """The single extremity moving most relative to the chest around t (agreed rule: one
    twitching extremity)."""
    i0, i1 = idx(t - win), idx(t + win)
    c = X[i0:i1, bn.index('chest')]
    best, bv = None, -1.0
    for e in EXTREMITIES:
        r = X[i0:i1, bn.index(e)] - c
        v = float(np.sqrt((np.diff(r, axis=0) ** 2).sum(1).mean()) / dt)
        if v > bv:
            best, bv = e, v
    return best


def flat(v):
    v = np.array(v, float)
    v[2] = 0
    return v / max(np.linalg.norm(v), 1e-9)


bpy.ops.wm.open_mainfile(filepath=src, use_scripts=False)
sc = bpy.context.scene
fps = sc.render.fps / sc.render.fps_base
nfr = sc.frame_end
root = bpy.data.objects['KO_canonical']
# draft memory: swap character images for a pre-shrunk copy (Simplify alone still decodes 4K first)
_td = opt('--tex-dir', None)
if _td:
    _n = 0
    for im in bpy.data.images:
        base = os.path.basename(bpy.path.abspath(im.filepath or ''))
        alt = os.path.join(_td, base)
        if base and os.path.exists(alt):
            if im.packed_file:
                im.unpack(method='REMOVE')
            im.filepath = alt
            im.reload()
            _n += 1
    print(f'[action] tex-dir: {_n} images swapped')
Mw =root.matrix_world.copy()
M3 = Mw.to_3x3()
coll = bpy.data.collections.new('KO_fx')
sc.collection.children.link(coll)


def W(v):
    return Mw @ Vector(list(map(float, v)))


# ---------------------------------------------------------------- in-scene FX
ko = strikes.get('ko_strike') or (min(strikes.values(), key=lambda v: abs(v['t'] - float(z['t_ko'])))
                                  if strikes and 't_ko' in z.files else None)   # archetypes may name it (e.g. 'hook')
fu = strikes.get('followup_1')
guard = None
if ko:
    d_ko = (M3 @ Vector(ko['dir'])).normalized()
    vh = FX.head_velocity(X, bn, ko['t'] + 0.03, dt, M3)
    # out of the mouth along the blow, plus the head's own snap, plus a little lift
    # --guard-eject ko (default, older takes) | followup_1 (owner 2026-11-16: stays in through the
    # KO, the follow-up knocks it out as the head whips) | none (stays in)
    if opt('--guard-eject', 'ko') == 'ko':
        guard = FX.eject_mouthguard(sc, coll, ko['t'] + 0.02, vh * 0.6 + d_ko * 2.6 + Vector((0, 0, 1.2)), fps, nfr)
    FX.spit_spray(sc, coll, ko['t'] + 0.012, d_ko + Vector((0, 0, 0.25)), vh * 0.5, fps, n=48, seed=1)
if opt('--guard-eject', 'ko') == 'none':
    guard = FX.worn_guard(sc, coll)
if fu:
    d_fu = (M3 @ Vector(fu['dir'])).normalized()
    if opt('--guard-eject', 'ko') == 'followup_1':
        # works loose over ~0.1 s, lets go ~0.14 s after contact, flung by the whip (fx.guard_knocked_out)
        vh_fu = FX.head_velocity(X, bn, fu['t'] + 0.14, dt, M3)
        guard = FX.guard_knocked_out(sc, coll, fu['t'], vh_fu * 1.1 + d_fu * 0.8 + Vector((0, 0, 0.6)),
                                     fps, nfr, seed=3)[1]
    # a blow driving down into a face on the canvas sprays out sideways, low
    side = d_fu.cross(Vector((0, 0, 1)))
    side = side if side.length > 0.2 else Vector((1, 0, 0))
    FX.spit_spray(sc, coll, fu['t'] + 0.012, side.normalized() + Vector((0, 0, 0.55)), Vector((0, 0, 0)),
                  fps, n=34, seed=4, speed=(1.0, 2.8), cone_deg=55, name='KO_spit_fu')
if '--no-save' not in a:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(outd, f'{name}_fx.blend'), compress=False, copy=True)

# ---------------------------------------------------------------- render setup
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = spp
sc.cycles.use_denoising = True
# memory (4K Daz textures + gym hit the workspace limit, 2026-11-13): 2K texture cap, small tiles
sc.render.use_simplify = True
sc.cycles.texture_limit_render = opt('--texture-limit', '2048')
sc.cycles.use_auto_tile = True
sc.cycles.tile_size = 512
sc.render.resolution_x, sc.render.resolution_y = res, int(res * 9 / 16)
sc.render.resolution_percentage = 100
sc.render.use_compositing = False
sc.render.use_sequencer = False
sc.render.use_motion_blur = '--no-mb' not in a
sc.render.motion_blur_shutter = 0.45
# the baked character smears as a whole under deformation blur (the bake is not sub-frame
# smooth), so blur only the things that fly: props, mouthguard, spit
for o in bpy.data.objects:
    if o.type == 'MESH' and o.parent is not None and o.parent.name != 'KO_canonical':
        try:
            o.cycles.use_motion_blur = False
        except AttributeError:
            o.motion_blur = False
cd = bpy.data.cameras.new('action_cam')
cd.clip_start = 0.02
cam = bpy.data.objects.new('action_cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam
Wr, Hr = sc.render.resolution_x, sc.render.resolution_y


FINISH = {'impact', 'whip'}          # the finishing blow: the one peak (VFX bible P6, dutch on it only)
CUR = {'beat': None}


CAMS = json.load(open(opt('--cams', ''))) if opt('--cams', '') else {}
VARIANT = opt('--variant', '')


def cam_override():
    """Camera chosen outside this script (angle variants, the owner's 3D editor), keyed by
    beat, or 'beat@X' for variant X. World coords: loc, target, lens (mm, 36 mm sensor), roll."""
    k = f"{CUR['beat']}@{VARIANT}" if VARIANT else CUR['beat']
    return CAMS.get(k)


def aim(loc, tgt, lens, roll_deg=0.0, focus=None, fstop=2.8):
    ov = cam_override()
    if ov:
        loc, tgt, lens = Vector(ov['loc']), Vector(ov['target']), float(ov['lens'])
        roll_deg = float(ov.get('roll', 0.0))
        focus = focus if focus is not None else tgt
    elif CUR['beat'] not in FINISH:
        roll_deg = 0.0
    cam.location = loc
    cd.lens = lens
    cam.rotation_mode = 'QUATERNION'
    q = (tgt - loc).to_track_quat('-Z', 'Y')
    cam.rotation_quaternion = q @ Quaternion((0, 0, 1), math.radians(roll_deg))
    cd.dof.use_dof = focus is not None and '--no-dof' not in a
    if focus is not None:
        cd.dof.focus_distance = (focus - loc).length
        cd.dof.aperture_fstop = fstop
    bpy.context.view_layer.update()            # world_to_camera_view reads matrix_world


def fit_body(t, fill=0.75):
    """Full-body beats (owner 2026-11-14): keep the camera position, re-aim at the centre of
    her projected bounding box and set the focal length so the box spans `fill` of the frame."""
    if cam_override():
        return
    pts = [W(P(b, t)) for b in bn if b != 'world' and not b.startswith(('rope', 'post', 'KO'))] + \
        [W(P('head', t)) + Vector((0, 0, 0.12))]
    for _ in range(2):
        Mi = cam.matrix_world.inverted()
        c = [Mi @ p_ for p_ in pts]
        tx = [v.x / -v.z for v in c if v.z < -1e-3]
        ty = [v.y / -v.z for v in c if v.z < -1e-3]
        cx, cy = 0.5 * (min(tx) + max(tx)), 0.5 * (min(ty) + max(ty))
        d = cam.matrix_world.to_3x3() @ Vector((cx, cy, -1.0))
        cam.rotation_quaternion = d.to_track_quat('-Z', 'Y')
        bpy.context.view_layer.update()
    ex, ey = 0.5 * (max(tx) - min(tx)), 0.5 * (max(ty) - min(ty))
    cd.lens = max(14.0, min(120.0, 18.0 * fill / max(ex, ey * Wr / Hr, 1e-4)))
    bpy.context.view_layer.update()


def px(q):
    uv = world_to_camera_view(sc, cam, q)
    return (uv.x * Wr, (1 - uv.y) * Hr)


def front_side(st):
    dv = (M3 @ Vector(st['dir'])).normalized()
    side = dv.cross(Vector((0, 0, 1)))
    if side.length < 0.35:
        side = M3 @ Vector(axes('chest', st['t'])[0].tolist())
    side.normalize()
    fwd = M3 @ Vector((-axes('head', st['t'])[1]).tolist())
    if side.dot(fwd) < 0:
        side = -side
    return dv, side, fwd.normalized()


def contact(st):
    gob = bpy.data.objects.get(f"{st.get('prop')}_{st['name']}")
    return Mw @ Vector(gob['contact'] if gob is not None and 'contact' in gob else st['point'])


t_hi = ev.get('head_impact')
beats = []
if ko and '--story' in a and opt('--story', '') == 'misread':
    # the setup: she reads it low and drops her hands (kick low in frame), then it climbs
    beats += [('read', ko['t'] - 0.20), ('rise', ko['t'] - 0.067)]
if ko:
    beats += [('impact', ko['t'] + 1.0 / fps), ('snap', ko['t'] + 0.13)]
for st, tag in ((ko, 'whip'), (fu, 'whip_fu')):
    if st:
        ts = np.arange(st['t'] + 1.0 / fps, st['t'] + 0.30, 1.0 / fps)
        dev = [whip_dev(st, tt) for tt in ts]
        # the snap, not the end of the fall: first frame past 3/4 of the window's peak turn
        k = int(np.argmax(np.array(dev) >= max(WHIP_DEG, 0.75 * max(dev)))) if max(dev) >= WHIP_DEG else int(np.argmax(dev))
        print(f'[action] {tag}: peak head turn {dev[k]:.0f} deg at +{ts[k] - st["t"]:.3f} s', flush=True)
        if dev[k] >= WHIP_DEG:
            beats += [(tag, float(ts[k]))]
beats += [('stagger', 0.5 * (ko['t'] + ev.get('down', t_hi)) if ko else 1.0)]
if t_hi:
    beats += [('canvas', t_hi + 0.02)]
if fu:
    beats += [('followup', fu['t'] + 1.0 / fps), ('face', fu['t'] + 0.7)]
elif t_hi:
    beats += [('face', t_hi - 0.12)]
beats += [('climax', min(Tend - 0.05, (fu['t'] if fu else t_hi) + 3.0))]
# a planned sequence (tools/plan_sequence.py) replaces the house beat list: [{name, t, marks}]
# where marks is a list of 'streak_head', 'focus_head', 'twitch' (empty = a quiet panel)
SEQ = {b['name']: b for b in json.load(open(opt('--beats', '')))} if opt('--beats', '') else {}
if SEQ:
    beats = [(b['name'], float(b['t'])) for b in SEQ.values()]
# ---------------------------------------------------------------- video mode
# --video CUTS.json: render a real-time clip (default 25 fps) frame by frame with the same in-scene
# FX, from a cut list: [{t0, t1, cam: {loc, target, lens, roll}} | {t0, t1, scene_cam: NAME} |
# {t0, t1, track: {loc: [x,y,z], fill: 0.75}}] (world coords). Frames already on disk are
# skipped, so a long job can be stopped and resumed (owner 2026-11-14: overnight renders).
VIDEO = opt('--video', '')
if VIDEO:
    cuts = json.load(open(VIDEO))
    vfps = float(opt('--vfps', '25'))
    vdir = os.path.join(outd, 'frames')
    os.makedirs(vdir, exist_ok=True)
    nfr = int(math.floor(Tend * vfps))
    i0 = int(math.ceil(float(opt('--vfrom', '0')) * vfps))   # owner 2026-11-16: render only from t >= vfrom
    CUR['beat'] = 'video'
    body_names = [b for b in bn if b != 'world' and not b.startswith(('rope', 'post', 'KO'))]

    def body_pts(t):
        return [W(P(b, t)) for b in body_names] + [W(P('head', t)) + Vector((0, 0, 0.12))]

    track = {}
    for ci, c_ in enumerate(cuts):
        if 'track' in c_:
            loc_ = Vector(c_['track']['loc'])
            fill_ = float(c_['track'].get('fill', 0.75))
            ts = [i / vfps for i in range(nfr) if c_['t0'] <= i / vfps < c_['t1']]
            aims, lens_ = [], []
            for t in ts:
                pts = body_pts(t)
                ctr = sum(pts, Vector()) / len(pts)
                for _ in range(3):
                    f_ = (ctr - loc_).normalized()
                    r_ = f_.cross(Vector((0, 0, 1))).normalized()
                    u_ = r_.cross(f_)
                    tx = [(p_ - loc_).dot(r_) / (p_ - loc_).dot(f_) for p_ in pts]
                    ty = [(p_ - loc_).dot(u_) / (p_ - loc_).dot(f_) for p_ in pts]
                    cx, cy = 0.5 * (min(tx) + max(tx)), 0.5 * (min(ty) + max(ty))
                    ctr = loc_ + (f_ + r_ * cx + u_ * cy) * (ctr - loc_).length
                ex, ey = 0.5 * (max(tx) - min(tx)), 0.5 * (max(ty) - min(ty))
                aims.append(np.array(ctr))
                lens_.append(min(135.0, max(18.0, 18.0 * fill_ / max(ex, ey * 16 / 9, 1e-4))))
            kk = max(1, int(1.2 * vfps))
            ker = np.ones(kk) / kk
            A_ = np.array(aims)
            pad_ = lambda x: np.concatenate([np.repeat(x[:1], kk, 0), x, np.repeat(x[-1:], kk, 0)])  # noqa: E731
            L_ = np.convolve(pad_(np.array(lens_)), ker, 'same')[kk:-kk]
            A_ = np.stack([np.convolve(pad_(A_[:, j]), ker, 'same')[kk:-kk] for j in range(3)], 1)
            for t, a_, l_ in zip(ts, A_, L_):
                track[round(t, 4)] = (loc_, Vector(a_.tolist()), float(l_))
    def bisect_order(n):          # owner 2026-11-15: first, last, then midpoints breadth-first, so a
        out, q = [0, n - 1], [(0, n - 1)]   # sparse but evenly spread preview exists at every stage
        while q:
            nq = []
            for a_, b_ in q:
                if b_ - a_ > 1:
                    m_ = (a_ + b_) // 2
                    out.append(m_)
                    nq += [(a_, m_), (m_, b_)]
            q = nq
        return list(dict.fromkeys(i for i in out if 0 <= i < n))
    done = 0
    for i in [i0 + j for j in bisect_order(nfr - i0)]:
        t = i / vfps
        p_out = os.path.join(vdir, f'{i:05d}.png')
        if os.path.exists(p_out):
            continue
        c_ = next((c for c in cuts if c['t0'] <= t < c['t1']), cuts[-1])
        fr = t * fps + 1.0
        sc.frame_set(int(fr), subframe=fr - int(fr))
        hw = W(P('head', t))
        if 'scene_cam' in c_:
            sc.camera = bpy.data.objects[c_['scene_cam']]
        else:
            sc.camera = cam
            if 'track' in c_:
                loc_, a_, l_ = track[round(t, 4)]
                aim(loc_, a_, l_, focus=hw, fstop=5.6)
            else:
                cm = c_['cam']
                aim(Vector(cm['loc']), Vector(cm['target']), float(cm['lens']), float(cm.get('roll', 0.0)),
                    focus=hw, fstop=5.6)
        sc.render.filepath = p_out
        bpy.ops.render.render(write_still=True)
        done += 1
        print(f'[video] {i + 1}/{nfr} t={t:.3f}', flush=True)
    print(f'[video] rendered {done}, total {len(os.listdir(vdir))}/{nfr} -> {vdir}')
    raise SystemExit(0)
PROXY = opt('--proxy', '')
PX = {}


def export_proxy(beat, t, f):
    """Low-poly posed proxy of her (+ glove) for the owner's browser camera editor, and the
    camera this script would use. glTF is Y-up: the page converts; saved cameras come back in
    Blender world coords (loc, target, lens, roll)."""
    dg = bpy.context.evaluated_depsgraph_get()
    made = []
    for o in [o for o in sc.objects if o.type == 'MESH' and not o.hide_render and o.visible_get()]:
        nm = o.name
        low = nm.lower()
        part = ('hair' if 'hair' in low else 'glove' if low.startswith('glove') else
                'suit' if any(k in low for k in ('leotard', 'bra', 'brief', 'suit')) else
                'body' if 'genesis 8 female mesh' in low else None)
        if part is None:
            continue
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
        me.transform(o.matrix_world)
        ob = bpy.data.objects.new(f'p_{part}_{len(made)}', me)
        sc.collection.objects.link(ob)
        ratio = {'hair': 0.03, 'body': 0.12, 'suit': 0.2, 'glove': 0.5}[part]
        dm = ob.modifiers.new('dec', 'DECIMATE')
        dm.ratio = ratio
        made.append(ob)
    bpy.ops.object.select_all(action='DESELECT')
    for ob in made:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = made[0]
    for ob in made:
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.modifier_apply(modifier='dec')
    os.makedirs(PROXY, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(PROXY, f'{beat}.glb'), use_selection=True,
                              export_materials='NONE', export_animations=False, export_yup=True,
                              export_apply=True, export_normals=True, export_texcoords=False)
    for ob in made:
        me = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(me)
    q = cam.matrix_world.to_quaternion()
    fwd = q @ Vector((0, 0, -1))
    PX[beat] = {'t': round(t, 3), 'frame': f,
                'cam': {'loc': list(cam.location), 'target': list(cam.location + fwd * 2.0),
                        'lens': cd.lens, 'roll': 0.0, 'quat': list(q)},
                'head': list(W(P('head', t))), 'pelvis': list(W(P('pelvis', t))),
                'feet': list((W(P('foot_L', t)) + W(P('foot_R', t))) * 0.5),
                'chest_fwd': list(M3 @ Vector((-axes('chest', t)[1]).tolist())),
                'head_fwd': list(M3 @ Vector((-axes('head', t)[1]).tolist())),
                'head_up': list(M3 @ Vector((axes('head', t)[2]).tolist())),
                'glove': (list(bpy.data.objects[f"{ko.get('prop')}_{ko['name']}"].matrix_world.translation)
                          if bpy.data.objects.get(f"{ko.get('prop')}_{ko['name']}") else None)}
    json.dump(PX, open(os.path.join(PROXY, 'proxy.json'), 'w'), indent=1)
    print(f'[proxy] {beat} t={t:.3f} frame {f}')


report = {}
for beat, t in beats:
    if only and beat not in only:
        continue
    f = int(round(t * fps)) + 1
    sc.frame_set(f)
    CUR['beat'] = beat
    mk = {}                                     # what to draw, in px
    if beat in ('impact', 'followup'):
        st = ko if beat == 'impact' else fu
        pt = contact(st)
        dv, side, fwd = front_side(st)
        gs = None
        if beat == 'impact' and st.get('prop') == 'shin':
            # kick: front quarter on the side it arrives from. Square-on, the kicker's shin sits
            # between the lens and her face (true, but it hides the reaction)
            loc = pt + fwd * 0.70 - dv * 0.50 + Vector((0, 0, -0.30))   # low: she is folded over, looking down
            aim(loc, pt + dv * 0.04, 40, roll_deg=11, focus=pt, fstop=6.3)
        elif beat == 'impact':
            gob = bpy.data.objects.get(f"{st.get('prop')}_{st['name']}")
            gs = None
            if gob is not None:
                # where the glove actually came from (its authored arc, 3 frames out)
                sc.frame_set(f - 3)
                g3 = gob.matrix_world.translation.copy()
                sc.frame_set(f)
                gs = g3 - pt
                gs.z = 0.0
                gs = gs.normalized() if gs.length > 0.03 else None
            if gs is not None and abs(gs.dot(fwd)) < 0.8:
                # hook: nearly square in front of her face, a little toward the glove side, so the
                # glove crosses the jaw silhouette and the head turn reads (2026-11-13)
                loc = pt + fwd * 0.72 + gs * 0.16 + Vector((0, 0, -0.08))
                aim(loc, pt - gs * 0.03, 40, roll_deg=9, focus=pt, fstop=6.3)
            else:
                # low, mostly side-on: the glove and the jaw read past her guard
                loc = pt + side * 0.80 + fwd * 0.18 - dv * 0.10 + Vector((0, 0, -0.30))
                aim(loc, pt + dv * 0.06, 40, roll_deg=11, focus=pt, fstop=6.3)
        if beat == 'followup':
            loc = pt + side * 0.75 + fwd * 0.25 + Vector((0, 0, 0.42))
            aim(loc, pt, 38, roll_deg=-12, focus=pt, fstop=6.3)
        c = px(pt)
        back = px(pt - dv * 0.4)
        if beat == 'impact' and gs is not None:
            back = px(pt + gs * 0.4)            # streak along the glove's real approach
        mk = dict(streak=(c, (c[0] - back[0], c[1] - back[1])))
        if beat in FINISH:
            mk.update(focus=c, bloom=c)
    elif beat == 'snap':
        h = W(P('head', t))
        g = guard.matrix_world.translation.copy() if guard else h
        mid = (h * 0.55 + g * 0.45)
        dv, side, fwd = front_side(ko)
        loc = mid + side * 1.55 + fwd * 0.55 + Vector((0, 0, -0.25))
        aim(loc, mid, 35, roll_deg=-9, focus=h, fstop=4.0)
        h0 = W(P('head', t - 0.08))
        mk = dict(streak=(px(h), (px(h)[0] - px(h0)[0], px(h)[1] - px(h0)[1])))
    elif beat in ('read', 'rise'):
        # front quarter on the kick side, hip height, wide enough for the whole leg arc
        # (VFX bible: headkick -> front-quarter, wide); the shin guard is the only opponent part
        lft, back, up = axes('chest', t)
        fwdc = M3 @ Vector((-back).tolist())
        sidec = M3 @ Vector(lft.tolist())
        hw = W(P('head', t))
        pv = W(P('pelvis', t))
        prop = bpy.data.objects.get(f"{ko.get('prop')}_{ko['name']}")
        pp = prop.matrix_world.translation.copy() if prop else pv
        # frame her head and the shin guard together, with room around both
        # ...and her hips: the misread is her hands dropping to cover low, which a head-height
        # glove alone would crop out (hook take, 2026-11-13)
        lo = pp if pp.z < pv.z else pv
        tgt = (hw + lo) * 0.5 + Vector((0, 0, 0.05))
        span = max((hw - pp).length, (hw - pv).length)
        dist = max(1.6, span * 2.4) if beat == 'read' else max(1.4, span * 2.6)
        vdir = (fwdc * 0.85 + sidec * 0.55).normalized()
        if pp.z > pv.z:
            # head-height glove (hook): centre on the box around head (+crown), glove and hips, and
            # back off until all of it fits with margin; the glove is nearer the lens than her head
            # and projects high, so a pelvis-to-head centre cropped it (2026-11-13)
            pts = [hw + Vector((0, 0, 0.14)), pp, pv]
            tgt = Vector([0.5 * (min(p_[i] for p_ in pts) + max(p_[i] for p_ in pts)) for i in range(3)])
            ext = max((p_ - tgt).length for p_ in pts)
            dist = max(dist, ext * 3.4)
        aim(tgt + vdir * dist + Vector((0, 0, 0.10)), tgt, 40, focus=hw, fstop=5.6)
        mk = {}
        if beat == 'rise' and prop is not None:
            sc.frame_set(f - 2)
            p0 = prop.matrix_world.translation.copy()
            sc.frame_set(f)
            c = px(pp)
            c0 = px(p0)
            mk = dict(streak=(c, (c[0] - c0[0], c[1] - c0[1])))
    elif beat in ('whip', 'whip_fu'):
        st = ko if beat == 'whip' else fu
        hw = W(P('head', t))
        lft, back, up = axes('chest', st['t'])
        fwdc = M3 @ Vector((-back).tolist())
        sidec = M3 @ Vector(lft.tolist())
        # front quarter on the side the blow drives her face toward (away from the striking limb)
        dvs = (M3 @ Vector(st['dir'])).normalized()
        dvs.z = 0.0
        if abs(dvs.normalized().dot(fwdc.normalized())) > 0.7:
            # straight shot: the head snaps back/up in her sagittal plane -> profile camera
            # (VFX bible: straight -> side), slightly in front so the face reads
            loc = hw + sidec * 0.72 + fwdc * 0.30 + Vector((0, 0, 0.02))
            aim(loc, hw + fwdc * 0.03, 45, roll_deg=-8, focus=hw, fstop=4.0)
        else:
            loc = hw + fwdc * 0.78 + dvs.normalized() * 0.50 + Vector((0, 0, -0.02))
            aim(loc, hw + dvs.normalized() * 0.04, 45, roll_deg=-8, focus=hw, fstop=4.0)
        hp = W(P('head', t - 2.0 / fps))
        mk = dict(streak=(px(hw), (px(hw)[0] - px(hp)[0], px(hw)[1] - px(hp)[1])), focus=px(hw))
    elif beat == 'stagger':
        lft, back, _ = axes('chest', t)
        cc = (P('chest', t) + P('pelvis', t)) / 2
        dd = flat(lft) * 0.85 + flat(-back) * 0.5
        dd = dd / np.linalg.norm(dd)
        aim(W(cc + dd * 2.5 + np.array([0, 0, -0.25])), W(cc + np.array([0, 0, 0.05])), 32, roll_deg=7,
            focus=W(cc), fstop=5.6)
        fit_body(t)
        mk = dict(twitch=[(twitchiest(t), 'out')])
    elif beat == 'canvas':
        hh = P('head', t)
        ax = flat(P('head', t) - P('pelvis', t))
        perp = np.array([-ax[1], ax[0], 0])
        aim(W(hh + perp * 0.95 + ax * 0.45 + np.array([0, 0, 0.05])), W(hh - ax * 0.5 + np.array([0, 0, 0.06])),
            26, roll_deg=-13, focus=W(hh), fstop=3.5)
        mk = dict(twitch=[(twitchiest(t), 'out')])
    elif beat == 'face' and not fu:
        # no follow-up: her face just before the canvas; own camera on the head (the house
        # face camera loses line of sight mid-fall)
        hw = W(P('head', t))
        lft, back, up_ = axes('head', t)
        fwd_h = M3 @ Vector((-back).tolist())
        loc = hw + fwd_h * 0.55 + Vector((0, 0, 0.30)) + (M3 @ Vector(lft.tolist())) * 0.15
        aim(loc, hw, 50, focus=hw, fstop=3.2)
        mk = {}
    elif beat == 'face':
        fc = bpy.data.objects.get('cam_face')
        cam.location = fc.matrix_world.translation.copy()
        cam.rotation_mode = 'QUATERNION'
        cam.rotation_quaternion = fc.matrix_world.to_quaternion()
        cd.lens = fc.data.lens
        cd.dof.use_dof = True
        cd.dof.focus_distance = (W(P('head', t)) - cam.location).length
        cd.dof.aperture_fstop = 2.2
        bpy.context.view_layer.update()
        mk = {}
    elif beat == 'climax' and beat not in SEQ:
        ax = flat(P('pelvis', t) - P('head', t))
        perp = np.array([-ax[1], ax[0], 0])
        k = (P('shin_L', t) + P('shin_R', t)) / 2
        cen = (P('pelvis', t) + k) / 2 * 0.6 + P('chest', t) * 0.4
        aim(W(cen + perp * 2.0 + ax * 0.9 + np.array([0, 0, 0.18])), W(cen + np.array([0, 0, 0.22])), 28,
            roll_deg=10, focus=W(cen), fstop=5.0)
        fit_body(t)
        mk = dict(twitch=[(twitchiest(t), 'out')])
    if beat in SEQ and beat not in ('read', 'rise', 'impact', 'whip', 'snap', 'stagger', 'canvas', 'face'):
        # planned panel: camera from the plan (--cams), marks from its spec
        hw = W(P('head', t))
        aim(hw, hw + Vector((0, 1, 0)), 35)     # replaced by the --cams entry for this beat
        mk = {}
        want = SEQ[beat].get('marks', [])
        if 'streak_head' in want:
            h0 = W(P('head', t - 0.06))
            mk['streak'] = (px(hw), (px(hw)[0] - px(h0)[0], px(hw)[1] - px(h0)[1]))
        if 'focus_head' in want:
            mk['focus'] = px(hw)
        if 'twitch' in want:
            mk['twitch'] = [(twitchiest(t), 'out')]
    # spit only reads in a face close-up; from further out the droplets look fake (owner)
    # spit: only on frames where the head is whipped (turned to the side or up by at least
    # WHIP_DEG from where it was before the blow), and only in close framing (owner rules)
    close = beat in ('impact', 'followup', 'face', 'whip', 'whip_fu')
    for o in coll.objects:
        if o.name.startswith('KO_spit'):
            st_ = fu if o.name.startswith('KO_spit_fu') else ko
            o.hide_render = not (close and st_ and st_['t'] <= t <= st_['t'] + 0.45 and whip_dev(st_, t) >= WHIP_DEG)
    if PROXY:
        export_proxy(beat, t, f)
        continue
    p_clean = os.path.join(outd, f'{name}_{beat}_clean.png')
    sc.render.filepath = p_clean
    if not ('--reuse' in a and os.path.exists(p_clean)):
        bpy.ops.render.render(write_still=True)
    # ------------------------------------------------ marks
    img = Image.open(p_clean).convert('RGBA')
    # lines take the colour that reads on this frame: white on the dark arena, ink on the canvas
    lum = float(np.asarray(img.convert('L'), float).mean())
    line = (255, 255, 255) if lum < 120 else (38, 36, 44)
    ksz = Wr / 1280.0
    if marks:
        L = AF.Layer(img.size)
        if 'shock' in mk and '--shock' in a:
            AF.shock_lines(L, n=60, seed=f)
        if 'focus' in mk:
            AF.focus_lines(L, mk['focus'], clear=0.55 if beat in ('impact', 'followup') else 0.68,
                           n=90, seed=f, rgba=line + (115 if lum < 120 else 95,), width=(1, 4))
        if 'streak' in mk:
            c, d = mk['streak']
            AF.streaks(L, c, d, n=14, seed=f + 1, spread=90, back=170, length=(80, 260),
                       rgba=line + (140,), width=(1, 3))
        for j, (body, mode) in enumerate(mk.get('twitch', [])):
            q = px(W(P(body, t)))
            cen = px(W(P('chest', t)))
            out = (q[0] - cen[0], q[1] - cen[1]) if mode == 'out' else ((0, -1) if mode == 'up' else (1, -0.4))
            if 0 < q[0] < Wr and 0 < q[1] < Hr:
                AF.twitch_cluster(L, q, out, size=(30 if beat != 'face' else 40) * ksz, seed=f + j, k=2)
        img = L.over(img)
        if 'bloom' in mk:
            img = AF.bloom(img, mk['bloom'], 0.10 * Wr, 0.45)
        img = AF.vignette(img, 0.28)
    p = os.path.join(outd, f'{name}_{beat}.png')
    img.convert('RGB').save(p)
    report[beat] = {'t': round(t, 3), 'frame': f, 'file': p, 'marks': sorted(k for k in mk),
                    'twitch': [b_ for b_, _ in mk.get('twitch', [])], 'head_turn_deg': [round(v, 1) for v in head_turn(t)],
                    'spit': any(not o.hide_render for o in coll.objects if o.name.startswith('KO_spit'))}
    print('[action]', beat, f't={t:.3f}', 'frame', f, flush=True)
if PROXY:
    # the ring, once: canvas, frame/posts/ropes, pads, platform (decimated)
    dg = bpy.context.evaluated_depsgraph_get()
    made = []
    for o in sc.objects:
        if o.type == 'MESH' and any(k in o.name for k in ('RingGymMM_Canvas', 'RingGymMM_FrameSection',
                                                           'RopePads', 'RingGymMM_Platform')):
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
            me.transform(o.matrix_world)
            ob = bpy.data.objects.new('ring_' + o.name.split('.')[0], me)
            sc.collection.objects.link(ob)
            dm = ob.modifiers.new('dec', 'DECIMATE')
            dm.ratio = 0.15
            made.append(ob)
    if made:
        bpy.ops.object.select_all(action='DESELECT')
        for ob in made:
            ob.select_set(True)
            bpy.context.view_layer.objects.active = ob
            bpy.ops.object.modifier_apply(modifier='dec')
        bpy.ops.export_scene.gltf(filepath=os.path.join(PROXY, 'ring.glb'), use_selection=True,
                                  export_materials='NONE', export_animations=False, export_yup=True,
                                  export_normals=True, export_texcoords=False)
        print('[proxy] ring', [o.name for o in made])
    raise SystemExit(0)
rp_ = os.path.join(outd, f'{name}_frames.json')
old_ = json.load(open(rp_)) if os.path.exists(rp_) else {}
old_.update(report)
json.dump(old_, open(rp_, 'w'), indent=1)
print('done', outd)
