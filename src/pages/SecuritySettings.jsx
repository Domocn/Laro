import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { securityApi, oauthApi, googleHealthApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { TrustedDevices } from '../components/TrustedDevices';
import {
  Shield,
  Key,
  Smartphone,
  Monitor,
  Loader2,
  Check,
  X,
  Copy,
  RefreshCw,
  LogOut,
  AlertTriangle,
  Github,
  Chrome,
  Lock
} from 'lucide-react';
import { toast } from 'sonner';
import { useLanguage } from '../context/LanguageContext';

export const SecuritySettings = () => {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [loading, setLoading] = useState(true);
  
  // Password change
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);
  
  // 2FA
  const [twoFAStatus, setTwoFAStatus] = useState({ enabled: false, backup_codes_remaining: 0 });
  const [setupData, setSetupData] = useState(null);
  const [verifyCode, setVerifyCode] = useState('');
  const [settingUp2FA, setSettingUp2FA] = useState(false);
  const [verifying2FA, setVerifying2FA] = useState(false);
  const [disabling2FA, setDisabling2FA] = useState(false);
  const [disablePassword, setDisablePassword] = useState('');
  const [disableCode, setDisableCode] = useState('');
  const [showDisable2FA, setShowDisable2FA] = useState(false);
  const [regeneratingCodes, setRegeneratingCodes] = useState(false);
  const [newBackupCodes, setNewBackupCodes] = useState(null);
  
  // Sessions
  const [sessions, setSessions] = useState([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  
  // OAuth
  const [oauthStatus, setOauthStatus] = useState({ google: false, github: false });
  const [linkedAccounts, setLinkedAccounts] = useState([]);
  const [linkingAccount, setLinkingAccount] = useState(null);
  const [googleHealth, setGoogleHealth] = useState({
    configured: false,
    linked: false,
    sync_on_cook: false,
  });
  const [linkingGoogleHealth, setLinkingGoogleHealth] = useState(false);
  const [updatingGoogleHealth, setUpdatingGoogleHealth] = useState(false);
  const [googleHealthLogs, setGoogleHealthLogs] = useState([]);
  const [deletingLogId, setDeletingLogId] = useState(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [twoFARes, sessionsRes, oauthStatusRes, linkedRes, ghRes] = await Promise.all([
        securityApi.get2FAStatus().catch(() => ({ data: { enabled: false } })),
        securityApi.getSessions().catch(() => ({ data: { sessions: [] } })),
        oauthApi.getStatus().catch(() => ({ data: { google: false, github: false } })),
        oauthApi.getLinkedAccounts().catch(() => ({ data: { accounts: [] } })),
        googleHealthApi.getStatus().catch(() => ({
          data: { configured: false, linked: false, sync_on_cook: false },
        })),
      ]);
      
      setTwoFAStatus(twoFARes.data);
      setSessions(sessionsRes.data.sessions || []);
      setOauthStatus(oauthStatusRes.data);
      setGoogleHealth(ghRes.data || { configured: false, linked: false, sync_on_cook: false });
      setLinkedAccounts(linkedRes.data.accounts || []);
      if (ghRes.data?.linked) {
        try {
          const logsRes = await googleHealthApi.listLogs();
          setGoogleHealthLogs(logsRes.data?.logs || []);
        } catch (_) {
          setGoogleHealthLogs([]);
        }
      } else {
        setGoogleHealthLogs([]);
      }
    } catch (error) {
      console.error('Failed to load security data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Password change
  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      toast.error(t('toastPwdsDoNotMatch'));
      return;
    }
    if (newPassword.length < 8) {
      toast.error(t('toastPwdTooShort'));
      return;
    }
    
    setChangingPassword(true);
    try {
      await securityApi.changePassword(currentPassword, newPassword);
      toast.success(t('toastPwdChanged'));
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastChangePwdFailed'));
    } finally {
      setChangingPassword(false);
    }
  };

  // 2FA Setup
  const handleSetup2FA = async () => {
    setSettingUp2FA(true);
    try {
      const res = await securityApi.setup2FA();
      setSetupData(res.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastSetup2faFailed'));
    } finally {
      setSettingUp2FA(false);
    }
  };

  const handleVerify2FA = async () => {
    if (!verifyCode || verifyCode.length !== 6) {
      toast.error(t('toastEnterSixDigitCode'));
      return;
    }
    
    setVerifying2FA(true);
    try {
      await securityApi.verify2FA(verifyCode);
      toast.success(t('toast2faEnabled'));
      setSetupData(null);
      setVerifyCode('');
      setTwoFAStatus({ enabled: true, backup_codes_remaining: 8 });
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastInvalidCode'));
    } finally {
      setVerifying2FA(false);
    }
  };

  const handleDisable2FA = async () => {
    setDisabling2FA(true);
    try {
      await securityApi.disable2FA(disablePassword, disableCode);
      toast.success(t('toast2faDisabled'));
      setTwoFAStatus({ enabled: false, backup_codes_remaining: 0 });
      setShowDisable2FA(false);
      setDisablePassword('');
      setDisableCode('');
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastDisable2faFailed'));
    } finally {
      setDisabling2FA(false);
    }
  };

  const handleRegenerateBackupCodes = async () => {
    const code = prompt(t('promptRegenerateBackupCodes'));
    if (!code) return;
    
    setRegeneratingCodes(true);
    try {
      const res = await securityApi.regenerateBackupCodes(code);
      setNewBackupCodes(res.data.backup_codes);
      toast.success(t('toastBackupCodesRegenerated'));
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastRegenerateBackupCodesFailed'));
    } finally {
      setRegeneratingCodes(false);
    }
  };

  // Sessions
  const handleRevokeSession = async (sessionId) => {
    try {
      await securityApi.revokeSession(sessionId);
      setSessions(sessions.filter(s => s.id !== sessionId));
      toast.success(t('toastSessionRevoked'));
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastRevokeSessionFailed'));
    }
  };

  const handleRevokeAllSessions = async () => {
    if (!window.confirm(t('confirmRevokeAllSessions'))) return;
    
    try {
      await securityApi.revokeAllSessions(true);
      const res = await securityApi.getSessions();
      setSessions(res.data.sessions || []);
      toast.success(t('toastAllSessionsRevoked'));
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastRevokeSessionsFailed'));
    }
  };

  // OAuth
  const handleLinkGoogle = async () => {
    setLinkingAccount('google');
    try {
      const res = await oauthApi.getGoogleAuthUrl();
      window.location.href = res.data.auth_url;
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastStartGoogleLoginFailed'));
      setLinkingAccount(null);
    }
  };

  const handleLinkGitHub = async () => {
    setLinkingAccount('github');
    try {
      const res = await oauthApi.getGitHubAuthUrl();
      window.location.href = res.data.auth_url;
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastStartGithubLoginFailed'));
      setLinkingAccount(null);
    }
  };

  const handleUnlinkAccount = async (provider) => {
    if (!window.confirm(t('confirmUnlinkAccount', { provider }))) return;
    
    try {
      await oauthApi.unlinkAccount(provider);
      setLinkedAccounts(linkedAccounts.filter(a => a.provider !== provider));
      toast.success(t('toastAccountUnlinked', { provider }));
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastUnlinkAccountFailed'));
    }
  };

  const handleLinkGoogleHealth = async () => {
    setLinkingGoogleHealth(true);
    try {
      const res = await googleHealthApi.getAuthUrl();
      if (res.data?.auth_url) {
        window.location.href = res.data.auth_url;
      } else {
        toast.error('Could not start Google Health link');
        setLinkingGoogleHealth(false);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Google Health is not configured');
      setLinkingGoogleHealth(false);
    }
  };

  const handleUnlinkGoogleHealth = async () => {
    if (!window.confirm('Disconnect Google Health? Future mark-cooked meals will not sync nutrition to Fitbit / Google Health.')) {
      return;
    }
    try {
      await googleHealthApi.unlink();
      setGoogleHealth({ configured: true, linked: false, sync_on_cook: false });
      toast.success('Google Health disconnected');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to disconnect Google Health');
    }
  };

  const handleToggleGoogleHealthSync = async (enabled) => {
    setUpdatingGoogleHealth(true);
    try {
      const res = await googleHealthApi.updateSettings(enabled);
      setGoogleHealth(res.data);
      toast.success(enabled ? 'Sync on cook enabled' : 'Sync on cook disabled');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update settings');
    } finally {
      setUpdatingGoogleHealth(false);
    }
  };

  const handleDeleteGoogleHealthLog = async (logId) => {
    if (!window.confirm('Remove this meal from Google Health / Fitbit? Fitbit often cannot delete Laro-written logs itself — this is the supported undo.')) {
      return;
    }
    setDeletingLogId(logId);
    try {
      await googleHealthApi.deleteLog(logId);
      setGoogleHealthLogs((prev) =>
        prev.map((log) =>
          log.id === logId ? { ...log, deleted_at: new Date().toISOString() } : log
        )
      );
      toast.success('Removed from Google Health');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete nutrition log');
    } finally {
      setDeletingLogId(null);
    }
  };

  const copyBackupCodes = () => {
    const codes = setupData?.backup_codes || newBackupCodes;
    if (codes) {
      navigator.clipboard.writeText(codes.join('\n'));
      toast.success(t('toastBackupCodesCopied'));
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return t('unknownDate');
    return new Date(dateStr).toLocaleString();
  };

  const isGoogleLinked = linkedAccounts.some(a => a.provider === 'google');
  const isGitHubLinked = linkedAccounts.some(a => a.provider === 'github');

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-laro" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-2xl mx-auto space-y-8" data-testid="security-settings">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="font-heading text-3xl font-bold flex items-center gap-2">
            <Shield className="w-8 h-8 text-laro" />
            {t('securitySettingsTitle')}
          </h1>
          <p className="text-muted-foreground mt-1">{t('manageAccountSecurity')}</p>
        </motion.div>

        {/* Change Password */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Key className="w-5 h-5 text-laro" />
              {t('changePwdLabel')}
            </h2>
          </div>

          <div className="p-4 space-y-4">
            <div>
              <Label htmlFor="current-password">{t('currentPwdLabel')}</Label>
              <Input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="mt-1 rounded-xl"
              />
            </div>
            <div>
              <Label htmlFor="new-password">{t('newPwdLabel')}</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="mt-1 rounded-xl"
              />
            </div>
            <div>
              <Label htmlFor="confirm-password">{t('confirmNewPwdLabel')}</Label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="mt-1 rounded-xl"
              />
            </div>
            <Button
              onClick={handleChangePassword}
              disabled={changingPassword || !currentPassword || !newPassword}
              className="rounded-full bg-laro hover:bg-laro-dark"
            >
              {changingPassword ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              {t('changePwdLabel')}
            </Button>
          </div>
        </motion.section>

        {/* Two-Factor Authentication */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Smartphone className="w-5 h-5 text-laro" />
              {t('twoFactorAuth')}
            </h2>
          </div>

          <div className="p-4 space-y-4">
            {!twoFAStatus.enabled && !setupData && (
              <>
                <p className="text-muted-foreground">
                  {t('twoFactorAuthDesc')}
                </p>
                <Button
                  onClick={handleSetup2FA}
                  disabled={settingUp2FA}
                  className="rounded-full bg-laro hover:bg-laro-dark"
                >
                  {settingUp2FA ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Shield className="w-4 h-4 mr-2" />}
                  {t('enable2fa')}
                </Button>
              </>
            )}

            {setupData && (
              <div className="space-y-4">
                <div className="p-4 bg-cream-subtle rounded-xl text-center">
                  <p className="text-sm text-muted-foreground mb-4">
                    {t('scanQrCodeHint')}
                  </p>
                  <img 
                    src={setupData.qr_code} 
                    alt={t('twoFaQrCodeAlt')} 
                    className="mx-auto rounded-lg"
                    style={{ maxWidth: '200px' }}
                  />
                  <p className="text-xs text-muted-foreground mt-4">
                    {t('enterCodeManually')} <code className="bg-white px-2 py-1 rounded">{setupData.secret}</code>
                  </p>
                </div>

                <div>
                  <Label>{t('enterSixDigitCode')}</Label>
                  <div className="flex gap-2 mt-1">
                    <Input
                      value={verifyCode}
                      onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                      placeholder="000000"
                      className="rounded-xl font-mono text-center text-lg tracking-widest"
                      maxLength={6}
                    />
                    <Button
                      onClick={handleVerify2FA}
                      disabled={verifying2FA || verifyCode.length !== 6}
                      className="rounded-xl bg-laro hover:bg-laro-dark"
                    >
                      {verifying2FA ? <Loader2 className="w-4 h-4 animate-spin" /> : t('verify')}
                    </Button>
                  </div>
                </div>

                <div className="p-4 bg-amber-50 rounded-xl border border-amber-200">
                  <p className="text-sm font-medium text-amber-800 mb-2">{t('saveBackupCodes')}</p>
                  <p className="text-xs text-amber-700 mb-3">
                    {t('backupCodesHint')}
                  </p>
                  <div className="grid grid-cols-2 gap-2 mb-3">
                    {setupData.backup_codes.map((code, i) => (
                      <code key={i} className="bg-white px-2 py-1 rounded text-sm text-center">{code}</code>
                    ))}
                  </div>
                  <Button variant="outline" size="sm" onClick={copyBackupCodes} className="rounded-full">
                    <Copy className="w-4 h-4 mr-2" />
                    {t('copyCodes')}
                  </Button>
                </div>

                <Button
                  variant="outline"
                  onClick={() => setSetupData(null)}
                  className="rounded-full"
                >
                  {t('cancelSetup')}
                </Button>
              </div>
            )}

            {twoFAStatus.enabled && !setupData && (
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-4 bg-green-50 rounded-xl border border-green-200">
                  <Check className="w-6 h-6 text-green-600" />
                  <div>
                    <p className="font-medium text-green-800">{t('twoFaEnabledLabel')}</p>
                    <p className="text-sm text-green-700">
                      {t('backupCodesRemaining', { count: twoFAStatus.backup_codes_remaining })}
                    </p>
                  </div>
                </div>

                {newBackupCodes && (
                  <div className="p-4 bg-amber-50 rounded-xl border border-amber-200">
                    <p className="text-sm font-medium text-amber-800 mb-2">{t('newBackupCodesGenerated')}</p>
                    <div className="grid grid-cols-2 gap-2 mb-3">
                      {newBackupCodes.map((code, i) => (
                        <code key={i} className="bg-white px-2 py-1 rounded text-sm text-center">{code}</code>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={copyBackupCodes} className="rounded-full">
                        <Copy className="w-4 h-4 mr-2" />
                        {t('copyCodes')}
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => setNewBackupCodes(null)} className="rounded-full">
                        {t('done')}
                      </Button>
                    </div>
                  </div>
                )}

                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={handleRegenerateBackupCodes}
                    disabled={regeneratingCodes}
                    className="rounded-full"
                  >
                    {regeneratingCodes ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <RefreshCw className="w-4 h-4 mr-2" />}
                    {t('regenerateBackupCodes')}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setShowDisable2FA(true)}
                    className="rounded-full text-red-600 border-red-200 hover:bg-red-50"
                  >
                    {t('disable2fa')}
                  </Button>
                </div>

                {showDisable2FA && (
                  <div className="p-4 border border-red-200 rounded-xl bg-red-50 space-y-3">
                    <p className="text-sm text-red-800">{t('disable2faConfirmHint')}</p>
                    <Input
                      type="password"
                      placeholder={t('pwdFieldLabel')}
                      value={disablePassword}
                      onChange={(e) => setDisablePassword(e.target.value)}
                      className="rounded-xl"
                    />
                    <Input
                      placeholder={t('twoFaCodePlaceholder')}
                      value={disableCode}
                      onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                      className="rounded-xl"
                      maxLength={6}
                    />
                    <div className="flex gap-2">
                      <Button
                        onClick={handleDisable2FA}
                        disabled={disabling2FA || !disablePassword || disableCode.length !== 6}
                        className="rounded-full bg-red-600 hover:bg-red-700 text-white"
                      >
                        {disabling2FA ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                        {t('disable2fa')}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setShowDisable2FA(false);
                          setDisablePassword('');
                          setDisableCode('');
                        }}
                        className="rounded-full"
                      >
                        {t('cancel')}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </motion.section>

        {/* Trusted Devices - Only show if 2FA is enabled */}
        {twoFAStatus.enabled && (
          <motion.section
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.17 }}
            className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
          >
            <div className="p-4">
              <TrustedDevices />
            </div>
          </motion.section>
        )}

        {/* Connected Accounts (OAuth) */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Lock className="w-5 h-5 text-laro" />
              {t('connectedAccounts')}
            </h2>
          </div>

          <div className="p-4 space-y-3">
            {/* Google */}
            <div className="flex items-center justify-between p-3 bg-cream-subtle rounded-xl">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-white rounded-lg flex items-center justify-center">
                  <Chrome className="w-5 h-5 text-blue-500" />
                </div>
                <div>
                  <p className="font-medium">Google</p>
                  {isGoogleLinked && (
                    <p className="text-xs text-muted-foreground">
                      {linkedAccounts.find(a => a.provider === 'google')?.provider_email}
                    </p>
                  )}
                </div>
              </div>
              {oauthStatus.google ? (
                isGoogleLinked ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleUnlinkAccount('google')}
                    className="rounded-full"
                  >
                    {t('unlink')}
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    onClick={handleLinkGoogle}
                    disabled={linkingAccount === 'google'}
                    className="rounded-full bg-laro hover:bg-laro-dark"
                  >
                    {linkingAccount === 'google' ? <Loader2 className="w-4 h-4 animate-spin" /> : t('connect')}
                  </Button>
                )
              ) : (
                <span className="text-xs text-muted-foreground">{t('notConfigured')}</span>
              )}
            </div>

            {/* GitHub */}
            <div className="flex items-center justify-between p-3 bg-cream-subtle rounded-xl">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-white rounded-lg flex items-center justify-center">
                  <Github className="w-5 h-5" />
                </div>
                <div>
                  <p className="font-medium">GitHub</p>
                  {isGitHubLinked && (
                    <p className="text-xs text-muted-foreground">
                      {linkedAccounts.find(a => a.provider === 'github')?.provider_email}
                    </p>
                  )}
                </div>
              </div>
              {oauthStatus.github ? (
                isGitHubLinked ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleUnlinkAccount('github')}
                    className="rounded-full"
                  >
                    {t('unlink')}
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    onClick={handleLinkGitHub}
                    disabled={linkingAccount === 'github'}
                    className="rounded-full bg-laro hover:bg-laro-dark"
                  >
                    {linkingAccount === 'github' ? <Loader2 className="w-4 h-4 animate-spin" /> : t('connect')}
                  </Button>
                )
              ) : (
                <span className="text-xs text-muted-foreground">{t('notConfigured')}</span>
              )}
            </div>

            <p className="text-xs text-muted-foreground mt-2">
              {t('connectAccountsHint')}
            </p>

            {/* Google Health (Fitbit / cloud nutrition) */}
            <div className="mt-4 pt-4 border-t border-border/60">
              <div className="flex items-center justify-between p-3 bg-cream-subtle rounded-xl">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white rounded-lg flex items-center justify-center">
                    <Chrome className="w-5 h-5 text-emerald-600" />
                  </div>
                  <div>
                    <p className="font-medium">Google Health</p>
                    <p className="text-xs text-muted-foreground">
                      {googleHealth.linked
                        ? 'Sync nutrition to Fitbit / Google Health when marked cooked'
                        : 'Link to log meals in Fitbit via Google Health API'}
                    </p>
                  </div>
                </div>
                {googleHealth.configured ? (
                  googleHealth.linked ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleUnlinkGoogleHealth}
                      className="rounded-full"
                    >
                      {t('unlink')}
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      onClick={handleLinkGoogleHealth}
                      disabled={linkingGoogleHealth}
                      className="rounded-full bg-laro hover:bg-laro-dark"
                    >
                      {linkingGoogleHealth ? <Loader2 className="w-4 h-4 animate-spin" /> : t('connect')}
                    </Button>
                  )
                ) : (
                  <span className="text-xs text-muted-foreground">{t('notConfigured')}</span>
                )}
              </div>
              {googleHealth.linked && (
                <label className="mt-3 flex items-center justify-between gap-3 px-1">
                  <span className="text-sm text-muted-foreground">
                    Sync calories &amp; macros when a meal is marked cooked
                  </span>
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-[hsl(var(--laro))]"
                    checked={!!googleHealth.sync_on_cook}
                    disabled={updatingGoogleHealth}
                    onChange={(e) => handleToggleGoogleHealthSync(e.target.checked)}
                  />
                </label>
              )}
              {googleHealth.linked && googleHealthLogs.length > 0 && (
                <div className="mt-3 space-y-2">
                  <p className="text-xs text-muted-foreground px-1">
                    Recent Google Health logs — delete here if Fitbit says it can’t remove them
                  </p>
                  {googleHealthLogs.slice(0, 10).map((log) => (
                    <div
                      key={log.id}
                      className="flex items-center justify-between gap-2 p-2 rounded-lg bg-white dark:bg-background border border-border/50"
                    >
                      <div className="min-w-0">
                        <p className={`text-sm font-medium truncate ${log.deleted_at ? 'line-through opacity-60' : ''}`}>
                          {log.food_display_name || 'Meal'}
                          {log.calories != null ? ` · ${log.calories} kcal` : ''}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {log.deleted_at
                            ? 'Deleted'
                            : log.created_at
                              ? new Date(log.created_at).toLocaleString()
                              : ''}
                        </p>
                      </div>
                      {!log.deleted_at && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="rounded-full shrink-0 text-red-600 border-red-200"
                          disabled={deletingLogId === log.id}
                          onClick={() => handleDeleteGoogleHealthLog(log.id)}
                        >
                          {deletingLogId === log.id ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            'Remove'
                          )}
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </motion.section>

        {/* Active Sessions */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle flex items-center justify-between">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Monitor className="w-5 h-5 text-laro" />
              {t('activeSessions')}
            </h2>
            {sessions.length > 1 && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleRevokeAllSessions}
                className="rounded-full text-red-600 border-red-200 hover:bg-red-50"
              >
                <LogOut className="w-4 h-4 mr-1" />
                {t('signOutAllOthers')}
              </Button>
            )}
          </div>

          <div className="divide-y divide-border/60">
            {sessions.length === 0 ? (
              <p className="p-4 text-muted-foreground text-center">{t('noActiveSessions')}</p>
            ) : (
              sessions.map((session) => (
                <div key={session.id} className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      session.is_current ? 'bg-laro/20' : 'bg-cream-subtle'
                    }`}>
                      <Monitor className={`w-5 h-5 ${session.is_current ? 'text-laro' : 'text-muted-foreground'}`} />
                    </div>
                    <div>
                      <p className="font-medium text-sm flex items-center gap-2">
                        {session.user_agent.includes('Chrome') ? 'Chrome' : 
                         session.user_agent.includes('Firefox') ? 'Firefox' :
                         session.user_agent.includes('Safari') ? 'Safari' : t('unknownBrowser')}
                        {session.is_current && (
                          <span className="text-xs bg-laro/20 text-laro px-2 py-0.5 rounded-full">{t('currentSessionLabel')}</span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {session.ip_address} • {t('lastActiveLabel', { when: formatDate(session.last_active) })}
                      </p>
                    </div>
                  </div>
                  {!session.is_current && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleRevokeSession(session.id)}
                      className="text-red-600 hover:bg-red-50"
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              ))
            )}
          </div>
        </motion.section>
      </div>
    </Layout>
  );
};
