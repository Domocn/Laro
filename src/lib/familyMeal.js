/**
 * Family one-meal helpers — one shared kid-suitable dish + optional adult boost.
 */

/** Preference defaults true when hasChildren (unless explicitly false). */
export function wantsFamilyOneMeal(preferences = {}) {
  if (!preferences) return false;
  if (preferences.familyOneMeal === true) return true;
  if (preferences.familyOneMeal === false) return false;
  return !!preferences.hasChildren;
}

/**
 * Resolve adult boost tip from meal plan entry.
 * Prefers adult_boost field; falls back to notes starting with "For adults:".
 */
export function parseAdultBoost(meal) {
  if (!meal) return '';
  const direct = (meal.adult_boost || meal.adultBoost || '').trim();
  if (direct) {
    return stripAdultBoostPrefix(direct);
  }
  const notes = (meal.notes || '').trim();
  if (!notes) return '';
  const match = notes.match(/^for adults\s*[:—–-]\s*(.+)$/i);
  return match ? match[1].trim() : '';
}

export function stripAdultBoostPrefix(text) {
  const raw = (text || '').trim();
  if (!raw) return '';
  return raw.replace(/^for adults\s*[:—–-]\s*/i, '').trim();
}

/** True when recipe tags include family-friendly. */
export function isFamilyFriendlyRecipe(recipe) {
  const tags = recipe?.tags || recipe?.dietary_tags || [];
  if (!Array.isArray(tags)) return false;
  return tags.some(
    (t) => String(t).toLowerCase().replace(/_/g, '-') === 'family-friendly'
  );
}
