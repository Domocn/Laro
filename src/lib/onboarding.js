/**
 * Onboarding / app tour triggers.
 *
 * Tutorial shows only when:
 * 1. A brand-new signup sets status to `pending`, or
 * 2. The user clicks an explicit Learn more / tour CTA.
 *
 * Missing localStorage must NOT auto-open the tutorial for returning users
 * (new browser, cleared storage, etc.).
 */

export function onboardingKey(userId) {
  return `laro_onboarding_${userId}`;
}

export function guidedTourKey(userId) {
  return `laro_guided_tour_${userId}`;
}

const FIND_AGAIN_TOAST_SESSION = 'laro_onboarding_find_again_toasted';

/** Toast at most once per browser tab/session. */
export function notifyFindAgainOnce(message) {
  try {
    if (sessionStorage.getItem(FIND_AGAIN_TOAST_SESSION) === '1') return false;
    sessionStorage.setItem(FIND_AGAIN_TOAST_SESSION, '1');
  } catch {
    /* private mode — still toast */
  }
  return true;
}

/** True when signup (or Learn more) queued the kitchen invite. */
export function isOnboardingPending(userId) {
  if (!userId) return false;
  return localStorage.getItem(onboardingKey(userId)) === 'pending';
}

/** Mark that signup just finished — UserOnboarding will soft-invite once. */
export function markOnboardingPending(userId) {
  if (!userId) return;
  localStorage.setItem(onboardingKey(userId), 'pending');
}

/** Open the kitchen setup invite (same flow as post-signup). */
export function requestOnboarding(userId) {
  if (!userId) return;
  localStorage.setItem(onboardingKey(userId), 'pending');
  window.dispatchEvent(new CustomEvent('laro-start-onboarding'));
}

/** Start the in-app guided tour only (no preference wizard). */
export function requestAppTour(userId) {
  if (!userId) return;
  localStorage.setItem(guidedTourKey(userId), 'pending');
  window.dispatchEvent(new CustomEvent('laro-start-guided-tour'));
}
