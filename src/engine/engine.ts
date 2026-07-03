import { narrate } from './narration';
import { logistic, Rng } from './rng';
import {
  cleanHitScene,
  clinchScene,
  finishScene,
  groundStrikesScene,
  standupScene,
  strikeScene,
  submissionScene,
  sweepScene,
  takedownScene,
  type SceneFighter,
} from './scenes';
import { STANCE_WEIGHTS, styleMultiplier, SUB_HUNT } from './styleMatrix';
import { pickStrike, pickSub, pickTakedown } from './techniques';
import type {
  FightConfig,
  FightEvent,
  Fighter,
  FighterFightStats,
  FightMethod,
  FightResult,
  SceneDescription,
  Scorecard,
} from './types';

/**
 * Round-by-round fight simulation with exchange-level events.
 *
 * Each 5-minute round is a sequence of exchanges. In every exchange the
 * fighters choose actions from their style profile (strike / shoot /
 * clinch, or ground actions when the fight hits the mat), rolls are
 * resolved against effective attributes (degraded by fatigue and damage),
 * and notable moments are logged as replicable, seeded play-by-play.
 */

const ROUND_SECONDS = 300;
const KO_DAMAGE = 100; // accumulating past this risks stoppage

type Position = 'standing' | 'clinch' | 'ground';

interface RoundStats {
  strikes: number;
  knockdowns: number;
  takedowns: number;
  subAttempts: number;
  control: number;
}

interface FighterState {
  f: Fighter;
  damage: number;
  stamina: number;
  staminaCap: number;
  /** Exchanges remaining in a hurt/compromised state */
  rockedFor: number;
  /** Per-fight form: fighters have good and bad nights */
  form: number;
  styleMul: number;
  stats: FighterFightStats;
  round: RoundStats;
  rounds: RoundStats[];
}

function newRoundStats(): RoundStats {
  return { strikes: 0, knockdowns: 0, takedowns: 0, subAttempts: 0, control: 0 };
}

function newState(f: Fighter, opp: Fighter, rng: Rng, carry?: { damage: number; staminaCap: number }): FighterState {
  const staminaCap = Math.min(100, Math.max(60, carry?.staminaCap ?? 100));
  return {
    f,
    damage: Math.min(50, Math.max(0, carry?.damage ?? 0)),
    stamina: staminaCap,
    staminaCap,
    rockedFor: 0,
    form: 1 + rng.gauss() * 0.065,
    styleMul: styleMultiplier(f.style, opp.style),
    stats: {
      sigStrikes: 0,
      sigStrikesThrown: 0,
      knockdowns: 0,
      takedowns: 0,
      takedownsAttempted: 0,
      subAttempts: 0,
      controlSeconds: 0,
      damageTaken: 0,
      staminaLeft: 100,
    },
    round: newRoundStats(),
    rounds: [],
  };
}

/** Overall condition multiplier applied to every roll. */
function condition(s: FighterState): number {
  const staminaFactor = 0.55 + 0.45 * (s.stamina / 100);
  const dmg = Math.min(100, s.damage) / 100;
  const hurtFactor = 1 - 0.38 * dmg * (1 - s.f.attributes.heart / 280);
  const rocked = s.rockedFor > 0 ? 0.72 : 1;
  return staminaFactor * hurtFactor * rocked * s.styleMul * s.form;
}

/** Effective attribute value after condition. */
function eff(s: FighterState, attr: keyof Fighter['attributes']): number {
  return s.f.attributes[attr] * condition(s);
}

function spend(s: FighterState, cost: number) {
  const burn = cost * (1.7 - s.f.attributes.cardio / 100);
  s.stamina = Math.max(5, s.stamina - burn);
}

function dealDamage(target: FighterState, amount: number) {
  target.damage += amount;
  target.stats.damageTaken += amount;
}

function strikeDamage(rng: Rng, attacker: FighterState, target: FighterState, lo: number, hi: number): number {
  const powerScale = 0.7 + eff(attacker, 'power') / 100;
  const chinScale = 90 / (50 + target.f.attributes.chin);
  return rng.range(lo, hi) * powerScale * chinScale;
}

interface Finish {
  method: FightMethod;
  winner: 0 | 1;
  round: number;
  time: number;
}

