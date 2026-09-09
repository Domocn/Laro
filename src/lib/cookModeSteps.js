/**
 * Helpers for Cook Mode: normalize steps, enrich with ingredient amounts, timers.
 *
 * Amount injection uses fuzzy name matching so list names like "White potatoes"
 * still match step text that says "the potatoes".
 */

import { formatIngredientLine } from './unitConversions';

/** @param {unknown} instructions */
export function normalizeCookSteps(instructions) {
  if (!instructions) return [];
  if (typeof instructions === 'string') {
    return instructions
      .split(/\n+/)
      .map((s) => s.replace(/^\s*\d+[.)]\s*/, '').trim())
      .filter(Boolean);
  }
  if (!Array.isArray(instructions)) return [];
  return instructions
    .map((step) => {
      if (typeof step === 'string') return step.trim();
      if (step && typeof step === 'object') {
        return String(step.text || step.instruction || step.step || '').trim();
      }
      return '';
    })
    .filter(Boolean);
}

/**
 * Quantity-only label for an ingredient, e.g. "500 g" (no name).
 * @param {{ amount?: string|number, unit?: string, name?: string }|string} ing
 * @param {string} [measurementUnit]
 */
export function formatIngredientQuantity(ing, measurementUnit = 'metric') {
  if (!ing || typeof ing === 'string') return '';
  const line = formatIngredientLine(
    { ...ing, name: '' },
    measurementUnit
  ).trim();
  return line;
}

