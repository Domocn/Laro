import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from './ui/button';
import { costApi } from '../lib/api';
import {
  DollarSign,
  TrendingDown,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Loader2,
  Save,
  Calculator,
  ShoppingCart,
  AlertCircle
} from 'lucide-react';
import { toast } from 'sonner';

export const CostCalculator = ({ recipeId, servings = 1, onSave }) => {
  const [cost, setCost] = useState(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [error, setError] = useState(null);

  const calculateCost = async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await costApi.getRecipeCost(recipeId);
      setCost(res.data);
    } catch (err) {
      setError('Could not calculate cost');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await costApi.saveRecipeCost(recipeId);
      toast.success('Cost saved to recipe');
      if (onSave) onSave(cost);
    } catch (err) {
      toast.error('Could not save cost');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden" data-testid="cost-calculator">
      {/* Header */}
      <button
        onClick={() => {
          setExpanded(!expanded);
          if (!expanded && !cost) {
            calculateCost();
          }
        }}
        className="w-full p-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-sunny" />
          <span className="font-medium">Cost Estimate</span>
          {cost && (
            <span className="text-sm text-muted-foreground">
              (${cost.cost_per_serving}/serving)
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
              ) : cost ? (
                <div className="space-y-4 pt-4">
                  {/* Summary */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-center p-4 bg-sunny-light rounded-xl">
                      <p className="text-3xl font-bold text-sunny">${cost.total_cost}</p>
                      <p className="text-sm text-sunny-dark">Total Cost</p>
                    </div>
                    <div className="text-center p-4 bg-mise-light rounded-xl">
                      <p className="text-3xl font-bold text-mise">${cost.cost_per_serving}</p>
                      <p className="text-sm text-mise-dark">Per Serving</p>
                      <p className="text-xs text-muted-foreground">({cost.servings} servings)</p>
                    </div>
                  </div>

                  {/* Budget Rating */}
                  <div className="flex items-center justify-center gap-2 py-2">
                    {cost.cost_per_serving < 3 ? (
                      <>
                        <TrendingDown className="w-5 h-5 text-sunny" />
                        <span className="text-sm text-sunny font-medium">Budget-Friendly!</span>
                      </>
                    ) : cost.cost_per_serving < 8 ? (
                      <>
                        <DollarSign className="w-5 h-5 text-tangerine" />
                        <span className="text-sm text-tangerine font-medium">Moderate Cost</span>
                      </>
                    ) : (
                      <>
                        <TrendingUp className="w-5 h-5 text-coral" />
                        <span className="text-sm text-coral font-medium">Premium Recipe</span>
                      </>
                    )}
                  </div>

                  {/* Breakdown */}
                  {cost.breakdown?.length > 0 && (
                    <div>
                      <p className="text-sm font-medium mb-2">Cost Breakdown</p>
                      <div className="space-y-1 max-h-40 overflow-y-auto">
                        {cost.breakdown.map((item, i) => (
                          <div key={`${item.ingredient}-${i}`} className="flex items-center justify-between text-sm py-1 border-b border-border/30">
                            <span className="text-muted-foreground truncate flex-1">
                              {item.ingredient}
                            </span>
                            <span className="font-medium ml-2">${item.estimated_cost}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Unknown Ingredients */}
                  {cost.unknown_ingredients?.length > 0 && (
                    <div className="p-3 bg-amber-50 dark:bg-amber-900/20 rounded-xl text-sm">
                      <p className="font-medium text-amber-700 dark:text-amber-400 mb-1">
                        Couldn't price these ingredients:
                      </p>
                      <p className="text-amber-600 dark:text-amber-500 text-xs">
                        {cost.unknown_ingredients.join(', ')}
                      </p>
                    </div>
                  )}

                  {/* Actions */}
                  <div className="flex gap-2 pt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={calculateCost}
                      className="flex-1 rounded-full"
                    >
                      <Calculator className="w-4 h-4 mr-2" />
                      Recalculate
                    </Button>
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
                  </div>

                  <p className="text-xs text-center text-muted-foreground">
                    Prices are estimates based on average US grocery costs
                  </p>
                </div>
              ) : (
                <div className="py-8 text-center">
                  <Button
                    onClick={calculateCost}
                    className="rounded-full bg-mise hover:bg-mise-dark"
                  >
                    <Calculator className="w-4 h-4 mr-2" />
                    Calculate Cost
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

// Compact cost badge for recipe cards
export const CostBadge = ({ cost }) => {
  if (!cost?.per_serving) return null;

  return (
    <div className="flex items-center gap-1 text-xs">
      <DollarSign className="w-3 h-3 text-sunny" />
      <span className="text-muted-foreground">${cost.per_serving}/serving</span>
    </div>
  );
};
