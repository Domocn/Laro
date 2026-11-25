import React, { createContext, useContext, useState, useCallback, useMemo } from 'react';

const ChatContext = createContext(null);

export const ChatProvider = ({ children }) => {
  const [isChatOpen, setIsChatOpen] = useState(false);
  /** Active recipe when the user is on a recipe page: { id, title, ... } */
  const [recipeContext, setRecipeContextState] = useState(null);

  const openChat = useCallback(() => {
    setIsChatOpen(true);
  }, []);

  const closeChat = useCallback(() => {
    setIsChatOpen(false);
  }, []);

  const toggleChat = useCallback(() => {
    setIsChatOpen((prev) => !prev);
  }, []);

  const setRecipeContext = useCallback((ctx) => {
    if (!ctx || !ctx.id) {
      setRecipeContextState(null);
      return;
    }
    setRecipeContextState((prev) => {
      // Avoid re-renders when the same recipe is set again with identical fields
      if (
        prev &&
        prev.id === ctx.id &&
        prev.title === (ctx.title || '') &&
        prev.description === (ctx.description || '')
      ) {
        return prev;
      }
      return {
        id: ctx.id,
        title: ctx.title || '',
        description: ctx.description || '',
        ingredients: ctx.ingredients || [],
        instructions: ctx.instructions || [],
      };
    });
  }, []);

  const clearRecipeContext = useCallback(() => {
    setRecipeContextState(null);
  }, []);

  const value = useMemo(
    () => ({
      isChatOpen,
      openChat,
      closeChat,
      toggleChat,
      recipeContext,
      setRecipeContext,
      clearRecipeContext,
    }),
    [
      isChatOpen,
      openChat,
      closeChat,
      toggleChat,
      recipeContext,
      setRecipeContext,
      clearRecipeContext,
    ]
  );

  return (
    <ChatContext.Provider value={value}>
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
};

export default ChatContext;
