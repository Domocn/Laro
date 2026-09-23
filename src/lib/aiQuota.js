/**
 * Free-tier AI quota helpers (3 free LLM uses, then Premium).
 * JSON-LD / schema.org scrapes do not consume quota.
 *
 * All LLM-backed features must surface 402 via these helpers so users
 * are directed to Settings (RevenueCat / Pro paywall).
 */
import { toast } from 'sonner';

/**
 * Prefer the real API `detail` (string, {message}, or validation array)
 * so toasts show why AI / meal-plan calls failed — not only a generic code.
 */
export function getAiQuotaErrorMessage(
  error,
  fallback = 'AI request failed. Please try again.'
) {
  const detail = error?.response?.data?.detail;
  if (isAiQuotaExceeded(error)) {
    if (detail?.error === 'laro_chat_pro_required') {
      return (
        detail?.message ||
        'Laro Chat is unlimited with Laro Pro. Upgrade in Settings to keep asking cooking questions.'
      );
    }
    return (
      detail?.message ||
      "You've used your free import assists. Upgrade to Laro Pro for unlimited imports."
    );
  }
  if (typeof detail === 'string' && detail.trim()) return detail.trim();
  if (detail?.message && typeof detail.message === 'string') return detail.message;
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (typeof d === 'string' ? d : d?.msg || d?.message))
      .filter(Boolean);
    if (msgs.length) return msgs.join('; ');
  }
  if (detail != null && typeof detail === 'object') {
    try {
      const s = JSON.stringify(detail);
      if (s && s !== '{}' && s !== 'null') return s;
    } catch {
      /* ignore */
    }
  }
  // Network / timeout with no JSON body
  if (!error?.response && error?.message) return error.message;
  return fallback;
}

export function isImportQuotaExceeded(error) {
  return error?.response?.data?.detail?.error === 'ai_quota_exceeded';
}

export function isLaroChatProRequired(error) {
  return error?.response?.data?.detail?.error === 'laro_chat_pro_required';
}

/** True when the UI should offer Settings → Pro (imports, chat, or explicit upgrade flag). */
export function isAiQuotaExceeded(error) {
  const detail = error?.response?.data?.detail;
  const code = detail?.error;
  if (isImportQuotaExceeded(error) || isLaroChatProRequired(error)) {
    return true;
  }
  return error?.response?.status === 402 && detail?.upgrade_required === true;
}

/**
 * Toast an AI failure. On quota exceeded, offer an Upgrade action that
 * navigates to Settings (subscription / paywall section).
 *
 * @param {unknown} error
 * @param {{ navigate?: (path: string) => void, fallback?: string, upgradeLabel?: string }} [opts]
 */
export function toastAiQuotaError(error, opts = {}) {
  const {
    navigate,
    fallback = 'AI request failed. Please try again.',
    upgradeLabel = 'Laro Pro',
  } = opts;
  const message = getAiQuotaErrorMessage(error, fallback);
  if (isAiQuotaExceeded(error) && typeof navigate === 'function') {
    toast.error(message, {
      action: {
        label: upgradeLabel,
        onClick: () => navigate('/settings'),
      },
      duration: 8000,
    });
    return message;
  }
  toast.error(message);
  return message;
}
