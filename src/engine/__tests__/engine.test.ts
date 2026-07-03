import assert from 'node:assert/strict';
import { test } from 'node:test';

import { createFighter, presetFighters } from '../data';
import { simulateFight } from '../engine';
import { createTournament, simulateNextRound } from '../tournament';
import type { Attributes, Fighter, FightResult } from '../types';

const attrs = (overrides: Partial<Attributes> = {}): Attributes => ({
  striking: 60,
  power: 60,
  speed: 60,
  chin: 60,
  cardio: 60,
  wrestling: 60,
  submissions: 60,
  grapplingDefense: 60,
  fightIQ: 60,
  aggression: 60,
  heart: 60,
  ...overrides,
});

function winRate(a: Fighter, b: Fighter, n: number): { a: number; b: number; finishes: number; results: FightResult[] } {
  let aWins = 0;
  let bWins = 0;
  let finishes = 0;
  const results: FightResult[] = [];
  for (let i = 0; i < n; i++) {
    const r = simulateFight(a, b, { rounds: 3, seed: i * 7919 + 13 });
    if (r.winnerId === a.id) aWins++;
    if (r.winnerId === b.id) bWins++;
    if (r.method === 'KO' || r.method === 'TKO' || r.method === 'Submission') finishes++;
    results.push(r);
  }
  return { a: aWins / n, b: bWins / n, finishes: finishes / n, results };
}

test('same seed reproduces the exact same fight', () => {
  const [a, b] = presetFighters();
  const r1 = simulateFight(a, b, { rounds: 3, seed: 42 });
  const r2 = simulateFight(a, b, { rounds: 3, seed: 42 });
  assert.equal(r1.winnerId, r2.winnerId);
  assert.equal(r1.method, r2.method);
  assert.equal(r1.endRound, r2.endRound);
  // Full event objects — including scene kinematics — must be identical
  assert.deepEqual(r1.events, r2.events);
});

test('key moments carry animator-ready scene descriptions', () => {
  const roster = presetFighters();
  const sceneTypes = new Set([
    'knockdown',
    'big_strike',
    'exchange',
    'takedown',
    'takedown_stuffed',
    'sub_attempt',
    'sub_escape',
    'submission',
    'sweep',
    'standup',
    'ground_strikes',
    'clinch_work',
    'ko',
    'tko',
  ]);
  let scenesSeen = 0;
  for (let s = 0; s < 30; s++) {
    for (let i = 0; i < 4; i++) {
      const r = simulateFight(roster[i], roster[7 - i], { rounds: 3, seed: s * 613 + i });
      for (const e of r.events) {
        if (sceneTypes.has(e.type)) {
          assert.ok(e.scene, `${e.type} event should carry a scene`);
          scenesSeen++;
          for (const who of [e.scene!.actor, e.scene!.target]) {
            assert.ok(who.body.length > 20, `body kinematics should be descriptive: ${who.body}`);
            assert.ok(who.face.length > 5, 'facial expression required');
            assert.ok(who.motion.length > 5, 'motion description required');
            assert.ok(who.fighterId && who.name);
          }
          assert.ok(e.scene!.setting.length > 5, 'scene needs a setting');
        } else {
          assert.equal(e.scene, undefined, `${e.type} should not carry a scene`);
        }
      }
    }
  }
  assert.ok(scenesSeen > 100, `expected plenty of scenes across fights, saw ${scenesSeen}`);
});

test('different seeds produce different fights', () => {
  const [a, b] = presetFighters();
  const texts = new Set<string>();
  for (let s = 1; s <= 5; s++) {
    const r = simulateFight(a, b, { rounds: 3, seed: s });
    texts.add(r.events.map((e) => e.text).join('|'));
  }
  assert.ok(texts.size >= 4, 'expected variety across seeds');
});

test('a clearly better fighter wins most but not all fights', () => {
  const elite = createFighter('Elite', 'balanced', attrs({ striking: 90, power: 85, speed: 88, wrestling: 85, grapplingDefense: 88, fightIQ: 90, cardio: 85 }));
  const journeyman = createFighter('Journeyman', 'balanced', attrs({ striking: 50, power: 55, speed: 50, wrestling: 50, grapplingDefense: 50, fightIQ: 50, cardio: 55 }));
  const { a, b } = winRate(elite, journeyman, 300);
  assert.ok(a > 0.75, `elite should dominate, won ${a}`);
  assert.ok(b > 0.005, `journeyman needs a puncher's chance, won ${b}`);
});

test('mirror match is close to a coin flip', () => {
  const f1 = createFighter('Twin A', 'balanced', attrs());
  const f2 = createFighter('Twin B', 'balanced', attrs());
  const { a } = winRate(f1, f2, 400);
  assert.ok(a > 0.32 && a < 0.68, `mirror match win rate was ${a}`);
});

