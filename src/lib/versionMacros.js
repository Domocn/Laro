// Macros for what the recipe page (and the meal plan) actually shows: a named version and/or
// the Low FODMAP swaps. Stored by the backend (services/version_macros.py):
//   adaptations.versions[i].nutrition / .ingredient_macros / .low_fodmap_macros
//   adaptations.low_fodmap_macros (Original with the swaps applied)
// One source of truth: per-serving totals = sum(per-ingredient line macros) / servings. When the
// shown list's badges are here, the totals are taken from them so the card always equals what
// the badges add up to.
import { getLowFodmap, findSwap } from './fodmap';

const clean = (v) => String(v ?? '').replace(/\s+/g, ' ').trim().toLowerCase();

function rawVersion(recipe, name) {
  const key = clean(name);
  if (!key || key === 'original') return null;
  const list = recipe?.adaptations?.versions;
  if (!Array.isArray(list)) return null;
  return list.find((v) => clean(v?.name) === key) || null;
}

function hasCoreMacros(n) {
  return !!n && typeof n === 'object' && ['calories', 'protein', 'carbs', 'fat'].some((k) => n[k] != null);
}

/** True when at least one Low FODMAP swap changes one of these ingredients. */
export function swapsApply(ingredients, swaps) {
  if (!Array.isArray(swaps) || !swaps.length) return false;
  return (ingredients || []).some((ing) => !!findSwap(typeof ing === 'string' ? ing : ing?.name, swaps));
}

/**
 * Per-serving {calories, protein, carbs, fat} from line badges (sum / servings), merged over
 * `base` so extra fields (fibre, sugar…) survive. Null when there are no badges.
 */
export function totalsFromBadges(badges, servings, base = null) {
  if (!Array.isArray(badges) || !badges.length) return null;
  const s = Math.max(1, Number(servings) || 1);
  const sum = (k) => badges.reduce((acc, b) => acc + (Number(b?.[k]) || 0), 0);
  const out = { ...(base || {}) };
  delete out.nutrition_estimated;
  delete out.nutrition_source;
  out.calories = Math.round(sum('cal') / s);
  out.protein = Math.round(sum('p') / s);
  out.carbs = Math.round(sum('c') / s);
  out.fat = Math.round(sum('f') / s);
  // US "Total carbs" (incl. fibre) only when every line knows it — never a partial sum.
  delete out.carbs_total;
  // A line with no carbs counts as 0 on either basis.
  if (badges.every((b) => (b?.c_total != null && !Number.isNaN(Number(b.c_total))) || !Number(b?.c))) {
    out.carbs_total = Math.round(sum('c_total') / s);
  }
  return out;
}

/** Per-line badges only when they line up with the shown ingredient list. */
function aligned(badges, ingredients) {
  return Array.isArray(badges) && badges.length > 0 && badges.length === (ingredients || []).length ? badges : null;
}

/**
 * Macros for a version / Low FODMAP choice.
 *
 * @param recipe the recipe (its `nutrition` is the Original's per-serving macros)
 * @param versionName '' / null for Original
 * @param lowFodmapOn whether the Low FODMAP swaps are shown
 * @param originalBadges the Original's per-ingredient macros (Pro, fetched separately)
 * @returns {{ nutrition: object|null, ingredientMacros: Array|null, pending: boolean, variant: boolean }}
 *   `pending`: a version / Low FODMAP is shown but its macros are not stored yet — `nutrition`
 *   is then the Original's and must be labelled (or replaced by POST /macros-preview).
 */
export function macrosForChoice(recipe, versionName, lowFodmapOn, originalBadges = null) {
  const original = recipe?.nutrition || null;
  const version = rawVersion(recipe, versionName);
  const ingredients = version
    ? (Array.isArray(version.ingredients) ? version.ingredients : [])
    : (recipe?.ingredients || []);
  const lf = lowFodmapOn ? getLowFodmap(recipe) : null;
  const lfApplies = !!lf && swapsApply(ingredients, lf.swaps);

  let stored = null;
  if (version && lfApplies) stored = version.low_fodmap_macros || null;
  else if (version) stored = hasCoreMacros(version.nutrition) ? { nutrition: version.nutrition, ingredient_macros: version.ingredient_macros } : null;
  else if (lfApplies) stored = recipe?.adaptations?.low_fodmap_macros || null;
  else {
    const badges = aligned(originalBadges, ingredients);
    return {
      nutrition: totalsFromBadges(badges, recipe?.servings, original) || original,
      ingredientMacros: badges,
      pending: false,
      variant: false,
    };
  }

  if (stored && hasCoreMacros(stored.nutrition)) {
    const badges = aligned(stored.ingredient_macros, ingredients);
    return {
      nutrition: totalsFromBadges(badges, recipe?.servings, stored.nutrition) || stored.nutrition,
      ingredientMacros: badges,
      pending: false,
      variant: true,
    };
  }
  return { nutrition: original, ingredientMacros: null, pending: true, variant: true };
}

/** Per-serving nutrition for a meal-plan entry (its planned version + Low FODMAP). */
export function nutritionForPlan(recipe, plan) {
  if (!recipe) return null;
  const { nutrition, pending } = macrosForChoice(recipe, plan?.recipe_version, !!plan?.low_fodmap);
  return pending ? recipe.nutrition || null : nutrition;
}

