import {
  enrichStepWithAmounts,
  ingredientsForStep,
  nameVariants,
  normalizeCookStepsWithAmounts,
} from './cookModeSteps';

describe('nameVariants', () => {
  it('includes core noun for adjective-prefixed names', () => {
    const variants = nameVariants('White potatoes');
    expect(variants).toContain('white potatoes');
    expect(variants).toContain('potatoes');
    expect(variants).toContain('potato');
  });

  it('includes short form for compound proteins', () => {
    const variants = nameVariants('Chicken breast');
    expect(variants).toContain('chicken breast');
    expect(variants).toContain('chicken');
  });

  it('adds leaves variants when unit is leaves', () => {
    const variants = nameVariants('fresh sage', 'leaves');
    expect(variants).toContain('sage leaves');
  });
});

describe('enrichStepWithAmounts', () => {
  it('inserts quantity before ingredient names', () => {
    const step = 'Chop the potatoes into cubes and coat with oil.';
    const ingredients = [
      { name: 'potatoes', amount: '500', unit: 'g' },
      { name: 'oil', amount: '8', unit: 'g' },
    ];
    const enriched = enrichStepWithAmounts(step, ingredients);
    expect(enriched.toLowerCase()).toContain('500 g potatoes');
    expect(enriched.toLowerCase()).toContain('8 g oil');
  });

  it('matches adjective-prefixed list names to bare step nouns', () => {
    const step = 'Chop the potatoes into cubes, then sear the chicken.';
    const ingredients = [
      { name: 'White potatoes', amount: '500', unit: 'g' },
      { name: 'Chicken breast', amount: '400', unit: 'g' },
    ];
    const enriched = enrichStepWithAmounts(step, ingredients);
    expect(enriched.toLowerCase()).toContain('500 g potatoes');
    expect(enriched.toLowerCase()).toContain('400 g chicken');
  });

  it('matches singular/plural leaf forms', () => {
    const step = 'Fry sage leaves in butter until crisp.';
    const ingredients = [
      { name: 'fresh sage', amount: '8', unit: 'leaves' },
      { name: 'butter', amount: '20', unit: 'g' },
    ];
    const enriched = enrichStepWithAmounts(step, ingredients);
    expect(enriched.toLowerCase()).toContain('8 sage leaves');
    expect(enriched.toLowerCase()).toContain('20 g butter');
  });

  it('does not double amounts already in the step', () => {
    const step = 'Add 500 g potatoes to the bowl.';
    const ingredients = [{ name: 'potatoes', amount: '500', unit: 'g' }];
    const enriched = enrichStepWithAmounts(step, ingredients);
    expect((enriched.match(/500\s*g/gi) || []).length).toBe(1);
  });

  it('normalizes a full instruction list', () => {
    const steps = normalizeCookStepsWithAmounts(
      ['Boil the spaghetti until al dente.'],
      [{ name: 'spaghetti', amount: '400', unit: 'g' }]
    );
    expect(steps[0].toLowerCase()).toContain('400 g spaghetti');
  });
});

describe('ingredientsForStep', () => {
  it('returns ingredients mentioned in the step', () => {
    const step = 'Chop the potatoes and sear the chicken.';
    const ingredients = [
      { name: 'White potatoes', amount: '500', unit: 'g' },
      { name: 'Chicken breast', amount: '400', unit: 'g' },
      { name: 'olive oil', amount: '1', unit: 'tbsp' },
    ];
    const found = ingredientsForStep(step, ingredients);
    const names = found.map((f) => f.name.toLowerCase());
    expect(names).toEqual(expect.arrayContaining(['white potatoes', 'chicken breast']));
    expect(names).not.toContain('olive oil');
    expect(found.find((f) => /potato/i.test(f.name))?.qty).toMatch(/500/);
  });

  it('returns empty when nothing matches', () => {
    expect(ingredientsForStep('Preheat the oven.', [{ name: 'butter', amount: '20', unit: 'g' }])).toEqual(
      []
    );
  });
});