test('fights end by a healthy mix of methods', () => {
  const roster = presetFighters();
  const methods = new Map<string, number>();
  let n = 0;
  for (let i = 0; i < roster.length; i++) {
    for (let j = i + 1; j < roster.length; j++) {
      for (let s = 0; s < 12; s++) {
        const r = simulateFight(roster[i], roster[j], { rounds: 3, seed: n * 104729 + 7 });
        methods.set(r.method, (methods.get(r.method) ?? 0) + 1);
        n++;
      }
    }
  }
  const finishes = (methods.get('KO') ?? 0) + (methods.get('TKO') ?? 0) + (methods.get('Submission') ?? 0);
  const decisions = n - finishes;
  assert.ok(finishes / n > 0.15, `finish rate too low: ${finishes / n}`);
  assert.ok(decisions / n > 0.15, `decision rate too low: ${decisions / n}`);
  assert.ok((methods.get('Submission') ?? 0) > 0, 'submissions should occur across a varied roster');
  assert.ok(((methods.get('KO') ?? 0) + (methods.get('TKO') ?? 0)) > 0, 'knockouts should occur');
});

test('elite grappler beats one-dimensional brawler more often than not', () => {
  const grappler = createFighter('Grappler', 'submission', attrs({ wrestling: 88, submissions: 92, grapplingDefense: 85, striking: 50 }));
  const brawler = createFighter('Brawler', 'brawler', attrs({ striking: 70, power: 92, chin: 85, wrestling: 40, submissions: 25, grapplingDefense: 40 }));
  const { a, b } = winRate(grappler, brawler, 300);
  assert.ok(a > b, `grappler should be favored: grappler ${a} vs brawler ${b}`);
  assert.ok(b > 0.03, `brawler should still land the odd bomb, won ${b}`);
});

test('cardio matters: identical fighters, one with a bad gas tank', () => {
  const engine = createFighter('Engine', 'pressure', attrs({ cardio: 92 }));
  const gasser = createFighter('Gasser', 'pressure', attrs({ cardio: 25 }));
  const { a, b } = winRate(engine, gasser, 300);
  assert.ok(a > b, `better cardio should win out: ${a} vs ${b}`);
});

test('every fight has a coherent event log', () => {
  const roster = presetFighters();
  const r = simulateFight(roster[0], roster[4], { rounds: 3, seed: 1234 });
  assert.ok(r.events.length >= 5, 'expected a populated play-by-play');
  assert.equal(r.events[0].type, 'round_start');
  const last = r.events[r.events.length - 1];
  assert.ok(['ko', 'tko', 'submission', 'decision'].includes(last.type), `fight should end conclusively, got ${last.type}`);
  if (last.type === 'decision') {
    assert.equal(r.scorecards.length, 3);
    for (const card of r.scorecards) {
      assert.equal(card.rounds.length, 3);
    }
  }
  for (const e of r.events) {
    assert.ok(e.text.length > 0);
    assert.ok(e.round >= 1 && e.round <= 3);
    assert.ok(e.time >= 0 && e.time < 300);
  }
});

test('tournament runs to a champion', () => {
  const roster = presetFighters();
  const fighters: Record<string, Fighter> = Object.fromEntries(roster.map((f) => [f.id, f]));
  let t = createTournament('Test GP', roster.map((f) => f.id), { carryover: true, roundsPerFight: 3 });
  assert.equal(t.rounds.length, 3); // quarters, semis, final for 8

  const allResults: FightResult[] = [];
  for (let i = 0; i < 3; i++) {
    const { tournament, results } = simulateNextRound(t, fighters);
    t = tournament;
    allResults.push(...results);
  }
  assert.equal(allResults.length, 7); // 4 + 2 + 1
  assert.ok(t.championId, 'tournament should crown a champion');
  assert.ok(roster.some((f) => f.id === t.championId));
  // Carryover states should exist for winners
  assert.ok(Object.keys(t.carryStates).length >= 4);
  // Every match should reference a stored result
  for (const round of t.rounds) {
    for (const m of round) {
      assert.ok(m.resultId);
      assert.ok(m.winnerId);
    }
  }
});

test('carryover damage handicaps the next fight', () => {
  const f1 = createFighter('Fresh', 'balanced', attrs());
  const f2 = createFighter('Damaged', 'balanced', attrs());
  let wins = 0;
  const n = 300;
  for (let i = 0; i < n; i++) {
    const r = simulateFight(f1, f2, {
      rounds: 3,
      seed: i * 31 + 1,
      carryoverB: { damage: 35, staminaCap: 75 },
    });
    if (r.winnerId === f1.id) wins++;
  }
  assert.ok(wins / n > 0.55, `fresh fighter should be favored over a damaged twin, won ${wins / n}`);
});
