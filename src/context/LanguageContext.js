import React, { createContext, useContext, useState, useEffect } from 'react';
import {
  LANGUAGES,
  DEFAULT_LANGUAGE,
  normalizeLanguage,
  detectBrowserLocale,
} from '../lib/locales';
import en from '../locales/en';
import es from '../locales/es';
import fr from '../locales/fr';
import de from '../locales/de';
import it from '../locales/it';
import pt from '../locales/pt';
import zh from '../locales/zh';
import yue from '../locales/yue';
import ja from '../locales/ja';
import ko from '../locales/ko';

export { LANGUAGES } from '../lib/locales';
export { COUNTRIES, DEFAULT_COUNTRY, normalizeCountry, defaultsForCountry } from '../lib/locales';

/** Base-language packs (en-US/en-GB → en, pt-BR/pt-PT → pt, …). */
const translations = { en, es, fr, de, it, pt, zh, yue, ja, ko };

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

function resolveTranslationPack(languageCode) {
  const code = normalizeLanguage(languageCode);
  const meta = LANGUAGES[code];
  const base = meta?.base || code.split('-')[0] || 'en';
  const pack = translations[base] || translations.en;
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

  const t = (key, params = {}) => {
    const pack = resolveTranslationPack(language);
    let text = pack[key] || translations.en[key] || key;

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
