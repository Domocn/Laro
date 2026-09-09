/**
 * Google Cast (Chromecast) helpers for Cook Mode.
 *
 * Custom receiver: /cast/receiver.html
 * Namespace: urn:x-cast:food.laro.cook
 *
 * Requires REACT_APP_CAST_APP_ID (Cast Developer Console → Custom Web Receiver
 * pointing at https://<your-host>/cast/receiver.html).
 */

export const CAST_NAMESPACE = 'urn:x-cast:food.laro.cook';

const RUNTIME_CAST_APP_ID = '%REACT_APP_CAST_APP_ID%';

export function getCastAppId() {
  const runtime = String(RUNTIME_CAST_APP_ID || '').trim();
  if (runtime && !runtime.includes('%REACT_APP_')) return runtime;
  const fromEnv = String(process.env.REACT_APP_CAST_APP_ID || '').trim();
  if (fromEnv) return fromEnv;
  try {
    return String(localStorage.getItem('laro_cast_app_id') || '').trim();
  } catch {
    return '';
  }
}

export function isCastConfigured() {
  return Boolean(getCastAppId());
}

let sdkLoadPromise = null;

export function loadCastSdk() {
  if (typeof window === 'undefined') return Promise.reject(new Error('no window'));
  if (window.cast?.framework) return Promise.resolve();
  if (sdkLoadPromise) return sdkLoadPromise;

  sdkLoadPromise = new Promise((resolve, reject) => {
    window['__onGCastApiAvailable'] = (isAvailable) => {
      if (isAvailable) resolve();
      else reject(new Error('Cast API unavailable'));
    };
    const existing = document.querySelector('script[data-laro-cast-sdk]');
    if (existing) return;
    const script = document.createElement('script');
    script.src = 'https://www.gstatic.com/cv/js/sender/v1/cast_sender.js?loadCastFramework=1';
    script.async = true;
    script.dataset.laroCastSdk = '1';
    script.onerror = () => reject(new Error('Failed to load Cast SDK'));
    document.head.appendChild(script);
  });

  return sdkLoadPromise;
}

export async function initCastContext() {
  const appId = getCastAppId();
  if (!appId) throw new Error('Cast App ID not configured');
  await loadCastSdk();
  const context = window.cast.framework.CastContext.getInstance();
  context.setOptions({
    receiverApplicationId: appId,
    autoJoinPolicy: window.chrome.cast.AutoJoinPolicy.ORIGIN_SCOPED,
    resumeSavedSession: true,
  });
  return context;
}

export function getCastSession() {
  try {
    return window.cast?.framework?.CastContext?.getInstance()?.getCurrentSession() || null;
  } catch {
    return null;
  }
}

export function sendCookCastMessage(message) {
  const session = getCastSession();
  if (!session || !message) return Promise.resolve(false);
  return session
    .sendMessage(CAST_NAMESPACE, message)
    .then(() => true)
    .catch((err) => {
      console.warn('Cast send failed', err);
      return false;
    });
}

export function buildShowMessage({ title, steps, stepIndex, timerLabel }) {
  return {
    type: 'show',
    title: title || '',
    steps: Array.isArray(steps) ? steps : [],
    stepIndex: stepIndex || 0,
    timerLabel: timerLabel || '',
  };
}

export function buildSetStepMessage(stepIndex, timerLabel = '') {
  return {
    type: 'set_step',
    stepIndex,
    timerLabel: timerLabel || '',
  };
}
