/**
 * @jest-environment node
 */
import fs from 'fs';
import path from 'path';

describe('landing and auth brand layout', () => {
  const landing = fs.readFileSync(path.join(__dirname, 'Landing.jsx'), 'utf8');
  const lockup = fs.readFileSync(
    path.join(__dirname, '../components/BrandAcrostic.jsx'),
    'utf8'
  );
  const settings = fs.readFileSync(path.join(__dirname, 'Settings.jsx'), 'utf8');

  it('keeps hero copy on cream on phones instead of overlaying the pot', () => {
    expect(landing).toMatch(/sm:hidden/);
    expect(landing).toMatch(/bg-cream sm:min-h-\[100svh\]/);
    expect(landing).not.toMatch(/min-h-\[100svh\] flex items-start/);
  });

  it('does not use a 2x2 crossword lockup on login', () => {
    expect(lockup).toMatch(/brandAcrosticLine/);
    expect(lockup).not.toMatch(/grid grid-cols-2 sm:grid-cols-4/);
  });

  it('settings footer is a single acrostic line', () => {
    expect(settings).toMatch(/settings-brand-acrostic/);
    expect(settings).not.toMatch(/settings-brand-origin/);
  });

  it('does not call a home server “your box”', () => {
    const en = fs.readFileSync(path.join(__dirname, '../locales/en.js'), 'utf8');
    expect(en).not.toMatch(/your box/);
    expect(en).toMatch(
      /heroSubcopy: 'You add the recipes\. Laro helps you cook them, plan the week, and shop\.'/
    );
    expect(en).not.toMatch(/heroSubcopy:.*content feed/);
    expect(en).not.toMatch(/heroSubcopy:.*self-host/);
    expect(en).toMatch(/designedForWeeknights: 'Made for weeknights'/);
    expect(en).toMatch(
      /designedForWeeknightsBody: 'Less on the screen when you are tired/
    );
    expect(en).not.toMatch(/designedForWeeknightsBody:.*neurospicy/);
    expect(en).not.toMatch(/Designed for real weeknights/);
    expect(en).not.toMatch(/startFromFridgeBody:.*content feed/);
  });
});
