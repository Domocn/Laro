import { applyMacroFilter, combineMacroFilters, isMacroFilterActive } from './macroFilter';

const r = (title, calories, protein, carbs, fat) => ({ id: title, title, nutrition: { calories, protein, carbs, fat } });
const salmon = r('Salmon', 400, 27, 24, 21);
const stirFry = r('Stir fry', 505, 37, 68, 9);
const salad = r('Greek salad', 500, 18, 19, 39);
const noNutrition = { id: 'x', title: 'Mystery stew', nutrition: null };
const all = [salmon, stirFry, salad, noNutrition];

describe('macroFilter', () => {
  it('shows everything when no limit is set', () => {
    expect(applyMacroFilter(all, {})).toEqual({ shown: all, hiddenNoNutrition: 0 });
    expect(isMacroFilterActive({ minProtein: '' })).toBe(false);
  });

  it('applies the presets per serving', () => {
    expect(applyMacroFilter(all, combineMacroFilters([], {}, 30)).shown).toEqual([stirFry]);
    expect(applyMacroFilter(all, combineMacroFilters([], {}, 25)).shown).toEqual([salmon, stirFry]);
    expect(applyMacroFilter(all, combineMacroFilters(['under-500'])).shown).toEqual([salmon, salad]);
    expect(applyMacroFilter(all, combineMacroFilters(['low-carb'])).shown).toEqual([salad]);
  });

  it('counts recipes without nutrition instead of showing them', () => {
    expect(applyMacroFilter(all, { maxCalories: 500 }).hiddenNoNutrition).toBe(1);
  });

  it('combines presets with custom limits using the tighter one', () => {
    const f = combineMacroFilters(['under-500'], { maxCalories: 450, minProtein: 20 });
    expect(f).toEqual({ maxCalories: 450, minProtein: 20 });
    expect(applyMacroFilter(all, f).shown).toEqual([salmon]);
  });
});
