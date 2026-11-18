"""Tone controller: one PD law for the whole take; the KO is a change of tone, not of state.

  tau_j = clip( tone_r * [ kp_j (q*_j - q_j) + kv_j (qd*_j - qd_j) ],  +-tone_r * tau_max_j )

 - gains from the reduced inertia of the two rigid halves each joint connects (see
   set_inertia: 1/diag(M^-1) was measured to be far too soft); a planted leg sees the body
   above it
 - damping sits inside the torque cap and acts on velocity error
 - at the KO nothing is zeroed or frozen: the last command stays, tone ramps to residual over
   tens of ms, tonic-posturing phases then raise tone toward their own target poses
 - integration is implicit in the actuator (MuJoCo affine actuators), so stiff gains are stable

Root assist: a capped, logged PD wrench on the pelvis toward the reference root. It is a
non-physical stand-in for balance control; it is forced to zero from the KO instant.
"""
import math

import mujoco
import numpy as np

from . import intensity as INT
from .consciousness import Consciousness
from .reference import POSES

REGIONS = ['neck', 'trunk', 'arm_L', 'arm_R', 'leg_L', 'leg_R']


class Controller:
    def __init__(self, m, spec, cfg, mass):
        self.m, self.cfg, self.mass = m, cfg, mass
        self.jn, self.qadr, self.dadr, self.reg, self.off, self.tmax = [], [], [], [], [], []
        for b in spec['bodies']:
            for j in b['joints']:
                jid = m.joint(j['name']).id
                self.jn.append(j['name'])
                self.qadr.append(m.jnt_qposadr[jid])
                self.dadr.append(m.jnt_dofadr[jid])
                self.reg.append(REGIONS.index(b['region']))
                self.off.append(j['offset'])
                self.tmax.append(j['torque'])
        self.qadr, self.dadr = np.array(self.qadr), np.array(self.dadr)
        self.reg, self.off, self.tmax = np.array(self.reg), np.array(self.off), np.array(self.tmax)
        self.idx = {n: i for i, n in enumerate(self.jn)}
        self.aid = np.array([m.actuator('a_' + n).id for n in self.jn])
        self.lo = m.jnt_range[[m.joint(n).id for n in self.jn], 0]
        self.hi = m.jnt_range[[m.joint(n).id for n in self.jn], 1]
        self.pelvis = m.body('pelvis').id
        self.grav_ff = np.array([not REGIONS[r].startswith('leg') for r in self.reg])
        self.t_ko = None
        self.q_hold = None
        self.events = {}                  # physical events seen by the sim: name -> time
        self.foot_w = np.ones(2)          # low-passed 0..1 'this foot is planted' weight
        self.rng = np.random.default_rng(cfg.get('seed', 0))
        self.tremor_phase = self.rng.uniform(0, 2 * np.pi, len(self.jn))
        # shaped-intensity state (only touched by phases/options that ask for it)
        self.dt = cfg.get('dt', 0.002)
        self.seed = cfg.get('seed', 0)
        self.event_data = {}              # event name -> {measured quantities}
        self._ph = {}                     # phase index -> sampled per-take parameters
        self._act = None
        self._tf = None
        self._wander = None
        self._qd_tgt = None
        self._trem_tau = None
        self._trem = {}
        self._zeta_r = None
        # consciousness: global level L(t) -> per-region authority (consciousness.py)
        self.cons = Consciousness(cfg.get('consciousness'), cfg.get('ko'), REGIONS)
        self.q_rel = None
        self._q_now = None
        self._qd_now = None
        self._auto = {}                   # phase index -> side picked for an '_auto' pose
        self._b = None                    # per-joint authority used to blend toward the command
        self.L = 1.0
        self.a_r = np.ones(len(REGIONS))

    # -- pose helpers ----------------------------------------------------------------------
    def pose_vec(self, pose, base=None):
        """anatomical degrees dict -> joint-coordinate radians, clipped to range."""
        q = np.zeros(len(self.jn)) if base is None else base.copy()
        for k, v in pose.items():
            if k in self.idx:
                i = self.idx[k]
                q[i] = np.radians(v - self.off[i])
        return np.clip(q, self.lo + 0.01, self.hi - 0.01)

    def rate_vec(self, rates):
        qd = np.zeros(len(self.jn))
        for k, v in rates.items():
            if k in self.idx:
                qd[self.idx[k]] = np.radians(v)
        return qd

    # -- gains -----------------------------------------------------------------------------
    def set_inertia(self, d):
        """Effective inertia each joint's PD gain is scaled by.

        1/diag(M^-1) (the old pipeline's rule) treats every other joint as free, so it sees
        only the lightest neighbouring link and gives gains far too soft to hold a posture
        (measured here: 30 N m of hip torque at 50 deg of error). Instead lock every other
        joint and take the reduced inertia of the two rigid halves the joint connects,
            I_free = Ia*Ib / (Ia + Ib),
        from the 7x7 block (floating root + this joint) of the mass matrix. A leg joint whose
        foot is planted has its distal half held by the ground, so it sees the proximal half
        alone: I_planted = Ia.
        """
        m = self.m
        Minv = np.zeros((m.nv, m.nv))
        mujoco.mj_solveM(m, d, Minv, np.eye(m.nv))
        M = np.linalg.inv(Minv)
        root = list(range(6))
        free = np.zeros(len(self.dadr))
        planted = np.zeros(len(self.dadr))
        for k, j in enumerate(self.dadr):
            idx = root + [int(j)]
            red = 1.0 / np.linalg.inv(M[np.ix_(idx, idx)])[6, 6]
            Ib = M[j, j]                              # distal subtree about the joint axis
            Ia = red * Ib / max(Ib - red, 1e-9)       # proximal half
            free[k] = red
            planted[k] = min(Ia, 40.0 * red) if REGIONS[self.reg[k]].startswith('leg') else red
        self.I_free, self.I_planted = free, planted

    def update_foot_load(self, load_L, load_R, dt):
        W = self.mass * 9.81
        tgt = np.clip(np.array([load_L, load_R]) / (0.2 * W), 0.0, 1.0)
        self.foot_w += (tgt - self.foot_w) * min(1.0, dt / 0.03)

    # -- tone ------------------------------------------------------------------------------
    def trigger_ko(self, t, q_cmd):
        """The KO strike landed: start the consciousness driver. t_ko is the onset of the drop."""
        if self.t_ko is not None:
            return
        self.t_ko = t
        self.q_hold = q_cmd.copy()
        self.q_rel = q_cmd.copy()
        self.cons.hit(t)

    def is_post(self, t):
        """Between the onset of the drop and full recovery (if the driver recovers)."""
        return self.t_ko is not None and t >= self.t_ko and not self.cons.recovered(t)

    def tone_and_target(self, t, q_ref):
        """-> (tone per joint, target per joint, tone per region)"""
        n = len(self.jn)
        if not self.is_post(t):
            self._b = None
            return np.ones(n), q_ref, np.ones(len(REGIONS))
        ko = self.cfg['ko']
        dt = t - self.t_ko
        res = np.array([ko['residual'][r.split('_')[0]] for r in REGIONS])
        cons = self.cons
        self.L = cons.level(t)
        self.a_r = cons.authority(self.L)
        tone_r = res + (1 - res) * self.a_r      # legacy strike: a_r == the old off_ramp ramp
        if cons.target_mode == 'hold':
            target = self.q_hold.copy()
            self._b = None
        else:
            if math.isfinite(cons.t_relax) and self._q_now is not None:
                self.q_rel = self.q_rel + (self._q_now - self.q_rel) * min(1.0, self.dt / cons.t_relax)
            b = self.a_r[self.reg]
            target = b * q_ref + (1 - b) * self.q_rel
            self._b = b
        for ip, ph in enumerate(ko.get('phases', [])):
            if INT.is_shaped(ph):
                self._shaped(ip, ph, t, dt, target, tone_r, res)
                continue
            if ph.get('after'):             # phase clocked from a physical event, not the KO
                if ph['after'] not in self.events:
                    continue
                a = t - self.events[ph['after']] - ph['t']
            else:
                a = dt - ph['t']
            if a < 0:
                continue
            rise, hold, fade = ph.get('rise', 0.1), ph.get('hold', 0.3), ph.get('fade', 0.3)
            env = (a / rise if a < rise else 1.0 if a < rise + hold
                   else max(0.0, 1 - (a - rise - hold) / fade))
            if env <= 0:
                continue
            regs = [REGIONS.index(r) for r in ph['regions']]
            w = min(1.0, a / rise)
            for r in regs:
                if ph.get('replace'):       # a later beat supersedes earlier ones (can lower tone)
                    tone_r[r] = (1 - w) * tone_r[r] + w * max(res[r], ph['tone'] * env)
                else:
                    tone_r[r] = max(tone_r[r], ph['tone'] * env)
            if ph.get('pose'):
                pv = self.pose_vec(POSES[self.auto_pose(ip, ph['pose'])], base=target)
                sel = np.isin(self.reg, regs)
                target[sel] = (1 - w) * target[sel] + w * pv[sel]
            for jn_, (a1, frac) in (ph.get('pose_rel') or {}).items():
                # relative pose: go `frac` of the way from wherever the target is to a1
                if jn_ in self.idx:
                    i_ = self.idx[jn_]
                    goal = np.clip(np.radians(a1 - self.off[i_]), self.lo[i_] + 0.01, self.hi[i_] - 0.01)
                    target[i_] += w * frac * (goal - target[i_])
        tone_r, target = self._post_filters(ko, t, tone_r, target, res)
        tone = tone_r[self.reg]
        tr = ko.get('tremor')
        self._trem_tau = None                      # torque tremor accumulates over entries
        for e in ([tr] if isinstance(tr, dict) else (tr or [])):
            if e.get('link'):
                target = self._linked_tremor(e, t, tone_r, res, target)
                continue
            t0 = self.events.get(e['after']) if e.get('after') else self.t_ko
            if t0 is None or t < t0:
                continue
            grow = min(1.0, (t - t0) / e.get('onset', 1.0))
            amp = np.radians(e['amp_deg']) * grow * np.sqrt(tone)
            if e.get('regions'):
                amp = amp * np.isin(self.reg, [REGIONS.index(r) for r in e['regions']])
            target = target + amp * np.sin(2 * np.pi * e['hz'] * t + self.tremor_phase)
        return tone, target, tone_r


    def auto_pose(self, ip, name, lead=0.15):
        """'<pose>_auto' -> '<pose>_R' or '<pose>_L', picked once when the phase starts, from the
        way the head is already turning: neck twist now plus `lead` s of its current rate
        (negative = toward her right -> _R). Owner 2026-11-17: the resting cheek follows the roll."""
        if not name.endswith('_auto'):
            return name
        if ip not in self._auto:
            tw = 0.0
            for k in ('neck_twist', 'head_twist'):
                if k in self.idx and self._q_now is not None:
                    i = self.idx[k]
                    tw += math.degrees(self._q_now[i]) + self.off[i]
                    if self._qd_now is not None:
                        tw += lead * math.degrees(self._qd_now[i])
            self._auto[ip] = 'R' if tw < 0 else 'L'
            self.event_data['auto_side_phase%d' % ip] = {'side': self._auto[ip], 'twist_deg': round(tw, 1)}
        return name[:-len('auto')] + self._auto[ip]

    # -- shaped intensity (see intensity.py) ------------------------------------------------
    def resolve_pose(self, spec):
        """pose spec -> anatomical-degree dict. Mixed postures: weighted blends, per-region
        sources, or a base posture with features picked from others."""
        if isinstance(spec, str):
            if spec.startswith('@'):              # named set from controller.ko.pose_sets
                return self.resolve_pose(self.cfg['ko']['pose_sets'][spec[1:]])
            return dict(POSES[spec])
        if isinstance(spec, list):
            acc, ws = {}, {}
            for name, w in spec:
                for k, v in self.resolve_pose(name).items():
                    acc[k] = acc.get(k, 0.0) + w * v
                    ws[k] = ws.get(k, 0.0) + w
            return {k: acc[k] / ws[k] for k in acc}
        if 'by_region' in spec:
            out = {}
            for rname, sub in spec['by_region'].items():
                rset = {'arms': ('arm_L', 'arm_R'), 'legs': ('leg_L', 'leg_R'),
                        'axial': ('trunk', 'neck')}.get(rname, (rname,))
                for k, v in self.resolve_pose(sub).items():
                    if k in self.idx and REGIONS[self.reg[self.idx[k]]] in rset:
                        out[k] = v
            return out
        out = self.resolve_pose(spec['base']) if spec.get('base') else {}
        for pk in spec.get('pick', []):
            src = self.resolve_pose(pk['from'])
            for j in pk['joints']:
                if j in src:
                    out[j] = src[j]
        for j, f in (spec.get('scale') or {}).items():
            if j in out:
                out[j] = out[j] * f
        return out

    def _phase_clock(self, ip, ph, t):
        """Phase start time, latched once resolved. `after` may be one event or a list (the
        first that happens); `fallback: {after, t}` starts it anyway if none has happened by
        then (e.g. no head bounce in this take)."""
        clk = getattr(self, '_clk', None)
        if clk is None:
            clk = self._clk = {}
        if ip in clk:
            return clk[ip]
        aft = ph.get('after')
        if not aft:
            clk[ip] = self.t_ko + ph.get('t', 0.0)
            return clk[ip]
        evs = [aft] if isinstance(aft, str) else list(aft)
        seen = [self.events[e] for e in evs if e in self.events]
        if seen:
            clk[ip] = min(seen) + ph.get('t', 0.0)
            return clk[ip]
        fb = ph.get('fallback')
        if fb and fb['after'] in self.events and t >= self.events[fb['after']] + fb.get('t', 0.0):
            clk[ip] = self.events[fb['after']] + fb.get('t', 0.0)
            return clk[ip]
        return None

    def _sample_phase(self, ip, ph):
        rng = np.random.default_rng([int(self.seed), 1000 + ip])
        j = float(ph.get('jitter', 0.0))
        P = {'onset': max(-ph.get('t', 0.0), 0.1 * j * rng.standard_normal()),
             'peak': ph['tone'] * max(0.3, 1 + j * rng.standard_normal()),
             'hold': ph.get('hold', 0.3) * max(0.3, 1 + j * rng.standard_normal()),
             'fade': ph.get('fade', 0.3) * max(0.3, 1 + j * rng.standard_normal()),
             'rise': ph.get('rise', 0.1)}
        scale = 1.0
        sb = ph.get('scale_by')
        if sb and sb['event'] in self.event_data and sb['key'] in self.event_data[sb['event']]:
            scale = INT.interp_map(self.event_data[sb['event']][sb['key']], sb['map'])
        P['scale'] = scale
        shape, sp = ph.get('shape', 'trapezoid'), dict(ph.get('shape_params') or {})
        if ph.get('shape_set'):                       # named set from controller.ko.shape_sets
            ss = self.cfg['ko']['shape_sets'][ph['shape_set']]
            shape, sp = ss['shape'], dict(ss.get('shape_params') or {})
        for cond in ph.get('shape_if', []):
            ed = self.event_data.get(cond['event'], {})
            if cond['key'] in ed and ed[cond['key']] > cond['gt']:
                shape, sp = cond['shape'], dict(cond.get('shape_params') or {})
                break
        if shape in ('ratchet', 'ratchet_pulse'):
            steps, sdt = sp.get('steps', 4), sp.get('step_dt', 0.22)
            gaps = sdt * np.clip(1 + 0.3 * rng.standard_normal(steps), 0.5, 1.6)
            sp['_times'] = np.concatenate([[0.0], np.cumsum(gaps[:-1])]).tolist()
            sz = np.clip(1 + 0.35 * rng.standard_normal(steps), 0.4, 1.8)
            sp['_sizes'] = (sz / sz.sum()).tolist()
        P['shape'], P['sp'] = shape, sp
        dp = ph.get('depth', 1.0)
        if isinstance(dp, dict):
            P['d0'], P['d1'], P['tau'] = dp.get('start', 0.0), dp.get('end', 1.0), dp.get('tau', 0.4)
        else:
            P['d0'], P['d1'], P['tau'] = 0.0, float(dp), sp.get('tau', 0.5) * 1.2
        pose = self.resolve_pose(self.auto_pose(ip, ph['pose']) if isinstance(ph.get('pose'), str)
                                 else ph['pose']) if ph.get('pose') else {}
        P['pose'] = pose
        n = len(self.jn)
        s_j, jit = np.ones(n), np.zeros(n)
        inpose = np.zeros(n, bool)
        for k in pose:
            if k in self.idx:
                inpose[self.idx[k]] = True
        v = ph.get('variety')
        if v and pose:
            nominal = np.abs(self.pose_vec(pose) - self.pose_vec({}))
            lo, hi = v.get('depth', [0.6, 1.1])
            for r in set(self.reg.tolist()):
                sel = (self.reg == r) & inpose
                if not sel.any():
                    continue
                d_r = rng.uniform(lo, hi)
                mx = nominal[sel].max() if nominal[sel].max() > 0 else 1.0
                for i_ in np.where(sel)[0]:
                    key = nominal[i_] >= v.get('key_frac', 0.5) * mx
                    sj = d_r * (1 + v.get('spread', 0.12) * rng.standard_normal())
                    s_j[i_] = max(sj, v.get('keep_key', 0.7)) if key else max(sj, 0.0)
                    sd = v.get('jitter_key_deg', 3.0) if key else v.get('jitter_minor_deg', 9.0)
                    jit[i_] = np.radians(sd * rng.standard_normal())
        P['s_j'], P['jit'], P['inpose'] = s_j, jit, inpose
        P['regs'] = [REGIONS.index(r) for r in ph['regions']]
        P['stagger'] = {REGIONS.index(k): v_ for k, v_ in (ph.get('stagger') or {}).items()}
        P['gain'] = {REGIONS.index(k): v_ for k, v_ in (ph.get('gain') or {}).items()}
        return P

    def _shaped(self, ip, ph, t, dt, target, tone_r, res):
        t0 = self._phase_clock(ip, ph, t)
        if t0 is None or t < t0 + min(0.0, ph.get('t', 0.0)):
            return
        if ip not in self._ph:
            self._ph[ip] = self._sample_phase(ip, ph)
        P = self._ph[ip]
        for r in P['regs']:
            a = t - t0 - P['onset'] - P['stagger'].get(r, 0.0)
            if a < 0:
                continue
            g = P['gain'].get(r, 1.0) * P['scale']
            env = INT.tone_env(P['shape'], a, P['rise'], P['hold'], P['fade'], P['sp'])
            if 'zeta' in ph and env > 0:          # lighter damping: an elastic, springy region
                if self._zeta_r is None:
                    self._zeta_r = np.full(len(REGIONS), np.nan)
                zr = self.cfg.get('zeta', 1.0)
                self._zeta_r[r] = zr + (ph['zeta'] - zr) * min(1.0, env)
            if env > 0:
                if ph.get('replace'):
                    wr = min(1.0, a / P['rise'])
                    tone_r[r] = (1 - wr) * tone_r[r] + wr * max(res[r], P['peak'] * g * env)
                else:
                    tone_r[r] = max(tone_r[r], P['peak'] * g * env)
            if not P['pose']:
                continue
            # the posture is latched after the fade: tone drains, the target stays put
            w = INT.depth_curve(P['shape'], a, P['rise'], P['hold'], P['fade'], P['sp'],
                                P['d0'], P['d1'], P['tau']) * P['gain'].get(r, 1.0) * min(P['scale'], 1.3)
            sel = (self.reg == r)
            pv = self.pose_vec(P['pose'], base=target)
            new = target + P['s_j'] * (pv - target) + P['jit'] * P['inpose']
            target[sel] = target[sel] + w * (new[sel] - target[sel])
            np.clip(target, self.lo + 0.01, self.hi - 0.01, out=target)

    def _post_filters(self, ko, t, tone_r, target, res):
        """Optional: tone wander, muscle-activation smoothing, target trajectory filter."""
        dt = self.dt
        tw = ko.get('tone_wander')
        if tw:
            if self._wander is None:
                self._wander = INT.OU(len(REGIONS), tw.get('tau', 0.6),
                                      np.random.default_rng([int(self.seed), 77]))
            tone_r = np.maximum(tone_r * (1 + tw.get('sigma', 0.12) * self._wander(dt)), 0.5 * res)
        ac = ko.get('activation')
        if ac:
            if self._act is None:
                self._act = INT.Activation(len(REGIONS), ac.get('tau_up', 0.035), ac.get('tau_down', 0.07))
            tone_r = self._act(tone_r, dt).copy()
        tf = ko.get('target_filter')
        if tf:
            if self._tf is None:
                self._tf = INT.TargetFilter(tf.get('hz', 6.0), tf.get('zeta', 1.0))
            q, v = self._tf(target, dt)
            target, self._qd_tgt = q.copy(), v.copy()
        return tone_r, target

    def _linked_tremor(self, e, t, tone_r, res, target):
        """Tremor driven by intensity: amplitude follows drive above residual and grows faster
        once drive passes full tone (straining past max); frequency drifts from hz_hi at peak
        to hz_lo as it fades. mode: target (servo-filtered) or torque (bypasses the servo)."""
        t0 = self.events.get(e['after']) if e.get('after') else self.t_ko
        key = id(e)
        if t0 is None or t < t0:
            return target
        st = self._trem.get(key)
        n = len(self.jn)
        if st is None:
            rng = np.random.default_rng([int(self.seed), 555])
            st = {'ph': rng.uniform(0, 2 * np.pi, n), 'fj': 1 + 0.08 * rng.standard_normal(n),
                  'ou': INT.OU(n, e.get('wander_tau', 0.4), rng)}
            self._trem[key] = st
        I = np.clip((tone_r - res) / np.maximum(1 - res, 1e-3), 0, None)[self.reg]
        if e.get('regions'):
            I = I * np.isin(self.reg, [REGIONS.index(r) for r in e['regions']])
        lo, hi = e.get('hz_lo', 5.0), e.get('hz_hi', 8.0)
        f = (lo + (hi - lo) * np.clip(I, 0, 1)) * st['fj']
        st['ph'] = st['ph'] + 2 * np.pi * f * self.dt
        over = e.get('over_gain', 2.5)
        gI = np.where(I <= 1, I ** 0.8, 1 + over * (I - 1))
        grow = min(1.0, (t - t0) / e.get('onset', 0.3))
        mod = 1 + 0.3 * st['ou'](self.dt)
        s = np.sin(st['ph']) * gI * grow * mod
        if e.get('mode') == 'torque':
            tau_ = e.get('amp_frac', 0.04) * self.tmax * s
            self._trem_tau = tau_ if self._trem_tau is None else self._trem_tau + tau_
            return target
        return target + np.radians(e.get('amp_deg', 2.0)) * s

    # -- per step --------------------------------------------------------------------------
    def apply(self, d, t, q_ref, qd_ref, breath=0.0):
        c = self.cfg
        self._q_now = d.qpos[self.qadr]
        self._qd_now = d.qvel[self.dadr]
        tone, target, tone_r = self.tone_and_target(t, q_ref)
        if self.t_ko is not None:
            self.cons.update_events(t, self.cons.level(t), self.events, self.event_data)
        if 'chest_flex' in self.idx:
            target = target.copy()
            target[self.idx['chest_flex']] += breath
        post = self.is_post(t)
        # A leg whose foot still carries load is a closed chain: its effective inertia is the
        # body above it, not the free limb. Blend by measured foot load so a leg with tone can
        # really hold her up after the KO, and goes soft the moment the foot unloads.
        I = self.I_planted.copy()
        if post:
            I = self.I_free.copy()
            for side, w in (('L', self.foot_w[0]), ('R', self.foot_w[1])):
                sel = self.reg == REGIONS.index('leg_' + side)
                I[sel] = w * self.I_planted[sel] + (1 - w) * self.I_free[sel]
        w = 2 * np.pi * c.get('track_hz', 3.0)
        kp = tone * I * w * w
        zeta = c.get('zeta', 1.0)
        if self._zeta_r is not None:
            zj = self._zeta_r[self.reg]
            zeta = np.where(np.isnan(zj), zeta, zj)
            self._zeta_r[:] = np.nan                 # re-asserted by its phase every step
        kv = 2 * zeta * np.sqrt(tone) * I * w
        m = self.m
        m.actuator_gainprm[self.aid, 0] = kp
        m.actuator_biasprm[self.aid, 1] = -kp
        m.actuator_biasprm[self.aid, 2] = -kv
        cap = np.maximum(tone, 1e-3) * self.tmax
        m.actuator_forcerange[self.aid, 0] = -cap
        m.actuator_forcerange[self.aid, 1] = cap
        qd = (self._qd_tgt if self._qd_tgt is not None else np.zeros_like(target)) if post else qd_ref
        if post and self._b is not None:              # following the command with authority b
            qd = qd + self._b * qd_ref
        if post and self._trem_tau is not None:
            d.qfrc_applied[self.dadr] += self._trem_tau
        # postural tone: muscles carry the weight of what hangs off each joint. Exact for the
        # trunk, neck and arms (segments distal to the joint); legs carry load through ground
        # contact instead, which the stiff planted-inertia PD handles. Scales with tone, so it
        # drains away with the KO like everything else.
        ff = np.where(self.grav_ff, tone * d.qfrc_bias[self.dadr], 0.0)
        d.ctrl[self.aid] = target + (kv * qd + ff) / np.maximum(kp, 1e-9)
        return tone_r

    def root_assist(self, d, t, p_ref, v_ref, cap_frac):
        """Horizontal force + upright torque on the pelvis, capped. Returns the wrench applied."""
        m = self.m
        d.xfrc_applied[self.pelvis] = 0
        if cap_frac <= 0:
            return np.zeros(6)
        if self.is_post(t):
            if self.cons.assist_mode == 'cut':
                return np.zeros(6)
            cap_frac = cap_frac * self.cons.level(t)   # balance comes back with consciousness
            if cap_frac <= 0:
                return np.zeros(6)
        W = self.mass * 9.81
        wn = 2 * np.pi * 1.5
        p = d.xpos[self.pelvis]
        v = d.qvel[:3]                      # free-joint linear velocity is world-frame
        F = self.mass * (wn * wn * (p_ref - p) + 2 * wn * (v_ref - v))
        F[2] = 0.0
        n = np.linalg.norm(F)
        if n > cap_frac * W:
            F *= cap_frac * W / n
        # keep the pelvis from pitching/rolling/yawing away (small-angle PD on its rotation)
        R = d.xmat[self.pelvis].reshape(3, 3)
        rv = 0.5 * np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
        Ip = 0.1 * self.mass
        T = -Ip * (wn * wn * rv + 2 * wn * (R @ d.qvel[3:6]))
        tcap = cap_frac * W * 0.3
        tn = np.linalg.norm(T)
        if tn > tcap:
            T *= tcap / tn
        d.xfrc_applied[self.pelvis, :3] = F
        d.xfrc_applied[self.pelvis, 3:] = T
        return np.concatenate([F, T])
