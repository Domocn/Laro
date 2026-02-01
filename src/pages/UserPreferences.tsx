import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { useAuth } from '../context/AuthContext';
import { useTheme, ACCENT_COLORS } from '../context/ThemeContext';
import { useLanguage, LANGUAGES } from '../context/LanguageContext';
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
  AlignLeft
} from 'lucide-react';
import { toast } from 'sonner';
import api from '../lib/api';

const DEFAULT_PREFERENCES = {
  theme: 'system',
  defaultServings: 4,
  measurementUnit: 'metric',
  dietaryRestrictions: [],
  showNutrition: true,
  compactView: false,
  weekStartsOn: 'monday',
  mealPlanNotifications: true,
  shoppingListAutoSort: true,
  defaultCookingTime: 30,
};

const DIETARY_OPTIONS = [
  { id: 'vegetarian', label: 'Vegetarian' },
  { id: 'vegan', label: 'Vegan' },
  { id: 'gluten-free', label: 'Gluten-Free' },
  { id: 'dairy-free', label: 'Dairy-Free' },
  { id: 'nut-free', label: 'Nut-Free' },
  { id: 'keto', label: 'Keto' },
  { id: 'paleo', label: 'Paleo' },
  { id: 'halal', label: 'Halal' },
  { id: 'kosher', label: 'Kosher' },
];

