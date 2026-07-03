import type { Rng } from './rng';
import type { StrikeTech, SubTech, TakedownTech } from './techniques';

/**
 * Template-based play-by-play. All variation is drawn from the fight's
 * seeded RNG, so replaying a seed reproduces the exact same commentary.
 * Technique objects are picked by the engine and shared with the scene
 * builder, keeping the commentary and the kinematics in sync.
 */

function fmt(t: number): string {
  const m = Math.floor(t / 60);
  const s = t % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export const narrate = {
  roundStart(round: number): string {
    return `Round ${round} begins.`;
  },

  exchange(rng: Rng, a: string, b: string, strike: StrikeTech): string {
    return rng.pick([
      `${a} lands ${strike.phrase}.`,
      `${a} finds a home for ${strike.phrase}.`,
      `${a} snaps ${b}'s head back with ${strike.phrase}.`,
    ]);
  },

  bigStrike(rng: Rng, a: string, b: string, strike: StrikeTech): string {
    return rng.pick([
      `${a} hurts ${b} with ${strike.phrase}! ${b} is backing up on wobbly legs!`,
      `Huge shot! ${a} lands ${strike.phrase} and ${b} is visibly rocked!`,
      `${a} cracks ${b} with ${strike.phrase} — ${b} is in trouble!`,
    ]);
  },

  knockdown(rng: Rng, a: string, b: string, strike: StrikeTech): string {
    return rng.pick([
      `DOWN GOES ${b.toUpperCase()}! ${a} drops him with ${strike.phrase}!`,
      `${a} lands ${strike.phrase} and ${b} hits the canvas!`,
      `Knockdown! ${strike.phrase} from ${a} puts ${b} on the mat!`,
    ]);
  },

  takedown(rng: Rng, a: string, b: string, td: TakedownTech): string {
    return rng.pick([
      `${a} completes ${td.phrase} and settles into top position.`,
      `${a} changes levels and finishes ${td.phrase} on ${b}.`,
      `Takedown ${a} — ${td.phrase} puts ${b} on his back.`,
    ]);
  },

  takedownStuffed(rng: Rng, a: string, b: string): string {
    return rng.pick([
      `${a} shoots but ${b} sprawls beautifully and stays upright.`,
      `${b} stuffs the takedown and shrugs ${a} off.`,
      `${a} dives on a leg — ${b}'s takedown defense holds.`,
    ]);
  },

  clinchWork(rng: Rng, a: string, b: string): string {
    return rng.pick([
      `${a} presses ${b} into the fence and lands short knees.`,
      `${a} controls the clinch, working dirty boxing on ${b}.`,
      `${a} grinds ${b} against the cage with heavy pressure.`,
    ]);
  },

  groundStrikes(rng: Rng, a: string, b: string): string {
    return rng.pick([
      `${a} postures up and rains down ground-and-pound on ${b}.`,
      `${a} lands heavy elbows from top position.`,
      `${a} is busy from the top, punishing ${b} with short shots.`,
    ]);
  },

  subAttempt(rng: Rng, a: string, b: string, sub: SubTech): string {
    return rng.pick([
      `${a} locks in a ${sub.phrase}! ${b} is fighting the hands...`,
      `${a} threatens with a tight ${sub.phrase} — this looks deep!`,
      `${a} isolates a limb and attacks with a ${sub.phrase}!`,
    ]);
  },

  subEscape(rng: Rng, a: string, b: string, sub: SubTech): string {
    return rng.pick([
      `${b} survives the ${sub.phrase} and slips free!`,
      `${b} works his way out of the ${sub.phrase} — great defense.`,
      `Somehow ${b} escapes the ${sub.phrase} and scrambles clear.`,
    ]);
  },

  standup(rng: Rng, a: string): string {
    return rng.pick([
      `${a} works back to his feet.`,
      `${a} scrambles up and resets in open space.`,
      `${a} builds his base and stands.`,
    ]);
  },

  sweep(rng: Rng, a: string): string {
    return rng.pick([
      `${a} hits a slick sweep and comes out on top!`,
      `${a} reverses position — huge momentum shift on the ground!`,
    ]);
  },

  roundEnd(round: number, a: string, b: string, aStrikes: number, bStrikes: number): string {
    return `End of round ${round}. Significant strikes: ${a} ${aStrikes}, ${b} ${bStrikes}.`;
  },

  ko(rng: Rng, a: string, b: string, round: number, time: number): string {
    return rng.pick([
      `IT'S ALL OVER! ${a} knocks ${b} out cold at ${fmt(time)} of round ${round}!`,
      `${b} is out! The referee waves it off — KO win for ${a} at ${fmt(time)} of round ${round}!`,
    ]);
  },

  tko(rng: Rng, a: string, b: string, round: number, time: number): string {
    return rng.pick([
      `The referee has seen enough! ${a} wins by TKO at ${fmt(time)} of round ${round} — ${b} was taking too much damage.`,
      `${a} swarms and the referee steps in! TKO at ${fmt(time)} of round ${round}.`,
    ]);
  },

  submissionWin(a: string, b: string, sub: SubTech, round: number, time: number): string {
    return `${b} taps! ${a} wins by ${sub.phrase} at ${fmt(time)} of round ${round}!`;
  },

  decision(winner: string | null, method: string, scores: string): string {
    if (!winner) return `The judges score it a draw (${scores}).`;
    return `${winner} wins by ${method.toLowerCase()} (${scores}).`;
  },
};

export { fmt as formatClock };
