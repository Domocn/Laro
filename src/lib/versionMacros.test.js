import { macroSourceText, macrosForChoice, nutritionForPlan, scaleBadge, swapsApply, totalsFromBadges } from './versionMacros';
import { rollupDayNutrition } from './mealPlanNutrition';

const PASTA = { amount: '200', unit: 'g', name: 'pasta' };
const GARLIC = { amount: '2', unit: 'cloves', name: 'garlic' };
const TOFU = { amount: '450', unit: 'g', name: 'tofu' };

const tofuVersion = {
  name: 'Lemon Pepper Tofu',
  ingredients: [PASTA, GARLIC, TOFU],
  instructions: ['Cook'],
  nutrition: { calories: 307, protein: 23, carbs: 31, fat: 12 },
  ingredient_macros: [
    { p: 10, c: 50, f: 2, cal: 262 },
    { p: 0, c: 2, f: 0, cal: 9 },
    { p: 36, c: 9, f: 22, cal: 342 },
  ],
  low_fodmap_macros: {
    nutrition: { calories: 325, protein: 23, carbs: 30, fat: 15 },
    ingredient_macros: [
      { p: 10, c: 50, f: 2, cal: 262 },
      { p: 0, c: 0, f: 5, cal: 45 },
      { p: 36, c: 9, f: 22, cal: 342 },
    ],
  },
};

const recipe = {
  id: 'r1',
  servings: 2,
  ingredients: [PASTA, GARLIC],
  nutrition: { calories: 566, protein: 20, carbs: 70, fat: 22 },
  adaptations: {
    low_fodmap: { swaps: [{ from: 'garlic', to: 'garlic-infused oil' }] },
    low_fodmap_macros: {
      nutrition: { calories: 154, protein: 5, carbs: 25, fat: 4 },
      ingredient_macros: [{ p: 10, c: 50, f: 2, cal: 262 }, { p: 0, c: 0, f: 5, cal: 45 }],
    },
    versions: [tofuVersion, { name: 'Old Version', ingredients: [PASTA, TOFU], instructions: ['x'] }],
  },
};

const originalBadges = [{ p: 9, c: 49, f: 1, cal: 250 }, { p: 0, c: 1, f: 0, cal: 5 }];

describe('macrosForChoice', () => {
  it('uses the recipe and its fetched badges for the plain Original', () => {
    expect(macrosForChoice(recipe, '', false).nutrition.calories).toBe(566); // no badges yet
    const m = macrosForChoice(recipe, '', false, originalBadges);
    // Totals = sum(badges) / servings: (250 + 5) / 2, not the stale stored 566.
    expect(m.nutrition.calories).toBe(128);
    expect(m.nutrition.protein).toBe(5);
    expect(m.ingredientMacros).toBe(originalBadges);
    expect(m.pending).toBe(false);
    expect(m.variant).toBe(false);
  });

  it('switches totals and badges to the chosen version', () => {
    const m = macrosForChoice(recipe, 'lemon pepper tofu', false, originalBadges);
    expect(m.nutrition.calories).toBe(307);
    expect(m.ingredientMacros).toHaveLength(3);
    expect(m.ingredientMacros[2].p).toBe(36);
    expect(m.variant).toBe(true);
  });

  it('uses the Low FODMAP numbers for a version and for the Original', () => {
    expect(macrosForChoice(recipe, 'Lemon Pepper Tofu', true).nutrition.calories).toBe(325);
    expect(macrosForChoice(recipe, '', true, originalBadges).nutrition.calories).toBe(154);
    expect(macrosForChoice(recipe, '', true, originalBadges).ingredientMacros[1].f).toBe(5);
  });

  it('flags a version with no stored macros as pending (Original numbers, no badges)', () => {
    const m = macrosForChoice(recipe, 'Old Version', false, originalBadges);
    expect(m.pending).toBe(true);
    expect(m.nutrition.calories).toBe(566);
    expect(m.ingredientMacros).toBeNull();
  });

  it('Low FODMAP that changes nothing on the shown list keeps the plain numbers', () => {
    const noGarlic = {
      ...recipe,
      adaptations: { ...recipe.adaptations, versions: [{ ...tofuVersion, ingredients: [PASTA, TOFU], ingredient_macros: tofuVersion.ingredient_macros.slice(0, 2), low_fodmap_macros: undefined }] },
    };
    const m = macrosForChoice(noGarlic, 'Lemon Pepper Tofu', true);
    expect(m.pending).toBe(false);
    expect(m.nutrition.calories).toBe(136); // (262 + 9) / 2 from its own badges
  });

  it('drops badges that do not line up with the shown list', () => {
    const odd = { ...recipe, adaptations: { versions: [{ ...tofuVersion, ingredient_macros: [{ p: 1, c: 1, f: 1, cal: 1 }] }] } };
    expect(macrosForChoice(odd, 'Lemon Pepper Tofu', false).ingredientMacros).toBeNull();
  });
});

