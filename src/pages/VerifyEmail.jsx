import React, { useState, useEffect } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { MailCheck, Loader2, CheckCircle, XCircle } from 'lucide-react';
import { toast } from 'sonner';

export const VerifyEmail = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();
  const { verifyEmail } = useAuth();

  const [status, setStatus] = useState('verifying'); // verifying, success, error
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    const verify = async () => {
      if (!token) {
        setStatus('error');
        setErrorMessage('No verification token provided');
        return;
      }

      try {
        await verifyEmail(token);
        setStatus('success');
        toast.success('Email verified successfully!');
      } catch (error) {
        setStatus('error');
        setErrorMessage(error.response?.data?.detail || 'Verification failed. The link may have expired.');
      }
    };

    verify();
  }, [token, verifyEmail]);

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
          {status === 'verifying' && (
            <>
              <div className="w-16 h-16 bg-laro/10 rounded-full flex items-center justify-center mx-auto mb-6">
                <Loader2 className="w-8 h-8 text-laro animate-spin" />
              </div>
              <h1 className="font-heading text-2xl font-bold mb-2">Verifying Email</h1>
              <p className="text-muted-foreground">Please wait while we verify your email address...</p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <CheckCircle className="w-8 h-8 text-green-600" />
              </div>
              <h1 className="font-heading text-2xl font-bold mb-2">Email Verified!</h1>
              <p className="text-muted-foreground mb-6">
                Your email has been verified successfully. You can now log in to your account.
              </p>
              <Button
                onClick={() => navigate('/login')}
                className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
              >
                Go to Login
              </Button>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <XCircle className="w-8 h-8 text-red-600" />
              </div>
              <h1 className="font-heading text-2xl font-bold mb-2">Verification Failed</h1>
              <p className="text-muted-foreground mb-6">{errorMessage}</p>
              <div className="space-y-3">
                <Button
                  onClick={() => navigate('/login')}
                  className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
                >
                  Go to Login
                </Button>
                <p className="text-sm text-muted-foreground">
                  Need a new verification link? Log in with your credentials and we'll send a new one.
                </p>
              </div>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
};
