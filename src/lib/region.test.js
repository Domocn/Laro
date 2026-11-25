import { describe, it, expect } from 'vitest';
import {
  nutritionStyleForCountry,
  styleFromPreferences,
  foodRegionForCountry,
  measurementUnitForCountryChange,
  carbsForStyle,
  badgeCarbsForStyle,
  carbsLabels,
  energyDisplay,
} from './region';
import { totalsFromBadges, scaleBadge } from './versionMacros';
import {
  ALL_COUNTRY_CODES,
  COMMON_COUNTRIES,
  countryOptions,
  countryName,
  normalizeCountry,
  defaultsForCountry,
} from './locales';

describe('country → nutrition style and food data', () => {
  it.each([
    ['GB', 'uk', 'uk'], ['IE', 'uk', 'uk'], ['FR', 'uk', 'uk'], ['NG', 'uk', 'uk'], ['JP', 'uk', 'uk'],
    ['AU', 'au', 'uk'], ['NZ', 'au', 'uk'],
    ['CA', 'ca', 'us'],
    ['US', 'us', 'us'], ['us', 'us', 'us'],
  ])('%s → %s style, %s data', (country, style, region) => {
    expect(nutritionStyleForCountry(country)).toBe(style);
    expect(foodRegionForCountry(country)).toBe(region);
  });

  it('defaults to UK', () => {
    expect(nutritionStyleForCountry(undefined)).toBe('uk');
    expect(nutritionStyleForCountry('ZZ')).toBe('uk');
    expect(styleFromPreferences({})).toBe('uk');
    expect(styleFromPreferences(null)).toBe('uk');
  });

  it('prefers the server-derived style, else derives from country', () => {
    expect(styleFromPreferences({ nutritionStyle: 'au', country: 'GB' })).toBe('au');
    expect(styleFromPreferences({ country: 'CA' })).toBe('ca');
  });
});

describe('country picker list', () => {
  it('has every ISO country with common ones first', () => {
    expect(ALL_COUNTRY_CODES).toHaveLength(249);
    const { common, rest } = countryOptions();
    expect(common.map((c) => c.code)).toEqual(['GB', 'IE', 'US', 'CA', 'AU', 'NZ']);
    expect(common[0].name).toBe('United Kingdom');
    expect(rest).toHaveLength(249 - COMMON_COUNTRIES.length);
    const names = rest.map((c) => c.name);
    expect([...names].sort((a, b) => a.localeCompare(b, 'en'))).toEqual(names);
    expect(rest.some((c) => c.code === 'GB')).toBe(false);
  });

  it('accepts any ISO country and keeps language for ones without defaults', () => {
    expect(normalizeCountry('ke')).toBe('KE');
    expect(normalizeCountry('uk')).toBe('GB');
    expect(normalizeCountry('ZZ')).toBe('GB');
    expect(countryName('KE')).toBe('Kenya');
    expect(defaultsForCountry('KE')).toMatchObject({ country: 'KE', language: null, measurementUnit: 'metric' });
    expect(defaultsForCountry('US')).toMatchObject({ language: 'en-US', measurementUnit: 'imperial' });
  });
});

describe('units follow the country unless the user picked something else', () => {
  it('switches the default', () => {
    expect(measurementUnitForCountryChange('metric', 'GB', 'US')).toBe('imperial');
    expect(measurementUnitForCountryChange('imperial', 'US', 'CA')).toBe('metric');
    expect(measurementUnitForCountryChange(undefined, 'GB', 'US')).toBe('imperial');
    expect(measurementUnitForCountryChange('metric', 'GB', 'AU')).toBe('metric');
  });
  it('keeps an explicit choice', () => {
    expect(measurementUnitForCountryChange('both', 'GB', 'US')).toBe('both');
    expect(measurementUnitForCountryChange('as_written', 'US', 'GB')).toBe('as_written');
  });
});

