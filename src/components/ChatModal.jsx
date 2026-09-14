import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { aiApi } from '../lib/api';
import { toastAiQuotaError, getAiQuotaErrorMessage } from '../lib/aiQuota';
import { toast } from 'sonner';
import {
  Sparkles,
  X,
  Send,
  Loader2,
  Lightbulb,
  RefreshCw,
  ChefHat,
  Minimize2,
  Maximize2,
  History,
  Plus,
  Trash2,
  Flag,
  ArrowLeft,
} from 'lucide-react';
import { ChatMarkdown } from './ChatMarkdown';
import { useChat } from '../context/ChatContext';

const WELCOME =
  "Hi! I'm Laro, your cooking assistant. Ask about recipes, techniques, substitutions, or meal ideas — I only answer food and cooking questions. For anything else, I'll point you to Google.";

const GENERIC_SUGGESTIONS = [
  'What can I make with chicken and rice?',
  'How do I properly sear a steak?',
  "What's a good substitute for eggs?",
  'Suggest a quick weeknight dinner',
];

const isGenericWelcome = (content) =>
  typeof content === 'string' && content.trim() === WELCOME.trim();

const makeWelcome = (recipe) => {
  const title = (recipe?.title || '').trim();
  if (title) {
    return {
      role: 'assistant',
      content: `Hi! You're looking at "${title}". Do you have a question about this recipe? I can help with steps, substitutions, timing, scaling, or technique.`,
      timestamp: new Date(),
      recipeScoped: true,
      recipeId: recipe?.id || null,
    };
  }
  return {
    role: 'assistant',
    content: WELCOME,
    timestamp: new Date(),
    recipeScoped: false,
  };
};

const recipeSuggestions = (title) => {
  const short = (title || 'this recipe').trim() || 'this recipe';
  return [
    `Do you have tips for ${short}?`,
    'What can I substitute in this recipe?',
    'How can I scale this recipe?',
    'Any timing tips for this recipe?',
  ];
};

