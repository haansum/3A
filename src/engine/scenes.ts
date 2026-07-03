import type { Rng } from './rng';
import type { StrikeKind, SubKind, TakedownKind } from './techniques';
import type { BodyState, SceneDescription } from './types';

/**
 * Scene builder: converts a fight moment into animator-ready kinematics.
 * Every string is chosen from the fight's seeded RNG, so replaying a seed
 * reproduces identical scene data.
 *
 * Vocabulary is deliberately concrete — joints, weight distribution,
 * contact points, gaze direction — so a renderer can stage the shot
 * straight from the description.
 */

export interface SceneCondition {
  tired: boolean;
  hurt: boolean;
  rocked: boolean;
}

export interface SceneFighter {
  id: string;
  name: string;
  cond: SceneCondition;
}

// ---- Faces ----

const FACE_FRESH = [
  'jaw set, eyes narrowed and locked on the opponent, breathing through the nose',
  'calm and focused, chin tucked, eyes tracking the opponent’s chest',
];
const FACE_TIRED = [
  'mouth hanging open, chest heaving, sweat streaming off the brow',
  'lips parted gasping for air, eyelids heavy, face slack with fatigue',
];
const FACE_HURT = [
  'blood tracing from the nostril, one eye beginning to swell, expression grim',
  'face marked up and reddened, wincing, jaw clenched against the pain',
];
const FACE_ROCKED = [
  'eyes glassy and unfocused, pupils drifting, mouth slack',
  'blinking hard trying to reset, eyes swimming, legs not receiving signals',
];
const FACE_PREDATOR = [
  'eyes wide and locked onto the hurt opponent, nostrils flared, killer instinct taking over',
  'face lit with urgency, teeth bared around the mouthguard, zeroed in for the finish',
];
const FACE_UNCONSCIOUS = [
  'eyes rolled back, jaw slack, features completely relaxed in unconsciousness',
  'eyes closed, mouthguard half out, face empty of all tension',
];
const FACE_DESPERATE = [
  'eyes pinched shut, face crimson, veins standing out at the temple',
  'grimacing, cheeks compressed, panic flickering across the eyes',
];
const FACE_STRAINING = [
  'teeth gritted with effort, brow knotted, exhaling hard through pursed lips',
  'face taut with exertion, eyes fixed on the grip',
];

function face(rng: Rng, f: SceneFighter): string {
  if (f.cond.rocked) return rng.pick(FACE_ROCKED);
  if (f.cond.hurt && f.cond.tired) return `${rng.pick(FACE_HURT)}; ${rng.pick(FACE_TIRED)}`;
  if (f.cond.hurt) return rng.pick(FACE_HURT);
  if (f.cond.tired) return rng.pick(FACE_TIRED);
  return rng.pick(FACE_FRESH);
}

// ---- Settings ----

const SETTINGS_STANDING = [
  'center of the cage, both fighters in open space under the main lights',
  'near the fence, the crowd on its feet just beyond the chain-link',
  'in open space just off-center, the canvas streaked with sweat',
];
const SETTINGS_GROUND = [
  'on the canvas near the center of the cage',
  'on the ground tight against the base of the fence',
  'flat on the canvas, the referee crouched low nearby watching for the stoppage',
];
const SETTINGS_CLINCH = [
  'pressed against the fence, bodies locked chest to chest',
  'along the cage wall, the chain-link bowing outward with their weight',
];

// ---- Strike kinematics (actor delivering the blow) ----

