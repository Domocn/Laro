import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { recipeApi, preferencesApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { Label } from '../components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { CATEGORIES, getImageUrl } from '../lib/utils';
import { 
  Plus, 
  Trash2, 
  Upload, 
  ArrowLeft,
  Loader2,
  GripVertical,
  X
} from 'lucide-react';
import { toast } from 'sonner';
import { useLanguage } from '../context/LanguageContext';
import { VetoReplacementBanner } from '../components/VetoReplacementBanner';
import { normalizeIngredient } from '../lib/parseIngredientLine';

const emptyIngredient = { name: '', amount: '', unit: '' };

export const RecipeForm = () => {
  const { t } = useLanguage();
  const { id } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const isEditing = !!id;

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploadingImage, setUploadingImage] = useState(false);
  
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('Other');
  const [prepTime, setPrepTime] = useState('');
  const [cookTime, setCookTime] = useState('');
  const [servings, setServings] = useState('4');
  const [tags, setTags] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [ingredients, setIngredients] = useState([{ ...emptyIngredient }]);
  const [instructions, setInstructions] = useState(['']);

  useEffect(() => {
    if (isEditing) {
      loadRecipe();
      return;
    }
    // New recipe: seed servings / cook time from user preferences
    preferencesApi
      .get()
      .then((res) => {
        const prefs = res.data || {};
        if (prefs.defaultServings) setServings(String(prefs.defaultServings));
        if (prefs.defaultCookingTime) setCookTime(String(prefs.defaultCookingTime));
      })
      .catch(() => {});
  }, [id]);

  // Grow instruction textareas to fit imported / loaded step text
  useEffect(() => {
    const root = document.querySelector('[data-testid="instructions-inputs"]');
    if (!root) return;
    root.querySelectorAll('textarea').forEach((el) => {
      el.style.height = 'auto';
      el.style.height = `${el.scrollHeight}px`;
    });
  }, [instructions, loading]);

  const loadRecipe = async () => {
    setLoading(true);
    try {
      const res = await recipeApi.getOne(id);
      const recipe = res.data;
      setTitle(recipe.title);
      setDescription(recipe.description || '');
      setCategory(recipe.category);
      setPrepTime(recipe.prep_time?.toString() || '');
      setCookTime(recipe.cook_time?.toString() || '');
      setServings(recipe.servings?.toString() || '4');
      setTags(recipe.tags?.join(', ') || '');
      setImageUrl(recipe.image_url || '');
      setIngredients(
        recipe.ingredients.length
          ? recipe.ingredients.map((ing) => normalizeIngredient(ing))
          : [{ ...emptyIngredient }]
      );
      setInstructions(recipe.instructions.length ? recipe.instructions : ['']);
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastLoadRecipeFailed'));
      navigate('/recipes');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!title.trim()) {
      toast.error(t('toastEnterRecipeTitle'));
      return;
    }
    
    const filteredIngredients = ingredients
      .map((ing) => normalizeIngredient(ing))
      .filter((i) => i.name.trim());
    if (filteredIngredients.length === 0) {
      toast.error(t('toastAddOneIngredient'));
      return;
    }
    
    const filteredInstructions = instructions.filter(i => i.trim());
    if (filteredInstructions.length === 0) {
      toast.error(t('toastAddOneInstruction'));
      return;
    }

    setSaving(true);
    
    const recipeData = {
      title: title.trim(),
      description: description.trim(),
      category,
      prep_time: parseInt(prepTime) || 0,
      cook_time: parseInt(cookTime) || 0,
      servings: parseInt(servings) || 4,
      tags: tags.split(',').map(tag => tag.trim()).filter(Boolean),
      image_url: imageUrl,
      ingredients: filteredIngredients,
      instructions: filteredInstructions,
    };

    try {
      if (isEditing) {
        await recipeApi.update(id, recipeData);
        toast.success(t('toastRecipeUpdated'));
      } else {
        const res = await recipeApi.create(recipeData);
        toast.success(t('toastRecipeCreated'));
        navigate(`/recipes/${res.data.id}`);
        return;
      }
      navigate(`/recipes/${id}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || (isEditing ? t('toastUpdateRecipeFailed') : t('toastCreateRecipeFailed')));
    } finally {
      setSaving(false);
    }
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!isEditing) {
      // For new recipes, we need to create the recipe first
      toast.error(t('toastSaveRecipeFirstForImage'));
      return;
    }

    setUploadingImage(true);
    try {
      const res = await recipeApi.uploadImage(id, file);
      setImageUrl(res.data.image_url);
      toast.success(t('toastImageUploaded'));
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastUploadImageFailed'));
    } finally {
      setUploadingImage(false);
    }
  };

  const addIngredient = () => {
    setIngredients([...ingredients, { ...emptyIngredient }]);
  };

  const removeIngredient = (index) => {
    if (ingredients.length > 1) {
      setIngredients(ingredients.filter((_, i) => i !== index));
    }
  };

  const updateIngredient = (index, field, value) => {
    const updated = [...ingredients];
    updated[index] = { ...updated[index], [field]: value };
    setIngredients(updated);
  };

  const addInstruction = () => {
    setInstructions([...instructions, '']);
  };

  const removeInstruction = (index) => {
    if (instructions.length > 1) {
      setInstructions(instructions.filter((_, i) => i !== index));
    }
  };

  const updateInstruction = (index, value) => {
    const updated = [...instructions];
    updated[index] = value;
    setInstructions(updated);
  };

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-laro" />
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="max-w-3xl mx-auto" data-testid="recipe-form">
        {/* Back Button */}
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
          <h1 className="font-heading text-2xl font-bold mb-6">
            {isEditing ? t('editRecipeTitle') : t('createNewRecipeTitle')}
          </h1>

          <form onSubmit={handleSubmit} className="space-y-8">
            {/* Image */}
            <div>
              <Label className="mb-2 block">{t('recipeImageLabel')}</Label>
              <div 
                className="relative aspect-video rounded-xl border-2 border-dashed border-border bg-cream-subtle overflow-hidden cursor-pointer hover:border-laro transition-colors"
                onClick={() => isEditing && fileInputRef.current?.click()}
              >
                {imageUrl ? (
                  <img 
                    src={getImageUrl(imageUrl, { id, title, category })} 
                    alt={t('recipe')} 
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="absolute inset-0 flex flex-col items-center justify-center text-muted-foreground">
                    <Upload className="w-8 h-8 mb-2" aria-hidden="true" />
                    <p className="text-sm">{isEditing ? t('clickToUploadImage') : t('saveRecipeFirstToUpload')}</p>
                  </div>
                )}
                {uploadingImage && (
                  <div className="absolute inset-0 bg-white/80 dark:bg-black/60 flex items-center justify-center">
                    <Loader2 className="w-8 h-8 animate-spin text-laro" aria-hidden="true" />
                  </div>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                onChange={handleImageUpload}
                className="hidden"
              />
              <p className="text-xs text-muted-foreground mt-2">{t('orPasteImageUrl')}</p>
              <Input
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                placeholder={t('imageUrlPlaceholder')}
                className="mt-1 rounded-xl"
              />
            </div>

            {/* Basic Info */}
            <div className="grid gap-4 md:grid-cols-2">
              <div className="md:col-span-2">
                <Label htmlFor="title">{t('recipeTitleLabel')}</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder={t('recipeTitlePlaceholder')}
                  className="mt-1 rounded-xl"
                  required
                  data-testid="recipe-title-input"
                />
              </div>

              <div className="md:col-span-2">
                <Label htmlFor="description">{t('descriptionLabel')}</Label>
                <Textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder={t('recipeDescPlaceholder')}
                  className="mt-1 rounded-xl resize-none"
                  rows={3}
                />
              </div>

              <div>
                <Label>{t('category')}</Label>
                <Select value={category} onValueChange={setCategory}>
                  <SelectTrigger className="mt-1 rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {CATEGORIES.filter(c => c !== 'All').map((cat) => (
                      <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="servings">{t('servings')}</Label>
                <Input
                  id="servings"
                  type="number"
                  min="1"
                  value={servings}
                  onChange={(e) => setServings(e.target.value)}
                  className="mt-1 rounded-xl"
                />
              </div>

              <div>
                <Label htmlFor="prepTime">{t('prepTimeMinLabel')}</Label>
                <Input
                  id="prepTime"
                  type="number"
                  min="0"
                  value={prepTime}
                  onChange={(e) => setPrepTime(e.target.value)}
                  className="mt-1 rounded-xl"
                />
              </div>

              <div>
                <Label htmlFor="cookTime">{t('cookTimeMinLabel')}</Label>
                <Input
                  id="cookTime"
                  type="number"
                  min="0"
                  value={cookTime}
                  onChange={(e) => setCookTime(e.target.value)}
                  className="mt-1 rounded-xl"
                />
              </div>

              <div className="md:col-span-2">
                <Label htmlFor="tags">{t('tagsCommaSeparated')}</Label>
                <Input
                  id="tags"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder={t('tagsPlaceholderExample')}
                  className="mt-1 rounded-xl"
                />
              </div>
            </div>

            {/* Ingredients */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <Label>{t('ingredientsRequired')}</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addIngredient}
                  className="rounded-full"
                >
                  <Plus className="w-4 h-4 mr-1" aria-hidden="true" />
                  {t('add')}
                </Button>
              </div>
              <div className="space-y-2" data-testid="ingredients-inputs">
                {ingredients.map((ing, idx) => (
                  <div key={idx} className="flex flex-wrap gap-2 items-center">
                    <Input
                      value={ing.amount}
                      onChange={(e) => updateIngredient(idx, 'amount', e.target.value)}
                      placeholder={t('amountPlaceholder')}
                      className="w-20 shrink-0 rounded-xl"
                    />
                    <Input
                      value={ing.unit}
                      onChange={(e) => updateIngredient(idx, 'unit', e.target.value)}
                      placeholder={t('unitPlaceholderShort')}
                      className="w-20 sm:w-24 shrink-0 rounded-xl"
                    />
                    <Input
                      value={ing.name}
                      onChange={(e) => updateIngredient(idx, 'name', e.target.value)}
                      placeholder={t('ingredientNamePlaceholder')}
                      className="min-w-[12rem] flex-1 basis-full sm:basis-0 rounded-xl"
                      title={ing.name || undefined}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeIngredient(idx)}
                      className="text-muted-foreground hover:text-destructive shrink-0"
                      aria-label={t('removeIngredientAria')}
                    >
                      <X className="w-4 h-4" aria-hidden="true" />
                    </Button>
                  </div>
                ))}
              </div>
              <VetoReplacementBanner
                className="mt-3"
                ingredients={ingredients}
                onApply={(index, suggestionName) => updateIngredient(index, 'name', suggestionName)}
              />
            </div>

            {/* Instructions */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <Label>{t('instructionsRequired')}</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={addInstruction}
                  className="rounded-full"
                >
                  <Plus className="w-4 h-4 mr-1" aria-hidden="true" />
                  {t('addStep')}
                </Button>
              </div>
              <div className="space-y-3" data-testid="instructions-inputs">
                {instructions.map((step, idx) => (
                  <div key={idx} className="flex gap-3 items-start">
                    <span className="flex-shrink-0 w-8 h-8 rounded-full bg-laro text-white flex items-center justify-center font-semibold text-sm mt-1">
                      {idx + 1}
                    </span>
                    <Textarea
                      value={step}
                      onChange={(e) => {
                        updateInstruction(idx, e.target.value);
                        e.target.style.height = 'auto';
                        e.target.style.height = `${e.target.scrollHeight}px`;
                      }}
                      onFocus={(e) => {
                        e.target.style.height = 'auto';
                        e.target.style.height = `${e.target.scrollHeight}px`;
                      }}
                      placeholder={t('stepPlaceholder', { n: idx + 1 })}
                      className="flex-1 min-w-0 rounded-xl resize-none overflow-hidden"
                      rows={2}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeInstruction(idx)}
                      className="text-muted-foreground hover:text-destructive mt-1"
                      aria-label={t('removeInstructionStepAria')}
                    >
                      <X className="w-4 h-4" aria-hidden="true" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>

            {/* Submit */}
            <div className="flex gap-3 pt-4">
              <Button
                type="submit"
                className="rounded-full bg-laro hover:bg-laro-dark px-8"
                disabled={saving}
                data-testid="save-recipe-btn"
              >
                {saving ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" aria-hidden="true" />
                ) : null}
                {isEditing ? t('saveChanges') : t('createRecipe')}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="rounded-full"
                onClick={() => navigate(-1)}
              >
                {t('cancel')}
              </Button>
            </div>
          </form>
        </motion.div>
      </div>
    </Layout>
  );
};
