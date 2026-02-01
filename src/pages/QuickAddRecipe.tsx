import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { aiApi, recipeApi, importApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { 
  Sparkles, 
  Link as LinkIcon, 
  FileText, 
  Upload,
  Loader2, 
  Check,
  ArrowLeft,
  ClipboardPaste,
  FileJson
} from 'lucide-react';
import { toast } from 'sonner';

export const QuickAddRecipe = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('paste');
  
  // Paste text state
  const [pasteText, setPasteText] = useState('');
  const [pasteLoading, setPasteLoading] = useState(false);
  
  // URL state
  const [url, setUrl] = useState('');
  const [urlLoading, setUrlLoading] = useState(false);
  
  // Import state
  const [importPlatform, setImportPlatform] = useState('paprika');
  const [importData, setImportData] = useState('');
  const [importLoading, setImportLoading] = useState(false);
  
  // Result state
  const [extractedRecipe, setExtractedRecipe] = useState(null);
  const [saving, setSaving] = useState(false);

  const handlePasteSubmit = async () => {
    if (!pasteText.trim()) {
      toast.error('Please paste a recipe');
      return;
    }
    
    setPasteLoading(true);
    try {
      const res = await aiApi.importText(pasteText);
      setExtractedRecipe(res.data);
      toast.success('Recipe parsed successfully!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to parse recipe');
    } finally {
      setPasteLoading(false);
    }
  };

  const handleUrlSubmit = async () => {
    if (!url.trim()) {
      toast.error('Please enter a URL');
      return;
    }
    
    setUrlLoading(true);
    try {
      const res = await aiApi.importUrl(url);
      setExtractedRecipe(res.data);
      toast.success('Recipe extracted successfully!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to extract recipe');
    } finally {
      setUrlLoading(false);
    }
  };

  const handleImportSubmit = async () => {
    if (!importData.trim()) {
      toast.error('Please paste your export data');
      return;
    }
    
    setImportLoading(true);
    try {
      const res = await importApi.fromPlatform(importPlatform, importData);
      toast.success(res.data.message);
      navigate('/recipes');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Import failed');
    } finally {
      setImportLoading(false);
    }
  };

  const handleSaveRecipe = async () => {
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
        image_url: extractedRecipe.image_url || '',
      };
      
      const res = await recipeApi.create(recipeData);
      toast.success('Recipe saved!');
      navigate(`/recipes/${res.data.id}`);
    } catch (error) {
      toast.error('Failed to save recipe');
    } finally {
      setSaving(false);
    }
  };

  const handlePasteFromClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText();
      setPasteText(text);
      toast.success('Pasted from clipboard');
    } catch (error) {
      toast.error('Could not access clipboard');
    }
  };

  return (
    <Layout>
      <div className="max-w-3xl mx-auto" data-testid="quick-add-recipe">
        <Link 
          to="/recipes" 
          className="inline-flex items-center text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Recipes
        </Link>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-2xl border border-border/60 p-6 shadow-card"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-mise-light flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-mise" />
            </div>
            <div>
              <h1 className="font-heading text-2xl font-bold">Quick Add Recipe</h1>
              <p className="text-muted-foreground text-sm">Paste, import, or enter a URL</p>
            </div>
          </div>

          {!extractedRecipe ? (
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="grid grid-cols-3 mb-6">
                <TabsTrigger value="paste" className="flex items-center gap-2">
                  <ClipboardPaste className="w-4 h-4" />
                  Paste
                </TabsTrigger>
                <TabsTrigger value="url" className="flex items-center gap-2">
                  <LinkIcon className="w-4 h-4" />
                  URL
                </TabsTrigger>
                <TabsTrigger value="import" className="flex items-center gap-2">
                  <Upload className="w-4 h-4" />
                  Import
                </TabsTrigger>
              </TabsList>

              {/* Paste Tab */}
              <TabsContent value="paste" className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label>Paste Recipe Text</Label>
                    <Button 
                      variant="ghost" 
                      size="sm"
                      onClick={handlePasteFromClipboard}
                      className="text-xs"
                    >
                      <ClipboardPaste className="w-3 h-3 mr-1" />
                      Paste from Clipboard
                    </Button>
                  </div>
                  <Textarea
                    value={pasteText}
                    onChange={(e) => setPasteText(e.target.value)}
                    placeholder="Paste your recipe here... Include ingredients, instructions, times, etc. AI will parse it automatically."
                    className="min-h-[200px] rounded-xl"
                    data-testid="paste-recipe-input"
                  />
                </div>
                <Button
                  onClick={handlePasteSubmit}
                  disabled={pasteLoading || !pasteText.trim()}
                  className="w-full rounded-full bg-mise hover:bg-mise-dark h-12"
                  data-testid="parse-recipe-btn"
                >
                  {pasteLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5 mr-2" />
                      Parse Recipe with AI
                    </>
                  )}
                </Button>
              </TabsContent>

              {/* URL Tab */}
              <TabsContent value="url" className="space-y-4">
                <div>
                  <Label className="mb-2 block">Recipe URL</Label>
                  <Input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://example.com/recipe..."
                    className="rounded-xl"
                    data-testid="url-input"
                  />
                </div>
                <Button
                  onClick={handleUrlSubmit}
                  disabled={urlLoading || !url.trim()}
                  className="w-full rounded-full bg-mise hover:bg-mise-dark h-12"
                  data-testid="extract-url-btn"
                >
                  {urlLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <LinkIcon className="w-5 h-5 mr-2" />
                      Extract from URL
                    </>
                  )}
                </Button>
              </TabsContent>

              {/* Import Tab */}
              <TabsContent value="import" className="space-y-4">
                <div>
                  <Label className="mb-2 block">Import From</Label>
                  <div className="grid grid-cols-3 gap-2">
                    {[
                      { id: 'paprika', label: 'Paprika' },
                      { id: 'cookmate', label: 'Cookmate' },
                      { id: 'json', label: 'JSON' },
                    ].map((platform) => (
                      <button
                        key={platform.id}
                        onClick={() => setImportPlatform(platform.id)}
                        className={`p-3 rounded-xl border text-sm font-medium transition-all ${
                          importPlatform === platform.id
                            ? 'border-mise bg-mise-light text-mise'
                            : 'border-border/60 hover:border-mise'
                        }`}
                      >
                        {platform.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <Label className="mb-2 block">Export Data (JSON)</Label>
                  <Textarea
                    value={importData}
                    onChange={(e) => setImportData(e.target.value)}
                    placeholder="Paste your exported recipes JSON here..."
                    className="min-h-[150px] rounded-xl font-mono text-sm"
                    data-testid="import-data-input"
                  />
                </div>
                <Button
                  onClick={handleImportSubmit}
                  disabled={importLoading || !importData.trim()}
                  className="w-full rounded-full bg-mise hover:bg-mise-dark h-12"
                  data-testid="import-btn"
                >
                  {importLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <Upload className="w-5 h-5 mr-2" />
                      Import Recipes
                    </>
                  )}
                </Button>
                <p className="text-xs text-muted-foreground text-center">
                  Export your recipes from Paprika, Cookmate, or other apps as JSON
                </p>
              </TabsContent>
            </Tabs>
          ) : (
            /* Recipe Preview */
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-6"
            >
              <div className="flex items-center justify-between">
                <h2 className="font-heading text-lg font-semibold">Recipe Preview</h2>
                <div className="flex items-center gap-2 text-sm text-mise">
                  <Check className="w-4 h-4" />
                  Ready to save
                </div>
              </div>

              <div className="p-4 bg-cream-subtle rounded-xl space-y-4">
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">Title</p>
                  <p className="font-heading font-semibold text-lg">{extractedRecipe.title}</p>
                </div>

                {extractedRecipe.description && (
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">Description</p>
                    <p className="text-sm">{extractedRecipe.description}</p>
                  </div>
                )}

                <div className="grid grid-cols-4 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground">Category</p>
                    <p className="font-medium text-sm">{extractedRecipe.category || 'Other'}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Prep</p>
                    <p className="font-medium text-sm">{extractedRecipe.prep_time || 0} min</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Cook</p>
                    <p className="font-medium text-sm">{extractedRecipe.cook_time || 0} min</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Servings</p>
                    <p className="font-medium text-sm">{extractedRecipe.servings || 4}</p>
                  </div>
                </div>

                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
                    Ingredients ({extractedRecipe.ingredients?.length || 0})
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {extractedRecipe.ingredients?.slice(0, 6).map((ing, idx) => (
                      <span key={idx} className="px-2 py-1 bg-white rounded-lg text-xs">
                        {ing.amount} {ing.unit} {ing.name}
                      </span>
                    ))}
                    {extractedRecipe.ingredients?.length > 6 && (
                      <span className="px-2 py-1 bg-mise-light text-mise rounded-lg text-xs">
                        +{extractedRecipe.ingredients.length - 6} more
                      </span>
                    )}
                  </div>
                </div>

                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">
                    Instructions: {extractedRecipe.instructions?.length || 0} steps
                  </p>
                </div>
              </div>

              <div className="flex gap-3">
                <Button
                  onClick={handleSaveRecipe}
                  disabled={saving}
                  className="flex-1 rounded-full bg-mise hover:bg-mise-dark h-12"
                  data-testid="save-recipe-btn"
                >
                  {saving ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <Check className="w-5 h-5 mr-2" />
                      Save Recipe
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setExtractedRecipe(null)}
                  className="rounded-full"
                >
                  Try Again
                </Button>
              </div>
            </motion.div>
          )}
        </motion.div>
      </div>
    </Layout>
  );
};