export function simulateFight(fighterA: Fighter, fighterB: Fighter, config: FightConfig): FightResult {
  const rng = new Rng(config.seed);
  const events: FightEvent[] = [];
  const A = newState(fighterA, fighterB, rng, config.carryoverA);
  const B = newState(fighterB, fighterA, rng, config.carryoverB);
  const S: [FighterState, FighterState] = [A, B];
  const name = (i: 0 | 1) => S[i].f.name;
  const other = (i: 0 | 1): 0 | 1 => (i === 0 ? 1 : 0);

  // Shared ring state (mutated by the exchange helpers below);
  // controller = who is on top / controlling the clinch
  const ring = { position: 'standing' as Position, controller: 0 as 0 | 1 };
  // Accessor defeats TS control-flow narrowing: helpers mutate ring.position
  // through closures, which the checker can't see at the call sites
  const currentPosition = (): Position => ring.position;
  let finish: Finish | null = null;
  let round = 1;
  let clock = 0;

  const log = (type: FightEvent['type'], text: string, actor?: 0 | 1, scene?: SceneDescription) => {
    events.push({
      round,
      time: clock,
      type,
      actorId: actor === undefined ? undefined : S[actor].f.id,
      targetId: actor === undefined ? undefined : S[other(actor)].f.id,
      text,
      scene,
    });
  };

  /** Snapshot of a fighter's current condition for the scene builder. */
  const sf = (i: 0 | 1): SceneFighter => ({
    id: S[i].f.id,
    name: S[i].f.name,
    cond: {
      tired: S[i].stamina < 40,
      hurt: S[i].damage > 45,
      rocked: S[i].rockedFor > 0,
    },
  });

  /** Knockout / stoppage checks after damage lands. Returns true if over. */
  const checkStoppage = (attacker: 0 | 1, wasKnockdown: boolean): boolean => {
    const t = S[other(attacker)];
    if (wasKnockdown) {
      const finisherInstinct = eff(S[attacker], 'power') / 500;
      const pKO = Math.min(0.85, Math.max(0.12, 0.18 + finisherInstinct + (t.damage - 65) / 130));
      if (rng.chance(pKO)) {
        finish = { method: 'KO', winner: attacker, round, time: clock };
        log(
          'ko',
          narrate.ko(rng, name(attacker), name(other(attacker)), round, clock),
          attacker,
          finishScene(rng, sf(attacker), sf(other(attacker)), 'ko'),
        );
        return true;
      }
    }
    if (t.damage >= KO_DAMAGE + 5 + t.f.attributes.heart / 10) {
      finish = { method: 'TKO', winner: attacker, round, time: clock };
      log(
        'tko',
        narrate.tko(rng, name(attacker), name(other(attacker)), round, clock),
        attacker,
        finishScene(rng, sf(attacker), sf(other(attacker)), 'tko'),
      );
      return true;
    }
    return false;
  };

  /** One striking exchange on the feet. Returns true if the fight ended. */
  const strikingExchange = (): boolean => {
    for (const i of [0, 1] as const) {
      const me = S[i];
      const op = S[other(i)];
      const throws = 1 + (rng.next() < me.f.attributes.aggression / 110 ? 1 : 0) + (rng.next() < me.f.attributes.aggression / 220 ? 1 : 0);
      for (let k = 0; k < throws; k++) {
        me.stats.sigStrikesThrown++;
        spend(me, 0.9);
        const defense = 0.6 * eff(op, 'speed') + 0.4 * eff(op, 'fightIQ');
        let pLand = logistic(eff(me, 'striking') - defense, 26, 0.44);
        if (me.f.style === 'counter' && op.f.attributes.aggression > 60) pLand += 0.05;
        if (op.rockedFor > 0) pLand += 0.15;
        if (!rng.chance(pLand)) continue;
        me.stats.sigStrikes++;
        me.round.strikes++;
        let dmg = strikeDamage(rng, me, op, 2.5, 5.5);
        const tech = pickStrike(rng, me.f.style);
        // Heavy shot: power vs chin, more likely against a worn opponent
        const pBig = 0.05 + eff(me, 'power') / 650 + Math.min(60, op.damage) / 500;
        if (rng.chance(pBig)) {
          dmg += strikeDamage(rng, me, op, 7, 14);
          const pKD = logistic(eff(me, 'power') - eff(op, 'chin'), 45, 0.3) * (0.55 + Math.min(100, op.damage) / 160);
          if (rng.chance(pKD)) {
            dealDamage(op, dmg + rng.range(5, 10));
            op.rockedFor = 3;
            me.stats.knockdowns++;
            me.round.knockdowns++;
            log(
              'knockdown',
              narrate.knockdown(rng, name(i), name(other(i)), tech),
              i,
              strikeScene(rng, sf(i), sf(other(i)), tech.kind, 'knockdown'),
            );
            if (checkStoppage(i, true)) return true;
            continue;
          }
          op.rockedFor = 2;
          dealDamage(op, dmg);
          log(
            'big_strike',
            narrate.bigStrike(rng, name(i), name(other(i)), tech),
            i,
            strikeScene(rng, sf(i), sf(other(i)), tech.kind, 'rocked'),
          );
          if (checkStoppage(i, false)) return true;
          continue;
        }
        dealDamage(op, dmg);
        if (checkStoppage(i, false)) return true;
        // Log ordinary landed strikes sparingly so the log stays readable
        if (rng.chance(0.22)) {
          log(
            'exchange',
            narrate.exchange(rng, name(i), name(other(i)), tech),
            i,
            cleanHitScene(rng, sf(i), sf(other(i)), tech.kind),
          );
        }
      }
    }
    return false;
  };

  /**
   * A counter shot against a fighter shooting a takedown (the classic
   * intercepting knee / uppercut). Returns 'ended' if it finished the
   * fight, 'broken' if it hurt the shooter enough to kill the takedown.
   */
  const counterOnShot = (defender: 0 | 1): 'ended' | 'broken' | 'none' => {
    const d = S[defender];
    const shooter = S[other(defender)];
    let dmg = strikeDamage(rng, d, shooter, 3, 7);
    d.stats.sigStrikes++;
    d.stats.sigStrikesThrown++;
    d.round.strikes++;
    const tech = pickStrike(rng, d.f.style);
    const pBig = 0.08 + eff(d, 'power') / 550;
    if (rng.chance(pBig)) {
      dmg += strikeDamage(rng, d, shooter, 7, 14);
      const pKD = logistic(eff(d, 'power') - eff(shooter, 'chin'), 40, 0.35);
      if (rng.chance(pKD)) {
        dealDamage(shooter, dmg + rng.range(5, 10));
        shooter.rockedFor = 3;
        d.stats.knockdowns++;
        d.round.knockdowns++;
        log(
          'knockdown',
          narrate.knockdown(rng, d.f.name, shooter.f.name, tech),
          defender,
          strikeScene(rng, sf(defender), sf(other(defender)), tech.kind, 'knockdown'),
        );
        return checkStoppage(defender, true) ? 'ended' : 'broken';
      }
      shooter.rockedFor = 2;
      dealDamage(shooter, dmg);
      log(
        'big_strike',
        narrate.bigStrike(rng, d.f.name, shooter.f.name, tech),
        defender,
        strikeScene(rng, sf(defender), sf(other(defender)), tech.kind, 'rocked'),
      );
      return checkStoppage(defender, false) ? 'ended' : 'broken';
    }
    dealDamage(shooter, dmg);
    return checkStoppage(defender, false) ? 'ended' : 'none';
  };

  /** Takedown attempt by `i`. Returns true if the fight ended. */
  const takedownAttempt = (i: 0 | 1): boolean => {
    const me = S[i];
    const op = S[other(i)];
    me.stats.takedownsAttempted++;
    spend(me, 3.5);
    spend(op, 2.2);
    // Shooting from the outside is exposed to an intercepting strike
    const pIntercept = 0.1 + eff(op, 'speed') / 800 + (op.f.style === 'counter' ? 0.08 : 0);
    if (rng.chance(pIntercept)) {
      const counter = counterOnShot(other(i));
      if (counter === 'ended') return true;
      if (counter === 'broken') return false; // shot collapses, shooter hurt
    }
    const td = pickTakedown(rng, me.f.style);
    const pTD = logistic(eff(me, 'wrestling') - eff(op, 'grapplingDefense'), 30, 0.42) + (op.rockedFor > 0 ? 0.2 : 0);
    if (rng.chance(pTD)) {
      me.stats.takedowns++;
      me.round.takedowns++;
      ring.position = 'ground';
      ring.controller = i;
      log(
        'takedown',
        narrate.takedown(rng, name(i), name(other(i)), td),
        i,
        takedownScene(rng, sf(i), sf(other(i)), td.kind, true),
      );
    } else {
      log(
        'takedown_stuffed',
        narrate.takedownStuffed(rng, name(i), name(other(i))),
        other(i),
        takedownScene(rng, sf(i), sf(other(i)), td.kind, false),
      );
      // Sprawl-and-brawl: counter shot for the defender
      if (rng.chance(0.25 + eff(op, 'fightIQ') / 400)) {
        if (counterOnShot(other(i)) === 'ended') return true;
      }
    }
    return false;
  };

  /** One exchange on the ground. Returns true if the fight ended. */
  const groundExchange = (slotSeconds: number): boolean => {
    const top = S[ring.controller];
    const bot = S[other(ring.controller)];
    top.round.control += slotSeconds * 0.8;
    top.stats.controlSeconds += slotSeconds * 0.8;
    spend(top, 1.0);
    spend(bot, 1.8);

    // Bottom fighter tries to get up / sweep
    const escapeDrive = 0.35 + (bot.f.style === 'wrestler' || bot.f.style === 'counter' || bot.f.style === 'brawler' ? 0.15 : 0);
    if (rng.chance(escapeDrive)) {
      spend(bot, 2.0);
      const pUp = logistic(
        0.6 * eff(bot, 'grapplingDefense') + 0.4 * eff(bot, 'wrestling') - eff(top, 'wrestling'),
        30,
        0.34,
      );
      if (rng.chance(pUp)) {
        const botIdx = other(ring.controller);
        const topIdx = ring.controller;
        if ((bot.f.style === 'submission' || bot.f.style === 'balanced') && rng.chance(0.3)) {
          ring.controller = botIdx;
          log('sweep', narrate.sweep(rng, bot.f.name), botIdx, sweepScene(rng, sf(botIdx), sf(topIdx)));
        } else {
          ring.position = 'standing';
          log('standup', narrate.standup(rng, bot.f.name), botIdx, standupScene(rng, sf(botIdx), sf(topIdx)));
        }
        return false;
      }
    }

    // Top fighter works: submission hunt or ground and pound
    const subDrive = SUB_HUNT[top.f.style] * (0.35 + eff(top, 'submissions') / 160);
    if (rng.chance(subDrive)) {
      const ci = ring.controller;
      top.stats.subAttempts++;
      top.round.subAttempts++;
      spend(top, 3.5);
      spend(bot, 3.0);
      const fatigueBonus = (bot.stamina < 40 ? 0.08 : 0) + (bot.damage > 50 ? 0.1 : 0);
      const pLock = logistic(eff(top, 'submissions') - eff(bot, 'grapplingDefense'), 26, 0.2) + fatigueBonus;
      if (rng.chance(pLock)) {
        const sub = pickSub(rng);
        log(
          'sub_attempt',
          narrate.subAttempt(rng, top.f.name, bot.f.name, sub),
          ci,
          submissionScene(rng, sf(ci), sf(other(ci)), sub.kind, 'locked'),
        );
        const pEscape = logistic(eff(bot, 'grapplingDefense') - eff(top, 'submissions'), 30, 0.62) - fatigueBonus;
        if (rng.chance(pEscape)) {
          log(
            'sub_escape',
            narrate.subEscape(rng, top.f.name, bot.f.name, sub),
            other(ci),
            submissionScene(rng, sf(ci), sf(other(ci)), sub.kind, 'escape'),
          );
          if (rng.chance(0.4)) ring.position = 'standing';
        } else {
          finish = { method: 'Submission', winner: ci, round, time: clock };
          log(
            'submission',
            narrate.submissionWin(top.f.name, bot.f.name, sub, round, clock),
            ci,
            submissionScene(rng, sf(ci), sf(other(ci)), sub.kind, 'tap'),
          );
          return true;
        }
      }
      return false;
    }

    // Ground and pound
    const pLand = logistic(eff(top, 'striking') - eff(bot, 'grapplingDefense'), 30, 0.55);
    if (rng.chance(pLand)) {
      const dmg = strikeDamage(rng, top, bot, 3, 8);
      dealDamage(bot, dmg);
      top.stats.sigStrikes += 2;
      top.stats.sigStrikesThrown += 3;
      top.round.strikes += 2;
      if (rng.chance(0.35)) {
        log(
          'ground_strikes',
          narrate.groundStrikes(rng, top.f.name, bot.f.name),
          ring.controller,
          groundStrikesScene(rng, sf(ring.controller), sf(other(ring.controller))),
        );
      }
      if (checkStoppage(ring.controller, false)) return true;
    }
    return false;
  };

  /** One clinch exchange. Returns true if the fight ended. */
  const clinchExchange = (slotSeconds: number): boolean => {
    const c = S[ring.controller];
    const d = S[other(ring.controller)];
    c.round.control += slotSeconds * 0.5;
    c.stats.controlSeconds += slotSeconds * 0.5;
    spend(c, 1.4);
    spend(d, 1.6);
    const dmg = strikeDamage(rng, c, d, 1, 3);
    dealDamage(d, dmg);
    c.stats.sigStrikes++;
    c.stats.sigStrikesThrown++;
    c.round.strikes++;
    if (rng.chance(0.3)) {
      log(
        'clinch_work',
        narrate.clinchWork(rng, c.f.name, d.f.name),
        ring.controller,
        clinchScene(rng, sf(ring.controller), sf(other(ring.controller))),
      );
    }
    if (checkStoppage(ring.controller, false)) return true;
    // Trip takedown from the clinch
    if (rng.chance(0.12 + (c.f.style === 'wrestler' ? 0.15 : 0))) {
      return takedownAttempt(ring.controller);
    }
    // Break back to open space
    if (rng.chance(0.45)) ring.position = 'standing';
    return false;
  };

  // ---- Main loop ----
  outer: for (round = 1; round <= config.rounds; round++) {
    ring.position = 'standing';
    clock = 0;
    A.round = newRoundStats();
    B.round = newRoundStats();
    log('round_start', narrate.roundStart(round));

    const pace = (A.f.attributes.aggression + B.f.attributes.aggression) / 2;
    const staminaAvg = (A.stamina + B.stamina) / 2;
    const exchanges = Math.max(6, Math.round((9 + pace / 18) * (0.7 + 0.3 * (staminaAvg / 100))));
    const slot = ROUND_SECONDS / exchanges;

    for (let x = 0; x < exchanges; x++) {
      clock = Math.min(299, Math.round(slot * (x + 0.5) + rng.range(-slot / 3, slot / 3)));

      let over = false;
      const pos = currentPosition();
      if (pos === 'ground') {
        over = groundExchange(slot);
      } else if (pos === 'clinch') {
        over = clinchExchange(slot);
      } else {
        // Standing: pick intents from style profiles
        const intents = ([0, 1] as const).map((i) => {
          const w = { ...STANCE_WEIGHTS[S[i].f.style] };
          const op = S[other(i)];
          if (op.rockedFor > 0) w.strike *= 3; // swarm a hurt opponent
          // Hurt or outgunned grapplers look for the takedown
          if (S[i].damage > 40 && S[i].damage > op.damage + 15) w.takedown *= 1.6;
          const total = w.strike + w.takedown + w.clinch;
          const r = rng.next() * total;
          return r < w.takedown ? 'takedown' : r < w.takedown + w.clinch ? 'clinch' : 'strike';
        });

        if (intents[0] === 'takedown' || intents[1] === 'takedown') {
          // Faster, smarter fighter gets their entry first
          const first: 0 | 1 =
            intents[0] === 'takedown' && intents[1] === 'takedown'
              ? eff(A, 'speed') + rng.range(0, 20) > eff(B, 'speed') + rng.range(0, 20)
                ? 0
                : 1
              : intents[0] === 'takedown'
                ? 0
                : 1;
          over = takedownAttempt(first);
        } else if (intents[0] === 'clinch' || intents[1] === 'clinch') {
          const initiator: 0 | 1 = intents[0] === 'clinch' ? 0 : 1;
          const iSt = S[initiator];
          const oSt = S[other(initiator)];
          if (rng.chance(logistic(eff(iSt, 'wrestling') - eff(oSt, 'wrestling'), 35, 0.55))) {
            ring.position = 'clinch';
            ring.controller = initiator;
            over = clinchExchange(slot);
          } else {
            over = strikingExchange();
          }
        } else {
          over = strikingExchange();
        }
      }

      if (over) break outer;
      for (const s of S) if (s.rockedFor > 0) s.rockedFor--;
    }

    clock = 299;
    log('round_end', narrate.roundEnd(round, A.f.name, B.f.name, A.round.strikes, B.round.strikes));
    A.rounds.push(A.round);
    B.rounds.push(B.round);

    // Between rounds: one minute on the stool
    for (const s of S) {
      const cap = Math.min(s.staminaCap, 100 - Math.min(100, s.damage) * 0.2);
      s.stamina = Math.min(cap, s.stamina + 12 + s.f.attributes.cardio * 0.15);
      s.damage = Math.max(0, s.damage - 3);
      s.rockedFor = 0;
    }
  }

  // If the fight was finished early we broke out before the round closed
  if (A.rounds.length < round) {
    A.rounds.push(A.round);
    B.rounds.push(B.round);
  }

  A.stats.staminaLeft = Math.round(A.stamina);
  B.stats.staminaLeft = Math.round(B.stamina);

  // ---- Judging (if we went the distance) ----
  const scorecards: Scorecard[] = [];
  let method: FightMethod;
  let winnerId: string | null;
  let endRound: number;
  let endTime: number;

  if (finish) {
    const f: Finish = finish;
    method = f.method;
    winnerId = S[f.winner].f.id;
    endRound = f.round;
    endTime = f.time;
  } else {
    const judgeNames = ['Judge Cecil', 'Judge Sal', 'Judge Doug'];
    const verdicts: (0 | 1 | null)[] = [];
    for (const judge of judgeNames) {
      const rounds: [number, number][] = [];
      let totalA = 0;
      let totalB = 0;
      for (let r = 0; r < A.rounds.length; r++) {
        const ra = A.rounds[r];
        const rb = B.rounds[r];
        const ptsA = ra.strikes + 3 * ra.takedowns + 2.5 * ra.subAttempts + 8 * ra.knockdowns + ra.control / 30;
        const ptsB = rb.strikes + 3 * rb.takedowns + 2.5 * rb.subAttempts + 8 * rb.knockdowns + rb.control / 30;
        const margin = ptsA - ptsB + rng.gauss() * 1.8; // judges see fights differently
        let sA = 10;
        let sB = 10;
        if (margin > 0.5) sB = margin >= 9 || ra.knockdowns > 0 ? 8 : 9;
        else if (margin < -0.5) sA = margin <= -9 || rb.knockdowns > 0 ? 8 : 9;
        rounds.push([sA, sB]);
        totalA += sA;
        totalB += sB;
      }
      scorecards.push({ judge, rounds, totalA, totalB });
      verdicts.push(totalA > totalB ? 0 : totalB > totalA ? 1 : null);
    }
    const votesA = verdicts.filter((v) => v === 0).length;
    const votesB = verdicts.filter((v) => v === 1).length;
    const draws = verdicts.filter((v) => v === null).length;
    if (votesA === votesB) {
      method = 'Draw';
      winnerId = null;
    } else {
      const w = votesA > votesB ? 0 : 1;
      winnerId = S[w].f.id;
      const wVotes = Math.max(votesA, votesB);
      method = wVotes === 3 ? 'Unanimous Decision' : draws > 0 ? 'Majority Decision' : 'Split Decision';
    }
    endRound = config.rounds;
    endTime = 299;
    const scores = scorecards.map((c) => `${Math.max(c.totalA, c.totalB)}-${Math.min(c.totalA, c.totalB)}`).join(', ');
    clock = 299;
    log('decision', narrate.decision(winnerId ? (winnerId === A.f.id ? A.f.name : B.f.name) : null, method, scores));
  }

  return {
    id: `fight_${config.seed.toString(16)}_${Date.now().toString(36)}`,
    seed: config.seed,
    date: new Date().toISOString(),
    fighterAId: A.f.id,
    fighterBId: B.f.id,
    fighterAName: A.f.name,
    fighterBName: B.f.name,
    winnerId,
    method,
    endRound,
    endTime,
    scheduledRounds: config.rounds,
    events,
    statsA: A.stats,
    statsB: B.stats,
    scorecards,
  };
}
