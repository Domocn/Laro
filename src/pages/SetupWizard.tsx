import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import {
  ChefHat,
  Shield,
  Mail,
  Users,
  ArrowRight,
  ArrowLeft,
  Check,
  Loader2,
  Key,
  Settings,
  Sparkles,
  Globe,
  ExternalLink,
  Eye,
  EyeOff,
  TestTube,
  AlertCircle,
  CheckCircle
} from 'lucide-react';
import { toast } from 'sonner';
import { adminApi } from '../lib/api';
import api from '../lib/api';

const STEPS = [
  { id: 'welcome', title: 'Welcome', icon: ChefHat },
  { id: 'security', title: 'Security', icon: Shield },
  { id: 'registration', title: 'Registration', icon: Users },
  { id: 'email', title: 'Email', icon: Mail },
  { id: 'oauth', title: 'Social Login', icon: Globe },
  { id: 'complete', title: 'Complete', icon: Check },
];

export const SetupWizard = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [setupComplete, setSetupComplete] = useState(false);
  const [showPasswords, setShowPasswords] = useState({});
  const [testingEmail, setTestingEmail] = useState(false);
  const [emailTestResult, setEmailTestResult] = useState(null);
  
  // Settings state
  const [settings, setSettings] = useState({
    // Security
    password_min_length: 8,
    password_require_uppercase: false,
    password_require_number: false,
    password_require_special: false,
    max_login_attempts: 5,
    lockout_duration_minutes: 15,
    // Registration
    allow_registration: true,
    require_invite_code: false,
    allow_admin_registration: false,
    // Sharing
    include_links_in_share: false,
    // Email
    email_enabled: false,
    smtp_host: '',
    smtp_port: 587,
    smtp_user: '',
    smtp_password: '',
    smtp_from_email: '',
    resend_api_key: '',
    email_provider: 'smtp', // 'smtp' or 'resend'
    // OAuth
    google_client_id: '',
    google_client_secret: '',
    github_client_id: '',
    github_client_secret: '',
    oauth_enabled: false,
  });

  useEffect(() => {
    checkSetupStatus();
  }, []);

  const checkSetupStatus = async () => {
    try {
      const res = await api.get('/setup/status');
      if (res.data.setup_complete) {
        setSetupComplete(true);
        navigate('/admin');
        return;
      }
      
      // Load current settings
      const settingsRes = await adminApi.getSettings();
      setSettings(prev => ({ ...prev, ...settingsRes.data }));
    } catch (error) {
      console.error('Failed to check setup status:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleNext = async () => {
    if (currentStep === STEPS.length - 2) {
      // Save settings before completing
      setSaving(true);
      try {
        await adminApi.updateSettings(settings);
        await api.post('/setup/complete');
        setCurrentStep(currentStep + 1);
      } catch (error) {
        toast.error('Failed to save settings');
      } finally {
        setSaving(false);
      }
    } else if (currentStep === STEPS.length - 1) {
      // Complete - go to dashboard
      navigate('/admin');
    } else {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const updateSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const togglePasswordVisibility = (field) => {
    setShowPasswords(prev => ({ ...prev, [field]: !prev[field] }));
  };

  const testEmailConfig = async () => {
    setTestingEmail(true);
    setEmailTestResult(null);
    try {
      const res = await api.post('/admin/test-email', {
        provider: settings.email_provider,
        smtp_host: settings.smtp_host,
        smtp_port: settings.smtp_port,
        smtp_user: settings.smtp_user,
        smtp_password: settings.smtp_password,
        resend_api_key: settings.resend_api_key,
      });
      setEmailTestResult({ success: true, message: 'Email configuration is valid!' });
      toast.success('Email test passed!');
    } catch (error) {
      setEmailTestResult({ 
        success: false, 
        message: error.response?.data?.detail || 'Failed to connect to email service'
      });
      toast.error('Email test failed');
    } finally {
      setTestingEmail(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-cream dark:bg-background flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-mise" />
      </div>
    );
  }

  if (setupComplete) {
    return null;
  }

  return (
    <div className="min-h-screen bg-cream dark:bg-background flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-2xl"
      >
        {/* Progress */}
        <div className="flex justify-between mb-8 px-4">
          {STEPS.map((step, index) => {
            const Icon = step.icon;
            const isActive = index === currentStep;
            const isComplete = index < currentStep;
            return (
              <div key={step.id} className="flex flex-col items-center">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${
                  isActive ? 'bg-mise text-white' :
                  isComplete ? 'bg-green-500 text-white' :
                  'bg-white dark:bg-card border-2 border-border/60 text-muted-foreground'
                }`}>
                  {isComplete ? <Check className="w-5 h-5" /> : <Icon className="w-5 h-5" />}
                </div>
                <span className={`text-xs mt-1 hidden sm:block ${isActive ? 'text-mise font-medium' : 'text-muted-foreground'}`}>
                  {step.title}
                </span>
              </div>
            );
          })}
        </div>

        {/* Card */}
        <div className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden shadow-lg">
          <AnimatePresence mode="wait">
            {/* Step 0: Welcome */}
            {currentStep === 0 && (
              <motion.div
                key="welcome"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="p-8 text-center"
              >
                <div className="w-20 h-20 bg-mise/10 rounded-2xl flex items-center justify-center mx-auto mb-6">
                  <ChefHat className="w-10 h-10 text-mise" />
                </div>
                <h1 className="font-heading text-2xl font-bold mb-2">Welcome to Laro!</h1>
                <p className="text-muted-foreground mb-6">
                  Let's set up your recipe management system. This wizard will help you configure 
                  essential settings for your instance.
                </p>
                <div className="bg-cream-subtle dark:bg-muted p-4 rounded-xl text-left space-y-3">
                  <p className="text-sm flex items-center gap-3">
                    <Shield className="w-5 h-5 text-mise flex-shrink-0" />
                    <span>Configure security & password policies</span>
                  </p>
                  <p className="text-sm flex items-center gap-3">
                    <Users className="w-5 h-5 text-mise flex-shrink-0" />
                    <span>Set up user registration rules</span>
                  </p>
                  <p className="text-sm flex items-center gap-3">
                    <Mail className="w-5 h-5 text-mise flex-shrink-0" />
                    <span>Configure email notifications</span>
                  </p>
                  <p className="text-sm flex items-center gap-3">
                    <Globe className="w-5 h-5 text-mise flex-shrink-0" />
                    <span>Enable Google & GitHub login</span>
                  </p>
                </div>
              </motion.div>
            )}

            {/* Step 1: Security */}
            {currentStep === 1 && (
              <motion.div
                key="security"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="p-8"
              >
                <h2 className="font-heading text-xl font-bold mb-2 flex items-center gap-2">
                  <Shield className="w-6 h-6 text-mise" />
                  Security Settings
                </h2>
                <p className="text-muted-foreground mb-6 text-sm">
                  Configure password requirements and account protection.
                </p>

                <div className="space-y-4">
                  <div>
                    <Label>Minimum Password Length</Label>
                    <Input
                      type="number"
                      min={6}
                      max={32}
                      value={settings.password_min_length}
                      onChange={(e) => updateSetting('password_min_length', parseInt(e.target.value) || 8)}
                      className="mt-1 rounded-xl w-24"
                    />
                  </div>

                  <div className="flex items-center justify-between py-2">
                    <span className="text-sm">Require uppercase letter</span>
                    <Switch
                      checked={settings.password_require_uppercase}
                      onCheckedChange={(checked) => updateSetting('password_require_uppercase', checked)}
                    />
                  </div>

                  <div className="flex items-center justify-between py-2">
                    <span className="text-sm">Require number</span>
                    <Switch
                      checked={settings.password_require_number}
                      onCheckedChange={(checked) => updateSetting('password_require_number', checked)}
                    />
                  </div>

                  <div className="flex items-center justify-between py-2">
                    <span className="text-sm">Require special character</span>
                    <Switch
                      checked={settings.password_require_special}
                      onCheckedChange={(checked) => updateSetting('password_require_special', checked)}
                    />
                  </div>

                  <hr className="border-border/60" />

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <Label>Max Login Attempts</Label>
                      <Input
                        type="number"
                        min={3}
                        max={20}
                        value={settings.max_login_attempts}
                        onChange={(e) => updateSetting('max_login_attempts', parseInt(e.target.value) || 5)}
                        className="mt-1 rounded-xl"
                      />
                    </div>
                    <div>
                      <Label>Lockout Duration (min)</Label>
                      <Input
                        type="number"
                        min={5}
                        max={1440}
                        value={settings.lockout_duration_minutes}
                        onChange={(e) => updateSetting('lockout_duration_minutes', parseInt(e.target.value) || 15)}
                        className="mt-1 rounded-xl"
                      />
                    </div>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Step 2: Registration */}
            {currentStep === 2 && (
              <motion.div
                key="registration"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="p-8"
              >
                <h2 className="font-heading text-xl font-bold mb-2 flex items-center gap-2">
                  <Users className="w-6 h-6 text-mise" />
                  Registration Settings
                </h2>
                <p className="text-muted-foreground mb-6 text-sm">
                  Control who can create accounts on your instance.
                </p>

                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-cream-subtle dark:bg-muted rounded-xl">
                    <div>
                      <p className="font-medium">Allow Registration</p>
                      <p className="text-xs text-muted-foreground">New users can create accounts</p>
                    </div>
                    <Switch
                      checked={settings.allow_registration}
                      onCheckedChange={(checked) => updateSetting('allow_registration', checked)}
                    />
                  </div>

                  <div className="flex items-center justify-between p-4 bg-cream-subtle dark:bg-muted rounded-xl">
                    <div>
                      <p className="font-medium">Require Invite Code</p>
                      <p className="text-xs text-muted-foreground">Users need a code to register</p>
                    </div>
                    <Switch
                      checked={settings.require_invite_code}
                      onCheckedChange={(checked) => updateSetting('require_invite_code', checked)}
                    />
                  </div>

                  <div className="flex items-center justify-between p-4 bg-cream-subtle dark:bg-muted rounded-xl">
                    <div>
                      <p className="font-medium">Allow Admin Self-Registration</p>
                      <p className="text-xs text-muted-foreground">Users can select admin role on signup</p>
                    </div>
                    <Switch
                      checked={settings.allow_admin_registration}
                      onCheckedChange={(checked) => updateSetting('allow_admin_registration', checked)}
                    />
                  </div>

                  <hr className="border-border/40 my-2" />

                  <div className="flex items-center justify-between p-4 bg-cream-subtle dark:bg-muted rounded-xl">
                    <div>
                      <p className="font-medium">Include Links in Shared Recipes</p>
                      <p className="text-xs text-muted-foreground">Add link to your instance when sharing via WhatsApp</p>
                    </div>
                    <Switch
                      checked={settings.include_links_in_share}
                      onCheckedChange={(checked) => updateSetting('include_links_in_share', checked)}
                    />
                  </div>

                  <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-xl p-4 text-sm">
                    <p className="text-blue-800 dark:text-blue-200">
                      <strong>Self-hosted:</strong> Disable link sharing if you don't want to expose your server URL when users share recipes externally. Full recipe content will still be shared.
                    </p>
                  </div>

                  <div className="bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-xl p-4 text-sm">
                    <p className="text-amber-800 dark:text-amber-200">
                      <strong>Tip:</strong> For maximum security, disable registration and use invite codes.
                      You can create users manually from the admin dashboard.
                    </p>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Step 3: Email */}
            {currentStep === 3 && (
              <motion.div
                key="email"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="p-8"
              >
                <h2 className="font-heading text-xl font-bold mb-2 flex items-center gap-2">
                  <Mail className="w-6 h-6 text-mise" />
                  Email Configuration
                </h2>
                <p className="text-muted-foreground mb-6 text-sm">
                  Email enables password resets and security notifications.
                </p>

                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-cream-subtle dark:bg-muted rounded-xl">
                    <div>
                      <p className="font-medium">Enable Email</p>
                      <p className="text-xs text-muted-foreground">Send password reset & notifications</p>
                    </div>
                    <Switch
                      checked={settings.email_enabled}
                      onCheckedChange={(checked) => updateSetting('email_enabled', checked)}
                    />
                  </div>

                  {settings.email_enabled && (
                    <>
                      {/* Provider Selection */}
                      <div className="flex gap-2 p-1 bg-cream-subtle dark:bg-muted rounded-xl">
                        <button
                          onClick={() => updateSetting('email_provider', 'smtp')}
                          className={`flex-1 py-2 rounded-lg font-medium text-sm transition-all ${
                            settings.email_provider === 'smtp'
                              ? 'bg-white dark:bg-card shadow-sm text-mise'
                              : 'text-muted-foreground hover:text-foreground'
                          }`}
                        >
                          SMTP Server
                        </button>
                        <button
                          onClick={() => updateSetting('email_provider', 'resend')}
                          className={`flex-1 py-2 rounded-lg font-medium text-sm transition-all ${
                            settings.email_provider === 'resend'
                              ? 'bg-white dark:bg-card shadow-sm text-mise'
                              : 'text-muted-foreground hover:text-foreground'
                          }`}
                        >
                          Resend API
                        </button>
                      </div>

                      {settings.email_provider === 'smtp' ? (
                        <div className="space-y-3">
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <Label>SMTP Host</Label>
                              <Input
                                placeholder="smtp.gmail.com"
                                value={settings.smtp_host}
                                onChange={(e) => updateSetting('smtp_host', e.target.value)}
                                className="mt-1 rounded-xl"
                              />
                            </div>
                            <div>
                              <Label>Port</Label>
                              <Input
                                type="number"
                                placeholder="587"
                                value={settings.smtp_port}
                                onChange={(e) => updateSetting('smtp_port', parseInt(e.target.value) || 587)}
                                className="mt-1 rounded-xl"
                              />
                            </div>
                          </div>
                          <div>
                            <Label>Username / Email</Label>
                            <Input
                              placeholder="your@email.com"
                              value={settings.smtp_user}
                              onChange={(e) => updateSetting('smtp_user', e.target.value)}
                              className="mt-1 rounded-xl"
                            />
                          </div>
                          <div>
                            <Label>Password / App Password</Label>
                            <div className="relative mt-1">
                              <Input
                                type={showPasswords.smtp ? 'text' : 'password'}
                                placeholder="••••••••"
                                value={settings.smtp_password}
                                onChange={(e) => updateSetting('smtp_password', e.target.value)}
                                className="rounded-xl pr-10"
                              />
                              <button
                                type="button"
                                onClick={() => togglePasswordVisibility('smtp')}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                              >
                                {showPasswords.smtp ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                              </button>
                            </div>
                          </div>
                          <div>
                            <Label>From Email</Label>
                            <Input
                              placeholder="noreply@yourdomain.com"
                              value={settings.smtp_from_email}
                              onChange={(e) => updateSetting('smtp_from_email', e.target.value)}
                              className="mt-1 rounded-xl"
                            />
                          </div>
                        </div>
                      ) : (
                        <div>
                          <Label>Resend API Key</Label>
                          <div className="relative mt-1">
                            <Input
                              type={showPasswords.resend ? 'text' : 'password'}
                              placeholder="re_xxxxxxxxx"
                              value={settings.resend_api_key}
                              onChange={(e) => updateSetting('resend_api_key', e.target.value)}
                              className="rounded-xl pr-10"
                            />
                            <button
                              type="button"
                              onClick={() => togglePasswordVisibility('resend')}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                            >
                              {showPasswords.resend ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                            </button>
                          </div>
                          <p className="text-xs text-muted-foreground mt-2">
                            Get your API key from{' '}
                            <a href="https://resend.com" target="_blank" rel="noopener noreferrer" className="text-mise hover:underline">
                              resend.com <ExternalLink className="w-3 h-3 inline" />
                            </a>
                          </p>
                        </div>
                      )}

                      {/* Test Button */}
                      <div className="flex items-center gap-3">
                        <Button
                          variant="outline"
                          onClick={testEmailConfig}
                          disabled={testingEmail}
                          className="rounded-full"
                        >
                          {testingEmail ? (
                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                          ) : (
                            <TestTube className="w-4 h-4 mr-2" />
                          )}
                          Test Configuration
                        </Button>
                        {emailTestResult && (
                          <span className={`text-sm flex items-center gap-1 ${emailTestResult.success ? 'text-green-600' : 'text-red-600'}`}>
                            {emailTestResult.success ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                            {emailTestResult.message}
                          </span>
                        )}
                      </div>
                    </>
                  )}

                  {!settings.email_enabled && (
                    <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-xl p-4 text-sm">
                      <p className="text-blue-800 dark:text-blue-200">
                        <strong>No email?</strong> That's okay! Users can still use the app, but password 
                        reset will require admin assistance.
                      </p>
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {/* Step 4: OAuth */}
            {currentStep === 4 && (
              <motion.div
                key="oauth"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="p-8"
              >
                <h2 className="font-heading text-xl font-bold mb-2 flex items-center gap-2">
                  <Globe className="w-6 h-6 text-mise" />
                  Social Login (OAuth)
                </h2>
                <p className="text-muted-foreground mb-6 text-sm">
                  Let users sign in with Google or GitHub. Optional but recommended for convenience.
                </p>

                <div className="space-y-6">
                  {/* Google OAuth */}
                  <div className="border border-border/60 rounded-xl overflow-hidden">
                    <div className="p-3 bg-cream-subtle dark:bg-muted flex items-center gap-2">
                      <svg className="w-5 h-5" viewBox="0 0 24 24">
                        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                      </svg>
                      <span className="font-medium text-sm">Google</span>
                    </div>
                    <div className="p-4 space-y-3">
                      <div>
                        <Label>Client ID</Label>
                        <Input
                          placeholder="xxxxx.apps.googleusercontent.com"
                          value={settings.google_client_id}
                          onChange={(e) => updateSetting('google_client_id', e.target.value)}
                          className="mt-1 rounded-xl font-mono text-sm"
                        />
                      </div>
                      <div>
                        <Label>Client Secret</Label>
                        <div className="relative mt-1">
                          <Input
                            type={showPasswords.google ? 'text' : 'password'}
                            placeholder="GOCSPX-xxxxxxx"
                            value={settings.google_client_secret}
                            onChange={(e) => updateSetting('google_client_secret', e.target.value)}
                            className="rounded-xl pr-10 font-mono text-sm"
                          />
                          <button
                            type="button"
                            onClick={() => togglePasswordVisibility('google')}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          >
                            {showPasswords.google ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Create credentials at{' '}
                        <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener noreferrer" className="text-mise hover:underline">
                          Google Cloud Console <ExternalLink className="w-3 h-3 inline" />
                        </a>
                      </p>
                    </div>
                  </div>

                  {/* GitHub OAuth */}
                  <div className="border border-border/60 rounded-xl overflow-hidden">
                    <div className="p-3 bg-cream-subtle dark:bg-muted flex items-center gap-2">
                      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
                      </svg>
                      <span className="font-medium text-sm">GitHub</span>
                    </div>
                    <div className="p-4 space-y-3">
                      <div>
                        <Label>Client ID</Label>
                        <Input
                          placeholder="Ov23lixxxxxxx"
                          value={settings.github_client_id}
                          onChange={(e) => updateSetting('github_client_id', e.target.value)}
                          className="mt-1 rounded-xl font-mono text-sm"
                        />
                      </div>
                      <div>
                        <Label>Client Secret</Label>
                        <div className="relative mt-1">
                          <Input
                            type={showPasswords.github ? 'text' : 'password'}
                            placeholder="xxxxxxxxxxxxxxxx"
                            value={settings.github_client_secret}
                            onChange={(e) => updateSetting('github_client_secret', e.target.value)}
                            className="rounded-xl pr-10 font-mono text-sm"
                          />
                          <button
                            type="button"
                            onClick={() => togglePasswordVisibility('github')}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          >
                            {showPasswords.github ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        Create an OAuth App at{' '}
                        <a href="https://github.com/settings/developers" target="_blank" rel="noopener noreferrer" className="text-mise hover:underline">
                          GitHub Developer Settings <ExternalLink className="w-3 h-3 inline" />
                        </a>
                      </p>
                    </div>
                  </div>

                  <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-xl p-4 text-sm">
                    <p className="text-blue-800 dark:text-blue-200">
                      <strong>Skip for now?</strong> You can always configure OAuth later from Admin → Settings.
                      Users can still register with email/password.
                    </p>
                  </div>
                </div>
              </motion.div>
            )}

            {/* Step 5: Complete */}
            {currentStep === 5 && (
              <motion.div
                key="complete"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="p-8 text-center"
              >
                <div className="w-20 h-20 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto mb-6">
                  <Sparkles className="w-10 h-10 text-green-600 dark:text-green-400" />
                </div>
                <h1 className="font-heading text-2xl font-bold mb-2">You're All Set!</h1>
                <p className="text-muted-foreground mb-6">
                  Your Laro instance is configured and ready to use. You can always change these 
                  settings later from the admin dashboard.
                </p>

                <div className="bg-cream-subtle dark:bg-muted rounded-xl p-4 text-left space-y-3">
                  <p className="font-medium">What's Next?</p>
                  <ul className="text-sm space-y-2">
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500" />
                      Create your first recipe
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500" />
                      Import recipes from your favorite sites
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500" />
                      Invite family members
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500" />
                      Plan your weekly meals
                    </li>
                  </ul>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Navigation */}
          <div className="p-6 border-t border-border/60 flex justify-between">
            <Button
              variant="outline"
              onClick={handleBack}
              disabled={currentStep === 0 || saving}
              className="rounded-full"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back
            </Button>
            <Button
              onClick={handleNext}
              disabled={saving}
              className="rounded-full bg-mise hover:bg-mise-dark"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : currentStep === STEPS.length - 1 ? (
                <>
                  Go to Dashboard
                  <ArrowRight className="w-4 h-4 ml-2" />
                </>
              ) : (
                <>
                  Next
                  <ArrowRight className="w-4 h-4 ml-2" />
                </>
              )}
            </Button>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default SetupWizard;
