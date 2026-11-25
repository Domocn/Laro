import { convertUnit, formatIngredientLine } from './unitConversions';

describe('convertUnit', () => {
  it('leaves spoons as written when preference is as_written', () => {
    expect(convertUnit(1, 'tsp', 'as_written')).toEqual({ amount: 1, unit: 'tsp' });
    expect(convertUnit(2, 'tbsp', 'as_written')).toEqual({ amount: 2, unit: 'tbsp' });
  });

  it('converts spoons to millilitres for metric using kitchen figures', () => {
    expect(convertUnit(1, 'tsp', 'metric')).toEqual({ amount: 5, unit: 'ml' });
    expect(convertUnit(2, 'tbsp', 'metric')).toEqual({ amount: 30, unit: 'ml' });
  });

  it('converts a cup of liquid to millilitres for metric', () => {
    expect(convertUnit(1, 'cup', 'metric', 'water')).toEqual({ amount: 250, unit: 'ml' });
    expect(convertUnit(2, 'cups', 'metric', 'milk')).toEqual({ amount: 500, unit: 'ml' });
  });

  it('converts a cup of a dry or solid ingredient to grams, not millilitres', () => {
    // A cup of flour is a weight. Metric cooks should never be told to use
    // 250 ml of flour, so ingredient density wins over the volume figure.
    const flour = convertUnit(1, 'cup', 'metric', 'plain flour');
    expect(flour.unit).toBe('g');
    expect(flour.amount).toBe(125);
  });

  it('estimates grams for a cup of an unrecognised non-liquid', () => {
    const unknown = convertUnit(1, 'cup', 'metric', 'something unfamiliar');
    expect(unknown.unit).toBe('g');
  });

  it('converts ounces to grams for metric', () => {
    expect(convertUnit(1, 'oz', 'metric').unit).toBe('g');
  });

  it('converts 15 ml to 1 tbsp on imperial', () => {
    expect(convertUnit(15, 'ml', 'imperial')).toEqual({ amount: 1, unit: 'tbsp' });
  });

  it('does not turn 100 ml into tablespoons on imperial', () => {
    const c = convertUnit(100, 'ml', 'imperial');
    expect(String(c.unit).toLowerCase()).not.toMatch(/tbsp|tablespoon|tsp/);
  });
});

describe('formatIngredientLine', () => {
  it('shows cocoa powder as grams when metric is chosen', () => {
    // 2 tbsp of cocoa is ~10 g, not 30 ml of powder.
    const line = formatIngredientLine(
      { amount: 2, unit: 'tbsp', name: 'cocoa powder' },
      'metric'
    );
    expect(line).toMatch(/10\.2 g cocoa powder/);
  });

  it('keeps cocoa powder as tablespoons when as written', () => {
    const line = formatIngredientLine(
      { amount: 2, unit: 'tbsp', name: 'cocoa powder' },
      'as_written'
    );
    expect(line).toMatch(/tbsp/i);
    expect(line).not.toMatch(/ml/);
  });
});

describe('density keywords match the food, not its notes', () => {
  it('keeps nutritional yeast as a spoon measure (not grams of "nut"/"basil")', () => {
    expect(convertUnit('1', 'tbsp', 'as_written', 'nutritional yeast (for the basil pesto)')).toEqual({ amount: '1', unit: 'tbsp' });
    const metric = convertUnit('1', 'tbsp', 'metric', 'nutritional yeast, plus extra basil to serve');
    expect(metric).toEqual({ amount: 15, unit: 'ml' });
    expect(formatIngredientLine({ amount: '1', unit: 'tbsp', name: 'nutritional yeast' }, 'as_written')).toBe('1 tbsp nutritional yeast');
  });

  it('still converts real dry goods and plurals', () => {
    expect(convertUnit(1, 'cup', 'metric', 'rolled oats').amount).toBe(90);
    expect(convertUnit(1, 'cup', 'metric', 'chopped walnuts').unit).toBe('g');
    expect(convertUnit(1, 'cup', 'metric', 'strawberries').amount).toBe(150);
  });
});
