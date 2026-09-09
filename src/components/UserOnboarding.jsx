import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { useAccessibility, ACCESSIBILITY_PRESETS } from '../context/AccessibilityContext';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Input } from './ui/input';
import { Switch } from './ui/switch';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import {
  ChefHat,
  Heart,
  Settings,
  Sparkles,
  ArrowRight,
  ArrowLeft,
  Check,
  X,
  Globe,
  Sun,
  Moon,
  Scale,
  ShieldAlert,
  Users,
  Map,
  Home,
  Target,
} from 'lucide-react';
import api, { authApi, preferencesApi } from '../lib/api';
import { useLanguage, COUNTRIES, defaultsForCountry } from '../context/LanguageContext';
import { useTheme } from '../context/ThemeContext';
import { startGuidedTour } from './GuidedTour';
import { onboardingKey, notifyFindAgainOnce } from '../lib/onboarding';
import { isPublicRecipeViewPath } from '../lib/publicRecipeView';
import { toast } from 'sonner';
import { OnboardingInvite } from './onboarding/OnboardingInvite';

function isPublicSharePath(pathname = '') {
  return isPublicRecipeViewPath(pathname);
}

const PRESET_LABEL_KEYS = {
  default: { name: 'presetDefault', desc: 'presetDefaultDesc' },
  adhd: { name: 'presetFocusAdhd', desc: 'presetFocusAdhdDesc' },
  dyslexia: { name: 'presetReadingDyslexia', desc: 'presetReadingDyslexiaDesc' },
  autism: { name: 'presetPredictableAutism', desc: 'presetPredictableAutismDesc' },
  sensory: { name: 'presetQuietSensory', desc: 'presetQuietSensoryDesc' },
};

const DIETARY_OPTIONS = [
  { id: 'vegetarian', key: 'vegetarian', emoji: '🥗' },
  { id: 'vegan', key: 'vegan', emoji: '🌱' },
  { id: 'gluten-free', key: 'glutenFree', emoji: '🌾' },
  { id: 'dairy-free', key: 'dairyFree', emoji: '🥛' },
  { id: 'nut-free', key: 'nutFree', emoji: '🥜' },
  { id: 'high-protein', key: 'highProtein', emoji: '💪' },
  { id: 'keto', key: 'keto', emoji: '🥑' },
  { id: 'paleo', key: 'paleo', emoji: '🍖' },
  { id: 'halal', key: 'halal', emoji: '☪️' },
  { id: 'kosher', key: 'kosher', emoji: '✡️' },
];

const ALLERGEN_OPTIONS = [
  'peanuts',
  'tree nuts',
  'milk',
  'eggs',
  'wheat',
  'soy',
  'fish',
  'shellfish',
  'sesame',
];

const DISLIKE_OPTIONS = [
  'cilantro',
  'mushrooms',
  'olives',
  'anchovies',
  'blue cheese',
  'liver',
  'eggplant',
  'coconut',
];

const KID_VETO_OPTIONS = [
  'broccoli',
  'peas',
  'mushrooms',
  'onions',
  'spicy peppers',
  'fish',
  'olives',
  'tomatoes',
];

const CUISINE_OPTIONS = [
  'italian', 'mexican', 'indian', 'chinese', 'japanese', 'thai',
  'mediterranean', 'american', 'french', 'middle-eastern', 'british', 'korean',
];

const WFH_DAY_OPTIONS = [
  { id: 'mon', key: 'weekdayMon' },
  { id: 'tue', key: 'weekdayTue' },
  { id: 'wed', key: 'weekdayWed' },
  { id: 'thu', key: 'weekdayThu' },
  { id: 'fri', key: 'weekdayFri' },
  { id: 'sat', key: 'weekdaySat' },
  { id: 'sun', key: 'weekdaySun' },
];

