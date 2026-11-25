/**
 * Map an ingredient name to a matching food emoji.
 * Keyword-based, most-specific first (so "peanut butter" → 🥜, not "butter" → 🧈).
 * Returns '' when nothing sensible matches (caller can hide or use a fallback).
 */

// [keywords, emoji] — first matching row wins, so order specific → general.
const FOOD_EMOJI = [
  // proteins / meat / fish
  [['peanut butter'], '🥜'],
  [['sausage', 'chorizo', 'bratwurst', 'hot dog', 'frankfurter'], '🌭'],
  [['bacon', 'pancetta', 'lardon'], '🥓'],
  [['turkey'], '🦃'],
  [['chicken', 'poultry'], '🍗'],
  [['steak', 'beef', 'mince', 'ground beef', 'brisket', 'veal'], '🥩'],
  [['pork', 'ham', 'gammon', 'ribs'], '🥩'],
  [['lamb', 'mutton'], '🍖'],
  [['prawn', 'shrimp'], '🍤'],
  [['salmon', 'tuna', 'cod', 'haddock', 'mackerel', 'trout', 'fish fillet', 'white fish', 'fish'], '🐟'],
  [['crab', 'lobster', 'shellfish'], '🦞'],
  [['squid', 'calamari', 'octopus'], '🦑'],
  [['egg'], '🥚'],
  [['tofu', 'tempeh', 'seitan', 'soy protein', 'tvp'], '🧊'],
  // dairy
  [['mozzarella', 'cheddar', 'parmesan', 'feta', 'halloumi', 'ricotta', 'cheese'], '🧀'],
  [['butter', 'ghee'], '🧈'],
  [['yoghurt', 'yogurt', 'skyr', 'quark', 'kefir'], '🥛'],
  [['cream', 'creme', 'custard'], '🍮'],
  [['milk'], '🥛'],
  // grains / carbs / baking
  [['oat flour', 'oatmeal', 'porridge', 'oats', 'oat', 'granola', 'muesli'], '🥣'],
  [['rice', 'risotto', 'basmati', 'jasmine rice'], '🍚'],
  [['pasta', 'spaghetti', 'penne', 'macaroni', 'lasagne', 'lasagna', 'tagliatelle', 'fusilli'], '🍝'],
  [['noodle', 'ramen', 'udon', 'vermicelli'], '🍜'],
  [['bread', 'baguette', 'sourdough', 'ciabatta', 'roll', 'bun', 'toast', 'bagel'], '🍞'],
  [['tortilla', 'wrap', 'flatbread', 'pita', 'naan'], '🫓'],
  [['flour', 'cornflour', 'cornstarch', 'semolina', 'couscous', 'polenta', 'cornmeal'], '🌾'],
  [['quinoa', 'buckwheat', 'bulgur', 'barley', 'millet', 'farro'], '🌾'],
  [['cereal', 'weetabix', 'cornflakes', 'shredded wheat'], '🥣'],
  // veg
  [['sweet potato'], '🍠'],
  [['potato', 'spud', 'hash brown'], '🥔'],
  [['carrot'], '🥕'],
  [['broccoli'], '🥦'],
  [['cauliflower', 'cabbage', 'brussels', 'kale', 'pak choi', 'bok choy', 'greens', 'chard', 'collard'], '🥬'],
  [['spinach', 'rocket', 'arugula', 'watercress', 'lettuce', 'salad leaves'], '🥬'],
  [['tomato', 'passata', 'sundried'], '🍅'],
  [['onion', 'shallot', 'spring onion', 'scallion', 'leek'], '🧅'],
  [['garlic'], '🧄'],
  [['mushroom', 'shiitake', 'portobello', 'chestnut mushroom'], '🍄'],
  [['chilli', 'chili', 'jalapeno', 'cayenne', 'scotch bonnet'], '🌶️'],
  [['seasoning', 'salt and pepper', 'salt & pepper', 'salt, pepper', 'salt pepper', 'black pepper', 'peppercorn', 'cracked pepper', 'white pepper', 'mixed spice'], '🧂'],
  [['bell pepper', 'red pepper', 'green pepper', 'capsicum', 'pepper'], '🫑'],
  [['cucumber', 'gherkin', 'courgette', 'zucchini'], '🥒'],
  [['aubergine', 'eggplant'], '🍆'],
  [['sweetcorn', 'corn', 'maize'], '🌽'],
  [['chickpea', 'lentil', 'dal', 'dhal', 'split pea'], '🫘'],
  [['green bean', 'kidney bean', 'black bean', 'butter bean', 'cannellini', 'baked bean', 'beans'], '🫘'],
  [['peas', 'edamame', 'mangetout', 'sugar snap'], '🫛'],
  [['avocado', 'guacamole'], '🥑'],
  [['ginger', 'galangal'], '🫚'],
  [['olive'], '🫒'],
  [['radish', 'turnip', 'swede', 'parsnip', 'beetroot', 'beet'], '🥔'],
  [['celery', 'fennel', 'asparagus'], '🥬'],
  // fruit
  [['banana', 'plantain'], '🍌'],
  [['strawberr'], '🍓'],
  [['blueberr', 'blackberr', 'raspberr', 'berries', 'berry'], '🫐'],
  [['cherr'], '🍒'],
  [['grape', 'raisin', 'sultana'], '🍇'],
  [['lemon'], '🍋'],
  [['lime'], '🍈'],
  [['orange', 'clementine', 'satsuma', 'mandarin', 'tangerine'], '🍊'],
  [['apple'], '🍎'],
  [['pear'], '🍐'],
  [['peach', 'nectarine', 'apricot'], '🍑'],
  [['mango'], '🥭'],
  [['pineapple'], '🍍'],
  [['watermelon', 'melon', 'cantaloupe'], '🍉'],
  [['coconut'], '🥥'],
  [['kiwi'], '🥝'],
  [['date', 'medjool', 'fig', 'prune'], '🌰'],
  // nuts / seeds
  [['peanut'], '🥜'],
  // Tree nuts get the chestnut; a bare "nut" must be a whole word so nutmeg,
  // nutritional yeast and butternut squash don't turn into nuts.
  [['almond', 'cashew', 'walnut', 'pecan', 'hazelnut', 'pistachio', 'macadamia', /\bnuts?\b/], '🌰'],
  [['chia', 'flax', 'linseed', 'sesame', 'sunflower seed', 'pumpkin seed', 'seed'], '🌰'],
  // pantry / condiments / sweet
  [['chocolate', 'cocoa', 'cacao', 'brownie'], '🍫'],
  [['honey', 'maple', 'agave', 'syrup', 'jam', 'marmalade', 'preserve'], '🍯'],
  [['sugar', 'sweetener', 'stevia', 'sweets'], '🍬'],
  [['salt'], '🧂'],
  [['oil', 'tahini'], '🫗'],
  [['vinegar', 'balsamic'], '🧴'],
  [['soy sauce', 'tamari', 'miso', 'worcestershire', 'fish sauce', 'ketchup', 'mustard', 'mayo', 'sriracha', 'sauce'], '🥫'],
  [['stock', 'broth', 'bouillon'], '🍲'],
  [['coffee', 'espresso'], '☕'],
  [['tea', 'matcha'], '🍵'],
  [['wine', 'beer', 'lager', 'cider', 'spirit', 'vodka', 'rum'], '🍷'],
  [['water', 'ice'], '💧'],
  [['cinnamon', 'nutmeg', 'paprika', 'turmeric', 'cumin', 'coriander', 'oregano', 'basil', 'thyme', 'rosemary', 'parsley', 'mint', 'dill', 'spice', 'herb', 'seasoning', 'curry powder', 'garam masala'], '🌿'],
  [['protein powder', 'whey'], '💪'],
  [['vanilla', 'baking powder', 'baking soda', 'bicarbonate', 'yeast', 'gelatine', 'gelatin'], '🧁'],
];

export function foodEmoji(name) {
  const n = String(name || '').toLowerCase();
  if (!n) return '';
  for (const [keys, emoji] of FOOD_EMOJI) {
    if (keys.some((k) => (k instanceof RegExp ? k.test(n) : n.includes(k)))) return emoji;
  }
  return '';
}
