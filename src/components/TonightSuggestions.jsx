import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { cookingApi } from '../lib/api';
import { getImageUrl } from '../lib/utils';
import { Button } from './ui/button';
import {
  Clock,
  Flame,
  ChefHat,
  Sparkles,
  RefreshCw,
  ArrowRight,
  Loader2
} from 'lucide-react';

export const TonightSuggestions = () => {
  const navigate = useNavigate();
  const [suggestions, setSuggestions] = useState([]);
  const [plannedRecipe, setPlannedRecipe] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadSuggestions();
  }, []);

  const loadSuggestions = async () => {
    try {
      const res = await cookingApi.getTonightSuggestions();
      if (res.data?.planned) {
        setPlannedRecipe(res.data.recipe);
        setSuggestions([]);
      } else {
        setPlannedRecipe(null);
        setSuggestions(res.data?.suggestions || []);
      }
    } catch (error) {
      console.error('Failed to load suggestions:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    loadSuggestions();
  };

  const getEffortColor = (effort) => {
    switch (effort) {
      case 'Low': return 'text-green-600 bg-green-50 border-green-200 dark:text-green-300 dark:bg-green-500/25 dark:border-green-500/40';
      case 'Medium': return 'text-amber-600 bg-amber-50 border-amber-200 dark:text-amber-300 dark:bg-amber-500/25 dark:border-amber-500/40';
      case 'High': return 'text-red-600 bg-red-50 border-red-200 dark:text-red-300 dark:bg-red-500/25 dark:border-red-500/40';
      default: return 'text-gray-600 bg-gray-50 border-gray-200 dark:text-gray-300 dark:bg-white/10 dark:border-white/20';
    }
  };

  const formatTime = (minutes) => {
    if (!minutes) return '?';
    if (minutes < 60) return `${minutes}m`;
    const hrs = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return mins ? `${hrs}h ${mins}m` : `${hrs}h`;
  };

  const RecipeRow = ({ recipe, highlight = false }) => (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`bg-white dark:bg-card rounded-[12px] p-3 sm:p-4 shadow-soft min-w-0 overflow-hidden hover:shadow-md transition-all cursor-pointer group ${
        highlight ? 'border-2 border-laro/30' : 'border-border/60'
      }`}
      onClick={() => navigate(`/recipes/${recipe.id}`)}
    >
      <div className="flex items-center gap-3 sm:gap-4 min-w-0">
        <div className="w-14 h-14 sm:w-20 sm:h-20 rounded-lg bg-cream-subtle flex-shrink-0 overflow-hidden">
          <img
            src={getImageUrl(recipe.image_url, recipe)}
            alt={recipe.title}
            loading="lazy"
            decoding="async"
            className="w-full h-full object-cover"
          />
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="font-heading font-semibold text-base sm:text-lg leading-snug line-clamp-2 group-hover:text-laro transition-colors">
            {recipe.title}
          </h3>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5 mt-1.5 sm:mt-2">
            <span className="inline-flex items-center gap-1 text-xs sm:text-sm text-muted-foreground">
              <Clock className="w-3.5 h-3.5 sm:w-4 sm:h-4 shrink-0" />
              {formatTime(recipe.total_time)}
            </span>
            {recipe.effort && (
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] sm:text-xs font-medium border ${getEffortColor(recipe.effort)}`}>
                <Flame className="w-3 h-3 shrink-0" />
                {recipe.effort}
              </span>
            )}
            <span className="text-[11px] sm:text-xs text-muted-foreground hidden xs:inline sm:inline">
              {recipe.ingredients?.length || '?'} ingredients
            </span>
          </div>
        </div>

        <ArrowRight className="w-4 h-4 sm:w-5 sm:h-5 text-muted-foreground shrink-0 group-hover:text-laro group-hover:translate-x-0.5 transition-all" />
      </div>
    </motion.div>
  );

  if (loading) {
    return (
      <div className="bg-cream-subtle rounded-[12px] shadow-card p-4 sm:p-8 w-full max-w-full overflow-hidden">
        <div className="flex items-center justify-center py-10 sm:py-12">
          <Loader2 className="w-8 h-8 animate-spin text-laro" />
        </div>
      </div>
    );
  }

  if (plannedRecipe) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-cream-subtle rounded-[12px] shadow-card p-4 sm:p-6 md:p-8 w-full max-w-full overflow-hidden"
      >
        <div className="mb-4 sm:mb-6 min-w-0">
          <h2 className="font-heading text-xl sm:text-2xl font-bold flex items-center gap-2 min-w-0">
            <ChefHat className="w-5 h-5 sm:w-6 sm:h-6 text-laro shrink-0" />
            <span className="truncate">Tonight&apos;s Dinner</span>
          </h2>
          <p className="text-sm sm:text-base text-muted-foreground mt-1">
            You&apos;ve got this planned!
          </p>
        </div>

        <RecipeRow recipe={plannedRecipe} highlight />

        <p className="text-center text-xs sm:text-sm text-muted-foreground mt-4 sm:mt-6 px-2">
          Tap to start cooking
        </p>
      </motion.div>
    );
  }

  if (suggestions.length === 0) {
    return (
      <div className="bg-cream-subtle rounded-[12px] shadow-card p-4 sm:p-8 w-full max-w-full overflow-hidden">
        <div className="text-center py-6 sm:py-8 px-1">
          <ChefHat className="w-10 h-10 sm:w-12 sm:h-12 mx-auto text-muted-foreground mb-3 sm:mb-4" />
          <h3 className="font-heading text-lg sm:text-xl font-semibold mb-2">No recipes yet</h3>
          <p className="text-sm sm:text-base text-muted-foreground mb-4 max-w-sm mx-auto">
            Add some recipes to get personalized suggestions
          </p>
          <Button onClick={() => navigate('/recipes/new')} className="rounded-full">
            Add Your First Recipe
          </Button>
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-cream-subtle rounded-[12px] shadow-card p-4 sm:p-6 md:p-8 w-full max-w-full overflow-hidden"
      data-testid="tonight-suggestions"
    >
      <div className="flex items-start justify-between gap-2 mb-4 sm:mb-6 min-w-0">
        <div className="min-w-0 flex-1">
          <h2 className="font-heading text-xl sm:text-2xl font-bold flex items-start gap-2 min-w-0">
            <Sparkles className="w-5 h-5 sm:w-6 sm:h-6 text-amber-500 shrink-0 mt-0.5" />
            <span className="leading-snug break-words">What can I cook tonight?</span>
          </h2>
          <p className="text-sm sm:text-base text-muted-foreground mt-1">
            Quick picks based on what you love
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded-full shrink-0 h-9 w-9 p-0"
          aria-label="Refresh suggestions"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      <div className="grid gap-3 sm:gap-4 min-w-0">
        {suggestions.map((recipe, index) => (
          <motion.div
            key={recipe.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.05 }}
          >
            <RecipeRow recipe={recipe} />
          </motion.div>
        ))}
      </div>

      <p className="text-center text-xs sm:text-sm text-muted-foreground mt-4 sm:mt-6 px-1 leading-relaxed">
        Tap a recipe to start cooking · We&apos;ll ask if you&apos;d make it again
      </p>
    </motion.div>
  );
};
