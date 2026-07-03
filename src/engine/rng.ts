/**
 * Deterministic seeded RNG (mulberry32). Given the same seed, a fight
 * plays out identically — this is what makes every fight replicable.
 */
export class Rng {
  private state: number;

  constructor(seed: number) {
    this.state = seed >>> 0;
    if (this.state === 0) this.state = 0x9e3779b9;
  }

  /** Uniform float in [0, 1) */
  next(): number {
    this.state = (this.state + 0x6d2b79f5) >>> 0;
    let t = this.state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  /** True with probability p */
  chance(p: number): boolean {
    return this.next() < p;
  }

  /** Integer in [min, max] inclusive */
  int(min: number, max: number): number {
    return min + Math.floor(this.next() * (max - min + 1));
  }

  /** Uniform float in [min, max) */
  range(min: number, max: number): number {
    return min + this.next() * (max - min);
  }

  pick<T>(items: readonly T[]): T {
    return items[Math.floor(this.next() * items.length)];
  }

  /** Roughly normal (sum of 3 uniforms), mean 0, most mass in [-1, 1] */
  gauss(): number {
    return (this.next() + this.next() + this.next()) * 2 - 3;
  }
}

/** Random 32-bit seed for when the caller doesn't care about replay */
export function randomSeed(): number {
  return Math.floor(Math.random() * 0xffffffff) >>> 0;
}

/** Logistic curve: maps a stat differential to a probability around `base`. */
export function logistic(diff: number, scale: number, base = 0.5): number {
  const p = 1 / (1 + Math.exp(-diff / scale));
  // Recenter so diff=0 -> base
  return Math.min(0.98, Math.max(0.02, base + (p - 0.5)));
}
