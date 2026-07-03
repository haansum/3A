import type { FightingStyle } from './types';

/**
 * "Styles make fights": a mild effectiveness multiplier applied to a
 * fighter's rolls based on the stylistic matchup. Values stay close to 1
 * so raw attributes dominate, but matchups create non-transitive results.
 */
const EDGES: Partial<Record<FightingStyle, Partial<Record<FightingStyle, number>>>> = {
  counter: { brawler: 1.05, pressure: 1.04, wrestler: 0.97 },
  pressure: { submission: 1.03, counter: 0.97 },
  wrestler: { brawler: 1.04, counter: 1.03 },
  brawler: { wrestler: 0.97, counter: 0.96, submission: 0.98 },
  submission: { brawler: 1.04, pressure: 0.98 },
};

export function styleMultiplier(self: FightingStyle, opponent: FightingStyle): number {
  return EDGES[self]?.[opponent] ?? 1.0;
}

/**
 * How a style wants to fight: probability weights for choosing an action
 * while standing. Normalized at use time.
 */
export interface StanceWeights {
  strike: number;
  takedown: number;
  clinch: number;
}

export const STANCE_WEIGHTS: Record<FightingStyle, StanceWeights> = {
  pressure: { strike: 0.78, takedown: 0.08, clinch: 0.14 },
  counter: { strike: 0.88, takedown: 0.07, clinch: 0.05 },
  wrestler: { strike: 0.38, takedown: 0.47, clinch: 0.15 },
  submission: { strike: 0.32, takedown: 0.5, clinch: 0.18 },
  brawler: { strike: 0.92, takedown: 0.03, clinch: 0.05 },
  balanced: { strike: 0.6, takedown: 0.25, clinch: 0.15 },
};

/** On top on the ground: how much the style hunts submissions vs strikes. */
export const SUB_HUNT: Record<FightingStyle, number> = {
  pressure: 0.15,
  counter: 0.15,
  wrestler: 0.25,
  submission: 0.65,
  brawler: 0.1,
  balanced: 0.3,
};
