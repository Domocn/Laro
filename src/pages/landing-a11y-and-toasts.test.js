/**
 * @vitest-environment node
 *
 * Guards the dark-mode toast fix and the landing page landmark.
 *
 * The toaster used to hardcode `background: '#FFFFFF'` inline, so in dark mode
 * the inherited light text landed on a white toast and the message was
 * unreadable. It must stay theme-driven.
 */
import fs from 'fs';
import path from 'path';

const read = (p) => fs.readFileSync(path.join(__dirname, p), 'utf8');

describe('toast theming', () => {
  const app = read('../App.jsx');
  const css = read('../index.css');

  it('does not hardcode a light toast background', () => {
    expect(app).not.toMatch(/#FFFFFF/);
    expect(app).not.toMatch(/background:\s*['"]#fff/i);
  });

  it('drives the toaster from the real theme', () => {
    expect(app).toMatch(/useTheme/);
    expect(app).toMatch(/theme=\{isDark \? 'dark' : 'light'\}/);
  });

  it('styles toasts from theme tokens so both modes are legible', () => {
    const rule = css.match(/\.laro-toast\s*\{[^}]*\}/);
    expect(rule).toBeTruthy();
    expect(rule[0]).toMatch(/background:\s*hsl\(var\(--popover\)\)/);
    expect(rule[0]).toMatch(/color:\s*hsl\(var\(--popover-foreground\)\)/);
  });
});

describe('landing page landmark and contrast', () => {
  const landing = read('Landing.jsx');
  const css = read('../index.css');

  it('provides the #main-content target the global skip link points at', () => {
    // SkipToContent links to #main-content, which Layout gives signed-in
    // pages. The landing page is outside Layout, so it needs its own <main>.
    expect(landing).toMatch(/<main id="main-content"/);
    expect(landing).toMatch(/tabIndex=\{-1\}/);
  });

  it('keeps the header and footer outside main', () => {
    const mainAt = landing.indexOf('<main id="main-content"');
    const headerAt = landing.indexOf('<header');
    const footerAt = landing.indexOf('<footer');
    expect(headerAt).toBeGreaterThanOrEqual(0);
    expect(mainAt).toBeGreaterThan(headerAt);
    expect(footerAt).toBeGreaterThan(mainAt);
  });

  it('does not use black-on-dark borders that vanish in dark mode', () => {
    expect(landing).not.toMatch(/border-black\//);
    expect(landing).not.toMatch(/border-\[#/);
  });

  it('lifts the fixed brand hexes for dark mode', () => {
    // #006241 / #00754A sit around 1.9:1 on the dark canvas.
    expect(css).toMatch(/\.dark \.text-laro-brand/);
    expect(css).toMatch(/\.dark \.text-teal/);
    expect(css).toMatch(/\.dark \.text-coral/);
  });
});

describe('every public page has a main landmark', () => {
  // These pages sit outside Layout, so they must supply their own target.
  const pages = ['ServerConfig', 'ForgotPassword', 'VerifyEmail'];

  it.each(pages)('%s exposes #main-content', (page) => {
    const src = fs.readFileSync(path.join(__dirname, `${page}.jsx`), 'utf8');
    expect(src).toMatch(/<main id="main-content"/);
    expect(src).toMatch(/<main[^>]*tabIndex=\{-1\}/);
  });
});

describe('Auth page landmarks', () => {
  const auth = read('Auth.jsx');

  // Slice a component out of the file by its declaration and the next one.
  const slice = (from, to) => auth.slice(auth.indexOf(from), auth.indexOf(to));

  it('wraps Login and Register in a main landmark', () => {
    expect(auth.match(/<main id="main-content"/g)).toHaveLength(2);

    const login = slice('export const Login', 'export const Register');
    expect(login).toMatch(/<main id="main-content"/);
    expect(login).toMatch(/<main[^>]*tabIndex=\{-1\}/);
    expect(login).toMatch(/<\/main>/);

    // Register is the last export in the file.
    const register = auth.slice(auth.indexOf('export const Register'));
    expect(register).toMatch(/<main id="main-content"/);
    expect(register).toMatch(/<\/main>/);
  });

  it('does not give EmailVerification its own main (it renders inside the page)', () => {
    const verification = slice('const EmailVerification', 'const OAuthButtons');
    expect(verification).not.toMatch(/<main/);
    // It should still be a plain div root.
    expect(verification).toMatch(/return \(\s*<div className="min-h-screen/);
  });

  it('keeps the original centering classes so layout is unchanged', () => {
    expect(auth).toMatch(
      /<main id="main-content" tabIndex=\{-1\} className="min-h-screen bg-cream flex items-center justify-center p-4 relative overflow-hidden"/
    );
  });
});
