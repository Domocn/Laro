import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { oauthApi, authApi, googleHealthApi } from '../lib/api';
import { markOnboardingPending } from '../lib/onboarding';
import { Loader2, Check, AlertCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';

export const OAuthCallback = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { provider } = useParams();
  const { updateUser } = useAuth();
  
  const [status, setStatus] = useState('loading'); // loading, success, error
  const [error, setError] = useState('');

  useEffect(() => {
    handleCallback();
  }, []);

  const handleCallback = async () => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const errorParam = searchParams.get('error');

    if (errorParam) {
      setStatus('error');
      setError(searchParams.get('error_description') || 'Authentication was cancelled');
      return;
    }

    if (!code) {
      setStatus('error');
      setError('No authorization code received');
      return;
    }

    // Google Health linking (user must already be logged in)
    if (provider === 'google-health') {
      try {
        await googleHealthApi.callback(code, state);
        setStatus('success');
        toast.success('Google Health connected');
        setTimeout(() => navigate('/settings/security'), 1200);
      } catch (err) {
        console.error('Google Health callback error:', err);
        setStatus('error');
        setError(err.response?.data?.detail || 'Failed to link Google Health');
      }
      return;
    }

    try {
      let response;
      
      if (provider === 'google') {
        response = await oauthApi.googleCallback(code, state);
      } else if (provider === 'github') {
        response = await oauthApi.githubCallback(code, state);
      } else {
        throw new Error('Unknown provider');
      }

      if (!response.data || !response.data.token || !response.data.user) {
        throw new Error('Invalid response from server');
      }

      const { token, user, is_new } = response.data;

      // Save auth data
      localStorage.setItem('token', token);
      localStorage.setItem('user', JSON.stringify(user));
      updateUser(user);

      // Refresh /auth/me so Pro/owner flags are present even if OAuth payload was thin
      try {
        const meRes = await authApi.me();
        if (meRes?.data?.id) {
          localStorage.setItem('user', JSON.stringify(meRes.data));
          updateUser(meRes.data);
        }
      } catch (_) { /* keep OAuth payload */ }

      setStatus('success');
      
      if (is_new) {
        markOnboardingPending(user.id);
        toast.success('Account created successfully!');
      } else {
        toast.success('Welcome back!');
      }

      // Redirect after short delay
      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);

    } catch (err) {
      console.error('OAuth callback error:', err);
      setStatus('error');
      setError(err.response?.data?.detail || 'Authentication failed');
    }
  };

  const isHealth = provider === 'google-health';

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center p-4">
      <motion.div 
        className="w-full max-w-md"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="bg-white rounded-2xl shadow-card border border-border/60 p-8 text-center">
          {status === 'loading' && (
            <>
              <Loader2 className="w-12 h-12 animate-spin text-laro mx-auto mb-4" />
              <h1 className="font-heading text-xl font-bold mb-2">
                {isHealth ? 'Connecting Google Health...' : 'Signing you in...'}
              </h1>
              <p className="text-muted-foreground">
                {isHealth
                  ? 'Please wait while we finish linking nutrition sync.'
                  : `Please wait while we complete authentication with ${provider}.`}
              </p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Check className="w-8 h-8 text-green-600" />
              </div>
              <h1 className="font-heading text-xl font-bold mb-2">Success!</h1>
              <p className="text-muted-foreground">
                {isHealth
                  ? 'Redirecting to security settings...'
                  : 'Redirecting to your dashboard...'}
              </p>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <AlertCircle className="w-8 h-8 text-red-600" />
              </div>
              <h1 className="font-heading text-xl font-bold mb-2">
                {isHealth ? 'Link Failed' : 'Authentication Failed'}
              </h1>
              <p className="text-muted-foreground mb-6">{error}</p>
              <div className="flex gap-2 justify-center">
                <Button
                  variant="outline"
                  onClick={() => navigate(isHealth ? '/settings/security' : '/login')}
                  className="rounded-full"
                >
                  {isHealth ? 'Back to Settings' : 'Back to Login'}
                </Button>
                <Button
                  onClick={() => {
                    setStatus('loading');
                    setError('');
                    handleCallback();
                  }}
                  className="rounded-full bg-laro hover:bg-laro-dark"
                >
                  Try Again
                </Button>
              </div>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
};
