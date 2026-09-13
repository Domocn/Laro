/**
 * Meal-plan day nutrition rollup, protein-swap helpers, and repeat-week logic.
 * Pure functions — unit-tested; used by MealPlanner (and portable to Android).
 */

const WEEKDAY_CODES = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];

/** date-fns / JS getDay(): 0=Sun … 6=Sat → mon–sun codes used in preferences */
export function weekdayCodeFromDate(date) {
  if (!date) return null;
  const d = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return null;
  return WEEKDAY_CODES[d.getDay()] || null;
}

export function recipeProteinGrams(recipe) {
  if (!recipe) return null;
  const n = recipe.nutrition;
  const raw =
    n?.protein ??
    recipe.nutrition_protein ??
    recipe.protein ??
    null;
  if (raw == null || raw === '') return null;
  const v = Number(raw);
  return Number.isFinite(v) ? v : null;
}

export function recipeCalories(recipe) {
  if (!recipe) return null;
  const n = recipe.nutrition;
  const raw =
    n?.calories ??
    recipe.nutrition_calories ??
    recipe.calories ??
    null;
  if (raw == null || raw === '') return null;
  const v = Number(raw);
  return Number.isFinite(v) ? v : null;
}

/**
 * Sum nutrition for meals on a day by joining meal plans → recipes.
 * Notes/leftovers without nutrition contribute 0 (counted in mealsWithNutrition only when known).
 */
export function rollupDayNutrition(meals = [], recipes = []) {
  const byId = new Map((recipes || []).map((r) => [r.id, r]));
  let protein = 0;
  let calories = 0;
  let mealsWithNutrition = 0;
  let recipeMeals = 0;

  for (const meal of meals || []) {
    const kind = meal.entry_type || (meal.recipe_id ? 'recipe' : 'note');
    if (kind !== 'recipe' || !meal.recipe_id) continue;
    recipeMeals += 1;
    const recipe = byId.get(meal.recipe_id);
    const p = recipeProteinGrams(recipe);
    const c = recipeCalories(recipe);
    if (p != null || c != null) {
      mealsWithNutrition += 1;
      if (p != null) protein += p;
      if (c != null) calories += c;
    }
  }

  return {
    protein: Math.round(protein),
    calories: Math.round(calories),
    mealsWithNutrition,
    recipeMeals,
    hasAnyNutrition: mealsWithNutrition > 0,
  };
}

/**
 * Compare totals to targets. Amber when under protein (or over cals if target set);
 * green when protein meets/exceeds target (or no protein target and we have data).
 */
export function nutritionStatus(totals, { proteinTarget, calorieTarget } = {}) {
  const pTarget =
    proteinTarget == null || proteinTarget === '' ? null : Number(proteinTarget);
  const cTarget =
    calorieTarget == null || calorieTarget === '' ? null : Number(calorieTarget);

  const hasP = Number.isFinite(pTarget) && pTarget > 0;
  const hasC = Number.isFinite(cTarget) && cTarget > 0;

  if (!totals?.hasAnyNutrition) {
    return { protein: 'unknown', calories: 'unknown', overall: 'unknown' };
  }

  let protein = 'ok';
  if (hasP) {
    protein = totals.protein + 0.5 >= pTarget ? 'met' : 'under';
  }

  let calories = 'ok';
  if (hasC) {
    if (totals.calories > cTarget * 1.05) calories = 'over';
    else if (totals.calories >= cTarget * 0.9) calories = 'met';
    else calories = 'under';
  }

  let overall = 'ok';
  if (protein === 'under' || calories === 'over') overall = 'amber';
  else if (protein === 'met' || (protein === 'ok' && calories === 'met')) overall = 'green';

  return { protein, calories, overall, proteinTarget: hasP ? pTarget : null, calorieTarget: hasC ? cTarget : null };
}

/**
 * Rank library recipes that would raise day protein if swapped into a meal slot.
 * Prefers dinner, then lunch; excludes recipes already on the day.
 */