/** Badge numbers for one ingredient line, scaled (servings / macro solver). */
export function scaleBadge(badge, factor = 1) {
  const f = Number.isFinite(factor) && factor > 0 ? factor : 1;
  const r = (v) => Math.round((Number(v) || 0) * f);
  const out = { p: r(badge?.p), c: r(badge?.c), f: r(badge?.f), cal: r(badge?.cal) };
  if (badge?.c_total != null) out.c_total = r(badge.c_total);
  return out;
}

const SOURCE_KEYS = {
  cofid: 'macroSourceCofid',
  usda_sr: 'macroSourceUsda',
  usda_foundation: 'macroSourceUsda',
  curated: 'macroSourceCurated',
};

/**
 * Where one line's macros came from (backend services/line_macros.py provenance), as text:
 * "Matched: Tofu, firm, raw · 450 g · UK CoFID" or "AI estimate". Null when the badge has no
 * provenance (saved before it existed). Grams follow the same scaling as the badge numbers.
 */
export function macroSourceText(badge, t, factor = 1) {
  if (!badge || typeof t !== 'function') return null;
  if (badge.src === 'ai') return t('macroSrcAi');
  if (badge.src !== 'db') return null;
  const f = Number.isFinite(factor) && factor > 0 ? factor : 1;
  const g = Number(badge.g);
  const grams = Number.isFinite(g) && g > 0 ? (g * f >= 10 ? Math.round(g * f) : Math.round(g * f * 10) / 10) : null;
  const source = SOURCE_KEYS[badge.source] ? t(SOURCE_KEYS[badge.source]) : (badge.source || '');
  const food = badge.food || t('macroSrcFood');
  const parts = [food, grams != null ? `${grams} g` : null, source || null].filter(Boolean);
  return t('macroSrcMatched', { detail: parts.join(' · ') });
}

// ---- Per 100 g (batch / base recipes: butters, pestos, sauces, breads ...) -------------------
// The backend derives these from the line grams (services/nutrition_basis.py) and sends them in
// `adaptations`: total_grams / raw_grams / nutrition_per_100g for the Original, the same on each
// version and Low FODMAP option, plus nutrition_basis (the user's choice), nutrition_basis_auto
// and bake_yield. Meal plans and shopping stay per serving.

/** 'serving' | '100g': the user's choice for this recipe, else the automatic one. */
export function nutritionBasis(recipe) {
  const a = recipe?.adaptations || {};
  if (a.nutrition_basis === '100g' || a.nutrition_basis === 'serving') return a.nutrition_basis;
  return a.nutrition_basis_auto === '100g' ? '100g' : 'serving';
}

function weightsOf(src) {
  const per = src?.nutrition_per_100g;
  const total = Number(src?.total_grams);
  if (!per || !(total > 0)) return null;
  const raw = Number(src?.raw_grams);
  return { totalGrams: total, rawGrams: raw > 0 ? raw : null, per100g: per };
}

/**
 * {totalGrams, rawGrams, per100g} for what the page shows (version / Low FODMAP), or null while
 * an ingredient's weight is unknown. `preview` = a POST /macros-preview reply for this choice.
 */
export function weightsForChoice(recipe, versionName, lowFodmapOn, preview = null) {
  if (preview) return weightsOf(preview);
  const a = recipe?.adaptations || {};
  const version = rawVersion(recipe, versionName);
  const ingredients = version ? (version.ingredients || []) : (recipe?.ingredients || []);
  const lf = lowFodmapOn ? getLowFodmap(recipe) : null;
  const lfApplies = !!lf && swapsApply(ingredients, lf.swaps);
  if (version && lfApplies) return weightsOf(version.low_fodmap_macros);
  if (version) return weightsOf(version);
  if (lfApplies) return weightsOf(a.low_fodmap_macros);
  return weightsOf(a);
}

/** 'bread' | 'cake' | null from the backend's bake-loss factor (0.88 bread, 0.90 cakes). */
export function bakeKind(recipe) {
  const y = Number(recipe?.adaptations?.bake_yield);
  if (!(y > 0)) return null;
  return y < 0.89 ? 'bread' : 'cake';
}

/** "520 g" / "1,250 g" — rounded to 10 g (it's an estimate). */
export function formatGrams(g) {
  const n = Number(g);
  if (!Number.isFinite(n) || n <= 0) return null;
  const r = n >= 100 ? Math.round(n / 10) * 10 : Math.round(n);
  return `${r.toLocaleString('en-GB')} g`;
}

/** "Recipe makes about 520 g" / "Loaf weighs about 880 g after baking". */
export function weightNote(weights, recipe, t) {
  if (!weights || typeof t !== 'function') return null;
  const g = formatGrams(weights.totalGrams);
  if (!g) return null;
  const kind = weights.rawGrams ? bakeKind(recipe) : null;
  if (kind === 'bread') return t('loafWeighsAbout', { g });
  if (kind === 'cake') return t('bakeWeighsAbout', { g });
  return t('recipeMakesAbout', { g });
}

/** Label-style macro number per 100 g: whole numbers from 10 g up, one decimal below. */
export function formatPer100(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  return n >= 10 ? String(Math.round(n)) : String(Math.round(n * 10) / 10);
}
