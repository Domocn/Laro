import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { securityApi, oauthApi } from '../lib/api';
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

export const SecuritySettings = () => {
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

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [twoFARes, sessionsRes, oauthStatusRes, linkedRes] = await Promise.all([
        securityApi.get2FAStatus().catch(() => ({ data: { enabled: false } })),
        securityApi.getSessions().catch(() => ({ data: { sessions: [] } })),
        oauthApi.getStatus().catch(() => ({ data: { google: false, github: false } })),
        oauthApi.getLinkedAccounts().catch(() => ({ data: { accounts: [] } }))
      ]);
      
      setTwoFAStatus(twoFARes.data);
      setSessions(sessionsRes.data.sessions || []);
      setOauthStatus(oauthStatusRes.data);
      setLinkedAccounts(linkedRes.data.accounts || []);
    } catch (error) {
      console.error('Failed to load security data:', error);
    } finally {
      setLoading(false);
    }
  };

  // Password change
  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }
    if (newPassword.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }
    
    setChangingPassword(true);
    try {
      await securityApi.changePassword(currentPassword, newPassword);
      toast.success('Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to change password');
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
      toast.error(error.response?.data?.detail || 'Failed to setup 2FA');
    } finally {
      setSettingUp2FA(false);
    }
  };

  const handleVerify2FA = async () => {
    if (!verifyCode || verifyCode.length !== 6) {
      toast.error('Please enter a 6-digit code');
      return;
    }
    
    setVerifying2FA(true);
    try {
      await securityApi.verify2FA(verifyCode);
      toast.success('2FA enabled successfully!');
      setSetupData(null);
      setVerifyCode('');
      setTwoFAStatus({ enabled: true, backup_codes_remaining: 8 });
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Invalid code');
    } finally {
      setVerifying2FA(false);
    }
  };

  const handleDisable2FA = async () => {
    setDisabling2FA(true);
    try {
      await securityApi.disable2FA(disablePassword, disableCode);
      toast.success('2FA disabled');
      setTwoFAStatus({ enabled: false, backup_codes_remaining: 0 });
      setShowDisable2FA(false);
      setDisablePassword('');
      setDisableCode('');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to disable 2FA');
    } finally {
      setDisabling2FA(false);
    }
  };

  const handleRegenerateBackupCodes = async () => {
    const code = prompt('Enter your current 2FA code to regenerate backup codes:');
    if (!code) return;
    
    setRegeneratingCodes(true);
    try {
      const res = await securityApi.regenerateBackupCodes(code);
      setNewBackupCodes(res.data.backup_codes);
      toast.success('Backup codes regenerated');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to regenerate codes');
    } finally {
      setRegeneratingCodes(false);
    }
  };

  // Sessions
  const handleRevokeSession = async (sessionId) => {
    try {
      await securityApi.revokeSession(sessionId);
      setSessions(sessions.filter(s => s.id !== sessionId));
      toast.success('Session revoked');
    } catch (error) {
      toast.error('Failed to revoke session');
    }
  };

  const handleRevokeAllSessions = async () => {
    if (!window.confirm('Revoke all other sessions? You will stay logged in on this device.')) return;
    
    try {
      await securityApi.revokeAllSessions(true);
      const res = await securityApi.getSessions();
      setSessions(res.data.sessions || []);
      toast.success('All other sessions revoked');
    } catch (error) {
      toast.error('Failed to revoke sessions');
    }
  };

  // OAuth
  const handleLinkGoogle = async () => {
    setLinkingAccount('google');
    try {
      const res = await oauthApi.getGoogleAuthUrl();
      window.location.href = res.data.auth_url;
    } catch (error) {
      toast.error('Failed to start Google login');
      setLinkingAccount(null);
    }
  };

  const handleLinkGitHub = async () => {
    setLinkingAccount('github');
    try {
      const res = await oauthApi.getGitHubAuthUrl();
      window.location.href = res.data.auth_url;
    } catch (error) {
      toast.error('Failed to start GitHub login');
      setLinkingAccount(null);
    }
  };

  const handleUnlinkAccount = async (provider) => {
    if (!window.confirm(`Unlink ${provider} account?`)) return;
    
    try {
      await oauthApi.unlinkAccount(provider);
      setLinkedAccounts(linkedAccounts.filter(a => a.provider !== provider));
      toast.success(`${provider} account unlinked`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to unlink account');
    }
  };

  const copyBackupCodes = () => {
    const codes = setupData?.backup_codes || newBackupCodes;
    if (codes) {
      navigator.clipboard.writeText(codes.join('\n'));
      toast.success('Backup codes copied');
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Unknown';
    return new Date(dateStr).toLocaleString();
  };

  const isGoogleLinked = linkedAccounts.some(a => a.provider === 'google');
  const isGitHubLinked = linkedAccounts.some(a => a.provider === 'github');

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-mise" />
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
            <Shield className="w-8 h-8 text-mise" />
            Security Settings
          </h1>
          <p className="text-muted-foreground mt-1">Manage your account security</p>
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
              <Key className="w-5 h-5 text-mise" />
              Change Password
            </h2>
          </div>

          <div className="p-4 space-y-4">
            <div>
              <Label htmlFor="current-password">Current Password</Label>
              <Input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="mt-1 rounded-xl"
              />
            </div>
            <div>
              <Label htmlFor="new-password">New Password</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="mt-1 rounded-xl"
              />
            </div>
            <div>
              <Label htmlFor="confirm-password">Confirm New Password</Label>
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
              className="rounded-full bg-mise hover:bg-mise-dark"
            >
              {changingPassword ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Change Password
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
              <Smartphone className="w-5 h-5 text-mise" />
              Two-Factor Authentication (2FA)
            </h2>
          </div>

          <div className="p-4 space-y-4">
            {!twoFAStatus.enabled && !setupData && (
              <>
                <p className="text-muted-foreground">
                  Add an extra layer of security to your account by enabling two-factor authentication.
                </p>
                <Button
                  onClick={handleSetup2FA}
                  disabled={settingUp2FA}
                  className="rounded-full bg-mise hover:bg-mise-dark"
                >
                  {settingUp2FA ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Shield className="w-4 h-4 mr-2" />}
                  Enable 2FA
                </Button>
              </>
            )}

            {setupData && (
              <div className="space-y-4">
                <div className="p-4 bg-cream-subtle rounded-xl text-center">
                  <p className="text-sm text-muted-foreground mb-4">
                    Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)
                  </p>
                  <img 
                    src={setupData.qr_code} 
                    alt="2FA QR Code" 
                    className="mx-auto rounded-lg"
                    style={{ maxWidth: '200px' }}
                  />
                  <p className="text-xs text-muted-foreground mt-4">
                    Or enter this code manually: <code className="bg-white px-2 py-1 rounded">{setupData.secret}</code>
                  </p>
                </div>

                <div>
                  <Label>Enter the 6-digit code from your app</Label>
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
                      className="rounded-xl bg-mise hover:bg-mise-dark"
                    >
                      {verifying2FA ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Verify'}
                    </Button>
                  </div>
                </div>

                <div className="p-4 bg-amber-50 rounded-xl border border-amber-200">
                  <p className="text-sm font-medium text-amber-800 mb-2">Save your backup codes!</p>
                  <p className="text-xs text-amber-700 mb-3">
                    These codes can be used to access your account if you lose your authenticator app.
                  </p>
                  <div className="grid grid-cols-2 gap-2 mb-3">
                    {setupData.backup_codes.map((code, i) => (
                      <code key={i} className="bg-white px-2 py-1 rounded text-sm text-center">{code}</code>
                    ))}
                  </div>
                  <Button variant="outline" size="sm" onClick={copyBackupCodes} className="rounded-full">
                    <Copy className="w-4 h-4 mr-2" />
                    Copy Codes
                  </Button>
                </div>

                <Button
                  variant="outline"
                  onClick={() => setSetupData(null)}
                  className="rounded-full"
                >
                  Cancel Setup
                </Button>
              </div>
            )}

            {twoFAStatus.enabled && !setupData && (
              <div className="space-y-4">
                <div className="flex items-center gap-3 p-4 bg-green-50 rounded-xl border border-green-200">
                  <Check className="w-6 h-6 text-green-600" />
                  <div>
                    <p className="font-medium text-green-800">2FA is enabled</p>
                    <p className="text-sm text-green-700">
                      {twoFAStatus.backup_codes_remaining} backup codes remaining
                    </p>
                  </div>
                </div>

                {newBackupCodes && (
                  <div className="p-4 bg-amber-50 rounded-xl border border-amber-200">
                    <p className="text-sm font-medium text-amber-800 mb-2">New backup codes generated!</p>
                    <div className="grid grid-cols-2 gap-2 mb-3">
                      {newBackupCodes.map((code, i) => (
                        <code key={i} className="bg-white px-2 py-1 rounded text-sm text-center">{code}</code>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <Button variant="outline" size="sm" onClick={copyBackupCodes} className="rounded-full">
                        <Copy className="w-4 h-4 mr-2" />
                        Copy Codes
                      </Button>
                      <Button variant="outline" size="sm" onClick={() => setNewBackupCodes(null)} className="rounded-full">
                        Done
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
                    Regenerate Backup Codes
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => setShowDisable2FA(true)}
                    className="rounded-full text-red-600 border-red-200 hover:bg-red-50"
                  >
                    Disable 2FA
                  </Button>
                </div>

                {showDisable2FA && (
                  <div className="p-4 border border-red-200 rounded-xl bg-red-50 space-y-3">
                    <p className="text-sm text-red-800">Enter your password and current 2FA code to disable:</p>
                    <Input
                      type="password"
                      placeholder="Password"
                      value={disablePassword}
                      onChange={(e) => setDisablePassword(e.target.value)}
                      className="rounded-xl"
                    />
                    <Input
                      placeholder="2FA Code"
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
                        Disable 2FA
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
                        Cancel
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
              <Lock className="w-5 h-5 text-mise" />
              Connected Accounts
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
                    Unlink
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    onClick={handleLinkGoogle}
                    disabled={linkingAccount === 'google'}
                    className="rounded-full bg-mise hover:bg-mise-dark"
                  >
                    {linkingAccount === 'google' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Connect'}
                  </Button>
                )
              ) : (
                <span className="text-xs text-muted-foreground">Not configured</span>
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
                    Unlink
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    onClick={handleLinkGitHub}
                    disabled={linkingAccount === 'github'}
                    className="rounded-full bg-mise hover:bg-mise-dark"
                  >
                    {linkingAccount === 'github' ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Connect'}
                  </Button>
                )
              ) : (
                <span className="text-xs text-muted-foreground">Not configured</span>
              )}
            </div>

            <p className="text-xs text-muted-foreground mt-2">
              Connect accounts for easy sign-in. OAuth providers must be configured by the server administrator.
            </p>
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
              <Monitor className="w-5 h-5 text-mise" />
              Active Sessions
            </h2>
            {sessions.length > 1 && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleRevokeAllSessions}
                className="rounded-full text-red-600 border-red-200 hover:bg-red-50"
              >
                <LogOut className="w-4 h-4 mr-1" />
                Sign out all others
              </Button>
            )}
          </div>

          <div className="divide-y divide-border/60">
            {sessions.length === 0 ? (
              <p className="p-4 text-muted-foreground text-center">No active sessions</p>
            ) : (
              sessions.map((session) => (
                <div key={session.id} className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      session.is_current ? 'bg-mise/20' : 'bg-cream-subtle'
                    }`}>
                      <Monitor className={`w-5 h-5 ${session.is_current ? 'text-mise' : 'text-muted-foreground'}`} />
                    </div>
                    <div>
                      <p className="font-medium text-sm flex items-center gap-2">
                        {session.user_agent.includes('Chrome') ? 'Chrome' : 
                         session.user_agent.includes('Firefox') ? 'Firefox' :
                         session.user_agent.includes('Safari') ? 'Safari' : 'Unknown Browser'}
                        {session.is_current && (
                          <span className="text-xs bg-mise/20 text-mise px-2 py-0.5 rounded-full">Current</span>
                        )}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {session.ip_address} • Last active {formatDate(session.last_active)}
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
