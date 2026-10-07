import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { format, parseISO, isSameDay, isToday } from 'date-fns';
import { mealPlanApi, pantryApi } from '../lib/api';
import { useLanguage } from '../context/LanguageContext';
import { useUserPreferences } from '../hooks/useUserPreferences';
import {
  resolveCalorieTarget,
  resolveProteinTarget,
  rollupDayNutrition,
} from '../lib/mealPlanNutrition';
import { TodayMacrosStrip } from './TodayMacrosStrip';
import { TonightSuggestions } from './TonightSuggestions';
import { Button } from './ui/button';
import {
  CalendarDays,
  ChefHat,
  Loader2,
  Refrigerator,
  ShoppingCart,
  Plus,
  UtensilsCrossed,
  ArrowRight,
} from 'lucide-react';

function parsePlanDate(raw) {
  if (!raw) return null;
  const s = String(raw).slice(0, 10);
  try {
    return parseISO(s);
  } catch {
    return null;
  }
}

/**
 * Single home summary: today, macros, coming up, pantry, primary actions.
 */
export function HomeSummary({
  weekMeals = [],
  allRecipes = [],
  onPlanAndShop,
  planShopBusy = false,
}) {
  const { t } = useLanguage();
  const { preferences } = useUserPreferences();
  const proteinTarget = resolveProteinTarget(preferences);
  const calorieTarget = resolveCalorieTarget(preferences);
  const todayStr = format(new Date(), 'yyyy-MM-dd');

  const [loading, setLoading] = useState(true);
  const [todayMeals, setTodayMeals] = useState([]);
  const [expiring, setExpiring] = useState([]);

  const loadToday = useCallback(async () => {
    setLoading(true);
    try {
      const [plansRes, expRes] = await Promise.all([
        mealPlanApi.getAll({ start_date: todayStr, end_date: todayStr }),
        pantryApi.getExpiring(5).catch(() => ({ data: { items: [] } })),
      ]);
      setTodayMeals(
        (plansRes.data || []).filter(
          (p) => String(p?.date || '').slice(0, 10) === todayStr
        )
      );
      setExpiring((expRes.data?.items || []).slice(0, 4));
    } catch {
      setTodayMeals([]);
      setExpiring([]);
    } finally {
      setLoading(false);
    }
  }, [todayStr]);

  useEffect(() => {
    loadToday();
  }, [loadToday]);

  const dayTotals = useMemo(
    () => rollupDayNutrition(todayMeals, allRecipes),
    [todayMeals, allRecipes]
  );

  const weekRecipeMeals = useMemo(
    () =>
      (weekMeals || []).filter(
        (p) => (p.entry_type || 'recipe') === 'recipe' && p.recipe_id
      ),
    [weekMeals]
  );

  const comingUp = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return weekRecipeMeals
      .map((p) => ({ ...p, _date: parsePlanDate(p.date) }))
      .filter((p) => p._date && p._date >= today)
      .sort((a, b) => a._date - b._date)
      .slice(0, 5);
  }, [weekRecipeMeals]);

  const hasDinnerTonight = todayMeals.some(
    (m) =>
      (m.entry_type || 'recipe') === 'recipe' &&
      String(m.meal_type || '').toLowerCase() === 'dinner'
  );

  const recipeLibraryCount = allRecipes.length;

  if (loading) {
    return (
      <div
        className="flex items-center justify-center py-16 rounded-2xl bg-white shadow-card border border-border/40"
        data-testid="home-summary"
      >
        <Loader2 className="w-7 h-7 animate-spin text-laro" />
      </div>
    );
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl bg-white shadow-card border border-border/40 overflow-hidden"
      data-testid="home-summary"
    >
      <div className="px-4 sm:px-6 py-4 border-b border-border/50 bg-gradient-to-r from-laro-light/30 to-transparent">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div>
            <h2 className="font-heading text-xl sm:text-2xl font-semibold text-laro-brand">
              {t('homeSummaryTitle')}
            </h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              {format(new Date(), 'EEEE, d MMMM')}
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-full bg-cream-subtle px-3 py-1 font-medium tabular-nums">
              {t('homeStatsMealsWeek', { count: weekRecipeMeals.length })}
            </span>
            <span className="rounded-full bg-cream-subtle px-3 py-1 font-medium tabular-nums">
              {t('homeStatsMealsToday', { count: todayMeals.length })}
            </span>
            {recipeLibraryCount > 0 && (
              <span className="rounded-full bg-cream-subtle px-3 py-1 font-medium tabular-nums">
                {t('homeStatsRecipes', { count: recipeLibraryCount })}
              </span>
            )}
          </div>
        </div>

        <div
          className="flex gap-2 mt-4 overflow-x-auto pb-1 -mx-1 px-1 sm:flex-wrap sm:overflow-visible scrollbar-thin"
          role="navigation"
          aria-label={t('homeSummaryTitle')}
        >
          <Button
            size="sm"
            className="rounded-full shrink-0 bg-laro hover:bg-laro-dark"
            disabled={planShopBusy}
            onClick={onPlanAndShop}
            data-testid="plan-and-shop-btn"
          >
            {planShopBusy ? (
              <Loader2 className="w-4 h-4 animate-spin mr-1.5" />
            ) : (
              <ShoppingCart className="w-4 h-4 mr-1.5" />
            )}
            {t('planAndShopWeek')}
          </Button>
          <Button size="sm" variant="outline" className="rounded-full shrink-0" asChild>
            <Link to="/meal-planner">
              <CalendarDays className="w-4 h-4 mr-1.5" />
              {t('mealPlan')}
            </Link>
          </Button>
          <Button size="sm" variant="outline" className="rounded-full shrink-0" asChild>
            <Link to="/shopping">
              <ShoppingCart className="w-4 h-4 mr-1.5" />
              {t('shopping')}
            </Link>
          </Button>
          <Button size="sm" variant="outline" className="rounded-full shrink-0" asChild>
            <Link to="/fridge">
              <Refrigerator className="w-4 h-4 mr-1.5" />
              {t('myFridge')}
            </Link>
          </Button>
          <Button size="sm" variant="outline" className="rounded-full shrink-0" asChild>
            <Link to="/recipes/new">
              <Plus className="w-4 h-4 mr-1.5" />
              {t('addRecipe')}
            </Link>
          </Button>
        </div>
      </div>

      <div className="px-4 sm:px-6 py-4 border-b border-border/40">
        <TodayMacrosStrip
          totals={dayTotals}
          proteinTarget={proteinTarget}
          calorieTarget={calorieTarget}
        />
      </div>

      <div className="p-4 sm:p-6 grid gap-6 lg:grid-cols-2">
        <div className="space-y-4 min-w-0">
          <div data-testid="today-meals-block">
            <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
              <UtensilsCrossed className="w-4 h-4 text-laro" />
              {t('todaysMeals')}
            </h3>
            {todayMeals.length === 0 ? (
              <p className="text-sm text-muted-foreground rounded-xl bg-cream-subtle/80 px-3 py-3">
                {t('noMealsToday')}
              </p>
            ) : (
              <ul className="space-y-2">
                {todayMeals.map((meal) => {
                  const isRecipe =
                    (meal.entry_type || 'recipe') === 'recipe' && meal.recipe_id;
                  return (
                    <li key={meal.id}>
                      {isRecipe ? (
                        <Link
                          to={`/recipes/${meal.recipe_id}`}
                          className="flex items-center gap-3 rounded-xl border border-border/50 bg-cream-subtle/50 hover:border-laro/40 hover:bg-laro-light/30 px-3 py-2.5 transition-colors"
                        >
                          <ChefHat className="w-4 h-4 text-laro shrink-0" />
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium truncate">
                              {meal.recipe_title}
                            </p>
                            <p className="text-xs text-muted-foreground capitalize">
                              {meal.meal_type}
                              {meal.servings
                                ? ` · ${meal.servings} ${t('servings')}`
                                : ''}
                            </p>
                          </div>
                          <ArrowRight className="w-4 h-4 text-muted-foreground shrink-0" />
                        </Link>
                      ) : (
                        <div className="rounded-xl border border-border/50 px-3 py-2.5 text-sm">
                          {meal.recipe_title || meal.notes}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          {!hasDinnerTonight && (
            <div className="pt-2 border-t border-border/40" data-testid="home-tonight-embedded">
              <h3 className="text-sm font-semibold text-foreground mb-2">
                {t('homeTonight')}
              </h3>
              <TonightSuggestions embedded maxItems={2} />
            </div>
          )}
        </div>

        <div className="space-y-4 min-w-0">
          {expiring.length > 0 && (
            <div data-testid="today-use-soon-block">
              <h3 className="text-sm font-semibold text-foreground mb-2 flex items-center gap-2">
                <Refrigerator className="w-4 h-4 text-amber-600" />
                {t('useSoonPantry')}
              </h3>
              <ul className="space-y-1.5 mb-2">
                {expiring.map((item) => {
                  let daysLeft = null;
                  if (item.expiry_date) {
                    try {
                      const exp = parseISO(String(item.expiry_date).slice(0, 10));
                      if (isSameDay(exp, new Date())) daysLeft = 0;
                      else {
                        daysLeft = Math.ceil(
                          (exp - new Date()) / (1000 * 60 * 60 * 24)
                        );
                      }
                    } catch {
                      daysLeft = null;
                    }
                  }
                  return (
                    <li
                      key={item.id}
                      className="text-sm flex justify-between gap-2 rounded-lg px-2.5 py-1.5 bg-amber-50/90 border border-amber-100"
                    >
                      <span className="truncate font-medium">{item.name}</span>
                      <span className="text-xs text-amber-900 shrink-0">
                        {daysLeft === 0
                          ? t('today')
                          : daysLeft != null && daysLeft > 0
                            ? t('expiresInDays', { days: daysLeft })
                            : t('expiringSoon')}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          <div>
            <div className="flex items-center justify-between gap-2 mb-2">
              <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
                <CalendarDays className="w-4 h-4 text-laro" />
                {t('homeComingUp')}
              </h3>
              <Link
                to="/meal-planner"
                className="text-xs font-medium text-laro hover:underline flex items-center gap-0.5"
              >
                {t('viewPlanner')}
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>
            {comingUp.length === 0 ? (
              <p className="text-sm text-muted-foreground rounded-xl bg-cream-subtle/80 px-3 py-3">
                {t('noMealsThisWeek')}{' '}
                <Link to="/meal-planner" className="text-laro font-medium hover:underline">
                  {t('planYourMeals')}
                </Link>
              </p>
            ) : (
              <ul className="space-y-1.5">
                {comingUp.map((plan) => {
                  const d = plan._date;
                  const dayLabel = d && isToday(d) ? t('today') : d ? format(d, 'EEE d MMM') : '';
                  const isRecipe =
                    (plan.entry_type || 'recipe') === 'recipe' && plan.recipe_id;
                  const inner = (
                    <>
                      <span className="text-xs text-muted-foreground w-20 shrink-0 tabular-nums">
                        {dayLabel}
                      </span>
                      <span className="text-xs capitalize text-laro w-16 shrink-0 truncate">
                        {plan.meal_type}
                      </span>
                      <span className="text-sm font-medium truncate flex-1">
                        {plan.recipe_title}
                      </span>
                    </>
                  );
                  return (
                    <li key={plan.id}>
                      {isRecipe ? (
                        <Link
                          to={`/recipes/${plan.recipe_id}`}
                          className="flex items-center gap-2 rounded-lg px-2 py-2 hover:bg-cream-subtle transition-colors"
                        >
                          {inner}
                        </Link>
                      ) : (
                        <div className="flex items-center gap-2 px-2 py-2 text-sm">
                          {inner}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </div>
    </motion.section>
  );
}
