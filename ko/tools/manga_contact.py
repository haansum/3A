"""Contact map as an action-manga page: the take's beats as inked panels (screentone, speed lines,
impact bursts, katakana sound effects, caption boxes carrying the measured numbers), and an ink
contact timeline along the bottom (which parts are on the canvas when, how hard, L(t)).

    python3 tools/manga_contact.py SCENE.blend SIM.npz OUT.png [--title "..."] [--samples 32]
        [--beats uppercut|headkick] [--mass 50]

Renders its own panels from the baked scene (film transparent, composited on white), so it needs
the stills scene with the strike props in it. All numbers on the page come from sim.npz; panel
choice, framing and lettering are authored (by eye). Lettering is generic onomatopoeia.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manga_fx as MF  # noqa: E402

a = sys.argv[1:]
src, simp, out = a[:3]
opt = lambda k, d: a[a.index(k) + 1] if k in a else d  # noqa: E731
title = opt('--title', 'KO')
style = opt('--beats', 'uppercut')
PROPN = {'glove': 'glove', 'shin': 'shin guard'}
CAPS = {'uppercut': dict(target='jaw', B='TEETER', F='legs scissored, straining past full tone'),
        'headkick': dict(target='chin, from her left', B='OUT ON HER FEET', F='tonic posture at its peak, tremor on')}[style]
spp = int(opt('--samples', 32))
mass = float(opt('--mass', 50.0))
BW = mass * 9.81
tmpd = os.path.splitext(out)[0] + '_panels'
os.makedirs(tmpd, exist_ok=True)

z = np.load(simp, allow_pickle=True)
ev = dict(json.loads(str(z['events'])))
evd = dict(json.loads(str(z['event_data']))) if 'event_data' in z.files else {}
strikes = {s['name']: s for s in json.loads(str(z['strikes']))}
bn = [str(b) for b in z['body_names']]
gn = [str(g) for g in z['geom_names']]
X, Q, T, dt = z['xpos'], z['xquat'], z['t'], float(z['dt'])
Lt = z['L'] if 'L' in z.files else None
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
    return R[:, 0], R[:, 1], R[:, 2]          # her +x (left), +y (back), +z (up) in world


def flat(v):
    v = np.array(v, float)
    v[2] = 0
    return v / max(np.linalg.norm(v), 1e-9)


# ---------------------------------------------------------------- page layout (px)
PW, M_, G = 1240, 40, 18
IW = PW - 2 * M_
rows = [(110, 450), (578, 420), (1016, 420), (1454, 340)]
TL_Y, TL_H = 1820, 370
PH = TL_Y + TL_H + 40
sl = 34                                         # slant of the diagonal gutters (px)


def quad(x0, x1t, x1b, y, h, x0b=None):
    return [(x0, y), (x1t, y), (x1b, y + h), (x0b if x0b is not None else x0, y + h)]


y1, h1 = rows[1]
y2, h2 = rows[2]
cut1 = M_ + int(IW * 0.44)
cut2 = M_ + int(IW * 0.58)
PANELS = {
    'A': quad(M_, PW - M_, PW - M_, *rows[0]),
    'B': quad(M_, cut1 + sl, cut1 - sl, y1, h1),
    'C': [(cut1 + sl + G, y1), (PW - M_, y1), (PW - M_, y1 + h1), (cut1 - sl + G, y1 + h1)],
    'D': quad(M_, cut2 - sl, cut2 + sl, y2, h2),
    'E': [(cut2 - sl + G, y2), (PW - M_, y2), (PW - M_, y2 + h2), (cut2 + sl + G, y2 + h2)],
    'F': quad(M_, PW - M_, PW - M_, *rows[3]),
}


def bbox(poly):
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


# ---------------------------------------------------------------- beats (authored)
t_ko = ev.get('ko_strike', float(z['t_ko']))
t_hi = ev.get('head_impact', t_ko + 1.5)
t_fu = ev.get('followup_1')
fu = strikes.get('followup_1')
ko = strikes.get('ko_strike')
BEATS = {
    'A': dict(kind='strike', strike='ko_strike', t=t_ko),
    'B': dict(kind='full', t=0.5 * (t_ko + ev.get('down', t_hi)), side=+1),
    'C': dict(kind='canvas', t=t_hi + 0.02),
    'D': dict(kind='strike', strike='followup_1', t=t_fu) if fu else dict(kind='canvas', t=t_hi + 0.6),
    # face: after the follow-up when there is one; otherwise just before the canvas (in the
    # head-kick takes she settles face-down and the face camera has no clear view afterwards)
    'E': dict(kind='face', t=(t_fu + 0.7) if t_fu else t_hi - 0.12),
    'F': dict(kind='climax', t=min(Tend - 0.05, (t_fu or t_hi) + 3.0)),
}

# ---------------------------------------------------------------- render panels
bpy.ops.wm.open_mainfile(filepath=src, use_scripts=False)
sc = bpy.context.scene
fps = sc.render.fps / sc.render.fps_base
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = spp
sc.cycles.use_denoising = True
sc.render.film_transparent = True
sc.render.image_settings.file_format = 'PNG'
sc.render.image_settings.color_mode = 'RGBA'
sc.render.resolution_percentage = 100
sc.render.use_compositing = False
sc.render.use_sequencer = False
sc.render.use_motion_blur = False
root = bpy.data.objects.get('KO_canonical')
Mw = root.matrix_world.copy()
for o in bpy.data.objects:                      # panels: the figure and the canvas, no ring dressing
    if o.type == 'MESH' and any(k in o.name.lower() for k in ('rope', 'post', 'pad', 'apron', 'floor', 'truss')):
        o.hide_render = True
cv_ = bpy.data.objects.get('canvas')
if cv_ is not None:                             # canvas -> shadow catcher: white page, her shadow kept
    cv_.is_shadow_catcher = True
cd = bpy.data.cameras.new('panel_cam')
cd.clip_start = 0.02
cam = bpy.data.objects.new('panel_cam', cd)
sc.collection.objects.link(cam)
sc.camera = cam


def W(v):
    return Mw @ Vector(list(map(float, v)))


def aim(loc, tgt, lens, roll_up=(0, 0, 1)):
    cam.location = loc
    cd.lens = lens
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (tgt - loc).to_track_quat('-Z', 'Y')
    bpy.context.view_layer.update()


focus = {}
reuse = '--reuse' in a and os.path.exists(os.path.join(tmpd, 'focus.json'))
if reuse:
    focus = json.load(open(os.path.join(tmpd, 'focus.json')))
redo = opt('--redo', '')
for key, b in [(k, v) for k, v in BEATS.items() if not reuse or k in redo]:
    x0, y0, x1, y1_ = bbox(PANELS[key])
    sc.render.resolution_x, sc.render.resolution_y = x1 - x0, y1_ - y0
    t = b['t']
    f = int(round(t * fps)) + 1
    pts = []
    if b['kind'] == 'strike':
        st = strikes[b['strike']]
        gob = bpy.data.objects.get(f"{st.get('prop')}_{st['name']}")
        pt = Mw @ Vector(gob['contact'] if gob is not None and 'contact' in gob else st['point'])
        dv = (Mw.to_3x3() @ Vector(st['dir'])).normalized()
        side = dv.cross(Vector((0, 0, 1)))
        if side.length < 0.35:
            side = Mw.to_3x3() @ Vector(axes('chest', t)[0].tolist())
        side.normalize()
        fwd = Mw.to_3x3() @ Vector((-axes('head', st['t'])[1]).tolist())   # her front: face and prop read
        if side.dot(fwd) < 0:
            side = -side
        # A: from the side of the strike, slightly in front of her; D (she is supine): higher
        up = 0.06 if key == 'A' else 0.45
        aim(pt + side * 0.95 - dv * 0.25 + Vector((0, 0, up)), pt + dv * 0.02, 38)
        f = int(round(st['t'] * fps)) + 1
        pts = [pt]
    elif b['kind'] == 'full':
        lft, back, _ = axes('chest', t)
        c = (P('chest', t) + P('pelvis', t)) / 2
        d_ = flat(lft) * b.get('side', 1)
        aim(W(c + d_ * 2.9 + np.array([0, 0, 0.0])), W(c + np.array([0, 0, -0.05])), 34)
        pts = [W(P('head', t))]
    elif b['kind'] == 'canvas':
        h = P('head', t)
        ax = flat(P('head', t) - P('pelvis', t))
        perp = np.array([-ax[1], ax[0], 0])
        aim(W(h + perp * 1.15 + ax * 0.25 + np.array([0, 0, 0.12])),
            W(h - ax * 0.45 + np.array([0, 0, 0.05])), 30)
        pts = [W(h)]
    elif b['kind'] == 'face':
        fc = bpy.data.objects.get('cam_face')
        if fc is not None:
            sc.frame_set(f)
            cam.location = fc.matrix_world.translation.copy()
            cam.rotation_mode = 'QUATERNION'
            cam.rotation_quaternion = fc.matrix_world.to_quaternion()
            cd.lens = fc.data.lens * 0.9
        pts = [W(P('head', t))]
    elif b['kind'] == 'climax':
        ax = flat(P('pelvis', t) - P('head', t))          # toward her feet
        perp = np.array([-ax[1], ax[0], 0])
        k = (P('shin_L', t) + P('shin_R', t)) / 2
        cen = (P('pelvis', t) + k) / 2 * 0.6 + P('chest', t) * 0.4
        aim(W(cen + perp * 2.6 + ax * 0.5 + np.array([0, 0, 0.30])), W(cen + np.array([0, 0, 0.22])), 30)
        pts = [W(k), W(P('foot_L', t)), W(P('foot_R', t)), W(P('chest', t))]
    sc.frame_set(f)
    p = os.path.join(tmpd, f'{key}.png')
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    Wr, Hr = sc.render.resolution_x, sc.render.resolution_y
    pp = []
    for q in pts:
        uv = world_to_camera_view(sc, cam, q)
        pp.append((uv.x * Wr, (1 - uv.y) * Hr))
    focus[key] = pp
    print('[manga] panel', key, b['kind'], f't={t:.2f}', 'focus', [tuple(round(v) for v in q) for q in pp])

json.dump(focus, open(os.path.join(tmpd, 'focus.json'), 'w'))
# ---------------------------------------------------------------- ink each panel
page = Image.new('RGB', (PW, PH), (255, 255, 255))
dr = ImageDraw.Draw(page)


INK = {'E': dict(cell=3, black=0.02, white=0.93, edge=0.45, gamma=0.65, lo=1, hi=99)}


def ink_panel(key):
    x0, y0, x1, y1_ = bbox(PANELS[key])
    im = Image.open(os.path.join(tmpd, f'{key}.png')).convert('RGBA')
    bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
    rgb = Image.alpha_composite(bg, im).convert('RGB')
    alpha = im.split()[3]
    fig = alpha.point(lambda v: 255 if v > 245 else 0)
    kw = dict(cell=5, black=0.10, white=0.88, gamma=1.1)
    kw.update(INK.get(key, {}))
    ink = MF.to_manga(rgb, mask=fig, **kw)
    # shadow on the canvas (partial alpha) -> screentone ground
    shadow = (Image.new('RGB', im.size, (255, 255, 255)) if key == 'E' else
              MF.screentone(alpha.point(lambda v: 255 - int(v * 0.55)), cell=4).convert('RGB'))
    fg = Image.composite(ink, shadow, fig)
    alpha = fig
    # silhouette contour (heavier line where the figure meets the white ground)
    edge = alpha.point(lambda v: 255 if v > 8 else 0).filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
    fg.paste((0, 0, 0), (0, 0), edge)
    return fg, alpha, (x0, y0)


def place(key, im):
    x0, y0, x1, y1_ = bbox(PANELS[key])
    mask = Image.new('L', page.size, 0)
    ImageDraw.Draw(mask).polygon(PANELS[key], fill=255)
    layer = Image.new('RGB', page.size, (255, 255, 255))
    layer.paste(im, (x0, y0))
    page.paste(layer, (0, 0), mask)


def letter(key, xy_local, text, size, angle=-12):
    x0, y0, _, _ = bbox(PANELS[key])
    MF.sfx(page, text, (x0 + xy_local[0], y0 + xy_local[1]), size, angle=angle)


def cap(key, corner, lines, size=17):
    x0, y0, x1, y1_ = bbox(PANELS[key])
    probe = Image.new('RGB', (10, 10))
    wd, ht = MF.caption(probe, (0, 0), lines, size=size)
    xy = {'tl': (x0 + 14, y0 + 12), 'tr': (x1 - wd - 14, y0 + 12),
          'bl': (x0 + 14, y1_ - ht - 12), 'br': (x1 - wd - 14, y1_ - ht - 12)}[corner]
    if (key, corner) in (('C', 'tl'), ('E', 'bl')):      # the slanted gutter leans in there
        xy = (xy[0] + 2 * sl + 4, xy[1])
    MF.caption(page, xy, lines, size=size)


def fmt_t(t):
    return f'{t:.2f} s'


# A: the uppercut -- inked, radial focus lines, burst on the contact, big ゴッ
fg, al, _ = ink_panel('A')
c = focus['A'][0]
MF.speed_lines(fg, c, n=140, inner=0.15, seed=7)
fg.paste(ink_panel('A')[0], (0, 0), al.point(lambda v: 255 if v > 8 else 0))
MF.burst(fg, c, 26, 70, spikes=16, seed=2)
place('A', fg)
x0, y0, x1, y1_ = bbox(PANELS['A'])
letter('A', (min(c[0] + 120, x1 - x0 - 330), 18), 'ゴッ', 150, angle=-14)
if ko:
    cap('A', 'bl', [f'{fmt_t(ko["t"])}  KO STRIKE', f'{PROPN.get(ko.get("prop"), "strike")} → {CAPS["target"]}'], 18)

# B: the teeter -- full figure, consciousness readout
fg, al, _ = ink_panel('B')
place('B', fg)
tB = BEATS['B']['t']
LB = float(Lt[idx(tB)]) if Lt is not None else None
cap('B', 'tl', [f'{fmt_t(tB)}  {CAPS["B"]}', f'L = {LB:.2f}' if LB is not None else 'out on her feet'], 16)
letter('B', (int((cut1 - M_) * 0.55), h1 - 150), 'フラッ', 64, angle=8)

# C: back of the head meets the canvas -- low, horizontal impact lines, ゴンッ
fg, al, _ = ink_panel('C')
c = focus['C'][0]
MF.speed_lines(fg, c, n=110, inner=0.12, seed=4, width=(1, 3))
fg.paste(ink_panel('C')[0], (0, 0), al.point(lambda v: 255 if v > 8 else 0))
MF.burst(fg, c, 18, 46, spikes=12, seed=5)
place('C', fg)
hi = evd.get('head_impact', {})
cap('C', 'tr', [f'{fmt_t(t_hi)}  HEAD → CANVAS', f'{hi.get("speed", float("nan")):.1f} m/s · peak {hi.get("force_bw", float("nan")):.1f} BW'], 16)
letter('C', (int((PW - M_ - cut1) * 0.42), h1 - 150), 'ゴンッ', 90, angle=-8)
if 'head_impact_2' in evd:
    h2_ = evd['head_impact_2']
    cap('C', 'bl', [f'bounce +{(ev["head_impact_2"] - t_hi) * 1000:.0f} ms', f'{h2_["force_bw"]:.2f} BW'], 14)

# D: follow-up
if fu:
    fg, al, _ = ink_panel('D')
    c = focus['D'][0]
    MF.speed_lines(fg, c, n=130, inner=0.12, seed=9)
    fg.paste(ink_panel('D')[0], (0, 0), al.point(lambda v: 255 if v > 8 else 0))
    MF.burst(fg, c, 22, 60, spikes=14, seed=8)
    place('D', fg)
    cap('D', 'bl', [f'{fmt_t(fu["t"])}  FOLLOW-UP', f'+{(fu["t"] - t_hi):.2f} s after the head lands'], 16)
    letter('D', (30, 14), 'ドゴッ', 120, angle=-10)
else:
    place('D', ink_panel('D')[0])
    tD = BEATS['D']['t']
    cap('D', 'bl', [f'{fmt_t(tD)}  ON THE CANVAS', f'+{tD - t_hi:.1f} s · posture building'], 16)

# E: her face after the follow-up (the house face camera, inked lighter)
fg, al, _ = ink_panel('E')
place('E', fg)
tE = BEATS['E']['t']
LE = float(Lt[idx(tE)]) if Lt is not None else None
cap('E', 'bl', [f'{fmt_t(tE)}', f'L = {LE:.2f}' if LE is not None else ''], 14)

# F: the climax -- tremor drawn as ghosted contour echoes, ガクガク
fg, al, _ = ink_panel('F')
sil = al.point(lambda v: 255 if v > 8 else 0)
edge = sil.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
ghost = Image.new('L', sil.size, 0)
for dx, dy in ((7, -3), (-7, 3), (13, -5)):
    ghost = ImageChops.lighter(ghost, ImageChops.offset(edge, dx, dy))
ghost = ImageChops.subtract(ghost, sil)
fg.paste((0, 0, 0), (0, 0), ghost)
place('F', fg)
tF = BEATS['F']['t']
cap('F', 'tl', [f'{fmt_t(tF)}  CLIMAX', f'+{tF - (t_fu or t_hi):.1f} s · {CAPS["F"]}'], 16)
x0, y0, x1, y1_ = bbox(PANELS['F'])
letter('F', (x1 - x0 - 430, 40), 'ガクガク', 92, angle=6)

# panel borders + title band
for key, poly in PANELS.items():
    dr.polygon(poly, outline=(0, 0, 0), width=5)
fT = MF.font(MF.FONT_CAP_I, 40)
dr.rectangle([M_, 30, PW - M_, 96], fill=(0, 0, 0))
dr.text((M_ + 18, 40), title.upper(), font=fT, fill=(255, 255, 255))
fS = MF.font(MF.FONT_CAP, 15)
sub = 'contact map · numbers from the sim'
tw_ = dr.textlength(sub, font=fS)
if M_ + 30 + dr.textlength(title.upper(), font=fT) + tw_ < PW - M_ - 16:
    dr.text((PW - M_ - 16 - tw_, 66), sub, font=fS, fill=(255, 255, 255))

# ---------------------------------------------------------------- ink contact timeline
GROUPS = [('HEAD', ['head']), ('NECK · TRUNK', ['neck', 'chest', 'spine', 'pelvis']),
          ('ARM L', ['upper_arm_L', 'forearm_L', 'hand_L']), ('ARM R', ['upper_arm_R', 'forearm_R', 'hand_R']),
          ('LEG L', ['thigh_L', 'shin_L', 'foot_L']), ('LEG R', ['thigh_R', 'shin_R', 'foot_R'])]
canvas = gn.index('canvas')
gidx = {}
for gi, (_, parts) in enumerate(GROUPS):
    for p_ in parts:
        if 'g_' + p_ in gn:
            gidx[gn.index('g_' + p_)] = gi
F_ = np.zeros((len(GROUPS), len(T)))
for step, g1, g2, dist, fN, slip in z['contacts']:
    g1, g2 = int(g1), int(g2)
    o = g2 if g1 == canvas else (g1 if g2 == canvas else None)
    if o in gidx:
        F_[gidx[o], int(step)] += max(fN, 0.0)
F_ /= BW
binw = max(1, int(round(0.02 / dt)))
nb = len(T) // binw
Fb = F_[:, :nb * binw].reshape(len(GROUPS), nb, binw).mean(2)

lx0, lx1 = M_ + 150, PW - M_ - 10
ty = TL_Y
dr.rectangle([M_, ty, PW - M_, ty + TL_H], outline=(0, 0, 0), width=5)
dr.text((M_ + 14, ty + 10), 'ON THE CANVAS', font=MF.font(MF.FONT_CAP_I, 22), fill=(0, 0, 0))
dr.text((M_ + 220, ty + 15), 'bar height ∝ log force (20 ms mean, body weights) · solid ≥ 0.5 BW, tone below',
        font=MF.font(MF.FONT_CAP, 13), fill=(0, 0, 0))
row_h, top = 30, ty + 88


def tx(t):
    return lx0 + (lx1 - lx0) * t / Tend


tone_tile = MF.screentone(Image.new('L', (lx1 - lx0, row_h), 150), cell=4)
fL = MF.font(MF.FONT_CAP, 15)
for gi, (lab, _) in enumerate(GROUPS):
    yc = top + gi * (row_h + 6)
    dr.text((M_ + 14, yc + 6), lab, font=fL, fill=(0, 0, 0))
    dr.line([lx0, yc + row_h, lx1, yc + row_h], fill=(0, 0, 0), width=1)
    for k in range(nb):
        v = Fb[gi, k]
        if v < 0.01:
            continue
        hpx = int(np.clip((math.log10(v) + 2) / 3.0, 0.12, 1.0) * row_h)   # 0.01 .. 10 BW
        xa, xb = int(tx(k * binw * dt)), int(math.ceil(tx((k + 1) * binw * dt)))
        box = (xa, yc + row_h - hpx, max(xb, xa + 1), yc + row_h)
        if v >= 0.5:
            dr.rectangle(box, fill=(0, 0, 0))
        else:
            page.paste(tone_tile.crop((xa - lx0, 0, max(xb, xa + 1) - lx0, hpx)).convert('RGB'), (xa, box[1]))
# L(t): thin line above the rows
ly = top + len(GROUPS) * (row_h + 6) + 6
if Lt is not None:
    dr.text((M_ + 14, ly - 2), 'L (conscious)', font=fL, fill=(0, 0, 0))
    pts_ = [(tx(T[i]), ly + 26 - 24 * float(Lt[i])) for i in range(0, len(T), 5)]
    dr.line(pts_, fill=(0, 0, 0), width=3)
# events: dashed verticals + small bursts + labels
EVL = {'ko_strike': ('KO', 'ゴッ'), 'head_impact': ('HEAD↓', 'ゴン'), 'head_impact_2': ('', ''),
       'followup_1': ('FOLLOW-UP', 'ドゴ'), 'down': ('DOWN', ''), 'L_half': ('L½', '')}
fE = MF.font(MF.FONT_CAP, 13)
lastx, lvl = -999, 0
for name, t in sorted(ev.items(), key=lambda kv: kv[1]):
    if name not in EVL or not EVL[name][0]:
        continue
    x = tx(t)
    for yy in range(top - 8, ly + 30, 9):
        dr.line([x, yy, x, yy + 4], fill=(0, 0, 0), width=2)
    lvl = 0 if x - lastx > 120 else (lvl + 1) % 3
    yl = ty + 38 + 16 * lvl
    dr.text((x + 4, yl), f'{EVL[name][0]} {t:.2f}', font=fE, fill=(0, 0, 0))
    lastx = x
    if EVL[name][1]:
        MF.burst(page, (x, top - 10), 5, 12, spikes=8, seed=3, width=2)
for s in range(0, int(Tend) + 1):
    dr.line([tx(s), ly + 32, tx(s), ly + 38], fill=(0, 0, 0), width=2)
    dr.text((tx(s) - 4, ly + 40), f'{s}', font=fE, fill=(0, 0, 0))
dr.text((lx1 - 14, ly + 40), 's', font=fE, fill=(0, 0, 0))

page.save(out)
json.dump({'beats': {k: {**v, 'focus_px': focus[k]} for k, v in BEATS.items()}}, open(os.path.splitext(out)[0] + '.json', 'w'),
          indent=1, default=float)
print('wrote', out)
