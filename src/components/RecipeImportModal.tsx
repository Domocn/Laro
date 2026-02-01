import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
  Link,
  FileText,
  Loader2,
  Check,
  AlertCircle,
  ExternalLink,
  ChefHat,
  X,
  Sparkles,
  Globe
} from 'lucide-react';
import { toast } from 'sonner';
import { importApi } from '../lib/api';

const SUPPORTED_SITES = [
  { domain: 'allrecipes.com', name: 'AllRecipes', logo: '🍳' },
  { domain: 'foodnetwork.com', name: 'Food Network', logo: '📺' },
  { domain: 'bbcgoodfood.com', name: 'BBC Good Food', logo: '🇬🇧' },
  { domain: 'epicurious.com', name: 'Epicurious', logo: '🍽️' },
  { domain: 'tasty.co', name: 'Tasty', logo: '😋' },
  { domain: 'bonappetit.com', name: 'Bon Appétit', logo: '👨‍🍳' },
  { domain: 'seriouseats.com', name: 'Serious Eats', logo: '🔬' },
  { domain: 'budgetbytes.com', name: 'Budget Bytes', logo: '💰' },
  { domain: 'simplyrecipes.com', name: 'Simply Recipes', logo: '🥗' },
  { domain: 'minimalistbaker.com', name: 'Minimalist Baker', logo: '🌱' },
];

