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
        // Dinner is already planned
        setPlannedRecipe(res.data.recipe);
        setSuggestions([]);
      } else {
        // Show suggestions
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
      case 'Low': return 'text-green-600 bg-green-50 border-green-200';
      case 'Medium': return 'text-amber-600 bg-amber-50 border-amber-200';
      case 'High': return 'text-red-600 bg-red-50 border-red-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const formatTime = (minutes) => {
    if (!minutes) return '?';
    if (minutes < 60) return `${minutes}m`;
    const hrs = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return mins ? `${hrs}h ${mins}m` : `${hrs}h`;
  };

  if (loading) {
    return (
      <div className="bg-gradient-to-br from-mise/10 to-coral/10 rounded-2xl p-8">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-mise" />
        </div>
      </div>
    );
  }

  // If dinner is planned, show that
  if (plannedRecipe) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-gradient-to-br from-mise/10 to-coral/10 rounded-2xl p-6 sm:p-8"
      >
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="font-heading text-2xl font-bold flex items-center gap-2">
              <ChefHat className="w-6 h-6 text-mise" />
              Tonight's Dinner
            </h2>
            <p className="text-muted-foreground mt-1">
              You've got this planned!
            </p>
          </div>
        </div>

        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          className="bg-white rounded-xl p-4 border-2 border-mise/30 hover:shadow-md transition-all cursor-pointer group"
          onClick={() => navigate(`/recipes/${plannedRecipe.id}`)}
        >
          <div className="flex items-center gap-4">
            <div className="w-20 h-20 rounded-lg bg-cream-subtle flex-shrink-0 overflow-hidden">
              {plannedRecipe.image_url ? (
                <img
                  src={getImageUrl(plannedRecipe.image_url)}
                  alt={plannedRecipe.title}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <ChefHat className="w-8 h-8 text-muted-foreground/50" />
                </div>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-heading font-semibold text-lg truncate group-hover:text-mise transition-colors">
                {plannedRecipe.title}
              </h3>
              <div className="flex items-center gap-3 mt-2">
                <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
                  <Clock className="w-4 h-4" />
                  {formatTime(plannedRecipe.total_time)}
                </span>
                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${getEffortColor(plannedRecipe.effort)}`}>
                  <Flame className="w-3 h-3" />
                  {plannedRecipe.effort}
                </span>
              </div>
            </div>
            <ArrowRight className="w-5 h-5 text-muted-foreground group-hover:text-mise group-hover:translate-x-1 transition-all" />
          </div>
        </motion.div>

        <p className="text-center text-sm text-muted-foreground mt-6">
          Tap to start cooking
        </p>
      </motion.div>
    );
  }

  if (suggestions.length === 0) {
    return (
      <div className="bg-gradient-to-br from-mise/10 to-coral/10 rounded-2xl p-8">
        <div className="text-center py-8">
          <ChefHat className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="font-heading text-xl font-semibold mb-2">No recipes yet</h3>
          <p className="text-muted-foreground mb-4">Add some recipes to get personalized suggestions</p>
          <Button onClick={() => navigate('/recipes/new')} className="rounded-full bg-mise hover:bg-mise-dark">
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
      className="bg-gradient-to-br from-mise/10 to-coral/10 rounded-2xl p-6 sm:p-8"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="font-heading text-2xl font-bold flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-amber-500" />
            What can I cook tonight?
          </h2>
          <p className="text-muted-foreground mt-1">
            Quick picks based on what you love
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
          className="rounded-full"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {/* Suggestions Grid */}
      <div className="grid gap-4">
        {suggestions.map((recipe, index) => (
          <motion.div
            key={recipe.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
            className="bg-white rounded-xl p-4 border border-border/60 hover:shadow-md transition-all cursor-pointer group"
            onClick={() => navigate(`/recipes/${recipe.id}`)}
          >
            <div className="flex items-center gap-4">
              {/* Recipe Image or Placeholder */}
              <div className="w-20 h-20 rounded-lg bg-cream-subtle flex-shrink-0 overflow-hidden">
                {recipe.image_url ? (
                  <img
                    src={getImageUrl(recipe.image_url)}
                    alt={recipe.title}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <ChefHat className="w-8 h-8 text-muted-foreground/50" />
                  </div>
                )}
              </div>

              {/* Recipe Info */}
              <div className="flex-1 min-w-0">
                <h3 className="font-heading font-semibold text-lg truncate group-hover:text-mise transition-colors">
                  {recipe.title}
                </h3>

                <div className="flex items-center gap-3 mt-2">
                  {/* Time */}
                  <span className="inline-flex items-center gap-1 text-sm text-muted-foreground">
                    <Clock className="w-4 h-4" />
                    {formatTime(recipe.total_time)}
                  </span>

                  {/* Effort */}
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${getEffortColor(recipe.effort)}`}>
                    <Flame className="w-3 h-3" />
                    {recipe.effort}
                  </span>

                  {/* Ingredient count hint */}
                  <span className="text-xs text-muted-foreground hidden sm:inline">
                    {recipe.ingredients?.length || '?'} ingredients
                  </span>
                </div>
              </div>

              {/* Arrow */}
              <ArrowRight className="w-5 h-5 text-muted-foreground group-hover:text-mise group-hover:translate-x-1 transition-all" />
            </div>
          </motion.div>
        ))}
      </div>

      {/* Cook Mode hint */}
      <p className="text-center text-sm text-muted-foreground mt-6">
        Tap a recipe to start cooking • We'll ask if you'd make it again
      </p>
    </motion.div>
  );
};
