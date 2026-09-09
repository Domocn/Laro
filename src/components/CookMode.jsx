import React, { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cookingApi } from '../lib/api';
import { getImageUrl } from '../lib/utils';
import {
  normalizeCookStepsWithAmounts,
  parseTimeFromStep,
  formatCookTimer,
  ingredientsForStep,
} from '../lib/cookModeSteps';
import { useAccessibility } from '../context/AccessibilityContext';
import { useLanguage } from '../context/LanguageContext';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { Button } from './ui/button';
import { CookingAIAssistant, AIAssistantButton } from './CookingAIAssistant';
import { VoiceCookingControls } from './VoiceCooking';
import {
  X,
  ChevronLeft,
  ChevronRight,
  Play,
  Pause,
  RotateCcw,
  Check,
  ThumbsUp,
  ThumbsDown,
  Meh,
  ChefHat,
  List,
  Timer,
  BookOpen,
  Cast,
} from 'lucide-react';
import { toast } from 'sonner';
import { useCookCast } from '../hooks/useCookCast';
import { useCookMediaSession } from '../hooks/useCookMediaSession';

const QUICK_TIMER_MINUTES = [1, 5, 10, 15, 20];

export const CookMode = ({ recipe, onClose }) => {
  const { t } = useLanguage();
  const { preferences } = useUserPreferences();
  const measurementUnit = preferences.measurement_unit || preferences.measurementUnit || 'metric';
  const {
    highlightCurrentStep,
    showProgressIndicators,
    soundEffects,
    timerNotifications,
    hapticFeedback,
    focusMode,
  } = useAccessibility();
  const [currentStep, setCurrentStep] = useState(0);
  const [sessionId, setSessionId] = useState(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [showAIAssistant, setShowAIAssistant] = useState(false);
  const [showIngredients, setShowIngredients] = useState(false);
  const [showTimerPicker, setShowTimerPicker] = useState(false);
  const [cookNote, setCookNote] = useState('');
  const [timers, setTimers] = useState({});
  const [direction, setDirection] = useState(1);
  const wakeLockRef = useRef(null);
  const timerIntervalRef = useRef({});

  const steps = useMemo(
    () => normalizeCookStepsWithAmounts(recipe?.instructions, recipe?.ingredients, measurementUnit),
    [recipe?.instructions, recipe?.ingredients, measurementUnit]
  );
  const coverUrl = useMemo(
    () => getImageUrl(recipe?.image_url, recipe),
    [recipe?.image_url, recipe?.id, recipe?.title, recipe?.category, recipe]
  );
  const totalSteps = steps.length;
  const progress = totalSteps ? (currentStep + 1) / totalSteps : 0;
  const currentInstruction = steps[currentStep] || '';
  const prevInstruction = currentStep > 0 ? steps[currentStep - 1] : '';
  const nextInstruction =
    currentStep < totalSteps - 1 ? steps[currentStep + 1] : '';
  const stepIngredients = useMemo(
    () => ingredientsForStep(currentInstruction, recipe?.ingredients, measurementUnit),
    [currentInstruction, recipe?.ingredients, measurementUnit]
  );
  const timer = timers[currentStep];
  const castTimerLabel =
    timer?.running || (timer?.remaining != null && timer.remaining !== timer.total)
      ? formatCookTimer(timer.remaining || 0)
      : '';

  const {
    castConfigured,
    castAvailable,
    castConnected,
    requestSession,
    endSession,
  } = useCookCast({
    title: recipe?.title || recipe?.name || 'Recipe',
    steps,
    stepIndex: currentStep,
    timerLabel: castTimerLabel,
    enabled: !showFeedback,
  });

  useCookMediaSession({
    title: recipe?.title || recipe?.name || 'Laro',
    stepIndex: currentStep,
    totalSteps,
    stepText: steps[currentStep] || '',
    artworkUrl: coverUrl,
    onNext: () => {
      if (currentStep < totalSteps - 1) {
        setDirection(1);
        setCurrentStep((s) => Math.min(s + 1, Math.max(totalSteps - 1, 0)));
      }
    },
    onPrev: () => {
      if (currentStep > 0) {
        setDirection(-1);
        setCurrentStep((s) => Math.max(s - 1, 0));
      }
    },
    enabled: !showFeedback && totalSteps > 0,
  });

  const handleCastClick = async () => {
    if (castConnected) {
      await endSession();
      toast.message(t('castDisconnected') || 'Cast stopped');
      return;
    }
    if (!castConfigured) {
      toast.error(
        t('castNeedsAppId') ||
          'Chromecast needs a Cast App ID. Set REACT_APP_CAST_APP_ID (receiver: /cast/receiver.html).'
      );
      return;
    }
    const ok = await requestSession();
    if (ok) toast.success(t('castConnected') || 'Casting cook mode to your TV');
  };

  useEffect(() => {
    const requestWakeLock = async () => {
      try {
        if ('wakeLock' in navigator) {
          wakeLockRef.current = await navigator.wakeLock.request('screen');
        }
      } catch (err) {
        console.log('Wake lock not supported:', err);
      }
    };
    requestWakeLock();

    const startSession = async () => {
      try {
        const res = await cookingApi.startSession(recipe.id);
        setSessionId(res.data.session_id);
      } catch (err) {
        console.error('Failed to start session:', err);
      }
    };
    startSession();

    return () => {
      if (wakeLockRef.current) {
        wakeLockRef.current.release();
      }
      Object.values(timerIntervalRef.current).forEach(clearInterval);
    };
  }, [recipe.id]);

  const playTimerSound = () => {
    try {
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      oscillator.frequency.value = 800;
      oscillator.type = 'sine';
      gainNode.gain.value = 0.3;
      oscillator.start();
      setTimeout(() => oscillator.stop(), 300);
    } catch (e) {
      console.log('Audio not supported');
    }
  };

  const notifyTimerDone = () => {
    const mode = timerNotifications || 'both';
    const wantsAudio = mode === 'audio' || mode === 'both';
    const wantsVisual = mode === 'visual' || mode === 'both';
    // Prefer timerNotifications; fall back to soundEffects for older prefs
    if (wantsAudio || (mode !== 'none' && mode !== 'visual' && soundEffects)) {
      if (mode !== 'visual' && mode !== 'none') playTimerSound();
    }
    if (wantsVisual) {
      toast.success(t('timerDone'));
    }
    if (hapticFeedback && typeof navigator !== 'undefined' && navigator.vibrate) {
      try {
        navigator.vibrate([80, 40, 80]);
      } catch {
        /* ignore */
      }
    }
  };

  const startTimer = (stepIndex, seconds) => {
    if (timerIntervalRef.current[stepIndex]) {
      clearInterval(timerIntervalRef.current[stepIndex]);
    }

    setTimers((prev) => ({
      ...prev,
      [stepIndex]: { total: seconds, remaining: seconds, running: true },
    }));

    timerIntervalRef.current[stepIndex] = setInterval(() => {
      setTimers((prev) => {
        const timer = prev[stepIndex];
        if (!timer || timer.remaining <= 0) {
          clearInterval(timerIntervalRef.current[stepIndex]);
          notifyTimerDone();
          return { ...prev, [stepIndex]: { ...timer, remaining: 0, running: false } };
        }
        return {
          ...prev,
          [stepIndex]: { ...timer, remaining: timer.remaining - 1 },
        };
      });
    }, 1000);
  };

  const pauseTimer = (stepIndex) => {
    clearInterval(timerIntervalRef.current[stepIndex]);
    setTimers((prev) => ({
      ...prev,
      [stepIndex]: { ...prev[stepIndex], running: false },
    }));
  };

  const resetTimer = (stepIndex, seconds) => {
    clearInterval(timerIntervalRef.current[stepIndex]);
    setTimers((prev) => ({
      ...prev,
      [stepIndex]: { total: seconds, remaining: seconds, running: false },
    }));
  };

  const goToStep = (next) => {
    setDirection(next > currentStep ? 1 : -1);
    setCurrentStep(next);
    setShowTimerPicker(false);
  };

  const backToRecipe = () => {
    Object.values(timerIntervalRef.current).forEach(clearInterval);
    onClose();
  };

  const handleNext = () => {
    if (currentStep < totalSteps - 1) {
      goToStep(currentStep + 1);
    } else {
      setShowFeedback(true);
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      goToStep(currentStep - 1);
    }
  };

  const handleFeedback = async (feedback) => {
    try {
      const note = cookNote.trim();
      if (sessionId) {
        await cookingApi.completeSession(sessionId, feedback, note);
      } else if (note) {
        await cookingApi.markCooked(recipe.id, { notes: note, feedback });
      } else if (feedback) {
        await cookingApi.submitFeedback(recipe.id, feedback);
      }

      const messages = {
        yes: t('feedbackYes'),
        no: t('feedbackNo'),
        meh: t('feedbackMeh'),
      };
      toast.success(note ? `${messages[feedback]}${t('feedbackNoteSavedSuffix')}` : messages[feedback]);
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    }
    backToRecipe();
  };

  const handleSkipWithNote = async () => {
    try {
      const note = cookNote.trim();
      if (sessionId) {
        await cookingApi.completeSession(sessionId, null, note);
      } else if (note) {
        await cookingApi.markCooked(recipe.id, { notes: note });
      }
      toast.success(note ? t('cookedNoteSaved') : t('niceWorkShort'));
    } catch (err) {
      console.error('Failed to complete cook session:', err);
    }
    backToRecipe();
  };

  const detectedSeconds = parseTimeFromStep(currentInstruction);
  const activeSeconds = timer?.total || detectedSeconds;
  const timerRemaining = timer?.remaining ?? detectedSeconds ?? 0;
  const timerTotal = timer?.total ?? detectedSeconds ?? 1;
  const timerProgress = activeSeconds ? 1 - timerRemaining / timerTotal : 0;
  const showActiveTimer = Boolean(timer || detectedSeconds);

  const stepVariants = {
    enter: (dir) => ({ opacity: 0, y: dir > 0 ? 18 : -18, scale: 0.985 }),
    center: { opacity: 1, y: 0, scale: 1 },
    exit: (dir) => ({ opacity: 0, y: dir > 0 ? -14 : 14, scale: 0.985 }),
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex flex-col cook-mode-root text-white"
        data-testid="cook-mode"
      >
        {/* Atmosphere: warm kitchen wash + optional recipe cover */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
          {coverUrl && (
            <div
              className="absolute inset-0 scale-110 bg-cover bg-center opacity-25 blur-2xl"
              style={{ backgroundImage: `url(${coverUrl})` }}
            />
          )}
          <div className="absolute inset-0 cook-mode-wash" />
          <div className="absolute -top-24 left-1/2 h-[28rem] w-[28rem] -translate-x-1/2 rounded-full cook-mode-glow" />
          <div className="absolute bottom-0 inset-x-0 h-48 cook-mode-floor" />
        </div>

        {/* Top chrome */}
        <header className="relative z-10 px-4 pt-[max(0.75rem,env(safe-area-inset-top))] pb-3">
          <div className="flex items-center justify-between gap-3 mb-3">
            <div className="min-w-0 flex items-center gap-3">
              <div className="shrink-0 w-10 h-10 rounded-2xl bg-laro/20 border border-laro/30 flex items-center justify-center">
                <ChefHat className="w-5 h-5 text-laro" />
              </div>
              <div className="min-w-0">
                <p className="text-[11px] uppercase tracking-[0.18em] text-white/50 font-semibold">
                  {t('cookModeLabel')}
                </p>
                <h1 className="font-heading font-semibold text-white truncate text-base sm:text-lg">
                  {recipe.title}
                </h1>
              </div>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowIngredients((v) => !v)}
                className={`rounded-full text-white hover:bg-white/10 ${
                  showIngredients ? 'bg-white/10 text-laro' : ''
                }`}
                aria-label={t('ingredients')}
                aria-pressed={showIngredients}
              >
                <List className="w-5 h-5" />
              </Button>
              <Button
                variant="ghost"
                onClick={backToRecipe}
                className="rounded-full text-white hover:bg-white/10 h-10 px-3 gap-1.5"
                aria-label={t('backToRecipe')}
                data-testid="cook-mode-back-to-recipe"
              >
                <BookOpen className="w-4 h-4" />
                <span className="hidden sm:inline text-sm">{t('backToRecipe')}</span>
                <X className="w-4 h-4 sm:hidden" />
              </Button>
            </div>
          </div>

          {/* Continuous progress */}
          <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-laro to-emerald-300"
              initial={false}
              animate={{ width: `${progress * 100}%` }}
              transition={{ type: 'spring', stiffness: 120, damping: 20 }}
            />
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-white/50">
            <span>
              {t('stepOfTotal', { current: Math.min(currentStep + 1, totalSteps), total: totalSteps })}
            </span>
            <span>{Math.round(progress * 100)}%</span>
          </div>
        </header>

        {/* Ingredients drawer */}
        <AnimatePresence>
          {showIngredients && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="relative z-10 overflow-hidden border-b border-white/10"
            >
              <div className="px-4 py-3 bg-black/25 backdrop-blur-md">
                <p className="text-xs uppercase tracking-wider text-white/45 mb-2 font-semibold">
                  {t('ingredients')} · {recipe.ingredients?.length || 0}
                </p>
                <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
                  {recipe.ingredients?.map((ing, i) => (
                    <div
                      key={i}
                      className="shrink-0 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-sm"
                    >
                      <span className="text-laro font-medium">
                        {[ing.amount, ing.unit].filter(Boolean).join(' ')}
                      </span>
                      <span className="text-white/85 ml-1.5">{ing.name}</span>
                    </div>
                  ))}
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {!showFeedback ? (
          <>
            {/* Main stage: filled card + peeks — not a lonely instruction in a void */}
            <div className="relative z-10 flex-1 flex flex-col px-4 sm:px-6 py-3 overflow-y-auto">
              {totalSteps === 0 ? (
                <div className="flex-1 flex items-center justify-center">
                  <div className="cook-mode-card w-full max-w-lg text-center p-8">
                    <p className="cook-mode-step-text font-heading font-semibold text-[#2a332c]">
                      {t('noStepsYet')}
                    </p>
                    <Button
                      onClick={backToRecipe}
                      className="mt-6 rounded-full bg-laro hover:bg-laro-dark text-white"
                    >
                      {t('backToRecipe')}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex-1 flex flex-col justify-center w-full max-w-xl mx-auto min-h-0 py-1">
                  {!focusMode && prevInstruction && (
                    <button
                      type="button"
                      onClick={handlePrev}
                      className="cook-mode-peek cook-mode-peek-prev mb-2 text-left w-full shrink-0"
                      aria-label={t('goToStep', { n: currentStep })}
                    >
                      <span className="cook-mode-peek-label">{t('previousStep')}</span>
                      <span className="cook-mode-peek-text">{prevInstruction}</span>
                    </button>
                  )}

                  <AnimatePresence mode="wait" custom={direction}>
                    <motion.div
                      key={currentStep}
                      custom={direction}
                      variants={stepVariants}
                      initial="enter"
                      animate="center"
                      exit="exit"
                      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                      className={`cook-mode-card w-full shrink-0 ${
                        highlightCurrentStep ? 'cook-mode-card-focus' : ''
                      }`}
                      data-testid="cook-mode-step"
                    >
                      <div className="flex items-center justify-between gap-3 mb-4">
                        <div className="inline-flex items-center gap-2 rounded-full bg-[#5bb080]/15 border border-[#5bb080]/30 px-3 py-1">
                          <span className="cook-mode-step-badge font-heading text-[#2f6b4a]">
                            {String(currentStep + 1).padStart(2, '0')}
                          </span>
                          <span className="text-xs font-semibold uppercase tracking-[0.14em] text-[#5a6b5e]">
                            {t('stepOfTotal', {
                              current: Math.min(currentStep + 1, totalSteps),
                              total: totalSteps,
                            })}
                          </span>
                        </div>
                        {showProgressIndicators && !focusMode && (
                          <span className="text-xs font-medium tabular-nums text-[#6b7a6f]">
                            {Math.round(progress * 100)}%
                          </span>
                        )}
                      </div>

                      <p className="cook-mode-step-text font-heading font-semibold leading-snug text-balance text-[#1f2a22]">
                        {currentInstruction}
                      </p>

                      {stepIngredients.length > 0 && (
                        <div className="mt-5" data-testid="cook-mode-step-ingredients">
                          <p className="text-[11px] uppercase tracking-[0.16em] font-semibold text-[#6b7a6f] mb-2">
                            {t('forThisStep')}
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {stepIngredients.map((ing) => (
                              <span key={ing.name} className="cook-mode-ing-chip">
                                {ing.qty ? (
                                  <>
                                    <span className="font-semibold text-[#2f6b4a]">{ing.qty}</span>
                                    <span className="ml-1.5">{ing.name}</span>
                                  </>
                                ) : (
                                  ing.name
                                )}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="mt-6"
                        data-testid="cook-mode-timer"
                      >
                        {showActiveTimer ? (
                          <div className="cook-mode-timer-row">
                            <div className="relative w-24 h-24 sm:w-28 sm:h-28 shrink-0">
                              <svg className="absolute inset-0 -rotate-90" viewBox="0 0 120 120">
                                <circle
                                  cx="60"
                                  cy="60"
                                  r="52"
                                  fill="none"
                                  stroke="rgba(47,107,74,0.12)"
                                  strokeWidth="8"
                                />
                                <motion.circle
                                  cx="60"
                                  cy="60"
                                  r="52"
                                  fill="none"
                                  stroke="url(#cookTimerGrad)"
                                  strokeWidth="8"
                                  strokeLinecap="round"
                                  strokeDasharray={2 * Math.PI * 52}
                                  animate={{
                                    strokeDashoffset:
                                      2 * Math.PI * 52 * (1 - (timer ? timerProgress : 0)),
                                  }}
                                  transition={{ duration: 0.4 }}
                                  className={timer?.running ? 'cook-mode-timer-pulse' : ''}
                                />
                                <defs>
                                  <linearGradient id="cookTimerGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                                    <stop offset="0%" stopColor="#5BB080" />
                                    <stop offset="100%" stopColor="#C4A46A" />
                                  </linearGradient>
                                </defs>
                              </svg>
                              <div className="absolute inset-0 flex flex-col items-center justify-center">
                                <Timer className="w-3.5 h-3.5 text-[#6b7a6f] mb-0.5" />
                                <span className="font-mono text-xl sm:text-2xl tabular-nums tracking-tight text-[#1f2a22]">
                                  {formatCookTimer(timerRemaining)}
                                </span>
                              </div>
                            </div>
                            <div className="flex flex-wrap gap-2 flex-1">
                              {!timer || !timer.running ? (
                                <Button
                                  onClick={() =>
                                    startTimer(
                                      currentStep,
                                      timer?.remaining || detectedSeconds || timerTotal
                                    )
                                  }
                                  className="rounded-full bg-laro hover:bg-laro-dark text-white shadow-md shadow-laro/20 px-4 h-11"
                                  data-testid="cook-mode-start-timer"
                                >
                                  <Play className="w-4 h-4 mr-2" />
                                  {t('startTimer')}
                                </Button>
                              ) : (
                                <Button
                                  onClick={() => pauseTimer(currentStep)}
                                  variant="outline"
                                  className="rounded-full border-[#2f6b4a]/25 bg-white/60 text-[#1f2a22] hover:bg-white px-4 h-11"
                                >
                                  <Pause className="w-4 h-4 mr-2" />
                                  {t('pauseTimer')}
                                </Button>
                              )}
                              <Button
                                onClick={() =>
                                  resetTimer(currentStep, detectedSeconds || timer?.total || 60)
                                }
                                variant="ghost"
                                size="icon"
                                className="rounded-full text-[#5a6b5e] hover:bg-black/5 h-11 w-11"
                                aria-label={t('resetTimer')}
                              >
                                <RotateCcw className="w-4 h-4" />
                              </Button>
                              <Button
                                onClick={() => setShowTimerPicker((v) => !v)}
                                variant="ghost"
                                className="rounded-full text-[#5a6b5e] hover:bg-black/5 h-11 px-3"
                              >
                                {t('change')}
                              </Button>
                            </div>
                          </div>
                        ) : (
                          <Button
                            onClick={() => setShowTimerPicker(true)}
                            variant="outline"
                            className="rounded-full border-[#2f6b4a]/20 bg-white/50 text-[#1f2a22] hover:bg-white h-11 px-4"
                            data-testid="cook-mode-add-timer"
                          >
                            <Timer className="w-4 h-4 mr-2" />
                            {t('setATimer')}
                          </Button>
                        )}

                        {showTimerPicker && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {QUICK_TIMER_MINUTES.map((m) => (
                              <Button
                                key={m}
                                type="button"
                                onClick={() => {
                                  startTimer(currentStep, m * 60);
                                  setShowTimerPicker(false);
                                }}
                                variant="outline"
                                className="rounded-full border-[#2f6b4a]/20 bg-white/60 text-[#1f2a22] hover:bg-white h-10 px-3"
                              >
                                {t('nMin', { n: m })}
                              </Button>
                            ))}
                          </div>
                        )}
                      </motion.div>
                    </motion.div>
                  </AnimatePresence>

                  {!focusMode && nextInstruction && (
                    <button
                      type="button"
                      onClick={handleNext}
                      className="cook-mode-peek cook-mode-peek-next mt-2 text-left w-full"
                      aria-label={t('goToStep', { n: currentStep + 2 })}
                    >
                      <span className="cook-mode-peek-label">{t('upNext')}</span>
                      <span className="cook-mode-peek-text">{nextInstruction}</span>
                    </button>
                  )}

                  {!focusMode && totalSteps > 1 && (
                    <div className="mt-4 mb-1 flex flex-wrap justify-center gap-1.5">
                      {steps.map((_, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => goToStep(i)}
                          aria-label={t('goToStep', { n: i + 1 })}
                          aria-current={i === currentStep ? 'step' : undefined}
                          className={`h-2 rounded-full transition-all duration-300 ${
                            i === currentStep
                              ? 'w-7 bg-laro shadow-[0_0_10px_rgba(123,200,156,0.4)]'
                              : i < currentStep
                              ? 'w-2.5 bg-laro/50'
                              : 'w-2.5 bg-white/25 hover:bg-white/40'
                          }`}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Bottom controls — large kitchen-friendly targets */}
            <div className="relative z-10 px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3 cook-mode-dock">
              <div className="flex justify-center mb-3 gap-2 flex-wrap">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleCastClick}
                  className={`rounded-full h-10 w-10 ${
                    castConnected
                      ? 'bg-laro text-white'
                      : 'text-white hover:bg-gray-700'
                  }`}
                  title={
                    castConnected
                      ? 'Stop casting'
                      : castConfigured
                        ? 'Cast cook mode to Chromecast'
                        : 'Chromecast (set Cast App ID)'
                  }
                  data-testid="cook-mode-cast"
                  aria-pressed={castConnected}
                >
                  <Cast className={`w-5 h-5 ${castAvailable || castConfigured ? '' : 'opacity-60'}`} />
                </Button>
                <VoiceCookingControls
                  recipe={recipe}
                  currentStep={currentStep}
                  totalSteps={totalSteps}
                  steps={steps}
                  onNavigate={(delta) => {
                    if (delta > 0) handleNext();
                    else handlePrev();
                  }}
                  onTimerStart={() => {
                    const secs = timer?.remaining || detectedSeconds || 5 * 60;
                    startTimer(currentStep, secs);
                  }}
                  onTimerStop={() => pauseTimer(currentStep)}
                  timerActive={timer?.running}
                />
              </div>

              <div className="flex items-stretch gap-3 max-w-lg mx-auto">
                <Button
                  variant="ghost"
                  onClick={handlePrev}
                  disabled={currentStep === 0 || totalSteps === 0}
                  className="flex-1 h-14 sm:h-16 rounded-2xl text-white/90 hover:bg-white/10 disabled:opacity-30 border border-white/10 text-base"
                >
                  <ChevronLeft className="w-6 h-6 mr-1" />
                  {t('back')}
                </Button>

                <Button
                  onClick={handleNext}
                  disabled={totalSteps === 0}
                  className="flex-[1.4] h-14 sm:h-16 rounded-2xl bg-laro hover:bg-laro-dark text-white text-lg font-semibold shadow-lg shadow-laro/30"
                  data-testid="cook-mode-next"
                >
                  {currentStep === totalSteps - 1 ? (
                    <>
                      {t('doneCooking')}
                      <Check className="w-5 h-5 ml-1.5" />
                    </>
                  ) : (
                    <>
                      {t('nextStep')}
                      <ChevronRight className="w-6 h-6 ml-1.5" />
                    </>
                  )}
                </Button>
              </div>
            </div>

            {!showAIAssistant && (
              <AIAssistantButton onClick={() => setShowAIAssistant(true)} />
            )}

            <CookingAIAssistant
              recipe={recipe}
              currentStep={currentStep}
              isOpen={showAIAssistant}
              onClose={() => setShowAIAssistant(false)}
            />
          </>
        ) : (
          <div className="relative z-10 flex-1 flex flex-col items-center justify-center p-6 sm:p-10">
            <motion.div
              initial={{ scale: 0.92, opacity: 0, y: 12 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              transition={{ type: 'spring', stiffness: 160, damping: 18 }}
              className="w-full max-w-md text-center"
            >
              <motion.div
                initial={{ rotate: -8, scale: 0.8 }}
                animate={{ rotate: 0, scale: 1 }}
                transition={{ delay: 0.1, type: 'spring', stiffness: 200 }}
                className="mx-auto mb-6 w-20 h-20 rounded-3xl bg-laro/20 border border-laro/35 flex items-center justify-center"
              >
                <ChefHat className="w-10 h-10 text-laro" />
              </motion.div>
              <h2 className="text-3xl sm:text-4xl font-heading font-bold text-white mb-2">
                {t('niceWorkChef')}
              </h2>
              <p className="text-lg text-white/65 mb-8">{t('wouldYouCookAgain')}</p>

              <textarea
                value={cookNote}
                onChange={(e) => setCookNote(e.target.value)}
                placeholder={t('cookNotePlaceholder')}
                className="w-full mb-6 rounded-2xl bg-white/5 border border-white/15 text-white placeholder:text-white/35 px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-laro/50"
                rows={2}
              />

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <Button
                  onClick={() => handleFeedback('yes')}
                  className="rounded-2xl h-14 bg-emerald-600 hover:bg-emerald-500 text-white text-base"
                >
                  <ThumbsUp className="w-5 h-5 mr-2" />
                  {t('yes')}
                </Button>
                <Button
                  onClick={() => handleFeedback('meh')}
                  variant="outline"
                  className="rounded-2xl h-14 border-white/20 bg-white/5 text-white hover:bg-white/10 text-base"
                >
                  <Meh className="w-5 h-5 mr-2" />
                  {t('meh')}
                </Button>
                <Button
                  onClick={() => handleFeedback('no')}
                  variant="outline"
                  className="rounded-2xl h-14 border-red-400/40 text-red-300 hover:bg-red-500/10 text-base"
                >
                  <ThumbsDown className="w-5 h-5 mr-2" />
                  {t('no')}
                </Button>
              </div>

              <Button
                variant="ghost"
                onClick={handleSkipWithNote}
                className="mt-6 text-white/45 hover:text-white"
                data-testid="cook-mode-finish-to-recipe"
              >
                {cookNote.trim() ? t('saveNoteBackToRecipe') : t('backToRecipe')}
              </Button>
            </motion.div>
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
};
