/**
 * Optional RevenueCat Web Billing (purchases-js).
 * Requires a Web Billing public API key (rcb_…), not the Play goog_ key.
 * When unset, the UI still shows Pro status from the Laro backend (RC webhooks).
 */
const ENTITLEMENT_PRO = 'Laro Pro';

// Runtime inject via docker-entrypoint.sh (must match placeholder string exactly)
const RUNTIME_RC_WEB_KEY = '%REACT_APP_REVENUECAT_WEB_API_KEY%';

function resolveWebApiKey() {
  const fromEnv = (process.env.REACT_APP_REVENUECAT_WEB_API_KEY || '').trim();
  if (fromEnv && !fromEnv.startsWith('%')) return fromEnv;
  if (
    typeof RUNTIME_RC_WEB_KEY === 'string' &&
    RUNTIME_RC_WEB_KEY &&
    !RUNTIME_RC_WEB_KEY.startsWith('%')
  ) {
    return RUNTIME_RC_WEB_KEY.trim();
  }
  try {
    const fromLs = localStorage.getItem('laro_revenuecat_web_api_key');
    if (fromLs) return fromLs.trim();
  } catch {
    /* ignore */
  }
  return '';
}

let purchasesInstance = null;
let configurePromise = null;
let configuredAppUserId = null;

export function isRevenueCatWebConfigured() {
  const key = resolveWebApiKey();
  return Boolean(key && (key.startsWith('rcb_') || key.startsWith('rcb_sb_')));
}

function requireAppUserId(appUserId) {
  const id = String(appUserId || '').trim();
  if (!id || id.startsWith('anon_')) {
    throw new Error('Sign in to subscribe on the web');
  }
  return id;
}

/**
 * Configure (or re-identify) Purchases for the logged-in Laro user id.
 * Never falls back to anonymous checkout — Pro must bind to the account.
 */
export async function getRevenueCatPurchases(appUserId) {
  if (!isRevenueCatWebConfigured()) return null;
  const userId = requireAppUserId(appUserId);

  if (purchasesInstance && configuredAppUserId === userId) {
    return purchasesInstance;
  }

  if (purchasesInstance && configuredAppUserId && configuredAppUserId !== userId) {
    try {
      await purchasesInstance.changeUser(userId);
      configuredAppUserId = userId;
      return purchasesInstance;
    } catch (err) {
      console.warn('RevenueCat changeUser failed; reconfiguring', err);
      purchasesInstance = null;
      configurePromise = null;
      configuredAppUserId = null;
    }
  }

  if (configurePromise) return configurePromise;

  configurePromise = (async () => {
    const mod = await import('@revenuecat/purchases-js');
    const Purchases = mod.Purchases || mod.default;
    const apiKey = resolveWebApiKey();
    purchasesInstance = Purchases.configure({
      apiKey,
      appUserId: userId,
    });
    configuredAppUserId = userId;
    try {
      if (typeof purchasesInstance.preload === 'function') {
        await purchasesInstance.preload();
      }
    } catch {
      /* preload is optional */
    }
    return purchasesInstance;
  })().catch((err) => {
    configurePromise = null;
    purchasesInstance = null;
    configuredAppUserId = null;
    throw err;
  });

  return configurePromise;
}

export async function fetchRevenueCatProStatus(appUserId) {
  const purchases = await getRevenueCatPurchases(appUserId);
  if (!purchases) return null;
  const info = await purchases.getCustomerInfo();
  const active = info?.entitlements?.active || {};
  const ent = active[ENTITLEMENT_PRO];
  return {
    isPro: Boolean(ent),
    entitlementId: ENTITLEMENT_PRO,
    activeEntitlements: Object.keys(active),
    managementURL: info?.managementURL || null,
    customerInfo: info,
  };
}

/**
 * True when the current offering has at least one package the Web Billing SDK can sell.
 */
export async function hasWebBillingPackages(appUserId) {
  const purchases = await getRevenueCatPurchases(appUserId);
  if (!purchases || typeof purchases.getOfferings !== 'function') return false;
  const offerings = await purchases.getOfferings();
  const pkgs = offerings?.current?.availablePackages || [];
  return pkgs.length > 0;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Poll CustomerInfo until Laro Pro is active (webhook / RC indexing lag).
 */
export async function waitForRevenueCatPro(appUserId, { attempts = 8, delayMs = 750 } = {}) {
  let last = null;
  for (let i = 0; i < attempts; i += 1) {
    last = await fetchRevenueCatProStatus(appUserId);
    if (last?.isPro) return last;
    await sleep(delayMs);
  }
  return last;
}

/**
 * Present RevenueCat-managed paywall when Web Billing is configured.
 * @returns {{ purchased: boolean, status?: object, cancelled?: boolean, noPackages?: boolean } | null}
 */
export async function presentRevenueCatPaywall(appUserId, customerEmail) {
  const purchases = await getRevenueCatPurchases(appUserId);
  if (!purchases || typeof purchases.presentPaywall !== 'function') {
    return null;
  }

  const hasPkgs = await hasWebBillingPackages(appUserId);
  if (!hasPkgs) {
    return { purchased: false, noPackages: true };
  }

  try {
    const result = await purchases.presentPaywall({
      customerEmail: customerEmail || undefined,
    });
    const status = await waitForRevenueCatPro(appUserId);
    const purchased =
      Boolean(status?.isPro) ||
      Boolean(result?.customerInfo?.entitlements?.active?.[ENTITLEMENT_PRO]);
    return { purchased, status, result };
  } catch (err) {
    const code = err?.errorCode ?? err?.code;
    const msg = String(err?.message || '').toLowerCase();
    const cancelled =
      code === 1 ||
      code === 'UserCancelledError' ||
      msg.includes('cancel') ||
      msg.includes('dismiss');
    if (cancelled) {
      return { purchased: false, cancelled: true };
    }
    throw err;
  }
}

export { ENTITLEMENT_PRO };
