import { formatShoppingListForShare } from './shareShoppingList';

describe('formatShoppingListForShare', () => {
  it('groups by aisle and skips checked items', () => {
    const text = formatShoppingListForShare({
      name: 'Week shop',
      items: [
        { name: 'Milk', category: 'Dairy', checked: false },
        { name: 'Eggs', category: 'Dairy', checked: true },
        { name: 'Rice', category: 'Pantry', checked: false },
      ],
    });
    expect(text).toContain('Week shop');
    expect(text).toContain('Milk');
    expect(text).not.toContain('Eggs');
    expect(text).toContain('Rice');
  });
});
