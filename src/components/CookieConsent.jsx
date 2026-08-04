import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Cookie, X } from 'lucide-react';
import { Button } from './ui/button';

const COOKIE_CONSENT_KEY = 'laro_cookie_consent';

export const CookieConsent = () => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem(COOKIE_CONSENT_KEY);
    if (!consent) {
      // Small delay so it doesn't flash on page load
      const timer = setTimeout(() => setVisible(true), 800);
      return () => clearTimeout(timer);
    }
  }, []);

  const accept = () => {
    localStorage.setItem(COOKIE_CONSENT_KEY, 'accepted');
    setVisible(false);
  };

  const decline = () => {
    localStorage.setItem(COOKIE_CONSENT_KEY, 'declined');
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 p-4 animate-in slide-in-from-bottom duration-500">
      <div className="max-w-2xl mx-auto bg-white dark:bg-zinc-900 rounded-2xl shadow-lg border border-border/60 p-4 sm:p-5">
        <div className="flex items-start gap-3">
          <Cookie className="w-5 h-5 text-laro mt-0.5 shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-foreground">
              We use cookies and local storage to keep you signed in, remember your preferences, and improve your experience.{' '}
              <Link to="/privacy-policy" className="text-laro hover:underline font-medium">
                Privacy Policy
              </Link>
            </p>
            <div className="flex items-center gap-2 mt-3">
              <Button
                onClick={accept}
                size="sm"
                className="rounded-full bg-laro hover:bg-laro-dark text-white"
              >
                Accept
              </Button>
              <Button
                onClick={decline}
                variant="ghost"
                size="sm"
                className="rounded-full text-muted-foreground"
              >
                Decline
              </Button>
            </div>
          </div>
          <button
            onClick={decline}
            className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
            aria-label="Dismiss cookie notice"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};
