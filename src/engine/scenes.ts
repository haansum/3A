import { pron, type PronounKey } from './pronouns';
import type { SlamKind, StrikeKind, SubKind, TakedownKind } from './techniques';
import type { BodyState, FinishTier, SceneDescription } from './types';
import type { UsageTracker } from './variety';

/**
 * Scene builder: converts a fight moment into animator-ready kinematics
 * that obey the Animation Bible (docs/animation-bible.md):
 *
 * - Law 1: falls conserve pre-KO momentum — the ghost of the last
 *   intent is visible in how the body drops
 * - Eyes never close peacefully; they go fixed, dilated, empty
 * - Fencing response fires on the jolt, asymmetric, one side worse
 * - One twitching extremity (finger for KOs, foot for chokes), never several
 * - Chokes melt (extremities first), KOs crash (instant shutdown)
 * - Wake-ups arrive in involuntary stages with confusion
 *
 * Every line is chosen through the UsageTracker (no repeats within a
 * fight until a bank is exhausted) and rendered with the subject
 * fighter's pronouns. All of it is deterministic per seed.
 */

export interface SceneCondition {
  tired: boolean;
  hurt: boolean;
  rocked: boolean;
}

export interface SceneFighter {
  id: string;
  name: string;
  p: PronounKey;
  cond: SceneCondition;
}

/** What the victim's body was doing when the lights went out (Law 1). */
export type Momentum = 'advancing' | 'retreating' | 'shooting' | 'flat';

// ---- Faces ----

