import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cookingApi } from '../lib/api';
import { useAccessibility } from '../context/AccessibilityContext';
import { Button } from './ui/button';
import { CookingAIAssistant, AIAssistantButton } from './CookingAIAssistant';
import { VoiceCookingControls } from './VoiceCooking';
import {
  X,
  ChevronLeft,
  ChevronRight,
  Clock,
  Play,
  Pause,
  RotateCcw,
  Check,
  ThumbsUp,
  ThumbsDown,
  Meh,
  Volume2,
  ChefHat,
  Sparkles
} from 'lucide-react';
import { toast } from 'sonner';

export const CookMode = ({ recipe, onClose }) => {
  const { highlightCurrentStep, showProgressIndicators, soundEffects } = useAccessibility();
  const [currentStep, setCurrentStep] = useState(0);
  const [sessionId, setSessionId] = useState(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [showAIAssistant, setShowAIAssistant] = useState(false);
  const [timers, setTimers] = useState({});
  const wakeLockRef = useRef(null);
  const timerIntervalRef = useRef({});

  // Request wake lock to keep screen on
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

    // Start cooking session
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
      // Release wake lock
      if (wakeLockRef.current) {
        wakeLockRef.current.release();
      }
      // Clear all timer intervals
      Object.values(timerIntervalRef.current).forEach(clearInterval);
    };
  }, [recipe.id]);

  // Parse time from step text (e.g., "cook for 10 minutes")
  const parseTimeFromStep = (step) => {
    const patterns = [
      /(\d+)\s*(?:minute|min|m)\b/i,
      /(\d+)\s*(?:hour|hr|h)\b/i,
      /(\d+)-(\d+)\s*(?:minute|min)/i,
    ];

    for (const pattern of patterns) {
      const match = step.match(pattern);
      if (match) {
        let minutes = parseInt(match[1]);
        if (pattern.toString().includes('hour')) {
          minutes *= 60;
        }
        return minutes * 60; // Return seconds
      }
    }
    return null;
  };

  // Start a timer for a step
  const startTimer = (stepIndex, seconds) => {
    if (timerIntervalRef.current[stepIndex]) {
      clearInterval(timerIntervalRef.current[stepIndex]);
    }

    setTimers(prev => ({ ...prev, [stepIndex]: { total: seconds, remaining: seconds, running: true } }));

    timerIntervalRef.current[stepIndex] = setInterval(() => {
      setTimers(prev => {
        const timer = prev[stepIndex];
        if (!timer || timer.remaining <= 0) {
          clearInterval(timerIntervalRef.current[stepIndex]);
          // Play sound when done
          playTimerSound();
          toast.success('Timer done!');
          return { ...prev, [stepIndex]: { ...timer, remaining: 0, running: false } };
        }
        return { ...prev, [stepIndex]: { ...timer, remaining: timer.remaining - 1 } };
      });
    }, 1000);
  };

  const pauseTimer = (stepIndex) => {
    clearInterval(timerIntervalRef.current[stepIndex]);
    setTimers(prev => ({ ...prev, [stepIndex]: { ...prev[stepIndex], running: false } }));
  };

  const resetTimer = (stepIndex, seconds) => {
    clearInterval(timerIntervalRef.current[stepIndex]);
    setTimers(prev => ({ ...prev, [stepIndex]: { total: seconds, remaining: seconds, running: false } }));
  };

  const playTimerSound = () => {
    if (!soundEffects) return; // Respect accessibility settings

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

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleNext = () => {
    if (currentStep < recipe.instructions.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      setShowFeedback(true);
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleFeedback = async (feedback) => {
    try {
      if (sessionId) {
        await cookingApi.completeSession(sessionId, feedback);
      } else {
        await cookingApi.submitFeedback(recipe.id, feedback);
      }

      const mesmises = {
        yes: "Great! We'll suggest this more often 👍",
        no: "Got it, we'll show this less 👎",
        meh: "Noted! Maybe with some tweaks next time"
      };
      toast.success(mesmises[feedback]);
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    }
    onClose();
  };

  const currentInstruction = recipe.instructions[currentStep];
  const stepTime = parseTimeFromStep(currentInstruction);
  const timer = timers[currentStep];

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black z-50 flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 bg-gray-900">
          <div className="flex items-center gap-3">
            <ChefHat className="w-6 h-6 text-mise" />
            <span className="font-heading font-semibold text-white truncate max-w-[200px]">
              {recipe.title}
            </span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="text-white hover:bg-gray-800 rounded-full"
          >
            <X className="w-6 h-6" />
          </Button>
        </div>

        {!showFeedback ? (
          <>
            {/* Ingredients sidebar (collapsed on mobile) */}
            <div className="bg-gray-900 border-b border-gray-800 p-4">
              <details className="text-gray-300">
                <summary className="cursor-pointer font-medium text-white mb-2">
                  Ingredients ({recipe.ingredients?.length || 0})
                </summary>
                <ul className="mt-3 space-y-1 text-sm max-h-32 overflow-y-auto">
                  {recipe.ingredients?.map((ing, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="text-mise">{ing.amount} {ing.unit}</span>
                      <span>{ing.name}</span>
                    </li>
                  ))}
                </ul>
              </details>
            </div>

            {/* Main content */}
            <div className="flex-1 flex flex-col items-center justify-center p-6 overflow-y-auto">
              {/* Step counter */}
              <div className="text-gray-400 mb-4">
                Step {currentStep + 1} of {recipe.instructions.length}
              </div>

              {/* Step progress dots */}
              <div className="flex gap-2 mb-8">
                {recipe.instructions.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setCurrentStep(i)}
                    className={`w-2 h-2 rounded-full transition-all ${
                      i === currentStep
                        ? 'w-8 bg-mise'
                        : i < currentStep
                        ? 'bg-mise/50'
                        : 'bg-gray-600'
                    }`}
                  />
                ))}
              </div>

              {/* Instruction */}
              <motion.div
                key={currentStep}
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -50 }}
                className={`text-center max-w-lg ${highlightCurrentStep ? 'step-highlighted' : ''}`}
              >
                {showProgressIndicators && (
                  <div className="flex items-center justify-center gap-2 mb-4">
                    <span className="step-counter current">{currentStep + 1}</span>
                    <span className="text-gray-400 text-sm">of {recipe.instructions.length}</span>
                  </div>
                )}
                <p className="text-white text-2xl sm:text-3xl font-light leading-relaxed">
                  {currentInstruction}
                </p>
              </motion.div>

              {/* Timer (if step has time) */}
              {stepTime && (
                <div className="mt-8 flex flex-col items-center">
                  <div className="text-5xl font-mono text-white mb-4">
                    {timer ? formatTime(timer.remaining) : formatTime(stepTime)}
                  </div>
                  <div className="flex gap-2">
                    {!timer || !timer.running ? (
                      <Button
                        onClick={() => startTimer(currentStep, timer?.remaining || stepTime)}
                        className="rounded-full bg-mise hover:bg-mise-dark"
                      >
                        <Play className="w-4 h-4 mr-2" />
                        Start Timer
                      </Button>
                    ) : (
                      <Button
                        onClick={() => pauseTimer(currentStep)}
                        variant="outline"
                        className="rounded-full text-white border-white/30 hover:bg-white/10"
                      >
                        <Pause className="w-4 h-4 mr-2" />
                        Pause
                      </Button>
                    )}
                    <Button
                      onClick={() => resetTimer(currentStep, stepTime)}
                      variant="ghost"
                      className="rounded-full text-gray-400 hover:text-white"
                    >
                      <RotateCcw className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}
            </div>

            {/* Navigation */}
            <div className="p-4 bg-gray-900 border-t border-gray-800">
              {/* Voice Controls */}
              <div className="flex justify-center mb-3">
                <VoiceCookingControls
                  recipe={recipe}
                  currentStep={currentStep}
                  totalSteps={recipe.instructions.length}
                  onNavigate={(delta) => {
                    if (delta > 0) handleNext();
                    else handlePrev();
                  }}
                  onTimerStart={() => stepTime && startTimer(currentStep, stepTime)}
                  onTimerStop={() => pauseTimer(currentStep)}
                  timerActive={timer?.running}
                />
              </div>
              
              <div className="flex items-center justify-between max-w-lg mx-auto">
                <Button
                  variant="ghost"
                  onClick={handlePrev}
                  disabled={currentStep === 0}
                  className="text-white hover:bg-gray-800 rounded-full"
                >
                  <ChevronLeft className="w-5 h-5 mr-1" />
                  Previous
                </Button>

                <Button
                  onClick={handleNext}
                  className="rounded-full bg-mise hover:bg-mise-dark px-8"
                >
                  {currentStep === recipe.instructions.length - 1 ? (
                    <>
                      Done
                      <Check className="w-5 h-5 ml-1" />
                    </>
                  ) : (
                    <>
                      Next
                      <ChevronRight className="w-5 h-5 ml-1" />
                    </>
                  )}
                </Button>
              </div>
            </div>

            {/* AI Assistant Button */}
            {!showAIAssistant && (
              <AIAssistantButton onClick={() => setShowAIAssistant(true)} />
            )}

            {/* AI Assistant Panel */}
            <CookingAIAssistant
              recipe={recipe}
              currentStep={currentStep}
              isOpen={showAIAssistant}
              onClose={() => setShowAIAssistant(false)}
            />
          </>
        ) : (
          /* Feedback screen */
          <div className="flex-1 flex flex-col items-center justify-center p-8">
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="text-center"
            >
              <ChefHat className="w-16 h-16 mx-auto text-mise mb-6" />
              <h2 className="text-3xl font-heading font-bold text-white mb-2">
                Nice work, chef!
              </h2>
              <p className="text-xl text-gray-300 mb-8">
                Would you cook this again?
              </p>

              <div className="flex flex-col sm:flex-row gap-4 justify-center">
                <Button
                  onClick={() => handleFeedback('yes')}
                  className="rounded-full bg-green-600 hover:bg-green-700 px-8 py-6 text-lg"
                >
                  <ThumbsUp className="w-6 h-6 mr-2" />
                  Yes!
                </Button>
                <Button
                  onClick={() => handleFeedback('meh')}
                  variant="outline"
                  className="rounded-full border-gray-500 text-white hover:bg-gray-800 px-8 py-6 text-lg"
                >
                  <Meh className="w-6 h-6 mr-2" />
                  Meh
                </Button>
                <Button
                  onClick={() => handleFeedback('no')}
                  variant="outline"
                  className="rounded-full border-red-500 text-red-400 hover:bg-red-500/10 px-8 py-6 text-lg"
                >
                  <ThumbsDown className="w-6 h-6 mr-2" />
                  No
                </Button>
              </div>

              <Button
                variant="ghost"
                onClick={onClose}
                className="mt-8 text-gray-400 hover:text-white"
              >
                Skip feedback
              </Button>
            </motion.div>
          </div>
        )}
      </motion.div>
    </AnimatePresence>
  );
};
