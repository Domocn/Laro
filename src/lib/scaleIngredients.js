/**
 * Scale structured recipe ingredients when servings change.
 * Mirrors backend /recipes/{id}/scaled but runs synchronously in the UI.
 */

const UNICODE_FRACTIONS = {
  '½': 0.5,
  '⅓': 1 / 3,
  '⅔': 2 / 3,
  '¼': 0.25,
  '¾': 0.75,
  '⅕': 0.2,
  '⅖': 0.4,
  '⅗': 0.6,
  '⅘': 0.8,
  '⅙': 1 / 6,
  '⅚': 5 / 6,
  '⅛': 0.125,
  '⅜': 0.375,
  '⅝': 0.625,
  '⅞': 0.875,
};

/** @returns {number | null} */
export function parseAmountToNumber(amount) {
  if (amount == null) return null;
  const raw = String(amount).trim();
  if (!raw) return null;

  if (UNICODE_FRACTIONS[raw] != null) return UNICODE_FRACTIONS[raw];

  let text = raw.replace(/,/g, '.');
  for (const [char, val] of Object.entries(UNICODE_FRACTIONS)) {
    if (text.includes(char)) {
      text = text.replace(char, ` ${val} `);
    }
  }
  text = text.replace(/\s+/g, ' ').trim();

  // "1 1/2" or "2 3/4"
  const mixed = text.match(/^(\d+)\s+(\d+)\s*\/\s*(\d+)$/);
  if (mixed) {
    return Number(mixed[1]) + Number(mixed[2]) / Number(mixed[3]);
  }

  const frac = text.match(/^(\d+)\s*\/\s*(\d+)$/);
  if (frac) {
    return Number(frac[1]) / Number(frac[2]);
  }

  const num = Number(text);
  return Number.isFinite(num) ? num : null;
}

/** @param {number} value */
export function formatScaledAmount(value) {
  if (!Number.isFinite(value)) return '';
  const rounded = Math.round(value * 1000) / 1000;
  if (Math.abs(rounded - Math.round(rounded)) < 1e-9) {
    return String(Math.round(rounded));
  }
  return String(rounded)
    .replace(/(\.\d*?[1-9])0+$/, '$1')
    .replace(/\.0+$/, '');
}

/**
 * @param {Array<string|object>} ingredients
 * @param {number} originalServings
 * @param {number} newServings
 */
export function scaleIngredients(ingredients, originalServings, newServings) {
  const list = ingredients || [];
  const orig = Number(originalServings) > 0 ? Number(originalServings) : 4;
  const target = Number(newServings) > 0 ? Number(newServings) : orig;
  if (target === orig) {
    return list.map((ing) => (typeof ing === 'string' ? ing : { ...ing }));
  }

  const factor = target / orig;

  return list.map((ing) => {
    if (typeof ing === 'string') return ing;
    const parsed = parseAmountToNumber(ing.amount);
    if (parsed == null) {
      return { ...ing };
    }
    return {
      ...ing,
      amount: formatScaledAmount(parsed * factor),
    };
  });
}
