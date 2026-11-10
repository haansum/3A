"""Trace: a sim record turned into named, scenario-independent signals.

Everything a predicate reads comes from here, so predicates never touch raw arrays or rig
conventions. Frames: world is metres, Z up; every body frame is world-aligned at the neutral
pose, so in body coordinates front = -Y, up = +Z, her left = +X on every rig.

'Her frame' for directions of travel is the heading frame: world rotated about Z by the
pelvis yaw at the KO instant (so 'backward' means behind her as she stood when she was hit).
"""
import json

import numpy as np

FRONT, UP, LEFT = np.array([0.0, -1.0, 0.0]), np.array([0.0, 0.0, 1.0]), np.array([1.0, 0.0, 0.0])
AXES = {'front': FRONT, 'back': -FRONT, 'up': UP, 'down': -UP, 'left': LEFT, 'right': -LEFT}
# body-part words -> sim bodies (a contact or position on any of them counts)
PARTS = {
    'head': ['head'], 'neck': ['neck'], 'chest': ['chest'], 'upper_back': ['chest'],
    'trunk': ['chest', 'spine', 'pelvis'], 'pelvis': ['pelvis'], 'hips': ['pelvis'],
    'glutes': ['pelvis'], 'hand_L': ['hand_L'], 'hand_R': ['hand_R'],
    'hands': ['hand_L', 'hand_R'], 'elbows': ['forearm_L', 'forearm_R', 'upper_arm_L', 'upper_arm_R'],
    'arms': ['upper_arm_L', 'upper_arm_R', 'forearm_L', 'forearm_R', 'hand_L', 'hand_R'],
    'knees': ['shin_L', 'shin_R'], 'knee_L': ['shin_L'], 'knee_R': ['shin_R'],
    'feet': ['foot_L', 'foot_R'], 'foot_L': ['foot_L'], 'foot_R': ['foot_R'],
    'legs': ['thigh_L', 'thigh_R', 'shin_L', 'shin_R'],
    'non_feet': ['pelvis', 'spine', 'chest', 'neck', 'head', 'upper_arm_L', 'upper_arm_R',
                 'forearm_L', 'forearm_R', 'hand_L', 'hand_R', 'thigh_L', 'thigh_R', 'shin_L', 'shin_R'],
}


def quat_R(q):
    """(..., 4) wxyz -> (..., 3, 3)"""
    w, x, y, z = np.moveaxis(np.asarray(q, float), -1, 0)
    return np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], -1),
                     np.stack([2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], -1),
                     np.stack([2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)], -1)], -2)


