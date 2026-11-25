import React from 'react';
import { formatPer100, weightNote } from '../lib/versionMacros';
import { carbsForStyle, carbsLabels, energyDisplay } from '../lib/region';

const PILL_CLS = {
  p: 'bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300',
  c: 'bg-sky-100 text-sky-700 dark:bg-sky-500/20 dark:text-sky-300',
  f: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
  cal: 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300',
};

const MODE_LABELS = {
  serving: ['nutritionPerServing', 'Per serving'],
  '100g': ['nutritionPer100g', 'Per 100 g'],
  total: ['nutritionRecipeTotal', 'Recipe total'],
};

function label(t, key, fallback) {
  const s = typeof t === 'function' ? t(key) : null;
  return s && s !== key ? s : fallback;
}

/**
 * Recipe totals card body: "Per serving | Per 100 g | Recipe total" toggle + colour pills.
 *
 * Per serving / Recipe total use `nutrition` (per serving) x `factor` (macro solver) x servings
 * for the total. Per 100 g uses `weights.per100g` (backend, from the line grams) and adds
 * "Recipe makes about 520 g" / "Loaf weighs about 880 g after baking"; it never scales.
 *
 * `onModeChange(mode)` — the page persists serving / 100 g as the recipe's basis.
 *
 * `nutritionStyle` (from the user's country): uk / au show carbs without fibre; us / ca show
 * total carbs (`carbs_total`) when known; energy is kcal (+kJ) for uk, kJ (+kcal) for au and
 * Calories for us / ca.
 */
export default function MacroTotals({
  nutrition,
  mode = 'serving',
  onModeChange,
  servings = 1,
  factor = 1,
  weights = null,
  recipe = null,
  pending = false,
  estimated = false,
  t,
  nutritionStyle = 'uk',
  children,
}) {
  const modes = ['serving', '100g', 'total'];
  const per100 = mode === '100g';
  const n = nutrition || {};
  const mult = mode === 'total' ? Math.max(1, Number(servings) || 1) : 1;
  const f = Number.isFinite(factor) && factor > 0 ? factor : 1;
  const val = (x) => (x == null ? null : Math.round(x * mult * f));
  const per = weights?.per100g || null;
  const style = nutritionStyle || 'uk';
  const carbsPill = (source, fmt) => {
    const c = carbsForStyle(source, style);
    const lbl = carbsLabels(style, c.isTotal, t);
    return { key: 'c', label: lbl.short, title: lbl.full, value: c.value == null ? null : fmt(c.value), unit: 'g' };
  };
  const energyPill = (kcal) => {
    const e = energyDisplay(kcal, style);
    return { key: 'cal', label: '🔥', value: e?.primary ?? null, secondary: e?.secondary, title: e?.full, unit: '' };
  };
  const pills = per100
    ? (per ? [
      { key: 'p', label: 'P', value: formatPer100(per.protein), unit: 'g' },
      carbsPill(per, formatPer100),
      { key: 'f', label: 'F', value: formatPer100(per.fat), unit: 'g' },
      energyPill(per.calories),
    ] : [])
    : [
      { key: 'p', label: 'P', value: val(n.protein), unit: 'g' },
      carbsPill(n, (x) => Math.round(x * mult * f)),
      { key: 'f', label: 'F', value: val(n.fat), unit: 'g' },
      energyPill(val(n.calories)),
    ];
  const shown = pills.filter((p) => p.value != null);
  const note = per100 ? weightNote(weights, recipe, t) : null;

  return (
    <div className="w-full rounded-2xl border border-border/60 bg-white dark:bg-card p-3 mt-1" data-testid="recipe-macro-card">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div
          role="group"
          aria-label={label(t, 'nutritionBasisLabel', 'Show nutrition')}
          className="inline-flex rounded-full bg-cream-subtle dark:bg-muted p-0.5 text-sm print:hidden"
          data-testid="nutrition-basis-toggle"
        >
          {modes.map((m) => (
            <button
              key={m}
              type="button"
              data-mode={m}
              aria-pressed={mode === m}
              onClick={() => onModeChange?.(m)}
              className={`px-3 py-1 rounded-full font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-laro ${mode === m ? 'bg-white dark:bg-card shadow-sm text-laro' : 'text-muted-foreground'}`}
            >
              {label(t, ...MODE_LABELS[m])}
            </button>
          ))}
        </div>
        {estimated && !pending && <span className="text-xs text-muted-foreground">est.</span>}
      </div>
      {pending && !per100 && (
        <p className="text-xs text-muted-foreground mb-2" data-testid="macros-pending">
          {label(t, 'macrosPendingForVersion', 'Working out macros for this version.')}
        </p>
      )}
      {per100 && !per && (
        <p className="text-sm text-muted-foreground mb-1" data-testid="per100g-pending">
          {label(t, 'per100gPending', "Per 100 g needs the weight of every ingredient, and that isn't worked out for this recipe yet.")}
        </p>
      )}
      {shown.length > 0 && (
        <div className="flex flex-wrap gap-2" data-testid={per100 ? 'per100g-pills' : 'serving-pills'}>
          {shown.map((p) => (
            <div
              key={p.key}
              className={`inline-flex items-baseline gap-1 rounded-full px-3 py-1.5 ${PILL_CLS[p.key]}`}
              title={p.title}
              data-testid={`macro-pill-${p.key}`}
            >
              <span className="text-xs font-bold opacity-80">{p.label}</span>
              <span className="text-base font-bold tabular-nums">{p.value}{p.unit}</span>
              {p.secondary && <span className="text-xs font-medium opacity-75 tabular-nums">· {p.secondary}</span>}
            </div>
          ))}
        </div>
      )}
      {note && (
        <p className="text-sm text-muted-foreground mt-2" data-testid="recipe-weight-note">{note}</p>
      )}
      {!per100 && children}
    </div>
  );
}
