import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { RecipeCard } from '../components/RecipeCard';
import { TonightSuggestions } from '../components/TonightSuggestions';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { recipeApi, mealPlanApi } from '../lib/api';
import {
  useLiveRefreshContext,
  useLiveRefreshEvent,
  EventType,
} from '../hooks/useLiveRefresh';
import { Button } from '../components/ui/button';
import {
  Plus,
  UtensilsCrossed,
  CalendarDays,
  ShoppingCart,
  Refrigerator,
  ArrowRight,
  ChefHat,
  Download
} from 'lucide-react';
import { toast } from 'sonner';
import { format, endOfWeek } from 'date-fns';

export const Dashboard = () => {
  const { user, household } = useAuth();
  const { t } = useLanguage();
  const liveRefresh = useLiveRefreshContext();
  const [recipes, setRecipes] = useState([]);
  const [mealPlans, setMealPlans] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [recipesRes, plansRes] = await Promise.all([
        recipeApi.getAll(),
        mealPlanApi.getAll({
          start_date: format(new Date(), 'yyyy-MM-dd'),
          end_date: format(endOfWeek(new Date()), 'yyyy-MM-dd'),
        }),
      ]);
      setRecipes(recipesRes.data.slice(0, 6));
      // Remaining week only — hide meals whose day has already passed
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
    [EventType.RECIPE_CREATED, EventType.RECIPE_UPDATED],
    useCallback(() => {
      loadData();
    }, [loadData]),
    liveRefresh
  );

  const quickActions = [
    { icon: Plus, label: t('addRecipe'), path: '/recipes/new', color: 'bg-laro-dark', shadowColor: 'shadow-soft' },
    { icon: CalendarDays, label: t('mealPlan'), path: '/meal-planner', color: 'bg-laro', shadowColor: 'shadow-soft' },
    { icon: ShoppingCart, label: t('shopping'), path: '/shopping', color: 'bg-laro-house', shadowColor: 'shadow-soft' },
    { icon: Refrigerator, label: t('myFridge'), path: '/fridge', color: 'bg-laro-uplift', shadowColor: 'shadow-soft' },
  ];

  return (
    <Layout>
      <div className="space-y-10" data-testid="dashboard">
        {/* Welcome Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="font-heading text-3xl sm:text-4xl font-semibold text-laro-brand tracking-tighter">
                {t('welcomeBackName', { name: user?.name?.split(' ')[0] })}
              </h1>
              <p className="text-muted-foreground mt-2 tracking-tight">
                {household ? `${household.name}` : t('yourPersonalKitchen')}
              </p>
            </div>
            <Link to="/recipes/new">
              <Button className="rounded-full" data-testid="dashboard-add-recipe">
                <Plus className="w-4 h-4 mr-2" />
                {t('addRecipe')}
              </Button>
            </Link>
          </div>
        </motion.div>

        {/* Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4"
        >
          {quickActions.map((action, index) => {
            const Icon = action.icon;
            return (
              <Link key={action.label} to={action.path}>
                <div className="group p-4 sm:p-6 rounded-[12px] bg-white shadow-card hover:shadow-hover transition-all duration-200 active:scale-[0.98]">
                  <div className={`w-12 h-12 rounded-full ${action.color} flex items-center justify-center mb-4`}>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  <p className="font-semibold text-foreground tracking-tight">{action.label}</p>
                </div>
              </Link>
            );
          })}
        </motion.div>

        {/* Tonight's Suggestions - The Core MVP Experience */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
        >
          <TonightSuggestions />
        </motion.section>

        {/* This Week's Meals */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-heading text-xl font-semibold">{t('thisWeeksMeals')}</h2>
            <Link to="/meal-planner" className="text-laro hover:text-laro-dark text-sm font-medium flex items-center gap-1">
              {t('viewAll')}
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {mealPlans.length === 0 ? (
            <div className="bg-white rounded-[12px] shadow-card p-8 text-center">
              <CalendarDays className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground mb-4">{t('noMealsThisWeek')}</p>
              <Link to="/meal-planner">
                <Button variant="outline" className="rounded-full">
                  {t('planYourMeals')}
                </Button>
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {mealPlans.slice(0, 4).map((plan) => (
                <div key={plan.id} className="bg-white rounded-[12px] p-4 shadow-card">
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">
                    {plan.meal_type ? t(plan.meal_type.toLowerCase()) : plan.meal_type}
                  </p>
                  <p className="font-semibold mt-1 line-clamp-1 tracking-tight">{plan.recipe_title}</p>
                  <p className="text-sm text-laro mt-2">{format(new Date(plan.date), 'EEE, MMM d')}</p>
                </div>
              ))}
            </div>
          )}
        </motion.section>

        {/* Recent Recipes */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-heading text-xl font-semibold">{t('recentRecipes')}</h2>
            <Link to="/recipes" className="text-laro hover:text-laro-dark text-sm font-medium flex items-center gap-1">
              {t('viewAll')}
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="bg-white rounded-2xl h-72 animate-pulse" />
              ))}
            </div>
          ) : recipes.length === 0 ? (
            <div className="bg-white rounded-2xl border border-border/60 p-12 text-center">
              <ChefHat className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
              <h3 className="font-heading text-lg font-semibold mb-2">{t('noRecipes')}</h3>
              <p className="text-muted-foreground mb-6">{t('startRecipeCollection')}</p>
              <div className="flex justify-center gap-3 flex-wrap">
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
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {recipes.map((recipe) => (
                <RecipeCard key={recipe.id} recipe={recipe} />
              ))}
            </div>
          )}
        </motion.section>
      </div>
    </Layout>
  );
};
