"""Coming round after being out (owner 2026-11-27: "make the kicks and jitters more organic,
theorize what the muscles would be doing when coming to, and simulate it").

Replaces random whole-limb torque pulses with a small motor model of what is *visible* when
someone comes round lying on their back. It is a movement reference for animation, nothing
clinical; every number below is an animation choice, tuned by eye against renders.

  1. twitches   before and around arousal: brief (40-90 ms), small, scattered jerks, mostly
                distal (fingers/wrist, ankle/foot, an elbow or a shoulder shrug), irregular
                intervals; they thin out as she comes back
  2. startle    at arousal: one quick, near-symmetric flexion flinch (shoulders draw in, elbows
                and hands curl, chin tucks, hips/knees bend a little), sides 15-40 ms apart
  3. tone order muscle tone comes back proximal -> distal: neck and trunk first, then hips and
                shoulders, then hands and feet (a per-region delay on the waking clock)
  4. movements  slow, purposeless, asymmetric primitives with minimum-jerk profiles: head turns
                and small lifts, a knee drawing up with the heel sliding, a leg rolling out, a
                hand going to the face or chest, fingers opening and closing. Each has a rise,
                a hold and a return; some returns are lapses (fast, the limb or head sags back)
  5. rest pose  while she is lying, the relaxed target is where her limbs lie at arousal, so
                earlier standing postures (the tonic arms) never drive her limbs against gravity
                once tone returns (rest: pose uses SUPINE_REST instead)

Config (controller.ko.wake_motor), all optional (variant: n re-rolls the random draws):
  after: waking            event that is the arousal moment
  pre_s: 0.8               twitches start this long before it (never before `not_before`)
  not_before: <t>          absolute time guard (grow: keep the approved past untouched)
  twitch: {rate: 2.5, tail: 0.6, tau: 2.0, amp: [0.10, 0.25]}
  startle: {amp: 0.18, dur: 0.18}            (amp: fraction of each joint's torque limit)
  moves: {gap: 0.9, tone: 0.22, lapse_p: 0.35, until: <s after arousal>}
  tremor: {hz: 7.0, deg: 1.5}
  breath: {amp: 3.0, rate: 1.7, tau: 4.0}   deeper, faster breathing after arousal (x base)
  tone_delay: {neck: 0.0, trunk: 0.3, arm: 0.9, leg: 0.5}  (s after arousal)
  gasp: {amp: 0.14, dur: 0.35}   fidget: {gap: 0.55, start: 0.6, tone: 0.12}
"""
import numpy as np

# relaxed supine rest (anatomical degrees, same convention as reference.POSES)
SUPINE_REST = {'upper_arm_L_abd': -68, 'upper_arm_L_flex': 6, 'upper_arm_L_twist': 10, 'forearm_L_flex': 22,
               'hand_L_flex': 18, 'upper_arm_R_abd': -66, 'upper_arm_R_flex': 8, 'upper_arm_R_twist': 12,
               'forearm_R_flex': 26, 'hand_R_flex': 20,
               'thigh_L_flex': 4, 'thigh_L_abd': 7, 'thigh_L_twist': 12, 'shin_L_flex': 8, 'foot_L_dorsi': -22,
               'thigh_R_flex': 6, 'thigh_R_abd': 6, 'thigh_R_twist': 10, 'shin_R_flex': 10, 'foot_R_dorsi': -20,
               'spine_flex': 0, 'chest_flex': 0, 'neck_flex': 2, 'head_flex': 0}

# twitch pool: joint -> (weight, sign) ; sign 0 = either way, +1 = only into flexion
TWITCH = {'hand_L_flex': (3, 0), 'hand_R_flex': (3, 0), 'hand_L_dev': (1, 0), 'hand_R_dev': (1, 0),
          'forearm_L_flex': (1.5, 1), 'forearm_R_flex': (1.5, 1),
          'foot_L_dorsi': (2.5, 0), 'foot_R_dorsi': (2.5, 0), 'foot_L_inv': (1, 0), 'foot_R_inv': (1, 0),
          'upper_arm_L_abd': (1, 0), 'upper_arm_R_abd': (1, 0), 'shin_L_flex': (1, 1), 'shin_R_flex': (1, 1),
          'neck_twist': (0.8, 0), 'chest_flex': (0.5, 1)}

