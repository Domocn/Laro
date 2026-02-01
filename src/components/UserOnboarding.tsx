import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { useAccessibility, ACCESSIBILITY_PRESETS } from '../context/AccessibilityContext';
import { Button } from './ui/button';
import { Label } from './ui/label';
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
  Focus,
  Type,
  Eye,
  Palette,
} from 'lucide-react';
import api from '../lib/api';
import { useLanguage } from '../context/LanguageContext';
import { useTheme } from '../context/ThemeContext';

const ONBOARDING_STEPS = [
  { id: 'welcome', title: 'Welcome', icon: ChefHat },
  { id: 'accessibility', title: 'Accessibility', icon: Heart },
  { id: 'preferences', title: 'Preferences', icon: Settings },
  { id: 'complete', title: 'Ready!', icon: Sparkles },
];

export const UserOnboarding = () => {
  const { user } = useAuth();
  const { language, setLanguage, languages } = useLanguage();
  const { theme, setTheme } = useTheme();
  const accessibility = useAccessibility();

  const [open, setOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedPreset, setSelectedPreset] = useState(null);
  const [preferences, setPreferences] = useState({
    measurementUnit: 'metric',
    dietaryRestrictions: [],
  });

  useEffect(() => {
    // Check if user needs onboarding
    const checkOnboarding = async () => {
      // Check localStorage flag first (instant check)
      const hasSeenOnboarding = localStorage.getItem(`mise_onboarding_${user?.id}`);

      if (!hasSeenOnboarding && user) {
        // Small delay for better UX
        setTimeout(() => setOpen(true), 500);
      }
    };

    if (user) {
      checkOnboarding();
    }
  }, [user]);

  const handleSkip = () => {
    localStorage.setItem(`mise_onboarding_${user?.id}`, 'skipped');
    setOpen(false);
  };

  const handleNext = async () => {
    if (currentStep === ONBOARDING_STEPS.length - 1) {
      // Save all preferences
      try {
        await api.put('/preferences', {
          ...preferences,
          // Accessibility settings are auto-saved by AccessibilityContext
        });
        localStorage.setItem(`mise_onboarding_${user?.id}`, 'completed');
        setOpen(false);
      } catch (error) {
        console.error('Failed to save preferences:', error);
        // Still mark as complete even if save fails
        localStorage.setItem(`mise_onboarding_${user?.id}`, 'completed');
        setOpen(false);
      }
    } else {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const applyAccessibilityPreset = (presetKey) => {
    setSelectedPreset(presetKey);
    accessibility.applyPreset(presetKey);
  };

  const toggleDietaryRestriction = (id) => {
    setPreferences(prev => ({
      ...prev,
      dietaryRestrictions: prev.dietaryRestrictions.includes(id)
        ? prev.dietaryRestrictions.filter(r => r !== id)
        : [...prev.dietaryRestrictions, id],
    }));
  };

  const DIETARY_OPTIONS = [
    { id: 'vegetarian', label: 'Vegetarian', emoji: '🥗' },
    { id: 'vegan', label: 'Vegan', emoji: '🌱' },
    { id: 'gluten-free', label: 'Gluten-Free', emoji: '🌾' },
    { id: 'dairy-free', label: 'Dairy-Free', emoji: '🥛' },
    { id: 'nut-free', label: 'Nut-Free', emoji: '🥜' },
    { id: 'keto', label: 'Keto', emoji: '🥑' },
  ];

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Skip Button */}
        <button
          onClick={handleSkip}
          className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground"
        >
          <X className="h-4 w-4" />
          <span className="sr-only">Skip</span>
        </button>

        {/* Progress Dots */}
        <div className="flex justify-center gap-2 mb-4 pt-2">
          {ONBOARDING_STEPS.map((step, index) => (
            <div
              key={step.id}
              className={`h-2 rounded-full transition-all ${
                index === currentStep
                  ? 'w-8 bg-mise'
                  : index < currentStep
                  ? 'w-2 bg-mise/50'
                  : 'w-2 bg-border'
              }`}
            />
          ))}
        </div>

        <AnimatePresence mode="wait">
          {/* Step 0: Welcome */}
          {currentStep === 0 && (
            <motion.div
              key="welcome"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <DialogHeader>
                <div className="w-16 h-16 bg-mise/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <ChefHat className="w-8 h-8 text-mise" />
                </div>
                <DialogTitle className="text-center text-2xl">
                  Welcome to Laro, {user?.name?.split(' ')[0]}! 👋
                </DialogTitle>
                <DialogDescription className="text-center">
                  Let's personalize your experience in just a few quick steps
                </DialogDescription>
              </DialogHeader>

              <div className="mt-6 space-y-3">
                <div className="flex items-start gap-3 p-3 bg-cream-subtle dark:bg-muted rounded-xl">
                  <Heart className="w-5 h-5 text-mise flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-sm">Accessibility Options</p>
                    <p className="text-xs text-muted-foreground">
                      Support for ADHD, dyslexia, autism, and more
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 bg-cream-subtle dark:bg-muted rounded-xl">
                  <Settings className="w-5 h-5 text-mise flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-sm">Your Preferences</p>
                    <p className="text-xs text-muted-foreground">
                      Theme, language, dietary needs, and units
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 bg-cream-subtle dark:bg-muted rounded-xl">
                  <Sparkles className="w-5 h-5 text-mise flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-sm">Sync Across Devices</p>
                    <p className="text-xs text-muted-foreground">
                      Your settings follow you everywhere
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* Step 1: Accessibility */}
          {currentStep === 1 && (
            <motion.div
              key="accessibility"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <DialogHeader>
                <div className="w-16 h-16 bg-mise/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Heart className="w-8 h-8 text-mise" />
                </div>
                <DialogTitle className="text-center">
                  ♿ Accessibility Settings
                </DialogTitle>
                <DialogDescription className="text-center">
                  Choose a preset that matches your needs, or skip to customize later
                </DialogDescription>
              </DialogHeader>

              <div className="mt-6 space-y-3">
                {Object.entries(ACCESSIBILITY_PRESETS).map(([key, preset]) => (
                  <button
                    key={key}
                    onClick={() => applyAccessibilityPreset(key)}
                    className={`w-full text-left p-4 rounded-xl border-2 transition-all ${
                      selectedPreset === key
                        ? 'border-mise bg-mise/5'
                        : 'border-border/60 hover:border-mise/50'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">{preset.name}</p>
                        <p className="text-sm text-muted-foreground mt-0.5">
                          {preset.description}
                        </p>
                      </div>
                      {selectedPreset === key && (
                        <Check className="w-5 h-5 text-mise flex-shrink-0" />
                      )}
                    </div>
                  </button>
                ))}
              </div>

              <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-xl">
                <p className="text-sm text-blue-800 dark:text-blue-200">
                  💡 <strong>Tip:</strong> You can fine-tune these settings anytime from{' '}
                  <span className="font-medium">Settings → Preferences → Accessibility</span>
                </p>
              </div>
            </motion.div>
          )}

          {/* Step 2: Preferences */}
          {currentStep === 2 && (
            <motion.div
              key="preferences"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <DialogHeader>
                <div className="w-16 h-16 bg-mise/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Settings className="w-8 h-8 text-mise" />
                </div>
                <DialogTitle className="text-center">
                  Your Preferences
                </DialogTitle>
                <DialogDescription className="text-center">
                  Customize your Laro experience
                </DialogDescription>
              </DialogHeader>

              <div className="mt-6 space-y-6">
                {/* Theme */}
                <div>
                  <Label className="mb-3 block flex items-center gap-2">
                    <Palette className="w-4 h-4" />
                    Theme
                  </Label>
                  <div className="flex gap-2">
                    {[
                      { id: 'light', icon: Sun, label: 'Light' },
                      { id: 'dark', icon: Moon, label: 'Dark' },
                    ].map(({ id, icon: Icon, label }) => (
                      <button
                        key={id}
                        onClick={() => setTheme(id)}
                        className={`flex-1 flex flex-col items-center gap-2 p-3 rounded-xl border-2 transition-all ${
                          theme === id
                            ? 'border-mise bg-mise/10'
                            : 'border-border/60 hover:border-mise/50'
                        }`}
                      >
                        <Icon className={`w-5 h-5 ${theme === id ? 'text-mise' : 'text-muted-foreground'}`} />
                        <span className={`text-sm font-medium ${theme === id ? 'text-mise' : ''}`}>
                          {label}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Language */}
                <div>
                  <Label className="mb-3 block flex items-center gap-2">
                    <Globe className="w-4 h-4" />
                    Language
                  </Label>
                  <div className="grid grid-cols-3 gap-2">
                    {Object.entries(languages).slice(0, 6).map(([code, { name, flag }]) => (
                      <button
                        key={code}
                        onClick={() => setLanguage(code)}
                        className={`flex flex-col items-center gap-1 p-2 rounded-xl border-2 transition-all ${
                          language === code
                            ? 'border-mise bg-mise/10'
                            : 'border-border/60 hover:border-mise/50'
                        }`}
                      >
                        <span className="text-xl">{flag}</span>
                        <span className={`text-xs font-medium ${language === code ? 'text-mise' : 'text-muted-foreground'}`}>
                          {name}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Measurement Units */}
                <div>
                  <Label className="mb-3 block flex items-center gap-2">
                    <Scale className="w-4 h-4" />
                    Measurement Units
                  </Label>
                  <div className="flex gap-2">
                    {[
                      { id: 'metric', label: 'Metric', desc: 'g, ml, kg' },
                      { id: 'imperial', label: 'Imperial', desc: 'oz, cups, lbs' },
                    ].map(({ id, label, desc }) => (
                      <button
                        key={id}
                        onClick={() => setPreferences(prev => ({ ...prev, measurementUnit: id }))}
                        className={`flex-1 p-3 rounded-xl border-2 transition-all ${
                          preferences.measurementUnit === id
                            ? 'border-mise bg-mise/10'
                            : 'border-border/60 hover:border-mise/50'
                        }`}
                      >
                        <p className={`font-medium text-sm ${preferences.measurementUnit === id ? 'text-mise' : ''}`}>
                          {label}
                        </p>
                        <p className="text-xs text-muted-foreground">{desc}</p>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Dietary Restrictions */}
                <div>
                  <Label className="mb-3 block">Dietary Preferences (Optional)</Label>
                  <div className="flex flex-wrap gap-2">
                    {DIETARY_OPTIONS.map(option => (
                      <button
                        key={option.id}
                        onClick={() => toggleDietaryRestriction(option.id)}
                        className={`px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                          preferences.dietaryRestrictions.includes(option.id)
                            ? 'bg-mise text-white'
                            : 'bg-cream-subtle dark:bg-muted hover:bg-mise/20'
                        }`}
                      >
                        {option.emoji} {option.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* Step 3: Complete */}
          {currentStep === 3 && (
            <motion.div
              key="complete"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
            >
              <DialogHeader>
                <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto mb-4">
                  <Sparkles className="w-8 h-8 text-green-600 dark:text-green-400" />
                </div>
                <DialogTitle className="text-center text-2xl">
                  You're All Set! 🎉
                </DialogTitle>
                <DialogDescription className="text-center">
                  Your personalized Laro experience is ready
                </DialogDescription>
              </DialogHeader>

              <div className="mt-6 space-y-4">
                <div className="bg-cream-subtle dark:bg-muted rounded-xl p-4 space-y-3">
                  <p className="font-medium">What's Next?</p>
                  <ul className="text-sm space-y-2">
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500 flex-shrink-0" />
                      <span>Import your first recipe from any website</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500 flex-shrink-0" />
                      <span>Plan your weekly meals with drag & drop</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500 flex-shrink-0" />
                      <span>Generate smart shopping lists automatically</span>
                    </li>
                    <li className="flex items-center gap-2">
                      <Check className="w-4 h-4 text-green-500 flex-shrink-0" />
                      <span>Cook with step-by-step guidance mode</span>
                    </li>
                  </ul>
                </div>

                <div className="p-3 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-xl">
                  <p className="text-sm text-blue-800 dark:text-blue-200">
                    💡 Your settings sync across all devices automatically!
                  </p>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Navigation */}
        <div className="flex justify-between mt-6 pt-4 border-t">
          <Button
            variant="outline"
            onClick={handleBack}
            disabled={currentStep === 0}
            className="rounded-full"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <Button
            onClick={handleNext}
            className="rounded-full bg-mise hover:bg-mise-dark"
          >
            {currentStep === ONBOARDING_STEPS.length - 1 ? (
              <>
                Get Started
                <Check className="w-4 h-4 ml-2" />
              </>
            ) : (
              <>
                Next
                <ArrowRight className="w-4 h-4 ml-2" />
              </>
            )}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
