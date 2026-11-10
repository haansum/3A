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
import mujoco
import numpy as np

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
        self.t_ko = t
        self.q_hold = q_cmd.copy()

    def tone_and_target(self, t, q_ref):
        """-> (tone per joint, target per joint, tone per region)"""
        n = len(self.jn)
        if self.t_ko is None or t < self.t_ko:
            return np.ones(n), q_ref, np.ones(len(REGIONS))
        ko = self.cfg['ko']
        dt = t - self.t_ko
        res = np.array([ko['residual'][r.split('_')[0]] for r in REGIONS])
        ramp = max(0.0, 1.0 - dt / ko.get('off_ramp', 0.04))
        tone_r = res + (1 - res) * ramp
        target = self.q_hold.copy()
        for ph in ko.get('phases', []):
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
            for r in regs:
                tone_r[r] = max(tone_r[r], ph['tone'] * env)
            if ph.get('pose'):
                pv = self.pose_vec(POSES[ph['pose']], base=target)
                sel = np.isin(self.reg, regs)
                w = min(1.0, a / rise)
                target[sel] = (1 - w) * target[sel] + w * pv[sel]
        tone = tone_r[self.reg]
        tr = ko.get('tremor')
        for e in ([tr] if isinstance(tr, dict) else (tr or [])):
            t0 = self.events.get(e['after']) if e.get('after') else self.t_ko
            if t0 is None or t < t0:
                continue
            grow = min(1.0, (t - t0) / e.get('onset', 1.0))
            amp = np.radians(e['amp_deg']) * grow * np.sqrt(tone)
            if e.get('regions'):
                amp = amp * np.isin(self.reg, [REGIONS.index(r) for r in e['regions']])
            target = target + amp * np.sin(2 * np.pi * e['hz'] * t + self.tremor_phase)
        return tone, target, tone_r

    # -- per step --------------------------------------------------------------------------
    def apply(self, d, t, q_ref, qd_ref, breath=0.0):
        c = self.cfg
        tone, target, tone_r = self.tone_and_target(t, q_ref)
        if 'chest_flex' in self.idx:
            target = target.copy()
            target[self.idx['chest_flex']] += breath
        post = self.t_ko is not None and t >= self.t_ko
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
        kv = 2 * c.get('zeta', 1.0) * np.sqrt(tone) * I * w
        m = self.m
        m.actuator_gainprm[self.aid, 0] = kp
        m.actuator_biasprm[self.aid, 1] = -kp
        m.actuator_biasprm[self.aid, 2] = -kv
        cap = np.maximum(tone, 1e-3) * self.tmax
        m.actuator_forcerange[self.aid, 0] = -cap
        m.actuator_forcerange[self.aid, 1] = cap
        qd = np.zeros_like(target) if post else qd_ref
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
        if cap_frac <= 0 or (self.t_ko is not None and t >= self.t_ko):
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
