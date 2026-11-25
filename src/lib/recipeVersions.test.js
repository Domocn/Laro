import { describe, it, expect, beforeEach } from 'vitest';
import {
  ORIGINAL_VERSION,
  MAX_VERSIONS,
  applyRecipeVersion,
  choiceFromSearch,
  findVersion,
  getPageNotes,
  getRecipeVersions,
  newVersionRow,
  planLabel,
  readVersionChoice,
  recipeLinkForPlan,
  rowsToVersions,
  scaleIngredients,
  validVersion,
  versionChoices,
  versionsToRows,
  withPageNotes,
  withVersions,
  writeVersionChoice,
} from './recipeVersions';
import { applyFodmapSwaps, getLowFodmap } from './fodmap';

const recipe = {
  id: 'r1',
  title: 'Pesto Pasta',
  servings: 2,
  ingredients: [{ name: 'pasta', amount: '200', unit: 'g' }, { name: 'chicken', amount: '2', unit: '' }],
  instructions: ['Boil pasta', 'Fry chicken'],
  adaptations: {
    low_fodmap: { swaps: [{ from: 'garlic', to: 'garlic-infused oil' }], notes: '' },
    versions: [
      { name: 'Pomegranate', ingredients: [{ name: 'pasta', amount: '1/2', unit: 'kg' }, { name: 'garlic', amount: '1', unit: '' }], instructions: ['Boil', 'Scatter'], notes: 'Best fresh' },
      { name: 'pomegranate', ingredients: [{ name: 'dupe' }], instructions: [] },
      { name: '', ingredients: [{ name: 'x' }] },
      { name: 'Empty', ingredients: [], instructions: [] },
      { name: 'Original', ingredients: [{ name: 'x' }] },
    ],
    page_notes: ['Soak 3 hours', '  ', 'Keeps 3 days'],
  },
};

describe('recipe versions', () => {
  it('lists usable versions, deduped, with Original first in the picker', () => {
    expect(getRecipeVersions(recipe).map((v) => v.name)).toEqual(['Pomegranate']);
    expect(versionChoices(recipe)).toEqual([ORIGINAL_VERSION, 'Pomegranate']);
    expect(versionChoices({ ingredients: [] })).toEqual([]);
    expect(versionChoices(null)).toEqual([]);
  });

  it('applies a version and falls back to Original for unknown names', () => {
    const shown = applyRecipeVersion(recipe, 'POMEGRANATE');
    expect(shown.ingredients[1].name).toBe('garlic');
    expect(shown.instructions).toEqual(['Boil', 'Scatter']);
    expect(shown.title).toBe('Pesto Pasta');
    expect(applyRecipeVersion(recipe, '')).toBe(recipe);
    expect(applyRecipeVersion(recipe, 'Gone')).toBe(recipe);
    expect(validVersion(recipe, ' pomegranate')).toBe('Pomegranate');
    expect(validVersion(recipe, 'Gone')).toBe('');
    expect(findVersion(recipe, 'Pomegranate').notes).toBe('Best fresh');
  });

  it('Low FODMAP swaps apply on top of whichever version is shown', () => {
    const swaps = getLowFodmap(recipe).swaps;
    const rows = applyFodmapSwaps(applyRecipeVersion(recipe, 'Pomegranate').ingredients, swaps);
    expect(rows[1].swap.to).toBe('garlic-infused oil');
    expect(rows[0].swap).toBeNull();
  });

  it('scales the displayed list like the server does', () => {
    const v = findVersion(recipe, 'Pomegranate').ingredients;
    expect(scaleIngredients(v, 2, 4).map((i) => i.amount)).toEqual(['1', '2']);
    expect(scaleIngredients([{ name: 'salt', amount: 'pinch' }], 2, 4)[0].amount).toBe('pinch');
    expect(scaleIngredients([{ name: 'egg', amount: '1 1/2' }], 2, 3)[0].amount).toBe('2.25');
    expect(scaleIngredients(v, 2, 2)).toBe(v);
    expect(scaleIngredients(v, 2, null)).toBe(v);
  });
});

