"""Two-body scaffold for holds (handoff track G2): an unseen torso anchor and two arms behind her.

Owner 2026-11-16: first choke is a rear-naked choke, both seated; only his arms are rendered.

Every attacker piece (torso anchor, upper arm, forearm, hand per side) is a free body welded
to a kinematic target (a mocap body) through a SOFT weld, so the arms give under her weight
and her hands can move them a little; nothing about him is a controller. Targets are authored
as points in her neck frame, taken once when the hold starts (C = midway between her neck and
head origins, f = her facing, l = her left, u = up), so no inverse kinematics is needed. The
frame is then fixed in the world: he sits behind her and does not follow her.

Phases (seconds, all authored, tuned by eye):
  loose    arms around her, not tight                 t < close_at
  close    loose -> locked                            close_at .. close_at + close_s
  squeeze  locked, the elbow and grip draw in by `squeeze_m` over `squeeze_s`
  open     `release_after` s after she goes out: the arms open, the elbow comes off the neck
  away     then every target withdraws back and up out of frame; the torso anchor backs off
  (standing: `lower_m` lowers her over `lower_s` before the open; then `tip_back_deg`
  swings the hold back and down about her hips over `tip_s`, so she goes over backward)

The squeeze score is an animation signal, not physiology: the normal contact force from his
arms on her neck and head, split by side in her neck frame, score = 2 * min(left, right) / her
weight. Nothing here is calibrated to real force or pressure values.
"""
import numpy as np

SEGS = ('torso', 'upper_arm_R', 'forearm_R', 'hand_R', 'upper_arm_L', 'forearm_L', 'hand_L')
RADIUS = {'torso': 0.11, 'upper_arm_R': 0.042, 'forearm_R': 0.035, 'hand_R': 0.034,
          'upper_arm_L': 0.042, 'forearm_L': 0.035, 'hand_L': 0.034}      # Mosin's arms, measured by eye
MASS = {'torso': 20.0, 'upper_arm_R': 1.6, 'forearm_R': 0.9, 'hand_R': 0.3,
        'upper_arm_L': 1.6, 'forearm_L': 0.9, 'hand_L': 0.3}

# segment end points in her neck frame (f, l, u) metres. His right arm chokes: biceps along the
# right side of her neck, elbow in front of her throat, forearm back along the left side, right
# hand on his left biceps; his left forearm folds up behind her head. Eyeballed.
LOCKED = {
    # sized to Mosin's arms (owner 2026-11-18: "the arms come from mosin"): upper arm 0.20 m,
    # forearm 0.20 m, shoulders tucked in close behind her (petite arms have to reach round)
    'torso': ((-0.27, 0.0, -0.30), (-0.24, 0.0, -0.04)),
    'upper_arm_R': ((-0.12, -0.10, -0.05), (0.06, -0.01, -0.035)),
    'forearm_R': ((0.06, -0.01, -0.035), (-0.08, 0.13, -0.04)),
    'hand_R': ((-0.08, 0.13, -0.04), (-0.06, 0.165, -0.06)),
    'upper_arm_L': ((-0.12, 0.10, -0.05), (0.04, 0.20, -0.08)),
    'forearm_L': ((0.04, 0.20, -0.08), (-0.09, 0.08, 0.04)),
    'hand_L': ((-0.09, 0.08, 0.04), (-0.11, 0.04, 0.09)),
}
# loose: the same shape with the elbow lower and further out, grip not yet closed
LOOSE_SHIFT = {'upper_arm_R': ((0, 0, 0), (0.05, -0.03, -0.06)), 'forearm_R': ((0.05, -0.03, -0.06), (0.0, 0.05, -0.08)),
               'hand_R': ((0.0, 0.05, -0.08), (0.0, 0.05, -0.08)), 'forearm_L': ((0, 0, 0), (0.0, 0.04, -0.08)),
               'hand_L': ((0.0, 0.04, -0.08), (0.0, 0.04, -0.08))}
# squeeze: elbow draws back into the throat, the grip side draws in
SQUEEZE_DIR = {'upper_arm_R': ((0, 0, 0), (-1.0, 0.0, 0.0)), 'forearm_R': ((-1.0, 0.0, 0.0), (0.0, -0.6, 0.0)),
               'hand_R': ((0.0, -0.6, 0.0), (0.0, -0.6, 0.0)), 'forearm_L': ((0, 0, 0), (0.6, 0.0, 0.0)),
               'hand_L': ((0.6, 0.0, 0.0), (0.6, 0.0, 0.0))}
