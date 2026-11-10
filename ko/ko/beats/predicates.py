"""Generic observations. Each predicate is scenario-independent: it reads a Trace and a time
window and returns a measured value; `judge` turns value + limits into pass/fail.

    value = PRED[name](trace, i0, i1, **params)        # i0:i1 = window in steps
    limits: min / max (numbers) or equals (bool)

Adding a predicate: write the function, register it, add one synthetic unit test and one
mutation that it must catch (tests/test_beats.py). Never special-case a scenario in here.
"""
import numpy as np

from .trace import AXES, UP

PRED = {}


def pred(fn):
    PRED[fn.__name__] = fn
    return fn


def _agg(x, how):
    x = np.asarray(x, float)
    if x.size == 0:
        return float('nan')
    return float({'median': np.median, 'mean': np.mean, 'max': np.max, 'min': np.min,
                  'end': lambda a: a[-1], 'start': lambda a: a[0],
                  'p90': lambda a: np.percentile(a, 90), 'p10': lambda a: np.percentile(a, 10)}[how](x))


def _side(name, side):
    return name.replace('$S', side or '').replace('$O', {'L': 'R', 'R': 'L'}.get(side, ''))


# -- joints ---------------------------------------------------------------------------------
@pred
def joint(tr, i0, i1, joint, agg='median', side=None):
    """Joint angle in anatomical degrees."""
    return _agg(tr.joints[_side(joint, side)][i0:i1], agg)


@pred
def joint_sum(tr, i0, i1, joints, agg='median', side=None):
    """Sum of several joints (e.g. spine + chest flexion = trunk slump)."""
    return _agg(sum(tr.joints[_side(j, side)][i0:i1] for j in joints), agg)


@pred
def joint_diff(tr, i0, i1, a, b, agg='median', side=None):
    """a - b: asymmetry between two joints (e.g. the two elbows)."""
    return _agg(tr.joints[_side(a, side)][i0:i1] - tr.joints[_side(b, side)][i0:i1], agg)


@pred
def joint_change(tr, i0, i1, joint, side=None, lead=0.1):
    """Change of a joint across the window relative to just before it (deg)."""
    k = max(1, int(lead / tr.dt))
    q = tr.joints[_side(joint, side)]
    return float(np.median(q[max(i0, i1 - k):i1]) - np.median(q[max(0, i0 - k):max(1, i0)]))


@pred
def intensity(tr, i0, i1, joints, agg='median', side=None, i_ref=None, lead=0.1):
    """How far a pose lever was reached, as a fraction of the way from where each joint was
    just before the window (i_ref) to the lever's extreme angle. 0 = did not move, 1 = fully
    there. A joint already within 8 deg of the extreme counts as reached (1)."""
    i_ref = i0 if i_ref is None else i_ref
    k = max(1, int(lead / tr.dt))
    out = []
    for j, a1 in joints.items():
        q = tr.joints[_side(j, side)]
        q0 = float(np.median(q[max(0, i_ref - k):max(1, i_ref)]))
        now = _agg(q[i0:i1], agg)
        if abs(a1 - q0) < 8.0:
            out.append(1.0 if abs(now - a1) < 12.0 else (1.0 - abs(now - a1) / 40.0))
        else:
            out.append((now - q0) / (a1 - q0))
    return float(np.mean(out)) if out else float('nan')


@pred
def height_diff(tr, i0, i1, a, b, agg='median'):
    """height(a) - height(b), m: size-independent 'is this part lifted relative to that'."""
    return _agg(tr.pos[i0:i1, tr.b(a), 2] - tr.pos[i0:i1, tr.b(b), 2], agg)


# -- tone -----------------------------------------------------------------------------------
@pred
def tone(tr, i0, i1, regions=None, agg='median'):
    """Mean commanded tone over regions (0 limp .. 1 full)."""
    regs = regions or list(tr.tone)
    return _agg(np.mean([tr.tone[r][i0:i1] for r in regs], axis=0), agg)


@pred
def tone_envelope_bumps(tr, i0, i1, regions=None):
    """Number of extra rises in the tone envelope: 0 means ramp-hold-fade, >0 means sporadic."""
    regs = regions or list(tr.tone)
    x = np.mean([tr.tone[r][i0:i1] for r in regs], axis=0)
    k = max(1, int(0.05 / tr.dt))
    x = x[::k]
    d = np.sign(np.round(np.diff(x), 3))
    d = d[d != 0]
    rises = int(((d[1:] > 0) & (d[:-1] < 0)).sum()) if len(d) > 1 else 0
    return float(rises)


