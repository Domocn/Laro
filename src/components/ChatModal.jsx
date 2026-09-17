import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Button } from './ui/button';
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
  MoreVertical,
} from 'lucide-react';
import { ChatMarkdown } from './ChatMarkdown';
import { useChat } from '../context/ChatContext';
import { useTheme } from '../context/ThemeContext';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';

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
    `Tips for ${short}?`,
    'What can I substitute?',
    'How do I scale this?',
    'Any timing tips?',
  ];
};

export const ChatModal = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const { recipeContext } = useChat();
  const { reducedMotion } = useTheme();
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
  const panelRef = useRef(null);

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

  const resizeComposer = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 128)}px`;
  }, []);

  useEffect(() => {
    if (isOpen && !isMinimized && !showHistory && inputRef.current) {
      const t = setTimeout(() => {
        inputRef.current?.focus();
        resizeComposer();
      }, 80);
      return () => clearTimeout(t);
    }
  }, [isOpen, isMinimized, showHistory, resizeComposer]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: reducedMotion ? 'auto' : 'smooth',
    });
  }, [messages, loading, reducedMotion]);

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        if (showHistory) {
          setShowHistory(false);
        } else if (!isMinimized) {
          onClose();
        } else {
          setIsMinimized(false);
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, showHistory, isMinimized, onClose]);

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
    requestAnimationFrame(() => {
      if (inputRef.current) {
        inputRef.current.style.height = 'auto';
      }
    });

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

  const motionProps = reducedMotion
    ? { initial: false, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: 0 } }
    : {
        initial: { opacity: 0, y: 20, scale: 0.98 },
        animate: { opacity: 1, y: 0, scale: 1 },
        exit: { opacity: 0, y: 12, scale: 0.98 },
        transition: { type: 'spring', damping: 28, stiffness: 320 },
      };

  const headerTitle = showHistory
    ? 'Your chats'
    : sessionTitle && sessionTitle !== 'New chat'
      ? sessionTitle
      : 'Chat with Laro';

  const headerSubtitle = showHistory
    ? 'Only you can see these'
    : recipeContext?.title
      ? `About ${recipeContext.title}`
      : 'Food and cooking questions';

  const showWelcomePrompts = messages.length <= 2 && !loading;

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {!isMinimized && (
            <motion.button
              key="chat-backdrop"
              type="button"
              aria-label="Close chat"
              initial={reducedMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reducedMotion ? 0 : 0.15 }}
              className="fixed inset-0 z-40 bg-black/25 dark:bg-black/45"
              onClick={onClose}
            />
          )}
          <motion.div
            key="chat-modal"
            ref={panelRef}
            {...motionProps}
            className={`fixed z-50 flex flex-col overflow-hidden bg-white dark:bg-card border border-border/70 shadow-2xl
              left-3 right-3 sm:left-auto sm:right-6
              ${isMinimized
                ? 'bottom-[max(1.25rem,env(safe-area-inset-bottom))] sm:w-[22rem]'
                : 'bottom-[max(0.75rem,env(safe-area-inset-bottom))] sm:bottom-6 sm:w-[26rem] md:w-[28rem] h-[min(82dvh,40rem)]'
              }
              rounded-2xl`}
            data-testid="chat-modal"
            role="dialog"
            aria-modal={!isMinimized}
            aria-labelledby="laro-chat-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-2 px-3 py-2.5 border-b border-border/60 bg-cream-subtle/90 dark:bg-muted/40">
              <div className="flex items-center gap-2.5 min-w-0">
                {showHistory ? (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setShowHistory(false)}
                    className="h-9 w-9 text-muted-foreground shrink-0"
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
                  <h3
                    id="laro-chat-title"
                    className="font-heading font-semibold text-foreground text-sm truncate"
                  >
                    {headerTitle}
                  </h3>
                  <p className="text-xs text-muted-foreground truncate">{headerSubtitle}</p>
                </div>
              </div>
              <div className="flex items-center gap-0.5 shrink-0">
                {!showHistory && !isMinimized && (
                  <>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={openHistory}
                      className="h-9 w-9 text-muted-foreground"
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
                      className="h-9 w-9 text-muted-foreground"
                      title="New chat"
                      type="button"
                      data-testid="chat-new-btn"
                    >
                      <Plus className="w-4 h-4" />
                    </Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-9 w-9 text-muted-foreground"
                          title="More"
                          type="button"
                          aria-label="More chat actions"
                        >
                          <MoreVertical className="w-4 h-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-48">
                        <DropdownMenuItem
                          onClick={startFresh}
                          disabled={messages.length <= 1}
                        >
                          <RefreshCw className="w-4 h-4" />
                          Clear chat
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={reportBug} disabled={!sessionId || reporting}>
                          {reporting ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <Flag className="w-4 h-4" />
                          )}
                          Report a problem
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => setIsMinimized((v) => !v)}
                  className="h-9 w-9 text-muted-foreground"
                  title={isMinimized ? 'Expand' : 'Minimize'}
                  type="button"
                >
                  {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onClose}
                  className="h-9 w-9 text-muted-foreground"
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
                  className="w-full justify-start gap-2 rounded-xl border-border/60 h-11"
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
                        className="h-8 w-8 shrink-0 text-muted-foreground opacity-70 group-hover:opacity-100"
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
                  {recipeContext?.title && (
                    <div className="sticky top-0 z-[1] pb-1">
                      <p className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-laro-light/80 dark:bg-muted px-2.5 py-1 text-[11px] text-laro border border-laro/15">
                        <ChefHat className="w-3 h-3 shrink-0" aria-hidden="true" />
                        <span className="truncate">Helping with {recipeContext.title}</span>
                      </p>
                    </div>
                  )}
                  {messages.map((msg, i) => {
                    const isUser = msg.role === 'user';
                    const isLast = i === messages.length - 1;
                    return (
                      <motion.div
                        key={msg.id || `${msg.role}-${i}-${msg.timestamp?.valueOf?.() || i}`}
                        initial={reducedMotion ? false : { opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: reducedMotion ? 0 : 0.18 }}
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
                        <div className={`max-w-[82%] flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
                          <div
                            className={`rounded-2xl px-3.5 py-2.5 ${
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
                          {isLast && msg.timestamp && (
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
                    <div className="flex items-end gap-2" aria-live="polite" aria-label="Laro is typing">
                      <div className="w-7 h-7 rounded-full bg-laro-light text-laro flex items-center justify-center shrink-0">
                        <ChefHat className="w-3.5 h-3.5" />
                      </div>
                      <div className="bg-white dark:bg-muted border border-border/50 rounded-2xl rounded-bl-md px-3.5 py-2.5 shadow-sm">
                        <div className="flex gap-1">
                          <span
                            className={`w-1.5 h-1.5 bg-laro/70 rounded-full ${reducedMotion ? '' : 'animate-bounce'}`}
                            style={reducedMotion ? undefined : { animationDelay: '0ms' }}
                          />
                          <span
                            className={`w-1.5 h-1.5 bg-laro/70 rounded-full ${reducedMotion ? '' : 'animate-bounce'}`}
                            style={reducedMotion ? undefined : { animationDelay: '150ms' }}
                          />
                          <span
                            className={`w-1.5 h-1.5 bg-laro/70 rounded-full ${reducedMotion ? '' : 'animate-bounce'}`}
                            style={reducedMotion ? undefined : { animationDelay: '300ms' }}
                          />
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {showWelcomePrompts && (
                  <div className="px-3 pb-2 border-t border-border/40 bg-white dark:bg-card">
                    <p className="text-[11px] text-muted-foreground mb-1.5 mt-2 flex items-center gap-1">
                      <Lightbulb className="w-3 h-3" />
                      Try asking
                    </p>
                    <div className="grid grid-cols-1 gap-1.5 pb-1">
                      {suggestedQuestions.map((q, i) => (
                        <button
                          key={`suggestion-${i}`}
                          type="button"
                          onClick={() => handleSend(q)}
                          disabled={loading}
                          className="text-left text-xs px-3 py-2 rounded-xl bg-cream-subtle dark:bg-muted text-foreground/90 hover:bg-laro-light hover:text-laro transition-colors border border-border/40"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                <div className="p-3 border-t border-border/60 bg-white dark:bg-card">
                  <div className="flex gap-2 items-end">
                    <label htmlFor="laro-chat-input" className="sr-only">
                      Message Laro
                    </label>
                    <textarea
                      id="laro-chat-input"
                      ref={inputRef}
                      value={input}
                      rows={1}
                      onChange={(e) => {
                        setInput(e.target.value);
                        resizeComposer();
                      }}
                      onKeyDown={handleKeyDown}
                      placeholder="Ask about food or cooking…"
                      className="flex-1 resize-none rounded-2xl bg-cream-subtle dark:bg-muted border border-border/60 min-h-11 max-h-32 px-3.5 py-2.5 text-sm leading-5 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50"
                      disabled={loading}
                    />
                    <Button
                      onClick={() => handleSend()}
                      disabled={!input.trim() || loading}
                      className="rounded-full bg-laro hover:bg-laro-dark w-11 h-11 p-0 shrink-0"
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
                  <p className="text-[10px] text-muted-foreground mt-1.5 px-1">
                    Enter to send · Shift+Enter for a new line · Esc to close
                  </p>
                </div>
              </>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export const ChatButton = ({ onClick, className = '' }) => {
  const { reducedMotion } = useTheme();
  return (
    <motion.button
      type="button"
      initial={reducedMotion ? false : { scale: 0.9, opacity: 0 }}
      animate={{ scale: 1, opacity: 1 }}
      whileHover={reducedMotion ? undefined : { scale: 1.04 }}
      whileTap={reducedMotion ? undefined : { scale: 0.96 }}
      onClick={onClick}
      className={`fixed bottom-[max(1.5rem,env(safe-area-inset-bottom))] right-5 w-14 h-14 rounded-full bg-laro text-white shadow-lg flex items-center justify-center z-40 hover:bg-laro-dark hover:shadow-xl transition-colors ${className}`}
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