export const UserOnboarding = () => {
  const { user } = useAuth();
  const { language, setLanguage, languages, t } = useLanguage();
  const { theme, setTheme } = useTheme();
  const accessibility = useAccessibility();
  const navigate = useNavigate();
  const location = useLocation();

  const STEPS = [
    { id: 'welcome', title: t('onboardingWelcome') },
    { id: 'kitchen', title: t('onboardingKitchenTitle') },
    { id: 'accessibility', title: t('accessibility') },
    { id: 'safety', title: t('onboardingSafetyTitle') },
    { id: 'taste', title: t('onboardingTasteTitle') },
    { id: 'lifestyle', title: t('onboardingLifestyleTitle') },
    { id: 'complete', title: t('onboardingReady') },
  ];

  // Soft invite first — full wizard only if the user opts in (less blocking).
  const [inviteOpen, setInviteOpen] = useState(false);
  const [open, setOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedPreset, setSelectedPreset] = useState(null);
  const [saving, setSaving] = useState(false);
  const [customAdultVeto, setCustomAdultVeto] = useState('');
  const [customKidVeto, setCustomKidVeto] = useState('');
  const [preferences, setPreferences] = useState({
    measurementUnit: 'metric',
    dietaryRestrictions: [],
    allergens: [],
    dislikedIngredients: [],
    kidVetoIngredients: [],
    favoriteCuisines: [],
    defaultServings: 4,
    weekStartsOn: 'monday',
    country: 'GB',
    language: language || 'en-GB',
    hasChildren: false,
    kidFriendlyMeals: true,
    familyOneMeal: true,
    worksFromHome: false,
    wfhDays: [],
    dailyCalorieTarget: '',
    dailyProteinTarget: '',
  });

  // Signup sets `pending`; Learn more CTA dispatches the same. Missing key ≠ show.
  useEffect(() => {
    if (!user) return;
    if (isPublicSharePath(location.pathname)) return;
    if (localStorage.getItem(onboardingKey(user.id)) !== 'pending') return;
    const timer = setTimeout(() => {
      setCurrentStep(0);
      setInviteOpen(true);
    }, 500);
    return () => clearTimeout(timer);
  }, [user, location.pathname]);

  useEffect(() => {
    const onStart = () => {
      if (isPublicSharePath(location.pathname)) return;
      setCurrentStep(0);
      setOpen(false);
      setInviteOpen(true);
    };
    window.addEventListener('laro-start-onboarding', onStart);
    return () => window.removeEventListener('laro-start-onboarding', onStart);
  }, [location.pathname]);

  const handleSkip = () => {
    if (user?.id) {
      localStorage.setItem(onboardingKey(user.id), 'skipped');
    }
    setInviteOpen(false);
    setOpen(false);
    const msg = t('onboardingFindAgainToast');
    if (notifyFindAgainOnce(msg)) toast.message(msg);
  };

  const startWizard = () => {
    setInviteOpen(false);
    setCurrentStep(0);
    setOpen(true);
  };

  const savePreferences = async () => {
    const highProtein = preferences.dietaryRestrictions?.includes('high-protein');
    const proteinVal =
      preferences.dailyProteinTarget === '' || preferences.dailyProteinTarget == null
        ? highProtein
          ? 140
          : null
        : Number(preferences.dailyProteinTarget);
    const calorieVal =
      preferences.dailyCalorieTarget === '' || preferences.dailyCalorieTarget == null
        ? highProtein
          ? 2200
          : null
        : Number(preferences.dailyCalorieTarget);
    const payload = {
      ...preferences,
      language,
      theme,
      hasChildren: !!preferences.hasChildren,
      kidFriendlyMeals: preferences.hasChildren
        ? preferences.kidFriendlyMeals !== false
        : !!preferences.kidFriendlyMeals,
      familyOneMeal: preferences.hasChildren
        ? preferences.familyOneMeal !== false
        : !!preferences.familyOneMeal,
      worksFromHome: !!preferences.worksFromHome,
      wfhDays: preferences.worksFromHome ? preferences.wfhDays || [] : [],
      dislikedIngredients: preferences.dislikedIngredients || [],
      kidVetoIngredients: preferences.hasChildren
        ? preferences.kidVetoIngredients || []
        : [],
      dailyProteinTarget: proteinVal,
      dailyCalorieTarget: calorieVal,
    };
    await preferencesApi.update(payload).catch(() =>
      api.put('/preferences', payload)
    );
    // Dual-write allergens for recipe safety checks
    if (preferences.allergens?.length) {
      try {
        await authApi.updateProfile({ allergies: preferences.allergens });
      } catch (_) { /* non-blocking */ }
    }
  };

  const completeOnboarding = async ({ startTour = false, goImport = false } = {}) => {
    setSaving(true);
    try {
      await savePreferences();
    } catch (error) {
      console.error('Failed to save preferences:', error);
    } finally {
      if (user?.id) localStorage.setItem(onboardingKey(user.id), 'completed');
      setOpen(false);
      setInviteOpen(false);
      setSaving(false);
      if (startTour && user?.id) {
        startGuidedTour(user.id);
        navigate('/dashboard');
      } else if (goImport) {
        localStorage.setItem(`laro_guided_tour_${user?.id}`, 'done');
        const msg = t('onboardingFindAgainToast');
        if (notifyFindAgainOnce(msg)) toast.message(msg);
        navigate('/recipes/import');
      } else {
        const msg = t('onboardingFindAgainToast');
        if (notifyFindAgainOnce(msg)) toast.message(msg);
        navigate('/dashboard');
      }
    }
  };

  const handleNext = async () => {
    if (currentStep === STEPS.length - 1) {
      await completeOnboarding({ startTour: true });
    } else {
      setCurrentStep((s) => s + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) setCurrentStep((s) => s - 1);
  };

  const applyAccessibilityPreset = (presetKey) => {
    setSelectedPreset(presetKey);
    accessibility.applyPreset(presetKey);
  };

  const toggleList = (field, id) => {
    setPreferences((prev) => ({
      ...prev,
      [field]: prev[field].includes(id)
        ? prev[field].filter((x) => x !== id)
        : [...prev[field], id],
    }));
  };

  const addCustomToList = (field, value, clear) => {
    const item = (value || '').trim().toLowerCase();
    if (!item) return;
    setPreferences((prev) => ({
      ...prev,
      [field]: prev[field].includes(item) ? prev[field] : [...prev[field], item],
    }));
    clear('');
  };

  const highProteinSelected = preferences.dietaryRestrictions?.includes('high-protein');

  return (
    <>
      {inviteOpen && !open && (
        <OnboardingInvite
          userName={user?.name?.split(' ')[0]}
          t={t}
          onSkip={handleSkip}
          onStart={startWizard}
        />
      )}

    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v && open) handleSkip();
        else setOpen(v);
      }}
    >
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="user-onboarding">
        <button
          type="button"
          onClick={handleSkip}
          className="absolute right-4 top-4 rounded-sm opacity-70 hover:opacity-100 z-10"
        >
          <X className="h-4 w-4" />
          <span className="sr-only">{t('skip')}</span>
        </button>

        <div className="flex justify-center gap-1.5 mb-4 pt-2">
          {STEPS.map((step, index) => (
            <div
              key={step.id}
              className={`h-2 rounded-full transition-all ${
                index === currentStep
                  ? 'w-8 bg-laro'
                  : index < currentStep
                    ? 'w-2 bg-laro/50'
                    : 'w-2 bg-border'
              }`}
            />
          ))}
        </div>

        <AnimatePresence mode="wait">
          {currentStep === 0 && (
            <motion.div key="welcome" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <DialogHeader>
                <div className="w-16 h-16 bg-laro/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <ChefHat className="w-8 h-8 text-laro" />
                </div>
                <DialogTitle className="text-center text-2xl">
                  {t('welcomeToLaro', { name: user?.name?.split(' ')[0] || '' })}
                </DialogTitle>
                <DialogDescription className="text-center">
                  {t('onboardingIntroV2')}
                </DialogDescription>
              </DialogHeader>
              <div className="mt-6 space-y-3">
                {[
                  { icon: Settings, title: t('onboardingBulletKitchen'), desc: t('onboardingBulletKitchenDesc') },
                  { icon: ShieldAlert, title: t('onboardingBulletSafety'), desc: t('onboardingBulletSafetyDesc') },
                  { icon: Map, title: t('onboardingBulletTour'), desc: t('onboardingBulletTourDesc') },
                ].map(({ icon: Icon, title, desc }) => (
                  <div key={title} className="flex items-start gap-3 p-3 bg-cream-subtle dark:bg-muted rounded-xl">
                    <Icon className="w-5 h-5 text-laro flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium text-sm">{title}</p>
                      <p className="text-xs text-muted-foreground">{desc}</p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-6 flex flex-col gap-2">
                <Button
                  onClick={handleNext}
                  className="w-full rounded-full bg-laro hover:bg-laro-dark h-11"
                  data-testid="onboarding-get-started"
                >
                  {t('onboardingStartSetup')}
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
                <Button
                  variant="ghost"
                  onClick={handleSkip}
                  className="w-full rounded-full"
                  data-testid="onboarding-skip"
                >
                  {t('onboardingExploreFirst')}
                </Button>
              </div>
            </motion.div>
          )}

          {currentStep === 1 && (
            <motion.div key="kitchen" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <DialogHeader>
                <div className="w-16 h-16 bg-laro/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Settings className="w-8 h-8 text-laro" />
                </div>
                <DialogTitle className="text-center">{t('onboardingKitchenTitle')}</DialogTitle>
                <DialogDescription className="text-center">{t('onboardingKitchenDesc')}</DialogDescription>
              </DialogHeader>

              <div className="mt-6 space-y-5">
                <div>
                  <Label className="mb-2 block flex items-center gap-2">
                    <PaletteIcon />
                    {t('theme')}
                  </Label>
                  <div className="flex gap-2">
                    {[
                      { id: 'light', icon: Sun, label: t('light') },
                      { id: 'dark', icon: Moon, label: t('dark') },
                    ].map(({ id, icon: Icon, label }) => (
                      <button
                        key={id}
                        type="button"
                        onClick={() => setTheme(id)}
                        className={`flex-1 flex flex-col items-center gap-2 p-3 rounded-xl border-2 ${
                          theme === id ? 'border-laro bg-laro/10' : 'border-border/60'
                        }`}
                      >
                        <Icon className={`w-5 h-5 ${theme === id ? 'text-laro' : 'text-muted-foreground'}`} />
                        <span className="text-sm font-medium">{label}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <Label className="mb-2 block flex items-center gap-2">
                    <Globe className="w-4 h-4" />
                    {t('country')}
                  </Label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-36 overflow-y-auto pr-1">
                    {Object.entries(COUNTRIES).map(([code, { name, flag }]) => (
                      <button
                        key={code}
                        type="button"
                        onClick={() => {
                          const defaults = defaultsForCountry(code);
                          setPreferences((prev) => ({
                            ...prev,
                            country: code,
                            measurementUnit: defaults.measurementUnit,
                            language: defaults.language,
                          }));
                          setLanguage(defaults.language);
                        }}
                        className={`flex items-center gap-2 p-2 rounded-xl border-2 text-left ${
                          preferences.country === code ? 'border-laro bg-laro/10' : 'border-border/60'
                        }`}
                      >
                        <span className="text-lg" aria-hidden="true">{flag}</span>
                        <span className="text-xs font-medium truncate">{name}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <Label className="mb-2 block">{t('language')}</Label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-32 overflow-y-auto">
                    {Object.entries(languages).map(([code, { name, flag }]) => (
                      <button
                        key={code}
                        type="button"
                        onClick={() => {
                          setLanguage(code);
                          setPreferences((prev) => ({ ...prev, language: code }));
                        }}
                        className={`flex flex-col items-center gap-1 p-2 rounded-xl border-2 ${
                          language === code ? 'border-laro bg-laro/10' : 'border-border/60'
                        }`}
                      >
                        <span className="text-xl" aria-hidden="true">{flag}</span>
                        <span className="text-xs font-medium text-center">{name}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <Label className="mb-2 block flex items-center gap-2">
                    <Scale className="w-4 h-4" />
                    {t('measurementUnits')}
                  </Label>
                  <div className="flex gap-2">
                    {[
                      { id: 'metric', label: t('metric'), desc: t('metricDesc') },
                      { id: 'imperial', label: t('imperial'), desc: t('imperialDesc') },
                    ].map(({ id, label, desc }) => (
                      <button
                        key={id}
                        type="button"
                        onClick={() => setPreferences((prev) => ({ ...prev, measurementUnit: id }))}
                        className={`flex-1 p-3 rounded-xl border-2 ${
                          preferences.measurementUnit === id ? 'border-laro bg-laro/10' : 'border-border/60'
                        }`}
                      >
                        <p className="font-medium text-sm">{label}</p>
                        <p className="text-xs text-muted-foreground">{desc}</p>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <Label className="mb-2 block flex items-center gap-2">
                    <Users className="w-4 h-4" />
                    {t('defaultServings')}
                  </Label>
                  <p className="text-xs text-muted-foreground mb-2">{t('onboardingServingsHint')}</p>
                  <div className="flex flex-wrap gap-2">
                    {[1, 2, 3, 4, 5, 6, 8].map((n) => (
                      <button
                        key={n}
                        type="button"
                        onClick={() => setPreferences((prev) => ({ ...prev, defaultServings: n }))}
                        className={`w-11 h-11 rounded-full border-2 font-medium ${
                          preferences.defaultServings === n
                            ? 'border-laro bg-laro text-white'
                            : 'border-border/60'
                        }`}
                      >
                        {n}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <Label className="mb-2 block">{t('weekStartsOn')}</Label>
                  <div className="flex gap-2">
                    {[
                      { id: 'monday', label: t('monday') || 'Monday' },
                      { id: 'sunday', label: t('sunday') || 'Sunday' },
                    ].map(({ id, label }) => (
                      <button
                        key={id}
                        type="button"
                        onClick={() => setPreferences((prev) => ({ ...prev, weekStartsOn: id }))}
                        className={`flex-1 p-3 rounded-xl border-2 text-sm font-medium ${
                          preferences.weekStartsOn === id ? 'border-laro bg-laro/10' : 'border-border/60'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {currentStep === 2 && (
            <motion.div key="a11y" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <DialogHeader>
                <div className="w-16 h-16 bg-laro/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Heart className="w-8 h-8 text-laro" />
                </div>
                <DialogTitle className="text-center">{t('accessibilitySettings')}</DialogTitle>
                <DialogDescription className="text-center">{t('choosePresetOrSkip')}</DialogDescription>
              </DialogHeader>
              <div className="mt-6 space-y-3">
                {Object.entries(ACCESSIBILITY_PRESETS).map(([key, preset]) => {
                  const labelKeys = PRESET_LABEL_KEYS[key];
                  return (
                    <button
                      key={key}
                      type="button"
                      onClick={() => applyAccessibilityPreset(key)}
                      className={`w-full text-left p-4 rounded-xl border-2 ${
                        selectedPreset === key ? 'border-laro bg-laro/5' : 'border-border/60'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="font-medium">{labelKeys ? t(labelKeys.name) : preset.name}</p>
                          <p className="text-sm text-muted-foreground mt-0.5">
                            {labelKeys ? t(labelKeys.desc) : preset.description}
                          </p>
                        </div>
                        {selectedPreset === key && <Check className="w-5 h-5 text-laro flex-shrink-0" />}
                      </div>
                    </button>
                  );
                })}
              </div>
              <p className="mt-4 text-sm text-muted-foreground bg-cream-subtle dark:bg-muted p-3 rounded-xl">
                {t('onboardingTip')}
              </p>
            </motion.div>
          )}

          {currentStep === 3 && (
            <motion.div key="safety" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <DialogHeader>
                <div className="w-16 h-16 bg-laro/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <ShieldAlert className="w-8 h-8 text-laro" />
                </div>
                <DialogTitle className="text-center">{t('onboardingSafetyTitle')}</DialogTitle>
                <DialogDescription className="text-center">{t('onboardingSafetyDesc')}</DialogDescription>
              </DialogHeader>
              <div className="mt-6 space-y-5">
                <div>
                  <Label className="mb-2 block">{t('dietaryPreferencesOptional')}</Label>
                  <div className="flex flex-wrap gap-2">
                    {DIETARY_OPTIONS.map((option) => (
                      <button
                        key={option.id}
                        type="button"
                        onClick={() => toggleList('dietaryRestrictions', option.id)}
                        className={`px-3 py-1.5 rounded-full text-sm font-medium ${
                          preferences.dietaryRestrictions.includes(option.id)
                            ? 'bg-laro text-white'
                            : 'bg-cream-subtle dark:bg-muted'
                        }`}
                      >
                        {option.emoji} {t(option.key)}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <Label className="mb-2 block">{t('allergies')}</Label>
                  <p className="text-xs text-muted-foreground mb-2">{t('allergiesHint')}</p>
                  <div className="flex flex-wrap gap-2">
                    {ALLERGEN_OPTIONS.map((allergen) => (
                      <button
                        key={allergen}
                        type="button"
                        onClick={() => toggleList('allergens', allergen)}
                        className={`px-3 py-1.5 rounded-full text-sm font-medium capitalize ${
                          preferences.allergens.includes(allergen)
                            ? 'bg-coral text-white'
                            : 'bg-cream-subtle dark:bg-muted'
                        }`}
                      >
                        {allergen}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <Label className="mb-2 block">{t('adultVetoList')}</Label>
                  <p className="text-xs text-muted-foreground mb-2">{t('adultVetoHint')}</p>
                  <div className="flex flex-wrap gap-2" data-testid="onboarding-adult-veto">
                    {[...new Set([...DISLIKE_OPTIONS, ...(preferences.dislikedIngredients || [])])].map((item) => (
                      <button
                        key={item}
                        type="button"
                        onClick={() => toggleList('dislikedIngredients', item)}
                        className={`px-3 py-1.5 rounded-full text-sm font-medium capitalize ${
                          preferences.dislikedIngredients.includes(item)
                            ? 'bg-amber-600 text-white'
                            : 'bg-cream-subtle dark:bg-muted'
                        }`}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                  <div className="flex gap-2 mt-2">
                    <Input
                      value={customAdultVeto}
                      onChange={(e) => setCustomAdultVeto(e.target.value)}
                      placeholder={t('adultVetoPlaceholder')}
                      className="rounded-xl"
                      data-testid="onboarding-adult-veto-input"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          addCustomToList('dislikedIngredients', customAdultVeto, setCustomAdultVeto);
                        }
                      }}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      className="rounded-xl shrink-0"
                      onClick={() =>
                        addCustomToList('dislikedIngredients', customAdultVeto, setCustomAdultVeto)
                      }
                    >
                      {t('add')}
                    </Button>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {currentStep === 4 && (
            <motion.div key="taste" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <DialogHeader>
                <div className="w-16 h-16 bg-laro/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Sparkles className="w-8 h-8 text-laro" />
                </div>
                <DialogTitle className="text-center">{t('onboardingTasteTitle')}</DialogTitle>
                <DialogDescription className="text-center">{t('onboardingTasteDesc')}</DialogDescription>
              </DialogHeader>
              <div className="mt-6">
                <Label className="mb-2 block">{t('onboardingCuisinesLabel')}</Label>
                <div className="flex flex-wrap gap-2">
                  {CUISINE_OPTIONS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      onClick={() => toggleList('favoriteCuisines', c)}
                      className={`px-3 py-1.5 rounded-full text-sm font-medium capitalize ${
                        preferences.favoriteCuisines.includes(c)
                          ? 'bg-laro text-white'
                          : 'bg-cream-subtle dark:bg-muted'
                      }`}
                    >
                      {c.replace('-', ' ')}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground mt-3">{t('onboardingTasteOptional')}</p>
              </div>
            </motion.div>
          )}

          {currentStep === 5 && (
            <motion.div key="lifestyle" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <DialogHeader>
                <div className="w-16 h-16 bg-laro/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Home className="w-8 h-8 text-laro" />
                </div>
                <DialogTitle className="text-center">{t('onboardingLifestyleTitle')}</DialogTitle>
                <DialogDescription className="text-center">{t('onboardingLifestyleDesc')}</DialogDescription>
              </DialogHeader>

              <div className="mt-6 space-y-5" data-testid="onboarding-lifestyle">
                <div className="flex items-center justify-between gap-3 p-3 rounded-xl border border-border/60">
                  <div className="min-w-0">
                    <p className="font-medium text-sm flex items-center gap-2">
                      <Users className="w-4 h-4 text-laro shrink-0" />
                      {t('hasChildrenQuestion')}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">{t('hasChildrenHint')}</p>
                  </div>
                  <Switch
                    checked={!!preferences.hasChildren}
                    onCheckedChange={(checked) =>
                      setPreferences((prev) => ({
                        ...prev,
                        hasChildren: checked,
                        kidFriendlyMeals: checked ? true : prev.kidFriendlyMeals,
                        familyOneMeal: checked ? true : prev.familyOneMeal,
                      }))
                    }
                    data-testid="onboarding-has-children"
                  />
                </div>

                {preferences.hasChildren && (
                  <div className="flex items-center justify-between gap-3 p-3 rounded-xl bg-cream-subtle dark:bg-muted">
                    <div className="min-w-0">
                      <p className="font-medium text-sm">{t('kidFriendlyMeals')}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{t('kidFriendlyMealsHint')}</p>
                    </div>
                    <Switch
                      checked={preferences.kidFriendlyMeals !== false}
                      onCheckedChange={(checked) =>
                        setPreferences((prev) => ({ ...prev, kidFriendlyMeals: checked }))
                      }
                      data-testid="onboarding-kid-friendly"
                    />
                  </div>
                )}

                {preferences.hasChildren && (
                  <div className="flex items-center justify-between gap-3 p-3 rounded-xl bg-cream-subtle dark:bg-muted">
                    <div className="min-w-0">
                      <p className="font-medium text-sm">{t('familyOneMeal')}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{t('familyOneMealHint')}</p>
                    </div>
                    <Switch
                      checked={preferences.familyOneMeal !== false}
                      onCheckedChange={(checked) =>
                        setPreferences((prev) => ({ ...prev, familyOneMeal: checked }))
                      }
                      data-testid="onboarding-family-one-meal"
                    />
                  </div>
                )}

                {preferences.hasChildren && (
                  <div data-testid="onboarding-kid-veto">
                    <Label className="mb-2 block">{t('kidVetoList')}</Label>
                    <p className="text-xs text-muted-foreground mb-2">{t('kidVetoHint')}</p>
                    <div className="flex flex-wrap gap-2">
                      {[...new Set([...KID_VETO_OPTIONS, ...(preferences.kidVetoIngredients || [])])].map((item) => (
                        <button
                          key={item}
                          type="button"
                          onClick={() => toggleList('kidVetoIngredients', item)}
                          className={`px-3 py-1.5 rounded-full text-sm font-medium capitalize ${
                            preferences.kidVetoIngredients?.includes(item)
                              ? 'bg-sky-600 text-white'
                              : 'bg-cream-subtle dark:bg-muted'
                          }`}
                        >
                          {item}
                        </button>
                      ))}
                    </div>
                    <div className="flex gap-2 mt-2">
                      <Input
                        value={customKidVeto}
                        onChange={(e) => setCustomKidVeto(e.target.value)}
                        placeholder={t('kidVetoPlaceholder')}
                        className="rounded-xl"
                        data-testid="onboarding-kid-veto-input"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            addCustomToList('kidVetoIngredients', customKidVeto, setCustomKidVeto);
                          }
                        }}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        className="rounded-xl shrink-0"
                        onClick={() =>
                          addCustomToList('kidVetoIngredients', customKidVeto, setCustomKidVeto)
                        }
                      >
                        {t('add')}
                      </Button>
                    </div>
                  </div>
                )}

                <div className="flex items-center justify-between gap-3 p-3 rounded-xl border border-border/60">
                  <div className="min-w-0">
                    <p className="font-medium text-sm flex items-center gap-2">
                      <Home className="w-4 h-4 text-laro shrink-0" />
                      {t('worksFromHomeQuestion')}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">{t('worksFromHomeHint')}</p>
                  </div>
                  <Switch
                    checked={!!preferences.worksFromHome}
                    onCheckedChange={(checked) =>
                      setPreferences((prev) => ({
                        ...prev,
                        worksFromHome: checked,
                        wfhDays: checked && !(prev.wfhDays || []).length
                          ? ['mon', 'tue', 'wed', 'thu', 'fri']
                          : prev.wfhDays,
                      }))
                    }
                    data-testid="onboarding-wfh"
                  />
                </div>

                {preferences.worksFromHome && (
                  <div>
                    <Label className="mb-2 block">{t('wfhDaysLabel')}</Label>
                    <div className="flex flex-wrap gap-2" data-testid="onboarding-wfh-days">
                      {WFH_DAY_OPTIONS.map(({ id, key }) => (
                        <button
                          key={id}
                          type="button"
                          onClick={() => toggleList('wfhDays', id)}
                          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                            preferences.wfhDays?.includes(id)
                              ? 'bg-laro text-white'
                              : 'bg-cream-subtle dark:bg-muted hover:bg-laro/20'
                          }`}
                        >
                          {preferences.wfhDays?.includes(id) && (
                            <Check className="w-3 h-3 inline mr-1" />
                          )}
                          {t(key)}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <Label className="mb-2 block flex items-center gap-2">
                    <Target className="w-4 h-4 text-laro" />
                    {t('onboardingGoalsLabel')}
                  </Label>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <Label htmlFor="ob-calories" className="text-xs text-muted-foreground">
                        {t('dailyCalorieTarget')}
                      </Label>
                      <Input
                        id="ob-calories"
                        data-testid="onboarding-calorie-target"
                        type="number"
                        min={0}
                        max={10000}
                        step={10}
                        className="mt-1 rounded-xl"
                        placeholder={highProteinSelected ? '2200' : '2000'}
                        value={preferences.dailyCalorieTarget ?? ''}
                        onChange={(e) =>
                          setPreferences((prev) => ({
                            ...prev,
                            dailyCalorieTarget: e.target.value === '' ? '' : e.target.value,
                          }))
                        }
                      />
                    </div>
                    <div>
                      <Label htmlFor="ob-protein" className="text-xs text-muted-foreground">
                        {t('dailyProteinTarget')}
                      </Label>
                      <Input
                        id="ob-protein"
                        data-testid="onboarding-protein-target"
                        type="number"
                        min={0}
                        max={500}
                        step={1}
                        className="mt-1 rounded-xl"
                        placeholder={highProteinSelected ? '140' : '100'}
                        value={preferences.dailyProteinTarget ?? ''}
                        onChange={(e) =>
                          setPreferences((prev) => ({
                            ...prev,
                            dailyProteinTarget: e.target.value === '' ? '' : e.target.value,
                          }))
                        }
                      />
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">{t('onboardingGoalsHint')}</p>
                </div>
              </div>
            </motion.div>
          )}

          {currentStep === 6 && (
            <motion.div key="done" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <DialogHeader>
                <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Sparkles className="w-8 h-8 text-green-600 dark:text-green-400" />
                </div>
                <DialogTitle className="text-center text-2xl">{t('youreAllSet')}</DialogTitle>
                <DialogDescription className="text-center">{t('personalizedReady')}</DialogDescription>
              </DialogHeader>
              <div className="mt-6 space-y-3">
                <p className="text-sm text-muted-foreground text-center">{t('onboardingNextHint')}</p>
                <p className="text-xs text-muted-foreground text-center">{t('onboardingFindAgainHint')}</p>
                <Button
                  className="w-full rounded-full bg-laro hover:bg-laro-dark h-12"
                  disabled={saving}
                  onClick={() => completeOnboarding({ startTour: true })}
                  data-testid="onboarding-start-tour"
                >
                  <Map className="w-4 h-4 mr-2" />
                  {t('onboardingStartTour')}
                </Button>
                <Button
                  variant="outline"
                  className="w-full rounded-full h-11"
                  disabled={saving}
                  onClick={() => completeOnboarding({ goImport: true })}
                >
                  {t('importFirstRecipeCta')}
                </Button>
                <Button
                  variant="ghost"
                  className="w-full rounded-full"
                  disabled={saving}
                  onClick={() => completeOnboarding({})}
                >
                  {t('goToDashboardInstead')}
                </Button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {currentStep > 0 && currentStep < STEPS.length - 1 && (
          <div className="flex justify-between mt-8 pt-4 border-t border-border/60">
            <Button
              variant="ghost"
              onClick={handleBack}
              disabled={currentStep === 0}
              className="rounded-full"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              {t('back')}
            </Button>
            <Button onClick={handleNext} className="rounded-full bg-laro hover:bg-laro-dark" data-testid="onboarding-next">
              {t('next')}
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
    </>
  );
};

function PaletteIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="13.5" cy="6.5" r=".5" fill="currentColor" />
      <circle cx="17.5" cy="10.5" r=".5" fill="currentColor" />
      <circle cx="8.5" cy="7.5" r=".5" fill="currentColor" />
      <circle cx="6.5" cy="12.5" r=".5" fill="currentColor" />
      <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z" />
    </svg>
  );
}

export default UserOnboarding;