# open, two stages (shifts from LOCKED, frame coords). Stage 1: his right elbow swings out to her
# right, his right hand slides forward along her left jaw, his left hand comes out from behind
# her head to her left. Stage 2: the right hand comes round in front to her right side. Each
# arm ends clear of her on its own side, so the withdrawal never drags through her.
OPEN1 = {'upper_arm_R': ((0, -0.03, 0), (0.05, -0.20, -0.06)), 'forearm_R': ((0.05, -0.20, -0.06), (0.22, -0.02, -0.06)),
         'hand_R': ((0.22, -0.02, -0.06), (0.22, -0.02, -0.06)), 'upper_arm_L': ((0, 0.04, 0), (-0.02, 0.10, -0.04)),
         'forearm_L': ((-0.02, 0.10, -0.04), (-0.04, 0.26, -0.08)), 'hand_L': ((-0.04, 0.26, -0.08), (-0.04, 0.26, -0.08))}
OPEN2 = {'upper_arm_R': ((0, -0.06, 0), (0.05, -0.28, -0.10)), 'forearm_R': ((0.05, -0.28, -0.10), (0.25, -0.40, -0.12)),
         'hand_R': ((0.25, -0.40, -0.12), (0.25, -0.40, -0.12)), 'upper_arm_L': ((0, 0.06, 0), (-0.02, 0.16, -0.08)),
         'forearm_L': ((-0.02, 0.16, -0.08), (-0.04, 0.32, -0.12)), 'hand_L': ((-0.04, 0.32, -0.12), (-0.04, 0.32, -0.12))}
AWAY = np.array([-1.1, 0.0, 0.9])          # whole attacker withdraws back and up (frame units)
AWAY_SIDE = 0.12                             # ...and each arm further out to its own side


