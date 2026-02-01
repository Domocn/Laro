import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useAuth } from './AuthContext';
import api from '../lib/api';

const AccessibilityContext = createContext();

export const useAccessibility = () => {
  const context = useContext(AccessibilityContext);
  if (!context) {
    throw new Error('useAccessibility must be used within AccessibilityProvider');
  }
  return context;
};

// Accessibility presets for different neurodiversity needs
export const ACCESSIBILITY_PRESETS = {
  default: {
    name: 'Default',
    description: 'Standard settings',
  },
  adhd: {
    name: 'Focus Mode (ADHD)',
    description: 'Reduced distractions, clear progress indicators',
  },
  dyslexia: {
    name: 'Reading Support (Dyslexia)',
    description: 'Dyslexic-friendly fonts, increased spacing',
  },
  autism: {
    name: 'Predictable Mode (Autism)',
    description: 'Consistent patterns, clear structure',
  },
  sensory: {
    name: 'Quiet Mode (Sensory)',
    description: 'Reduced motion, muted colors, minimal animations',
  },
};

export const AccessibilityProvider = ({ children }) => {
  const { isAuthenticated, user } = useAuth();
  const [loadedFromServer, setLoadedFromServer] = useState(false);
  const [saveTimeout, setSaveTimeout] = useState(null);

  // Helper function to get initial value (localStorage or default)
  const getInitialValue = (key, defaultValue) => {
    const saved = localStorage.getItem(`mise_${key}`);
    if (saved === null) return defaultValue;
    if (typeof defaultValue === 'boolean') return saved === 'true';
    return saved;
  };

  // Font settings
  const [dyslexicFont, setDyslexicFont] = useState(() => getInitialValue('dyslexic_font', false));

  // Text spacing for dyslexia support
  const [textSpacing, setTextSpacing] = useState(() => getInitialValue('text_spacing', 'normal'));

  // Line height
  const [lineHeight, setLineHeight] = useState(() => getInitialValue('line_height', 'normal'));

  // Focus mode (ADHD support)
  const [focusMode, setFocusMode] = useState(() => getInitialValue('focus_mode', false));

  // Simplified UI mode
  const [simplifiedMode, setSimplifiedMode] = useState(() => getInitialValue('simplified_mode', false));

  // Step highlighting in cooking mode
  const [highlightCurrentStep, setHighlightCurrentStep] = useState(() => getInitialValue('highlight_step', true));

  // Progress indicators
  const [showProgressIndicators, setShowProgressIndicators] = useState(() => getInitialValue('progress_indicators', true));

  // Confirmation dialogs for important actions
  const [confirmActions, setConfirmActions] = useState(() => getInitialValue('confirm_actions', true));

  // Icon labels (show text labels alongside icons)
  const [iconLabels, setIconLabels] = useState(() => getInitialValue('icon_labels', false));

  // Reading ruler (highlight current line being read)
  const [readingRuler, setReadingRuler] = useState(() => getInitialValue('reading_ruler', false));

  // Contrast level
  const [contrastLevel, setContrastLevel] = useState(() => getInitialValue('contrast_level', 'normal'));

  // Animation level
  const [animationLevel, setAnimationLevel] = useState(() => getInitialValue('animation_level', 'normal'));

  // Sound effects
  const [soundEffects, setSoundEffects] = useState(() => getInitialValue('sound_effects', false));

  // Haptic feedback (for devices that support it)
  const [hapticFeedback, setHapticFeedback] = useState(() => getInitialValue('haptic_feedback', false));

  // Timer notifications
  const [timerNotifications, setTimerNotifications] = useState(() => getInitialValue('timer_notifications', 'both'));

  // Load settings from backend when user logs in
  useEffect(() => {
    if (!isAuthenticated || !user || loadedFromServer) return;

    const loadServerSettings = async () => {
      try {
        const res = await api.get('/preferences');
        if (res.data) {
          // Load accessibility settings from server
          if (res.data.dyslexicFont !== undefined) setDyslexicFont(res.data.dyslexicFont);
          if (res.data.textSpacing !== undefined) setTextSpacing(res.data.textSpacing);
          if (res.data.lineHeight !== undefined) setLineHeight(res.data.lineHeight);
          if (res.data.focusMode !== undefined) setFocusMode(res.data.focusMode);
          if (res.data.simplifiedMode !== undefined) setSimplifiedMode(res.data.simplifiedMode);
          if (res.data.highlightCurrentStep !== undefined) setHighlightCurrentStep(res.data.highlightCurrentStep);
          if (res.data.showProgressIndicators !== undefined) setShowProgressIndicators(res.data.showProgressIndicators);
          if (res.data.confirmActions !== undefined) setConfirmActions(res.data.confirmActions);
          if (res.data.iconLabels !== undefined) setIconLabels(res.data.iconLabels);
          if (res.data.readingRuler !== undefined) setReadingRuler(res.data.readingRuler);
          if (res.data.contrastLevel !== undefined) setContrastLevel(res.data.contrastLevel);
          if (res.data.animationLevel !== undefined) setAnimationLevel(res.data.animationLevel);
          if (res.data.soundEffects !== undefined) setSoundEffects(res.data.soundEffects);
          if (res.data.hapticFeedback !== undefined) setHapticFeedback(res.data.hapticFeedback);
          if (res.data.timerNotifications !== undefined) setTimerNotifications(res.data.timerNotifications);

          setLoadedFromServer(true);
        }
      } catch (error) {
        console.log('Using local accessibility settings:', error);
      }
    };

    loadServerSettings();
  }, [isAuthenticated, user, loadedFromServer]);

  // Save to backend (debounced)
  const saveToServer = useCallback(async () => {
    if (!isAuthenticated) return;

    try {
      await api.put('/preferences', {
        dyslexicFont,
        textSpacing,
        lineHeight,
        focusMode,
        simplifiedMode,
        highlightCurrentStep,
        showProgressIndicators,
        confirmActions,
        iconLabels,
        readingRuler,
        contrastLevel,
        animationLevel,
        soundEffects,
        hapticFeedback,
        timerNotifications,
      });
    } catch (error) {
      console.error('Failed to save accessibility settings to server:', error);
    }
  }, [
    isAuthenticated,
    dyslexicFont,
    textSpacing,
    lineHeight,
    focusMode,
    simplifiedMode,
    highlightCurrentStep,
    showProgressIndicators,
    confirmActions,
    iconLabels,
    readingRuler,
    contrastLevel,
    animationLevel,
    soundEffects,
    hapticFeedback,
    timerNotifications,
  ]);

  // Debounced save to server when settings change
  useEffect(() => {
    if (!loadedFromServer || !isAuthenticated) return;

    // Clear previous timeout
    if (saveTimeout) {
      clearTimeout(saveTimeout);
    }

    // Set new timeout to save after 1 second of no changes
    const timeout = setTimeout(() => {
      saveToServer();
    }, 1000);

    setSaveTimeout(timeout);

    return () => {
      if (timeout) clearTimeout(timeout);
    };
  }, [
    loadedFromServer,
    isAuthenticated,
    dyslexicFont,
    textSpacing,
    lineHeight,
    focusMode,
    simplifiedMode,
    highlightCurrentStep,
    showProgressIndicators,
    confirmActions,
    iconLabels,
    readingRuler,
    contrastLevel,
    animationLevel,
    soundEffects,
    hapticFeedback,
    timerNotifications,
  ]);

  // Apply dyslexic font
  useEffect(() => {
    localStorage.setItem('mise_dyslexic_font', dyslexicFont.toString());
    const root = document.documentElement;

    if (dyslexicFont) {
      root.classList.add('dyslexic-font');
    } else {
      root.classList.remove('dyslexic-font');
    }
  }, [dyslexicFont]);

  // Apply text spacing
  useEffect(() => {
    localStorage.setItem('mise_text_spacing', textSpacing);
    const root = document.documentElement;

    // Remove all spacing classes
    root.classList.remove('text-spacing-comfortable', 'text-spacing-spacious');

    if (textSpacing === 'comfortable') {
      root.classList.add('text-spacing-comfortable');
    } else if (textSpacing === 'spacious') {
      root.classList.add('text-spacing-spacious');
    }
  }, [textSpacing]);

  // Apply line height
  useEffect(() => {
    localStorage.setItem('mise_line_height', lineHeight);
    const root = document.documentElement;

    root.classList.remove('line-height-relaxed', 'line-height-loose');

    if (lineHeight === 'relaxed') {
      root.classList.add('line-height-relaxed');
    } else if (lineHeight === 'loose') {
      root.classList.add('line-height-loose');
    }
  }, [lineHeight]);

  // Apply focus mode
  useEffect(() => {
    localStorage.setItem('mise_focus_mode', focusMode.toString());
    const root = document.documentElement;

    if (focusMode) {
      root.classList.add('focus-mode');
    } else {
      root.classList.remove('focus-mode');
    }
  }, [focusMode]);

  // Apply simplified mode
  useEffect(() => {
    localStorage.setItem('mise_simplified_mode', simplifiedMode.toString());
    const root = document.documentElement;

    if (simplifiedMode) {
      root.classList.add('simplified-mode');
    } else {
      root.classList.remove('simplified-mode');
    }
  }, [simplifiedMode]);

  // Apply contrast level
  useEffect(() => {
    localStorage.setItem('mise_contrast_level', contrastLevel);
    const root = document.documentElement;

    root.classList.remove('contrast-high', 'contrast-maximum');

    if (contrastLevel === 'high') {
      root.classList.add('contrast-high');
    } else if (contrastLevel === 'maximum') {
      root.classList.add('contrast-maximum');
    }
  }, [contrastLevel]);

  // Apply animation level
  useEffect(() => {
    localStorage.setItem('mise_animation_level', animationLevel);
    const root = document.documentElement;

    root.classList.remove('animations-none', 'animations-reduced', 'animations-enhanced');

    if (animationLevel === 'none') {
      root.classList.add('animations-none');
    } else if (animationLevel === 'reduced') {
      root.classList.add('animations-reduced');
    } else if (animationLevel === 'enhanced') {
      root.classList.add('animations-enhanced');
    }
  }, [animationLevel]);

  // Store other settings in localStorage
  useEffect(() => {
    localStorage.setItem('mise_highlight_step', highlightCurrentStep.toString());
  }, [highlightCurrentStep]);

  useEffect(() => {
    localStorage.setItem('mise_progress_indicators', showProgressIndicators.toString());
  }, [showProgressIndicators]);

  useEffect(() => {
    localStorage.setItem('mise_confirm_actions', confirmActions.toString());
  }, [confirmActions]);

  useEffect(() => {
    localStorage.setItem('mise_icon_labels', iconLabels.toString());
  }, [iconLabels]);

  useEffect(() => {
    localStorage.setItem('mise_reading_ruler', readingRuler.toString());
  }, [readingRuler]);

  useEffect(() => {
    localStorage.setItem('mise_sound_effects', soundEffects.toString());
  }, [soundEffects]);

  useEffect(() => {
    localStorage.setItem('mise_haptic_feedback', hapticFeedback.toString());
  }, [hapticFeedback]);

  useEffect(() => {
    localStorage.setItem('mise_timer_notifications', timerNotifications);
  }, [timerNotifications]);

  // Apply preset
  const applyPreset = (presetName) => {
    switch (presetName) {
      case 'adhd':
        setFocusMode(true);
        setSimplifiedMode(true);
        setShowProgressIndicators(true);
        setConfirmActions(true);
        setHighlightCurrentStep(true);
        setTimerNotifications('both');
        setIconLabels(true);
        break;

      case 'dyslexia':
        setDyslexicFont(true);
        setTextSpacing('spacious');
        setLineHeight('loose');
        setReadingRuler(true);
        setHighlightCurrentStep(true);
        setContrastLevel('high');
        break;

      case 'autism':
        setConfirmActions(true);
        setShowProgressIndicators(true);
        setSimplifiedMode(true);
        setIconLabels(true);
        setAnimationLevel('reduced');
        break;

      case 'sensory':
        setAnimationLevel('none');
        setContrastLevel('normal');
        setSoundEffects(false);
        setHapticFeedback(false);
        setSimplifiedMode(true);
        setFocusMode(true);
        break;

      case 'default':
      default:
        // Reset to defaults
        setDyslexicFont(false);
        setTextSpacing('normal');
        setLineHeight('normal');
        setFocusMode(false);
        setSimplifiedMode(false);
        setHighlightCurrentStep(true);
        setShowProgressIndicators(true);
        setConfirmActions(true);
        setIconLabels(false);
        setReadingRuler(false);
        setContrastLevel('normal');
        setAnimationLevel('normal');
        setSoundEffects(false);
        setHapticFeedback(false);
        setTimerNotifications('both');
        break;
    }
  };

  // Reset all settings
  const resetAccessibilitySettings = () => {
    applyPreset('default');
  };

  const value = {
    // Font settings
    dyslexicFont,
    setDyslexicFont,
    textSpacing,
    setTextSpacing,
    lineHeight,
    setLineHeight,

    // Focus and attention
    focusMode,
    setFocusMode,
    simplifiedMode,
    setSimplifiedMode,

    // Visual aids
    highlightCurrentStep,
    setHighlightCurrentStep,
    showProgressIndicators,
    setShowProgressIndicators,
    iconLabels,
    setIconLabels,
    readingRuler,
    setReadingRuler,
    contrastLevel,
    setContrastLevel,

    // Animation and motion
    animationLevel,
    setAnimationLevel,

    // Interaction
    confirmActions,
    setConfirmActions,

    // Sensory
    soundEffects,
    setSoundEffects,
    hapticFeedback,
    setHapticFeedback,
    timerNotifications,
    setTimerNotifications,

    // Presets
    applyPreset,
    resetAccessibilitySettings,
    presets: ACCESSIBILITY_PRESETS,
  };

  return (
    <AccessibilityContext.Provider value={value}>
      {children}
    </AccessibilityContext.Provider>
  );
};
