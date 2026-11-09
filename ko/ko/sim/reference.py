"""Pre-KO reference motion.

`procedural`: keyframed fight poses in anatomical joint angles (degrees), splined in time.
This is a stand-in for real fight motion; `bvh` (mocap / dispatch clips) is the intended
source and plugs in behind the same interface: sample(t) -> (q_ref dict, root_ref).

Pose angles are anatomical, so the same pose works on any rig: shoulder 'abd' is absolute
elevation (-90 arm hanging, 0 horizontal) and is converted with each rig's rest offset.
"""
import numpy as np

POSES = {
    # orthodox stance, left lead, facing -Y. All eyeballed, not from footage.
    'stance': {
        'thigh_L_flex': 28, 'shin_L_flex': 32, 'foot_L_dorsi': 4, 'thigh_L_abd': 6,
        'thigh_R_flex': -8, 'shin_R_flex': 22, 'foot_R_dorsi': 14, 'thigh_R_abd': 8,
        'spine_flex': 8, 'chest_flex': 6, 'neck_flex': 8,
        'upper_arm_L_abd': -62, 'upper_arm_L_flex': 50, 'forearm_L_flex': 112,
        'upper_arm_R_abd': -70, 'upper_arm_R_flex': 35, 'forearm_R_flex': 122,
    },
    # weight driven forward over the lead leg, rear hand extended (a cross / reach)
    'lunge': {
        'thigh_L_flex': 48, 'shin_L_flex': 55, 'foot_L_dorsi': 7, 'thigh_L_abd': 6,
        'thigh_R_flex': -22, 'shin_R_flex': 12, 'foot_R_dorsi': -12, 'thigh_R_abd': 8,
        'spine_flex': 16, 'chest_flex': 10, 'chest_twist': 22, 'spine_twist': 8, 'neck_flex': 4,
        'neck_twist': -20,
        'upper_arm_L_abd': -62, 'upper_arm_L_flex': 45, 'forearm_L_flex': 118,
        'upper_arm_R_abd': -12, 'upper_arm_R_flex': 80, 'forearm_R_flex': 12,
    },
    # KO posturing targets (Animation Bible vocabulary)
    'arms_forward': {'upper_arm_L_abd': -15, 'upper_arm_L_flex': 85, 'forearm_L_flex': 8,
                     'upper_arm_R_abd': -15, 'upper_arm_R_flex': 85, 'forearm_R_flex': 8},
    'fencing_L': {'upper_arm_L_abd': -10, 'upper_arm_L_flex': 70, 'forearm_L_flex': 5,
                  'upper_arm_R_abd': -50, 'upper_arm_R_flex': 40, 'forearm_R_flex': 130},
    'extensor_legs': {'thigh_L_flex': 0, 'shin_L_flex': 0, 'foot_L_dorsi': -35,
                      'thigh_R_flex': 0, 'shin_R_flex': 0, 'foot_R_dorsi': -35,
                      'thigh_L_abd': 0, 'thigh_R_abd': 0},
    'decorticate': {'upper_arm_L_abd': -75, 'upper_arm_L_flex': 30, 'forearm_L_flex': 135,
                    'upper_arm_R_abd': -75, 'upper_arm_R_flex': 30, 'forearm_R_flex': 135,
                    'hand_L_flex': 50, 'hand_R_flex': 50},
    'curl_core': {'spine_flex': 25, 'chest_flex': 18, 'neck_flex': 25},
}


def smooth(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3 - 2 * u)


def dsmooth(u):
    return np.where((u > 0) & (u < 1), 6 * u * (1 - u), 0.0)


class Procedural:
    """keys: [{t, pose, advance}] - `advance` = forward pelvis travel (m) reached at that key."""

    def __init__(self, keys):
        self.keys = sorted(keys, key=lambda k: k['t'])

    def sample(self, t):
        ks = self.keys
        i = max(0, min(len(ks) - 2, int(np.searchsorted([k['t'] for k in ks], t, 'right')) - 1))
        a, b = ks[i], ks[i + 1] if len(ks) > 1 else ks[i]
        span = max(b['t'] - a['t'], 1e-6)
        u = (t - a['t']) / span
        w, dw = float(smooth(u)), float(dsmooth(u)) / span
        pa, pb = POSES[a['pose']], POSES[b['pose']]
        q = {k: (1 - w) * pa.get(k, 0.0) + w * pb.get(k, 0.0) for k in set(pa) | set(pb)}
        qd = {k: dw * (pb.get(k, 0.0) - pa.get(k, 0.0)) for k in set(pa) | set(pb)}
        adv = (1 - w) * a.get('advance', 0.0) + w * b.get('advance', 0.0)
        vadv = dw * (b.get('advance', 0.0) - a.get('advance', 0.0))
        return q, qd, adv, vadv


def make(cfg):
    if cfg.get('type', 'procedural') == 'procedural':
        return Procedural(cfg['keys'])
    raise NotImplementedError('reference type "bvh" is the planned mocap/dispatch path; '
                              'not implemented yet')