def _smooth(u):
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def _quat_axes(x, z):
    """quaternion (w, x, y, z) of the frame with local x ~ x and local z = z"""
    z = np.asarray(z, float) / np.linalg.norm(z)
    x = np.asarray(x, float) - (np.asarray(x, float) @ z) * z
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    R = np.stack([x, y, z], 1)
    w = np.sqrt(max(1e-12, 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2
    return np.array([w, (R[2, 1] - R[1, 2]) / (4 * w), (R[0, 2] - R[2, 0]) / (4 * w), (R[1, 0] - R[0, 1]) / (4 * w)])


def _quat_z_to(v):
    """quaternion (w, x, y, z) rotating +z onto v"""
    v = np.asarray(v, float)
    v = v / np.linalg.norm(v)
    z = np.array([0.0, 0.0, 1.0])
    c = float(z @ v)
    if c < -0.999999:
        return np.array([0.0, 1.0, 0.0, 0.0])
    ax = np.cross(z, v)
    q = np.array([1.0 + c, *ax])
    return q / np.linalg.norm(q)


class Grapple:
    def __init__(self, cfg):
        self.cfg = dict(cfg)
        self.locked = self._fit_lengths(LOCKED, self.cfg.get('upper_m'), self.cfg.get('forearm_m'))
        self.on = False
        self.frame = None                 # (C, f, l, u) once the hold starts
        self.t_out = None
        self.log = {'seg': [], 'force_L': [], 'force_R': [], 'score': [], 'phase': []}

    @staticmethod
    def _fit_lengths(base, upper, forearm):
        """Resize the authored hold to the attacker's arms (2026-11-18): the wrap round her neck
        (elbows) stays where it is; each shoulder moves back along its upper arm and each wrist
        and hand moves along the forearm, and the torso anchor moves back with the shoulders."""
        L = {k: tuple(np.array(p, float) for p in v) for k, v in base.items()}
        if not upper and not forearm:
            return {k: tuple(tuple(p) for p in v) for k, v in L.items()}
        shift = []
        for sd in ('R', 'L'):
            sh, el = L['upper_arm_' + sd]
            if upper:
                d = (sh - el) / np.linalg.norm(sh - el)
                sh2 = el + d * upper
                shift.append(sh2 - sh)
                L['upper_arm_' + sd] = (sh2, el)
            el, wr = L['forearm_' + sd]
            if forearm:
                d = (wr - el) / np.linalg.norm(wr - el)
                wr2 = el + d * forearm
                h0, h1 = L['hand_' + sd]
                L['forearm_' + sd] = (el, wr2)
                L['hand_' + sd] = (wr2, h1 + (wr2 - wr))
        if shift:
            m = np.mean(shift, 0)
            L['torso'] = tuple(p + np.array([m[0], 0.0, m[2]]) for p in L['torso'])
        return {k: tuple(tuple(float(x) for x in p) for p in v) for k, v in L.items()}

    # -- model ------------------------------------------------------------------------------
    def mjcf(self):
        """-> (worldbody xml, equality xml). Placed far behind her until the hold is set up."""
        sr = self.cfg.get('weld_solref', '0.04 1')
        bodies, eqs = [], []
        for i, s in enumerate(SEGS):
            p = f'0 {8 + i} 1'
            if s == 'torso':
                g = (f'<geom name="atk_{s}" type="box" size="0.17 {RADIUS[s]} 0.16" mass="{MASS[s]}" '
                     f'contype="8" conaffinity="1" friction="0.9" rgba=".2 .2 .25 1"/>')
            elif s.startswith('hand'):
                g = (f'<geom name="atk_{s}" type="sphere" size="{RADIUS[s]}" mass="{MASS[s]}" '
                     f'contype="8" conaffinity="1" friction="1.0" rgba=".8 .6 .5 1"/>')
            else:
                g = (f'<geom name="atk_{s}" type="capsule" fromto="0 0 -0.5 0 0 0.5" size="{RADIUS[s]}" '
                     f'mass="{MASS[s]}" contype="8" conaffinity="1" friction="1.0" rgba=".15 .15 .18 1"/>')
            # capsule length is set at start(): geom_size / fromto rescaled there
            bodies.append(f'<body name="atk_{s}" pos="{p}"><freejoint name="atk_{s}_free"/>{g}</body>')
            bodies.append(f'<body name="atk_{s}_tgt" mocap="true" pos="{p}"/>')
            eqs.append(f'<weld name="atk_{s}_weld" body1="atk_{s}" body2="atk_{s}_tgt" '
                       f'relpose="0 0 0 1 0 0 0" solref="{sr}" solimp="0.9 0.95 0.001"/>')
        return ''.join(bodies), ''.join(eqs)

    def bind(self, m):
        import mujoco
        self.m = m
        self.bid = {s: m.body('atk_' + s).id for s in SEGS}
        self.mid = {s: m.body_mocapid[m.body('atk_' + s + '_tgt').id] for s in SEGS}
        self.gid = {s: m.geom('atk_' + s).id for s in SEGS}
        self.qadr = {s: m.jnt_qposadr[m.joint('atk_' + s + '_free').id] for s in SEGS}
        self.dadr = {s: m.jnt_dofadr[m.joint('atk_' + s + '_free').id] for s in SEGS}
        self.her_neck = {m.geom('g_neck').id, m.geom('g_head').id}
        self.eq = {s_: m.equality('atk_' + s_ + '_weld').id for s_ in SEGS}
        self.eq_ref0 = {s_: m.eq_solref[self.eq[s_]].copy() for s_ in SEGS}
        self.neck_b, self.head_b, self.pelvis_b = m.body('neck').id, m.body('head').id, m.body('pelvis').id
        self._mj = mujoco

    # -- geometry ---------------------------------------------------------------------------
    def _frame_now(self, d):
        C = 0.5 * (d.xpos[self.neck_b] + d.xpos[self.head_b])
        f = d.xmat[self.pelvis_b].reshape(3, 3) @ np.array([0.0, -1.0, 0.0])
        f[2] = 0.0
        f /= np.linalg.norm(f)
        u = np.array([0.0, 0.0, 1.0])
        l = np.cross(u, f)
        return C, f, l, u

    def _w(self, p):
        C, f, l, u = self.frame
        p = np.asarray(p, float)
        return C + p[0] * f + p[1] * l + p[2] * u

    def _ends(self, s, t):
        """segment end points (frame coords) at time t, by phase"""
        c = self.cfg
        a, b = (np.array(x, float) for x in self.locked[s])
        ls = LOOSE_SHIFT.get(s, ((0, 0, 0), (0, 0, 0)))
        sq = SQUEEZE_DIR.get(s, ((0, 0, 0), (0, 0, 0)))
        o1 = OPEN1.get(s, ((0, 0, 0), (0, 0, 0)))
        o2 = OPEN2.get(s, ((0, 0, 0), (0, 0, 0)))
        t_close, close_s = c.get('close_at', 0.3), c.get('close_s', 0.7)
        w_loose = 1.0 - _smooth((t - t_close) / close_s)
        w_sq = c.get('squeeze_m', 0.03) * _smooth((t - t_close - close_s) / c.get('squeeze_s', 2.5))
        if c.get('squeeze_changes'):         # [[t0, metres, ramp]]: retune the squeeze from t0 on
            from .intensity import timed
            w_sq = timed(c['squeeze_changes'], t, w_sq)
        w1 = w2 = w_away = w_low = w_tip = w_pull = 0.0
        if self.t_out is not None:
            t_rel = self.t_out + c.get('release_after', 2.5)
            # standing holds (2026-11-18): he lowers her first (lower_m over lower_s) and only
            # then opens his arms, so she ends sitting against him instead of dropping in a heap
            lower_m, lower_s = c.get('lower_m', 0.0), c.get('lower_s', 1.2)
            w_low = _smooth((t - t_rel) / lower_s) if lower_m else 0.0
            t_tip = t_rel + (lower_s if lower_m else 0.0)
            tip_s = c.get('tip_s', 1.0) if c.get('tip_back_deg') else 0.0
            w_tip = _smooth((t - t_tip) / tip_s) if tip_s else 0.0
            # pull back (owner 2026-11-24: "the arms do not drop with her, they move back and
            # release"): the hold draws straight back at its height by pull_back_m over pull_s,
            # then opens; her knees go as he lets go and she falls back away from his arms
            pull_s = c.get('pull_s', 0.7) if c.get('pull_back_m') else 0.0
            w_pull = _smooth((t - t_tip - tip_s) / pull_s) if pull_s else 0.0
            t_open, os_ = t_tip + tip_s + pull_s, c.get('open_s', 0.6)
            w1 = _smooth((t - t_open) / os_)
            w2 = _smooth((t - t_open - os_) / os_)
            w_away = _smooth((t - t_open - 2 * os_) / c.get('away_s', 1.2))
            w_sq *= 1.0 - w1
        ends = []
        for k, p in enumerate((a, b)):
            q = p + w_loose * np.array(ls[k]) + w_sq * np.array(sq[k])
            q = q + (1 - w2) * w1 * np.array(o1[k]) + w2 * np.array(o2[k])
            side = 0.0 if s == 'torso' else (-1.0 if s.endswith('_R') else 1.0)
            if s == 'torso' and self.t_out is not None and c.get('torso_delay'):
                # his body stays behind her a little longer, so she sits back into it as her
                # knees go instead of pitching forward when the arms open (2026-11-18)
                w_away = _smooth((t - t_open - 2 * os_ - c['torso_delay']) / c.get('away_s', 1.2))
            q = q + w_away * (AWAY * (1.6 if s != 'torso' else 1.0) + np.array([0.0, side * AWAY_SIDE, 0.0]))
            # lift (standing variant, toes off the canvas): the whole hold rises by lift_m once
            # locked, and comes back down as it opens
            lift = c.get('lift_m', 0.0)
            if lift:
                w_lift = _smooth((t - t_close - close_s) / c.get('lift_s', 1.2)) * (1.0 - w1)
                q = q + np.array([0.0, 0.0, lift * w_lift])
            if self.t_out is not None and c.get('lower_m'):
                q = q + np.array([0.0, 0.0, -c['lower_m'] * w_low])
            if self.t_out is not None and c.get('tip_back_deg'):
                # backward fall (owner 2026-11-24: "drop slightly behind her, so she falls
                # backward"): once she has sat down, the hold swings back and down on an arc of
                # radius tip_r about her hips (her trunk reclines tip_back_deg), then opens, so she
                # goes down onto her back. Pulling back while she was still on her feet only dragged
                # her whole body back and she still folded forward (probe 2026-11-24).
                th = np.radians(c['tip_back_deg']) * w_tip
                r = c.get('tip_r', 0.55)
                q = q + np.array([-r * np.sin(th), 0.0, -r * (1.0 - np.cos(th))])
            if c.get('pull_back_m'):
                q = q + np.array([-c['pull_back_m'] * w_pull, 0.0, 0.0])
            ends.append(q)
        return ends

    def _set_target(self, d, s, t, snap=False):
        a, b = (self._w(p) for p in self._ends(s, t))
        mid, quat = 0.5 * (a + b), _quat_z_to(b - a)
        if s == 'torso':                       # box: width along her left-right axis
            quat = _quat_axes(self.frame[2], b - a)
        d.mocap_pos[self.mid[s]] = mid
        d.mocap_quat[self.mid[s]] = quat
        if snap:
            d.qpos[self.qadr[s]:self.qadr[s] + 3] = mid
            d.qpos[self.qadr[s] + 3:self.qadr[s] + 7] = quat
            d.qvel[self.dadr[s]:self.dadr[s] + 6] = 0.0
        return a, b

    def start(self, m, d, t=0.0):
        """take her neck frame now, size the segments, snap everything to the loose targets"""
        self.frame = self._frame_now(d)
        for s in SEGS:
            a, b = (self._w(p) for p in self.locked[s])
            half = max(0.5 * np.linalg.norm(b - a), 0.02)
            g = self.gid[s]
            if s == 'torso':
                pass
            elif s.startswith('hand'):
                m.geom_size[g, 0] = RADIUS[s]
            else:
                m.geom_size[g, 1] = max(half - RADIUS[s] * 0.5, 0.01)    # capsule half length
            self._set_target(d, s, t, snap=True)
        self.on = True

    # -- per step ---------------------------------------------------------------------------
    def step(self, d, t, events):
        if not self.on:
            return
        if self.t_out is None and 'out' in events:
            self.t_out = events['out']
        if self.t_out is not None and 'release' not in events and t >= self.t_out + self.cfg.get('release_after', 2.5):
            events['release'] = t
        c = self.cfg
        if self.t_out is not None and c.get('release_soft', 0.0):
            # once his arms start to open they go loose (weld time constant -> release_soft s), so
            # her slumped head pushes them aside instead of being lifted by them (2026-11-18)
            t_open = (self.t_out + c.get('release_after', 2.5) + (c.get('lower_s', 1.2) if c.get('lower_m') else 0.0)
                      + (c.get('tip_s', 1.0) if c.get('tip_back_deg') else 0.0)
                      + (c.get('pull_s', 0.7) if c.get('pull_back_m') else 0.0))
            w = _smooth((t - t_open) / c.get('open_s', 0.6))
            for s_ in SEGS:
                if s_ != 'torso':
                    tc0 = float(self.eq_ref0[s_][0])
                    self.m.eq_solref[self.eq[s_], 0] = tc0 + (float(c['release_soft']) - tc0) * w
        for s in SEGS:
            self._set_target(d, s, t)

    def squeeze(self, d, weight):
        """-> (left N, right N, score): arm contact on her neck/head split by side"""
        if not self.on:
            return 0.0, 0.0, 0.0
        atk = set(self.gid.values())
        C, f, l, u = self._frame_now(d)
        fl = fr = 0.0
        fb = np.zeros(6)
        for i in range(d.ncon):
            c = d.contact[i]
            if (c.geom1 in atk and c.geom2 in self.her_neck) or (c.geom2 in atk and c.geom1 in self.her_neck):
                self._mj.mj_contactForce(self.m, d, i, fb)
                side = float((c.pos - C) @ l)
                if side > 0.0:
                    fl += fb[0]
                else:
                    fr += fb[0]
        return fl, fr, 2.0 * min(fl, fr) / weight

    def record(self, d, fl, fr, score):
        self.log['seg'].append(np.concatenate([np.concatenate([d.xpos[self.bid[s]], d.xquat[self.bid[s]]])
                                               for s in SEGS]).reshape(len(SEGS), 7))
        self.log['force_L'].append(fl)
        self.log['force_R'].append(fr)
        self.log['score'].append(score)

    def arrays(self):
        out = {'grapple_seg': np.array(self.log['seg']), 'grapple_force_L': np.array(self.log['force_L']),
               'grapple_force_R': np.array(self.log['force_R']), 'grapple_score': np.array(self.log['score']),
               'grapple_names': np.array(SEGS),
               'grapple_len': np.array([np.linalg.norm(np.subtract(*map(np.array, self.locked[s]))) for s in SEGS]),
               'grapple_radius': np.array([RADIUS[s] for s in SEGS])}
        return out
