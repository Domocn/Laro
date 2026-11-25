import { describe, it, expect } from 'vitest';
import {
  addEditorSection,
  fromEditorSections,
  groupedRows,
  groupHeading,
  ingredientParts,
  ingredientsAsText,
  moveEditorSection,
  parseSectionedLines,
  removeEditorSection,
  renameEditorSection,
  sectionedLines,
  splitIngredientGroup,
  toEditorSections,
  withIngredientGroup,
} from './ingredientGroups';
import { foodEmoji } from './foodEmoji';
import { ingredientsToText, textToIngredients } from './parseIngredientLine';
import { rowsToVersions, versionsToRows } from './recipeVersions';
import { enrichStepWithAmounts } from './cookModeSteps';

describe('splitIngredientGroup', () => {
  it('splits a sub-recipe prefix', () => {
    expect(splitIngredientGroup('Basil Pesto: almonds or cashews')).toEqual({ group: 'Basil Pesto', name: 'almonds or cashews' });
  });
  it('leaves plain lines alone', () => {
    expect(splitIngredientGroup('gluten-free pasta')).toEqual({ group: null, name: 'gluten-free pasta' });
  });
  it('ignores times and ratios', () => {
    expect(splitIngredientGroup('ratio 1:2 rice')).toEqual({ group: null, name: 'ratio 1:2 rice' });
  });
  it('builds a readable heading', () => {
    expect(groupHeading('Basil Pesto')).toBe('For the basil pesto');
    expect(groupHeading('For the sauce')).toBe('For the sauce');
  });
  it('translates the heading when given t', () => {
    const t = (key, p = {}) => (key === 'ingredientGroupHeading' ? `Für: ${p.Group}` : key);
    expect(groupHeading('Soße', t)).toBe('Für: Soße');
    expect(groupHeading('Sauce', (k) => k)).toBe('For the sauce'); // missing key falls back
  });
});

describe('ingredientParts / detail grouping', () => {
  it('prefers the group field and falls back to a legacy prefix', () => {
    expect(ingredientParts({ name: 'tahini', group: 'Sauce' })).toEqual({ group: 'Sauce', name: 'tahini' });
    expect(ingredientParts({ name: 'Sauce: tahini' })).toEqual({ group: 'Sauce', name: 'tahini' });
    expect(ingredientParts({ name: 'Sauce: tahini', group: 'sauce' })).toEqual({ group: 'sauce', name: 'tahini' });
    expect(ingredientParts('Dressing: lemon')).toEqual({ group: 'Dressing', name: 'lemon' });
    expect(ingredientParts({ name: 'flour', group: '' })).toEqual({ group: null, name: 'flour' });
  });

  it('groups rows: ungrouped first, sections in first-seen order, original indices kept', () => {
    const rows = groupedRows([
      { name: 'almonds', amount: '75', unit: 'g', group: 'Basil Pesto' },
      { name: 'pasta', amount: '200', unit: 'g' },
      { name: 'Basil Pesto: basil' }, // legacy prefix joins the same section
      { name: 'feta', group: 'Topping' },
      { name: 'salt' },
    ]);
    expect(rows.map((r) => [r.index, r.group, r.name, r.groupStart])).toEqual([
      [1, null, 'pasta', false],
      [4, null, 'salt', false],
      [0, 'Basil Pesto', 'almonds', true],
      [2, 'Basil Pesto', 'basil', false],
      [3, 'Topping', 'feta', true],
    ]);
  });

  it('withIngredientGroup cleans legacy names', () => {
    expect(withIngredientGroup({ name: 'Sauce: tahini', amount: '2' })).toEqual({ name: 'tahini', amount: '2', group: 'Sauce' });
    expect(withIngredientGroup({ name: 'flour', group: '' })).toEqual({ name: 'flour' });
  });

  it('copies as text with headings', () => {
    expect(ingredientsAsText([
      { name: 'almonds', amount: '75', unit: 'g', group: 'Pesto' },
      { name: 'pasta', amount: '200', unit: 'g' },
    ])).toBe('• 200 g pasta\n\nFor the pesto:\n• 75 g almonds');
  });
});

