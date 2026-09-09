import { useCallback, useEffect, useState } from 'react';
import { preferencesApi } from '../lib/api';

/** Module cache so Settings, Meal Planner, Recipes, etc. share one fetch. */
let cache = null;
let inflight = null;

export function invalidateUserPreferencesCache() {
  cache = null;
}

/**
 * Load /preferences with a short-lived in-memory cache.
 * Returns defaults-friendly empty object when unauthenticated or offline.
 */
export function useUserPreferences() {
  const [preferences, setPreferences] = useState(cache || {});
  const [loading, setLoading] = useState(!cache);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      if (!inflight) {
        inflight = preferencesApi
          .get()
          .then((res) => {
            cache = res.data || {};
            return cache;
          })
          .finally(() => {
            inflight = null;
          });
      }
      const data = await inflight;
      setPreferences(data || {});
      return data || {};
    } catch {
      setPreferences(cache || {});
      return cache || {};
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (cache) {
        setPreferences(cache);
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        if (!inflight) {
          inflight = preferencesApi
            .get()
            .then((res) => {
              cache = res.data || {};
              return cache;
            })
            .finally(() => {
              inflight = null;
            });
        }
        const data = await inflight;
        if (!cancelled) setPreferences(data || {});
      } catch {
        if (!cancelled) setPreferences({});
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { preferences, loading, refresh };
}

/** Map preference string → date-fns weekStartsOn (0=Sun … 6=Sat). */
export function weekStartsOnNumber(value, fallback = 1) {
  const map = { sunday: 0, monday: 1, tuesday: 2, wednesday: 3, thursday: 4, friday: 5, saturday: 6 };
  if (typeof value === 'number' && value >= 0 && value <= 6) return value;
  const key = String(value || '').toLowerCase();
  return key in map ? map[key] : fallback;
}