export const ChatModal = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const { recipeContext } = useChat();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [sessionTitle, setSessionTitle] = useState('New chat');
  const [showHistory, setShowHistory] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);
  const [reporting, setReporting] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const suggestedQuestions = recipeContext?.title
    ? recipeSuggestions(recipeContext.title)
    : GENERIC_SUGGESTIONS;

  const startFresh = useCallback(() => {
    setSessionId(null);
    setSessionTitle('New chat');
    setMessages([makeWelcome(recipeContext)]);
    setShowHistory(false);
    setInput('');
  }, [recipeContext]);

  const loadSessions = useCallback(async () => {
    setSessionsLoading(true);
    try {
      const res = await aiApi.listChatSessions();
      setSessions(res.data?.sessions || []);
    } catch (error) {
      console.error('Failed to load chat history', error);
      toast.error(getAiQuotaErrorMessage(error, 'Could not load your chat history'));
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen && !isMinimized && !showHistory && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen, isMinimized, showHistory]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Opening chat (or landing on a recipe) with no real conversation yet →
  // greet and ask if they have a question about this recipe.
  useEffect(() => {
    if (!isOpen) return;
    setMessages((prev) => {
      const onlyWelcome =
        prev.length === 0 ||
        (prev.length === 1 &&
          prev[0]?.role === 'assistant' &&
          (prev[0]?.recipeScoped || isGenericWelcome(prev[0]?.content)));
      if (!onlyWelcome) return prev;
      const next = makeWelcome(recipeContext);
      if (
        prev.length === 1 &&
        prev[0]?.content === next.content &&
        !!prev[0]?.recipeScoped === !!next.recipeScoped
      ) {
        return prev;
      }
      return [next];
    });
  }, [isOpen, recipeContext?.id, recipeContext?.title]);

  const openHistory = async () => {
    setShowHistory(true);
    await loadSessions();
  };

  const loadSession = async (id) => {
    setLoading(true);
    try {
      const res = await aiApi.getChatSession(id);
      const data = res.data || {};
      setSessionId(data.id);
      setSessionTitle(data.title || 'Chat');
      const loaded = (data.messages || []).map((m) => ({
        role: m.role,
        content: m.content,
        timestamp: m.created_at ? new Date(m.created_at) : new Date(),
        id: m.id,
      }));
      setMessages(loaded.length ? loaded : [makeWelcome(recipeContext)]);
      setShowHistory(false);
    } catch (error) {
      toast.error(getAiQuotaErrorMessage(error, 'Could not open that chat'));
    } finally {
      setLoading(false);
    }
  };

  const deleteSession = async (id, e) => {
    e?.stopPropagation?.();
    try {
      await aiApi.deleteChatSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (sessionId === id) startFresh();
      toast.success('Chat deleted');
    } catch (error) {
      toast.error(getAiQuotaErrorMessage(error, 'Could not delete chat'));
    }
  };

  const reportBug = async () => {
    if (!sessionId) {
      toast.error('Send a message first so there is a transcript to report');
      return;
    }
    setReporting(true);
    try {
      const res = await aiApi.reportChatSession(sessionId, {
        subject: `AI chat bug: ${sessionTitle || 'conversation'}`,
        details: 'Reported from chat UI',
        platform: 'web',
      });
      const ticket =
        res.data?.ticket?.ticket_number || res.data?.ticket?.id || null;
      toast.success(
        ticket ? `Bug reported (${ticket})` : 'Bug reported with chat transcript'
      );
    } catch (error) {
      toast.error(getAiQuotaErrorMessage(error, 'Could not report this chat'));
    } finally {
      setReporting(false);
    }
  };

  const handleSend = async (question = input) => {
    if (!question.trim() || loading) return;

    const userMessage = { role: 'user', content: question, timestamp: new Date() };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const conversationHistory = messages.slice(-10).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await aiApi.chat(question, conversationHistory, sessionId, {
        recipe_id: recipeContext?.id,
        recipe_title: recipeContext?.title,
        recipe_description: recipeContext?.description,
        ingredients: recipeContext?.ingredients,
        instructions: recipeContext?.instructions,
      });
      const nextSessionId = response.data?.session_id || sessionId;
      if (nextSessionId && nextSessionId !== sessionId) {
        setSessionId(nextSessionId);
      }
      if (!sessionTitle || sessionTitle === 'New chat') {
        setSessionTitle(question.trim().slice(0, 80));
      }

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content:
            response.data.response ||
            response.data.answer ||
            "I'm not sure about that. Try asking another way!",
          timestamp: new Date(),
        },
      ]);
    } catch (error) {
      console.error('Chat error:', error);
      toastAiQuotaError(error, { navigate });
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: getAiQuotaErrorMessage(
            error,
            "Sorry, I couldn't answer that. Check AI is set up in Settings, then try again."
          ),
          timestamp: new Date(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (date) =>
    new Date(date).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

  const formatSessionDate = (value) => {
    if (!value) return '';
    try {
      return new Date(value).toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      });
    } catch {
      return '';
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="chat-modal"
          initial={{ opacity: 0, y: 24, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 16, scale: 0.98 }}
          transition={{ type: 'spring', damping: 28, stiffness: 320 }}
          className={`fixed z-50 flex flex-col overflow-hidden bg-white dark:bg-card border border-border/60 shadow-card
            bottom-20 right-4 left-4 sm:left-auto sm:bottom-6 sm:right-6 sm:w-[22rem]
            rounded-2xl
            ${isMinimized ? '' : 'h-[min(70vh,32rem)]'}`}
          data-testid="chat-modal"
          role="dialog"
          aria-label="Chat with Laro"
        >
          <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-border/60 bg-cream-subtle/80 dark:bg-muted/40">
            <div className="flex items-center gap-3 min-w-0">
              {showHistory ? (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setShowHistory(false)}
                  className="h-8 w-8 text-muted-foreground shrink-0"
                  title="Back to chat"
                  type="button"
                >
                  <ArrowLeft className="w-4 h-4" />
                </Button>
              ) : (
                <div className="w-9 h-9 rounded-full bg-laro flex items-center justify-center shrink-0 shadow-sm">
                  <ChefHat className="w-5 h-5 text-white" aria-hidden="true" />
                </div>
              )}
              <div className="min-w-0">
                <h3 className="font-heading font-semibold text-foreground text-sm truncate">
                  {showHistory ? 'Your chats' : sessionTitle || 'Chat with Laro'}
                </h3>
                <p className="text-xs text-muted-foreground truncate">
                  {showHistory ? 'Only you can see these' : 'Food & cooking only'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-0.5 shrink-0">
              {!showHistory && (
                <>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={openHistory}
                    className="h-8 w-8 text-muted-foreground"
                    title="Chat history"
                    type="button"
                    data-testid="chat-history-btn"
                  >
                    <History className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={startFresh}
                    className="h-8 w-8 text-muted-foreground"
                    title="New chat"
                    type="button"
                    data-testid="chat-new-btn"
                  >
                    <Plus className="w-4 h-4" />
                  </Button>
                  {sessionId && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={reportBug}
                      disabled={reporting}
                      className="h-8 w-8 text-muted-foreground"
                      title="Report bug with transcript"
                      type="button"
                    >
                      {reporting ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Flag className="w-4 h-4" />
                      )}
                    </Button>
                  )}
                  {messages.length > 1 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={startFresh}
                      className="h-8 w-8 text-muted-foreground"
                      title="Clear chat"
                      type="button"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </Button>
                  )}
                </>
              )}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsMinimized((v) => !v)}
                className="h-8 w-8 text-muted-foreground"
                title={isMinimized ? 'Expand' : 'Minimize'}
                type="button"
              >
                {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
                className="h-8 w-8 text-muted-foreground"
                title="Close"
                type="button"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {!isMinimized && showHistory && (
            <div
              className="flex-1 overflow-y-auto px-3 py-3 space-y-2 min-h-0 bg-cream/40 dark:bg-background"
              data-testid="chat-history-list"
            >
              <Button
                type="button"
                variant="outline"
                className="w-full justify-start gap-2 rounded-xl border-border/60"
                onClick={startFresh}
              >
                <Plus className="w-4 h-4" />
                Start a new chat
              </Button>
              {sessionsLoading && (
                <div className="flex items-center justify-center py-8 text-muted-foreground">
                  <Loader2 className="w-5 h-5 animate-spin" />
                </div>
              )}
              {!sessionsLoading && sessions.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-8 px-4">
                  No saved chats yet. Ask a cooking question and it will appear here — only for your account.
                </p>
              )}
              {!sessionsLoading &&
                sessions.map((s) => (
                  <div
                    key={s.id}
                    className={`group flex items-start gap-2 rounded-xl border border-border/50 bg-white dark:bg-muted/40 px-3 py-2.5 cursor-pointer hover:border-laro/40 transition-colors ${
                      sessionId === s.id ? 'border-laro/50 bg-laro-light/30' : ''
                    }`}
                    onClick={() => loadSession(s.id)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        loadSession(s.id);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    data-testid={`chat-session-${s.id}`}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-foreground truncate">
                        {s.title || 'New chat'}
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {formatSessionDate(s.updated_at || s.created_at)}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0 text-muted-foreground opacity-70 group-hover:opacity-100"
                      type="button"
                      title="Delete chat"
                      onClick={(e) => deleteSession(s.id, e)}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                ))}
            </div>
          )}

          {!isMinimized && !showHistory && (
            <>
              <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3 min-h-0 bg-cream/40 dark:bg-background">
                {messages.map((msg, i) => {
                  const isUser = msg.role === 'user';
                  return (
                    <motion.div
                      key={msg.id || `${msg.role}-${i}-${msg.timestamp?.valueOf?.() || i}`}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`flex items-end gap-2 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}
                    >
                      <div
                        className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                          isUser ? 'bg-laro text-white' : 'bg-laro-light text-laro'
                        }`}
                        aria-hidden="true"
                      >
                        {isUser ? (
                          <span className="text-[10px] font-semibold">You</span>
                        ) : (
                          <ChefHat className="w-3.5 h-3.5" />
                        )}
                      </div>
                      <div className={`max-w-[78%] flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
                        <div
                          className={`rounded-2xl px-3.5 py-2 ${
                            isUser
                              ? 'bg-laro text-white rounded-br-md'
                              : 'bg-white dark:bg-muted text-foreground border border-border/50 rounded-bl-md shadow-sm'
                          }`}
                        >
                          {isUser ? (
                            <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                              {msg.content}
                            </p>
                          ) : (
                            <ChatMarkdown content={msg.content} />
                          )}
                        </div>
                        {msg.timestamp && (
                          <p
                            className={`text-[10px] text-muted-foreground mt-1 px-1 ${
                              isUser ? 'text-right' : 'text-left'
                            }`}
                          >
                            {formatTime(msg.timestamp)}
                          </p>
                        )}
                      </div>
                    </motion.div>
                  );
                })}

                {loading && (
                  <div className="flex items-end gap-2">
                    <div className="w-7 h-7 rounded-full bg-laro-light text-laro flex items-center justify-center shrink-0">
                      <ChefHat className="w-3.5 h-3.5" />
                    </div>
                    <div className="bg-white dark:bg-muted border border-border/50 rounded-2xl rounded-bl-md px-3.5 py-2.5 shadow-sm">
                      <div className="flex gap-1">
                        <span className="w-1.5 h-1.5 bg-laro/70 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-1.5 h-1.5 bg-laro/70 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-1.5 h-1.5 bg-laro/70 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              {messages.length <= 2 && !loading && (
                <div className="px-3 pb-2 border-t border-border/40 bg-white dark:bg-card">
                  <p className="text-[11px] text-muted-foreground mb-1.5 mt-2 flex items-center gap-1">
                    <Lightbulb className="w-3 h-3" />
                    Try asking
                  </p>
                  <div className="flex flex-wrap gap-1.5 pb-1">
                    {suggestedQuestions.map((q, i) => (
                      <button
                        key={`suggestion-${i}`}
                        type="button"
                        onClick={() => handleSend(q)}
                        disabled={loading}
                        className="text-xs px-2.5 py-1 rounded-full bg-cream-subtle dark:bg-muted text-foreground/80 hover:bg-laro-light hover:text-laro transition-colors border border-border/40"
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <div className="p-3 border-t border-border/60 bg-white dark:bg-card">
                <div className="flex gap-2 items-center">
                  <Input
                    ref={inputRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask about food or cooking…"
                    className="flex-1 rounded-full bg-cream-subtle dark:bg-muted border-border/60 h-10"
                    disabled={loading}
                  />
                  <Button
                    onClick={() => handleSend()}
                    disabled={!input.trim() || loading}
                    className="rounded-full bg-laro hover:bg-laro-dark w-10 h-10 p-0 shrink-0"
                    type="button"
                    aria-label="Send message"
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
      )}
    </AnimatePresence>
  );
};

export const ChatButton = ({ onClick, className = '' }) => {
  return (
    <motion.button
      type="button"
      initial={{ scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      whileHover={{ scale: 1.04 }}
      whileTap={{ scale: 0.96 }}
      onClick={onClick}
      className={`fixed bottom-6 right-6 w-14 h-14 rounded-full bg-laro text-white shadow-lg flex items-center justify-center z-40 hover:bg-laro-dark hover:shadow-xl transition-colors ${className}`}
      data-testid="chat-button"
      aria-label="Chat with Laro"
    >
      <span className="relative flex items-center justify-center">
        <ChefHat className="w-6 h-6" />
        <span className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-white rounded-full border border-laro/20 flex items-center justify-center shadow-sm">
          <Sparkles className="w-2.5 h-2.5 text-laro" />
        </span>
      </span>
    </motion.button>
  );
};

export default ChatModal;
