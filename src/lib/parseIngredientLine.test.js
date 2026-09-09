import {
  ingredientsToText,
  isIngredientUnit,
  normalizeIngredient,
  parseIngredientLine,
  textToIngredients,
} from './parseIngredientLine';

describe('parseIngredientLine', () => {
  it('keeps single-word names intact (no amount)', () => {
    expect(parseIngredientLine('pepper')).toEqual({
      amount: '',
      unit: '',
      name: 'pepper',
    });
    expect(parseIngredientLine('dill')).toEqual({
      amount: '',
      unit: '',
      name: 'dill',
    });
    expect(parseIngredientLine('sriracha')).toEqual({
      amount: '',
      unit: '',
      name: 'sriracha',
    });
  });

  it('keeps multi-word names intact when there is no amount', () => {
    expect(parseIngredientLine('chinese five spice')).toEqual({
      amount: '',
      unit: '',
      name: 'chinese five spice',
    });
    expect(parseIngredientLine('spring onion')).toEqual({
      amount: '',
      unit: '',
      name: 'spring onion',
    });
    expect(parseIngredientLine('smoked paprika')).toEqual({
      amount: '',
      unit: '',
      name: 'smoked paprika',
    });
    expect(parseIngredientLine('onion granules')).toEqual({
      amount: '',
      unit: '',
      name: 'onion granules',
    });
  });

  it('parses amount + unit + name', () => {
    expect(parseIngredientLine('250 ml water')).toEqual({
      amount: '250',
      unit: 'ml',
      name: 'water',
    });
    expect(parseIngredientLine('100 g mushroom')).toEqual({
      amount: '100',
      unit: 'g',
      name: 'mushroom',
    });
    expect(parseIngredientLine('2 cups flour')).toEqual({
      amount: '2',
      unit: 'cups',
      name: 'flour',
    });
    expect(parseIngredientLine('1/2 tsp salt')).toEqual({
      amount: '1/2',
      unit: 'tsp',
      name: 'salt',
    });
  });

  it('parses glued units', () => {
    expect(parseIngredientLine('100g mushroom')).toEqual({
      amount: '100',
      unit: 'g',
      name: 'mushroom',
    });
    expect(parseIngredientLine('250Ml water')).toEqual({
      amount: '250',
      unit: 'Ml',
      name: 'water',
    });
  });

  it('keeps non-unit words with the name when amount is present', () => {
    expect(parseIngredientLine('1 spring onion')).toEqual({
      amount: '1',
      unit: '',
      name: 'spring onion',
    });
    expect(parseIngredientLine('4 eggs')).toEqual({
      amount: '4',
      unit: '',
      name: 'eggs',
    });
  });

  it('allows size words as units only with an amount', () => {
    expect(parseIngredientLine('1 large egg')).toEqual({
      amount: '1',
      unit: 'large',
      name: 'egg',
    });
    expect(parseIngredientLine('large eggs')).toEqual({
      amount: '',
      unit: '',
      name: 'large eggs',
    });
  });

  it('treats known measure words as units even without a number', () => {
    expect(parseIngredientLine('pinch salt')).toEqual({
      amount: '',
      unit: 'pinch',
      name: 'salt',
    });
    expect(parseIngredientLine('1 pinch salt')).toEqual({
      amount: '1',
      unit: 'pinch',
      name: 'salt',
    });
  });
});

describe('normalizeIngredient', () => {
  it('rejoins split single words from the old parser', () => {
    expect(normalizeIngredient({ amount: '', unit: 'peppe', name: 'r' })).toEqual({
      amount: '',
      unit: '',
      name: 'pepper',
    });
    expect(normalizeIngredient({ amount: '', unit: 'dil', name: 'l' })).toEqual({
      amount: '',
      unit: '',
      name: 'dill',
    });
  });

  it('rejoins stolen first words', () => {
    expect(
      normalizeIngredient({ amount: '', unit: 'chinese', name: 'five spice' })
    ).toEqual({
      amount: '',
      unit: '',
      name: 'chinese five spice',
    });
    expect(
      normalizeIngredient({ amount: '1', unit: 'spring', name: 'onion' })
    ).toEqual({
      amount: '1',
      unit: '',
      name: 'spring onion',
    });
  });

  it('leaves real units alone', () => {
    expect(
      normalizeIngredient({ amount: '100', unit: 'g', name: 'mushroom' })
    ).toEqual({
      amount: '100',
      unit: 'g',
      name: 'mushroom',
    });
  });
});

describe('textToIngredients round-trip', () => {
  it('does not corrupt the noodle-broth style list', () => {
    const text = [
      '250 ml water',
      'onion granules',
      'garlic granules',
      'smoked paprika',
      'chinese five spice',
      '100 g mushroom',
      '250 g white fish',
      'pepper',
      'dill',
      '1 spring onion',
      'cucumber',
      'kimchi',
      'sriracha',
    ].join('\n');

    expect(textToIngredients(text)).toEqual([
      { amount: '250', unit: 'ml', name: 'water' },
      { amount: '', unit: '', name: 'onion granules' },
      { amount: '', unit: '', name: 'garlic granules' },
      { amount: '', unit: '', name: 'smoked paprika' },
      { amount: '', unit: '', name: 'chinese five spice' },
      { amount: '100', unit: 'g', name: 'mushroom' },
      { amount: '250', unit: 'g', name: 'white fish' },
      { amount: '', unit: '', name: 'pepper' },
      { amount: '', unit: '', name: 'dill' },
      { amount: '1', unit: '', name: 'spring onion' },
      { amount: '', unit: '', name: 'cucumber' },
      { amount: '', unit: '', name: 'kimchi' },
      { amount: '', unit: '', name: 'sriracha' },
    ]);
  });

  it('round-trips structured ingredients through text', () => {
    const ings = [
      { amount: '', unit: '', name: 'pepper' },
      { amount: '100', unit: 'g', name: 'mushroom' },
    ];
    expect(textToIngredients(ingredientsToText(ings))).toEqual(ings);
  });
});

describe('isIngredientUnit', () => {
  it('recognizes common units case-insensitively', () => {
    expect(isIngredientUnit('Ml', { hasAmount: true })).toBe(true);
    expect(isIngredientUnit('TBSP', { hasAmount: true })).toBe(true);
    expect(isIngredientUnit('pepper', { hasAmount: false })).toBe(false);
  });
});