const STRIKE_BODY: Record<StrikeKind, string[]> = {
  straight: [
    'rear foot pivoting, hips rotating square, rear shoulder extending fully with the fist corkscrewing, chin tucked behind the lead shoulder',
    'weight transferring rear-to-front through the punch, elbow tight to the ribs until full extension, lead hand framing high',
  ],
  hook: [
    'weight snapping onto the lead leg, elbow locked at ninety degrees, torso whipping the arm through a horizontal arc, heel raised and pivoting',
    'compact rotation from the core, shoulder turning through the target line, fist palm-down at impact',
  ],
  uppercut: [
    'knees bent, torso dipping low then exploding upward, fist rising vertically between the opponent’s guard, hips driving through the punch',
    'weight coiled over the rear leg, arm shoveling upward from the waist, shoulder finishing at chin height',
  ],
  overhand: [
    'body lunging forward, rear arm looping over the top in a wide arc, rear heel lifting completely off the canvas, torso bent at the finish',
    'launching off the back foot, arm swung like a hammer over the opponent’s lead shoulder, body carried past the target by the follow-through',
  ],
  bodyshot: [
    'level dropping sharply, lead shoulder dipping, fist buried into the ribs beneath the elbow, legs coiled in a deep stance',
    'crouched rotation, torso twisting to sink the punch under the floating ribs, eyes up on the opponent’s hands',
  ],
  legkick: [
    'hips swinging through with the whole body, shin chopping into the outer thigh, arms counter-rotating for balance, base foot pivoted ninety degrees',
    'stepping slightly outside the lead foot, shin whipping low and hard through the leg, torso leaning back for balance',
  ],
  headkick: [
    'base leg pivoting fully, hips whipping over as the shin arcs at neck height, arms slashing down and across for counterbalance, torso tilting away',
    'kick rising in one motion from the floor, hip rolling over the top, shin connecting across the jawline, arms wide',
  ],
  frontkick: [
    'knee chambering high to the chest, hips thrusting forward, ball of the foot snapping straight out into the midsection, arms tight',
    'lead knee lifting, foot pistoning out at belt height, shoulders back to keep balance through the push',
  ],
  knee: [
    'hips surging forward, knee spearing upward into the target, back arched, arms pulling down for collision force',
    'stepping in with the knee rising diagonally, hips fully extended at impact, standing leg on the ball of the foot',
  ],
  elbow: [
    'short violent rotation at close range, elbow slicing horizontally across the target’s face, forearm folded fully',
    'stepping through, elbow carving a tight downward diagonal, shoulder driving behind the point of contact',
  ],
};

const STRIKE_MOTION = [
  'explosive and compact, the strike arriving before the guard can react',
  'thrown with full commitment, weight fully transferred through the target',
  'short, sharp and violent — maximum force over minimum distance',
];

// ---- Target reactions ----

const HIT_CLEAN = [
  'head snapping back on impact, sweat spraying in an arc, feet still planted but weight thrown onto the heels',
  'torso twisting away from the blow, guard splitting open at the moment of contact',
];
const HIT_ROCKED = [
  'knees buckling momentarily, hands dropping to the waist, stumbling a half step backward with the hips sagging',
  'sagging against his own legs, feet doing a small involuntary shuffle to stay under the body, arms pawing out blindly for range',
];
const FALL_KINEMATICS = [
  'legs cutting out from under him, falling straight back, arms windmilling, the back of the head bouncing off the canvas',
  'crumpling forward onto both knees, torso folding, one glove touching the canvas before the body tips onto its side',
  'sitting down heavily into the fence, legs splayed, head lolling back against the chain-link',
  'spinning a quarter turn from the impact and dropping face-first, catching himself on his forearms',
];
const KO_BODY = [
  'body going rigid mid-fall, arms locked straight out, unconscious before impact, landing flat with legs folded underneath',
  'collapsing in stages — knees, hips, shoulders — ending face-down with one arm pinned under the torso, completely limp',
];
const MOTION_FALLING = [
  'all muscle control gone, gravity doing the rest',
  'dropping with dead weight, no attempt to break the fall',
];
const MOTION_STAGGER = [
  'reeling backward on unsteady legs, balance system misfiring',
  'wobbling laterally, feet crossing as the body fights to stay upright',
];

// ---- Takedown kinematics ----

