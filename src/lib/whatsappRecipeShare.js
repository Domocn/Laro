/** WhatsApp share copy — link first so previews work; compact card, not full recipe text. */

export const LARO_SHARE_TAGLINE = 'Laro — Local · Archived · Recipes · Organised';

function formatDuration(label, value) {
  if (value == null || value === '') return null;
  const text = String(value).trim();
  if (!text) return null;
  if (/min|hour|hr|h\b/i.test(text)) return `${label} ${text}`;
  if (/^\d+$/.test(text)) return `${label} ${text} min`;
  return `${label} ${text}`;
}

function truncate(text, maxLen) {
  const t = String(text || '')
    .replace(/\s+/g, ' ')
    .trim();
  if (!t) return '';
  if (t.length <= maxLen) return t;
  return `${t.slice(0, maxLen - 1).trim()}…`;
}

/** Signup URL with friend/referral code (hash-router). */
export function buildReferralSignupUrl(origin, referralCode) {
  const code = String(referralCode || '')
    .trim()
    .toUpperCase();
  if (!code) return '';
  const base = String(origin || '')
    .trim()
    .replace(/\/$/, '');
  if (!base) return '';
  return `${base}/#/register?ref=${encodeURIComponent(code)}`;
}

/**
 * @param {{ title?: string, description?: string, prep_time?: *, cook_time?: *, servings?: * }} recipe
 * @param {{ shareUrl?: string, includeLink?: boolean, referralCode?: string, signupOrigin?: string }} options
 */
export function buildWhatsAppRecipeShareText(recipe, options = {}) {
  const { shareUrl, includeLink = true, referralCode, signupOrigin } = options;
  const title = recipe?.title?.trim() || 'Recipe';

  const metaParts = [
    formatDuration('Prep', recipe?.prep_time),
    formatDuration('Cook', recipe?.cook_time),
    recipe?.servings != null && String(recipe.servings).trim()
      ? `Serves ${recipe.servings}`
      : null,
  ].filter(Boolean);

  const description = truncate(recipe?.description, 160);

  const cardLines = [`🍳 *${title}*`];
  if (metaParts.length) {
    cardLines.push(metaParts.join(' · '));
  }
  if (description) {
    cardLines.push(description);
  }

  const referralLines = [];
  const code = String(referralCode || '')
    .trim()
    .toUpperCase();
  if (code) {
    const signupUrl =
      buildReferralSignupUrl(signupOrigin, code) ||
      `Use code ${code} at signup`;
    referralLines.push(
      '',
      `New to Laro? Use my code *${code}* for 2 weeks of Pro free:`,
      signupUrl
    );
  }

  const url = shareUrl?.trim();
  if (includeLink && url) {
    return [
      url,
      '',
      ...cardLines,
      '',
      `Full recipe card on ${LARO_SHARE_TAGLINE}`,
      ...referralLines,
    ].join('\n');
  }

  return [...cardLines, '', `Shared via ${LARO_SHARE_TAGLINE}`, ...referralLines].join('\n');
}

export function openWhatsAppShare(message) {
  const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(message)}`;
  window.open(whatsappUrl, '_blank', 'noopener,noreferrer');
}
