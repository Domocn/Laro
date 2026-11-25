import { describe, expect, it } from 'vitest';
import {
  confirmedPayload,
  isUncertain,
  labelToMacros,
  overrideFrom,
  splitLines,
  totalsFor,
} from './checkNumbers';

// Pesto Pasta-like fixture: two AI lines, the rest trusted database lines.
const LINES = [
  { index: 0, line: '400 g dried spaghetti', amount: '400', unit: 'g', name: 'dried spaghetti', uncertain: false,
    macros: { p: 52, c: 296, f: 6, cal: 1420, src: 'db', g: 400, source: 'cofid' } },
  { index: 1, line: '1 bunch basil', amount: '1', unit: 'bunch', name: 'basil', uncertain: true,
    reasons: ['AI estimate', 'Vague amount'], macros: { p: 1, c: 1, f: 0, cal: 9, src: 'ai' } },
  { index: 2, line: 'drizzle of olive oil', amount: '', unit: '', name: 'drizzle of olive oil', uncertain: true,
    reasons: ['AI estimate', 'Vague amount'], macros: { p: 0, c: 0, f: 14, cal: 120, src: 'ai' } },
  { index: 3, line: '50 g parmesan', amount: '50', unit: 'g', name: 'parmesan', uncertain: false,
    macros: { p: 18, c: 0, f: 15, cal: 204, src: 'db', g: 50, source: 'cofid' } },
  { index: 4, line: '30 g pine nuts', amount: '30', unit: 'g', name: 'pine nuts', uncertain: false,
    macros: { p: 4, c: 1, f: 21, cal: 206, src: 'db', g: 30, source: 'usda' } },
];

describe('uncertain-line selection', () => {
  it('puts AI / vague lines first and keeps trusted database lines aside', () => {
    const { uncertain, trusted } = splitLines(LINES);
    expect(uncertain.map((r) => r.name)).toEqual(['basil', 'drizzle of olive oil']);
    expect(trusted.map((r) => r.name)).toEqual(['dried spaghetti', 'parmesan', 'pine nuts']);
  });

  it('treats missing numbers, AI badges and weightless lines as uncertain even without a server flag', () => {
    expect(isUncertain({ index: 0, macros: null })).toBe(true);
    expect(isUncertain({ index: 0, macros: { p: 1, c: 1, f: 1, cal: 10, src: 'ai' } })).toBe(true);
    expect(isUncertain({ index: 0, macros: { p: 1, c: 1, f: 1, cal: 10, src: 'db' } })).toBe(true);
    expect(isUncertain({ index: 0, macros: { p: 0, c: 0, f: 0, cal: 0, src: 'db' } })).toBe(false);
    expect(isUncertain({ index: 0, confirmed: true, uncertain: true, macros: { src: 'user' } })).toBe(false);
    expect(isUncertain({ index: 0, macros: { p: 1, c: 1, f: 1, cal: 10, src: 'user' } })).toBe(false);
  });
});

describe('totals recompute', () => {
  it('sums the lines per serving and follows the user fixes live', () => {
    expect(totalsFor(LINES, {}, 4)).toEqual({ calories: 490, protein: 19, carbs: 75, fat: 14, complete: true });
    const edits = { 2: { macros: { p: 0, c: 0, f: 5, cal: 45, g: 5 }, source: 'user' } };
    expect(totalsFor(LINES, edits, 4).calories).toBe(Math.round((1420 + 9 + 45 + 204 + 206) / 4));
  });

  it('flags incomplete totals when a line has no numbers', () => {
    const lines = [...LINES, { index: 5, line: 'salt', macros: null }];
    expect(totalsFor(lines, {}, 4).complete).toBe(false);
    expect(totalsFor(lines, { 5: { macros: { p: 0, c: 0, f: 0, cal: 0 } } }, 4).complete).toBe(true);
  });

  it('builds the per-cook override only when something was checked', () => {
    const totals = totalsFor(LINES, {}, 4);
    expect(overrideFrom(totals, {})).toBeNull();
    const edits = { 1: { macros: { p: 1, c: 1, f: 0, cal: 9 }, source: 'user' } };
    expect(overrideFrom(totalsFor(LINES, edits, 4), edits)).toEqual({ calories: 490, protein: 19, carbs: 75, fat: 14 });
  });
});

describe('label maths', () => {
  it('scales per-100 g figures by the grams used', () => {
    expect(labelToMacros({ kcal: 884, protein: 0, carbs: 0, fat: 100 }, { usedG: '13.5' }))
      .toEqual({ macros: { cal: 119, p: 0, c: 0, f: 14, g: 13.5 } });
  });

  it('scales per-pack figures by the packs used', () => {
    expect(labelToMacros({ kcal: 200, protein: 10, carbs: 20, fat: 5 }, { basis: 'pack', packs: 0.5, packG: 80 }))
      .toEqual({ macros: { cal: 100, p: 5, c: 10, f: 3, g: 40 } });
  });

  it('explains what is missing in plain words', () => {
    expect(labelToMacros({ kcal: 100 }, { usedG: 10 }).error).toMatch(/protein/);
    expect(labelToMacros({ kcal: 100, protein: 1, carbs: 1, fat: 1 }, {}).error).toMatch(/grams/);
    expect(labelToMacros({ kcal: 2000, protein: 1, carbs: 1, fat: 1 }, { usedG: 10 }).error).toMatch(/950/);
  });
});

describe('save payload', () => {
  it('sends only fixed lines with their source', () => {
    const edits = {
      2: { macros: { p: 0, c: 0, f: 9, cal: 82, g: 10 }, source: 'barcode', barcode: '8001250120083', product: 'Olive oil' },
    };
    expect(confirmedPayload(LINES, edits)).toEqual([
      { index: 2, line: 'drizzle of olive oil', p: 0, c: 0, f: 9, cal: 82, g: 10, source: 'barcode',
        barcode: '8001250120083', product: 'Olive oil' },
    ]);
  });
});
