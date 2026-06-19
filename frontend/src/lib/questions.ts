/**
 * Question catalogue presented in the seeker composer.
 *
 * The backend `question_asked` payload requires `category` (matching/measuring/radar/
 * thermometer) + a free-form `subtype` string + optional `params` for the deduction engine.
 * This list is a curated subset drawn from `data/game-config.json` (the SF small-game).
 */

import type { QuestionCategory } from './types';

export interface QuestionOption {
  category: QuestionCategory;
  subtype: string;
  label: string;
  /** Whether this question needs a numeric radius param (radar). */
  needsRadius?: boolean;
}

export const QUESTION_OPTIONS: QuestionOption[] = [
  // Measuring: "are you closer or further than me to the nearest X?"
  { category: 'measuring', subtype: 'rail-station', label: 'Measuring · Nearest Rail Station' },
  { category: 'measuring', subtype: 'museum', label: 'Measuring · Nearest Museum' },
  { category: 'measuring', subtype: 'library', label: 'Measuring · Nearest Library' },
  { category: 'measuring', subtype: 'hospital', label: 'Measuring · Nearest Hospital' },
  { category: 'measuring', subtype: 'consulate', label: 'Measuring · Nearest Consulate' },
  { category: 'measuring', subtype: 'coastline', label: 'Measuring · Coastline' },
  // Radar: "are you within N miles of me?"
  { category: 'radar', subtype: 'radius', label: 'Radar · Within radius', needsRadius: true },
  // Matching: "is your nearest X the same as mine?"
  { category: 'matching', subtype: 'rail-station', label: 'Matching · Same Rail Station' },
  { category: 'matching', subtype: 'district', label: 'Matching · Same District' },
  { category: 'matching', subtype: 'landmass', label: 'Matching · Same Landmass' },
  // Thermometer: "did I get warmer or colder after moving?"
  { category: 'thermometer', subtype: 'warmer-colder', label: 'Thermometer · Warmer / Colder' },
];

/** Plausible answer options keyed by category, for the hider's answer UI. */
export function answerOptions(category: string): string[] {
  switch (category) {
    case 'measuring':
      return ['closer', 'further', 'same'];
    case 'radar':
      return ['yes', 'no'];
    case 'matching':
      return ['yes', 'no'];
    case 'thermometer':
      return ['warmer', 'colder', 'same'];
    default:
      return ['yes', 'no'];
  }
}
