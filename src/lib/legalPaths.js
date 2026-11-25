/** Quiet legal pages: no cookie banner, PWA install, onboarding, or tour. */
export function isQuietLegalPath(pathname = '') {
  const path = String(pathname || '').replace(/\/+$/, '') || '/';
  return path === '/privacy-policy' || path === '/terms' || path === '/terms-of-service';
}

export const LEGAL_PRIVACY_HREF = '/privacy-policy';
export const LEGAL_TERMS_HREF = '/terms';
export const LEGAL_PRIVACY_URL = 'https://laro.food/privacy-policy';
export const LEGAL_TERMS_URL = 'https://laro.food/terms';
