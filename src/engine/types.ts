/**
 * Core types for the fight simulation engine.
 * The engine is pure TypeScript with no React/native dependencies,
 * so it can be unit-tested and Monte-Carlo-balanced in Node.
 */

export type FightingStyle =
  | 'pressure' // pressure striker: high pace, walks opponents down
  | 'counter' // counter striker: patient, punishes aggression
  | 'wrestler' // takedowns + top control, grinds
  | 'submission' // hunts the ground and finishes with submissions
  | 'brawler' // wild power shots, weak defense
  | 'balanced'; // well-rounded, adapts

export const STYLES: FightingStyle[] = [
  'pressure',
  'counter',
  'wrestler',
  'submission',
  'brawler',
  'balanced',
];

export const STYLE_LABELS: Record<FightingStyle, string> = {
  pressure: 'Pressure Striker',
  counter: 'Counter Striker',
  wrestler: 'Wrestler',
  submission: 'Submission Artist',
  brawler: 'Brawler',
  balanced: 'All-Rounder',
};

/** All attributes are on a 0-100 scale. */
export interface Attributes {
  /** Striking technique and accuracy */
  striking: number;
  /** One-shot knockout power */
  power: number;
  /** Hand/foot speed and reflexive defense */
  speed: number;
  /** Ability to absorb strikes without going down */
  chin: number;
  /** Gas tank: pace sustained across rounds */
  cardio: number;
  /** Takedowns and top control */
  wrestling: number;
  /** Submission offense */
  submissions: number;
  /** Takedown defense, escapes, and submission defense */
  grapplingDefense: number;
  /** Reads, adjustments, and shot selection */
  fightIQ: number;
  /** Forward pressure and output volume */
  aggression: number;
  /** Toughness when hurt or losing */
  heart: number;
}

export const ATTRIBUTE_KEYS: (keyof Attributes)[] = [
  'striking',
  'power',
  'speed',
  'chin',
  'cardio',
  'wrestling',
  'submissions',
  'grapplingDefense',
  'fightIQ',
  'aggression',
  'heart',
];

export const ATTRIBUTE_LABELS: Record<keyof Attributes, string> = {
  striking: 'Striking',
  power: 'Power',
  speed: 'Speed',
  chin: 'Chin',
  cardio: 'Cardio',
  wrestling: 'Wrestling',
  submissions: 'Submissions',
  grapplingDefense: 'Grappling Defense',
  fightIQ: 'Fight IQ',
  aggression: 'Aggression',
  heart: 'Heart',
};

export interface Fighter {
  id: string;
  name: string;
  nickname?: string;
  style: FightingStyle;
  attributes: Attributes;
  /** Win/loss record accumulated from simulated fights */
  wins: number;
  losses: number;
  draws: number;
}

export type FightEventType =
  | 'round_start'
  | 'exchange' // notable striking exchange
  | 'big_strike' // a heavy shot that visibly hurts
  | 'knockdown'
  | 'takedown'
  | 'takedown_stuffed'
  | 'clinch_work'
  | 'ground_strikes'
  | 'sub_attempt' // locked in but escaped
  | 'sub_escape'
  | 'standup' // bottom fighter gets back up
  | 'sweep' // bottom fighter reverses position
  | 'round_end'
  | 'ko'
  | 'tko'
  | 'submission'
  | 'decision';

/**
 * Kinematic snapshot of one fighter at a key moment, written for
 * animators/renderers: joint-level body positioning, movement quality,
 * and facial expression.
 */
export interface BodyState {
  fighterId: string;
  name: string;
  /** Whole-body position: stance, joints, weight distribution, contact points */
  body: string;
  /** Direction, speed, and quality of movement through the moment */
  motion: string;
  /** Facial expression, eyes, mouth */
  face: string;
}

/** A renderable scene attached to key fight moments. */
export interface SceneDescription {
  /** Where in the cage the moment happens and how it's framed */
  setting: string;
  /** The fighter performing the action */
  actor: BodyState;
  /** The fighter on the receiving end */
  target: BodyState;
}

export interface FightEvent {
  round: number;
  /** Seconds elapsed within the round (0-299) */
  time: number;
  type: FightEventType;
  /** Fighter id of the one doing the thing (if any) */
  actorId?: string;
  targetId?: string;
  /** Rendered play-by-play sentence */
  text: string;
  /** Structured kinematics for key moments (animation/render source data) */
  scene?: SceneDescription;
}

export type FightMethod =
  | 'KO'
  | 'TKO'
  | 'Submission'
  | 'Unanimous Decision'
  | 'Split Decision'
  | 'Majority Decision'
  | 'Draw';

export interface FighterFightStats {
  sigStrikes: number;
  sigStrikesThrown: number;
  knockdowns: number; // scored (inflicted on opponent)
  takedowns: number;
  takedownsAttempted: number;
  subAttempts: number;
  controlSeconds: number;
  /** Damage absorbed by this fighter over the fight (0-100+) */
  damageTaken: number;
  /** Stamina remaining at the end (0-100) */
  staminaLeft: number;
}

export interface Scorecard {
  judge: string;
  /** score[roundIndex] = [pointsA, pointsB] */
  rounds: [number, number][];
  totalA: number;
  totalB: number;
}

export interface FightResult {
  id: string;
  /** Seed makes every fight exactly reproducible */
  seed: number;
  date: string; // ISO
  fighterAId: string;
  fighterBId: string;
  fighterAName: string;
  fighterBName: string;
  /** null = draw */
  winnerId: string | null;
  method: FightMethod;
  /** Round the fight ended in (== scheduled rounds for decisions) */
  endRound: number;
  /** Time in seconds within the final round */
  endTime: number;
  scheduledRounds: number;
  events: FightEvent[];
  statsA: FighterFightStats;
  statsB: FighterFightStats;
  scorecards: Scorecard[];
  /** Set when the fight belongs to a tournament */
  tournamentId?: string;
}

/** Lingering damage/fatigue carried into a fighter's next tournament fight. */
export interface CarryoverState {
  damage: number;
  /** Stamina ceiling below 100 for the next fight */
  staminaCap: number;
}

export interface FightConfig {
  rounds: number; // 3 or 5
  seed: number;
  carryoverA?: CarryoverState;
  carryoverB?: CarryoverState;
}
