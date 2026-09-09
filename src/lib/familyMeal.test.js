import {
  wantsFamilyOneMeal,
  parseAdultBoost,
  stripAdultBoostPrefix,
  isFamilyFriendlyRecipe,
} from './familyMeal';

describe('wantsFamilyOneMeal', () => {
  it('defaults true when hasChildren', () => {
    expect(wantsFamilyOneMeal({ hasChildren: true })).toBe(true);
    expect(wantsFamilyOneMeal({ hasChildren: false })).toBe(false);
    expect(wantsFamilyOneMeal({})).toBe(false);
  });

  it('respects explicit toggle', () => {
    expect(wantsFamilyOneMeal({ hasChildren: true, familyOneMeal: false })).toBe(
      false
    );
    expect(wantsFamilyOneMeal({ hasChildren: false, familyOneMeal: true })).toBe(
      true
    );
  });
});

describe('parseAdultBoost', () => {
  it('reads adult_boost field', () => {
    expect(parseAdultBoost({ adult_boost: 'Add chili flakes' })).toBe(
      'Add chili flakes'
    );
    expect(
      parseAdultBoost({ adult_boost: 'For adults: Extra cheese' })
    ).toBe('Extra cheese');
  });

  it('falls back to notes prefix', () => {
    expect(
      parseAdultBoost({ notes: 'For adults: Serve with hot sauce' })
    ).toBe('Serve with hot sauce');
    expect(parseAdultBoost({ notes: 'Leftovers tomorrow' })).toBe('');
  });
});

describe('stripAdultBoostPrefix / isFamilyFriendlyRecipe', () => {
  it('strips prefix variants', () => {
    expect(stripAdultBoostPrefix('For adults — chili oil')).toBe('chili oil');
  });

  it('detects family-friendly tag', () => {
    expect(isFamilyFriendlyRecipe({ tags: ['family-friendly', 'pasta'] })).toBe(
      true
    );
    expect(isFamilyFriendlyRecipe({ tags: ['spicy'] })).toBe(false);
  });
});
