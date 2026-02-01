import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { ChefHat, Mail, Lock, User, ArrowRight, Loader2, Smartphone } from 'lucide-react';
import { toast } from 'sonner';

export const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [requires2FA, setRequires2FA] = useState(false);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
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
      
      toast.success('Welcome back!');
      navigate('/dashboard');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Invalid credentials');
    } finally {
      setLoading(false);
    }
  };

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
            src="/mise-banner.svg"
            alt="Laro - Bring order to your larder"
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
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-mise"
                  required
                  data-testid="login-email"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-mise"
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
                  <Smartphone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <Input
                    id="totp"
                    type="text"
                    placeholder="000000"
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-mise font-mono text-center tracking-widest"
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
              className="w-full rounded-full bg-mise hover:bg-mise-dark h-12"
              disabled={loading}
              data-testid="login-submit"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  {requires2FA ? 'Verify' : 'Sign In'}
                  <ArrowRight className="w-4 h-4 ml-2" />
                </>
              )}
            </Button>
          </form>

          <p className="text-center text-sm text-muted-foreground mt-6">
            Don't have an account?{' '}
            <Link to="/register" className="text-mise hover:underline font-medium">
              Sign up
            </Link>
          </p>
          <p className="text-center text-sm mt-2">
            <Link to="/forgot-password" className="text-muted-foreground hover:text-mise">
              Forgot your password?
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
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const result = await register(name, email, password, null, inviteCode || null);
      // Clear any existing onboarding flag to ensure walkthrough shows for new user
      if (result?.user?.id) {
        localStorage.removeItem(`mise_onboarding_${result.user.id}`);
      }
      toast.success('Account created successfully!');
      navigate('/dashboard');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

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
            src="/mise-banner.svg"
            alt="Laro - Bring order to your larder"
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
              <Label htmlFor="name">Name</Label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="name"
                  type="text"
                  placeholder="Your name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-mise"
                  required
                  data-testid="register-name"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-mise"
                  required
                  data-testid="register-email"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-mise"
                  required
                  minLength={6}
                  data-testid="register-password"
                />
              </div>
            </div>

            {/* Invite Code (optional) */}
            <div className="space-y-2">
              {!showInviteCode ? (
                <button
                  type="button"
                  onClick={() => setShowInviteCode(true)}
                  className="text-sm text-mise hover:underline"
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
                    className="rounded-xl bg-cream-subtle border-transparent focus:border-mise"
                    data-testid="register-invite-code"
                  />
                </>
              )}
            </div>

            <Button 
              type="submit" 
              className="w-full rounded-full bg-mise hover:bg-mise-dark h-12"
              disabled={loading}
              data-testid="register-submit"
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <>
                  Create Account
                  <ArrowRight className="w-4 h-4 ml-2" />
                </>
              )}
            </Button>
          </form>

          <p className="text-center text-sm text-muted-foreground mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-mise hover:underline font-medium">
              Sign in
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
};
