"""Grow a take 2 s at a time (owner 2026-11-18): five sim/camera options for the next window,
the owner picks one, the clip grows, repeat.

    python3 tools/grow.py STATE.yaml next          # simulate + render 5 options for the next window
    python3 tools/grow.py STATE.yaml pick N        # keep option N, extend the clip, show it

STATE (takes/branches/<name>.yaml): the base take, window length, render settings, the current
camera, the accumulated sim overrides (`sets`) and the picks so far. The tool writes it back.

Every option re-simulates from t = 0 with the picks so far plus its own change; changes are
time-stamped at the window start (fade rate, squeeze, posture tone, movement, waking speed,
release timing, hand-fight choreography after the next reference key), so the past stays
bit-identical; the tool verifies that against the approved clip and drops any option that
would change it. Each option renders only its window. Output under build/grow/<name>/win<k>/:
option clips (labelled), a side-by-side grid, and the clip so far (picked windows joined,
unlabelled, cuts where the camera changes).
"""
import copy
import glob
import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np  # noqa: E402
import yaml  # noqa: E402

from ko import cli, manifest  # noqa: E402

CAMERAS = [
    ('front-left 3/4', {'live_az': -60, 'live_dist': 2.6, 'live_z': 1.3}),
    ('front, low', {'live_az': -105, 'live_dist': 2.3, 'live_z': 0.8}),
    ('closer 3/4', {'live_az': -55, 'live_dist': 1.7, 'live_z': 1.45}),
    ('her left side', {'live_az': -5, 'live_dist': 2.5, 'live_z': 1.2}),
    ('high, front-right', {'live_az': -150, 'live_dist': 2.6, 'live_z': 2.1}),
    ('her right side, low', {'live_az': -175, 'live_dist': 2.2, 'live_z': 0.7}),
]


def setp(d, path, val):
    toks = re.findall(r'[^.\[\]]+|\[\d+\]', path)
    cur = d
    for k, tok in enumerate(toks):
        key = int(tok[1:-1]) if tok.startswith('[') else tok
        if k == len(toks) - 1:
            cur[key] = val
        else:
            if not tok.startswith('[') and (key not in cur or cur[key] is None):
                cur[key] = {}
            cur = cur[key]


def getp(d, path, default=None):
    cur = d
    for tok in re.findall(r'[^.\[\]]+|\[\d+\]', path):
        key = int(tok[1:-1]) if tok.startswith('[') else tok
        try:
            cur = cur[key]
        except (KeyError, IndexError, TypeError):
            return default
    return cur


def with_change(sets, path, entry):
    """append a time-stamped change to a list-valued knob"""
    s2 = copy.deepcopy(sets)
    s2[path] = list(s2.get(path) or []) + [entry]
    return s2


a = sys.argv[1:]
sp, cmd = a[0], a[1]
st = yaml.safe_load(open(sp))
name = os.path.splitext(os.path.basename(sp))[0]
root = os.path.join(manifest.ROOT, 'build', 'grow', name)
picks = st.get('picks') or []
k = len(picks)
W = float(st.get('window_s', 2.0))


def clip_end():
    """where the approved clip ends: the last pick's window end (windows may differ in length;
    picks from before this was recorded were 2 s each)"""
    ps = st.get('picks') or []
    return float(ps[-1].get('t1', 2.0 * len(ps))) if ps else 0.0


def save_state():
    yaml.safe_dump(st, open(sp, 'w'), sort_keys=False, default_flow_style=None, width=140)


def assemble():
    """join the picked windows' clean clips into the clip so far"""
    parts = [p['clip'] for p in st.get('picks') or [] if p.get('clip') and os.path.exists(p['clip'])]
    if not parts:
        return None
    lst = os.path.join(root, 'so_far.txt')
    open(lst, 'w').write(''.join(f"file '{p}'\n" for p in parts))
    out = os.path.join(root, f'{name}_so_far_{clip_end():.0f}s.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', out], check=True)
    return out



