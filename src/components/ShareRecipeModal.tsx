import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import {
  Share2,
  Link,
  Copy,
  Check,
  X,
  Loader2,
  ExternalLink,
  Clock,
  Eye,
  Trash2,
  QrCode,
  MessageCircle
} from 'lucide-react';
import { toast } from 'sonner';
import { sharingApi } from '../lib/api';

// WhatsApp icon component
const WhatsAppIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="currentColor">
    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
  </svg>
);

export const ShareRecipeModal = ({ isOpen, onClose, recipe }) => {
  const [loading, setLoading] = useState(false);
  const [existingLinks, setExistingLinks] = useState([]);
  const [loadingLinks, setLoadingLinks] = useState(true);
  const [copied, setCopied] = useState(false);
  const [showCreateNew, setShowCreateNew] = useState(false);
  const [includeLinksInShare, setIncludeLinksInShare] = useState(true);

  // New link options
  const [expiresInDays, setExpiresInDays] = useState(0); // 0 = never
  const [allowPrint, setAllowPrint] = useState(true);
  const [showAuthor, setShowAuthor] = useState(true);

  useEffect(() => {
    if (isOpen && recipe) {
      loadExistingLinks();
      loadShareSettings();
    }
  }, [isOpen, recipe]);

  const loadShareSettings = async () => {
    try {
      const res = await sharingApi.getSettings();
      setIncludeLinksInShare(res.data.include_links_in_share !== false);
    } catch (error) {
      console.error('Failed to load share settings:', error);
    }
  };

  const loadExistingLinks = async () => {
    setLoadingLinks(true);
    try {
      const res = await sharingApi.getMyLinks();
      // Filter to only show links for this recipe
      const recipeLinks = res.data.links.filter(
        link => link.recipe_id === recipe.id
      );
      setExistingLinks(recipeLinks);
      setShowCreateNew(recipeLinks.length === 0);
    } catch (error) {
      console.error('Failed to load share links:', error);
    } finally {
      setLoadingLinks(false);
    }
  };

  const handleCreateLink = async () => {
    setLoading(true);
    try {
      const res = await sharingApi.create({
        recipe_id: recipe.id,
        expires_in_days: expiresInDays || null,
        allow_print: allowPrint,
        show_author: showAuthor,
      });
      
      toast.success('Share link created!');
      await loadExistingLinks();
      setShowCreateNew(false);
      
      // Auto-copy the new link
      copyToClipboard(res.data.share_url);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create share link');
    } finally {
      setLoading(false);
    }
  };

  const handleRevokeLink = async (linkId) => {
    if (!window.confirm('Revoke this share link? Anyone with this link will no longer be able to view the recipe.')) {
      return;
    }
    
    try {
      await sharingApi.revoke(linkId);
      toast.success('Share link revoked');
      await loadExistingLinks();
    } catch (error) {
      toast.error('Failed to revoke link');
    }
  };

  const copyToClipboard = async (url) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      toast.success('Link copied to clipboard!');
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      toast.error('Failed to copy link');
    }
  };

  const handleWhatsAppShare = (shareUrl) => {
    // Format all ingredients
    const allIngredients = recipe.ingredients
      ?.map((ing, i) => `${i + 1}. ${typeof ing === 'string' ? ing : ing.text || ing.name}`)
      .join('\n');

    // Format all instructions
    const allInstructions = recipe.instructions
      ?.map((step, i) => `${i + 1}. ${typeof step === 'string' ? step : step.text || step.instruction}`)
      .join('\n\n');

    // Build time info line
    const timeInfo = [
      recipe.prep_time ? `⏱️ Prep: ${recipe.prep_time}` : '',
      recipe.cook_time ? `🍳 Cook: ${recipe.cook_time}` : '',
      recipe.servings ? `👥 Serves ${recipe.servings}` : ''
    ].filter(Boolean).join(' | ');

    // Create full recipe message
    let message = `🍳 *${recipe.title}*

${recipe.description ? `${recipe.description}\n\n` : ''}${timeInfo ? `${timeInfo}\n\n` : ''}📝 *Ingredients:*
${allIngredients || 'No ingredients listed'}

👨‍🍳 *Instructions:*
${allInstructions || 'No instructions listed'}`;

    // Add link if enabled
    if (includeLinksInShare && shareUrl) {
      message += `\n\n👉 View online: ${shareUrl}`;
    }

    message += `\n\n_Shared via Laro_`;

    const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(message)}`;
    window.open(whatsappUrl, '_blank');
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white dark:bg-card rounded-2xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col"
        data-testid="share-recipe-modal"
      >
        {/* Header */}
        <div className="p-4 border-b border-border/60 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-mise/10 rounded-xl flex items-center justify-center">
              <Share2 className="w-5 h-5 text-mise" />
            </div>
            <div>
              <h2 className="font-heading font-semibold text-lg">Share Recipe</h2>
              <p className="text-sm text-muted-foreground truncate max-w-[250px]">{recipe?.title}</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {loadingLinks ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-6 h-6 animate-spin text-mise" />
            </div>
          ) : (
            <>
              {/* Existing Links */}
              {existingLinks.length > 0 && !showCreateNew && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">Active Share Links</p>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowCreateNew(true)}
                      className="text-mise"
                    >
                      + New Link
                    </Button>
                  </div>
                  
                  {existingLinks.map((link) => (
                    <div
                      key={link.id}
                      className="border border-border/60 rounded-xl p-3 space-y-3"
                    >
                      <div className="flex items-center gap-2">
                        <Input
                          value={link.share_url}
                          readOnly
                          className="rounded-lg text-sm font-mono"
                        />
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => copyToClipboard(link.share_url)}
                          className="flex-shrink-0"
                        >
                          {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => window.open(link.share_url, '_blank')}
                          className="flex-shrink-0"
                        >
                          <ExternalLink className="w-4 h-4" />
                        </Button>
                      </div>

                      {/* WhatsApp Share Button */}
                      <Button
                        onClick={() => handleWhatsAppShare(link.share_url)}
                        className="w-full rounded-lg bg-[#25D366] hover:bg-[#20BD5A] text-white h-9 text-sm font-medium"
                      >
                        <WhatsAppIcon className="w-4 h-4 mr-2" />
                        Share on WhatsApp
                      </Button>

                      <div className="flex items-center justify-between text-xs text-muted-foreground">
                        <div className="flex items-center gap-3">
                          <span className="flex items-center gap-1">
                            <Eye className="w-3 h-3" />
                            {link.view_count} views
                          </span>
                          {link.expires_at && (
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              Expires {new Date(link.expires_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRevokeLink(link.id)}
                          className="text-red-500 hover:text-red-600 h-6 px-2"
                        >
                          <Trash2 className="w-3 h-3" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Create New Link Form */}
              {(showCreateNew || existingLinks.length === 0) && (
                <div className="space-y-4">
                  {existingLinks.length > 0 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowCreateNew(false)}
                      className="mb-2"
                    >
                      ← Back to existing links
                    </Button>
                  )}
                  
                  <div className="bg-cream-subtle dark:bg-muted rounded-xl p-4 space-y-4">
                    <p className="font-medium text-sm">Create New Share Link</p>
                    
                    {/* Expiration */}
                    <div>
                      <Label className="text-sm">Link Expiration</Label>
                      <select
                        value={expiresInDays}
                        onChange={(e) => setExpiresInDays(parseInt(e.target.value))}
                        className="w-full mt-1 p-2 rounded-lg border border-border/60 bg-white dark:bg-card text-sm"
                      >
                        <option value={0}>Never expires</option>
                        <option value={1}>1 day</option>
                        <option value={7}>7 days</option>
                        <option value={30}>30 days</option>
                        <option value={90}>90 days</option>
                      </select>
                    </div>

                    {/* Options */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <Label className="text-sm">Allow printing</Label>
                        <Switch
                          checked={allowPrint}
                          onCheckedChange={setAllowPrint}
                        />
                      </div>
                      <div className="flex items-center justify-between">
                        <Label className="text-sm">Show author name</Label>
                        <Switch
                          checked={showAuthor}
                          onCheckedChange={setShowAuthor}
                        />
                      </div>
                    </div>
                  </div>

                  <Button
                    onClick={handleCreateLink}
                    disabled={loading}
                    className="w-full rounded-xl bg-mise hover:bg-mise-dark"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        Creating...
                      </>
                    ) : (
                      <>
                        <Link className="w-4 h-4 mr-2" />
                        Create Share Link
                      </>
                    )}
                  </Button>
                </div>
              )}

              {/* Info */}
              <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-xl p-3 text-sm">
                <p className="text-blue-800 dark:text-blue-200">
                  <strong>Public link:</strong> Anyone with this link can view the recipe without logging in.
                </p>
              </div>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
};

export default ShareRecipeModal;
