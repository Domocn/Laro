/**
 * Laro Pro checkout — Lemon Squeezy (server-created checkout URLs).
 */
import { subscriptionsApi } from './api';

export async function loadBillingConfig() {
  try {
    const res = await subscriptionsApi.getBillingConfig();
    return res?.data || { provider: 'lemonsqueezy', plans: [], configured: false };
  } catch {
    return { provider: 'lemonsqueezy', plans: [], configured: false };
  }
}

export function isLemonSqueezyBilling(config) {
  return (
    config?.provider === 'lemonsqueezy'
    && Array.isArray(config.plans)
    && config.plans.length > 0
  );
}

export async function startLemonSqueezyCheckout(plan = 'monthly') {
  const res = await subscriptionsApi.createCheckout({ plan });
  const url = res?.data?.url;
  if (!url) {
    throw new Error('Checkout URL missing');
  }
  window.location.assign(url);
}

export async function openLemonSqueezyCustomerPortal() {
  const res = await subscriptionsApi.getCustomerPortal();
  const url = res?.data?.url;
  if (!url) {
    throw new Error('Billing portal unavailable');
  }
  window.open(url, '_blank', 'noopener,noreferrer');
}
