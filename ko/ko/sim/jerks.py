"""Involuntary movement while out (handoff track G4): short, irregular, multi-site torque pulses.

Presets (owner 2026-11-16: build all three, default pronounced; exaggerated on purpose but
keeping the pattern: a delay after going out, an episode of irregular jerks, then stillness):

  quiet       none (limp, breathing only)
  mild        onset 0.5-1.5 s after out, episode 3-5 s, pulses ~4/s, amplitude 0.15 of a joint's limit
  pronounced  onset 0.3-1.0 s, episode 5-8 s, pulses ~6/s, amplitude 0.35, plus tonic phases
              authored in the archetype (keyed on the `out` event)

Intervals are gamma-distributed (shape 2.5 -> coefficient of variation ~0.63), each pulse picks
one region and 1-3 of its joints with random signs, and a half-sine profile 50-120 ms long.
Pulse sizes are fractions of each joint's own torque limit: animation choices, tuned by eye.
"""
import numpy as np

PRESETS = {
    'quiet': None,
    'mild': {'onset': (0.5, 1.5), 'episode': (3.0, 5.0), 'rate': 4.0, 'amp': 0.15},
    'pronounced': {'onset': (0.3, 1.0), 'episode': (5.0, 8.0), 'rate': 6.0, 'amp': 0.35},
    # coming round (owner 2026-11-18: jitters and kicks as consciousness is regained): fast small
    # jitters everywhere plus big leg kicks, tapering as she comes back
    'waking': {'onset': (0.0, 0.3), 'episode': (3.0, 4.5), 'rate': 7.0, 'amp': 0.3, 'after': 'waking',
               'weights': {'leg_L': 3.0, 'leg_R': 3.0, 'arm_L': 1.0, 'arm_R': 1.0, 'neck': 0.4, 'trunk': 0.6},
               'kick': 0.45},
}
REGION_W = {'arm_L': 1.0, 'arm_R': 1.0, 'leg_L': 1.0, 'leg_R': 1.0, 'neck': 0.6, 'trunk': 0.5}


class Jerks:
    def __init__(self, preset, ctl, rng):
        self.p = PRESETS[preset] if isinstance(preset, str) else preset
        self.after = (self.p or {}).get('after', 'out')
        self.ctl, self.rng = ctl, rng
        self.pulses = None              # [(t0, dur, {dof index: torque})]

    def _plan(self, t_out):
        p, rng, ctl = self.p, self.rng, self.ctl
        from .control import REGIONS
        t = t_out + rng.uniform(*p['onset'])
        t_end = t + rng.uniform(*p['episode'])
        rw = p.get('weights', REGION_W)
        regs = list(rw)
        w = np.array([rw[r] for r in regs])
        w /= w.sum()
        out = []
        while t < t_end:
            r = regs[rng.choice(len(regs), p=w)]
            js = np.nonzero(ctl.reg == REGIONS.index(r))[0]
            # no pulses on the upper-arm twist: they rolled the shoulder forward and turned the
            # elbow up and back, which read as hyperextension (2026-11-18)
            js = np.array([j for j in js if ctl.jn[j] not in ('upper_arm_L_twist', 'upper_arm_R_twist')])
            pick = rng.choice(js, size=min(len(js), int(rng.integers(1, 4))), replace=False)
            fade = 1.0 - 0.6 * (t - t_out) / max(t_end - t_out, 1e-6)      # episode tapers off
            # elbows and knees only jerk into flexion: a pulse toward the straight stop read as
            # hyperextension (2026-11-18)
            tq = {int(ctl.dadr[j]): float((1 if ctl.jn[j].split('_')[0] in ('forearm', 'shin')
                                           else rng.choice([-1, 1])) * p['amp'] * fade * ctl.tmax[j]
                                          * rng.uniform(0.5, 1.0)) for j in pick}
            if p.get('kick') and r.startswith('leg'):
                # a kick: hip and knee together, knee driven straight (bounded by the stop)
                side = r[-1]
                for jn_, sgn in ((f'thigh_{side}_flex', 1), (f'shin_{side}_flex', -1)):
                    if jn_ in ctl.jn:
                        j = ctl.jn.index(jn_)
                        tq[int(ctl.dadr[j])] = sgn * p['kick'] * fade * ctl.tmax[j] * rng.uniform(0.6, 1.0)
            out.append((t, rng.uniform(0.05, 0.12), tq))
            t += rng.gamma(2.5, 1.0 / (2.5 * p['rate']))
        return out

    def apply(self, d, t, events):
        if self.p is None or self.after not in events:
            return
        if self.pulses is None:
            self.pulses = self._plan(events[self.after])
        for t0, dur, tq in self.pulses:
            if t0 <= t < t0 + dur:
                s = np.sin(np.pi * (t - t0) / dur)
                for k, v in tq.items():
                    d.qfrc_applied[k] += v * s
