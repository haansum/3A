import { makeId } from './data';
import { randomSeed } from './rng';
import { simulateFight } from './engine';
import type { CarryoverState, Fighter, FightResult } from './types';

/**
 * Single-elimination bracket with optional damage carryover: a fighter who
 * survives a war enters the next round compromised, while a quick finish
 * leaves them fresh — the classic one-night-tournament dynamic.
 */

export interface BracketMatch {
  id: string;
  /** null until the previous round decides who advances */
  fighterAId: string | null;
  fighterBId: string | null;
  resultId: string | null;
  winnerId: string | null;
}

export interface Tournament {
  id: string;
  name: string;
  date: string;
  /** 4, 8, or 16 entrants, in bracket order */
  fighterIds: string[];
  /** rounds[0] = first round matches, last = final */
  rounds: BracketMatch[][];
  carryover: boolean;
  roundsPerFight: number;
  championId: string | null;
  /** Lingering damage per fighter, updated as rounds are simulated */
  carryStates: Record<string, CarryoverState>;
}

export function createTournament(
  name: string,
  fighterIds: string[],
  options: { carryover: boolean; roundsPerFight: number },
): Tournament {
  const size = fighterIds.length;
  if (![4, 8, 16].includes(size)) {
    throw new Error('Tournament size must be 4, 8, or 16 fighters');
  }
  const rounds: BracketMatch[][] = [];
  let matches = size / 2;
  let first = true;
  while (matches >= 1) {
    const roundMatches: BracketMatch[] = [];
    for (let m = 0; m < matches; m++) {
      roundMatches.push({
        id: makeId('m'),
        fighterAId: first ? fighterIds[m * 2] : null,
        fighterBId: first ? fighterIds[m * 2 + 1] : null,
        resultId: null,
        winnerId: null,
      });
    }
    rounds.push(roundMatches);
    matches = Math.floor(matches / 2);
    first = false;
  }
  return {
    id: makeId('t'),
    name,
    date: new Date().toISOString(),
    fighterIds,
    rounds,
    carryover: options.carryover,
    roundsPerFight: options.roundsPerFight,
    championId: null,
    carryStates: {},
  };
}

/** Index of the next bracket round with unfought matches, or -1 if done. */
export function nextRoundIndex(t: Tournament): number {
  return t.rounds.findIndex((r) => r.some((m) => m.resultId === null));
}

export function roundLabel(t: Tournament, roundIndex: number): string {
  const remaining = t.rounds.length - roundIndex;
  if (remaining === 1) return 'Final';
  if (remaining === 2) return 'Semifinals';
  if (remaining === 3) return 'Quarterfinals';
  return `Round of ${t.rounds[roundIndex].length * 2}`;
}

/** Convert end-of-fight state into what the winner carries into the next fight. */
function carryoverFromResult(result: FightResult, winnerId: string): CarryoverState {
  const stats = winnerId === result.fighterAId ? result.statsA : result.statsB;
  return {
    damage: Math.min(40, stats.damageTaken * 0.35),
    staminaCap: Math.max(70, 100 - (100 - stats.staminaLeft) * 0.3),
  };
}

export interface RoundSimResults {
  tournament: Tournament;
  results: FightResult[];
}

/**
 * Simulate every fight in the next unfought bracket round.
 * Returns the updated tournament (new object) and the fight results,
 * which the caller is responsible for storing.
 */
export function simulateNextRound(t: Tournament, fighters: Record<string, Fighter>): RoundSimResults {
  const idx = nextRoundIndex(t);
  if (idx === -1) return { tournament: t, results: [] };

  const updated: Tournament = {
    ...t,
    rounds: t.rounds.map((r) => r.map((m) => ({ ...m }))),
    carryStates: { ...t.carryStates },
  };
  const results: FightResult[] = [];

  for (const match of updated.rounds[idx]) {
    if (match.resultId || !match.fighterAId || !match.fighterBId) continue;
    const fa = fighters[match.fighterAId];
    const fb = fighters[match.fighterBId];
    if (!fa || !fb) continue;

    const result = simulateFight(fa, fb, {
      rounds: updated.roundsPerFight,
      seed: randomSeed(),
      carryoverA: updated.carryover ? updated.carryStates[fa.id] : undefined,
      carryoverB: updated.carryover ? updated.carryStates[fb.id] : undefined,
    });
    result.tournamentId = updated.id;
    results.push(result);

    // A draw can't advance anyone — the fresher fighter gets the nod
    const winnerId =
      result.winnerId ?? (result.statsA.damageTaken <= result.statsB.damageTaken ? fa.id : fb.id);
    match.resultId = result.id;
    match.winnerId = winnerId;
    updated.carryStates[winnerId] = carryoverFromResult(result, winnerId);
  }

  // Advance winners into the next round's slots
  if (idx + 1 < updated.rounds.length) {
    const winners = updated.rounds[idx].map((m) => m.winnerId);
    updated.rounds[idx + 1].forEach((m, i) => {
      m.fighterAId = winners[i * 2];
      m.fighterBId = winners[i * 2 + 1];
    });
  } else {
    updated.championId = updated.rounds[idx][0].winnerId;
  }

  return { tournament: updated, results };
}
