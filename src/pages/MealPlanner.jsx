import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { useNavigate } from 'react-router-dom';
import { recipeApi, mealPlanApi, aiApi, calendarApi, shoppingListApi } from '../lib/api';
import { getAiQuotaErrorMessage } from '../lib/aiQuota';
import { useLanguage } from '../context/LanguageContext';
import { useUserPreferences, weekStartsOnNumber } from '../hooks/useUserPreferences';
import {
  useLiveRefreshContext,
  useLiveRefreshEvent,
  EventType,
} from '../hooks/useLiveRefresh';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Checkbox } from '../components/ui/checkbox';
import { Calendar } from '../components/ui/calendar';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '../components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../components/ui/alert-dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { MEAL_TYPES } from '../lib/utils';
import {
  buildRepeatWeekPayloads,
  dayModeCues,
  loadPlanHorizon,
  nutritionStatus,
  resolveCalorieTarget,
  resolveProteinTarget,
  rollupDayNutrition,
  savePlanHorizon,
  suggestProteinSwaps,
} from '../lib/mealPlanNutrition';
import { parseAdultBoost, wantsFamilyOneMeal } from '../lib/familyMeal';
import { 
  Plus, 
  Trash2, 
  Loader2,
  ChevronLeft,
  ChevronRight,
  UtensilsCrossed,
  Sparkles,
  Download,
  CalendarDays,
  ShoppingCart,
  StickyNote,
  Refrigerator,
  FileUp,
  Link2,
  Search,
  RefreshCw,
  Home,
  Baby,
  Dumbbell,
  Copy,
  Users,
  Zap,
} from 'lucide-react';
import { toast } from 'sonner';
import { format, startOfWeek, endOfWeek, addWeeks, subWeeks, eachDayOfInterval, isSameDay, addDays, parseISO, differenceInCalendarWeeks } from 'date-fns';

function groupPreviewByAisle(items = []) {
  const groups = new Map();
  items.forEach((item, index) => {
    const aisle = item.category || 'Other';
    if (!groups.has(aisle)) groups.set(aisle, []);
    groups.get(aisle).push({ item, index, key: item.id || `${item.name}-${index}` });
  });
  return [...groups.entries()].sort(([a, rowsA], [b, rowsB]) => {
    const orderA = rowsA[0]?.item?.sort_order ?? (a === 'Other' ? 99 : 50);
    const orderB = rowsB[0]?.item?.sort_order ?? (b === 'Other' ? 99 : 50);
    if (orderA !== orderB) return orderA - orderB;
    return a.localeCompare(b);
  });
}

const MEAL_TYPE_KEYS = {
  Breakfast: 'breakfast',
  Lunch: 'lunch',
  Dinner: 'dinner',
  Snack: 'snack',
};