def make_grid(k, ms):
    """grid of the options for window k: each tile plays the whole clip so far, then that
    option's new window (owner 2026-11-19: "ensure that the videos are added on to each
    other"), all tiles in sync; the so-far part is unlabelled, the new window labelled"""
    outd = os.path.join(root, f'win{k}')
    so_far = assemble()
    cfps = int((st.get('render') or {}).get('fps', 12))
    full = []
    for i, m in enumerate(ms):
        if so_far:
            fm = os.path.join(outd, f'opt{i}', f'win{k}_opt{i}_with_history.mp4')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', so_far, '-i', m, '-filter_complex',
                            '[0:v][1:v]concat=n=2:v=1:a=0[o]', '-map', '[o]', '-r', str(cfps),
                            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', fm], check=True)
            full.append(fm)
        else:
            full.append(m)
    dur = clip_end() + W
    tiles = full[:]
    inputs, filt = [], []
    for i, m in enumerate(tiles):
        inputs += ['-i', m]
        filt.append(f'[{i}:v]tpad=stop_mode=clone:stop_duration=5[v{i}]')
    while len(tiles) < 6:
        inputs += ['-f', 'lavfi', '-t', str(dur), '-i', f'color=c=black:s=480x270:r={cfps}']
        filt.append(f'[{len(tiles)}:v]null[v{len(tiles)}]')
        tiles.append(None)
    lay = '0_0|w0_0|w0+w0_0|0_h0|w0_h0|w0+w0_h0'
    grid = os.path.join(outd, f'{name}_window{k}_options_from_0s.mp4')
    fc = ';'.join(filt) + ';' + ''.join(f'[v{i}]' for i in range(6)) + f'xstack=inputs=6:layout={lay}[out]'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error'] + inputs + ['-filter_complex', fc, '-map', '[out]', '-t', str(dur),
                    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', grid], check=True)
    print('[grow] grid', grid)
    print('[grow] so far', so_far)
    return grid


if cmd == 'regrid':                # rebuild the current window's grid from the clips on disk
    kk = len(st.get('picks') or [])
    oj = json.load(open(os.path.join(root, f'win{kk}', 'options.json')))
    make_grid(kk, [o['clip'] for o in oj])
    sys.exit(0)

if cmd == 'pick':
    n = int(a[2])
    allo = json.load(open(os.path.join(root, f'win{k}', 'options.json')))
    opt = dict(allo[n])
    if '--camera-from' in a:
        # owner 2026-11-22: "3 but with high front right cam": option n's sim, option m's camera.
        # Allowed only when the two sims match through the window, so m's render shows n exactly
        m = int(a[a.index('--camera-from') + 1])
        sa = np.load(os.path.join(allo[n]['dir'], 'sim', 'sim.npz'))
        sb = np.load(os.path.join(allo[m]['dir'], 'sim', 'sim.npz'))
        i1 = int(np.searchsorted(sa['t'], float(opt.get('t1', 0))))
        dev = float(np.degrees(np.abs(sa['qpos'][:i1, 7:] - sb['qpos'][:i1, 7:]).max()))
        if dev > 1e-6:
            sys.exit(f'[grow] option {n} and {m} differ by {dev:.3f} deg inside the window: render option {n} with that camera instead')
        opt.update(camera=allo[m]['camera'], camera_label=allo[m]['camera_label'], clean_clip=allo[m]['clean_clip'])
        opt['label'] = opt['label'] + f' (camera from option {m})'
    st['sets'] = opt['sets']
    st['camera'] = opt['camera']
    st.setdefault('picks', []).append({'window': k, 'option': n, 't0': opt.get('t0'), 't1': opt.get('t1'), 'label': opt['label'],
                                       'camera_label': opt['camera_label'], 'clip': opt['clean_clip']})
    save_state()
    print('[grow] clip so far:', assemble())
    sys.exit(0)

# ---- next: five options for window k ---------------------------------------------------------
t0 = clip_end()
t1 = t0 + W
outd = os.path.join(root, f'win{k}')
os.makedirs(outd, exist_ok=True)
base_lock, dirs, _ = cli.build(st['take'], None, 'body', ['noqa'])
from ko.sim import run as simrun  # noqa: E402


def make_lock(sets, camera, dur):
    L = json.loads(json.dumps(base_lock, default=str))
    for p_, v_ in (sets or {}).items():
        setp(L, p_, v_)
    L['sim']['duration'] = dur
    L['render'] = dict(L['render'], **(st.get('render') or {}), **camera)
    return L


sets0 = st.get('sets') or {}
cam0 = st.get('camera') or CAMERAS[0][1]
cam0_label = next((lb for lb, c in CAMERAS if c == cam0), 'current camera')
parent = simrun.run(make_lock(sets0, cam0, t1 + 0.25), dirs['body'], None, record=False)
ev = json.loads(str(parent['events']))
T = t1
phase = ('fight' if 'out' not in ev or ev['out'] > t0 else
         'out' if 'release' not in ev or ev['release'] > t0 else
         'down' if 'waking' not in ev or ev['waking'] > t0 else 'waking')
L0 = make_lock(sets0, cam0, t1)

