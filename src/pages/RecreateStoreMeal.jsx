import React, { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { useLanguage } from '../context/LanguageContext';
import { aiApi, recipeApi } from '../lib/api';
import { toastAiQuotaError } from '../lib/aiQuota';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
  ArrowLeft,
  Camera,
  Loader2,
  Salad,
  Sparkles,
  Dumbbell,
  Flame,
  WheatOff,
  RefreshCw,
  Save,
  X,
} from 'lucide-react';
import { toast } from 'sonner';

const MODES = [
  {
    id: 'recreate',
    icon: RefreshCw,
    titleKey: 'storeMealModeRecreate',
    descKey: 'storeMealModeRecreateDesc',
  },
  {
    id: 'healthier',
    icon: Salad,
    titleKey: 'storeMealModeHealthier',
    descKey: 'storeMealModeHealthierDesc',
  },
  {
    id: 'higher_protein',
    icon: Dumbbell,
    titleKey: 'storeMealModeHigherProtein',
    descKey: 'storeMealModeHigherProteinDesc',
  },
  {
    id: 'lower_calorie',
    icon: Flame,
    titleKey: 'storeMealModeLowerCalorie',
    descKey: 'storeMealModeLowerCalorieDesc',
  },
  {
    id: 'lower_carb',
    icon: WheatOff,
    titleKey: 'storeMealModeLowerCarb',
    descKey: 'storeMealModeLowerCarbDesc',
  },
  {
    id: 'custom',
    icon: Sparkles,
    titleKey: 'storeMealModeCustom',
    descKey: 'storeMealModeCustomDesc',
  },
];

async function filesToBase64(files) {
  const out = [];
  for (const file of files) {
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
    out.push(String(dataUrl));
  }
  return out;
}

