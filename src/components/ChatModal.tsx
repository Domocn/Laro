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
  Minimize2,
  Maximize2
} from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface ChatModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ChatModal = ({ isOpen, onClose }: ChatModalProps) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const suggestedQuestions = [
    "What can I make with chicken and rice?",
    "How do I properly sear a steak?",
    "What's a good substitute for eggs?",
    "Suggest a quick weeknight dinner",
    "How long do I cook pasta?",
    "What goes well with salmon?"
  ];

  useEffect(() => {
    if (isOpen && !isMinimized && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen, isMinimized]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([{
        role: 'assistant',
        content: "Hi! I'm Laro, your AI cooking assistant. Ask me anything about recipes, cooking techniques, ingredient substitutions, meal planning, and more!",
        timestamp: new Date()
      }]);
    }
  }, [isOpen, messages.length]);

  const handleSend = async (question = input) => {
    if (!question.trim() || loading) return;

    const userMessage: Message = { role: 'user', content: question, timestamp: new Date() };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const conversationHistory = messages.slice(-10).map(m => ({
        role: m.role,
        content: m.content
      }));

      const response = await (api as any).post('/ai/chat', {
        message: question,
        history: conversationHistory
      });

      const assistantMessage: Message = {
        role: 'assistant',
        content: response.data.response || response.data.answer || "I'm not sure about that. Try asking in a different way!",
        timestamp: new Date()
      };
      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Chat error:', error);

      try {
        const fallbackResponse = await (api as any).post('/ai/cooking-assistant', {
          question: question
        });

        const assistantMessage: Message = {
          role: 'assistant',
          content: fallbackResponse.data.response || fallbackResponse.data.answer || "I'm not sure about that. Try asking in a different way!",
          timestamp: new Date()
        };
        setMessages(prev => [...prev, assistantMessage]);
      } catch (fallbackError) {
        const errorMessage: Message = {
          role: 'assistant',
          content: "Sorry, I couldn't process that request. Make sure AI is configured in Settings. Try again!",
          timestamp: new Date()
        };
        setMessages(prev => [...prev, errorMessage]);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = () => {
    setMessages([{
      role: 'assistant',
      content: "Chat cleared! How can I help you with cooking today?",
      timestamp: new Date()
    }]);
  };

  const formatTime = (date: Date) => {
    return new Date(date).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 100, scale: 0.9 }}
        animate={{
          opacity: 1,
          y: 0,
          scale: 1,
          height: isMinimized ? 'auto' : undefined
        }}
        exit={{ opacity: 0, y: 100, scale: 0.9 }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className={`fixed bottom-4 right-4 md:bottom-6 md:right-6 w-[calc(100vw-2rem)] md:w-96 bg-card rounded-2xl shadow-2xl border border-border z-50 flex flex-col ${
          isMinimized ? '' : 'h-[60vh] max-h-[500px] min-h-[400px]'
        }`}
        data-testid="chat-modal"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border rounded-t-2xl bg-gradient-to-r from-primary/10 to-secondary/10">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center shadow-lg">
              <span className="text-lg">🥑</span>
            </div>
            <div>
              <h3 className="font-semibold text-foreground">Chat with Laro</h3>
              <p className="text-xs text-muted-foreground">Your AI cooking assistant</p>
            </div>
          </div>
          <div className="flex items-center gap-1">
            {messages.length > 1 && (
              <Button
                variant="ghost"
                size="icon"
                onClick={clearChat}
                className="text-muted-foreground hover:text-foreground h-8 w-8"
                title="Clear chat"
              >
                <RefreshCw className="w-4 h-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setIsMinimized(!isMinimized)}
              className="text-muted-foreground hover:text-foreground h-8 w-8"
              title={isMinimized ? "Expand" : "Minimize"}
            >
              {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="text-muted-foreground hover:text-foreground h-8 w-8"
              title="Close"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {!isMinimized && (
          <>
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-[300px]">
              {messages.map((msg, i) => (
                <motion.div
                  key={`${msg.role}-${i}-${msg.timestamp.getTime()}`}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {msg.role === 'assistant' && (
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <span className="text-sm">🥑</span>
                    </div>
                  )}
                  <div className={`max-w-[80%] ${msg.role === 'user' ? 'order-first' : ''}`}>
                    <div className={`rounded-2xl px-4 py-2.5 ${
                      msg.role === 'user'
                        ? 'bg-primary text-primary-foreground rounded-br-md'
                        : 'bg-muted text-foreground rounded-bl-md'
                    }`}>
                      <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    </div>
                    <p className={`text-xs text-muted-foreground mt-1 ${msg.role === 'user' ? 'text-right' : ''}`}>
                      {formatTime(msg.timestamp)}
                    </p>
                  </div>
                  {msg.role === 'user' && (
                    <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0">
                      <span className="text-primary-foreground text-xs font-medium">You</span>
                    </div>
                  )}
                </motion.div>
              ))}

              {loading && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex gap-2 justify-start"
                >
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                    <span className="text-sm">🥑</span>
                  </div>
                  <div className="bg-muted rounded-2xl rounded-bl-md px-4 py-3">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-primary/40 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                      <span className="w-2 h-2 bg-primary/40 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                      <span className="w-2 h-2 bg-primary/40 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  </div>
                </motion.div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Suggestions */}
            {messages.length <= 2 && !loading && (
              <div className="px-4 pb-2">
                <p className="text-xs text-muted-foreground mb-2 flex items-center gap-1">
                  <Lightbulb className="w-3 h-3" />
                  Try asking
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {suggestedQuestions.slice(0, 4).map((q, i) => (
                    <button
                      key={`suggestion-${i}`}
                      onClick={() => handleSend(q)}
                      disabled={loading}
                      className="text-xs px-3 py-1.5 rounded-full bg-muted text-muted-foreground hover:bg-primary/10 hover:text-primary transition-colors border border-transparent hover:border-primary/20"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Input */}
            <div className="p-3 border-t border-border flex-shrink-0">
              <div className="flex gap-2">
                <Input
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask Laro anything..."
                  className="flex-1 rounded-full bg-muted border-border focus:border-primary"
                  disabled={loading}
                />
                <Button
                  onClick={() => handleSend()}
                  disabled={!input.trim() || loading}
                  className="rounded-full bg-primary hover:bg-primary/90 w-10 h-10 p-0 flex-shrink-0"
                >
                  {loading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Send className="w-4 h-4" />
                  )}
                </Button>
              </div>
            </div>
          </>
        )}
      </motion.div>
    </AnimatePresence>
  );
};

interface ChatButtonProps {
  onClick: () => void;
  className?: string;
}

export const ChatButton = ({ onClick, className = '' }: ChatButtonProps) => {
  return (
    <motion.button
      initial={{ scale: 0 }}
      animate={{ scale: 1 }}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      onClick={onClick}
      className={`fixed bottom-6 right-6 w-14 h-14 rounded-full bg-gradient-to-br from-primary to-secondary text-primary-foreground shadow-lg flex items-center justify-center z-40 hover:shadow-xl transition-shadow ${className}`}
      data-testid="chat-button"
      aria-label="Chat with Laro"
    >
      <div className="relative">
        <span className="text-2xl">🥑</span>
        <span className="absolute -top-1 -right-1 w-4 h-4 bg-green-400 rounded-full border-2 border-white flex items-center justify-center">
          <Sparkles className="w-2 h-2 text-white" />
        </span>
      </div>
    </motion.button>
  );
};

export default ChatModal;