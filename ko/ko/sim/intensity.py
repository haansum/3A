"""Intensity shaping for tonic-posture phases (owner 2026-11-12).

A phase that uses any of the keys below takes the shaped path; a phase without them keeps
the legacy trapezoid code in control.py unchanged (golden-master tested).

Per phase (all optional):
  shape:   trapezoid | crescendo | overshoot | ratchet | pulse        (default trapezoid)
  shape_params: {...}           see SHAPES below
  depth:   number (end) | {start, end, tau}   how far into the pose the target goes, 0..~1.3
           (separate from tone: tone = how hard, depth = how far)
  variety: {depth: [lo, hi], spread: 0.12, key_frac: 0.5, keep_key: 0.7,
            jitter_key_deg: 3, jitter_minor_deg: 9}
           sampled once per take and phase from the take seed: per-region depth, per-joint
           spread and angle jitter. Key joints (the ones that define the posture) keep at
           least keep_key of their depth and get less jitter, so the posture keeps its spirit.
  stagger: {region: seconds}    per-region onset delay
  gain:    {region: factor}     per-region tone and depth multiplier (asymmetry)
  jitter:  0.15                 seeded relative variation of onset (x0.1 s), peak, hold, fade
  scale_by: {event, key, map: [[x0, y0], [x1, y1], ...]}   peak tone and depth multiplied by
           the interpolated y of the measured event quantity x (e.g. head impact speed)
  shape_if: [{event, key, gt, shape, shape_params}]       pick the shape from the measurement
  pose:    name | [[name, weight], ...] | {by_region: {region: spec}} |
           {base: spec, pick: [{from: name, joints: [..]}]}           mixed postures

Every number here is an artistic control, tuned by eye.
"""
import math

import numpy as np

SHAPES = ('trapezoid', 'crescendo', 'overshoot', 'ratchet', 'pulse', 'ratchet_pulse')


def _smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def timed(changes, t, base):
    """Time-stamped changes (2026-11-18, segment-by-segment authoring): `changes` is a list of
    [t0, value, ramp_s]; before the first t0 the value is `base` (which may itself vary with t),
    from each t0 it ramps linearly to `value` over ramp_s. Nothing before a change's t0 is
    touched, so a later segment can retune a knob without changing the past."""
    v = base
    for t0, val, ramp in sorted((list(c) + [1.0])[:3] for c in (changes or [])):
        if t < t0:
            break
        u = min(1.0, (t - t0) / max(float(ramp), 1e-6))
        v = v + (float(val) - v) * u
    return v


