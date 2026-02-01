import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from './ui/button';
import { nutritionApi } from '../lib/api';
import {
  Flame,
  Beef,
  Wheat,
  Droplet,
  Leaf,
  Calculator,
  Loader2,
  AlertCircle,
  Save,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { toast } from 'sonner';

const NutritionBar = ({ label, value, unit, color, icon: Icon, max = 100 }) => {
  const percentage = Math.min((value / max) * 100, 100);
  
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <Icon className={`w-4 h-4 ${color}`} />
          {label}
        </span>
        <span className="font-medium">{value}{unit}</span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className={`h-full rounded-full ${color.replace('text-', 'bg-')}`}
        />
      </div>
    </div>
  );
};

export const NutritionCalculator = ({ recipeId, ingredients, servings = 1, onSave }) => {
  const [nutrition, setNutrition] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState(null);

  const calculateNutrition = async () => {
    if (!ingredients || ingredients.length === 0) {
      setError('No ingredients to calculate');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      let res;
      if (recipeId) {
        res = await nutritionApi.getRecipeNutrition(recipeId);
      } else {
        res = await nutritionApi.calculate(ingredients, servings);
      }
      setNutrition(res.data);
    } catch (err) {
      setError('Failed to calculate nutrition');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!recipeId) return;
    
    setSaving(true);
    try {
      await nutritionApi.saveRecipeNutrition(recipeId);
      toast.success('Nutrition info saved to recipe');
      if (onSave) onSave(nutrition);
    } catch (err) {
      toast.error('Failed to save nutrition');
    } finally {
      setSaving(false);
    }
  };

  if (!ingredients || ingredients.length === 0) {
    return null;
  }

  return (
    <div className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden" data-testid="nutrition-calculator">
      {/* Header */}
      <button
        onClick={() => {
          setExpanded(!expanded);
          if (!expanded && !nutrition) {
            calculateNutrition();
          }
        }}
        className="w-full p-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Flame className="w-5 h-5 text-coral" />
          <span className="font-medium">Nutrition Facts</span>
          {nutrition && (
            <span className="text-sm text-muted-foreground">
              ({nutrition.per_serving.calories} cal/serving)
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="w-5 h-5 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-5 h-5 text-muted-foreground" />
        )}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="px-4 pb-4 border-t border-border/60">
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-mise" />
                  <span className="ml-2 text-muted-foreground">Calculating...</span>
                </div>
              ) : error ? (
                <div className="flex items-center justify-center py-8 text-muted-foreground">
                  <AlertCircle className="w-5 h-5 mr-2" />
                  {error}
                </div>
              ) : nutrition ? (
                <div className="space-y-4 pt-4">
                  {/* Per Serving */}
                  <div className="text-center pb-3 border-b border-border/60">
                    <p className="text-sm text-muted-foreground">Per serving ({servings} servings total)</p>
                    <p className="text-3xl font-bold text-coral">{nutrition.per_serving.calories}</p>
                    <p className="text-sm text-muted-foreground">calories</p>
                  </div>

                  {/* Macros */}
                  <div className="space-y-3">
                    <NutritionBar
                      label="Protein"
                      value={nutrition.per_serving.protein}
                      unit="g"
                      color="text-coral"
                      icon={Beef}
                      max={50}
                    />
                    <NutritionBar
                      label="Carbs"
                      value={nutrition.per_serving.carbs}
                      unit="g"
                      color="text-tangerine"
                      icon={Wheat}
                      max={100}
                    />
                    <NutritionBar
                      label="Fat"
                      value={nutrition.per_serving.fat}
                      unit="g"
                      color="text-mise"
                      icon={Droplet}
                      max={50}
                    />
                    <NutritionBar
                      label="Fiber"
                      value={nutrition.per_serving.fiber}
                      unit="g"
                      color="text-teal"
                      icon={Leaf}
                      max={25}
                    />
                  </div>

                  {/* Unknown Ingredients */}
                  {nutrition.unknown_ingredients?.length > 0 && (
                    <div className="mt-4 p-3 bg-amber-50 dark:bg-amber-900/20 rounded-xl text-sm">
                      <p className="font-medium text-amber-700 dark:text-amber-400 mb-1">
                        Some ingredients couldn't be calculated:
                      </p>
                      <ul className="text-amber-600 dark:text-amber-500 text-xs">
                        {nutrition.unknown_ingredients.map((ing, i) => (
                          <li key={`${ing}-${i}`}>• {ing}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={calculateNutrition}
                      className="flex-1 rounded-full"
                    >
                      <Calculator className="w-4 h-4 mr-2" />
                      Recalculate
                    </Button>
                    {recipeId && (
                      <Button
                        size="sm"
                        onClick={handleSave}
                        disabled={saving}
                        className="flex-1 rounded-full bg-mise hover:bg-mise-dark"
                      >
                        {saving ? (
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        ) : (
                          <Save className="w-4 h-4 mr-2" />
                        )}
                        Save to Recipe
                      </Button>
                    )}
                  </div>
                </div>
              ) : (
                <div className="py-8 text-center">
                  <Button
                    onClick={calculateNutrition}
                    className="rounded-full bg-mise hover:bg-mise-dark"
                  >
                    <Calculator className="w-4 h-4 mr-2" />
                    Calculate Nutrition
                  </Button>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// Compact version for recipe cards
export const NutritionBadge = ({ nutrition }) => {
  if (!nutrition?.per_serving) return null;

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span className="flex items-center gap-1">
        <Flame className="w-3 h-3 text-coral" />
        {nutrition.per_serving.calories} cal
      </span>
      <span className="flex items-center gap-1">
        <Beef className="w-3 h-3 text-coral" />
        {nutrition.per_serving.protein}g
      </span>
    </div>
  );
};
