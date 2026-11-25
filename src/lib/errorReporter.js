// Sends web-app crashes to the server error log (backend/services/error_log.py)
// so they show in Admin → Errors and the owner's alert emails.

const sentThisSession = new Set();
const MAX_PER_SESSION = 20;

// Browser noise that is not a Laro bug
const IGNORE = [
  /ResizeObserver loop/i,
  /_AutofillCallbackHandler/, // Facebook/Instagram in-app browser on iOS
  /^Script error\.?$/i,
  /Non-Error promise rejection captured/i,
  /extension:\/\//i,
  // Injected by in-app browsers (Facebook, Instagram, Chrome on iOS), not our code
  /_AutofillCallbackHandler/,
  /__gCrWeb/,
  /webkit\.messageHandlers/i,
];

function endpoint() {
  let serverUrl = '';
  try {
    serverUrl = localStorage.getItem('laro_server_url') || '';
  } catch {
    /* ignore */
  }
  serverUrl = serverUrl || process.env.REACT_APP_BACKEND_URL || '';
  return serverUrl ? `${serverUrl.replace(/\/+$/, '')}/api/errors/client` : 'api/errors/client';
}

export function reportError(error, extra = {}) {
  try {
    const message = String(error?.message || error || 'Unknown error').slice(0, 2000);
    if (IGNORE.some((re) => re.test(message))) return;
    const key = `${message}|${extra.page || window.location.hash}`;
    if (sentThisSession.has(key) || sentThisSession.size >= MAX_PER_SESSION) return;
    sentThisSession.add(key);

    let token = null;
    try {
      token = localStorage.getItem('token');
    } catch {
      /* ignore */
    }
    const body = {
      message,
      error_type: String(error?.name || 'Error').slice(0, 200),
      stack: String(error?.stack || '').slice(0, 6000) || null,
      component_stack: extra.componentStack ? String(extra.componentStack).slice(0, 4000) : null,
      page: String(extra.page || window.location.hash || window.location.pathname).slice(0, 500),
      app_version: String(process.env.REACT_APP_VERSION || '').slice(0, 40) || null,
    };
    fetch(endpoint(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* reporting must never throw */
  }
}

export function installErrorReporter() {
  if (typeof window === 'undefined' || window.__laroErrorReporter) return;
  window.__laroErrorReporter = true;
  window.addEventListener('error', (event) => {
    reportError(event.error || event.message);
  });
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason;
    // Axios errors are API problems already logged server-side (or expected 4xx)
    if (reason?.isAxiosError || reason?.response) return;
    reportError(reason);
  });
}