export function suggestProteinSwaps({
  meals = [],
  recipes = [],
  proteinTarget,
  excludeRecipeIds = [],
  limit = 5,
} = {}) {
  const totals = rollupDayNutrition(meals, recipes);
  const pTarget =
    proteinTarget == null || proteinTarget === '' ? null : Number(proteinTarget);
  const deficit =
    Number.isFinite(pTarget) && pTarget > 0
      ? Math.max(0, pTarget - totals.protein)
      : 0;

  const onDay = new Set(
    (meals || [])
      .filter((m) => m.recipe_id)
      .map((m) => m.recipe_id)
      .concat(excludeRecipeIds || [])
  );

  const mealCandidates = (meals || []).filter(
    (m) => (m.entry_type || 'recipe') === 'recipe' && m.recipe_id
  );
  // Prefer swapping dinner, then lunch, then others
  const order = { Dinner: 0, Lunch: 1, Breakfast: 2, Snack: 3 };
  mealCandidates.sort(
    (a, b) => (order[a.meal_type] ?? 9) - (order[b.meal_type] ?? 9)
  );

  const scored = [];
  for (const recipe of recipes || []) {
    if (!recipe?.id || onDay.has(recipe.id)) continue;
    const protein = recipeProteinGrams(recipe);
    if (protein == null || protein <= 0) continue;

    for (const meal of mealCandidates) {
      const current = recipes.find((r) => r.id === meal.recipe_id);
      const currentP = recipeProteinGrams(current) || 0;
      const gain = protein - currentP;
      if (gain <= 0) continue;
      scored.push({
        mealId: meal.id,
        mealType: meal.meal_type,
        currentRecipeId: meal.recipe_id,
        currentTitle: meal.recipe_title,
        recipeId: recipe.id,
        title: recipe.title,
        protein,
        currentProtein: currentP,
        gain: Math.round(gain),
        closesDeficit: deficit > 0 ? gain >= deficit : false,
      });
    }
  }

  scored.sort((a, b) => {
    if (a.closesDeficit !== b.closesDeficit) return a.closesDeficit ? -1 : 1;
    if (b.gain !== a.gain) return b.gain - a.gain;
    return (order[a.mealType] ?? 9) - (order[b.mealType] ?? 9);
  });

  // Unique by meal+recipe (keep best gain)
  const seen = new Set();
  const unique = [];
  for (const s of scored) {
    const key = `${s.mealId}:${s.recipeId}`;
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(s);
    if (unique.length >= limit) break;
  }

  return {
    totals,
    deficit: Math.round(deficit),
    underTarget: deficit > 0.5,
    suggestions: unique,
  };
}

/**
 * Build create payloads to copy meals from source week onto target week (+7 days).
 * Skips ids; shifts date by dayOffset (default 7).
 */
export function buildRepeatWeekPayloads(meals = [], { dayOffset = 7 } = {}) {
  const out = [];
  for (const meal of meals || []) {
    if (!meal?.date) continue;
    const base = typeof meal.date === 'string' ? meal.date.slice(0, 10) : meal.date;
    const d = new Date(`${base}T12:00:00`);
    if (Number.isNaN(d.getTime())) continue;
    d.setDate(d.getDate() + dayOffset);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const payload = {
      date: `${yyyy}-${mm}-${dd}`,
      meal_type: meal.meal_type || 'Dinner',
      entry_type: meal.entry_type || (meal.recipe_id ? 'recipe' : 'note'),
      notes: meal.notes || '',
      adult_boost: meal.adult_boost || meal.adultBoost || '',
    };
    if (payload.entry_type === 'recipe') {
      if (!meal.recipe_id) continue;
      payload.recipe_id = meal.recipe_id;
    } else {
      payload.recipe_title = meal.recipe_title || 'Note';
    }
    out.push(payload);
  }
  return out;
}

/** Day-mode cues for the week grid (WFH / gym / kid / busy). */
export function dayModeCues(date, preferences = {}, dayBusyness = null) {
  const code = weekdayCodeFromDate(date);
  const wfh =
    !!preferences.worksFromHome &&
    Array.isArray(preferences.wfhDays) &&
    code &&
    preferences.wfhDays.includes(code);
  const gym =
    !!preferences.hasGymRoutine &&
    Array.isArray(preferences.gymDays) &&
    code &&
    preferences.gymDays.includes(code);
  const kidNight =
    preferences.hasChildren && preferences.kidFriendlyMeals !== false;
  const familyOneMeal =
    preferences.familyOneMeal === true ||
    (preferences.familyOneMeal !== false && !!preferences.hasChildren);
  const busyLevel = dayBusyness?.level || null;

  return {
    weekday: code,
    wfh,
    gym,
    kidNight: !!kidNight,
    familyOneMeal: !!familyOneMeal,
    busyLevel,
  };
}

export function resolveProteinTarget(preferences = {}) {
  const raw = preferences.dailyProteinTarget;
  if (raw != null && raw !== '' && Number(raw) > 0) return Number(raw);
  const dietary = preferences.dietaryRestrictions || [];
  if (
    dietary.some((d) =>
      String(d).toLowerCase().replace(/_/g, '-').includes('high-protein')
    )
  ) {
    return 140;
  }
  return null;
}

export function resolveCalorieTarget(preferences = {}) {
  const raw = preferences.dailyCalorieTarget;
  if (raw != null && raw !== '' && Number(raw) > 0) return Number(raw);
  return null;
}

const HORIZON_KEY = 'laro_meal_plan_horizon';

export function savePlanHorizon({ anchorStart, weeks }) {
  try {
    const payload = {
      anchorStart: String(anchorStart).slice(0, 10),
      weeks: Math.max(1, Math.min(8, Number(weeks) || 1)),
    };
    sessionStorage.setItem(HORIZON_KEY, JSON.stringify(payload));
    return payload;
  } catch {
    return null;
  }
}

export function loadPlanHorizon() {
  try {
    const raw = sessionStorage.getItem(HORIZON_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.anchorStart || !parsed?.weeks) return null;
    return {
      anchorStart: String(parsed.anchorStart).slice(0, 10),
      weeks: Math.max(1, Math.min(8, Number(parsed.weeks) || 1)),
    };
  } catch {
    return null;
  }
}

export function clearPlanHorizon() {
  try {
    sessionStorage.removeItem(HORIZON_KEY);
  } catch {
    /* ignore */
  }
}
