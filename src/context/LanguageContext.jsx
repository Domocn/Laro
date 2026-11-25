import React, { createContext, useContext, useState, useEffect } from 'react';
import {
  LANGUAGES,
  DEFAULT_LANGUAGE,
  normalizeLanguage,
  detectBrowserLocale,
} from '../lib/locales';
import en from '../locales/en';

export { LANGUAGES } from '../lib/locales';
export { COUNTRIES, DEFAULT_COUNTRY, normalizeCountry, defaultsForCountry } from '../lib/locales';

/**
 * Base-language packs (en-US/en-GB → en, pt-BR/pt-PT → pt, …).
 *
 * Only English is bundled up front. The other nine are ~600 KB of strings
 * that a single-language visitor would never read, so each is code-split and
 * fetched the first time that language is actually selected. `packCache`
 * keeps them for the rest of the session.
 */
const loadPack = {
  es: () => import('../locales/es'),
  fr: () => import('../locales/fr'),
  de: () => import('../locales/de'),
  it: () => import('../locales/it'),
  pt: () => import('../locales/pt'),
  zh: () => import('../locales/zh'),
  yue: () => import('../locales/yue'),
  ja: () => import('../locales/ja'),
  ko: () => import('../locales/ko'),
};

const packCache = { en };

function loadTranslationPack(base) {
  if (packCache[base]) return Promise.resolve(packCache[base]);
  const loader = loadPack[base];
  if (!loader) return Promise.resolve(en);
  return loader()
    .then((mod) => {
      packCache[base] = mod.default;
      return mod.default;
    })
    // A failed language chunk must never leave the app without strings.
    .catch(() => en);
}

/** Light UK spelling / wording overrides on top of the shared English pack. */
const EN_GB_OVERRIDES = {
  favorite: 'Favourite',
  favorites: 'Favourites',
  color: 'Colour',
  organize: 'Organise',
};

/** European Portuguese wording on top of the shared (Brazilian) pt pack. */
const PT_PT_OVERRIDES = {
  save: 'Guardar',
  delete: 'Eliminar',
  search: 'Pesquisar',
  loading: 'A carregar...',
  settings: 'Definições',
  signUp: 'Registar',
  startCooking: 'Começar a Cozinhar',
};

function baseLanguageFor(languageCode) {
  const code = normalizeLanguage(languageCode);
  const meta = LANGUAGES[code];
  return meta?.base || code.split('-')[0] || 'en';
}

/**
 * Fold the regional wording overrides into a pack.
 *
 * This used to run on every `t()` call, spreading two objects per lookup
 * across ~1,600 call sites. It is now called once per language change and the
 * result is held in state.
 */
function withOverrides(code, pack) {
  if (code === 'en-GB') {
    return { ...pack, ...EN_GB_OVERRIDES };
  }
  if (code === 'pt-PT') {
    return { ...pack, ...PT_PT_OVERRIDES };
  }
  return pack;
}

const LanguageContext = createContext();

export const useLanguage = () => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within LanguageProvider');
  }
  return context;
};

export const LanguageProvider = ({ children }) => {
  const [language, setLanguageState] = useState(() => {
    const saved = localStorage.getItem('laro_language');
    if (saved) return normalizeLanguage(saved);
    return detectBrowserLocale().language || DEFAULT_LANGUAGE;
  });

  const setLanguage = (code) => {
    setLanguageState(normalizeLanguage(code));
  };

  useEffect(() => {
    localStorage.setItem('laro_language', language);
    document.documentElement.lang = language;
  }, [language]);

  // Resolve the active pack once per language change instead of rebuilding it
  // on every t() call. On a *switch* the previous pack stays up until the new
  // chunk lands, so no flash. On first mount a non-English visitor does see
  // English until their chunk resolves — unavoidable once the packs are
  // code-split, and only on the first load (the service worker caches it).
  const [pack, setPack] = useState(() => withOverrides(normalizeLanguage(language), en));

  useEffect(() => {
    const code = normalizeLanguage(language);
    const base = baseLanguageFor(code);
    let cancelled = false;

    if (packCache[base]) {
      setPack(withOverrides(code, packCache[base]));
      return undefined;
    }

    loadTranslationPack(base).then((loaded) => {
      if (!cancelled) setPack(withOverrides(code, loaded));
    });

    return () => {
      cancelled = true;
    };
  }, [language]);

  const t = (key, params = {}) => {
    let text = pack[key] || en[key] || key;

    Object.entries(params).forEach(([param, value]) => {
      text = text.replaceAll(`{${param}}`, String(value));
    });

    return text;
  };

  const value = {
    language,
    setLanguage,
    t,
    languages: LANGUAGES,
  };

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
};
