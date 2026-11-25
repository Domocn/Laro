/**
 * Shared locale + country catalogues for Laro.
 * Flags must match the country/region the label represents.
 */

/** UI languages available in the app */
export const LANGUAGES = {
  'en-US': { name: 'English (US)', flag: '🇺🇸', voice: 'en-US', base: 'en' },
  'en-GB': { name: 'English (UK)', flag: '🇬🇧', voice: 'en-GB', base: 'en' },
  es: { name: 'Español', flag: '🇪🇸', voice: 'es-ES', base: 'es' },
  fr: { name: 'Français', flag: '🇫🇷', voice: 'fr-FR', base: 'fr' },
  de: { name: 'Deutsch', flag: '🇩🇪', voice: 'de-DE', base: 'de' },
  it: { name: 'Italiano', flag: '🇮🇹', voice: 'it-IT', base: 'it' },
  'pt-BR': { name: 'Português (Brasil)', flag: '🇧🇷', voice: 'pt-BR', base: 'pt' },
  'pt-PT': { name: 'Português (Portugal)', flag: '🇵🇹', voice: 'pt-PT', base: 'pt' },
  zh: { name: '中文（简体）', flag: '🇨🇳', voice: 'zh-CN', base: 'zh' },
  yue: { name: '粵語 (Cantonese)', flag: '🇭🇰', voice: 'zh-HK', base: 'yue' },
  ja: { name: '日本語', flag: '🇯🇵', voice: 'ja-JP', base: 'ja' },
  ko: { name: '한국어', flag: '🇰🇷', voice: 'ko-KR', base: 'ko' },
};

/** Countries offered at signup / preferences (flags match ISO region) */
export const COUNTRIES = {
  US: { name: 'United States', flag: '🇺🇸', language: 'en-US', measurementUnit: 'imperial', currency: 'USD' },
  GB: { name: 'United Kingdom', flag: '🇬🇧', language: 'en-GB', measurementUnit: 'metric', currency: 'GBP' },
  IE: { name: 'Ireland', flag: '🇮🇪', language: 'en-GB', measurementUnit: 'metric', currency: 'EUR' },
  CA: { name: 'Canada', flag: '🇨🇦', language: 'en-US', measurementUnit: 'metric', currency: 'CAD' },
  AU: { name: 'Australia', flag: '🇦🇺', language: 'en-GB', measurementUnit: 'metric', currency: 'AUD' },
  NZ: { name: 'New Zealand', flag: '🇳🇿', language: 'en-GB', measurementUnit: 'metric', currency: 'NZD' },
  ES: { name: 'Spain', flag: '🇪🇸', language: 'es', measurementUnit: 'metric', currency: 'EUR' },
  MX: { name: 'Mexico', flag: '🇲🇽', language: 'es', measurementUnit: 'metric', currency: 'MXN' },
  FR: { name: 'France', flag: '🇫🇷', language: 'fr', measurementUnit: 'metric', currency: 'EUR' },
  BE: { name: 'Belgium', flag: '🇧🇪', language: 'fr', measurementUnit: 'metric', currency: 'EUR' },
  DE: { name: 'Germany', flag: '🇩🇪', language: 'de', measurementUnit: 'metric', currency: 'EUR' },
  AT: { name: 'Austria', flag: '🇦🇹', language: 'de', measurementUnit: 'metric', currency: 'EUR' },
  CH: { name: 'Switzerland', flag: '🇨🇭', language: 'de', measurementUnit: 'metric', currency: 'CHF' },
  IT: { name: 'Italy', flag: '🇮🇹', language: 'it', measurementUnit: 'metric', currency: 'EUR' },
  BR: { name: 'Brazil', flag: '🇧🇷', language: 'pt-BR', measurementUnit: 'metric', currency: 'BRL' },
  PT: { name: 'Portugal', flag: '🇵🇹', language: 'pt-PT', measurementUnit: 'metric', currency: 'EUR' },
  CN: { name: 'China', flag: '🇨🇳', language: 'zh', measurementUnit: 'metric', currency: 'CNY' },
  HK: { name: 'Hong Kong', flag: '🇭🇰', language: 'yue', measurementUnit: 'metric', currency: 'HKD' },
  MO: { name: 'Macao', flag: '🇲🇴', language: 'yue', measurementUnit: 'metric', currency: 'MOP' },
  TW: { name: 'Taiwan', flag: '🇹🇼', language: 'zh', measurementUnit: 'metric', currency: 'TWD' },
  JP: { name: 'Japan', flag: '🇯🇵', language: 'ja', measurementUnit: 'metric', currency: 'JPY' },
  KR: { name: 'South Korea', flag: '🇰🇷', language: 'ko', measurementUnit: 'metric', currency: 'KRW' },
};

/** Every ISO 3166-1 alpha-2 country ("Which country are you in?"). COUNTRIES only lists the
 * ones with their own language / unit defaults. Keep in sync with backend/utils/locales.py. */
