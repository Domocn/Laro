/**
 * Deterministic metric ⇄ imperial conversion for recipe ingredient display.
 * Port of android UnitConverter.kt (tables first; odd units left unchanged).
 */

const VOLUME_TO_ML = {
  ml: 1,
  milliliter: 1,
  milliliters: 1,
  l: 1000,
  liter: 1000,
  liters: 1000,
  litre: 1000,
  litres: 1000,
  tsp: 4.929,
  teaspoon: 4.929,
  teaspoons: 4.929,
  tbsp: 14.787,
  tablespoon: 14.787,
  tablespoons: 14.787,
  'fl oz': 29.574,
  cup: 236.588,
  cups: 236.588,
  pt: 473.176,
  pint: 473.176,
  pints: 473.176,
  qt: 946.353,
  quart: 946.353,
  quarts: 946.353,
  gal: 3785.41,
  gallon: 3785.41,
  gallons: 3785.41,
};

const WEIGHT_TO_G = {
  g: 1,
  gram: 1,
  grams: 1,
  kg: 1000,
  kilogram: 1000,
  kilograms: 1000,
  oz: 28.3495,
  ounce: 28.3495,
  ounces: 28.3495,
  lb: 453.592,
  pound: 453.592,
  pounds: 453.592,
  lbs: 453.592,
};

const METRIC_VOLUME = new Set(['ml', 'milliliter', 'milliliters', 'l', 'liter', 'liters', 'litre', 'litres']);
const METRIC_WEIGHT = new Set(['g', 'gram', 'grams', 'kg', 'kilogram', 'kilograms']);
const IMPERIAL_VOLUME = new Set([
  'tsp', 'teaspoon', 'teaspoons', 'tbsp', 'tablespoon', 'tablespoons',
  'fl oz', 'cup', 'cups', 'pt', 'pint', 'pints', 'qt', 'quart', 'quarts', 'gal', 'gallon', 'gallons',
]);
const IMPERIAL_WEIGHT = new Set(['oz', 'ounce', 'ounces', 'lb', 'pound', 'pounds', 'lbs']);
const NON_CONVERTIBLE = new Set([
  'piece', 'pieces', 'slice', 'slices', 'clove', 'cloves', 'pinch', 'pinches',
  'dash', 'dashes', 'bunch', 'bunches', 'sprig', 'sprigs', 'leaf', 'leaves',
  'can', 'cans', 'package', 'packages', 'bag', 'bags', 'box', 'boxes',
  'stick', 'sticks', 'head', 'heads', 'stalk', 'stalks', 'whole', 'large',
  'medium', 'small', 'to taste', '',
]);

function parseAmount(amount) {
  if (amount == null || amount === '') return null;
  if (typeof amount === 'number' && Number.isFinite(amount)) return amount;
  const s = String(amount).trim();
  if (!s) return null;
  // "1/2" or "1 1/2"
  const mixed = s.match(/^(\d+)\s+(\d+)\/(\d+)$/);
  if (mixed) return parseFloat(mixed[1]) + parseFloat(mixed[2]) / parseFloat(mixed[3]);
  const frac = s.match(/^(\d+)\/(\d+)$/);
  if (frac) return parseFloat(frac[1]) / parseFloat(frac[2]);
  const n = parseFloat(s);
  return Number.isFinite(n) ? n : null;
}

function niceNumber(n) {
  if (n >= 100) return Math.round(n);
  if (n >= 10) return Math.round(n * 10) / 10;
  return Math.round(n * 100) / 100;
}

function pickVolumeImperial(ml) {
  if (ml >= 236.588 * 0.75) return { amount: niceNumber(ml / 236.588), unit: 'cups' };
  if (ml >= 14.787) return { amount: niceNumber(ml / 14.787), unit: 'tbsp' };
  return { amount: niceNumber(ml / 4.929), unit: 'tsp' };
}

function pickVolumeMetric(ml) {
  if (ml >= 1000) return { amount: niceNumber(ml / 1000), unit: 'l' };
  return { amount: niceNumber(ml), unit: 'ml' };
}

function pickWeightImperial(g) {
  if (g >= 453.592 * 0.5) return { amount: niceNumber(g / 453.592), unit: 'lb' };
  return { amount: niceNumber(g / 28.3495), unit: 'oz' };
}

function pickWeightMetric(g) {
  if (g >= 1000) return { amount: niceNumber(g / 1000), unit: 'kg' };
  return { amount: niceNumber(g), unit: 'g' };
}

/**
 * @param {string|number} amount
 * @param {string} unit
 * @param {'metric'|'imperial'|'both'} targetSystem
 * @returns {{ amount: string|number, unit: string, alt?: string }}
 */
export function convertUnit(amount, unit, targetSystem = 'metric') {
  const numeric = parseAmount(amount);
  const u = (unit || '').toLowerCase().trim();
  if (numeric == null || NON_CONVERTIBLE.has(u) || targetSystem === 'both') {
    return { amount, unit: unit || '' };
  }

  const isVol = u in VOLUME_TO_ML;
  const isWt = u in WEIGHT_TO_G;
  if (!isVol && !isWt) return { amount, unit: unit || '' };

  if (targetSystem === 'metric') {
    if (METRIC_VOLUME.has(u) || METRIC_WEIGHT.has(u)) return { amount: niceNumber(numeric), unit: u };
    if (isVol) {
      const ml = numeric * VOLUME_TO_ML[u];
      const c = pickVolumeMetric(ml);
      return { amount: c.amount, unit: c.unit };
    }
    const g = numeric * WEIGHT_TO_G[u];
    const c = pickWeightMetric(g);
    return { amount: c.amount, unit: c.unit };
  }

  // imperial
  if (IMPERIAL_VOLUME.has(u) || IMPERIAL_WEIGHT.has(u)) return { amount: niceNumber(numeric), unit: u };
  if (isVol) {
    const ml = numeric * VOLUME_TO_ML[u];
    const c = pickVolumeImperial(ml);
    return { amount: c.amount, unit: c.unit };
  }
  const g = numeric * WEIGHT_TO_G[u];
  const c = pickWeightImperial(g);
  return { amount: c.amount, unit: c.unit };
}

export function formatIngredientLine(ing, measurementUnit = 'metric') {
  if (typeof ing === 'string') return ing;
  const name = ing.name || '';
  const rawAmount = ing.amount;
  const rawUnit = ing.unit || '';
  if (measurementUnit === 'both') {
    const metric = convertUnit(rawAmount, rawUnit, 'metric');
    const imperial = convertUnit(rawAmount, rawUnit, 'imperial');
    const a = `${metric.amount ?? ''} ${metric.unit || ''}`.trim();
    const b = `${imperial.amount ?? ''} ${imperial.unit || ''}`.trim();
    if (a && b && a !== b) return `${a} (${b}) ${name}`.trim();
    return `${a || b} ${name}`.trim();
  }
  const c = convertUnit(rawAmount, rawUnit, measurementUnit);
  return `${c.amount ?? ''} ${c.unit || ''} ${name}`.trim().replace(/\s+/g, ' ');
}
