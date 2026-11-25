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

/** Curated Unsplash food photos — varied placeholders when a recipe has no image. */
const UNSPLASH_FOOD = {
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
    'photo-1555939594-58d7cb561ad1',
    'photo-1544025162-d76694265947',
    'photo-1414235077428-338989a2e8c0',
    'photo-1476224203421-9ac39bcb3327',
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

/** Title/ingredient keywords → specific Unsplash photo (prefer over category hash). */
const UNSPLASH_KEYWORDS = [
  { keys: ['weetabix', 'weet-bix', 'weet-a-bix', 'wheat biscuit'], id: 'photo-1664802460246-42deccecbc92' },
  { keys: ['overnight oat', 'bircher'], id: 'photo-1517673400267-0251440c45dc' },
  { keys: ['banana bread', 'banana loaf'], id: 'photo-1632931057819-4eefffa8e007' },
  { keys: ['meatball', 'meatballs', 'meat ball', 'meat balls', 'kofta'], id: 'photo-1529042410759-befb1204b468' },
  { keys: ['nut bar', 'granola bar', 'protein bar', 'cereal bar', 'energy bar', 'snack bar'], id: 'photo-1705868432559-211198009991' },
  { keys: ['cheesecake'], id: 'photo-1533134242443-d4fd215305ad' },
  { keys: ['mango lassi', 'lassi'], id: 'photo-1600271886742-f049cd451bba' },
  // Dish names before their main ingredient ("Mango Smoothie" is a drink, not a mango).
  { keys: ['mango smoothie', 'mango shake'], id: 'photo-1623065422902-30a2d299bbe4' },
  { keys: ['smoothie', 'protein shake', 'milkshake'], id: 'photo-1579954115545-a95591f28bfc' },
  { keys: ['guacamole'], id: 'photo-1680992071073-cb1696ba8d3e' },
  { keys: ['stir fry', 'stir-fry', 'stirfry'], id: 'photo-1767974877206-a594e0b1008e' },
  { keys: ['greek salad', 'horiatiki'], id: 'photo-1606735584785-1848fdcaea57' },
  { keys: ['green curry'], id: 'photo-1761315412830-2f59480377b0' },
  { keys: ['mango'], id: 'photo-1553279768-865429fa0078' },
  { keys: ['custard', 'pudding'], id: 'photo-1488477181946-6428a0291777' },
  { keys: ['yogurt', 'yoghurt', 'skyr'], id: 'photo-1488477181946-6428a0291777' },
  { keys: ['pancake'], id: 'photo-1528207776546-365bb710ee93' },
  { keys: ['salad'], id: 'photo-1512621776951-a57141f2eefd' },
  { keys: ['pasta', 'spaghetti'], id: 'photo-1621996346565-e3dbc646d9a9' },
  { keys: ['pizza'], id: 'photo-1565299624946-b28f40a0ae38' },
  { keys: ['burger'], id: 'photo-1568901346375-23c9450c58cd' },
  { keys: ['oatmeal', 'porridge', 'oats', 'oat'], id: 'photo-1517673400267-0251440c45dc' },
  { keys: ['soup', 'stew'], id: 'photo-1547592166-23ac45744acd' },
  { keys: ['curry'], id: 'photo-1585937421612-70a008356fbe' },
  { keys: ['taco', 'burrito'], id: 'photo-1565299585323-38d6b0865b47' },
  { keys: ['cake', 'brownie', 'cookie'], id: 'photo-1563729784474-d77dbb933a9e' },
  { keys: ['coffee', 'latte'], id: 'photo-1495474472287-4d71bcdd2085' },
  {
    keys: ['cereal', 'granola', 'cornflakes', 'corn flakes', 'cheerios', 'muesli', 'shredded wheat'],
    id: 'photo-1572319216151-4fb52730dc68',
  },
  { keys: ['fruit', 'berry', 'berries', 'strawberry', 'pear'], id: 'photo-1490474418585-ba9bad8fd0ea' },
  // Ingredient keywords LAST: the dish wins ('Beef Tacos' -> tacos, not a steak photo).
  { keys: ['chicken'], id: 'photo-1598103442097-8b74394b95c6' },
  { keys: ['beef', 'steak', 'mince'], id: 'photo-1544025162-d76694265947' },
  { keys: ['salmon', 'fish'], id: 'photo-1467003909585-2f8a72700288' },
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

function recipeImageSeed(recipe) {
  const parts = [recipe.title, recipe.category];
  if (Array.isArray(recipe.tags)) parts.push(...recipe.tags);
  else if (recipe.tags) parts.push(String(recipe.tags));
  for (const ing of (recipe.ingredients || []).slice(0, 16)) {
    if (typeof ing === 'string') parts.push(ing);
    else if (ing && typeof ing === 'object') parts.push(ing.name || ing.item || '');
  }
  return parts.filter(Boolean).join(' ');
}

function hasKeyword(blob, key) {
  const k = String(key || '').trim().toLowerCase();
  if (!k) return false;
  const escaped = k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(?:^|[^a-z0-9])${escaped}(?:$|[^a-z0-9])`).test(blob);
}

function keywordUnsplashId(titleOrSeed) {
  const blob = String(titleOrSeed || '').toLowerCase();
  if (!blob) return null;
  for (const row of UNSPLASH_KEYWORDS) {
    if (row.keys.some((k) => hasKeyword(blob, k))) return row.id;
  }
  return null;
}

/** Wikimedia / Unsplash / TheMealDB covers can be swapped for a better title match. User uploads stay. */
function isReplaceableStockUrl(url) {
  if (!url) return true;
  const u = String(url).toLowerCase();
  if (u.includes('/uploads/')) return false;
  return (
    u.includes('images.unsplash.com')
    || u.includes('unsplash.com')
    || u.includes('themealdb.com')
    || u.includes('wikimedia.org')
    || u.includes('wikipedia.org')
  );
}

/**
 * Deterministic Unsplash food image for a recipe without its own photo.
 * Prefers title keyword matches (e.g. Weetabix, cheesecake) over category hash.
 */
export function getUnsplashFoodImage(seed, category, width = 800, title = null) {
  const fromTitle = keywordUnsplashId(title);
  if (fromTitle) return unsplashUrl(fromTitle, width);
  const keywordId = keywordUnsplashId(seed);
  if (keywordId) return unsplashUrl(keywordId, width);
  const cat = category && UNSPLASH_FOOD[category] ? category : null;
  const pool = cat ? UNSPLASH_FOOD[cat] : UNSPLASH_ALL;
  const photoId = pool[hashSeed(seed) % pool.length];
  return unsplashUrl(photoId, width);
}

function readServerOrigin() {
  try {
    if (typeof localStorage !== 'undefined') {
      return localStorage.getItem('laro_server_url') || process.env.REACT_APP_BACKEND_URL || '';
    }
  } catch (e) {
    /* node tests */
  }
  return process.env.REACT_APP_BACKEND_URL || '';
}

/**
 * Resolve recipe / media URL. Pass recipe (or {id,title,category}) for varied
 * Unsplash placeholders when image_url is empty.
 */
export function getImageUrl(url, recipeOrSeed = null) {
  const title = recipeOrSeed && typeof recipeOrSeed === 'object'
    ? recipeOrSeed.title
    : (typeof recipeOrSeed === 'string' ? recipeOrSeed : '');
  const titleId = keywordUnsplashId(title);
  if (titleId && isReplaceableStockUrl(url)) {
    return unsplashUrl(titleId);
  }
  if (url) {
    if (url.startsWith('http')) return url;
    const serverUrl = readServerOrigin();
    return `${serverUrl}${url}`;
  }
  if (recipeOrSeed && typeof recipeOrSeed === 'object') {
    const seed = recipeImageSeed(recipeOrSeed) || recipeOrSeed.id || 'laro';
    return getUnsplashFoodImage(seed, recipeOrSeed.category, 800, recipeOrSeed.title);
  }
  if (typeof recipeOrSeed === 'string' && recipeOrSeed) {
    return getUnsplashFoodImage(recipeOrSeed);
  }
  return getUnsplashFoodImage('laro-default');
}

export const MEAL_TYPES = ['Breakfast', 'Lunch', 'Dinner', 'Snack'];

export const CATEGORIES = [
  'All', 'Breakfast', 'Lunch', 'Dinner',
  'Dessert', 'Appetizer', 'Snack', 'Beverage', 'Sauce', 'Meal Pack', 'Other'
];
