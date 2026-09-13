import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { friendsApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Avatar, AvatarFallback } from '../components/ui/avatar';
import {
  Users,
  UserPlus,
  Loader2,
  Copy,
  Trash2,
  Gift,
  Link2,
} from 'lucide-react';
import { toast } from 'sonner';
import { Link } from 'react-router-dom';
import { useAccessibility, confirmDestructive } from '../context/AccessibilityContext';
import { useLanguage } from '../context/LanguageContext';

export const Friends = () => {
  const { t } = useLanguage();
  const { confirmActions } = useAccessibility();
  const [friends, setFriends] = useState([]);
  const [incoming, setIncoming] = useState([]);
  const [outgoing, setOutgoing] = useState([]);
  const [myCode, setMyCode] = useState('');
  const [friendCode, setFriendCode] = useState('');
  const [referralStats, setReferralStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    try {
      const [codeRes, listRes, reqRes, statsRes] = await Promise.all([
        friendsApi.getMyCode(),
        friendsApi.list(),
        friendsApi.listRequests(),
        friendsApi.referralStats().catch(() => ({ data: null })),
      ]);
      setMyCode(codeRes.data?.friend_code || '');
      setFriends(listRes.data?.friends || []);
      setIncoming(reqRes.data?.incoming || []);
      setOutgoing(reqRes.data?.outgoing || []);
      setReferralStats(statsRes.data || null);
    } catch (error) {
      console.error('Failed to load friends:', error);
      toast.error(t('toastFriendsLoadFailed'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const inviteLink = myCode
    ? `${window.location.origin}/register?ref=${encodeURIComponent(myCode)}`
    : '';

  const playStoreUrl = 'https://play.google.com/store/apps/details?id=com.laro.app';

  const inviteShareMessage = myCode
    ? [
        t('inviteShareLine1'),
        '',
        t('inviteShareLine2', { code: myCode }),
        '',
        t('inviteSharePlayStore', { url: playStoreUrl }),
        t('inviteShareWeb', { url: inviteLink }),
      ].join('\n')
    : '';

  const handleCopyCode = async () => {
    if (!myCode) return;
    try {
      await navigator.clipboard.writeText(myCode);
      toast.success(t('toastFriendCodeCopied'));
    } catch {
      toast.error(t('toastCopyCodeFailed'));
    }
  };

  const handleCopyInviteLink = async () => {
    if (!inviteShareMessage) return;
    try {
      await navigator.clipboard.writeText(inviteShareMessage);
      toast.success(t('toastInviteLinkCopied'));
    } catch {
      toast.error(t('toastCopyCodeFailed'));
    }
  };

  const handleShareInvite = async () => {
    if (!inviteShareMessage) return;
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Laro',
          text: inviteShareMessage,
        });
        return;
      } catch (err) {
        if (err?.name === 'AbortError') return;
      }
    }
    await handleCopyInviteLink();
  };

  const handleAdd = async () => {
    if (!friendCode.trim()) return;
    setAdding(true);
    try {
      const res = await friendsApi.add(friendCode.trim());
      if (res.data?.pending) {
        toast.success(t('toastFriendRequestSent'));
      } else {
        toast.success(res.data?.message || t('toastFriendAdded'));
      }
      setFriendCode('');
      await load();
    } catch (error) {
      toast.error(
        error.response?.data?.detail || t('toastAddFriendFailed')
      );
    } finally {
      setAdding(false);
    }
  };

  const handleAcceptRequest = async (requestId) => {
    try {
      await friendsApi.acceptRequest(requestId);
      toast.success(t('toastFriendRequestAccepted'));
      await load();
    } catch (error) {
      toast.error(
        error.response?.data?.detail || t('toastAcceptRequestFailed')
      );
    }
  };

  const handleDeclineRequest = async (requestId) => {
    try {
      await friendsApi.declineRequest(requestId);
      toast.success(t('toastFriendRequestDeclined'));
      setIncoming((prev) => prev.filter((r) => r.id !== requestId));
    } catch (error) {
      toast.error(
        error.response?.data?.detail || t('toastDeclineRequestFailed')
      );
    }
  };

  const handleRemove = async (friend) => {
    if (
      !confirmDestructive(
        confirmActions,
        t('removeFriendConfirm', { name: friend.name })
      )
    ) {
      return;
    }
    try {
      await friendsApi.remove(friend.id);
      toast.success(t('toastFriendRemoved'));
      setFriends((prev) => prev.filter((f) => f.id !== friend.id));
    } catch (error) {
      toast.error(
        error.response?.data?.detail || t('toastRemoveFriendFailed')
      );
    }
  };

  const getInitials = (name) => {
    if (!name) return '?';
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
  };

  return (
    <Layout>
      <div className="max-w-2xl mx-auto space-y-8" data-testid="friends-page">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="font-heading text-3xl font-bold">{t('friends')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('friendsIntro')}
          </p>
        </motion.div>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-laro" />
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-6"
          >
            <div className="bg-white dark:bg-card rounded-2xl border border-border/60 p-6">
              <div className="flex items-start gap-4">
                <div className="w-12 h-12 rounded-xl bg-laro-light flex items-center justify-center flex-shrink-0">
                  <Gift className="w-6 h-6 text-laro" />
                </div>
                <div className="flex-1 min-w-0">
                  <h2 className="font-heading text-lg font-semibold">{t('yourReferralCode')}</h2>
                  <p className="text-sm text-muted-foreground mb-3">
                    {t('referralShareHint')}
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <code
                      className="px-3 py-2 rounded-xl bg-cream-subtle text-laro font-mono text-sm"
                      data-testid="my-friend-code"
                    >
                      {myCode || '—'}
                    </code>
                    <Button
                      variant="outline"
                      className="rounded-full"
                      onClick={handleCopyCode}
                      disabled={!myCode}
                      data-testid="copy-friend-code"
                    >
                      <Copy className="w-4 h-4 mr-2" />
                      {t('copy')}
                    </Button>
                    <Button
                      variant="outline"
                      className="rounded-full"
                      onClick={handleCopyInviteLink}
                      disabled={!inviteShareMessage}
                      data-testid="copy-invite-link"
                    >
                      <Link2 className="w-4 h-4 mr-2" />
                      {t('copyInviteLink')}
                    </Button>
                    <Button
                      className="rounded-full bg-laro hover:bg-laro-dark"
                      onClick={handleShareInvite}
                      disabled={!inviteShareMessage}
                      data-testid="share-invite"
                    >
                      <Gift className="w-4 h-4 mr-2" />
                      {t('shareInvite')}
                    </Button>
                  </div>
                  {referralStats && (
                    <p className="text-xs text-muted-foreground mt-3">
                      {t('referralStatsLine', {
                        count: referralStats.referral_count || 0,
                        pending: referralStats.pending_referrals || 0,
                      })}
                      {typeof referralStats.reward_points === 'number'
                        ? ` · ${t('pointsBalance', { points: referralStats.reward_points })}`
                        : ''}
                      {referralStats.has_referral_trial && referralStats.days_remaining != null
                        ? ` · ${t('referralTrialDaysLeft', { days: referralStats.days_remaining })}`
                        : ''}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-2">
                    {t('rewardStoreEarnOnFriends')}{' '}
                    <Link to="/settings" className="text-laro hover:underline font-medium">
                      {t('openRewards')}
                    </Link>
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-white dark:bg-card rounded-2xl border border-border/60 p-6">
              <h2 className="font-heading text-lg font-semibold mb-1 flex items-center gap-2">
                <UserPlus className="w-5 h-5 text-laro" />
                {t('addAFriend')}
              </h2>
              <p className="text-sm text-muted-foreground mb-4">
                {t('addFriendHint')}
              </p>
              <div className="space-y-3">
                <div>
                  <Label htmlFor="friend-code-input">{t('friendCodeLabel')}</Label>
                  <Input
                    id="friend-code-input"
                    placeholder={t('friendCodeInputPlaceholder')}
                    value={friendCode}
                    onChange={(e) => setFriendCode(e.target.value)}
                    className="mt-1 rounded-xl font-mono uppercase"
                    data-testid="friend-code-input"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleAdd();
                    }}
                  />
                </div>
                <Button
                  className="rounded-full bg-laro hover:bg-laro-dark"
                  onClick={handleAdd}
                  disabled={adding || !friendCode.trim()}
                  data-testid="add-friend-btn"
                >
                  {adding ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <UserPlus className="w-4 h-4 mr-2" />
                  )}
                  {t('sendRequest')}
                </Button>
              </div>
            </div>

            {incoming.length > 0 && (
              <div
                className="bg-white dark:bg-card rounded-2xl border border-border/60 p-6"
                data-testid="incoming-friend-requests"
              >
                <h2 className="font-heading text-lg font-semibold mb-4">{t('incomingRequests')}</h2>
                <ul className="space-y-3">
                  {incoming.map((req) => (
                    <li
                      key={req.id}
                      className="flex flex-wrap items-center gap-3 p-3 rounded-xl bg-cream-subtle"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{req.from_name}</p>
                        <p className="text-sm text-muted-foreground font-mono">
                          {req.from_friend_code || '—'}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        className="rounded-full bg-laro hover:bg-laro-dark"
                        onClick={() => handleAcceptRequest(req.id)}
                      >
                        {t('accept')}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="rounded-full"
                        onClick={() => handleDeclineRequest(req.id)}
                      >
                        {t('decline')}
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {outgoing.length > 0 && (
              <div className="bg-white dark:bg-card rounded-2xl border border-border/60 p-6">
                <h2 className="font-heading text-lg font-semibold mb-4">{t('outgoingRequests')}</h2>
                <ul className="space-y-3">
                  {outgoing.map((req) => (
                    <li
                      key={req.id}
                      className="flex items-center gap-3 p-3 rounded-xl bg-cream-subtle"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{req.to_name}</p>
                        <p className="text-sm text-muted-foreground font-mono">
                          {req.to_friend_code || '—'}
                        </p>
                      </div>
                      <span className="text-xs text-muted-foreground">{t('pending')}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="bg-white dark:bg-card rounded-2xl border border-border/60 p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-heading text-lg font-semibold flex items-center gap-2">
                  <Users className="w-5 h-5 text-laro" />
                  {t('yourFriends')}
                </h2>
                <span className="text-sm text-muted-foreground">
                  {t('totalCountSuffix', { count: friends.length })}
                </span>
              </div>

              {friends.length === 0 ? (
                <p className="text-sm text-muted-foreground py-6 text-center">
                  {t('noFriendsYet')}
                </p>
              ) : (
                <ul className="space-y-3" data-testid="friends-list">
                  {friends.map((friend) => (
                    <li
                      key={friend.id}
                      className="flex items-center gap-3 p-3 rounded-xl bg-cream-subtle"
                    >
                      <Avatar>
                        <AvatarFallback className="bg-laro text-white">
                          {getInitials(friend.name)}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{friend.name}</p>
                        <p className="text-sm text-muted-foreground font-mono">
                          {friend.friend_code || '—'}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-muted-foreground hover:text-destructive"
                        onClick={() => handleRemove(friend)}
                        aria-label={t('removeFriendAria', { name: friend.name })}
                        data-testid={`remove-friend-${friend.id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </motion.div>
        )}
      </div>
    </Layout>
  );
};

export default Friends;
