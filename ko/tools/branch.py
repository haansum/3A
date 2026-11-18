"""Branching, segment-by-segment authoring of a take (owner 2026-11-18): "give me five options
for the first little bit, then the one I pick is the input to the next simulation".

    python3 tools/branch.py SPEC.yaml run SEG [--options 0,2] [--no-render]
    python3 tools/branch.py SPEC.yaml pick SEG OPTION

A spec (takes/branches/<name>.yaml) names a base take, splits it into segments that end at a
sim event plus an offset, and lists options per segment as overrides on the take's lock
(dotted paths, list indices allowed: `controller.ko.phases[0].pose: x`). `chosen` holds the
option picked for each earlier segment.

How a branch continues from the pick: the sim is deterministic, so every option re-runs from
t = 0 with the earlier picks applied plus its own overrides. Overrides that only act after the
segment starts (phases keyed on later events, release settings, wake settings...) leave the past
bit-identical; the tool checks that numerically against the parent branch (max joint deviation
before the segment start) and flags any option that changes the past.

Output, under build/branches/<spec>/seg<k>/: per option the sim, a clip of just this segment
(12 fps by default, from the segment start minus a lead-in to its end) per shot, and one grid
video per shot with every option side by side, frame-synced from each option's own segment start,
labelled. Clips render through the render stage (same look as the previews).
"""
import copy
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np  # noqa: E402
import yaml  # noqa: E402

from ko import cli, manifest  # noqa: E402


def setp(d, path, val):
    """set a dotted path with [i] list indices inside nested dicts/lists"""
    toks = re.findall(r'[^.\[\]]+|\[\d+\]', path)
    cur = d
    for k, tok in enumerate(toks):
        last = k == len(toks) - 1
        key = int(tok[1:-1]) if tok.startswith('[') else tok
        if last:
            cur[key] = val
        else:
            if not tok.startswith('[') and (key not in cur or cur[key] is None):
                cur[key] = {}
            cur = cur[key]


def apply(lock, sets):
    for p, v in (sets or {}).items():
        setp(lock, p, v)
    return lock


def seg_end(seg, ev, T):
    u = seg.get('until') or {}
    if 'event' in u:
        return min(T, ev.get(u['event'], T) + float(u.get('dt', 0.0))) if u['event'] in ev else T
    return min(T, float(u.get('t', T)))


a = sys.argv[1:]
spec_p, cmd = a[0], a[1]
spec = yaml.safe_load(open(spec_p))
name = os.path.splitext(os.path.basename(spec_p))[0]
if cmd == 'pick':
    k, o = int(a[2]), int(a[3])
    ch = list(spec.get('chosen') or [])
    ch = (ch + [0] * (k + 1))[:k + 1]
    ch[k] = o
    txt = open(spec_p).read()
    txt = re.sub(r'^chosen:.*$', f'chosen: {ch}', txt, flags=re.M) if re.search(r'^chosen:', txt, re.M) else txt + f'\nchosen: {ch}\n'
    open(spec_p, 'w').write(txt)
    print('chosen', ch)
    sys.exit(0)

k = int(a[2])
segs = spec['segments']
seg = segs[k]
chosen = list(spec.get('chosen') or [])
chosen = (chosen + [0] * k)[:k]
only = [int(x) for x in a[a.index('--options') + 1].split(',')] if '--options' in a else range(len(seg['options']))
outd = os.path.join(manifest.ROOT, 'build', 'branches', name, f'seg{k}')
os.makedirs(outd, exist_ok=True)

base_lock, dirs, _ = cli.build(spec['take'], None, 'body', ['noqa'])
prefix = {}
for j, oi in enumerate(chosen):
    prefix.update(segs[j]['options'][oi].get('set') or {})

from ko.sim import run as simrun  # noqa: E402


def sim_for(sets):
    lock = apply(copy.deepcopy(json.loads(json.dumps(base_lock, default=str))), sets)
    return lock, simrun.run(lock, dirs['body'], None, record=False)


# the parent branch: the earlier picks, this segment at its first option's defaults (no overrides)
parent_lock, parent = sim_for(prefix)
pev = json.loads(str(parent['events']))
T = float(parent['t'][-1])
t_start = 0.0 if k == 0 else seg_end(segs[k - 1], pev, T)
report = {'spec': name, 'segment': k, 'name': seg.get('name'), 'chosen_before': chosen,
          'segment_start_s': round(t_start, 3), 'options': []}
runs = []
for oi in only:
    opt = seg['options'][oi]
    sets = dict(prefix, **(opt.get('set') or {}))
    lock, out = sim_for(sets)
    ev = json.loads(str(out['events']))
    t_end = seg_end(seg, ev, float(out['t'][-1]))
    i0 = int(np.searchsorted(out['t'], t_start))
    dev = float(np.degrees(np.abs(out['qpos'][:i0, 7:] - parent['qpos'][:i0, 7:]).max())) if i0 > 0 else 0.0
    sd = os.path.join(outd, f'opt{oi}', 'sim')
    os.makedirs(sd, exist_ok=True)
    np.savez_compressed(os.path.join(sd, 'sim.npz'), **out)
    lock['keys'] = dict(lock['keys'], sim=f'branch_{name}_s{k}_o{oi}')
    json.dump(lock, open(os.path.join(sd, 'take.lock.json'), 'w'), default=str)
    row = {'option': oi, 'label': opt.get('label', f'option {oi}'), 'set': opt.get('set') or {},
           'segment_end_s': round(t_end, 3), 'past_changed_max_deg': round(dev, 4),
           'past_identical': dev < 1e-6, 'events': {e: round(v, 2) for e, v in ev.items()}}
    report['options'].append(row)
    runs.append((oi, opt, lock, sd, t_end))
    print(f"[branch] seg {k} option {oi} '{row['label']}': ends {t_end:.2f} s, past identical: {row['past_identical']}"
          f" (max {dev:.4f} deg)", flush=True)
