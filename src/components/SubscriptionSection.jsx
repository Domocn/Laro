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
  fetchRevenueCatProStatus,
  hasWebBillingPackages,
  isRevenueCatWebConfigured,
  presentRevenueCatPaywall,
} from '../lib/revenueCat';
import { useLanguage } from '../context/LanguageContext';
import { RewardStore } from './RewardStore';

const PLAY_STORE_URL =
  'https://play.google.com/store/apps/details?id=com.laro.app';

/** Shared Laro Pro benefit lines (food-first; mirrors Android paywall). */
export const LARO_PRO_OFFERING_BENEFITS = [
  'Unlimited AI meal plans & recipe imports',
  'Scan recipes from photos and video',
  'Unlimited cookbook — no recipe caps',
  'Barcode product lookup while shopping',
  'Household kitchen sharing with friends',
  'AI cooking assistant while you cook',
];

/**
 * Laro Pro / RevenueCat subscription panel for the web Settings page.
 * Status comes from the Laro backend (synced via RC webhooks + owner forever).
 * Falls back to auth user Pro flags when /subscriptions/status is briefly unavailable
 * so owner/Pro accounts never flash as Free after login.
 * Optional Web Billing paywall when REACT_APP_REVENUECAT_WEB_API_KEY (rcb_…) is set.
 */
export function SubscriptionSection({ userId, userEmail, user }) {
  const { t } = useLanguage();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [purchasing, setPurchasing] = useState(false);
  const [status, setStatus] = useState(null);
  const [quota, setQuota] = useState(null);
  const [rcStatus, setRcStatus] = useState(null);
  const [webPackagesReady, setWebPackagesReady] = useState(null);
  const [statusFailed, setStatusFailed] = useState(false);
  const [freeLimits, setFreeLimits] = useState(null);
  const webBilling = isRevenueCatWebConfigured();

  const load = useCallback(async () => {
    try {
      const [subRes, quotaRes, catalogRes] = await Promise.all([
        subscriptionsApi.getStatus().catch(() => null),
        aiApi.quota().catch(() => null),
        rewardsApi.catalog().catch(() => null),
      ]);
      if (subRes?.data) {
        setStatus(subRes.data);
        setStatusFailed(false);
      } else {
        setStatusFailed(true);
      }
      if (quotaRes?.data) setQuota(quotaRes.data);
      if (catalogRes?.data?.limits) setFreeLimits(catalogRes.data.limits);
      if (catalogRes?.data?.bonuses) {
        /* keep for future; limits already include bonuses */
      }

      if (webBilling && userId) {
        try {
          const [rc, pkgs] = await Promise.all([
            fetchRevenueCatProStatus(userId),
            hasWebBillingPackages(userId).catch(() => false),
          ]);
          setRcStatus(rc);
          setWebPackagesReady(Boolean(pkgs));
        } catch (e) {
          console.warn('RevenueCat web status failed:', e);
          setRcStatus(null);
          setWebPackagesReady(false);
        }
      } else {
        setWebPackagesReady(null);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [userId, webBilling]);

  useEffect(() => {
    load();
  }, [load]);

  // Auth payload Pro flags (login /auth/me) — seamless fallback when status endpoint fails
  const authIsOwner = Boolean(user?.is_owner);
  const authIsPro = Boolean(
    user?.is_pro || user?.is_owner || user?.subscription_active
  );
  const authIsLifetime = Boolean(user?.is_lifetime || user?.is_owner);

  const isPro =
    Boolean(status?.is_active) ||
    Boolean(status?.is_owner) ||
    Boolean(rcStatus?.isPro) ||
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

  const pollBackendPro = async () => {
    for (let i = 0; i < 6; i += 1) {
      try {
        const res = await subscriptionsApi.getStatus();
        if (res?.data?.is_active || res?.data?.is_owner) return res.data;
      } catch (_) { /* retry */ }
      await new Promise((r) => setTimeout(r, 800));
    }
    return null;
  };

  const handleUpgradeWeb = async () => {
    if (!webBilling || webPackagesReady === false) {
      window.open(PLAY_STORE_URL, '_blank', 'noopener,noreferrer');
      return;
    }
    if (!userId) {
      toast.error('Sign in to unlock Laro Pro on the web');
      return;
    }
    setPurchasing(true);
    try {
      const result = await presentRevenueCatPaywall(userId, userEmail);
      if (result == null) {
        toast.message('Web checkout is not available yet — open Laro on Android to subscribe.');
        window.open(PLAY_STORE_URL, '_blank', 'noopener,noreferrer');
        return;
      }
      if (result.noPackages) {
        toast.message(
          'Web plans are not in RevenueCat yet — subscribe on Android for now.'
        );
        window.open(PLAY_STORE_URL, '_blank', 'noopener,noreferrer');
        return;
      }
      if (result.cancelled) {
        return;
      }
      if (result.purchased) {
        try {
          await subscriptionsApi.sync({
            revenuecat_user_id: userId,
            is_active: true,
            product_id: 'web',
          });
        } catch (_) { /* non-fatal; webhook usually wins */ }
        await pollBackendPro();
        toast.success('Welcome to Laro Pro!');
        await load();
      }
    } catch (e) {
      console.error(e);
      toast.error(e?.message || 'Could not open checkout');
    } finally {
      setPurchasing(false);
    }
  };

  const handleManage = () => {
    if (rcStatus?.managementURL) {
      window.open(rcStatus.managementURL, '_blank', 'noopener,noreferrer');
      return;
    }
    // Prefer Play only when this Pro was not purchased on web
    window.open(PLAY_STORE_URL, '_blank', 'noopener,noreferrer');
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
          Cook smarter — AI, scans, and an unlimited kitchen
        </p>
        <p className="text-xs text-muted-foreground mt-0.5">
          Powered by RevenueCat · synced with your account
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

            <div className="flex flex-wrap gap-2 pt-1">
              {!isPro && (
                <Button
                  onClick={handleUpgradeWeb}
                  disabled={purchasing}
                  className="rounded-full bg-laro hover:bg-laro-dark"
                  data-testid="upgrade-pro-btn"
                >
                  {purchasing ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Crown className="w-4 h-4 mr-2" />
                  )}
                  {webBilling && webPackagesReady !== false
                    ? t('unlockLaroPro')
                    : t('getProOnAndroid')}
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
                  {rcStatus?.managementURL ? t('manageBilling') : t('manageSubscription')}
                </Button>
              )}
              {(!webBilling || webPackagesReady === false) && (
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => window.open(PLAY_STORE_URL, '_blank', 'noopener,noreferrer')}
                >
                  <ExternalLink className="w-4 h-4 mr-2" />
                  {t('openPlayStore')}
                </Button>
              )}
            </div>

            {!webBilling && (
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {t('webBillingKeyNeededHint')}
              </p>
            )}
            {webBilling && webPackagesReady === false && (
              <p
                className="text-[11px] text-muted-foreground leading-relaxed"
                data-testid="web-billing-packages-missing"
              >
                {t('webBillingPackagesMissingHint')}
              </p>
            )}
          </>
        )}
      </div>
    </motion.section>
  );
}

export default SubscriptionSection;
