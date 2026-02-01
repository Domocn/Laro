import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { configApi, llmApi, notificationApi, promptsApi, authApi, householdApi, importApi, apiTokensApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Settings as SettingsIcon,
  Server,
  User,
  Users,
  LogOut,
  Cpu,
  Globe,
  Wifi,
  ChevronRight,
  Loader2,
  Check,
  AlertCircle,
  Sparkles,
  Cloud,
  HardDrive,
  Bug,
  MessageSquare,
  Download,
  WifiOff,
  Bell,
  BellOff,
  Moon,
  Sun,
  Palette,
  Edit3,
  RotateCcw,
  FileText,
  Trash2,
  AlertTriangle,
  Upload,
  Copy,
  UserPlus,
  Key,
  Shield,
  X
} from 'lucide-react';
import { toast } from 'sonner';
import { Switch } from '../components/ui/switch';

const allTabs = [
  { id: 'user', label: 'User', icon: User },
  { id: 'ai', label: 'AI', icon: Sparkles },
  { id: 'household', label: 'Household', icon: Users },
  { id: 'admin', label: 'Admin', icon: Server },
];

export const Settings = () => {
  const navigate = useNavigate();
  const { user, household, logout } = useAuth();
  const [serverInfo, setServerInfo] = useState(null);
  const [isCloud, setIsCloud] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('user');

  // Filter tabs based on cloud mode - hide AI settings for cloud users
  const tabs = isCloud ? allTabs.filter(tab => tab.id !== 'ai') : allTabs;
  
  // LLM Settings
  const [llmSettings, setLlmSettings] = useState({
    provider: 'openai',
    ollama_url: 'http://localhost:11434',
    ollama_model: 'llama3',
    embedded_model: 'Phi-3-mini-4k-instruct.Q4_0.gguf'
  });
  const [availableModels, setAvailableModels] = useState([]);
  const [embeddedModels, setEmbeddedModels] = useState([]);
  const [testingLlm, setTestingLlm] = useState(false);
  const [llmTestResult, setLlmTestResult] = useState(null);
  const [savingLlm, setSavingLlm] = useState(false);

  // Notification Settings
  const [notificationSettings, setNotificationSettings] = useState({
    enabled: false,
    meal_reminders: true,
    reminder_time: 30,
    shopping_reminders: true,
    weekly_plan_reminder: true
  });
  const [notificationPermission, setNotificationPermission] = useState('default');
  const [savingNotifications, setSavingNotifications] = useState(false);
  const [subscribing, setSubscribing] = useState(false);

  // Custom AI Prompts
  const [customPrompts, setCustomPrompts] = useState({
    recipe_extraction: '',
    meal_planning: '',
    fridge_search: ''
  });
  const [defaultPrompts, setDefaultPrompts] = useState({});
  const [savingPrompts, setSavingPrompts] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState(null);

  // Profile Settings
  const [profileName, setProfileName] = useState('');
  const [profileEmail, setProfileEmail] = useState('');
  const [savingProfile, setSavingProfile] = useState(false);

  // Allergies
  const [allergies, setAllergies] = useState([]);
  const [newAllergy, setNewAllergy] = useState('');
  const [savingAllergies, setSavingAllergies] = useState(false);

  // Household
  const [householdMembers, setHouseholdMembers] = useState([]);
  const [joinCode, setJoinCode] = useState(null);
  const [joinCodeExpires, setJoinCodeExpires] = useState(null);
  const [joinCodeInput, setJoinCodeInput] = useState('');
  const [generatingCode, setGeneratingCode] = useState(false);
  const [joiningHousehold, setJoiningHousehold] = useState(false);

  // Import
  const [importFile, setImportFile] = useState(null);
  const [importing, setImporting] = useState(false);

  // Danger Zone
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmText, setDeleteConfirmText] = useState('');
  const [deleting, setDeleting] = useState(false);

  // API Tokens
  const [apiTokens, setApiTokens] = useState([]);
  const [loadingTokens, setLoadingTokens] = useState(false);
  const [newTokenName, setNewTokenName] = useState('');
  const [newTokenExpiry, setNewTokenExpiry] = useState('never');
  const [creatingToken, setCreatingToken] = useState(false);
  const [newlyCreatedToken, setNewlyCreatedToken] = useState(null);
  const [showCreateToken, setShowCreateToken] = useState(false);

  // Theme Settings
  const [darkMode, setDarkMode] = useState(() => {
    // Check localStorage or system preference
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('mise_dark_mode');
      if (saved !== null) return saved === 'true';
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return false;
  });

  useEffect(() => {
    loadData();
    checkNotificationPermission();
  }, []);

  // Apply dark mode to document
  useEffect(() => {
    if (darkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('mise_dark_mode', String(darkMode));
  }, [darkMode]);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
    toast.success(darkMode ? 'Light mode enabled' : 'Dark mode enabled');
  };

  const checkNotificationPermission = () => {
    if ('Notification' in window) {
      setNotificationPermission(Notification.permission);
    }
  };

  // Reset tab if AI tab is selected but we're in cloud mode
  useEffect(() => {
    if (isCloud && activeTab === 'ai') {
      setActiveTab('user');
    }
  }, [isCloud, activeTab]);

  const loadData = async () => {
    try {
      const [serverRes, llmRes, notifRes, promptsRes] = await Promise.all([
        configApi.getConfig(),
        llmApi.getSettings(),
        notificationApi.getSettings().catch(() => ({ data: {} })),
        promptsApi.get().catch(() => ({ data: {} }))
      ]);
      setServerInfo(serverRes.data);
      setIsCloud(serverRes.data?.is_cloud || false);
      setLlmSettings({
        provider: llmRes.data.provider || 'openai',
        ollama_url: llmRes.data.ollama_url || 'http://localhost:11434',
        ollama_model: llmRes.data.ollama_model || 'llama3',
        embedded_model: llmRes.data.embedded_model || 'Phi-3-mini-4k-instruct.Q4_0.gguf'
      });
      if (llmRes.data.embedded_models) {
        setEmbeddedModels(llmRes.data.embedded_models);
      }

      // Load notification settings
      if (notifRes.data) {
        setNotificationSettings(prev => ({
          ...prev,
          meal_reminders: notifRes.data.meal_reminders ?? true,
          reminder_time: notifRes.data.reminder_time ?? 30,
          shopping_reminders: notifRes.data.shopping_reminders ?? true,
          weekly_plan_reminder: notifRes.data.weekly_plan_reminder ?? true,
          enabled: notifRes.data.enabled ?? false
        }));
      }

      // Load custom prompts
      if (promptsRes.data) {
        setCustomPrompts({
          recipe_extraction: promptsRes.data.recipe_extraction || '',
          meal_planning: promptsRes.data.meal_planning || '',
          fridge_search: promptsRes.data.fridge_search || ''
        });
        if (promptsRes.data.defaults) {
          setDefaultPrompts(promptsRes.data.defaults);
        }
      }

      // Load user profile
      const userRes = await authApi.me();
      if (userRes.data) {
        setProfileName(userRes.data.name || '');
        setProfileEmail(userRes.data.email || '');
        setAllergies(userRes.data.allergies || []);
      }

      // Load household members and join code
      if (user?.household_id) {
        try {
          const [membersRes, householdRes] = await Promise.all([
            householdApi.getMembers(),
            householdApi.getMy()
          ]);
          setHouseholdMembers(membersRes.data || []);
          if (householdRes.data) {
            setJoinCode(householdRes.data.join_code || null);
            setJoinCodeExpires(householdRes.data.join_code_expires || null);
          }
        } catch (e) {
          console.error('Failed to load household data:', e);
        }
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const handleChangeServer = () => {
    navigate('/server');
  };

  const handleTestLlm = async () => {
    setTestingLlm(true);
    setLlmTestResult(null);
    
    try {
      const res = await llmApi.testConnection(llmSettings);
      setLlmTestResult(res.data);
      
      if (res.data.success && res.data.available_models) {
        setAvailableModels(res.data.available_models);
      }
      
      if (res.data.success) {
        toast.success(res.data.mesmise);
      } else {
        toast.error(res.data.mesmise);
      }
    } catch (error) {
      setLlmTestResult({ success: false, mesmise: 'Connection test failed' });
      toast.error('Failed to test connection');
    } finally {
      setTestingLlm(false);
    }
  };

  const handleSaveLlm = async () => {
    setSavingLlm(true);
    try {
      await llmApi.updateSettings(llmSettings);
      toast.success('AI settings saved!');
    } catch (error) {
      toast.error('Failed to save settings');
    } finally {
      setSavingLlm(false);
    }
  };

  // Convert VAPID key from base64 to Uint8Array
  const urlBase64ToUint8Array = (base64String) => {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
      .replace(/-/g, '+')
      .replace(/_/g, '/');
    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  };

  const handleEnableNotifications = async () => {
    setSubscribing(true);
    
    try {
      // Check if notifications are supported
      if (!('Notification' in window)) {
        toast.error('Notifications are not supported in this browser');
        return;
      }

      // Request permission
      const permission = await Notification.requestPermission();
      setNotificationPermission(permission);
      
      if (permission !== 'granted') {
        toast.error('Notification permission denied');
        return;
      }

      // Check for service worker and push manager
      if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        toast.error('Push notifications are not supported');
        return;
      }

      // Get service worker registration
      const registration = await navigator.serviceWorker.ready;
      
      // Check if already subscribed
      let subscription = await registration.pushManager.getSubscription();
      
      if (!subscription) {
        // For demo purposes, we'll create a simple subscription
        // In production, you'd need to generate proper VAPID keys
        // and store the public key on the server
        try {
          subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            // This is a placeholder - in production, use your VAPID public key
            applicationServerKey: urlBase64ToUint8Array(
              'BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U'
            )
          });
        } catch (subscribeError) {
          // If VAPID key fails, try without it (for development)
          console.warn('VAPID subscription failed, notifications may be limited:', subscribeError);
        }
      }

      // Send subscription to server
      if (subscription) {
        await notificationApi.subscribe(subscription.toJSON());
      }

      // Update settings to mark as enabled
      const newSettings = { ...notificationSettings, enabled: true };
      setNotificationSettings(newSettings);
      await notificationApi.updateSettings(newSettings);
      
      toast.success('Notifications enabled!');
    } catch (error) {
      console.error('Failed to enable notifications:', error);
      toast.error('Failed to enable notifications');
    } finally {
      setSubscribing(false);
    }
  };

  const handleDisableNotifications = async () => {
    setSavingNotifications(true);
    try {
      // Unsubscribe from push
      if ('serviceWorker' in navigator) {
        const registration = await navigator.serviceWorker.ready;
        const subscription = await registration.pushManager.getSubscription();
        if (subscription) {
          await subscription.unsubscribe();
        }
      }

      const newSettings = { ...notificationSettings, enabled: false };
      setNotificationSettings(newSettings);
      await notificationApi.updateSettings(newSettings);
      toast.success('Notifications disabled');
    } catch (error) {
      toast.error('Failed to disable notifications');
    } finally {
      setSavingNotifications(false);
    }
  };

  const handleSaveNotificationSettings = async () => {
    setSavingNotifications(true);
    try {
      await notificationApi.updateSettings(notificationSettings);
      toast.success('Notification settings saved!');
    } catch (error) {
      toast.error('Failed to save notification settings');
    } finally {
      setSavingNotifications(false);
    }
  };

  const handleSavePrompt = async (promptType) => {
    setSavingPrompts(true);
    try {
      await promptsApi.update({ [promptType]: customPrompts[promptType] });
      toast.success('Custom prompt saved!');
      setEditingPrompt(null);
    } catch (error) {
      toast.error('Failed to save prompt');
    } finally {
      setSavingPrompts(false);
    }
  };

  const handleResetPrompt = async (promptType) => {
    setCustomPrompts(prev => ({ ...prev, [promptType]: '' }));
    try {
      await promptsApi.update({ [promptType]: null });
      toast.success('Prompt reset to default');
    } catch (error) {
      toast.error('Failed to reset prompt');
    }
  };

  const handleResetAllPrompts = async () => {
    try {
      await promptsApi.reset();
      setCustomPrompts({
        recipe_extraction: '',
        meal_planning: '',
        fridge_search: ''
      });
      toast.success('All prompts reset to defaults');
    } catch (error) {
      toast.error('Failed to reset prompts');
    }
  };

  // Profile handlers
  const handleSaveProfile = async () => {
    setSavingProfile(true);
    try {
      await authApi.updateProfile({ name: profileName, email: profileEmail });
      toast.success('Profile updated!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update profile');
    } finally {
      setSavingProfile(false);
    }
  };

  // Allergy handlers
  const handleAddAllergy = () => {
    if (newAllergy.trim() && !allergies.includes(newAllergy.trim().toLowerCase())) {
      setAllergies([...allergies, newAllergy.trim().toLowerCase()]);
      setNewAllergy('');
    }
  };

  const handleRemoveAllergy = (allergy) => {
    setAllergies(allergies.filter(a => a !== allergy));
  };

  const handleSaveAllergies = async () => {
    setSavingAllergies(true);
    try {
      await authApi.updateProfile({ allergies });
      toast.success('Allergies saved!');
    } catch (error) {
      toast.error('Failed to save allergies');
    } finally {
      setSavingAllergies(false);
    }
  };

  // Household handlers
  const handleGenerateJoinCode = async () => {
    setGeneratingCode(true);
    try {
      const res = await householdApi.generateJoinCode();
      setJoinCode(res.data.join_code);
      setJoinCodeExpires(res.data.expires);
      toast.success('Join code generated!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate join code');
    } finally {
      setGeneratingCode(false);
    }
  };

  const handleRevokeJoinCode = async () => {
    try {
      await householdApi.revokeJoinCode();
      setJoinCode(null);
      setJoinCodeExpires(null);
      toast.success('Join code revoked');
    } catch (error) {
      toast.error('Failed to revoke join code');
    }
  };

  const handleJoinHousehold = async () => {
    if (!joinCodeInput.trim()) return;
    setJoiningHousehold(true);
    try {
      await householdApi.joinWithCode(joinCodeInput.trim());
      toast.success('Joined household!');
      window.location.reload();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to join household');
    } finally {
      setJoiningHousehold(false);
    }
  };

  const copyJoinCode = () => {
    navigator.clipboard.writeText(joinCode);
    toast.success('Join code copied!');
  };

  // Import handlers
  const handleImportFile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setImporting(true);
    try {
      const content = await file.text();
      let platform = 'json';

      if (file.name.endsWith('.paprikarecipes') || file.name.includes('paprika')) {
        platform = 'paprika';
      } else if (file.name.includes('mealie') || file.name.includes('tandoor')) {
        platform = 'cookmate';
      }

      const res = await importApi.fromPlatform(platform, content);
      toast.success(res.data.mesmise || `Imported ${res.data.imported} recipes!`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to import recipes');
    } finally {
      setImporting(false);
      e.target.value = '';
    }
  };

  // Delete account handler
  const handleDeleteAccount = async () => {
    if (deleteConfirmText !== 'DELETE') return;
    setDeleting(true);
    try {
      await authApi.deleteAccount();
      toast.success('Account deleted');
      await logout();
      navigate('/');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete account');
    } finally {
      setDeleting(false);
    }
  };

  // API Token handlers
  const loadApiTokens = async () => {
    setLoadingTokens(true);
    try {
      const res = await apiTokensApi.list();
      setApiTokens(res.data || []);
    } catch (error) {
      console.error('Failed to load API tokens:', error);
    } finally {
      setLoadingTokens(false);
    }
  };

  const handleCreateToken = async () => {
    if (!newTokenName.trim()) {
      toast.error('Please enter a token name');
      return;
    }
    setCreatingToken(true);
    try {
      const expiryDays = newTokenExpiry === 'never' ? null : parseInt(newTokenExpiry);
      const res = await apiTokensApi.create({
        name: newTokenName.trim(),
        expires_in_days: expiryDays
      });
      setNewlyCreatedToken(res.data.token);
      setNewTokenName('');
      setNewTokenExpiry('never');
      await loadApiTokens();
      toast.success('API token created!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create token');
    } finally {
      setCreatingToken(false);
    }
  };

  const handleRevokeToken = async (tokenId) => {
    try {
      await apiTokensApi.revoke(tokenId);
      await loadApiTokens();
      toast.success('Token revoked');
    } catch (error) {
      toast.error('Failed to revoke token');
    }
  };

  const handleDeleteToken = async (tokenId) => {
    try {
      await apiTokensApi.delete(tokenId);
      await loadApiTokens();
      toast.success('Token deleted');
    } catch (error) {
      toast.error('Failed to delete token');
    }
  };

  const copyToken = (token) => {
    navigator.clipboard.writeText(token);
    toast.success('Token copied to clipboard!');
  };

  // Load API tokens when user tab becomes active
  useEffect(() => {
    if (activeTab === 'user' && apiTokens.length === 0) {
      loadApiTokens();
    }
  }, [activeTab]);

  const promptLabels = {
    recipe_extraction: { name: 'Recipe Extraction', description: 'Used when importing recipes from URLs or text' },
    meal_planning: { name: 'Meal Planning', description: 'Used when generating meal plans' },
    fridge_search: { name: 'Fridge Search', description: 'Used when finding recipes by ingredients' }
  };

  const currentServer = localStorage.getItem('mise_server_url') || process.env.REACT_APP_BACKEND_URL;
  const isLocalServer = currentServer?.includes('localhost') || currentServer?.includes('192.168');

  const ollamaModels = availableModels.length > 0 ? availableModels : [
    'llama3', 'llama3:70b', 'mistral', 'phi3', 'gemma', 'codellama'
  ];

  return (
    <Layout>
      <div className="max-w-2xl mx-auto space-y-8" data-testid="settings-page">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <h1 className="font-heading text-3xl font-bold">Settings</h1>
          <p className="text-muted-foreground mt-1">Manage your app preferences</p>
        </motion.div>

        {/* Tab Bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="bg-white dark:bg-card rounded-xl border border-border/60 p-1 flex gap-1"
        >
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-mise text-white shadow-sm'
                    : 'text-muted-foreground hover:text-foreground hover:bg-cream-subtle'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span className="hidden sm:inline">{tab.label}</span>
              </button>
            );
          })}
        </motion.div>

        {/* User Tab Content */}
        {activeTab === 'user' && (
          <>
        {/* Profile Section */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <User className="w-5 h-5 text-mise" />
              Account
            </h2>
          </div>

          <div className="p-4 space-y-4">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 rounded-full bg-mise/20 flex items-center justify-center text-mise text-xl font-semibold">
                {user?.name?.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2) || 'U'}
              </div>
              <div className="flex-1 space-y-3">
                <div>
                  <Label htmlFor="profile-name" className="text-xs text-muted-foreground">Name</Label>
                  <Input
                    id="profile-name"
                    value={profileName}
                    onChange={(e) => setProfileName(e.target.value)}
                    className="rounded-lg mt-1"
                  />
                </div>
                <div>
                  <Label htmlFor="profile-email" className="text-xs text-muted-foreground">Email</Label>
                  <Input
                    id="profile-email"
                    type="email"
                    value={profileEmail}
                    onChange={(e) => setProfileEmail(e.target.value)}
                    className="rounded-lg mt-1"
                  />
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                className="rounded-full text-destructive border-destructive/30 hover:bg-destructive hover:text-white"
                onClick={handleLogout}
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4 mr-2" />
                Sign Out
              </Button>
              <Button
                onClick={handleSaveProfile}
                disabled={savingProfile}
                className="rounded-full bg-mise hover:bg-mise-dark"
              >
                {savingProfile ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Check className="w-4 h-4 mr-2" />}
                Save Changes
              </Button>
            </div>
          </div>
        </motion.section>

        {/* Allergies Section */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.12 }}
          className="bg-white rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Shield className="w-5 h-5 text-mise" />
              Allergies
            </h2>
          </div>

          <div className="p-4 space-y-4">
            <p className="text-sm text-muted-foreground">
              Add your food allergies to receive warnings when planning recipes that contain allergens.
            </p>

            <div className="flex gap-2">
              <Input
                placeholder="Type allergies (e.g., gluten, nuts, dairy)..."
                value={newAllergy}
                onChange={(e) => setNewAllergy(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleAddAllergy()}
                className="rounded-lg flex-1"
              />
              <Button onClick={handleAddAllergy} variant="outline" className="rounded-lg">
                Add
              </Button>
            </div>

            {allergies.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {allergies.map((allergy) => (
                  <span
                    key={allergy}
                    className="inline-flex items-center gap-1 px-3 py-1 bg-amber-50 text-amber-800 rounded-full text-sm border border-amber-200"
                  >
                    {allergy}
                    <button onClick={() => handleRemoveAllergy(allergy)} className="hover:text-amber-600">
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}

            <Button
              onClick={handleSaveAllergies}
              disabled={savingAllergies}
              className="rounded-full bg-mise hover:bg-mise-dark"
            >
              {savingAllergies ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Check className="w-4 h-4 mr-2" />}
              Save Allergies
            </Button>
          </div>
        </motion.section>

        {/* Appearance Section */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.14 }}
          className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Palette className="w-5 h-5 text-mise" />
              Appearance
            </h2>
          </div>

          <div className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {darkMode ? (
                  <Moon className="w-5 h-5 text-mise" />
                ) : (
                  <Sun className="w-5 h-5 text-amber-500" />
                )}
                <div>
                  <p className="font-medium">Dark Mode</p>
                  <p className="text-sm text-muted-foreground">
                    {darkMode ? 'Currently using dark theme' : 'Currently using light theme'}
                  </p>
                </div>
              </div>
              <Switch
                checked={darkMode}
                onCheckedChange={toggleDarkMode}
              />
            </div>
          </div>
        </motion.section>

        {/* Import Recipe Archive Section */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.16 }}
          className="bg-white rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Upload className="w-5 h-5 text-mise" />
              Import Recipe Archive
            </h2>
          </div>

          <div className="p-4 space-y-4">
            <p className="text-sm text-muted-foreground">
              Import recipes from Mela (.melarecipes), Mealie, Tandoor, or Paprika (.zip) exports.
            </p>

            <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-border/60 rounded-xl cursor-pointer hover:bg-cream-subtle transition-colors">
              <div className="flex flex-col items-center justify-center pt-5 pb-6">
                {importing ? (
                  <Loader2 className="w-8 h-8 text-mise animate-spin mb-2" />
                ) : (
                  <Upload className="w-8 h-8 text-muted-foreground mb-2" />
                )}
                <p className="text-sm text-muted-foreground">
                  <span className="font-medium text-mise">Upload a file</span> or drag and drop
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  .melarecipes (.html), .zip (Mealie, Tandoor, or Paprika export)
                </p>
              </div>
              <input
                type="file"
                className="hidden"
                accept=".json,.zip,.melarecipes,.html"
                onChange={handleImportFile}
                disabled={importing}
              />
            </label>
          </div>
        </motion.section>

        {/* API Tokens Section */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.17 }}
          className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Key className="w-5 h-5 text-mise" />
              API Tokens
            </h2>
          </div>

          <div className="p-4 space-y-4">
            <p className="text-sm text-muted-foreground">
              Create API tokens for integrations like Home Assistant. Tokens provide access to your account without sharing your password.
            </p>

            {/* Newly created token display */}
            {newlyCreatedToken && (
              <div className="p-4 bg-mise-light rounded-xl border border-mise/30">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-mise flex-shrink-0 mt-0.5" />
                  <div className="flex-1 space-y-2">
                    <p className="font-medium text-mise">Save your token now!</p>
                    <p className="text-sm text-mise/80">This token will only be shown once. Copy it and store it securely.</p>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 p-2 bg-white rounded-lg text-sm font-mono break-all border">
                        {newlyCreatedToken}
                      </code>
                      <Button variant="outline" size="icon" onClick={() => copyToken(newlyCreatedToken)} className="rounded-lg flex-shrink-0">
                        <Copy className="w-4 h-4" />
                      </Button>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setNewlyCreatedToken(null)}
                      className="text-mise/70 hover:text-mise"
                    >
                      I've saved my token
                    </Button>
                  </div>
                </div>
              </div>
            )}

            {/* Create new token */}
            {!showCreateToken ? (
              <Button
                variant="outline"
                onClick={() => setShowCreateToken(true)}
                className="rounded-full"
              >
                <Key className="w-4 h-4 mr-2" />
                Create New Token
              </Button>
            ) : (
              <div className="p-4 bg-cream-subtle rounded-xl space-y-3">
                <div>
                  <Label htmlFor="token-name" className="mb-2 block text-sm">Token Name</Label>
                  <Input
                    id="token-name"
                    placeholder="e.g., Home Assistant"
                    value={newTokenName}
                    onChange={(e) => setNewTokenName(e.target.value)}
                    className="rounded-lg"
                  />
                </div>
                <div>
                  <Label htmlFor="token-expiry" className="mb-2 block text-sm">Expiration</Label>
                  <Select value={newTokenExpiry} onValueChange={setNewTokenExpiry}>
                    <SelectTrigger className="rounded-lg w-48">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="never">Never expires</SelectItem>
                      <SelectItem value="30">30 days</SelectItem>
                      <SelectItem value="90">90 days</SelectItem>
                      <SelectItem value="365">1 year</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex gap-2 pt-2">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setShowCreateToken(false);
                      setNewTokenName('');
                      setNewTokenExpiry('never');
                    }}
                    className="rounded-full"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCreateToken}
                    disabled={creatingToken || !newTokenName.trim()}
                    className="rounded-full bg-mise hover:bg-mise-dark"
                  >
                    {creatingToken ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Key className="w-4 h-4 mr-2" />}
                    Create Token
                  </Button>
                </div>
              </div>
            )}

            {/* Existing tokens list */}
            {loadingTokens ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-6 h-6 animate-spin text-mise" />
              </div>
            ) : apiTokens.length > 0 ? (
              <div className="space-y-2">
                <Label className="text-sm text-muted-foreground">Your Tokens</Label>
                <div className="divide-y divide-border/60 border border-border/60 rounded-xl overflow-hidden">
                  {apiTokens.map((token) => (
                    <div key={token.id} className="p-3 flex items-center justify-between bg-white dark:bg-card">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-medium text-sm truncate">{token.name}</p>
                          {token.revoked && (
                            <span className="px-2 py-0.5 text-xs bg-red-100 text-red-600 rounded">Revoked</span>
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          Created {new Date(token.created_at).toLocaleDateString()}
                          {token.expires_at && ` · Expires ${new Date(token.expires_at).toLocaleDateString()}`}
                          {token.last_used_at && ` · Last used ${new Date(token.last_used_at).toLocaleDateString()}`}
                        </p>
                      </div>
                      <div className="flex items-center gap-1 ml-2">
                        {!token.revoked && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRevokeToken(token.id)}
                            className="text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                          >
                            Revoke
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDeleteToken(token.id)}
                          className="text-red-500 hover:text-red-600 hover:bg-red-50"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-4">
                No API tokens yet. Create one to integrate with external services.
              </p>
            )}

            <div className="p-3 bg-amber-50 rounded-xl border border-amber-200">
              <p className="text-xs text-amber-800">
                <strong>Security tip:</strong> Only create tokens for services you trust. Tokens have full access to your account.
                Revoke any tokens you no longer need.
              </p>
            </div>
          </div>
        </motion.section>

        {/* Danger Zone Section */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.18 }}
          className="bg-white rounded-2xl border border-red-200 overflow-hidden"
        >
          <div className="p-4 border-b border-red-200 bg-red-50">
            <h2 className="font-heading font-semibold flex items-center gap-2 text-red-700">
              <AlertTriangle className="w-5 h-5" />
              Danger Zone
            </h2>
          </div>

          <div className="p-4 space-y-4">
            <p className="text-sm text-muted-foreground">
              Once you delete your account, there is no going back. Please be certain.
            </p>

            {!showDeleteConfirm ? (
              <Button
                variant="outline"
                className="rounded-full text-red-600 border-red-300 hover:bg-red-50"
                onClick={() => setShowDeleteConfirm(true)}
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Delete My Account
              </Button>
            ) : (
              <div className="p-4 bg-red-50 rounded-xl space-y-3">
                <p className="text-sm font-medium text-red-700">
                  Type DELETE to confirm account deletion:
                </p>
                <Input
                  value={deleteConfirmText}
                  onChange={(e) => setDeleteConfirmText(e.target.value)}
                  placeholder="DELETE"
                  className="rounded-lg border-red-300"
                />
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    className="rounded-full"
                    onClick={() => {
                      setShowDeleteConfirm(false);
                      setDeleteConfirmText('');
                    }}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleDeleteAccount}
                    disabled={deleteConfirmText !== 'DELETE' || deleting}
                    className="rounded-full bg-red-600 hover:bg-red-700 text-white"
                  >
                    {deleting ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Trash2 className="w-4 h-4 mr-2" />}
                    Delete Account
                  </Button>
                </div>
              </div>
            )}
          </div>
        </motion.section>
          </>
        )}

        {/* AI Tab Content */}
        {activeTab === 'ai' && (
          <>
        {/* AI Settings Section */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="bg-white rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-mise" />
              AI Settings
            </h2>
          </div>
          
          <div className="p-4 space-y-6">
            {/* Provider Selection */}
            <div>
              <Label className="mb-3 block">AI Provider</Label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <button
                  onClick={() => setLlmSettings({ ...llmSettings, provider: 'openai' })}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    llmSettings.provider === 'openai'
                      ? 'border-mise bg-mise-light'
                      : 'border-border/60 hover:border-mise'
                  }`}
                >
                  <div className="flex flex-col items-center text-center gap-2">
                    <Cloud className={`w-6 h-6 ${llmSettings.provider === 'openai' ? 'text-mise' : 'text-muted-foreground'}`} />
                    <div>
                      <p className="font-medium text-sm">OpenAI</p>
                      <p className="text-xs text-muted-foreground">GPT-4o</p>
                    </div>
                  </div>
                </button>
                
                <button
                  onClick={() => setLlmSettings({ ...llmSettings, provider: 'anthropic' })}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    llmSettings.provider === 'anthropic'
                      ? 'border-mise bg-mise-light'
                      : 'border-border/60 hover:border-mise'
                  }`}
                >
                  <div className="flex flex-col items-center text-center gap-2">
                    <Sparkles className={`w-6 h-6 ${llmSettings.provider === 'anthropic' ? 'text-mise' : 'text-muted-foreground'}`} />
                    <div>
                      <p className="font-medium text-sm">Claude</p>
                      <p className="text-xs text-muted-foreground">Anthropic</p>
                    </div>
                  </div>
                </button>
                
                <button
                  onClick={() => setLlmSettings({ ...llmSettings, provider: 'ollama' })}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    llmSettings.provider === 'ollama'
                      ? 'border-mise bg-mise-light'
                      : 'border-border/60 hover:border-mise'
                  }`}
                >
                  <div className="flex flex-col items-center text-center gap-2">
                    <HardDrive className={`w-6 h-6 ${llmSettings.provider === 'ollama' ? 'text-mise' : 'text-muted-foreground'}`} />
                    <div>
                      <p className="font-medium text-sm">Ollama</p>
                      <p className="text-xs text-muted-foreground">Local Server</p>
                    </div>
                  </div>
                </button>
                
                <button
                  onClick={() => setLlmSettings({ ...llmSettings, provider: 'embedded' })}
                  className={`p-4 rounded-xl border-2 text-left transition-all ${
                    llmSettings.provider === 'embedded'
                      ? 'border-mise bg-mise-light'
                      : 'border-border/60 hover:border-mise'
                  }`}
                >
                  <div className="flex flex-col items-center text-center gap-2">
                    <WifiOff className={`w-6 h-6 ${llmSettings.provider === 'embedded' ? 'text-mise' : 'text-muted-foreground'}`} />
                    <div>
                      <p className="font-medium text-sm">Embedded</p>
                      <p className="text-xs text-muted-foreground">100% Offline</p>
                    </div>
                  </div>
                </button>
              </div>
            </div>

            {/* Anthropic/Claude Configuration */}
            {llmSettings.provider === 'anthropic' && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="space-y-4 p-4 bg-cream-subtle rounded-xl"
              >
                <div>
                  <Label htmlFor="anthropic-key" className="mb-2 block">Anthropic API Key</Label>
                  <Input
                    id="anthropic-key"
                    type="password"
                    placeholder="sk-ant-..."
                    value={llmSettings.anthropic_api_key || ''}
                    onChange={(e) => setLlmSettings({ ...llmSettings, anthropic_api_key: e.target.value })}
                    className="rounded-xl"
                  />
                  <p className="text-xs text-muted-foreground mt-2">
                    Get your API key from{' '}
                    <a 
                      href="https://console.anthropic.com/settings/keys" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="text-mise hover:underline"
                    >
                      console.anthropic.com
                    </a>
                  </p>
                </div>
              </motion.div>
            )}

            {/* Embedded Configuration */}
            {llmSettings.provider === 'embedded' && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="space-y-4 p-4 bg-cream-subtle rounded-xl"
              >
                <div className="flex items-start gap-3 p-3 bg-amber-50 rounded-lg border border-amber-200">
                  <WifiOff className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-amber-800">
                    <p className="font-medium">Fully Offline AI</p>
                    <p className="text-xs mt-1">AI runs entirely on your server. No internet required after model download.</p>
                  </div>
                </div>
                
                <div>
                  <Label htmlFor="embedded-model" className="mb-2 block">Model</Label>
                  <Select 
                    value={llmSettings.embedded_model} 
                    onValueChange={(value) => setLlmSettings({ ...llmSettings, embedded_model: value })}
                  >
                    <SelectTrigger className="rounded-xl">
                      <SelectValue placeholder="Select model" />
                    </SelectTrigger>
                    <SelectContent>
                      {(embeddedModels.length > 0 ? embeddedModels : [
                        { id: 'Phi-3-mini-4k-instruct.Q4_0.gguf', name: 'Phi-3 Mini (Recommended)', size: '2.2GB', ram: '4GB' },
                        { id: 'Llama-3.2-3B-Instruct-Q4_K_M.gguf', name: 'Llama 3.2 3B', size: '2.0GB', ram: '4GB' },
                        { id: 'Mistral-7B-Instruct-v0.3-Q4_K_M.gguf', name: 'Mistral 7B', size: '4.4GB', ram: '8GB' },
                      ]).map((model) => (
                        <SelectItem key={model.id} value={model.id}>
                          <div className="flex justify-between items-center w-full">
                            <span>{model.name}</span>
                            <span className="text-xs text-muted-foreground ml-2">({model.ram} RAM)</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground mt-1">
                    Model will be downloaded automatically on first use (~2-5GB)
                  </p>
                </div>

                {/* Test Connection */}
                <div className="pt-2">
                  <Button 
                    variant="outline" 
                    onClick={handleTestLlm}
                    disabled={testingLlm}
                    className="rounded-full"
                  >
                    {testingLlm ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Download className="w-4 h-4 mr-2" />
                    )}
                    Check Model Status
                  </Button>
                  
                  {llmTestResult && (
                    <div className={`mt-3 p-3 rounded-lg flex items-center gap-2 ${
                      llmTestResult.success ? 'bg-mise-light text-mise' : 'bg-red-50 text-red-600'
                    }`}>
                      {llmTestResult.success ? (
                        <Check className="w-4 h-4" />
                      ) : (
                        <AlertCircle className="w-4 h-4" />
                      )}
                      <span className="text-sm">{llmTestResult.mesmise}</span>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {/* Ollama Configuration */}
            {llmSettings.provider === 'ollama' && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="space-y-4 p-4 bg-cream-subtle rounded-xl"
              >
                <div>
                  <Label htmlFor="ollama-url" className="mb-2 block">Ollama Server URL</Label>
                  <Input
                    id="ollama-url"
                    value={llmSettings.ollama_url}
                    onChange={(e) => setLlmSettings({ ...llmSettings, ollama_url: e.target.value })}
                    placeholder="http://localhost:11434"
                    className="rounded-xl"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Default: http://localhost:11434
                  </p>
                </div>

                <div>
                  <Label htmlFor="ollama-model" className="mb-2 block">Model</Label>
                  <Select 
                    value={llmSettings.ollama_model} 
                    onValueChange={(value) => setLlmSettings({ ...llmSettings, ollama_model: value })}
                  >
                    <SelectTrigger className="rounded-xl">
                      <SelectValue placeholder="Select model" />
                    </SelectTrigger>
                    <SelectContent>
                      {ollamaModels.map((model) => (
                        <SelectItem key={model} value={model}>{model}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground mt-1">
                    Run `ollama pull {llmSettings.ollama_model}` to download
                  </p>
                </div>

                {/* Test Connection */}
                <div className="pt-2">
                  <Button 
                    variant="outline" 
                    onClick={handleTestLlm}
                    disabled={testingLlm}
                    className="rounded-full"
                  >
                    {testingLlm ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Wifi className="w-4 h-4 mr-2" />
                    )}
                    Test Connection
                  </Button>
                  
                  {llmTestResult && (
                    <div className={`mt-3 p-3 rounded-lg flex items-center gap-2 ${
                      llmTestResult.success ? 'bg-mise-light text-mise' : 'bg-red-50 text-red-600'
                    }`}>
                      {llmTestResult.success ? (
                        <Check className="w-4 h-4" />
                      ) : (
                        <AlertCircle className="w-4 h-4" />
                      )}
                      <span className="text-sm">{llmTestResult.mesmise}</span>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {/* OpenAI Info */}
            {llmSettings.provider === 'openai' && (
              <div className="p-4 bg-cream-subtle rounded-xl">
                <p className="text-sm text-muted-foreground">
                  Using OpenAI GPT-4o for AI features. API calls are made through the server.
                </p>
              </div>
            )}

            {/* Save Button */}
            <Button
              onClick={handleSaveLlm}
              disabled={savingLlm}
              className="rounded-full bg-mise hover:bg-mise-dark"
            >
              {savingLlm ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Check className="w-4 h-4 mr-2" />
              )}
              Save AI Settings
            </Button>
          </div>
        </motion.section>

        {/* Custom AI Prompts Section */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.16 }}
          className="bg-white rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle">
            <div className="flex items-center justify-between">
              <h2 className="font-heading font-semibold flex items-center gap-2">
                <FileText className="w-5 h-5 text-mise" />
                Custom AI Prompts
              </h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleResetAllPrompts}
                className="text-xs text-muted-foreground hover:text-destructive"
              >
                <RotateCcw className="w-3 h-3 mr-1" />
                Reset All
              </Button>
            </div>
          </div>

          <div className="p-4 space-y-4">
            <p className="text-sm text-muted-foreground">
              Customize the AI prompts to adjust how recipes are extracted, meal plans are generated, and ingredient searches work.
            </p>

            {Object.entries(promptLabels).map(([key, label]) => (
              <div key={key} className="border border-border/60 rounded-xl overflow-hidden">
                <div
                  className="p-3 bg-cream-subtle flex items-center justify-between cursor-pointer"
                  onClick={() => setEditingPrompt(editingPrompt === key ? null : key)}
                >
                  <div>
                    <p className="font-medium text-sm">{label.name}</p>
                    <p className="text-xs text-muted-foreground">{label.description}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {customPrompts[key] && (
                      <span className="text-xs bg-mise/20 text-mise px-2 py-0.5 rounded-full">
                        Customized
                      </span>
                    )}
                    <Edit3 className={`w-4 h-4 text-muted-foreground transition-transform ${editingPrompt === key ? 'rotate-45' : ''}`} />
                  </div>
                </div>

                {editingPrompt === key && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    className="p-4 space-y-3"
                  >
                    <textarea
                      value={customPrompts[key] || defaultPrompts[key] || ''}
                      onChange={(e) => setCustomPrompts(prev => ({ ...prev, [key]: e.target.value }))}
                      placeholder={defaultPrompts[key] || 'Enter custom prompt...'}
                      className="w-full h-48 p-3 text-sm border border-border/60 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-mise/50 font-mono"
                    />
                    <div className="flex items-center justify-between">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleResetPrompt(key)}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <RotateCcw className="w-4 h-4 mr-1" />
                        Reset to Default
                      </Button>
                      <Button
                        size="sm"
                        onClick={() => handleSavePrompt(key)}
                        disabled={savingPrompts}
                        className="rounded-full bg-mise hover:bg-mise-dark"
                      >
                        {savingPrompts ? (
                          <Loader2 className="w-4 h-4 animate-spin mr-1" />
                        ) : (
                          <Check className="w-4 h-4 mr-1" />
                        )}
                        Save
                      </Button>
                    </div>
                  </motion.div>
                )}
              </div>
            ))}

            <div className="p-3 bg-amber-50 rounded-xl border border-amber-200">
              <p className="text-xs text-amber-800">
                <strong>Note:</strong> Custom prompts must maintain the JSON output format expected by the app.
                If AI responses fail after customizing, reset to defaults.
              </p>
            </div>
          </div>
        </motion.section>
          </>
        )}

        {/* Admin Tab Content */}
        {activeTab === 'admin' && (
          <>
        {/* Notifications Section */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.18 }}
          className="bg-white rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Bell className="w-5 h-5 text-mise" />
              Notifications
            </h2>
          </div>
          
          <div className="p-4 space-y-6">
            {/* Enable/Disable Notifications */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {notificationSettings.enabled ? (
                  <Bell className="w-5 h-5 text-mise" />
                ) : (
                  <BellOff className="w-5 h-5 text-muted-foreground" />
                )}
                <div>
                  <p className="font-medium">Push Notifications</p>
                  <p className="text-sm text-muted-foreground">
                    {notificationPermission === 'denied' 
                      ? 'Blocked in browser settings'
                      : notificationSettings.enabled 
                        ? 'Enabled' 
                        : 'Disabled'}
                  </p>
                </div>
              </div>
              
              {notificationPermission === 'denied' ? (
                <Button variant="outline" disabled className="rounded-full">
                  <AlertCircle className="w-4 h-4 mr-2" />
                  Blocked
                </Button>
              ) : notificationSettings.enabled ? (
                <Button 
                  variant="outline" 
                  onClick={handleDisableNotifications}
                  disabled={savingNotifications}
                  className="rounded-full"
                >
                  {savingNotifications ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <BellOff className="w-4 h-4 mr-2" />
                  )}
                  Disable
                </Button>
              ) : (
                <Button 
                  onClick={handleEnableNotifications}
                  disabled={subscribing}
                  className="rounded-full bg-mise hover:bg-mise-dark"
                >
                  {subscribing ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Bell className="w-4 h-4 mr-2" />
                  )}
                  Enable
                </Button>
              )}
            </div>

            {/* Notification Options - only show if enabled */}
            {notificationSettings.enabled && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="space-y-4 pt-4 border-t border-border/60"
              >
                {/* Meal Reminders */}
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-sm">Meal Reminders</p>
                    <p className="text-xs text-muted-foreground">
                      Get reminded before planned meals
                    </p>
                  </div>
                  <Switch
                    checked={notificationSettings.meal_reminders}
                    onCheckedChange={(checked) => 
                      setNotificationSettings({ ...notificationSettings, meal_reminders: checked })
                    }
                  />
                </div>

                {/* Reminder Time */}
                {notificationSettings.meal_reminders && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="ml-4 p-3 bg-cream-subtle rounded-xl"
                  >
                    <Label htmlFor="reminder-time" className="mb-2 block text-sm">
                      Remind me before meals
                    </Label>
                    <Select 
                      value={String(notificationSettings.reminder_time)} 
                      onValueChange={(value) => 
                        setNotificationSettings({ ...notificationSettings, reminder_time: parseInt(value) })
                      }
                    >
                      <SelectTrigger className="rounded-xl w-48">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="15">15 minutes</SelectItem>
                        <SelectItem value="30">30 minutes</SelectItem>
                        <SelectItem value="60">1 hour</SelectItem>
                        <SelectItem value="120">2 hours</SelectItem>
                      </SelectContent>
                    </Select>
                  </motion.div>
                )}

                {/* Shopping Reminders */}
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-sm">Shopping List Reminders</p>
                    <p className="text-xs text-muted-foreground">
                      Remind when items are added to shopping list
                    </p>
                  </div>
                  <Switch
                    checked={notificationSettings.shopping_reminders}
                    onCheckedChange={(checked) => 
                      setNotificationSettings({ ...notificationSettings, shopping_reminders: checked })
                    }
                  />
                </div>

                {/* Weekly Plan Reminder */}
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-sm">Weekly Planning Reminder</p>
                    <p className="text-xs text-muted-foreground">
                      Remind to plan meals for the week
                    </p>
                  </div>
                  <Switch
                    checked={notificationSettings.weekly_plan_reminder}
                    onCheckedChange={(checked) => 
                      setNotificationSettings({ ...notificationSettings, weekly_plan_reminder: checked })
                    }
                  />
                </div>

                {/* Save Button */}
                <Button 
                  onClick={handleSaveNotificationSettings}
                  disabled={savingNotifications}
                  className="rounded-full bg-mise hover:bg-mise-dark mt-4"
                >
                  {savingNotifications ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Check className="w-4 h-4 mr-2" />
                  )}
                  Save Notification Settings
                </Button>
              </motion.div>
            )}

            {/* Help text when disabled */}
            {!notificationSettings.enabled && notificationPermission !== 'denied' && (
              <p className="text-sm text-muted-foreground">
                Enable notifications to get meal reminders, shopping alerts, and weekly planning prompts.
              </p>
            )}

            {/* Help text when blocked */}
            {notificationPermission === 'denied' && (
              <div className="p-3 bg-amber-50 rounded-xl border border-amber-200">
                <p className="text-sm text-amber-800">
                  Notifications are blocked in your browser. To enable them, click the lock icon 
                  in your browser's address bar and allow notifications for this site.
                </p>
              </div>
            )}
          </div>
        </motion.section>

        {/* Server Section */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Server className="w-5 h-5 text-mise" />
              Server Connection
            </h2>
          </div>
          
          <div className="divide-y divide-border/60">
            {/* Current Server */}
            <div className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {isLocalServer ? (
                    <Wifi className="w-5 h-5 text-mise" />
                  ) : (
                    <Globe className="w-5 h-5 text-mise" />
                  )}
                  <div>
                    <p className="font-medium text-sm">
                      {isLocalServer ? 'Local Server' : 'Cloud Server'}
                    </p>
                    <p className="text-xs text-muted-foreground truncate max-w-[200px]">
                      {currentServer}
                    </p>
                  </div>
                </div>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={handleChangeServer}
                  className="rounded-full"
                  data-testid="change-server-btn"
                >
                  Change
                  <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </div>
            </div>
          </div>
        </motion.section>
          </>
        )}

        {/* Household Tab Content */}
        {activeTab === 'household' && (
          <>
        {household ? (
          <>
            {/* Household Info */}
            <motion.section
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="bg-white rounded-2xl border border-border/60 overflow-hidden"
            >
              <div className="p-4 border-b border-border/60 bg-cream-subtle">
                <h2 className="font-heading font-semibold flex items-center gap-2">
                  <Users className="w-5 h-5 text-mise" />
                  {household.name}
                </h2>
              </div>

              <div className="p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-muted-foreground">Your Role</p>
                    <p className="font-medium">
                      {household.owner_id === user?.id ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-mise/20 text-mise rounded text-xs">Admin</span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">Member</span>
                      )}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-muted-foreground">Members</p>
                    <p className="font-medium">{householdMembers.length}</p>
                  </div>
                </div>
                {household.owner_id !== user?.id && (
                  <Button
                    variant="outline"
                    className="rounded-full text-red-600 border-red-300 hover:bg-red-50"
                    onClick={async () => {
                      try {
                        await householdApi.leave();
                        toast.success('Left household');
                        window.location.reload();
                      } catch (error) {
                        toast.error(error.response?.data?.detail || 'Failed to leave household');
                      }
                    }}
                  >
                    <LogOut className="w-4 h-4 mr-2" />
                    Leave Household
                  </Button>
                )}
              </div>
            </motion.section>

            {/* Members Section */}
            <motion.section
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.12 }}
              className="bg-white rounded-2xl border border-border/60 overflow-hidden"
            >
              <div className="p-4 border-b border-border/60 bg-cream-subtle">
                <h2 className="font-heading font-semibold flex items-center gap-2">
                  <UserPlus className="w-5 h-5 text-mise" />
                  Members
                </h2>
              </div>

              <div className="divide-y divide-border/60">
                {householdMembers.map((member) => (
                  <div key={member.id} className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-mise/20 flex items-center justify-center text-mise text-sm font-medium">
                        {member.name?.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2) || 'U'}
                      </div>
                      <div>
                        <p className="font-medium text-sm">{member.name}</p>
                        {member.id === user?.id && (
                          <span className="text-xs text-mise">You</span>
                        )}
                      </div>
                    </div>
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      household.owner_id === member.id
                        ? 'bg-mise/20 text-mise'
                        : 'bg-gray-100 text-gray-600'
                    }`}>
                      {household.owner_id === member.id ? 'Admin' : 'Member'}
                    </span>
                  </div>
                ))}
              </div>
            </motion.section>

            {/* Join Code Section (Owner Only) */}
            {household.owner_id === user?.id && (
              <motion.section
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.14 }}
                className="bg-white rounded-2xl border border-border/60 overflow-hidden"
              >
                <div className="p-4 border-b border-border/60 bg-cream-subtle">
                  <h2 className="font-heading font-semibold flex items-center gap-2">
                    <Key className="w-5 h-5 text-mise" />
                    Join Code
                  </h2>
                </div>

                <div className="p-4 space-y-4">
                  {joinCode ? (
                    <>
                      <div className="p-4 bg-cream-subtle rounded-xl">
                        <p className="text-sm text-muted-foreground mb-2">Share this code to invite members:</p>
                        <div className="flex items-center gap-2">
                          <code className="flex-1 p-3 bg-white rounded-lg text-xl font-mono tracking-widest text-center border">
                            {joinCode}
                          </code>
                          <Button variant="outline" size="icon" onClick={copyJoinCode} className="rounded-lg">
                            <Copy className="w-4 h-4" />
                          </Button>
                        </div>
                        <p className="text-xs text-muted-foreground mt-2">
                          Expires: {new Date(joinCodeExpires).toLocaleDateString()}
                        </p>
                      </div>
                      <Button
                        variant="outline"
                        className="rounded-full text-red-600 border-red-300 hover:bg-red-50"
                        onClick={handleRevokeJoinCode}
                      >
                        Revoke Code
                      </Button>
                    </>
                  ) : (
                    <>
                      <p className="text-sm text-muted-foreground">
                        No active join code. Generate one to invite new members.
                      </p>
                      <Button
                        onClick={handleGenerateJoinCode}
                        disabled={generatingCode}
                        className="rounded-full bg-mise hover:bg-mise-dark"
                      >
                        {generatingCode ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Key className="w-4 h-4 mr-2" />}
                        Generate Join Code
                      </Button>
                    </>
                  )}
                </div>
              </motion.section>
            )}
          </>
        ) : (
          <>
            {/* No Household - Create or Join */}
            <motion.section
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="bg-white rounded-2xl border border-border/60 overflow-hidden"
            >
              <div className="p-4 border-b border-border/60 bg-cream-subtle">
                <h2 className="font-heading font-semibold flex items-center gap-2">
                  <Users className="w-5 h-5 text-mise" />
                  Join a Household
                </h2>
              </div>

              <div className="p-4 space-y-4">
                <p className="text-sm text-muted-foreground">
                  Enter a join code to join an existing household and share recipes with family.
                </p>
                <div className="flex gap-2">
                  <Input
                    placeholder="Enter join code..."
                    value={joinCodeInput}
                    onChange={(e) => setJoinCodeInput(e.target.value.toUpperCase())}
                    className="rounded-lg font-mono tracking-widest"
                    maxLength={8}
                  />
                  <Button
                    onClick={handleJoinHousehold}
                    disabled={joiningHousehold || !joinCodeInput.trim()}
                    className="rounded-full bg-mise hover:bg-mise-dark"
                  >
                    {joiningHousehold ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Join'}
                  </Button>
                </div>
              </div>
            </motion.section>

            <motion.section
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.12 }}
              className="bg-white rounded-2xl border border-border/60 overflow-hidden"
            >
              <div className="p-4 border-b border-border/60 bg-cream-subtle">
                <h2 className="font-heading font-semibold flex items-center gap-2">
                  <UserPlus className="w-5 h-5 text-mise" />
                  Create a Household
                </h2>
              </div>

              <div className="p-4 space-y-4">
                <p className="text-sm text-muted-foreground">
                  Create a new household to share recipes, meal plans, and shopping lists with your family.
                </p>
                <Button
                  onClick={() => navigate('/household')}
                  className="rounded-full bg-mise hover:bg-mise-dark"
                >
                  <Users className="w-4 h-4 mr-2" />
                  Create Household
                </Button>
              </div>
            </motion.section>
          </>
        )}
          </>
        )}

        {/* Admin Tab - Feedback & Support */}
        {activeTab === 'admin' && (
          <>
        {/* Feedback & Support Section */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="bg-white rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-mise" />
              Feedback & Support
            </h2>
          </div>

          <div className="divide-y divide-border/60">
            <a
              href="https://github.com/Domocn/Recipe-App/issues/new?template=bug_report.md&labels=bug"
              target="_blank"
              rel="noopener noreferrer"
              className="p-4 flex items-center justify-between hover:bg-cream-subtle transition-colors block"
            >
              <div className="flex items-center gap-3">
                <Bug className="w-5 h-5 text-coral" />
                <div>
                  <p className="font-medium text-sm">Report a Bug</p>
                  <p className="text-xs text-muted-foreground">Found something broken? Let us know on GitHub</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            </a>
            
            <a 
              href="https://github.com/Domocn/Recipe-App/issues/new?template=feature_request.md&labels=enhancement"
              target="_blank"
              rel="noopener noreferrer"
              className="p-4 flex items-center justify-between hover:bg-cream-subtle transition-colors block"
            >
              <div className="flex items-center gap-3">
                <Sparkles className="w-5 h-5 text-amber-500" />
                <div>
                  <p className="font-medium text-sm">Request a Feature</p>
                  <p className="text-xs text-muted-foreground">Have an idea? We'd love to hear it</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            </a>
            
            <a 
              href="https://github.com/Domocn/Recipe-App/discussions"
              target="_blank"
              rel="noopener noreferrer"
              className="p-4 flex items-center justify-between hover:bg-cream-subtle transition-colors block"
            >
              <div className="flex items-center gap-3">
                <MessageSquare className="w-5 h-5 text-mise" />
                <div>
                  <p className="font-medium text-sm">Community Discussions</p>
                  <p className="text-xs text-muted-foreground">Ask questions and share tips</p>
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-muted-foreground" />
            </a>
          </div>
        </motion.section>
          </>
        )}

        {/* App Info */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="text-center text-sm text-muted-foreground"
        >
          <p>Laro v{serverInfo?.version || '1.0.0'} Beta</p>
          <p className="mt-1">Self-hostable recipe app for families</p>
        </motion.section>
      </div>
    </Layout>
  );
};
