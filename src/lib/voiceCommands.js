/**
 * Shared cook-mode voice command matching (web + keep in sync with Android).
 * Source of truth phrases also live in backend/routers/voice_cooking.py.
 */

export const HANDS_FREE_STORAGE_KEY = 'laro_cook_hands_free';

export function getHandsFreePreference() {
  try {
    return localStorage.getItem(HANDS_FREE_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

export function setHandsFreePreference(on) {
  try {
    localStorage.setItem(HANDS_FREE_STORAGE_KEY, on ? '1' : '0');
  } catch {
    /* ignore */
  }
}

export function matchLocalVoiceCommand(transcript) {
  const text = String(transcript || '').toLowerCase().trim();
  if (!text) return null;

  const rules = [
    {
      action: { type: 'navigate', direction: 'next' },
      phrases: ['nexty', 'next step', 'next please', 'next', 'continue', 'go on', 'forward', 'nexte', 'skip'],
    },
    {
      action: { type: 'navigate', direction: 'previous' },
      phrases: ['previous', 'go back', 'last step', 'back'],
    },
    {
      action: { type: 'repeat' },
      phrases: ['repeat', 'say again', 'what was that', 'again'],
    },
    {
      action: { type: 'show_ingredients' },
      phrases: ['ingredients', 'what do i need', 'show ingredients'],
    },
    {
      action: { type: 'timer', operation: 'start' },
      phrases: ['start timer', 'set timer', 'timer on'],
    },
    {
      action: { type: 'timer', operation: 'stop' },
      phrases: ['stop timer', 'cancel timer', 'timer off'],
    },
    {
      action: { type: 'help' },
      phrases: ['help', 'commands', 'what can i say'],
    },
  ];

  for (const rule of rules) {
    const sorted = [...rule.phrases].sort((a, b) => b.length - a.length);
    for (const phrase of sorted) {
      if (text.includes(phrase)) return rule.action;
    }
  }
  return null;
}
