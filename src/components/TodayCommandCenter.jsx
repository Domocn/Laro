import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { format, parseISO, isSameDay } from 'date-fns';
import { mealPlanApi, pantryApi } from '../lib/api';
import { useLanguage } from '../context/LanguageContext';
import { Button } from './ui/button';
import {
  CalendarDays,
  ChefHat,
  Loader2,
  Refrigerator,
  AlertTriangle,
  ArrowRight,
} from 'lucide-react';

/**
 * Feedle-style "Today" strip: meals due today + pantry use-soon nudges.
 */
export function TodayCommandCenter() {
  const { t } = useLanguage();
  const [loading, setLoading] = useState(true);
  const [todayMeals, setTodayMeals] = useState([]);
  const [expiring, setExpiring] = useState([]);

  const todayStr = format(new Date(), 'yyyy-MM-dd');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [plansRes, expRes] = await Promise.all([
        mealPlanApi.getAll({ start_date: todayStr, end_date: todayStr }),
        pantryApi.getExpiring(5).catch(() => ({ data: { items: [] } })),
      ]);
      const meals = (plansRes.data || []).filter(
        (p) => String(p?.date || '').slice(0, 10) === todayStr
      );
      setTodayMeals(meals);
      setExpiring((expRes.data?.items || []).slice(0, 5));
    } catch {
      setTodayMeals([]);
      setExpiring([]);
    } finally {
      setLoading(false);
    }
  }, [todayStr]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 rounded-[12px] bg-white shadow-card">
        <Loader2 className="w-6 h-6 animate-spin text-laro" />
      </div>
    );
  }

  if (!todayMeals.length && !expiring.length) {
    return null;
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-[12px] bg-white shadow-card border border-border/40 overflow-hidden"
      data-testid="today-command-center"
    >
      <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <CalendarDays className="w-5 h-5 text-laro" aria-hidden="true" />
          <h2 className="font-heading text-lg font-semibold">{t('todayCommandCenter')}</h2>
          <span className="text-xs text-muted-foreground">
            {format(new Date(), 'EEE, d MMM')}
          </span>
        </div>
        <Link to="/meal-planner">
          <Button variant="ghost" size="sm" className="rounded-full text-laro">
            {t('mealPlan')}
            <ArrowRight className="w-3.5 h-3.5 ml-1" />
          </Button>
        </Link>
      </div>

      <div className="p-4 grid gap-4 sm:grid-cols-2">
        <div data-testid="today-meals-block">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">
            {t('todaysMeals')}
          </p>
          {todayMeals.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('noMealsToday')}</p>
          ) : (
            <ul className="space-y-2">
              {todayMeals.map((meal) => {
                const isRecipe = (meal.entry_type || 'recipe') === 'recipe' && meal.recipe_id;
                return (
                  <li key={meal.id}>
                    {isRecipe ? (
                      <Link
                        to={`/recipes/${meal.recipe_id}`}
                        className="flex items-start gap-2 rounded-xl bg-cream-subtle hover:bg-laro-light/40 px-3 py-2 transition-colors"
                      >
                        <ChefHat className="w-4 h-4 text-laro mt-0.5 shrink-0" />
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">{meal.recipe_title}</p>
                          <p className="text-xs text-muted-foreground capitalize">
                            {meal.meal_type}
                            {meal.servings ? ` · ${meal.servings} ${t('servings')}` : ''}
                          </p>
                        </div>
                      </Link>
                    ) : (
                      <div className="flex items-start gap-2 rounded-xl bg-cream-subtle px-3 py-2">
                        <p className="text-sm font-medium">{meal.recipe_title || meal.notes}</p>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div data-testid="today-use-soon-block">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            {t('useSoonPantry')}
          </p>
          {expiring.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('nothingExpiringSoon')}</p>
          ) : (
            <>
              <ul className="space-y-1.5 mb-3">
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
                      className="text-sm flex justify-between gap-2 rounded-lg px-2 py-1 bg-amber-50/80"
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
              <Link to="/fridge">
                <Button variant="outline" size="sm" className="rounded-full w-full sm:w-auto">
                  <Refrigerator className="w-4 h-4 mr-2" />
                  {t('myFridge')}
                </Button>
              </Link>
            </>
          )}
        </div>
      </div>
    </motion.section>
  );
}
