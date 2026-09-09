import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

/**
 * Accent presets. Default Sage maps to Starbucks-inspired Green Accent.
 * Keys stay stable for localStorage / Android parity.
 */
export const ACCENT_COLORS = {
  sage: {
    name: 'Café Green',
    primary: '#00754A',   /* Green Accent — CTAs */
    secondary: '#2b5148', /* Green Uplift */
    light: '#d4e9e2',     /* Green Light */
    dark: '#006241',      /* Starbucks Green — headings / dark */
  },
  teal: {
    name: 'House Green',
    primary: '#1E3932',
    secondary: '#2b5148',
    light: '#d4e9e2',
    dark: '#006241',
  },
  blue: {
    name: 'Ocean',
    primary: '#3D6B8C',
    secondary: '#6B9BB8',
    light: '#E4EEF5',
    dark: '#2A4A66',
  },
  orange: {
    name: 'Coral',
    primary: '#c82014',
    secondary: '#D48A7A',
    light: '#F6E8E5',
    dark: '#9A3F32',
  },
  champagne: {
    name: 'Gold',
    primary: '#cba258',   /* Rewards/premium moments */
    secondary: '#dfc49d',
    light: '#faf6ee',
    dark: '#9A7D3A',
  },
  purple: {
    name: 'Plum',
    primary: '#6B5B7A',
    secondary: '#9A8AA8',
    light: '#F0EBF2',
    dark: '#4A3F54',
  },
  pink: {
    name: 'Rose',
    primary: '#A66B7A',
    secondary: '#C49AA6',
    light: '#F6EBEF',
    dark: '#7A4554',
  },
};

const LEGACY_ACCENT = {
  green: 'sage',
  mint: 'sage',
};

export function resolveAccentKey(key) {
  const mapped = LEGACY_ACCENT[key] || key;
  return ACCENT_COLORS[mapped] ? mapped : 'sage';
}

export function getAccentColors(key) {
  return ACCENT_COLORS[resolveAccentKey(key)];
}

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
};

