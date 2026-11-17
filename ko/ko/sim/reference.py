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
    # straight right on the spot (owner 2026-11-15): the lunge's arm and trunk turn, rear foot
    # kept flatter so the sole does not skate while it drives
    'cross': {
        'thigh_L_flex': 42, 'shin_L_flex': 48, 'foot_L_dorsi': 7, 'thigh_L_abd': 6,
        'thigh_R_flex': -14, 'shin_R_flex': 16, 'foot_R_dorsi': 4, 'thigh_R_abd': 8,
        'spine_flex': 14, 'chest_flex': 9, 'chest_twist': 22, 'spine_twist': 8, 'neck_flex': 4,
        'neck_twist': -20,
        'upper_arm_L_abd': -62, 'upper_arm_L_flex': 45, 'forearm_L_flex': 118,
        'upper_arm_R_abd': -12, 'upper_arm_R_flex': 80, 'forearm_R_flex': 12,
    },
    # giving ground: weight on the rear leg, trunk upright to slightly back, guard high
    'retreat': {
        'thigh_L_flex': 30, 'shin_L_flex': 14, 'foot_L_dorsi': -12, 'thigh_L_abd': 6,
        'thigh_R_flex': 12, 'shin_R_flex': 28, 'foot_R_dorsi': 14, 'thigh_R_abd': 8,
        'spine_flex': -4, 'chest_flex': -2, 'neck_flex': 6,
        'upper_arm_L_abd': -55, 'upper_arm_L_flex': 60, 'forearm_L_flex': 105,
        'upper_arm_R_abd': -65, 'upper_arm_R_flex': 45, 'forearm_R_flex': 120,
    },
    # misread: she reads a kick from her left as low and drops both hands to catch it at her lead
    # thigh: trunk folds and turns toward the kick, eyes down on it, chin uncovered (owner
    # 2026-11-12). Eyeballed.
    'catch_low_L': {
        'thigh_L_flex': 36, 'shin_L_flex': 44, 'foot_L_dorsi': 8, 'thigh_L_abd': 8,
        'thigh_R_flex': -4, 'shin_R_flex': 32, 'foot_R_dorsi': 16, 'thigh_R_abd': 8,
        'spine_flex': 20, 'chest_flex': 14, 'chest_twist': 18, 'spine_twist': 8,
        'neck_flex': 22, 'neck_twist': -6,
        'upper_arm_L_abd': -68, 'upper_arm_L_flex': 22, 'forearm_L_flex': 62,
        'upper_arm_R_abd': -52, 'upper_arm_R_flex': 58, 'forearm_R_flex': 48,
    },
    # misread: covers a body feint: elbows tucked, forearms across the stomach, trunk crunched
    # forward, eyes down on the feint, chin open (owner 2026-11-12). Eyeballed.
    'cover_body': {
        'thigh_L_flex': 26, 'shin_L_flex': 30, 'foot_L_dorsi': 4, 'thigh_L_abd': 6,
        'thigh_R_flex': -8, 'shin_R_flex': 22, 'foot_R_dorsi': 14, 'thigh_R_abd': 8,
        'spine_flex': 6, 'chest_flex': 4, 'neck_flex': 10,
        'upper_arm_L_abd': -84, 'upper_arm_L_flex': 4, 'forearm_L_flex': 52,
        'upper_arm_R_abd': -85, 'upper_arm_R_flex': 2, 'forearm_R_flex': 56,
    },
    # hook KO, slump then fall back (owner 2026-11-13): knees fold deep with the hips dropping
    # behind the heels, so the slumped body sits down instead of pitching forward; then the trunk
    # is thrown back over the hips (momentum of the sit), neck limp. Eyeballed.
    'sit_back': {'thigh_L_flex': 95, 'shin_L_flex': 120, 'foot_L_dorsi': 28,
                 'thigh_R_flex': 85, 'shin_R_flex': 110, 'foot_R_dorsi': 24,
                 'thigh_L_abd': 10, 'thigh_R_abd': 12},
    'hunch_back': {'spine_flex': -4, 'chest_flex': 14, 'neck_flex': 30, 'head_flex': 10},   # shoulders round, lower back upright
    # legs lock and tip her back: hips extend, knees straight, toes come up (heels take the
    # weight), so the body pivots backward over the heels instead of forward over the toes
    # tonic pike (owner 2026-11-14 hook_chair_gnp): knees locked straight, hips flexed so the heels
    # lift off the canvas when the core curls, ankles pointed just inside the -45 deg stop (past it
    # they chattered on the limit: QA jitter; the bake 'pointe' layer adds the rest); L/R uneven
    # limp and organic while laid out (owner 2026-11-14): knees a little bent, legs fallen apart,
    # feet relaxed; head rolled to one side
    'legs_limp_splay': {'thigh_L_flex': 9, 'thigh_L_abd': 12, 'shin_L_flex': 16, 'foot_L_dorsi': -18,
                        'thigh_R_flex': 4, 'thigh_R_abd': 8, 'shin_R_flex': 9, 'foot_R_dorsi': -14},
    'head_rolled_limp': {'neck_twist': 28, 'neck_lat': 10, 'head_lat': 6, 'neck_flex': 4},
    'pike_legs_locked': {'thigh_L_flex': -10, 'shin_L_flex': 0, 'foot_L_dorsi': -43, 'thigh_L_abd': -3,
                         'thigh_R_flex': -12, 'shin_R_flex': 0, 'foot_R_dorsi': -42, 'thigh_R_abd': -5},
    'lock_back': {'thigh_L_flex': -16, 'shin_L_flex': 0, 'foot_L_dorsi': 14,
                  'thigh_R_flex': -12, 'shin_R_flex': 0, 'foot_R_dorsi': 12},
    'trunk_throw_back': {'spine_flex': -14, 'chest_flex': -10, 'spine_lat': 3, 'chest_lat': 2},
    # KO posturing targets (Animation Bible vocabulary)
    'rigid_trunk': {'spine_flex': 0, 'chest_flex': 0, 'spine_lat': 0, 'chest_lat': 0,
                    'spine_twist': 0, 'chest_twist': 0, 'neck_flex': 0, 'neck_lat': 0,
                    'neck_twist': 0, 'head_flex': 0},
    'extensor_legs_hard': {'thigh_L_flex': -5, 'shin_L_flex': 0, 'foot_L_dorsi': -45,
                           'thigh_R_flex': -5, 'shin_R_flex': 0, 'foot_R_dorsi': -45,
                           'thigh_L_abd': -4, 'thigh_R_abd': -4},
    'fencing_escalated': {'upper_arm_L_abd': -5, 'upper_arm_L_flex': 60, 'forearm_L_flex': 0,
                          'hand_L_flex': -30,
                          'upper_arm_R_abd': -40, 'upper_arm_R_flex': 55, 'forearm_R_flex': 140,
                          'hand_R_flex': 55},
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
    # wheel-kick GNP archetype
    'loose_guard_asym': {   # guard sags but hands stay up; one elbow opens, the other closes
        'upper_arm_L_abd': -66, 'upper_arm_L_flex': 52, 'forearm_L_flex': 84, 'hand_L_flex': 50,
        'upper_arm_R_abd': -72, 'upper_arm_R_flex': 30, 'forearm_R_flex': 138, 'hand_R_flex': 55},
    'slump_forward': {'spine_flex': 9, 'chest_flex': 7, 'neck_flex': 14, 'head_flex': 5,
                      'spine_lat': 0, 'chest_lat': 0, 'spine_twist': 0, 'chest_twist': 0},
    'fencing_mid': {'upper_arm_L_abd': -40, 'upper_arm_L_flex': 62, 'forearm_L_flex': 40,
                    'hand_L_flex': 55, 'upper_arm_L_twist': 25,
                    'upper_arm_R_abd': -62, 'upper_arm_R_flex': 42, 'forearm_R_flex': 142,
                    'hand_R_flex': 60, 'upper_arm_R_twist': 25},
    'shoulders_forward': {'chest_flex': 20, 'spine_flex': 8, 'neck_flex': 12, 'head_flex': 4},
    'scissor_legs': {'thigh_L_flex': 8, 'thigh_L_abd': -12, 'shin_L_flex': 4, 'foot_L_dorsi': -35,
                     'thigh_R_flex': -6, 'thigh_R_abd': -10, 'shin_R_flex': 0, 'foot_R_dorsi': -35},
    'ankles_crossed': {'thigh_L_flex': 3, 'thigh_L_abd': -22, 'thigh_L_twist': 12, 'shin_L_flex': 6,
                       'foot_L_dorsi': -45, 'foot_L_inv': 15,
                       'thigh_R_flex': -5, 'thigh_R_abd': -22, 'thigh_R_twist': 12, 'shin_R_flex': 0,
                       'foot_R_dorsi': -45, 'foot_R_inv': 15},
    'fencing_max': {'upper_arm_L_abd': -8, 'upper_arm_L_flex': 68, 'forearm_L_flex': 0,
                    'hand_L_flex': 65, 'upper_arm_L_twist': 35,
                    'upper_arm_R_abd': -48, 'upper_arm_R_flex': 50, 'forearm_R_flex': 148,
                    'hand_R_flex': 68, 'upper_arm_R_twist': 35},
    'shoulders_max': {'chest_flex': 24, 'spine_flex': 5, 'neck_flex': 18, 'head_flex': 6},
    # tonic posture demos (2026-11-11). Twist sign follows fencing_mid's convention (+ = inward,
    # pronating); checked visually on Mosin, not numerically.
    'arms_up_sym': {'upper_arm_L_abd': -12, 'upper_arm_L_flex': 88, 'forearm_L_flex': 12,
                    'hand_L_flex': 45, 'upper_arm_L_twist': 15,
                    'upper_arm_R_abd': -12, 'upper_arm_R_flex': 88, 'forearm_R_flex': 12,
                    'hand_R_flex': 45, 'upper_arm_R_twist': 15},
    'decerebrate': {'upper_arm_L_abd': -84, 'upper_arm_L_flex': 4, 'forearm_L_flex': 0,
                    'hand_L_flex': 55, 'upper_arm_L_twist': 45,
                    'upper_arm_R_abd': -84, 'upper_arm_R_flex': 4, 'forearm_R_flex': 0,
                    'hand_R_flex': 55, 'upper_arm_R_twist': 45},
    'arch_neck': {'spine_flex': -6, 'chest_flex': -4, 'neck_flex': -22, 'head_flex': -10,
                  'spine_lat': 0, 'chest_lat': 0, 'spine_twist': 0, 'chest_twist': 0},
    'decorticate_tight': {'upper_arm_L_abd': -78, 'upper_arm_L_flex': 38, 'forearm_L_flex': 140,
                          'hand_L_flex': 62, 'upper_arm_L_twist': 20,
                          'upper_arm_R_abd': -78, 'upper_arm_R_flex': 38, 'forearm_R_flex': 140,
                          'hand_R_flex': 62, 'upper_arm_R_twist': 20},
    # exaggerated, deliberately unequal left/right versions (owner 2026-11-12: "more extreme,
    # looks too perfect"). Wrists sit at their +70 limit on the lead side.
    'slump_hard': {'spine_flex': 24, 'chest_flex': 22, 'neck_flex': 34, 'head_flex': 12,
                   'spine_lat': 5, 'chest_lat': 4, 'spine_twist': 6, 'chest_twist': 8},
    # shut off going forward (owner 2026-11-15): knees and hips fold under the falling weight,
    # lead leg deeper, trunk folds over; she drops toward her knees instead of toppling as a plank
    'buckle_forward': {'thigh_L_flex': 62, 'shin_L_flex': 95, 'foot_L_dorsi': 18,
                       'thigh_R_flex': 30, 'shin_R_flex': 85, 'foot_R_dorsi': -10,
                       'spine_flex': 18, 'chest_flex': 14},
    'knees_give': {'thigh_L_flex': 14, 'shin_L_flex': 22, 'foot_L_dorsi': 6,
                   'thigh_R_flex': 8, 'shin_R_flex': 14, 'foot_R_dorsi': 2},
    'arms_forward_ragged': {'upper_arm_L_abd': -10, 'upper_arm_L_flex': 92, 'forearm_L_flex': 6,
                            'hand_L_flex': 40, 'upper_arm_R_abd': -28, 'upper_arm_R_flex': 64,
                            'forearm_R_flex': 38, 'hand_R_flex': 55},
    'fencing_extreme': {'upper_arm_L_abd': 2, 'upper_arm_L_flex': 82, 'forearm_L_flex': 0,
                        'hand_L_flex': 70, 'upper_arm_L_twist': 45,
                        'upper_arm_R_abd': -30, 'upper_arm_R_flex': 64, 'forearm_R_flex': 150,
                        'hand_R_flex': 68, 'upper_arm_R_twist': 38},
    'arms_up_extreme': {'upper_arm_L_abd': -4, 'upper_arm_L_flex': 104, 'forearm_L_flex': 4,
                        'hand_L_flex': 70, 'upper_arm_L_twist': 32,
                        'upper_arm_R_abd': -22, 'upper_arm_R_flex': 86, 'forearm_R_flex': 28,
                        'hand_R_flex': 58, 'upper_arm_R_twist': 12},
    'decorticate_extreme': {'upper_arm_L_abd': -82, 'upper_arm_L_flex': 46, 'forearm_L_flex': 150,
                            'hand_L_flex': 70, 'upper_arm_L_twist': 32,
                            'upper_arm_R_abd': -70, 'upper_arm_R_flex': 30, 'forearm_R_flex': 142,
                            'hand_R_flex': 62, 'upper_arm_R_twist': 14},
    'decerebrate_extreme': {'upper_arm_L_abd': -88, 'upper_arm_L_flex': -12, 'forearm_L_flex': 0,
                            'hand_L_flex': 70, 'upper_arm_L_twist': 72,
                            'upper_arm_R_abd': -78, 'upper_arm_R_flex': 0, 'forearm_R_flex': 6,
                            'hand_R_flex': 60, 'upper_arm_R_twist': 56},
    'extensor_legs_ragged': {'thigh_L_flex': -8, 'shin_L_flex': 0, 'foot_L_dorsi': -45, 'thigh_L_abd': -8,
                             'thigh_L_twist': 14, 'thigh_R_flex': 2, 'shin_R_flex': 6,
                             'foot_R_dorsi': -36, 'thigh_R_abd': 3, 'thigh_R_twist': -6},
    'arch_neck_hard': {'spine_flex': -16, 'chest_flex': -12, 'neck_flex': -36, 'head_flex': -18,
                       'spine_lat': 4, 'chest_lat': 3, 'spine_twist': 5, 'chest_twist': 6},
    'curl_core_hard': {'spine_flex': 34, 'chest_flex': 26, 'neck_flex': 36, 'spine_lat': -6,
                       'chest_twist': -8},
    'curl_core': {'spine_flex': 25, 'chest_flex': 18, 'neck_flex': 25},
    # head kick (2026-11-12): the neck springs back to neutral after the whip, arms drop loose
    'neck_neutral': {'neck_flex': 0, 'neck_lat': 0, 'neck_twist': 0, 'head_flex': 0, 'head_lat': 0},
    # uppercut / teeter back (2026-11-12): shoulders roll forward (no scapula DoF: upper arms
    # adduct and turn in across the chest, elbows bent), chest curls; chin lifts (neck extends)
    'shoulders_roll_fwd': {'upper_arm_L_abd': -64, 'upper_arm_L_flex': 46, 'upper_arm_L_twist': 34,
                           'forearm_L_flex': 96, 'hand_L_flex': 55,
                           'upper_arm_R_abd': -58, 'upper_arm_R_flex': 38, 'upper_arm_R_twist': 28,
                           'forearm_R_flex': 84, 'hand_R_flex': 48},
    'chin_up': {'neck_flex': -30, 'head_flex': -16},
    # lying on her back the heavier end stays down: curling at the lumbar spine lifts the legs,
    # curling at the thoracic (chest) joint lifts the upper back off the mat
    'upper_back_curl': {'chest_flex': 30, 'spine_flex': 6, 'chest_lat': -4, 'chest_twist': -5},
    # a failed catch while drifting back: hips and trunk lean forward, ankles dorsiflex
    'teeter_catch': {'spine_flex': 14, 'chest_flex': 10, 'thigh_L_flex': 14, 'thigh_R_flex': 10,
                     'foot_L_dorsi': 12, 'foot_R_dorsi': 10, 'shin_L_flex': 8, 'shin_R_flex': 6},
    # uppercut + hook follow-up (owner 2026-11-16 "arms extended straight"): after the follow-up both
    # arms lock straight, elbows at 0, raised toward the ceiling lying on her back; L/R uneven
    # (v3 owner 2026-11-16 13:26: "one arm angled higher, one lower") left swept up past vertical
    # toward her head, right low toward her hip and lifted off the mat; both elbows locked
    # face-down rest (owner 2026-11-17: a tucked chin face down reads inorganic): the head rolls
    # onto one cheek, the neck slightly extended rather than flexed
    'head_rest_cheek_R': {'neck_flex': -8, 'neck_lat': -14, 'neck_twist': -70, 'head_flex': -4, 'head_lat': -8},
    'head_rest_cheek_L': {'neck_flex': -8, 'neck_lat': 14, 'neck_twist': 70, 'head_flex': -4, 'head_lat': 8},
    # arms that trail the fall instead of reaching for the canvas (no protective reaction)
    'arms_trail': {'upper_arm_L_abd': -80, 'upper_arm_L_flex': -15, 'forearm_L_flex': 20, 'hand_L_flex': 20,
                   'upper_arm_R_abd': -80, 'upper_arm_R_flex': -15, 'forearm_R_flex': 20, 'hand_R_flex': 20},
    'arms_extended_straight': {'upper_arm_L_abd': -8, 'upper_arm_L_flex': 128, 'forearm_L_flex': 0,
                               'hand_L_flex': 60, 'upper_arm_L_twist': 45,
                               'upper_arm_R_abd': -26, 'upper_arm_R_flex': 38, 'forearm_R_flex': 0,
                               'hand_R_flex': 55, 'upper_arm_R_twist': 45},
    # springy load (owner 2026-11-15 note): knees and hips fold shallow under the dropping weight
    # (not the deep chair sit); an overshoot shape on light damping makes them rebound once
    # hook follow-up lying down: head whipped to her right and left there (twist sign measured on
    # izzy_uppercut_spring_001: the left-cheek impulse drives neck_twist negative)
    'head_whipped_R': {'neck_twist': -38, 'neck_lat': -8, 'head_lat': -6, 'neck_flex': 4},
    # escalated legs (owner 2026-11-16): knees locked, ankles crossed (v4: the L leg lifts and swings across (legs_crossed_high), then the L knee bends (28 deg) and the L ankle drops across onto the R shin (legs_crossed_pike): measured L ankle 8 cm past and 8 cm above the R ankle, shins in contact; straight-kneed crossing jammed knee against knee), pointed but kept
    # off the -45 deg stop (crossed feet chattered there: QA jitter); the core curl lifts the heels
    # (v5 owner 2026-11-16 13:26: "legs extended: glutes, quads and calves contracted, ballerina
    # point") knees locked straight, hips extended, feet pointed just inside the -45 deg stop (the
    # bake pointe layer adds the arch). Ankles crossed L over R: the L leg rides a little higher,
    # adducted across; shin-shin contact is excluded for this take (knees jammed otherwise)
    'legs_crossed_high': {'thigh_L_flex': 6, 'thigh_L_abd': -20, 'thigh_L_twist': 8, 'shin_L_flex': 0,
                          'foot_L_dorsi': -40, 'foot_L_inv': 8,
                          'thigh_R_flex': -6, 'thigh_R_abd': -9, 'thigh_R_twist': 6, 'shin_R_flex': 0,
                          'foot_R_dorsi': -40, 'foot_R_inv': 6},
    'legs_crossed_pike': {'thigh_L_flex': -2, 'thigh_L_abd': -17, 'thigh_L_twist': 8, 'shin_L_flex': 0,
                          'foot_L_dorsi': -40, 'foot_L_inv': 8,
                          'thigh_R_flex': -8, 'thigh_R_abd': -9, 'thigh_R_twist': 6, 'shin_R_flex': 0,
                          'foot_R_dorsi': -40, 'foot_R_inv': 6},
    'knees_load': {'thigh_L_flex': 48, 'shin_L_flex': 78, 'foot_L_dorsi': 20, 'thigh_L_abd': 8,
                   'thigh_R_flex': 42, 'shin_R_flex': 70, 'foot_R_dorsi': 18, 'thigh_R_abd': 10},
    'arms_drop': {'upper_arm_L_abd': -72, 'upper_arm_L_flex': 22, 'forearm_L_flex': 38, 'hand_L_flex': 30,
                  'upper_arm_R_abd': -76, 'upper_arm_R_flex': 16, 'forearm_R_flex': 52, 'hand_R_flex': 35},
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
