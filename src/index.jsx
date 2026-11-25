import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { installErrorReporter } from "@/lib/errorReporter";
import { trackVisit } from "@/lib/linkTracking";

installErrorReporter();
trackVisit();

// Apply theme + accent before render to prevent flash (must match ThemeContext)
(() => {
  const theme = localStorage.getItem('laro_theme');
  // Migrate legacy key once
  const legacy = localStorage.getItem('laro_dark_mode');
  if (!theme && legacy != null) {
    localStorage.setItem('laro_theme', legacy === 'true' ? 'dark' : 'light');
    localStorage.removeItem('laro_dark_mode');
  }
  const resolved = localStorage.getItem('laro_theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const useDark =
    resolved === 'dark' ||
    ((!resolved || resolved === 'system') && prefersDark);
  if (useDark) document.documentElement.classList.add('dark');

  // Accent presets (keep in sync with ThemeContext ACCENT_COLORS)
  const accents = {
    sage: { primary: '#4A7C63', light: '#E8F0EB', dark: '#2F5442', secondary: '#6B9B82' },
    teal: { primary: '#3D8B8C', light: '#E4F2F2', dark: '#2A6667', secondary: '#6BB0B1' },
    blue: { primary: '#3D6B8C', light: '#E4EEF5', dark: '#2A4A66', secondary: '#6B9BB8' },
    orange: { primary: '#C45C4A', light: '#F6E8E5', dark: '#9A3F32', secondary: '#D48A7A' },
    champagne: { primary: '#C4A35A', light: '#F5EFD9', dark: '#9A7D3A', secondary: '#D4BA7A' },
    purple: { primary: '#6B5B7A', light: '#F0EBF2', dark: '#4A3F54', secondary: '#9A8AA8' },
    pink: { primary: '#A66B7A', light: '#F6EBEF', dark: '#7A4554', secondary: '#C49AA6' },
    green: null, // legacy → sage
  };
  let accentKey = localStorage.getItem('laro_accent') || 'sage';
  if (accentKey === 'green' || accentKey === 'mint') accentKey = 'sage';
  const accent = accents[accentKey] || accents.sage;
  const toRgb = (hex) => {
    const h = hex.replace('#', '');
    return `${parseInt(h.slice(0, 2), 16)} ${parseInt(h.slice(2, 4), 16)} ${parseInt(h.slice(4, 6), 16)}`;
  };
  const root = document.documentElement;
  root.style.setProperty('--laro-accent', accent.primary);
  root.style.setProperty('--laro-accent-light', accent.light);
  root.style.setProperty('--laro-accent-dark', accent.dark);
  root.style.setProperty('--laro-accent-secondary', accent.secondary);
  root.style.setProperty('--laro-accent-rgb', toRgb(accent.primary));
  root.style.setProperty('--laro-accent-light-rgb', toRgb(accent.light));
  root.style.setProperty('--laro-accent-dark-rgb', toRgb(accent.dark));
  root.dataset.accent = accents[accentKey] ? accentKey : 'sage';
})();

// Register Service Worker for PWA.
// Use /sw.js (not /service-worker.js) — Cloudflare previously cached
// /service-worker.js as immutable for 1y after a bad nginx Cache-Control.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .getRegistrations()
      .then((regs) =>
        Promise.all(
          regs
            .filter((r) => (r.active || r.waiting || r.installing)?.scriptURL?.includes('service-worker.js'))
            .map((r) => r.unregister())
        )
      )
      .finally(() => {
        navigator.serviceWorker
          .register('/sw.js')
          .then((registration) => {
            console.log('Laro SW registered:', registration.scope, 'build 2026-09-20-2');
            // Pull a fresh SW on each load and activate it immediately so a new
            // deploy is never stuck behind an old cached app shell.
            // update() rejects on a network blip ("Script .../sw.js load failed");
            // the next page load retries, so this is not worth an error report.
            registration.update?.()?.catch?.(() => {});
          })
          .catch((error) => {
            console.log('Laro SW registration failed:', error);
          });
      });
  });
}

// No #root means this isn't the app page (the document was swapped mid-load,
// e.g. during the /register -> /#/register bounce or an offline fallback).
// Mounting would throw React error #299; the real page load mounts instead.
const rootEl = document.getElementById("root");
if (rootEl) {
  const root = ReactDOM.createRoot(rootEl);
  root.render(
    <React.StrictMode>
      <ErrorBoundary>
        <App />
      </ErrorBoundary>
    </React.StrictMode>,
  );
}