function hexToRgbChannels(hex) {
  const h = hex.replace(/^#/, '');
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `${r} ${g} ${b}`;
}

/** Soft dark-mode surface tint from primary (26% accent on House Green ink). */
function darkSurfaceRgb(primaryHex) {
  const h = primaryHex.replace(/^#/, '');
  const pr = parseInt(h.substring(0, 2), 16);
  const pg = parseInt(h.substring(2, 4), 16);
  const pb = parseInt(h.substring(4, 6), 16);
  const br = 0x1e; /* #1E3932 */
  const bg = 0x39;
  const bb = 0x32;
  const t = 0.26;
  return `${Math.round(pr * t + br * (1 - t))} ${Math.round(pg * t + bg * (1 - t))} ${Math.round(pb * t + bb * (1 - t))}`;
}

function applyAccentToDocument(accentKey, themeMode = 'light') {
  const colors = getAccentColors(accentKey);
  const root = document.documentElement;
  const isDark = themeMode === 'dark' || root.classList.contains('dark');
  const primaryHSL = hexToHSL(colors.primary);
  // In dark mode, lift primary slightly so accents stay readable
  const displayHSL = isDark
    ? { ...primaryHSL, l: Math.min(primaryHSL.l + 12, 68) }
    : primaryHSL;

  const darkHex = isDark ? colors.secondary : colors.dark;

  root.style.setProperty('--laro-accent', colors.primary);
  root.style.setProperty('--laro-accent-rgb', hexToRgbChannels(colors.primary));
  root.style.setProperty(
    '--laro-accent-light',
    isDark ? `color-mix(in srgb, ${colors.primary} 26%, #1E3932)` : colors.light
  );
  /* Keep brand heading green stable unless user picked a non-green accent */
  if (resolveAccentKey(accentKey) === 'sage' || resolveAccentKey(accentKey) === 'teal') {
    root.style.setProperty('--laro-brand', colors.dark || '#006241');
    root.style.setProperty('--laro-house', '#1E3932');
  } else {
    root.style.setProperty('--laro-brand', colors.dark);
  }
  root.style.setProperty(
    '--laro-accent-light-rgb',
    isDark ? darkSurfaceRgb(colors.primary) : hexToRgbChannels(colors.light)
  );
  root.style.setProperty('--laro-accent-dark', darkHex);
  root.style.setProperty('--laro-accent-dark-rgb', hexToRgbChannels(darkHex));
  root.style.setProperty('--laro-accent-secondary', colors.secondary);
  root.style.setProperty('--laro-primary', colors.primary);
  root.style.setProperty('--laro-secondary', colors.secondary);

  root.style.setProperty('--laro-primary-h', String(displayHSL.h));
  root.style.setProperty('--laro-primary-s', `${displayHSL.s}%`);
  root.style.setProperty('--laro-primary-l', `${displayHSL.l}%`);

  // Drive shadcn primary / ring so buttons & focus rings follow the pick
  root.style.setProperty('--primary', `${displayHSL.h} ${displayHSL.s}% ${displayHSL.l}%`);
  root.style.setProperty('--ring', `${displayHSL.h} ${displayHSL.s}% ${displayHSL.l}%`);
  root.dataset.accent = resolveAccentKey(accentKey);
}

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('laro_theme');
    if (saved) return saved;
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  });

  const [accentColor, setAccentColorState] = useState(() => {
    const saved = localStorage.getItem('laro_accent');
    return resolveAccentKey(saved || 'sage');
  });

  const [reducedMotion, setReducedMotion] = useState(() => {
    const saved = localStorage.getItem('laro_reduced_motion');
    if (saved) return saved === 'true';
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  const setAccentColor = (key) => {
    setAccentColorState(resolveAccentKey(key));
  };

  useEffect(() => {
    localStorage.setItem('laro_theme', theme);

    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [theme]);

  useEffect(() => {
    const key = resolveAccentKey(accentColor);
    if (key !== accentColor) {
      setAccentColorState(key);
      return;
    }
    localStorage.setItem('laro_accent', key);
    applyAccentToDocument(key, theme);
  }, [accentColor, theme]);

  useEffect(() => {
    localStorage.setItem('laro_reduced_motion', reducedMotion.toString());

    const root = document.documentElement;
    if (reducedMotion) {
      root.classList.add('reduce-motion');
    } else {
      root.classList.remove('reduce-motion');
    }
  }, [reducedMotion]);

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e) => {
      const saved = localStorage.getItem('laro_theme');
      if (!saved || saved === 'system') {
        setTheme(e.matches ? 'dark' : 'light');
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

  const setThemeMode = (mode) => {
    if (mode === 'system') {
      localStorage.removeItem('laro_theme');
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      setTheme(systemTheme);
    } else {
      setTheme(mode);
    }
  };

  const value = {
    theme,
    setTheme,
    setThemeMode,
    toggleTheme,
    isDark: theme === 'dark',
    accentColor,
    setAccentColor,
    accentColors: ACCENT_COLORS,
    reducedMotion,
    setReducedMotion,
  };

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
};

function hexToHSL(hex) {
  hex = hex.replace(/^#/, '');

  const r = parseInt(hex.substring(0, 2), 16) / 255;
  const g = parseInt(hex.substring(2, 4), 16) / 255;
  const b = parseInt(hex.substring(4, 6), 16) / 255;

  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h;
  let s;
  const l = (max + min) / 2;

  if (max === min) {
    h = s = 0;
  } else {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
      case g: h = ((b - r) / d + 2) / 6; break;
      case b: h = ((r - g) / d + 4) / 6; break;
      default: h = 0;
    }
  }

  return {
    h: Math.round(h * 360),
    s: Math.round(s * 100),
    l: Math.round(l * 100),
  };
}