const TD_ACTOR: Record<TakedownKind, string[]> = {
  double: [
    'explosive level change, penetration step planted deep between the opponent’s feet, back flat and head up, arms wrapping behind both knees, driving through and lifting',
    'shooting low off the rear leg, shoulder spearing into the midsection, hands clasping behind the thighs, running the feet on contact to finish the drive',
  ],
  single: [
    'dropping to one knee on the shot, both arms lassoing the lead leg, head pinned tight to the inside of the thigh, rising to a stand while cradling the captured leg',
    'snatching the lead ankle to the chest, chest pressing the knee, hopping the opponent backward to break his base',
  ],
  trip: [
    'chest-to-chest grip, leg reaping behind the opponent’s calf while the upper body twists him over the blocked leg',
    'foot hooking behind the heel, weight surging forward through the chest to topple him over the trapped foot',
  ],
  anklepick: [
    'snapping the opponent’s head down with one hand and diving for the ankle with the other, plucking the foot off the canvas in one motion',
    'faking high then dropping low, fingers hooking the Achilles, lifting the ankle to hip height as the opponent hops and falls',
  ],
  bodylock: [
    'arms cinched around the waist, hips lowered beneath the opponent’s center of gravity, arching and turning to plant him sideways on the canvas',
    'clamping a tight over-under body lock, forehead in the jaw, sagging the weight down and corkscrewing him to the floor',
  ],
  highcrotch: [
    'ducking under the arm, shoulder in the hip crease, one arm threaded deep between the legs, standing tall to elevate the opponent off the floor before turning the corner',
    'climbing the position from a deep underhook, lifting the opponent across the shoulders, feet leaving the canvas before the slam',
  ],
};

const TD_TARGET_TAKEN = [
  'hips caught mid-sprawl, legs swept from under him, landing flat on his back with elbows tucking in instinctively',
  'base broken, arms posting toward the canvas on the way down, guard already closing around the top fighter',
  'lifted clear of the floor, legs kicking, then driven down through the canvas with the attacker’s weight following through',
];
const TD_TARGET_SPRAWL = [
  'hips shooting back hard, legs flaring wide out of reach, chest crushing down on the attacker’s shoulders, forearm barred across the neck',
  'reading the shot early, feet backpedaling, palm stiff-arming the attacker’s forehead into the canvas',
];
const TD_ACTOR_STUFFED = [
  'stretched face-down under the sprawl, arms still hugging air, hips flattened to the canvas',
  'caught on one knee with the shot dead, head trapped under the opponent’s chest, hands sliding off the sweat-slick legs',
];

// ---- Submission kinematics ----

interface SubScene {
  actor: string[];
  target: string[];
}

