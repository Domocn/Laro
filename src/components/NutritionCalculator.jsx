import React, { useState, useEffect, useMemo } from 'react';
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
  const percentage = Math.min(((value || 0) / max) * 100, 100);
  
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <Icon className={`w-4 h-4 ${color}`} />
          {label}
        </span>
        <span className="font-medium">{value ?? 0}{unit}</span>
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

const CORE_MACRO_KEYS = ['calories', 'protein', 'carbs', 'fat'];

/** Build UI shape from recipe.nutrition (flat macros saved or API-estimated). */
function fromSavedNutrition(saved, servings = 1) {
  if (!saved) return null;
  const hasCore = CORE_MACRO_KEYS.some((k) => saved[k] != null && saved[k] !== '');
  if (!hasCore) return null;
  const per_serving = {
    calories: Number(saved.calories) || 0,
    protein: Number(saved.protein) || 0,
    carbs: Number(saved.carbs) || 0,
    fat: Number(saved.fat) || 0,
    fiber: Number(saved.fiber) || 0,
  };
  const estimated =
    !!saved.nutrition_estimated ||
    saved.nutrition_source === 'estimated' ||
    saved.nutrition_source === 'mixed';
  return {
    source: estimated ? 'estimated' : 'saved',
    per_serving,
    totals: Object.fromEntries(
      Object.entries(per_serving).map(([k, v]) => [k, Math.round(v * servings * 10) / 10])
    ),
    unknown_ingredients: [],
    servings,
  };
}

export const NutritionCalculator = ({
  recipeId,
  ingredients,
  servings = 1,
  savedNutrition,
  onSave,
}) => {
  const seeded = useMemo(
    () => fromSavedNutrition(savedNutrition, servings),
    [savedNutrition, servings]
  );
  const [nutrition, setNutrition] = useState(seeded);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Prefer macros already on the recipe (saved or API-estimated from ingredients)
    if (seeded) {
      setNutrition(seeded);
      setError(null);
      return;
    }
    // No macros yet — estimate once from ingredients so the section is not blank
    if (!ingredients?.length) return;
    calculateNutrition({ force: true });
    // Only re-run when seed/recipe identity changes — parent often remaps ingredients
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seeded, recipeId, servings]);

  const calculateNutrition = async ({ force = false } = {}) => {
    if (!force && seeded) {
      setNutrition(seeded);
      return;
    }
    if (!ingredients || ingredients.length === 0) {
      setError('No ingredients to calculate');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      let res;
      if (recipeId) {
        // recalculate=1 bypasses saved macros and uses the ingredient table
        res = await nutritionApi.getRecipeNutrition(recipeId, { recalculate: true });
      } else {
        res = await nutritionApi.calculate(ingredients, servings);
      }
      setNutrition({ ...res.data, source: res.data.source || 'estimated' });
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
      toast.error(err.response?.data?.detail || 'Couldn\'t save nutrition info. Please try again. (E-NC001)');
    } finally {
      setSaving(false);
    }
  };

  if (!ingredients || ingredients.length === 0) {
    return null;
  }

  const perServing = nutrition?.per_serving;
  const showFiber = perServing && (perServing.fiber != null && Number(perServing.fiber) > 0);

  return (
    <div className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden" data-testid="nutrition-calculator">
      {/* Header */}
      <button
        onClick={() => {
          const next = !expanded;
          setExpanded(next);
          if (next && !nutrition) {
            if (seeded) setNutrition(seeded);
            else calculateNutrition({ force: true });
          }
        }}
        className="w-full p-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Flame className="w-5 h-5 text-coral" />
          <span className="font-medium">Nutrition Facts</span>
          {perServing && (
            <span className="text-sm text-muted-foreground">
              ({perServing.calories} cal/serving)
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
                  <Loader2 className="w-6 h-6 animate-spin text-laro" />
                  <span className="ml-2 text-muted-foreground">Calculating...</span>
                </div>
              ) : error ? (
                <div className="flex items-center justify-center py-8 text-muted-foreground">
                  <AlertCircle className="w-5 h-5 mr-2" />
                  {error}
                </div>
              ) : nutrition && perServing ? (
                <div className="space-y-4 pt-4">
                  {/* Per Serving */}
                  <div className="text-center pb-3 border-b border-border/60">
                    <p className="text-sm text-muted-foreground">Per serving ({servings} servings total)</p>
                    <p className="text-3xl font-bold text-coral">{perServing.calories}</p>
                    <p className="text-sm text-muted-foreground">calories</p>
                    {nutrition.source === 'saved' && (
                      <p className="text-xs text-muted-foreground mt-1">From recipe macros</p>
                    )}
                    {nutrition.source === 'estimated' && (
                      <p className="text-xs text-muted-foreground mt-1">Estimated from ingredients</p>
                    )}
                  </div>

                  {/* Macros */}
                  <div className="space-y-3">
                    <NutritionBar
                      label="Protein"
                      value={perServing.protein}
                      unit="g"
                      color="text-coral"
                      icon={Beef}
                      max={50}
                    />
                    <NutritionBar
                      label="Carbs"
                      value={perServing.carbs}
                      unit="g"
                      color="text-tangerine"
                      icon={Wheat}
                      max={100}
                    />
                    <NutritionBar
                      label="Fat"
                      value={perServing.fat}
                      unit="g"
                      color="text-laro"
                      icon={Droplet}
                      max={50}
                    />
                    {showFiber && (
                      <NutritionBar
                        label="Fiber"
                        value={perServing.fiber}
                        unit="g"
                        color="text-teal"
                        icon={Leaf}
                        max={25}
                      />
                    )}
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
                      onClick={() => calculateNutrition({ force: true })}
                      className="flex-1 rounded-full"
                    >
                      <Calculator className="w-4 h-4 mr-2" />
                      Recalculate
                    </Button>
                    {recipeId && nutrition.source === 'estimated' && (
                      <Button
                        size="sm"
                        onClick={handleSave}
                        disabled={saving}
                        className="flex-1 rounded-full bg-laro hover:bg-laro-dark"
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
                    onClick={() => calculateNutrition({ force: true })}
                    className="rounded-full bg-laro hover:bg-laro-dark"
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