json.dump(report, open(os.path.join(outd, 'report.json'), 'w'), indent=1)

if '--no-render' in a:
    sys.exit(0)

# render each option's segment through the render stage (stills path at chosen times)
R = dict(spec.get('render') or {})
cfps = int(R.pop('clip_fps', 12))
lead = float(R.pop('lead_s', 0.5))
shots = seg.get('shots') or R.pop('shots', ['live'])
R.pop('shots', None)
from ko.bake import bake as BK  # noqa: E402
from ko.render import render as RD  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

try:
    FONT = ImageFont.truetype('DejaVuSans-Bold.ttf', 15)
except Exception:
    FONT = ImageFont.load_default()
clips = {}
for oi, opt, lock, sd, t_end in runs:
    od = os.path.join(outd, f'opt{oi}')
    bd = os.path.join(od, 'bake')
    os.makedirs(bd, exist_ok=True)
    lock_r = dict(lock, render=dict(lock['render'], **R))
    BK.run(lock_r, dirs['character'], sd, bd)
    ta = max(0.0, t_start - (lead if k > 0 else 0.0))
    times = list(np.arange(ta, t_end + 1e-6, 1.0 / cfps))
    lock_r['render'] = dict(lock_r['render'], still_times=times, still_shots=shots)
    rd = os.path.join(od, 'render')
    os.makedirs(rd, exist_ok=True)
    RD.run(lock_r, bd, sd, rd, stills=True)
    fps = lock_r['render']['fps']
    for sh in shots:
        fdir = os.path.join(od, f'clip_{sh}')
        os.makedirs(fdir, exist_ok=True)
        for j, tt in enumerate(times):
            f = max(1, int(tt * fps + 1))
            src = os.path.join(rd, f'still_{sh}_{f:04d}.png')
            if not os.path.exists(src):
                continue
            im = Image.open(src).convert('RGB')
            dr = ImageDraw.Draw(im)
            lab = f"{oi}: {opt.get('label', '')}   {tt:5.2f} s"
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    dr.text((8 + dx, 6 + dy), lab, fill=(0, 0, 0), font=FONT)
            dr.text((8, 6), lab, fill=(255, 235, 120), font=FONT)
            im.save(os.path.join(fdir, f'{j:04d}.png'))
        mp4 = os.path.join(od, f'seg{k}_opt{oi}_{sh}.mp4')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(cfps), '-i', os.path.join(fdir, '%04d.png'),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', mp4], check=True)
        clips.setdefault(sh, []).append(mp4)
    # intermediates (scene files, frames) are deleted once the clips exist: ~1 GB per option
    import shutil
    for p_ in (os.path.join(bd, 'take.blend'), os.path.join(rd, 'scene.blend')):
        if os.path.exists(p_):
            os.remove(p_)
    for f_ in os.listdir(rd):
        if f_.endswith('.png'):
            os.remove(os.path.join(rd, f_))
    for sh in shots:
        shutil.rmtree(os.path.join(od, f'clip_{sh}'), ignore_errors=True)

# grid per shot: every option clip on disk for this segment (so options rendered in separate
# runs, e.g. with --options, still land in one grid), side by side, padded to the longest
import glob as _glob
for sh in set(clips) | set(shots):
    ms = sorted(_glob.glob(os.path.join(outd, 'opt*', f'seg{k}_opt*_{sh}.mp4')),
                key=lambda p_: int(re.search(r'opt(\d+)_', os.path.basename(p_)).group(1)))
    if not ms:
        continue
    n = len(ms)
    cols = n if n <= 3 else (n + 1) // 2
    rows = 1 if n <= 3 else 2
    inputs, filt = [], []
    for i, m in enumerate(ms):
        inputs += ['-i', m]
        filt.append(f'[{i}:v]tpad=stop_mode=clone:stop_duration=30[v{i}]')
    if n < cols * rows:                                  # blank tile for an odd count
        inputs += ['-f', 'lavfi', '-i', 'color=c=black:s=480x270:r=12']
        filt.append(f'[{n}:v]null[v{n}]')
    lay = '|'.join(f"{'+'.join(['w0'] * (i % cols)) or '0'}_{'+'.join(['h0'] * (i // cols)) or '0'}" for i in range(cols * rows))
    grid = os.path.join(outd, f'seg{k}_{sh}_grid.mp4')
    longest = max(float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', m],
                                       capture_output=True, text=True).stdout or 0) for m in ms)
    fc = ';'.join(filt) + ';' + ''.join(f'[v{i}]' for i in range(cols * rows)) + f'xstack=inputs={cols * rows}:layout={lay}[out]'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error'] + inputs + ['-filter_complex', fc, '-map', '[out]',
                    '-t', f'{longest:.2f}', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '21', grid], check=True)
    print('[branch] grid', grid)
print('[branch] report', os.path.join(outd, 'report.json'))