const SUB_SCENES: Record<SubKind, SubScene> = {
  armbar: {
    actor: [
      'swiveled perpendicular across the opponent’s chest, both legs clamped over the torso and face, hips glued under the shoulder, back arching as the trapped wrist is dragged to the sternum',
      'falling back with the arm secured, knees pinched tight around the shoulder, heels digging into ribs and jaw, hips bridging upward against the elbow joint',
    ],
    target: [
      'flat on his back, arm fully extended and trapped between the attacker’s thighs, free hand clamped onto his own wrist in a last grip fight, heels scraping the canvas for leverage',
      'elbow hyperextending by degrees, body curling toward the trapped arm to relieve the pressure, legs kicking for a stack position',
    ],
  },
  triangle: {
    actor: [
      'on his back with hips elevated, legs figure-foured around the opponent’s neck and trapped arm, hands clasped behind the opponent’s head pulling down, calf biting into the carotid',
      'angling off perpendicular, locking the ankle behind the knee, squeezing the thighs while curling the torso upward',
    ],
    target: [
      'posture broken, head dragged down to the attacker’s chest, one arm swallowed inside the leg lock and the other posting desperately on the canvas, face darkening',
      'trying to stack forward with legs driving, hands prying at the shin across the back of the neck',
    ],
  },
  rnc: {
    actor: [
      'chest sealed to the opponent’s back, both hooks in behind the thighs, forearm barred under the chin with the bicep and forearm scissoring the neck, other hand behind the head, squeezing and arching',
      'flattening the opponent out from back mount, chin over the shoulder, arm sliding under the jaw millimeter by millimeter until the grip locks',
    ],
    target: [
      'face-down and covered by the attacker’s body, chin tucked hard, both hands peeling at the choking forearm, legs pushing blindly against the canvas',
      'seated back into the attacker’s chest, eyes toward the ceiling, two-on-one grip on the strangling wrist as the hooks stretch him out',
    ],
  },
  guillotine: {
    actor: [
      'front headlock cinched, forearm blade under the throat, wrist clasped and elbows drawn skyward, arching backward with guard closed around the opponent’s waist',
      'snatching the neck as the opponent ducks in, sitting to guard and extending the hips into the choke, shoulders shrugged to the ears',
    ],
    target: [
      'head trapped under the armpit, neck bent forward, one arm inside the guard pushing at the hip, feet driving the body forward to relieve the angle',
      'caught mid-shot with the head down, hands clamping the choking wrist, trying to jump the legs over to the safe side',
    ],
  },
  kimura: {
    actor: [
      'figure-four grip locked on the wrist, chest pinning the shoulder, cranking the bent arm up the spine in a slow arc, legs stapling the torso',
      'sitting through to the side, double wrist lock secured, torso rotating to wrench the shoulder past its range',
    ],
    target: [
      'arm bent behind at a worsening angle, shoulder rolling forward against the joint, free hand gripping his own belt line in defense, face pressed to the canvas',
      'body flattening as the arm is levered upward, heels drumming for base, tapping hand hovering',
    ],
  },
  armtriangle: {
    actor: [
      'head-and-arm grip locked, own shoulder crushing the trapped arm across the opponent’s carotid, sliding off the mount to the choking side, legs sprawled wide with hips driving low',
      'cheek pressed to the canvas past the opponent’s trapped shoulder, hands palm-to-palm squeezing, toes driving the body forward',
    ],
    target: [
      'pinned under the side pressure, own bicep crushed against the neck, eyes bulging, free hand slapping at the attacker’s hip for space',
      'trapped arm buckled across the throat, legs bridging in short spasms, color draining from the face',
    ],
  },
  darce: {
    actor: [
      'arm threaded deep under the neck and armpit, hands locked in a tight figure-four, sprawled with chest weight through the shoulders, squeezing while walking the legs around',
      'rolling the opponent onto his shoulder with the choke locked, knees pinched around the head-and-arm bundle, back rounding to finish',
    ],
    target: [
      'balled up on his side, neck and arm wrapped in the coil, free hand tugging uselessly at the locked wrist, legs scissoring for a way out',
      'shoulder pinned under his own trapped arm, face compressed and darkening, feet scrambling against the fence',
    ],
  },
};

const SUB_TAP = [
  'the free hand rising and slapping the attacker’s body twice, fast and unmistakable',
  'palm hammering the canvas in rapid taps, whole body going slack the instant the hold releases',
];

// ---- Builders ----

function bodyState(f: SceneFighter, body: string, motion: string, faceStr: string): BodyState {
  return { fighterId: f.id, name: f.name, body, motion, face: faceStr };
}

export type StrikeSeverity = 'rocked' | 'knockdown';

export function strikeScene(
  rng: Rng,
  actor: SceneFighter,
  target: SceneFighter,
  kind: StrikeKind,
  severity: StrikeSeverity,
): SceneDescription {
  const targetBody = severity === 'knockdown' ? rng.pick(FALL_KINEMATICS) : rng.pick(HIT_ROCKED);
  const targetMotion = severity === 'knockdown' ? rng.pick(MOTION_FALLING) : rng.pick(MOTION_STAGGER);
  return {
    setting: rng.pick(SETTINGS_STANDING),
    actor: bodyState(actor, rng.pick(STRIKE_BODY[kind]), rng.pick(STRIKE_MOTION), rng.pick(FACE_PREDATOR)),
    target: bodyState(target, targetBody, targetMotion, rng.pick(FACE_ROCKED)),
  };
}

