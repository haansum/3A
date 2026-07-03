import { pron, type PronounKey } from './pronouns';
import type { SlamKind, StrikeTech, SubTech, TakedownTech } from './techniques';
import type { FinishTier } from './types';
import type { UsageTracker } from './variety';

/**
 * Template-based play-by-play in a ringside-witness voice: sound
 * effects, crowd noise, referee dialogue, and the neurological detail
 * of the Animation Bible. Every line is picked through the UsageTracker
 * (no repeats within a fight until a bank is exhausted) and rendered
 * with the subject fighter's pronouns; all variation comes from the
 * fight's seeded RNG, so a replayed seed reproduces identical
 * commentary. Pronoun tokens in each template refer to the fighter
 * being described (usually the one on the receiving end).
 */

function fmt(t: number): string {
  const m = Math.floor(t / 60);
  const s = t % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

/** A fighter reference for narration: display name + pronoun set. */
export interface Who {
  name: string;
  p: PronounKey;
}

export const narrate = {
  roundStart(round: number): string {
    return `Round ${round} begins.`;
  },

  exchange(t: UsageTracker, a: Who, b: Who, strike: StrikeTech): string {
    return pron(
      t.pick('n.exchange', [
        `${a.name} lands ${strike.phrase}.`,
        `${a.name} finds a home for ${strike.phrase}.`,
        `${a.name} snaps ${b.name}'s head back with ${strike.phrase}.`,
        `${a.name} steps in and scores with ${strike.phrase}.`,
        `${a.name} touches ${b.name} with ${strike.phrase} and angles out.`,
        `${b.name} eats ${strike.phrase} on the way in.`,
      ]),
      b.p,
    );
  },

  bigStrike(t: UsageTracker, a: Who, b: Who, strike: StrikeTech): string {
    return pron(
      t.pick('n.bigStrike', [
        `${a.name} hurts ${b.name} with ${strike.phrase}! ${b.name} is backing up on wobbly legs!`,
        `CRACK! ${a.name} lands ${strike.phrase} and ${b.name} is visibly rocked!`,
        `${a.name} cracks ${b.name} with ${strike.phrase} — [he's] in trouble!`,
        `${b.name}'s legs betray [him]! ${strike.phrase} from ${a.name} lands flush!`,
        `Oh, that one hurt! ${a.name} detonates ${strike.phrase} and ${b.name} does the jelly-leg dance!`,
        `WHAP! ${b.name} sees a flash of white light — ${strike.phrase} from ${a.name}, lightning fast!`,
      ]),
      b.p,
    );
  },

  bodyFold(t: UsageTracker, a: Who, b: Who, strike: StrikeTech): string {
    return pron(
      t.pick('n.bodyFold', [
        `THUD! A deep, dry impact — ${a.name} buries ${strike.phrase} downstairs and all the oxygen leaves ${b.name}'s body! "OOFFF!"`,
        `${a.name} goes to the body with ${strike.phrase} and ${b.name} folds in half! That's a liver shot — [he] wants no part of this anymore!`,
        `The delayed reaction tells the story: ${strike.phrase} from ${a.name} lands to the body, one beat, two — and ${b.name} crumples, airless!`,
        `${b.name} takes ${strike.phrase} under the ribs and the grunt is audible cageside. [He's] hurt bad to the body!`,
      ]),
      b.p,
    );
  },

  knockdown(t: UsageTracker, a: Who, b: Who, strike: StrikeTech): string {
    return pron(
      t.pick('n.knockdown', [
        `DOWN GOES ${b.name.toUpperCase()}! ${a.name} drops [him] with ${strike.phrase}!`,
        `BAMMM! The crack of ${strike.phrase} from ${a.name} — ${b.name}'s head snaps back and the canvas rushes up to meet [him]!`,
        `Knockdown! ${strike.phrase} from ${a.name} puts ${b.name} on the mat!`,
        `${b.name} is DOWN! ${a.name} timed ${strike.phrase} perfectly — time seemed to slow as [he] fell!`,
        `The shot lands and ${b.name} crumbles — ${a.name} scores the knockdown with ${strike.phrase}!`,
        `${a.name} uncorks ${strike.phrase} and ${b.name} hits the canvas! The crowd is on its feet!`,
      ]),
      b.p,
    );
  },

  takedown(t: UsageTracker, a: Who, b: Who, td: TakedownTech): string {
    return pron(
      t.pick('n.takedown', [
        `${a.name} completes ${td.phrase} and settles into top position.`,
        `${a.name} changes levels and finishes ${td.phrase} on ${b.name}.`,
        `Takedown ${a.name} — ${td.phrase} puts ${b.name} on [his] back.`,
        `${b.name} is grounded! ${a.name} hits ${td.phrase} clean.`,
        `${a.name} chains into ${td.phrase} and plants ${b.name} on the canvas.`,
      ]),
      b.p,
    );
  },

  slam(t: UsageTracker, a: Who, b: Who, kind: SlamKind): string {
    const move = kind === 'spike' ? 'a high-crotch spike' : kind === 'powerbomb' ? 'a thunderous power slam' : 'a full-arc suplex';
    return pron(
      t.pick('n.slam', [
        `OH MY GOD! ${a.name} hoists ${b.name} into the air and drives [him] through the canvas with ${move}! The whole arena felt that one — ${b.name} is OUT on impact!`,
        `${a.name} lifts — the crowd rises with [him]... ${move.toUpperCase()}! ${b.name}'s body bounces off the mat and goes limp! It's over!`,
        `THOOM! ${move} from ${a.name} shakes the cage floor! ${b.name} is not moving — the slam switched the lights off!`,
      ]),
      b.p,
    );
  },

  takedownStuffed(t: UsageTracker, a: Who, b: Who): string {
    return pron(
      t.pick('n.tdStuffed', [
        `${a.name} shoots but ${b.name} sprawls beautifully and stays upright.`,
        `${b.name} stuffs the takedown and shrugs ${a.name} off.`,
        `${a.name} dives on a leg — ${b.name}'s takedown defense holds.`,
        `Denied! ${b.name} reads the shot and shuts it down cold.`,
        `${a.name} telegraphs the entry and ${b.name} makes [him] pay for the real estate.`,
      ]),
      a.p,
    );
  },

  clinchWork(t: UsageTracker, a: Who, b: Who): string {
    return pron(
      t.pick('n.clinch', [
        `${a.name} presses ${b.name} into the fence and lands short knees.`,
        `${a.name} controls the clinch, working dirty boxing on ${b.name}.`,
        `${a.name} grinds ${b.name} against the cage with heavy pressure.`,
        `The fight stalls on the fence — ${a.name} winning the grip battle and banking control time.`,
      ]),
      b.p,
    );
  },

  groundStrikes(t: UsageTracker, a: Who, b: Who): string {
    return pron(
      t.pick('n.gnp', [
        `${a.name} postures up and rains down ground-and-pound on ${b.name}.`,
        `${a.name} lands heavy elbows from top position.`,
        `${a.name} is busy from the top, punishing ${b.name} with short shots.`,
        `${b.name} is wearing punches on the ground — ${a.name} methodical from top position.`,
      ]),
      b.p,
    );
  },

  subAttempt(t: UsageTracker, a: Who, b: Who, sub: SubTech): string {
    return pron(
      t.pick('n.subAttempt', [
        `${a.name} locks in a ${sub.phrase}! ${b.name} is fighting the hands...`,
        `${a.name} threatens with a tight ${sub.phrase} — this looks deep!`,
        `${a.name} isolates a limb and attacks with a ${sub.phrase}!`,
        `Danger! ${a.name} has the ${sub.phrase} locked and is starting to squeeze — ${b.name}'s corner is screaming instructions!`,
        `${a.name} snatches up a ${sub.phrase} out of the scramble!`,
      ]),
      b.p,
    );
  },

  subEscape(t: UsageTracker, a: Who, b: Who, sub: SubTech): string {
    return pron(
      t.pick('n.subEscape', [
        `${b.name} survives the ${sub.phrase} and slips free!`,
        `${b.name} works [his] way out of the ${sub.phrase} — great defense.`,
        `Somehow ${b.name} escapes the ${sub.phrase} and scrambles clear.`,
        `${b.name} finds the one exit from the ${sub.phrase} and takes it!`,
      ]),
      b.p,
    );
  },

  standup(t: UsageTracker, a: Who): string {
    return pron(
      t.pick('n.standup', [
        `${a.name} works back to [his] feet.`,
        `${a.name} scrambles up and resets in open space.`,
        `${a.name} builds [his] base and stands.`,
        `${a.name} fights the grips, wall-walks, and gets the fight back to standing.`,
      ]),
      a.p,
    );
  },

  sweep(t: UsageTracker, a: Who): string {
    return pron(
      t.pick('n.sweep', [
        `${a.name} hits a slick sweep and comes out on top!`,
        `${a.name} reverses position — huge momentum shift on the ground!`,
        `Beautiful reversal by ${a.name} — bottom to top in a blink!`,
        `${a.name} times the sweep perfectly and steals top position!`,
      ]),
      a.p,
    );
  },

  roundEnd(round: number, a: string, b: string, aStrikes: number, bStrikes: number): string {
    return `End of round ${round}. Significant strikes: ${a} ${aStrikes}, ${b} ${bStrikes}.`;
  },

  ko(t: UsageTracker, a: Who, b: Who, tier: FinishTier, round: number, time: number): string {
    if (tier === 'flash') {
      return pron(
        t.pick('n.ko.flash', [
          `${b.name} tries to rise on jelly legs — one step, two — and the referee wraps [him] up! It's waved off at ${fmt(time)} of round ${round}! ${a.name} by KO!`,
          `${b.name} is up too fast and [his] legs are lying to [him]! The referee catches the stumble and stops it — ${a.name} wins by KO at ${fmt(time)} of round ${round}!`,
          `[He] beat the count of instinct but the ankles roll like a newborn foal's — the referee has seen enough at ${fmt(time)} of round ${round}. ${a.name} by KO!`,
        ]),
        b.p,
      );
    }
    if (tier === 'deep') {
      return pron(
        t.pick('n.ko.deep', [
          `${b.name} is out COLD — unconscious before [he] hit the canvas! ${a.name} by devastating KO at ${fmt(time)} of round ${round}! The referee didn't even count!`,
          `GOODNIGHT! ${b.name} melted where [he] stood — ${a.name} switches the lights off at ${fmt(time)} of round ${round} and the snoring starts before the referee lands on [his] knees!`,
          `Everything went quiet for a heartbeat — then the arena EXPLODED! ${b.name} is deeply, deeply unconscious. ${a.name} by KO, ${fmt(time)} of round ${round}!`,
        ]),
        b.p,
      );
    }
    return pron(
      t.pick('n.ko.stiff', [
        `IT'S ALL OVER! ${b.name} went rigid on the way down — stiff as a board! ${a.name} by KO at ${fmt(time)} of round ${round}!`,
        `${b.name} is OUT! Eyes open, nobody home — the referee waves it off at ${fmt(time)} of round ${round}! ${a.name} by knockout!`,
        `${b.name} timbers over like a felled tree and the fencing response fires on impact! ${a.name} wins by KO at ${fmt(time)} of round ${round}!`,
      ]),
      b.p,
    );
  },

  tko(t: UsageTracker, a: Who, b: Who, round: number, time: number): string {
    return pron(
      t.pick('n.tko', [
        `The referee has seen enough! ${a.name} wins by TKO at ${fmt(time)} of round ${round} — ${b.name} was taking too much damage.`,
        `${a.name} swarms and the referee steps in! TKO at ${fmt(time)} of round ${round}.`,
        `${b.name} is not defending [himself] — the referee rescues [him] at ${fmt(time)} of round ${round}. TKO for ${a.name}.`,
        `A flurry with no answer! It's waved off at ${fmt(time)} of round ${round} — ${a.name} by TKO.`,
      ]),
      b.p,
    );
  },

  submissionWin(t: UsageTracker, a: Who, b: Who, sub: SubTech, round: number, time: number): string {
    return pron(
      t.pick('n.subWin', [
        `${b.name} taps! ${a.name} wins by ${sub.phrase} at ${fmt(time)} of round ${round}!`,
        `The tap comes! ${a.name} finishes the ${sub.phrase} at ${fmt(time)} of round ${round}!`,
        `There's no way out — ${b.name} surrenders to the ${sub.phrase} at ${fmt(time)} of round ${round}!`,
        `${a.name} squeezes and ${b.name} has to tap! ${sub.phrase} finish at ${fmt(time)} of round ${round}!`,
      ]),
      b.p,
    );
  },

  submissionSleep(t: UsageTracker, a: Who, b: Who, sub: SubTech, round: number, time: number): string {
    return pron(
      t.pick('n.subSleep', [
        `${b.name} REFUSED to tap — and the ${sub.phrase} took the decision away! [He's] out! The referee dives in at ${fmt(time)} of round ${round} — technical submission for ${a.name}!`,
        `The hands went from clawing to brushing to gone... ${b.name} is asleep in the ${sub.phrase}! ${a.name} puts [him] out at ${fmt(time)} of round ${round}!`,
        `"[He's] out! [HE'S] OUT!" — the referee peels ${a.name} off at ${fmt(time)} of round ${round}. ${b.name} went to sleep rather than tap to the ${sub.phrase}. Heart, and the price of it.`,
      ]),
      b.p,
    );
  },

  aftermath(t: UsageTracker, a: Who, b: Who, tier: FinishTier): string {
    if (tier === 'flash') {
      return pron(
        t.pick('n.after.flash', [
          `${b.name} is arguing with the referee through eyes that won't focus — "I'm good, I'm good!" — while [his] legs vote no confidence beneath [him].`,
          `The replay shows it clean: ${b.name} never saw it. [He's] sitting against the fence now, blinking hard, shaking [his] head at nobody.`,
          `${b.name}'s cornerman is already in the cage with the ice bag. [He] keeps trying to stand; the referee keeps sitting [him] back down.`,
        ]),
        b.p,
      );
    }
    if (tier === 'sleep') {
      return pron(
        t.pick('n.after.sleep', [
          `${b.name} is stretched out with [his] toes curled tight and one foot twitching on a slow rhythm — the wet, guttural snore tells the whole story. The referee waves the doctor in.`,
          `The referee checks ${b.name} and shakes [his] head: "Out cold." The legs are stiff, feet pointed, and the snore is audible three rows back.`,
          `${b.name}'s hands slid off the choke like [he] was falling asleep mid-sentence. Now the whole arena watches the involuntary twitching and holds its breath.`,
        ]),
        b.p,
      );
    }
    if (tier === 'deep') {
      return pron(
        t.pick('n.after.deep', [
          `${b.name} hasn't moved. The snoring started before ${a.name} finished celebrating — deep, wet, rattling. The doctor is kneeling at [his] head, thumbs at the eyelids.`,
          `The referee took one look at ${b.name} and threw both arms in the air — no count, no doubt. [His] eyes are open and rolled back, seeing nothing.`,
          `It's uncomfortably quiet cageside. ${b.name} is in a heap, breathing on autopilot, one glove twitching once... twice... then still.`,
        ]),
        b.p,
      );
    }
    return pron(
      t.pick('n.after.stiff', [
        `${b.name} hit the canvas and the fencing response fired — one arm locked toward the lights, the other curled to [his] chest. The crowd's roar dies to a murmur while the referee kneels over [him].`,
        `${b.name} is stiff as a mannequin, shoulders rolled toward [his] chin, one finger drumming an involuntary rhythm on the canvas. "Lights on, nobody home," the doctor mutters, checking [his] pupils.`,
        `The stiffening is the scary part — ${b.name} locked into a bent pose no conscious person would hold, then slowly, slowly settling flat while the first rattling snore climbs out.`,
      ]),
      b.p,
    );
  },

  wakeup(t: UsageTracker, a: Who, b: Who, tier: FinishTier): string {
    if (tier === 'flash') {
      return pron(
        t.pick('n.wake.flash', [
          `${b.name} is back within seconds, embarrassed more than hurt: "I was up! I was UP!" The referee just pats [his] shoulder and points at the replay screen.`,
          `"What'd [he] catch me with?" ${b.name} asks the cutman, who answers by holding up the ice bag. [He'll] want that one back.`,
        ]),
        b.p,
      );
    }
    return pron(
      t.pick('n.wake', [
        `${b.name} comes to mid-sentence — "Wait, what? Did the fight start yet?" The referee keeps a hand on [his] chest: "It's over. You got caught. Sit for a minute — it was a bad one."`,
        `The twitching turns into real movement, then ${b.name}'s eyes finally catch and focus. [He] tries to stand immediately; three sets of hands ease [him] back down onto the stool.`,
        `${b.name} wakes up asking for [his] mouthguard. It's still in. The doctor holds up two fingers; ${b.name} guesses wrong, smiles anyway, and the stretcher stands down as [he] finally sits up on [his] own.`,
        `A groan, a slow roll to one elbow, and ${b.name} is back among the living — no memory of the finish, reaching up to check [his] jaw like [he's] making sure it's still attached.`,
      ]),
      b.p,
    );
  },

  decision(winner: string | null, method: string, scores: string): string {
    if (!winner) return `The judges score it a draw (${scores}).`;
    return `${winner} wins by ${method.toLowerCase()} (${scores}).`;
  },
};

export { fmt as formatClock };
