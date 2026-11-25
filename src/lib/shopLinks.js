/**
 * "Shop at…" search links for a shopping-list item. No UK grocer has a public basket API, so we
 * open the store's own search; the user picks the store each time.
 * Formats checked in a browser 2026-10-20. Mirrors Android `util/ShopLinks.kt`.
 */
export const SHOP_STORES = [
  { id: 'tesco', label: 'Tesco' },
  { id: 'sainsburys', label: "Sainsbury's" },
  { id: 'asda', label: 'Asda' },
  { id: 'morrisons', label: 'Morrisons' },
  { id: 'ocado', label: 'Ocado' },
  { id: 'waitrose', label: 'Waitrose' },
  { id: 'iceland', label: 'Iceland' },
  { id: 'amazon', label: 'Amazon (incl. Gopuff fast delivery)' },
];

/** "chopped tomatoes, drained" -> "chopped tomatoes"; "onion (finely chopped)" -> "onion". */
export function shopSearchTerm(name = '') {
  const t = String(name).split(',')[0].split('(')[0].trim();
  return t || String(name).trim();
}

const TAG_RE = /^[A-Za-z0-9-]{3,40}$/;

export function shopUrl(storeId, itemName, amazonTag) {
  const term = shopSearchTerm(itemName);
  const q = encodeURIComponent(term).replace(/%20/g, '+');
  const pathQ = encodeURIComponent(term);
  switch (storeId) {
    case 'tesco':
      return `https://www.tesco.com/shop/en-GB/search?query=${q}`;
    case 'sainsburys':
      return `https://www.sainsburys.co.uk/groceries/search?searchTerm=${q}`;
    case 'asda':
      return `https://www.asda.com/groceries/search/${pathQ}`;
    case 'morrisons':
      return `https://groceries.morrisons.com/search?q=${q}`;
    case 'ocado':
      return `https://www.ocado.com/search?q=${q}`;
    case 'waitrose':
      return `https://www.waitrose.com/ecom/shop/search?searchTerm=${q}`;
    case 'iceland':
      return `https://www.iceland.co.uk/search?q=${q}`;
    case 'amazon': {
      const tag = String(amazonTag || '').trim();
      return `https://www.amazon.co.uk/s?k=${q}&i=grocery${TAG_RE.test(tag) ? `&tag=${tag}` : ''}`;
    }
    default:
      return '';
  }
}