export const RecreateStoreMeal = () => {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [imageFiles, setImageFiles] = useState([]);
  const [previews, setPreviews] = useState([]);
  const [productName, setProductName] = useState('');
  const [description, setDescription] = useState('');
  const [ingredientsText, setIngredientsText] = useState('');
  const [nutritionText, setNutritionText] = useState('');
  const [mode, setMode] = useState('recreate');
  const [notes, setNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [recipe, setRecipe] = useState(null);

  const canGenerate = useMemo(() => {
    return imageFiles.length > 0 || productName.trim() || ingredientsText.trim() || nutritionText.trim();
  }, [imageFiles, productName, ingredientsText, nutritionText]);

  const onPickPhotos = async (event) => {
    const files = Array.from(event.target.files || []).slice(0, 6);
    if (!files.length) return;
    setImageFiles(files);
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
  };

  const clearPhotos = () => {
    previews.forEach((url) => URL.revokeObjectURL(url));
    setPreviews([]);
    setImageFiles([]);
  };

  const handleGenerate = async () => {
    if (!canGenerate) {
      toast.error(t('storeMealNeedInput'));
      return;
    }
    if (mode === 'custom' && !notes.trim()) {
      toast.error(t('storeMealCustomNotesRequired'));
      return;
    }
    setLoading(true);
    setRecipe(null);
    try {
      const images = imageFiles.length ? await filesToBase64(imageFiles) : [];
      const res = await aiApi.recreateStoreMeal({
        images,
        mode,
        notes,
        product_name: productName,
        description,
        ingredients_text: ingredientsText,
        nutrition_text: nutritionText,
      });
      setRecipe(res.data.recipe);
      setStep(4);
      toast.success(t('storeMealReadyToReview'));
    } catch (error) {
      toastAiQuotaError(error, {
        navigate,
        fallback: error.response?.data?.detail || t('storeMealGenerateFailed'),
        upgradeLabel: t('unlockLaroPro'),
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!recipe) return;
    setSaving(true);
    try {
      const tags = Array.from(
        new Set([...(recipe.tags || []), 'needs-review', 'store-meal'].filter(Boolean))
      );
      const res = await recipeApi.create({
        title: recipe.title,
        description: recipe.description || '',
        category: recipe.category || 'Dinner',
        prep_time: recipe.prep_time || 0,
        cook_time: recipe.cook_time || 0,
        servings: recipe.servings || 2,
        tags,
        ingredients: recipe.ingredients || [],
        instructions: recipe.instructions || [],
        image_url: recipe.image_url || '',
        source_type: 'store_meal',
        ...(recipe.nutrition ? { nutrition: recipe.nutrition } : {}),
      });
      toast.success(t('toastRecipeSavedForReview'));
      navigate(`/recipes/${res.data.id}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastSaveRecipeFailed2'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-3xl mx-auto space-y-6" data-testid="recreate-store-meal">
        <div className="flex items-center gap-3">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => navigate(-1)}
            aria-label={t('back')}
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-laro-brand tracking-tight">
              {t('storeMealTitle')}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">{t('storeMealSubtitle')}</p>
          </div>
        </div>

        <div className="flex gap-2 text-xs text-muted-foreground">
          {[1, 2, 3, 4].map((n) => (
            <span
              key={n}
              className={`px-2.5 py-1 rounded-full border ${
                step === n ? 'border-laro text-laro bg-laro/10' : 'border-border/60'
              }`}
            >
              {n}. {t(`storeMealStep${n}`)}
            </span>
          ))}
        </div>

        {step === 1 && (
          <motion.section
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-border/60 bg-white p-5 space-y-4"
          >
            <div>
              <h2 className="font-semibold text-lg">{t('storeMealPhotosHeading')}</h2>
              <p className="text-sm text-muted-foreground mt-1">{t('storeMealPhotosHint')}</p>
            </div>
            <label className="flex flex-col items-center justify-center gap-2 border border-dashed border-border rounded-2xl p-8 cursor-pointer hover:bg-cream-subtle/60 transition-colors">
              <Camera className="w-8 h-8 text-laro" />
              <span className="text-sm font-medium">{t('storeMealAddPhotos')}</span>
              <span className="text-xs text-muted-foreground">{t('storeMealPhotosLimit')}</span>
              <input
                type="file"
                accept="image/*"
                capture="environment"
                multiple
                className="hidden"
                data-testid="store-meal-photo-input"
                onChange={onPickPhotos}
              />
            </label>
            {previews.length > 0 && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {previews.map((src) => (
                    <img
                      key={src}
                      src={src}
                      alt=""
                      className="h-28 w-full object-cover rounded-xl border border-border/60"
                    />
                  ))}
                </div>
                <Button type="button" variant="ghost" size="sm" onClick={clearPhotos}>
                  <X className="w-4 h-4 mr-1" />
                  {t('clear')}
                </Button>
              </div>
            )}
            <div className="flex justify-end">
              <Button
                type="button"
                className="rounded-full"
                onClick={() => setStep(2)}
                data-testid="store-meal-next-details"
              >
                {t('continue')}
              </Button>
            </div>
          </motion.section>
        )}

        {step === 2 && (
          <motion.section
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-border/60 bg-white p-5 space-y-4"
          >
            <div>
              <h2 className="font-semibold text-lg">{t('storeMealDetailsHeading')}</h2>
              <p className="text-sm text-muted-foreground mt-1">{t('storeMealDetailsHint')}</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="product-name">{t('storeMealProductName')}</Label>
              <Input
                id="product-name"
                value={productName}
                onChange={(e) => setProductName(e.target.value)}
                placeholder={t('storeMealProductNamePlaceholder')}
                data-testid="store-meal-product-name"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="item-desc">{t('storeMealItemDescription')}</Label>
              <Textarea
                id="item-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={2}
                placeholder={t('storeMealItemDescriptionPlaceholder')}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ingredients">{t('storeMealIngredients')}</Label>
              <Textarea
                id="ingredients"
                value={ingredientsText}
                onChange={(e) => setIngredientsText(e.target.value)}
                rows={4}
                placeholder={t('storeMealIngredientsPlaceholder')}
                data-testid="store-meal-ingredients"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="nutrition">{t('storeMealNutrition')}</Label>
              <Textarea
                id="nutrition"
                value={nutritionText}
                onChange={(e) => setNutritionText(e.target.value)}
                rows={3}
                placeholder={t('storeMealNutritionPlaceholder')}
                data-testid="store-meal-nutrition"
              />
            </div>
            <div className="flex justify-between gap-2">
              <Button type="button" variant="ghost" onClick={() => setStep(1)}>
                {t('back')}
              </Button>
              <Button
                type="button"
                className="rounded-full"
                onClick={() => setStep(3)}
                data-testid="store-meal-next-goal"
              >
                {t('continue')}
              </Button>
            </div>
          </motion.section>
        )}

        {step === 3 && (
          <motion.section
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-border/60 bg-white p-5 space-y-4"
          >
            <div>
              <h2 className="font-semibold text-lg">{t('storeMealGoalHeading')}</h2>
              <p className="text-sm text-muted-foreground mt-1">{t('storeMealGoalHint')}</p>
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              {MODES.map((item) => {
                const Icon = item.icon;
                const active = mode === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setMode(item.id)}
                    data-testid={`store-meal-mode-${item.id}`}
                    className={`text-left rounded-2xl border p-4 transition-all ${
                      active
                        ? 'border-laro bg-laro/10 shadow-soft'
                        : 'border-border/60 hover:border-laro/40'
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Icon className={`w-4 h-4 ${active ? 'text-laro' : 'text-muted-foreground'}`} />
                      <span className="font-medium text-sm">{t(item.titleKey)}</span>
                    </div>
                    <p className="text-xs text-muted-foreground">{t(item.descKey)}</p>
                  </button>
                );
              })}
            </div>
            {(mode === 'custom' || notes) && (
              <div className="space-y-2">
                <Label htmlFor="notes">{t('storeMealCustomNotes')}</Label>
                <Textarea
                  id="notes"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                  placeholder={t('storeMealCustomNotesPlaceholder')}
                  data-testid="store-meal-notes"
                />
              </div>
            )}
            <div className="flex justify-between gap-2">
              <Button type="button" variant="ghost" onClick={() => setStep(2)}>
                {t('back')}
              </Button>
              <Button
                type="button"
                className="rounded-full"
                disabled={loading || !canGenerate}
                onClick={handleGenerate}
                data-testid="store-meal-generate"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    {t('storeMealGenerating')}
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    {t('storeMealGenerate')}
                  </>
                )}
              </Button>
            </div>
          </motion.section>
        )}

        {step === 4 && recipe && (
          <motion.section
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-border/60 bg-white p-5 space-y-4"
            data-testid="store-meal-review"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="font-semibold text-xl">{recipe.title}</h2>
                {recipe.description ? (
                  <p className="text-sm text-muted-foreground mt-1">{recipe.description}</p>
                ) : null}
              </div>
              <Button type="button" variant="outline" size="sm" onClick={() => setStep(3)}>
                {t('edit')}
              </Button>
            </div>

            {Array.isArray(recipe.changes_made) && recipe.changes_made.length > 0 && (
              <div className="rounded-xl bg-laro/5 border border-laro/20 p-3">
                <p className="text-xs font-semibold text-laro mb-1">{t('storeMealChanges')}</p>
                <ul className="text-sm space-y-1 list-disc pl-4">
                  {recipe.changes_made.map((c) => (
                    <li key={c}>{c}</li>
                  ))}
                </ul>
              </div>
            )}

            {recipe.nutrition && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
                {[
                  ['calories', t('calories')],
                  ['protein', t('protein')],
                  ['carbs', t('carbs')],
                  ['fat', t('fat')],
                ].map(([key, label]) => (
                  <div key={key} className="rounded-xl border border-border/60 p-2">
                    <p className="text-xs text-muted-foreground">{label}</p>
                    <p className="font-semibold">{recipe.nutrition?.[key] ?? '—'}</p>
                  </div>
                ))}
              </div>
            )}

            <div>
              <h3 className="font-medium mb-2">{t('ingredients')}</h3>
              <ul className="text-sm space-y-1">
                {(recipe.ingredients || []).map((ing, idx) => (
                  <li key={`${ing.name}-${idx}`}>
                    {[ing.amount, ing.unit, ing.name].filter(Boolean).join(' ')}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="font-medium mb-2">{t('instructions')}</h3>
              <ol className="text-sm space-y-2 list-decimal pl-4">
                {(recipe.instructions || []).map((stepText, idx) => (
                  <li key={`${idx}-${stepText.slice(0, 12)}`}>{stepText}</li>
                ))}
              </ol>
            </div>

            <div className="flex flex-wrap justify-between gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => setStep(3)} disabled={saving}>
                {t('back')}
              </Button>
              <div className="flex gap-2">
                <Link to="/recipes/new">
                  <Button type="button" variant="outline">
                    {t('createManually')}
                  </Button>
                </Link>
                <Button
                  type="button"
                  className="rounded-full"
                  onClick={handleSave}
                  disabled={saving}
                  data-testid="store-meal-save"
                >
                  {saving ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Save className="w-4 h-4 mr-2" />
                  )}
                  {t('saveRecipe')}
                </Button>
              </div>
            </div>
          </motion.section>
        )}
      </div>
    </Layout>
  );
};

export default RecreateStoreMeal;
