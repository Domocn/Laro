import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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
  Globe,
  FileType
} from 'lucide-react';
import { toast } from 'sonner';
import { importApi, aiApi, recipeApi } from '../lib/api';
import { getAiQuotaErrorMessage } from '../lib/aiQuota';

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
  const navigate = useNavigate();
  const [mode, setMode] = useState('url'); // 'url' | 'text' | 'pdf'
  const [url, setUrl] = useState('');
  const [text, setText] = useState('');
  const [title, setTitle] = useState('');
  const [pdfFile, setPdfFile] = useState(null);
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
    // Same path as Android + /recipes/import: AI extract → review → save
    const target = `/recipes/import?url=${encodeURIComponent(url.trim())}`;
    onClose?.();
    navigate(target);
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
      toast.error('Parse failed (E-RI002)');
    } finally {
      setLoading(false);
    }
  };

  const handleImportPdf = async () => {
    if (!pdfFile) {
      toast.error('Please choose a PDF');
      return;
    }
    if (pdfFile.size > 12_000_000) {
      toast.error('PDF too large (max 12MB)');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append('file', pdfFile);
      formData.append('apply', 'true');
      formData.append('context', 'recipes');
      const extract = await aiApi.importPdf(formData);
      const recipes = extract.data.recipes || (extract.data.recipe ? [extract.data.recipe] : []);
      const n = extract.data.recipe_count || recipes.length;
      const skipped = extract.data.skipped?.length || 0;
      if (!n) {
        setResult({
          success: false,
          error: extract.data.message || 'No new recipes found',
        });
        toast.error(extract.data.message || 'No new recipes found');
        return;
      }
      setResult({
        success: true,
        recipe: recipes[0] || { title: `${n} recipes` },
        recipeCount: n,
        platform: 'PDF',
        skipped,
      });
      toast.success(
        n === 1
          ? 'Recipe imported for review'
          : `Separated ${n} recipes from one PDF — each marked for review` +
            (skipped ? ` (${skipped} duplicates skipped)` : '')
      );
      if (onSuccess) onSuccess(recipes[0]);
    } catch (error) {
      setResult({
        success: false,
        error:
          error.response?.data?.detail ||
          'Failed to import recipe PDF',
      });
      toast.error(
        getAiQuotaErrorMessage(error, 'PDF import failed (E-RI003)')
      );
    } finally {
      setLoading(false);
    }
  };

  const resetForm = () => {
    setUrl('');
    setText('');
    setTitle('');
    setPdfFile(null);
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
            <div className="w-10 h-10 bg-laro/10 rounded-xl flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-laro" />
            </div>
            <div>
              <h2 className="font-heading font-semibold text-lg">Import Recipe</h2>
              <p className="text-sm text-muted-foreground">
                Sites, meal packs, or a PDF (recipes or weekly meal plans)
              </p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={handleClose}>
            <X className="w-5 h-5" />
          </Button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Mode Toggle */}
          <div className="flex gap-1 p-1 bg-cream-subtle dark:bg-muted rounded-xl">
            <button
              onClick={() => { setMode('url'); setResult(null); }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg font-medium text-sm transition-all ${
                mode === 'url'
                  ? 'bg-white dark:bg-card shadow-sm text-laro'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <Link className="w-4 h-4" />
              URL
            </button>
            <button
              onClick={() => { setMode('text'); setResult(null); }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg font-medium text-sm transition-all ${
                mode === 'text'
                  ? 'bg-white dark:bg-card shadow-sm text-laro'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              <FileText className="w-4 h-4" />
              Text
            </button>
            <button
              onClick={() => { setMode('pdf'); setResult(null); }}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg font-medium text-sm transition-all ${
                mode === 'pdf'
                  ? 'bg-white dark:bg-card shadow-sm text-laro'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
              data-testid="import-mode-pdf"
            >
              <FileType className="w-4 h-4" />
              PDF
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
                    placeholder="https://huel.com/... or allrecipes.com/recipe/..."
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
                  <span className="inline-flex items-center gap-1 px-2 py-1 bg-laro/10 text-laro rounded-full text-xs font-medium">
                    + Recipe Schema
                  </span>
                  <span className="inline-flex items-center gap-1 px-2 py-1 bg-laro/10 text-laro rounded-full text-xs font-medium">
                    + Huel / RTD meal packs
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  RTD shakes and pouches are saved as Recipes under Meal Pack.
                </p>
              </div>

              <Button
                onClick={handleImportUrl}
                disabled={loading || !url.trim()}
                className="w-full rounded-xl bg-laro hover:bg-laro-dark"
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
                  className="mt-1 rounded-xl min-h-[120px] sm:min-h-[200px]"
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
                className="w-full rounded-xl bg-laro hover:bg-laro-dark"
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

          {/* PDF Import */}
          {mode === 'pdf' && !result && (
            <div className="space-y-4">
              <div>
                <Label>Recipe or meal-plan PDF</Label>
                <Input
                  type="file"
                  accept="application/pdf,.pdf"
                  className="mt-1 rounded-xl"
                  onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                  data-testid="import-pdf-input"
                />
                {pdfFile && (
                  <p className="text-xs text-muted-foreground mt-1">{pdfFile.name}</p>
                )}
                <p className="text-xs text-muted-foreground mt-2">
                  Text-based PDFs (max 12MB). Weekly plans become separate recipes; use Meal Plan → PDF to also schedule the week.
                </p>
              </div>
              <Button
                onClick={handleImportPdf}
                disabled={loading || !pdfFile}
                className="w-full rounded-xl bg-laro hover:bg-laro-dark"
                data-testid="import-pdf-button"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Extracting PDF...
                  </>
                ) : (
                  <>
                    <FileType className="w-4 h-4 mr-2" />
                    Import PDF
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
                  <h3 className="font-heading font-semibold text-lg mb-2">
                    {result.recipeCount > 1 ? 'Recipes imported for review' : 'Recipe Imported!'}
                  </h3>
                  <p className="text-muted-foreground mb-4">
                    {result.recipeCount > 1 ? (
                      <>
                        Separated <strong>{result.recipeCount}</strong> recipes from one PDF
                        {result.skipped ? ` (${result.skipped} duplicates skipped)` : ''}.
                        Each is marked for review in Recipes.
                      </>
                    ) : (
                      <>
                        <strong>{result.recipe.title}</strong> has been added for review.
                      </>
                    )}
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
                      className="rounded-full bg-laro hover:bg-laro-dark"
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
                      <li>Use a direct recipe page or a product page (Huel RTD / shake / pouch)</li>
                      <li>Some sites require login to view recipes</li>
                      <li>Try the &quot;Paste Text&quot; option instead</li>
                    </ul>
                  </div>

                  <Button
                    onClick={resetForm}
                    className="rounded-full bg-laro hover:bg-laro-dark"
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
