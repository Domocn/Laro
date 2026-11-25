/**
 * One popup at a time.
 *
 * Every sign-in / app-wide popup asks for its turn with usePopupTurn(id, wants).
 * Only the highest-priority popup that currently wants to show gets `true`;
 * the rest wait (they keep their own state) and appear when it closes.
 */
import { useEffect, useSyncExternalStore } from 'react';

// Lower number = more important. Required prompts first, nice-to-haves last.
const PRIORITY = {
  'password-change': 1,
  'name-update': 2,
  onboarding: 3,
  'guided-tour': 4,
  'whats-new': 5,
  'cookie-consent': 6,
  'install-prompt': 7,
};

const wanting = new Set();
const listeners = new Set();
let active = null;

function recompute() {
  let best = null;
  wanting.forEach((id) => {
    if (best === null || (PRIORITY[id] ?? 99) < (PRIORITY[best] ?? 99)) best = id;
  });
  if (best !== active) {
    active = best;
    listeners.forEach((fn) => fn());
  }
}

function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

const getActive = () => active;

/** True only when this popup wants to show and nothing more important does. */
export function usePopupTurn(id, wants) {
  useEffect(() => {
    if (!wants) return undefined;
    wanting.add(id);
    recompute();
    return () => {
      wanting.delete(id);
      recompute();
    };
  }, [id, wants]);
  const current = useSyncExternalStore(subscribe, getActive, getActive);
  return Boolean(wants) && current === id;
}