# ---- candidate sim changes for this phase, all starting at t0 -------------------------------
cands = []
if phase == 'fight':
    # scale from the value in effect at t0 (earlier picks' changes included), not the original
    from ko.sim.intensity import timed
    rate = timed(sets0.get('controller.consciousness.rate_changes'), t0, getp(L0, 'controller.consciousness.rate', 0.16))
    sq = timed(sets0.get('grapple.squeeze_changes'), t0, getp(L0, 'grapple.squeeze_m', 0.02))
    cands += [('he tightens the squeeze', with_change(sets0, 'grapple.squeeze_changes', [t0, sq + 0.014, 0.8])),
              ('he loosens a little', with_change(sets0, 'grapple.squeeze_changes', [t0, max(0.0, sq - 0.012), 0.8])),
              ('she fades faster', with_change(sets0, 'controller.consciousness.rate_changes', [t0, rate * 1.7, 0.4])),
              ('she holds on longer', with_change(sets0, 'controller.consciousness.rate_changes', [t0, rate * 0.55, 0.4]))]
    keys = getp(L0, 'motion.reference.keys', [])
    later = [kk for kk in keys if kk['t'] > t0]
    if later:
        anchor = later[0]['t']                       # the next key stays: the past is untouched
        for lab, seq in (('she reaches back for his head', ['stand_reach_back', 'stand_hand_fight_a']),
                         ('two-on-one pull on his forearm', ['stand_pull_down', 'stand_pull_down']),
                         ('she bends forward to drag him', ['stand_lean_forward', 'stand_pull_down']),
                         ('frantic hand fight', ['stand_hand_fight_b', 'stand_hand_fight_a', 'stand_hand_fight_b'])):
            new = [kk for kk in keys if kk['t'] <= anchor]
            step = 0.35 if lab.startswith('frantic') else 0.6
            tt = anchor
            for pz in seq:
                tt += step
                new.append({'t': round(tt, 3), 'pose': pz})
            new += [kk for kk in keys if kk['t'] > tt + 0.3]
            s2 = copy.deepcopy(sets0)
            s2['motion.reference.keys'] = new
            cands.append((lab, s2))
elif phase == 'out':
    rel = getp(L0, 'grapple.release_after', 10.0)
    cands += [('posture builds harder', with_change(with_change(sets0, 'controller.ko.tone_changes.arms', [t0, 1.4, 1.0]),
                                                    'controller.ko.tone_changes.legs', [t0, 1.4, 1.0])),
              ('posture eases off', with_change(with_change(sets0, 'controller.ko.tone_changes.arms', [t0, 0.55, 1.0]),
                                                'controller.ko.tone_changes.legs', [t0, 0.55, 1.0])),
              ('more involuntary movement', with_change(sets0, 'grapple.jerk_changes', [t0, 1.9, 0.3])),
              ('she goes still', with_change(sets0, 'grapple.jerk_changes', [t0, 0.25, 0.3])),
              ('head lolls harder', with_change(sets0, 'controller.ko.tone_changes.neck', [t0, 0.3, 0.6]))]
    # release timing only when the change lands inside this window (otherwise the option looks
    # identical to 'as is' here; owner feedback 2026-11-22)
    for dr, lab in ((-2.0, 'he lets go 2 s sooner'), (2.0, 'he holds her 2 s longer')):
        t_new, t_old = ev['out'] + rel + dr, ev['out'] + rel
        if t0 + 0.3 < min(t_new, t_old) and min(t_new, t_old) < t1:
            s2 = copy.deepcopy(sets0)
            s2['grapple.release_after'] = rel + dr
            cands.append((lab, s2))
    if t0 + 0.3 < ev['out'] + rel - 3.0 < t1 - 0.5:
        s2 = copy.deepcopy(sets0)
        s2['grapple.release_after'] = max(0.5, (t0 + 0.6) - ev['out'])
        cands.append(('he lets go now', s2))
else:
    from ko.sim.intensity import timed
    dec = timed(sets0.get('controller.consciousness.wake.decay_changes'), t0, getp(L0, 'controller.consciousness.wake.decay', 0.15))
    cands += [('limper, heavier', with_change(sets0, 'controller.ko.tone_changes.all', [t0, 0.5, 0.6])),
              ('bigger kicks / jitters', with_change(sets0, 'grapple.jerk_changes', [t0, 2.0, 0.3])),
              ('calmer', with_change(sets0, 'grapple.jerk_changes', [t0, 0.3, 0.3])),
              ('comes round faster', with_change(sets0, 'controller.consciousness.wake.decay_changes', [t0, dec * 2.0, 0.3])),
              ('comes round slower', with_change(sets0, 'controller.consciousness.wake.decay_changes', [t0, dec * 0.4, 0.3]))]

