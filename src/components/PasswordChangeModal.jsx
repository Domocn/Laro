import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Lock, Loader2, Check, X } from 'lucide-react';
import { toast } from 'sonner';
import api from '../lib/api';

export const PasswordChangeModal = () => {
  const { forcePasswordChange, changePassword } = useAuth();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [policy, setPolicy] = useState({
    min_length: 8,
    require_uppercase: false,
    require_number: false,
    require_special: false,
  });

  useEffect(() => {
    if (forcePasswordChange) {
      api.get('/auth/password-policy')
        .then(res => setPolicy(res.data))
        .catch(() => {}); // Use defaults if fetch fails
    }
  }, [forcePasswordChange]);

  if (!forcePasswordChange) return null;

  const checks = [
    { met: newPassword.length >= policy.min_length, label: `At least ${policy.min_length} characters` },
    ...(policy.require_uppercase ? [{ met: /[A-Z]/.test(newPassword), label: 'One uppercase letter' }] : []),
    ...(policy.require_number ? [{ met: /\d/.test(newPassword), label: 'One number' }] : []),
    ...(policy.require_special ? [{ met: /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(newPassword), label: 'One special character' }] : []),
  ];

  const allMet = newPassword.length > 0 && checks.every(c => c.met);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (!allMet) {
      setError('Password does not meet all requirements');
      return;
    }

    setLoading(true);
    setError('');
    try {
      await changePassword(currentPassword, newPassword);
      toast.success('Password updated!');
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to change password';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl shadow-xl border border-border/60 p-8 w-full max-w-md">
        <div className="text-center mb-6">
          <div className="w-14 h-14 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Lock className="w-7 h-7 text-amber-600" />
          </div>
          <h2 className="font-heading text-xl font-bold">Password Update Required</h2>
          <p className="text-muted-foreground text-sm mt-2">
            Our password policy has been updated. Please set a new password that meets the requirements.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="currentPassword">Current Password</Label>
            <Input
              id="currentPassword"
              type="password"
              value={currentPassword}
              onChange={(e) => { setCurrentPassword(e.target.value); setError(''); }}
              className="rounded-xl bg-cream-subtle border-transparent focus:border-laro"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="newPassword">New Password</Label>
            <Input
              id="newPassword"
              type="password"
              value={newPassword}
              onChange={(e) => { setNewPassword(e.target.value); setError(''); }}
              className="rounded-xl bg-cream-subtle border-transparent focus:border-laro"
              required
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirmPassword">Confirm New Password</Label>
            <Input
              id="confirmPassword"
              type="password"
              value={confirmPassword}
              onChange={(e) => { setConfirmPassword(e.target.value); setError(''); }}
              className="rounded-xl bg-cream-subtle border-transparent focus:border-laro"
              required
            />
          </div>

          {/* Password requirements checklist */}
          {newPassword.length > 0 && (
            <div className="bg-gray-50 rounded-xl p-3 space-y-1.5">
              <p className="text-xs font-medium text-muted-foreground mb-1">Password requirements:</p>
              {checks.map((check, i) => (
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

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          <Button
            type="submit"
            className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
            disabled={loading || !currentPassword || !allMet || newPassword !== confirmPassword}
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
                <span className="ml-2">Updating...</span>
              </>
            ) : (
              'Update Password'
            )}
          </Button>
        </form>
      </div>
    </div>
  );
};
