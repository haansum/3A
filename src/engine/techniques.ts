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

export function pickStrike(rng: Rng, style: FightingStyle): StrikeTech {
  return rng.pick(STRIKES_BY_STYLE[style]);
}

export function pickTakedown(rng: Rng, style: FightingStyle): TakedownTech {
  return rng.pick(TAKEDOWNS_BY_STYLE[style]);
}

export function pickSub(rng: Rng): SubTech {
  return rng.pick(SUBS);
}
