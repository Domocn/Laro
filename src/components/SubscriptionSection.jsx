import React, { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Check,
  Crown,
  ExternalLink,
  Loader2,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { toast } from 'sonner';
import { Button } from './ui/button';
import { subscriptionsApi, aiApi, rewardsApi } from '../lib/api';
import { Link } from 'react-router-dom';
import {
  isLemonSqueezyBilling,
  loadBillingConfig,
  openLemonSqueezyCustomerPortal,
  startLemonSqueezyCheckout,
} from '../lib/billing';
import { useLanguage } from '../context/LanguageContext';
import { RewardStore } from './RewardStore';

/** Shared Laro Pro benefit lines (food-first). */
export const LARO_PRO_OFFERING_BENEFITS = [
  'Unlimited AI meal plans & recipe imports',
  'Scan recipes from photos and video',
  'Unlimited cookbook — no recipe caps',
  'Barcode product lookup while shopping',
  'Household kitchen sharing with friends',
  'AI cooking assistant while you cook',
];

/**
 * Laro Pro panel (Settings). Checkout via Lemon Squeezy; status from Laro backend
 * (LS webhooks + owner forever). Legacy RevenueCat/Play subs still sync via RC webhook.
 */
export function SubscriptionSection({ userId, userEmail, user }) {
  const { t } = useLanguage();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [purchasing, setPurchasing] = useState(false);
  const [status, setStatus] = useState(null);
  const [quota, setQuota] = useState(null);
  const [statusFailed, setStatusFailed] = useState(false);
  const [freeLimits, setFreeLimits] = useState(null);
  const [billingConfig, setBillingConfig] = useState(null);
  const [checkoutPlan, setCheckoutPlan] = useState('monthly');
  const lemonBilling = isLemonSqueezyBilling(billingConfig);
  const billingConfigured = Boolean(billingConfig?.configured !== false && lemonBilling);

  const load = useCallback(async () => {
    try {
      const [subRes, quotaRes, catalogRes, billCfg] = await Promise.all([
        subscriptionsApi.getStatus().catch(() => null),
        aiApi.quota().catch(() => null),
        rewardsApi.catalog().catch(() => null),
        loadBillingConfig(),
      ]);
      setBillingConfig(billCfg);
      if (billCfg?.plans?.length === 1) {
        setCheckoutPlan(billCfg.plans[0].id);
      }
      if (subRes?.data) {
        setStatus(subRes.data);
        setStatusFailed(false);
      } else {
        setStatusFailed(true);
      }
      if (quotaRes?.data) setQuota(quotaRes.data);
      if (catalogRes?.data?.limits) setFreeLimits(catalogRes.data.limits);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const authIsOwner = Boolean(user?.is_owner);
  const authIsPro = Boolean(
    user?.is_pro || user?.is_owner || user?.subscription_active
  );
  const authIsLifetime = Boolean(user?.is_lifetime || user?.is_owner);

  const isPro =
    Boolean(status?.is_active) ||
    Boolean(status?.is_owner) ||
    (statusFailed && authIsPro);
  const isLifetime =
    Boolean(status?.is_lifetime || status?.is_owner) ||
    (statusFailed && authIsLifetime);
  const isOwner = Boolean(status?.is_owner) || (statusFailed && authIsOwner);
  const planLabel = isOwner
    ? 'Owner · Lifetime'
    : isLifetime
      ? 'Lifetime Pro'
      : isPro
        ? String(status?.status || user?.subscription_status || 'premium').replace(
            /^\w/,
            (c) => c.toUpperCase()
          )
        : null;

  const handleRefresh = async () => {
    setRefreshing(true);
    await load();
    toast.success('Subscription status refreshed');
  };

  const handleUpgradeWeb = async () => {
    if (!userId) {
      toast.error(t('signInToSubscribe'));
      return;
    }
    if (!billingConfigured) {
      toast.error(t('webBillingKeyNeededHint'));
      return;
    }
    setPurchasing(true);
    try {
      await startLemonSqueezyCheckout(checkoutPlan);
    } catch (e) {
      console.error(e);
      toast.error(e?.response?.data?.detail || e?.message || t('webCheckoutUnavailableHint'));
    } finally {
      setPurchasing(false);
    }
  };

  const handleManage = async () => {
    const source = (status?.source || user?.subscription_source || '').toLowerCase();
    if (source === 'lemonsqueezy' || lemonBilling) {
      try {
        await openLemonSqueezyCustomerPortal();
        return;
      } catch {
        toast.message(t('manageBillingNoPortalHint'));
        return;
      }
    }
    if (source === 'revenuecat') {
      toast.message(t('manageBillingLegacyRevenueCatHint'));
      return;
    }
    toast.message(t('manageBillingNoPortalHint'));
  };

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.11 }}
      className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
      data-testid="subscription-section"
    >
      <div className="p-4 border-b border-border/60 bg-gradient-to-br from-laro/10 via-cream-subtle to-cream-subtle dark:from-laro/15 dark:via-muted/40 dark:to-muted/40">
        <h2 className="font-heading font-semibold flex items-center gap-2">
          <Crown className="w-5 h-5 text-laro" />
          Laro Pro
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          {t('laroProSectionSubtitle')}
        </p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {t('laroProSyncedHint')}
        </p>
      </div>

      <div className="p-4 space-y-4">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading subscription…
          </div>
        ) : (
          <>
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                      isPro
                        ? 'bg-laro/15 text-laro'
                        : 'bg-muted text-muted-foreground'
                    }`}
                    data-testid="subscription-badge"
                  >
                    {isPro ? 'Pro' : 'Free'}
                  </span>
                  {planLabel && (
                    <span className="text-sm font-medium">{planLabel}</span>
                  )}
                </div>
                {userEmail && (
                  <p className="text-xs text-muted-foreground mt-1">{userEmail}</p>
                )}
                {((status?.source || (statusFailed && user?.subscription_source)) || isOwner) && (
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Source: {status?.source || user?.subscription_source || (isOwner ? 'owner' : '—')}
                    {(status?.expires_at || user?.subscription_expires) && !isLifetime
                      ? ` · expires ${new Date(status?.expires_at || user?.subscription_expires).toLocaleDateString()}`
                      : isLifetime
                        ? ' · never expires'
                        : ''}
                  </p>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                disabled={refreshing}
                aria-label="Refresh subscription"
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              </Button>
            </div>

            <ul className="space-y-1.5 text-sm text-muted-foreground">
              {LARO_PRO_OFFERING_BENEFITS.map((line) => (
                <li key={line} className="flex items-start gap-2">
                  <Check className="w-4 h-4 text-laro shrink-0 mt-0.5" />
                  <span>{line}</span>
                </li>
              ))}
            </ul>

            {quota && (
              <p className="text-xs text-muted-foreground" data-testid="ai-quota-line">
                {quota.unlimited || quota.premium ? (
                  <span className="text-laro font-medium flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5" />
                    Unlimited AI on this account
                  </span>
                ) : (
                  <>
                    Free AI: {quota.remaining ?? 0} of {quota.limit ?? 3} uses left
                    {quota.bonus ? ` (includes +${quota.bonus} bonus)` : ''}
                  </>
                )}
              </p>
            )}

            {!isPro && (
              <div
                className="rounded-xl bg-cream-subtle border border-border/50 p-3 space-y-1.5"
                data-testid="free-plan-limits"
              >
                <p className="text-sm font-medium text-foreground">Free plan includes</p>
                <ul className="text-xs text-muted-foreground space-y-1">
                  <li>
                    {freeLimits?.recipes ?? 15} recipes
                    {freeLimits?.free_defaults?.recipes && freeLimits.recipes > freeLimits.free_defaults.recipes
                      ? ` (base ${freeLimits.free_defaults.recipes} + bonuses)`
                      : ''}
                  </li>
                  <li>{freeLimits?.ai_base ?? 3} AI uses (lifetime)</li>
                  <li>{freeLimits?.friends ?? 3} friends</li>
                  <li>{freeLimits?.shares_weekly ?? 5} recipe shares / week</li>
                  <li>{freeLimits?.cookbooks ?? 3} cookbooks</li>
                  <li>{freeLimits?.household_members ?? 2} household members</li>
                </ul>
                <p className="text-xs text-muted-foreground pt-1">
                  Earn points by referring friends — redeem below or invite on{' '}
                  <Link to="/friends" className="text-laro hover:underline font-medium">
                    Friends
                  </Link>
                </p>
              </div>
            )}

            <RewardStore />

            {!isPro && lemonBilling && billingConfig.plans.length > 1 && (
              <div className="flex flex-wrap gap-2" role="group" aria-label="Billing period">
                {billingConfig.plans.map((plan) => (
                  <Button
                    key={plan.id}
                    type="button"
                    size="sm"
                    variant={checkoutPlan === plan.id ? 'default' : 'outline'}
                    className="rounded-full"
                    onClick={() => setCheckoutPlan(plan.id)}
                  >
                    {plan.label}
                  </Button>
                ))}
              </div>
            )}

            <div className="flex flex-wrap gap-2 pt-1">
              {!isPro && (
                <Button
                  onClick={handleUpgradeWeb}
                  disabled={purchasing || !billingConfigured}
                  className="rounded-full bg-laro hover:bg-laro-dark"
                  data-testid="upgrade-pro-btn"
                >
                  {purchasing ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Crown className="w-4 h-4 mr-2" />
                  )}
                  {t('unlockLaroPro')}
                </Button>
              )}
              {isPro && (
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={handleManage}
                  data-testid="manage-sub-btn"
                >
                  <ExternalLink className="w-4 h-4 mr-2" />
                  {t('manageBilling')}
                </Button>
              )}
            </div>
          </>
        )}
      </div>
    </motion.section>
  );
}

export default SubscriptionSection;