export function cleanHitScene(
  rng: Rng,
  actor: SceneFighter,
  target: SceneFighter,
  kind: StrikeKind,
): SceneDescription {
  return {
    setting: rng.pick(SETTINGS_STANDING),
    actor: bodyState(actor, rng.pick(STRIKE_BODY[kind]), rng.pick(STRIKE_MOTION), face(rng, actor)),
    target: bodyState(target, rng.pick(HIT_CLEAN), 'absorbing the shot and resetting the guard', face(rng, target)),
  };
}

export function takedownScene(
  rng: Rng,
  actor: SceneFighter,
  target: SceneFighter,
  kind: TakedownKind,
  completed: boolean,
): SceneDescription {
  if (completed) {
    return {
      setting: rng.pick(SETTINGS_STANDING),
      actor: bodyState(
        actor,
        rng.pick(TD_ACTOR[kind]),
        'one continuous chain: level change, contact, drive, finish',
        rng.pick(FACE_STRAINING),
      ),
      target: bodyState(target, rng.pick(TD_TARGET_TAKEN), 'balance stolen mid-step, falling with the drive', face(rng, target)),
    };
  }
  return {
    setting: rng.pick(SETTINGS_STANDING),
    actor: bodyState(actor, rng.pick(TD_ACTOR_STUFFED), 'forward drive dying against the sprawl', rng.pick(FACE_STRAINING)),
    target: bodyState(target, rng.pick(TD_TARGET_SPRAWL), 'reacting in a blink — hips back, weight down', face(rng, target)),
  };
}

export type SubPhase = 'locked' | 'escape' | 'tap';

export function submissionScene(
  rng: Rng,
  actor: SceneFighter,
  target: SceneFighter,
  kind: SubKind,
  phase: SubPhase,
): SceneDescription {
  const bank = SUB_SCENES[kind];
  const targetBody = phase === 'tap' ? `${rng.pick(bank.target)} — ${rng.pick(SUB_TAP)}` : rng.pick(bank.target);
  const targetMotion =
    phase === 'escape'
      ? 'creating an inch of space and sliding free, scrambling immediately'
      : phase === 'tap'
        ? 'resistance collapsing all at once'
        : 'every muscle fighting the hold';
  const targetFace = phase === 'escape' ? face(rng, target) : rng.pick(FACE_DESPERATE);
  return {
    setting: rng.pick(SETTINGS_GROUND),
    actor: bodyState(actor, rng.pick(bank.actor), 'constricting by degrees, adjusting grip with each breath', rng.pick(FACE_STRAINING)),
    target: bodyState(target, targetBody, targetMotion, targetFace),
  };
}

export function groundStrikesScene(rng: Rng, actor: SceneFighter, target: SceneFighter): SceneDescription {
  return {
    setting: rng.pick(SETTINGS_GROUND),
    actor: bodyState(
      actor,
      rng.pick([
        'postured tall in the guard, knees pinning the hips, torso rising and twisting with each downward punch, fists falling like pistons',
        'riding half guard with head low, short elbows carving from the shoulder, weight never leaving the opponent’s chest',
      ]),
      'rhythmic and heavy, each shot loaded with body weight',
      rng.pick(FACE_PREDATOR),
    ),
    target: bodyState(
      target,
      rng.pick([
        'flat on his back, forearms crossed over the face, hips bumping to off-balance the top fighter, knees climbing for guard',
        'turtled to one side, glove and forearm shelled around the head, eyes peeking between the gaps',
      ]),
      'absorbing and deflecting, hunting for the hip escape',
      face(rng, target),
    ),
  };
}