export const UserPreferences = () => {
  const { user } = useAuth();
  const { theme, setTheme, accentColor, setAccentColor, accentColors, reducedMotion, setReducedMotion } = useTheme();
  const { language, setLanguage, t, languages } = useLanguage();
  const accessibility = useAccessibility();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [preferences, setPreferences] = useState(DEFAULT_PREFERENCES);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    loadPreferences();
  }, []);

  const loadPreferences = async () => {
    setLoading(true);
    try {
      const res = await api.get('/preferences');
      if (res.data) {
        setPreferences({ ...DEFAULT_PREFERENCES, ...res.data });
      }
    } catch (error) {
      // Use defaults if no preferences saved
      console.log('Using default preferences');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/preferences', preferences);
      toast.success('Preferences saved!');
      setHasChanges(false);
    } catch (error) {
      toast.error('Failed to save preferences');
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

  if (loading) {
    return (
      <Layout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-mise" />
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
              <Settings className="w-8 h-8 text-mise" />
              Preferences
            </h1>
            <p className="text-muted-foreground mt-1">Customize your Laro experience</p>
          </div>
          {hasChanges && (
            <Button
              onClick={handleSave}
              disabled={saving}
              className="rounded-full bg-mise hover:bg-mise-dark"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
              Save Changes
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
              <Sun className="w-5 h-5 text-mise" />
              Appearance
            </h2>
          </div>
          <div className="p-4 space-y-4">
            <div>
              <Label className="mb-3 block">Theme</Label>
              <div className="flex gap-3">
                {[
                  { id: 'light', icon: Sun, label: 'Light' },
                  { id: 'dark', icon: Moon, label: 'Dark' },
                  { id: 'system', icon: Monitor, label: 'System' },
                ].map(({ id, icon: Icon, label }) => (
                  <button
                    key={id}
                    onClick={() => handleThemeChange(id)}
                    className={`flex-1 flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all ${
                      preferences.theme === id
                        ? 'border-mise bg-mise/10'
                        : 'border-border/60 hover:border-mise/50'
                    }`}
                  >
                    <Icon className={`w-6 h-6 ${preferences.theme === id ? 'text-mise' : 'text-muted-foreground'}`} />
                    <span className={`text-sm font-medium ${preferences.theme === id ? 'text-mise' : ''}`}>{label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Accent Color */}
            <div>
              <Label className="mb-3 block flex items-center gap-2">
                <Palette className="w-4 h-4" />
                Accent Color
              </Label>
              <div className="flex gap-2 flex-wrap">
                {Object.entries(accentColors).map(([key, color]) => (
                  <button
                    key={key}
                    onClick={() => setAccentColor(key)}
                    title={color.name}
                    className={`w-10 h-10 rounded-xl transition-all ${
                      accentColor === key 
                        ? 'ring-2 ring-offset-2 ring-mise scale-110' 
                        : 'hover:scale-105'
                    }`}
                    style={{ backgroundColor: color.primary }}
                  />
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Changes buttons, links, and accent elements
              </p>
            </div>

            {/* Reduced Motion */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-muted-foreground" />
                <div>
                  <p className="font-medium">Reduce Motion</p>
                  <p className="text-sm text-muted-foreground">Minimize animations</p>
                </div>
              </div>
              <Switch
                checked={reducedMotion}
                onCheckedChange={setReducedMotion}
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Compact View</p>
                <p className="text-sm text-muted-foreground">Show more recipes in less space</p>
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
              <Heart className="w-5 h-5 text-mise" />
              Neurodiversity & Accessibility
            </h2>
            <p className="text-xs text-muted-foreground mt-1">
              Features to support ADHD, dyslexia, autism, and sensory sensitivities
            </p>
          </div>
          <div className="p-4 space-y-4">
            {/* Quick Presets */}
            <div>
              <Label className="mb-3 block flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                Quick Presets
              </Label>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(ACCESSIBILITY_PRESETS).map(([key, preset]) => (
                  <button
                    key={key}
                    onClick={() => {
                      accessibility.applyPreset(key);
                      toast.success(`Applied ${preset.name} settings`);
                    }}
                    className="text-left p-3 rounded-xl border-2 border-border/60 hover:border-mise/50 transition-all"
                  >
                    <p className="font-medium text-sm">{preset.name}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">{preset.description}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Reading Support */}
            <div className="pt-2 border-t">
              <Label className="mb-3 block flex items-center gap-2">
                <Type className="w-4 h-4" />
                Reading Support (Dyslexia)
              </Label>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Dyslexia-Friendly Font</p>
                    <p className="text-sm text-muted-foreground">Use Comic Sans MS for better readability</p>
                  </div>
                  <Switch
                    checked={accessibility.dyslexicFont}
                    onCheckedChange={accessibility.setDyslexicFont}
                  />
                </div>

                <div>
                  <Label className="mb-2 block">Text Spacing</Label>
                  <div className="flex gap-2">
                    {[
                      { id: 'normal', label: 'Normal' },
                      { id: 'comfortable', label: 'Comfortable' },
                      { id: 'spacious', label: 'Spacious' },
                    ].map(({ id, label }) => (
                      <button
                        key={id}
                        onClick={() => accessibility.setTextSpacing(id)}
                        className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium border-2 transition-all ${
                          accessibility.textSpacing === id
                            ? 'border-mise bg-mise/10 text-mise'
                            : 'border-border/60 hover:border-mise/50'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <Label className="mb-2 block">Line Height</Label>
                  <div className="flex gap-2">
                    {[
                      { id: 'normal', label: 'Normal' },
                      { id: 'relaxed', label: 'Relaxed' },
                      { id: 'loose', label: 'Loose' },
                    ].map(({ id, label }) => (
                      <button
                        key={id}
                        onClick={() => accessibility.setLineHeight(id)}
                        className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium border-2 transition-all ${
                          accessibility.lineHeight === id
                            ? 'border-mise bg-mise/10 text-mise'
                            : 'border-border/60 hover:border-mise/50'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Reading Ruler</p>
                    <p className="text-sm text-muted-foreground">Highlight the line you're reading</p>
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
                Focus & Attention (ADHD)
              </Label>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Focus Mode</p>
                    <p className="text-sm text-muted-foreground">Reduce distractions and visual clutter</p>
                  </div>
                  <Switch
                    checked={accessibility.focusMode}
                    onCheckedChange={accessibility.setFocusMode}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Simplified Mode</p>
                    <p className="text-sm text-muted-foreground">Cleaner interface with fewer decorations</p>
                  </div>
                  <Switch
                    checked={accessibility.simplifiedMode}
                    onCheckedChange={accessibility.setSimplifiedMode}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Progress Indicators</p>
                    <p className="text-sm text-muted-foreground">Show clear progress through tasks</p>
                  </div>
                  <Switch
                    checked={accessibility.showProgressIndicators}
                    onCheckedChange={accessibility.setShowProgressIndicators}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Highlight Current Step</p>
                    <p className="text-sm text-muted-foreground">Emphasize the active cooking step</p>
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
                Visual Clarity
              </Label>
              <div className="space-y-3">
                <div>
                  <Label className="mb-2 block">Contrast Level</Label>
                  <div className="flex gap-2">
                    {[
                      { id: 'normal', label: 'Normal' },
                      { id: 'high', label: 'High' },
                      { id: 'maximum', label: 'Maximum' },
                    ].map(({ id, label }) => (
                      <button
                        key={id}
                        onClick={() => accessibility.setContrastLevel(id)}
                        className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium border-2 transition-all ${
                          accessibility.contrastLevel === id
                            ? 'border-mise bg-mise/10 text-mise'
                            : 'border-border/60 hover:border-mise/50'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <Label className="mb-2 block">Animation Level</Label>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { id: 'none', label: 'None' },
                      { id: 'reduced', label: 'Reduced' },
                      { id: 'normal', label: 'Normal' },
                      { id: 'enhanced', label: 'Enhanced' },
                    ].map(({ id, label }) => (
                      <button
                        key={id}
                        onClick={() => accessibility.setAnimationLevel(id)}
                        className={`px-3 py-2 rounded-lg text-sm font-medium border-2 transition-all ${
                          accessibility.animationLevel === id
                            ? 'border-mise bg-mise/10 text-mise'
                            : 'border-border/60 hover:border-mise/50'
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Show Icon Labels</p>
                    <p className="text-sm text-muted-foreground">Display text alongside icons</p>
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
                Interaction (Autism Support)
              </Label>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Confirm Important Actions</p>
                    <p className="text-sm text-muted-foreground">Ask before deleting or significant changes</p>
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
                Sensory Preferences
              </Label>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Sound Effects</p>
                    <p className="text-sm text-muted-foreground">Play audio feedback</p>
                  </div>
                  <Switch
                    checked={accessibility.soundEffects}
                    onCheckedChange={accessibility.setSoundEffects}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Haptic Feedback</p>
                    <p className="text-sm text-muted-foreground">Vibration on touch devices</p>
                  </div>
                  <Switch
                    checked={accessibility.hapticFeedback}
                    onCheckedChange={accessibility.setHapticFeedback}
                  />
                </div>

                <div>
                  <Label className="mb-2 block">Timer Notifications</Label>
                  <Select
                    value={accessibility.timerNotifications}
                    onValueChange={accessibility.setTimerNotifications}
                  >
                    <SelectTrigger className="rounded-xl">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="visual">Visual Only</SelectItem>
                      <SelectItem value="audio">Audio Only</SelectItem>
                      <SelectItem value="both">Both Visual & Audio</SelectItem>
                      <SelectItem value="none">None</SelectItem>
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
                  toast.success('Reset to default accessibility settings');
                }}
                className="w-full rounded-xl"
              >
                Reset Accessibility Settings
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
              <Globe className="w-5 h-5 text-mise" />
              Language
            </h2>
          </div>
          <div className="p-4">
            <Label className="mb-3 block">App Language</Label>
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
              {Object.entries(languages).map(([code, { name, flag }]) => (
                <button
                  key={code}
                  onClick={() => setLanguage(code)}
                  className={`flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all ${
                    language === code
                      ? 'border-mise bg-mise/10'
                      : 'border-border/60 hover:border-mise/50'
                  }`}
                >
                  <span className="text-2xl">{flag}</span>
                  <span className={`text-xs font-medium ${language === code ? 'text-mise' : 'text-muted-foreground'}`}>
                    {name}
                  </span>
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              Changes some UI text. Recipe content remains in its original language.
            </p>
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
              <Utensils className="w-5 h-5 text-mise" />
              Cooking Preferences
            </h2>
          </div>
          <div className="p-4 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Default Servings</Label>
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
                <Label>Measurement Units</Label>
                <Select
                  value={preferences.measurementUnit}
                  onValueChange={(value) => updatePreference('measurementUnit', value)}
                >
                  <SelectTrigger className="mt-1 rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="metric">Metric (g, ml)</SelectItem>
                    <SelectItem value="imperial">Imperial (oz, cups)</SelectItem>
                    <SelectItem value="both">Show Both</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div>
              <Label className="mb-2 block">Dietary Restrictions</Label>
              <div className="flex flex-wrap gap-2">
                {DIETARY_OPTIONS.map(option => (
                  <button
                    key={option.id}
                    onClick={() => toggleDietaryRestriction(option.id)}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                      preferences.dietaryRestrictions?.includes(option.id)
                        ? 'bg-mise text-white'
                        : 'bg-cream-subtle dark:bg-muted hover:bg-mise/20'
                    }`}
                  >
                    {preferences.dietaryRestrictions?.includes(option.id) && (
                      <Check className="w-3 h-3 inline mr-1" />
                    )}
                    {option.label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                These will be used for AI meal suggestions and recipe filtering
              </p>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Show Nutrition Info</p>
                <p className="text-sm text-muted-foreground">Display nutritional information on recipes</p>
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
              <Clock className="w-5 h-5 text-mise" />
              Meal Planning
            </h2>
          </div>
          <div className="p-4 space-y-4">
            <div>
              <Label>Week Starts On</Label>
              <Select
                value={preferences.weekStartsOn}
                onValueChange={(value) => updatePreference('weekStartsOn', value)}
              >
                <SelectTrigger className="mt-1 rounded-xl w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sunday">Sunday</SelectItem>
                  <SelectItem value="monday">Monday</SelectItem>
                  <SelectItem value="saturday">Saturday</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label>Default Cooking Time (minutes)</Label>
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
              <Bell className="w-5 h-5 text-mise" />
              Notifications & Lists
            </h2>
          </div>
          <div className="p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Meal Plan Reminders</p>
                <p className="text-sm text-muted-foreground">Get notified about upcoming meals</p>
              </div>
              <Switch
                checked={preferences.mealPlanNotifications}
                onCheckedChange={(checked) => updatePreference('mealPlanNotifications', checked)}
              />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Auto-Sort Shopping Lists</p>
                <p className="text-sm text-muted-foreground">Organize items by store section</p>
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
              className="w-full rounded-full bg-mise hover:bg-mise-dark"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
              Save Changes
            </Button>
          </motion.div>
        )}
      </div>
    </Layout>
  );
};