# -- contact --------------------------------------------------------------------------------
@pred
def contact_time(tr, i0, i1, part, surface='canvas', min_bw=0.03):
    """Seconds the part carries load on the canvas (or ropes) inside the window."""
    f = tr.part_load(part) if surface == 'canvas' else sum(tr.rope_load[b] for b in tr.parts(part))
    return float((f[i0:i1] > min_bw * tr.weight).sum() * tr.dt)


@pred
def contact_peak_bw(tr, i0, i1, part):
    """Peak canvas force on the part, in body weights."""
    return float(tr.part_load(part)[i0:i1].max() / tr.weight) if i1 > i0 else 0.0


@pred
def first_touch_gap(tr, i0, i1, first, then, min_bw=0.05):
    """t(then touches) - t(first touches), s; > 0 means `first` landed first. NaN if either
    never touches in the window."""
    def tt(part):
        h = np.nonzero(tr.part_load(part)[i0:i1] > min_bw * tr.weight)[0]
        return h[0] * tr.dt if len(h) else float('nan')
    return float(tt(then) - tt(first))


@pred
def impacts(tr, i0, i1, part, min_bw=0.5, gap=0.04):
    """Count of separate hard impacts of the part on the canvas (bounces = impacts - 1)."""
    f = tr.part_load(part)[i0:i1]
    on = np.nonzero(f > 0.05 * tr.weight)[0]
    if not len(on):
        return 0.0
    n = 0
    for seg in np.split(on, np.nonzero(np.diff(on) > int(gap / tr.dt))[0] + 1):
        n += int(f[seg].max() > min_bw * tr.weight)
    return float(n)


# -- orientation ----------------------------------------------------------------------------
@pred
def facing(tr, i0, i1, body='chest', axis='front', toward='up', agg='median'):
    """Cosine between a body axis and a world direction (1 = aligned). chest front toward up
    = lying on her back; toward down = prone."""
    return _agg(tr.axis(body, axis)[i0:i1] @ AXES[toward], agg)


@pred
def lean(tr, i0, i1, body='chest', toward='back', agg='median'):
    """Tilt of the body's long axis from vertical toward a direction in her heading frame,
    degrees (+ = toward that direction). 0 upright, 90 horizontal."""
    H = tr.heading()
    d = {'front': H[:, 0], 'back': -H[:, 0], 'left': H[:, 1], 'right': -H[:, 1]}[toward]
    u = tr.axis(body, 'up')[i0:i1]
    return _agg(np.degrees(np.arctan2(u @ d, u @ UP)), agg)


@pred
def side_lying(tr, i0, i1, toward='left', agg='median'):
    """Cosine between her left (or right) axis and world down: 1 = lying on that side."""
    return _agg(tr.axis('chest', toward)[i0:i1] @ AXES['down'], agg)


@pred
def yaw_change(tr, i0, i1, body='pelvis'):
    """Net rotation about vertical across the window, degrees (spin on the canvas)."""
    f = tr.axis(body, 'front' if abs(tr.axis(body, 'front')[i0, 2]) < 0.8 else 'up')[i0:i1]
    a = np.unwrap(np.arctan2(f[:, 1], f[:, 0]))
    return float(np.degrees(a[-1] - a[0])) if len(a) else 0.0


@pred
def roll_events(tr, i0, i1):
    """Number of supine<->prone flips of the chest in the window."""
    c = tr.axis('chest', 'front')[i0:i1, 2]
    s = np.sign(c[np.abs(c) > 0.5])
    return float((np.diff(s) != 0).sum()) if len(s) > 1 else 0.0


# -- position / travel ----------------------------------------------------------------------
@pred
def height(tr, i0, i1, body, agg='median'):
    return _agg(tr.pos[i0:i1, tr.b(body), 2], agg)


@pred
def travel(tr, i0, i1, body='pelvis', toward='back'):
    """Displacement across the window along a direction of her heading frame, m."""
    H = tr.heading()
    d = {'front': H[:, 0], 'back': -H[:, 0], 'left': H[:, 1], 'right': -H[:, 1], 'up': UP}[toward]
    p = tr.pos[:, tr.b(body)]
    return float((p[max(i1 - 1, i0)] - p[i0]) @ d)


@pred
def rel(tr, i0, i1, point, frame='pelvis', axis='x', agg='median'):
    """Coordinate of `point` in the frame of body `frame`: x = her left, y = behind her,
    z = toward her head. Judged in HER frame, never the camera's."""
    return _agg(tr.in_frame(point, frame)[i0:i1, 'xyz'.index(axis)], agg)


@pred
def rel_gap(tr, i0, i1, a, b, frame='pelvis', axis='x', agg='median'):
    """coordinate(a) - coordinate(b) in the frame of `frame`. For feet along x: <= 0 means
    the left foot is to the right of the right foot, i.e. crossed."""
    k = 'xyz'.index(axis)
    return _agg(tr.in_frame(a, frame)[i0:i1, k] - tr.in_frame(b, frame)[i0:i1, k], agg)


