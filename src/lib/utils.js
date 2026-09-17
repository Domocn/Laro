import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}

export function formatTime(minutes) {
  if (!minutes) return '0 min';
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return mins > 0 ? `${hours}h ${mins}m` : `${hours}h`;
}

export function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * Curated Unsplash photos for recipes with no image of their own.
 * Meal-slot categories (Breakfast/Dinner) are a fallback. Food kinds like
 * "cereal" win when the title or ingredients mention them — Weetabix should
 * look like cereal, not scrambled eggs.
 */
const UNSPLASH_FOOD = {
  cereal: [
    'photo-1664802460246-42deccecbc92',
    'photo-1572319216151-4fb52730dc68',
    'photo-1654923064926-be7e64267a31',
    'photo-1736605406266-dbb985ef3325',
  ],
  oats: [
    'photo-1572319216151-4fb52730dc68',
    'photo-1505576399279-565b52d4ac71',
    'photo-1664802460246-42deccecbc92',
  ],
  yogurt: [
    'photo-1488477181946-6428a0291777',
    'photo-1505576399279-565b52d4ac71',
  ],
  eggs: [
    'photo-1525351484163-7529414344d8',
    'photo-1482049016688-2d3e1b311543',
  ],
  toast: [
    'photo-1482049016688-2d3e1b311543',
    'photo-1484723091739-30a097e8f929',
  ],
  pancakes: [
    'photo-1567620905732-2d1ec7ab7445',
    'photo-1528207776546-365bb710ee93',
  ],
  pasta: [
    'photo-1621996346565-e3dbc646d9a9',
    'photo-1551183053-bf91a1d81141',
  ],
  pizza: [
    'photo-1565299624946-b28f40a0ae38',
    'photo-1513104890138-7c749659a591',
  ],
  salad: [
    'photo-1512621776951-a57141f2eefd',
    'photo-1540189549336-e6e99c3679fe',
  ],
  soup: [
    'photo-1547592166-23ac45744acd',
    'photo-1476718406336-bb5a9690ee2a',
  ],
  chicken: [
    'photo-1598103442097-8b45306b3119',
    'photo-1604908176997-125f25cc6f3d',
  ],
  fish: [
    'photo-1519708227418-c8fd9a32b7a2',
    'photo-1467003909585-2f8a72700288',
  ],
  burger: [
    'photo-1568901346375-23c9450c58cd',
    'photo-1550547660-d9450f859349',
  ],
  rice: [
    'photo-1516684669134-de6f7c473a2a',
    'photo-1536304993881-eb2e5c2c1a80',
  ],
  smoothie: [
    'photo-1505252585461-04db1eb84625',
    'photo-1553530666-ba11c7d38dba',
  ],
  coffee: [
    'photo-1495474472287-4d71bcdd2085',
    'photo-1511920170033-20832279e92c',
  ],
  Breakfast: [
    'photo-1493770348161-369560ae357d',
    'photo-1533089860892-a7c6f0a88666',
    'photo-1525351484163-7529414344d8',
    'photo-1484723091739-30a097e8f929',
  ],
  Lunch: [
    'photo-1512621776951-a57141f2eefd',
    'photo-1540189549336-e6e99c3679fe',
    'photo-1546069901-ba9599a7e63c',
    'photo-1567620905732-2d1ec7ab7445',
  ],
  Dinner: [
    'photo-1467003909585-2f8a72700288',
    'photo-1544025162-d76694265947',
    'photo-1476224203421-9ac39bcb3327',
    'photo-1414235077428-338989a2e8c0',
  ],
  Dessert: [
    'photo-1606313564200-e75d5e30476c',
    'photo-1488477181946-6428a0291777',
    'photo-1563729784474-d77dbb933a9e',
    'photo-1551024601-bec78aea704b',
  ],
  Appetizer: [
    'photo-1541014741259-de529411b96a',
    'photo-1572695157366-5e585ab2b69f',
    'photo-1562967916-eb82221dfb92',
  ],
  Snack: [
    'photo-1505576399279-565b52d4ac71',
    'photo-1621939514649-280e2ee25f60',
    'photo-1558961363-fa8fdf82db35',
  ],
  Beverage: [
    'photo-1544145945-f90425340c7e',
    'photo-1495474472287-4d71bcdd2085',
    'photo-1513558161293-cdaf765ed2fd',
  ],
  'Meal Pack': [
    'photo-1546069901-ba9599a7e63c',
    'photo-1498837167922-ddd27525d352',
  ],
  Other: [
    'photo-1498837167922-ddd27525d352',
    'photo-1504674900247-0877df9cc836',
    'photo-1555939594-58d7cb561ad1',
    'photo-1565299624946-b28f40a0ae38',
    'photo-1565958011703-44f9829ba187',
    'photo-1482049016688-2d3e1b311543',
  ],
};

