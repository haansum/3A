"""Body-contact map for one simulated take: which body parts touch the canvas, when, and how hard.

    python3 tools/contact_map.py SIM.npz OUT.png [--title T] [--mass 50]

Top: canvas contact force per body part over time (mean over 20 ms bins, in body weights, log
colour), with the sim events marked. Bottom-left: top-down canvas footprint, final pose as a
grey stick figure, numbered markers where each part first lands (after the KO strike), coloured
by landing time. The marker is the part's body origin projected onto the canvas, not the exact
contact point (contact positions are not recorded). Bottom-right: peak force and time in contact
per part after the KO strike.
"""
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, LogNorm

a = sys.argv[1:]
src, out = a[0], a[1]
title = a[a.index('--title') + 1] if '--title' in a else src
mass = float(a[a.index('--mass') + 1]) if '--mass' in a else 50.0
BW = mass * 9.81

z = np.load(src, allow_pickle=True)
gn = [str(g) for g in z['geom_names']]
bn = [str(b) for b in z['body_names']]
t = z['t']
dt = float(z['dt'])
ev = dict(json.loads(str(z['events'])))
ev['ko'] = float(z['t_ko'])
c = z['contacts']
canvas = gn.index('canvas')

ROWS = ['head', 'neck', 'chest', 'spine', 'pelvis',
        'upper_arm_L', 'forearm_L', 'hand_L', 'upper_arm_R', 'forearm_R', 'hand_R',
        'thigh_L', 'shin_L', 'foot_L', 'thigh_R', 'shin_R', 'foot_R']
LABEL = {r: r.replace('_L', ' (L)').replace('_R', ' (R)').replace('_', ' ') for r in ROWS}
row_of = {gn.index('g_' + r): i for i, r in enumerate(ROWS) if 'g_' + r in gn}

nstep = len(t)
F = np.zeros((len(ROWS), nstep))
for step, g1, g2, dist, f, slip in c:
    g1, g2 = int(g1), int(g2)
    other = g2 if g1 == canvas else (g1 if g2 == canvas else None)
    if other in row_of:
        F[row_of[other], int(step)] += max(f, 0.0)
F /= BW

binw = max(1, int(round(0.02 / dt)))
nb = nstep // binw
Fraw_pk = F.max(1)
Fb = F[:, :nb * binw].reshape(len(ROWS), nb, binw).mean(2)   # 20 ms mean: impulse at body scale
tb = (np.arange(nb) + 0.5) * binw * dt

# palette: sequential blue (dataviz reference ramp), ink tokens
RAMP = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#184f95', '#0d366b']
cmap = LinearSegmentedColormap.from_list('seq', RAMP)
cmap.set_bad('#f6f6f4')
INK, INK2, MUTED, GRID, SURF = '#1f1f1d', '#4a4a46', '#8a8a84', '#e4e3df', '#ffffff'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 9, 'text.color': INK,
                     'axes.labelcolor': INK2, 'xtick.color': INK2, 'ytick.color': INK2,
                     'axes.edgecolor': GRID})

fig = plt.figure(figsize=(12, 8.2), facecolor=SURF)
gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1], width_ratios=[1.25, 1], hspace=0.32, wspace=0.62)
ax = fig.add_subplot(gs[0, :])
M = np.ma.masked_less(Fb, 0.005)
im = ax.imshow(M, aspect='auto', cmap=cmap, norm=LogNorm(0.01, 3.0), interpolation='nearest',
               extent=(0, nb * binw * dt, len(ROWS) - 0.5, -0.5))
ax.set_yticks(range(len(ROWS)), [LABEL[r] for r in ROWS])
ax.set_xlabel('time (s)')
for sep in (4.5, 10.5):
    ax.axhline(sep, color=GRID, lw=1)
EVL = [('ko_strike', 'KO strike'), ('ko', 'KO'), ('down', 'first non-foot contact'), ('head_impact', 'head impact')]
EVL += [(k, k.replace('head_impact_', 'head contact #').replace('followup_', 'follow-up #'))
        for k in sorted(ev, key=ev.get) if k.startswith(('head_impact_', 'followup_'))]
evs = [(ev[k], n) for k, n in EVL if k in ev]
merged = []
for tt, n in evs:
    if merged and tt - merged[-1][0] < 0.12:
        merged[-1] = (merged[-1][0], merged[-1][1] + ' / ' + n, merged[-1][2] + [tt])
    else:
        merged.append((tt, n, [tt]))
