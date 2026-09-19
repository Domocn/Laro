/** Destructive confirm helper — respects the confirmActions accessibility toggle. */
export const confirmDestructive = (confirmActions, message) => {
  if (!confirmActions) return true;
  if (typeof window === 'undefined') return true;
  return window.confirm(message);
};

/** Optional haptic pulse when the user has haptic feedback enabled. */
export const pulseHaptic = (hapticFeedback, pattern = [40, 30, 40]) => {
  if (!hapticFeedback || typeof navigator === 'undefined' || !navigator.vibrate) return;
  try {
    navigator.vibrate(pattern);
  } catch {
    /* ignore unsupported devices */
  }
};
