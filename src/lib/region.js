// Nutrition style, derived from the user's country (Settings → Country; default GB).
// Keep aligned with backend/utils/region.py and android util/NutritionStyle.kt.
//   uk — UK, EU and every country not listed below: carbs exclude fibre, kcal (+kJ), metric.
//   au — AU, NZ: as uk, but energy in kJ first (then kcal).
//   ca — CA: total carbohydrate incl. fibre, "Calories", metric.
//   us — US: total carbs incl. fibre, "Calories", US customary units.
// Line macros may carry `c_total` (incl. fibre) next to `c` (fibre excluded); recipe nutrition
// may carry `carbs_total`. Older rows have neither, so total-carb styles fall back to the UK
// figure and label it "Carbs" — never "Total carbs" for a number that isn't one.
import { defaultsForCountry, normalizeCountry } from './locales';

export const DEFAULT_STYLE = 'uk';
const STYLE_BY_COUNTRY = { US: 'us', CA: 'ca', AU: 'au', NZ: 'au' };
const TOTAL_CARB_STYLES = new Set(['us', 'ca']);
const KJ_PER_KCAL = 4.184;

export function nutritionStyleForCountry(country) {
  return STYLE_BY_COUNTRY[normalizeCountry(country)] || DEFAULT_STYLE;
}

/** Style from a /preferences payload (server-derived `nutritionStyle`, else from `country`). */
export function styleFromPreferences(prefs) {
  const s = prefs?.nutritionStyle;
  if (s && ['uk', 'au', 'ca', 'us'].includes(s)) return s;
  return nutritionStyleForCountry(prefs?.country);
}

/** Food-data region the backend uses for lookups: USDA-first for US / CA, UK otherwise. */
export function foodRegionForCountry(country) {
  const c = normalizeCountry(country);
  return c === 'US' || c === 'CA' ? 'us' : 'uk';
}

/**
 * Units after changing country: follow the new country's default only when the current choice is
 * still the old country's default (or unset) — an explicit pick is kept.
 */
export function measurementUnitForCountryChange(current, fromCountry, toCountry) {
  const from = defaultsForCountry(fromCountry).measurementUnit;
  const to = defaultsForCountry(toCountry).measurementUnit;
  if (!current || current === from) return to;
  return current;
}

const num = (v) => (v == null || v === '' || Number.isNaN(Number(v)) ? null : Number(v));

/** Which carbs figure to show. @returns {{ value: number|null, isTotal: boolean }} */
export function carbsForStyle(nutrition, style) {
  const uk = num(nutrition?.carbs);
  if (TOTAL_CARB_STYLES.has(style)) {
    const total = num(nutrition?.carbs_total);
    if (total != null) return { value: total, isTotal: true };
  }
  return { value: uk, isTotal: false };
}

/** Carbs grams for one ingredient badge ({c, c_total?}). */
export function badgeCarbsForStyle(badge, style) {
  if (TOTAL_CARB_STYLES.has(style) && num(badge?.c_total) != null) {
    return { value: num(badge.c_total), isTotal: true };
  }
  return { value: num(badge?.c) ?? 0, isTotal: false };
}

function tr(t, key, fallback) {
  const s = typeof t === 'function' ? t(key) : null;
  return s && s !== key ? s : fallback;
}

/** Visible pill label + full accessible name for the carbs figure. */
export function carbsLabels(style, isTotal, t) {
  if (isTotal && style === 'ca') {
    const full = tr(t, 'totalCarbohydrateLabel', 'Total carbohydrate');
    return { short: full, full };
  }
  if (isTotal) {
    return { short: tr(t, 'totalCarbsShort', 'Total carbs'), full: tr(t, 'totalCarbsLabel', 'Total carbs (incl. fibre)') };
  }
  return { short: 'C', full: tr(t, 'carbsLabel', 'Carbs') };
}

/** Day strip "current / target" energy text: kcal (UK), kJ (AU/NZ), Calories (US/CA). */
export function energyStripText(current, target, style) {
  const c = num(current) ?? 0;
  const tg = num(target);
  if (style === 'au') {
    return `${Math.round(c * KJ_PER_KCAL)} / ${tg == null ? '—' : Math.round(tg * KJ_PER_KCAL)} kJ`;
  }
  const unit = style === 'us' || style === 'ca' ? 'Calories' : 'kcal';
  return `${Math.round(c)} / ${tg == null ? '—' : Math.round(tg)} ${unit}`;
}

/**
 * Energy as labelled for the style.
 * uk: "400 kcal" (+ "1674 kJ"); au: "1674 kJ" (+ "400 kcal"); us / ca: "400 Calories".
 * @returns {{ primary: string, secondary: string|null, full: string }|null}
 */
export function energyDisplay(kcal, style) {
  const k = num(kcal);
  if (k == null) return null;
  const kcalTxt = `${Math.round(k)} kcal`;
  const kjTxt = `${Math.round(k * KJ_PER_KCAL)} kJ`;
  if (style === 'us' || style === 'ca') {
    const txt = `${Math.round(k)} Calories`;
    return { primary: txt, secondary: null, full: txt };
  }
  if (style === 'au') return { primary: kjTxt, secondary: kcalTxt, full: `${kjTxt} (${kcalTxt})` };
  return { primary: kcalTxt, secondary: kjTxt, full: `${kcalTxt} (${kjTxt})` };
}
