import React, { createContext, useContext, useState, useEffect } from 'react';

const ThemeContext = createContext();

// Accent color presets
export const ACCENT_COLORS = {
  purple: { name: 'Lavender', primary: '#6C5CE7', secondary: '#A29BFE' },
  blue: { name: 'Ocean', primary: '#0984E3', secondary: '#74B9FF' },
  green: { name: 'Mint', primary: '#00B894', secondary: '#55EFC4' },
  orange: { name: 'Coral', primary: '#E17055', secondary: '#FAB1A0' },
  pink: { name: 'Rose', primary: '#FD79A8', secondary: '#FDCB6E' },
  teal: { name: 'Teal', primary: '#00CEC9', secondary: '#81ECEC' },
};

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return context;
};

export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('mise_theme');
    if (saved) return saved;
    // Check system preference
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
    return 'light';
  });

  const [accentColor, setAccentColor] = useState(() => {
    const saved = localStorage.getItem('mise_accent');
    return saved || 'purple';
  });

  const [reducedMotion, setReducedMotion] = useState(() => {
    const saved = localStorage.getItem('mise_reduced_motion');
    if (saved) return saved === 'true';
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  });

  // Apply theme to document
  useEffect(() => {
    localStorage.setItem('mise_theme', theme);
    
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [theme]);

  // Apply accent color as CSS variables
  useEffect(() => {
    localStorage.setItem('mise_accent', accentColor);
    
    const colors = ACCENT_COLORS[accentColor] || ACCENT_COLORS.purple;
    const root = document.documentElement;
    
    root.style.setProperty('--mise-primary', colors.primary);
    root.style.setProperty('--mise-secondary', colors.secondary);
    
    // Convert hex to HSL for Tailwind compatibility
    const primaryHSL = hexToHSL(colors.primary);
    const secondaryHSL = hexToHSL(colors.secondary);
    
    root.style.setProperty('--mise-primary-h', primaryHSL.h);
    root.style.setProperty('--mise-primary-s', `${primaryHSL.s}%`);
    root.style.setProperty('--mise-primary-l', `${primaryHSL.l}%`);
  }, [accentColor]);

  // Apply reduced motion preference
  useEffect(() => {
    localStorage.setItem('mise_reduced_motion', reducedMotion.toString());
    
    const root = document.documentElement;
    if (reducedMotion) {
      root.classList.add('reduce-motion');
    } else {
      root.classList.remove('reduce-motion');
    }
  }, [reducedMotion]);

  // Listen for system theme changes
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = (e) => {
      const saved = localStorage.getItem('mise_theme');
      // Only auto-switch if user hasn't set a preference (or set to 'system')
      if (!saved || saved === 'system') {
        setTheme(e.matches ? 'dark' : 'light');
      }
    };
    
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  const setThemeMode = (mode) => {
    if (mode === 'system') {
      localStorage.removeItem('mise_theme');
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

// Helper function to convert hex to HSL
function hexToHSL(hex) {
  // Remove the # if present
  hex = hex.replace(/^#/, '');
  
  // Parse the hex values
  const r = parseInt(hex.substring(0, 2), 16) / 255;
  const g = parseInt(hex.substring(2, 4), 16) / 255;
  const b = parseInt(hex.substring(4, 6), 16) / 255;
  
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h, s, l = (max + min) / 2;
  
  if (max === min) {
    h = s = 0; // achromatic
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
    l: Math.round(l * 100)
  };
}