export const MealPlanner = () => {
  const navigate = useNavigate();
  const { t } = useLanguage();
  const { preferences } = useUserPreferences();
  const familyMode = wantsFamilyOneMeal(preferences);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [mealPlans, setMealPlans] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showAutoDialog, setShowAutoDialog] = useState(false);
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedMealType, setSelectedMealType] = useState('Dinner');
  const [selectedRecipe, setSelectedRecipe] = useState('');
  const [recipeSearch, setRecipeSearch] = useState('');
  const [entryType, setEntryType] = useState('recipe'); // recipe | note | leftover
  const [entryTitle, setEntryTitle] = useState('');
  const [entryNotes, setEntryNotes] = useState('');
  const [adding, setAdding] = useState(false);
  const [autoGenerating, setAutoGenerating] = useState(false);
  const [autoPreferences, setAutoPreferences] = useState('');
  /** Week start chosen in the auto-generate dialog (defaults to the viewed week). */
  const [autoPlanWeekStart, setAutoPlanWeekStart] = useState(null);
  /** Plan length: 7, 14, or 28 days (default 7). */
  const [autoPlanDays, setAutoPlanDays] = useState(7);
  const [showSwapDialog, setShowSwapDialog] = useState(false);
  const [swapMeal, setSwapMeal] = useState(null);
  const [swapRecipeId, setSwapRecipeId] = useState('');
  const [swapRecipeSearch, setSwapRecipeSearch] = useState('');
  const [swapping, setSwapping] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [shopping, setShopping] = useState(false);
  const [showShopReview, setShowShopReview] = useState(false);
  const [shopPreview, setShopPreview] = useState(null);
  const [shopSelected, setShopSelected] = useState({}); // key -> boolean
  const [confirmingShop, setConfirmingShop] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [importText, setImportText] = useState('');
  const [importFile, setImportFile] = useState(null);
  const [importUrl, setImportUrl] = useState('');
  const [importing, setImporting] = useState(false);
  const [importCreateShopping, setImportCreateShopping] = useState(true);
  const [importIncludeSourceNote, setImportIncludeSourceNote] = useState(false);
  const [importMode, setImportMode] = useState('url'); // url | manual | pdf
  const [packDrafts, setPackDrafts] = useState([]); // [{title, calories, protein, carbs, fat, ...}]
  const [importSourceUrl, setImportSourceUrl] = useState('');
  const [macrosFromOnline, setMacrosFromOnline] = useState(false);
  const [dayBusyness, setDayBusyness] = useState({}); // yyyy-MM-dd -> { level, ... }
  const [showRepeatConfirm, setShowRepeatConfirm] = useState(false);
  const [repeatingWeek, setRepeatingWeek] = useState(false);
  const [planHorizon, setPlanHorizon] = useState(() => loadPlanHorizon());
  const [proteinBoostDay, setProteinBoostDay] = useState(null); // Date | null
  const [tonightHeadcount, setTonightHeadcount] = useState(null);

  // Honor Preferences → weekStartsOn (default Monday)
  const weekStartsOn = weekStartsOnNumber(preferences.weekStartsOn, 1);
  const weekStart = startOfWeek(currentDate, { weekStartsOn });
  const weekEnd = endOfWeek(currentDate, { weekStartsOn });
  const weekDays = eachDayOfInterval({ start: weekStart, end: weekEnd });
  const liveRefresh = useLiveRefreshContext();
  const proteinTarget = resolveProteinTarget(preferences);
  const calorieTarget = resolveCalorieTarget(preferences);
  const dinnerHeadcount =
    tonightHeadcount != null
      ? tonightHeadcount
      : preferences.dinnerHeadcount != null && preferences.dinnerHeadcount !== ''
        ? Number(preferences.dinnerHeadcount)
        : preferences.defaultServings != null
          ? Number(preferences.defaultServings)
          : null;

  const weekStartKey = format(weekStart, 'yyyy-MM-dd');
  const weekEndKey = format(weekEnd, 'yyyy-MM-dd');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [plansRes, recipesRes] = await Promise.all([
        mealPlanApi.getAll({
          start_date: weekStartKey,
          end_date: weekEndKey,
        }),
        recipeApi.getAll(),
      ]);
      setMealPlans(plansRes.data);
      setRecipes(recipesRes.data);
    } catch (error) {
      toast.error(`${t('toastLoadMealPlansFailed')} (E-MP001)`);
    } finally {
      setLoading(false);
    }
  }, [weekStartKey, weekEndKey, t]);

  const loadBusyness = useCallback(async () => {
    const calendarOn =
      preferences?.useCalendarForMealDifficulty &&
      (preferences?.calendarIcsUrl || '').trim();
    if (!calendarOn) {
      setDayBusyness({});
      return;
    }
    try {
      const res = await calendarApi.getBusyness(weekStartKey, 7);
      const map = {};
      (res.data?.days || []).forEach((d) => {
        if (d?.date) map[d.date] = d;
      });
      setDayBusyness(map);
    } catch {
      setDayBusyness({});
    }
  }, [
    weekStartKey,
    preferences?.useCalendarForMealDifficulty,
    preferences?.calendarIcsUrl,
  ]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    loadBusyness();
  }, [loadBusyness]);

  useLiveRefreshEvent(
    EventType.RECIPE_DELETED,
    useCallback((data) => {
      const id = data?.id;
      if (!id) {
        loadData();
        return;
      }
      setRecipes((prev) => prev.filter((r) => r.id !== id));
    }, [loadData]),
    liveRefresh
  );
  useLiveRefreshEvent(
    [EventType.RECIPE_CREATED, EventType.RECIPE_UPDATED, EventType.MEAL_PLAN_CREATED, EventType.MEAL_PLAN_UPDATED, EventType.MEAL_PLAN_DELETED],
    useCallback(() => {
      loadData();
    }, [loadData]),
    liveRefresh
  );

  const getMealsForDay = (date) => {
    const dateStr = format(date, 'yyyy-MM-dd');
    return mealPlans.filter(plan => plan.date === dateStr);
  };

  const handleAddMeal = async () => {
    if (!selectedDate) return;
    if (entryType === 'recipe' && !selectedRecipe) return;
    if (entryType !== 'recipe' && !entryTitle.trim()) return;

    setAdding(true);
    try {
      const payload = {
        date: format(selectedDate, 'yyyy-MM-dd'),
        meal_type: selectedMealType,
        entry_type: entryType,
        notes: entryNotes.trim(),
      };
      if (entryType === 'recipe') {
        payload.recipe_id = selectedRecipe;
      } else {
        payload.recipe_title = entryTitle.trim();
      }
      await mealPlanApi.create(payload);
      toast.success(
        entryType === 'leftover'
          ? t('toastLeftoversAdded')
          : entryType === 'note'
            ? t('toastNoteAdded')
            : t('toastMealAdded')
      );
      setShowAddDialog(false);
      setSelectedRecipe('');
      setRecipeSearch('');
      setEntryTitle('');
      setEntryNotes('');
      setEntryType('recipe');
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('toastAddItemFailed')} (E-MP002)`);
    } finally {
      setAdding(false);
    }
  };

  const handleDeleteMeal = async (planId) => {
    // Optimistic remove so stale ghost meals disappear immediately (E-MP003)
    setMealPlans((prev) => prev.filter((p) => p.id !== planId));
    try {
      await mealPlanApi.delete(planId);
      toast.success(t('toastMealRemoved'));
    } catch (error) {
      if (error?.response?.status === 404) {
        toast.success(t('toastMealRemoved'));
        return;
      }
      toast.error(`${t('toastRemoveItemFailed')} (E-MP003)`);
      loadData();
    }
  };

  const handleRepeatWeek = async () => {
    if (!mealPlans.length) {
      toast.error(t('toastRepeatWeekEmpty'));
      setShowRepeatConfirm(false);
      return;
    }
    setRepeatingWeek(true);
    try {
      const res = await mealPlanApi.repeatWeek({
        start_date: format(weekStart, 'yyyy-MM-dd'),
        end_date: format(weekEnd, 'yyyy-MM-dd'),
        day_offset: 7,
      });
      const created = res.data?.created ?? 0;
      toast.success(t('toastWeekRepeated', { count: created }));
      setShowRepeatConfirm(false);
      setCurrentDate(addWeeks(weekStart, 1));
    } catch (error) {
      if (error?.response?.status === 404) {
        try {
          const nextStart = format(addWeeks(weekStart, 1), 'yyyy-MM-dd');
          const nextEnd = format(addWeeks(weekEnd, 1), 'yyyy-MM-dd');
          const existingNext = await mealPlanApi.getAll({
            start_date: nextStart,
            end_date: nextEnd,
          });
          await Promise.all(
            (existingNext.data || []).map(async (p) => {
              try {
                await mealPlanApi.delete(p.id);
              } catch (err) {
                if (err?.response?.status !== 404) throw err;
              }
            })
          );
          const payloads = buildRepeatWeekPayloads(mealPlans, { dayOffset: 7 });
          for (const payload of payloads) {
            await mealPlanApi.create(payload);
          }
          toast.success(t('toastWeekRepeated', { count: payloads.length }));
          setShowRepeatConfirm(false);
          setCurrentDate(addWeeks(weekStart, 1));
          return;
        } catch (fallbackErr) {
          toast.error(
            fallbackErr.response?.data?.detail ||
              `${t('toastRepeatWeekFailed')} (E-MP011)`
          );
          return;
        }
      }
      toast.error(error.response?.data?.detail || `${t('toastRepeatWeekFailed')} (E-MP011)`);
    } finally {
      setRepeatingWeek(false);
    }
  };

  const openProteinBoost = (day) => {
    setProteinBoostDay(day);
  };

  const applyProteinSwap = async (suggestion) => {
    if (!suggestion?.mealId || !suggestion?.recipeId) return;
    setSwapping(true);
    try {
      await mealPlanApi.update(suggestion.mealId, {
        recipe_id: suggestion.recipeId,
        entry_type: 'recipe',
      });
      toast.success(t('toastRecipeSwapped'));
      setProteinBoostDay(null);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('toastSwapRecipeFailed')} (E-MP010)`);
    } finally {
      setSwapping(false);
    }
  };

  const openAutoDialog = () => {
    setAutoPlanWeekStart(weekStart);
    setAutoPlanDays(7);
    setShowAutoDialog(true);
  };

  const openSwapDialog = (meal) => {
    setSwapMeal(meal);
    setSwapRecipeId('');
    setSwapRecipeSearch('');
    setShowSwapDialog(true);
  };

  const handleSwapRecipe = async () => {
    if (!swapMeal?.id || !swapRecipeId) return;
    if (swapRecipeId === swapMeal.recipe_id) {
      setShowSwapDialog(false);
      return;
    }

    setSwapping(true);
    try {
      await mealPlanApi.update(swapMeal.id, {
        recipe_id: swapRecipeId,
        entry_type: 'recipe',
      });
      toast.success(t('toastRecipeSwapped'));
      setShowSwapDialog(false);
      setSwapMeal(null);
      setSwapRecipeId('');
      setSwapRecipeSearch('');
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('toastSwapRecipeFailed')} (E-MP010)`);
    } finally {
      setSwapping(false);
    }
  };

  const handleAutoGenerate = async () => {
    if (recipes.length < 3) {
      toast.error(t('toastNeedThreeRecipes'));
      return;
    }

    const planDays = [7, 14, 28].includes(autoPlanDays) ? autoPlanDays : 7;
    const targetWeekStart = startOfWeek(autoPlanWeekStart || weekStart, { weekStartsOn });
    const targetPlanEnd = addDays(targetWeekStart, planDays - 1);

    setAutoGenerating(true);
    try {
      const startDate = format(targetWeekStart, 'yyyy-MM-dd');
      // Server applies for planDays (normalizes 1-based AI days + clears range)
      const res = await aiApi.autoMealPlan(planDays, autoPreferences, [], {
        start_date: startDate,
        apply: true,
        replace_week: true,
      });
      const plan = res.data || {};
      const created = plan.created ?? 0;

      // Legacy fallback: older backends only return the plan JSON
      if (!plan.applied && created === 0 && Array.isArray(plan.plan) && plan.plan.length) {
        for (const existingPlan of mealPlans) {
          await mealPlanApi.delete(existingPlan.id);
        }
        for (const day of plan.plan) {
          const date = day.date
            ? parseISO(day.date)
            : addDays(targetWeekStart, Number(day.day) || 0);
          for (const meal of day.meals || []) {
            if (meal.recipe_id) {
              await mealPlanApi.create({
                date: format(date, 'yyyy-MM-dd'),
                meal_type: meal.meal_type,
                recipe_id: meal.recipe_id,
              });
            }
          }
        }
      }

      toast.success(t('toastMealPlanGenerated'));
      setShowAutoDialog(false);
      // Jump the planner to the week we just filled so meals are visible
      setCurrentDate(targetWeekStart);
      const weeks = Math.ceil(planDays / 7);
      if (weeks > 1) {
        const horizon = savePlanHorizon({
          anchorStart: startDate,
          weeks,
        });
        setPlanHorizon(horizon);
      } else {
        setPlanHorizon(null);
      }
      if (
        isSameDay(targetWeekStart, weekStart) &&
        targetPlanEnd >= weekStart &&
        targetWeekStart <= weekEnd
      ) {
        loadData();
      }
    } catch (error) {
      toast.error(
        getAiQuotaErrorMessage(
          error,
          "Couldn't generate your meal plan. Please try again. (E-MP004)"
        )
      );
    } finally {
      setAutoGenerating(false);
    }
  };

  const resetImportDialog = () => {
    setImportText('');
    setImportFile(null);
    setImportUrl('');
    setPackDrafts([]);
    setImportSourceUrl('');
    setMacrosFromOnline(false);
    setImportMode('url');
    setImportIncludeSourceNote(false);
  };

  const handleFetchMealPacks = async () => {
    if (!importUrl.trim()) {
      toast.error('Paste a Huel (or similar) product URL');
      return;
    }
    setImporting(true);
    try {
      const startDate = format(weekStart, 'yyyy-MM-dd');
      const res = await aiApi.importMealPlanUrl({
        url: importUrl.trim(),
        start_date: startDate,
        apply: false,
        replace_week: true,
        create_shopping_list: importCreateShopping,
        include_source_note: importIncludeSourceNote,
        schedule: true,
      });
      const data = res.data || {};
      if (data.import_mode === 'meal_plan' && data.applied) {
        toast.success(t('toastMealPlanGenerated'));
        setShowImportDialog(false);
        resetImportDialog();
        loadData();
        return;
      }
      const products = data.plan?.products || [];
      if (!products.length) {
        toast.error('No meal packs found — add one manually with macros');
        setImportMode('manual');
        setPackDrafts([
          { title: '', calories: '', protein: '', carbs: '', fat: '', kind: 'shake' },
        ]);
        return;
      }
      setImportSourceUrl(data.source_url || importUrl.trim());
      setPackDrafts(
        products.map((p) => ({
          title: p.title || '',
          kind: p.kind || 'meal',
          meal_type: p.meal_type || undefined,
          description: p.description || '',
          ingredients: p.ingredients || [],
          instructions: p.instructions || [],
          tags: p.tags || ['meal-pack'],
          image_url: p.image_url || '',
          servings: p.servings || 1,
          calories: p.calories ?? p.nutrition?.calories ?? '',
          protein: p.protein ?? p.nutrition?.protein ?? '',
          carbs: p.carbs ?? p.nutrition?.carbs ?? '',
          fat: p.fat ?? p.nutrition?.fat ?? '',
          needs_macros: !!p.needs_macros,
        }))
      );
      setMacrosFromOnline(products.some((p) => (p.calories ?? p.nutrition?.calories) != null));
      setImportMode('macros');
      if (data.needs_macros) {
        toast.message('Fill in missing calories / macros, then import');
      } else {
        toast.success('Macros found online — review and import');
      }
    } catch (error) {
      toast.error(
        getAiQuotaErrorMessage(
          error,
          error.response?.data?.detail ||
            "Couldn't fetch that page. Add the pack manually with macros instead."
        )
      );
      setImportMode('manual');
      setPackDrafts([
        { title: '', calories: '', protein: '', carbs: '', fat: '', kind: 'shake' },
      ]);
    } finally {
      setImporting(false);
    }
  };

  const handleConfirmMealPacks = async () => {
    const cleaned = packDrafts
      .map((p) => ({
        ...p,
        title: (p.title || '').trim(),
        calories: p.calories === '' || p.calories == null ? null : Number(p.calories),
        protein: p.protein === '' || p.protein == null ? null : Number(p.protein),
        carbs: p.carbs === '' || p.carbs == null ? null : Number(p.carbs),
        fat: p.fat === '' || p.fat == null ? null : Number(p.fat),
      }))
      .filter((p) => p.title);

    if (!cleaned.length) {
      toast.error('Add at least one pack name');
      return;
    }
    const missing = cleaned.filter((p) => p.calories == null || Number.isNaN(p.calories));
    if (missing.length) {
      toast.error(`Enter calories for: ${missing.map((p) => p.title).join(', ')}`);
      return;
    }

    setImporting(true);
    try {
      const startDate = format(weekStart, 'yyyy-MM-dd');
      const res = await aiApi.importMealPlanUrl({
        url: importSourceUrl || importUrl.trim() || undefined,
        start_date: startDate,
        apply: true,
        replace_week: true,
        create_shopping_list: importCreateShopping,
        include_source_note: importIncludeSourceNote,
        schedule: true,
        products: cleaned.map((p) => ({
          title: p.title,
          kind: p.kind || 'meal',
          meal_type: p.meal_type,
          description: p.description || '',
          ingredients: p.ingredients,
          instructions: p.instructions,
          tags: p.tags || ['meal-pack'],
          image_url: p.image_url || '',
          servings: p.servings || 1,
          calories: p.calories,
          protein: p.protein,
          carbs: p.carbs,
          fat: p.fat,
        })),
      });
      const data = res.data || {};
      if (data.status === 'needs_macros') {
        toast.error(data.detail || 'Enter calories for each pack');
        return;
      }
      const created = data.recipes_created ?? 0;
      const reused = data.recipes_reused ?? 0;
      const slots = data.slots_created ?? 0;
      toast.success(
        `Saved ${created + reused} meal pack${created + reused === 1 ? '' : 's'} to Recipes` +
          (slots ? ` · ${slots} on this week` : '')
      );
      if (data.shopping_list_id) toast.message(t('toastShoppingListCreated'));
      setShowImportDialog(false);
      resetImportDialog();
      loadData();
    } catch (error) {
      toast.error(
        getAiQuotaErrorMessage(
          error,
          error.response?.data?.detail || "Couldn't save meal packs. (E-MP006)"
        )
      );
    } finally {
      setImporting(false);
    }
  };

  const handleImportMealPlan = async () => {
    if (importMode === 'url') {
      await handleFetchMealPacks();
      return;
    }
    if (importMode === 'macros' || importMode === 'manual') {
      await handleConfirmMealPacks();
      return;
    }
    if (!importFile && !importText.trim()) {
      toast.error('Upload a PDF or paste the plan text');
      return;
    }

    setImporting(true);
    try {
      let res;
      const startDate = format(weekStart, 'yyyy-MM-dd');
      if (importFile) {
        const fd = new FormData();
        fd.append('file', importFile);
        fd.append('start_date', startDate);
        fd.append('apply', 'true');
        fd.append('replace_week', 'true');
        fd.append('create_shopping_list', importCreateShopping ? 'true' : 'false');
        fd.append('include_source_note', importIncludeSourceNote ? 'true' : 'false');
        // Dedicated meal-plan endpoint schedules the week (import-pdf with
        // context=recipes only adds to the library — that looked "broken").
        res = await aiApi.importMealPlanPdf(fd);
      } else {
        res = await aiApi.importMealPlan({
          text: importText,
          start_date: startDate,
          apply: true,
          replace_week: true,
          create_shopping_list: importCreateShopping,
          include_source_note: importIncludeSourceNote,
        });
      }

      const data = res.data || {};
      if (data.kind === 'recipes') {
        const n = data.recipe_count ?? data.recipes?.length ?? 0;
        toast.success(
          data.message ||
            `Imported ${n} recipe(s) from the PDF into your library (not a weekly schedule).`
        );
        setShowImportDialog(false);
        resetImportDialog();
        // Recipes live under Recipes → tap Needs review if you don't see them yet
        return;
      }
      const created = data.recipes_created ?? 0;
      const reused = data.recipes_reused ?? 0;
      const slots = data.slots_created ?? 0;
      // Jump calendar to the week we just scheduled (import may target next week)
      const importedStart = data.start_date || startDate;
      let rangeLabel = '';
      if (importedStart) {
        try {
          const start = parseISO(String(importedStart).slice(0, 10));
          const end = addDays(start, 6);
          setCurrentDate(start);
          rangeLabel = ` · ${format(start, 'MMM d')}–${format(end, 'MMM d')}`;
        } catch {
          /* keep current week */
        }
      }
      toast.success(
        `Imported ${data.plan?.title || 'meal plan'}: ${created} new recipes` +
          (reused ? `, ${reused} reused` : '') +
          `, ${slots} meals scheduled` +
          rangeLabel
      );
      if (created + reused > 0) {
        toast.message('Recipes are in your library (Recipes → Needs review)');
      }
      if (data.shopping_list_id) {
        toast.message(t('toastShoppingListCreated'));
      }
      setShowImportDialog(false);
      resetImportDialog();
      // loadData runs via useEffect when currentDate changes; call anyway if week unchanged
      loadData();
    } catch (error) {
      toast.error(
        getAiQuotaErrorMessage(
          error,
          error.response?.data?.detail ||
            "Couldn't import that meal plan. Try a text-based PDF or paste the meal breakdown. (E-MP006)"
        )
      );
    } finally {
      setImporting(false);
    }
  };

  const handleExportCalendar = async () => {
    setExporting(true);
    try {
      const res = await calendarApi.exportIcal(
        format(weekStart, 'yyyy-MM-dd'),
        format(addWeeks(weekEnd, 4), 'yyyy-MM-dd')
      );
      
      const blob = new Blob([res.data], { type: 'text/calendar' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'laro-meals.ics';
      a.click();
      window.URL.revokeObjectURL(url);
      
      toast.success(t('toastCalendarExported'));
    } catch (error) {
      toast.error(error.response?.data?.detail || "Couldn't export your calendar. Please try again. (E-MP005)");
    } finally {
      setExporting(false);
    }
  };

  const handleShopThisPlan = async () => {
    const recipeMeals = mealPlans.filter(
      (p) => (p.entry_type || 'recipe') === 'recipe' && p.recipe_id
    );
    if (recipeMeals.length === 0) {
      toast.error(t('toastAddRecipeMealsFirst'));
      return;
    }
    setShopping(true);
    try {
      const start = format(weekStart, 'yyyy-MM-dd');
      const end = format(weekEnd, 'yyyy-MM-dd');
      // Preview only — SideChef-style review before save
      const res = await shoppingListApi.fromMealPlan({
        start_date: start,
        end_date: end,
        exclude_pantry: true,
        combine_quantities: true,
        assign_aisles: true,
        keep_pantry_items: true,
        save: false,
        list_name: `Week of ${format(weekStart, 'MMM d')}`,
      });
      const items = res.data.items || [];
      if (items.length === 0) {
        toast.error(t('toastNothingToShop'));
        return;
      }
      const selected = {};
      items.forEach((item, index) => {
        const key = item.id || `${item.name}-${index}`;
        // Pantry staples default off so you review before buying
        selected[key] = !item.in_pantry;
      });
      setShopPreview(res.data);
      setShopSelected(selected);
      setShowShopReview(true);
    } catch (error) {
      const detail = error.response?.data?.detail;
      toast.error(
        typeof detail === 'string'
          ? detail
          : detail?.message || "Couldn't build a shopping list from this plan. (E-MP006)"
      );
    } finally {
      setShopping(false);
    }
  };

  const shopAisleGroups = useMemo(
    () => groupPreviewByAisle(shopPreview?.items || []),
    [shopPreview]
  );

  const selectedShopCount = useMemo(
    () => Object.values(shopSelected).filter(Boolean).length,
    [shopSelected]
  );

  const handleConfirmShop = async () => {
    if (!shopPreview) return;
    const items = (shopPreview.items || []).filter((item, index) => {
      const key = item.id || `${item.name}-${index}`;
      return shopSelected[key];
    });
    if (items.length === 0) {
      toast.error(t('toastSelectAtLeastOne'));
      return;
    }
    setConfirmingShop(true);
    try {
      await shoppingListApi.create({
        name: shopPreview.list_name || `Week of ${format(weekStart, 'MMM d')}`,
        items: items.map(({ in_pantry, ...rest }) => ({
          ...rest,
          checked: false,
          in_pantry: !!in_pantry,
        })),
      });
      toast.success(t('toastShoppingListReady', { count: items.length }));
      setShowShopReview(false);
      setShopPreview(null);
      navigate('/shopping');
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('toastCreateListFailed')} (E-MP007)`);
    } finally {
      setConfirmingShop(false);
    }
  };

  const toggleShopAisle = (rows, checked) => {
    setShopSelected((prev) => {
      const next = { ...prev };
      rows.forEach(({ key }) => {
        next[key] = checked;
      });
      return next;
    });
  };

  const openAddDialog = (date, mealType = 'Dinner') => {
    setSelectedDate(date);
    setSelectedMealType(mealType);
    setEntryType('recipe');
    setEntryTitle('');
    setEntryNotes('');
    setSelectedRecipe('');
    setRecipeSearch('');
    setShowAddDialog(true);
  };

  const filterRecipesByQuery = (list, query) => {
    const q = query.trim().toLowerCase();
    if (!q) return list;
    return list.filter((recipe) => {
      const title = String(recipe.title || '').toLowerCase();
      const category = String(recipe.category || '').toLowerCase();
      const tags = (recipe.tags || []).map((tag) => String(tag).toLowerCase());
      return (
        title.includes(q) ||
        category.includes(q) ||
        tags.some((tag) => tag.includes(q))
      );
    });
  };

  const filteredRecipesForPicker = useMemo(
    () => filterRecipesByQuery(recipes, recipeSearch),
    [recipes, recipeSearch]
  );

  const filteredRecipesForSwap = useMemo(
    () => filterRecipesByQuery(recipes, swapRecipeSearch),
    [recipes, swapRecipeSearch]
  );

  const proteinBoostSuggestions = useMemo(() => {
    if (!proteinBoostDay) return null;
    const meals = getMealsForDay(proteinBoostDay);
    return suggestProteinSwaps({
      meals,
      recipes,
      proteinTarget,
      limit: 6,
    });
  }, [proteinBoostDay, mealPlans, recipes, proteinTarget]);

  const multiWeekTabs = useMemo(() => {
    if (!planHorizon?.anchorStart || !(planHorizon.weeks > 1)) return [];
    const anchor = parseISO(planHorizon.anchorStart);
    if (Number.isNaN(anchor.getTime())) return [];
    const anchorWeek = startOfWeek(anchor, { weekStartsOn });
    return Array.from({ length: planHorizon.weeks }, (_, i) => {
      const start = addWeeks(anchorWeek, i);
      return {
        index: i,
        label: t('planWeekN', { n: i + 1 }),
        start,
        end: endOfWeek(start, { weekStartsOn }),
        active: isSameDay(start, weekStart),
      };
    });
  }, [planHorizon, weekStartsOn, weekStart, t]);

  const activeWeekIndex = useMemo(() => {
    if (!planHorizon?.anchorStart) return null;
    const anchor = parseISO(planHorizon.anchorStart);
    if (Number.isNaN(anchor.getTime())) return null;
    const anchorWeek = startOfWeek(anchor, { weekStartsOn });
    const idx = differenceInCalendarWeeks(weekStart, anchorWeek, { weekStartsOn });
    if (idx < 0 || idx >= (planHorizon.weeks || 0)) return null;
    return idx;
  }, [planHorizon, weekStart, weekStartsOn]);

  return (
    <Layout reading>
      <div className="space-y-8" data-testid="meal-planner">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-4"
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="font-heading text-3xl font-bold">{t('mealPlanner')}</h1>
              <p className="text-muted-foreground mt-1">{t('planWeeklyMeals')}</p>
            </div>

          <div className="flex items-center gap-2 self-start sm:self-auto max-w-full">
              <Button
                variant="outline"
                size="icon"
                onClick={() => setCurrentDate(subWeeks(currentDate, 1))}
                className="rounded-full shrink-0"
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <div className="px-3 sm:px-4 py-2 bg-white rounded-full border border-border/60 text-center min-w-0 flex-1 sm:flex-none sm:min-w-[11rem]">
                <span className="font-medium text-xs sm:text-sm md:text-base whitespace-nowrap">
                  {format(weekStart, 'MMM d')} – {format(weekEnd, 'MMM d, yyyy')}
                </span>
              </div>
              <Button
                variant="outline"
                size="icon"
                onClick={() => setCurrentDate(addWeeks(currentDate, 1))}
                className="rounded-full shrink-0"
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              className="rounded-full bg-laro hover:bg-laro-dark"
              onClick={handleShopThisPlan}
              disabled={shopping || mealPlans.length === 0}
              data-testid="shop-this-plan-btn"
            >
              {shopping ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <ShoppingCart className="w-4 h-4 mr-2" />
              )}
              {t('shopThisPlan')}
            </Button>
            <Button
              variant="outline"
              className="rounded-full"
              onClick={openAutoDialog}
              data-testid="auto-generate-btn"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              {t('autoPlan')}
            </Button>
            <Button
              variant="outline"
              className="rounded-full"
              onClick={() => setShowRepeatConfirm(true)}
              disabled={!mealPlans.length || repeatingWeek}
              data-testid="repeat-week-btn"
            >
              {repeatingWeek ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Copy className="w-4 h-4 mr-2" />
              )}
              {t('repeatWeek')}
            </Button>
            <Button
              variant="outline"
              className="rounded-full"
              onClick={() => setShowImportDialog(true)}
              data-testid="import-meal-plan-btn"
            >
              <FileUp className="w-4 h-4 mr-2" />
              {t('importPlan')}
            </Button>
            <Button
              variant="outline"
              className="rounded-full"
              onClick={handleExportCalendar}
              disabled={exporting}
              data-testid="export-calendar-btn"
            >
              {exporting ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Download className="w-4 h-4 mr-2" />
              )}
              {t('export')}
            </Button>
          </div>

          {multiWeekTabs.length > 0 && (
            <div
              className="flex flex-wrap items-center gap-2"
              data-testid="meal-plan-week-tabs"
            >
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                {t('planWeeks')}
              </span>
              {multiWeekTabs.map((tab) => (
                <button
                  key={tab.index}
                  type="button"
                  data-testid={`meal-plan-week-tab-${tab.index + 1}`}
                  onClick={() => setCurrentDate(tab.start)}
                  className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    tab.active || activeWeekIndex === tab.index
                      ? 'bg-laro text-white'
                      : 'bg-white border border-border/60 hover:bg-laro-light/40'
                  }`}
                >
                  {tab.label}
                  <span className="ml-1.5 text-[10px] opacity-80">
                    {format(tab.start, 'MMM d')}
                  </span>
                </button>
              ))}
            </div>
          )}

          {dinnerHeadcount != null && Number.isFinite(dinnerHeadcount) && (
            <div
              className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground"
              data-testid="dinner-headcount-strip"
            >
              <Users className="w-4 h-4 text-laro" />
              <span>{t('dinnerHeadcountLabel')}</span>
              <div className="inline-flex items-center gap-1">
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <button
                    key={n}
                    type="button"
                    data-testid={`dinner-headcount-${n}`}
                    onClick={() => setTonightHeadcount(n)}
                    className={`w-8 h-8 rounded-full text-xs font-semibold transition-colors ${
                      Number(dinnerHeadcount) === n
                        ? 'bg-laro text-white'
                        : 'bg-white border border-border/60 hover:bg-laro-light/50'
                    }`}
                  >
                    {n}
                  </button>
                ))}
              </div>
              <span className="text-xs">{t('dinnerHeadcountHint')}</span>
            </div>
          )}
        </motion.div>

        {/* Week agenda — one day per row so titles stay readable */}
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-laro" />
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="space-y-3"
          >
            {weekDays.map((day) => {
              const meals = getMealsForDay(day);
              const isToday = isSameDay(day, new Date());
              const dayKey = format(day, 'yyyy-MM-dd');
              const busy = dayBusyness[dayKey];
              const busyLevel = busy?.level;
              const cues = dayModeCues(day, preferences, busy);
              const dayTotals = rollupDayNutrition(meals, recipes);
              const dayStatus = nutritionStatus(dayTotals, {
                proteinTarget,
                calorieTarget,
              });
              const proteinBoost = suggestProteinSwaps({
                meals,
                recipes,
                proteinTarget,
                limit: 1,
              });

              return (
                <div
                  key={day.toISOString()}
                  className={`bg-white rounded-2xl border px-4 py-4 sm:px-5 sm:py-5 ${
                    isToday ? 'border-laro border-2 shadow-sm' : 'border-border/60'
                  }`}
                  data-testid={`meal-day-${dayKey}`}
                >
                  <div className="flex items-center justify-between gap-3 mb-2 sm:mb-3">
                    <div className="flex items-baseline gap-3 min-w-0">
                      <p
                        className={`font-heading font-bold text-2xl tabular-nums leading-none ${
                          isToday ? 'text-laro' : 'text-foreground'
                        }`}
                      >
                        {format(day, 'd')}
                      </p>
                      <div className="min-w-0">
                        <p className="font-medium text-foreground leading-tight">
                          {format(day, 'EEEE')}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {format(day, 'MMM yyyy')}
                          {isToday ? ` · ${t('today')}` : ''}
                        </p>
                      </div>
                      <div
                        className="flex items-center gap-1.5 shrink-0"
                        data-testid={`day-mode-icons-${dayKey}`}
                      >
                        {cues.wfh ? (
                          <span
                            title={t('dayModeWfh')}
                            className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-sky-50 text-sky-800"
                            data-testid={`day-mode-wfh-${dayKey}`}
                          >
                            <Home className="w-3.5 h-3.5" />
                          </span>
                        ) : null}
                        {cues.gym ? (
                          <span
                            title={t('dayModeGym')}
                            className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-violet-50 text-violet-800"
                            data-testid={`day-mode-gym-${dayKey}`}
                          >
                            <Dumbbell className="w-3.5 h-3.5" />
                          </span>
                        ) : null}
                        {cues.kidNight ? (
                          <span
                            title={
                              cues.familyOneMeal
                                ? t('dayModeFamilyMeal')
                                : t('dayModeKidNight')
                            }
                            className="inline-flex items-center justify-center w-7 h-7 rounded-md bg-rose-50 text-rose-800"
                            data-testid={`day-mode-kid-${dayKey}`}
                          >
                            {cues.familyOneMeal ? (
                              <Users className="w-3.5 h-3.5" />
                            ) : (
                              <Baby className="w-3.5 h-3.5" />
                            )}
                          </span>
                        ) : null}
                        {busyLevel ? (
                          <span
                            data-testid={`calendar-busy-${dayKey}`}
                            title={
                              busyLevel === 'busy'
                                ? t('calendarDayBusy')
                                : busyLevel === 'moderate'
                                  ? t('calendarDayModerate')
                                  : t('calendarDayFree')
                            }
                            className={`shrink-0 text-[10px] font-medium uppercase tracking-wide px-2 py-0.5 rounded-md ${
                              busyLevel === 'busy'
                                ? 'bg-amber-100 text-amber-900 dark:bg-amber-950/50 dark:text-amber-200'
                                : busyLevel === 'moderate'
                                  ? 'bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-200'
                                  : 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200'
                            }`}
                          >
                            {busyLevel === 'busy'
                              ? t('calendarDayBusy')
                              : busyLevel === 'moderate'
                                ? t('calendarDayModerate')
                                : t('calendarDayFree')}
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-full shrink-0"
                      onClick={() => openAddDialog(day)}
                      data-testid={`add-meal-${format(day, 'yyyy-MM-dd')}`}
                    >
                      <Plus className="w-4 h-4 mr-1" />
                      {t('add')}
                    </Button>
                  </div>

                  {(proteinTarget || calorieTarget || dayTotals.hasAnyNutrition) && (
                    <div
                      className={`mb-3 flex flex-wrap items-center gap-2 rounded-xl px-3 py-2 text-xs sm:text-sm ${
                        dayStatus.overall === 'green'
                          ? 'bg-emerald-50 text-emerald-900'
                          : dayStatus.overall === 'amber'
                            ? 'bg-amber-50 text-amber-950'
                            : 'bg-cream-subtle text-muted-foreground'
                      }`}
                      data-testid={`day-nutrition-${dayKey}`}
                    >
                      <span className="font-medium tabular-nums">
                        {t('dayProteinStrip', {
                          current: dayTotals.protein,
                          target: proteinTarget != null ? Math.round(proteinTarget) : '—',
                        })}
                      </span>
                      {calorieTarget != null && (
                        <span className="tabular-nums opacity-90">
                          ·{' '}
                          {t('dayCalorieStrip', {
                            current: dayTotals.calories,
                            target: Math.round(calorieTarget),
                          })}
                        </span>
                      )}
                      {proteinBoost.underTarget && proteinBoost.suggestions.length > 0 && (
                        <button
                          type="button"
                          className="ml-auto inline-flex items-center gap-1 rounded-full bg-white/80 border border-amber-200 px-2.5 py-1 text-[11px] font-semibold text-amber-900 hover:bg-white"
                          onClick={() => openProteinBoost(day)}
                          data-testid={`boost-protein-${dayKey}`}
                        >
                          <Zap className="w-3 h-3" />
                          {t('swapToHitProtein')}
                        </button>
                      )}
                    </div>
                  )}

                  {meals.length === 0 ? (
                    <button
                      type="button"
                      onClick={() => openAddDialog(day)}
                      className="w-full text-left rounded-xl border border-dashed border-border/70 px-4 py-3 text-sm text-muted-foreground hover:border-laro/40 hover:bg-laro-light/30 transition-colors"
                    >
                      {t('noMealsPlannedTap')}
                    </button>
                  ) : (
                    <div className="space-y-2">
                      {meals.map((meal) => {
                        const kind = meal.entry_type || 'recipe';
                        const canOpenRecipe = kind === 'recipe' && !!meal.recipe_id;
                        const adultBoost = parseAdultBoost(meal);
                        const showFamilyBadge = familyMode && kind === 'recipe';
                        return (
                          <div
                            key={meal.id}
                            role={canOpenRecipe ? 'button' : undefined}
                            tabIndex={canOpenRecipe ? 0 : undefined}
                            onClick={() => {
                              if (canOpenRecipe) navigate(`/recipes/${meal.recipe_id}`);
                            }}
                            onKeyDown={(e) => {
                              if (!canOpenRecipe) return;
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault();
                                navigate(`/recipes/${meal.recipe_id}`);
                              }
                            }}
                            className={`group relative rounded-xl px-4 py-3.5 transition-colors min-w-0 ${
                              canOpenRecipe ? 'cursor-pointer' : ''
                            } ${
                              kind === 'leftover'
                                ? 'bg-amber-50 hover:bg-amber-100/80'
                                : kind === 'note'
                                  ? 'bg-sky-50 hover:bg-sky-100/80'
                                  : 'bg-cream-subtle hover:bg-laro-light'
                            }`}
                            data-testid={`meal-slot-${meal.id}`}
                          >
                            <div className="flex items-center gap-3 sm:gap-4">
                              <div className="w-20 sm:w-24 shrink-0">
                                <p className="text-xs font-semibold text-laro">
                                  {MEAL_TYPE_KEYS[meal.meal_type] ? t(MEAL_TYPE_KEYS[meal.meal_type]) : meal.meal_type}
                                </p>
                                {kind === 'leftover' && (
                                  <p className="mt-0.5 inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide text-amber-800/80">
                                    <Refrigerator className="w-3 h-3" />
                                    {t('leftover')}
                                  </p>
                                )}
                                {kind === 'note' && (
                                  <p className="mt-0.5 inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide text-sky-800/80">
                                    <StickyNote className="w-3 h-3" />
                                    {t('note')}
                                  </p>
                                )}
                                {showFamilyBadge && (
                                  <p
                                    className="mt-0.5 inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide text-rose-800/90"
                                    data-testid={`family-badge-${meal.id}`}
                                  >
                                    <Users className="w-3 h-3" />
                                    {t('familyMealBadge')}
                                  </p>
                                )}
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className={`text-sm sm:text-base font-medium leading-snug break-words ${canOpenRecipe ? 'text-foreground underline-offset-2 group-hover:underline' : ''}`}>
                                  {meal.recipe_title}
                                </p>
                                {meal.notes && !adultBoost ? (
                                  <p className="text-sm text-muted-foreground mt-0.5 leading-relaxed">
                                    {meal.notes}
                                  </p>
                                ) : null}
                                {meal.notes && adultBoost && !/^for adults/i.test(meal.notes.trim()) ? (
                                  <p className="text-sm text-muted-foreground mt-0.5 leading-relaxed">
                                    {meal.notes}
                                  </p>
                                ) : null}
                                {adultBoost ? (
                                  <p
                                    className="text-xs sm:text-sm text-amber-900/80 mt-1 leading-relaxed"
                                    data-testid={`adult-boost-${meal.id}`}
                                  >
                                    <span className="font-medium">{t('adultBoostLabel')}:</span>{' '}
                                    {adultBoost}
                                  </p>
                                ) : null}
                              </div>
                              <div className="flex items-center gap-0.5 shrink-0">
                                {canOpenRecipe && (
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8 text-muted-foreground hover:text-laro opacity-70 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      openSwapDialog(meal);
                                    }}
                                    aria-label={`${t('swapRecipe')} ${meal.recipe_title}`}
                                    data-testid={`swap-meal-${meal.id}`}
                                  >
                                    <RefreshCw className="w-4 h-4" />
                                  </Button>
                                )}
                                <Button
                                  variant="ghost"
                                  size="icon"
                                  className="h-8 w-8 text-muted-foreground hover:text-destructive opacity-70 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleDeleteMeal(meal.id);
                                  }}
                                  aria-label={`${t('remove')} ${meal.recipe_title}`}
                                >
                                  <Trash2 className="w-4 h-4" />
                                </Button>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </motion.div>
        )}

        {/* Add Meal Dialog */}
        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('addToPlan')}</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              {selectedDate && (
                <p className="text-sm text-muted-foreground">
                  {t('forDate', { date: format(selectedDate, 'EEEE, MMMM d') })}
                </p>
              )}

              <div>
                <label className="text-sm font-medium mb-2 block">{t('whatAreYouAdding')}</label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { id: 'recipe', label: t('recipe'), icon: UtensilsCrossed },
                    { id: 'leftover', label: t('leftover'), icon: Refrigerator },
                    { id: 'note', label: t('note'), icon: StickyNote },
                  ].map(({ id, label, icon: Icon }) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setEntryType(id)}
                      className={`flex flex-col items-center gap-1 rounded-xl border px-2 py-3 text-xs font-medium transition-colors ${
                        entryType === id
                          ? 'border-laro bg-laro-light text-laro'
                          : 'border-border/60 hover:bg-cream-subtle'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              
              <div>
                <label className="text-sm font-medium mb-2 block">{t('mealType')}</label>
                <Select value={selectedMealType} onValueChange={setSelectedMealType}>
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

              {entryType === 'recipe' ? (
                <div>
                  <label className="text-sm font-medium mb-2 block">{t('selectRecipe')}</label>
                  {recipes.length === 0 ? (
                    <div className="text-center py-6 bg-cream-subtle rounded-xl">
                      <UtensilsCrossed className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                      <p className="text-sm text-muted-foreground">{t('noRecipes')}</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                        <Input
                          value={recipeSearch}
                          onChange={(e) => setRecipeSearch(e.target.value)}
                          placeholder={t('searchRecipesPlaceholder')}
                          className="rounded-xl pl-9"
                          data-testid="meal-plan-recipe-search"
                          autoComplete="off"
                        />
                      </div>
                      <div
                        className="max-h-48 overflow-y-auto rounded-xl border border-border/60 divide-y divide-border/40"
                        data-testid="meal-plan-recipe-list"
                      >
                        {filteredRecipesForPicker.length === 0 ? (
                          <p className="px-3 py-4 text-sm text-center text-muted-foreground">
                            {t('noMatchingRecipes')}
                          </p>
                        ) : (
                          filteredRecipesForPicker.map((recipe) => {
                            const selected = selectedRecipe === recipe.id;
                            return (
                              <button
                                key={recipe.id}
                                type="button"
                                onClick={() => setSelectedRecipe(recipe.id)}
                                className={`w-full text-left px-3 py-2.5 text-sm transition-colors ${
                                  selected
                                    ? 'bg-laro-light text-laro font-medium'
                                    : 'hover:bg-cream-subtle'
                                }`}
                                data-testid={`meal-plan-recipe-option-${recipe.id}`}
                              >
                                <span className="block truncate">{recipe.title}</span>
                                {(recipe.category || (recipe.tags && recipe.tags.length > 0)) && (
                                  <span className="block truncate text-xs text-muted-foreground mt-0.5">
                                    {[recipe.category, ...(recipe.tags || []).slice(0, 3)]
                                      .filter(Boolean)
                                      .join(' · ')}
                                  </span>
                                )}
                              </button>
                            );
                          })
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  <div>
                    <label className="text-sm font-medium mb-2 block">
                      {entryType === 'leftover' ? t('leftoverName') : t('noteTitle')}
                    </label>
                    <Input
                      value={entryTitle}
                      onChange={(e) => setEntryTitle(e.target.value)}
                      placeholder={
                        entryType === 'leftover'
                          ? t('leftoverPlaceholder')
                          : t('notePlaceholder')
                      }
                      className="rounded-xl"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-2 block">{t('detailsOptional')}</label>
                    <Input
                      value={entryNotes}
                      onChange={(e) => setEntryNotes(e.target.value)}
                      placeholder={t('extraContextPlaceholder')}
                      className="rounded-xl"
                    />
                  </div>
                </div>
              )}

              <Button 
                onClick={handleAddMeal} 
                className="w-full rounded-full bg-laro hover:bg-laro-dark"
                disabled={
                  adding ||
                  (entryType === 'recipe' ? !selectedRecipe : !entryTitle.trim())
                }
              >
                {adding ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                {t('addToPlan')}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Shop this plan — review before save */}
        <Dialog open={showShopReview} onOpenChange={setShowShopReview}>
          <DialogContent className="max-w-lg max-h-[85vh] flex flex-col">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <ShoppingCart className="w-5 h-5 text-laro" />
                {t('reviewGroceryList')}
              </DialogTitle>
              <DialogDescription>
                {t('reviewGroceryDesc')}
              </DialogDescription>
            </DialogHeader>
            <div className="flex-1 overflow-y-auto space-y-4 pr-1">
              {shopAisleGroups.map(([aisle, rows]) => (
                <div key={aisle}>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      {aisle}
                    </p>
                    <button
                      type="button"
                      className="text-xs text-laro hover:underline"
                      onClick={() => {
                        const allOn = rows.every(({ key }) => shopSelected[key]);
                        toggleShopAisle(rows, !allOn);
                      }}
                    >
                      {t('toggleAisle')}
                    </button>
                  </div>
                  <div className="space-y-2">
                    {rows.map(({ item, key }) => (
                      <label
                        key={key}
                        className={`flex items-start gap-3 rounded-xl border p-3 cursor-pointer transition-colors ${
                          shopSelected[key]
                            ? 'border-laro/40 bg-laro-light/40'
                            : 'border-border/50 bg-muted/20 opacity-70'
                        }`}
                      >
                        <Checkbox
                          checked={!!shopSelected[key]}
                          onCheckedChange={(v) =>
                            setShopSelected((prev) => ({ ...prev, [key]: !!v }))
                          }
                          className="mt-0.5"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium">
                            {item.quantity != null ? `${item.quantity} ` : ''}
                            {item.unit ? `${item.unit} ` : ''}
                            {item.name}
                          </p>
                          <div className="flex flex-wrap gap-2 mt-1">
                            {item.in_pantry && (
                              <span className="text-[10px] uppercase tracking-wide text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded">
                                {t('inPantry')}
                              </span>
                            )}
                            {(item.recipe_names || []).slice(0, 2).map((name) => (
                              <span
                                key={name}
                                className="text-[10px] text-muted-foreground truncate max-w-[140px]"
                              >
                                {name}
                              </span>
                            ))}
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="flex gap-2 pt-3 border-t">
              <Button
                variant="outline"
                className="rounded-full flex-1"
                onClick={() => setShowShopReview(false)}
                disabled={confirmingShop}
              >
                {t('cancel')}
              </Button>
              <Button
                className="rounded-full flex-1 bg-laro hover:bg-laro-dark"
                onClick={handleConfirmShop}
                disabled={confirmingShop || selectedShopCount === 0}
              >
                {confirmingShop ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <ShoppingCart className="w-4 h-4 mr-2" />
                )}
                {t('saveNItems', { count: selectedShopCount })}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Import meal packs (Huel) or printable weekly plan */}
        <Dialog
          open={showImportDialog}
          onOpenChange={(open) => {
            setShowImportDialog(open);
            if (!open) resetImportDialog();
          }}
        >
          <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <FileUp className="w-5 h-5 text-laro" />
                {importMode === 'macros' || importMode === 'manual'
                  ? t('confirmMacros')
                  : t('addMealPacksPlan')}
              </DialogTitle>
              <DialogDescription>
                {importMode === 'macros' || importMode === 'manual'
                  ? macrosFromOnline
                    ? 'Macros pulled from the product page — edit anything that looks wrong, then import.'
                    : 'Enter calories (and protein/carbs/fat if you have them) for each pack.'
                  : 'Fetch Huel (or similar) from a URL, enter macros, or upload a PDF (weekly meal plan or recipes).'}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              {(importMode === 'url' || importMode === 'pdf') && (
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant={importMode === 'url' ? 'default' : 'outline'}
                    className="rounded-full"
                    onClick={() => setImportMode('url')}
                  >
                    {t('fromUrl')}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="rounded-full"
                    onClick={() => {
                      setImportMode('manual');
                      setPackDrafts([
                        { title: '', calories: '', protein: '', carbs: '', fat: '', kind: 'shake' },
                      ]);
                    }}
                  >
                    {t('enterMacros')}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={importMode === 'pdf' ? 'default' : 'outline'}
                    className="rounded-full"
                    onClick={() => setImportMode('pdf')}
                  >
                    {t('pdfOrPaste')}
                  </Button>
                </div>
              )}

              {importMode === 'pdf' && (
                <p className="text-xs text-muted-foreground -mt-1">
                  Accepts weekly meal-plan PDFs (schedules this week) or recipe cookbooks (adds recipes to your library).
                </p>
              )}

              {importMode === 'url' && (
                <div>
                  <label className="text-sm font-medium mb-2 block">{t('productCollectionUrl')}</label>
                  <div className="relative">
                    <Link2 className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      type="url"
                      value={importUrl}
                      onChange={(e) => setImportUrl(e.target.value)}
                      placeholder="https://huel.com/products/…"
                      className="rounded-xl pl-9"
                      data-testid="import-meal-plan-url"
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    We pull macros from the page when available; otherwise you can fill them in.
                  </p>
                </div>
              )}

              {(importMode === 'macros' || importMode === 'manual') && (
                <div className="space-y-3">
                  {packDrafts.map((pack, idx) => (
                    <div
                      key={idx}
                      className="rounded-xl border border-border/60 p-3 space-y-2 bg-white"
                    >
                      <Input
                        value={pack.title}
                        onChange={(e) => {
                          const next = [...packDrafts];
                          next[idx] = { ...next[idx], title: e.target.value };
                          setPackDrafts(next);
                        }}
                        placeholder={t('packNamePlaceholder')}
                        className="rounded-xl"
                      />
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        {[
                          ['calories', t('kcalLabel')],
                          ['protein', t('proteinG')],
                          ['carbs', t('carbsG')],
                          ['fat', t('fatG')],
                        ].map(([key, label]) => (
                          <div key={key}>
                            <label className="text-[11px] text-muted-foreground">{label}</label>
                            <Input
                              type="number"
                              min="0"
                              value={pack[key]}
                              onChange={(e) => {
                                const next = [...packDrafts];
                                next[idx] = { ...next[idx], [key]: e.target.value };
                                setPackDrafts(next);
                              }}
                              className={`rounded-xl ${
                                key === 'calories' && (pack.calories === '' || pack.calories == null)
                                  ? 'border-amber-400'
                                  : ''
                              }`}
                              data-testid={`pack-macro-${key}-${idx}`}
                            />
                          </div>
                        ))}
                      </div>
                      {pack.needs_macros && (
                        <p className="text-xs text-amber-700">{t('macrosMissingOnline')}</p>
                      )}
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="rounded-full"
                    onClick={() =>
                      setPackDrafts([
                        ...packDrafts,
                        { title: '', calories: '', protein: '', carbs: '', fat: '', kind: 'shake' },
                      ])
                    }
                  >
                    {t('addAnotherPack')}
                  </Button>
                </div>
              )}

              {importMode === 'pdf' && (
                <>
                  <div>
                    <label className="text-sm font-medium mb-2 block">{t('pdfFile')}</label>
                    <Input
                      type="file"
                      accept="application/pdf,.pdf"
                      className="rounded-xl"
                      onChange={(e) => {
                        const f = e.target.files?.[0] || null;
                        setImportFile(f);
                        if (f) setImportText('');
                      }}
                    />
                    {importFile && (
                      <p className="text-xs text-muted-foreground mt-1">{importFile.name}</p>
                    )}
                  </div>
                  <div>
                    <label className="text-sm font-medium mb-2 block">{t('orPastePlanText')}</label>
                    <textarea
                      value={importText}
                      onChange={(e) => {
                        setImportText(e.target.value);
                        if (e.target.value) setImportFile(null);
                      }}
                      placeholder={t('pastePlanPlaceholder')}
                      className="w-full min-h-[140px] rounded-xl border border-border/60 bg-white px-3 py-2 text-sm"
                      disabled={!!importFile}
                    />
                  </div>
                </>
              )}

              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={importCreateShopping}
                  onCheckedChange={(v) => setImportCreateShopping(!!v)}
                />
                {t('alsoCreateShoppingList')}
              </label>

              {(importMode === 'pdf' || importMode === 'url') && (
                <label className="flex items-start gap-2 text-sm">
                  <Checkbox
                    className="mt-0.5"
                    checked={importIncludeSourceNote}
                    onCheckedChange={(v) => setImportIncludeSourceNote(!!v)}
                    data-testid="include-source-note"
                  />
                  <span>
                    {t('includePlanSourceNote')}
                    <span className="block text-xs text-muted-foreground mt-0.5">
                      {t('includePlanSourceNoteHint')}
                    </span>
                  </span>
                </label>
              )}

              <div className="p-3 bg-amber-50 rounded-xl text-sm text-amber-800">
                Scheduling replaces meals already on this week (
                {format(weekStart, 'MMM d')} – {format(weekEnd, 'MMM d')}).
              </div>

              <Button
                onClick={handleImportMealPlan}
                className="w-full rounded-full bg-laro hover:bg-laro-dark"
                disabled={
                  importing ||
                  (importMode === 'url' && !importUrl.trim()) ||
                  (importMode === 'pdf' && !importFile && !importText.trim()) ||
                  ((importMode === 'macros' || importMode === 'manual') &&
                    !packDrafts.some((p) => (p.title || '').trim()))
                }
                data-testid="confirm-import-meal-plan"
              >
                {importing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    {importMode === 'url' ? t('fetching') : t('importing')}
                  </>
                ) : importMode === 'url' ? (
                  <>
                    <Link2 className="w-4 h-4 mr-2" />
                    {t('fetchFromWebsite')}
                  </>
                ) : (
                  <>
                    <FileUp className="w-4 h-4 mr-2" />
                    {t('importIntoThisWeek')}
                  </>
                )}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Auto Generate Dialog */}
        <Dialog
          open={showAutoDialog}
          onOpenChange={(open) => {
            if (open) {
              openAutoDialog();
            } else {
              setShowAutoDialog(false);
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-laro" />
                {t('autoGenerateMealPlan')}
              </DialogTitle>
              <DialogDescription>{t('autoGenerateDesc')}</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              {(() => {
                const planDays = [7, 14, 28].includes(autoPlanDays) ? autoPlanDays : 7;
                const dialogWeekStart = startOfWeek(autoPlanWeekStart || weekStart, {
                  weekStartsOn,
                });
                const dialogPlanEnd = addDays(dialogWeekStart, planDays - 1);
                return (
                  <>
                    <div>
                      <label className="text-sm font-medium mb-2 block">
                        {t('choosePlanLength')}
                      </label>
                      <div
                        className="grid grid-cols-3 gap-2"
                        role="group"
                        aria-label={t('choosePlanLength')}
                        data-testid="auto-plan-days-group"
                      >
                        {[7, 14, 28].map((days) => (
                          <Button
                            key={days}
                            type="button"
                            variant={autoPlanDays === days ? 'default' : 'outline'}
                            className={`rounded-xl ${
                              autoPlanDays === days
                                ? 'bg-laro hover:bg-laro-dark text-white'
                                : ''
                            }`}
                            disabled={autoGenerating}
                            onClick={() => setAutoPlanDays(days)}
                            data-testid={`auto-plan-days-${days}`}
                          >
                            {t('nDays', { count: days })}
                          </Button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <label className="text-sm font-medium mb-2 block">
                        {t('chooseWeekForPlan')}
                      </label>
                      <div className="flex items-center gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          size="icon"
                          className="rounded-full shrink-0"
                          disabled={autoGenerating}
                          onClick={() =>
                            setAutoPlanWeekStart(subWeeks(dialogWeekStart, 1))
                          }
                          data-testid="auto-plan-prev-week"
                          aria-label={t('previousWeek')}
                        >
                          <ChevronLeft className="w-4 h-4" />
                        </Button>
                        <div
                          className="flex-1 px-3 py-2 bg-muted/50 rounded-xl border border-border/60 text-center"
                          data-testid="auto-plan-week-range"
                        >
                          <p className="font-medium text-sm">
                            {format(dialogWeekStart, 'MMM d')} –{' '}
                            {format(dialogPlanEnd, 'MMM d, yyyy')}
                          </p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {t('nDayPlanHint', { count: planDays })}
                          </p>
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          size="icon"
                          className="rounded-full shrink-0"
                          disabled={autoGenerating}
                          onClick={() =>
                            setAutoPlanWeekStart(addWeeks(dialogWeekStart, 1))
                          }
                          data-testid="auto-plan-next-week"
                          aria-label={t('nextWeek')}
                        >
                          <ChevronRight className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </>
                );
              })()}

              <div>
                <label className="text-sm font-medium mb-2 block">{t('preferencesOptional')}</label>
                <Input
                  value={autoPreferences}
                  onChange={(e) => setAutoPreferences(e.target.value)}
                  placeholder={t('autoPrefsPlaceholder')}
                  className="rounded-xl"
                  disabled={autoGenerating}
                />
              </div>

              <div className="p-3 bg-amber-50 rounded-xl text-sm text-amber-800">
                <p>{t('willReplaceNDayPlan', { count: [7, 14, 28].includes(autoPlanDays) ? autoPlanDays : 7 })}</p>
              </div>

              <Button
                onClick={handleAutoGenerate}
                className="w-full rounded-full bg-laro hover:bg-laro-dark"
                disabled={autoGenerating || recipes.length < 3}
                data-testid="auto-plan-generate-submit"
              >
                {autoGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    {t('generating')}
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    {t('generateNDayPlan', {
                      count: [7, 14, 28].includes(autoPlanDays) ? autoPlanDays : 7,
                    })}
                  </>
                )}
              </Button>

              {recipes.length < 3 && (
                <p className="text-xs text-muted-foreground text-center">
                  {t('needThreeRecipes')}
                </p>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* Swap Recipe Dialog */}
        <Dialog
          open={showSwapDialog}
          onOpenChange={(open) => {
            setShowSwapDialog(open);
            if (!open) {
              setSwapMeal(null);
              setSwapRecipeId('');
              setSwapRecipeSearch('');
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('swapRecipe')}</DialogTitle>
              <DialogDescription>
                {swapMeal
                  ? t('swapRecipeDesc', {
                      title: swapMeal.recipe_title,
                      meal: MEAL_TYPE_KEYS[swapMeal.meal_type]
                        ? t(MEAL_TYPE_KEYS[swapMeal.meal_type])
                        : swapMeal.meal_type,
                      date: swapMeal.date
                        ? format(parseISO(swapMeal.date), 'EEEE, MMM d')
                        : '',
                    })
                  : null}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              {recipes.length === 0 ? (
                <div className="text-center py-6 bg-cream-subtle rounded-xl">
                  <UtensilsCrossed className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">{t('noRecipes')}</p>
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
                    <Input
                      value={swapRecipeSearch}
                      onChange={(e) => setSwapRecipeSearch(e.target.value)}
                      placeholder={t('searchRecipesPlaceholder')}
                      className="rounded-xl pl-9"
                      data-testid="meal-plan-recipe-search"
                      autoComplete="off"
                    />
                  </div>
                  <div
                    className="max-h-48 overflow-y-auto rounded-xl border border-border/60 divide-y divide-border/40"
                    data-testid="meal-plan-swap-recipe-list"
                  >
                    {filteredRecipesForSwap.length === 0 ? (
                      <p className="px-3 py-4 text-sm text-center text-muted-foreground">
                        {t('noMatchingRecipes')}
                      </p>
                    ) : (
                      filteredRecipesForSwap.map((recipe) => {
                        const selected = swapRecipeId === recipe.id;
                        const isCurrent = swapMeal?.recipe_id === recipe.id;
                        return (
                          <button
                            key={recipe.id}
                            type="button"
                            onClick={() => setSwapRecipeId(recipe.id)}
                            className={`w-full text-left px-3 py-2.5 text-sm transition-colors ${
                              selected
                                ? 'bg-laro-light text-laro font-medium'
                                : 'hover:bg-cream-subtle'
                            }`}
                            data-testid={`meal-plan-swap-option-${recipe.id}`}
                          >
                            <span className="block truncate">
                              {recipe.title}
                              {isCurrent ? ` · ${t('currentRecipe')}` : ''}
                            </span>
                            {(recipe.category || (recipe.tags && recipe.tags.length > 0)) && (
                              <span className="block truncate text-xs text-muted-foreground mt-0.5">
                                {[recipe.category, ...(recipe.tags || []).slice(0, 3)]
                                  .filter(Boolean)
                                  .join(' · ')}
                              </span>
                            )}
                          </button>
                        );
                      })
                    )}
                  </div>
                </div>
              )}

              <Button
                onClick={handleSwapRecipe}
                className="w-full rounded-full bg-laro hover:bg-laro-dark"
                disabled={swapping || !swapRecipeId || swapRecipeId === swapMeal?.recipe_id}
                data-testid="meal-plan-swap-submit"
              >
                {swapping ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                {t('swapRecipe')}
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        <AlertDialog open={showRepeatConfirm} onOpenChange={setShowRepeatConfirm}>
          <AlertDialogContent data-testid="repeat-week-confirm">
            <AlertDialogHeader>
              <AlertDialogTitle>{t('repeatWeek')}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('repeatWeekConfirm', {
                  from: `${format(weekStart, 'MMM d')} – ${format(weekEnd, 'MMM d')}`,
                  to: `${format(addWeeks(weekStart, 1), 'MMM d')} – ${format(addWeeks(weekEnd, 1), 'MMM d')}`,
                })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={repeatingWeek}>{t('cancel')}</AlertDialogCancel>
              <AlertDialogAction
                onClick={(e) => {
                  e.preventDefault();
                  handleRepeatWeek();
                }}
                disabled={repeatingWeek}
                data-testid="repeat-week-confirm-btn"
                className="bg-laro hover:bg-laro-dark"
              >
                {repeatingWeek ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                {t('repeatWeek')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        <Dialog
          open={!!proteinBoostDay}
          onOpenChange={(open) => {
            if (!open) setProteinBoostDay(null);
          }}
        >
          <DialogContent data-testid="protein-boost-dialog">
            <DialogHeader>
              <DialogTitle>{t('swapToHitProtein')}</DialogTitle>
              <DialogDescription>
                {proteinBoostDay
                  ? t('swapToHitProteinDesc', {
                      date: format(proteinBoostDay, 'EEEE, MMM d'),
                      deficit: proteinBoostSuggestions?.deficit ?? 0,
                      target: proteinTarget != null ? Math.round(proteinTarget) : '—',
                    })
                  : null}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-2 max-h-80 overflow-y-auto pt-2">
              {(proteinBoostSuggestions?.suggestions || []).length === 0 ? (
                <p className="text-sm text-muted-foreground">{t('noProteinSwaps')}</p>
              ) : (
                proteinBoostSuggestions.suggestions.map((s) => (
                  <button
                    key={`${s.mealId}-${s.recipeId}`}
                    type="button"
                    data-testid={`protein-swap-option-${s.recipeId}`}
                    disabled={swapping}
                    onClick={() => applyProteinSwap(s)}
                    className="w-full text-left rounded-xl border border-border/60 px-3 py-3 hover:border-laro/50 hover:bg-laro-light/30 transition-colors"
                  >
                    <p className="font-medium text-sm">{s.title}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {t('proteinSwapDetail', {
                        meal: MEAL_TYPE_KEYS[s.mealType] ? t(MEAL_TYPE_KEYS[s.mealType]) : s.mealType,
                        from: s.currentTitle,
                        protein: s.protein,
                        gain: s.gain,
                      })}
                    </p>
                  </button>
                ))
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};
