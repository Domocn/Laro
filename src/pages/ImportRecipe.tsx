import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { aiApi, recipeApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { 
  Link as LinkIcon, 
  ArrowLeft, 
  Loader2, 
  Sparkles,
  Check,
  Edit
} from 'lucide-react';
import { toast } from 'sonner';

export const ImportRecipe = () => {
  const navigate = useNavigate();
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [extractedRecipe, setExtractedRecipe] = useState(null);
  const [saving, setSaving] = useState(false);

  const handleExtract = async (e) => {
    e.preventDefault();
    
    if (!url.trim()) {
      toast.error('Please enter a recipe URL');
      return;
    }

    setLoading(true);
    try {
      const res = await aiApi.importUrl(url);
      setExtractedRecipe(res.data);
      toast.success('Recipe extracted successfully!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to extract recipe');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!extractedRecipe) return;

    setSaving(true);
    try {
      const recipeData = {
        title: extractedRecipe.title,
        description: extractedRecipe.description || '',
        category: extractedRecipe.category || 'Other',
        prep_time: extractedRecipe.prep_time || 0,
        cook_time: extractedRecipe.cook_time || 0,
        servings: extractedRecipe.servings || 4,
        tags: extractedRecipe.tags || [],
        ingredients: extractedRecipe.ingredients || [],
        instructions: extractedRecipe.instructions || [],
        image_url: '',
      };

      const res = await recipeApi.create(recipeData);
      toast.success('Recipe saved to your collection!');
      navigate(`/recipes/${res.data.id}`);
    } catch (error) {
      toast.error('Failed to save recipe');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-3xl mx-auto" data-testid="import-recipe">
        {/* Back Button */}
        <button 
          onClick={() => navigate(-1)}
          className="inline-flex items-center text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </button>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-2xl border border-border/60 p-6 md:p-8 shadow-card"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-mise-light flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-mise" />
            </div>
            <div>
              <h1 className="font-heading text-2xl font-bold">Import Recipe from URL</h1>
              <p className="text-muted-foreground text-sm">Paste a recipe URL and AI will extract it for you</p>
            </div>
          </div>

          {/* URL Input */}
          <form onSubmit={handleExtract} className="mb-8">
            <Label htmlFor="url" className="mb-2 block">Recipe URL</Label>
            <div className="flex gap-3">
              <div className="relative flex-1">
                <LinkIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="url"
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com/recipe..."
                  className="pl-10 rounded-xl"
                  disabled={loading}
                  data-testid="import-url-input"
                />
              </div>
              <Button 
                type="submit" 
                className="rounded-full bg-mise hover:bg-mise-dark px-6"
                disabled={loading}
                data-testid="extract-btn"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Extract
                  </>
                )}
              </Button>
            </div>
          </form>

          {/* Extracted Recipe Preview */}
          {extractedRecipe && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="border border-border/60 rounded-xl p-6 bg-cream-subtle"
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-heading text-lg font-semibold">Extracted Recipe</h2>
                <div className="flex items-center gap-2 text-sm text-mise">
                  <Check className="w-4 h-4" />
                  Ready to save
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Title</p>
                  <p className="font-medium text-lg">{extractedRecipe.title}</p>
                </div>

                {extractedRecipe.description && (
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Description</p>
                    <p className="text-sm">{extractedRecipe.description}</p>
                  </div>
                )}

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Category</p>
                    <p className="font-medium">{extractedRecipe.category || 'Other'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Prep Time</p>
                    <p className="font-medium">{extractedRecipe.prep_time || 0} min</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Cook Time</p>
                    <p className="font-medium">{extractedRecipe.cook_time || 0} min</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Servings</p>
                    <p className="font-medium">{extractedRecipe.servings || 4}</p>
                  </div>
                </div>

                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">Ingredients ({extractedRecipe.ingredients?.length || 0})</p>
                  <div className="flex flex-wrap gap-2">
                    {extractedRecipe.ingredients?.slice(0, 5).map((ing, idx) => (
                      <span key={`${ing.name}-${idx}`} className="px-2 py-1 bg-white rounded-lg text-sm">
                        {ing.amount} {ing.unit} {ing.name}
                      </span>
                    ))}
                    {extractedRecipe.ingredients?.length > 5 && (
                      <span className="px-2 py-1 bg-mise-light text-mise rounded-lg text-sm">
                        +{extractedRecipe.ingredients.length - 5} more
                      </span>
                    )}
                  </div>
                </div>

                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Instructions</p>
                  <p className="text-sm">{extractedRecipe.instructions?.length || 0} steps</p>
                </div>

                {extractedRecipe.tags && extractedRecipe.tags.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {extractedRecipe.tags.map((tag, idx) => (
                      <span key={`${tag}-${idx}`} className="px-2 py-1 bg-mise-light text-mise rounded-full text-xs">
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex gap-3 mt-6 pt-6 border-t border-border/60">
                <Button
                  onClick={handleSave}
                  className="rounded-full bg-mise hover:bg-mise-dark"
                  disabled={saving}
                  data-testid="save-imported-btn"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Check className="w-4 h-4 mr-2" />
                  )}
                  Save to My Recipes
                </Button>
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => setExtractedRecipe(null)}
                >
                  Try Another URL
                </Button>
              </div>
            </motion.div>
          )}

          {/* Tips */}
          {!extractedRecipe && (
            <div className="text-sm text-muted-foreground bg-cream-subtle rounded-xl p-4">
              <p className="font-medium mb-2">Tips for best results:</p>
              <ul className="list-disc list-inside space-y-1">
                <li>Use direct recipe page URLs (not search results)</li>
                <li>Most major recipe sites are supported</li>
                <li>You can edit the recipe after importing</li>
              </ul>
            </div>
          )}
        </motion.div>
      </div>
    </Layout>
  );
};
