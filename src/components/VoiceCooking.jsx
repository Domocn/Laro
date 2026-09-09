import React, { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from './ui/button';
import { voiceApi } from '../lib/api';
import { enrichStepWithAmounts } from '../lib/cookModeSteps';
import {
  getHandsFreePreference,
  matchLocalVoiceCommand,
  setHandsFreePreference,
} from '../lib/voiceCommands';
import {
  Volume2,
  VolumeX,
  Mic,
  MicOff,
  HelpCircle,
  Ear,
} from 'lucide-react';
import { toast } from 'sonner';

const speak = (text, lang = 'en-US', rate = 1.0) => {
  return new Promise((resolve, reject) => {
    if (!window.speechSynthesis) {
      reject(new Error('Speech synthesis not supported'));
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.rate = rate;
    utterance.onend = resolve;
    utterance.onerror = reject;
    window.speechSynthesis.speak(utterance);
  });
};

const createRecognition = (lang = 'en-US', { continuous = false } = {}) => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return null;
  const recognition = new SpeechRecognition();
  recognition.lang = lang;
  recognition.continuous = continuous;
  recognition.interimResults = false;
  recognition.maxAlternatives = 3;
  return recognition;
};

export { matchLocalVoiceCommand } from '../lib/voiceCommands';

export const VoiceCookingControls = ({
  recipe,
  currentStep,
  totalSteps,
  steps,
  onNavigate,
  onTimerStart,
  onTimerStop,
  timerActive,
}) => {
  const [settings, setSettings] = useState({
    enabled: true,
    auto_read_steps: true,
    voice_language: 'en-US',
    speech_rate: 1.0,
    voice_commands_enabled: true,
  });
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [handsFree, setHandsFree] = useState(false);
  const [needsGesture, setNeedsGesture] = useState(() => getHandsFreePreference());
  const [showHelp, setShowHelp] = useState(false);
  const recognitionRef = useRef(null);
  const handsFreeRef = useRef(false);
  const speakingRef = useRef(false);
  const processingRef = useRef(false);
  const stepRef = useRef(currentStep);
  const startListeningRef = useRef(() => {});

  stepRef.current = currentStep;
  handsFreeRef.current = handsFree;

  useEffect(() => {
    loadSettings();
  }, []);

  const getStepText = useCallback(
    (index) => {
      if (Array.isArray(steps) && steps[index]) return steps[index];
      const raw = recipe?.instructions?.[index];
      if (!raw) return '';
      return enrichStepWithAmounts(raw, recipe?.ingredients);
    },
    [steps, recipe]
  );

  const pauseMicForSpeech = useCallback(() => {
    speakingRef.current = true;
    try {
      recognitionRef.current?.stop();
    } catch {
      /* ignore */
    }
  }, []);

  const resumeMicAfterSpeech = useCallback(() => {
    speakingRef.current = false;
    if (handsFreeRef.current) {
      setTimeout(() => startListeningRef.current({ continuous: true }), 350);
    }
  }, []);

  const readCurrentStep = useCallback(async () => {
    const body = getStepText(currentStep);
    if (!body) return;
    const text = `Step ${currentStep + 1} of ${totalSteps}. ${body}`;
    setIsSpeaking(true);
    pauseMicForSpeech();
    try {
      await speak(text, settings.voice_language, settings.speech_rate);
    } catch (err) {
      console.error('Speech error:', err);
    } finally {
      setIsSpeaking(false);
      resumeMicAfterSpeech();
    }
  }, [
    currentStep,
    totalSteps,
    getStepText,
    settings.voice_language,
    settings.speech_rate,
    pauseMicForSpeech,
    resumeMicAfterSpeech,
  ]);

  useEffect(() => {
    if (settings.enabled && settings.auto_read_steps) {
      readCurrentStep();
    }
  }, [currentStep, settings.enabled, settings.auto_read_steps]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadSettings = async () => {
    try {
      const res = await voiceApi.getSettings();
      setSettings((prev) => ({ ...prev, ...res.data }));
    } catch {
      console.log('Using default voice settings');
    }
  };

  const stopSpeaking = () => {
    window.speechSynthesis?.cancel();
    setIsSpeaking(false);
    resumeMicAfterSpeech();
  };

  const readIngredients = async () => {
    if (!recipe?.ingredients) return;
    const ingredientList = recipe.ingredients
      .map((ing) => {
        if (typeof ing === 'object') {
          return `${ing.amount || ''} ${ing.unit || ''} ${ing.name}`.trim();
        }
        return ing;
      })
      .join('. ');
    const text = `Here are the ingredients: ${ingredientList}`;
    setIsSpeaking(true);
    pauseMicForSpeech();
    try {
      await speak(text, settings.voice_language, settings.speech_rate);
    } catch (err) {
      console.error('Speech error:', err);
    } finally {
      setIsSpeaking(false);
      resumeMicAfterSpeech();
    }
  };

  const applyAction = useCallback(
    async (action, spokenResponse, shouldSpeak) => {
      if (!action) return;
      if (action.type === 'navigate') {
        if (action.direction === 'next') onNavigate(1);
        else if (action.direction === 'previous') onNavigate(-1);
        else if (action.step !== undefined) {
          onNavigate(action.step === -1 ? totalSteps - 1 - currentStep : -currentStep);
        }
      } else if (action.type === 'repeat') {
        await readCurrentStep();
      } else if (action.type === 'show_ingredients') {
        await readIngredients();
      } else if (action.type === 'timer') {
        if (action.operation === 'start') onTimerStart?.();
        else if (action.operation === 'stop') onTimerStop?.();
      } else if (action.type === 'help') {
        setShowHelp(true);
      }
      if (spokenResponse && shouldSpeak) {
        pauseMicForSpeech();
        try {
          await speak(spokenResponse, settings.voice_language, settings.speech_rate);
        } catch {
          /* ignore */
        } finally {
          resumeMicAfterSpeech();
        }
      }
    },
    [
      onNavigate,
      onTimerStart,
      onTimerStop,
      totalSteps,
      currentStep,
      readCurrentStep,
      settings.voice_language,
      settings.speech_rate,
      pauseMicForSpeech,
      resumeMicAfterSpeech,
    ]
  );

  const handleTranscript = useCallback(
    async (command) => {
      if (processingRef.current || speakingRef.current) return;
      processingRef.current = true;
      try {
        const local = matchLocalVoiceCommand(command);
        if (local) {
          await applyAction(local, null, false);
          voiceApi.processCommand(command, recipe?.id, stepRef.current).catch(() => {});
          return;
        }
        const res = await voiceApi.processCommand(command, recipe?.id, stepRef.current);
        if (res.data.understood) {
          await applyAction(res.data.action, res.data.response, res.data.speak);
        } else if (res.data.response) {
          pauseMicForSpeech();
          try {
            await speak(res.data.response, settings.voice_language, settings.speech_rate);
          } finally {
            resumeMicAfterSpeech();
          }
        }
      } catch {
        toast.error('Could not process voice command (E-VC001)');
      } finally {
        processingRef.current = false;
      }
    },
    [
      applyAction,
      recipe?.id,
      settings.voice_language,
      settings.speech_rate,
      pauseMicForSpeech,
      resumeMicAfterSpeech,
    ]
  );

  const stopListening = useCallback(() => {
    try {
      recognitionRef.current?.stop();
    } catch {
      /* ignore */
    }
    setIsListening(false);
  }, []);

  const startListening = useCallback(
    (opts = { continuous: handsFreeRef.current }) => {
      if (!settings.voice_commands_enabled) return;
      if (speakingRef.current) return;

      const continuous = Boolean(opts.continuous);
      const recognition = createRecognition(settings.voice_language, { continuous });
      if (!recognition) {
        toast.error('Voice commands not supported in this browser');
        return;
      }

      try {
        recognitionRef.current?.abort?.();
        recognitionRef.current?.stop();
      } catch {
        /* ignore */
      }

      recognition.onresult = async (event) => {
        if (speakingRef.current) return;
        const result = event.results[event.results.length - 1];
        if (!result?.isFinal && continuous) return;
        const command = result?.[0]?.transcript;
        if (!command) return;
        if (!continuous) setIsListening(false);
        await handleTranscript(command);
      };

      recognition.onerror = (event) => {
        if (event.error === 'no-speech' || event.error === 'aborted') {
          if (!handsFreeRef.current) setIsListening(false);
          return;
        }
        if (event.error === 'not-allowed') {
          setIsListening(false);
          setHandsFree(false);
          handsFreeRef.current = false;
          setNeedsGesture(false);
          setHandsFreePreference(false);
          toast.error('Microphone permission denied — allow mic for hands-free');
          return;
        }
        setIsListening(false);
        if (handsFreeRef.current) {
          setTimeout(() => {
            if (handsFreeRef.current && !speakingRef.current) {
              startListeningRef.current({ continuous: true });
            }
          }, 500);
        } else {
          toast.error('Voice recognition error (E-VC002)');
        }
      };

      recognition.onend = () => {
        if (handsFreeRef.current && !speakingRef.current) {
          setTimeout(() => {
            if (handsFreeRef.current && !speakingRef.current) {
              try {
                recognition.start();
                setIsListening(true);
              } catch {
                startListeningRef.current({ continuous: true });
              }
            }
          }, 280);
          return;
        }
        if (!handsFreeRef.current) setIsListening(false);
      };

      recognitionRef.current = recognition;
      setIsListening(true);
      setNeedsGesture(false);
      try {
        recognition.start();
      } catch {
        setIsListening(false);
        toast.error('Could not start microphone');
      }
    },
    [handleTranscript, settings.voice_commands_enabled, settings.voice_language]
  );

  startListeningRef.current = startListening;

  const enableHandsFree = useCallback(() => {
    setHandsFree(true);
    handsFreeRef.current = true;
    setHandsFreePreference(true);
    setNeedsGesture(false);
    toast.success('Hands-free on — say “Next”, “Back”, or “Repeat”');
    startListening({ continuous: true });
  }, [startListening]);

  const disableHandsFree = useCallback(() => {
    setHandsFree(false);
    handsFreeRef.current = false;
    setHandsFreePreference(false);
    setNeedsGesture(false);
    stopListening();
    toast.message('Hands-free off');
  }, [stopListening]);

  const toggleHandsFree = () => {
    if (handsFree) disableHandsFree();
    else enableHandsFree();
  };

  useEffect(() => {
    return () => {
      handsFreeRef.current = false;
      try {
        recognitionRef.current?.stop();
      } catch {
        /* ignore */
      }
      window.speechSynthesis?.cancel();
    };
  }, []);

  if (!settings.enabled) return null;

  return (
    <>
      <AnimatePresence>
        {(handsFree || needsGesture) && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            className="mb-2 w-full max-w-lg mx-auto"
          >
            {needsGesture && !handsFree ? (
              <button
                type="button"
                onClick={enableHandsFree}
                className="w-full rounded-2xl bg-laro/20 border border-laro/50 px-4 py-3 text-left text-white"
                data-testid="hands-free-resume"
              >
                <div className="font-semibold flex items-center gap-2">
                  <Ear className="w-5 h-5 text-laro" />
                  Tap to start hands-free
                </div>
                <p className="text-xs text-white/70 mt-1">
                  Then say “Next”, “Back”, or “Repeat” — keep this phone nearby (screen can stay on).
                </p>
              </button>
            ) : (
              <div
                className="rounded-2xl bg-laro/15 border border-laro/40 px-4 py-2.5 text-white flex items-center justify-between gap-3"
                data-testid="hands-free-listening"
              >
                <div className="min-w-0">
                  <div className="font-medium text-sm flex items-center gap-2">
                    <span className="inline-block h-2 w-2 rounded-full bg-laro animate-pulse" />
                    Listening — say “Next”
                  </div>
                  <p className="text-xs text-white/65 truncate">Also: Back · Repeat · Start timer</p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={disableHandsFree}
                  className="shrink-0 text-white/90 hover:bg-white/10 h-9"
                >
                  Stop
                </Button>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex items-center justify-center gap-2 p-2 bg-gray-800/50 rounded-full flex-wrap" data-testid="voice-controls">
        <Button
          variant="ghost"
          size="icon"
          onClick={isSpeaking ? stopSpeaking : readCurrentStep}
          className="text-white hover:bg-gray-700 rounded-full h-10 w-10"
          title={isSpeaking ? 'Stop reading' : 'Read step'}
        >
          {isSpeaking ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
        </Button>

        {settings.voice_commands_enabled && (
          <>
            <Button
              variant="ghost"
              size="icon"
              onClick={isListening && !handsFree ? stopListening : () => startListening({ continuous: false })}
              className={`rounded-full h-10 w-10 ${
                isListening && !handsFree
                  ? 'bg-coral text-white animate-pulse'
                  : 'text-white hover:bg-gray-700'
              }`}
              title={isListening && !handsFree ? 'Stop listening' : 'Voice command (tap once)'}
              disabled={handsFree}
            >
              {isListening && !handsFree ? <Mic className="w-5 h-5" /> : <MicOff className="w-5 h-5" />}
            </Button>

            <Button
              variant={handsFree ? 'default' : 'ghost'}
              onClick={toggleHandsFree}
              className={`rounded-full h-10 px-3 gap-1.5 ${
                handsFree
                  ? 'bg-laro hover:bg-laro-dark text-white'
                  : 'text-white hover:bg-gray-700'
              }`}
              title={handsFree ? 'Stop hands-free' : 'Hands-free listening'}
              data-testid="voice-hands-free"
            >
              <Ear className="w-4 h-4" />
              <span className="text-sm font-medium">{handsFree ? 'Listening' : 'Hands-free'}</span>
            </Button>
          </>
        )}

        <Button
          variant="ghost"
          size="icon"
          onClick={() => setShowHelp(!showHelp)}
          className="text-white hover:bg-gray-700 rounded-full h-10 w-10"
          title="Voice commands help"
        >
          <HelpCircle className="w-5 h-5" />
        </Button>
      </div>

      <AnimatePresence>
        {showHelp && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="absolute bottom-full mb-2 left-1/2 transform -translate-x-1/2 bg-gray-800 rounded-xl p-4 shadow-xl border border-gray-700 w-80 z-20"
          >
            <h4 className="font-medium text-white mb-2 flex items-center gap-2">
              <Ear className="w-4 h-4 text-laro" />
              Hands-free cook mode
            </h4>
            <ol className="text-sm text-gray-300 space-y-1.5 list-decimal list-inside">
              <li>Tap <span className="text-laro">Hands-free</span> (allow microphone once).</li>
              <li>Leave this phone nearby with the screen on.</li>
              <li>Say <span className="text-laro">“Next”</span>, <span className="text-laro">“Back”</span>, or <span className="text-laro">“Repeat”</span>.</li>
            </ol>
            <p className="text-xs text-gray-500 mt-2">
              Google Home speakers can’t hear Laro commands — use this phone’s mic. Nest Hub / Chromecast can show the steps if Cast is set up.
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

export const VoiceButton = ({ onClick, isSpeaking }) => (
  <Button variant="ghost" size="icon" onClick={onClick} className="text-white hover:bg-gray-700 rounded-full">
    {isSpeaking ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
  </Button>
);
