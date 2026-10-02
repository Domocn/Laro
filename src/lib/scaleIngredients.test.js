import { parseAmountToNumber, scaleIngredients, formatScaledAmount } from './scaleIngredients';

describe('parseAmountToNumber', () => {
  it('parses integers, decimals, and fractions', () => {
    expect(parseAmountToNumber('2')).toBe(2);
    expect(parseAmountToNumber('1.5')).toBe(1.5);
    expect(parseAmountToNumber('1/2')).toBe(0.5);
    expect(parseAmountToNumber('1 1/2')).toBe(1.5);
    expect(parseAmountToNumber('½')).toBe(0.5);
  });

  it('returns null for empty or non-numeric amounts', () => {
    expect(parseAmountToNumber('')).toBe(null);
    expect(parseAmountToNumber('  ')).toBe(null);
    expect(parseAmountToNumber('to taste')).toBe(null);
  });
});

describe('scaleIngredients', () => {
  const base = [
    { name: 'flour', amount: '2', unit: 'cup' },
    { name: 'salt', amount: '1/2', unit: 'tsp' },
    { name: 'pepper', amount: '', unit: '' },
  ];

  it('doubles amounts when servings double', () => {
    const scaled = scaleIngredients(base, 4, 8);
    expect(scaled[0].amount).toBe('4');
    expect(scaled[1].amount).toBe('1');
    expect(scaled[2].amount).toBe('');
  });

  it('returns copies when servings unchanged', () => {
    const scaled = scaleIngredients(base, 4, 4);
    expect(scaled[0].amount).toBe('2');
    expect(scaled).not.toBe(base);
  });
});

describe('formatScaledAmount', () => {
  it('strips trailing zeros', () => {
    expect(formatScaledAmount(1.5)).toBe('1.5');
    expect(formatScaledAmount(2)).toBe('2');
  });
});
