/**
 * @jest-environment node
 *
 * Share must stay visible in light theme. The control lives on the cover photo
 * with white-on-dark styles, not inside Settings → Appearance / Dark Mode.
 */
import fs from 'fs';
import path from 'path';

describe('recipe share visibility', () => {
  const src = fs.readFileSync(path.join(__dirname, 'RecipeDetail.jsx'), 'utf8');

  it('puts a labeled Share control on the hero photo', () => {
    expect(src).toMatch(/data-testid="share-recipe"/);
    expect(src).toMatch(/bg-black\/55/);
    expect(src).toMatch(/text-white/);
    expect(src).toMatch(/setShowShareDialog\(true\)/);
  });

  it('keeps Share in the header and actions rows as well', () => {
    expect(src).toMatch(/data-testid="share-recipe-header"/);
    expect(src).toMatch(/data-testid="share-recipe-actions"/);
  });
});
