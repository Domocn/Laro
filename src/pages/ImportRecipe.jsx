import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { aiApi, recipeApi } from '../lib/api';
import { getAiQuotaErrorMessage } from '../lib/aiQuota';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
  Link as LinkIcon,
  ArrowLeft,
  Loader2,
  Sparkles,
  Check,
  FileType,
  ThumbsUp,
  ThumbsDown,
  Meh,
} from 'lucide-react';
import { toast } from 'sonner';
import { useLanguage } from '../context/LanguageContext';
import { SocialImportFallback } from '../components/SocialImportFallback';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import {
  ingredientsToText,
  textToIngredients,
} from '../lib/parseIngredientLine';

function instructionsToText(instructions = []) {
  return (instructions || []).join('\n');
}

function textToInstructions(text = '') {
  return text
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean);
}

export const ImportRecipe = () => {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [urlFailed, setUrlFailed] = useState(false);
  const [pdfFile, setPdfFile] = useState(null);
  const [extractedRecipe, setExtractedRecipe] = useState(null);
  const [draft, setDraft] = useState(null);
  const [ingredientsText, setIngredientsText] = useState('');
  const [instructionsText, setInstructionsText] = useState('');
  const [saving, setSaving] = useState(false);
  const [importId, setImportId] = useState(null);
  const [importMode, setImportMode] = useState(null);
  const [originalRecipeSnapshot, setOriginalRecipeSnapshot] = useState(null);
  const [importRating, setImportRating] = useState(null);
  const [importFeedbackNote, setImportFeedbackNote] = useState('');
  const [feedbackSending, setFeedbackSending] = useState(false);
  const [creatorWebsite, setCreatorWebsite] = useState(null);
  const [suggestedRecipeUrl, setSuggestedRecipeUrl] = useState(null);
  const [creatorWebsiteHint, setCreatorWebsiteHint] = useState('');
  const [dmGatedMessage, setDmGatedMessage] = useState('');
  const [dmCommentWords, setDmCommentWords] = useState([]);
  const [dmInstagramUrl, setDmInstagramUrl] = useState(null);
  const [dmInstagramHandle, setDmInstagramHandle] = useState('');
  const [showDmGateDialog, setShowDmGateDialog] = useState(false);
  const [quota, setQuota] = useState(null);


  const refreshQuota = async () => {
    try {
      const res = await aiApi.quota();
      setQuota(res.data);
    } catch {
      // Non-blocking
    }
  };

  useEffect(() => {
    refreshQuota();
  }, []);

  const applyExtracted = (recipe, meta = {}) => {
    setExtractedRecipe(recipe);
    setImportId(meta.import_id || null);
    setImportMode(meta.import_mode || null);
    setOriginalRecipeSnapshot(recipe ? JSON.parse(JSON.stringify(recipe)) : null);
    setImportRating(null);
    setImportFeedbackNote('');
    setCreatorWebsite(meta.creator_website || null);
    setSuggestedRecipeUrl(meta.suggested_recipe_url || null);
    setCreatorWebsiteHint(meta.creator_website_hint || '');
    const dmMsg = meta.dm_gated
      ? (meta.dm_gated_message || t('dmGatedRecipeBody'))
      : '';
    setDmGatedMessage(dmMsg);
    setDmCommentWords(
      Array.isArray(meta.dm_comment_words) ? meta.dm_comment_words.filter(Boolean) : []
    );
    setDmInstagramUrl(meta.dm_instagram_url || null);
    setDmInstagramHandle(meta.dm_instagram_handle || '');
    if (dmMsg) setShowDmGateDialog(true);
    const nutrition = recipe.nutrition || {};
    setDraft({
      title: recipe.title || '',
      description: recipe.description || '',
      category: recipe.category || (recipe.is_meal_pack ? 'Meal Pack' : 'Other'),
      prep_time: recipe.prep_time || 0,
      cook_time: recipe.cook_time || 0,
      servings: recipe.servings || (recipe.is_meal_pack ? 1 : 4),
      tags: (recipe.tags || []).join(', '),
      image_url: recipe.image_url || '',
      source_author: meta.source_author || recipe.source_author || '',
      calories: nutrition.calories ?? '',
      protein: nutrition.protein ?? '',
      carbs: nutrition.carbs ?? '',
      fat: nutrition.fat ?? '',
      is_meal_pack: !!recipe.is_meal_pack,
      needs_macros: !!recipe.needs_macros || !!meta.needs_macros,
    });
    setIngredientsText(ingredientsToText(recipe.ingredients || []));
    setInstructionsText(instructionsToText(recipe.instructions || []));
  };

  const extractRecipe = async (recipeUrl) => {
    if (!recipeUrl.trim()) {
      toast.error(t('toastEnterRecipeUrl'));
      return;
    }

    setLoading(true);
    setUrlFailed(false);
    try {
      const res = await aiApi.importUrl(recipeUrl);
      applyExtracted(res.data.recipe, res.data);
      if (res.data.import_mode === 'meal_pack' || res.data.recipe?.is_meal_pack) {
        toast.success(
          res.data.needs_macros || res.data.recipe?.needs_macros
            ? t('toastMealPackFoundEnterCalories')
            : t('toastMealPackReady')
        );
      } else {
        toast.success(
          res.data.used_ai
            ? t('toastRecipeExtractedAi')
            : t('toastRecipeExtractedFree')
        );
      }
      refreshQuota();
    } catch (error) {
      console.error('Extract error:', error);
      setUrlFailed(true);
      const detail = error?.response?.data?.detail;
      if (detail && typeof detail === 'object') {
        setCreatorWebsite(detail.creator_website || null);
        setSuggestedRecipeUrl(detail.suggested_recipe_url || null);
        setCreatorWebsiteHint(detail.creator_website_hint || '');
        if (detail.dm_gated) {
          const dmMsg = detail.dm_gated_message || t('dmGatedRecipeBody');
          setDmGatedMessage(dmMsg);
          setDmCommentWords(
            Array.isArray(detail.dm_comment_words)
              ? detail.dm_comment_words.filter(Boolean)
              : []
          );
          setDmInstagramUrl(detail.dm_instagram_url || null);
          setDmInstagramHandle(detail.dm_instagram_handle || '');
          setShowDmGateDialog(true);
        }
      }
      toast.error(
        getAiQuotaErrorMessage(
          error,
          t('toastExtractPageFailed')
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const extractFromSharedText = async (sharedText) => {
    const text = (sharedText || '').trim();
    if (!text) return;

    // Prefer a URL embedded in shared caption/title text.
    const embedded = text.match(/https?:\/\/[^\s<>"']+/i);
    if (embedded) {
      const cleanUrl = embedded[0].replace(/[.,;:)\]}]+$/g, '');
      setUrl(cleanUrl);
      await extractRecipe(cleanUrl);
      return;
    }

    setLoading(true);
    setUrlFailed(false);
    try {
      const res = await aiApi.importText(text);
      applyExtracted(res.data.recipe, res.data);
      toast.success(
        res.data.used_ai
          ? t('toastRecipeExtractedAi')
          : t('toastRecipeExtractedFree')
      );
      refreshQuota();
    } catch (error) {
      console.error('Shared text extract error:', error);
      setUrlFailed(true);
      toast.error(
        getAiQuotaErrorMessage(
          error,
          t('toastExtractPageFailed')
        )
      );
    } finally {
      setLoading(false);
    }
  };

  // Deep link / PWA share_target: /#/recipes/import?url=… or ?text=…
  useEffect(() => {
    const urlParam = searchParams.get('url');
    const textParam = searchParams.get('text');
    if (urlParam && !url) {
      setUrl(urlParam);
      extractRecipe(urlParam);
      return;
    }
    if (textParam && !extractedRecipe && !loading) {
      extractFromSharedText(textParam);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const handleExtract = async (e) => {
    e.preventDefault();
    extractRecipe(url);
  };

  const extractPdf = async () => {
    if (!pdfFile) {
      toast.error(t('toastChoosePdf'));
      return;
    }
    if (pdfFile.size > 12_000_000) {
      toast.error(t('toastPdfTooLarge'));
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', pdfFile);
      // Multi-recipe docs: save each separately, marked for review
      formData.append('apply', 'true');
      formData.append('context', 'recipes');
      const res = await aiApi.importPdf(formData);
      const list = res.data.recipes || [];
      const n = res.data.recipe_count || list.length;
      const skipped = res.data.skipped?.length || 0;
      if (!n) {
        toast.error(res.data.message || t('toastNoRecipesInPdf'));
        return;
      }
      if (n === 1 && list[0]) {
        applyExtracted(list[0], res.data);
        toast.success(t('toastRecipeImportedForReview'));
      } else {
        toast.success(
          t('toastSeparatedRecipesFromPdf', { n }) +
            (skipped ? t('toastDuplicatesSkippedSuffix', { count: skipped }) : '') +
            t('toastMarkedForReviewSuffix')
        );
        navigate('/recipes?review=1');
        return;
      }
      refreshQuota();
    } catch (error) {
      toast.error(
        getAiQuotaErrorMessage(
          error,
          error.response?.data?.detail || t('toastExtractPdfFailed')
        )
      );
    } finally {
      setLoading(false);
    }
  };

  const updateDraft = (patch) => setDraft((d) => ({ ...d, ...patch }));

  const buildCurrentRecipePayload = () => {
    if (!draft) return null;
    const calories =
      draft.calories === '' || draft.calories == null ? null : Number(draft.calories);
    const toNum = (v) => (v === '' || v == null || Number.isNaN(Number(v)) ? null : Number(v));
    const nutrition = {
      calories,
      protein: toNum(draft.protein),
      carbs: toNum(draft.carbs),
      fat: toNum(draft.fat),
    };
    const hasNutrition = Object.values(nutrition).some((v) => v != null);
    return {
      title: draft.title || 'Untitled Recipe',
      description: draft.description || '',
      category: draft.category || (draft.is_meal_pack ? 'Meal Pack' : 'Other'),
      prep_time: parseInt(draft.prep_time, 10) || 0,
      cook_time: parseInt(draft.cook_time, 10) || 0,
      servings: parseInt(draft.servings, 10) || (draft.is_meal_pack ? 1 : 4),
      tags: (draft.tags || '')
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
      ingredients: textToIngredients(ingredientsText),
      instructions: textToInstructions(instructionsText),
      image_url: draft.image_url || '',
      source_url: url || '',
      ...(draft.source_author
        ? { source_author: String(draft.source_author).replace(/^@/, '').trim() }
        : {}),
      ...(hasNutrition ? { nutrition } : {}),
    };
  };

  const submitImportFeedback = async (rating, { recipeId = null, silent = false } = {}) => {
    if (!importId && !originalRecipeSnapshot) return;
    const corrected = buildCurrentRecipePayload();
    setFeedbackSending(true);
    try {
      await aiApi.importFeedback({
        rating,
        import_id: importId,
        source_url: url || originalRecipeSnapshot?.source_url || '',
        import_mode: importMode,
        recipe_id: recipeId,
        note: importFeedbackNote || '',
        original_recipe: originalRecipeSnapshot,
        corrected_recipe: corrected,
        platform: 'web',
      });
      setImportRating(rating);
      if (!silent) toast.success(t('importFeedbackThanks'));
    } catch (err) {
      console.error('Import feedback failed', err);
      if (!silent) toast.error(t('toastSaveRecipeFailed'));
    } finally {
      setFeedbackSending(false);
    }
  };

  const handleSave = async () => {
    if (!draft) return;

    setSaving(true);
    try {
      const recipeData = buildCurrentRecipePayload();
      if (!recipeData) {
        setSaving(false);
        return;
      }
      if (draft.is_meal_pack && (recipeData.nutrition?.calories == null)) {
        toast.error(t('toastEnterCaloriesMealPack'));
        setSaving(false);
        return;
      }

      if (!recipeData.ingredients.length) {
        toast.error(t('toastAddIngredientBeforeSaving'));
        setSaving(false);
        return;
      }
      if (!recipeData.instructions.length) {
        toast.error(t('toastAddInstructionBeforeSaving'));
        setSaving(false);
        return;
      }

      const res = await recipeApi.create(recipeData);
      // Always send correction snapshot on save so edits improve Whisper cleanup.
      const rating =
        importRating ||
        (JSON.stringify(recipeData.ingredients) !==
        JSON.stringify(originalRecipeSnapshot?.ingredients || [])
          ? 'ok'
          : 'good');
      await submitImportFeedback(rating, { recipeId: res.data.id, silent: true });
      toast.success(
        draft.is_meal_pack
          ? t('toastMealPackSaved')
          : t('toastRecipeSavedCollection')
      );
      navigate(`/recipes/${res.data.id}`);
    } catch (error) {
      console.error('Save error:', error.response?.data || error);
      toast.error(error.response?.data?.detail || t('toastSaveRecipeFailed'));
    } finally {
      setSaving(false);
    }
  };

  const clearPreview = () => {
    setExtractedRecipe(null);
    setDraft(null);
    setIngredientsText('');
    setInstructionsText('');
    setImportId(null);
    setImportMode(null);
    setOriginalRecipeSnapshot(null);
    setImportRating(null);
    setImportFeedbackNote('');
    setCreatorWebsite(null);
    setSuggestedRecipeUrl(null);
    setCreatorWebsiteHint('');
    setDmGatedMessage('');
    setDmCommentWords([]);
    setDmInstagramUrl(null);
    setDmInstagramHandle('');
    setShowDmGateDialog(false);
  };

  return (
    <Layout>
      <AlertDialog open={showDmGateDialog} onOpenChange={setShowDmGateDialog}>
        <AlertDialogContent data-testid="dm-gated-recipe-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle>{t('dmGatedRecipeTitle')}</AlertDialogTitle>
            <AlertDialogDescription className="whitespace-pre-wrap space-y-3">
              <span className="block">
                {dmGatedMessage || t('dmGatedRecipeBody')}
              </span>
              {dmCommentWords.length > 0 && (
                <span className="block text-foreground font-medium" data-testid="dm-comment-words">
                  {dmCommentWords.length === 1
                    ? t('dmGatedCommentWord', { word: dmCommentWords[0] })
                    : t('dmGatedCommentWords', {
                        words: dmCommentWords.map((w) => `"${w}"`).join(', '),
                      })}
                </span>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="flex-col sm:flex-row gap-2">
            {dmInstagramUrl && (
              <Button
                type="button"
                variant="outline"
                className="rounded-full"
                data-testid="dm-gated-open-instagram"
                onClick={() =>
                  window.open(dmInstagramUrl, '_blank', 'noopener,noreferrer')
                }
              >
                {dmInstagramHandle
                  ? t('dmGatedOpenInstagramHandle', { handle: dmInstagramHandle })
                  : t('dmGatedOpenInstagram')}
              </Button>
            )}
            <AlertDialogAction
              data-testid="dm-gated-recipe-got-it"
              onClick={() => setShowDmGateDialog(false)}
            >
              {t('dmGatedRecipeGotIt')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <div className="max-w-3xl mx-auto" data-testid="import-recipe">
        <button
          onClick={() => navigate(-1)}
          className="inline-flex items-center text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t('back')}
        </button>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-2xl border border-border/60 p-6 md:p-8 shadow-card"
        >
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 rounded-xl bg-laro-light flex items-center justify-center">
              <Sparkles className="w-6 h-6 text-laro" />
            </div>
            <div>
              <h1 className="font-heading text-2xl font-bold">{t('importRecipe')}</h1>
              <p className="text-muted-foreground text-sm">
                {t('importRecipeSubtitle')}
              </p>
              {quota && !quota.unlimited && (
                <p className="text-xs mt-1 text-muted-foreground" data-testid="ai-quota-badge">
                  {quota.remaining > 0
                    ? t('freeAiUsesLeft', { remaining: quota.remaining, limit: quota.limit })
                    : t('freeAiUsedUp', { limit: quota.limit })}
                </p>
              )}
              {quota?.unlimited && (
                <p className="text-xs mt-1 text-laro" data-testid="ai-quota-badge">
                  {t('premiumUnlimitedAi')}
                </p>
              )}
            </div>
          </div>

          <form onSubmit={handleExtract} className="mb-8">
            <Label htmlFor="url" className="mb-2 block">{t('recipeOrProductUrl')}</Label>
            <div className="flex gap-3">
              <div className="relative flex-1">
                <LinkIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                <Input
                  id="url"
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder={t('recipeUrlHintPlaceholder')}
                  className="pl-10 rounded-xl"
                  disabled={loading}
                  data-testid="import-url-input"
                />
              </div>
              <Button
                type="submit"
                className="rounded-full bg-laro hover:bg-laro-dark px-6"
                disabled={loading}
                data-testid="extract-btn"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    {t('extract')}
                  </>
                )}
              </Button>
            </div>
          </form>

          {urlFailed && !draft && (
            <div className="mb-8">
              {(creatorWebsite || suggestedRecipeUrl) && (
                <div
                  className="mb-4 rounded-xl border border-laro/30 bg-laro/5 p-4 space-y-3"
                  data-testid="creator-website-offer"
                >
                  <p className="text-sm text-foreground">
                    {creatorWebsiteHint || t('creatorWebsiteHintFallback')}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {suggestedRecipeUrl && (
                      <Button
                        type="button"
                        className="rounded-full bg-laro hover:bg-laro-dark"
                        disabled={loading}
                        onClick={() => {
                          setUrl(suggestedRecipeUrl);
                          setUrlFailed(false);
                          extractRecipe(suggestedRecipeUrl);
                        }}
                        data-testid="import-suggested-recipe-btn"
                      >
                        {t('importWrittenRecipe')}
                      </Button>
                    )}
                    {creatorWebsite && (
                      <Button
                        type="button"
                        variant="outline"
                        className="rounded-full"
                        onClick={() => window.open(creatorWebsite, '_blank', 'noopener,noreferrer')}
                        data-testid="open-creator-website-btn"
                      >
                        {t('openCreatorWebsite')}
                      </Button>
                    )}
                  </div>
                </div>
              )}
              <SocialImportFallback
                failedUrl={url}
                onSuccess={(recipe, meta) => {
                  setUrlFailed(false);
                  applyExtracted(recipe, meta || {});
                  refreshQuota();
                }}
              />
            </div>
          )}

          <div className="mb-8 pt-2 border-t border-border/40">
            <Label className="mb-2 block">{t('orUploadPdf')}</Label>
            <div className="flex flex-col sm:flex-row gap-3">
              <Input
                type="file"
                accept="application/pdf,.pdf"
                className="rounded-xl flex-1"
                onChange={(e) => setPdfFile(e.target.files?.[0] || null)}
                disabled={loading}
                data-testid="import-recipe-pdf-input"
              />
              <Button
                type="button"
                variant="outline"
                className="rounded-full px-6"
                disabled={loading || !pdfFile}
                onClick={extractPdf}
                data-testid="extract-pdf-btn"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <FileType className="w-4 h-4 mr-2" />
                    {t('extractPdfButton')}
                  </>
                )}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              {t('pdfImportHint')}
            </p>
          </div>

          {draft && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="border border-border/60 rounded-xl p-6 bg-cream-subtle space-y-4"
              data-testid="import-preview"
            >
              <div className="flex items-center justify-between">
                <h2 className="font-heading text-lg font-semibold">{t('reviewBeforeSaving')}</h2>
                <div className="flex items-center gap-2 text-sm text-laro">
                  <Check className="w-4 h-4" />
                  {t('editablePreview')}
                </div>
              </div>

              {(creatorWebsite || suggestedRecipeUrl) && (
                <div
                  className="rounded-xl border border-laro/30 bg-white/80 p-3 space-y-2"
                  data-testid="creator-website-offer"
                >
                  <p className="text-sm text-foreground">
                    {creatorWebsiteHint || t('creatorWebsiteHintFallback')}
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {suggestedRecipeUrl && (
                      <Button
                        type="button"
                        size="sm"
                        className="rounded-full bg-laro hover:bg-laro-dark"
                        disabled={loading}
                        onClick={() => {
                          setUrl(suggestedRecipeUrl);
                          extractRecipe(suggestedRecipeUrl);
                        }}
                        data-testid="import-suggested-recipe-btn"
                      >
                        {t('importWrittenRecipe')}
                      </Button>
                    )}
                    {creatorWebsite && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        className="rounded-full"
                        onClick={() => window.open(creatorWebsite, '_blank', 'noopener,noreferrer')}
                        data-testid="open-creator-website-btn"
                      >
                        {t('openCreatorWebsite')}
                      </Button>
                    )}
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <Label>{t('titleLabel')}</Label>
                <Input
                  value={draft.title}
                  onChange={(e) => updateDraft({ title: e.target.value })}
                  className="rounded-xl bg-white"
                />
              </div>

              {(draft.is_meal_pack || draft.needs_macros || draft.category === 'Meal Pack') && (
                <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-3 space-y-2">
                  <p className="text-sm font-medium text-amber-900">
                    {t('macrosLabel')} {draft.needs_macros ? t('macrosRequiredNotFound') : t('macrosFromProductPage')}
                  </p>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    {[
                      ['calories', 'kcalLabel'],
                      ['protein', 'proteinG'],
                      ['carbs', 'carbsG'],
                      ['fat', 'fatG'],
                    ].map(([key, labelKey]) => (
                      <div key={key} className="space-y-1">
                        <Label className="text-xs">{t(labelKey)}</Label>
                        <Input
                          type="number"
                          min="0"
                          value={draft[key]}
                          onChange={(e) => updateDraft({ [key]: e.target.value })}
                          className="rounded-xl bg-white"
                          data-testid={`import-macro-${key}`}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <Label>{t('descriptionLabel')}</Label>
                <Textarea
                  value={draft.description}
                  onChange={(e) => updateDraft({ description: e.target.value })}
                  className="rounded-xl bg-white min-h-[72px]"
                />
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="space-y-2">
                  <Label>{t('category')}</Label>
                  <Input
                    value={draft.category}
                    onChange={(e) => updateDraft({ category: e.target.value })}
                    className="rounded-xl bg-white"
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t('prepMinLabel')}</Label>
                  <Input
                    type="number"
                    value={draft.prep_time}
                    onChange={(e) => updateDraft({ prep_time: e.target.value })}
                    className="rounded-xl bg-white"
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t('cookMinLabel')}</Label>
                  <Input
                    type="number"
                    value={draft.cook_time}
                    onChange={(e) => updateDraft({ cook_time: e.target.value })}
                    className="rounded-xl bg-white"
                  />
                </div>
                <div className="space-y-2">
                  <Label>{t('servings')}</Label>
                  <Input
                    type="number"
                    value={draft.servings}
                    onChange={(e) => updateDraft({ servings: e.target.value })}
                    className="rounded-xl bg-white"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>{t('ingredientsOnePerLine')}</Label>
                <Textarea
                  value={ingredientsText}
                  onChange={(e) => setIngredientsText(e.target.value)}
                  className="rounded-xl bg-white min-h-[140px] font-mono text-sm"
                  placeholder={"2 cups flour\n1 tsp salt\n..."}
                />
                <p className="text-xs text-muted-foreground">
                  {t('ingredientsFixHint')}
                </p>
              </div>

              <div className="space-y-2">
                <Label>{t('instructionsOnePerLine')}</Label>
                <Textarea
                  value={instructionsText}
                  onChange={(e) => setInstructionsText(e.target.value)}
                  className="rounded-xl bg-white min-h-[140px] text-sm"
                />
              </div>

              <div className="space-y-2">
                <Label>{t('tagsCommaSeparated')}</Label>
                <Input
                  value={draft.tags}
                  onChange={(e) => updateDraft({ tags: e.target.value })}
                  className="rounded-xl bg-white"
                />
              </div>

              <div
                className="rounded-2xl border border-border/60 bg-muted/30 p-4 space-y-3"
                data-testid="import-feedback-panel"
              >
                <div>
                  <p className="text-sm font-medium">{t('importFeedbackTitle')}</p>
                  <p className="text-xs text-muted-foreground mt-1">{t('importFeedbackHint')}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant={importRating === 'good' ? 'default' : 'outline'}
                    className="rounded-full"
                    disabled={feedbackSending}
                    data-testid="import-feedback-good"
                    onClick={() => submitImportFeedback('good')}
                  >
                    <ThumbsUp className="w-3.5 h-3.5 mr-1.5" />
                    {t('importFeedbackGood')}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={importRating === 'ok' ? 'default' : 'outline'}
                    className="rounded-full"
                    disabled={feedbackSending}
                    data-testid="import-feedback-ok"
                    onClick={() => submitImportFeedback('ok')}
                  >
                    <Meh className="w-3.5 h-3.5 mr-1.5" />
                    {t('importFeedbackOk')}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={importRating === 'bad' ? 'default' : 'outline'}
                    className="rounded-full"
                    disabled={feedbackSending}
                    data-testid="import-feedback-bad"
                    onClick={() => submitImportFeedback('bad')}
                  >
                    <ThumbsDown className="w-3.5 h-3.5 mr-1.5" />
                    {t('importFeedbackBad')}
                  </Button>
                </div>
                <Textarea
                  value={importFeedbackNote}
                  onChange={(e) => setImportFeedbackNote(e.target.value)}
                  placeholder={t('importFeedbackNotePlaceholder')}
                  className="rounded-xl bg-white min-h-[64px] text-sm"
                  data-testid="import-feedback-note"
                />
              </div>

              <div className="flex gap-3 pt-4 border-t border-border/60">
                <Button
                  onClick={handleSave}
                  className="rounded-full bg-laro hover:bg-laro-dark"
                  disabled={saving}
                  data-testid="save-imported-btn"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Check className="w-4 h-4 mr-2" />
                  )}
                  {t('saveToMyRecipes')}
                </Button>
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={clearPreview}
                >
                  {t('tryAnotherUrl')}
                </Button>
              </div>
            </motion.div>
          )}

          {!extractedRecipe && (
            <div className="text-sm text-muted-foreground bg-cream-subtle rounded-xl p-4">
              <p className="font-medium mb-2">{t('importTipsTitle')}</p>
              <ul className="list-disc list-inside space-y-1">
                <li>{t('importTipDirectUrl')}</li>
                <li>{t('importTipReviewPreview')}</li>
                <li>{t('importTipSchemaOrg')}</li>
              </ul>
            </div>
          )}
        </motion.div>
      </div>
    </Layout>
  );
};
