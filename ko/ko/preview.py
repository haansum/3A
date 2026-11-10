"""Cheapest possible look at a take: a stick-figure filmstrip and a tone timeline straight from
sim.npz. No Blender, no render; a couple of seconds. Use it to judge staging and timing
before anything is baked.

  python -m ko.preview takes/x.yaml            (builds through sim+qa if needed)
"""
import json
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .character.bonemap import CANON, PARENT

COL = {'L': '#c0392b', 'R': '#2471a3', '': '#222222'}


def draw(ax, P, a, b, origin, flip=1.0):
    for i, n in enumerate(CANON):
        par = PARENT[n]
        if par is None:
            continue
        side = 'L' if n.endswith('_L') else 'R' if n.endswith('_R') else ''
        p0, p1 = P[CANON.index(par)], P[i]
        ax.plot([flip * (p0[a] - origin[a]), flip * (p1[a] - origin[a])], [p0[b] - origin[b], p1[b] - origin[b]],
                color=COL[side], lw=2.2, solid_capstyle='round')
    h = P[CANON.index('head')]
    ax.add_patch(plt.Circle((flip * (h[a] - origin[a]), h[b] - origin[b] + (0.09 if b == 2 else 0)), 0.09,
                            color='#222222', fill=False, lw=1.5))


def make(sim_path, out_png, title=''):
    z = np.load(sim_path)
    t, dt = z['t'], float(z['dt'])
    ev = dict(json.loads(str(z['events'])))
    ev = {'KO': float(z['t_ko']), **{k: v for k, v in ev.items()}}
    ko, hi = ev['KO'], ev.get('head_impact', ev['KO'] + 1.0)
    keys = [0.0] + list(np.linspace(ko, hi, 6)) + [hi + 0.3]
    for k, v in ev.items():
        if v > hi:
            keys += [v, v + 0.15, v + 0.6]
    keys += [t[-1] * 0.85, t[-1]]
    keys = sorted(set(round(float(k), 3) for k in keys if 0 <= k <= t[-1]))[:14]
    n = len(keys)
    fig = plt.figure(figsize=(2.0 * n, 9.0), dpi=80)
    gs = fig.add_gridspec(3, n, height_ratios=[1.6, 1.4, 0.8], hspace=0.12, wspace=0.0)
    X = z['xpos']
    for c, tk in enumerate(keys):
        i = min(int(tk / dt), len(t) - 1)
        P = X[i]
        org = np.array([P[0][0], P[0][1], 0.0])
        ax = fig.add_subplot(gs[0, c])          # side view: her forward (-y) to the left
        draw(ax, P, 1, 2, org)
        ax.axhline(0, color='#888', lw=1)
        ax.set_xlim(-1.0, 1.0); ax.set_ylim(-0.05, 1.6); ax.set_aspect('equal'); ax.axis('off')
        lab = [k for k, v in ev.items() if abs(v - tk) < 2e-3]
        ax.set_title(f"{tk:.2f}s" + (f"\n{lab[0]}" if lab else ''), fontsize=9)
        ax2 = fig.add_subplot(gs[1, c])         # top view
        draw(ax2, P, 0, 1, org)
        ax2.set_xlim(-1.1, 1.1); ax2.set_ylim(-1.1, 1.1); ax2.set_aspect('equal'); ax2.axis('off')
    ax3 = fig.add_subplot(gs[2, :])
    for r, name in enumerate([str(x) for x in z['regions']]):
        ax3.plot(t, z['tone'][:, r], label=name, lw=1.4)
    for k, v in ev.items():
        ax3.axvline(v, color='k', lw=0.8, ls='--')
        ax3.text(v, 1.04, k, fontsize=8, rotation=0, ha='left')
    ax3.set_ylim(0, 1.15); ax3.set_xlim(0, t[-1]); ax3.set_xlabel('s'); ax3.set_ylabel('tone')
    ax3.legend(ncol=6, fontsize=8, loc='lower right')
    fig.suptitle(title + '   side view (top row: red = her left, blue = her right), top view (middle), tone (bottom)',
                 fontsize=10)
    fig.savefig(out_png, bbox_inches='tight')
    plt.close(fig)
    return out_png


def main(argv=None):
    from . import cli, manifest
    take = (argv or sys.argv[1:])[0]
    lock, dirs, _ = cli.build(take, to='qa', force=['noqa'])
    out = os.path.join(manifest.ROOT, 'drafts', f"{lock['take']}_preview_{lock['keys']['sim']}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    print(make(os.path.join(dirs['sim'], 'sim.npz'), out, lock['take']))


if __name__ == '__main__':
    main()