# startle flinch (signs into flexion / adduction); per-joint fraction of the global amp
STARTLE = {'upper_arm_{s}_abd': -0.8, 'upper_arm_{s}_flex': 0.5, 'forearm_{s}_flex': 0.55, 'hand_{s}_flex': 0.7,
           'thigh_{s}_flex': 0.6, 'shin_{s}_flex': 0.45, 'foot_{s}_dorsi': 0.5}
STARTLE_AXIAL = {'neck_flex': 0.8, 'head_flex': 0.5, 'chest_flex': 0.5, 'spine_flex': 0.3}


def mj(u):
    """minimum-jerk 0..1"""
    u = min(max(u, 0.0), 1.0)
    return u * u * u * (10 - 15 * u + 6 * u * u)


def _moves_library(side, rng, head_to=0.0):
    """the movement primitives (absolute anatomical targets for the joints they touch);
    head_to: neck twist (deg) the next head turn goes to"""
    o = 'R' if side == 'L' else 'L'
    return {
        'head_turn': ({'neck_twist': head_to, 'head_lat': np.sign(head_to) * rng.uniform(2, 6),
                       'neck_flex': rng.uniform(0, 6)}, ('neck',)),
        'head_lift': ({'neck_flex': rng.uniform(18, 28), 'head_flex': rng.uniform(4, 10),
                       'chest_flex': rng.uniform(2, 6)}, ('neck', 'trunk')),
        'knee_draw': ({f'thigh_{side}_flex': rng.uniform(45, 70), f'shin_{side}_flex': rng.uniform(75, 105),
                       f'thigh_{side}_abd': rng.uniform(2, 10), f'thigh_{side}_twist': rng.uniform(-5, 8),
                       f'foot_{side}_dorsi': rng.uniform(-5, 8)}, (f'leg_{side}',)),
        'leg_roll': ({f'thigh_{side}_twist': rng.uniform(20, 32), f'thigh_{side}_abd': rng.uniform(10, 18),
                      f'shin_{side}_flex': rng.uniform(10, 25), f'foot_{side}_inv': rng.uniform(-8, 8)}, (f'leg_{side}',)),
        # hand to the face: elbow folds deep, upper arm only half raised and drawn across, so the
        # hand lands on the forehead/eyes instead of reaching up past the face (v1 review)
        'hand_to_face': ({f'upper_arm_{side}_flex': rng.uniform(50, 62), f'upper_arm_{side}_abd': rng.uniform(-55, -40),
                          f'upper_arm_{side}_twist': rng.uniform(40, 60), f'forearm_{side}_flex': rng.uniform(135, 148),
                          f'hand_{side}_flex': rng.uniform(10, 30)}, (f'arm_{side}',)),
        'hand_to_chest': ({f'upper_arm_{side}_flex': rng.uniform(30, 45), f'upper_arm_{side}_abd': rng.uniform(-55, -40),
                           f'upper_arm_{side}_twist': rng.uniform(20, 40), f'forearm_{side}_flex': rng.uniform(95, 115),
                           f'hand_{side}_flex': rng.uniform(20, 40)}, (f'arm_{side}',)),
        'arm_slide': ({f'upper_arm_{side}_abd': rng.uniform(-45, -30), f'upper_arm_{side}_flex': rng.uniform(-10, 5),
                       f'forearm_{side}_flex': rng.uniform(50, 75), f'hand_{side}_flex': rng.uniform(-20, 0)}, (f'arm_{side}',)),
        'fist': ({f'hand_{side}_flex': rng.uniform(35, 55), f'hand_{o}_flex': rng.uniform(5, 25)}, (f'arm_{side}',)),
    }