const FACE_FRESH = [
  'jaw set, eyes narrowed and locked on the opponent, breathing steady through the nose',
  'calm and unreadable, chin tucked, eyes tracking the opponent’s chest rather than the hands',
  'loose and confident, a slow exhale flaring the nostrils, gaze sweeping feet-hips-shoulders',
  'brow smooth, eyes bright and quick, tongue pressed to the mouthguard in concentration',
  'expression flat as poured concrete, only the eyes moving',
];
const FACE_TIRED = [
  'mouth hanging open, chest heaving, sweat streaming off the brow in a steady drip',
  'lips peeled back around the mouthguard gasping for air, eyelids at half mast',
  'cheeks puffing with every exhale, shoulders rising visibly with each breath, eyes dulled',
  'sucking wind through a slack jaw, face glazed with sweat, blinking it out of [his] eyes',
  'head dipping between breaths, the mouthguard showing on every long open-mouthed pull of air',
];
const FACE_HURT = [
  'blood tracing from one nostril over the lip, an eye beginning to close, expression grim',
  'face lumped and reddened along the cheekbone, wincing on every movement, jaw clenched',
  'a cut weeping above the eyebrow, red smearing with the sweat, one eye blinking it away',
  'nose swollen and leaking, breathing switched to the mouth, eyes hard with stubbornness',
  'a mouse rising under the left eye, lips split, face set in a mask that refuses to show more',
];
const FACE_ROCKED = [
  'eyes glassy and unfocused, pupils drifting to opposite corners, mouth slack',
  'blinking hard and fast trying to reboot, eyes swimming, legs getting no signal',
  'the thousand-yard stare — eyes open but nobody home, mouthguard hanging off the bottom teeth',
  'face gone loose and childlike, eyes rolling up to find the ceiling lights, brow slack',
  'a flash of animal panic through unfocused eyes, head wobbling on the neck like a bobblehead',
];
const FACE_PREDATOR = [
  'eyes flared wide and locked onto the hurt opponent, nostrils open, every feature sharpened',
  'face lit with urgency, teeth bared around the mouthguard, zeroed in on the finish',
  'cold and surgical — no snarl, just total attention, eyes measuring the distance to the chin',
  'a flicker of recognition then pure intent, jaw tight, eyes never leaving the wound',
  'breathing through the teeth, eyes hungry — the face of a fighter who smells blood in the water',
];
// Animation Bible: the eyes do NOT close. Fixed, dilated, lights on, nobody home.
const FACE_UNCONSCIOUS = [
  'eyes open and rolled back to white slivers, jaw slack, every muscle of the face released at once',
  'eyes fixed and dilated at nothing, glazed over, mouthguard half out — lights on, nobody home',
  'lids fluttering over unseeing eyes that track nothing, lips parted, expression erased',
  'one eye a slit showing white, the other staring blankly past the referee, cheek flat to the canvas',
  'eyes glazed and unmoving even as the winner crosses [his] field of vision — total vacancy',
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
  'along the sponsor logos at the cage’s edge, the whole front row screaming for blood',
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
const SETTINGS_AFTERMATH = [
  'the arena gone strangely quiet for a heartbeat before the roar detonates',
  'the referee kneeling over the fallen fighter, one hand hovering, waving the corner in',
  'cageside doctors already up off their stools, the crowd craning to see the canvas',
  'the winner’s corner spilling toward the cage door while the referee guards the fallen fighter',
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
    'weight coiled over the rear leg, arm shoveling up from the waist, shoulder finishing beside [his] own chin, back arched at full extension',
    'a short drop-step inside, spine loading like a spring, the fist traveling barely a foot straight up under the jaw',
  ],
  overhand: [
    'body lunging forward, rear arm looping over the top in a wide arc, rear heel fully off the canvas, torso folded at the finish',
    'launching off the back foot, the arm swung like a hammer over the opponent’s lead shoulder, momentum carrying [him] a half-step past the target',
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
  'sagging against [his] own skeleton, feet doing a small involuntary shuffle to stay underneath, arms pawing at air for range',
  'one leg stiffening straight while the other folds, body tilting like a door off one hinge, glove reaching for the fence',
  'back slapping into the chain-link to stay upright, chin high and exposed, arms crossing instinctively in front of the face',
  'the legs going to jelly — knees knocking inward, feet chattering against the canvas, torso swaying on a loose axis',
];
const HIT_BODYFOLD = [
  'folding in half around the glove, mouth open in a silent O, sinking to one knee with a forearm pressed to the ribs',
  'all the air leaving in one audible "OOF" — knees buckling, torso caving forward over the point of impact, glove clutching the liver',
  'freezing for a full beat as the liver shot registers, face going white, then crumpling sideways with knees drawn up',
  'staggering backward hugging the midsection, spine curling forward, legs suddenly unable to hold the weight upright',
];
const HIT_LEGBUCKLE = [
  'the lead leg swept off the floor mid-stance, hips dropping sideways, hand slapping the canvas to catch the fall',
  'the thigh seizing on impact, leg refusing weight, a lurching hop to the fence dragging the dead limb',
  'stance collapsing inward as the calf gives, knee kissing the canvas before [he] hobbles back upright',
];

// ---- Law 1: falls conserve pre-KO momentum ----

const FALLS: Record<Momentum, string[]> = {
  advancing: [
    'the punch [he] was throwing keeps traveling as dead mass, dragging the body after it — falling forward through the target with the ghost of the swing still visible',
    'the hook’s torque with no brakes left: the torso keeps rotating past its range and corkscrews [him] face-down into the canvas',
    'the forward step completes with no balance behind it — weight committing too far, a headlong pitch onto the forearms with the hips still driving',
    'mid-combination shutdown: the second punch dies half-thrown, the arm drifting past the target as the body follows it down and forward',
  ],
  retreating: [
    'legs cutting out mid-backstep, falling straight back, arms windmilling, the back of the head bouncing once off the canvas',
    'the retreat becoming the fall — heels crossing, weight already moving backward with nothing to catch it, shoulder blades slapping the mat',
    'stumbling backward three steps, heel catching, arms flung wide as the canvas comes up to meet the shoulder blades',
    'sitting down heavily into the fence [he] was backing toward, legs splayed in front, head lolling back against the chain-link',
  ],
  shooting: [
    'the takedown dying mid-shot — the penetration step finishes on inertia and [he] slides face-down along the line of the shot, arms still wrapped around nothing',
    'shutdown at the level change: the dive continues without a pilot, chin plowing the canvas, hips settling last',
    'the shot’s forward drive spending itself into the mat, body stretched long and flat, hands open where the grip used to be',
  ],
  flat: [
    'legs turning to rope beneath [him], descending in a slow spiral, one hand grasping for a fence that is not there',
    'knees knocking inward, hips dropping first, folding straight down onto the haunches with gloves dragging down [his] own chest',
    'crumpling onto both knees, torso folding, one glove touching the canvas before the body tips onto its side',
    'lifted clean off [his] feet, airborne for a beat, landing flat on the back hard enough to bounce both heels off the mat',
  ],
};

// Bible: the stiff KO is a rigid timber fall preserving the pre-KO pose
const FALLS_STIFF = [
  'going rigid mid-fall, arms locked straight out in the fencing response, unconscious before impact — toppling like felled timber around the ankles',
  'stiffening board-straight and tipping over as one piece, the pre-KO guard frozen in place, heels leaving the canvas as the shoulders strike it',
  'legs locking straight instead of buckling — a statue pushed off its base, the whole body rotating around the feet to the floor',
];
// Bible: the deep KO melts — cascading collapse into a heap
const FALLS_DEEP = [
  'every ounce of muscle tone vanishing at once — knees buckling inward first, then hips, then the torso folding, a cascading collapse into a compact heap',
  'dropping like a marionette with the strings cut, no bracing at all, limbs arranging themselves wherever they land, piled on [himself]',
  'melting down the opponent’s body, maintaining contact the whole way like liquid, ending in a crumpled pile at [his] feet',
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
    'snatching the lead ankle up to [his] chest, chest crushing down on the knee, hopping the opponent backward one-footed to break the base',
    'running the pipe — leg secured, head driving outside, sweeping [his] own leg back to chop the standing foot away',
  ],
  trip: [
    'chest-to-chest grip, leg reaping behind the opponent’s calf while the upper body twists them over the blocked leg',
    'foot hooking behind the heel, weight surging forward through the chest to topple the opponent over the trapped foot',
    'stepping across the body and sitting through, hip blocking hip, the opponent levered backward over the outstretched leg',
  ],
  anklepick: [
    'snapping the opponent’s head down with one hand and diving for the ankle with the other, plucking the foot off the canvas in one motion',
    'faking high then dropping low, fingers hooking the Achilles, lifting the ankle to hip height as the opponent hops once and falls',
    'a collar tie dragged down hard, then the free hand shooting to the shoelaces, stealing the foot the moment the weight leaves it',
  ],
  bodylock: [
    'arms cinched around the waist, hips lowered beneath the opponent’s center of gravity, arching and turning to plant them sideways on the canvas',
    'a tight over-under lock, forehead jammed into the jaw, sagging the weight down then corkscrewing the opponent off their feet',
    'hands clasped at the small of the back, hips popping in and under, lifting the opponent’s belt line above [his] own before the turn and slam',
  ],
  highcrotch: [
    'ducking under the punch, shoulder in the hip crease, one arm threaded deep between the legs, standing tall to elevate the opponent before turning the corner',
    'climbing the position off a deep underhook, lifting the opponent across the shoulders, both of the opponent’s feet leaving the canvas before the slam',
    'snatching the thigh to [his] chest mid-exchange, chest proud and back straight, walking the dangling opponent two steps before dumping them through the floor',
  ],
};

