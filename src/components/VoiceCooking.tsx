import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from './ui/button';
import { voiceApi } from '../lib/api';
import {
  Volume2,
  VolumeX,
  Mic,
  MicOff,
  Settings,
  Play,
  Pause,
  SkipForward,
  SkipBack,
  HelpCircle,
  Loader2
} from 'lucide-react';
import { toast } from 'sonner';

// Voice synthesis helper
const speak = (text, lang = 'en-US', rate = 1.0) => {
  return new Promise((resolve, reject) => {
    if (!window.speechSynthesis) {
      reject(new Error('Speech synthesis not supported'));
      return;
    }
    
    // Cancel any ongoing speech
    window.speechSynthesis.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.rate = rate;
    utterance.onend = resolve;
    utterance.onerror = reject;
    
    window.speechSynthesis.speak(utterance);
  });
};

// Voice recognition helper
const createRecognition = (lang = 'en-US') => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return null;
  
  const recognition = new SpeechRecognition();
  recognition.lang = lang;
  recognition.continuous = false;
  recognition.interimResults = false;
  
  return recognition;
};

export const VoiceCookingControls = ({
  recipe,
  currentStep,
  totalSteps,
  onNavigate,
  onTimerStart,
  onTimerStop,
  timerActive
}) => {
  const [settings, setSettings] = useState({
    enabled: true,
    auto_read_steps: true,
    voice_language: 'en-US',
    speech_rate: 1.0,
    voice_commands_enabled: true
  });
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [recognition, setRecognition] = useState(null);

  // Load settings
  useEffect(() => {
    loadSettings();
  }, []);

  // Initialize speech recognition
  useEffect(() => {
    if (settings.voice_commands_enabled) {
      const recog = createRecognition(settings.voice_language);
      setRecognition(recog);
    }
  }, [settings.voice_language, settings.voice_commands_enabled]);

  // Auto-read step when it changes
  useEffect(() => {
    if (settings.enabled && settings.auto_read_steps && recipe?.instructions?.[currentStep]) {
      readCurrentStep();
    }
  }, [currentStep, settings.enabled, settings.auto_read_steps]);

  const loadSettings = async () => {
    try {
      const res = await voiceApi.getSettings();
      setSettings(prev => ({ ...prev, ...res.data }));
    } catch (err) {
      console.log('Using default voice settings');
    }
  };

  const readCurrentStep = async () => {
    if (!recipe?.instructions?.[currentStep]) return;
    
    const text = `Step ${currentStep + 1} of ${totalSteps}. ${recipe.instructions[currentStep]}`;
    setIsSpeaking(true);
    
    try {
      await speak(text, settings.voice_language, settings.speech_rate);
    } catch (err) {
      console.error('Speech error:', err);
    } finally {
      setIsSpeaking(false);
    }
  };

  const stopSpeaking = () => {
    window.speechSynthesis?.cancel();
    setIsSpeaking(false);
  };

  const readIngredients = async () => {
    if (!recipe?.ingredients) return;
    
    const ingredientList = recipe.ingredients.map(ing => {
      if (typeof ing === 'object') {
        return `${ing.amount || ''} ${ing.unit || ''} ${ing.name}`.trim();
      }
      return ing;
    }).join('. ');
    
    const text = `Here are the ingredients: ${ingredientList}`;
    setIsSpeaking(true);
    
    try {
      await speak(text, settings.voice_language, settings.speech_rate);
    } catch (err) {
      console.error('Speech error:', err);
    } finally {
      setIsSpeaking(false);
    }
  };

  const startListening = () => {
    if (!recognition) {
      toast.error('Voice commands not supported in this browser');
      return;
    }

    recognition.onresult = async (event) => {
      const command = event.results[0][0].transcript;
      setIsListening(false);
      
      try {
        const res = await voiceApi.processCommand(command, recipe?.id, currentStep);
        
        if (res.data.understood) {
          const action = res.data.action;
          
          if (action?.type === 'navigate') {
            if (action.direction === 'next') onNavigate(1);
            else if (action.direction === 'previous') onNavigate(-1);
            else if (action.step !== undefined) onNavigate(action.step === -1 ? totalSteps - 1 - currentStep : -currentStep);
          } else if (action?.type === 'repeat') {
            readCurrentStep();
          } else if (action?.type === 'show_ingredients') {
            readIngredients();
          } else if (action?.type === 'timer') {
            if (action.operation === 'start') onTimerStart?.();
            else if (action.operation === 'stop') onTimerStop?.();
          } else if (action?.type === 'help') {
            setShowHelp(true);
          }
          
          if (res.data.response && res.data.speak) {
            speak(res.data.response, settings.voice_language, settings.speech_rate);
          }
        } else {
          speak(res.data.response, settings.voice_language, settings.speech_rate);
        }
      } catch (err) {
        toast.error('Could not process voice command');
      }
    };

    recognition.onerror = (event) => {
      setIsListening(false);
      if (event.error !== 'no-speech') {
        toast.error('Voice recognition error');
      }
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    setIsListening(true);
    recognition.start();
  };

  const stopListening = () => {
    recognition?.stop();
    setIsListening(false);
  };

  if (!settings.enabled) return null;

  return (
    <>
      {/* Voice Controls Bar */}
      <div className="flex items-center justify-center gap-2 p-2 bg-gray-800/50 rounded-full" data-testid="voice-controls">
        {/* Read/Stop Button */}
        <Button
          variant="ghost"
          size="icon"
          onClick={isSpeaking ? stopSpeaking : readCurrentStep}
          className="text-white hover:bg-gray-700 rounded-full h-10 w-10"
          title={isSpeaking ? 'Stop reading' : 'Read step'}
        >
          {isSpeaking ? (
            <VolumeX className="w-5 h-5" />
          ) : (
            <Volume2 className="w-5 h-5" />
          )}
        </Button>

        {/* Voice Command Button */}
        {settings.voice_commands_enabled && (
          <Button
            variant="ghost"
            size="icon"
            onClick={isListening ? stopListening : startListening}
            className={`rounded-full h-10 w-10 ${
              isListening 
                ? 'bg-coral text-white animate-pulse' 
                : 'text-white hover:bg-gray-700'
            }`}
            title={isListening ? 'Stop listening' : 'Voice command'}
          >
            {isListening ? (
              <Mic className="w-5 h-5" />
            ) : (
              <MicOff className="w-5 h-5" />
            )}
          </Button>
        )}

        {/* Help Button */}
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

      {/* Help Panel */}
      <AnimatePresence>
        {showHelp && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="absolute bottom-full mb-2 left-1/2 transform -translate-x-1/2 bg-gray-800 rounded-xl p-4 shadow-xl border border-gray-700 w-72"
          >
            <h4 className="font-medium text-white mb-2 flex items-center gap-2">
              <Mic className="w-4 h-4 text-mise" />
              Voice Commands
            </h4>
            <ul className="text-sm text-gray-300 space-y-1">
              <li><span className="text-mise">"Next"</span> - Go to next step</li>
              <li><span className="text-mise">"Previous"</span> - Go back</li>
              <li><span className="text-mise">"Repeat"</span> - Read again</li>
              <li><span className="text-mise">"Ingredients"</span> - List ingredients</li>
              <li><span className="text-mise">"Start timer"</span> - Start timer</li>
              <li><span className="text-mise">"Stop timer"</span> - Stop timer</li>
            </ul>
            <p className="text-xs text-gray-500 mt-2">
              Tap the microphone and speak clearly
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

// Compact voice button for mobile
export const VoiceButton = ({ onClick, isSpeaking }) => (
  <Button
    variant="ghost"
    size="icon"
    onClick={onClick}
    className="text-white hover:bg-gray-700 rounded-full"
  >
    {isSpeaking ? (
      <VolumeX className="w-5 h-5" />
    ) : (
      <Volume2 className="w-5 h-5" />
    )}
  </Button>
);
