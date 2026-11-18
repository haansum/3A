"""Consciousness level L(t) and per-region voluntary authority a_r = curve_r(L).

The strike KO used to be a switch (t_ko). It is now one global level L in [0, 1] supplied by a
driver, and each body region maps L to its own authority through an adjustable curve, so
regions can fail in their own order (neck first, legs last, ...). The controller uses a_r for:
  tone    tone_r = residual_r + (1 - residual_r) * a_r          (replaces the off_ramp)
  target  target = b * q_cmd + (1 - b) * q_rel, b = a_r (target: follow)
          or the legacy frozen pose (target: hold)
          q_rel starts at the command when L first drops and relaxes toward the actual pose
          with time constant t_relax (inf = never: the legacy hold)
  assist  root assist cut at the drop (assist: cut, legacy) or scaled by L (assist: scale)

Drivers (controller.consciousness.driver):
  strike    L ramps 1 -> 0 linearly over `ramp` s (default: ko.off_ramp) from the KO strike.
            With identity curves, target: hold, assist: cut, t_relax: inf it reproduces the
            pre-refactor controller bit for bit (golden-master tested).
  flash     L dips to L_min over `drop` s, holds `hold` s, recovers over `recover` s
            (smoothstep): stumble-and-recover knockdowns.
  scripted  L from keys [[t, L], ...] after the strike (linear), for tests and directing.
  choke     L from a deficit D in [0, 1] fed every step with the hold's squeeze score (feed()):
            D rises at `rate`/s scaled by how far the score is above `score_on` (full at `full`), and
            falls at `decay`/s only while the score is below `score_on`, so L never rises while she is
            squeezed. L = 1 - smoothstep(D). Events: fading (L < 0.95), out (L < 0.05).
            The score and every rate are tuned animation signals, not physiology.

Curves (controller.consciousness.curves): region or group name -> [[L, a], ...] (piecewise
linear, must span L = 0..1). Names: neck, trunk, arm_L, arm_R, leg_L, leg_R, or the groups
arms, legs, axial, default. Missing -> identity (a = L exactly).

Events written by the controller: L_half (first L < 0.5), L_min (time of the minimum; value in
event_data), recovered (L back to 1 for good). t_ko stays the onset of the drop, which is what
every existing phase, gate and bake step keys on.
"""
import math

import numpy as np

GROUPS = {'arms': ('arm_L', 'arm_R'), 'legs': ('leg_L', 'leg_R'), 'axial': ('neck', 'trunk')}


def _smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


class Consciousness:
    def __init__(self, cfg, ko_cfg, regions):
        cfg = dict(cfg or {})
        self.cfg = cfg
        self.driver = cfg.get('driver', 'strike')
        self.target_mode = cfg.get('target', 'hold' if self.driver == 'strike' else 'follow')
        self.assist_mode = cfg.get('assist', 'cut' if self.driver == 'strike' else 'scale')
        tr = cfg.get('t_relax', math.inf if self.driver == 'strike' else 0.8)
        self.t_relax = math.inf if tr in (None, 'inf') else float(tr)
        self.ramp = cfg.get('ramp', (ko_cfg or {}).get('off_ramp', 0.04))
        self.regions = list(regions)
        self.curves = [None] * len(self.regions)
        for i, r in enumerate(self.regions):
            for key in (r, next((g for g, rs in GROUPS.items() if r in rs), None), 'default'):
                if key and key in (cfg.get('curves') or {}):
                    pts = np.array(cfg['curves'][key], float)
                    self.curves[i] = (pts[:, 0], pts[:, 1])
                    break
        self.t0 = None
        self.t_rec = None
        self._min = (None, 1.0)
        self.D = 0.0                       # choke deficit

    # -- driver ---------------------------------------------------------------------------
    def hit(self, t):
        if self.t0 is None:
            self.t0 = t

    def level(self, t):
        if self.t0 is None or t < self.t0:
            return 1.0
        u = t - self.t0
        c = self.cfg
        if self.driver == 'strike':
            return max(0.0, 1.0 - u / self.ramp)
        if self.driver == 'flash':
            lm, dr, hd, rc = c.get('L_min', 0.3), c.get('drop', 0.08), c.get('hold', 0.4), c.get('recover', 1.2)
            if u < dr:
                return 1.0 - (1.0 - lm) * u / dr
            if u < dr + hd:
                return lm
            return lm + (1.0 - lm) * _smooth((u - dr - hd) / rc)
        if self.driver == 'choke':
            return 1.0 - _smooth(self.D)
        if self.driver == 'scripted':
            k = np.array(c['keys'], float)
            return float(np.interp(u, k[:, 0], k[:, 1]))
        raise ValueError(f'unknown consciousness driver {self.driver!r}')

    def feed(self, t, score, dt):
        """choke driver: integrate the squeeze score into the deficit"""
        if self.driver != 'choke' or self.t0 is None or t < self.t0:
            return
        c = self.cfg
        on, full = c.get('score_on', 0.05), c.get('full', 0.25)
        if score >= on:
            self.D = min(1.0, self.D + dt * c.get('rate', 0.16) * min(1.0, (score - on) / max(full - on, 1e-6)))
        elif self.D < 1.0 or not c.get('latch', True):     # once out, out for good (no waking in v1)
            self.D = max(0.0, self.D - dt * c.get('decay', 0.05))

    def authority(self, L):
        """per-region authority array (len REGIONS)."""
        a = np.empty(len(self.regions))
        for i, cv in enumerate(self.curves):
            a[i] = L if cv is None else float(np.interp(L, cv[0], cv[1]))
        return a

    def recovered(self, t):
        return self.t_rec is not None and t >= self.t_rec

    def update_events(self, t, L, events, event_data):
        if self.t0 is None or t < self.t0:
            return
        if self.driver == 'choke':
            if L < 0.95 and 'fading' not in events:
                events['fading'] = t
            if L < 0.05 and 'out' not in events:
                events['out'] = t
        if L < 0.5 and 'L_half' not in events:
            events['L_half'] = t
        if L < self._min[1] - 1e-12:
            self._min = (t, L)
        elif self._min[0] is not None and 'L_min' not in events and L > self._min[1] + 1e-6:
            events['L_min'] = self._min[0]
            event_data['L_min'] = {'L': self._min[1]}
        if self.driver != 'strike' and L >= 0.999 and t > self.t0 + 1e-6 and self.t_rec is None \
                and self._min[1] < 0.999:
            self.t_rec = t
            events['recovered'] = t