const TD_TARGET_TAKEN = [
  'hips caught mid-sprawl, legs swept from under [him], landing flat on the back with elbows tucking in instinctively',
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

// ---- Slam KOs (Animation Bible, Part 3) ----

interface SlamBank {
  actor: string[];
  /** Victim still fighting it (Spring) */
  spring: string[];
  /** Victim already out or gone limp (Water) */
  water: string[];
  aftermath: string[];
}

const SLAM_SCENES: Record<SlamKind, SlamBank> = {
  spike: {
    actor: [
      'holding the opponent fully inverted for one dreadful beat — the crowd sees it coming — then dropping to both knees and spiking the crown straight down through the canvas',
      'climbing the lift until the opponent hangs upside down against [his] chest, then sitting out violently, driving all of their combined weight through the point of the skull',
    ],
    spring: [
      'inverted and fighting it — core crunched, chin tucked hard, hands clawing at the attacker’s thighs for any brake — right up until the impact overwhelms everything',
      'legs scissoring in the air, neck a rigid pillar of resistance, one arm reaching uselessly for the canvas that arrives all at once',
    ],
    water: [
      'hanging inverted with zero resistance, arms dangling and swaying against the attacker’s shins, head sagging free on the neck — dead weight waiting for gravity',
      'limp through the whole carry, spine a loose chain, the head simply the lowest link when the drop comes',
    ],
    aftermath: [
      'the accordion: shoulders shrugged violently up toward the ears as the torso’s mass telescopes down onto the stopped head, then the slow unfolding from inverted to a sideways sprawl, shoulders rolled hard toward the chin in a permanent hunch',
      'the spine compressing on itself for a sickening beat before the body topples sideways and settles into a broken-doll posture, neck at an angle no conscious person would allow',
    ],
  },
  powerbomb: {
    actor: [
      'hoisting the opponent high overhead — a full display of the strength gap — then driving them down flat with [his] whole body following through the impact',
      'the lift reaching full extension, a half-step forward for angle, then the pancake: throwing the opponent’s back through the canvas with both arms',
    ],
    spring: [
      'elevated and panicking — legs bicycling in the air, hands pushing at the attacker’s head, every muscle firing against a fall that has already been decided',
      'kicking at altitude, one hand snatching a collar grip that tears free, core crunched right up until the flat back impact blasts it loose',
    ],
    water: [
      'limbs hanging like a marionette with cut strings through the whole lift, head rolled back, already gone before the slam adds the exclamation point',
      'pouring over the attacker’s shoulder with no tension anywhere, the lift carrying pure dead weight to altitude',
    ],
    aftermath: [
      'the pancake — full flat-back impact, limbs bouncing, then the head snapping back off the mat once (the second impact is the one that matters) before the full starfish jolt and the total melt: no stiffening, straight to dead weight',
      'body flattening completely on impact, one bounce of the skull, all four limbs snapping outward in the starfish before everything goes liquid at once',
    ],
  },
  suplex: {
    actor: [
      'hips popping under the body lock, arching backward in one motion and launching the opponent overhead, following the arc down with [his] own bridge',
      'the over-under grip sagging low, then exploding upward and back — the opponent’s feet tracing a full arc across the arena lights',
    ],
    spring: [
      'arcing backward through the air in a rigid C — back arched, head trailing, arms grabbing at the attacker’s wrists all the way over',
      'twisting mid-arc trying to turn into the fall, which only changes the angle the neck takes into the canvas',
    ],
    water: [
      'a loose ragdoll through the arc, limbs trailing the torso like streamers, landing wherever physics decides',
      'the body following the throw with no shape at all, folding over itself as the upper back leads the way down',
    ],
    aftermath: [
      'the involuntary bridge — for two beats only the shoulders and feet touch the mat, an arch held by momentum and not muscle — before it collapses flat into the Void: eyes fixed open on the rafters, abs heaving, GASPING for the air the compressed diaphragm cannot find',
      'landing on the upper trapezius with the legs still overhead, holding a broken arch for a heartbeat, then flattening — eyes locked on one point in the lights, breath coming in ragged crow-hops instead of a snore',
    ],
  },
};

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
      'flat on [his] back, arm fully extended and trapped between the attacker’s thighs, free hand clamped onto [his] own wrist in a last grip fight, heels scraping the canvas',
      'elbow hyperextending by degrees, body curling toward the trapped arm to relieve the angle, legs kicking over for a stack',
      'the hand grip peeled one finger at a time, forearm quivering at full stretch, body rolling desperately in the direction of the thumb',
    ],
  },
  triangle: {
    actor: [
      'on [his] back with hips elevated, legs figure-foured around the opponent’s neck and trapped arm, hands lacing behind the head and pulling down, calf biting into the carotid',
      'angling off perpendicular, ankle locked behind the knee, thighs crushing inward while the torso curls up into the squeeze',
      'hips climbing the opponent’s spine, the locked triangle tightening a notch with each adjustment, arms wrenching the trapped arm across the throat',
    ],
    target: [
      'posture broken, head dragged down to the attacker’s chest, one arm swallowed inside the leg lock and the other posting on the canvas, face darkening',
      'trying to stack forward, legs driving like a sled push, hands prying at the shin barred across the back of [his] neck',
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
      'face-down and blanketed, chin jammed to [his] chest, both hands peeling at the choking forearm, feet pushing blindly against the canvas',
      'seated back into the attacker’s chest, eyes to the ceiling, a two-on-one grip on the strangling wrist as the hooks stretch [him] out',
      'chin tucked behind [his] own shoulder, walking [his] back up the fence in a bid to shuck the weight, fingers digging under the wrist bone',
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
      'stacking [his] weight down through the attacker’s chest, walking sideways around the pressure, face going from red toward purple',
    ],
  },
  kimura: {
    actor: [
      'the figure-four grip locked on the wrist, chest pinning the shoulder flat, cranking the bent arm up the spine in a slow arc, legs stapling the torso',
      'sitting through to the side, double wrist lock secured, torso rotating to wrench the shoulder past its range',
      'stepping over the head for the finish, the trapped arm levered like a pump handle, whole bodyweight rotating around the shoulder joint',
    ],
    target: [
      'arm bent behind at a worsening angle, shoulder rolling forward against the joint, free hand gripping [his] own belt line in defense, cheek pressed to the canvas',
      'body flattening as the arm is levered upward, heels drumming for base, the free hand hovering between defense and the tap',
      'rolling through in the direction of the crank to save the shoulder, wrist grip failing knuckle by knuckle',
    ],
  },
  armtriangle: {
    actor: [
      'the head-and-arm grip locked, [his] own shoulder crushing the trapped arm across the carotid, sliding off the mount to the choking side, legs sprawled wide and hips driving low',
      'cheek pressed to the canvas past the opponent’s trapped shoulder, hands palm-to-palm, squeezing while the toes drive the body forward',
      'chest walking incrementally toward the far hip, the strangle tightening with each inch, breath hissing out in a controlled leak',
    ],
    target: [
      'pinned under the side pressure, [his] own bicep crushed against the neck, eyes bulging, free hand slapping at the attacker’s hip for space',
      'the trapped arm buckled across the throat, legs bridging in short spasms, color draining out of the face',
      'trying to answer the phone — hand fighting to [his] own ear for relief that will not come, legs swimming without traction',
    ],
  },
  darce: {
    actor: [
      'the arm threaded deep under neck and armpit, hands locked in a tight figure-four, sprawled with chest weight through the shoulders, squeezing while the legs walk around',
      'rolling the opponent onto [his] shoulder with the choke locked, knees pinched around the head-and-arm bundle, back rounding to finish',
      'gable grip buried to the elbow, forehead planted on the canvas for leverage, the coil ratcheting closed with each exhale',
    ],
    target: [
      'balled up on [his] side, neck and arm wrapped in the coil, free hand tugging uselessly at the locked wrist, legs scissoring for an exit',
      'shoulder pinned under [his] own trapped arm, face compressed and darkening, feet scrambling against the fence for angle',
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

// The wet melt (Animation Bible, Part 2, Phase 2) — refusing to tap
const SUB_MELT = [
  'the clawing fingers going flat, becoming brushes, then sliding off the choking arm and dropping away — the hands are the first thing to die',
  'the struggle losing its rhythm — bridges getting shallower, kicks slowing to drags — then the spine liquefying in a wave from the hips up, head lolling onto the attacker’s shoulder',
  'grip failing in stages: hooked fingers, then flat palms, then nothing — the arms falling to the canvas as the eyes drift and slowly cross',
  '[his] whole weight arriving on the attacker at once as the last of the tone drains out, legs stretching long and going still, toes already beginning to point',
];

// ---- Aftermath banks (the agonal state, by tier) ----

const AFTERMATH_STIFF = [
  'the jolt fires the instant the head meets canvas — arms snapping outward, fingers splayed, one side locked worse than the other — then the slow asymmetric stiffening: shoulders rolling inward toward the chin, wrists curling, legs rigid, the whole silhouette bent at wrong angles',
  'fencing response, textbook and horrifying: one arm locked straight toward the lights, the other curled against the chest, held for a breathless beat before the body begins its ugly settle — an arm trapped under the torso, head at an angle no one conscious would tolerate — and the first rattling snore climbs out of [his] throat',
  'the body seizing into a mannequin pose, one side crushed tighter than the other, then releasing by degrees into the hollow settle while the chest starts heaving in hard mechanical pulls — and one index finger begins a tiny rhythmic twitch that no one who sees it will forget',
];
const AFTERMATH_DEEP = [
  'no fencing response — the brainstem is too scrambled even for reflex. The body simply finishes melting into a compact heap, limbs overlapping wherever they landed, and the snoring starts IMMEDIATELY: deep, wet, rattling breaths that fill the stunned silence',
  'straight past the stiffening into the deepest shutdown — a crumpled pile against the canvas, one leg folded impossibly beneath the other, chest crunching in sharp heaves as the agonal snore rolls out within seconds',
  'the heap barely moves — no twitch, no seize, just the heavy automatic breathing of a body running on brainstem autopilot, drool starting at the corner of the mouth while the referee screams for the doctor',
];
const AFTERMATH_FLASH = [
  'not out cold — worse, half in: eyes open and searching, hands pawing the canvas to find which way is up. [He] plants a glove, pushes to a knee, and the leg simply is not there — a wobbling, ankle-rolling stagger back down as the referee dives in',
  'the jelly-leg dance: up at the count of instinct, knees chattering inward, one hand grabbing the fence like a drunk grabbing a railing, eyes blinking hard trying to clear cobwebs that will not clear — the referee wraps [him] up mid-stumble',
  'trying to walk it off on legs that answer half a second late, weaving a small circle, smiling the embarrassed smile of a fighter whose body has stopped taking calls — waved off before [he] falls a second time',
];
const AFTERMATH_SLEEP = [
  'the choke-specific signature, unmistakable: legs stretched stiff, feet pointed hard with the toes curled down tight in plantar flexion, and a rhythmic foot twitch pulsing on a slow beat while the wet, guttural snore saws in and out',
  'a compact heap — choke victims never spread out — stomach crunching sharply on every inhale, the snore wet and rattling, toes scrunched and pointed like the feet are the last part still fighting',
  'held too long: both legs quivering together — the one exception to the single-limb rule, the mark of a deep shutdown — eyes drifting and slightly crossed beneath half-open lids, breath coming fast and gurgling',
];
const AFTERMATH_ACTOR = [
  'frozen mid-pose over the fallen opponent for a half-second — the follow-through still hanging in the air — then peeling away as the referee shoves through, arms rising as the arena detonates',
  'sprinting to the fence and leaping onto it, straddling the top, screaming down at the front row with both fists shaking',
  'not celebrating yet — standing off to the side, hands on hips, watching the doctors work with something almost like concern before the corner floods in',
  'walking a slow circle with both arms spread wide, drinking in the roar, then dropping to both knees at the center of the canvas',
  'a stone-cold walk-off — back turned before the body settles, one hand raised without breaking stride',
];

// ---- Wake-up banks (involuntary stages + confusion) ----

const WAKEUP_BODY = [
  'the first movements look like waking but are nothing of the kind — involuntary shivers running through the arms, eyes rolling loose beneath the lids — until suddenly the eyes catch, focus, and go wide with the question',
  '[he] tries to sit up on the second twitch, gets an elbow under [himself], and the referee presses [him] gently back down by the shoulder — the legs are still pointed and stiff, not ready to take orders',
  'consciousness arriving in pieces: a groan, a slow blink, one hand rising to the face to check whether the fight is still happening, finding the referee’s glove instead',
  'coming to mid-sentence, already trying to stand, ankles rolling like a newborn foal’s while the referee holds [him] down with two firm hands and a shake of the head',
];
const WAKEUP_ACTOR = [
  'already on the fence celebrating, pointing down at the spot where the finish landed',
  'crouched a few feet away, watching the opponent come back online, nodding with respect',
  'being pulled away by the referee for the third time, still barking at the fallen fighter’s corner',
  'standing at the center of the cage with arms crossed, letting the replay on the big screen do the talking',
];

// ---- Builders ----

function bodyState(f: SceneFighter, body: string, motion: string, faceStr: string): BodyState {
  return {
    fighterId: f.id,
    name: f.name,
    body: pron(body, f.p),
    motion: pron(motion, f.p),
    face: pron(faceStr, f.p),
  };
}

export type StrikeSeverity = 'rocked' | 'knockdown';

export function strikeScene(
  t: UsageTracker,
  actor: SceneFighter,
  target: SceneFighter,
  kind: StrikeKind,
  severity: StrikeSeverity,
  momentum: Momentum = 'flat',
): SceneDescription {
  let targetBody: string;
  let targetMotion: string;
  if (severity === 'knockdown') {
    targetBody = kind === 'legkick' ? t.pick('hit.legbuckle', HIT_LEGBUCKLE) : t.pick(`fall.${momentum}`, FALLS[momentum]);
    targetMotion = t.pick('motion.falling', MOTION_FALLING);
  } else {
    targetBody = kind === 'legkick' ? t.pick('hit.legbuckle', HIT_LEGBUCKLE) : t.pick('hit.rocked', HIT_ROCKED);
    targetMotion = t.pick('motion.stagger', MOTION_STAGGER);
  }
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

export function bodyFoldScene(
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
      t.pick('face.predator', FACE_PREDATOR),
    ),
    // Body-shot damage is conscious agony, not shutdown (Animation Bible)
    target: bodyState(target, t.pick('hit.bodyfold', HIT_BODYFOLD), 'the delay, then the fold — the body answering the liver, not the will', t.pick('face.desperate', FACE_DESPERATE)),
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

export function slamScene(
  t: UsageTracker,
  actor: SceneFighter,
  target: SceneFighter,
  kind: SlamKind,
): SceneDescription {
  const bank = SLAM_SCENES[kind];
  // Spring vs Water: a rocked victim rides the slam as dead weight
  const spring = !target.cond.rocked;
  return {
    setting: t.pick('setting.standing', SETTINGS_STANDING),
    actor: bodyState(actor, t.pick(`slam.${kind}.actor`, bank.actor), 'potential energy converted to axial compression — a gravity weapon', t.pick('face.straining', FACE_STRAINING)),
    target: bodyState(
      target,
      `${t.pick(`slam.${kind}.${spring ? 'spring' : 'water'}`, spring ? bank.spring : bank.water)} — ${t.pick(`slam.${kind}.impact`, bank.aftermath)}`,
      spring ? 'maximum deceleration: fighting it right up to the frame everything stops' : 'water, not spring — pure physics acting on dead weight',
      t.pick('face.unconscious', FACE_UNCONSCIOUS),
    ),
  };
}

export type SubPhase = 'locked' | 'escape' | 'tap' | 'sleep';

export function submissionScene(
  t: UsageTracker,
  actor: SceneFighter,
  target: SceneFighter,
  kind: SubKind,
  phase: SubPhase,
): SceneDescription {
  const bank = SUB_SCENES[kind];
  const targetBase = t.pick(`sub.${kind}.target`, bank.target);
  const targetBody =
    phase === 'tap'
      ? `${targetBase} — ${t.pick('sub.tap', SUB_TAP)}`
      : phase === 'sleep'
        ? `${targetBase} — ${t.pick('sub.melt', SUB_MELT)}`
        : targetBase;
  const targetMotion =
    phase === 'escape'
      ? 'creating an inch of space and sliding free, scrambling the moment the grip breaks'
      : phase === 'tap'
        ? 'resistance collapsing all at once'
        : phase === 'sleep'
          ? 'a drain, not a surge — the battery dying in full view'
          : 'every muscle recruited against the hold';
  const targetFace =
    phase === 'escape'
      ? face(t, target)
      : phase === 'sleep'
        ? t.pick('face.unconscious', FACE_UNCONSCIOUS)
        : t.pick('face.desperate', FACE_DESPERATE);
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

/** The agonal state after a finish (Animation Bible Phase 4). */
export function aftermathScene(
  t: UsageTracker,
  winner: SceneFighter,
  loser: SceneFighter,
  tier: FinishTier,
): SceneDescription {
  const bank =
    tier === 'deep' ? AFTERMATH_DEEP : tier === 'flash' ? AFTERMATH_FLASH : tier === 'sleep' ? AFTERMATH_SLEEP : AFTERMATH_STIFF;
  const bankId = `aftermath.${tier === 'deep' ? 'deep' : tier === 'flash' ? 'flash' : tier === 'sleep' ? 'sleep' : 'stiff'}`;
  return {
    setting: t.pick('setting.aftermath', SETTINGS_AFTERMATH),
    actor: bodyState(winner, t.pick('aftermath.actor', AFTERMATH_ACTOR), 'from violence to celebration in a single beat', t.pick('ko.face', KO_ACTOR_FACE)),
    target: bodyState(
      loser,
      t.pick(bankId, bank),
      tier === 'flash' ? 'half a signal getting through — the body answering late and wrong' : 'running on brainstem autopilot, nothing voluntary left',
      tier === 'flash' ? t.pick('face.rocked', FACE_ROCKED) : t.pick('face.unconscious', FACE_UNCONSCIOUS),
    ),
  };
}

/** The involuntary, confused return to consciousness. */
export function wakeupScene(
  t: UsageTracker,
  winner: SceneFighter,
  loser: SceneFighter,
): SceneDescription {
  return {
    setting: t.pick('setting.aftermath', SETTINGS_AFTERMATH),
    actor: bodyState(winner, t.pick('wakeup.actor', WAKEUP_ACTOR), 'the moment already belongs to [him]', t.pick('ko.face', KO_ACTOR_FACE)),
    target: bodyState(loser, t.pick('wakeup.body', WAKEUP_BODY), 'rebooting in stages, none of them voluntary', t.pick('face.rocked', FACE_ROCKED)),
  };
}

const GNP_ACTOR = [
  'postured tall in the guard, knees pinning the hips, torso rising and twisting with each downward punch, fists falling like pistons',
  'riding half guard with head low, short elbows carving from the shoulder, weight never leaving the opponent’s chest',
  'one hand posting on the sternum while the other cocks back to the ceiling, hips heavy, punches dropping straight down the centerline',
  'knee slid up to the armpit, torso levered over the trapped head, alternating hammerfists swinging from the elbow',
];
const GNP_TARGET = [
  'flat on [his] back, forearms crossed over the face, hips bumping to unbalance the top fighter, knees climbing for guard',
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
  'collar tie and wrist control, shoulder crushed into the opponent’s chest, feet staggered and walking them flat into the fence',
  'double overhooks clamped, chin dug into the shoulder, thigh wedged between the opponent’s legs to kill the hip escape',
  'head pinned to the collarbone, one hand ripping the far arm across, knees thumping into the thigh on a metronome',
];
const CLINCH_TARGET = [
  'back bowed into the chain-link, hips pushed away to deny the takedown, elbows tight, hand-fighting for the underhook',
  'flattened against the fence, chin down, absorbing knees on the thighs while [his] feet circle for the exit',
  'framing at the neck and bicep with both forearms, spine grinding against the links, trying to create an arm’s length of daylight',
  'weathering the pressure with short shoulder shrugs, palms stapled to the hips in front of [him], waiting for the break',
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
  'hips escaping sideways, a knee levering under the opponent’s base, momentum carrying [him] up and over into top position',
  'a butterfly hook elevating the opponent’s whole hip, the world flipping as bottom becomes top in one motion',
  'catching the posting wrist mid-punch and rolling with it, using the opponent’s own weight as the engine of the reversal',
];

export function sweepScene(t: UsageTracker, actor: SceneFighter, target: SceneFighter): SceneDescription {
  return {
    setting: t.pick('setting.ground', SETTINGS_GROUND),
    actor: bodyState(actor, t.pick('sweep.actor', SWEEP_ACTOR), 'one violent reversal — bottom to top inside a second', t.pick('face.straining', FACE_STRAINING)),
    target: bodyState(
      target,
      'weight suddenly floating, base gone, rolled onto [his] back with arms flaring for a frame',
      'toppled sideways, scrambling to re-guard',
      face(t, target),
    ),
  };
}

const STANDUP_ACTOR = [
  'building to a tripod — one hand posted, feet walking under the hips, peeling the wrist off [his] waist and rising into stance',
  'exploding into a scramble off a missed punch, knees to feet in one beat, hands already back at [his] chin',
  'wall-walking up the fence, shoulder blades dragging the links, hips swiveling out as the feet find their base',
  'kicking the top fighter’s hips away with both feet and back-rolling up to standing in the space it buys',
];

export function standupScene(t: UsageTracker, actor: SceneFighter, target: SceneFighter): SceneDescription {
  return {
    setting: t.pick('setting.ground', SETTINGS_GROUND),
    actor: bodyState(actor, t.pick('standup.actor', STANDUP_ACTOR), 'technical stand-up, guard restored before fully upright', face(t, actor)),
    target: bodyState(
      target,
      'grip broken, sliding off the hips, rocking back to [his] knees before rising to follow',
      'the control position dissolving, resetting to the feet',
      face(t, target),
    ),
  };
}

const KO_ACTOR_BODY = [
  'follow-through complete, arms dropping for one beat, then sprinting to the fence and leaping onto it, arms spread wide',
  'standing over the fallen opponent for a frozen half-second, fist still cocked, then turning away with both arms raised',
  'walking off before the body lands, back already turned, one finger raised to the crowd',
  'dropping to both knees mid-cage, head tilted back to the lights, arms opening as the arena detonates',
];
const KO_ACTOR_FACE = [
  'roaring, veins roped on the neck, eyes wild with adrenaline',
  'mouth open in a scream of release, eyes searching out [his] corner',
  'stone calm amid the chaos, a single exhale, eyes closing for a moment',
  'disbelief melting into joy, eyebrows up, laughing at the noise',
];
const TKO_ACTOR_BODY = [
  'straddling the downed opponent, punches pouring down until the referee’s arms close around [his] shoulders, then rising with fists spread',
  'unloading against the fence, hands a blur, the last punch pulled mid-flight as the referee dives between them',
  'hammerfists cascading from full mount, torso twisting with each one, until the tap on [his] back stops the arm mid-cock',
  'a knee pinning the chest, punches thudding into the guard like an axe into wood, until the referee’s grip drags [him] backward off the finish',
];
const TKO_TARGET_BODY = [
  'crumpled against the fence, forearms shelled over the face, no longer punching back, knees drawn up to the chest',
  'face-down under the storm, one hand extended weakly toward the referee’s legs, body curled into itself',
  'rolling to [his] side with both gloves welded to the temples, absorbing without answering, eyes gone somewhere else',
  'flattened out with arms wrapped over the back of [his] own head, fingers laced, taking punches on the knuckles and elbows',
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
  tier: FinishTier = 'stiff',
): SceneDescription {
  if (kind === 'ko') {
    const fallBank = tier === 'deep' ? FALLS_DEEP : FALLS_STIFF;
    return {
      setting: 'the referee diving in between them, waving both arms overhead as the arena erupts',
      actor: bodyState(actor, t.pick('ko.actor', KO_ACTOR_BODY), 'from violence to celebration in a single beat', t.pick('ko.face', KO_ACTOR_FACE)),
      target: bodyState(
        target,
        t.pick(tier === 'deep' ? 'ko.body.deep' : 'ko.body.stiff', fallBank),
        t.pick('motion.falling', MOTION_FALLING),
        t.pick('face.unconscious', FACE_UNCONSCIOUS),
      ),
    };
  }
  return {
    setting: 'the referee wrapping both arms around the attacker and hauling them off the beaten fighter',
    actor: bodyState(actor, t.pick('tko.actor', TKO_ACTOR_BODY), 'a final flurry with nothing coming back', t.pick('face.predator', FACE_PREDATOR)),
    target: bodyState(target, t.pick('tko.target', TKO_TARGET_BODY), 'defense collapsed to pure survival', t.pick('tko.face', TKO_TARGET_FACE)),
  };
}
