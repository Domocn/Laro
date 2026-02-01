import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from './ui/button';
import { Input } from './ui/input';
import api from '../lib/api';
import {
  Sparkles,
  X,
  Send,
  Loader2,
  Lightbulb,
  RefreshCw,
  ChefHat,
  MessageCircle
} from 'lucide-react';
import { toast } from 'sonner';

export const CookingAIAssistant = ({ recipe, currentStep, isOpen, onClose }) => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const currentInstruction = recipe?.instructions?.[currentStep] || '';
  
  // Suggested questions based on context
  const suggestedQuestions = [
    `What can I substitute in this step?`,
    `How do I know when it's done?`,
    `What temperature should I use?`,
    `Any tips for this step?`,
    `Is there a shortcut for this?`,
  ];

  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Initialize with a welcome message
  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([{
        role: 'assistant',
        content: `Hi! I'm your cooking assistant. Ask me anything about "${recipe?.title}" or the current step. I can help with substitutions, techniques, timing, and more!`
      }]);
    }
  }, [isOpen, recipe?.title]);

  const handleSend = async (question = input) => {
    if (!question.trim() || loading) return;

    const userMessage = { role: 'user', content: question };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response = await api.post('/ai/cooking-assistant', {
        recipe_id: recipe?.id,
        recipe_title: recipe?.title,
        current_step: currentStep + 1,
        current_instruction: currentInstruction,
        ingredients: recipe?.ingredients?.map(i => 
          typeof i === 'object' ? `${i.amount} ${i.unit} ${i.name}` : i
        ),
        question: question
      });

      const assistantMessage = {
        role: 'assistant',
        content: response.data.answer || response.data.response || "I'm not sure about that. Try asking in a different way!"
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('AI Assistant error:', error);
      const errorMessage = {
        role: 'assistant',
        content: "Sorry, I couldn't process that. Make sure AI is configured in Settings → AI. Try asking again!"
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = () => {
    setMessages([{
      role: 'assistant',
      content: `Chat cleared! Ask me anything about "${recipe?.title}".`
    }]);
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 100 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 100 }}
        className="fixed bottom-0 right-0 left-0 md:left-auto md:right-4 md:bottom-4 md:w-96 bg-gray-900 rounded-t-2xl md:rounded-2xl shadow-2xl border border-gray-700 z-50 flex flex-col max-h-[70vh] md:max-h-[500px]"
        data-testid="cooking-ai-assistant"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-mise flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <div>
              <h3 className="font-medium text-white text-sm">AI Assistant</h3>
              <p className="text-xs text-gray-400">Step {currentStep + 1}</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              onClick={clearChat}
              className="text-gray-400 hover:text-white hover:bg-gray-800 h-8 w-8"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="text-gray-400 hover:text-white hover:bg-gray-800 h-8 w-8"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((msg, i) => (
            <motion.div
              key={`${msg.role}-${i}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`max-w-[85%] rounded-2xl px-4 py-2 ${
                msg.role === 'user'
                  ? 'bg-mise text-white'
                  : 'bg-gray-800 text-gray-100'
              }`}>
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              </div>
            </motion.div>
          ))}
          
          {loading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex justify-start"
            >
              <div className="bg-gray-800 rounded-2xl px-4 py-2">
                <Loader2 className="w-4 h-4 animate-spin text-mise" />
              </div>
            </motion.div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Suggestions */}
        {messages.length <= 2 && (
          <div className="px-4 pb-2">
            <p className="text-xs text-gray-500 mb-2 flex items-center gap-1">
              <Lightbulb className="w-3 h-3" />
              Quick questions
            </p>
            <div className="flex flex-wrap gap-1">
              {suggestedQuestions.slice(0, 3).map((q, i) => (
                <button
                  key={`suggestion-${i}`}
                  onClick={() => handleSend(q)}
                  disabled={loading}
                  className="text-xs px-2 py-1 rounded-full bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="p-3 border-t border-gray-700">
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask me anything..."
              className="flex-1 bg-gray-800 border-gray-700 text-white placeholder:text-gray-500 rounded-full"
              disabled={loading}
            />
            <Button
              onClick={() => handleSend()}
              disabled={!input.trim() || loading}
              className="rounded-full bg-mise hover:bg-mise-dark w-10 h-10 p-0"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
};

// Floating button to open AI assistant
export const AIAssistantButton = ({ onClick }) => {
  return (
    <motion.button
      initial={{ scale: 0 }}
      animate={{ scale: 1 }}
      whileHover={{ scale: 1.1 }}
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      className="fixed bottom-24 right-4 w-14 h-14 rounded-full bg-mise text-white shadow-lg flex items-center justify-center z-40 hover:bg-mise-dark transition-colors"
      data-testid="ai-assistant-button"
    >
      <MessageCircle className="w-6 h-6" />
      <span className="absolute -top-1 -right-1 w-4 h-4 bg-coral rounded-full flex items-center justify-center">
        <Sparkles className="w-2.5 h-2.5" />
      </span>
    </motion.button>
  );
};