describe('recipe editor sections', () => {
  let n = 0;
  const id = () => `s${(n += 1)}`;
  const empty = { name: '', amount: '', unit: '', sectionId: null };

  it('loads groups into sections and saves them back (ungrouped first)', () => {
    n = 0;
    const state = toEditorSections([
      { name: 'tahini', amount: '2', unit: 'tbsp', group: 'Sauce' },
      { name: 'pasta', amount: '200', unit: 'g' },
      { name: 'Sauce: lemon', amount: '1', unit: '' },
    ], id);
    expect(state.sections).toEqual([{ id: 's1', name: 'Sauce' }]);
    expect(state.rows.map((r) => [r.name, r.sectionId])).toEqual([['tahini', 's1'], ['pasta', null], ['lemon', 's1']]);
    expect(fromEditorSections(state)).toEqual([
      { name: 'pasta', amount: '200', unit: 'g' },
      { name: 'tahini', amount: '2', unit: 'tbsp', group: 'Sauce' },
      { name: 'lemon', amount: '1', unit: '', group: 'Sauce' },
    ]);
  });

  it('adds a section with an empty row, renames it and saves ingredients under it', () => {
    n = 0;
    let state = toEditorSections([{ name: 'pasta', amount: '200', unit: 'g' }], id);
    state = addEditorSection(state, empty, id);
    expect(state.sections).toEqual([{ id: 's1', name: '' }]);
    expect(state.rows[1]).toEqual({ ...empty, sectionId: 's1' });
    state = renameEditorSection(state, 's1', 'Topping');
    state = { ...state, rows: state.rows.map((r, i) => (i === 1 ? { ...r, name: 'feta' } : r)) };
    expect(fromEditorSections(state)).toEqual([
      { name: 'pasta', amount: '200', unit: 'g' },
      { name: 'feta', amount: '', unit: '', group: 'Topping' },
    ]);
  });

  it('an unnamed section saves its lines ungrouped', () => {
    n = 0;
    let state = addEditorSection({ rows: [], sections: [] }, empty, id);
    state = { ...state, rows: [{ ...state.rows[0], name: 'salt' }] };
    expect(fromEditorSections(state)).toEqual([{ name: 'salt', amount: '', unit: '' }]);
  });

  it('removing a section moves its ingredients to the end of the main list', () => {
    n = 0;
    let state = toEditorSections([
      { name: 'tahini', group: 'Sauce' },
      { name: 'pasta' },
      { name: 'feta', group: 'Topping' },
    ], id);
    state = removeEditorSection(state, 's1');
    expect(state.sections).toEqual([{ id: 's2', name: 'Topping' }]);
    expect(state.rows.map((r) => [r.name, r.sectionId])).toEqual([['pasta', null], ['feta', 's2'], ['tahini', null]]);
    expect(fromEditorSections(state).map((i) => [i.name, i.group])).toEqual([
      ['pasta', undefined], ['tahini', undefined], ['feta', 'Topping'],
    ]);
  });

  it('moves sections up and down, ignoring moves past the ends', () => {
    n = 0;
    let state = toEditorSections([{ name: 'a', group: 'One' }, { name: 'b', group: 'Two' }], id);
    expect(moveEditorSection(state, 's1', -1)).toBe(state);
    state = moveEditorSection(state, 's2', -1);
    expect(state.sections.map((s) => s.name)).toEqual(['Two', 'One']);
    expect(fromEditorSections(state).map((i) => i.group)).toEqual(['Two', 'One']);
  });
});

describe('one-per-line text with sections', () => {
  it('writes heading lines and parses them back', () => {
    const ings = [
      { amount: '200', unit: 'g', name: 'pasta' },
      { amount: '2', unit: 'tbsp', name: 'tahini', group: 'Sauce' },
    ];
    const text = ingredientsToText(ings);
    expect(text).toBe('200 g pasta\nSauce:\n2 tbsp tahini');
    expect(textToIngredients(text)).toEqual(ings);
  });

  it('reads the older single-line "Sauce: 2 tbsp tahini" form', () => {
    expect(parseSectionedLines(['Sauce: 2 tbsp tahini'], (l) => ({ amount: '', unit: '', name: l }))).toEqual([
      { amount: '', unit: '', name: '2 tbsp tahini', group: 'Sauce' },
    ]);
  });

  it('round-trips version ingredients through the edit form', () => {
    const recipe = { adaptations: { versions: [{ name: 'Vegan', ingredients: [
      { amount: '1', unit: '', name: 'lemon' },
      { amount: '75', unit: 'g', name: 'cashews', group: 'Pesto' },
    ], instructions: ['Blend.'] }] } };
    const rows = versionsToRows(recipe);
    expect(rows[0].ingredientsText).toBe('1 lemon\nPesto:\n75 g cashews');
    const parse = (line) => {
      const m = /^(\d+)\s+(g\s+)?(.*)$/.exec(line);
      return { amount: m[1], unit: (m[2] || '').trim(), name: m[3] };
    };
    expect(rowsToVersions(rows, parse)[0].ingredients).toEqual(recipe.adaptations.versions[0].ingredients);
  });

  it('sectionedLines skips blank lines', () => {
    expect(sectionedLines([{ name: '' }, { name: 'salt', group: 'Dough' }], (i) => i.name)).toEqual(['Dough:', 'salt']);
  });
});

describe('cook mode', () => {
  it('never injects an amount into a section name taken from group', () => {
    const ings = [
      { amount: '30', unit: 'g', name: 'basil', group: 'Basil Pesto' },
      { amount: '200', unit: 'g', name: 'pasta' },
    ];
    const out = enrichStepWithAmounts('Blitz all the Basil Pesto ingredients, then cook the pasta.', ings);
    expect(out).toContain('Blitz all the Basil Pesto ingredients');
    expect(out).toContain('200 g pasta');
  });
});

describe('shopping uses the clean name', () => {
  it('a grouped line shops as the food itself', () => {
    // The server builds shopping lists (shopping_name in routers/shopping_lists.py); the web
    // only ever shows and sends the clean name.
    expect(ingredientParts({ name: 'Basil Pesto: almonds or cashews' }).name).toBe('almonds or cashews');
    expect(ingredientParts({ name: 'almonds or cashews', group: 'Basil Pesto' }).name).toBe('almonds or cashews');
  });
});

describe('foodEmoji nuts', () => {
  it('uses the chestnut for tree nuts and the peanut for peanuts', () => {
    expect(foodEmoji('almonds or cashews')).toBe('🌰');
    expect(foodEmoji('pine nuts')).toBe('🌰');
    expect(foodEmoji('roasted peanuts')).toBe('🥜');
    expect(foodEmoji('peanut butter')).toBe('🥜');
  });
  it('does not treat nutmeg or nutritional yeast as nuts', () => {
    expect(foodEmoji('nutritional yeast')).not.toBe('🌰');
    expect(foodEmoji('ground nutmeg')).not.toBe('🌰');
    expect(foodEmoji('butternut squash')).not.toBe('🌰');
  });
});