export function clinchScene(rng: Rng, actor: SceneFighter, target: SceneFighter): SceneDescription {
  return {
    setting: rng.pick(SETTINGS_CLINCH),
    actor: bodyState(
      actor,
      rng.pick([
        'underhook cinched deep, forehead pressed under the jaw, hips square and driving, short uppercuts and knees churning from inside the tie-up',
        'collar tie and wrist control, shoulder crushed into the opponent’s chest, feet staggered and driving him flat to the fence',
      ]),
      'grinding, constant forward pressure',
      face(rng, actor),
    ),
    target: bodyState(
      target,
      rng.pick([
        'back bowed into the chain-link, hips pushed away to deny the takedown, elbows tight, hand-fighting for the underhook',
        'flattened against the fence, chin down, absorbing knees on the thighs while circling the feet for an exit',
      ]),
      'defending, working to reverse the position',
      face(rng, target),
    ),
  };
}

export function sweepScene(rng: Rng, actor: SceneFighter, target: SceneFighter): SceneDescription {
  return {
    setting: rng.pick(SETTINGS_GROUND),
    actor: bodyState(
      actor,
      rng.pick([
        'bridging explosively off both heels, trapping the arm and rolling the top fighter over the shoulder line, ending mounted with posture',
        'hips escaping sideways, knee levering under the opponent’s base, momentum carrying him up and over into top position',
      ]),
      'one violent reversal — bottom to top in under a second',
      rng.pick(FACE_STRAINING),
    ),
    target: bodyState(
      target,
      'weight suddenly floating, base gone, rolled onto his back with arms flaring for a frame',
      'toppled sideways, scrambling to re-guard',
      face(rng, target),
    ),
  };
}

export function standupScene(rng: Rng, actor: SceneFighter, target: SceneFighter): SceneDescription {
  return {
    setting: rng.pick(SETTINGS_GROUND),
    actor: bodyState(
      actor,
      'building to a tripod — posting one hand, feet under the hips, peeling the wrist off the waist and rising into stance',
      'technical stand-up, hands returning to guard before fully upright',
      face(rng, actor),
    ),
    target: bodyState(
      target,
      'grip broken, sliding off the hips, rocking back to the knees before rising to follow',
      'losing the control position, resetting',
      face(rng, target),
    ),
  };
}

export function finishScene(
  rng: Rng,
  actor: SceneFighter,
  target: SceneFighter,
  kind: 'ko' | 'tko',
): SceneDescription {
  if (kind === 'ko') {
    return {
      setting: 'the referee diving in between them, waving both arms overhead as the arena erupts',
      actor: bodyState(
        actor,
        rng.pick([
          'follow-through complete, arms dropping to his sides for a beat, then sprinting to the fence and leaping onto it, arms spread wide',
          'standing over the fallen opponent for a frozen half-second, then turning away with both fists raised',
        ]),
        'from violence to celebration in a single beat',
        rng.pick([
          'roaring, veins standing out on the neck, eyes wild with adrenaline',
          'mouth open in a scream of release, eyes finding his corner',
        ]),
      ),
      target: bodyState(target, rng.pick(KO_BODY), rng.pick(MOTION_FALLING), rng.pick(FACE_UNCONSCIOUS)),
    };
  }
  return {
    setting: 'the referee wrapping both arms around the attacker and pulling him off the damaged fighter',
    actor: bodyState(
      actor,
      rng.pick([
        'straddling the downed opponent, punches pouring down until the referee’s grip closes around his shoulders, then rising with arms spread',
        'unloading against the fence, hands a blur, letting the last punch go as the referee steps between them',
      ]),
      'a final flurry with nothing coming back',
      rng.pick(FACE_PREDATOR),
    ),
    target: bodyState(
      target,
      rng.pick([
        'crumpled against the fence, forearms shelled over the face, no longer returning fire, knees drawn up',
        'face-down under the barrage, hand extended weakly toward the referee’s legs, body curled defensively',
      ]),
      'defense collapsed to pure survival',
      rng.pick([
        'eyes squeezed shut behind the gloves, face swollen and resigned',
        'dazed, staring through the referee, unaware the fight is over',
      ]),
    ),
  };
}
