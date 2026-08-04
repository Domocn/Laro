import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ChefHat, Mail, Lock, User, ArrowRight, Loader2, Smartphone, MailCheck, RefreshCw, Check, X } from 'lucide-react';
import { toast } from 'sonner';
import api, { oauthApi } from '../lib/api';

// Email Verification Component
const EmailVerification = ({ email, onResend, onBack, loading }) => {
  const [resendCooldown, setResendCooldown] = useState(0);

  const handleResend = async () => {
    if (resendCooldown > 0) return;
    await onResend();
    setResendCooldown(60);
    const interval = setInterval(() => {
      setResendCooldown((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center p-4">
      <motion.div
        className="w-full max-w-md"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <Link to="/" className="flex justify-center mb-8">
          <img src="/laro-banner.png" alt="Laro" className="h-14" />
        </Link>

        <div className="bg-white rounded-2xl shadow-card border border-border/60 p-8 text-center">
          <div className="w-16 h-16 bg-laro/10 rounded-full flex items-center justify-center mx-auto mb-6">
            <MailCheck className="w-8 h-8 text-laro" aria-hidden="true" />
          </div>

          <h1 className="font-heading text-2xl font-bold mb-2">Check Your Email</h1>
          <p className="text-muted-foreground mb-2">
            We've sent a verification link to:
          </p>
          <p className="font-semibold text-foreground mb-6">{email}</p>

          <p className="text-sm text-muted-foreground mb-6">
            Click the link in the email to verify your account. If you don't see it, check your spam folder.
          </p>

          <div className="space-y-3">
            <Button
              onClick={handleResend}
              disabled={loading || resendCooldown > 0}
              variant="outline"
              className="w-full rounded-full h-12"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
              ) : (
                <>
                  <RefreshCw className="w-4 h-4 mr-2" aria-hidden="true" />
                  {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend Email'}
                </>
              )}
            </Button>

            <Button
              onClick={onBack}
              variant="ghost"
              className="w-full"
            >
              Back to Login
            </Button>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

// OAuth Buttons Component
const OAuthButtons = ({ dividerText = "or" }) => {
  const [oauthStatus, setOauthStatus] = useState({ google: false, github: false });
  const [oauthLoading, setOauthLoading] = useState(null);

  useEffect(() => {
    oauthApi.getStatus()
      .then(res => setOauthStatus(res.data))
      .catch(() => {});
  }, []);

  const hasOAuth = oauthStatus.google || oauthStatus.github;
  if (!hasOAuth) return null;

  const handleOAuth = async (provider) => {
    setOauthLoading(provider);
    try {
      const res = provider === 'google'
        ? await oauthApi.getGoogleAuthUrl()
        : await oauthApi.getGitHubAuthUrl();
      window.location.href = res.data.auth_url;
    } catch (error) {
      const message = error.response?.data?.detail
        || `Couldn't connect to ${provider}. Please check your connection and try again.`;
      toast.error(message);
      setOauthLoading(null);
    }
  };

  return (
    <div className="mt-6" role="group" aria-label="Social sign-in options">
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-border/60" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="bg-white px-4 text-muted-foreground">{dividerText}</span>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-3">
        {oauthStatus.google && (
          <Button
            type="button"
            variant="outline"
            className="w-full rounded-full h-12 border-border/60 focus-visible:ring-2 focus-visible:ring-laro focus-visible:ring-offset-2"
            onClick={() => handleOAuth('google')}
            disabled={oauthLoading !== null}
            aria-label="Continue with Google"
          >
            {oauthLoading === 'google' ? (
              <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
            ) : (
              <>
                <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                Continue with Google
              </>
            )}
          </Button>
        )}

        {oauthStatus.github && (
          <Button
            type="button"
            variant="outline"
            className="w-full rounded-full h-12 border-border/60 focus-visible:ring-2 focus-visible:ring-laro focus-visible:ring-offset-2"
            onClick={() => handleOAuth('github')}
            disabled={oauthLoading !== null}
            aria-label="Continue with GitHub"
          >
            {oauthLoading === 'github' ? (
              <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
            ) : (
              <>
                <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/>
                </svg>
                Continue with GitHub
              </>
            )}
          </Button>
        )}
      </div>
    </div>
  );
};

export const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [requires2FA, setRequires2FA] = useState(false);
  const [requiresVerification, setRequiresVerification] = useState(false);
  const [verificationEmail, setVerificationEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, resendVerification } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const result = await login(email, password, requires2FA ? totpCode : null);

      if (result?.requires_2fa) {
        setRequires2FA(true);
        toast.info('Please enter your 2FA code');
        setLoading(false);
        return;
      }

      if (result?.requires_verification) {
        setRequiresVerification(true);
        setVerificationEmail(result.email || email);
        toast.info('Please verify your email address');
        setLoading(false);
        return;
      }

      toast.success('Welcome back!');
      navigate('/dashboard');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Incorrect email or password. Please try again. (E-AU001)');
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = async () => {
    setLoading(true);
    try {
      await resendVerification(verificationEmail);
      toast.success('Verification email sent!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Couldn\'t resend the verification email. Please try again. (E-AU002)');
    } finally {
      setLoading(false);
    }
  };

  if (requiresVerification) {
    return (
      <EmailVerification
        email={verificationEmail}
        onResend={handleResendVerification}
        onBack={() => setRequiresVerification(false)}
        loading={loading}
      />
    );
  }

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center p-4">
      <motion.div 
        className="w-full max-w-md"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Logo */}
        <Link to="/" className="flex justify-center mb-8">
          <img
            src="/laro-banner.png"
            alt="Laro - Your Kitchen Sidekick"
            className="h-14"
          />
        </Link>

        {/* Form Card */}
        <div className="bg-white rounded-2xl shadow-card border border-border/60 p-8">
          <div className="text-center mb-8">
            <h1 className="font-heading text-2xl font-bold">Welcome Back</h1>
            <p className="text-muted-foreground mt-2">Sign in to your account</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" aria-hidden="true" />
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-laro"
                  required
                  data-testid="login-email"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" aria-hidden="true" />
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-laro"
                  required
                  data-testid="login-password"
                />
              </div>
            </div>

            {/* 2FA Code Input - only shows when required */}
            {requires2FA && (
              <motion.div 
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="space-y-2"
              >
                <Label htmlFor="totp">Two-Factor Authentication Code</Label>
                <div className="relative">
                  <Smartphone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" aria-hidden="true" />
                  <Input
                    id="totp"
                    type="text"
                    placeholder="000000"
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-laro font-mono text-center tracking-widest"
                    maxLength={6}
                    autoFocus
                    data-testid="login-totp"
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  Enter the code from your authenticator app or a backup code
                </p>
              </motion.div>
            )}

            <Button 
              type="submit" 
              className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
              disabled={loading}
              data-testid="login-submit"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
                  <span className="ml-2">Signing in...</span>
                </>
              ) : (
                <>
                  {requires2FA ? 'Verify' : 'Sign In'}
                  <ArrowRight className="w-4 h-4 ml-2" aria-hidden="true" />
                </>
              )}
            </Button>
          </form>

          <OAuthButtons dividerText="or continue with" />

          <p className="text-center text-sm text-muted-foreground mt-6">
            Don't have an account?{' '}
            <Link to="/register" className="text-laro hover:underline font-medium">
              Sign up
            </Link>
          </p>
          <p className="text-center text-sm mt-2">
            <Link to="/forgot-password" className="text-muted-foreground hover:text-laro">
              Forgot your password?
            </Link>
          </p>
          <p className="text-center text-xs text-muted-foreground mt-4">
            <Link to="/privacy-policy" className="hover:text-laro">
              Privacy Policy
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
};

export const Register = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [showInviteCode, setShowInviteCode] = useState(false);
  const [requiresVerification, setRequiresVerification] = useState(false);
  const [verificationEmail, setVerificationEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [policy, setPolicy] = useState({ min_length: 8, require_uppercase: false, require_number: false, require_special: false });
  const { register, resendVerification } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/auth/password-policy').then(res => setPolicy(res.data)).catch(() => {});
  }, []);

  const passwordChecks = [
    { met: password.length >= policy.min_length, label: `At least ${policy.min_length} characters` },
    ...(policy.require_uppercase ? [{ met: /[A-Z]/.test(password), label: 'One uppercase letter' }] : []),
    ...(policy.require_number ? [{ met: /\d/.test(password), label: 'One number' }] : []),
    ...(policy.require_special ? [{ met: /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(password), label: 'One special character' }] : []),
  ];
  const passwordValid = password.length > 0 && passwordChecks.every(c => c.met);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const result = await register(name, email, password, null, inviteCode || null);
      // A stale flag from a recycled user id would silently skip the
      // walkthrough for a genuinely new account. Ported from Domocn/Laro.
      if (result?.user?.id) {
        localStorage.removeItem(`laro_onboarding_${result.user.id}`);
      }

      if (result?.requires_verification) {
        setRequiresVerification(true);
        setVerificationEmail(result.email || email);
        toast.success('Account created! Please check your email to verify.');
        setLoading(false);
        return;
      }

      toast.success('Account created successfully!');
      navigate('/dashboard');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Something went wrong. Please check your details and try again. (E-AU003)');
    } finally {
      setLoading(false);
    }
  };

  const handleResendVerification = async () => {
    setLoading(true);
    try {
      await resendVerification(verificationEmail);
      toast.success('Verification email sent!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Couldn\'t resend the verification email. Please try again. (E-AU004)');
    } finally {
      setLoading(false);
    }
  };

  if (requiresVerification) {
    return (
      <EmailVerification
        email={verificationEmail}
        onResend={handleResendVerification}
        onBack={() => navigate('/login')}
        loading={loading}
      />
    );
  }

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center p-4">
      <motion.div 
        className="w-full max-w-md"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {/* Logo */}
        <Link to="/" className="flex justify-center mb-8">
          <img
            src="/laro-banner.png"
            alt="Laro - Your Kitchen Sidekick"
            className="h-14"
          />
        </Link>

        {/* Form Card */}
        <div className="bg-white rounded-2xl shadow-card border border-border/60 p-8">
          <div className="text-center mb-8">
            <h1 className="font-heading text-2xl font-bold">Create Account</h1>
            <p className="text-muted-foreground mt-2">Start organizing your recipes</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="name">First Name</Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" aria-hidden="true" />
                <Input
                  id="name"
                  type="text"
                  placeholder="e.g. Sarah"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-laro"
                  required
                  minLength={2}
                  maxLength={50}
                  data-testid="register-name"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" aria-hidden="true" />
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-laro"
                  required
                  data-testid="register-email"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" aria-hidden="true" />
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-laro"
                  required
                  data-testid="register-password"
                />
              </div>
              {password.length > 0 && (
                <div className="bg-gray-50 rounded-xl p-3 space-y-1.5">
                  <p className="text-xs font-medium text-muted-foreground mb-1">Password requirements:</p>
                  {passwordChecks.map((check, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm">
                      {check.met ? (
                        <Check className="w-4 h-4 text-green-600 flex-shrink-0" aria-hidden="true" />
                      ) : (
                        <X className="w-4 h-4 text-red-400 flex-shrink-0" aria-hidden="true" />
                      )}
                      <span className={check.met ? 'text-green-700' : 'text-muted-foreground'}>
                        {check.label}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Invite Code (optional) */}
            <div className="space-y-2">
              {!showInviteCode ? (
                <button
                  type="button"
                  onClick={() => setShowInviteCode(true)}
                  className="text-sm text-laro hover:underline"
                >
                  Have an invite code?
                </button>
              ) : (
                <>
                  <Label htmlFor="inviteCode">Invite Code (optional)</Label>
                  <Input
                    id="inviteCode"
                    type="text"
                    placeholder="Enter invite code"
                    value={inviteCode}
                    onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                    className="rounded-xl bg-cream-subtle border-transparent focus:border-laro"
                    data-testid="register-invite-code"
                  />
                </>
              )}
            </div>

            <Button 
              type="submit" 
              className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
              disabled={loading}
              data-testid="register-submit"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
                  <span className="ml-2">Creating account...</span>
                </>
              ) : (
                <>
                  Create Account
                  <ArrowRight className="w-4 h-4 ml-2" aria-hidden="true" />
                </>
              )}
            </Button>
          </form>

          <OAuthButtons dividerText="or sign up with" />

          <p className="text-center text-sm text-muted-foreground mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-laro hover:underline font-medium">
              Sign in
            </Link>
          </p>

          <p className="text-center text-xs text-muted-foreground mt-4">
            By creating an account, you agree to our{' '}
            <Link to="/privacy-policy" className="text-laro hover:underline">
              Privacy Policy
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
};
