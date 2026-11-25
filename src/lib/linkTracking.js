// Works out where a visit came from (backend/services/link_tracking.py) and remembers the
// first one so a later sign-up is credited to it. No personal data: just a source label.
//
// Trackable links: laro.food/?s=whatsapp  or  ?utm_source=instagram&utm_campaign=walks
// Promo / friend links (?ref=CIRCLEUP) count as code:CIRCLEUP.

const FIRST_KEY = 'laro_first_source';
const SESSION_KEY = 'laro_visit_sent';

const IN_APP = [
  [/instagram/i, 'instagram'],
  [/FBAN|FBAV|FB_IAB/, 'facebook'],
  [/musical_ly|BytedanceWebview/i, 'tiktok'],
  [/snapchat/i, 'snapchat'],
  [/LinkedInApp/i, 'linkedin'],
  [/Twitter/i, 'x'],
  [/Pinterest/i, 'pinterest'],
  [/WhatsApp/i, 'whatsapp'],
];

const REFERRERS = [
  [/(^|\.)google\./, 'google'],
  [/(^|\.)bing\.com$/, 'bing'],
  [/duckduckgo\.com$/, 'duckduckgo'],
  [/(^|\.)instagram\.com$/, 'instagram'],
  [/(^|\.)(facebook\.com|fb\.com)$|^l\.facebook\.com$|^lm\.facebook\.com$/, 'facebook'],
  [/(^|\.)whatsapp\.com$|^wa\.me$/, 'whatsapp'],
  [/(^|\.)t\.co$|(^|\.)x\.com$|twitter\.com$/, 'x'],
  [/(^|\.)tiktok\.com$/, 'tiktok'],
  [/(^|\.)reddit\.com$/, 'reddit'],
  [/(^|\.)linkedin\.com$|^lnkd\.in$/, 'linkedin'],
  [/play\.google\.com$/, 'play-store'],
  [/(^|\.)github\.com$/, 'github'],
];

function allParams() {
  const params = new URLSearchParams(window.location.search);
  const hash = window.location.hash || '';
  const q = hash.indexOf('?');
  if (q >= 0) {
    new URLSearchParams(hash.slice(q + 1)).forEach((v, k) => {
      if (!params.has(k)) params.set(k, v);
    });
  }
  return params;
}

function referrerHost() {
  try {
    let ref = document.referrer;
    try {
      ref = sessionStorage.getItem('laro_entry_referrer') || ref;
    } catch {
      /* ignore */
    }
    if (!ref) return '';
    const host = new URL(ref).hostname.toLowerCase();
    return host === window.location.hostname ? '' : host;
  } catch {
    return '';
  }
}

export function detectSource() {
  const params = allParams();
  const host = referrerHost();
  const tagged = params.get('s') || params.get('utm_source') || params.get('src');
  const code = (params.get('ref') || params.get('referral') || '').trim();
  let source = '';
  if (tagged) source = tagged.trim().toLowerCase();
  else if (code) source = `code:${code.toUpperCase()}`;
  else {
    const ua = navigator.userAgent || '';
    const inApp = IN_APP.find(([re]) => re.test(ua));
    if (inApp) source = inApp[1];
    else if (host) {
      const known = REFERRERS.find(([re]) => re.test(host));
      source = known ? known[1] : host.replace(/^www\./, '');
    }
  }
  return {
    source: (source || 'direct').slice(0, 100),
    campaign: (params.get('c') || params.get('utm_campaign') || '').slice(0, 100) || null,
    referrer_host: host || null,
  };
}

/** Source to credit a new sign-up with: the first real (non-direct) visit, else this one. */
export function signupSource() {
  try {
    return localStorage.getItem(FIRST_KEY) || detectSource().source;
  } catch {
    return detectSource().source;
  }
}

function endpoint() {
  let serverUrl = '';
  try {
    serverUrl = localStorage.getItem('laro_server_url') || '';
  } catch {
    /* ignore */
  }
  serverUrl = serverUrl || process.env.REACT_APP_BACKEND_URL || '';
  return serverUrl ? `${serverUrl.replace(/\/+$/, '')}/api/track/visit` : 'api/track/visit';
}

export function trackVisit() {
  try {
    if (typeof window === 'undefined') return;
    // Signed-in people opening the app are not new visits
    if (localStorage.getItem('token')) return;
    if (sessionStorage.getItem(SESSION_KEY)) return;
    sessionStorage.setItem(SESSION_KEY, '1');

    const visit = detectSource();
    if (visit.source !== 'direct' && !localStorage.getItem(FIRST_KEY)) {
      localStorage.setItem(FIRST_KEY, visit.source);
    }
    const hash = (window.location.hash || '').replace(/^#/, '').split('?')[0];
    const landing = (hash || window.location.pathname || '/').slice(0, 200);
    fetch(endpoint(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...visit, landing }),
      keepalive: true,
    }).catch(() => {});
  } catch {
    /* tracking must never break the page */
  }
}