@pred
def distance(tr, i0, i1, a, b, agg='median'):
    return _agg(np.linalg.norm(tr.pos[i0:i1, tr.b(a)] - tr.pos[i0:i1, tr.b(b)], axis=1), agg)


@pred
def speed(tr, i0, i1, body='pelvis', agg='max'):
    return _agg(tr.speed(body, max(1, int(0.03 / tr.dt)))[i0:i1], agg)


# -- dynamics -------------------------------------------------------------------------------
def _joints_of(tr, regions=None, joints=None):
    if joints:
        return joints
    key = {'neck': ('neck_', 'head_'), 'trunk': ('spine_', 'chest_'), 'arm_L': ('upper_arm_L', 'forearm_L', 'hand_L'),
           'arm_R': ('upper_arm_R', 'forearm_R', 'hand_R'), 'leg_L': ('thigh_L', 'shin_L', 'foot_L'),
           'leg_R': ('thigh_R', 'shin_R', 'foot_R')}
    pre = sum((key[r] for r in (regions or key)), ())
    return [j for j in tr.joints if j.startswith(pre)]


@pred
def oscillation(tr, i0, i1, regions=None, joints=None, lo_hz=5.0, hi_hz=14.0):
    """RMS joint motion inside a frequency band, degrees (largest joint). Tremor lives at
    5-14 Hz; breathing at 0.15-0.5 Hz."""
    n = i1 - i0
    if n < int(1.5 / hi_hz / tr.dt) or n < 16:        # needs 1.5 periods of the band's fast edge
        return float('nan')
    f = np.fft.rfftfreq(n, tr.dt)
    band = (f >= lo_hz) & (f <= hi_hz)
    best = 0.0
    for j in _joints_of(tr, regions, joints):
        x = tr.joints[j][i0:i1]
        X = np.fft.rfft((x - np.polyval(np.polyfit(np.arange(n), x, 1), np.arange(n))) * np.hanning(n))
        rms = np.sqrt(2 * (np.abs(X[band]) ** 2).sum()) / (n * np.sqrt(0.375))
        best = max(best, float(rms))
    return best


@pred
def jolt(tr, i0, i1, regions=None, joints=None, within=0.12):
    """Largest joint excursion in the first `within` seconds of the window (deg): the
    visible kick through a region right after an impact."""
    k = min(i1, i0 + max(2, int(within / tr.dt)))
    return float(max(np.ptp(tr.joints[j][i0:k]) for j in _joints_of(tr, regions, joints)))


@pred
def returns(tr, i0, i1, joints=None, regions=None, lead=0.05, settle=0.6):
    """After a jolt, distance from the pre-impact pose once settled (deg, worst joint): small
    = she snaps back to the posture she was stuck in."""
    a = max(0, i0 - int(lead / tr.dt))
    k = min(i1 - 1, i0 + int(settle / tr.dt))
    return float(max(abs(tr.joints[j][k] - tr.joints[j][a]) for j in _joints_of(tr, regions, joints)))


@pred
def range_of_motion(tr, i0, i1, joint, side=None):
    return float(np.ptp(tr.joints[_side(joint, side)][i0:i1])) if i1 > i0 else 0.0


@pred
def monotone_drift(tr, i0, i1, joint, side=None):
    """Net slow change of a joint over the window, deg (e.g. an arm that slowly rises)."""
    q = tr.joints[_side(joint, side)][i0:i1]
    k = max(1, len(q) // 10)
    return float(q[-k:].mean() - q[:k].mean())


# -- timing ---------------------------------------------------------------------------------
@pred
def event_gap(tr, i0, i1, a, b):
    """t(b) - t(a) in seconds; NaN if either event never happened."""
    if a not in tr.events or b not in tr.events:
        return float('nan')
    return float(tr.events[b] - tr.events[a])


@pred
def time_left_after(tr, i0, i1, event):
    """Seconds of take remaining after an event (e.g. on her back with >= 3 s left)."""
    return float(tr.t[-1] - tr.events[event]) if event in tr.events else float('nan')


@pred
def happened(tr, i0, i1, event):
    return 1.0 if event in tr.events else 0.0


def judge(value, lim):
    """lim: {min, max} -> (ok, text). NaN never passes: an unmeasurable claim is a failure,
    not a silent pass."""
    if value is None or not np.isfinite(value):
        return False, 'not measurable in this window'
    lo, hi = lim.get('min'), lim.get('max')
    ok = (lo is None or value >= lo) and (hi is None or value <= hi)
    want = (f'{lo:g}..{hi:g}' if lo is not None and hi is not None else
            f'>= {lo:g}' if lo is not None else f'<= {hi:g}' if hi is not None else 'any')
    return bool(ok), want
