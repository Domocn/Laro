import React, { useState, useEffect, useCallback, useLayoutEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { Button } from './ui/button';
import { isPublicRecipeViewPath } from '../lib/publicRecipeView';
import { guidedTourKey, notifyFindAgainOnce, requestAppTour } from '../lib/onboarding';
import { toast } from 'sonner';
import {
  Home,
  UtensilsCrossed,
  CalendarDays,
  ShoppingCart,
  Refrigerator,
  Settings,
  ArrowRight,
  ArrowLeft,
  X,
  Sparkles,
  Download,
} from 'lucide-react';

/**
 * Real product tour: navigates through live app screens with coach-mark copy.
 * Started after UserOnboarding (or when laro_guided_tour_<id> === 'pending').
 */
const TOUR_STEPS = [
  {
    id: 'home',
    path: '/dashboard',
    icon: Home,
    titleKey: 'tourHomeTitle',
    bodyKey: 'tourHomeBody',
    target: '[data-tour="nav-home"]',
  },
  {
    id: 'recipes',
    path: '/recipes',
    icon: UtensilsCrossed,
    titleKey: 'tourRecipesTitle',
    bodyKey: 'tourRecipesBody',
    target: '[data-tour="nav-recipes"]',
  },
  {
    id: 'import',
    path: '/recipes/import',
    icon: Download,
    titleKey: 'tourImportTitle',
    bodyKey: 'tourImportBody',
    target: null,
  },
  {
    id: 'meal',
    path: '/meal-planner',
    icon: CalendarDays,
    titleKey: 'tourMealTitle',
    bodyKey: 'tourMealBody',
    target: '[data-tour="nav-meal-plan"]',
  },
  {
    id: 'shop',
    path: '/shopping',
    icon: ShoppingCart,
    titleKey: 'tourShopTitle',
    bodyKey: 'tourShopBody',
    target: '[data-tour="nav-shopping"]',
  },
  {
    id: 'fridge',
    path: '/fridge',
    icon: Refrigerator,
    titleKey: 'tourFridgeTitle',
    bodyKey: 'tourFridgeBody',
    target: '[data-tour="nav-my-fridge"]',
  },
  {
    id: 'settings',
    path: '/settings',
    icon: Settings,
    titleKey: 'tourSettingsTitle',
    bodyKey: 'tourSettingsBody',
    target: '[data-tour="nav-settings"]',
  },
];

/** @deprecated Prefer requestAppTour from lib/onboarding — kept for existing imports. */
export function startGuidedTour(userId) {
  requestAppTour(userId);
}

function useSpotlightRect(selector, active) {
  const [rect, setRect] = useState(null);

  useLayoutEffect(() => {
    if (!active || !selector) {
      setRect(null);
      return undefined;
    }

    let cancelled = false;
    const measure = () => {
      const el = document.querySelector(selector);
      if (!el || cancelled) {
        setRect(null);
        return;
      }
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) {
        setRect(null);
        return;
      }
      setRect({
        top: r.top - 6,
        left: r.left - 6,
        width: r.width + 12,
        height: r.height + 12,
      });
    };

    measure();
    const t1 = setTimeout(measure, 120);
    const t2 = setTimeout(measure, 400);
    window.addEventListener('resize', measure);
    window.addEventListener('scroll', measure, true);
    return () => {
      cancelled = true;
      clearTimeout(t1);
      clearTimeout(t2);
      window.removeEventListener('resize', measure);
      window.removeEventListener('scroll', measure, true);
    };
  }, [selector, active]);

  return rect;
}