describe('totalsFromBadges', () => {
  it('is the badge sum over servings and keeps extra fields', () => {
    const out = totalsFromBadges([{ p: 10, c: 20, f: 5, cal: 165 }, { p: 1, c: 0, f: 9, cal: 85 }], 2, {
      calories: 999, fiber: 4, nutrition_estimated: true,
    });
    expect(out).toEqual({ calories: 125, protein: 6, carbs: 10, fat: 7, fiber: 4 });
    expect(totalsFromBadges([], 2)).toBeNull();
    expect(totalsFromBadges([{ cal: 100 }], 0).calories).toBe(100);
  });

  it('version totals always equal what its badges add up to', () => {
    const stale = { ...recipe, adaptations: { versions: [{ ...tofuVersion, nutrition: { calories: 900, protein: 1, carbs: 1, fat: 1 } }] } };
    const m = macrosForChoice(stale, 'Lemon Pepper Tofu', false);
    const sum = m.ingredientMacros.reduce((a, b) => a + b.cal, 0);
    expect(m.nutrition.calories).toBe(Math.round(sum / 2));
  });
});

describe('swapsApply', () => {
  it('is true only when a swap hits an ingredient', () => {
    expect(swapsApply([GARLIC], [{ from: 'garlic', to: 'oil' }])).toBe(true);
    expect(swapsApply([PASTA], [{ from: 'garlic', to: 'oil' }])).toBe(false);
    expect(swapsApply([GARLIC], [])).toBe(false);
  });
});

describe('scaleBadge', () => {
  it('scales and rounds each macro', () => {
    expect(scaleBadge({ p: 10, c: 5, f: 3, cal: 101 }, 1.5)).toEqual({ p: 15, c: 8, f: 5, cal: 152 });
    expect(scaleBadge({ p: 10 }, 0)).toEqual({ p: 10, c: 0, f: 0, cal: 0 });
  });
});

describe('meal plan totals follow the planned version', () => {
  it('nutritionForPlan picks version / Low FODMAP / Original', () => {
    expect(nutritionForPlan(recipe, { recipe_version: 'Lemon Pepper Tofu' }).calories).toBe(307);
    expect(nutritionForPlan(recipe, { recipe_version: 'Lemon Pepper Tofu', low_fodmap: true }).calories).toBe(325);
    expect(nutritionForPlan(recipe, {}).calories).toBe(566);
    expect(nutritionForPlan(recipe, { recipe_version: 'Old Version' }).calories).toBe(566);
  });

  it('rollupDayNutrition sums the planned version', () => {
    const meals = [
      { id: '1', recipe_id: 'r1', entry_type: 'recipe', recipe_version: 'Lemon Pepper Tofu' },
      { id: '2', recipe_id: 'r1', entry_type: 'recipe' },
    ];
    const totals = rollupDayNutrition(meals, [recipe]);
    expect(totals.calories).toBe(307 + 566);
    expect(totals.protein).toBe(23 + 20);
  });
});

describe('macroSourceText', () => {
  const en = {
    macroSrcMatched: 'Matched: {detail}', macroSrcAi: 'AI estimate', macroSrcFood: 'food database',
    macroSourceCofid: 'UK CoFID', macroSourceUsda: 'USDA FoodData Central', macroSourceCurated: 'Laro food table',
  };
  const t = (k, params = {}) => Object.entries(params).reduce((s, [p, v]) => s.replaceAll(`{${p}}`, String(v)), en[k] || k);

  it('describes a database match with grams and source', () => {
    const b = { p: 36, c: 9, f: 21, cal: 648, src: 'db', food: 'Tofu, firm, raw', g: 450, source: 'cofid' };
    expect(macroSourceText(b, t)).toBe('Matched: Tofu, firm, raw · 450 g · UK CoFID');
    expect(macroSourceText(b, t, 0.5)).toBe('Matched: Tofu, firm, raw · 225 g · UK CoFID');
    expect(macroSourceText({ ...b, g: 3, source: 'curated', food: 'Garlic' }, t)).toBe('Matched: Garlic · 3 g · Laro food table');
    expect(macroSourceText({ src: 'db', g: 27.6, source: 'usda_sr' }, t, 0.25)).toBe('Matched: food database · 6.9 g · USDA FoodData Central');
  });

  it('labels AI estimates and ignores badges without provenance', () => {
    expect(macroSourceText({ p: 1, c: 1, f: 1, cal: 10, src: 'ai' }, t)).toBe('AI estimate');
    expect(macroSourceText({ p: 1, c: 1, f: 1, cal: 10 }, t)).toBeNull();
    expect(macroSourceText(null, t)).toBeNull();
  });
});