def interp_map(x, pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return float(np.interp(x, xs, ys))


def tone_env(shape, a, rise, hold, fade, sp):
    """0..1 envelope on the phase's peak tone at phase-local time a (s)."""
    end = rise + hold
    if shape == 'crescendo':
        tau = sp.get('tau', 0.5)
        if a < end:
            return 1.0 - math.exp(-a / tau)
        v = 1.0 - math.exp(-end / tau)
        return max(0.0, v * (1.0 - (a - end) / fade))
    if shape == 'ratchet_pulse':
        # owner 2026-11-18 (lifted RNC): the ratchet climbs in irregular notches and, while it
        # is climbing, the tone pulses (a dip of `pulse_amp` at `pulse_hz`) between notches; once
        # the last notch is in, it holds steady, then fades
        v = _ratchet_level(a, sp)
        if a < end:
            t_last = (sp['_times'][-1] if '_times' in sp else (sp.get('steps', 4) - 1) * sp.get('step_dt', 0.22)) \
                + sp.get('step_rise', 0.05)
            if a < t_last:              # pulse tapers out over the last half second (no jump)
                taper = 1.0 - _smooth((a - (t_last - 0.5)) / 0.5)
                v *= 1.0 - taper * sp.get('pulse_amp', 0.3) * 0.5 * (1.0 - math.cos(2 * math.pi * sp.get('pulse_hz', 2.0) * a))
            return min(v, 1.0)
        return max(0.0, (1.0 - (a - end) / fade))
    if shape == 'ratchet':
        steps, sdt, srise = sp.get('steps', 4), sp.get('step_dt', 0.22), sp.get('step_rise', 0.05)
        lvl = sp.get('start', 0.35)
        if a < end:
            v = lvl
            for k in range(steps):
                tk = sp['_times'][k] if '_times' in sp else k * sdt
                v += (1.0 - lvl) / steps * _smooth((a - tk) / srise)
            return min(v, 1.0)
        return max(0.0, (1.0 - (a - end) / fade))
    if shape == 'pulse':
        f, base, amp = sp.get('hz', 0.6), sp.get('base', 0.55), sp.get('amp', 0.45)
        v = min(1.0, a / rise) * min(1.0, max(0.0, base + amp * math.sin(2 * math.pi * f * a - 1.2)))
        return v if a < end else v * max(0.0, 1.0 - (a - end) / fade)
    # trapezoid and overshoot (overshoot shapes the pose, not the tone: the lock is instant)
    if a < rise:
        return a / rise
    if a < end:
        return 1.0
    return max(0.0, 1.0 - (a - end) / fade)


def _ratchet_level(a, sp):
    steps, sdt, srise = sp.get('steps', 4), sp.get('step_dt', 0.22), sp.get('step_rise', 0.05)
    lvl = sp.get('start', 0.0)
    v = lvl
    for k in range(steps):
        tk = sp['_times'][k] if '_times' in sp else k * sdt
        sz = sp['_sizes'][k] if '_sizes' in sp else 1.0 / steps
        v += (1.0 - lvl) * sz * _smooth((a - tk) / srise)
    return min(v, 1.0)


def depth_curve(shape, a, rise, hold, fade, sp, d0, d1, tau):
    """Pose blend fraction (can exceed 1: past the pose, toward its direction)."""
    if shape == 'overshoot':
        fn, z = sp.get('fn', 2.2), sp.get('zeta', 0.32)
        wn = 2 * math.pi * fn
        wd = wn * math.sqrt(1 - z * z)
        s = 1 - math.exp(-z * wn * a) * (math.cos(wd * a) + z / math.sqrt(1 - z * z) * math.sin(wd * a))
        return d0 + (d1 - d0) * s
    if shape == 'ratchet_pulse':
        # pose notches up with the tone; while climbing it also pulses (smaller than the tone)
        v = _ratchet_level(a, dict(sp, start=0.0))
        t_last = (sp['_times'][-1] if '_times' in sp else (sp.get('steps', 4) - 1) * sp.get('step_dt', 0.22)) \
            + sp.get('step_rise', 0.05)
        if a < t_last:
            taper = 1.0 - _smooth((a - (t_last - 0.5)) / 0.5)
            v *= 1.0 - taper * sp.get('pulse_depth', 0.15) * 0.5 * (1.0 - math.cos(2 * math.pi * sp.get('pulse_hz', 2.0) * a))
        return d0 + (d1 - d0) * v
    if shape == 'ratchet':
        steps, sdt, srise = sp.get('steps', 4), sp.get('step_dt', 0.22), sp.get('step_rise', 0.05)
        v = 0.0
        for k in range(steps):
            tk = sp['_times'][k] if '_times' in sp else k * sdt
            sz = sp['_sizes'][k] if '_sizes' in sp else 1.0 / steps
            v += sz * _smooth((a - tk) / srise)
        return d0 + (d1 - d0) * min(v, 1.0)
    if shape in ('crescendo', 'pulse'):
        return d0 + (d1 - d0) * (1.0 - math.exp(-a / max(tau, 1e-3)))
    return d0 + (d1 - d0) * min(1.0, a / max(rise, 1e-3))


class Activation:
    """First-order muscle-activation filter on tone, faster up than down. Smooths any step in
    stiffness so a sharp authored change cannot kick the body (torque = tone * kp * error)."""

    def __init__(self, n, tau_up, tau_down):
        self.x = None
        self.up, self.down = tau_up, tau_down

    def __call__(self, u, dt):
        if self.x is None:
            self.x = u.copy()
            return self.x
        tau = np.where(u > self.x, self.up, self.down)
        self.x = self.x + (u - self.x) * np.minimum(1.0, dt / tau)
        return self.x


class TargetFilter:
    """Critically damped 2nd-order trajectory on the joint targets: the commanded posture moves
    with bounded acceleration, and its velocity is fed to the servo as the velocity target."""

    def __init__(self, hz, zeta=1.0):
        self.w = 2 * math.pi * hz
        self.z = zeta
        self.q = None
        self.v = None

    def __call__(self, goal, dt):
        if self.q is None:
            self.q, self.v = goal.copy(), np.zeros_like(goal)
            return self.q, self.v
        acc = self.w * self.w * (goal - self.q) - 2 * self.z * self.w * self.v
        self.v = self.v + acc * dt              # semi-implicit Euler, stable for w*dt << 1
        self.q = self.q + self.v * dt
        return self.q, self.v


class OU:
    """Seeded Ornstein-Uhlenbeck noise, unit variance, correlation time tau."""

    def __init__(self, n, tau, rng):
        self.x = np.zeros(n)
        self.tau, self.rng = tau, rng

    def __call__(self, dt):
        a = dt / self.tau
        self.x += -a * self.x + math.sqrt(2 * a) * self.rng.standard_normal(len(self.x))
        return self.x


def is_shaped(ph):
    return any(k in ph for k in ('shape', 'depth', 'variety', 'stagger', 'gain', 'jitter',
                                 'scale_by', 'shape_if', 'shape_set', 'fallback')) or isinstance(ph.get('pose'), (list, dict)) \
        or str(ph.get('pose', '')).startswith('@') or isinstance(ph.get('after'), list)
