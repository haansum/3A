import type { Rng } from './rng';
import type { FightingStyle } from './types';

/**
 * Technique catalogs. Each technique carries a `kind` so the scene
 * builder can attach matching kinematics to the commentary phrase.
 */

export type StrikeKind =
  | 'straight'
  | 'hook'
  | 'uppercut'
  | 'overhand'
  | 'bodyshot'
  | 'legkick'
  | 'headkick'
  | 'frontkick'
  | 'knee'
  | 'elbow';

export interface StrikeTech {
  phrase: string;
  kind: StrikeKind;
}

/**
 * Animation Bible, Part 1: KO comes from ROTATIONAL acceleration.
 * Strikes that spin the skull knock people out; straight pushes score
 * but starch less often; body work folds rather than switches off.
 */
export interface KOProfile {
  /** Multiplier on knockdown probability when a heavy version lands */
  kd: number;
  /** Bias toward deeper KO tiers (Stiff/Deep vs Flash) */
  deepBias: number;
  /** Where the damage goes */
  target: 'head' | 'body' | 'leg';
}

export const KO_PROFILE: Record<StrikeKind, KOProfile> = {
  hook: { kd: 1.25, deepBias: 0.15, target: 'head' },
  headkick: { kd: 1.35, deepBias: 0.3, target: 'head' },
  overhand: { kd: 1.3, deepBias: 0.2, target: 'head' },
  uppercut: { kd: 1.25, deepBias: 0.15, target: 'head' },
  knee: { kd: 1.2, deepBias: 0.25, target: 'head' },
  elbow: { kd: 1.1, deepBias: 0.05, target: 'head' },
  straight: { kd: 1.0, deepBias: 0, target: 'head' },
  frontkick: { kd: 0.85, deepBias: 0, target: 'body' },
  bodyshot: { kd: 0.9, deepBias: 0, target: 'body' },
  legkick: { kd: 0.5, deepBias: 0, target: 'leg' },
};

export type SlamKind = 'spike' | 'powerbomb' | 'suplex';

/** Takedown kinds capable of a slam KO (Animation Bible, Part 3). */
export const SLAM_CAPABLE: Record<TakedownKind, SlamKind | null> = {
  double: 'powerbomb',
  single: null,
  trip: null,
  anklepick: null,
  bodylock: 'suplex',
  highcrotch: 'spike',
};

export type TakedownKind = 'double' | 'single' | 'trip' | 'anklepick' | 'bodylock' | 'highcrotch';

export interface TakedownTech {
  phrase: string;
  kind: TakedownKind;
}

export type SubKind = 'armbar' | 'triangle' | 'rnc' | 'guillotine' | 'kimura' | 'armtriangle' | 'darce';

export interface SubTech {
  phrase: string;
  kind: SubKind;
}

const STRIKES_BY_STYLE: Record<FightingStyle, StrikeTech[]> = {
  pressure: [
    { phrase: 'a stiff jab', kind: 'straight' },
    { phrase: 'a straight right down the pipe', kind: 'straight' },
    { phrase: 'a chopping leg kick', kind: 'legkick' },
    { phrase: 'a hard hook to the body', kind: 'bodyshot' },
    { phrase: 'the second punch of a one-two', kind: 'straight' },
  ],
  counter: [
    { phrase: 'a check hook', kind: 'hook' },
    { phrase: 'a counter right hand', kind: 'straight' },
    { phrase: 'a slick pull-counter', kind: 'straight' },
    { phrase: 'a counter left down the middle', kind: 'straight' },
    { phrase: 'an intercepting knee', kind: 'knee' },
  ],
  wrestler: [
    { phrase: 'a heavy overhand right', kind: 'overhand' },
    { phrase: 'a short elbow in close', kind: 'elbow' },
    { phrase: 'a clubbing hook off the break', kind: 'hook' },
    { phrase: 'a right hand behind the jab', kind: 'straight' },
  ],
  submission: [
    { phrase: 'a quick low kick', kind: 'legkick' },
    { phrase: 'a straight left', kind: 'straight' },
    { phrase: 'a front kick to the body', kind: 'frontkick' },
    { phrase: 'a looping right to close distance', kind: 'overhand' },
  ],
  brawler: [
    { phrase: 'a wild overhand', kind: 'overhand' },
    { phrase: 'a huge looping hook', kind: 'hook' },
    { phrase: 'a winging left hand', kind: 'hook' },
    { phrase: 'an uppercut from hell', kind: 'uppercut' },
    { phrase: 'a haymaker', kind: 'overhand' },
  ],
  balanced: [
    { phrase: 'a crisp jab-cross', kind: 'straight' },
    { phrase: 'a head kick', kind: 'headkick' },
    { phrase: 'a tight left hook', kind: 'hook' },
    { phrase: 'a straight right', kind: 'straight' },
    { phrase: 'a knee up the middle', kind: 'knee' },
  ],
};

const TAKEDOWNS_BY_STYLE: Record<FightingStyle, TakedownTech[]> = {
  wrestler: [
    { phrase: 'a blast double-leg', kind: 'double' },
    { phrase: 'a single-leg against the fence', kind: 'single' },
    { phrase: 'a high-crotch lift', kind: 'highcrotch' },
    { phrase: 'a slick ankle pick', kind: 'anklepick' },
  ],
  submission: [
    { phrase: 'a body-lock takedown', kind: 'bodylock' },
    { phrase: 'a trip from the clinch', kind: 'trip' },
    { phrase: 'a shot to a single-leg', kind: 'single' },
  ],
  balanced: [
    { phrase: 'a double-leg', kind: 'double' },
    { phrase: 'an outside trip', kind: 'trip' },
    { phrase: 'a reactive double-leg', kind: 'double' },
  ],
  pressure: [
    { phrase: 'a takedown against the fence', kind: 'double' },
    { phrase: 'a double-leg off a combination', kind: 'double' },
  ],
  counter: [
    { phrase: 'a reactive double-leg', kind: 'double' },
    { phrase: 'a level change under a punch', kind: 'double' },
  ],
  brawler: [
    { phrase: 'a crude double-leg', kind: 'double' },
    { phrase: 'a bum-rush takedown', kind: 'bodylock' },
  ],
};

const SUBS: SubTech[] = [
  { phrase: 'guillotine choke', kind: 'guillotine' },
  { phrase: 'rear-naked choke', kind: 'rnc' },
  { phrase: 'armbar', kind: 'armbar' },
  { phrase: 'triangle choke', kind: 'triangle' },
  { phrase: 'kimura', kind: 'kimura' },
  { phrase: 'arm-triangle choke', kind: 'armtriangle' },
  { phrase: "D'Arce choke", kind: 'darce' },
];

/**
 * Blood chokes can put a fighter to sleep if they refuse to tap
 * (Animation Bible, Part 2). Joint locks force the tap (or worse).
 */
export const IS_BLOOD_CHOKE: Record<SubKind, boolean> = {
  rnc: true,
  guillotine: true,
  triangle: true,
  armtriangle: true,
  darce: true,
  armbar: false,
  kimura: false,
};

export function pickStrike(rng: Rng, style: FightingStyle): StrikeTech {
  return rng.pick(STRIKES_BY_STYLE[style]);
}

export function pickTakedown(rng: Rng, style: FightingStyle): TakedownTech {
  return rng.pick(TAKEDOWNS_BY_STYLE[style]);
}

export function pickSub(rng: Rng): SubTech {
  return rng.pick(SUBS);
}
