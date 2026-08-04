import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { User, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export const NameUpdateModal = () => {
  const { nameUpdateRequired, updateName } = useAuth();
  const [firstName, setFirstName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!nameUpdateRequired) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const trimmed = firstName.trim();
    if (trimmed.length < 2) {
      setError('Name must be at least 2 characters');
      return;
    }
    if (trimmed.includes('@')) {
      setError('Please enter your name, not your email');
      return;
    }

    setLoading(true);
    setError('');
    try {
      await updateName(trimmed);
      toast.success('Name updated!');
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to update name';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl shadow-xl border border-border/60 p-8 w-full max-w-md">
        <div className="text-center mb-6">
          <div className="w-14 h-14 bg-laro/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <User className="w-7 h-7 text-laro" />
          </div>
          <h2 className="font-heading text-xl font-bold">What's your first name?</h2>
          <p className="text-muted-foreground text-sm mt-2">
            We need your real first name to personalise your experience.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="firstName">First Name</Label>
            <Input
              id="firstName"
              type="text"
              placeholder="e.g. Sarah"
              value={firstName}
              onChange={(e) => { setFirstName(e.target.value); setError(''); }}
              className="rounded-xl bg-cream-subtle border-transparent focus:border-laro"
              autoFocus
              required
              minLength={2}
              maxLength={50}
            />
          </div>

          {error && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>
          )}

          <Button
            type="submit"
            className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
            disabled={loading || firstName.trim().length < 2}
          >
            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              'Continue'
            )}
          </Button>
        </form>
      </div>
    </div>
  );
};
