import React, { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { securityApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Mail, ArrowRight, Loader2, Check, ArrowLeft, Key } from 'lucide-react';
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
      toast.error(error.response?.data?.detail || 'Failed to send reset email');
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
                      className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-mise"
                      required
                      data-testid="forgot-email"
                    />
                  </div>
                </div>

                <Button 
                  type="submit" 
                  className="w-full rounded-full bg-mise hover:bg-mise-dark h-12"
                  disabled={loading}
                  data-testid="forgot-submit"
                >
                  {loading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
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
                    className="text-mise hover:underline text-sm break-all"
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
            <Link to="/login" className="text-mise hover:underline font-medium flex items-center justify-center gap-1">
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

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }
    
    if (password.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }
    
    setLoading(true);
    
    try {
      await securityApi.confirmPasswordReset(token, password);
      setSuccess(true);
      toast.success('Password reset successfully!');
      setTimeout(() => navigate('/login'), 2000);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to reset password');
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
            <Button className="rounded-full bg-mise hover:bg-mise-dark">
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
            src="/mise-banner.svg"
            alt="Laro - Bring order to your larder"
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
                      className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-mise"
                      required
                      minLength={8}
                      data-testid="reset-password"
                    />
                  </div>
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
                      className="pl-10 rounded-xl bg-cream-subtle border-transparent focus:border-mise"
                      required
                      data-testid="reset-confirm-password"
                    />
                  </div>
                </div>

                <Button 
                  type="submit" 
                  className="w-full rounded-full bg-mise hover:bg-mise-dark h-12"
                  disabled={loading}
                  data-testid="reset-submit"
                >
                  {loading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
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
