import React, { useCallback, useEffect, useState } from 'react';
import { Crown, Loader2, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { Link } from 'react-router-dom';
import { Button } from './ui/button';
import { rewardsApi } from '../lib/api';
import { useLanguage } from '../context/LanguageContext';

/**
 * Points balance + redeem catalog. Lives in Settings (Subscription),
 * not Friends — Friends is for inviting; this is for spending points.
 */
export function RewardStore({ className = '' }) {
  const { t } = useLanguage();
  const [rewards, setRewards] = useState(null);
  const [loading, setLoading] = useState(true);
  const [redeeming, setRedeeming] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await rewardsApi.catalog();
      setRewards(res.data || null);
    } catch (e) {
      console.warn('Rewards catalog failed:', e);
      setRewards(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRedeem = async (sku, title) => {
    if (redeeming) return;
    setRedeeming(sku);
    try {
      const res = await rewardsApi.redeem(sku);
      toast.success(t('toastRewardRedeemed', { title: res.data?.title || title }));
      await load();
    } catch (error) {
      const detail = error.response?.data?.detail;
      const msg =
        (typeof detail === 'object' && detail?.message) ||
        (typeof detail === 'string' && detail) ||
        t('toastRedeemFailed');
      toast.error(msg);
    } finally {
      setRedeeming(null);
    }
  };

  if (loading) {
    return (
      <div className={`flex justify-center py-6 ${className}`} id="rewards">
        <Loader2 className="w-5 h-5 animate-spin text-laro" />
      </div>
    );
  }

  if (!rewards) return null;

  return (
    <div
      id="rewards"
      className={`rounded-xl border border-border/50 bg-cream-subtle/80 p-4 space-y-4 ${className}`}
      data-testid="reward-store"
    >
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-xl bg-laro-light flex items-center justify-center flex-shrink-0">
          <Sparkles className="w-5 h-5 text-laro" />
        </div>
        <div className="min-w-0">
          <h3 className="font-medium text-foreground">{t('rewardStoreTitle')}</h3>
          <p className="text-sm text-muted-foreground mt-0.5">
            {t('rewardStoreIntro', {
              signup: rewards.earn?.referral_signup ?? 50,
              subscribe: rewards.earn?.referral_subscribe ?? 150,
            })}
          </p>
          <p className="mt-2 text-sm font-medium text-laro" data-testid="reward-points">
            {t('pointsBalance', { points: rewards.points ?? 0 })}
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            {t('rewardStoreEarnHint')}{' '}
            <Link to="/friends" className="text-laro hover:underline font-medium">
              {t('friends')}
            </Link>
          </p>
        </div>
      </div>

      <ul className="space-y-2">
        {(rewards.catalog || []).map((item) => {
          const canAfford = (rewards.points || 0) >= item.cost;
          return (
            <li
              key={item.sku}
              className="flex flex-wrap items-center gap-3 p-3 rounded-xl bg-background/80 border border-border/40"
              data-testid={`reward-sku-${item.sku}`}
            >
              <div className="flex-1 min-w-0">
                <p className="font-medium flex items-center gap-1.5 text-sm">
                  {item.kind === 'pro_days' && (
                    <Crown className="w-3.5 h-3.5 text-laro flex-shrink-0" aria-hidden="true" />
                  )}
                  <span className="truncate">{item.title}</span>
                </p>
                <p className="text-xs text-muted-foreground">{item.description}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t('pointsCost', { cost: item.cost })}
                </p>
              </div>
              <Button
                size="sm"
                className="rounded-full bg-laro hover:bg-laro-dark"
                disabled={!canAfford || redeeming === item.sku}
                onClick={() => handleRedeem(item.sku, item.title)}
                data-testid={`redeem-${item.sku}`}
              >
                {redeeming === item.sku ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  t('redeem')
                )}
              </Button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default RewardStore;
