import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { CookMode } from '../components/CookMode';
import { CheckNumbers } from '../components/CheckNumbers';
import { ListChecks } from 'lucide-react';
import { NutritionCalculator } from '../components/NutritionCalculator';
import { foodEmoji } from '../lib/foodEmoji';
import { groupedRows, groupHeading, ingredientsAsText } from '../lib/ingredientGroups';
import { getLowFodmap, findSwap, readFodmapView, writeFodmapView } from '../lib/fodmap';
import { macroSourceText, macrosForChoice, nutritionBasis, scaleBadge, weightsForChoice } from '../lib/versionMacros';
import MacroTotals from '../components/MacroTotals';
import { badgeCarbsForStyle, carbsLabels, styleFromPreferences } from '../lib/region';
import { temperaturesForStyle } from '../lib/temperature';
import {
  ORIGINAL_VERSION,
  applyRecipeVersion,
  choiceFromSearch,
  findVersion,
  getPageNotes,
  readVersionChoice,
  scaleIngredients,
  validVersion,
  versionChoices,
  writeVersionChoice,
} from '../lib/recipeVersions';
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
import { MeasurementUnitPicker } from '../components/MeasurementUnitPicker';
import { patchUserPreferencesCache } from '../hooks/useUserPreferences';
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

// Macro-target solver (Pro): scale the recipe so a chosen macro hits a target/serving.
const SOLVER_MACROS = [
  { key: 'p', field: 'protein', label: 'Protein', unit: 'g' },
  { key: 'c', field: 'carbs', label: 'Carbs', unit: 'g' },
  { key: 'f', field: 'fat', label: 'Fat', unit: 'g' },
  { key: 'cal', field: 'calories', label: 'Calories', unit: 'kcal' },
];

function solverFactor(recipe, solver) {
  if (!solver || !recipe?.nutrition) return 1;
  const m = SOLVER_MACROS.find((x) => x.key === solver.macro);
  const cur = m && recipe.nutrition[m.field];
  const tgt = parseFloat(solver.target);
  if (!cur || cur <= 0 || !tgt || tgt <= 0) return 1;
  return tgt / cur;
}

// Multiply a recipe amount (number, "1.5", "1/2", "1 1/2") by a factor; leave non-numeric ("pinch") alone.
function scaleAmountStr(amount, f) {
  if (!f || f === 1) return amount;
  const s = String(amount ?? '').trim();
  let n = null;
  const mixed = s.match(/^(\d+)\s+(\d+)\/(\d+)$/);
  const frac = s.match(/^(\d+)\/(\d+)$/);
  if (mixed) n = parseInt(mixed[1], 10) + parseInt(mixed[2], 10) / parseInt(mixed[3], 10);
  else if (frac) n = parseInt(frac[1], 10) / parseInt(frac[2], 10);
  else if (s && !Number.isNaN(parseFloat(s))) n = parseFloat(s);
  if (n == null) return amount;
  const v = n * f;
  const r = v >= 10 ? Math.round(v) : Math.round(v * 100) / 100;
  return String(r);
}

