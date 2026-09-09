import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { CookMode } from '../components/CookMode';
import { NutritionCalculator } from '../components/NutritionCalculator';
import { RecipeVersions } from '../components/RecipeVersions';
import { RecipeReviews } from '../components/RecipeReviews';
import { CostCalculator } from '../components/CostCalculator';
import { ShareRecipeModal } from '../components/ShareRecipeModal';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { useAccessibility, confirmDestructive } from '../context/AccessibilityContext';
import { useChat } from '../context/ChatContext';
import {
  useLiveRefreshContext,
  useLiveRefreshEvent,
  EventType,
} from '../hooks/useLiveRefresh';
import { recipeApi, mealPlanApi, shoppingListApi, cookingApi, preferencesApi } from '../lib/api';
import { convertUnit } from '../lib/unitConversions';
import { enrichStepWithAmounts } from '../lib/cookModeSteps';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { VetoReplacementBanner } from '../components/VetoReplacementBanner';
import { IngredientSubstituteButton } from '../components/IngredientSubstituteButton';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { Calendar } from '../components/ui/calendar';
import { Input } from '../components/ui/input';
import { Textarea } from '../components/ui/textarea';
import { getImageUrl, formatTime, MEAL_TYPES } from '../lib/utils';
import { wantsFamilyOneMeal } from '../lib/familyMeal';
import {
  Clock,
  Users,
  Edit,
  Trash2,
  CalendarPlus,
  ShoppingCart,
  ArrowLeft,
  ChefHat,
  Loader2,
  Share2,
  Copy,
  Check,
  Download,
  FileText,
  Link as LinkIcon,
  Image,
  Heart,
  Printer,
  Minus,
  Plus as PlusIcon,
  Play,
  AlertTriangle,
  Star,
  Leaf,
  Wheat,
  CheckCircle2
} from 'lucide-react';
import { toast } from 'sonner';
import { format, formatDistanceToNow, parseISO } from 'date-fns';

const MEAL_TYPE_KEYS = {
  Breakfast: 'breakfast',
  Lunch: 'lunch',
  Dinner: 'dinner',
  Snack: 'snack',
};

