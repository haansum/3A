import type { StrikeTech, SubTech, TakedownTech } from './techniques';
import type { UsageTracker } from './variety';

/**
 * Template-based play-by-play. Every line is picked through the
 * UsageTracker so no template repeats within a fight until its bank is
 * exhausted, and all variation comes from the fight's seeded RNG —
 * replaying a seed reproduces the exact same commentary. Technique
 * objects are picked by the engine and shared with the scene builder,
 * keeping the commentary and the kinematics in sync.
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

  exchange(t: UsageTracker, a: string, b: string, strike: StrikeTech): string {
    return t.pick('n.exchange', [
      `${a} lands ${strike.phrase}.`,
      `${a} finds a home for ${strike.phrase}.`,
      `${a} snaps ${b}'s head back with ${strike.phrase}.`,
      `${a} steps in and scores with ${strike.phrase}.`,
      `${a} touches ${b} with ${strike.phrase} and angles out.`,
      `${b} eats ${strike.phrase} on the way in.`,
    ]);
  },

  bigStrike(t: UsageTracker, a: string, b: string, strike: StrikeTech): string {
    return t.pick('n.bigStrike', [
      `${a} hurts ${b} with ${strike.phrase}! ${b} is backing up on wobbly legs!`,
      `Huge shot! ${a} lands ${strike.phrase} and ${b} is visibly rocked!`,
      `${a} cracks ${b} with ${strike.phrase} — ${b} is in trouble!`,
      `${b}'s legs betray him! ${strike.phrase} from ${a} lands flush!`,
      `Oh, that one hurt him! ${a} detonates ${strike.phrase} and ${b} is on rubber legs!`,
    ]);
  },

  knockdown(t: UsageTracker, a: string, b: string, strike: StrikeTech): string {
    return t.pick('n.knockdown', [
      `DOWN GOES ${b.toUpperCase()}! ${a} drops him with ${strike.phrase}!`,
      `${a} lands ${strike.phrase} and ${b} hits the canvas!`,
      `Knockdown! ${strike.phrase} from ${a} puts ${b} on the mat!`,
      `${b} is DOWN! ${a} timed ${strike.phrase} perfectly!`,
      `The shot lands and ${b} crumbles — ${a} scores the knockdown with ${strike.phrase}!`,
      `${a} uncorks ${strike.phrase} and the canvas rushes up to meet ${b}!`,
    ]);
  },

  takedown(t: UsageTracker, a: string, b: string, td: TakedownTech): string {
    return t.pick('n.takedown', [
      `${a} completes ${td.phrase} and settles into top position.`,
      `${a} changes levels and finishes ${td.phrase} on ${b}.`,
      `Takedown ${a} — ${td.phrase} puts ${b} on his back.`,
      `${b} is grounded! ${a} hits ${td.phrase} clean.`,
      `${a} chains into ${td.phrase} and plants ${b} on the canvas.`,
    ]);
  },

  takedownStuffed(t: UsageTracker, a: string, b: string): string {
    return t.pick('n.tdStuffed', [
      `${a} shoots but ${b} sprawls beautifully and stays upright.`,
      `${b} stuffs the takedown and shrugs ${a} off.`,
      `${a} dives on a leg — ${b}'s takedown defense holds.`,
      `Denied! ${b} reads the shot and shuts it down cold.`,
      `${a} telegraphs the entry and ${b} makes him pay for the real estate.`,
    ]);
  },

  clinchWork(t: UsageTracker, a: string, b: string): string {
    return t.pick('n.clinch', [
      `${a} presses ${b} into the fence and lands short knees.`,
      `${a} controls the clinch, working dirty boxing on ${b}.`,
      `${a} grinds ${b} against the cage with heavy pressure.`,
      `The fight stalls on the fence — ${a} winning the grip battle and banking control time.`,
    ]);
  },

  groundStrikes(t: UsageTracker, a: string, b: string): string {
    return t.pick('n.gnp', [
      `${a} postures up and rains down ground-and-pound on ${b}.`,
      `${a} lands heavy elbows from top position.`,
      `${a} is busy from the top, punishing ${b} with short shots.`,
      `${b} is wearing punches on the ground — ${a} methodical from top position.`,
    ]);
  },

  subAttempt(t: UsageTracker, a: string, b: string, sub: SubTech): string {
    return t.pick('n.subAttempt', [
      `${a} locks in a ${sub.phrase}! ${b} is fighting the hands...`,
      `${a} threatens with a tight ${sub.phrase} — this looks deep!`,
      `${a} isolates a limb and attacks with a ${sub.phrase}!`,
      `Danger! ${a} has the ${sub.phrase} locked and is starting to squeeze!`,
      `${a} snatches up a ${sub.phrase} out of the scramble!`,
    ]);
  },

  subEscape(t: UsageTracker, a: string, b: string, sub: SubTech): string {
    return t.pick('n.subEscape', [
      `${b} survives the ${sub.phrase} and slips free!`,
      `${b} works his way out of the ${sub.phrase} — great defense.`,
      `Somehow ${b} escapes the ${sub.phrase} and scrambles clear.`,
      `${b} finds the one exit from the ${sub.phrase} and takes it!`,
    ]);
  },

  standup(t: UsageTracker, a: string): string {
    return t.pick('n.standup', [
      `${a} works back to his feet.`,
      `${a} scrambles up and resets in open space.`,
      `${a} builds his base and stands.`,
      `${a} fights the grips, wall-walks, and gets the fight back to standing.`,
    ]);
  },

  sweep(t: UsageTracker, a: string): string {
    return t.pick('n.sweep', [
      `${a} hits a slick sweep and comes out on top!`,
      `${a} reverses position — huge momentum shift on the ground!`,
      `Beautiful reversal by ${a} — bottom to top in a blink!`,
      `${a} times the sweep perfectly and steals top position!`,
    ]);
  },

  roundEnd(round: number, a: string, b: string, aStrikes: number, bStrikes: number): string {
    return `End of round ${round}. Significant strikes: ${a} ${aStrikes}, ${b} ${bStrikes}.`;
  },

  ko(t: UsageTracker, a: string, b: string, round: number, time: number): string {
    return t.pick('n.ko', [
      `IT'S ALL OVER! ${a} knocks ${b} out cold at ${fmt(time)} of round ${round}!`,
      `${b} is out! The referee waves it off — KO win for ${a} at ${fmt(time)} of round ${round}!`,
      `GOODNIGHT! ${a} ends it in one shot at ${fmt(time)} of round ${round}!`,
      `${b} is unconscious before he lands! ${a} by knockout, ${fmt(time)} of round ${round}!`,
    ]);
  },

  tko(t: UsageTracker, a: string, b: string, round: number, time: number): string {
    return t.pick('n.tko', [
      `The referee has seen enough! ${a} wins by TKO at ${fmt(time)} of round ${round} — ${b} was taking too much damage.`,
      `${a} swarms and the referee steps in! TKO at ${fmt(time)} of round ${round}.`,
      `${b} is not defending himself — the referee rescues him at ${fmt(time)} of round ${round}. TKO for ${a}.`,
      `A flurry with no answer! It's waved off at ${fmt(time)} of round ${round} — ${a} by TKO.`,
    ]);
  },

  submissionWin(t: UsageTracker, a: string, b: string, sub: SubTech, round: number, time: number): string {
    return t.pick('n.subWin', [
      `${b} taps! ${a} wins by ${sub.phrase} at ${fmt(time)} of round ${round}!`,
      `The tap comes! ${a} finishes the ${sub.phrase} at ${fmt(time)} of round ${round}!`,
      `There's no way out — ${b} surrenders to the ${sub.phrase} at ${fmt(time)} of round ${round}!`,
      `${a} squeezes and ${b} has to tap! ${sub.phrase} finish at ${fmt(time)} of round ${round}!`,
    ]);
  },

  decision(winner: string | null, method: string, scores: string): string {
    if (!winner) return `The judges score it a draw (${scores}).`;
    return `${winner} wins by ${method.toLowerCase()} (${scores}).`;
  },
};

export { fmt as formatClock };
