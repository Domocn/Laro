/**
 * Per-serving macro limits for the Recipes list. null/undefined = no limit.
 * Mirrors Android `util/MacroFilter.kt`.
 */
export const MACRO_FIELDS = ['calories', 'protein', 'carbs', 'fat'];

export const MACRO_PRESETS = [
  { id: 'under-500', emoji: '🔥', labelKey: 'macroUnder500', filter: { maxCalories: 500 } },
  { id: 'low-carb', emoji: '🥬', labelKey: 'macroLowCarb', filter: { maxCarbs: 20 } },
];

const cap = (f) => f.charAt(0).toUpperCase() + f.slice(1);
const num = (v) => (v === null || v === undefined || v === '' || Number.isNaN(Number(v)) ? null : Number(v));

export function isMacroFilterActive(filter = {}) {
  return MACRO_FIELDS.some((f) => num(filter[`min${cap(f)}`]) !== null || num(filter[`max${cap(f)}`]) !== null);
}

/** Both must pass: keep the tighter limit on each side. */
export function andMacroFilters(a = {}, b = {}) {
  const out = {};
  MACRO_FIELDS.forEach((f) => {
    const mins = [a[`min${cap(f)}`], b[`min${cap(f)}`]].map(num).filter((v) => v !== null);
    const maxs = [a[`max${cap(f)}`], b[`max${cap(f)}`]].map(num).filter((v) => v !== null);
    if (mins.length) out[`min${cap(f)}`] = Math.max(...mins);
    if (maxs.length) out[`max${cap(f)}`] = Math.min(...maxs);
  });
  return out;
}

/** "High protein" is personal, so the user picks the grams; these are the quick picks. */
export const PROTEIN_QUICK_PICKS = [20, 25, 30, 35, 40];
export const DEFAULT_PROTEIN_MIN = 30;

export function combineMacroFilters(presetIds = [], custom = {}, proteinMin = null) {
  const base = andMacroFilters(custom, proteinMin ? { minProtein: proteinMin } : {});
  return MACRO_PRESETS.filter((p) => presetIds.includes(p.id)).reduce((acc, p) => andMacroFilters(acc, p.filter), base);
}

export const hasNutrition = (recipe) => Number(recipe?.nutrition?.calories) > 0;

/** Returns { shown, hiddenNoNutrition }. Recipes without nutrition are skipped (and counted) while active. */
export function applyMacroFilter(recipes = [], filter = {}) {
  if (!isMacroFilterActive(filter)) return { shown: recipes, hiddenNoNutrition: 0 };
  let hidden = 0;
  const shown = recipes.filter((r) => {
    if (!hasNutrition(r)) {
      hidden += 1;
      return false;
    }
    return MACRO_FIELDS.every((f) => {
      const v = Number(r.nutrition[f]) || 0;
      const min = num(filter[`min${cap(f)}`]);
      const max = num(filter[`max${cap(f)}`]);
      return (min === null || v >= min) && (max === null || v <= max);
    });
  });
  return { shown, hiddenNoNutrition: hidden };
}