/** More specific kinds first. Matched against title, tags, and ingredient names. */
const FOOD_IMAGE_HINTS = [
  {
    kind: 'cereal',
    words: [
      'weetabix', 'weet-a-bix', 'cereal', 'cornflakes', 'corn flakes', 'cheerios',
      'shredded wheat', 'rice krispies', 'frosties', 'bran flakes', 'special k',
      'granola', 'muesli', 'crunchy nut', 'alpen',
    ],
  },
  { kind: 'oats', words: ['porridge', 'oatmeal', 'overnight oats', 'rolled oats'] },
  { kind: 'yogurt', words: ['yogurt', 'yoghurt', 'skyr', 'fromage frais'] },
  { kind: 'smoothie', words: ['smoothie', 'protein shake', 'shake'] },
  { kind: 'coffee', words: ['coffee', 'latte', 'espresso', 'cappuccino'] },
  { kind: 'pancakes', words: ['pancake', 'waffle', 'french toast'] },
  { kind: 'eggs', words: ['omelette', 'omelet', 'scrambled egg', 'fried egg', 'poached egg', 'eggs'] },
  { kind: 'toast', words: ['toast', 'avocado toast', 'sandwich'] },
  { kind: 'pasta', words: ['pasta', 'spaghetti', 'lasagna', 'lasagne', 'noodle', 'penne', 'linguine'] },
  { kind: 'pizza', words: ['pizza'] },
  { kind: 'salad', words: ['salad'] },
  { kind: 'soup', words: ['soup', 'stew', 'chowder'] },
  { kind: 'chicken', words: ['chicken', 'roast chicken', 'nugget'] },
  { kind: 'fish', words: ['salmon', 'cod', 'tuna', 'fish'] },
  { kind: 'burger', words: ['burger', 'cheeseburger'] },
  { kind: 'rice', words: ['rice', 'risotto', 'fried rice'] },
];

const UNSPLASH_ALL = Object.values(UNSPLASH_FOOD).flat();

function hashSeed(seed) {
  const s = String(seed || 'laro');
  let h = 0;
  for (let i = 0; i < s.length; i += 1) {
    h = (h * 31 + s.charCodeAt(i)) >>> 0;
  }
  return h;
}

function unsplashUrl(photoId, width = 800) {
  return `https://images.unsplash.com/${photoId}?auto=format&fit=crop&w=${width}&q=80`;
}

function recipeSearchText(recipe) {
  const parts = [recipe.title, recipe.category];
  if (Array.isArray(recipe.tags)) parts.push(...recipe.tags);
  const ingredients = recipe.ingredients || [];
  for (const ing of ingredients.slice(0, 12)) {
    if (typeof ing === 'string') parts.push(ing);
    else if (ing && ing.name) parts.push(ing.name);
  }
  return parts.filter(Boolean).join(' ').toLowerCase();
}

/**
 * Pick a photo bucket from the actual food (Weetabix → cereal), then meal category.
 */
export function inferFoodImageKind(recipeOrText) {
  const text =
    recipeOrText && typeof recipeOrText === 'object'
      ? recipeSearchText(recipeOrText)
      : String(recipeOrText || '').toLowerCase();
  if (!text) return null;
  for (const { kind, words } of FOOD_IMAGE_HINTS) {
    if (words.some((word) => text.includes(word))) return kind;
  }
  if (recipeOrText && typeof recipeOrText === 'object' && UNSPLASH_FOOD[recipeOrText.category]) {
    return recipeOrText.category;
  }
  return null;
}

/**
 * Deterministic Unsplash food image for a recipe without its own photo.
 * Same recipe id/title always maps to the same image; different recipes vary.
 */
export function getUnsplashFoodImage(seed, category, width = 800) {
  let kind = category && UNSPLASH_FOOD[category] ? category : null;
  if (!kind && seed) {
    kind = inferFoodImageKind(seed);
  }
  const pool = kind && UNSPLASH_FOOD[kind] ? UNSPLASH_FOOD[kind] : UNSPLASH_ALL;
  const photoId = pool[hashSeed(seed) % pool.length];
  return unsplashUrl(photoId, width);
}

/**
 * Resolve recipe / media URL. Pass recipe (or {id,title,category,ingredients})
 * so placeholders match the food, not only Breakfast/Dinner.
 */
export function getImageUrl(url, recipeOrSeed = null) {
  if (url) {
    if (url.startsWith('http')) return url;
    const serverUrl = localStorage.getItem('laro_server_url') || process.env.REACT_APP_BACKEND_URL || '';
    return `${serverUrl}${url}`;
  }
  if (recipeOrSeed && typeof recipeOrSeed === 'object') {
    const seed = recipeOrSeed.id || recipeOrSeed.title || 'laro';
    const kind = inferFoodImageKind(recipeOrSeed);
    return getUnsplashFoodImage(seed, kind);
  }
  if (typeof recipeOrSeed === 'string' && recipeOrSeed) {
    return getUnsplashFoodImage(recipeOrSeed);
  }
  return getUnsplashFoodImage('laro-default');
}

export const MEAL_TYPES = ['Breakfast', 'Lunch', 'Dinner', 'Snack'];

export const CATEGORIES = [
  'All', 'Breakfast', 'Lunch', 'Dinner',
  'Dessert', 'Appetizer', 'Snack', 'Beverage', 'Meal Pack', 'Other'
];