# rotate through the candidates so successive windows offer different things
rot = k % max(1, len(cands))
cands = cands[rot:] + cands[:rot]
cams = [c for c in CAMERAS if c[1] != cam0]
cams = cams[k % len(cams):] + cams[:k % len(cams)]
plan = [('as is', sets0, cam0_label, cam0)]
for lab, s2 in cands:
    if len(plan) >= 3:
        break
    plan.append((lab, s2, cam0_label, cam0))
if len(cands) > 2:
    plan.append((cands[2][0], cands[2][1], cams[0][0], cams[0][1]))
plan.append(('as is', sets0, cams[1][0], cams[1][1]))

# ---- simulate, check the past, keep five --------------------------------------------------
i0 = int(np.searchsorted(parent['t'], t0))
opts = []
for oi, (lab, sets, clab, cam) in enumerate(plan):
    L = make_lock(sets, cam, t1 + 0.25)
    out = simrun.run(L, dirs['body'], None, record=False)
    dev = float(np.degrees(np.abs(out['qpos'][:i0, 7:] - parent['qpos'][:i0, 7:]).max())) if i0 else 0.0
    if dev > 1e-6:
        print(f'[grow] dropped "{lab}": it changes the approved past by {dev:.3f} deg')
        continue
    od = os.path.join(outd, f'opt{len(opts)}')
    sd = os.path.join(od, 'sim')
    os.makedirs(sd, exist_ok=True)
    np.savez_compressed(os.path.join(sd, 'sim.npz'), **out)
    L['keys'] = dict(L['keys'], sim=f'grow_{name}_w{k}_o{len(opts)}')
    opts.append({'label': lab, 'camera_label': clab, 'camera': cam, 'sets': sets, 'dir': od, 'lock': L, 't0': t0, 't1': t1,
                 'events': {e: round(v, 2) for e, v in json.loads(str(out['events'])).items()}})
    print(f'[grow] window {k} ({t0:.1f}-{t1:.1f} s, {phase}) option {len(opts) - 1}: {lab} / {clab}', flush=True)

# ---- render each option's window ---------------------------------------------------------
from ko.bake import bake as BK  # noqa: E402
from ko.render import render as RD  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

try:
    FONT = ImageFont.truetype('DejaVuSans-Bold.ttf', 15)
except Exception:
    FONT = ImageFont.load_default()
cfps = int((st.get('render') or {}).get('fps', 12))
for oi, o in enumerate(opts):
    od, L = o['dir'], o['lock']
    bd, rd = os.path.join(od, 'bake'), os.path.join(od, 'render')
    os.makedirs(bd, exist_ok=True)
    os.makedirs(rd, exist_ok=True)
    BK.run(L, dirs['character'], os.path.join(od, 'sim'), bd)
    # frame j of the window sits at (j + 1e-3)/fps so this and the render stage agree on the frame
    times = [t0 + (j + 1e-3) / cfps for j in range(int(round((t1 - t0) * cfps)))]
    L['render'] = dict(L['render'], still_times=times, still_shots=['live'])
    RD.run(L, bd, os.path.join(od, 'sim'), rd, stills=True)
    fps = L['render']['fps']
    for tag in ('clean', 'lab'):
        fdir = os.path.join(od, 'f_' + tag)
        os.makedirs(fdir, exist_ok=True)
        jj = 0
        for tt in times:
            src = os.path.join(rd, f'still_live_{int(min(1e9, max(1, tt * fps + 1))):04d}.png')
            if not os.path.exists(src):
                continue
            im = Image.open(src).convert('RGB')
            if tag == 'lab':
                dr = ImageDraw.Draw(im)
                txt = f"{oi}: {o['label']}  |  {o['camera_label']}   {tt:4.1f} s"
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        dr.text((8 + dx, 6 + dy), txt, fill=(0, 0, 0), font=FONT)
                dr.text((8, 6), txt, fill=(255, 235, 120), font=FONT)
            im.save(os.path.join(fdir, f'{jj:04d}.png'))
            jj += 1
        mp4 = os.path.join(od, f'win{k}_opt{oi}_{tag}.mp4')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(cfps), '-i', os.path.join(fdir, '%04d.png'),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-r', str(cfps), mp4], check=True)
        o['clean_clip' if tag == 'clean' else 'clip'] = mp4
        shutil.rmtree(fdir, ignore_errors=True)
    for p_ in (os.path.join(bd, 'take.blend'), os.path.join(rd, 'scene.blend')):
        if os.path.exists(p_):
            os.remove(p_)
    for f_ in glob.glob(os.path.join(rd, '*.png')):
        os.remove(f_)
    print(f'[grow] rendered option {oi}', flush=True)

json.dump([{kk: v for kk, v in o.items() if kk != 'lock'} for o in opts], open(os.path.join(outd, 'options.json'), 'w'), indent=1, default=str)
make_grid(k, [o['clip'] for o in opts])

