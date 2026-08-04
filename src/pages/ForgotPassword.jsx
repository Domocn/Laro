import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { securityApi } from '../lib/api';
import api from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Mail, ArrowRight, Loader2, Check, ArrowLeft, Key, X } from 'lucide-react';
import { toast } from 'sonner';

export const ForgotPassword = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [token, setToken] = useState(''); // For development mode

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const res = await securityApi.requestPasswordReset(email);
      setSent(true);
      
      // In development mode, the token might be returned
      if (res.data.token) {
        setToken(res.data.token);
      }
      
      toast.success('Check your email for reset instructions');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Couldn\'t send the reset email. Please try again. (E-FP001)');
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
            src="/laro-banner.png"
            alt="Laro - Your Kitchen Sidekick"
            className="h-14"
          />
        </Link>

        {/* Form Card */}
        <div className="bg-white rounded-2xl shadow-card border border-border/60 p-8">
          {!sent ? (
            <>
              <div className="text-center mb-8">
                <h1 className="font-heading text-2xl font-bold">Forgot Password</h1>
                <p className="text-muted-foreground mt-2">Enter your email to reset your password</p>
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
                      className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-laro"
                      required
                      data-testid="forgot-email"
                    />
                  </div>
                </div>

                <Button 
                  type="submit" 
                  className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
                  disabled={loading}
                  data-testid="forgot-submit"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
                      <span className="ml-2">Sending...</span>
                    </>
                  ) : (
                    <>
                      Send Reset Link
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </>
                  )}
                </Button>
              </form>
            </>
          ) : (
            <div className="text-center">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Check className="w-8 h-8 text-green-600" />
              </div>
              <h1 className="font-heading text-2xl font-bold mb-2">Check Your Email</h1>
              <p className="text-muted-foreground mb-6">
                We've sent password reset instructions to <strong>{email}</strong>
              </p>
              
              {/* Development mode token display */}
              {token && (
                <div className="mb-6 p-4 bg-amber-50 rounded-xl border border-amber-200 text-left">
                  <p className="text-xs text-amber-800 font-medium mb-2">Development Mode</p>
                  <p className="text-xs text-amber-700 mb-2">
                    Email is disabled. Use this link to reset your password:
                  </p>
                  <Link 
                    to={`/reset-password?token=${token}`}
                    className="text-laro hover:underline text-sm break-all"
                  >
                    /reset-password?token={token}
                  </Link>
                </div>
              )}
              
              <Button
                variant="outline"
                onClick={() => {
                  setSent(false);
                  setEmail('');
                  setToken('');
                }}
                className="rounded-full"
              >
                Send to different email
              </Button>
            </div>
          )}

          <p className="text-center text-sm text-muted-foreground mt-6">
            <Link to="/login" className="text-laro hover:underline font-medium flex items-center justify-center gap-1">
              <ArrowLeft className="w-4 h-4" />
              Back to Sign In
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
};

export const ResetPassword = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [policy, setPolicy] = useState({ min_length: 8, require_uppercase: false, require_number: false, require_special: false });

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

    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }

    if (!passwordValid) {
      toast.error('Password does not meet all requirements');
      return;
    }
    
    setLoading(true);
    
    try {
      await securityApi.confirmPasswordReset(token, password);
      setSuccess(true);
      toast.success('Password reset successfully!');
      setTimeout(() => navigate('/login'), 2000);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Couldn\'t reset your password. Please try again. (E-FP002)');
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-cream flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-card border border-border/60 p-8 max-w-md w-full text-center">
          <h1 className="font-heading text-2xl font-bold mb-4">Invalid Link</h1>
          <p className="text-muted-foreground mb-6">
            This password reset link is invalid or has expired.
          </p>
          <Link to="/forgot-password">
            <Button className="rounded-full bg-laro hover:bg-laro-dark">
              Request New Link
            </Button>
          </Link>
        </div>
      </div>
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
          {!success ? (
            <>
              <div className="text-center mb-8">
                <h1 className="font-heading text-2xl font-bold">Reset Password</h1>
                <p className="text-muted-foreground mt-2">Enter your new password</p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="password">New Password</Label>
                  <div className="relative">
                    <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input
                      id="password"
                      type="password"
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-laro"
                      required
                      data-testid="reset-password"
                    />
                  </div>
                  {password.length > 0 && (
                    <div className="bg-gray-50 rounded-xl p-3 space-y-1.5">
                      <p className="text-xs font-medium text-muted-foreground mb-1">Password requirements:</p>
                      {passwordChecks.map((check, i) => (
                        <div key={i} className="flex items-center gap-2 text-sm">
                          {check.met ? (
                            <Check className="w-4 h-4 text-green-600 flex-shrink-0" />
                          ) : (
                            <X className="w-4 h-4 text-red-400 flex-shrink-0" />
                          )}
                          <span className={check.met ? 'text-green-700' : 'text-muted-foreground'}>
                            {check.label}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="confirm-password">Confirm Password</Label>
                  <div className="relative">
                    <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                    <Input
                      id="confirm-password"
                      type="password"
                      placeholder="••••••••"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-laro"
                      required
                      data-testid="reset-confirm-password"
                    />
                  </div>
                </div>

                <Button 
                  type="submit" 
                  className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
                  disabled={loading}
                  data-testid="reset-submit"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
                      <span className="ml-2">Resetting...</span>
                    </>
                  ) : (
                    <>
                      Reset Password
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </>
                  )}
                </Button>
              </form>
            </>
          ) : (
            <div className="text-center">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Check className="w-8 h-8 text-green-600" />
              </div>
              <h1 className="font-heading text-2xl font-bold mb-2">Password Reset!</h1>
              <p className="text-muted-foreground mb-6">
                Your password has been reset successfully. Redirecting to login...
              </p>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
};
