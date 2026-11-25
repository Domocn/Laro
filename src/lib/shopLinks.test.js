import { shopSearchTerm, shopUrl, SHOP_STORES } from './shopLinks';

describe('shopLinks', () => {
  it('trims notes from the item name', () => {
    expect(shopSearchTerm('chopped tomatoes, drained')).toBe('chopped tomatoes');
    expect(shopSearchTerm('onion (finely chopped)')).toBe('onion');
  });

  it('builds store search urls', () => {
    expect(shopUrl('tesco', 'chopped tomatoes')).toBe('https://www.tesco.com/shop/en-GB/search?query=chopped+tomatoes');
    expect(shopUrl('asda', 'chopped tomatoes')).toBe('https://www.asda.com/groceries/search/chopped%20tomatoes');
    SHOP_STORES.forEach((s) => expect(shopUrl(s.id, 'feta')).toMatch(/^https:\/\//));
  });

  it('adds the Amazon tag only when valid', () => {
    expect(shopUrl('amazon', 'feta', 'laro-21')).toMatch(/&tag=laro-21$/);
    expect(shopUrl('amazon', 'feta')).not.toMatch(/tag=/);
    expect(shopUrl('amazon', 'feta', 'bad tag&x=1')).not.toMatch(/tag=/);
  });
});
