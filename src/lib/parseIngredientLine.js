/**
 * Parse a free-text ingredient line into { amount, unit, name }.
 *
 * Important: never treat an arbitrary first word as a unit. The old ImportRecipe
 * regex `^([\d./]+)?\s*([a-zA-Z]+)?\s*(.+)$` backtracked on single words
 * ("pepper" → unit "peppe", name "r") and stole the first word of multi-word
 * names with no quantity ("chinese five spice" → unit "chinese").
 */

const MEASURE_UNITS = new Set(
  [
    // metric
    'g',
    'gram',
    'grams',
    'kg',
    'kilogram',
    'kilograms',
    'ml',
    'milliliter',
    'milliliters',
    'millilitre',
    'millilitres',
    'l',
    'liter',
    'liters',
    'litre',
    'litres',
    // imperial / US
    'oz',
    'ounce',
    'ounces',
    'lb',
    'lbs',
    'pound',
    'pounds',
    'tsp',
    'tsps',
    'teaspoon',
    'teaspoons',
    'tbsp',
    'tbsps',
    'tablespoon',
    'tablespoons',
    'cup',
    'cups',
    'pint',
    'pints',
    'pt',
    'quart',
    'quarts',
    'qt',
    'gallon',
    'gallons',
    'gal',
    'fl',
    // common kitchen counts / measures
    'clove',
    'cloves',
    'pinch',
    'pinches',
    'dash',
    'dashes',
    'drop',
    'drops',
    'sprig',
    'sprigs',
    'bunch',
    'bunches',
    'leaf',
    'leaves',
    'slice',
    'slices',
    'piece',
    'pieces',
    'can',
    'cans',
    'jar',
    'jars',
    'package',
    'packages',
    'pack',
    'packs',
    'bag',
    'bags',
    'box',
    'boxes',
    'stick',
    'sticks',
    'stalk',
    'stalks',
    'head',
    'heads',
    'ear',
    'ears',
    'sheet',
    'sheets',
    'serving',
    'servings',
  ].map((u) => u.toLowerCase())
);

/** Size / count words only treated as units when an amount is present (e.g. "1 large egg"). */
const AMOUNT_SCOPED_UNITS = new Set(
  ['large', 'medium', 'small', 'whole', 'extra-large', 'xl'].map((u) => u.toLowerCase())
);

const AMOUNT_RE =
  /^((?:\d+\s+\d+\/\d+)|(?:\d+\/\d+)|(?:\d+[.,]\d+)|(?:\d+))\s*/i;

export function isIngredientUnit(token, { hasAmount = false } = {}) {
  if (!token) return false;
  const t = String(token).trim().toLowerCase();
  if (!t) return false;
  if (MEASURE_UNITS.has(t)) return true;
  if (hasAmount && AMOUNT_SCOPED_UNITS.has(t)) return true;
  return false;
}

/**
 * Repair rows corrupted by the old line parser (or similar): non-unit text
 * sitting in `unit` gets folded back into `name`.
 */
export function normalizeIngredient(ing = {}) {
  const amount =
    ing.amount != null && String(ing.amount).trim() !== ''
      ? String(ing.amount).trim()
      : '';
  let unit = ing.unit != null ? String(ing.unit).trim() : '';
  let name = ing.name != null ? String(ing.name).trim() : '';

  if (unit && !isIngredientUnit(unit, { hasAmount: Boolean(amount) })) {
    // Old regex split "pepper" → unit "peppe" + name "r". Rejoin tightly when
    // the name looks like a 1–2 letter remnant of the same word.
    const tight =
      /^[A-Za-z]+$/.test(unit) && /^[A-Za-z]{1,2}$/.test(name);
    name = tight ? `${unit}${name}` : `${unit} ${name}`.trim();
    unit = '';
  }

  return {
    ...ing,
    amount,
    unit,
    name,
  };
}

export function parseIngredientLine(line = '') {
  const raw = String(line || '').trim();
  if (!raw) return { amount: '', unit: '', name: '' };

  let rest = raw;
  let amount = '';
  const amountMatch = rest.match(AMOUNT_RE);
  if (amountMatch) {
    amount = amountMatch[1].replace(',', '.');
    rest = rest.slice(amountMatch[0].length).trim();
  }

  if (!rest) {
    return { amount, unit: '', name: '' };
  }

  // "100g mushrooms" / "250ml water" (unit glued to amount)
  const glued = rest.match(/^([a-zA-Z]+)\b\s*(.*)$/);
  if (glued && isIngredientUnit(glued[1], { hasAmount: Boolean(amount) })) {
    return {
      amount,
      unit: glued[1],
      name: (glued[2] || '').trim(),
    };
  }

  // No amount and first token isn't a known unit → entire line is the name
  // (fixes "pepper", "dill", "chinese five spice", "spring onion").
  if (!amount) {
    return { amount: '', unit: '', name: rest };
  }

  // Amount present but next token isn't a unit → "1 spring onion", "4 eggs"
  return { amount, unit: '', name: rest };
}

export function ingredientsToText(ingredients = []) {
  return (ingredients || [])
    .map((ing) => {
      if (typeof ing === 'string') return ing;
      const fixed = normalizeIngredient(ing);
      const amt =
        fixed.amount != null && fixed.amount !== '' ? `${fixed.amount}` : '';
      const unit = fixed.unit ? ` ${fixed.unit}` : '';
      const name = fixed.name || '';
      return `${amt}${unit} ${name}`.trim();
    })
    .filter(Boolean)
    .join('\n');
}

export function textToIngredients(text = '') {
  return String(text || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => parseIngredientLine(line));
}
