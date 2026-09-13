import React, { createContext, useContext, useState, useCallback } from 'react';

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
    setRecipeContextState({
      id: ctx.id,
      title: ctx.title || '',
      description: ctx.description || '',
      ingredients: ctx.ingredients || [],
      instructions: ctx.instructions || [],
    });
  }, []);

  const clearRecipeContext = useCallback(() => {
    setRecipeContextState(null);
  }, []);

  return (
    <ChatContext.Provider
      value={{
        isChatOpen,
        openChat,
        closeChat,
        toggleChat,
        recipeContext,
        setRecipeContext,
        clearRecipeContext,
      }}
    >
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