export const RecipeImportModal = ({ isOpen, onClose, onSuccess }) => {
  const [mode, setMode] = useState('url'); // 'url' or 'text'
  const [url, setUrl] = useState('');
  const [text, setText] = useState('');
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [platforms, setPlatforms] = useState([]);

  useEffect(() => {
    if (isOpen) {
      loadPlatforms();
    }
  }, [isOpen]);

  const loadPlatforms = async () => {
    try {
      const res = await importApi.getPlatforms();
      setPlatforms(res.data.platforms || []);
    } catch (error) {
      console.log('Using default platforms');
    }
  };

  const handleImportUrl = async () => {
    if (!url.trim()) {
      toast.error('Please enter a URL');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const res = await importApi.importFromUrl(url);
      setResult({
        success: true,
        recipe: res.data.recipe,
        platform: res.data.platform
      });
      toast.success('Recipe imported successfully!');
      
      // Notify parent
      if (onSuccess) {
        onSuccess(res.data.recipe);
      }
    } catch (error) {
      setResult({
        success: false,
        error: error.response?.data?.detail || 'Failed to import recipe'
      });
      toast.error('Import failed');
    } finally {
      setLoading(false);
    }
  };

  const handleImportText = async () => {
    if (!text.trim()) {
      toast.error('Please paste recipe text');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const res = await importApi.importFromText(text, title);
      setResult({
        success: true,
        recipe: res.data.recipe,
        platform: 'Text'
      });
      toast.success('Recipe parsed successfully!');
      
      if (onSuccess) {
        onSuccess(res.data.recipe);
      }
    } catch (error) {
      setResult({
        success: false,
        error: error.response?.data?.detail || 'Failed to parse recipe'
      });
      toast.error('Parse failed');
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setUrl('');
    setText('');
    setTitle('');
    setResult(null);
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white dark:bg-card rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col"
        data-testid="recipe-import-modal"
      >
        {/* Header */}
        <div className="p-4 border-b border-border/60 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-mise/10 rounded-xl flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-mise" />
            </div>
            <div>
              <h2 className="font-heading font-semibold text-lg">Import Recipe</h2>
              <p className="text-sm text-muted-foreground">From URL or paste text</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={handleClose}>
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Mode Toggle */}
          <div className="flex gap-2 p-1 bg-cream-subtle dark:bg-muted rounded-xl">
            <button
              onClick={() => { setMode('url'); setResult(null); }}
              className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg font-medium text-sm transition-all ${
                mode === 'url'
                  ? 'bg-white dark:bg-card shadow-sm text-mise'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Link className="w-4 h-4" />
              Import from URL
            </button>
            <button
              onClick={() => { setMode('text'); setResult(null); }}
              className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-lg font-medium text-sm transition-all ${
                mode === 'text'
                  ? 'bg-white dark:bg-card shadow-sm text-mise'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <FileText className="w-4 h-4" />
              Paste Text
            </button>
          </div>

          {/* URL Import */}
          {mode === 'url' && !result && (
            <div className="space-y-4">
              <div>
                <Label>Recipe URL</Label>
                <div className="relative mt-1">
                  <Globe className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    type="url"
                    placeholder="https://allrecipes.com/recipe/..."
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    className="pl-10 rounded-xl"
                    data-testid="import-url-input"
                  />
                </div>
              </div>

              {/* Supported Sites */}
              <div>
                <p className="text-sm text-muted-foreground mb-2">Supported sites include:</p>
                <div className="flex flex-wrap gap-2">
                  {SUPPORTED_SITES.map((site) => (
                    <span
                      key={site.domain}
                      className="inline-flex items-center gap-1 px-2 py-1 bg-cream-subtle dark:bg-muted rounded-full text-xs"
                    >
                      <span>{site.logo}</span>
                      <span>{site.name}</span>
                    </span>
                  ))}
                  <span className="inline-flex items-center gap-1 px-2 py-1 bg-mise/10 text-mise rounded-full text-xs font-medium">
                    + Any site with Recipe Schema
                  </span>
                </div>
              </div>

              <Button
                onClick={handleImportUrl}
                disabled={loading || !url.trim()}
                className="w-full rounded-xl bg-mise hover:bg-mise-dark"
                data-testid="import-url-button"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Importing...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Import Recipe
                  </>
                )}
              </Button>
            </div>
          )}

          {/* Text Import */}
          {mode === 'text' && !result && (
            <div className="space-y-4">
              <div>
                <Label>Recipe Title (optional)</Label>
                <Input
                  placeholder="My Grandma's Cookies"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="mt-1 rounded-xl"
                />
              </div>

              <div>
                <Label>Recipe Text</Label>
                <Textarea
                  placeholder="Paste your recipe here...

Example:
2 cups flour
1 cup sugar
2 eggs
1 tsp vanilla

Mix dry ingredients. Add eggs and vanilla. Bake at 350°F for 25 minutes."
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  className="mt-1 rounded-xl min-h-[200px]"
                  data-testid="import-text-input"
                />
              </div>

              <div className="bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-xl p-3 text-sm">
                <p className="text-blue-800 dark:text-blue-200">
                  <strong>AI Parsing:</strong> Our AI will extract ingredients, instructions, and timing from your text.
                </p>
              </div>

              <Button
                onClick={handleImportText}
                disabled={loading || !text.trim()}
                className="w-full rounded-xl bg-mise hover:bg-mise-dark"
                data-testid="import-text-button"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Parsing with AI...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Parse Recipe
                  </>
                )}
              </Button>
            </div>
          )}

          {/* Result */}
          {result && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              {result.success ? (
                <div className="text-center py-6">
                  <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto mb-4">
                    <Check className="w-8 h-8 text-green-600 dark:text-green-400" />
                  </div>
                  <h3 className="font-heading font-semibold text-lg mb-2">Recipe Imported!</h3>
                  <p className="text-muted-foreground mb-4">
                    <strong>{result.recipe.title}</strong> has been added to your collection.
                  </p>
                  
                  {result.recipe.image_url && (
                    <img
                      src={result.recipe.image_url}
                      alt={result.recipe.title}
                      className="w-full h-48 object-cover rounded-xl mb-4"
                    />
                  )}

                  <div className="flex gap-2 justify-center">
                    <Button
                      variant="outline"
                      onClick={resetForm}
                      className="rounded-full"
                    >
                      Import Another
                    </Button>
                    <Button
                      onClick={handleClose}
                      className="rounded-full bg-mise hover:bg-mise-dark"
                    >
                      Done
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="text-center py-6">
                  <div className="w-16 h-16 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center mx-auto mb-4">
                    <AlertCircle className="w-8 h-8 text-red-600 dark:text-red-400" />
                  </div>
                  <h3 className="font-heading font-semibold text-lg mb-2">Import Failed</h3>
                  <p className="text-muted-foreground mb-4">{result.error}</p>
                  
                  <div className="bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-xl p-3 text-sm text-left mb-4">
                    <p className="text-amber-800 dark:text-amber-200">
                      <strong>Tips:</strong>
                    </p>
                    <ul className="list-disc list-inside text-amber-700 dark:text-amber-300 mt-1">
                      <li>Make sure the URL is a direct recipe page</li>
                      <li>Some sites require login to view recipes</li>
                      <li>Try the &quot;Paste Text&quot; option instead</li>
                    </ul>
                  </div>

                  <Button
                    onClick={resetForm}
                    className="rounded-full bg-mise hover:bg-mise-dark"
                  >
                    Try Again
                  </Button>
                </div>
              )}
            </motion.div>
          )}
        </div>
      </motion.div>
    </div>
  );
};

export default RecipeImportModal;
