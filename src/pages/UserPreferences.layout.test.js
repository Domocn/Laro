/**
 * @jest-environment node
 *
 * Settings → Cooking Preferences must not squeeze measurements into a
 * half-width column of wrapping chips (selected fill overlapped the labels).
 */
import fs from 'fs';
import path from 'path';

describe('settings cooking preferences layout', () => {
  const prefs = fs.readFileSync(path.join(__dirname, 'UserPreferences.jsx'), 'utf8');
  const picker = fs.readFileSync(
    path.join(__dirname, '../components/MeasurementUnitPicker.jsx'),
    'utf8'
  );

  it('stacks servings and measurements instead of a 2-column grid', () => {
    expect(prefs).toMatch(/layout="grid"/);
    expect(prefs).not.toMatch(/grid grid-cols-2 gap-4[\s\S]*measurementUnits/);
  });

  it('uses a 2x2 selected card, not a filled overlapping pill', () => {
    expect(picker).toMatch(/grid grid-cols-2/);
    expect(picker).toMatch(/border-laro bg-laro\/10 text-laro/);
    expect(picker).not.toMatch(/bg-laro text-white border-laro/);
    expect(picker).toMatch(/whitespace-nowrap/);
  });

  it('does not shrink labelled radio-style buttons to 24px', () => {
    const css = fs.readFileSync(path.join(__dirname, '../index.css'), 'utf8');
    expect(css).not.toMatch(/button\[role="radio"\][\s\S]{0,80}width:\s*24px/);
    expect(picker).not.toMatch(/role="radio"/);
  });
});
