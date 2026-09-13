import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { useTheme, ACCENT_COLORS } from '../context/ThemeContext';
import { useLanguage, LANGUAGES, COUNTRIES, defaultsForCountry } from '../context/LanguageContext';
import { useAccessibility, ACCESSIBILITY_PRESETS } from '../context/AccessibilityContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import {
  Settings,
  Sun,
  Moon,
  Monitor,
  Scale,
  Utensils,
  Bell,
  Clock,
  Loader2,
  Save,
  Check,
  Globe,
  Palette,
  Zap,
  Eye,
  Heart,
  Focus,
  Type,
  Volume2,
  Sparkles,
  Target,
  AlignLeft,
  Home,
  Users,
} from 'lucide-react';
import { toast } from 'sonner';
import api, { calendarApi } from '../lib/api';
import { invalidateUserPreferencesCache } from '../hooks/useUserPreferences';

const DEFAULT_PREFERENCES = {
  theme: 'system',
  language: 'en-GB',
  country: 'GB',
  defaultServings: 4,
  measurementUnit: 'metric',
  dietaryRestrictions: [],
  dislikedIngredients: [],
  kidVetoIngredients: [],
  preferredRecipeSites: [],
  dailyProteinTarget: '',
  dailyCalorieTarget: '',
  dailyCarbTarget: '',
  dailyFatTarget: '',
  hasChildren: false,
  kidFriendlyMeals: true,
  familyOneMeal: true,
  worksFromHome: false,
  wfhDays: [],
  hasGymRoutine: false,
  gymDays: [],
  dinnerHeadcount: '',
  calendarIcsUrl: '',
  useCalendarForMealDifficulty: false,
  googleCalendarConnected: false,
  calendarTimezone: '',
  showNutrition: true,
  compactView: false,
  weekStartsOn: 'monday',
  mealPlanNotifications: true,
  shoppingListAutoSort: true,
  defaultCookingTime: 30,
};

