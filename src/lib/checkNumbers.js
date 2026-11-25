// "Check the numbers" (before / while cooking): which ingredient lines deserve a look, live
// per-serving totals with the user's fixes, label maths and the per-cook nutrition override.
// Server shape: GET /recipes/{id}/check-numbers (backend/services/confirmed_lines.py).

const MACRO_KEYS = ['p', 'c', 'f', 'cal'];
const CAPS = { p: 1000, c: 2000, f: 1000, cal: 10000 };

/** Lines the user should look at: AI estimates, vague amounts, no weight, plausibility flags,
 * no estimate at all. Lines they already confirmed are trusted. */
export function isUncertain(row) {
  if (!row || row.confirmed) return false;
  if (row.uncertain) return true;
  const m = row.macros;
  if (!m) return true;
  if (m.src !== 'db') return m.src !== 'user' && m.src !== 'barcode';
  return m.g == null && Number(m.cal) > 0;
}

/** { uncertain, trusted } in recipe order. Grouping uses the server's view of each line, so a
 * line doesn't jump between groups while the user is fixing it. */
export function splitLines(lines) {
  const uncertain = [];
  const trusted = [];
  for (const row of Array.isArray(lines) ? lines : []) {
    (isUncertain(row) ? uncertain : trusted).push(row);
  }
  return { uncertain, trusted };
}

/** The macros a line counts with: the user's fix for it if any, else the server's. */
export function effectiveMacros(row, edits = {}) {
  const edit = edits?.[row?.index];
  return edit?.macros || row?.macros || null;
}

/** Per-serving {calories, protein, carbs, fat} for these lines with the user's fixes, plus
 * `complete` (every line has numbers). */
export function totalsFor(lines, edits = {}, servings = 1) {
  const s = Math.max(1, Math.round(Number(servings) || 1));
  const sum = { p: 0, c: 0, f: 0, cal: 0 };
  let complete = true;
  for (const row of Array.isArray(lines) ? lines : []) {
    const m = effectiveMacros(row, edits);
    if (!m) {
      complete = false;
      continue;
    }
    for (const k of MACRO_KEYS) sum[k] += Number(m[k]) || 0;
  }
  return {
    calories: Math.round(sum.cal / s),
    protein: Math.round(sum.p / s),
    carbs: Math.round(sum.c / s),
    fat: Math.round(sum.f / s),
    complete,
  };
}

function num(value) {
  if (value === '' || value == null) return null;
  const n = Number(String(value).replace(',', '.'));
  return Number.isFinite(n) && n >= 0 ? n : null;
}

/** Label figures -> line macros (same maths as the server's badge_from_label).
 * basis '100g': figures per 100 g x usedG / 100; 'pack': figures per pack x packs.
 * Returns { macros } or { error } (plain-language). */
export function labelToMacros(label, { basis = '100g', usedG, packs, packG } = {}) {
  const fig = {
    cal: num(label?.kcal),
    p: num(label?.protein),
    c: num(label?.carbs),
    f: num(label?.fat),
  };
  if (Object.values(fig).some((v) => v == null)) return { error: 'Fill in kcal, protein, carbs and fat.' };
  let scale;
  let grams = null;
  if (basis === 'pack') {
    const n = num(packs);
    if (!n || n > 50) return { error: 'How many packs did you use?' };
    scale = n;
    const pg = num(packG);
    if (pg) grams = Math.round(pg * n * 10) / 10;
  } else {
    const g = num(usedG);
    if (!g || g > 10000) return { error: 'How many grams (or ml) did you use?' };
    if (fig.cal > 950) return { error: 'That is more than 950 kcal per 100 g. Check the label.' };
    scale = g / 100;
    grams = Math.round(g * 10) / 10;
  }
  const macros = {};
  for (const k of MACRO_KEYS) {
    macros[k] = Math.round(fig[k] * scale);
    if (macros[k] > CAPS[k]) return { error: 'That works out too high for one line. Check the amount.' };
  }
  if (grams != null) macros.g = grams;
  return { macros };
}

/** Body lines for PUT /recipes/{id}/confirmed-lines from the user's fixes. */
export function confirmedPayload(lines, edits = {}) {
  const out = [];
  for (const row of Array.isArray(lines) ? lines : []) {
    const edit = edits?.[row.index];
    if (!edit?.macros) continue;
    const m = edit.macros;
    const item = { index: row.index, line: row.line, p: m.p | 0, c: m.c | 0, f: m.f | 0, cal: m.cal | 0 };
    if (m.g != null) item.g = m.g;
    item.source = edit.source === 'barcode' ? 'barcode' : 'user';
    if (edit.barcode) item.barcode = edit.barcode;
    if (edit.product) item.product = String(edit.product).slice(0, 200);
    out.push(item);
  }
  return out;
}

export function hasEdits(edits) {
  return Object.values(edits || {}).some((e) => e?.macros);
}

/** Per-serving totals to send with this cook (meal log + Health Connect / Google Health), or
 * null when nothing was checked / the totals are incomplete. */
export function overrideFrom(totals, edits) {
  if (!totals?.complete || !hasEdits(edits)) return null;
  const out = {
    calories: totals.calories,
    protein: totals.protein,
    carbs: totals.carbs,
    fat: totals.fat,
  };
  return Object.values(out).some((v) => v > 0) ? out : null;
}

const SKIP_KEY = 'laro_check_numbers_skip:';

/** "Don't ask again for this recipe" (per device). */
export function readSkipCheck(recipeId) {
  try {
    return localStorage.getItem(SKIP_KEY + recipeId) === '1';
  } catch {
    return false;
  }
}

export function writeSkipCheck(recipeId, skip) {
  try {
    if (skip) localStorage.setItem(SKIP_KEY + recipeId, '1');
    else localStorage.removeItem(SKIP_KEY + recipeId);
  } catch {
    /* private mode: just ask next time */
  }
}

/** "500 g" / "1 bunch" / "" for the amount column. */
export function amountText(row) {
  return [row?.amount, row?.unit].map((x) => String(x || '').trim()).filter(Boolean).join(' ');
}
