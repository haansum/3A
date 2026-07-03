import { ATTRIBUTE_KEYS, type Attributes, type Fighter, type FightingStyle } from './types';

export function makeId(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.floor(Math.random() * 1e9).toString(36)}`;
}

export function createFighter(
  name: string,
  style: FightingStyle,
  attributes: Attributes,
  nickname?: string,
): Fighter {
  return { id: makeId('f'), name, nickname, style, attributes, wins: 0, losses: 0, draws: 0 };
}

/** Simple average rating for display/seeding purposes. */
export function overallRating(f: Fighter): number {
  const sum = ATTRIBUTE_KEYS.reduce((acc, k) => acc + f.attributes[k], 0);
  return Math.round(sum / ATTRIBUTE_KEYS.length);
}

export function defaultAttributes(): Attributes {
  return {
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
  };
}

const a = (
  striking: number,
  power: number,
  speed: number,
  chin: number,
  cardio: number,
  wrestling: number,
  submissions: number,
  grapplingDefense: number,
  fightIQ: number,
  aggression: number,
  heart: number,
): Attributes => ({
  striking,
  power,
  speed,
  chin,
  cardio,
  wrestling,
  submissions,
  grapplingDefense,
  fightIQ,
  aggression,
  heart,
});

/** Starter roster so the app is usable on first launch. */
export function presetFighters(): Fighter[] {
  return [
    createFighter('Marcus Cole', 'pressure', a(88, 78, 82, 75, 90, 55, 45, 70, 80, 85, 82), 'The Machine'),
    createFighter('Dmitri Volkov', 'counter', a(92, 84, 88, 72, 74, 50, 48, 75, 92, 45, 70), 'The Surgeon'),
    createFighter('Hank Boulder', 'wrestler', a(58, 72, 65, 82, 84, 94, 62, 88, 78, 70, 88), 'Granite'),
    createFighter('João Ribeiro', 'submission', a(62, 58, 70, 74, 78, 76, 95, 85, 84, 60, 80), 'Anaconda'),
    createFighter('Tommy Ruckus', 'brawler', a(70, 95, 72, 90, 60, 40, 30, 45, 50, 95, 95), 'Ruckus'),
    createFighter('Ken Sato', 'balanced', a(80, 70, 80, 76, 82, 74, 72, 78, 88, 65, 78), 'Zen'),
    createFighter('Ezekiel Brand', 'pressure', a(76, 88, 74, 68, 72, 60, 50, 65, 68, 88, 75), 'Hellfire'),
    createFighter('Otis Freeman', 'wrestler', a(64, 76, 70, 78, 76, 88, 74, 82, 74, 72, 84), 'Bulldozer'),
  ];
}
