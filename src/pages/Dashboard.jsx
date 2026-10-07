import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { RecipeCard } from '../components/RecipeCard';
import { HomeSummary } from '../components/HomeSummary';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { recipeApi, mealPlanApi, aiApi } from '../lib/api';
import {
  useLiveRefreshContext,
  useLiveRefreshEvent,
  EventType,
} from '../hooks/useLiveRefresh';
import { Button } from '../components/ui/button';
import {
  Plus,
  ChefHat,
  Download,
  Loader2,
  ArrowRight,
} from 'lucide-react';
import { toast } from 'sonner';
import { format, endOfWeek, startOfWeek } from 'date-fns';
import { useUserPreferences, weekStartsOnNumber } from '../hooks/useUserPreferences';
import { shoppingListApi } from '../lib/api';

export const Dashboard = () => {
  const { user, household } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { preferences } = useUserPreferences();
  const liveRefresh = useLiveRefreshContext();
  const [allRecipes, setAllRecipes] = useState([]);
  const [mealPlans, setMealPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [liveImports, setLiveImports] = useState([]);
  const [planShopBusy, setPlanShopBusy] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [recipesRes, plansRes] = await Promise.all([
        recipeApi.getAll(),
        mealPlanApi.getAll({
          start_date: format(new Date(), 'yyyy-MM-dd'),
          end_date: format(endOfWeek(new Date()), 'yyyy-MM-dd'),
        }),
      ]);
      setAllRecipes(Array.isArray(recipesRes.data) ? recipesRes.data : []);
      const todayStr = format(new Date(), 'yyyy-MM-dd');
      setMealPlans((plansRes.data || []).filter((p) => (p.date || '') >= todayStr));
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error(error.response?.data?.detail || `${t('toastLoadDashboardFailed')} (E-DS001)`);
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useLiveRefreshEvent(
    EventType.MEAL_PLAN_CREATED,
    useCallback(() => loadData(), [loadData]),
    liveRefresh
  );
  useLiveRefreshEvent(
    EventType.MEAL_PLAN_UPDATED,
    useCallback(() => loadData(), [loadData]),
    liveRefresh
  );
  useLiveRefreshEvent(
    EventType.MEAL_PLAN_DELETED,
    useCallback(() => loadData(), [loadData]),
    liveRefresh
  );

  const loadLiveImports = useCallback(async () => {
    try {
      const res = await aiApi.listImports({ limit: 10, status: 'importing' });
      setLiveImports(res.data?.imports || []);
    } catch (_) {
      // non-blocking
    }
  }, []);

  useEffect(() => {
    loadLiveImports();
    const id = setInterval(loadLiveImports, 4000);
    return () => clearInterval(id);
  }, [loadLiveImports]);

  useLiveRefreshEvent(
    EventType.RECIPE_DELETED,
    useCallback((data) => {
      const id = data?.id;
      if (!id) {
        loadData();
        return;
      }
      setAllRecipes((prev) => prev.filter((r) => r.id !== id));
    }, [loadData]),
    liveRefresh
  );
  useLiveRefreshEvent(
    [EventType.RECIPE_CREATED, EventType.RECIPE_UPDATED],
    useCallback(() => {
      loadData();
    }, [loadData]),
    liveRefresh
  );

  const handlePlanAndShop = async () => {
    setPlanShopBusy(true);
    try {
      const weekStartsOn = weekStartsOnNumber(preferences.weekStartsOn, 1);
      const weekStart = startOfWeek(new Date(), { weekStartsOn });
      const weekEnd = endOfWeek(new Date(), { weekStartsOn });
      const start = format(weekStart, 'yyyy-MM-dd');
      const end = format(weekEnd, 'yyyy-MM-dd');
      const plansRes = await mealPlanApi.getAll({ start_date: start, end_date: end });
      const plans = plansRes.data || [];
      const hasRecipes = plans.some(
        (p) => (p.entry_type || 'recipe') === 'recipe' && p.recipe_id
      );
      if (!hasRecipes) {
        navigate('/meal-planner', { state: { planAndShop: true } });
        return;
      }
      const preview = await shoppingListApi.fromMealPlan({
        start_date: start,
        end_date: end,
        exclude_pantry: true,
        combine_quantities: true,
        assign_aisles: true,
        keep_pantry_items: true,
        save: false,
        list_name: `Week of ${format(weekStart, 'MMM d')}`,
        attach_retailer_hints: true,
      });
      const items = (preview.data?.items || []).filter((item) => !item.in_pantry);
      if (!items.length) {
        toast.error(t('toastNothingToShop'));
        navigate('/meal-planner');
        return;
      }
      await shoppingListApi.create({
        name: preview.data.list_name || `Week of ${format(weekStart, 'MMM d')}`,
        items: items.map((item) => ({ ...item, checked: false })),
      });
      toast.success(t('toastShoppingListReady', { count: items.length }));
      navigate('/shopping');
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastCreateListFailed'));
      navigate('/meal-planner', { state: { planAndShop: true } });
    } finally {
      setPlanShopBusy(false);
    }
  };

  const recentRecipes = allRecipes.slice(0, 3);

  return (
    <Layout>
      <div className="space-y-8 max-w-5xl mx-auto" data-testid="dashboard">
        <motion.header
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-1"
        >
          <p className="text-sm font-medium text-laro uppercase tracking-wide">
            {t('home')}
          </p>
          <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-laro-brand tracking-tight">
            {t('welcomeBackName', { name: user?.name?.split(' ')[0] })}
          </h1>
          <p className="text-muted-foreground text-sm sm:text-base">
            {household ? household.name : t('yourPersonalKitchen')}
            {' · '}
            {t('homeSummarySubtitle')}
          </p>
        </motion.header>

        {liveImports.length > 0 && (
          <Link
            to="/settings/imports"
            className="inline-flex items-center gap-2 rounded-full bg-white border border-border/60 shadow-card px-4 py-2 text-sm font-medium text-laro-brand hover:shadow-hover transition-all"
            data-testid="importing-pill"
          >
            <Loader2 className="w-4 h-4 animate-spin text-laro" />
            <span>
              {t('importing')}
              {liveImports[0]?.title || liveImports[0]?.url
                ? ` · ${liveImports[0].title || liveImports[0].url}`
                : ''}
            </span>
          </Link>
        )}

        <HomeSummary
          weekMeals={mealPlans}
          allRecipes={allRecipes}
          onPlanAndShop={handlePlanAndShop}
          planShopBusy={planShopBusy}
        />

        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          aria-labelledby="home-recent-recipes"
        >
          <div className="flex items-center justify-between mb-4">
            <h2 id="home-recent-recipes" className="font-heading text-lg font-semibold">
              {t('recentRecipes')}
            </h2>
            <Link
              to="/recipes"
              className="text-laro hover:text-laro-dark text-sm font-medium flex items-center gap-1"
            >
              {t('viewAll')}
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="bg-white rounded-2xl h-48 animate-pulse" />
              ))}
            </div>
          ) : recentRecipes.length === 0 ? (
            <div className="bg-white rounded-2xl border border-border/60 p-8 text-center">
              <ChefHat className="w-12 h-12 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground mb-4 max-w-md mx-auto">{t('startRecipeCollection')}</p>
              <div className="flex justify-center gap-2 flex-wrap">
                <Link to="/recipes/new">
                  <Button className="rounded-full bg-laro hover:bg-laro-dark">
                    <Plus className="w-4 h-4 mr-2" />
                    {t('createRecipe')}
                  </Button>
                </Link>
                <Link to="/recipes/import">
                  <Button variant="outline" className="rounded-full">
                    {t('importFromUrl')}
                  </Button>
                </Link>
                <Link to="/recipes/import-batch">
                  <Button variant="outline" className="rounded-full">
                    <Download className="w-4 h-4 mr-2" />
                    {t('importFromApp')}
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {recentRecipes.map((recipe) => (
                <RecipeCard key={recipe.id} recipe={recipe} />
              ))}
            </div>
          )}
        </motion.section>
      </div>
    </Layout>
  );
};
