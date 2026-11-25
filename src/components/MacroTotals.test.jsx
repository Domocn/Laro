import React from 'react';
import { createRoot } from 'react-dom/client';
import { act } from 'react';
import MacroTotals from './MacroTotals';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const en = {
  nutritionPerServing: 'Per serving', nutritionPer100g: 'Per 100 g', nutritionRecipeTotal: 'Recipe total',
  recipeMakesAbout: 'Recipe makes about {g}', loafWeighsAbout: 'Loaf weighs about {g} after baking',
  per100gPending: 'Still working out how much each ingredient weighs.',
};
const t = (k, p = {}) => Object.entries(p).reduce((s, [a, v]) => s.replaceAll(`{${a}}`, v), en[k] || k);

function render(props) {
  const el = document.createElement('div');
  document.body.appendChild(el);
  const root = createRoot(el);
  act(() => root.render(<MacroTotals t={t} {...props} />));
  return { el, root };
}

const nutrition = { calories: 133, protein: 0, carbs: 0, fat: 15 };
const weights = { totalGrams: 523, rawGrams: null, per100g: { calories: 664, protein: 0.2, carbs: 1.8, fat: 75.5 } };

describe('MacroTotals', () => {
  it('per serving shows the serving numbers and marks the pressed option', () => {
    const { el } = render({ nutrition, mode: 'serving', weights, servings: 20 });
    const buttons = [...el.querySelectorAll('[data-testid="nutrition-basis-toggle"] button')];
    expect(buttons.map((b) => b.textContent)).toEqual(['Per serving', 'Per 100 g', 'Recipe total']);
    expect(buttons.map((b) => b.getAttribute('aria-pressed'))).toEqual(['true', 'false', 'false']);
    expect(el.querySelector('[data-testid="serving-pills"]').textContent).toContain('15g');
    expect(el.querySelector('[data-testid="recipe-weight-note"]')).toBeNull();
  });

  it('per 100 g shows label numbers and the recipe weight, and hides the solver', () => {
    const { el } = render({ nutrition, mode: '100g', weights, children: <div data-testid="solver" /> });
    const text = el.querySelector('[data-testid="per100g-pills"]').textContent;
    expect(text).toContain('664');
    expect(text).toContain('76g');
    expect(text).toContain('0.2g');
    expect(el.querySelector('[data-testid="recipe-weight-note"]').textContent).toBe('Recipe makes about 520 g');
    expect(el.querySelector('[data-testid="solver"]')).toBeNull();
  });

  it('bread says what the loaf weighs after baking', () => {
    const { el } = render({ nutrition, mode: '100g', weights: { ...weights, totalGrams: 880, rawGrams: 1000 }, recipe: { adaptations: { bake_yield: 0.88 } } });
    expect(el.querySelector('[data-testid="recipe-weight-note"]').textContent).toBe('Loaf weighs about 880 g after baking');
  });

  it('per 100 g without weights says so instead of guessing', () => {
    const { el } = render({ nutrition, mode: '100g', weights: null });
    expect(el.querySelector('[data-testid="per100g-pending"]')).not.toBeNull();
    expect(el.querySelector('[data-testid="per100g-pills"]')).toBeNull();
  });

  it('clicking an option reports it; recipe total multiplies by servings', () => {
    const seen = [];
    const { el } = render({ nutrition, mode: 'total', servings: 20, onModeChange: (m) => seen.push(m) });
    expect(el.querySelector('[data-testid="serving-pills"]').textContent).toContain('300g');
    act(() => el.querySelector('[data-mode="100g"]').click());
    expect(seen).toEqual(['100g']);
  });
});

describe('MacroTotals nutrition style (from country)', () => {
  const n = { calories: 400, protein: 20, carbs: 40, carbs_total: 46, fat: 10 };
  const w = { totalGrams: 500, per100g: { calories: 200, protein: 4, carbs: 20, carbs_total: 23.5, fat: 5 } };
  const pill = (el, key) => el.querySelector(`[data-testid="macro-pill-${key}"]`).textContent;

  it('UK: carbs without fibre, kcal with kJ second', () => {
    const { el } = render({ nutrition: n, mode: 'serving', nutritionStyle: 'uk' });
    expect(pill(el, 'c')).toBe('C40g');
    expect(pill(el, 'cal')).toContain('400 kcal');
    expect(pill(el, 'cal')).toContain('1674 kJ');
  });
  it('AU: kJ first', () => {
    const { el } = render({ nutrition: n, mode: 'serving', nutritionStyle: 'au' });
    expect(pill(el, 'cal').indexOf('1674 kJ')).toBeLessThan(pill(el, 'cal').indexOf('400 kcal'));
  });
  it('US: Total carbs and Calories, per serving and per 100 g', () => {
    const { el } = render({ nutrition: n, mode: 'serving', nutritionStyle: 'us' });
    expect(pill(el, 'c')).toBe('Total carbs46g');
    expect(pill(el, 'cal')).toBe('🔥400 Calories');
    const per = render({ nutrition: n, mode: '100g', weights: w, nutritionStyle: 'us' }).el;
    expect(pill(per, 'c')).toBe('Total carbs24g'); // per-100 g formatting: whole grams from 10 g
  });
  it('CA: Total carbohydrate; falls back to UK carbs when the total is unknown', () => {
    const { el } = render({ nutrition: n, mode: 'serving', nutritionStyle: 'ca' });
    expect(pill(el, 'c')).toBe('Total carbohydrate46g');
    const old = render({ nutrition: { ...n, carbs_total: undefined }, mode: 'serving', nutritionStyle: 'ca' }).el;
    expect(pill(old, 'c')).toBe('C40g');
  });
});