class WakeMotor:
    def __init__(self, cfg, ctl, rng):
        self.c = cfg or {}
        self.ctl, self.rng = ctl, rng
        self.after = self.c.get('after', 'waking')
        self.gain_changes = None
        self.t_w = None
        self.pulses = []                  # (t0, dur, {dof: torque})
        self.moves = []                   # (t0, rise, hold, ret, ret_frac, pose_vec, mask, region idx, tone, name)
        self.log = []
        self.q_rest = None
        self._ph = self._tb = None

    # -- planning ---------------------------------------------------------------------------
    def _plan(self, t_w):
        c, rng, ctl = self.c, self.rng, self.ctl
        from .control import REGIONS
        nb = float(c.get('not_before', -1e9))
        # 1. twitches: rate peaks at arousal, decays with tau, keeps a sparse tail
        tw = dict({'rate': 2.5, 'tail': 0.6, 'tau': 2.0, 'amp': [0.10, 0.25]}, **(c.get('twitch') or {}))
        names = [n for n in TWITCH if n in ctl.idx]
        w = np.array([TWITCH[n][0] for n in names], float)
        w /= w.sum()
        t, t_end = max(t_w - float(c.get('pre_s', 0.8)), nb), t_w + float(c.get('moves', {}).get('until', 6.0))
        while t < t_end:
            dt_ = abs(t - t_w)
            rate = tw['tail'] + (tw['rate'] - tw['tail']) * np.exp(-dt_ / tw['tau'])
            n_ = int(rng.integers(1, 3))
            tq = {}
            for j in rng.choice(len(names), size=n_, replace=False, p=w):
                nm = names[j]
                i = ctl.idx[nm]
                sgn = TWITCH[nm][1] or rng.choice([-1, 1])
                tq[int(ctl.dadr[i])] = float(sgn * rng.uniform(*tw['amp']) * ctl.tmax[i])
            self.pulses.append((t, rng.uniform(0.04, 0.09), tq))
            t += rng.gamma(2.0, 1.0 / (2.0 * rate))
        # 2. startle at arousal
        st = dict({'amp': 0.18, 'dur': 0.18}, **(c.get('startle') or {}))
        if st['amp'] > 0 and t_w >= nb:
            first = rng.choice(['L', 'R'])
            for s in ('L', 'R'):
                lag = 0.0 if s == first else rng.uniform(0.015, 0.04)
                k = rng.uniform(0.8, 1.2)
                tq = {}
                for pat, f in STARTLE.items():
                    nm = pat.format(s=s)
                    if nm in ctl.idx:
                        i = ctl.idx[nm]
                        tq[int(ctl.dadr[i])] = float(f * k * st['amp'] * ctl.tmax[i])
                if s == first:
                    for nm, f in STARTLE_AXIAL.items():
                        if nm in ctl.idx:
                            i = ctl.idx[nm]
                            tq[int(ctl.dadr[i])] = float(f * st['amp'] * ctl.tmax[i])
                self.pulses.append((t_w + lag, st['dur'] * rng.uniform(0.85, 1.15), tq))
        # 2b. gasp: a sharp inhalation with the arousal (chest and neck extend, shoulders lift a
        # little), just ahead of the flinch
        gp = dict({'amp': 0.14, 'dur': 0.35}, **(c.get('gasp') or {}))
        if gp['amp'] > 0 and t_w - 0.06 >= nb:
            tq = {}
            for nm, f in (('chest_flex', -1.0), ('spine_flex', -0.5), ('neck_flex', -0.6),
                          ('upper_arm_L_abd', 0.25), ('upper_arm_R_abd', 0.25)):
                if nm in ctl.idx:
                    i = ctl.idx[nm]
                    tq[int(ctl.dadr[i])] = float(f * gp['amp'] * ctl.tmax[i])
            self.pulses.append((t_w - 0.06, gp['dur'], tq))
        # 2c. fidgets: small overlapping hand/foot movements (relative to wherever the limb is),
        # so something is always a little alive once she starts coming round
        fd = dict({'gap': 0.55, 'start': 0.6, 'tone': 0.12}, **(c.get('fidget') or {}))
        t = t_w + fd['start']
        while fd['gap'] > 0 and t < t_w + float(c.get('moves', {}).get('until', 6.0)):
            sd = rng.choice(['L', 'R'])
            if rng.random() < 0.55:
                dl = {f'hand_{sd}_flex': rng.uniform(-25, 25), f'hand_{sd}_dev': rng.uniform(-10, 10)}
                reg = f'arm_{sd}'
            else:
                dl = {f'foot_{sd}_dorsi': rng.uniform(-15, 15), f'foot_{sd}_inv': rng.uniform(-8, 8)}
                reg = f'leg_{sd}'
            dv = np.zeros(len(ctl.jn))
            for nm, v in dl.items():
                if nm in ctl.idx:
                    dv[ctl.idx[nm]] = np.radians(v)
            self.moves.append((t, rng.uniform(0.3, 0.6), rng.uniform(0.1, 0.4), rng.uniform(0.3, 0.6), 1.0, dv,
                               dv != 0, [REGIONS.index(reg)], fd['tone'], 'fidget', False, True))
            t += rng.gamma(2.0, fd['gap'] / 2.0)
        # 3./4. movements: head first, then legs, then arms/hands; asymmetric, with lapses
        mv = dict({'gap': 0.9, 'tone': 0.22, 'lapse_p': 0.35, 'until': 6.0,
                   'tone_kind': {'neck': 0.22, 'trunk': 0.22, 'arm': 0.25, 'leg': 0.35},
                   # carrying the hand up to the face against gravity needs more (v3: stopped 0.35 m short)
                   'tone_move': {'hand_to_face': 0.42, 'hand_to_chest': 0.32}}, **(c.get('moves') or {}))
        td = dict({'neck': 0.0, 'trunk': 0.3, 'arm': 0.9, 'leg': 0.5}, **(c.get('tone_delay') or {}))
        seq = c.get('sequence') or ['head_turn', 'knee_draw', 'head_lift', 'hand_to_face', 'leg_roll', 'head_turn',
                                     'hand_to_chest', 'knee_draw', 'arm_slide', 'fist', 'head_turn']
        t = t_w + 0.35
        side = rng.choice(['L', 'R'])
        # the head starts rolled to one side; turns go back toward and past the middle, then back
        tw0 = 0.0
        if 'neck_twist' in ctl.idx and ctl._q_now is not None:
            tw0 = float(np.degrees(ctl._q_now[ctl.idx['neck_twist']]) + ctl.off[ctl.idx['neck_twist']])
        hs = -np.sign(tw0) if abs(tw0) > 5 else rng.choice([-1, 1])
        for name in seq:
            if t > t_w + mv['until']:
                break
            head_to = 0.0
            if name == 'head_turn':
                head_to = float(hs * rng.uniform(12, 28))
                hs = -hs
            lib = _moves_library(side, rng, head_to)
            if name not in lib:
                continue
            pose, regs = lib[name]
            kind = regs[0].split('_')[0]
            t0 = max(t, t_w + td.get(kind, 0.0))
            slow = 1.0 + 0.6 * np.exp(-(t0 - t_w) / 2.0)          # first movements are the slowest
            rise = rng.uniform(0.6, 1.1) * slow
            hold = rng.uniform(0.3, 1.4)
            lapse = rng.random() < mv['lapse_p']
            if name == 'head_lift':        # lifting the head is effortful: brief, usually drops back (v3 review)
                hold, lapse = rng.uniform(0.2, 0.6), rng.random() < 0.65
            kick = name == 'knee_draw' and not lapse and rng.random() < mv.get('kick_p', 0.6)
            ret = rng.uniform(0.15, 0.3) if lapse else rng.uniform(0.35, 0.5) if kick else rng.uniform(0.7, 1.2) * slow
            ret_frac = 1.0 if (lapse or kick) else rng.uniform(0.35, 0.9)
            if kick:                       # the drawn-up leg pushes back out (a kick), tone kept (v5 review)
                hold = rng.uniform(0.15, 0.5)
            pv = ctl.pose_vec(pose, base=np.zeros(len(ctl.jn)))
            mask = np.array([n in pose for n in ctl.jn])
            ridx = [REGIONS.index(r) for r in regs]
            tk = (mv.get('tone_move') or {}).get(name, (mv.get('tone_kind') or {}).get(kind, mv['tone']))
            self.moves.append((t0, rise, hold, ret, ret_frac, pv, mask, ridx, tk * rng.uniform(0.8, 1.2), name, lapse, False))
            self.log.append({'t0': round(t0, 2), 'move': name + (' + kick out' if kick else ''), 'side': side if 'head' not in name else '-',
                             'rise': round(rise, 2), 'hold': round(hold, 2), 'lapse': bool(lapse)})
            t = t0 + min(rng.gamma(3.0, mv['gap'] / 3.0), 1.6 * mv['gap'])    # no long dead gaps (v3 review)
            if 'head' not in name and rng.random() < 0.65:
                side = 'L' if side == 'R' else 'R'

    # -- target / tone (called from the controller each step) ------------------------------
    def modify(self, t, events, tone_r, target):
        if self.after not in events:
            return tone_r, target
        if self.t_w is None:
            self.t_w = events[self.after]
            self._plan(self.t_w)
        ctl, c, t_w = self.ctl, self.c, self.t_w
        from .control import REGIONS
        nb = float(c.get('not_before', -1e9))
        if t < max(t_w - float(c.get('pre_s', 0.8)), nb):
            return tone_r, target
        # rest pose takes over from earlier postures over 0.5 s from the arousal. Default: where
        # her limbs lie at that moment (v4 review: a guessed supine pose stood her forearms up off
        # the canvas once tone came back); rest: pose uses SUPINE_REST instead
        if self.q_rest is None and ctl._q_now is not None and t >= t_w - 0.2:
            self.q_rest = np.array(ctl._q_now, float).copy()
        wr = mj((t - t_w + 0.2) / 0.5)
        if wr > 0 and self.q_rest is not None:
            rest = ctl.pose_vec(SUPINE_REST, base=target) if c.get('rest') == 'pose' else self.q_rest
            sel = np.isin(ctl.reg, [REGIONS.index(r) for r in ('arm_L', 'arm_R', 'leg_L', 'leg_R')])
            target = target.copy()
            target[sel] = (1 - wr) * target[sel] + wr * rest[sel]
            # the head comes off its arched, chin-up rest toward neutral as neck tone returns
            # (v6 review), over neck_settle s
            wn = mj((t - t_w) / float(c.get('neck_settle', 2.5)))
            for nm, v in (('neck_flex', c.get('neck_rest', 2.0)), ('head_flex', 0.0)):
                if nm in ctl.idx:
                    i = ctl.idx[nm]
                    target[i] = (1 - wn) * target[i] + wn * np.radians(v - ctl.off[i])
        tr = dict({'hz': 7.0, 'deg': 1.5}, **(c.get('tremor') or {}))
        L = getattr(ctl, 'L', 0.0)
        for (t0, rise, hold, ret, ret_frac, pv, mask, ridx, tone, name, lapse, rel) in self.moves:
            a = t - t0
            if rel:                                            # fidget: a delta on the target
                if 0 <= a <= rise + hold + ret:
                    w = mj(a / rise) if a < rise else 1.0 if a < rise + hold else 1.0 - mj((a - rise - hold) / ret)
                    target = target + w * pv
                    for r in ridx:
                        tone_r[r] = max(tone_r[r], tone * w)
                continue
            if a < 0 or a > rise + hold + ret + 0.05:
                if a > rise + hold + ret and ret_frac < 1.0:      # a partial return stays put
                    w = 1.0 - ret_frac
                    if w > 0:
                        target = target.copy()
                        target[mask] = (1 - w) * target[mask] + w * pv[mask]
                continue
            if a < rise:
                w = mj(a / rise)
            elif a < rise + hold:
                w = 1.0
            else:
                w = 1.0 - ret_frac * mj((a - rise - hold) / ret)
            target = target.copy()
            target[mask] = (1 - w) * target[mask] + w * pv[mask]
            if tr['deg'] > 0 and a < rise + hold:              # effort tremor, fades as she comes back
                target[mask] += np.radians(tr['deg']) * (1 - L) * w * np.sin(2 * np.pi * tr['hz'] * t + ctl.tremor_phase[mask])
            # tone: the moving region gets enough to carry the limb; a lapse drops it
            env = w if not (lapse and a > rise + hold) else 0.0
            for r in ridx:
                tone_r[r] = max(tone_r[r], tone * env)
        return tone_r, np.clip(target, ctl.lo + 0.01, ctl.hi - 0.01)

    # -- torque pulses (called with the jerks) ---------------------------------------------
    def apply(self, d, t, events):
        if self.t_w is None:
            return
        for t0, dur, tq in self.pulses:
            if t0 <= t < t0 + dur:
                s = np.sin(np.pi * (t - t0) / dur)
                for k, v in tq.items():
                    d.qfrc_applied[k] += v * s

    # -- breathing (called from the sim loop) ------------------------------------------------
    def breath(self, t, amp_deg, period):
        """chest breathing target offset (rad). Unchanged until the arousal; then deeper, faster
        breaths that settle back (recovering after being out), phase-continuous."""
        base = np.radians(amp_deg) * np.sin(2 * np.pi * t / period)
        if self.t_w is None or t < self.t_w:
            return base
        b = dict({'amp': 3.0, 'rate': 1.7, 'tau': 4.0}, **(self.c.get('breath') or {}))
        if self._ph is None:
            self._ph, self._tb = 2 * np.pi * t / period, t
        k = np.exp(-(t - self.t_w) / b['tau'])
        self._ph += 2 * np.pi / period * (1 + (b['rate'] - 1) * k) * (t - self._tb)
        self._tb = t
        return np.radians(amp_deg) * (1 + (b['amp'] - 1) * k) * np.sin(self._ph)
