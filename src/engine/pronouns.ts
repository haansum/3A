/**
 * Pronoun support for narration and scene prose.
 *
 * Template strings use tokens — [he] [him] [his] [himself] and their
 * capitalized forms — which are rendered with the described fighter's
 * pronoun set. Each template line refers to exactly one fighter (the
 * subject); the other fighter is referenced as "the opponent" or by
 * name, so a single substitution pass per line is always correct.
 */

export type PronounKey = 'she' | 'he' | 'they';

export interface PronounSet {
  /** she / he / they */
  subject: string;
  /** her / him / them */
  object: string;
  /** her / his / their */
  possessive: string;
  /** herself / himself / themself */
  reflexive: string;
  /** she's / he's / they're (contraction of "is/are") */
  isContraction: string;
  /** was / was / were */
  was: string;
}

export const PRONOUNS: Record<PronounKey, PronounSet> = {
  she: { subject: 'she', object: 'her', possessive: 'her', reflexive: 'herself', isContraction: "she's", was: 'was' },
  he: { subject: 'he', object: 'him', possessive: 'his', reflexive: 'himself', isContraction: "he's", was: 'was' },
  they: { subject: 'they', object: 'them', possessive: 'their', reflexive: 'themself', isContraction: "they're", was: 'were' },
};

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Render pronoun tokens in a template with the subject's pronoun set. */
export function pron(text: string, key: PronounKey): string {
  const p = PRONOUNS[key];
  return text
    .replaceAll('[he]', p.subject)
    .replaceAll('[He]', cap(p.subject))
    .replaceAll('[him]', p.object)
    .replaceAll('[Him]', cap(p.object))
    .replaceAll('[his]', p.possessive)
    .replaceAll('[His]', cap(p.possessive))
    .replaceAll('[himself]', p.reflexive)
    .replaceAll("[he's]", p.isContraction)
    .replaceAll("[He's]", cap(p.isContraction))
    .replaceAll('[was]', p.was);
}
