import AsyncStorage from '@react-native-async-storage/async-storage';
import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

import { makeId, presetFighters } from '@/engine/data';
import { simulateFight } from '@/engine/engine';
import { randomSeed } from '@/engine/rng';
import { createTournament, simulateNextRound, type Tournament } from '@/engine/tournament';
import type { Fighter, FightResult } from '@/engine/types';
import { recentFromUsage } from '@/engine/variety';

const MAX_LOOSE_RESULTS = 50; // quick fights beyond this get pruned (oldest first)

interface AppState {
  fighters: Record<string, Fighter>;
  fighterOrder: string[];
  results: Record<string, FightResult>;
  resultOrder: string[]; // newest first
  tournaments: Record<string, Tournament>;
  tournamentOrder: string[]; // newest first
  /**
   * Rolling map of recently used narration/scene template variants
   * (bank -> variant indices), fed into each new simulation so
   * back-to-back fights don't reuse the same prose.
   */
  recentVariants: Record<string, number[]>;

  addFighter: (fighter: Fighter) => void;
  updateFighter: (fighter: Fighter) => void;
  deleteFighter: (id: string) => void;

  /** Simulate a one-off fight, persist the result, update records. Returns result id. */
  runQuickFight: (aId: string, bId: string, rounds: number, seed?: number) => string | null;
  deleteResult: (id: string) => void;

  createNewTournament: (
    name: string,
    fighterIds: string[],
    options: { carryover: boolean; roundsPerFight: number },
  ) => string;
  simulateTournamentRound: (tournamentId: string) => void;
  deleteTournament: (id: string) => void;
}

function applyRecord(
  fighters: Record<string, Fighter>,
  result: FightResult,
): Record<string, Fighter> {
  const next = { ...fighters };
  const bump = (id: string, key: 'wins' | 'losses' | 'draws') => {
    const f = next[id];
    if (f) next[id] = { ...f, [key]: f[key] + 1 };
  };
  if (result.winnerId) {
    const loserId = result.winnerId === result.fighterAId ? result.fighterBId : result.fighterAId;
    bump(result.winnerId, 'wins');
    bump(loserId, 'losses');
  } else {
    bump(result.fighterAId, 'draws');
    bump(result.fighterBId, 'draws');
  }
  return next;
}

function initialRoster() {
  const roster = presetFighters();
  return {
    fighters: Object.fromEntries(roster.map((f) => [f.id, f])),
    fighterOrder: roster.map((f) => f.id),
  };
}

export const useStore = create<AppState>()(
  persist(
    (set, get) => ({
      ...initialRoster(),
      results: {},
      resultOrder: [],
      tournaments: {},
      tournamentOrder: [],
      recentVariants: {},

      addFighter: (fighter) =>
        set((s) => ({
          fighters: { ...s.fighters, [fighter.id]: fighter },
          fighterOrder: [...s.fighterOrder, fighter.id],
        })),

      updateFighter: (fighter) =>
        set((s) => ({ fighters: { ...s.fighters, [fighter.id]: fighter } })),

      deleteFighter: (id) =>
        set((s) => {
          const fighters = { ...s.fighters };
          delete fighters[id];
          return { fighters, fighterOrder: s.fighterOrder.filter((f) => f !== id) };
        }),

      runQuickFight: (aId, bId, rounds, seed) => {
        const s = get();
        const a = s.fighters[aId];
        const b = s.fighters[bId];
        if (!a || !b || aId === bId) return null;
        const result = simulateFight(a, b, {
          rounds,
          seed: seed ?? randomSeed(),
          avoidRecent: s.recentVariants,
        });

        set((state) => {
          const results = { ...state.results, [result.id]: result };
          let resultOrder = [result.id, ...state.resultOrder];
          // Prune old quick fights; tournament results live with their tournament
          const loose = resultOrder.filter((id) => !results[id]?.tournamentId);
          if (loose.length > MAX_LOOSE_RESULTS) {
            for (const id of loose.slice(MAX_LOOSE_RESULTS)) {
              delete results[id];
              resultOrder = resultOrder.filter((r) => r !== id);
            }
          }
          return {
            results,
            resultOrder,
            fighters: applyRecord(state.fighters, result),
            recentVariants: result.usage
              ? recentFromUsage(state.recentVariants, result.usage)
              : state.recentVariants,
          };
        });
        return result.id;
      },

      deleteResult: (id) =>
        set((s) => {
          const results = { ...s.results };
          delete results[id];
          return { results, resultOrder: s.resultOrder.filter((r) => r !== id) };
        }),

      createNewTournament: (name, fighterIds, options) => {
        const t = createTournament(name || `Tournament ${makeId('').slice(-4)}`, fighterIds, options);
        set((s) => ({
          tournaments: { ...s.tournaments, [t.id]: t },
          tournamentOrder: [t.id, ...s.tournamentOrder],
        }));
        return t.id;
      },

      simulateTournamentRound: (tournamentId) => {
        const s = get();
        const t = s.tournaments[tournamentId];
        if (!t) return;
        const { tournament, results } = simulateNextRound(t, s.fighters, s.recentVariants);
        set((state) => {
          let fighters = state.fighters;
          const resultsMap = { ...state.results };
          let resultOrder = state.resultOrder;
          let recentVariants = state.recentVariants;
          for (const r of results) {
            resultsMap[r.id] = r;
            resultOrder = [r.id, ...resultOrder];
            fighters = applyRecord(fighters, r);
            if (r.usage) recentVariants = recentFromUsage(recentVariants, r.usage);
          }
          return {
            tournaments: { ...state.tournaments, [tournamentId]: tournament },
            results: resultsMap,
            resultOrder,
            fighters,
            recentVariants,
          };
        });
      },

      deleteTournament: (id) =>
        set((s) => {
          const tournaments = { ...s.tournaments };
          delete tournaments[id];
          const results = { ...s.results };
          const removed = new Set(
            Object.values(s.results)
              .filter((r) => r.tournamentId === id)
              .map((r) => r.id),
          );
          for (const rid of removed) delete results[rid];
          return {
            tournaments,
            tournamentOrder: s.tournamentOrder.filter((t) => t !== id),
            results,
            resultOrder: s.resultOrder.filter((r) => !removed.has(r)),
          };
        }),
    }),
    {
      name: 'fight-sim-store-v1',
      storage: createJSONStorage(() => AsyncStorage),
    },
  ),
);
