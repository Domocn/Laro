/**
 * Deterministic metric ⇄ imperial conversion for recipe ingredient display.
 * Port of android UnitConverter.kt (tables first; odd units left unchanged).
 *
 * Converts amounts to the user's measurement preference.
 * As written leaves the recipe alone. Metric uses kitchen figures
 * (1 tsp = 5 ml, 1 tbsp = 15 ml, 1 cup = 250 ml).
 */

const VOLUME_TO_ML = {
  ml: 1,
  milliliter: 1,
  milliliters: 1,
  millilitre: 1,
  millilitres: 1,
  cl: 10,
  centilitre: 10,
  centilitres: 10,
  centiliter: 10,
  centiliters: 10,
  l: 1000,
  liter: 1000,
  liters: 1000,
  litre: 1000,
  litres: 1000,
  tsp: 5,
  tsps: 5,
  teaspoon: 5,
  teaspoons: 5,
  tbsp: 15,
  tbs: 15,
  tbsps: 15,
  tablespoon: 15,
  tablespoons: 15,
  'fl oz': 30,
  floz: 30,
  'fl. oz': 30,
  'fl. oz.': 30,
  'fluid ounce': 30,
  'fluid ounces': 30,
  cup: 250,
  cups: 250,
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

// Approx grams per US cup for common DRY ingredients (recipe-grade densities).
// A cup of oats/flour/sugar is a weight, not 250 ml — convert volume→grams for these.
// Ordered most-specific first so "oat flour" beats "oats", etc.
const DRY_DENSITY_G_PER_CUP = [
  { keys: ['oat flour'], g: 100 },
  { keys: ['rolled oat', 'old-fashioned oat', 'old fashioned oat', 'porridge oat', 'jumbo oat', 'oatmeal', 'oats', 'oat'], g: 90 },
  { keys: ['icing sugar', 'powdered sugar', 'confectioner'], g: 120 },
  { keys: ['brown sugar', 'muscovado', 'coconut sugar'], g: 200 },
  { keys: ['caster sugar', 'granulated sugar', 'white sugar', 'sugar'], g: 200 },
  { keys: ['self-raising flour', 'self raising flour', 'plain flour', 'all-purpose flour', 'all purpose flour', 'wholemeal flour', 'whole wheat flour', 'wholewheat flour', 'bread flour', 'spelt flour', 'flour'], g: 125 },
  { keys: ['cornflour', 'cornstarch'], g: 120 },
  { keys: ['cocoa', 'cacao'], g: 85 },
  { keys: ['ground almond', 'almond flour', 'almond meal'], g: 100 },
  { keys: ['desiccated coconut', 'shredded coconut'], g: 80 },
  { keys: ['breadcrumb', 'panko'], g: 110 },
  { keys: ['chia seed', 'chia'], g: 170 },
  { keys: ['flax', 'flaxseed', 'linseed'], g: 150 },
  { keys: ['protein powder'], g: 100 },
  { keys: ['quinoa'], g: 170 },
  { keys: ['couscous'], g: 175 },
  { keys: ['lentil'], g: 190 },
  { keys: ['rice'], g: 185 },
  // Produce / whole foods — approximate grams per cup so metric users never see "cup".
  { keys: ['spinach', 'kale', 'lettuce', 'romaine', 'rocket', 'chard', 'greens', 'cabbage', 'bean sprout', 'sprouts', 'basil', 'coriander', 'cilantro', 'parsley', 'mint', 'herb'], g: 40 },
  { keys: ['strawberr', 'blueberr', 'raspberr', 'blackberr', 'cherr', 'berries'], g: 150 },
  { keys: ['mango', 'melon', 'watermelon', 'pineapple', 'peach', 'apple', 'pear'], g: 165 },
  { keys: ['cashew', 'almond', 'walnut', 'peanut', 'pecan', 'hazelnut', 'pistachio', 'nut'], g: 140 },
  { keys: ['chickpea', 'edamame', 'kidney bean', 'black bean', 'butter bean', 'beans', 'pea', 'sweetcorn', 'corn', 'dal', 'dhal'], g: 165 },
  { keys: ['cauliflower', 'broccoli', 'mushroom', 'carrot', 'courgette', 'zucchini', 'pepper', 'cucumber', 'onion', 'celery', 'tomato', 'radish', 'potato', 'aubergine', 'eggplant', 'squash', 'pumpkin'], g: 130 },
];

// Fallback for a cup of anything else non-liquid: a rough gram estimate beats
// showing "cup" to a metric cook who never uses cups.
const DEFAULT_G_PER_CUP = 140;

/**
 * The food itself, without notes: "nutritional yeast (for the basil pesto)" -> "nutritional yeast".
 * Density / liquid keywords are matched against this so a note can't change the food.
 */
function primaryName(name) {
  return String(name || '').toLowerCase().split(/[,(;]|\s[-–—]\s/)[0].trim();
}

const keyRegexCache = new Map();
/** Whole-word keyword match (plurals allowed): "nut" matches "nuts", never "nutritional". */
function hasKeyword(text, key) {
  let re = keyRegexCache.get(key);
  if (!re) {
    const esc = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    re = new RegExp(`(^|[^a-z])${esc}(s|es|ies|y)?(?![a-z])`);
    keyRegexCache.set(key, re);
  }
  return re.test(text);
}

function dryGramsPerCup(name) {
  const n = primaryName(name);
  if (!n) return null;
  for (const row of DRY_DENSITY_G_PER_CUP) {
    if (row.keys.some((k) => hasKeyword(n, k))) return row.g;
  }
  return null;
}

// Ingredients that are genuinely liquid, so a cup really is a volume (→ ml).
const LIQUID_KEYWORDS = [
  'water', 'milk', 'juice', 'stock', 'broth', 'oil', 'vinegar', 'aquafaba',
  'passata', 'sauce', 'syrup', 'maple', 'cream', 'wine', 'yoghurt', 'yogurt',
  'coffee', 'tea', 'brine', 'kombucha', 'kefir', 'coconut milk', 'espresso',
];
function isLiquidIngredient(name) {
  const n = primaryName(name);
  return LIQUID_KEYWORDS.some((k) => hasKeyword(n, k));
}

const METRIC_VOLUME = new Set([
  'ml', 'milliliter', 'milliliters', 'millilitre', 'millilitres',
  'cl', 'centilitre', 'centilitres', 'centiliter', 'centiliters',
  'l', 'liter', 'liters', 'litre', 'litres',
]);
const METRIC_WEIGHT = new Set(['g', 'gram', 'grams', 'kg', 'kilogram', 'kilograms']);
const IMPERIAL_VOLUME = new Set([
  'tsp', 'tsps', 'teaspoon', 'teaspoons', 'tbsp', 'tbs', 'tbsps', 'tablespoon', 'tablespoons',
  'fl oz', 'floz', 'fl. oz', 'fl. oz.', 'fluid ounce', 'fluid ounces',
  'cup', 'cups', 'pt', 'pint', 'pints', 'qt', 'quart', 'quarts', 'gal', 'gallon', 'gallons',
]);
const IMPERIAL_WEIGHT = new Set(['oz', 'ounce', 'ounces', 'lb', 'pound', 'pounds', 'lbs']);
const AS_WRITTEN = new Set(['as_written', 'original', 'as-written']);

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
  if (ml >= 187.5) return { amount: niceNumber(ml / 250), unit: 'cups' };
  if (ml >= 75) return { amount: niceNumber(ml / 30), unit: 'fl oz' };
  if (ml >= 12) return { amount: niceNumber(ml / 15), unit: 'tbsp' };
  return { amount: niceNumber(ml / 5), unit: 'tsp' };
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
 * @param {'metric'|'imperial'|'both'|'as_written'} targetSystem
 * @returns {{ amount: string|number, unit: string, alt?: string }}
 */
export function convertUnit(amount, unit, targetSystem = 'metric', ingredientName = '') {
  const numeric = parseAmount(amount);
  const u = (unit || '').toLowerCase().trim();
  const system = String(targetSystem || 'metric').toLowerCase();
  if (numeric == null || NON_CONVERTIBLE.has(u) || AS_WRITTEN.has(system) || system === 'both') {
    return { amount, unit: unit || '' };
  }

  const isVol = u in VOLUME_TO_ML;
  const isWt = u in WEIGHT_TO_G;
  if (!isVol && !isWt) return { amount, unit: unit || '' };

  if (system === 'metric') {
    if (METRIC_VOLUME.has(u) || METRIC_WEIGHT.has(u)) return { amount: niceNumber(numeric), unit: u };
    // Dry goods measured by volume (cup/tbsp/tsp) are a weight — convert to grams, not ml.
    if (isVol) {
      const dpc = dryGramsPerCup(ingredientName);
      if (dpc != null) {
        const cups = (numeric * VOLUME_TO_ML[u]) / 250;
        const c = pickWeightMetric(dpc * cups);
        return { amount: c.amount, unit: c.unit };
      }
      // A cup of a non-liquid (veg, fruit, beans, or anything not recognised)
      // is a weight, not ml — estimate grams so metric users never see "cup".
      if ((u === 'cup' || u === 'cups') && !isLiquidIngredient(ingredientName)) {
        const cups = (numeric * VOLUME_TO_ML[u]) / 250;
        const c = pickWeightMetric(DEFAULT_G_PER_CUP * cups);
        return { amount: c.amount, unit: c.unit };
      }
    }
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
    const metric = convertUnit(rawAmount, rawUnit, 'metric', name);
    const imperial = convertUnit(rawAmount, rawUnit, 'imperial', name);
    const a = `${metric.amount ?? ''} ${metric.unit || ''}`.trim();
    const b = `${imperial.amount ?? ''} ${imperial.unit || ''}`.trim();
    if (a && b && a !== b) return `${a} (${b}) ${name}`.trim();
    return `${a || b} ${name}`.trim();
  }
  const c = convertUnit(rawAmount, rawUnit, measurementUnit, name);
  return `${c.amount ?? ''} ${c.unit || ''} ${name}`.trim().replace(/\s+/g, ' ');
}
