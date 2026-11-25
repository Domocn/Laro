// Named recipe versions ("Chicken Schnitzel", "Chocolate Orange") for the recipe page / edit form.
// recipe.adaptations.versions = [{ name, ingredients: [...], instructions: [...], notes }]
// The recipe's own ingredients/instructions are the "Original" (version name '').
import { parseSectionedLines, sectionedLines } from './ingredientGroups';

export const ORIGINAL_VERSION = '';
export const MAX_VERSIONS = 10;
const STORAGE_PREFIX = 'laro_recipe_version:';

const clean = (v) => String(v ?? '').replace(/\s+/g, ' ').trim();

/** The recipe's usable versions (named, with something in them), deduped by name. */
export function getRecipeVersions(recipe) {
  const raw = recipe?.adaptations?.versions;
  if (!Array.isArray(raw)) return [];
  const seen = new Set();
  const out = [];
  for (const v of raw) {
    const name = clean(v?.name);
    const key = name.toLowerCase();
    if (!name || key === 'original' || seen.has(key)) continue;
    const ingredients = Array.isArray(v.ingredients) ? v.ingredients : [];
    const instructions = Array.isArray(v.instructions) ? v.instructions : [];
    if (!ingredients.length && !instructions.length) continue;
    seen.add(key);
    out.push({ name, ingredients, instructions, notes: String(v.notes || '').trim() });
  }
  return out.slice(0, MAX_VERSIONS);
}

/** Picker chips: Original first, then each version name (empty when there are no versions). */
export function versionChoices(recipe) {
  const names = getRecipeVersions(recipe).map((v) => v.name);
  return names.length ? [ORIGINAL_VERSION, ...names] : [];
}

/** A stored / linked version name that still exists on this recipe (canonical case), else Original. */
export function validVersion(recipe, name) {
  return findVersion(recipe, name)?.name || ORIGINAL_VERSION;
}

/** "Pesto Pasta · Pomegranate · Low FODMAP" (just the title for Original). */
export function planLabel(title, plan, lowFodmapLabel = 'Low FODMAP') {
  const parts = [title || ''];
  if (plan?.recipe_version) parts.push(String(plan.recipe_version));
  if (plan?.low_fodmap) parts.push(lowFodmapLabel);
  return parts.filter(Boolean).join(' · ');
}

/** Recipe page link that opens on the planned version (+ Low FODMAP). */
export function recipeLinkForPlan(plan) {
  const params = new URLSearchParams();
  if (plan?.recipe_version) params.set('version', String(plan.recipe_version));
  if (plan?.low_fodmap) params.set('lowFodmap', '1');
  const qs = params.toString();
  return `/recipes/${plan?.recipe_id}${qs ? `?${qs}` : ''}`;
}

/** Choice from a recipe link (?version=…&lowFodmap=1), or null when the link has none. */
export function choiceFromSearch(search) {
  const params = new URLSearchParams(search || '');
  if (!params.has('version') && !params.has('lowFodmap')) return null;
  return { version: params.get('version') || ORIGINAL_VERSION, lowFodmap: params.get('lowFodmap') === '1' };
}

/** The chosen version, or null for Original / unknown names. */
export function findVersion(recipe, name) {
  const key = clean(name).toLowerCase();
  if (!key) return null;
  return getRecipeVersions(recipe).find((v) => v.name.toLowerCase() === key) || null;
}

/** Recipe as shown for a version: its ingredients/instructions swapped in (Original is unchanged). */
export function applyRecipeVersion(recipe, name) {
  const version = findVersion(recipe, name);
  if (!recipe || !version) return recipe;
  return { ...recipe, ingredients: version.ingredients, instructions: version.instructions };
}

function parseAmount(amount) {
  const s = String(amount ?? '').trim();
  const mixed = s.match(/^(\d+)\s+(\d+)\/(\d+)$/);
  if (mixed) return parseInt(mixed[1], 10) + parseInt(mixed[2], 10) / parseInt(mixed[3], 10);
  const frac = s.match(/^(\d+(?:\.\d+)?)\s*\/\s*(\d+(?:\.\d+)?)$/);
  if (frac) return parseFloat(frac[1]) / parseFloat(frac[2]);
  if (/^\d+(?:\.\d+)?$/.test(s)) return parseFloat(s);
  return null;
}

