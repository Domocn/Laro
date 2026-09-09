import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { aiApi, recipeApi, importApi, cookbooksApi } from '../lib/api';
import { getAiQuotaErrorMessage } from '../lib/aiQuota';
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
  FileJson,
  Image as ImageIcon,
  FileType
} from 'lucide-react';
import { toast } from 'sonner';
import { useLanguage } from '../context/LanguageContext';
import { SocialImportFallback } from '../components/SocialImportFallback';
import { VetoReplacementBanner } from '../components/VetoReplacementBanner';

export const QuickAddRecipe = () => {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('paste');
  
  // Paste text state
  const [pasteText, setPasteText] = useState('');
  const [pasteLoading, setPasteLoading] = useState(false);
  
  // URL state
  const [url, setUrl] = useState('');
  const [urlLoading, setUrlLoading] = useState(false);
  const [urlFailed, setUrlFailed] = useState(false);
  
  // Import state
  const [importPlatform, setImportPlatform] = useState('paprika');
  const [importData, setImportData] = useState('');
  const [importLoading, setImportLoading] = useState(false);
  const [imageFiles, setImageFiles] = useState([]);
  const [imageLoading, setImageLoading] = useState(false);
  const [pdfFile, setPdfFile] = useState(null);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfRecipes, setPdfRecipes] = useState(null); // multi-recipe preview from one PDF
  const [pdfSkipped, setPdfSkipped] = useState([]);
  const [cookbooks, setCookbooks] = useState([]);
  const [selectedCookbookId, setSelectedCookbookId] = useState('');
  const [cookbookPage, setCookbookPage] = useState('');
  
  // Result state
  const [extractedRecipe, setExtractedRecipe] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await cookbooksApi.getAll();
        if (!cancelled) setCookbooks(res.data || []);
      } catch {
        // Cookbooks optional for import
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const cookbookAttachFields = (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div>
        <Label className="mb-2 block">{t('attachToCookbookOptional')}</Label>
        <select
          value={selectedCookbookId}
          onChange={(e) => setSelectedCookbookId(e.target.value)}
          className="w-full h-10 rounded-xl border border-border/60 bg-background px-3 text-sm"
          data-testid="attach-cookbook-select"
        >
          <option value="">{t('noCookbook')}</option>
          {cookbooks.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title}
              {c.author ? ` — ${c.author}` : ''}
            </option>
          ))}
        </select>
      </div>
      <div>
        <Label className="mb-2 block">{t('cookbookPageOptional')}</Label>
        <Input
          type="number"
          min={1}
          value={cookbookPage}
          onChange={(e) => setCookbookPage(e.target.value)}
          placeholder="e.g. 42"
          className="rounded-xl"
          data-testid="cookbook-page-input"
        />
      </div>
    </div>
  );

  const handlePasteSubmit = async () => {
    if (!pasteText.trim()) {
      toast.error(t('toastPasteRecipe'));
      return;
    }
    
    setPasteLoading(true);
    try {
      const res = await aiApi.importText(pasteText);
      setExtractedRecipe(res.data);
      toast.success(t('toastRecipeParsed'));
    } catch (error) {
      toast.error(
        getAiQuotaErrorMessage(
          error,
          t('toastParseRecipeFailed')
        )
      );
    } finally {
      setPasteLoading(false);
    }
  };

  const handleUrlSubmit = async () => {
    if (!url.trim()) {
      toast.error(t('toastEnterUrl'));
      return;
    }
    
    setUrlLoading(true);
    setUrlFailed(false);
    try {
      const res = await aiApi.importUrl(url);
      setExtractedRecipe(res.data.recipe || res.data);
      toast.success(t('toastRecipeExtractedSuccess'));
    } catch (error) {
      setUrlFailed(true);
      toast.error(
        getAiQuotaErrorMessage(
          error,
          t('toastExtractUrlFailed')
        )
      );
    } finally {
      setUrlLoading(false);
    }
  };

  const handleImportSubmit = async () => {
    if (!importData.trim()) {
      toast.error(t('toastPasteExportData'));
      return;
    }
    
    setImportLoading(true);
    try {
      const res = await importApi.fromPlatform(importPlatform, importData);
      toast.success(res.data.message);
      navigate('/recipes');
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastImportRecipesFailed'));
    } finally {
      setImportLoading(false);
    }
  };


  const fileToDataUrl = (file) => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });

  const handleImageSubmit = async () => {
    if (!imageFiles.length) {
      toast.error(t('toastAddPhoto'));
      return;
    }
    setImageLoading(true);
    try {
      const images = await Promise.all(imageFiles.slice(0, 5).map(fileToDataUrl));
      const pageNum = cookbookPage ? parseInt(cookbookPage, 10) : null;
      const res = await aiApi.extractFromImages(
        images,
        selectedCookbookId || null,
        Number.isFinite(pageNum) ? pageNum : null
      );
      setExtractedRecipe(res.data.recipe || res.data);
      toast.success(
        t('toastRecipeExtractedPhoto') +
          (res.data.images_processed > 1
            ? ` (${res.data.images_processed} ${t('pagesLabel')})`
            : '')
      );
    } catch (error) {
      toast.error(
        getAiQuotaErrorMessage(
          error,
          t('toastReadPhotoFailed')
        )
      );
    } finally {
      setImageLoading(false);
    }
  };

  const handlePdfSubmit = async () => {
    if (!pdfFile) {
      toast.error(t('toastChoosePdf'));
      return;
    }
    if (pdfFile.size > 12_000_000) {
      toast.error(t('toastPdfTooLarge'));
      return;
    }
    setPdfLoading(true);
    setPdfRecipes(null);
    setPdfSkipped([]);
    try {
      const formData = new FormData();
      formData.append('file', pdfFile);
      formData.append('apply', 'false');
      formData.append('context', 'recipes');
      if (selectedCookbookId) formData.append('cookbook_id', selectedCookbookId);
      const res = await aiApi.importPdf(formData);
      const list = res.data.recipes?.length
        ? res.data.recipes
        : res.data.recipe
          ? [res.data.recipe]
          : [];
      setPdfSkipped(res.data.skipped || []);
      if (!list.length) {
        toast.error(res.data.message || t('toastNoRecipesInPdf'));
        return;
      }
      if (list.length === 1) {
        setExtractedRecipe(list[0]);
        setPdfRecipes(null);
        toast.success(
          res.data.source === 'scanned_pdf'
            ? t('toastRecipeExtractedScannedPdf')
            : t('toastRecipeExtractedPdfReview')
        );
      } else {
        setExtractedRecipe(null);
        setPdfRecipes(list);
        toast.success(
          t('toastSeparatedRecipesReviewEach', { count: list.length })
        );
      }
    } catch (error) {
      toast.error(
        getAiQuotaErrorMessage(
          error,
          error.response?.data?.detail || t('toastReadPdfFailed2')
        )
      );
    } finally {
      setPdfLoading(false);
    }
  };

  const handleSavePdfRecipes = async () => {
    if (!pdfRecipes?.length) return;
    setSaving(true);
    try {
      const formData = new FormData();
      formData.append('file', pdfFile);
      formData.append('apply', 'true');
      if (selectedCookbookId) formData.append('cookbook_id', selectedCookbookId);
      const res = await aiApi.importRecipePdf(formData);
      const n = res.data.recipe_count || res.data.recipes?.length || 0;
      const skipped = res.data.skipped?.length || 0;
      toast.success(
        t('toastAddedRecipesForReview', { count: n, plural: n === 1 ? '' : 's' }) +
          (skipped ? t('toastSkippedDuplicatesSuffix', { count: skipped }) : '')
      );
      navigate('/recipes?review=1');
    } catch (error) {
      toast.error(
        getAiQuotaErrorMessage(
          error,
          error.response?.data?.detail || t('toastSaveRecipesFailed')
        )
      );
    } finally {
      setSaving(false);
    }
  };

  const handleSaveRecipe = async () => {
    if (!extractedRecipe) return;
    
    setSaving(true);
    try {
      const tags = Array.from(
        new Set([
          ...(extractedRecipe.tags || []),
          'needs-review',
          ...(pdfFile ? ['imported-pdf'] : imageFiles.length ? ['imported-photo'] : []),
        ].filter(Boolean))
      );
      const pageNum = cookbookPage ? parseInt(cookbookPage, 10) : null;
      const cookbookId =
        selectedCookbookId ||
        extractedRecipe.cookbook_id ||
        null;
      const recipeData = {
        title: extractedRecipe.title,
        description: extractedRecipe.description || '',
        category: extractedRecipe.category || 'Other',
        prep_time: extractedRecipe.prep_time || 0,
        cook_time: extractedRecipe.cook_time || 0,
        servings: extractedRecipe.servings || 4,
        tags,
        ingredients: extractedRecipe.ingredients || [],
        instructions: extractedRecipe.instructions || [],
        image_url: extractedRecipe.image_url || '',
        ...(extractedRecipe.nutrition ? { nutrition: extractedRecipe.nutrition } : {}),
        ...(cookbookId
          ? {
              cookbook_id: cookbookId,
              source_type: 'cookbook',
              ...(Number.isFinite(pageNum) ? { cookbook_page: pageNum } : {}),
            }
          : {}),
      };
      
      const res = await recipeApi.create(recipeData);
      toast.success(t('toastRecipeSavedForReview'));
      navigate(`/recipes/${res.data.id}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastSaveRecipeFailed2'));
    } finally {
      setSaving(false);
    }
  };

  const handlePasteFromClipboard = async () => {
    try {
      const text = await navigator.clipboard.readText();
      setPasteText(text);
      toast.success(t('toastPastedFromClipboard'));
    } catch (error) {
      toast.error(t('toastClipboardAccessFailed'));
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
          {t('backToRecipes')}
        </Link>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-2xl border border-border/60 p-6 shadow-card"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-laro-light flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-laro" />
            </div>
            <div>
              <h1 className="font-heading text-2xl font-bold">{t('quickAddRecipeTitle')}</h1>
              <p className="text-muted-foreground text-sm">{t('quickAddSubtitle')}</p>
            </div>
          </div>

          {!extractedRecipe && !pdfRecipes ? (
            <Tabs value={activeTab} onValueChange={setActiveTab}>
              <TabsList className="grid grid-cols-5 mb-6">
                <TabsTrigger value="paste" className="flex items-center gap-1 px-1">
                  <ClipboardPaste className="w-4 h-4" />
                  <span className="hidden sm:inline">{t('tabPaste')}</span>
                </TabsTrigger>
                <TabsTrigger value="url" className="flex items-center gap-1 px-1">
                  <LinkIcon className="w-4 h-4" />
                  <span className="hidden sm:inline">{t('tabUrl')}</span>
                </TabsTrigger>
                <TabsTrigger value="photo" className="flex items-center gap-1 px-1">
                  <ImageIcon className="w-4 h-4" />
                  <span className="hidden sm:inline">{t('tabPhoto')}</span>
                </TabsTrigger>
                <TabsTrigger value="pdf" className="flex items-center gap-1 px-1" data-testid="quick-add-pdf-tab">
                  <FileType className="w-4 h-4" />
                  <span className="hidden sm:inline">{t('tabPdf')}</span>
                </TabsTrigger>
                <TabsTrigger value="import" className="flex items-center gap-1 px-1">
                  <Upload className="w-4 h-4" />
                  <span className="hidden sm:inline">{t('import')}</span>
                </TabsTrigger>
              </TabsList>

              {/* Paste Tab */}
              <TabsContent value="paste" className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label>{t('pasteRecipeText')}</Label>
                    <Button 
                      variant="ghost" 
                      size="sm"
                      onClick={handlePasteFromClipboard}
                      className="text-xs"
                    >
                      <ClipboardPaste className="w-3 h-3 mr-1" />
                      {t('pasteFromClipboard')}
                    </Button>
                  </div>
                  <Textarea
                    value={pasteText}
                    onChange={(e) => setPasteText(e.target.value)}
                    placeholder={t('pasteRecipePlaceholder')}
                    className="min-h-[200px] rounded-xl"
                    data-testid="paste-recipe-input"
                  />
                </div>
                <Button
                  onClick={handlePasteSubmit}
                  disabled={pasteLoading || !pasteText.trim()}
                  className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
                  data-testid="parse-recipe-btn"
                >
                  {pasteLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <Sparkles className="w-5 h-5 mr-2" />
                      {t('parseRecipeWithAi')}
                    </>
                  )}
                </Button>
              </TabsContent>

              {/* URL Tab */}
              <TabsContent value="url" className="space-y-4">
                <div>
                  <Label className="mb-2 block">{t('recipeUrlLabel')}</Label>
                  <Input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder={t('recipeUrlPlaceholder')}
                    className="rounded-xl"
                    data-testid="url-input"
                  />
                </div>
                <Button
                  onClick={handleUrlSubmit}
                  disabled={urlLoading || !url.trim()}
                  className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
                  data-testid="extract-url-btn"
                >
                  {urlLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <LinkIcon className="w-5 h-5 mr-2" />
                      {t('extractFromUrl')}
                    </>
                  )}
                </Button>
                {urlFailed && (
                  <SocialImportFallback
                    failedUrl={url}
                    onSuccess={(recipe) => setExtractedRecipe(recipe)}
                    onSwitchToPhoto={() => {
                      setActiveTab('photo');
                      setUrlFailed(false);
                    }}
                  />
                )}
              </TabsContent>


              <TabsContent value="photo" className="space-y-4">
                <div>
                  <Label className="mb-2 block">{t('cookbookRecipePhotos')}</Label>
                  <Input
                    type="file"
                    accept="image/*"
                    multiple
                    onChange={(e) => setImageFiles(Array.from(e.target.files || []))}
                    className="rounded-xl"
                    data-testid="photo-recipe-input"
                  />
                  <p className="text-xs text-muted-foreground mt-2">
                    {t('photoUploadHint')}
                  </p>
                </div>
                {cookbookAttachFields}
                <Button
                  onClick={handleImageSubmit}
                  disabled={imageLoading || !imageFiles.length}
                  className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
                  data-testid="extract-photo-btn"
                >
                  {imageLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <ImageIcon className="w-5 h-5 mr-2" />
                      {t('extractFromPhotos')}
                    </>
                  )}
                </Button>
              </TabsContent>

              <TabsContent value="pdf" className="space-y-4">
                <div>
                  <Label className="mb-2 block">{t('recipeOrMealPlanPdf')}</Label>
                  <Input
                    type="file"
                    accept="application/pdf,.pdf"
                    onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                    className="rounded-xl"
                    data-testid="pdf-recipe-input"
                  />
                  {pdfFile && (
                    <p className="text-xs text-muted-foreground mt-2">{pdfFile.name}</p>
                  )}
                  <p className="text-xs text-muted-foreground mt-2">
                    {t('pdfUploadHint')}
                  </p>
                </div>
                {cookbookAttachFields}
                <Button
                  onClick={handlePdfSubmit}
                  disabled={pdfLoading || !pdfFile}
                  className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
                  data-testid="extract-pdf-btn"
                >
                  {pdfLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <FileType className="w-5 h-5 mr-2" />
                      {t('extractFromPdf')}
                    </>
                  )}
                </Button>
              </TabsContent>

              {/* Import Tab */}
              <TabsContent value="import" className="space-y-4">
                <div>
                  <Label className="mb-2 block">{t('importFromLabel')}</Label>
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
                            ? 'border-laro bg-laro-light text-laro'
                            : 'border-border/60 hover:border-laro'
                        }`}
                      >
                        {platform.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <Label className="mb-2 block">{t('exportDataJsonLabel')}</Label>
                  <Textarea
                    value={importData}
                    onChange={(e) => setImportData(e.target.value)}
                    placeholder={t('importDataPlaceholder')}
                    className="min-h-[150px] rounded-xl font-mono text-sm"
                    data-testid="import-data-input"
                  />
                </div>
                <Button
                  onClick={handleImportSubmit}
                  disabled={importLoading || !importData.trim()}
                  className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
                  data-testid="import-btn"
                >
                  {importLoading ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <Upload className="w-5 h-5 mr-2" />
                      {t('importRecipesBtn')}
                    </>
                  )}
                </Button>
                <p className="text-xs text-muted-foreground text-center">
                  {t('exportRecipesHint')}
                </p>
              </TabsContent>
            </Tabs>
          ) : pdfRecipes ? (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
              data-testid="pdf-multi-recipe-preview"
            >
              <div>
                <h2 className="font-heading text-lg font-semibold">
                  {t('recipesSeparatedFromPdf', { count: pdfRecipes.length })}
                </h2>
                <p className="text-sm text-muted-foreground mt-1">
                  {t('pdfRecipesReviewHint')}
                </p>
              </div>
              <ul className="space-y-2 max-h-80 overflow-y-auto">
                {pdfRecipes.map((r, idx) => (
                  <li
                    key={`${r.title}-${idx}`}
                    className="rounded-xl border border-border/60 bg-cream-subtle px-4 py-3"
                  >
                    <p className="font-medium text-sm">{r.title}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {t('ingredientsStepsCount', {
                        ingredients: (r.ingredients || []).length,
                        steps: (r.instructions || []).length,
                      })}
                      {r.category ? ` · ${r.category}` : ''}
                    </p>
                  </li>
                ))}
              </ul>
              {pdfSkipped?.length > 0 && (
                <p className="text-xs text-amber-700">
                  {t('skippedDuplicatesHint', { count: pdfSkipped.length })}
                </p>
              )}
              <div className="flex gap-3">
                <Button
                  variant="outline"
                  className="flex-1 rounded-full"
                  onClick={() => {
                    setPdfRecipes(null);
                    setPdfSkipped([]);
                  }}
                >
                  {t('back')}
                </Button>
                <Button
                  className="flex-1 rounded-full bg-laro hover:bg-laro-dark"
                  onClick={handleSavePdfRecipes}
                  disabled={saving || !pdfFile}
                  data-testid="save-pdf-recipes-btn"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    t('addForReviewCount', { count: pdfRecipes.length })
                  )}
                </Button>
              </div>
            </motion.div>
          ) : (
            /* Recipe Preview */
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-6"
            >
              <div className="flex items-center justify-between">
                <h2 className="font-heading text-lg font-semibold">{t('recipePreview')}</h2>
                <div className="flex items-center gap-2 text-sm text-laro">
                  <Check className="w-4 h-4" />
                  {t('markedForReview')}
                </div>
              </div>

              <div className="p-4 bg-cream-subtle rounded-xl space-y-4">
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">{t('titleLabel')}</p>
                  <p className="font-heading font-semibold text-lg">{extractedRecipe.title}</p>
                </div>

                {extractedRecipe.description && (
                  <div>
                    <p className="text-xs text-muted-foreground uppercase tracking-wide">{t('descriptionLabel')}</p>
                    <p className="text-sm">{extractedRecipe.description}</p>
                  </div>
                )}

                <div className="grid grid-cols-4 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground">{t('category')}</p>
                    <p className="font-medium text-sm">{extractedRecipe.category || t('other')}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">{t('prep')}</p>
                    <p className="font-medium text-sm">{extractedRecipe.prep_time || 0} min</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">{t('cook')}</p>
                    <p className="font-medium text-sm">{extractedRecipe.cook_time || 0} min</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">{t('servings')}</p>
                    <p className="font-medium text-sm">{extractedRecipe.servings || 4}</p>
                  </div>
                </div>

                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide mb-2">
                    {t('ingredientsCountLabel', { count: extractedRecipe.ingredients?.length || 0 })}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {extractedRecipe.ingredients?.slice(0, 6).map((ing, idx) => (
                      <span key={idx} className="px-2 py-1 bg-white rounded-lg text-xs">
                        {ing.amount} {ing.unit} {ing.name}
                      </span>
                    ))}
                    {extractedRecipe.ingredients?.length > 6 && (
                      <span className="px-2 py-1 text-xs text-muted-foreground">
                        +{extractedRecipe.ingredients.length - 6} {t('more') || 'more'}
                      </span>
                    )}
                  </div>
                  <VetoReplacementBanner
                    className="mt-3"
                    ingredients={extractedRecipe.ingredients || []}
                    refreshKey={extractedRecipe.title}
                    onApply={(index, suggestionName) => {
                      setExtractedRecipe((prev) => {
                        if (!prev?.ingredients) return prev;
                        const next = [...prev.ingredients];
                        if (!next[index]) return prev;
                        next[index] = { ...next[index], name: suggestionName };
                        return { ...prev, ingredients: next };
                      });
                    }}
                  />
                </div>

                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">
                    {t('instructionsStepsCount', { count: extractedRecipe.instructions?.length || 0 })}
                  </p>
                </div>
              </div>

              <div className="flex gap-3">
                <Button
                  onClick={handleSaveRecipe}
                  disabled={saving}
                  className="flex-1 rounded-full bg-laro hover:bg-laro-dark h-12"
                  data-testid="save-recipe-btn"
                >
                  {saving ? (
                    <Loader2 className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <Check className="w-5 h-5 mr-2" />
                      {t('saveRecipe')}
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setExtractedRecipe(null)}
                  className="rounded-full"
                >
                  {t('tryAgain')}
                </Button>
              </div>
            </motion.div>
          )}
        </motion.div>
      </div>
    </Layout>
  );
};