function escapeRegex(value) {
  return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

const NOISE_WORDS = new Set([
  'fresh',
  'dried',
  'ground',
  'chopped',
  'minced',
  'sliced',
  'diced',
  'large',
  'small',
  'medium',
  'extra',
  'virgin',
  'organic',
  'raw',
  'cooked',
  'boneless',
  'skinless',
  'white',
  'black',
  'red',
  'green',
  'yellow',
  'brown',
  'whole',
  'plain',
  'unsalted',
  'salted',
  'light',
  'dark',
  'sweet',
  'hot',
  'cold',
  'warm',
  'olive',
  'vegetable',
  'canola',
  'coconut',
  'free',
  'range',
  'low',
  'fat',
  'lean',
  'thick',
  'thin',
  'fine',
  'coarse',
  'baby',
  'ripe',
  'frozen',
  'canned',
  'jarred',
  'packed',
  'of',
  'and',
  'or',
  'the',
  'a',
  'an',
  'to',
  'for',
  'with',
]);

function singularize(token) {
  const w = String(token || '').toLowerCase();
  if (w.endsWith('ies') && w.length > 4) return `${w.slice(0, -3)}y`;
  if (w.endsWith('oes') && w.length > 4) return w.slice(0, -2);
  if (w.endsWith('ves') && w.length > 4) {
    const stem = w.slice(0, -3);
    if (stem.endsWith('l') || stem.endsWith('r') || stem.endsWith('a')) return `${stem}f`;
    return `${stem}fe`;
  }
  if (w.endsWith('ses') || w.endsWith('xes') || w.endsWith('zes') || w.endsWith('ches') || w.endsWith('shes')) {
    return w.slice(0, -2);
  }
  if (w.endsWith('s') && !w.endsWith('ss') && w.length > 3) return w.slice(0, -1);
  return w;
}

function pluralize(token) {
  const w = String(token || '').toLowerCase();
  // Already plural / ends with s — leave alone
  if (w.endsWith('s')) return w;
  if (w.endsWith('y') && w.length > 2 && !/[aeiou]y$/.test(w)) return `${w.slice(0, -1)}ies`;
  if (w.endsWith('o') && !w.endsWith('oo')) return `${w}es`;
  if (w.endsWith('x') || w.endsWith('z') || w.endsWith('ch') || w.endsWith('sh')) {
    return `${w}es`;
  }
  if (w.endsWith('f')) return `${w.slice(0, -1)}ves`;
  if (w.endsWith('fe')) return `${w.slice(0, -2)}ves`;
  return `${w}s`;
}

function significantTokens(name) {
  return String(name || '')
    .toLowerCase()
    .replace(/[()]/g, ' ')
    .split(/[\s,/]+/)
    .map((t) => t.trim())
    .filter((t) => t && t.length > 1 && !NOISE_WORDS.has(t));
}

/**
 * Candidate phrases to look for in step text, longest/most specific first.
 * @param {string} name
 * @param {string} [unit]
 * @returns {string[]}
 */
export function nameVariants(name, unit = '') {
  const raw = String(name || '').trim().toLowerCase();
  if (!raw) return [];

  const variants = new Set();
  variants.add(raw);

  if (raw.includes(',')) {
    raw.split(',').forEach((part) => {
      const cleaned = part.trim();
      if (cleaned && cleaned !== raw) {
        nameVariants(cleaned, unit).forEach((v) => variants.add(v));
      }
    });
  }

  const tokens = significantTokens(raw);
  if (tokens.length) {
    variants.add(tokens.join(' '));
    const last = tokens[tokens.length - 1];
    const first = tokens[0];
    const lastSing = singularize(last);
    const lastPlur = pluralize(lastSing);
    variants.add(last);
    variants.add(first);
    variants.add(lastSing);
    variants.add(lastPlur);
    variants.add(singularize(first));
    variants.add(pluralize(singularize(first)));
    // "fresh sage" + unit leaves should also match step text "sage leaves"
    const unitLower = String(unit || '').toLowerCase();
    if (/leaves?/.test(unitLower) || /leaves?/.test(raw)) {
      variants.add(`${last} leaves`);
      variants.add(`${lastSing} leaves`);
      variants.add(`${lastPlur} leaves`);
    }
    if (tokens.length >= 2) {
      variants.add(tokens.slice(-2).join(' '));
    }
  }

  return [...variants]
    .map((v) => v.trim())
    .filter((v) => v.length >= 3)
    .sort((a, b) => b.length - a.length);
}

/**
 * Insert ingredient amounts into a step when the ingredient name appears
 * without a nearby quantity. Example: "chop the potatoes" + 500g potatoes
 * → "chop the 500 g potatoes".
 *
 * Also matches fuzzy variants: "White potatoes" → "potatoes", "Chicken breast" → "chicken".
 *
 * @param {string} step
 * @param {Array<{name?: string, amount?: string|number, unit?: string}>} ingredients
 * @param {string} [measurementUnit]
 */
export function enrichStepWithAmounts(step, ingredients, measurementUnit = 'metric') {
  if (!step || typeof step !== 'string' || !Array.isArray(ingredients) || !ingredients.length) {
    return step || '';
  }

  const usable = ingredients
    .filter((ing) => ing && typeof ing === 'object' && ing.name && (ing.amount || ing.unit))
    .map((ing) => ({
      name: String(ing.name).trim(),
      qty: formatIngredientQuantity(ing, measurementUnit),
      variants: nameVariants(ing.name, ing.unit),
    }))
    .filter((ing) => ing.name && ing.qty && ing.variants.length);

  if (!usable.length) return step;

  /** @type {{ variant: string, qty: string, fullName: string }[]} */
  const needles = [];
  for (const ing of usable) {
    for (const variant of ing.variants) {
      needles.push({ variant, qty: ing.qty, fullName: ing.name });
    }
  }
  needles.sort((a, b) => b.variant.length - a.variant.length);

  let result = step;
  const injectedNames = new Set();

  for (const { variant, qty, fullName } of needles) {
    if (injectedNames.has(fullName)) continue;

    const escapedVariant = escapeRegex(variant);
    const escapedQty = escapeRegex(qty);

    // Already has "500 g potatoes" (or qty + this variant)
    if (new RegExp(`${escapedQty}\\s+${escapedVariant}\\b`, 'i').test(result)) {
      injectedNames.add(fullName);
      continue;
    }

    const re = new RegExp(`\\b(${escapedVariant})\\b`, 'i');
    const match = re.exec(result);
    if (!match) continue;

    const idx = match.index;
    const before = result.slice(Math.max(0, idx - 28), idx);
    // If there's already a number + unit right before the name, leave it
    if (/\d[\d./]*\s*(?:g|kg|ml|l|oz|lb|tsp|tbsp|cups?|cloves?|leaves?)?\s*$/i.test(before)) {
      injectedNames.add(fullName);
      continue;
    }

    // Avoid "8 leaves sage leaves" when qty unit already ends the matched phrase
    let insertQty = qty;
    const qtyParts = qty.trim().split(/\s+/);
    const matchedParts = String(match[1]).trim().split(/\s+/);
    if (
      qtyParts.length >= 2 &&
      matchedParts.length >= 2 &&
      qtyParts[qtyParts.length - 1].toLowerCase() === matchedParts[matchedParts.length - 1].toLowerCase()
    ) {
      insertQty = qtyParts.slice(0, -1).join(' ');
    }

    result = `${result.slice(0, idx)}${insertQty} ${match[1]}${result.slice(idx + match[1].length)}`;
    injectedNames.add(fullName);
  }

  return result.replace(/\s+/g, ' ').trim();
}

/**
 * @param {unknown} instructions
 * @param {Array} [ingredients]
 * @param {string} [measurementUnit]
 */
export function normalizeCookStepsWithAmounts(instructions, ingredients, measurementUnit = 'metric') {
  return normalizeCookSteps(instructions).map((step) =>
    enrichStepWithAmounts(step, ingredients, measurementUnit)
  );
}

/**
 * Ingredients mentioned in a step (for cook-mode context chips).
 * @param {string} step
 * @param {Array<{name?: string, amount?: string|number, unit?: string}|string>} ingredients
 * @param {string} [measurementUnit]
 * @returns {Array<{ name: string, qty: string, label: string }>}
 */
export function ingredientsForStep(step, ingredients, measurementUnit = 'metric') {
  if (!step || typeof step !== 'string' || !Array.isArray(ingredients) || !ingredients.length) {
    return [];
  }

  const found = [];
  const seen = new Set();

  for (const ing of ingredients) {
    if (!ing) continue;
    const name = typeof ing === 'string' ? ing.trim() : String(ing.name || '').trim();
    if (!name || seen.has(name.toLowerCase())) continue;

    const unit = typeof ing === 'object' ? ing.unit : '';
    const variants = nameVariants(name, unit);
    const hit = variants.some((variant) => {
      if (!variant || variant.length < 3) return false;
      return new RegExp(`\\b${escapeRegex(variant)}\\b`, 'i').test(step);
    });
    if (!hit) continue;

    seen.add(name.toLowerCase());
    const qty =
      typeof ing === 'object' ? formatIngredientQuantity(ing, measurementUnit) : '';
    const label = [qty, name].filter(Boolean).join(' ').trim() || name;
    found.push({ name, qty, label });
  }

  return found;
}

/**
 * Parse a duration in seconds from a step string.
 * Prefers the first sensible minute/hour mention.
 * @param {string} step
 * @returns {number|null} seconds
 */
export function parseTimeFromStep(step) {
  if (!step || typeof step !== 'string') return null;

  // Ranges: "5-7 minutes" / "5 to 7 min" → use the lower bound
  const range = step.match(
    /(\d+)\s*(?:-|–|to)\s*(\d+)\s*(?:minutes?|mins?|m)\b/i
  );
  if (range) {
    return parseInt(range[1], 10) * 60;
  }

  const hour = step.match(/(\d+)\s*(?:hours?|hrs?|h)\b/i);
  if (hour) {
    return parseInt(hour[1], 10) * 60 * 60;
  }

  const min = step.match(/(\d+)\s*(?:minutes?|mins?|m)\b/i);
  if (min) {
    return parseInt(min[1], 10) * 60;
  }

  // "90 seconds" / "30 sec"
  const sec = step.match(/(\d+)\s*(?:seconds?|secs?|s)\b/i);
  if (sec) {
    const n = parseInt(sec[1], 10);
    if (n >= 15) return n; // ignore tiny numbers that are likely not timers
  }

  return null;
}

export function formatCookTimer(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  const mins = Math.floor(s / 60);
  const secs = s % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
