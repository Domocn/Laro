/**
 * @jest-environment node
 */
import { getImageUrl, getUnsplashFoodImage } from './utils';

const SALMON = 'photo-1467003909585';
const MEATBALLS = 'photo-1529042410759';
const PIZZA = 'photo-1565299624946';
const BANANA_BREAD = 'photo-1632931057819';
const OATS = 'photo-1517673400267';
const FRUIT = 'photo-1490474418585';
const NUT_BAR = 'photo-1705868432559';

describe('recipe cover matching', () => {
  it('shows meatballs not salmon for beef meat balls', () => {
    const url = getImageUrl('', { title: 'Beef meat balls', category: 'Dinner' });
    expect(url).toContain(MEATBALLS);
    expect(url).not.toContain(SALMON);
  });

  it('shows pizza not strawberries for 2 ingredient pizza', () => {
    const stored = 'https://upload.wikimedia.org/wikipedia/commons/s/strawberry.jpg';
    const url = getImageUrl(stored, { title: '2 Ingredient Pizza' });
    expect(url).toContain(PIZZA);
  });

  it('shows banana bread not fruit or oats', () => {
    const url = getImageUrl('', {
      title: '4 Ingredient Healthy Banana Bread',
      category: 'Breakfast',
      ingredients: [{ name: 'oats' }, { name: 'banana' }],
    });
    expect(url).toContain(BANANA_BREAD);
    expect(url).not.toContain(OATS);
    expect(url).not.toContain(FRUIT);
  });

  it('shows a nut bar photo for pear and nut bar', () => {
    const url = getImageUrl('', { title: 'Pear and nut bar', category: 'Snack' });
    expect(url).toContain(NUT_BAR);
  });

  it('keeps a user upload even when the title is pizza', () => {
    const url = getImageUrl('/uploads/my-pizza.jpg', { title: 'Pizza' });
    expect(url).toContain('/uploads/my-pizza.jpg');
  });

  it('still maps Weetabix to the cereal photo', () => {
    const url = getUnsplashFoodImage('Original Protein Overnight Weetabix', 'Breakfast', 800, 'Original Protein Overnight Weetabix');
    expect(url).toContain('photo-1664802460246');
  });

  it('picks the dish photo before its main ingredient', () => {
    const img = (title) => getImageUrl('', { title, category: 'Dinner' });
    expect(img('Mango Smoothie')).toContain('photo-1623065422902');
    expect(img('Berry Smoothie')).toContain('photo-1579954115545');
    expect(img('Chicken Stir Fry')).toContain('photo-1767974877206');
    expect(img('Greek Salad')).toContain('photo-1606735584785');
    expect(img('Thai Green Curry')).toContain('photo-1761315412830');
    expect(img('Classic Guacamole')).toContain('photo-1680992071073');
  });
});
