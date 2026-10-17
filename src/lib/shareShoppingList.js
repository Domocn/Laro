/** Format a shopping list for WhatsApp / clipboard sharing (aisle-grouped). */

export function formatShoppingListForShare(list, { uncheckedOnly = true } = {}) {
  const name = list?.name || 'Shopping list';
  const items = list?.items || [];
  const rows = items.filter((item) => !uncheckedOnly || !item.checked);
  if (!rows.length) return `${name}\n\n(nothing to buy)`;

  const byAisle = new Map();
  rows.forEach((item) => {
    const aisle = item.category || 'Other';
    if (!byAisle.has(aisle)) byAisle.set(aisle, []);
    byAisle.get(aisle).push(item);
  });

  const lines = [`🛒 ${name}`, ''];
  [...byAisle.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .forEach(([aisle, aisleItems]) => {
      lines.push(`__${aisle}__`);
      aisleItems.forEach((item) => {
        const qty =
          item.amount != null && item.amount !== ''
            ? `${item.amount}${item.unit ? ` ${item.unit}` : ''} `
            : item.quantity != null
              ? `${item.quantity}${item.unit ? ` ${item.unit}` : ''} `
              : '';
        lines.push(`• ${qty}${item.name}`);
      });
      lines.push('');
    });
  lines.push('— Laro');
  return lines.join('\n').trim();
}

export function shareShoppingListWhatsApp(list, options) {
  const text = formatShoppingListForShare(list, options);
  const url = `https://wa.me/?text=${encodeURIComponent(text)}`;
  window.open(url, '_blank', 'noopener,noreferrer');
}

export async function copyShoppingListToClipboard(list, options) {
  const text = formatShoppingListForShare(list, options);
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.setAttribute('readonly', '');
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.select();
  const ok = document.execCommand('copy');
  document.body.removeChild(ta);
  return ok;
}
