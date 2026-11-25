/**
 * What this ACCOUNT has already been shown (onboarding, guided tour, what's new).
 *
 * Stored on the server (users.ui_seen) so each one shows once per account, not once
 * per browser or device. localStorage stays as a fast local hint.
 * Automatic popups check getSeen(); explicit "Learn more" / tour buttons bypass it.
 */
import api from './api';

const cache = new Map(); // userId -> Promise<object>

export function getSeen(userId) {
  if (!userId) return Promise.resolve({});
  if (!cache.has(userId)) {
    const p = api
      .get('/me/seen')
      .then((res) => res.data?.seen || {})
      .catch(() => {
        cache.delete(userId); // try again next time; don't block the UI
        return {};
      });
    cache.set(userId, p);
  }
  return cache.get(userId);
}

export function markSeen(userId, key, value = 'yes') {
  if (!userId) return Promise.resolve();
  const prev = cache.get(userId) || Promise.resolve({});
  cache.set(userId, prev.then((seen) => ({ ...seen, [key]: value })));
  return api.post('/me/seen', { key, value }).catch(() => {});
}
