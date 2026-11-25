/**
 * @jest-environment node
 *
 * Global touch-target CSS must not break labelled pickers or Radix switches.
 */
import fs from 'fs';
import path from 'path';

describe('buttons and switches layout guards', () => {
  const css = fs.readFileSync(path.join(__dirname, '../../index.css'), 'utf8');
  const switchSrc = fs.readFileSync(path.join(__dirname, 'switch.jsx'), 'utf8');
  const picker = fs.readFileSync(
    path.join(__dirname, '../MeasurementUnitPicker.jsx'),
    'utf8'
  );

  it('exempts role=switch from the global button min-height rule', () => {
    expect(css).toMatch(/button\[role="switch"\]/);
    expect(css).toMatch(/button\[role="switch"\][\s\S]*min-height:\s*unset/);
  });

  it('does not force labelled pickers to 24px radios', () => {
    expect(css).not.toMatch(/button\[role="radio"\]/);
    expect(picker).not.toMatch(/role="radio"/);
  });

  it('uses matched track and thumb travel on Switch', () => {
    expect(switchSrc).toMatch(/w-11/);
    expect(switchSrc).toMatch(/translate-x-5/);
  });
});