const ADULT_VETO_OPTIONS = [
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

const WFH_DAY_OPTIONS = [
  { id: 'mon', key: 'weekdayMon' },
  { id: 'tue', key: 'weekdayTue' },
  { id: 'wed', key: 'weekdayWed' },
  { id: 'thu', key: 'weekdayThu' },
  { id: 'fri', key: 'weekdayFri' },
  { id: 'sat', key: 'weekdaySat' },
  { id: 'sun', key: 'weekdaySun' },
];

const DIETARY_OPTIONS = [
  { id: 'vegetarian', key: 'vegetarian' },
  { id: 'vegan', key: 'vegan' },
  { id: 'gluten-free', key: 'glutenFree' },
  { id: 'dairy-free', key: 'dairyFree' },
  { id: 'nut-free', key: 'nutFree' },
  { id: 'high-protein', key: 'highProtein' },
  { id: 'keto', key: 'keto' },
  { id: 'paleo', key: 'paleo' },
  { id: 'halal', key: 'halal' },
  { id: 'kosher', key: 'kosher' },
];

// Maps ACCESSIBILITY_PRESETS keys to their en.js translation keys.
const PRESET_LABEL_KEYS = {
  default: { name: 'presetDefault', desc: 'presetDefaultDesc' },
  adhd: { name: 'presetFocusAdhd', desc: 'presetFocusAdhdDesc' },
  dyslexia: { name: 'presetReadingDyslexia', desc: 'presetReadingDyslexiaDesc' },
  autism: { name: 'presetPredictableAutism', desc: 'presetPredictableAutismDesc' },
  sensory: { name: 'presetQuietSensory', desc: 'presetQuietSensoryDesc' },
};

export const UserPreferences = () => {
  const { user } = useAuth();
  const { theme, setTheme, accentColor, setAccentColor, accentColors, reducedMotion, setReducedMotion } = useTheme();
  const { language, setLanguage, t, languages } = useLanguage();
  const accessibility = useAccessibility();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
  const [hasChanges, setHasChanges] = useState(false);
  const [customAdultVeto, setCustomAdultVeto] = useState('');
  const [customKidVeto, setCustomKidVeto] = useState('');
  const [validatingIcs, setValidatingIcs] = useState(false);
  const [icsValidateMsg, setIcsValidateMsg] = useState('');

  useEffect(() => {
    loadPreferences();
  }, []);

  const loadPreferences = async () => {
    setLoading(true);
    try {
      const res = await api.get('/preferences');
      if (res.data) {
        setPreferences({
          ...DEFAULT_PREFERENCES,
          ...res.data,
          calendarIcsUrl: res.data.calendarIcsUrl || '',
          calendarTimezone: res.data.calendarTimezone || '',
        });
        if (res.data.language) {
          setLanguage(res.data.language);
        }
      }
    } catch (error) {
      // Use defaults if no preferences saved
      console.log('Using default preferences');
    } finally {
      setLoading(false);
    }
  };

  const handleValidateIcs = async () => {
    const url = (preferences.calendarIcsUrl || '').trim();
    if (!url) {
      setIcsValidateMsg('');
      toast.error(t('calendarIcsUrlRequired'));
      return;
    }
    setValidatingIcs(true);
    setIcsValidateMsg('');
    try {
      const res = await calendarApi.validateIcs(url);
      const n = res.data?.busy_blocks_next_14_days ?? 0;
      setIcsValidateMsg(t('calendarIcsValidateOk', { count: n }));
      toast.success(t('calendarIcsValidateOk', { count: n }));
    } catch (error) {
      const detail = error.response?.data?.detail || t('calendarIcsValidateFailed');
      setIcsValidateMsg(detail);
      toast.error(detail);
    } finally {
      setValidatingIcs(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        ...preferences,
        hasChildren: !!preferences.hasChildren,
        kidFriendlyMeals: preferences.hasChildren
          ? preferences.kidFriendlyMeals !== false
          : !!preferences.kidFriendlyMeals,
        familyOneMeal: preferences.hasChildren
          ? preferences.familyOneMeal !== false
          : !!preferences.familyOneMeal,
        worksFromHome: !!preferences.worksFromHome,
        wfhDays: preferences.worksFromHome ? preferences.wfhDays || [] : [],
        hasGymRoutine: !!preferences.hasGymRoutine,
        gymDays: preferences.hasGymRoutine ? preferences.gymDays || [] : [],
        dinnerHeadcount:
          preferences.dinnerHeadcount === '' || preferences.dinnerHeadcount == null
            ? null
            : Number(preferences.dinnerHeadcount),
        calendarIcsUrl: (preferences.calendarIcsUrl || '').trim() || null,
        useCalendarForMealDifficulty: !!preferences.useCalendarForMealDifficulty,
        googleCalendarConnected: !!preferences.googleCalendarConnected,
        calendarTimezone: (preferences.calendarTimezone || '').trim() || null,
        dislikedIngredients: preferences.dislikedIngredients || [],
        kidVetoIngredients: preferences.hasChildren
          ? preferences.kidVetoIngredients || []
          : [],
        dailyProteinTarget:
          preferences.dailyProteinTarget === '' || preferences.dailyProteinTarget == null
            ? null
            : Number(preferences.dailyProteinTarget),
        dailyCalorieTarget:
          preferences.dailyCalorieTarget === '' || preferences.dailyCalorieTarget == null
            ? null
            : Number(preferences.dailyCalorieTarget),
        dailyCarbTarget:
          preferences.dailyCarbTarget === '' || preferences.dailyCarbTarget == null
            ? null
            : Number(preferences.dailyCarbTarget),
        dailyFatTarget:
          preferences.dailyFatTarget === '' || preferences.dailyFatTarget == null
            ? null
            : Number(preferences.dailyFatTarget),
      };
      await api.put('/preferences', payload);
      invalidateUserPreferencesCache();
      // Keep notification_settings.meal_reminders aligned with this preference
      try {
        const { notificationApi } = await import('../lib/api');
        const current = await notificationApi.getSettings();
        await notificationApi.updateSettings({
          ...(current.data || {}),
          meal_reminders: !!preferences.mealPlanNotifications,
        });
      } catch (e) {
        console.warn('Could not sync meal reminder toggle to notification settings', e);
      }
      toast.success(t('toastPreferencesSaved'));
      setHasChanges(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('toastPreferencesSaveFailed')} (E-UP001)`);
    } finally {
      setSaving(false);
    }
  };

  const updatePreference = (key, value) => {
    setPreferences(prev => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  const handleThemeChange = (newTheme) => {
    updatePreference('theme', newTheme);
    if (newTheme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      setTheme(systemTheme);
    } else {
      setTheme(newTheme);
    }
  };

  const toggleDietaryRestriction = (id) => {
    const current = preferences.dietaryRestrictions || [];
    const updated = current.includes(id)
      ? current.filter(r => r !== id)
      : [...current, id];
    updatePreference('dietaryRestrictions', updated);
  };

  const toggleListPref = (field, id) => {
    const current = preferences[field] || [];
    const updated = current.includes(id)
      ? current.filter((x) => x !== id)
      : [...current, id];
    updatePreference(field, updated);
  };

  const addCustomListPref = (field, value, clear) => {
    const item = (value || '').trim().toLowerCase();
    if (!item) return;
    const current = preferences[field] || [];
    if (!current.includes(item)) {
      updatePreference(field, [...current, item]);
    }
    clear('');
  };

  const toggleWfhDay = (id) => {
    const current = preferences.wfhDays || [];
    const updated = current.includes(id)
      ? current.filter((d) => d !== id)
      : [...current, id];
    updatePreference('wfhDays', updated);
  };

  const toggleGymDay = (id) => {
    const current = preferences.gymDays || [];
    const updated = current.includes(id)
      ? current.filter((d) => d !== id)
      : [...current, id];
    updatePreference('gymDays', updated);
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
      <div className="max-w-2xl mx-auto space-y-6" data-testid="user-preferences">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between"
        >
          <div>
            <h1 className="font-heading text-3xl font-bold flex items-center gap-2">
              <Settings className="w-8 h-8 text-laro" />
              {t('preferences')}
            </h1>
            <p className="text-muted-foreground mt-1">{t('customizeLaro')}</p>
          </div>
          {hasChanges && (
            <Button
              onClick={handleSave}
              disabled={saving}
              className="rounded-full bg-laro hover:bg-laro-dark"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
              {t('saveChanges')}
            </Button>
          )}
        </motion.div>

        {/* Appearance */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle dark:bg-muted">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Sun className="w-5 h-5 text-laro" />
              {t('appearance')}
            </h2>
          </div>
          <div className="p-4 space-y-4">
            <div>
              <Label className="mb-3 block">{t('theme')}</Label>
              <div className="flex gap-3">
                {[
                  { id: 'light', icon: Sun, label: t('light') },
                  { id: 'dark', icon: Moon, label: t('dark') },
                  { id: 'system', icon: Monitor, label: t('system') },
                ].map(({ id, icon: Icon, label }) => (
                  <button
                    key={id}
                    onClick={() => handleThemeChange(id)}
                    className={`flex-1 flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all ${
                      preferences.theme === id
                        ? 'border-laro bg-laro/10'
                        : 'border-border/60 hover:border-laro/50'
                    }`}
                  >
                    <Icon className={`w-6 h-6 ${preferences.theme === id ? 'text-laro' : 'text-muted-foreground'}`} />
                    <span className={`text-sm font-medium ${preferences.theme === id ? 'text-laro' : ''}`}>{label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Accent Color */}
            <div>
              <Label className="mb-3 block flex items-center gap-2">
                <Palette className="w-4 h-4" />
                {t('accentColor')}
              </Label>
              <div className="flex gap-2 flex-wrap">
                {Object.entries(accentColors).map(([key, color]) => (
                  <button
                    key={key}
                    onClick={() => setAccentColor(key)}
                    title={color.name}
                    className={`w-10 h-10 rounded-xl transition-all ${
                      accentColor === key 
                        ? 'ring-2 ring-offset-2 ring-laro scale-110' 
                        : 'hover:scale-105'
                    }`}
                    style={{ backgroundColor: color.primary }}
                  />
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                {t('accentColorHint')}
              </p>
            </div>

            {/* Reduced Motion */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-muted-foreground" />
                <div>
                  <p className="font-medium">{t('reduceMotion')}</p>
                  <p className="text-sm text-muted-foreground">{t('minimizeAnimations')}</p>
                </div>
              </div>
              <Switch
                checked={reducedMotion}
                onCheckedChange={setReducedMotion}
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{t('compactView')}</p>
                <p className="text-sm text-muted-foreground">{t('compactViewDesc')}</p>
              </div>
              <Switch
                checked={preferences.compactView}
                onCheckedChange={(checked) => updatePreference('compactView', checked)}
              />
            </div>
          </div>
        </motion.section>

        {/* Neurodiversity & Accessibility */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.065 }}
          className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle dark:bg-muted">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Heart className="w-5 h-5 text-laro" />
              {t('neurodiversityAccessibility')}
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              {t('neurodiversityHint')}
            </p>
          </div>
          <div className="p-4 space-y-4">
            {/* Quick Presets */}
            <div>
              <Label className="mb-3 block flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                {t('quickPresets')}
              </Label>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(ACCESSIBILITY_PRESETS).map(([key, preset]) => {
                  const labelKeys = PRESET_LABEL_KEYS[key];
                  const presetName = labelKeys ? t(labelKeys.name) : preset.name;
                  const presetDesc = labelKeys ? t(labelKeys.desc) : preset.description;
                  return (
                    <button
                      key={key}
                      onClick={() => {
                        accessibility.applyPreset(key);
                        toast.success(t('toastAppliedPreset', { name: presetName }));
                      }}
                      className="text-left p-3 rounded-xl border-2 border-border/60 hover:border-laro/50 transition-all"
                    >
                      <p className="font-medium text-sm">{presetName}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">{presetDesc}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Reading Support */}
            <div className="pt-2 border-t">
              <Label className="mb-3 block flex items-center gap-2">
                <Type className="w-4 h-4" />
                {t('readingSupportDyslexia')}
              </Label>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{t('dyslexiaFriendlyFont')}</p>
                    <p className="text-sm text-muted-foreground">{t('dyslexiaFontDesc')}</p>
                  </div>
                  <Switch
                    checked={accessibility.dyslexicFont}
                    onCheckedChange={accessibility.setDyslexicFont}
                  />
                </div>

                <div>
                  <Label className="mb-2 block">{t('textSpacing')}</Label>
                  <div className="flex gap-2">
                    {[
                      { id: 'normal', label: t('normal') },
                      { id: 'comfortable', label: t('comfortable') },
                      { id: 'spacious', label: t('spacious') },
                    ].map(({ id, label }) => (
                      <button
                        key={id}
                        onClick={() => accessibility.setTextSpacing(id)}
                        className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium border-2 transition-all ${
                          accessibility.textSpacing === id
                            ? 'border-laro bg-laro/10 text-laro'
                            : 'border-border/60 hover:border-laro/50'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <Label className="mb-2 block">{t('lineHeight')}</Label>
                  <div className="flex gap-2">
                    {[
                      { id: 'normal', label: t('normal') },
                      { id: 'relaxed', label: t('relaxed') },
                      { id: 'loose', label: t('loose') },
                    ].map(({ id, label }) => (
                      <button
                        key={id}
                        onClick={() => accessibility.setLineHeight(id)}
                        className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium border-2 transition-all ${
                          accessibility.lineHeight === id
                            ? 'border-laro bg-laro/10 text-laro'
                            : 'border-border/60 hover:border-laro/50'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{t('readingRuler')}</p>
                    <p className="text-sm text-muted-foreground">{t('readingRulerDesc')}</p>
                  </div>
                  <Switch
                    checked={accessibility.readingRuler}
                    onCheckedChange={accessibility.setReadingRuler}
                  />
                </div>
              </div>
            </div>

            {/* Focus & Attention (ADHD) */}
            <div className="pt-2 border-t">
              <Label className="mb-3 block flex items-center gap-2">
                <Focus className="w-4 h-4" />
                {t('focusAttentionAdhd')}
              </Label>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{t('focusMode')}</p>
                    <p className="text-sm text-muted-foreground">{t('focusModeDesc')}</p>
                  </div>
                  <Switch
                    checked={accessibility.focusMode}
                    onCheckedChange={accessibility.setFocusMode}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{t('simplifiedMode')}</p>
                    <p className="text-sm text-muted-foreground">{t('simplifiedModeDesc')}</p>
                  </div>
                  <Switch
                    checked={accessibility.simplifiedMode}
                    onCheckedChange={accessibility.setSimplifiedMode}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{t('progressIndicators')}</p>
                    <p className="text-sm text-muted-foreground">{t('progressIndicatorsDesc')}</p>
                  </div>
                  <Switch
                    checked={accessibility.showProgressIndicators}
                    onCheckedChange={accessibility.setShowProgressIndicators}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{t('highlightCurrentStep')}</p>
                    <p className="text-sm text-muted-foreground">{t('highlightCurrentStepDesc')}</p>
                  </div>
                  <Switch
                    checked={accessibility.highlightCurrentStep}
                    onCheckedChange={accessibility.setHighlightCurrentStep}
                  />
                </div>
              </div>
            </div>

            {/* Visual & Clarity */}
            <div className="pt-2 border-t">
              <Label className="mb-3 block flex items-center gap-2">
                <Eye className="w-4 h-4" />
                {t('visualClarity')}
              </Label>
              <div className="space-y-3">
                <div>
                  <Label className="mb-2 block">{t('contrastLevel')}</Label>
                  <div className="flex gap-2">
                    {[
                      { id: 'normal', label: t('normal') },
                      { id: 'high', label: t('high') },
                      { id: 'maximum', label: t('maximum') },
                    ].map(({ id, label }) => (
                      <button
                        key={id}
                        onClick={() => accessibility.setContrastLevel(id)}
                        className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium border-2 transition-all ${
                          accessibility.contrastLevel === id
                            ? 'border-laro bg-laro/10 text-laro'
                            : 'border-border/60 hover:border-laro/50'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <Label className="mb-2 block">{t('animationLevel')}</Label>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { id: 'none', label: t('none') },
                      { id: 'reduced', label: t('reduced') },
                      { id: 'normal', label: t('normal') },
                      { id: 'enhanced', label: t('enhanced') },
                    ].map(({ id, label }) => (
                      <button
                        key={id}
                        onClick={() => accessibility.setAnimationLevel(id)}
                        className={`px-3 py-2 rounded-lg text-sm font-medium border-2 transition-all ${
                          accessibility.animationLevel === id
                            ? 'border-laro bg-laro/10 text-laro'
                            : 'border-border/60 hover:border-laro/50'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{t('showIconLabels')}</p>
                    <p className="text-sm text-muted-foreground">{t('showIconLabelsDesc')}</p>
                  </div>
                  <Switch
                    checked={accessibility.iconLabels}
                    onCheckedChange={accessibility.setIconLabels}
                  />
                </div>
              </div>
            </div>

            {/* Interaction & Confirmations */}
            <div className="pt-2 border-t">
              <Label className="mb-3 block flex items-center gap-2">
                <Target className="w-4 h-4" />
                {t('interactionAutismSupport')}
              </Label>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{t('confirmImportantActions')}</p>
                    <p className="text-sm text-muted-foreground">{t('confirmImportantActionsDesc')}</p>
                  </div>
                  <Switch
                    checked={accessibility.confirmActions}
                    onCheckedChange={accessibility.setConfirmActions}
                  />
                </div>
              </div>
            </div>

            {/* Sensory Preferences */}
            <div className="pt-2 border-t">
              <Label className="mb-3 block flex items-center gap-2">
                <Volume2 className="w-4 h-4" />
                {t('sensoryPreferences')}
              </Label>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{t('soundEffects')}</p>
                    <p className="text-sm text-muted-foreground">{t('soundEffectsDesc')}</p>
                  </div>
                  <Switch
                    checked={accessibility.soundEffects}
                    onCheckedChange={accessibility.setSoundEffects}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{t('hapticFeedback')}</p>
                    <p className="text-sm text-muted-foreground">{t('hapticFeedbackDesc')}</p>
                  </div>
                  <Switch
                    checked={accessibility.hapticFeedback}
                    onCheckedChange={accessibility.setHapticFeedback}
                  />
                </div>

                <div>
                  <Label className="mb-2 block">{t('timerNotifications')}</Label>
                  <Select
                    value={accessibility.timerNotifications}
                    onValueChange={accessibility.setTimerNotifications}
                  >
                    <SelectTrigger className="rounded-xl">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="visual">{t('visualOnly')}</SelectItem>
                      <SelectItem value="audio">{t('audioOnly')}</SelectItem>
                      <SelectItem value="both">{t('bothVisualAudio')}</SelectItem>
                      <SelectItem value="none">{t('none')}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            {/* Reset Button */}
            <div className="pt-3 border-t">
              <Button
                variant="outline"
                onClick={() => {
                  accessibility.resetAccessibilitySettings();
                  toast.success(t('toastResetAccessibility'));
                }}
                className="w-full rounded-xl"
              >
                {t('resetAccessibilitySettings')}
              </Button>
            </div>
          </div>
        </motion.section>

        {/* Language */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.07 }}
          className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle dark:bg-muted">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Globe className="w-5 h-5 text-laro" />
              {t('language')}
            </h2>
          </div>
          <div className="p-4 space-y-4">
            <div>
              <Label className="mb-2 block">{t('country')}</Label>
              <Select
                value={preferences.country || 'GB'}
                onValueChange={(value) => {
                  const defaults = defaultsForCountry(value);
                  setPreferences(prev => ({
                    ...prev,
                    country: value,
                    language: defaults.language,
                    measurementUnit: prev.measurementUnit === 'both' ? prev.measurementUnit : defaults.measurementUnit,
                  }));
                  setLanguage(defaults.language);
                  setHasChanges(true);
                }}
              >
                <SelectTrigger className="rounded-xl">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="max-h-64">
                  {Object.entries(COUNTRIES).map(([code, { name, flag }]) => (
                    <SelectItem key={code} value={code}>
                      {flag} {name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-2 block">{t('appLanguage')}</Label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {Object.entries(LANGUAGES).map(([code, { name, flag }]) => (
                  <button
                    key={code}
                    type="button"
                    onClick={() => {
                      setLanguage(code);
                      updatePreference('language', code);
                    }}
                    className={`flex items-center gap-2 p-2.5 rounded-xl border-2 transition-all text-left ${
                      language === code
                        ? 'border-laro bg-laro/10'
                        : 'border-border/60 hover:border-laro/50'
                    }`}
                  >
                    <span className="text-lg" aria-hidden="true">{flag}</span>
                    <span className={`text-xs font-medium ${language === code ? 'text-laro' : ''}`}>
                      {name}
                    </span>
                  </button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                {t('fullUiTranslationsNote')}
              </p>
            </div>
          </div>
        </motion.section>

        {/* Cooking Preferences */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle dark:bg-muted">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Utensils className="w-5 h-5 text-laro" />
              {t('cookingPreferences')}
            </h2>
          </div>
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>{t('defaultServings')}</Label>
                <Input
                  type="number"
                  min={1}
                  max={20}
                  value={preferences.defaultServings}
                  onChange={(e) => updatePreference('defaultServings', parseInt(e.target.value) || 4)}
                  className="mt-1 rounded-xl"
                />
              </div>
              <div>
                <Label>{t('measurementUnits')}</Label>
                <Select
                  value={preferences.measurementUnit}
                  onValueChange={(value) => updatePreference('measurementUnit', value)}
                >
                  <SelectTrigger className="mt-1 rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="metric">{t('metricUnits')}</SelectItem>
                    <SelectItem value="imperial">{t('imperialUnits')}</SelectItem>
                    <SelectItem value="both">{t('showBoth')}</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground mt-1">
                  {t('unitsAppliedHint')}
                </p>
              </div>
            </div>

            <div>
              <Label className="mb-2 block">{t('dietaryRestrictions')}</Label>
              <div className="flex flex-wrap gap-2">
                {DIETARY_OPTIONS.map(option => (
                  <button
                    key={option.id}
                    onClick={() => toggleDietaryRestriction(option.id)}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                      preferences.dietaryRestrictions?.includes(option.id)
                        ? 'bg-laro text-white'
                        : 'bg-cream-subtle dark:bg-muted hover:bg-laro/20'
                    }`}
                  >
                    {preferences.dietaryRestrictions?.includes(option.id) && (
                      <Check className="w-3 h-3 inline mr-1" />
                    )}
                    {t(option.key)}
                  </button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                {t('dietaryUsedForAi')}
              </p>
            </div>

            <div data-testid="pref-adult-veto">
              <Label className="mb-2 block">{t('adultVetoList')}</Label>
              <p className="text-xs text-muted-foreground mb-2">{t('adultVetoHint')}</p>
              <div className="flex flex-wrap gap-2">
                {[...new Set([...ADULT_VETO_OPTIONS, ...(preferences.dislikedIngredients || [])])].map((item) => (
                  <button
                    key={item}
                    type="button"
                    onClick={() => toggleListPref('dislikedIngredients', item)}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium capitalize transition-all ${
                      preferences.dislikedIngredients?.includes(item)
                        ? 'bg-amber-600 text-white'
                        : 'bg-cream-subtle dark:bg-muted hover:bg-amber-600/20'
                    }`}
                  >
                    {preferences.dislikedIngredients?.includes(item) && (
                      <Check className="w-3 h-3 inline mr-1" />
                    )}
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
                  data-testid="pref-adult-veto-input"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addCustomListPref('dislikedIngredients', customAdultVeto, setCustomAdultVeto);
                    }
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-xl shrink-0"
                  onClick={() =>
                    addCustomListPref('dislikedIngredients', customAdultVeto, setCustomAdultVeto)
                  }
                >
                  {t('add')}
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="daily-protein-target">{t('dailyProteinTarget')}</Label>
                <Input
                  id="daily-protein-target"
                  data-testid="daily-protein-target"
                  type="number"
                  min={0}
                  max={500}
                  step={1}
                  className="mt-1 rounded-xl"
                  placeholder={
                    preferences.dietaryRestrictions?.includes('high-protein') ? '140' : '100'
                  }
                  value={preferences.dailyProteinTarget ?? ''}
                  onChange={(e) =>
                    updatePreference(
                      'dailyProteinTarget',
                      e.target.value === '' ? '' : e.target.value
                    )
                  }
                />
                <p className="text-xs text-muted-foreground mt-1">{t('dailyProteinTargetHint')}</p>
              </div>
              <div>
                <Label htmlFor="daily-calorie-target">{t('dailyCalorieTarget')}</Label>
                <Input
                  id="daily-calorie-target"
                  data-testid="daily-calorie-target"
                  type="number"
                  min={0}
                  max={10000}
                  step={10}
                  className="mt-1 rounded-xl"
                  placeholder={
                    preferences.dietaryRestrictions?.includes('high-protein') ? '2200' : '2000'
                  }
                  value={preferences.dailyCalorieTarget ?? ''}
                  onChange={(e) =>
                    updatePreference(
                      'dailyCalorieTarget',
                      e.target.value === '' ? '' : e.target.value
                    )
                  }
                />
                <p className="text-xs text-muted-foreground mt-1">{t('dailyCalorieTargetHint')}</p>
              </div>
              <div>
                <Label htmlFor="daily-carb-target">{t('dailyCarbTarget')}</Label>
                <Input
                  id="daily-carb-target"
                  data-testid="daily-carb-target"
                  type="number"
                  min={0}
                  max={1000}
                  step={1}
                  className="mt-1 rounded-xl"
                  placeholder="250"
                  value={preferences.dailyCarbTarget ?? ''}
                  onChange={(e) =>
                    updatePreference(
                      'dailyCarbTarget',
                      e.target.value === '' ? '' : e.target.value
                    )
                  }
                />
                <p className="text-xs text-muted-foreground mt-1">{t('dailyCarbTargetHint')}</p>
              </div>
              <div>
                <Label htmlFor="daily-fat-target">{t('dailyFatTarget')}</Label>
                <Input
                  id="daily-fat-target"
                  data-testid="daily-fat-target"
                  type="number"
                  min={0}
                  max={500}
                  step={1}
                  className="mt-1 rounded-xl"
                  placeholder="70"
                  value={preferences.dailyFatTarget ?? ''}
                  onChange={(e) =>
                    updatePreference(
                      'dailyFatTarget',
                      e.target.value === '' ? '' : e.target.value
                    )
                  }
                />
                <p className="text-xs text-muted-foreground mt-1">{t('dailyFatTargetHint')}</p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground -mt-2">{t('nutritionGoalsDisclaimer')}</p>

            <div className="pt-2 border-t border-border/40 space-y-4" data-testid="lifestyle-prefs">
              <h3 className="font-medium flex items-center gap-2">
                <Home className="w-4 h-4 text-laro" />
                {t('lifestylePreferences')}
              </h3>

              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium flex items-center gap-2">
                    <Users className="w-4 h-4 text-muted-foreground" />
                    {t('hasChildren')}
                  </p>
                  <p className="text-sm text-muted-foreground">{t('hasChildrenHint')}</p>
                </div>
                <Switch
                  checked={!!preferences.hasChildren}
                  onCheckedChange={(checked) => {
                    updatePreference('hasChildren', checked);
                    if (checked && preferences.kidFriendlyMeals == null) {
                      updatePreference('kidFriendlyMeals', true);
                    }
                    if (checked && preferences.familyOneMeal == null) {
                      updatePreference('familyOneMeal', true);
                    }
                  }}
                  data-testid="pref-has-children"
                />
              </div>

              {preferences.hasChildren && (
                <div className="flex items-center justify-between gap-3 pl-1">
                  <div className="min-w-0">
                    <p className="font-medium">{t('kidFriendlyMeals')}</p>
                    <p className="text-sm text-muted-foreground">{t('kidFriendlyMealsHint')}</p>
                  </div>
                  <Switch
                    checked={preferences.kidFriendlyMeals !== false}
                    onCheckedChange={(checked) => updatePreference('kidFriendlyMeals', checked)}
                    data-testid="pref-kid-friendly"
                  />
                </div>
              )}

              {preferences.hasChildren && (
                <div className="flex items-center justify-between gap-3 pl-1">
                  <div className="min-w-0">
                    <p className="font-medium">{t('familyOneMeal')}</p>
                    <p className="text-sm text-muted-foreground">{t('familyOneMealHint')}</p>
                  </div>
                  <Switch
                    checked={preferences.familyOneMeal !== false}
                    onCheckedChange={(checked) => updatePreference('familyOneMeal', checked)}
                    data-testid="pref-family-one-meal"
                  />
                </div>
              )}

              {preferences.hasChildren && (
                <div className="pl-1" data-testid="pref-kid-veto">
                  <Label className="mb-2 block">{t('kidVetoList')}</Label>
                  <p className="text-xs text-muted-foreground mb-2">{t('kidVetoHint')}</p>
                  <div className="flex flex-wrap gap-2">
                    {[...new Set([...KID_VETO_OPTIONS, ...(preferences.kidVetoIngredients || [])])].map((item) => (
                      <button
                        key={item}
                        type="button"
                        onClick={() => toggleListPref('kidVetoIngredients', item)}
                        className={`px-3 py-1.5 rounded-full text-sm font-medium capitalize transition-all ${
                          preferences.kidVetoIngredients?.includes(item)
                            ? 'bg-sky-600 text-white'
                            : 'bg-cream-subtle dark:bg-muted hover:bg-sky-600/20'
                        }`}
                      >
                        {preferences.kidVetoIngredients?.includes(item) && (
                          <Check className="w-3 h-3 inline mr-1" />
                        )}
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
                      data-testid="pref-kid-veto-input"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          addCustomListPref('kidVetoIngredients', customKidVeto, setCustomKidVeto);
                        }
                      }}
                    />
                    <Button
                      type="button"
                      variant="outline"
                      className="rounded-xl shrink-0"
                      onClick={() =>
                        addCustomListPref('kidVetoIngredients', customKidVeto, setCustomKidVeto)
                      }
                    >
                      {t('add')}
                    </Button>
                  </div>
                </div>
              )}

              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium">{t('worksFromHome')}</p>
                  <p className="text-sm text-muted-foreground">{t('worksFromHomeHint')}</p>
                </div>
                <Switch
                  checked={!!preferences.worksFromHome}
                  onCheckedChange={(checked) => {
                    updatePreference('worksFromHome', checked);
                    if (checked && !(preferences.wfhDays || []).length) {
                      updatePreference('wfhDays', ['mon', 'tue', 'wed', 'thu', 'fri']);
                    }
                  }}
                  data-testid="pref-wfh"
                />
              </div>

              {preferences.worksFromHome && (
                <div>
                  <Label className="mb-2 block">{t('wfhDaysLabel')}</Label>
                  <div className="flex flex-wrap gap-2" data-testid="pref-wfh-days">
                    {WFH_DAY_OPTIONS.map(({ id, key }) => (
                      <button
                        key={id}
                        type="button"
                        onClick={() => toggleWfhDay(id)}
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

              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium">{t('hasGymRoutine')}</p>
                  <p className="text-sm text-muted-foreground">{t('hasGymRoutineHint')}</p>
                </div>
                <Switch
                  checked={!!preferences.hasGymRoutine}
                  onCheckedChange={(checked) => {
                    updatePreference('hasGymRoutine', checked);
                    if (checked && !(preferences.gymDays || []).length) {
                      updatePreference('gymDays', ['mon', 'wed', 'fri']);
                    }
                  }}
                  data-testid="pref-gym"
                />
              </div>

              {preferences.hasGymRoutine && (
                <div>
                  <Label className="mb-2 block">{t('gymDaysLabel')}</Label>
                  <div className="flex flex-wrap gap-2" data-testid="pref-gym-days">
                    {WFH_DAY_OPTIONS.map(({ id, key }) => (
                      <button
                        key={id}
                        type="button"
                        onClick={() => toggleGymDay(id)}
                        className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                          preferences.gymDays?.includes(id)
                            ? 'bg-laro text-white'
                            : 'bg-cream-subtle dark:bg-muted hover:bg-laro/20'
                        }`}
                      >
                        {preferences.gymDays?.includes(id) && (
                          <Check className="w-3 h-3 inline mr-1" />
                        )}
                        {t(key)}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <Label htmlFor="dinner-headcount">{t('dinnerHeadcountPref')}</Label>
                <Input
                  id="dinner-headcount"
                  type="number"
                  min={1}
                  max={20}
                  className="mt-1 rounded-xl max-w-[8rem]"
                  value={preferences.dinnerHeadcount ?? ''}
                  onChange={(e) =>
                    updatePreference(
                      'dinnerHeadcount',
                      e.target.value === '' ? '' : Number(e.target.value)
                    )
                  }
                  data-testid="pref-dinner-headcount"
                />
                <p className="text-xs text-muted-foreground mt-1">{t('dinnerHeadcountPrefHint')}</p>
              </div>
            </div>

            <div>
              <Label className="mb-2 block" htmlFor="preferred-recipe-sites">
                {t('preferredRecipeSites')}
              </Label>
              <textarea
                id="preferred-recipe-sites"
                data-testid="preferred-recipe-sites"
                className="w-full min-h-[88px] rounded-xl border border-border bg-background px-3 py-2 text-sm"
                placeholder={t('preferredRecipeSitesPlaceholder')}
                value={(preferences.preferredRecipeSites || []).join('\n')}
                onChange={(e) => {
                  const sites = e.target.value
                    .split(/[\n,]+/)
                    .map((s) => s.trim())
                    .filter(Boolean);
                  updatePreference('preferredRecipeSites', sites);
                }}
              />
              <p className="text-xs text-muted-foreground mt-2">
                {t('preferredRecipeSitesHint')}
              </p>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{t('showNutritionInfo')}</p>
                <p className="text-sm text-muted-foreground">{t('showNutritionDesc')}</p>
              </div>
              <Switch
                checked={preferences.showNutrition}
                onCheckedChange={(checked) => updatePreference('showNutrition', checked)}
              />
            </div>
          </div>
        </motion.section>

        {/* Meal Planning */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle dark:bg-muted">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Clock className="w-5 h-5 text-laro" />
              {t('mealPlanning')}
            </h2>
          </div>
          <div className="p-4 space-y-4">
            <div>
              <Label>{t('weekStartsOn')}</Label>
              <Select
                value={preferences.weekStartsOn}
                onValueChange={(value) => updatePreference('weekStartsOn', value)}
              >
                <SelectTrigger className="mt-1 rounded-xl w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sunday">{t('sunday')}</SelectItem>
                  <SelectItem value="monday">{t('monday')}</SelectItem>
                  <SelectItem value="saturday">{t('saturday')}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label>{t('defaultCookingTime')}</Label>
              <Input
                type="number"
                min={5}
                max={240}
                step={5}
                value={preferences.defaultCookingTime}
                onChange={(e) => updatePreference('defaultCookingTime', parseInt(e.target.value) || 30)}
                className="mt-1 rounded-xl w-32"
              />
            </div>

            <div className="pt-2 border-t border-border/50 space-y-3" data-testid="pref-calendar-section">
              <div>
                <p className="font-medium">{t('calendarForMeals')}</p>
                <p className="text-sm text-muted-foreground">{t('calendarForMealsHint')}</p>
              </div>

              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-medium text-sm">{t('useCalendarForMealDifficulty')}</p>
                  <p className="text-xs text-muted-foreground">{t('useCalendarForMealDifficultyHint')}</p>
                </div>
                <Switch
                  checked={!!preferences.useCalendarForMealDifficulty}
                  onCheckedChange={(checked) =>
                    updatePreference('useCalendarForMealDifficulty', checked)
                  }
                  data-testid="pref-calendar-meal-difficulty"
                />
              </div>

              <div>
                <Label htmlFor="calendar-ics-url">{t('calendarIcsUrl')}</Label>
                <Input
                  id="calendar-ics-url"
                  type="url"
                  data-testid="pref-calendar-ics-url"
                  className="mt-1 rounded-xl"
                  placeholder={t('calendarIcsUrlPlaceholder')}
                  value={preferences.calendarIcsUrl || ''}
                  onChange={(e) => updatePreference('calendarIcsUrl', e.target.value)}
                  autoComplete="off"
                />
                <p className="text-xs text-muted-foreground mt-2">{t('calendarPrivacyNote')}</p>
                <div className="flex flex-wrap items-center gap-2 mt-2">
                  <Button
                    type="button"
                    variant="outline"
                    className="rounded-xl"
                    disabled={validatingIcs || !(preferences.calendarIcsUrl || '').trim()}
                    onClick={handleValidateIcs}
                    data-testid="pref-calendar-ics-validate"
                  >
                    {validatingIcs ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : null}
                    {t('calendarIcsTest')}
                  </Button>
                  {icsValidateMsg ? (
                    <span className="text-xs text-muted-foreground">{icsValidateMsg}</span>
                  ) : null}
                </div>
              </div>
            </div>
          </div>
        </motion.section>

        {/* Notifications */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden"
        >
          <div className="p-4 border-b border-border/60 bg-cream-subtle dark:bg-muted">
            <h2 className="font-heading font-semibold flex items-center gap-2">
              <Bell className="w-5 h-5 text-laro" />
              {t('notificationsAndLists')}
            </h2>
          </div>
          <div className="p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{t('mealPlanReminders')}</p>
                <p className="text-sm text-muted-foreground">
                  {t('mealRemindersHint')}
                </p>
              </div>
              <Switch
                checked={preferences.mealPlanNotifications}
                onCheckedChange={(checked) => updatePreference('mealPlanNotifications', checked)}
                data-testid="pref-meal-plan-notifications"
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{t('autoSortShoppingLists')}</p>
                <p className="text-sm text-muted-foreground">{t('autoSortShoppingDesc')}</p>
              </div>
              <Switch
                checked={preferences.shoppingListAutoSort}
                onCheckedChange={(checked) => updatePreference('shoppingListAutoSort', checked)}
              />
            </div>
          </div>
        </motion.section>

        {/* Save Button (Mobile) */}
        {hasChanges && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="md:hidden"
          >
            <Button
              onClick={handleSave}
              disabled={saving}
              className="w-full rounded-full bg-laro hover:bg-laro-dark"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
              {t('saveChanges')}
            </Button>
          </motion.div>
        )}
      </div>
    </Layout>
  );
};