for j, (tt, n, ts) in enumerate(merged):
    for x in ts:
        ax.axvline(x, color=INK2, lw=0.8, ls=(0, (3, 2)))
    ax.text(tt, -0.7 - 1.1 * (j % 2), f"{n} · {'/'.join(f'{x:.2f}' for x in ts)} s",
            ha='left', va='bottom', fontsize=7.5, color=INK2)
cb = fig.colorbar(im, ax=ax, pad=0.01, fraction=0.025)
cb.set_label('canvas force (× body weight)')
cb.outline.set_edgecolor(GRID)
ax.set_title(title, loc='left', fontsize=12, fontweight='bold', pad=40)

# ---- footprint
ax2 = fig.add_subplot(gs[1, 0])
X = z['xpos']
bi = {b: i for i, b in enumerate(bn)}
CH = [['pelvis', 'spine', 'chest', 'neck', 'head'],
      ['chest', 'upper_arm_L', 'forearm_L', 'hand_L'], ['chest', 'upper_arm_R', 'forearm_R', 'hand_R'],
      ['pelvis', 'thigh_L', 'shin_L', 'foot_L'], ['pelvis', 'thigh_R', 'shin_R', 'foot_R']]
fin = X[-1]
for ch in CH:
    p = np.array([fin[bi[b]] for b in ch if b in bi])
    ax2.plot(p[:, 0], p[:, 1], color='#c9c8c3', lw=5, solid_capstyle='round', zorder=1)
t0 = ev.get('ko_strike', ev['ko'])
first = []
for i, r in enumerate(ROWS):
    inc = F[i] > 0.01
    on = np.where(inc & ~np.r_[False, inc[:-1]] & (t > t0))[0]
    if len(on) and r in bi:
        first.append((t[on[0]], r, X[on[0], bi[r]]))
first.sort()
tmin, tmax = (first[0][0], first[-1][0]) if first else (0, 1)
for k, (tt, r, p) in enumerate(first, 1):
    u = 0 if tmax == tmin else (tt - tmin) / (tmax - tmin)
    col = cmap(0.35 + 0.65 * u)
    ax2.scatter(p[0], p[1], s=150, color=col, edgecolor=SURF, linewidth=2, zorder=3)
    ax2.text(p[0], p[1], str(k), ha='center', va='center', fontsize=7, color='white', zorder=4,
             fontweight='bold')
ax2.set_aspect('equal')
ax2.set_xlabel('x (m)  · +x = her left')
ax2.set_ylabel('y (m)')
ax2.grid(color=GRID, lw=0.6)
ax2.set_title('Landing order on the canvas (top-down, final pose in grey)', loc='left', fontsize=10)
lines = [f'{k:>2}  {tt:5.2f} s  {LABEL[r]}' for k, (tt, r, p) in enumerate(first, 1)]
ax2.text(1.02, 1.0, '\n'.join(lines), transform=ax2.transAxes, va='top', ha='left', fontsize=7.5,
         family='DejaVu Sans Mono', color=INK2)

# ---- peak force / time in contact
ax3 = fig.add_subplot(gs[1, 1])
after = t >= t0
Fm = np.array([np.convolve(r, np.ones(binw) / binw, 'same') for r in F])
pk = Fm[:, after].max(1)
tc = (F[:, after] > 0.01).sum(1) * dt
order = [i for i in range(len(ROWS)) if pk[i] > 0.01]
y = np.arange(len(order))
ax3.barh(y, pk[order], color='#3987e5', height=0.6)
for yy, i in zip(y, order):
    ax3.text(pk[i] * 1.02 + 0.02, yy, f'{pk[i]:.2f} BW · {tc[i]:.2f} s', va='center', fontsize=7.5, color=INK2)
ax3.set_yticks(y, [LABEL[ROWS[i]] for i in order])
ax3.invert_yaxis()
ax3.set_xlim(0, max(pk.max() * 1.55, 0.1))
ax3.set_xlabel('peak 20 ms-mean canvas force after the KO strike (× body weight)')
ax3.grid(axis='x', color=GRID, lw=0.6)
ax3.set_axisbelow(True)
for s_ in ('top', 'right'):
    ax3.spines[s_].set_visible(False)
ax3.set_title('Peak force · time in contact', loc='left', fontsize=10)
fig.text(0.01, 0.005, f'MuJoCo canvas contacts, {dt*1000:.0f} ms steps, {binw*dt*1000:.0f} ms bins; '
         f'body weight {mass:.0f} kg × g. Footprint markers are body origins, not contact points. '
         f'Raw single-step solver peaks (rigid-contact spikes, not physiological) reach {Fraw_pk.max():.0f} BW.',
         fontsize=7, color=MUTED)
fig.savefig(out, dpi=150, facecolor=SURF, bbox_inches='tight')
print('wrote', out)