export const ALL_COUNTRY_CODES = (
  'AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE ' +
  'BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD ' +
  'CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM ' +
  'DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF ' +
  'GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ' +
  'ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN ' +
  'KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME ' +
  'MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA ' +
  'NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM ' +
  'PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI ' +
  'SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK ' +
  'TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI ' +
  'VN VU WF WS YE YT ZA ZM ZW '
).trim().split(/\s+/);

/** Shown first in the country picker. */
export const COMMON_COUNTRIES = ['GB', 'IE', 'US', 'CA', 'AU', 'NZ'];

const ALL_COUNTRY_SET = new Set(ALL_COUNTRY_CODES);
let regionNames = null;

/** English country name (Intl when available; catalogue name / code otherwise). */
export function countryName(code) {
  const upper = String(code || '').toUpperCase();
  if (upper === 'GB') return 'United Kingdom';
  try {
    if (!regionNames && typeof Intl !== 'undefined' && Intl.DisplayNames) {
      regionNames = new Intl.DisplayNames(['en'], { type: 'region' });
    }
    const name = regionNames?.of(upper);
    if (name && name !== upper) return name;
  } catch {
    /* fall through */
  }
  return COUNTRIES[upper]?.name || upper;
}

/** Flag emoji from the two regional-indicator letters. */
export function countryFlag(code) {
  const upper = String(code || '').toUpperCase();
  if (!/^[A-Z]{2}$/.test(upper)) return '';
  return String.fromCodePoint(...[...upper].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}

/** Picker order: common countries first, then every other country A-Z by name. */
export function countryOptions() {
  const common = COMMON_COUNTRIES.map((code) => ({ code, name: countryName(code), flag: countryFlag(code) }));
  const rest = ALL_COUNTRY_CODES.filter((c) => !COMMON_COUNTRIES.includes(c))
    .map((code) => ({ code, name: countryName(code), flag: countryFlag(code) }))
    .sort((a, b) => a.name.localeCompare(b.name, 'en'));
  return { common, rest };
}

export const DEFAULT_LANGUAGE = 'en-GB';
export const DEFAULT_COUNTRY = 'GB';

/** Normalize legacy codes (`en` → `en-US`, `pt` → `pt-BR`) and unknown values. */
export function normalizeLanguage(code) {
  if (!code) return DEFAULT_LANGUAGE;
  if (code === 'en') return 'en-US';
  // Legacy bare Portuguese → Brazil (previous default)
  if (code === 'pt') return 'pt-BR';
  const lower = String(code).toLowerCase().replace(/_/g, '-');
  // Browser / BCP-47 aliases for Cantonese
  if (
    lower === 'zh-hk' ||
    lower === 'zh-mo' ||
    lower === 'zh-yue' ||
    lower === 'yue-hk' ||
    lower === 'yue-hant' ||
    lower.startsWith('yue')
  ) {
    return 'yue';
  }
  if (LANGUAGES[code]) return code;
  // Case-insensitive exact match (pt-br → pt-BR)
  const exact = Object.keys(LANGUAGES).find((k) => k.toLowerCase() === lower);
  if (exact) return exact;
  const parts = String(code).split(/[-_]/);
  const base = parts[0].toLowerCase();
  if (base === 'en') {
    const region = parts[1]?.toUpperCase();
    if (region === 'GB' || region === 'UK') return 'en-GB';
    return 'en-US';
  }
  if (base === 'pt') {
    const region = parts[1]?.toUpperCase();
    if (region === 'PT') return 'pt-PT';
    return 'pt-BR';
  }
  if (LANGUAGES[base]) return base;
  return DEFAULT_LANGUAGE;
}

export function normalizeCountry(code) {
  if (!code) return DEFAULT_COUNTRY;
  const upper = String(code).toUpperCase();
  if (upper === 'UK') return 'GB';
  return COUNTRIES[upper] || ALL_COUNTRY_SET.has(upper) ? upper : DEFAULT_COUNTRY;
}

/**
 * Suggest language + units when the user picks a country. Countries without a catalogue entry
 * get metric and `language: null` (keep whatever language is already chosen).
 */
export function defaultsForCountry(countryCode) {
  const code = normalizeCountry(countryCode);
  const c = COUNTRIES[code];
  return {
    country: code,
    language: c ? c.language : null,
    measurementUnit: c ? c.measurementUnit : 'metric',
    currency: c ? c.currency : null,
  };
}

/** Detect browser locale → language + country guess. */
export function detectBrowserLocale() {
  const nav = (typeof navigator !== 'undefined' && navigator.language) || 'en-GB';
  const parts = nav.split('-');
  const lang = normalizeLanguage(nav);
  let country = DEFAULT_COUNTRY;
  if (parts[1] && COUNTRIES[parts[1].toUpperCase()]) {
    country = parts[1].toUpperCase();
  } else if (lang === 'en-US') {
    country = 'US';
  } else if (lang === 'en-GB') {
    country = 'GB';
  } else if (lang === 'pt-BR') {
    country = 'BR';
  } else if (lang === 'pt-PT') {
    country = 'PT';
  } else if (lang === 'yue') {
    country = 'HK';
  } else {
    // Prefer a country whose default language matches
    const match = Object.entries(COUNTRIES).find(([, v]) => v.language === lang);
    if (match) country = match[0];
  }
  return { language: lang, country };
}
