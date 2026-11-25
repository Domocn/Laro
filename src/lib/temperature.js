// Oven / cooking temperatures in instruction text, shown in °F for US users.
// Keep aligned with android util/Temperature.kt.
//
//   "Bake at 180C for 20 min"        → "Bake at 350°F for 20 min"
//   "Heat oven to 200°C (400°F)"      → "Heat oven to 400°F"   (text already gives both: keep °F)
//   "350F / 180C"                     → "350°F"
//   "cook to 75 °C"                   → "cook to 167°F"
//   "180-200C"                        → "350-400°F"
// Oven temperatures (120 °C and up) round to the nearest 25 °F like oven dials; lower ones
// (meat, sugar, water) round to the nearest degree. A bare "C" needs 100+ so "2 C flour"
// (cups) is never touched. Other countries see the text unchanged.

const DEG = '(?:\\s*(?:°|º|˚|degrees?|deg\\.?)\\s*)';
const UNIT = '([CF])(?:elsius|ahrenheit)?(?![A-Za-z])';
const NUM = '(\\d{2,3})';

export function cToF(c) {
  const f = (Number(c) * 9) / 5 + 32;
  return Number(c) >= 120 ? Math.round(f / 25) * 25 : Math.round(f);
}

function isCelsius(n, hasDegree) {
  const v = Number(n);
  return hasDegree ? v >= 30 && v <= 300 : v >= 100 && v <= 300;
}

// "200°C (400°F)", "200C/400F", "400F (200C)", "200 C or 400 F" — keep the °F half.
const PAIR = new RegExp(
  `${NUM}(${DEG})?\\s*${UNIT}\\s*(\\(|/|,|or\\b|\\|)\\s*${NUM}(${DEG})?\\s*${UNIT}(\\s*\\))?`,
  'gi'
);
// "180-200C", "180 to 200 °C"
const RANGE_C = new RegExp(`${NUM}\\s*(?:-|–|to)\\s*${NUM}(${DEG})?\\s*C(?:elsius)?(?![A-Za-z])`, 'gi');
// "180C", "180 °C", "180 degrees C", "180 degrees Celsius"
const SINGLE_C = new RegExp(`${NUM}(${DEG})?\\s*([Cc])(?:elsius)?(?![A-Za-z])`, 'g');

/** Instruction text with Celsius temperatures shown for `nutritionStyle` (only 'us' changes). */
export function temperaturesForStyle(text, style) {
  if (style !== 'us' || typeof text !== 'string' || !text) return text;
  let out = text.replace(PAIR, (m, n1, d1, u1, sep, n2, d2, u2, close) => {
    const firstIsF = u1.toUpperCase() === 'F';
    if (firstIsF === (u2.toUpperCase() === 'F')) return m; // not a C/F pair
    const fNum = firstIsF ? n1 : n2;
    const cNum = firstIsF ? n2 : n1;
    if (!isCelsius(cNum, true) || Number(fNum) < 80) return m;
    // Keep a closing bracket that wasn't part of "C (F)".
    const keepClose = close && sep !== '(' ? close : '';
    return `${fNum}°F${keepClose}`;
  });
  out = out.replace(RANGE_C, (m, a, b, deg) => (
    isCelsius(a, !!deg) && isCelsius(b, !!deg) ? `${cToF(a)}-${cToF(b)}°F` : m
  ));
  // A bare lower-case "c" is cups ("250 c flour"): only "°c" / "degrees c" count.
  out = out.replace(SINGLE_C, (m, n, deg, unit) => (
    isCelsius(n, !!deg) && (deg || unit === 'C') ? `${cToF(n)}°F` : m
  ));
  return out;
}
