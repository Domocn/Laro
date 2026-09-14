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

/**
 * Deterministic Unsplash food image for a recipe without its own photo.
 * Same recipe id/title always maps to the same image; different recipes vary.
 */
export function getUnsplashFoodImage(seed, category, width = 800) {
  const cat = category && UNSPLASH_FOOD[category] ? category : null;
  const pool = cat ? UNSPLASH_FOOD[cat] : UNSPLASH_ALL;
  const photoId = pool[hashSeed(seed) % pool.length];
  return unsplashUrl(photoId, width);
}

/**
 * Resolve recipe / media URL. Pass recipe (or {id,title,category}) for varied
 * Unsplash placeholders when image_url is empty.
 */
export function getImageUrl(url, recipeOrSeed = null) {
  if (url) {
    if (url.startsWith('http')) return url;
    const serverUrl = localStorage.getItem('laro_server_url') || process.env.REACT_APP_BACKEND_URL || '';
    return `${serverUrl}${url}`;
  }
  if (recipeOrSeed && typeof recipeOrSeed === 'object') {
    const seed = recipeOrSeed.id || recipeOrSeed.title || 'laro';
    return getUnsplashFoodImage(seed, recipeOrSeed.category);
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
