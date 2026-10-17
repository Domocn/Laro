import { orderedRetailerEntries, retailerLabel } from './ukRetailers';

describe('ukRetailers', () => {
  it('orders known retailers before unknown keys', () => {
    const ordered = orderedRetailerEntries({
      zzz: 'https://example.com',
      tesco: 'https://tesco.com',
      asda: 'https://asda.com',
    });
    expect(ordered[0][0]).toBe('tesco');
    expect(ordered[1][0]).toBe('asda');
  });

  it('labels retailers for display', () => {
    expect(retailerLabel('sainsburys')).toBe("Sainsbury's");
    expect(retailerLabel('marksandspencer')).toBe('M&S Food');
  });
});