class Trace:
    """t, dt, bodies[list], pos (T,B,3), R (T,B,3,3), joints {name: deg (T,)},
    tone {region: (T,)}, load {body: canvas normal force (T,)}, events {name: s}, weight N."""

    def __init__(self, t, bodies, pos, quat, joints, tone, load, events, weight, rope_load=None):
        self.t, self.dt = np.asarray(t), float(t[1] - t[0])
        self.bodies, self.pos, self.R = list(bodies), np.asarray(pos), quat_R(quat)
        self.joints, self.tone, self.load = joints, tone, load
        self.rope_load = rope_load or {}
        self.weight = float(weight)
        self.events = dict(events)
        self._derive_events()

    # -- construction ----------------------------------------------------------------------
    @classmethod
    def load(cls, sim_path):
        z = np.load(sim_path, allow_pickle=False)
        t, dt = z['t'], float(z['dt'])
        bn = [str(n) for n in z['body_names']]
        gn = [str(n) for n in z['geom_names']]
        jn = [str(n) for n in z['joint_names']]
        q = np.degrees(z['qpos'][:, z['joint_qadr']])
        C = z['contacts']
        cs, g1, g2, cf = C[:, 0].astype(int), C[:, 1].astype(int), C[:, 2].astype(int), C[:, 4]
        canvas = gn.index('canvas')
        load, rope_load = {}, {}
        is_rope = np.array([n.startswith('rope') for n in gn])
        for b in bn:
            g = gn.index('g_' + b) if 'g_' + b in gn else -1
            a = np.zeros(len(t))
            m = ((g1 == canvas) & (g2 == g)) | ((g2 == canvas) & (g1 == g))
            np.add.at(a, cs[m], cf[m])
            load[b] = a
            r = np.zeros(len(t))
            m = (is_rope[g1] & (g2 == g)) | (is_rope[g2] & (g1 == g))
            np.add.at(r, cs[m], cf[m])
            rope_load[b] = r
        ev = dict(json.loads(str(z['events']))) if 'events' in z.files else {}
        if float(z['t_ko']) >= 0:
            ev['ko'] = float(z['t_ko'])
        return cls(t, bn, z['xpos'], z['xquat'], {n: q[:, i] for i, n in enumerate(jn)},
                   {str(r): z['tone'][:, i] for i, r in enumerate(z['regions'])}, load, ev,
                   float(z['mass']) * 9.81, rope_load)

    def _derive_events(self):
        """Events every scenario can refer to, found from the record itself (not from what the
        controller happened to log): start, end, first hard touch of each part, down, rest."""
        ev, t = self.events, self.t
        ev.setdefault('start', 0.0)
        ev['end'] = float(t[-1])
        t0 = ev.get('ko', 0.0)
        after = t >= t0
        for part in ('head', 'glutes', 'chest', 'hands', 'knees', 'non_feet'):
            f = self.part_load(part)
            hit = np.nonzero((f > 0.05 * self.weight) & after)[0]
            if len(hit):
                ev.setdefault('touch:' + part, float(t[hit[0]]))
        if 'touch:non_feet' in ev:
            ev.setdefault('down', ev['touch:non_feet'])
        if 'head_impact' in ev:
            ev['touch:head'] = ev['head_impact']
        elif 'touch:head' in ev:
            ev['head_impact'] = ev['touch:head']
        # rest: last time the pelvis or head moved faster than 0.15 m/s (smoothed over 0.1 s)
        k = max(1, int(0.1 / self.dt))
        sp = np.maximum(self.speed('pelvis', k), self.speed('head', k))
        mov = np.nonzero(sp > 0.15)[0]
        ev.setdefault('rest', float(t[min(len(t) - 1, (mov[-1] + 1) if len(mov) else 0)]))

    # -- accessors -------------------------------------------------------------------------
    def i(self, tt):
        return int(np.clip(round(tt / self.dt), 0, len(self.t) - 1))

    def b(self, name):
        return self.bodies.index(name)

    def parts(self, part):
        return PARTS.get(part, [part])

    def part_load(self, part):
        return sum(self.load[b] for b in self.parts(part))

    def speed(self, body, k=1):
        p = self.pos[:, self.b(body)]
        v = np.zeros(len(p))
        v[k:] = np.linalg.norm(p[k:] - p[:-k], axis=1) / (k * self.dt)
        return v

    def axis(self, body, which):
        """World direction (T,3) of a body axis: front/back/up/down/left/right."""
        return self.R[:, self.b(body)] @ AXES[which]

    def heading(self):
        """3x3 whose columns are her forward, her left, up at the KO instant (yaw only)."""
        i = self.i(self.events.get('ko', 0.0))
        f = self.R[i, self.b('pelvis')] @ FRONT
        f[2] = 0.0
        f /= max(np.linalg.norm(f), 1e-9)
        return np.stack([f, np.cross(UP, f), UP], 1)

    def in_frame(self, point, frame_body):
        """(T,3) position of body `point` in the moving frame of `frame_body` (x = her left,
        y = behind her, z = toward her head)."""
        d = self.pos[:, self.b(point)] - self.pos[:, self.b(frame_body)]
        return np.einsum('tji,tj->ti', self.R[:, self.b(frame_body)], d)