describe('remembered choice', () => {
  beforeEach(() => localStorage.clear());

  it('stores version + Low FODMAP per recipe', () => {
    expect(readVersionChoice('r1')).toBeNull();
    writeVersionChoice('r1', { version: 'Pomegranate', lowFodmap: true });
    expect(localStorage.getItem('laro_recipe_version:r1')).toBeTruthy();
    expect(readVersionChoice('r1')).toEqual({ version: 'Pomegranate', lowFodmap: true });
    writeVersionChoice('r1', { version: '', lowFodmap: false });
    expect(readVersionChoice('r1')).toBeNull();
    localStorage.setItem('laro_recipe_version:r2', 'Chocolate Orange'); // plain name
    expect(readVersionChoice('r2')).toEqual({ version: 'Chocolate Orange', lowFodmap: false });
  });
});

describe('meal plan helpers', () => {
  it('labels and links planned versions', () => {
    const plan = { recipe_id: 'r1', recipe_version: 'Pomegranate', low_fodmap: true };
    expect(planLabel('Pesto Pasta', plan)).toBe('Pesto Pasta · Pomegranate · Low FODMAP');
    expect(planLabel('Pesto Pasta', { recipe_id: 'r1' })).toBe('Pesto Pasta');
    expect(recipeLinkForPlan(plan)).toBe('/recipes/r1?version=Pomegranate&lowFodmap=1');
    expect(recipeLinkForPlan({ recipe_id: 'r1' })).toBe('/recipes/r1');
    expect(choiceFromSearch('?version=Pomegranate&lowFodmap=1')).toEqual({ version: 'Pomegranate', lowFodmap: true });
    expect(choiceFromSearch('?lowFodmap=1')).toEqual({ version: '', lowFodmap: true });
    expect(choiceFromSearch('')).toBeNull();
  });
});

describe('edit form', () => {
  const parse = (line) => {
    const [amount, ...rest] = line.split(' ');
    return /\d/.test(amount) ? { amount, unit: '', name: rest.join(' ') } : { amount: '', unit: '', name: line };
  };

  it('round-trips rows and drops empty / repeated / unnamed versions', () => {
    const rows = versionsToRows(recipe);
    expect(rows[0]).toEqual({
      name: 'Pomegranate',
      ingredientsText: '1/2 kg pasta\n1 garlic',
      instructionsText: 'Boil\nScatter',
      notes: 'Best fresh',
    });
    const versions = rowsToVersions(
      [...rows, { name: 'pomegranate', ingredientsText: 'x' }, { name: '', ingredientsText: 'y' }, { name: 'Blank', ingredientsText: ' ' }],
      parse,
    );
    expect(versions).toHaveLength(1);
    expect(versions[0].instructions).toEqual(['Boil', 'Scatter']);
    expect(versions[0].ingredients[1]).toEqual({ amount: '1', unit: '', name: 'garlic' });
    const many = Array.from({ length: 15 }, (_, i) => ({ name: `V${i}`, instructionsText: 'Cook' }));
    expect(rowsToVersions(many)).toHaveLength(MAX_VERSIONS);
  });

  it('new version starts from the current ingredients and steps', () => {
    const row = newVersionRow('Spicy', recipe.ingredients, recipe.instructions);
    expect(row.ingredientsText).toBe('200 g pasta\n2 chicken');
    expect(row.instructionsText).toBe('Boil pasta\nFry chicken');
  });

  it('saving versions / notes keeps Low FODMAP', () => {
    const next = withVersions(recipe.adaptations, [{ name: 'Spicy', ingredients: [], instructions: ['Cook'] }]);
    expect(next.low_fodmap).toEqual(recipe.adaptations.low_fodmap);
    expect(next.versions.map((v) => v.name)).toEqual(['Spicy']);
    expect(withVersions({ versions: [{}] }, [])).toBeNull();
    expect(withPageNotes(next, 'A\n\nB\nA').page_notes).toEqual(['A', 'B']);
    expect(withPageNotes({ page_notes: ['x'] }, '  ')).toBeNull();
  });

  it('reads page notes', () => {
    expect(getPageNotes(recipe)).toEqual(['Soak 3 hours', 'Keeps 3 days']);
    expect(getPageNotes({})).toEqual([]);
  });
});