export const RecipeDetail = () => {
  const { id } = useParams();
  const { t } = useLanguage();
  const { confirmActions } = useAccessibility();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { setRecipeContext, clearRecipeContext } = useChat();
  const liveRefresh = useLiveRefreshContext();
  const [recipe, setRecipe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [showMealDialog, setShowMealDialog] = useState(false);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [mealType, setMealType] = useState('Dinner');
  const [addingToMealPlan, setAddingToMealPlan] = useState(false);
  const [addingToShopping, setAddingToShopping] = useState(false);
  const [showShareDialog, setShowShareDialog] = useState(false);
  const [measurementUnit, setMeasurementUnit] = useState('metric');
  const [showNutrition, setShowNutrition] = useState(true);
  const [familyMode, setFamilyMode] = useState(false);
  const [generatingCard, setGeneratingCard] = useState(false);
  const [isFavorite, setIsFavorite] = useState(false);
  const [togglingFavorite, setTogglingFavorite] = useState(false);
  const [scaledServings, setScaledServings] = useState(null);
  const [scaledIngredients, setScaledIngredients] = useState(null);
  const [showCookMode, setShowCookMode] = useState(false);
  const [allergenWarnings, setAllergenWarnings] = useState([]);
  const [userRating, setUserRating] = useState(null);
  const [personalNotes, setPersonalNotes] = useState('');
  const [hoverRating, setHoverRating] = useState(0);
  const [savingRating, setSavingRating] = useState(false);
  const [savingNotes, setSavingNotes] = useState(false);
  const [markingCooked, setMarkingCooked] = useState(false);
  const recipeCardRef = useRef(null);

  // Generate formatted text for sharing (memoized)
  const generateRecipeText = useMemo(() => {
    if (!recipe) return '';

    let text = `🍳 ${recipe.title}\n`;
    text += `${'─'.repeat(30)}\n\n`;

    if (recipe.description) {
      text += `${recipe.description}\n\n`;
    }

    const totalTime = (recipe.prep_time || 0) + (recipe.cook_time || 0);
    text += `⏱️ ${formatTime(totalTime)} | 👥 ${recipe.servings} servings\n\n`;

    text += `📝 INGREDIENTS\n`;
    recipe.ingredients.forEach(ing => {
      text += `• ${ing.amount} ${ing.unit} ${ing.name}\n`;
    });

    text += `\n👨‍🍳 INSTRUCTIONS\n`;
    recipe.instructions.forEach((step, idx) => {
      text += `${idx + 1}. ${step}\n`;
    });

    text += `\n─────────────────────────────\n`;
    text += `Shared from Laro`;

    return text;
  }, [recipe]);

  const handleCopyAsText = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(generateRecipeText);
      toast.success(t('toastRecipeCopied'));
    } catch (error) {
      toast.error("Couldn't copy to clipboard. Please try again. (E-RD001)");
    }
  }, [generateRecipeText, t]);

  const handleDownloadCard = async () => {
    setGeneratingCard(true);
    
    try {
      // Create a canvas to generate the recipe card
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      
      // Card dimensions (Instagram story size for easy sharing)
      const width = 1080;
      const height = 1920;
      canvas.width = width;
      canvas.height = height;
      
      // Background
      ctx.fillStyle = '#FDFBF7';
      ctx.fillRect(0, 0, width, height);
      
      // Header background
      ctx.fillStyle = '#4A6741';
      ctx.fillRect(0, 0, width, 400);
      
      // Recipe image placeholder area
      ctx.fillStyle = '#E8F0E6';
      ctx.fillRect(40, 440, width - 80, 400);
      
      // Load and draw image if available
      if (recipe.image_url) {
        const img = new window.Image();
        img.crossOrigin = 'anonymous';
        img.src = getImageUrl(recipe.image_url, recipe);
        
        await new Promise((resolve) => {
          img.onload = () => {
            // Draw image with cover fit
            const aspectRatio = img.width / img.height;
            const targetAspect = (width - 80) / 400;
            let drawWidth, drawHeight, offsetX, offsetY;
            
            if (aspectRatio > targetAspect) {
              drawHeight = 400;
              drawWidth = drawHeight * aspectRatio;
              offsetX = 40 - (drawWidth - (width - 80)) / 2;
              offsetY = 440;
            } else {
              drawWidth = width - 80;
              drawHeight = drawWidth / aspectRatio;
              offsetX = 40;
              offsetY = 440 - (drawHeight - 400) / 2;
            }
            
            ctx.save();
            ctx.beginPath();
            ctx.rect(40, 440, width - 80, 400);
            ctx.clip();
            ctx.drawImage(img, offsetX, offsetY, drawWidth, drawHeight);
            ctx.restore();
            resolve();
          };
          img.onerror = resolve;
        });
      }
      
      // Title
      ctx.fillStyle = '#FFFFFF';
      ctx.font = 'bold 64px Manrope, sans-serif';
      ctx.textAlign = 'center';
      
      // Word wrap title
      const words = recipe.title.split(' ');
      let line = '';
      let y = 180;
      for (const word of words) {
        const testLine = line + word + ' ';
        if (ctx.measureText(testLine).width > width - 100) {
          ctx.fillText(line, width / 2, y);
          line = word + ' ';
          y += 70;
        } else {
          line = testLine;
        }
      }
      ctx.fillText(line, width / 2, y);
      
      // Meta info
      ctx.font = '36px Sora, system-ui, sans-serif';
      ctx.fillStyle = '#E8F0E6';
      const totalTime = (recipe.prep_time || 0) + (recipe.cook_time || 0);
      ctx.fillText(`${formatTime(totalTime)} • ${recipe.servings} servings`, width / 2, 340);
      
      // Ingredients section
      ctx.textAlign = 'left';
      ctx.fillStyle = '#2F5442';
      ctx.font = 'bold 42px Fraunces, Georgia, serif';
      ctx.fillText('Ingredients', 60, 920);
      
      ctx.fillStyle = '#1A2922';
      ctx.font = '32px Sora, system-ui, sans-serif';
      let ingredientY = 980;
      recipe.ingredients.slice(0, 10).forEach(ing => {
        ctx.fillText(`• ${ing.amount} ${ing.unit} ${ing.name}`, 60, ingredientY);
        ingredientY += 50;
      });
      if (recipe.ingredients.length > 10) {
        ctx.fillStyle = '#5C6860';
        ctx.fillText(`+ ${recipe.ingredients.length - 10} more ingredients...`, 60, ingredientY);
      }
      
      // Instructions section
      ctx.fillStyle = '#2F5442';
      ctx.font = 'bold 42px Fraunces, Georgia, serif';
      ctx.fillText('Instructions', 60, ingredientY + 80);
      
      ctx.fillStyle = '#1A2922';
      ctx.font = '30px Sora, system-ui, sans-serif';
      let instructionY = ingredientY + 140;
      recipe.instructions.slice(0, 6).forEach((step, idx) => {
        const shortStep = step.length > 60 ? step.substring(0, 60) + '...' : step;
        ctx.fillText(`${idx + 1}. ${shortStep}`, 60, instructionY);
        instructionY += 50;
      });
      if (recipe.instructions.length > 6) {
        ctx.fillStyle = '#6B7C66';
        ctx.fillText(`+ ${recipe.instructions.length - 6} more steps...`, 60, instructionY);
      }
      
      // Footer
      ctx.fillStyle = '#4A6741';
      ctx.fillRect(0, height - 100, width, 100);
      ctx.fillStyle = '#FFFFFF';
      ctx.font = 'bold 32px Manrope, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('🍳 Made with Laro', width / 2, height - 40);
      
      // Download
      const dataUrl = canvas.toDataURL('image/png');
      const link = document.createElement('a');
      link.download = `${recipe.title.replace(/[^a-z0-9]/gi, '_')}_recipe.png`;
      link.href = dataUrl;
      link.click();
      
      toast.success(t('toastRecipeCardDownloaded'));
    } catch (error) {
      console.error('Failed to generate card:', error);
      toast.error("Couldn't generate the recipe card. Please try again. (E-RD002)");
    } finally {
      setGeneratingCard(false);
    }
  };

  useEffect(() => {
    loadRecipe();
    preferencesApi
      .get()
      .then((res) => {
        if (res.data?.measurementUnit) setMeasurementUnit(res.data.measurementUnit);
        if (res.data?.showNutrition !== undefined) setShowNutrition(!!res.data.showNutrition);
        setFamilyMode(wantsFamilyOneMeal(res.data || {}));
      })
      .catch(() => {});
  }, [id]);

  // Scope global AI chat to this recipe while the detail page is open
  useEffect(() => {
    if (recipe?.id) {
      setRecipeContext(recipe);
    }
    return () => clearRecipeContext();
  }, [recipe, setRecipeContext, clearRecipeContext]);

  const loadRecipe = async () => {
    try {
      const res = await recipeApi.getOne(id);
      setRecipe(res.data);
      setIsFavorite(res.data.is_favorite || false);
      setScaledServings(res.data.servings || 4);
      // Set allergen warnings from API response
      setAllergenWarnings(res.data.allergen_warnings || []);

      // Load user's personal rating + notes
      try {
        const ratingRes = await recipeApi.getRating(id);
        setUserRating(ratingRes.data.rating);
        setPersonalNotes(ratingRes.data.personal_notes || '');
      } catch (e) {
        // Rating not found is ok
      }
    } catch (error) {
      toast.error(t('toastRecipeNotFound'));
      navigate('/recipes');
    } finally {
      setLoading(false);
    }
  };

  useLiveRefreshEvent(
    EventType.RECIPE_DELETED,
    useCallback((data) => {
      if (data?.id && data.id === id) {
        toast.message(t('toastRecipeDeleted') || 'Recipe deleted');
        navigate('/recipes');
      }
    }, [id, navigate, t]),
    liveRefresh
  );
  useLiveRefreshEvent(
    EventType.RECIPE_UPDATED,
    useCallback((data) => {
      if (data?.id === id) {
        loadRecipe();
      }
    }, [id]),
    liveRefresh
  );

  const handleSetRating = async (rating) => {
    setSavingRating(true);
    try {
      await recipeApi.setRating(id, rating, personalNotes);
      setUserRating(rating);
      toast.success(t('toastRatedStars', { n: rating }));
    } catch (error) {
      toast.error(error.response?.data?.detail || "Couldn't save your rating. Please try again. (E-RD003)");
    } finally {
      setSavingRating(false);
    }
  };

  const handleSaveNotes = async () => {
    setSavingNotes(true);
    try {
      await recipeApi.setRating(id, userRating || 3, personalNotes);
      if (!userRating) setUserRating(3);
      toast.success(t('toastPersonalNoteSaved'));
    } catch (error) {
      toast.error(error.response?.data?.detail || "Couldn't save note. (E-RD008)");
    } finally {
      setSavingNotes(false);
    }
  };

  const handleMarkCooked = async () => {
    setMarkingCooked(true);
    try {
      // Stamp last_cooked only — personal notes are saved separately above
      const res = await cookingApi.markCooked(id, {});
      setRecipe((prev) =>
        prev
          ? { ...prev, last_cooked_at: res.data.last_cooked_at || new Date().toISOString() }
          : prev
      );
      toast.success(t('toastMarkedAsCooked'));
    } catch (error) {
      toast.error(error.response?.data?.detail || "Couldn't mark as cooked. (E-RD009)");
    } finally {
      setMarkingCooked(false);
    }
  };

  const handleToggleFavorite = useCallback(async () => {
    setTogglingFavorite(true);
    try {
      const res = await recipeApi.toggleFavorite(id);
      setIsFavorite(res.data.is_favorite);
      toast.success(res.data.is_favorite ? t('toastAddedToFavorites') : t('toastRemovedFromFavorites'));
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('toastUpdateItemFailed')} (E-RD004)`);
    } finally {
      setTogglingFavorite(false);
    }
  }, [id, t]);

  const handleApplySubstitution = useCallback(
    async (index, newName) => {
      if (!recipe?.ingredients) return;
      const next = recipe.ingredients.map((ing, i) => {
        if (i !== index) return ing;
        if (typeof ing === 'string') return newName;
        return { ...ing, name: newName };
      });
      try {
        const res = await recipeApi.update(id, { ...recipe, ingredients: next });
        setRecipe(res.data);
        setScaledIngredients(null);
      } catch (error) {
        toast.error(
          error.response?.data?.detail ||
            t('toastUpdateRecipeFailed') ||
            "Couldn't apply substitution."
        );
      }
    },
    [recipe, id, t]
  );

  const handleScaleServings = useCallback(async (newServings) => {
    if (newServings < 1) return;
    setScaledServings(newServings);

    try {
      const res = await recipeApi.getScaled(id, newServings);
      setScaledIngredients(res.data.ingredients);
    } catch (error) {
      console.error('Failed to scale:', error);
    }
  }, [id]);

  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  const handleDelete = useCallback(async () => {
    if (!confirmDestructive(confirmActions, t('deleteRecipeConfirm'))) return;

    setDeleting(true);
    try {
      await recipeApi.delete(id);
      toast.success(t('toastRecipeDeleted'));
      // Replace so back doesn't revive the deleted detail; Recipes reloads from network
      // (in-memory + SW no longer cache /recipes, so All won't resurrect ghosts).
      navigate('/recipes', { replace: true, state: { deletedRecipeId: id } });
    } catch (error) {
      toast.error(error.response?.data?.detail || "Couldn't delete that recipe. Please try again. (E-RD005)");
    } finally {
      setDeleting(false);
    }
  }, [id, navigate, confirmActions, t]);

  const handleAddToMealPlan = useCallback(async () => {
    setAddingToMealPlan(true);
    try {
      await mealPlanApi.create({
        date: format(selectedDate, 'yyyy-MM-dd'),
        meal_type: mealType,
        recipe_id: recipe?.id,
      });
      toast.success(t('toastAddedToMealPlan'));
      setShowMealDialog(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Couldn't add to your meal plan. Please try again. (E-RD006)");
    } finally {
      setAddingToMealPlan(false);
    }
  }, [selectedDate, mealType, recipe?.id, t]);

  const handleAddToShopping = useCallback(async () => {
    setAddingToShopping(true);
    try {
      await shoppingListApi.fromRecipes([recipe?.id]);
      toast.success(t('toastShoppingListCreated'));
      navigate('/shopping');
    } catch (error) {
      toast.error(error.response?.data?.detail || "Couldn't create the shopping list. Please try again. (E-RD007)");
    } finally {
      setAddingToShopping(false);
    }
  }, [recipe?.id, navigate, t]);

  // Memoize expensive computed values - must be before any early returns
  const totalTime = useMemo(() =>
    recipe ? (recipe.prep_time || 0) + (recipe.cook_time || 0) : 0,
  [recipe?.prep_time, recipe?.cook_time]);

  const isOwner = useMemo(() =>
    user?.id === recipe?.author_id,
  [user?.id, recipe?.author_id]);

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-laro" />
        </div>
      </Layout>
    );
  }

  if (!recipe) return null;

  return (
    <Layout>
      <div className="max-w-4xl mx-auto" data-testid="recipe-detail">
        {/* Back Button */}
        <Link 
          to="/recipes" 
          className="inline-flex items-center text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          {t('backToRecipes')}
        </Link>

        <motion.article
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-2xl border border-border/60 overflow-hidden shadow-card"
        >
          {/* Hero Image */}
          <div className="relative aspect-video">
            <img
              src={getImageUrl(recipe.image_url, recipe)}
              alt={recipe.title}
              loading="eager"
              decoding="async"
              className="w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-transparent" />
            
            {/* Category Badge */}
            <Badge className="absolute top-4 left-4 bg-white/90 text-foreground backdrop-blur-sm font-semibold dark:bg-black/80 dark:text-cream dark:border dark:border-white/70 dark:shadow-md">
              {recipe.category}
            </Badge>

            {/* Dietary Tags */}
            {recipe.dietary_tags && recipe.dietary_tags.length > 0 && (
              <div className="absolute top-4 right-4 flex gap-2 flex-wrap justify-end max-w-[200px]">
                {recipe.dietary_tags.map((tag, idx) => (
                  <Badge key={idx} variant="secondary" className="bg-green-100 text-green-800 border-green-200 dark:bg-green-500/25 dark:text-green-200 dark:border-green-500/40">
                    {tag === 'vegan' && <Leaf className="w-3 h-3 mr-1" aria-hidden="true" />}
                    {tag === 'vegetarian' && <Leaf className="w-3 h-3 mr-1" aria-hidden="true" />}
                    {tag === 'gluten-free' && <Wheat className="w-3 h-3 mr-1" aria-hidden="true" />}
                    {tag}
                  </Badge>
                ))}
              </div>
            )}
          </div>

          <div className="p-6 md:p-8">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6">
              <div>
                <h1 className="font-heading text-3xl font-bold text-foreground" data-testid="recipe-title">
                  {recipe.title}
                </h1>
                {recipe.source_author && (
                  <a
                    href={
                      recipe.source_url && /instagram\.com/i.test(recipe.source_url)
                        ? `https://www.instagram.com/${String(recipe.source_author).replace(/^@/, '')}/`
                        : recipe.source_url && /tiktok\.com/i.test(recipe.source_url)
                          ? `https://www.tiktok.com/@${String(recipe.source_author).replace(/^@/, '')}`
                          : recipe.source_url || undefined
                    }
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-block mt-2 text-sm font-medium text-primary hover:underline"
                    data-testid="recipe-source-author"
                  >
                    {(() => {
                      const author = String(recipe.source_author).replace(/^@/, '').trim();
                      const social = recipe.source_url && /(instagram|tiktok)\.com/i.test(recipe.source_url);
                      const looksHost = author.includes('.') && !author.includes(' ');
                      return social && !looksHost ? `Source: @${author}` : `Source: ${author}`;
                    })()}
                  </a>
                )}
                {recipe.description && (
                  <p className="text-muted-foreground mt-2">{recipe.description}</p>
                )}
                {/* Personal Rating */}
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">{t('yourRating')}</span>
                    <div className="flex items-center gap-1">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          onClick={() => handleSetRating(star)}
                          onMouseEnter={() => setHoverRating(star)}
                          onMouseLeave={() => setHoverRating(0)}
                          disabled={savingRating}
                          className="p-0.5 transition-transform hover:scale-110 disabled:opacity-50"
                        >
                          <Star
                            className={`w-5 h-5 ${
                              (hoverRating || userRating) >= star
                                ? 'fill-yellow-400 text-yellow-400'
                                : 'text-gray-300'
                            }`}
                          />
                        </button>
                      ))}
                    </div>
                    {savingRating && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" aria-hidden="true" />}
                  </div>
                  {recipe.last_cooked_at && (
                    <span className="text-xs text-muted-foreground bg-cream-subtle px-2 py-1 rounded-full">
                      {t('lastCooked', { when: formatDistanceToNow(parseISO(recipe.last_cooked_at), { addSuffix: true }) })}
                    </span>
                  )}
                </div>

                {/* Allergen Warnings */}
                {allergenWarnings.length > 0 && (
                  <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" aria-hidden="true" />
                    <div>
                      <p className="font-medium text-amber-800">{t('allergenWarning')}</p>
                      <p className="text-sm text-amber-700 mt-1">
                        {t('allergenContains')}{' '}
                        {allergenWarnings.map((w, i) => (
                          <span key={i}>
                            <span className="font-medium">{w.ingredient}</span>
                            <span className="text-amber-600"> ({w.allergen})</span>
                            {i < allergenWarnings.length - 1 ? ', ' : ''}
                          </span>
                        ))}
                      </p>
                    </div>
                  </div>
                )}

                {/* Adult / kid veto hits with suggested swaps (edit to apply) */}
                {recipe?.ingredients?.length > 0 && (
                  <VetoReplacementBanner
                    className="mt-4"
                    ingredients={recipe.ingredients}
                    refreshKey={recipe.id}
                  />
                )}
              </div>

              {isOwner && (
                <div className="flex gap-2">
                  <Link to={`/recipes/${recipe.id}/edit`}>
                    <Button variant="outline" size="sm" className="rounded-full" data-testid="edit-recipe-btn">
                      <Edit className="w-4 h-4 mr-2" />
                      {t('edit')}
                    </Button>
                  </Link>
                  <Button 
                    variant="outline" 
                    size="sm" 
                    className="rounded-full text-destructive hover:bg-destructive hover:text-white"
                    onClick={handleDelete}
                    disabled={deleting}
                    data-testid="delete-recipe-btn"
                  >
                    {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                  </Button>
                </div>
              )}
              
              {/* Favorite & Print buttons */}
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  size="sm" 
                  className={`rounded-full ${isFavorite ? 'text-red-500 border-red-200 bg-red-50' : ''}`}
                  onClick={handleToggleFavorite}
                  disabled={togglingFavorite}
                  data-testid="favorite-btn"
                >
                  {togglingFavorite ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Heart className={`w-4 h-4 ${isFavorite ? 'fill-current' : ''}`} />
                  )}
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="rounded-full print:hidden"
                  onClick={handlePrint}
                  data-testid="print-btn"
                >
                  <Printer className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Meta Info */}
            <div className="flex flex-wrap gap-6 mb-8 pb-8 border-b border-border/60">
              {totalTime > 0 && (
                <div className="flex items-center gap-2">
                  <Clock className="w-5 h-5 text-laro" aria-hidden="true" />
                  <div>
                    <p className="text-xs text-muted-foreground">{t('totalTime')}</p>
                    <p className="font-medium">{formatTime(totalTime)}</p>
                  </div>
                </div>
              )}
              {recipe.prep_time > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground">{t('prep')}</p>
                  <p className="font-medium">{formatTime(recipe.prep_time)}</p>
                </div>
              )}
              {recipe.cook_time > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground">{t('cook')}</p>
                  <p className="font-medium">{formatTime(recipe.cook_time)}</p>
                </div>
              )}
              
              {/* Servings with scaling controls */}
              <div className="flex items-center gap-2">
                <Users className="w-5 h-5 text-laro" aria-hidden="true" />
                <div>
                  <p className="text-xs text-muted-foreground">{t('servings')}</p>
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={() => handleScaleServings(scaledServings - 1)}
                      className="w-6 h-6 rounded-full bg-laro-light hover:bg-laro text-laro hover:text-white flex items-center justify-center transition-colors print:hidden"
                      disabled={scaledServings <= 1}
                    >
                      <Minus className="w-3 h-3" />
                    </button>
                    <span className="font-medium w-8 text-center">{scaledServings}</span>
                    <button 
                      onClick={() => handleScaleServings(scaledServings + 1)}
                      className="w-6 h-6 rounded-full bg-laro-light hover:bg-laro text-laro hover:text-white flex items-center justify-center transition-colors print:hidden"
                    >
                      <PlusIcon className="w-3 h-3" />
                    </button>
                    {scaledServings !== recipe.servings && (
                      <span className="text-xs text-muted-foreground ml-1">
                        {t('wasServings', { n: recipe.servings })}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Per-serving macros (saved or estimated from ingredients) */}
              {showNutrition && recipe.nutrition && (
                (() => {
                  const n = recipe.nutrition;
                  const chips = [
                    n.calories != null && { key: 'cal', value: n.calories, label: 'cal' },
                    n.protein != null && { key: 'p', value: `${n.protein}g`, label: 'protein' },
                    n.carbs != null && { key: 'c', value: `${n.carbs}g`, label: 'carbs' },
                    n.fat != null && { key: 'f', value: `${n.fat}g`, label: 'fat' },
                  ].filter(Boolean);
                  if (!chips.length) return null;
                  return (
                    <div className="w-full flex flex-wrap items-center gap-2 pt-1" data-testid="recipe-macro-chips">
                      {chips.map((chip) => (
                        <div
                          key={chip.key}
                          className="rounded-full bg-laro-light/80 text-laro-dark px-3 py-1 text-sm"
                        >
                          <span className="font-semibold">{chip.value}</span>
                          <span className="text-xs ml-1 opacity-80">{chip.label}</span>
                        </div>
                      ))}
                      {(n.nutrition_estimated || n.nutrition_source === 'estimated' || n.nutrition_source === 'mixed') && (
                        <span className="text-xs text-muted-foreground">est. / serving</span>
                      )}
                    </div>
                  );
                })()
              )}
            </div>

            {/* Personal notes */}
            <div className="mb-8 p-4 rounded-2xl border border-border/60 bg-cream-subtle/50">
              <label className="text-sm font-medium mb-2 block">{t('yourNotes')}</label>
              <Textarea
                value={personalNotes}
                onChange={(e) => setPersonalNotes(e.target.value)}
                placeholder={t('personalNotesPlaceholder')}
                className="rounded-xl bg-white min-h-[72px]"
              />
              <div className="flex justify-end mt-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="rounded-full"
                  onClick={handleSaveNotes}
                  disabled={savingNotes}
                >
                  {savingNotes ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                  {t('saveNote')}
                </Button>
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-wrap gap-3 mb-8">
              <Button
                onClick={() => setShowCookMode(true)}
                className="rounded-full bg-laro hover:bg-laro-dark"
                data-testid="start-cook-mode"
              >
                <Play className="w-4 h-4 mr-2" />
                {t('cookMode')}
              </Button>
              <Button
                variant="outline"
                className="rounded-full"
                onClick={handleMarkCooked}
                disabled={markingCooked}
                data-testid="mark-cooked-btn"
              >
                {markingCooked ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                )}
                {t('markCooked')}
              </Button>
              <Dialog open={showMealDialog} onOpenChange={setShowMealDialog}>
                <DialogTrigger asChild>
                  <Button variant="outline" className="rounded-full" data-testid="add-to-meal-plan">
                    <CalendarPlus className="w-4 h-4 mr-2" />
                    {t('addToMealPlan')}
                  </Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>{t('addToMealPlan')}</DialogTitle>
                  </DialogHeader>
                  <div className="space-y-4 pt-4">
                    <div>
                      <label className="text-sm font-medium mb-2 block">{t('selectDate')}</label>
                      <Calendar
                        mode="single"
                        selected={selectedDate}
                        onSelect={(date) => date && setSelectedDate(date)}
                        className="rounded-xl border"
                      />
                    </div>
                    <div>
                      <label className="text-sm font-medium mb-2 block">{t('mealType')}</label>
                      <Select value={mealType} onValueChange={setMealType}>
                        <SelectTrigger className="rounded-xl">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {MEAL_TYPES.map((type) => (
                            <SelectItem key={type} value={type}>
                              {MEAL_TYPE_KEYS[type] ? t(MEAL_TYPE_KEYS[type]) : type}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <Button
                      onClick={handleAddToMealPlan}
                      className="w-full rounded-full bg-laro hover:bg-laro-dark"
                      disabled={addingToMealPlan}
                    >
                      {addingToMealPlan ? <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" /> : t('addToPlan')}
                    </Button>
                  </div>
                </DialogContent>
              </Dialog>

              <Button 
                variant="outline" 
                className="rounded-full"
                onClick={handleAddToShopping}
                disabled={addingToShopping}
                data-testid="add-to-shopping"
              >
                {addingToShopping ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <ShoppingCart className="w-4 h-4 mr-2" />
                )}
                {t('addToShoppingList')}
              </Button>

              <Button 
                variant="outline" 
                className="rounded-full"
                onClick={() => setShowShareDialog(true)}
                data-testid="share-recipe"
              >
                <Share2 className="w-4 h-4 mr-2" />
                {t('share')}
              </Button>
            </div>

            <ShareRecipeModal
              isOpen={showShareDialog}
              onClose={() => setShowShareDialog(false)}
              recipe={recipe}
            />

            {/* Tags */}
            {recipe.tags && recipe.tags.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-8">
                {recipe.tags.map((tag, idx) => (
                  <span
                    key={`${tag}-${idx}`}
                    className="px-3 py-1 rounded-full bg-laro-light text-laro text-sm"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}

            {familyMode ? (
              <div
                className="mb-8 rounded-xl border border-amber-200/80 bg-amber-50/80 px-4 py-3"
                data-testid="recipe-adult-boost-tip"
              >
                <p className="text-sm font-medium text-amber-950 flex items-center gap-2">
                  <Users className="w-4 h-4 shrink-0" aria-hidden="true" />
                  {t('recipeAdultBoostTitle')}
                </p>
                <p className="text-sm text-amber-900/80 mt-1 leading-relaxed">
                  {t('recipeAdultBoostBody')}
                </p>
              </div>
            ) : null}

            {/* Ingredients */}
            <section className="mb-8">
              <h2 className="font-heading text-xl font-semibold mb-4 flex items-center gap-2">
                <ChefHat className="w-5 h-5 text-laro" aria-hidden="true" />
                {t('ingredients')}
                {scaledServings !== recipe.servings && (
                  <span className="text-sm font-normal text-muted-foreground">
                    {t('scaledForServings', { n: scaledServings })}
                  </span>
                )}
              </h2>
              <ul className="space-y-2" data-testid="ingredients-list">
                {(scaledIngredients || recipe.ingredients).map((ing, idx) => {
                  const converted =
                    typeof ing === 'string'
                      ? null
                      : convertUnit(ing.amount, ing.unit, measurementUnit);
                  const both =
                    measurementUnit === 'both' && typeof ing !== 'string'
                      ? {
                          metric: convertUnit(ing.amount, ing.unit, 'metric'),
                          imperial: convertUnit(ing.amount, ing.unit, 'imperial'),
                        }
                      : null;
                  const displayName = typeof ing === 'string' ? ing : ing.name;
                  return (
                  <li key={`${ing.name || ing}-${idx}`} className="flex items-start gap-3 p-3 rounded-xl bg-cream-subtle">
                    <span className="w-2 h-2 rounded-full bg-laro mt-2 flex-shrink-0" />
                    <span className="flex-1 min-w-0">
                      {typeof ing === 'string' ? (
                        ing
                      ) : both ? (
                        <>
                          <span className="font-medium">{both.metric.amount}</span>
                          {both.metric.unit && (
                            <span className="text-muted-foreground"> {both.metric.unit}</span>
                          )}
                          <span className="text-muted-foreground text-sm">
                            {' '}
                            ({both.imperial.amount} {both.imperial.unit})
                          </span>
                          <span> {ing.name}</span>
                        </>
                      ) : (
                        <>
                          <span className="font-medium">{converted?.amount ?? ing.amount}</span>
                          {(converted?.unit || ing.unit) && (
                            <span className="text-muted-foreground">
                              {' '}
                              {converted?.unit || ing.unit}
                            </span>
                          )}
                          <span> {ing.name}</span>
                        </>
                      )}
                    </span>
                    <IngredientSubstituteButton
                      ingredientName={displayName}
                      canApply={isOwner}
                      onApply={(newName) => handleApplySubstitution(idx, newName)}
                      recipeContext={recipe}
                    />
                  </li>
                  );
                })}
              </ul>
            </section>

            {/* Instructions */}
            <section className="mb-8">
              <h2 className="font-heading text-xl font-semibold mb-4">{t('instructions')}</h2>
              <ol className="space-y-4" data-testid="instructions-list">
                {recipe.instructions.map((step, idx) => (
                  <li key={`step-${idx}`} className="flex gap-4">
                    <span className="flex-shrink-0 w-8 h-8 rounded-full bg-laro text-white flex items-center justify-center font-semibold text-sm">
                      {idx + 1}
                    </span>
                    <p className="pt-1">
                      {enrichStepWithAmounts(step, recipe.ingredients, measurementUnit)}
                    </p>
                  </li>
                ))}
              </ol>
            </section>

            {/* Nutrition Calculator — gated by Preferences → showNutrition */}
            {showNutrition && (
              <section className="mb-6">
                <NutritionCalculator 
                  recipeId={recipe.id}
                  ingredients={recipe.ingredients?.map(i => `${i.amount || ''} ${i.unit || ''} ${i.name}`)}
                  servings={scaledServings || recipe.servings}
                  savedNutrition={recipe.nutrition}
                />
              </section>
            )}

            {/* Cost Calculator */}
            <section className="mb-6">
              <CostCalculator 
                recipeId={recipe.id}
                servings={scaledServings || recipe.servings}
              />
            </section>

            {/* Reviews & Ratings */}
            <section className="mb-6">
              <RecipeReviews 
                recipeId={recipe.id}
                currentUserId={user?.id}
              />
            </section>

            {/* Recipe Version History */}
            {isOwner && (
              <section className="mb-6">
                <RecipeVersions 
                  recipeId={recipe.id}
                  currentVersion={recipe.current_version}
                  onRestore={() => loadRecipe()}
                />
              </section>
            )}
          </div>
        </motion.article>
      </div>

      {/* Cook Mode */}
      {showCookMode && (
        <CookMode recipe={recipe} onClose={() => setShowCookMode(false)} />
      )}
    </Layout>
  );
};