/** Scale ingredient amounts from `fromServings` to `toServings` (same rules as GET /recipes/{id}/scaled). */
export function scaleIngredients(ingredients, fromServings, toServings) {
  const from = Number(fromServings) > 0 ? Number(fromServings) : 4;
  const to = Number(toServings);
  if (!to || to <= 0 || to === from) return ingredients || [];
  const f = to / from;
  return (ingredients || []).map((ing) => {
    if (!ing || typeof ing !== 'object') return ing;
    const n = parseAmount(ing.amount);
    if (n == null) return ing;
    const v = n * f;
    const amount = Number.isInteger(v) ? String(v) : String(Math.round(v * 100) / 100);
    return { ...ing, amount };
  });
}

/**
 * Remembered { version, lowFodmap } for a recipe, or null when nothing is stored
 * (then the caller falls back to the global Low FODMAP view preference).
 */
export function readVersionChoice(recipeId) {
  if (!recipeId) return null;
  try {
    const raw = localStorage.getItem(STORAGE_PREFIX + recipeId);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        return { version: String(parsed.version || ''), lowFodmap: !!parsed.lowFodmap };
      }
    } catch {
      /* plain version name */
    }
    return { version: raw, lowFodmap: false };
  } catch {
    return null;
  }
}

export function writeVersionChoice(recipeId, choice) {
  if (!recipeId) return;
  try {
    const version = choice?.version || '';
    const lowFodmap = !!choice?.lowFodmap;
    if (!version && !lowFodmap) localStorage.removeItem(STORAGE_PREFIX + recipeId);
    else localStorage.setItem(STORAGE_PREFIX + recipeId, JSON.stringify({ version, lowFodmap }));
  } catch {
    /* private mode — choice just isn't remembered */
  }
}

// ---- Edit form ----

/** Saved versions -> editable rows (ingredients/instructions as one-per-line text). */
export function versionsToRows(recipe) {
  return getRecipeVersions(recipe).map((v) => ({
    name: v.name,
    // Sections become a "Sauce:" line above their ingredients (parsed back by rowsToVersions).
    ingredientsText: sectionedLines(v.ingredients, (i) => [i?.amount, i?.unit, i?.name].map(clean).filter(Boolean).join(' '))
      .join('\n'),
    instructionsText: v.instructions.map((s) => String(s ?? '').trim()).filter(Boolean).join('\n'),
    notes: v.notes,
  }));
}

/** Copy the recipe's current ingredients/steps as the starting point for a new version. */
export function newVersionRow(name, ingredients, instructions) {
  return versionsToRows({
    adaptations: { versions: [{ name: name || 'New version', ingredients: ingredients || [], instructions: instructions || [] }] },
  })[0] || { name: name || '', ingredientsText: '', instructionsText: '', notes: '' };
}

const lines = (text) => String(text || '').split('\n').map((l) => l.trim()).filter(Boolean);

/**
 * Edit-form rows -> versions to save. `parseIngredient` turns one line into {amount, unit, name}
 * (the form's own parser); unnamed or empty rows are dropped, names deduped, capped at 10.
 */
export function rowsToVersions(rows, parseIngredient) {
  const parse = parseIngredient || ((line) => ({ amount: '', unit: '', name: line }));
  const seen = new Set();
  const out = [];
  for (const row of rows || []) {
    const name = clean(row?.name);
    const key = name.toLowerCase();
    if (!name || key === 'original' || seen.has(key)) continue;
    const ingredients = parseSectionedLines(lines(row.ingredientsText), parse).filter((i) => i && clean(i.name));
    const instructions = lines(row.instructionsText);
    if (!ingredients.length && !instructions.length) continue;
    seen.add(key);
    const entry = { name, ingredients, instructions };
    const notes = String(row.notes || '').trim();
    if (notes) entry.notes = notes;
    out.push(entry);
  }
  return out.slice(0, MAX_VERSIONS);
}

/** Adaptations to save with new versions (null clears). Keeps low_fodmap and anything else. */
export function withVersions(existing, versions) {
  const rest = { ...(existing && typeof existing === 'object' ? existing : {}) };
  delete rest.versions;
  if (versions && versions.length) rest.versions = versions;
  return Object.keys(rest).length ? rest : null;
}

// ---- Page notes ("Notes & tips": timing, storage, to serve, …) in adaptations.page_notes ----

export function getPageNotes(recipe) {
  const raw = recipe?.adaptations?.page_notes;
  return (Array.isArray(raw) ? raw : []).map((n) => String(n ?? '').trim()).filter(Boolean);
}

/** One-note-per-line textarea -> adaptations to save (null clears). Keeps everything else. */
export function withPageNotes(existing, text) {
  const notes = [...new Set(lines(text))].slice(0, 30);
  const rest = { ...(existing && typeof existing === 'object' ? existing : {}) };
  delete rest.page_notes;
  if (notes.length) rest.page_notes = notes;
  return Object.keys(rest).length ? rest : null;
}