// ---- Per 100 g ---------------------------------------------------------------------------------
import { bakeKind, formatGrams, formatPer100, nutritionBasis, weightNote, weightsForChoice } from './versionMacros';

describe('per 100 g', () => {
  const tt = (key, params = {}) => ({
    recipeMakesAbout: 'Recipe makes about {g}',
    loafWeighsAbout: 'Loaf weighs about {g} after baking',
    bakeWeighsAbout: 'Bake weighs about {g} after baking',
  }[key] || key).replace('{g}', params.g);

  const butter = {
    title: 'Dairy-Free Butter',
    servings: 20,
    ingredients: [PASTA, GARLIC],
    nutrition: { calories: 133, protein: 0, carbs: 0, fat: 15 },
    adaptations: {
      nutrition_basis_auto: '100g',
      total_grams: 400,
      nutrition_per_100g: { calories: 664, protein: 0.2, carbs: 1.8, fat: 75.5 },
      low_fodmap: { swaps: [{ from: 'garlic', to: 'garlic-infused oil' }] },
      low_fodmap_macros: { nutrition: { calories: 1 }, total_grams: 390, nutrition_per_100g: { calories: 700, protein: 0, carbs: 0, fat: 79 } },
      versions: [{ ...tofuVersion, total_grams: 850, nutrition_per_100g: { calories: 72, protein: 5.4, carbs: 7.1, fat: 2.8 } }],
    },
  };

  it('basis: user choice, else automatic, else per serving', () => {
    expect(nutritionBasis(butter)).toBe('100g');
    expect(nutritionBasis({ adaptations: { ...butter.adaptations, nutrition_basis: 'serving' } })).toBe('serving');
    expect(nutritionBasis({ adaptations: { nutrition_basis: '100g' } })).toBe('100g');
    expect(nutritionBasis(recipe)).toBe('serving');
    expect(nutritionBasis(null)).toBe('serving');
  });

  it('weights follow the shown version / Low FODMAP list', () => {
    expect(weightsForChoice(butter, '', false)).toEqual({ totalGrams: 400, rawGrams: null, per100g: butter.adaptations.nutrition_per_100g });
    expect(weightsForChoice(butter, '', true).totalGrams).toBe(390);
    expect(weightsForChoice(butter, 'Lemon Pepper Tofu', false).totalGrams).toBe(850);
    expect(weightsForChoice(butter, 'Lemon Pepper Tofu', true)).toBeNull(); // its LF list has no weights yet
    expect(weightsForChoice(recipe, '', false)).toBeNull();
    expect(weightsForChoice(butter, 'Lemon Pepper Tofu', true, { total_grams: 800, nutrition_per_100g: { calories: 80 } }).totalGrams).toBe(800);
  });

  it('weight line: recipe size, or the baked weight for breads and cakes', () => {
    expect(weightNote({ totalGrams: 523 }, butter, tt)).toBe('Recipe makes about 520 g');
    const shokupan = { adaptations: { bake_yield: 0.88 } };
    expect(weightNote({ totalGrams: 880, rawGrams: 1000 }, shokupan, tt)).toBe('Loaf weighs about 880 g after baking');
    expect(weightNote({ totalGrams: 1251, rawGrams: 1390 }, { adaptations: { bake_yield: 0.9 } }, tt)).toBe('Bake weighs about 1,250 g after baking');
    expect(bakeKind(shokupan)).toBe('bread');
    expect(bakeKind(butter)).toBeNull();
    expect(weightNote(null, butter, tt)).toBeNull();
  });

  it('formats label-style numbers', () => {
    expect(formatPer100(75.46)).toBe('75');
    expect(formatPer100(1.84)).toBe('1.8');
    expect(formatPer100(0)).toBe('0');
    expect(formatGrams(57)).toBe('57 g');
    expect(formatGrams(0)).toBeNull();
  });
});
