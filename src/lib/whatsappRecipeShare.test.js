import { buildWhatsAppRecipeShareText, LARO_SHARE_TAGLINE } from './whatsappRecipeShare';

describe('buildWhatsAppRecipeShareText', () => {
  const recipe = {
    title: 'Tomato Soup',
    description: 'A cozy bowl for weeknights.',
    prep_time: 10,
    cook_time: '25 min',
    servings: 4,
    ingredients: [{ name: 'tomato' }],
    instructions: ['Simmer'],
  };

  it('puts the share link first and omits full ingredients/instructions', () => {
    const text = buildWhatsAppRecipeShareText(recipe, {
      shareUrl: 'https://laro.food/recipe/Ab12Cd',
      includeLink: true,
    });
    expect(text.startsWith('https://laro.food/recipe/Ab12Cd')).toBe(true);
    expect(text).toContain('*Tomato Soup*');
    expect(text).toContain('Prep 10 min');
    expect(text).toContain('Serves 4');
    expect(text).toContain(LARO_SHARE_TAGLINE);
    expect(text).not.toContain('Ingredients:');
    expect(text).not.toContain('Simmer');
  });

  it('builds a card without URL when links disabled', () => {
    const text = buildWhatsAppRecipeShareText(recipe, { includeLink: false });
    expect(text).not.toContain('https://laro.food/recipe');
    expect(text).toContain('*Tomato Soup*');
    expect(text).toContain(`Shared via ${LARO_SHARE_TAGLINE}`);
  });

  it('appends referral code and signup link when provided', () => {
    const text = buildWhatsAppRecipeShareText(recipe, {
      shareUrl: 'https://laro.food/recipe/Ab12Cd',
      referralCode: 'chef42',
      signupOrigin: 'https://laro.food',
    });
    expect(text).toContain('*CHEF42*');
    expect(text).toContain('https://laro.food/#/register?ref=CHEF42');
  });
});