export const RecipeDetail = () => {
  const { id } = useParams();
  const { t } = useLanguage();
  const { confirmActions } = useAccessibility();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { setRecipeContext, clearRecipeContext } = useChat();
  const liveRefresh = useLiveRefreshContext();
  const [presenceViewers, setPresenceViewers] = useState([]);
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
  const [nutritionStyle, setNutritionStyle] = useState('uk'); // from country: uk / au / ca / us
  const [showNutrition, setShowNutrition] = useState(true);
  const [familyMode, setFamilyMode] = useState(false);
  const [generatingCard, setGeneratingCard] = useState(false);
  const [isFavorite, setIsFavorite] = useState(false);
  const [togglingFavorite, setTogglingFavorite] = useState(false);
  const [scaledServings, setScaledServings] = useState(null);
  const [scaledIngredients, setScaledIngredients] = useState(null);
  const [macroMode, setMacroMode] = useState('serving'); // 'serving' | '100g' | 'total'
  const [solver, setSolver] = useState(null); // applied {macro, target} — Pro
  const [solverOpen, setSolverOpen] = useState(false);
  const [solverMacroSel, setSolverMacroSel] = useState('p');
  const [solverTargetInput, setSolverTargetInput] = useState('');
  const [ingredientMacros, setIngredientMacros] = useState(null); // Pro: per-ingredient breakdown
  const [macroInfoIdx, setMacroInfoIdx] = useState(null); // line whose macro source is expanded
  const [showCookMode, setShowCookMode] = useState(false);
  const [showCheckNumbers, setShowCheckNumbers] = useState(false);
  const [allergenWarnings, setAllergenWarnings] = useState([]);
  const [userRating, setUserRating] = useState(null);
  const [personalNotes, setPersonalNotes] = useState('');
  const [hoverRating, setHoverRating] = useState(0);
  const [savingRating, setSavingRating] = useState(false);
  const [savingNotes, setSavingNotes] = useState(false);
  const [markingCooked, setMarkingCooked] = useState(false);
  const [fodmapView, setFodmapView] = useState(readFodmapView);
  const [versionName, setVersionName] = useState(ORIGINAL_VERSION);
  const location = useLocation();
  const recipeCardRef = useRef(null);
  const lowFodmap = useMemo(() => getLowFodmap(recipe), [recipe]);
  const showFodmap = !!lowFodmap && fodmapView === 'low_fodmap';
  // Named versions ("Chicken Schnitzel", "Chocolate Orange"): '' = Original. Low FODMAP is a
  // separate on/off that swaps alternatives into whichever version is shown.
  const versionList = useMemo(() => versionChoices(recipe), [recipe]);
  const activeVersion = validVersion(recipe, versionName);
  const activeVersionInfo = useMemo(() => findVersion(recipe, activeVersion), [recipe, activeVersion]);
  const shown = useMemo(() => applyRecipeVersion(recipe, activeVersion), [recipe, activeVersion]);
  const pageNotes = useMemo(() => getPageNotes(recipe), [recipe]);
  // Macros follow what is shown: the version's (and Low FODMAP's) own numbers, not the Original's.
  const storedMacros = useMemo(
    () => macrosForChoice(recipe, activeVersion, showFodmap, ingredientMacros),
    [recipe, activeVersion, showFodmap, ingredientMacros],
  );
  const choiceKey = `${recipe?.id || ''}|${activeVersion}|${showFodmap ? 1 : 0}`;
  const [previewMacros, setPreviewMacros] = useState(null); // { key, nutrition, ingredient_macros }
  const preview = storedMacros.pending && previewMacros?.key === choiceKey ? previewMacros : null;
  const displayNutrition = preview?.nutrition || storedMacros.nutrition;
  const macrosPending = storedMacros.pending && !preview?.nutrition;
  const lineMacros = preview
    ? (Array.isArray(preview.ingredient_macros) && preview.ingredient_macros.length === (shown?.ingredients || []).length
      ? preview.ingredient_macros
      : null)
    : storedMacros.ingredientMacros;
  // Per 100 g (batch / base recipes): weights of the shown list, from the backend.
  const choiceWeights = useMemo(
    () => weightsForChoice(recipe, activeVersion, showFodmap, preview),
    [recipe, activeVersion, showFodmap, preview],
  );
  const basis = nutritionBasis(recipe);
  // The card opens on the recipe's basis (its saved choice, else automatic) for each recipe.
  useEffect(() => { if (recipe?.id) setMacroMode(basis); }, [recipe?.id, basis]);
  // Solver / macro card read `nutrition` off this (the shown version's).
  const macroRecipe = useMemo(
    () => (recipe ? { ...recipe, nutrition: displayNutrition } : recipe),
    [recipe, displayNutrition],
  );

  // A meal-plan link (?version=…&lowFodmap=1) wins; else this recipe's remembered choice;
  // else the last Low FODMAP view used anywhere.
  useEffect(() => {
    const choice = choiceFromSearch(location.search) || readVersionChoice(id);
    setVersionName(choice?.version || ORIGINAL_VERSION);
    setFodmapView(choice ? (choice.lowFodmap ? 'low_fodmap' : 'original') : readFodmapView());
  }, [id, location.search]);

  const chooseVersion = (name) => {
    setVersionName(name);
    writeVersionChoice(id, { version: name, lowFodmap: showFodmap });
  };
  const chooseFodmapView = (view) => {
    setFodmapView(view);
    writeFodmapView(view);
    writeVersionChoice(id, { version: activeVersion, lowFodmap: view === 'low_fodmap' });
  };

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
    text += `${ingredientsAsText(recipe.ingredients, t)}\n`;

    text += `\n👨‍🍳 INSTRUCTIONS\n`;
    recipe.instructions.forEach((step, idx) => {
      text += `${idx + 1}. ${step}\n`;
    });

    text += `\n─────────────────────────────\n`;
    text += `Shared from Laro`;

    return text;
  }, [recipe, t]);

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
        setNutritionStyle(styleFromPreferences(res.data));
        if (res.data?.showNutrition !== undefined) setShowNutrition(!!res.data.showNutrition);
        setFamilyMode(wantsFamilyOneMeal(res.data || {}));
      })
      .catch(() => {});
  }, [id]);

  // Pro: per-ingredient macro breakdown (AI-estimated, cached server-side after first view)
  useEffect(() => { setIngredientMacros(null); }, [recipe?.id]);
  // Refetched when the recipe changes (edit, or the server finishing its line macros) so the
  // badges and the totals card keep describing the same numbers.
  useEffect(() => {
    if (!recipe?.id || !user?.is_pro) return;
    let cancelled = false;
    recipeApi
      .getIngredientMacros(recipe.id)
      .then((res) => {
        if (cancelled) return;
        setIngredientMacros(res.data?.ingredient_macros || null);
        // First compute also wrote the totals + version / Low FODMAP macros: show them now.
        if (res.data?.adaptations || res.data?.nutrition) {
          setRecipe((prev) => (prev && prev.id === recipe.id ? {
            ...prev,
            ...(res.data.adaptations ? { adaptations: res.data.adaptations } : {}),
            ...(res.data.nutrition ? {
              nutrition: { ...(prev.nutrition || {}), ...res.data.nutrition, nutrition_estimated: false, nutrition_source: 'lines' },
            } : {}),
          } : prev));
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [recipe?.id, recipe?.updated_at, user?.is_pro]);

  // Version / Low FODMAP macros not stored yet (recipe saved before they existed): ask the
  // server, which computes and saves them. Until then the card says the numbers are pending.
  useEffect(() => {
    if (!recipe?.id || !storedMacros.pending) return;
    let cancelled = false;
    recipeApi
      .macrosPreview(recipe.id, { version: activeVersion || null, low_fodmap: showFodmap })
      .then((res) => {
        if (!cancelled && res.data?.nutrition) setPreviewMacros({ key: choiceKey, ...res.data });
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [recipe?.id, storedMacros.pending, activeVersion, showFodmap, choiceKey]);

  // Scope global AI chat to this recipe while the detail page is open
  useEffect(() => {
    if (recipe?.id) {
      setRecipeContext(recipe);
    }
    return () => clearRecipeContext();
  }, [recipe, setRecipeContext, clearRecipeContext]);

  const persistMeasurementUnit = async (value) => {
    setMeasurementUnit(value);
    patchUserPreferencesCache({ measurementUnit: value });
    try {
      await preferencesApi.update({ measurementUnit: value });
    } catch {
      /* keep optimistic value */
    }
  };

  // Live refreshes (household edits) re-run loadRecipe; only reset the user's own
  // working state (servings, notes, rating) on the first load for this recipe so
  // half-typed notes aren't wiped.
  const loadedIdRef = useRef(null);

  const loadRecipe = async () => {
    const firstLoad = loadedIdRef.current !== id;
    try {
      const res = await recipeApi.getOne(id);
      setRecipe(res.data);
      setIsFavorite(res.data.is_favorite || false);
      if (firstLoad) setScaledServings(res.data.servings || 4);
      // Set allergen warnings from API response
      setAllergenWarnings(res.data.allergen_warnings || []);

      if (firstLoad) {
        loadedIdRef.current = id;
        // Load user's personal rating + notes
        try {
          const ratingRes = await recipeApi.getRating(id);
          setUserRating(ratingRes.data.rating);
          setPersonalNotes(ratingRes.data.personal_notes || '');
        } catch (e) {
          // Rating not found is ok
        }
      }
    } catch (error) {
      const status = error?.response?.status;
      if (status === 404 || status === 403) {
        toast.error(t('toastRecipeNotFound'));
        navigate('/recipes');
      } else if (firstLoad) {
        // Network blip / server error: say so, but don't throw the user out of the page.
        toast.error(error?.response?.data?.detail || t('toastLoadRecipeFailed'));
      }
    } finally {
      setLoading(false);
    }
  };


  useEffect(() => {
    if (!id || !liveRefresh?.send) {
      setPresenceViewers([]);
      return undefined;
    }
    const send = liveRefresh.send;
    const payload = {
      resource_type: 'recipe',
      resource_id: id,
      display_name: user?.name || user?.email || 'Someone',
    };
    send({ type: 'presence:join', ...payload });
    const beat = setInterval(() => send({ type: 'presence:heartbeat', ...payload }), 20000);
    return () => {
      clearInterval(beat);
      send({ type: 'presence:leave', ...payload });
      setPresenceViewers([]);
    };
  }, [id, liveRefresh?.send, user?.name, user?.email]);

  useLiveRefreshEvent(
    EventType.PRESENCE_UPDATED,
    (data) => {
      if (!data || data.resource_type !== 'recipe' || data.resource_id !== id) return;
      setPresenceViewers((data.viewers || []).filter((v) => v.user_id !== user?.id));
    },
    liveRefresh,
  );

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
      // Send the user's rating only if they gave one; a note alone shouldn't add stars.
      await recipeApi.setRating(id, userRating || null, personalNotes);
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

  // Per serving / Per 100 g is remembered per recipe (adaptations.nutrition_basis, normal update
  // endpoint, other adaptations kept). Recipe total is just a view. Non-owners: view only.
  const handleMacroMode = useCallback(async (mode) => {
    setMacroMode(mode);
    if (mode === 'total' || !recipe || mode === nutritionBasis(recipe) || user?.id !== recipe.author_id) return;
    try {
      const res = await recipeApi.update(id, {
        ...recipe,
        adaptations: { ...(recipe.adaptations || {}), nutrition_basis: mode },
      });
      setRecipe(res.data);
    } catch {
      // Still shown this way for now; it just isn't remembered.
    }
  }, [recipe, id, user?.id]);

  const handleScaleServings = useCallback(async (newServings) => {
    if (newServings < 1) return;
    const previous = scaledServings;
    setScaledServings(newServings);

    try {
      const res = await recipeApi.getScaled(id, newServings);
      setScaledIngredients(res.data.ingredients);
    } catch (error) {
      // Don't leave the servings number and the ingredient amounts disagreeing silently.
      console.error('Failed to scale:', error);
      setScaledServings(previous);
      toast.error(error?.response?.data?.detail || t('toastScaleFailed'));
    }
  }, [id, scaledServings, t]);

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
        // Plan the version + Low FODMAP choice shown on this page (shopping follows it).
        recipe_version: activeVersion || null,
        low_fodmap: showFodmap,
      });
      toast.success(t('toastAddedToMealPlan'));
      setShowMealDialog(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Couldn't add to your meal plan. Please try again. (E-RD006)");
    } finally {
      setAddingToMealPlan(false);
    }
  }, [selectedDate, mealType, recipe?.id, activeVersion, showFodmap, t]);

  const handleAddToShopping = useCallback(async () => {
    setAddingToShopping(true);
    try {
      await shoppingListApi.fromRecipes([recipe?.id], {
        recipe_version: activeVersion || undefined,
        low_fodmap: showFodmap || undefined,
      });
      toast.success(t('toastShoppingListCreated'));
      navigate('/shopping');
    } catch (error) {
      toast.error(error.response?.data?.detail || "Couldn't create the shopping list. Please try again. (E-RD007)");
    } finally {
      setAddingToShopping(false);
    }
  }, [recipe?.id, activeVersion, showFodmap, navigate, t]);

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

  if (!recipe) {
    // Load failed for a non-404 reason (offline / server hiccup): offer a retry, not a blank page.
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center h-64 gap-4 text-center">
          <p className="text-muted-foreground">{t('toastLoadRecipeFailed')}</p>
          <Button className="rounded-full" onClick={() => { setLoading(true); loadRecipe(); }}>
            {t('tryAgain')}
          </Button>
        </div>
      </Layout>
    );
  }

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
            <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-black/40" />
            
            {/* Category Badge */}
            <Badge className="absolute top-4 left-4 bg-white/90 text-foreground backdrop-blur-sm font-semibold dark:bg-black/80 dark:text-cream dark:border dark:border-white/70 dark:shadow-md">
              {recipe.category}
            </Badge>

            {/* Share stays on the photo so light-theme chrome cannot hide it */}
            <button
              type="button"
              onClick={() => setShowShareDialog(true)}
              data-testid="share-recipe"
              className="absolute bottom-4 right-4 z-10 inline-flex items-center gap-2 rounded-full bg-black/55 text-white px-3.5 py-2 text-sm font-semibold backdrop-blur-sm hover:bg-black/70 print:hidden"
            >
              <Share2 className="w-4 h-4" aria-hidden="true" />
              {t('share')}
            </button>

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
                {presenceViewers.length > 0 && (
                  <p className="text-xs text-emerald-700 mt-1" data-testid="recipe-presence">
                    {presenceViewers.length === 1
                      ? t('presenceOne', { name: presenceViewers[0].name })
                      : t('presenceMany', { name: presenceViewers[0].name, count: presenceViewers.length - 1 })}
                  </p>
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
                  aria-label={t('ariaPrintRecipe')}
                  data-testid="print-btn"
                >
                  <Printer className="w-4 h-4" />
                </Button>
                <Button 
                  variant="outline" 
                  size="sm" 
                  className="rounded-full print:hidden"
                  onClick={() => setShowShareDialog(true)}
                  data-testid="share-recipe-header"
                >
                  <Share2 className="w-4 h-4 mr-2" />
                  {t('share')}
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
                      type="button"
                      aria-label={t('ariaFewerServings')}
                      onClick={() => handleScaleServings(scaledServings - 1)}
                      className="w-6 h-6 rounded-full bg-laro-light hover:bg-laro text-laro hover:text-white flex items-center justify-center transition-colors print:hidden"
                      disabled={scaledServings <= 1}
                    >
                      <Minus className="w-3 h-3" />
                    </button>
                    <span className="font-medium w-8 text-center" aria-live="polite">{scaledServings}</span>
                    <button 
                      type="button"
                      aria-label={t('ariaMoreServings')}
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

              {/* Macro card — Per serving | Per 100 g | Recipe total + colour pills */}
              {showNutrition && displayNutrition && (
                (() => {
                  const n = displayNutrition;
                  if (n.calories == null && n.protein == null && n.carbs == null && n.fat == null) return null;
                  const servingCount = Math.max(1, scaledServings || recipe.servings || 1);
                  const f = solverFactor(macroRecipe, solver);
                  const isEst = n.nutrition_estimated || n.nutrition_source === 'estimated' || n.nutrition_source === 'mixed';
                  const isPro = !!user?.is_pro;
                  const solverM = SOLVER_MACROS.find((x) => x.key === (solver?.macro || solverMacroSel));
                  const canSolve = (mm) => { const c = displayNutrition?.[SOLVER_MACROS.find((x) => x.key === mm)?.field]; return c && c > 0; };
                  return (
                    <MacroTotals
                      nutrition={n}
                      mode={macroMode}
                      onModeChange={handleMacroMode}
                      servings={servingCount}
                      factor={f}
                      weights={choiceWeights}
                      recipe={recipe}
                      pending={macrosPending}
                      estimated={isEst}
                      t={t}
                      nutritionStyle={nutritionStyle}
                    >
                      {/* Macro-target solver (Pro) */}
                      <div className="mt-3 pt-3 border-t border-border/50 print:hidden">
                        {solver ? (
                          <div className="flex items-center justify-between gap-2 text-sm">
                            <span className="text-laro font-medium">
                              🎯 Scaled ×{f.toFixed(2)} to hit {solver.target}{solverM?.unit} {solverM?.label.toLowerCase()}/serving
                            </span>
                            <button type="button" className="text-xs underline text-muted-foreground hover:text-foreground"
                              onClick={() => { setSolver(null); setSolverOpen(false); }}>
                              Reset
                            </button>
                          </div>
                        ) : !solverOpen ? (
                          <button type="button"
                            onClick={() => {
                              if (!isPro) { toast('Laro Pro: auto-scale a recipe to your macro target', { description: 'Upgrade in Settings → Laro Pro', action: { label: 'Upgrade', onClick: () => navigate('/settings') } }); return; }
                              setSolverTargetInput(''); setSolverOpen(true);
                            }}
                            className="inline-flex items-center gap-1.5 text-sm font-medium text-laro hover:opacity-80">
                            🎯 Auto-scale to a macro target
                            {!isPro && <span className="text-[10px] uppercase tracking-wide bg-laro/10 text-laro px-1.5 py-0.5 rounded-full">Pro</span>}
                          </button>
                        ) : (
                          <div className="flex flex-wrap items-center gap-2 text-sm">
                            <span className="text-muted-foreground">Hit</span>
                            <div className="inline-flex rounded-lg bg-cream-subtle dark:bg-muted p-0.5">
                              {SOLVER_MACROS.filter((m) => canSolve(m.key)).map((m) => (
                                <button key={m.key} type="button" onClick={() => setSolverMacroSel(m.key)}
                                  className={`px-2 py-0.5 rounded-md text-xs font-medium ${solverMacroSel === m.key ? 'bg-white dark:bg-card shadow-sm text-laro' : 'text-muted-foreground'}`}>
                                  {m.label}
                                </button>
                              ))}
                            </div>
                            <input type="number" min="1" value={solverTargetInput} onChange={(e) => setSolverTargetInput(e.target.value)}
                              placeholder={String(Math.round(displayNutrition?.[solverM?.field] || 0))}
                              className="w-20 rounded-lg border border-input bg-background px-2 py-1 text-sm" />
                            <span className="text-muted-foreground">{solverM?.unit}/serving</span>
                            <button type="button"
                              onClick={() => { if (parseFloat(solverTargetInput) > 0) { setSolver({ macro: solverMacroSel, target: solverTargetInput }); setSolverOpen(false); } }}
                              className="px-3 py-1 rounded-lg bg-laro text-white text-sm font-medium hover:opacity-90">
                              Apply
                            </button>
                            <button type="button" className="text-xs text-muted-foreground underline" onClick={() => setSolverOpen(false)}>Cancel</button>
                          </div>
                        )}
                      </div>
                    </MacroTotals>
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
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => setShowCheckNumbers(true)}
                data-testid="check-nutrition-btn"
              >
                <ListChecks className="w-4 h-4 mr-2" />
                {t('checkNutrition') === 'checkNutrition' ? 'Check nutrition' : t('checkNutrition')}
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
                data-testid="share-recipe-actions"
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
              {(versionList.length > 0 || lowFodmap) && (
                <div className="mb-4 print:hidden space-y-2">
                  {versionList.length > 0 && (
                    <div
                      role="group"
                      aria-label={t('recipeVersionPickerLabel')}
                      className="flex flex-wrap gap-2 text-sm"
                      data-testid="version-picker"
                    >
                      {versionList.map((name) => (
                        <button
                          key={name || 'original'}
                          type="button"
                          aria-pressed={activeVersion === name}
                          onClick={() => chooseVersion(name)}
                          className={`shrink-0 whitespace-nowrap px-3 py-1.5 rounded-full border font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-laro ${activeVersion === name ? 'bg-laro text-white border-laro' : 'bg-white dark:bg-card border-border text-foreground hover:border-laro/50'}`}
                        >
                          {name || t('recipeVersionOriginal')}
                        </button>
                      ))}
                    </div>
                  )}
                  {activeVersionInfo?.notes && (
                    <p className="text-sm text-muted-foreground whitespace-pre-line" data-testid="version-notes">
                      {activeVersionInfo.notes}
                    </p>
                  )}
                  {lowFodmap && (
                    <div data-testid="fodmap-switch">
                      <button
                        type="button"
                        aria-pressed={showFodmap}
                        onClick={() => chooseFodmapView(showFodmap ? 'original' : 'low_fodmap')}
                        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-laro ${showFodmap ? 'bg-laro-light border-laro text-laro' : 'bg-white dark:bg-card border-border text-muted-foreground hover:border-laro/50'}`}
                      >
                        <Leaf className="w-4 h-4" aria-hidden="true" />
                        {t('fodmapLowFodmap')}
                      </button>
                    </div>
                  )}
                  {showFodmap && lowFodmap.notes && (
                    <div
                      className="mt-3 rounded-xl border border-laro/20 bg-laro-light/60 px-4 py-3"
                      data-testid="fodmap-notes"
                    >
                      <p className="text-sm font-medium text-laro flex items-center gap-2">
                        <Leaf className="w-4 h-4 shrink-0" aria-hidden="true" />
                        {t('fodmapNotesTitle')}
                      </p>
                      <p className="text-sm text-muted-foreground mt-1 leading-relaxed whitespace-pre-line">
                        {lowFodmap.notes}
                      </p>
                    </div>
                  )}
                </div>
              )}
              <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <h2 className="font-heading text-xl font-semibold flex items-center gap-2">
                  <ChefHat className="w-5 h-5 text-laro" aria-hidden="true" />
                  {t('ingredients')}
                  {scaledServings !== recipe.servings && (
                    <span className="text-sm font-normal text-muted-foreground">
                      {t('scaledForServings', { n: scaledServings })}
                    </span>
                  )}
                </h2>
                <MeasurementUnitPicker
                  compact
                  value={measurementUnit}
                  onChange={persistMeasurementUnit}
                />
              </div>
              <ul className="space-y-2" data-testid="ingredients-list">
                {groupedRows(
                  solver
                    ? shown.ingredients
                    : activeVersion
                      ? scaleIngredients(shown.ingredients, recipe.servings, scaledServings)
                      : (scaledIngredients || recipe.ingredients)
                ).map(({ ing, index: idx, group, name, groupStart }) => {
                  // Ungrouped lines first, then each section under its "For the …" heading;
                  // idx stays the line's own index (line macros / substitutions are per line).
                  const split = { group, name };
                  const ingAmount = typeof ing === 'string' ? null : (solver ? scaleAmountStr(ing.amount, solverFactor(macroRecipe, solver)) : ing.amount);
                  const converted =
                    typeof ing === 'string'
                      ? null
                      : convertUnit(ingAmount, ing.unit, measurementUnit, ing.name);
                  const both =
                    measurementUnit === 'both' && typeof ing !== 'string'
                      ? {
                          metric: convertUnit(ingAmount, ing.unit, 'metric', ing.name),
                          imperial: convertUnit(ingAmount, ing.unit, 'imperial', ing.name),
                        }
                      : null;
                  const displayName = split.name;
                  const fodmapSwap = showFodmap ? findSwap(displayName, lowFodmap.swaps) : null;
                  const emoji = foodEmoji(fodmapSwap ? fodmapSwap.to : displayName);
                  const originalLine = typeof ing === 'string'
                    ? ing
                    : [converted?.amount ?? ingAmount, converted?.unit || ing.unit, split.name].filter(Boolean).join(' ');
                  return (
                  <React.Fragment key={`${ing.name || ing}-${idx}`}>
                  {groupStart && (
                    <li className="pt-2 text-sm font-semibold text-laro list-none" data-testid="ingredient-group">
                      {groupHeading(split.group, t)}
                    </li>
                  )}
                  <li className="flex items-start gap-3 p-3 rounded-xl bg-cream-subtle" data-fodmap-swapped={fodmapSwap ? 'true' : undefined}>
                    {emoji ? (
                      <span className="text-lg leading-none mt-0.5 w-6 text-center flex-shrink-0" aria-hidden="true">{emoji}</span>
                    ) : (
                      <span className="w-2 h-2 rounded-full bg-laro mt-2 flex-shrink-0" />
                    )}
                    <span className="flex-1 min-w-0">
                      {fodmapSwap ? (
                        <>
                          <span className="font-medium">{fodmapSwap.to}</span>
                          <span className="ml-2 inline-flex items-center rounded-full bg-laro-light px-1.5 py-0.5 text-[11px] font-semibold text-laro align-middle">
                            {t('fodmapSwapped')}
                          </span>
                          <span className="block text-xs text-muted-foreground mt-0.5">
                            <span className="sr-only">{t('fodmapInsteadOf', { name: originalLine })}</span>
                            <s aria-hidden="true">{originalLine}</s>
                          </span>
                        </>
                      ) : typeof ing === 'string' ? (
                        split.name
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
                          <span> {split.name}</span>
                        </>
                      ) : (
                        <>
                          <span className="font-medium">{converted?.amount ?? ingAmount}</span>
                          {(converted?.unit || ing.unit) && (
                            <span className="text-muted-foreground">
                              {' '}
                              {converted?.unit || ing.unit}
                            </span>
                          )}
                          <span> {split.name}</span>
                        </>
                      )}
                      {(() => {
                        const badge = (txt, cls, extra = '') => (
                          <span className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[11px] font-semibold ${cls} ${extra}`}>{txt}</span>
                        );
                        const proView = !!user?.is_pro;
                        if (proView && lineMacros && lineMacros[idx]) {
                          // Badges follow the line as shown: version / Low FODMAP list, scaled by
                          // the macro solver or the servings picker (same as the amounts).
                          const baseServings = Number(recipe.servings) > 0 ? Number(recipe.servings) : 4;
                          const factor = solver
                            ? solverFactor(macroRecipe, solver)
                            : (Number(scaledServings) > 0 ? Number(scaledServings) / baseServings : 1);
                          const im = scaleBadge(lineMacros[idx], factor);
                          const b = (v) => v;
                          // Where the numbers came from: food database match or AI estimate.
                          const sourceText = macroSourceText(lineMacros[idx], t, factor);
                          const infoOpen = macroInfoIdx === idx;
                          return (
                            <span className="flex flex-wrap items-center gap-1 mt-1.5" data-testid="ingredient-macros">
                              {badge(`P${b(im.p)}`, 'bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300')}
                              {(() => {
                                const bc = badgeCarbsForStyle(im, nutritionStyle);
                                const lbl = carbsLabels(nutritionStyle, bc.isTotal, t);
                                return (
                                  <span title={lbl.full} aria-label={`${lbl.full} ${bc.value} g`}>
                                    {badge(`C${b(bc.value)}`,'bg-sky-100 text-sky-700 dark:bg-sky-500/20 dark:text-sky-300')}
                                  </span>
                                );
                              })()}
                              {badge(`F${b(im.f)}`, 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300')}
                              {badge(`🔥${b(im.cal)}`, 'bg-amber-100 text-amber-700 dark:bg-amber-500/20 dark:text-amber-300')}
                              {sourceText && (
                                <button
                                  type="button"
                                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); setMacroInfoIdx(infoOpen ? null : idx); }}
                                  className="inline-flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-semibold text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring print:hidden"
                                  title={sourceText}
                                  aria-label={`${t('macroSrcInfo')}: ${sourceText}`}
                                  aria-expanded={infoOpen}
                                  data-testid="ingredient-macro-source"
                                >
                                  ⓘ
                                </button>
                              )}
                              {sourceText && infoOpen && (
                                <span className="basis-full text-[11px] text-muted-foreground" role="note">{sourceText}</span>
                              )}
                            </span>
                          );
                        }
                        if (!proView && typeof ing !== 'string') {
                          return (
                            <button
                              type="button"
                              onClick={() => toast('Laro Pro: macros for every ingredient', { description: 'Upgrade in Settings → Laro Pro', action: { label: 'Upgrade', onClick: () => navigate('/settings') } })}
                              className="flex flex-wrap items-center gap-1 mt-1.5 print:hidden"
                              aria-label="Unlock per-ingredient macros with Laro Pro"
                            >
                              {badge('P00', 'bg-rose-100 text-rose-700', 'blur-[2px] select-none')}
                              {badge('C00', 'bg-sky-100 text-sky-700', 'blur-[2px] select-none')}
                              {badge('F00', 'bg-emerald-100 text-emerald-700', 'blur-[2px] select-none')}
                              {badge('🔥000', 'bg-amber-100 text-amber-700', 'blur-[2px] select-none')}
                              <span className="text-[11px] text-laro font-semibold ml-0.5">🔒 Pro</span>
                            </button>
                          );
                        }
                        return null;
                      })()}
                    </span>
                    <IngredientSubstituteButton
                      ingredientName={displayName}
                      canApply={isOwner && !activeVersion}
                      onApply={(newName) => handleApplySubstitution(idx, newName)}
                      recipeContext={recipe}
                    />
                  </li>
                  </React.Fragment>
                  );
                })}
              </ul>
            </section>

            {/* Instructions */}
            <section className="mb-8">
              <h2 className="font-heading text-xl font-semibold mb-4">{t('instructions')}</h2>
              <ol className="space-y-4" data-testid="instructions-list">
                {(shown.instructions || []).map((step, idx) => (
                  <li key={`step-${idx}`} className="flex gap-4">
                    <span className="flex-shrink-0 w-8 h-8 rounded-full bg-laro text-white flex items-center justify-center font-semibold text-sm">
                      {idx + 1}
                    </span>
                    <p className="pt-1">
                      {temperaturesForStyle(enrichStepWithAmounts(step, shown.ingredients, measurementUnit), nutritionStyle)}
                    </p>
                  </li>
                ))}
              </ol>
            </section>

            {/* Notes & tips from the cookbook page (timing, storage, to serve, …) */}
            {pageNotes.length > 0 && (
              <section className="mb-8" data-testid="page-notes">
                <h2 className="font-heading text-xl font-semibold mb-3">{t('pageNotesTitle')}</h2>
                <ul className="space-y-2">
                  {pageNotes.map((note, idx) => (
                    <li key={`note-${idx}`} className="text-sm leading-relaxed rounded-xl bg-cream-subtle px-4 py-3 whitespace-pre-line">
                      {note}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {/* Nutrition Calculator — gated by Preferences → showNutrition */}
            {showNutrition && (
              <section className="mb-6">
                {/* A version / Low FODMAP view calculates its own list and never saves over the Original. */}
                <NutritionCalculator 
                  key={storedMacros.variant ? choiceKey : 'original'}
                  recipeId={storedMacros.variant ? undefined : recipe.id}
                  ingredients={(storedMacros.variant ? shown.ingredients : recipe.ingredients)?.map(i => (typeof i === 'string' ? i : `${i.amount || ''} ${i.unit || ''} ${showFodmap && findSwap(i.name, lowFodmap?.swaps) ? findSwap(i.name, lowFodmap.swaps).to : i.name}`))}
                  servings={scaledServings || recipe.servings}
                  savedNutrition={storedMacros.variant ? (macrosPending ? null : displayNutrition) : recipe.nutrition}
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

            {/* Original source — kept at the bottom so it is not easy to tap on open */}
            {(recipe.source_author || recipe.source_url) && (
              <section
                className="mt-2 pt-6 border-t border-border/60"
                data-testid="recipe-original-source"
              >
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
                  {t('originalSource')}
                </p>
                <div className="flex flex-wrap items-center gap-3">
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
                      className="inline-block text-sm font-medium text-primary hover:underline"
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
                  {recipe.source_url && (
                    <a
                      href={recipe.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
                      data-testid="recipe-source-url"
                    >
                      <LinkIcon className="w-3.5 h-3.5" aria-hidden="true" />
                      {t('original')}
                    </a>
                  )}
                </div>
              </section>
            )}
          </div>
        </motion.article>
      </div>

      {/* Cook Mode */}
      {showCookMode && (
        <CookMode
          recipe={shown}
          versionName={activeVersion}
          lowFodmap={showFodmap}
          onClose={() => setShowCookMode(false)}
        />
      )}
      {showCheckNumbers && (
        <CheckNumbers
          recipe={shown}
          versionName={activeVersion}
          lowFodmap={showFodmap}
          mode="page"
          onClose={(_override, { saved } = {}) => {
            setShowCheckNumbers(false);
            if (saved) loadRecipe();
          }}
        />
      )}
    </Layout>
  );
};
