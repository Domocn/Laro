import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { oauthApi } from '../lib/api';
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

    try {
      let response;
      
      if (provider === 'google') {
        response = await oauthApi.googleCallback(code, state);
      } else if (provider === 'github') {
        response = await oauthApi.githubCallback(code, state);
      } else {
        throw new Error('Unknown provider');
      }

      const { token, user, is_new } = response.data;

      // Save auth data
      localStorage.setItem('token', token);
      localStorage.setItem('user', JSON.stringify(user));
      updateUser(user);

      setStatus('success');

      if (is_new) {
        // Clear onboarding flag to ensure walkthrough shows for new user
        localStorage.removeItem(`mise_onboarding_${user.id}`);
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
              <Loader2 className="w-12 h-12 animate-spin text-mise mx-auto mb-4" />
              <h1 className="font-heading text-xl font-bold mb-2">Signing you in...</h1>
              <p className="text-muted-foreground">
                Please wait while we complete authentication with {provider}.
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
                Redirecting to your dashboard...
              </p>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <AlertCircle className="w-8 h-8 text-red-600" />
              </div>
              <h1 className="font-heading text-xl font-bold mb-2">Authentication Failed</h1>
              <p className="text-muted-foreground mb-6">{error}</p>
              <div className="flex gap-2 justify-center">
                <Button
                  variant="outline"
                  onClick={() => navigate('/login')}
                  className="rounded-full"
                >
                  Back to Login
                </Button>
                <Button
                  onClick={() => {
                    setStatus('loading');
                    setError('');
                    handleCallback();
                  }}
                  className="rounded-full bg-mise hover:bg-mise-dark"
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