export function GuidedTour() {
  const { user } = useAuth();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();
  const [active, setActive] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);

  const finish = useCallback(() => {
    if (user?.id) localStorage.setItem(guidedTourKey(user.id), 'done');
    setActive(false);
    setStepIndex(0);
    const msg = t('onboardingFindAgainToast');
    if (notifyFindAgainOnce(msg)) toast.message(msg);
  }, [user?.id, t]);

  const begin = useCallback(() => {
    if (!user?.id) return;
    const status = localStorage.getItem(guidedTourKey(user.id));
    // pending = queued; in_progress = already showing (do not reset step on remount/nav)
    if (status !== 'pending') return;
    localStorage.setItem(guidedTourKey(user.id), 'in_progress');
    setStepIndex(0);
    setActive(true);
    navigate(TOUR_STEPS[0].path);
  }, [user?.id, navigate]);

  useEffect(() => {
    if (!user?.id) return;
    const status = localStorage.getItem(guidedTourKey(user.id));
    if (status === 'pending') {
      // Delay so onboarding dialog can close first
      const timer = setTimeout(begin, 600);
      return () => clearTimeout(timer);
    }
    // Abandoned mid-tour (refresh / new tab) — never trap returning users
    if (status === 'in_progress') {
      localStorage.setItem(guidedTourKey(user.id), 'done');
      setActive(false);
    }
  }, [user?.id, begin]);

  useEffect(() => {
    const onStart = () => begin();
    window.addEventListener('laro-start-guided-tour', onStart);
    return () => window.removeEventListener('laro-start-guided-tour', onStart);
  }, [begin]);

  const step = TOUR_STEPS[stepIndex];

  // Do not force-redirect when the user navigates away — Next/Back still move on purpose.

  const spotlight = useSpotlightRect(step?.target, active && !!step?.target);

  if (!active || !step || isPublicRecipeViewPath(location.pathname)) return null;

  const Icon = step.icon;
  const isLast = stepIndex === TOUR_STEPS.length - 1;

  const goNext = () => {
    if (isLast) {
      finish();
      navigate('/dashboard');
      return;
    }
    const next = stepIndex + 1;
    setStepIndex(next);
    navigate(TOUR_STEPS[next].path);
  };

  const goBack = () => {
    if (stepIndex === 0) return;
    const prev = stepIndex - 1;
    setStepIndex(prev);
    navigate(TOUR_STEPS[prev].path);
  };

  return (
    <div
      className="fixed inset-0 z-[90] pointer-events-none"
      data-testid="guided-tour"
      aria-live="polite"
    >
      {/* Soft spotlight only — no full-screen dim that traps navigation */}
      {spotlight && (
        <div
          className="absolute z-[1] rounded-xl ring-2 ring-laro ring-offset-2 ring-offset-transparent pointer-events-none transition-all duration-300"
          style={{
            top: spotlight.top,
            left: spotlight.left,
            width: spotlight.width,
            height: spotlight.height,
          }}
        />
      )}
      <div
        className="absolute bottom-20 sm:bottom-6 left-4 right-4 sm:left-auto sm:right-6 sm:w-[380px] z-[2] pointer-events-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={step.id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="rounded-2xl bg-background border border-border shadow-xl p-5"
          >
            <div className="flex items-start justify-between gap-3 mb-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-laro/10 flex items-center justify-center">
                  <Icon className="w-5 h-5 text-laro" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">
                    {t('tourProgress', { current: stepIndex + 1, total: TOUR_STEPS.length })}
                  </p>
                  <h2 className="font-heading font-semibold text-lg leading-tight">
                    {t(step.titleKey)}
                  </h2>
                </div>
              </div>
              <button
                type="button"
                onClick={finish}
                className="p-1 rounded-md text-muted-foreground hover:text-foreground"
                aria-label={t('skip')}
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-sm text-muted-foreground mb-4">{t(step.bodyKey)}</p>
            <div className="flex gap-1.5 mb-4">
              {TOUR_STEPS.map((s, i) => (
                <div
                  key={s.id}
                  className={`h-1.5 flex-1 rounded-full ${i <= stepIndex ? 'bg-laro' : 'bg-border'}`}
                />
              ))}
            </div>
            <div className="flex items-center justify-between gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={goBack}
                disabled={stepIndex === 0}
                className="rounded-full"
              >
                <ArrowLeft className="w-4 h-4 mr-1" />
                {t('back')}
              </Button>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={finish} className="rounded-full">
                  {t('tourSkip')}
                </Button>
                <Button size="sm" onClick={goNext} className="rounded-full bg-laro hover:bg-laro-dark">
                  {isLast ? (
                    <>
                      <Sparkles className="w-4 h-4 mr-1" />
                      {t('tourFinish')}
                    </>
                  ) : (
                    <>
                      {t('next')}
                      <ArrowRight className="w-4 h-4 ml-1" />
                    </>
                  )}
                </Button>
              </div>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}

export default GuidedTour;
