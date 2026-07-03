import type { Rng } from './rng';

/**
 * Anti-repetition engine for narration and scene prose.
 *
 * Every template bank pick goes through the tracker. Within a fight, a
 * bank never repeats a variant until every variant has been used (each
 * full cycle is a permutation of the bank), and a new cycle never opens
 * with the variant that just closed the previous one. Picks are drawn
 * from the fight's seeded RNG, so replays reproduce identical choices.
 *
 * The tracker also produces a usage log — which variant of which bank
 * was used, in order. The log is stored on the fight result so (a) the
 * app can surface repetition stats, and (b) the store can feed recently
 * used variants back in as `avoid`, biasing the next fight away from
 * prose the user has just read.
 */

export interface BankUsage {
  /** Number of variants in the bank at simulation time */
  size: number;
  /** Variant indices in the order they were used */
  picks: number[];
}

export type UsageLog = Record<string, BankUsage>;

export class UsageTracker {
  private cycleUsed = new Map<string, Set<number>>();
  private lastPick = new Map<string, number>();
  private log: UsageLog = {};

  constructor(
    private rng: Rng,
    /** Variants to treat as already-seen (from recent fights) */
    private avoid: Record<string, number[]> = {},
  ) {}

  pick<T>(bank: string, items: readonly T[]): T {
    if (items.length === 1) {
      this.record(bank, items.length, 0);
      return items[0];
    }

    let used = this.cycleUsed.get(bank);
    if (!used) {
      // Seed the first cycle with cross-fight avoidance, but never
      // exclude so much that the bank can't breathe
      used = new Set((this.avoid[bank] ?? []).filter((i) => i >= 0 && i < items.length));
      if (used.size >= items.length) used.clear();
      this.cycleUsed.set(bank, used);
    }

    let candidates: number[] = [];
    for (let i = 0; i < items.length; i++) if (!used.has(i)) candidates.push(i);

    if (candidates.length === 0) {
      // Cycle complete: start over, but don't immediately repeat
      used.clear();
      const last = this.lastPick.get(bank);
      for (let i = 0; i < items.length; i++) if (i !== last) candidates.push(i);
    }

    const index = candidates[Math.floor(this.rng.next() * candidates.length)];
    used.add(index);
    this.lastPick.set(bank, index);
    this.record(bank, items.length, index);
    return items[index];
  }

  private record(bank: string, size: number, index: number) {
    const entry = (this.log[bank] ??= { size, picks: [] });
    entry.size = size;
    entry.picks.push(index);
  }

  usage(): UsageLog {
    return this.log;
  }
}

/**
 * Roll a usage log into a compact "recently used" map for the next
 * fight's `avoid` input. Keeps the tail end (most recent picks) of each
 * bank, capped so small banks always keep at least one live option.
 */
export function recentFromUsage(
  previous: Record<string, number[]>,
  usage: UsageLog,
): Record<string, number[]> {
  const next: Record<string, number[]> = { ...previous };
  for (const [bank, { size, picks }] of Object.entries(usage)) {
    if (size < 2) continue;
    const keep = Math.min(Math.floor(size / 2), 6);
    const merged = [...(next[bank] ?? []), ...picks];
    // De-duplicate keeping the most recent occurrence of each variant
    const seen = new Set<number>();
    const recent: number[] = [];
    for (let i = merged.length - 1; i >= 0 && recent.length < keep; i--) {
      if (!seen.has(merged[i])) {
        seen.add(merged[i]);
        recent.unshift(merged[i]);
      }
    }
    next[bank] = recent;
  }
  return next;
}
