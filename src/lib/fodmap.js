// Low FODMAP adaptation helpers for the recipe page / edit form.
// recipe.adaptations = { low_fodmap: { swaps: [{ from, to }], notes } }

export const FODMAP_VIEW_KEY = 'laro_fodmap_view';

/** The recipe's Low FODMAP adaptation, or null when it has nothing useful. */
export function getLowFodmap(recipe) {
  const lf = recipe?.adaptations?.low_fodmap;
  if (!lf || typeof lf !== 'object') return null;
  const swaps = (Array.isArray(lf.swaps) ? lf.swaps : []).filter(
    (s) => s && String(s.from || '').trim() && String(s.to || '').trim(),
  );
  const notes = String(lf.notes || '').trim();
  if (!swaps.length && !notes) return null;
  return { swaps, notes };
}

/** First swap whose `from` appears in the ingredient name (case-insensitive; longest match wins). */
export function findSwap(name, swaps) {
  const n = String(name || '').toLowerCase();
  if (!n) return null;
  let best = null;
  for (const s of swaps || []) {
    const from = String(s?.from || '').trim().toLowerCase();
    if (from && n.includes(from) && (!best || from.length > best.from.trim().length)) best = s;
  }
  return best;
}

/** Ingredients with swap info: [{ ingredient, swap }] where swap is null when unchanged. */
export function applyFodmapSwaps(ingredients, swaps) {
  return (ingredients || []).map((ingredient) => {
    const name = typeof ingredient === 'string' ? ingredient : ingredient?.name;
    return { ingredient, swap: findSwap(name, swaps) };
  });
}

/** Edit-form rows/notes -> adaptations object to save (null clears it). Keeps other adaptations. */
export function buildAdaptations(existing, swaps, notes) {
  const cleanSwaps = (swaps || [])
    .map((s) => ({ from: String(s?.from || '').trim(), to: String(s?.to || '').trim() }))
    .filter((s) => s.from && s.to);
  const cleanNotes = String(notes || '').trim();
  const rest = { ...(existing && typeof existing === 'object' ? existing : {}) };
  delete rest.low_fodmap;
  if (cleanSwaps.length || cleanNotes) rest.low_fodmap = { swaps: cleanSwaps, notes: cleanNotes };
  return Object.keys(rest).length ? rest : null;
}

export function readFodmapView() {
  try {
    return localStorage.getItem(FODMAP_VIEW_KEY) === 'low_fodmap' ? 'low_fodmap' : 'original';
  } catch {
    return 'original';
  }
}

export function writeFodmapView(view) {
  try {
    localStorage.setItem(FODMAP_VIEW_KEY, view === 'low_fodmap' ? 'low_fodmap' : 'original');
  } catch {
    /* private mode — choice just isn't remembered */
  }
}
