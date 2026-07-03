import type { StrikeKind, SubKind, TakedownKind } from './techniques';
import type { BodyState, SceneDescription } from './types';
import type { UsageTracker } from './variety';

/**
 * Scene builder: converts a fight moment into animator-ready kinematics.
 * Every line is chosen through the UsageTracker, which guarantees a bank
 * never repeats a variant within a fight until every variant has been
 * used — and it's all driven by the fight's seeded RNG, so replaying a
 * seed reproduces identical scene data.
 *
 * Vocabulary is deliberately concrete — joints, weight distribution,
 * contact points, gaze direction, sound — so a renderer can stage the
 * shot straight from the description.
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
  'jaw set, eyes narrowed and locked on the opponent, breathing steady through the nose',
  'calm and unreadable, chin tucked, eyes tracking the opponent’s chest rather than his hands',
  'loose and confident, a slow exhale flaring the nostrils, gaze sweeping feet-hips-shoulders',
  'brow smooth, eyes bright and quick, tongue pressed to the mouthguard in concentration',
  'expression flat as poured concrete, only the eyes moving',
];
const FACE_TIRED = [
  'mouth hanging open, chest heaving, sweat streaming off the brow in a steady drip',
  'lips peeled back around the mouthguard gasping for air, eyelids at half mast',
  'cheeks puffing with every exhale, shoulders rising visibly with each breath, eyes dulled',
  'sucking wind through a slack jaw, face glazed with sweat, blinking it out of his eyes',
  'head dipping between breaths, the mouthguard showing on every long open-mouthed pull of air',
];
const FACE_HURT = [
  'blood tracing from one nostril over the lip, an eye beginning to close, expression grim',
  'face lumped and reddened along the cheekbone, wincing on every movement, jaw clenched',
  'a cut weeping above the eyebrow, red smearing with the sweat, one eye blinking it away',
  'nose swollen and leaking, breathing switched to the mouth, eyes hard with stubbornness',
  'mouse rising under the left eye, lips split, face set in a mask that refuses to show more',
];
const FACE_ROCKED = [
  'eyes glassy and unfocused, pupils drifting to opposite corners, mouth slack',
  'blinking hard and fast trying to reboot, eyes swimming, legs getting no signal',
  'the thousand-yard stare — eyes open but nobody home, mouthguard hanging off the bottom teeth',
  'face gone loose and childlike, eyes rolling to find the ceiling lights, brow slack',
  'a flash of animal panic through unfocused eyes, head wobbling on the neck like a bobblehead',
];
const FACE_PREDATOR = [
  'eyes flared wide and locked onto the hurt man, nostrils open, every feature sharpened',
  'face lit with urgency, teeth bared around the mouthguard, zeroed in on the finish',
  'cold and surgical — no snarl, just total attention, eyes measuring the distance to the chin',
  'a flicker of recognition then pure intent, jaw tight, eyes never leaving the wound',
  'breathing through the teeth, eyes hungry, the face of a man who smells blood in the water',
];
const FACE_UNCONSCIOUS = [
  'eyes rolled white, jaw slack, every muscle of the face released at once',
  'eyes closed, mouthguard half out, features emptied of all tension, almost peaceful',
  'lids fluttering over unseeing eyes, lips parted, face soft as deep sleep',
  'one eye a slit and the other shut, cheek pressed flat to the canvas, expression erased',
];
const FACE_DESPERATE = [
  'eyes pinched shut, face crimson, veins roped at the temple and neck',
  'grimacing around the mouthguard, cheeks compressed, panic flickering at the eye corners',
  'face purpling, eyes bulging at the lights, mouth working without sound',
  'teeth clamped, spit stringing, eyes hunting wildly for the referee or the clock',
];
const FACE_STRAINING = [
  'teeth gritted with effort, brow knotted, breath hissing out in bursts',
  'face taut with exertion, eyes locked on the grip, sweat beading along the hairline',
  'jaw grinding, a low growl leaking out, every feature squeezed toward the center',
  'cheek pressed hard into the opponent, one visible eye burning with concentration',
];

function face(t: UsageTracker, f: SceneFighter): string {
  if (f.cond.rocked) return t.pick('face.rocked', FACE_ROCKED);
  if (f.cond.hurt && f.cond.tired)
    return `${t.pick('face.hurt', FACE_HURT)}; ${t.pick('face.tired', FACE_TIRED)}`;
  if (f.cond.hurt) return t.pick('face.hurt', FACE_HURT);
  if (f.cond.tired) return t.pick('face.tired', FACE_TIRED);
  return t.pick('face.fresh', FACE_FRESH);
}

// ---- Settings ----

const SETTINGS_STANDING = [
  'center of the cage, both fighters in open space under the flat white glare of the overheads',
  'a stride from the fence, the crowd on its feet just beyond the chain-link',
  'in open space just off-center, the canvas already streaked and slick with sweat',
  'near the cage door, coaches’ shouts cutting through the arena noise',
  'mid-cage with the big screen washing them both in shifting light',
  'along the sponsor logos at the cage’s edge, the ring girl’s card still being carried away',
];
const SETTINGS_GROUND = [
  'on the canvas near the center of the cage, bodies printed in sweat beneath them',
  'on the ground tight against the base of the fence, a cutman’s towel visible through the links',
  'flat on the canvas, the referee crouched low and close, watching hands and eyes',
  'in the shadow of the fence, cornermen kneeling at the cage bottom yelling instructions',
  'square in the middle of the octagon logo, nothing around them but open mat',
];
const SETTINGS_CLINCH = [
  'pressed into the fence, bodies locked chest to chest, the chain-link flexing outward',
  'along the cage wall, four hands fighting for the same two grips',
  'jammed into the corner where two fence panels meet, sweat smearing the padding',
  'against the fence directly in front of the judges’ table, close enough to hear the breathing',
];

// ---- Strike kinematics (actor delivering the blow) ----

const STRIKE_BODY: Record<StrikeKind, string[]> = {
  straight: [
    'rear foot pivoting, hips rotating square, rear shoulder extending fully as the fist corkscrews, chin buried behind the lead shoulder',
    'weight transferring rear-to-front through the punch, elbow skimming the ribs until full extension, lead hand framing high by the temple',
    'a piston off the back leg — the kinetic chain rolling ankle to knee to hip to shoulder, whole bodyweight stacked behind the knuckles at impact',
  ],
  hook: [
    'weight snapping onto the lead leg, elbow locked at ninety degrees, torso whipping the arm through a flat horizontal arc, rear heel raised and pivoting',
    'compact rotation from the core, shoulder turning through the target line, fist palm-down and forearm parallel to the floor at impact',
    'lead knee dipping then corkscrewing upward, the punch swinging shoulder-height like a gate slamming, head slipping off the center line as it lands',
  ],
  uppercut: [
    'knees bent, torso dipping low then exploding upward, fist rising vertically between the opponent’s forearms, hips driving through the punch',
    'weight coiled over the rear leg, arm shoveling up from the waist, shoulder finishing beside his own chin, back arched at full extension',
    'a short drop-step inside, spine loading like a spring, the fist traveling barely a foot straight up under the jaw',
  ],
  overhand: [
    'body lunging forward, rear arm looping over the top in a wide arc, rear heel fully off the canvas, torso folded at the finish',
    'launching off the back foot, the arm swung like a hammer over the opponent’s lead shoulder, momentum carrying him a half-step past the target',
    'head dipping off-line as the arm climbs and crashes down at forty-five degrees, knuckles landing behind the temple, body corkscrewed to the knees',
  ],
  bodyshot: [
    'level dropping sharply, lead shoulder dipping, fist buried into the ribs just below the elbow, legs coiled in a deep stance',
    'a crouched rotation, torso twisting to sink the punch under the floating ribs, eyes up and fixed on the opponent’s hands',
    'stepping the lead foot outside, hips sinking, the punch digging upward into the liver with the elbow still bent at impact',
  ],
  legkick: [
    'hips swinging through with the whole body, shin chopping into the outer thigh with a sound like a bat on leather, arms counter-rotating',
    'a skip-step to close, base foot pivoted ninety degrees, shin whipping low and hard through the leg, torso leaned back for balance',
    'no wind-up at all — the leg simply released from the floor, turning over at the hip, shin biting into the muscle just above the knee',
  ],
  headkick: [
    'base leg pivoting fully, hips whipping over the top as the shin arcs at neck height, arms slashing down across the body for counterbalance',
    'the kick rising in one motion off the floor, hip rolling over, shin connecting flush across the jawline, torso laid nearly horizontal',
    'disguised off a step — knee climbing like a front kick, then the hip turning it over at the last instant, instep wrapping around the guard',
  ],
  frontkick: [
    'knee chambered to the chest, hips thrusting forward, ball of the foot snapping into the midsection, arms tight to the body',
    'the lead knee lifting, foot pistoning out at belt height, shoulders leaning back to keep balance through the push',
    'a stabbing teep up the middle, hip fully extended, toes pulled back so the ball of the foot lands like a fist',
  ],
  knee: [
    'hips surging forward, knee spearing upward into the target, back arched, both hands pulling down for collision force',
    'stepping in as the knee rises diagonally across the body, hips fully extended at impact, standing leg up on the ball of the foot',
    'a skip of the back leg, then the knee driving up through the space where the head is folding down, arms framing the collision',
  ],
  elbow: [
    'a short violent rotation at close range, elbow slicing horizontally across the target’s face, forearm folded flat',
    'stepping through, elbow carving a tight downward diagonal, shoulder driving behind the point of bone',
    'the arm folding mid-punch into a spike, torso torquing, the elbow tip drawing a line across the brow',
  ],
};

const STRIKE_MOTION = [
  'explosive and compact, the strike arriving before the guard even twitches',
  'thrown with full commitment, bodyweight transferred completely through the target',
  'short, sharp, and violent — maximum force over minimum distance',
  'fluid and rehearsed, one link of the chain firing after another without a seam',
  'ugly but fast, technique abandoned for pure velocity',
  'timed rather than forced, arriving exactly where the target’s head was always going to be',
];

// ---- Target reactions ----

const HIT_CLEAN = [
  'head snapping back on impact, sweat leaving the scalp in a visible arc, feet planted but weight thrown onto the heels',
  'torso twisting away from the blow, guard splitting open for a half-second at the moment of contact',
  'the mouthguard clacking audibly, a stutter-step backward, hands rising a beat too late',
  'chin jerking sideways, one foot sliding out of stance before the body pulls itself back to center',
  'absorbing it on the forehead at the last instant, neck compressing, eyes blinking through the flash',
];
const HIT_ROCKED = [
  'knees buckling in a single dip, hands dropping to the waist, stumbling a half step back with the hips sagging',
  'sagging against his own skeleton, feet doing a small involuntary shuffle to stay under him, arms pawing at air for range',
  'one leg stiffening straight while the other folds, body tilting like a door off one hinge, glove reaching for the fence',
  'back slapping into the chain-link to stay upright, chin high and exposed, arms crossing instinctively in front of the face',
  'the legs doing the chicken dance — knees knocking inward, feet chattering against the canvas, torso swaying on a loose axis',
];
const FALL_KINEMATICS = [
  'legs cutting out from under him, falling straight back, arms windmilling, the back of the head bouncing once off the canvas',
  'crumpling forward onto both knees, torso folding, one glove touching the canvas before the body tips onto its side',
  'sitting down heavily into the fence, legs splayed in front of him, head lolling back against the chain-link',
  'spinning a quarter turn from the impact and dropping face-first, catching himself on his forearms with his hips still high',
  'legs turning to rope beneath him, descending in a slow spiral, one hand grasping for a fence that is not there',
  'stumbling backward three steps, heel catching, arms flung wide as the canvas comes up to meet his shoulder blades',
  'knees knocking inward, hips dropping first, folding straight down onto his haunches with his gloves dragging down his own chest',
  'lifted clean off his feet, airborne for a beat, landing flat on his back hard enough to bounce both heels off the mat',
];
const KO_BODY = [
  'body going rigid mid-fall, arms locked straight out in the fencing response, unconscious before impact, landing flat with legs folded beneath him',
  'collapsing in stages — knees, hips, shoulders — ending face-down with one arm pinned under his own torso, completely limp',
  'dropping like a marionette with the strings cut, no bracing at all, limbs arranging themselves wherever they land',
  'stiffening board-straight and toppling like felled timber, heels leaving the canvas as the shoulders strike it',
  'folding sideways over one ankle, the body corkscrewing down into a heap, one leg bent impossibly beneath the other',
];
const MOTION_FALLING = [
  'all muscle control gone, gravity doing the rest',
  'dropping with dead weight, no attempt to break the fall',
  'consciousness leaving mid-air, the body finishing the fall on its own',
  'a slow-motion collapse that no part of the nervous system contests',
];
const MOTION_STAGGER = [
  'reeling backward on unsteady legs, the balance system misfiring',
  'wobbling laterally, feet crossing over themselves as the body fights to stay vertical',
  'lurching in a small circle, inner ear and eyes disagreeing about which way is down',
  'swaying at the hips like a mast in weather, feet planted too wide, hands hunting for the range',
];

// ---- Takedown kinematics ----

const TD_ACTOR: Record<TakedownKind, string[]> = {
  double: [
    'an explosive level change, penetration step planted deep between the opponent’s feet, back flat and head up, arms wrapping behind both knees, driving through and lifting',
    'shooting low off the rear leg, shoulder spearing into the midsection, hands clasping behind the thighs, feet churning on contact to finish the drive',
    'changing levels under the punch, ear pressed to the hip, both hands snatching the backs of the knees and yanking them forward as the shoulder drives back',
  ],
  single: [
    'dropping to one knee on the shot, both arms lassoing the lead leg, head pinned tight to the inside of the thigh, rising to a stand while cradling the captured leg',
    'snatching the lead ankle up to his chest, chest crushing down on the knee, hopping the opponent backward one-footed to break his base',
    'running the pipe — leg secured, head driving outside, sweeping his own leg back to chop the standing foot away',
  ],
  trip: [
    'chest-to-chest grip, leg reaping behind the opponent’s calf while the upper body twists him over the blocked leg',
    'foot hooking behind the heel, weight surging forward through the chest to topple him over the trapped foot',
    'stepping across the body and sitting through, hip blocking hip, the opponent levered backward over the outstretched leg',
  ],
  anklepick: [
    'snapping the opponent’s head down with one hand and diving for the ankle with the other, plucking the foot off the canvas in one motion',
    'faking high then dropping low, fingers hooking the Achilles, lifting the ankle to hip height as the opponent hops once and falls',
    'a collar tie dragged down hard, then the free hand shooting to the shoelaces, stealing the foot the moment the weight leaves it',
  ],
  bodylock: [
    'arms cinched around the waist, hips lowered beneath the opponent’s center of gravity, arching and turning to plant him sideways on the canvas',
    'a tight over-under lock, forehead jammed into the jaw, sagging his weight down then corkscrewing the opponent off his feet',
    'hands clasped at the small of the back, hips popping in and under, lifting the opponent’s belt line above his own before the turn and slam',
  ],
  highcrotch: [
    'ducking under the punch, shoulder in the hip crease, one arm threaded deep between the legs, standing tall to elevate the opponent before turning the corner',
    'climbing the position off a deep underhook, lifting the opponent across the shoulders, both of the opponent’s feet leaving the canvas before the slam',
    'snatching the thigh to his chest mid-exchange, chest proud and back straight, walking the dangling opponent two steps before dumping him through the floor',
  ],
};

const TD_TARGET_TAKEN = [
  'hips caught mid-sprawl, legs swept from under him, landing flat on his back with elbows tucking in instinctively',
  'base broken, arms posting toward the canvas on the way down, guard already closing around the top fighter before impact',
  'lifted clear of the floor, legs kicking at nothing, then driven down through the canvas with the attacker’s weight following through',
  'one leg hopping uselessly as the other is carried away, balance surrendered in increments until the mat arrives',
  'wrists fighting for grips that never materialize, spine curling as the shoulder blades touch down, feet already climbing to the attacker’s hips',
];
const TD_TARGET_SPRAWL = [
  'hips shooting back hard, legs flaring wide out of reach, chest crushing down on the attacker’s shoulders, forearm barred across the neck',
  'reading the shot early, feet backpedaling, a stiff palm jamming the attacker’s forehead down into the canvas',
  'the lead leg yanked free at the last instant, weight dropping through the sprawl, hips grinding the shot flat',
  'whipping both legs back and wide, underhooks digging in, riding the attacker’s momentum down into the mat instead of backward',
];
const TD_ACTOR_STUFFED = [
  'stretched face-down under the sprawl, arms still hugging air, hips flattened to the canvas',
  'caught on one knee with the shot dead, head trapped beneath the opponent’s chest, hands sliding off sweat-slick legs',
  'the penetration step dying a foot short, posture broken forward, neck bent under the descending weight',
  'grasping a single ankle that is already pulling away, chin driven into the mat by a crossface',
];

// ---- Submission kinematics ----

interface SubScene {
  actor: string[];
  target: string[];
}

const SUB_SCENES: Record<SubKind, SubScene> = {
  armbar: {
    actor: [
      'swiveled perpendicular across the opponent’s chest, both legs clamped over the torso and face, hips glued beneath the shoulder, back arching as the trapped wrist is dragged to the sternum',
      'falling back with the arm secured, knees pinched around the shoulder, heels digging into ribs and jaw, hips bridging upward against the elbow joint',
      'thighs squeezing the arm like a vise, pinky finger turned to the ceiling, spine extending in a slow arch, head thrown back with the effort',
    ],
    target: [
      'flat on his back, arm fully extended and trapped between the attacker’s thighs, free hand clamped onto his own wrist in a last grip fight, heels scraping the canvas',
      'elbow hyperextending by degrees, body curling toward the trapped arm to relieve the angle, legs kicking over for a stack',
      'hand grip peeled one finger at a time, forearm quivering at full stretch, body rolling desperately in the direction of the thumb',
    ],
  },
  triangle: {
    actor: [
      'on his back with hips elevated, legs figure-foured around the opponent’s neck and trapped arm, hands lacing behind the head and pulling down, calf biting into the carotid',
      'angling off perpendicular, ankle locked behind the knee, thighs crushing inward while the torso curls up into the squeeze',
      'hips climbing the opponent’s spine, the locked triangle tightening a notch with each adjustment, arms wrenching the trapped arm across the throat',
    ],
    target: [
      'posture broken, head dragged down to the attacker’s chest, one arm swallowed inside the leg lock and the other posting on the canvas, face darkening',
      'trying to stack forward, legs driving like a sled push, hands prying at the shin barred across the back of his neck',
      'lifting the attacker clear off the mat in a last-ditch slam attempt, veins standing out at the temples, the choke riding up anyway',
    ],
  },
  rnc: {
    actor: [
      'chest sealed to the opponent’s back, both hooks in behind the thighs, forearm barred under the chin, bicep and forearm scissoring the neck, other hand hidden behind the head, squeezing and arching',
      'flattening the opponent out from back mount, chin over the shoulder, the arm sliding under the jaw millimeter by millimeter until the grip locks',
      'a body triangle cinched around the waist, torso arching away to stretch the opponent long, elbow tip centered under the chin as the squeeze begins',
    ],
    target: [
      'face-down and blanketed, chin jammed to his chest, both hands peeling at the choking forearm, feet pushing blindly against the canvas',
      'seated back into the attacker’s chest, eyes to the ceiling, a two-on-one grip on the strangling wrist as the hooks stretch him out',
      'chin tucked behind his own shoulder, walking his back up the fence in a bid to shuck the weight, fingers digging under the wrist bone',
    ],
  },
  guillotine: {
    actor: [
      'the front headlock cinched, forearm blade under the throat, wrist clasped and elbows drawn skyward, arching backward with the guard closed around the waist',
      'snatching the neck as the opponent ducks in, sitting to guard and extending the hips into the choke, shoulders shrugged to the ears',
      'a high-elbow finish — arm wrapped to the far shoulder, chest swelling into the back of the trapped head, hips walking up the torso',
    ],
    target: [
      'head trapped under the armpit, neck bent forward, one arm inside the guard pushing at the hip, feet driving the body forward to relieve the angle',
      'caught mid-shot with the head down, hands clamping the choking wrist, hopping the legs around to the safe side',
      'stacking his weight down through the attacker’s chest, walking sideways around the pressure, face going from red toward purple',
    ],
  },
  kimura: {
    actor: [
      'the figure-four grip locked on the wrist, chest pinning the shoulder flat, cranking the bent arm up the spine in a slow arc, legs stapling the torso',
      'sitting through to the side, double wrist lock secured, torso rotating to wrench the shoulder past its range',
      'stepping over the head for the finish, the trapped arm levered like a pump handle, whole bodyweight rotating around the shoulder joint',
    ],
    target: [
      'arm bent behind at a worsening angle, shoulder rolling forward against the joint, free hand gripping his own belt line in defense, cheek pressed to the canvas',
      'body flattening as the arm is levered upward, heels drumming for base, the free hand hovering between defense and the tap',
      'rolling through in the direction of the crank to save the shoulder, wrist grip failing knuckle by knuckle',
    ],
  },
  armtriangle: {
    actor: [
      'the head-and-arm grip locked, his own shoulder crushing the trapped arm across the carotid, sliding off the mount to the choking side, legs sprawled wide and hips driving low',
      'cheek pressed to the canvas past the opponent’s trapped shoulder, hands palm-to-palm, squeezing while the toes drive the body forward',
      'chest walking incrementally toward the far hip, the strangle tightening with each inch, breath hissing out in a controlled leak',
    ],
    target: [
      'pinned under the side pressure, his own bicep crushed against his neck, eyes bulging, free hand slapping at the attacker’s hip for space',
      'the trapped arm buckled across his throat, legs bridging in short spasms, color draining out of the face',
      'trying to answer the phone — hand fighting to his own ear for relief that will not come, legs swimming without traction',
    ],
  },
  darce: {
    actor: [
      'the arm threaded deep under neck and armpit, hands locked in a tight figure-four, sprawled with chest weight through the shoulders, squeezing while the legs walk around',
      'rolling the opponent onto his shoulder with the choke locked, knees pinched around the head-and-arm bundle, back rounding to finish',
      'gable grip buried to the elbow, forehead planted on the canvas for leverage, the coil ratcheting closed with each exhale',
    ],
    target: [
      'balled up on his side, neck and arm wrapped in the coil, free hand tugging uselessly at the locked wrist, legs scissoring for an exit',
      'shoulder pinned under his own trapped arm, face compressed and darkening, feet scrambling against the fence for angle',
      'bridging into the choke to make space and finding none, the free arm flailing at the attacker’s locked hands',
    ],
  },
};

const SUB_TAP = [
  'the free hand rising and slapping the attacker’s body twice, fast and unmistakable',
  'a palm hammering the canvas in rapid taps, the whole body going slack the instant the hold releases',
  'fingers fluttering against the attacker’s forearm — half tap, half surrender — before the referee dives in',
  'a single emphatic slap on the shoulder, then both hands open and empty in the air',
];

// ---- Builders ----

function bodyState(f: SceneFighter, body: string, motion: string, faceStr: string): BodyState {
  return { fighterId: f.id, name: f.name, body, motion, face: faceStr };
}

export type StrikeSeverity = 'rocked' | 'knockdown';

export function strikeScene(
  t: UsageTracker,
  actor: SceneFighter,
  target: SceneFighter,
  kind: StrikeKind,
  severity: StrikeSeverity,
): SceneDescription {
  const targetBody =
    severity === 'knockdown' ? t.pick('fall', FALL_KINEMATICS) : t.pick('hit.rocked', HIT_ROCKED);
  const targetMotion =
    severity === 'knockdown' ? t.pick('motion.falling', MOTION_FALLING) : t.pick('motion.stagger', MOTION_STAGGER);
  return {
    setting: t.pick('setting.standing', SETTINGS_STANDING),
    actor: bodyState(
      actor,
      t.pick(`strike.${kind}`, STRIKE_BODY[kind]),
      t.pick('strike.motion', STRIKE_MOTION),
      t.pick('face.predator', FACE_PREDATOR),
    ),
    target: bodyState(target, targetBody, targetMotion, t.pick('face.rocked', FACE_ROCKED)),
  };
}

export function cleanHitScene(
  t: UsageTracker,
  actor: SceneFighter,
  target: SceneFighter,
  kind: StrikeKind,
): SceneDescription {
  return {
    setting: t.pick('setting.standing', SETTINGS_STANDING),
    actor: bodyState(
      actor,
      t.pick(`strike.${kind}`, STRIKE_BODY[kind]),
      t.pick('strike.motion', STRIKE_MOTION),
      face(t, actor),
    ),
    target: bodyState(target, t.pick('hit.clean', HIT_CLEAN), 'absorbing the shot and resetting the guard', face(t, target)),
  };
}

export function takedownScene(
  t: UsageTracker,
  actor: SceneFighter,
  target: SceneFighter,
  kind: TakedownKind,
  completed: boolean,
): SceneDescription {
  if (completed) {
    return {
      setting: t.pick('setting.standing', SETTINGS_STANDING),
      actor: bodyState(
        actor,
        t.pick(`td.${kind}`, TD_ACTOR[kind]),
        'one continuous chain: level change, contact, drive, finish',
        t.pick('face.straining', FACE_STRAINING),
      ),
      target: bodyState(
        target,
        t.pick('td.taken', TD_TARGET_TAKEN),
        'balance stolen mid-step, falling with the drive',
        face(t, target),
      ),
    };
  }
  return {
    setting: t.pick('setting.standing', SETTINGS_STANDING),
    actor: bodyState(
      actor,
      t.pick('td.stuffed', TD_ACTOR_STUFFED),
      'forward drive dying against the sprawl',
      t.pick('face.straining', FACE_STRAINING),
    ),
    target: bodyState(
      target,
      t.pick('td.sprawl', TD_TARGET_SPRAWL),
      'reacting in a blink — hips back, weight down',
      face(t, target),
    ),
  };
}

export type SubPhase = 'locked' | 'escape' | 'tap';

export function submissionScene(
  t: UsageTracker,
  actor: SceneFighter,
  target: SceneFighter,
  kind: SubKind,
  phase: SubPhase,
): SceneDescription {
  const bank = SUB_SCENES[kind];
  const targetBase = t.pick(`sub.${kind}.target`, bank.target);
  const targetBody = phase === 'tap' ? `${targetBase} — ${t.pick('sub.tap', SUB_TAP)}` : targetBase;
  const targetMotion =
    phase === 'escape'
      ? 'creating an inch of space and sliding free, scrambling the moment the grip breaks'
      : phase === 'tap'
        ? 'resistance collapsing all at once'
        : 'every muscle recruited against the hold';
  const targetFace = phase === 'escape' ? face(t, target) : t.pick('face.desperate', FACE_DESPERATE);
  return {
    setting: t.pick('setting.ground', SETTINGS_GROUND),
    actor: bodyState(
      actor,
      t.pick(`sub.${kind}.actor`, bank.actor),
      'constricting by degrees, re-gripping with each exhale',
      t.pick('face.straining', FACE_STRAINING),
    ),
    target: bodyState(target, targetBody, targetMotion, targetFace),
  };
}

const GNP_ACTOR = [
  'postured tall in the guard, knees pinning the hips, torso rising and twisting with each downward punch, fists falling like pistons',
  'riding half guard with head low, short elbows carving from the shoulder, weight never leaving the opponent’s chest',
  'one hand posting on the sternum while the other cocks back to the ceiling, hips heavy, punches dropping straight down the centerline',
  'knee slid up to the armpit, torso levered over the trapped head, alternating hammerfists swinging from the elbow',
];
const GNP_TARGET = [
  'flat on his back, forearms crossed over the face, hips bumping to unbalance the top fighter, knees climbing for guard',
  'turtled to one side, glove and forearm shelled around the head, eyes peeking between the gaps for the referee',
  'wrists snatching at the falling arms, head rolling with the punches to bleed off their force, feet hunting for the fence',
  'bridging and turning into the pressure, one arm framing the throat, absorbing shots on the crown to buy the escape',
];

export function groundStrikesScene(t: UsageTracker, actor: SceneFighter, target: SceneFighter): SceneDescription {
  return {
    setting: t.pick('setting.ground', SETTINGS_GROUND),
    actor: bodyState(actor, t.pick('gnp.actor', GNP_ACTOR), 'rhythmic and heavy, each shot loaded with bodyweight', t.pick('face.predator', FACE_PREDATOR)),
    target: bodyState(target, t.pick('gnp.target', GNP_TARGET), 'absorbing and deflecting, hunting the hip escape', face(t, target)),
  };
}

const CLINCH_ACTOR = [
  'underhook cinched deep, forehead pressed under the jaw, hips square and driving, short uppercuts and knees churning inside the tie-up',
  'collar tie and wrist control, shoulder crushed into the opponent’s chest, feet staggered and walking him flat into the fence',
  'double overhooks clamped, chin dug into the shoulder, thigh wedged between the opponent’s legs to kill the hip escape',
  'head pinned to the collarbone, one hand ripping the far arm across, knees thumping into the thigh on a metronome',
];
const CLINCH_TARGET = [
  'back bowed into the chain-link, hips pushed away to deny the takedown, elbows tight, hand-fighting for the underhook',
  'flattened against the fence, chin down, absorbing knees on the thighs while his feet circle for the exit',
  'framing at the neck and bicep with both forearms, spine grinding against the links, trying to create an arm’s length of daylight',
  'weathering the pressure with short shoulder shrugs, palms stapled to the hips in front of him, waiting for the break',
];

export function clinchScene(t: UsageTracker, actor: SceneFighter, target: SceneFighter): SceneDescription {
  return {
    setting: t.pick('setting.clinch', SETTINGS_CLINCH),
    actor: bodyState(actor, t.pick('clinch.actor', CLINCH_ACTOR), 'grinding, constant forward pressure', face(t, actor)),
    target: bodyState(target, t.pick('clinch.target', CLINCH_TARGET), 'defending, working to reverse the position', face(t, target)),
  };
}

const SWEEP_ACTOR = [
  'bridging explosively off both heels, trapping the arm and rolling the top fighter over the shoulder line, ending mounted with posture',
  'hips escaping sideways, a knee levering under the opponent’s base, momentum carrying him up and over into top position',
  'a butterfly hook elevating the opponent’s whole hip, the world flipping as bottom becomes top in one motion',
  'catching the posting wrist mid-punch and rolling with it, using the opponent’s own weight as the engine of the reversal',
];

export function sweepScene(t: UsageTracker, actor: SceneFighter, target: SceneFighter): SceneDescription {
  return {
    setting: t.pick('setting.ground', SETTINGS_GROUND),
    actor: bodyState(actor, t.pick('sweep.actor', SWEEP_ACTOR), 'one violent reversal — bottom to top inside a second', t.pick('face.straining', FACE_STRAINING)),
    target: bodyState(
      target,
      'weight suddenly floating, base gone, rolled onto his back with arms flaring for a frame',
      'toppled sideways, scrambling to re-guard',
      face(t, target),
    ),
  };
}

const STANDUP_ACTOR = [
  'building to a tripod — one hand posted, feet walking under the hips, peeling the wrist off his waist and rising into stance',
  'exploding into a scramble off a missed punch, knees to feet in one beat, hands already back at his chin',
  'wall-walking up the fence, shoulder blades dragging the links, hips swiveling out as the feet find their base',
  'kicking the top fighter’s hips away with both feet and back-rolling up to standing in the space it buys',
];

export function standupScene(t: UsageTracker, actor: SceneFighter, target: SceneFighter): SceneDescription {
  return {
    setting: t.pick('setting.ground', SETTINGS_GROUND),
    actor: bodyState(actor, t.pick('standup.actor', STANDUP_ACTOR), 'technical stand-up, guard restored before fully upright', face(t, actor)),
    target: bodyState(
      target,
      'grip broken, sliding off the hips, rocking back to his knees before rising to follow',
      'the control position dissolving, resetting to the feet',
      face(t, target),
    ),
  };
}

const KO_ACTOR_BODY = [
  'follow-through complete, arms dropping to his sides for one beat, then sprinting to the fence and leaping onto it, arms spread wide',
  'standing over the fallen man for a frozen half-second, fist still cocked, then turning away with both arms raised',
  'walking off before the body lands, back already turned, one finger raised to the crowd',
  'dropping to both knees mid-cage, head tilted back to the lights, arms opening as the arena detonates',
];
const KO_ACTOR_FACE = [
  'roaring, veins roped on the neck, eyes wild with adrenaline',
  'mouth open in a scream of release, eyes searching out his corner',
  'stone calm amid the chaos, a single exhale, eyes closing for a moment',
  'disbelief melting into joy, eyebrows up, laughing at the noise',
];
const TKO_ACTOR_BODY = [
  'straddling the downed man, punches pouring down until the referee’s arms close around his shoulders, then rising with fists spread',
  'unloading against the fence, hands a blur, the last punch pulled mid-flight as the referee dives between them',
  'hammerfists cascading from full mount, torso twisting with each one, until the tap on his back stops the arm mid-cock',
  'a knee pinning the chest, punches thudding into the guard like an axe into wood, until the referee’s grip drags him backward off the finish',
];
const TKO_TARGET_BODY = [
  'crumpled against the fence, forearms shelled over his face, no longer punching back, knees drawn up to his chest',
  'face-down under the storm, one hand extended weakly toward the referee’s legs, body curled into itself',
  'rolling to his side with both gloves welded to his temples, absorbing without answering, eyes gone somewhere else',
  'flattened out with arms wrapped over the back of his own head, fingers laced, taking punches on the knuckles and elbows',
];
const TKO_TARGET_FACE = [
  'eyes squeezed shut behind the gloves, face swollen and resigned',
  'dazed and staring through the referee, unaware the fight is over',
  'blinking up at the lights through a mask of blood, relief arriving before the pain',
  'mouthguard gone, lips moving in protest the body cannot back up',
];

export function finishScene(
  t: UsageTracker,
  actor: SceneFighter,
  target: SceneFighter,
  kind: 'ko' | 'tko',
): SceneDescription {
  if (kind === 'ko') {
    return {
      setting: 'the referee diving in between them, waving both arms overhead as the arena erupts',
      actor: bodyState(actor, t.pick('ko.actor', KO_ACTOR_BODY), 'from violence to celebration in a single beat', t.pick('ko.face', KO_ACTOR_FACE)),
      target: bodyState(target, t.pick('ko.body', KO_BODY), t.pick('motion.falling', MOTION_FALLING), t.pick('face.unconscious', FACE_UNCONSCIOUS)),
    };
  }
  return {
    setting: 'the referee wrapping both arms around the attacker and hauling him off the beaten fighter',
    actor: bodyState(actor, t.pick('tko.actor', TKO_ACTOR_BODY), 'a final flurry with nothing coming back', t.pick('face.predator', FACE_PREDATOR)),
    target: bodyState(target, t.pick('tko.target', TKO_TARGET_BODY), 'defense collapsed to pure survival', t.pick('tko.face', TKO_TARGET_FACE)),
  };
}
