import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { AlertCircle, Copy, Key, Loader2, Trash2 } from 'lucide-react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { apiTokensApi } from '../../lib/api';
import { useLanguage } from '../../context/LanguageContext';
import { useAccessibility, confirmDestructive } from '../../context/AccessibilityContext';

/**
 * API tokens for integrations such as Home Assistant.
 *
 * Extracted from the Settings page: this block owns its own list, form and
 * reveal state, so none of it needs to live in the page component any more.
 * `active` tells it when the User tab is on screen so the list is fetched
 * lazily, exactly as before.
 */
export const ApiTokensSection = ({ active }) => {
  const { t } = useLanguage();
  const { confirmActions } = useAccessibility();

  const [apiTokens, setApiTokens] = useState([]);
  const [loadingTokens, setLoadingTokens] = useState(false);
  const [newTokenName, setNewTokenName] = useState('');
  const [newTokenExpiry, setNewTokenExpiry] = useState('never');
  const [creatingToken, setCreatingToken] = useState(false);
  const [newlyCreatedToken, setNewlyCreatedToken] = useState(null);
  const [showCreateToken, setShowCreateToken] = useState(false);

  const loadApiTokens = async () => {
    setLoadingTokens(true);
    try {
      const res = await apiTokensApi.list();
      setApiTokens(res.data || []);
    } catch (error) {
      console.error('Failed to load API tokens:', error);
    } finally {
      setLoadingTokens(false);
    }
  };

  // Load tokens the first time the User tab is actually shown.
  useEffect(() => {
    if (active && apiTokens.length === 0) {
      loadApiTokens();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  const handleCreateToken = async () => {
    if (!newTokenName.trim()) {
      toast.error(t('toastEnterTokenName'));
      return;
    }
    setCreatingToken(true);
    try {
      const expiryDays = newTokenExpiry === 'never' ? null : parseInt(newTokenExpiry);
      const res = await apiTokensApi.create({
        name: newTokenName.trim(),
        expires_in_days: expiryDays,
      });
      setNewlyCreatedToken(res.data.token);
      setNewTokenName('');
      setNewTokenExpiry('never');
      await loadApiTokens();
      toast.success(t('toastTokenCreated'));
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Couldn\'t create that token. Please try again. (E-ST017)');
    } finally {
      setCreatingToken(false);
    }
  };

  const handleRevokeToken = async (tokenId) => {
    if (!confirmDestructive(confirmActions, t('confirmRevokeApiToken'))) return;
    try {
      await apiTokensApi.revoke(tokenId);
      await loadApiTokens();
      toast.success(t('toastTokenRevoked'));
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Couldn\'t revoke the token. Please try again. (E-ST018)');
    }
  };

  const handleDeleteToken = async (tokenId) => {
    if (!confirmDestructive(confirmActions, t('confirmDeleteApiToken'))) return;
    try {
      await apiTokensApi.delete(tokenId);
      await loadApiTokens();
      toast.success(t('toastTokenDeleted'));
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Couldn\'t delete the token. Please try again. (E-ST019)');
    }
  };

  const copyToken = (token) => {
    navigator.clipboard.writeText(token);
    toast.success(t('toastTokenCopied'));
  };

  return (
    <motion.section
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.17 }}
      className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
    >
      <div className="p-4 border-b border-border/60 bg-cream-subtle">
        <h2 className="font-heading font-semibold flex items-center gap-2">
          <Key className="w-5 h-5 text-laro" />
          {t('apiTokens')}
        </h2>
      </div>

      <div className="p-4 space-y-4">
        <p className="text-sm text-muted-foreground">
          Create API tokens for integrations like Home Assistant. Tokens provide access to your account without sharing your password.
        </p>

        {/* Newly created token display */}
        {newlyCreatedToken && (
          <div className="p-4 bg-laro-light rounded-xl border border-laro/30">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-laro flex-shrink-0 mt-0.5" />
              <div className="flex-1 space-y-2">
                <p className="font-medium text-laro">{t('saveTokenNow')}</p>
                <p className="text-sm text-laro/80">This token will only be shown once. Copy it and store it securely.</p>
                <div className="flex items-center gap-2">
                  <code className="flex-1 p-2 bg-white rounded-lg text-sm font-mono break-all border">
                    {newlyCreatedToken}
                  </code>
                  <Button variant="outline" size="icon" onClick={() => copyToken(newlyCreatedToken)} className="rounded-lg flex-shrink-0">
                    <Copy className="w-4 h-4" />
                  </Button>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setNewlyCreatedToken(null)}
                  className="text-laro/70 hover:text-laro"
                >
                  I've saved my token
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Create new token */}
        {!showCreateToken ? (
          <Button
            variant="outline"
            onClick={() => setShowCreateToken(true)}
            className="rounded-full"
          >
            <Key className="w-4 h-4 mr-2" />
            {t('createNewToken')}
          </Button>
        ) : (
          <div className="p-4 bg-cream-subtle rounded-xl space-y-3">
            <div>
              <Label htmlFor="token-name" className="mb-2 block text-sm">{t('tokenName')}</Label>
              <Input
                id="token-name"
                placeholder="e.g., Home Assistant"
                value={newTokenName}
                onChange={(e) => setNewTokenName(e.target.value)}
                className="rounded-lg"
              />
            </div>
            <div>
              <Label htmlFor="token-expiry" className="mb-2 block text-sm">{t('expiration')}</Label>
              <Select value={newTokenExpiry} onValueChange={setNewTokenExpiry}>
                <SelectTrigger className="rounded-lg w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="never">Never expires</SelectItem>
                  <SelectItem value="30">30 days</SelectItem>
                  <SelectItem value="90">90 days</SelectItem>
                  <SelectItem value="365">1 year</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex gap-2 pt-2">
              <Button
                variant="outline"
                onClick={() => {
                  setShowCreateToken(false);
                  setNewTokenName('');
                  setNewTokenExpiry('never');
                }}
                className="rounded-full"
              >
                {t('cancel')}
              </Button>
              <Button
                onClick={handleCreateToken}
                disabled={creatingToken || !newTokenName.trim()}
                className="rounded-full bg-laro hover:bg-laro-dark"
              >
                {creatingToken ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Key className="w-4 h-4 mr-2" />}
                {t('createNewToken')}
              </Button>
            </div>
          </div>
        )}

        {/* Existing tokens list */}
        {loadingTokens ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-laro" />
          </div>
        ) : apiTokens.length > 0 ? (
          <div className="space-y-2">
            <Label className="text-sm text-muted-foreground">Your Tokens</Label>
            <div className="divide-y divide-border/60 border border-border/60 rounded-xl overflow-hidden">
              {apiTokens.map((token) => (
                <div key={token.id} className="p-3 flex items-center justify-between bg-white dark:bg-card">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium text-sm truncate">{token.name}</p>
                      {token.revoked && (
                        <span className="px-2 py-0.5 text-xs bg-red-100 text-red-600 rounded">{t('revoked')}</span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Created {new Date(token.created_at).toLocaleDateString()}
                      {token.expires_at && ` · Expires ${new Date(token.expires_at).toLocaleDateString()}`}
                      {token.last_used_at && ` · Last used ${new Date(token.last_used_at).toLocaleDateString()}`}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 ml-2">
                    {!token.revoked && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRevokeToken(token.id)}
                        className="text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                      >
                        Revoke
                      </Button>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDeleteToken(token.id)}
                      className="text-red-500 hover:text-red-600 hover:bg-red-50"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground text-center py-4">
            No API tokens yet. Create one to integrate with external services.
          </p>
        )}

        <div className="p-3 bg-amber-50 rounded-xl border border-amber-200">
          <p className="text-xs text-amber-800">
            <strong>Security tip:</strong> Only create tokens for services you trust. Tokens have full access to your account.
            Revoke any tokens you no longer need.
          </p>
        </div>
      </div>
    </motion.section>
  );
};