describe('carbs label + value by style', () => {
  const n = { calories: 400, carbs: 40, carbs_total: 46 };

  it('UK and AU show carbs without fibre, labelled "Carbs"', () => {
    for (const style of ['uk', 'au']) {
      const c = carbsForStyle(n, style);
      expect(c).toEqual({ value: 40, isTotal: false });
      expect(carbsLabels(style, c.isTotal)).toEqual({ short: 'C', full: 'Carbs' });
    }
  });

  it('US shows "Total carbs"', () => {
    const c = carbsForStyle(n, 'us');
    expect(c).toEqual({ value: 46, isTotal: true });
    expect(carbsLabels('us', c.isTotal).short).toBe('Total carbs');
  });

  it('Canada shows "Total carbohydrate"', () => {
    const c = carbsForStyle(n, 'ca');
    expect(c).toEqual({ value: 46, isTotal: true });
    expect(carbsLabels('ca', c.isTotal).short).toBe('Total carbohydrate');
  });

  it('total-carb styles fall back to the UK figure (and label) when unknown', () => {
    const c = carbsForStyle({ carbs: 40 }, 'us');
    expect(c).toEqual({ value: 40, isTotal: false });
    expect(carbsLabels('us', c.isTotal).short).toBe('C');
  });

  it('per-ingredient badges', () => {
    expect(badgeCarbsForStyle({ c: 10, c_total: 13 }, 'us')).toEqual({ value: 13, isTotal: true });
    expect(badgeCarbsForStyle({ c: 10, c_total: 13 }, 'ca')).toEqual({ value: 13, isTotal: true });
    expect(badgeCarbsForStyle({ c: 10, c_total: 13 }, 'uk')).toEqual({ value: 10, isTotal: false });
    expect(badgeCarbsForStyle({ c: 10 }, 'us')).toEqual({ value: 10, isTotal: false });
  });
});

describe('energy by style', () => {
  it('UK: kcal first, kJ secondary', () => {
    expect(energyDisplay(400, 'uk')).toEqual({ primary: '400 kcal', secondary: '1674 kJ', full: '400 kcal (1674 kJ)' });
  });
  it('AU/NZ: kJ first, then kcal', () => {
    expect(energyDisplay(400, 'au')).toMatchObject({ primary: '1674 kJ', secondary: '400 kcal' });
  });
  it('US/CA: Calories', () => {
    expect(energyDisplay(400, 'us')).toMatchObject({ primary: '400 Calories', secondary: null });
    expect(energyDisplay(400, 'ca')).toMatchObject({ primary: '400 Calories', secondary: null });
  });
  it('missing stays missing', () => {
    expect(energyDisplay(null, 'uk')).toBeNull();
  });
});

describe('totals from badges carry total carbs', () => {
  it('adds carbs_total only when every line has c_total', () => {
    const all = [{ p: 1, c: 10, c_total: 14, f: 1, cal: 50 }, { p: 1, c: 4, c_total: 6, f: 1, cal: 20 }];
    expect(totalsFromBadges(all, 2).carbs_total).toBe(10);
    const some = [...all, { p: 0, c: 2, f: 0, cal: 8 }];
    expect(totalsFromBadges(some, 2).carbs_total).toBeUndefined();
    expect(totalsFromBadges(some, 2, { carbs_total: 99 }).carbs_total).toBeUndefined();
  });
  it('scales c_total with the line', () => {
    expect(scaleBadge({ p: 2, c: 10, c_total: 12, f: 1, cal: 40 }, 2)).toEqual({ p: 4, c: 20, c_total: 24, f: 2, cal: 80 });
    expect(scaleBadge({ p: 2, c: 10, f: 1, cal: 40 }, 2)).toEqual({ p: 4, c: 20, f: 2, cal: 80 });
  });
});

describe('day strip energy text', () => {
  it('follows the style', async () => {
    const { energyStripText } = await import('./region');
    expect(energyStripText(1800, 2000, 'uk')).toBe('1800 / 2000 kcal');
    expect(energyStripText(1800, 2000, 'au')).toBe('7531 / 8368 kJ');
    expect(energyStripText(1800, 2000, 'us')).toBe('1800 / 2000 Calories');
  });
});
