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
  ArrowUp,
  ArrowDown,
  Loader2,
  GripVertical,
  X
} from 'lucide-react';
import { toast } from 'sonner';
import { useLanguage } from '../context/LanguageContext';
import { VetoReplacementBanner } from '../components/VetoReplacementBanner';
import { normalizeIngredient, parseIngredientLine } from '../lib/parseIngredientLine';
import { buildAdaptations } from '../lib/fodmap';
import {
  MAX_VERSIONS,
  getPageNotes,
  newVersionRow,
  rowsToVersions,
  versionsToRows,
  withPageNotes,
  withVersions,
} from '../lib/recipeVersions';
import {
  addEditorSection,
  fromEditorSections,
  groupHeading,
  moveEditorSection,
  removeEditorSection,
  renameEditorSection,
  toEditorSections,
} from '../lib/ingredientGroups';

const emptyIngredient = { name: '', amount: '', unit: '', sectionId: null };

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
  const [tags, setTags] = useState([]);
  const [tagInput, setTagInput] = useState('');
  const [allTags, setAllTags] = useState([]); // existing tags across the library, for suggestions
  const [tagFocused, setTagFocused] = useState(false);
  const [imageUrl, setImageUrl] = useState('');
  // Ingredient rows carry a sectionId; sections ("For the sauce") are [{ id, name }] in order.
  const [ingredients, setIngredients] = useState([{ ...emptyIngredient }]);
  const [sections, setSections] = useState([]);
  const [instructions, setInstructions] = useState(['']);
  // Optional Low FODMAP adaptation (recipe.adaptations.low_fodmap)
  const [fodmapSwaps, setFodmapSwaps] = useState([]);
  const [fodmapNotes, setFodmapNotes] = useState('');
  const [fodmapOpen, setFodmapOpen] = useState(false);
  // Named versions (recipe.adaptations.versions) + cookbook "Notes & tips" (adaptations.page_notes)
  const [versionRows, setVersionRows] = useState([]);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [pageNotesText, setPageNotesText] = useState('');
  const adaptationsRef = useRef(null);

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

  // Load existing tags across the user's recipes for add-tag suggestions.
  useEffect(() => {
    let cancelled = false;
    recipeApi
      .getAll()
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.recipes || []);
        const seen = new Map(); // lowercase -> canonical form (most common casing)
        const count = new Map();
        list.forEach((r) => (r.tags || []).forEach((raw) => {
          const t = String(raw || '').trim();
          if (!t) return;
          const k = t.toLowerCase();
          count.set(t, (count.get(t) || 0) + 1);
          if (!seen.has(k) || count.get(t) > count.get(seen.get(k))) seen.set(k, t);
        }));
        if (!cancelled) setAllTags([...seen.values()].sort((a, b) => a.localeCompare(b)));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  // Add a tag, snapping to an existing tag's casing so near-duplicates aren't created.
  const commitTag = (raw) => {
    const v = String(raw || '').trim();
    if (!v) return;
    const existing = allTags.find((t) => t.toLowerCase() === v.toLowerCase());
    const value = existing || v;
    setTags((prev) => (prev.some((t) => t.toLowerCase() === value.toLowerCase()) ? prev : [...prev, value]));
    setTagInput('');
  };

  const tagSuggestions = tagInput.trim()
    ? allTags
        .filter((t) => t.toLowerCase().includes(tagInput.trim().toLowerCase())
          && !tags.some((x) => x.toLowerCase() === t.toLowerCase()))
        .slice(0, 8)
    : [];

  // Grow instruction textareas to fit imported / loaded step text
  useEffect(() => {
    const root = document.querySelector('[data-testid="instructions-inputs"]');
    if (!root) return;
    root.querySelectorAll('textarea').forEach((el) => {
      el.style.height = 'auto';
      el.style.height = `${el.scrollHeight}px`;
    });
  }, [instructions, loading]);

  // Fields the form doesn't edit but must round-trip so saving doesn't wipe them.
  const preservedRef = useRef({});

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
      setTags(Array.isArray(recipe.tags) ? recipe.tags.filter(Boolean) : []);
      setImageUrl(recipe.image_url || '');
      preservedRef.current = {
        nutrition: recipe.nutrition ?? null,
        dietary_tags: Array.isArray(recipe.dietary_tags) ? recipe.dietary_tags : [],
        difficulty: recipe.difficulty ?? null,
      };
      const editor = toEditorSections((recipe.ingredients || []).map((ing) => normalizeIngredient(ing)));
      setIngredients(editor.rows.length ? editor.rows : [{ ...emptyIngredient }]);
      setSections(editor.sections);
      setInstructions(recipe.instructions?.length ? recipe.instructions : ['']);
      adaptationsRef.current = recipe.adaptations || null;
      const lf = recipe.adaptations?.low_fodmap;
      setFodmapSwaps(Array.isArray(lf?.swaps) ? lf.swaps.map((sw) => ({ from: sw.from || '', to: sw.to || '' })) : []);
      setFodmapNotes(lf?.notes || '');
      setFodmapOpen(!!(lf?.swaps?.length || lf?.notes));
      const rows = versionsToRows(recipe);
      setVersionRows(rows);
      setVersionsOpen(rows.length > 0);
      setPageNotesText(getPageNotes(recipe).join('\n'));
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
    
    const filteredIngredients = fromEditorSections({ rows: ingredients, sections })
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
      tags: [...tags, tagInput]
        .map(tag => (tag || '').trim())
        .filter(Boolean)
        .filter((t, i, a) => a.findIndex(x => x.toLowerCase() === t.toLowerCase()) === i),
      image_url: imageUrl,
      ingredients: filteredIngredients,
      instructions: filteredInstructions,
      ...(isEditing ? preservedRef.current : {}),
    };
    const adaptations = withPageNotes(
      withVersions(
        buildAdaptations(adaptationsRef.current, fodmapSwaps, fodmapNotes),
        rowsToVersions(versionRows, parseIngredientLine),
      ),
      pageNotesText,
    );
    // Always send on edit so clearing the section removes it; only send on create when filled in.
    if (isEditing || adaptations) recipeData.adaptations = adaptations;

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

  const addIngredient = (sectionId = null) => {
    setIngredients([...ingredients, { ...emptyIngredient, sectionId }]);
  };

  const applySections = (next) => {
    setIngredients(next.rows);
    setSections(next.sections);
  };

  const addSection = () => {
    const next = addEditorSection({ rows: ingredients, sections }, emptyIngredient);
    applySections(next);
    const id = next.sections[next.sections.length - 1].id;
    setTimeout(() => document.getElementById(`section-name-${id}`)?.focus(), 0);
  };

  const removeSection = (id) => {
    applySections(removeEditorSection({ rows: ingredients, sections }, id));
    toast(t('ingredientSectionRemoved'));
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
                role={isEditing ? 'button' : undefined}
                tabIndex={isEditing ? 0 : undefined}
                aria-label={isEditing ? t('recipeImageLabel') : undefined}
                onKeyDown={(e) => {
                  if (!isEditing || e.target !== e.currentTarget) return;
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    fileInputRef.current?.click();
                  }
                }}
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
                <Label htmlFor="tag-input">{t('tags') || 'Tags'}</Label>
                <div className="relative">
                  <div
                    className="mt-1 flex flex-wrap gap-2 items-center rounded-xl border border-input bg-background p-2 min-h-[44px] focus-within:ring-2 focus-within:ring-laro/40 cursor-text"
                    onClick={() => document.getElementById('tag-input')?.focus()}
                  >
                    {tags.map((tag, i) => (
                      <span
                        key={`${tag}-${i}`}
                        className="inline-flex items-center gap-1 rounded-full bg-laro/10 text-laro px-2.5 py-1 text-sm"
                      >
                        {tag}
                        <button
                          type="button"
                          aria-label={`Remove ${tag}`}
                          onClick={(e) => { e.stopPropagation(); setTags(tags.filter((_, j) => j !== i)); }}
                          className="hover:text-red-500"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </span>
                    ))}
                    <input
                      id="tag-input"
                      value={tagInput}
                      autoComplete="off"
                      onChange={(e) => setTagInput(e.target.value)}
                      onFocus={() => setTagFocused(true)}
                      onKeyDown={(e) => {
                        if ((e.key === 'Enter' || e.key === ',') && tagInput.trim()) {
                          e.preventDefault();
                          commitTag(tagInput);
                        } else if (e.key === 'Backspace' && !tagInput && tags.length) {
                          setTags(tags.slice(0, -1));
                        }
                      }}
                      onBlur={() => { commitTag(tagInput); setTimeout(() => setTagFocused(false), 150); }}
                      placeholder={tags.length ? '' : (t('tagsPlaceholderExample') || 'Add a tag…')}
                      className="flex-1 min-w-[120px] bg-transparent outline-none text-sm px-1 py-1"
                    />
                  </div>
                  {tagFocused && tagSuggestions.length > 0 && (
                    <div className="absolute z-20 left-0 right-0 mt-1 max-h-52 overflow-auto rounded-xl border border-input bg-white dark:bg-card shadow-lg">
                      {tagSuggestions.map((s) => (
                        <button
                          key={s}
                          type="button"
                          onMouseDown={(e) => { e.preventDefault(); commitTag(s); }}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-laro/10"
                        >
                          {s}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <p className="text-xs text-muted-foreground mt-1">Type to search your tags · Enter or comma to add · click × to remove</p>
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
                  onClick={() => addIngredient()}
                  className="rounded-full"
                >
                  <Plus className="w-4 h-4 mr-1" aria-hidden="true" />
                  {t('add')}
                </Button>
              </div>
              <div className="space-y-2" data-testid="ingredients-inputs">
                {(() => {
                  const sectionIds = new Set(sections.map((s) => s.id));
                  const row = (ing, idx) => (
                  <div key={idx} className="flex flex-wrap gap-2 items-center" data-testid="ingredient-row">
                    <Input
                      value={ing.amount}
                      onChange={(e) => updateIngredient(idx, 'amount', e.target.value)}
                      placeholder={t('amountPlaceholder')}
                      className="w-32 sm:w-36 shrink-0 rounded-xl"
                      title={ing.amount || undefined}
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
                  );
                  const indexed = ingredients.map((ing, idx) => ({ ing, idx }));
                  return (
                    <>
                      {indexed.filter(({ ing }) => !sectionIds.has(ing.sectionId)).map(({ ing, idx }) => row(ing, idx))}
                      {/* Sections: ungrouped ingredients above, then each named part of the dish */}
                      {sections.map((section, sIdx) => {
                        const label = section.name.trim() || t('ingredientSectionUnnamed');
                        const rows = indexed.filter(({ ing }) => ing.sectionId === section.id);
                        return (
                          <div
                            key={section.id}
                            role="group"
                            aria-labelledby={`section-name-label-${section.id}`}
                            className="mt-4 rounded-xl border border-input bg-cream-subtle/50 dark:bg-muted/40 p-3 space-y-2"
                            data-testid="ingredient-section"
                          >
                            <Label id={`section-name-label-${section.id}`} htmlFor={`section-name-${section.id}`} className="text-sm">
                              {t('ingredientSectionNameLabel')}
                            </Label>
                            <div className="flex flex-wrap gap-2 items-center">
                              <Input
                                id={`section-name-${section.id}`}
                                value={section.name}
                                onChange={(e) => applySections(renameEditorSection({ rows: ingredients, sections }, section.id, e.target.value))}
                                placeholder={t('ingredientSectionNamePlaceholder')}
                                className="min-w-[10rem] flex-1 rounded-xl font-semibold h-11"
                                maxLength={80}
                                data-testid="ingredient-section-name"
                              />
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="h-11 w-11 shrink-0 rounded-xl"
                                disabled={sIdx === 0}
                                onClick={() => applySections(moveEditorSection({ rows: ingredients, sections }, section.id, -1))}
                                aria-label={t('ingredientSectionMoveUp', { name: label })}
                                title={t('ingredientSectionMoveUp', { name: label })}
                              >
                                <ArrowUp className="w-4 h-4" aria-hidden="true" />
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                size="icon"
                                className="h-11 w-11 shrink-0 rounded-xl"
                                disabled={sIdx === sections.length - 1}
                                onClick={() => applySections(moveEditorSection({ rows: ingredients, sections }, section.id, 1))}
                                aria-label={t('ingredientSectionMoveDown', { name: label })}
                                title={t('ingredientSectionMoveDown', { name: label })}
                              >
                                <ArrowDown className="w-4 h-4" aria-hidden="true" />
                              </Button>
                              <Button
                                type="button"
                                variant="ghost"
                                className="h-11 shrink-0 rounded-xl text-muted-foreground hover:text-destructive"
                                onClick={() => removeSection(section.id)}
                                aria-label={t('ingredientSectionRemoveAria', { name: label })}
                                data-testid="ingredient-section-remove"
                              >
                                <Trash2 className="w-4 h-4 mr-1" aria-hidden="true" />
                                {t('ingredientSectionRemove')}
                              </Button>
                            </div>
                            {section.name.trim() && (
                              <p className="text-xs text-muted-foreground">
                                {t('ingredientSectionPreview', { heading: groupHeading(section.name.trim(), t) })}
                              </p>
                            )}
                            {rows.length === 0 && (
                              <p className="text-sm text-muted-foreground">{t('ingredientSectionEmpty')}</p>
                            )}
                            {rows.map(({ ing, idx }) => row(ing, idx))}
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() => addIngredient(section.id)}
                              className="h-11 rounded-full"
                              data-testid="ingredient-section-add-ingredient"
                            >
                              <Plus className="w-4 h-4 mr-1" aria-hidden="true" />
                              {t('ingredientSectionAddIngredient')}
                            </Button>
                          </div>
                        );
                      })}
                    </>
                  );
                })()}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <Button
                  type="button"
                  variant="outline"
                  onClick={addSection}
                  className="h-11 rounded-full"
                  data-testid="add-ingredient-section"
                >
                  <Plus className="w-4 h-4 mr-1" aria-hidden="true" />
                  {t('ingredientSectionAdd')}
                </Button>
                <p className="text-xs text-muted-foreground flex-1 min-w-[12rem]">{t('ingredientSectionHint')}</p>
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

            {/* Low FODMAP adaptation (optional) */}
            <details
              className="rounded-xl border border-input px-4 py-3"
              open={fodmapOpen}
              onToggle={(e) => setFodmapOpen(e.currentTarget.open)}
              data-testid="fodmap-edit"
            >
              <summary className="cursor-pointer font-medium text-sm">{t('fodmapSectionTitle')}</summary>
              <p className="text-xs text-muted-foreground mt-2">{t('fodmapSectionHint')}</p>
              <div className="space-y-2 mt-3">
                {fodmapSwaps.map((sw, idx) => (
                  <div key={idx} className="flex flex-wrap gap-2 items-center">
                    <Input
                      value={sw.from}
                      onChange={(e) => setFodmapSwaps((prev) => prev.map((x, i) => (i === idx ? { ...x, from: e.target.value } : x)))}
                      placeholder={t('fodmapSwapFromPlaceholder')}
                      aria-label={t('fodmapSwapFrom')}
                      className="min-w-[8rem] flex-1 rounded-xl"
                    />
                    <span aria-hidden="true" className="text-muted-foreground">→</span>
                    <Input
                      value={sw.to}
                      onChange={(e) => setFodmapSwaps((prev) => prev.map((x, i) => (i === idx ? { ...x, to: e.target.value } : x)))}
                      placeholder={t('fodmapSwapToPlaceholder')}
                      aria-label={t('fodmapSwapTo')}
                      className="min-w-[8rem] flex-1 rounded-xl"
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => setFodmapSwaps((prev) => prev.filter((_, i) => i !== idx))}
                      className="text-muted-foreground hover:text-destructive shrink-0"
                      aria-label={t('fodmapRemoveSwap')}
                    >
                      <X className="w-4 h-4" aria-hidden="true" />
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setFodmapSwaps((prev) => [...prev, { from: '', to: '' }])}
                  className="rounded-full"
                >
                  <Plus className="w-4 h-4 mr-1" aria-hidden="true" />
                  {t('fodmapAddSwap')}
                </Button>
              </div>
              <div className="mt-3">
                <Label htmlFor="fodmap-notes">{t('fodmapNotesLabel')}</Label>
                <Textarea
                  id="fodmap-notes"
                  value={fodmapNotes}
                  onChange={(e) => setFodmapNotes(e.target.value)}
                  placeholder={t('fodmapNotesPlaceholder')}
                  className="mt-1 rounded-xl"
                  rows={2}
                />
              </div>
            </details>

            {/* Named versions (optional): same dish, different ingredients / steps */}
            <details
              className="rounded-xl border border-input px-4 py-3"
              open={versionsOpen}
              onToggle={(e) => setVersionsOpen(e.currentTarget.open)}
              data-testid="versions-edit"
            >
              <summary className="cursor-pointer font-medium text-sm">{t('versionsSectionTitle')}</summary>
              <p className="text-xs text-muted-foreground mt-2">{t('versionsSectionHint')}</p>
              <div className="space-y-4 mt-3">
                {versionRows.map((row, idx) => {
                  const update = (patch) => setVersionRows((prev) => prev.map((x, i) => (i === idx ? { ...x, ...patch } : x)));
                  return (
                    <div key={idx} className="rounded-xl bg-cream-subtle dark:bg-muted p-3 space-y-2">
                      <div className="flex gap-2 items-center">
                        <Input
                          value={row.name}
                          onChange={(e) => update({ name: e.target.value })}
                          placeholder={t('versionNamePlaceholder')}
                          aria-label={t('versionNameLabel')}
                          className="flex-1 rounded-xl"
                          maxLength={80}
                        />
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => setVersionRows((prev) => prev.filter((_, i) => i !== idx))}
                          className="text-muted-foreground hover:text-destructive shrink-0"
                          aria-label={t('versionRemove', { name: row.name || t('versionNameLabel') })}
                        >
                          <X className="w-4 h-4" aria-hidden="true" />
                        </Button>
                      </div>
                      <Label htmlFor={`version-ings-${idx}`} className="text-xs">{t('versionIngredientsLabel')}</Label>
                      <Textarea
                        id={`version-ings-${idx}`}
                        value={row.ingredientsText}
                        onChange={(e) => update({ ingredientsText: e.target.value })}
                        className="rounded-xl font-mono text-sm"
                        rows={5}
                      />
                      <Label htmlFor={`version-steps-${idx}`} className="text-xs">{t('versionStepsLabel')}</Label>
                      <Textarea
                        id={`version-steps-${idx}`}
                        value={row.instructionsText}
                        onChange={(e) => update({ instructionsText: e.target.value })}
                        className="rounded-xl text-sm"
                        rows={5}
                      />
                      <Input
                        value={row.notes}
                        onChange={(e) => update({ notes: e.target.value })}
                        placeholder={t('versionNotesPlaceholder')}
                        aria-label={t('versionNotesLabel')}
                        className="rounded-xl"
                      />
                    </div>
                  );
                })}
                {versionRows.length < MAX_VERSIONS && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setVersionRows((prev) => [
                        ...prev,
                        {
                          ...newVersionRow(
                            '',
                            fromEditorSections({ rows: ingredients, sections }).filter((i) => String(i?.name || '').trim()),
                            instructions.filter((s) => String(s || '').trim()),
                          ),
                          name: '',
                        },
                      ])
                    }
                    className="rounded-full"
                  >
                    <Plus className="w-4 h-4 mr-1" aria-hidden="true" />
                    {t('versionAdd')}
                  </Button>
                )}
              </div>
            </details>

            {/* Notes & tips (timing, storage, to serve, …) */}
            <div>
              <Label htmlFor="page-notes">{t('pageNotesTitle')}</Label>
              <p className="text-xs text-muted-foreground mt-1">{t('pageNotesHint')}</p>
              <Textarea
                id="page-notes"
                value={pageNotesText}
                onChange={(e) => setPageNotesText(e.target.value)}
                placeholder={t('pageNotesPlaceholder')}
                className="mt-1 rounded-xl"
                rows={3}
                data-testid="page-notes-edit"
              />
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
