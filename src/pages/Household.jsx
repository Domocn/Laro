import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { useAccessibility, confirmDestructive } from '../context/AccessibilityContext';
import { householdApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Avatar, AvatarFallback } from '../components/ui/avatar';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import { 
  Users, 
  Plus, 
  Loader2,
  Home,
  UserPlus,
  LogOut,
  Crown,
  Mail
} from 'lucide-react';
import { toast } from 'sonner';
import { useLanguage } from '../context/LanguageContext';

export const Household = () => {
  const { t } = useLanguage();
  const { user, household, refreshHousehold, updateUser } = useAuth();
  const { confirmActions } = useAccessibility();
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showInviteDialog, setShowInviteDialog] = useState(false);
  const [householdName, setHouseholdName] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [creating, setCreating] = useState(false);
  const [inviting, setInviting] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [pendingInvites, setPendingInvites] = useState([]);

  useEffect(() => {
    if (household) {
      loadMembers();
    } else {
      setLoading(false);
    }
    loadPendingInvites();
  }, [household]);

  const loadPendingInvites = async () => {
    try {
      const res = await householdApi.listInvites();
      setPendingInvites(res.data?.invites || []);
    } catch (error) {
      console.error('Failed to load household invites:', error);
    }
  };

  const loadMembers = async () => {
    try {
      const res = await householdApi.getMembers();
      setMembers(res.data);
    } catch (error) {
      console.error('Failed to load members:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateHousehold = async () => {
    if (!householdName.trim()) return;

    setCreating(true);
    try {
      await householdApi.create({ name: householdName });
      await refreshHousehold();
      const meRes = await householdApi.getMy();
      if (meRes.data) {
        updateUser({ ...user, household_id: meRes.data.id });
      }
      setShowCreateDialog(false);
      setHouseholdName('');
      toast.success(t('toastHouseholdCreated'));
      loadMembers();
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastCreateHouseholdFailed'));
    } finally {
      setCreating(false);
    }
  };

  const handleInvite = async () => {
    if (!inviteEmail.trim()) return;

    setInviting(true);
    try {
      await householdApi.invite(inviteEmail);
      toast.success(t('toastInviteSentAcceptHint'));
      setShowInviteDialog(false);
      setInviteEmail('');
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastInviteUserFailed'));
    } finally {
      setInviting(false);
    }
  };

  const handleAcceptInvite = async (inviteId) => {
    try {
      await householdApi.acceptInvite(inviteId);
      await refreshHousehold();
      const meRes = await householdApi.getMy();
      if (meRes.data) {
        updateUser({ ...user, household_id: meRes.data.id });
      }
      toast.success(t('toastJoinedHousehold'));
      await loadPendingInvites();
      loadMembers();
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastAcceptInviteFailed'));
    }
  };

  const handleDeclineInvite = async (inviteId) => {
    try {
      await householdApi.declineInvite(inviteId);
      toast.success(t('toastInviteDeclined'));
      setPendingInvites((prev) => prev.filter((i) => i.id !== inviteId));
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastDeclineInviteFailed'));
    }
  };

  const handleLeave = async () => {
    if (!confirmDestructive(confirmActions, t('confirmLeaveHousehold'))) return;

    setLeaving(true);
    try {
      await householdApi.leave();
      updateUser({ ...user, household_id: null });
      await refreshHousehold();
      toast.success(t('toastLeftHousehold'));
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastLeaveHouseholdFailed'));
    } finally {
      setLeaving(false);
    }
  };

  const getInitials = (name) => {
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  };

  return (
    <Layout>
      <div className="max-w-2xl mx-auto space-y-8" data-testid="household-page">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="font-heading text-3xl font-bold">{t('householdTitle')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('householdPageDesc')}
          </p>
        </motion.div>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-laro" />
          </div>
        ) : !household ? (
          /* No Household */
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-6"
          >
            {pendingInvites.length > 0 && (
              <div className="bg-white rounded-2xl border border-border/60 p-6" data-testid="pending-household-invites">
                <h3 className="font-heading text-lg font-semibold mb-3">{t('pendingInvites')}</h3>
                <ul className="space-y-3">
                  {pendingInvites.map((invite) => (
                    <li key={invite.id} className="flex flex-wrap items-center gap-3 p-3 rounded-xl bg-cream-subtle">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium truncate">{invite.household_name}</p>
                        <p className="text-sm text-muted-foreground truncate">
                          {t('fromInviterPrefix', { inviter: invite.inviter_name || invite.inviter_email })}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        className="rounded-full bg-laro hover:bg-laro-dark"
                        onClick={() => handleAcceptInvite(invite.id)}
                      >
                        {t('accept')}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="rounded-full"
                        onClick={() => handleDeclineInvite(invite.id)}
                      >
                        {t('decline')}
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="bg-white rounded-2xl border border-border/60 p-8 text-center">
            <div className="w-16 h-16 rounded-full bg-laro-light mx-auto mb-4 flex items-center justify-center">
              <Home className="w-8 h-8 text-laro" />
            </div>
            <h3 className="font-heading text-lg font-semibold mb-2">{t('noHouseholdYet')}</h3>
            <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
              {t('noHouseholdDesc')}
            </p>
            
            <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
              <DialogTrigger asChild>
                <Button className="rounded-full bg-laro hover:bg-laro-dark" data-testid="create-household-btn">
                  <Plus className="w-4 h-4 mr-2" />
                  {t('createHousehold')}
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>{t('createYourHouseholdTitle')}</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 pt-4">
                  <div>
                    <Label>{t('householdNameLabel')}</Label>
                    <Input
                      placeholder={t('householdNamePlaceholder')}
                      value={householdName}
                      onChange={(e) => setHouseholdName(e.target.value)}
                      className="mt-1 rounded-xl"
                      data-testid="household-name-input"
                    />
                  </div>
                  <Button 
                    onClick={handleCreateHousehold}
                    className="w-full rounded-full bg-laro hover:bg-laro-dark"
                    disabled={creating || !householdName.trim()}
                  >
                    {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                    {t('createHousehold')}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
            </div>
          </motion.div>
        ) : (
          /* Has Household */
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-6"
          >
            {/* Household Info */}
            <div className="bg-white rounded-2xl border border-border/60 p-6">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                  <div className="w-14 h-14 rounded-xl bg-laro flex items-center justify-center">
                    <Home className="w-7 h-7 text-white" />
                  </div>
                  <div>
                    <h2 className="font-heading text-xl font-semibold">{household.name}</h2>
                    <p className="text-sm text-muted-foreground">
                      {t('memberCountLabel', { count: members.length })}
                    </p>
                  </div>
                </div>
                
                <Dialog open={showInviteDialog} onOpenChange={setShowInviteDialog}>
                  <DialogTrigger asChild>
                    <Button className="rounded-full bg-laro hover:bg-laro-dark" data-testid="invite-member-btn">
                      <UserPlus className="w-4 h-4 mr-2" />
                      {t('invite')}
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>{t('inviteMemberTitle')}</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 pt-4">
                      <p className="text-sm text-muted-foreground">
                        {t('inviteMemberHint')}
                      </p>
                      <div>
                        <Label>{t('emailAddressLabel')}</Label>
                        <div className="relative mt-1">
                          <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                          <Input
                            type="email"
                            placeholder={t('inviteEmailPlaceholder')}
                            value={inviteEmail}
                            onChange={(e) => setInviteEmail(e.target.value)}
                            className="pl-10 rounded-xl"
                            data-testid="invite-email-input"
                          />
                        </div>
                      </div>
                      <Button 
                        onClick={handleInvite}
                        className="w-full rounded-full bg-laro hover:bg-laro-dark"
                        disabled={inviting || !inviteEmail.trim()}
                      >
                        {inviting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                        {t('sendInvite')}
                      </Button>
                    </div>
                  </DialogContent>
                </Dialog>
              </div>

              {/* Members List */}
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
                  {t('members')}
                </h3>
                {members.map((member) => (
                  <div 
                    key={member.id}
                    className="flex items-center gap-3 p-3 rounded-xl bg-cream-subtle"
                  >
                    <Avatar>
                      <AvatarFallback className="bg-laro text-white">
                        {getInitials(member.name)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1">
                      <p className="font-medium">{member.name}</p>
                      <p className="text-sm text-muted-foreground">{member.email}</p>
                    </div>
                    {member.id === household.owner_id && (
                      <Crown className="w-5 h-5 text-amber-500" />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Leave Household */}
            {user?.id !== household.owner_id && (
              <div className="bg-white rounded-2xl border border-destructive/20 p-6">
                <h3 className="font-medium mb-2">{t('leaveHousehold')}</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {t('leaveHouseholdDesc')}
                </p>
                <Button 
                  variant="outline"
                  className="rounded-full border-destructive text-destructive hover:bg-destructive hover:text-white"
                  onClick={handleLeave}
                  disabled={leaving}
                >
                  {leaving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <LogOut className="w-4 h-4 mr-2" />}
                  {t('leaveHousehold')}
                </Button>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </Layout>
  );
};
