import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { adminApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Users,
  Shield,
  Settings,
  Activity,
  Database,
  Key,
  Search,
  ChevronLeft,
  ChevronRight,
  Loader2,
  UserCog,
  Ban,
  CheckCircle,
  Trash2,
  RefreshCw,
  Copy,
  Plus,
  AlertTriangle,
  Clock,
  HardDrive,
  FileText,
  Download,
  X,
  Globe,
  Mail,
  Bell,
  Crown
} from 'lucide-react';
import { toast } from 'sonner';
import { RolesManager } from '../components/RolesManager';

const tabs = [
  { id: 'users', label: 'Users', icon: Users },
  { id: 'roles', label: 'Roles', icon: Crown },
  { id: 'settings', label: 'Settings', icon: Settings },
  { id: 'invites', label: 'Invite Codes', icon: Key },
  { id: 'ip-rules', label: 'IP Rules', icon: Globe },
  { id: 'audit', label: 'Audit Log', icon: FileText },
  { id: 'system', label: 'System', icon: Activity },
];

export const AdminDashboard = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('users');
  const [loading, setLoading] = useState(true);
  
  // Users state
  const [users, setUsers] = useState([]);
  const [userSearch, setUserSearch] = useState('');
  const [userPage, setUserPage] = useState(1);
  const [userTotal, setUserTotal] = useState(0);
  const [selectedUser, setSelectedUser] = useState(null);
  const [showUserModal, setShowUserModal] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  
  // Settings state
  const [settings, setSettings] = useState({
    allow_registration: true,
    allow_admin_registration: false,
    require_invite_code: false,
    password_min_length: 8,
    password_require_uppercase: false,
    password_require_number: false,
    password_require_special: false,
    max_login_attempts: 5,
    lockout_duration_minutes: 15,
    enable_ip_allowlist: false,
    enable_ip_blocklist: false,
    notify_new_login: false,
  });
  const [savingSettings, setSavingSettings] = useState(false);
  
  // Invite codes state
  const [inviteCodes, setInviteCodes] = useState([]);
  const [showCreateInvite, setShowCreateInvite] = useState(false);
  const [newInvite, setNewInvite] = useState({ max_uses: 1, expires_days: 7, grants_admin: false });
  
  // IP Rules state
  const [ipAllowlist, setIpAllowlist] = useState([]);
  const [ipBlocklist, setIpBlocklist] = useState([]);
  const [newIPRule, setNewIPRule] = useState({ ip: '', description: '' });
  const [showAddAllowlist, setShowAddAllowlist] = useState(false);
  const [showAddBlocklist, setShowAddBlocklist] = useState(false);
  
  // Audit logs state
  const [auditLogs, setAuditLogs] = useState([]);
  const [auditPage, setAuditPage] = useState(1);
  const [auditTotal, setAuditTotal] = useState(0);
  
  // System health state
  const [systemHealth, setSystemHealth] = useState(null);
  const [backups, setBackups] = useState([]);
  const [creatingBackup, setCreatingBackup] = useState(false);
  const [backupSettings, setBackupSettings] = useState({
    auto_backup_enabled: false,
    interval_hours: 24,
    max_backups_to_keep: 7
  });

  useEffect(() => {
    // Check admin access
    if (user && user.role !== 'admin') {
      toast.error('Admin access required');
      navigate('/dashboard');
      return;
    }
    
    loadData();
  }, [user, activeTab]);

  useEffect(() => {
    if (activeTab === 'users') {
      loadUsers();
    }
  }, [userPage, userSearch]);

  useEffect(() => {
    if (activeTab === 'audit') {
      loadAuditLogs();
    }
  }, [auditPage]);

  const loadData = async () => {
    setLoading(true);
    try {
      switch (activeTab) {
        case 'users':
          await loadUsers();
          break;
        case 'settings':
          await loadSettings();
          break;
        case 'invites':
          await loadInviteCodes();
          break;
        case 'ip-rules':
          await loadIPRules();
          break;
        case 'audit':
          await loadAuditLogs();
          break;
        case 'system':
          await loadSystemHealth();
          break;
      }
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    try {
      const res = await adminApi.listUsers({ page: userPage, per_page: 20, search: userSearch || undefined });
      setUsers(res.data.users);
      setUserTotal(res.data.total);
    } catch (error) {
      console.error('Failed to load users:', error);
    }
  };

  const loadSettings = async () => {
    try {
      const res = await adminApi.getSettings();
      setSettings(res.data);
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  };

  const loadInviteCodes = async () => {
    try {
      const res = await adminApi.listInviteCodes();
      setInviteCodes(res.data.codes || []);
    } catch (error) {
      console.error('Failed to load invite codes:', error);
    }
  };

  const loadIPRules = async () => {
    try {
      const res = await adminApi.getIPRules();
      setIpAllowlist(res.data.allowlist || []);
      setIpBlocklist(res.data.blocklist || []);
    } catch (error) {
      console.error('Failed to load IP rules:', error);
    }
  };

  const loadAuditLogs = async () => {
    try {
      const res = await adminApi.getAuditLogs({ page: auditPage, per_page: 50 });
      setAuditLogs(res.data.logs || []);
      setAuditTotal(res.data.total || 0);
    } catch (error) {
      console.error('Failed to load audit logs:', error);
    }
  };

  const loadSystemHealth = async () => {
    try {
      const [healthRes, backupsRes, backupSettingsRes] = await Promise.all([
        adminApi.getSystemHealth(),
        adminApi.listBackups(),
        adminApi.getBackupSettings().catch(() => ({ data: {} }))
      ]);
      setSystemHealth(healthRes.data);
      setBackups(backupsRes.data.backups || []);
      if (backupSettingsRes.data) {
        setBackupSettings({
          auto_backup_enabled: backupSettingsRes.data.auto_backup_enabled || false,
          interval_hours: backupSettingsRes.data.interval_hours || 24,
          max_backups_to_keep: backupSettingsRes.data.max_backups_to_keep || 7
        });
      }
    } catch (error) {
      console.error('Failed to load system health:', error);
    }
  };

  // User actions
  const handleUserAction = async (action, userId) => {
    setActionLoading(true);
    try {
      switch (action) {
        case 'suspend':
          await adminApi.updateUserStatus(userId, 'suspended');
          toast.success('User suspended');
          break;
        case 'activate':
          await adminApi.updateUserStatus(userId, 'active');
          toast.success('User activated');
          break;
        case 'make-admin':
          await adminApi.updateUserRole(userId, 'admin');
          toast.success('User promoted to admin');
          break;
        case 'remove-admin':
          await adminApi.updateUserRole(userId, 'user');
          toast.success('Admin role removed');
          break;
        case 'reset-password':
          if (!newPassword || newPassword.length < 8) {
            toast.error('Password must be at least 8 characters');
            return;
          }
          await adminApi.resetUserPassword(userId, newPassword);
          toast.success('Password reset successfully');
          setNewPassword('');
          break;
        case 'delete':
          if (window.confirm('Are you sure you want to delete this user?')) {
            await adminApi.deleteUser(userId, false);
            toast.success('User deleted');
          }
          break;
        case 'delete-permanent':
          if (window.confirm('PERMANENT DELETE: This cannot be undone. Continue?')) {
            await adminApi.deleteUser(userId, true);
            toast.success('User permanently deleted');
          }
          break;
      }
      await loadUsers();
      setShowUserModal(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Action failed');
    } finally {
      setActionLoading(false);
    }
  };

  // Settings actions
  const handleSaveSettings = async () => {
    setSavingSettings(true);
    try {
      await adminApi.updateSettings(settings);
      toast.success('Settings saved');
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setSavingSettings(false);
    }
  };

  // Invite code actions
  const handleCreateInvite = async () => {
    try {
      const res = await adminApi.createInviteCode(newInvite);
      toast.success('Invite code created');
      setInviteCodes([res.data, ...inviteCodes]);
      setShowCreateInvite(false);
      setNewInvite({ max_uses: 1, expires_days: 7, grants_admin: false });
    } catch (error) {
      toast.error('Failed to create invite code');
    }
  };

  const handleDeleteInvite = async (codeId) => {
    try {
      await adminApi.deleteInviteCode(codeId);
      setInviteCodes(inviteCodes.filter(c => c.id !== codeId));
      toast.success('Invite code deleted');
    } catch (error) {
      toast.error('Failed to delete invite code');
    }
  };

  const copyInviteCode = (code) => {
    navigator.clipboard.writeText(code);
    toast.success('Code copied to clipboard');
  };

  // IP Rules actions
  const handleAddAllowlist = async () => {
    if (!newIPRule.ip) {
      toast.error('Please enter an IP address or pattern');
      return;
    }
    try {
      const res = await adminApi.addIPAllowlist(newIPRule.ip, newIPRule.description);
      setIpAllowlist([res.data, ...ipAllowlist]);
      setNewIPRule({ ip: '', description: '' });
      setShowAddAllowlist(false);
      toast.success('IP added to allowlist');
    } catch (error) {
      toast.error('Failed to add IP');
    }
  };

  const handleAddBlocklist = async () => {
    if (!newIPRule.ip) {
      toast.error('Please enter an IP address or pattern');
      return;
    }
    try {
      const res = await adminApi.addIPBlocklist(newIPRule.ip, newIPRule.description);
      setIpBlocklist([res.data, ...ipBlocklist]);
      setNewIPRule({ ip: '', description: '' });
      setShowAddBlocklist(false);
      toast.success('IP added to blocklist');
    } catch (error) {
      toast.error('Failed to add IP');
    }
  };

  const handleRemoveAllowlist = async (ruleId) => {
    try {
      await adminApi.removeIPAllowlist(ruleId);
      setIpAllowlist(ipAllowlist.filter(r => r.id !== ruleId));
      toast.success('IP removed from allowlist');
    } catch (error) {
      toast.error('Failed to remove IP');
    }
  };

  const handleRemoveBlocklist = async (ruleId) => {
    try {
      await adminApi.removeIPBlocklist(ruleId);
      setIpBlocklist(ipBlocklist.filter(r => r.id !== ruleId));
      toast.success('IP removed from blocklist');
    } catch (error) {
      toast.error('Failed to remove IP');
    }
  };

  // Export user data
  const handleExportUserData = async (userId) => {
    try {
      const token = localStorage.getItem('token');
      const url = adminApi.downloadUserData(userId);
      
      // Open download in new window with auth
      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      if (response.ok) {
        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `user_export_${userId}.zip`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(downloadUrl);
        toast.success('Data exported successfully');
      } else {
        toast.error('Failed to export data');
      }
    } catch (error) {
      toast.error('Failed to export data');
    }
  };

  // Backup actions
  const handleCreateBackup = async () => {
    setCreatingBackup(true);
    try {
      await adminApi.createBackup();
      toast.success('Backup started');
      setTimeout(() => loadSystemHealth(), 2000);
    } catch (error) {
      toast.error('Failed to start backup');
    } finally {
      setCreatingBackup(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleString();
  };

  const totalPages = Math.ceil(userTotal / 20);

  return (
    <Layout>
      <div className="max-w-6xl mx-auto space-y-6" data-testid="admin-dashboard">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="font-heading text-3xl font-bold flex items-center gap-2">
            <Shield className="w-8 h-8 text-mise" />
            Admin Dashboard
          </h1>
          <p className="text-muted-foreground mt-1">Manage users, settings, and system health</p>
        </motion.div>

        {/* Tab Bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="bg-white dark:bg-card rounded-xl border border-border/60 p-1 flex gap-1 overflow-x-auto"
        >
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
                  isActive
                    ? 'bg-mise text-white shadow-sm'
                    : 'text-muted-foreground hover:text-foreground hover:bg-cream-subtle'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </motion.div>

        {/* Content */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="w-8 h-8 animate-spin text-mise" />
            </div>
          ) : (
            <>
              {/* Users Tab */}
              {activeTab === 'users' && (
                <div className="space-y-4">
                  {/* Search */}
                  <div className="flex gap-4">
                    <div className="relative flex-1">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        placeholder="Search users by email or name..."
                        value={userSearch}
                        onChange={(e) => {
                          setUserSearch(e.target.value);
                          setUserPage(1);
                        }}
                        className="pl-10 rounded-xl"
                      />
                    </div>
                    <Button variant="outline" onClick={loadUsers} className="rounded-xl">
                      <RefreshCw className="w-4 h-4" />
                    </Button>
                  </div>

                  {/* Users Table */}
                  <div className="bg-white dark:bg-card rounded-xl border border-border/60 overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead className="bg-cream-subtle">
                          <tr>
                            <th className="text-left p-4 font-medium text-sm">User</th>
                            <th className="text-left p-4 font-medium text-sm">Role</th>
                            <th className="text-left p-4 font-medium text-sm">Status</th>
                            <th className="text-left p-4 font-medium text-sm">Created</th>
                            <th className="text-left p-4 font-medium text-sm">Last Login</th>
                            <th className="text-right p-4 font-medium text-sm">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border/60">
                          {users.map((u) => (
                            <tr key={u.id} className="hover:bg-cream-subtle/50">
                              <td className="p-4">
                                <div>
                                  <p className="font-medium">{u.name}</p>
                                  <p className="text-sm text-muted-foreground">{u.email}</p>
                                </div>
                              </td>
                              <td className="p-4">
                                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                  u.role === 'admin' 
                                    ? 'bg-mise/20 text-mise' 
                                    : 'bg-gray-100 text-gray-600'
                                }`}>
                                  {u.role}
                                </span>
                              </td>
                              <td className="p-4">
                                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                  u.status === 'active' 
                                    ? 'bg-green-100 text-green-700' 
                                    : u.status === 'suspended'
                                    ? 'bg-red-100 text-red-700'
                                    : 'bg-gray-100 text-gray-600'
                                }`}>
                                  {u.status || 'active'}
                                </span>
                              </td>
                              <td className="p-4 text-sm text-muted-foreground">
                                {formatDate(u.created_at)}
                              </td>
                              <td className="p-4 text-sm text-muted-foreground">
                                {formatDate(u.last_login)}
                              </td>
                              <td className="p-4 text-right">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    setSelectedUser(u);
                                    setShowUserModal(true);
                                  }}
                                  disabled={u.id === user?.id}
                                >
                                  <UserCog className="w-4 h-4" />
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    {/* Pagination */}
                    {totalPages > 1 && (
                      <div className="p-4 border-t border-border/60 flex items-center justify-between">
                        <p className="text-sm text-muted-foreground">
                          Showing {(userPage - 1) * 20 + 1} to {Math.min(userPage * 20, userTotal)} of {userTotal} users
                        </p>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setUserPage(p => Math.max(1, p - 1))}
                            disabled={userPage === 1}
                          >
                            <ChevronLeft className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setUserPage(p => Math.min(totalPages, p + 1))}
                            disabled={userPage === totalPages}
                          >
                            <ChevronRight className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Roles Tab */}
              {activeTab === 'roles' && (
                <RolesManager />
              )}

              {/* Settings Tab */}
              {activeTab === 'settings' && (
                <div className="bg-white dark:bg-card rounded-xl border border-border/60 p-6 space-y-6">
                  <h2 className="font-heading font-semibold text-lg">Registration Settings</h2>
                  
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Allow Registration</p>
                        <p className="text-sm text-muted-foreground">Allow new users to register</p>
                      </div>
                      <Switch
                        checked={settings.allow_registration}
                        onCheckedChange={(checked) => setSettings({ ...settings, allow_registration: checked })}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Allow Admin Self-Registration</p>
                        <p className="text-sm text-muted-foreground">Let users choose admin role during signup</p>
                      </div>
                      <Switch
                        checked={settings.allow_admin_registration}
                        onCheckedChange={(checked) => setSettings({ ...settings, allow_admin_registration: checked })}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Require Invite Code</p>
                        <p className="text-sm text-muted-foreground">Require an invite code to register</p>
                      </div>
                      <Switch
                        checked={settings.require_invite_code}
                        onCheckedChange={(checked) => setSettings({ ...settings, require_invite_code: checked })}
                      />
                    </div>
                  </div>

                  <hr className="border-border/60" />

                  <h2 className="font-heading font-semibold text-lg">Password Policy</h2>
                  
                  <div className="space-y-4">
                    <div>
                      <Label>Minimum Password Length</Label>
                      <Input
                        type="number"
                        min={6}
                        max={32}
                        value={settings.password_min_length}
                        onChange={(e) => setSettings({ ...settings, password_min_length: parseInt(e.target.value) || 8 })}
                        className="w-24 mt-1 rounded-xl"
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Require Uppercase Letter</p>
                      </div>
                      <Switch
                        checked={settings.password_require_uppercase}
                        onCheckedChange={(checked) => setSettings({ ...settings, password_require_uppercase: checked })}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Require Number</p>
                      </div>
                      <Switch
                        checked={settings.password_require_number}
                        onCheckedChange={(checked) => setSettings({ ...settings, password_require_number: checked })}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Require Special Character</p>
                      </div>
                      <Switch
                        checked={settings.password_require_special}
                        onCheckedChange={(checked) => setSettings({ ...settings, password_require_special: checked })}
                      />
                    </div>
                  </div>

                  <hr className="border-border/60" />

                  <h2 className="font-heading font-semibold text-lg">Security</h2>
                  
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label>Max Login Attempts</Label>
                        <Input
                          type="number"
                          min={1}
                          max={20}
                          value={settings.max_login_attempts}
                          onChange={(e) => setSettings({ ...settings, max_login_attempts: parseInt(e.target.value) || 5 })}
                          className="mt-1 rounded-xl"
                        />
                      </div>
                      <div>
                        <Label>Lockout Duration (minutes)</Label>
                        <Input
                          type="number"
                          min={1}
                          max={1440}
                          value={settings.lockout_duration_minutes}
                          onChange={(e) => setSettings({ ...settings, lockout_duration_minutes: parseInt(e.target.value) || 15 })}
                          className="mt-1 rounded-xl"
                        />
                      </div>
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Enable IP Allowlist</p>
                        <p className="text-sm text-muted-foreground">Only allow specific IPs to access the app</p>
                      </div>
                      <Switch
                        checked={settings.enable_ip_allowlist}
                        onCheckedChange={(checked) => setSettings({ ...settings, enable_ip_allowlist: checked })}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">Enable IP Blocklist</p>
                        <p className="text-sm text-muted-foreground">Block specific IPs from accessing the app</p>
                      </div>
                      <Switch
                        checked={settings.enable_ip_blocklist}
                        onCheckedChange={(checked) => setSettings({ ...settings, enable_ip_blocklist: checked })}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">New Login Notifications</p>
                        <p className="text-sm text-muted-foreground">Email users when they sign in from a new device</p>
                      </div>
                      <Switch
                        checked={settings.notify_new_login}
                        onCheckedChange={(checked) => setSettings({ ...settings, notify_new_login: checked })}
                      />
                    </div>
                  </div>

                  <Button
                    onClick={handleSaveSettings}
                    disabled={savingSettings}
                    className="rounded-full bg-mise hover:bg-mise-dark"
                  >
                    {savingSettings ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                    Save Settings
                  </Button>
                </div>
              )}

              {/* Invite Codes Tab */}
              {activeTab === 'invites' && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <h2 className="font-heading font-semibold text-lg">Invite Codes</h2>
                    <Button
                      onClick={() => setShowCreateInvite(true)}
                      className="rounded-full bg-mise hover:bg-mise-dark"
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Create Code
                    </Button>
                  </div>

                  {showCreateInvite && (
                    <div className="bg-white dark:bg-card rounded-xl border border-border/60 p-4 space-y-4">
                      <div className="grid grid-cols-3 gap-4">
                        <div>
                          <Label>Max Uses</Label>
                          <Input
                            type="number"
                            min={1}
                            value={newInvite.max_uses}
                            onChange={(e) => setNewInvite({ ...newInvite, max_uses: parseInt(e.target.value) || 1 })}
                            className="mt-1 rounded-xl"
                          />
                        </div>
                        <div>
                          <Label>Expires In (days)</Label>
                          <Input
                            type="number"
                            min={1}
                            value={newInvite.expires_days}
                            onChange={(e) => setNewInvite({ ...newInvite, expires_days: parseInt(e.target.value) || 7 })}
                            className="mt-1 rounded-xl"
                          />
                        </div>
                        <div className="flex items-end">
                          <label className="flex items-center gap-2">
                            <Switch
                              checked={newInvite.grants_admin}
                              onCheckedChange={(checked) => setNewInvite({ ...newInvite, grants_admin: checked })}
                            />
                            <span className="text-sm">Grants Admin</span>
                          </label>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button onClick={handleCreateInvite} className="rounded-full bg-mise hover:bg-mise-dark">
                          Create
                        </Button>
                        <Button variant="outline" onClick={() => setShowCreateInvite(false)} className="rounded-full">
                          Cancel
                        </Button>
                      </div>
                    </div>
                  )}

                  <div className="bg-white dark:bg-card rounded-xl border border-border/60 overflow-hidden">
                    <table className="w-full">
                      <thead className="bg-cream-subtle">
                        <tr>
                          <th className="text-left p-4 font-medium text-sm">Code</th>
                          <th className="text-left p-4 font-medium text-sm">Uses</th>
                          <th className="text-left p-4 font-medium text-sm">Grants Admin</th>
                          <th className="text-left p-4 font-medium text-sm">Expires</th>
                          <th className="text-right p-4 font-medium text-sm">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {inviteCodes.length === 0 ? (
                          <tr>
                            <td colSpan={5} className="p-8 text-center text-muted-foreground">
                              No invite codes created yet
                            </td>
                          </tr>
                        ) : inviteCodes.map((code) => (
                          <tr key={code.id}>
                            <td className="p-4">
                              <code className="bg-cream-subtle px-2 py-1 rounded">{code.code}</code>
                            </td>
                            <td className="p-4">{code.uses} / {code.max_uses}</td>
                            <td className="p-4">
                              {code.grants_admin ? (
                                <span className="text-mise">Yes</span>
                              ) : (
                                <span className="text-muted-foreground">No</span>
                              )}
                            </td>
                            <td className="p-4 text-sm text-muted-foreground">
                              {code.expires_at ? formatDate(code.expires_at) : 'Never'}
                            </td>
                            <td className="p-4 text-right">
                              <Button variant="ghost" size="sm" onClick={() => copyInviteCode(code.code)}>
                                <Copy className="w-4 h-4" />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => handleDeleteInvite(code.id)}>
                                <Trash2 className="w-4 h-4 text-red-500" />
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* IP Rules Tab */}
              {activeTab === 'ip-rules' && (
                <div className="space-y-6">
                  {/* Allowlist */}
                  <div className="bg-white dark:bg-card rounded-xl border border-border/60 p-4">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="font-heading font-semibold flex items-center gap-2">
                          <CheckCircle className="w-5 h-5 text-green-600" />
                          IP Allowlist
                        </h3>
                        <p className="text-sm text-muted-foreground">Only these IPs can access when enabled</p>
                      </div>
                      <Button
                        size="sm"
                        onClick={() => setShowAddAllowlist(true)}
                        className="rounded-full bg-mise hover:bg-mise-dark"
                      >
                        <Plus className="w-4 h-4 mr-1" /> Add IP
                      </Button>
                    </div>

                    {showAddAllowlist && (
                      <div className="p-3 bg-cream-subtle rounded-lg mb-4 space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                          <Input
                            placeholder="IP address (e.g., 192.168.1.0/24)"
                            value={newIPRule.ip}
                            onChange={(e) => setNewIPRule({ ...newIPRule, ip: e.target.value })}
                            className="rounded-lg"
                          />
                          <Input
                            placeholder="Description (optional)"
                            value={newIPRule.description}
                            onChange={(e) => setNewIPRule({ ...newIPRule, description: e.target.value })}
                            className="rounded-lg"
                          />
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" onClick={handleAddAllowlist} className="rounded-full bg-mise hover:bg-mise-dark">
                            Add
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => { setShowAddAllowlist(false); setNewIPRule({ ip: '', description: '' }); }} className="rounded-full">
                            Cancel
                          </Button>
                        </div>
                      </div>
                    )}

                    {ipAllowlist.length === 0 ? (
                      <p className="text-muted-foreground text-sm">No IPs in allowlist</p>
                    ) : (
                      <div className="space-y-2">
                        {ipAllowlist.map((rule) => (
                          <div key={rule.id} className="flex items-center justify-between p-2 bg-cream-subtle rounded-lg">
                            <div>
                              <code className="text-sm font-mono">{rule.ip_pattern}</code>
                              {rule.description && <span className="text-xs text-muted-foreground ml-2">({rule.description})</span>}
                            </div>
                            <Button variant="ghost" size="sm" onClick={() => handleRemoveAllowlist(rule.id)}>
                              <Trash2 className="w-4 h-4 text-red-500" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Blocklist */}
                  <div className="bg-white dark:bg-card rounded-xl border border-border/60 p-4">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="font-heading font-semibold flex items-center gap-2">
                          <Ban className="w-5 h-5 text-red-600" />
                          IP Blocklist
                        </h3>
                        <p className="text-sm text-muted-foreground">These IPs are blocked when enabled</p>
                      </div>
                      <Button
                        size="sm"
                        onClick={() => setShowAddBlocklist(true)}
                        className="rounded-full bg-red-600 hover:bg-red-700 text-white"
                      >
                        <Plus className="w-4 h-4 mr-1" /> Block IP
                      </Button>
                    </div>

                    {showAddBlocklist && (
                      <div className="p-3 bg-red-50 rounded-lg mb-4 space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                          <Input
                            placeholder="IP address (e.g., 192.168.1.100)"
                            value={newIPRule.ip}
                            onChange={(e) => setNewIPRule({ ...newIPRule, ip: e.target.value })}
                            className="rounded-lg"
                          />
                          <Input
                            placeholder="Reason (optional)"
                            value={newIPRule.description}
                            onChange={(e) => setNewIPRule({ ...newIPRule, description: e.target.value })}
                            className="rounded-lg"
                          />
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" onClick={handleAddBlocklist} className="rounded-full bg-red-600 hover:bg-red-700 text-white">
                            Block
                          </Button>
                          <Button size="sm" variant="outline" onClick={() => { setShowAddBlocklist(false); setNewIPRule({ ip: '', description: '' }); }} className="rounded-full">
                            Cancel
                          </Button>
                        </div>
                      </div>
                    )}

                    {ipBlocklist.length === 0 ? (
                      <p className="text-muted-foreground text-sm">No IPs blocked</p>
                    ) : (
                      <div className="space-y-2">
                        {ipBlocklist.map((rule) => (
                          <div key={rule.id} className="flex items-center justify-between p-2 bg-red-50 rounded-lg">
                            <div>
                              <code className="text-sm font-mono text-red-700">{rule.ip_pattern}</code>
                              {rule.description && <span className="text-xs text-muted-foreground ml-2">({rule.description})</span>}
                            </div>
                            <Button variant="ghost" size="sm" onClick={() => handleRemoveBlocklist(rule.id)}>
                              <X className="w-4 h-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <p className="text-xs text-muted-foreground">
                    Supports exact IPs, CIDR notation (e.g., 192.168.1.0/24), and wildcards (e.g., 192.168.*.*)
                  </p>
                </div>
              )}

              {/* Audit Log Tab */}
              {activeTab === 'audit' && (
                <div className="bg-white dark:bg-card rounded-xl border border-border/60 overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-cream-subtle">
                        <tr>
                          <th className="text-left p-4 font-medium text-sm">Time</th>
                          <th className="text-left p-4 font-medium text-sm">User</th>
                          <th className="text-left p-4 font-medium text-sm">Action</th>
                          <th className="text-left p-4 font-medium text-sm">Details</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border/60">
                        {auditLogs.length === 0 ? (
                          <tr>
                            <td colSpan={4} className="p-8 text-center text-muted-foreground">
                              No audit logs yet
                            </td>
                          </tr>
                        ) : auditLogs.map((log) => (
                          <tr key={log.id}>
                            <td className="p-4 text-sm text-muted-foreground">
                              {formatDate(log.timestamp)}
                            </td>
                            <td className="p-4 text-sm">{log.user_email}</td>
                            <td className="p-4">
                              <span className="px-2 py-1 bg-cream-subtle rounded text-sm">
                                {log.action}
                              </span>
                            </td>
                            <td className="p-4 text-sm text-muted-foreground">
                              {log.target_type && `${log.target_type}: ${log.target_id?.slice(0, 8)}...`}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* System Tab */}
              {activeTab === 'system' && systemHealth && (
                <div className="space-y-4">
                  {/* Health Cards */}
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="bg-white dark:bg-card rounded-xl border border-border/60 p-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                          systemHealth.status === 'healthy' ? 'bg-green-100' : 'bg-amber-100'
                        }`}>
                          <Activity className={`w-5 h-5 ${
                            systemHealth.status === 'healthy' ? 'text-green-600' : 'text-amber-600'
                          }`} />
                        </div>
                        <div>
                          <p className="text-sm text-muted-foreground">Status</p>
                          <p className="font-semibold capitalize">{systemHealth.status}</p>
                        </div>
                      </div>
                    </div>

                    <div className="bg-white dark:bg-card rounded-xl border border-border/60 p-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-blue-100 flex items-center justify-center">
                          <Users className="w-5 h-5 text-blue-600" />
                        </div>
                        <div>
                          <p className="text-sm text-muted-foreground">Users</p>
                          <p className="font-semibold">{systemHealth.users.total}</p>
                        </div>
                      </div>
                    </div>

                    <div className="bg-white dark:bg-card rounded-xl border border-border/60 p-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-purple-100 flex items-center justify-center">
                          <Database className="w-5 h-5 text-purple-600" />
                        </div>
                        <div>
                          <p className="text-sm text-muted-foreground">Database</p>
                          <p className="font-semibold">{systemHealth.database.size_mb} MB</p>
                        </div>
                      </div>
                    </div>

                    <div className="bg-white dark:bg-card rounded-xl border border-border/60 p-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-orange-100 flex items-center justify-center">
                          <HardDrive className="w-5 h-5 text-orange-600" />
                        </div>
                        <div>
                          <p className="text-sm text-muted-foreground">Storage</p>
                          <p className="font-semibold">{systemHealth.storage.used_mb} MB</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Backups */}
                  <div className="bg-white dark:bg-card rounded-xl border border-border/60 p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="font-heading font-semibold">Backups</h3>
                      <Button
                        onClick={handleCreateBackup}
                        disabled={creatingBackup}
                        className="rounded-full bg-mise hover:bg-mise-dark"
                      >
                        {creatingBackup ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Download className="w-4 h-4 mr-2" />}
                        Create Backup
                      </Button>
                    </div>

                    {backups.length === 0 ? (
                      <p className="text-muted-foreground text-center py-4">No backups created yet</p>
                    ) : (
                      <div className="space-y-2">
                        {backups.map((backup) => (
                          <div key={backup.id} className="flex items-center justify-between p-3 bg-cream-subtle rounded-lg">
                            <div>
                              <p className="font-medium text-sm">{formatDate(backup.created_at)}</p>
                              <p className="text-xs text-muted-foreground">
                                {backup.status} • {Math.round((backup.size_bytes || 0) / 1024)} KB
                              </p>
                            </div>
                            <span className={`px-2 py-1 rounded text-xs ${
                              backup.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                            }`}>
                              {backup.status}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Backup Settings */}
                  <div className="bg-white dark:bg-card rounded-xl border border-border/60 p-4">
                    <h3 className="font-heading font-semibold mb-4">Automatic Backups</h3>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium">Enable Auto Backup</p>
                          <p className="text-sm text-muted-foreground">Automatically create backups on schedule</p>
                        </div>
                        <Switch
                          checked={backupSettings.auto_backup_enabled}
                          onCheckedChange={(checked) => setBackupSettings({ ...backupSettings, auto_backup_enabled: checked })}
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <Label>Interval (hours)</Label>
                          <Input
                            type="number"
                            min={1}
                            max={168}
                            value={backupSettings.interval_hours}
                            onChange={(e) => setBackupSettings({ ...backupSettings, interval_hours: parseInt(e.target.value) || 24 })}
                            className="mt-1 rounded-xl"
                          />
                        </div>
                        <div>
                          <Label>Keep Last N Backups</Label>
                          <Input
                            type="number"
                            min={1}
                            max={30}
                            value={backupSettings.max_backups_to_keep}
                            onChange={(e) => setBackupSettings({ ...backupSettings, max_backups_to_keep: parseInt(e.target.value) || 7 })}
                            className="mt-1 rounded-xl"
                          />
                        </div>
                      </div>
                      <Button
                        onClick={async () => {
                          try {
                            await adminApi.updateBackupSettings(
                              backupSettings.auto_backup_enabled,
                              backupSettings.interval_hours,
                              backupSettings.max_backups_to_keep
                            );
                            toast.success('Backup settings saved');
                          } catch (error) {
                            toast.error('Failed to save backup settings');
                          }
                        }}
                        className="rounded-full bg-mise hover:bg-mise-dark"
                      >
                        Save Backup Settings
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </motion.div>

        {/* User Action Modal */}
        {showUserModal && selectedUser && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-white dark:bg-card rounded-2xl p-6 max-w-md w-full"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-heading font-semibold text-lg">Manage User</h3>
                <Button variant="ghost" size="sm" onClick={() => setShowUserModal(false)}>
                  <X className="w-4 h-4" />
                </Button>
              </div>

              <div className="space-y-4">
                <div className="p-4 bg-cream-subtle rounded-xl">
                  <p className="font-medium">{selectedUser.name}</p>
                  <p className="text-sm text-muted-foreground">{selectedUser.email}</p>
                  <div className="flex gap-2 mt-2">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      selectedUser.role === 'admin' ? 'bg-mise/20 text-mise' : 'bg-gray-100'
                    }`}>
                      {selectedUser.role}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      selectedUser.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {selectedUser.status || 'active'}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div className="space-y-2">
                  {selectedUser.status === 'active' ? (
                    <Button
                      variant="outline"
                      className="w-full justify-start rounded-xl"
                      onClick={() => handleUserAction('suspend', selectedUser.id)}
                      disabled={actionLoading}
                    >
                      <Ban className="w-4 h-4 mr-2" />
                      Suspend User
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      className="w-full justify-start rounded-xl"
                      onClick={() => handleUserAction('activate', selectedUser.id)}
                      disabled={actionLoading}
                    >
                      <CheckCircle className="w-4 h-4 mr-2" />
                      Activate User
                    </Button>
                  )}

                  {selectedUser.role === 'admin' ? (
                    <Button
                      variant="outline"
                      className="w-full justify-start rounded-xl"
                      onClick={() => handleUserAction('remove-admin', selectedUser.id)}
                      disabled={actionLoading}
                    >
                      <Shield className="w-4 h-4 mr-2" />
                      Remove Admin Role
                    </Button>
                  ) : (
                    <Button
                      variant="outline"
                      className="w-full justify-start rounded-xl"
                      onClick={() => handleUserAction('make-admin', selectedUser.id)}
                      disabled={actionLoading}
                    >
                      <Shield className="w-4 h-4 mr-2" />
                      Make Admin
                    </Button>
                  )}

                  <div className="p-3 border border-border/60 rounded-xl space-y-2">
                    <Label>Reset Password</Label>
                    <div className="flex gap-2">
                      <Input
                        type="password"
                        placeholder="New password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        className="rounded-lg"
                      />
                      <Button
                        onClick={() => handleUserAction('reset-password', selectedUser.id)}
                        disabled={actionLoading || !newPassword}
                        className="rounded-lg"
                      >
                        Reset
                      </Button>
                    </div>
                  </div>

                  {/* Data Export (GDPR) */}
                  <Button
                    variant="outline"
                    className="w-full justify-start rounded-xl"
                    onClick={() => handleExportUserData(selectedUser.id)}
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Export User Data (GDPR)
                  </Button>

                  <hr className="border-border/60" />

                  <Button
                    variant="outline"
                    className="w-full justify-start rounded-xl text-red-600 border-red-200 hover:bg-red-50"
                    onClick={() => handleUserAction('delete', selectedUser.id)}
                    disabled={actionLoading}
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Delete User (Soft)
                  </Button>

                  <Button
                    variant="outline"
                    className="w-full justify-start rounded-xl text-red-600 border-red-200 hover:bg-red-50"
                    onClick={() => handleUserAction('delete-permanent', selectedUser.id)}
                    disabled={actionLoading}
                  >
                    <AlertTriangle className="w-4 h-4 mr-2" />
                    Delete Permanently
                  </Button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </div>
    </Layout>
  );
};
