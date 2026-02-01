import React, { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { recipeApi, mealPlanApi, aiApi, calendarApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Calendar } from '../components/ui/calendar';
import { useLiveRefreshContext, useLiveRefreshEvent, EventType } from '../hooks/useLiveRefresh';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';
import { MEAL_TYPES } from '../lib/utils';
import { 
  Plus, 
  Trash2, 
  Loader2,
  ChevronLeft,
  ChevronRight,
  UtensilsCrossed,
  Sparkles,
  Download,
  CalendarDays
} from 'lucide-react';
import { toast } from 'sonner';
import { format, startOfWeek, endOfWeek, addWeeks, subWeeks, eachDayOfInterval, isSameDay, addDays } from 'date-fns';

export const MealPlanner = () => {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [mealPlans, setMealPlans] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showAutoDialog, setShowAutoDialog] = useState(false);
  const [selectedDate, setSelectedDate] = useState(null);
  const [selectedMealType, setSelectedMealType] = useState('Dinner');
  const [selectedRecipe, setSelectedRecipe] = useState('');
  const [adding, setAdding] = useState(false);
  const [autoGenerating, setAutoGenerating] = useState(false);
  const [autoPreferences, setAutoPreferences] = useState('');
  const [exporting, setExporting] = useState(false);

  const weekStart = startOfWeek(currentDate, { weekStartsOn: 0 });
  const weekEnd = endOfWeek(currentDate, { weekStartsOn: 0 });
  const weekDays = eachDayOfInterval({ start: weekStart, end: weekEnd });

  // Real-time WebSocket connection
  const liveRefresh = useLiveRefreshContext();

  // Handle real-time meal plan events
  const handleMealPlanCreated = useCallback((data: any) => {
    setMealPlans((prev: any[]) => {
      if (prev.some(p => p.id === data.id)) return prev;
      return [...prev, data];
    });
  }, []);

  const handleMealPlanUpdated = useCallback((data: any) => {
    setMealPlans((prev: any[]) => prev.map(p => p.id === data.id ? data : p));
  }, []);

  const handleMealPlanDeleted = useCallback((data: any) => {
    setMealPlans((prev: any[]) => prev.filter(p => p.id !== data.id));
  }, []);

  // Subscribe to WebSocket events
  useLiveRefreshEvent(EventType.MEAL_PLAN_CREATED, handleMealPlanCreated, liveRefresh);
  useLiveRefreshEvent(EventType.MEAL_PLAN_UPDATED, handleMealPlanUpdated, liveRefresh);
  useLiveRefreshEvent(EventType.MEAL_PLAN_DELETED, handleMealPlanDeleted, liveRefresh);

  useEffect(() => {
    loadData();
  }, [currentDate]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [plansRes, recipesRes] = await Promise.all([
        mealPlanApi.getAll({
          start_date: format(weekStart, 'yyyy-MM-dd'),
          end_date: format(weekEnd, 'yyyy-MM-dd'),
        }),
        recipeApi.getAll(),
      ]);
      setMealPlans(plansRes.data);
      setRecipes(recipesRes.data);
    } catch (error) {
      toast.error('Failed to load meal plans');
    } finally {
      setLoading(false);
    }
  };

  const getMealsForDay = (date) => {
    const dateStr = format(date, 'yyyy-MM-dd');
    return mealPlans.filter(plan => plan.date === dateStr);
  };

  const handleAddMeal = async () => {
    if (!selectedRecipe || !selectedDate) return;

    setAdding(true);
    try {
      await mealPlanApi.create({
        date: format(selectedDate, 'yyyy-MM-dd'),
        meal_type: selectedMealType,
        recipe_id: selectedRecipe,
      });
      toast.success('Meal added to plan');
      setShowAddDialog(false);
      setSelectedRecipe('');
      loadData();
    } catch (error) {
      toast.error('Failed to add meal');
    } finally {
      setAdding(false);
    }
  };

  const handleDeleteMeal = async (planId) => {
    try {
      await mealPlanApi.delete(planId);
      toast.success('Meal removed from plan');
      setMealPlans(mealPlans.filter(p => p.id !== planId));
    } catch (error) {
      toast.error('Failed to remove meal');
    }
  };

  const handleAutoGenerate = async () => {
    if (recipes.length < 3) {
      toast.error('Need at least 3 recipes to auto-generate a plan');
      return;
    }

    setAutoGenerating(true);
    try {
      const res = await aiApi.autoMealPlan(7, autoPreferences);
      const plan = res.data;

      // Clear existing meals for the week
      for (const existingPlan of mealPlans) {
        await mealPlanApi.delete(existingPlan.id);
      }

      // Add new meals
      for (const day of plan.plan) {
        const date = addDays(new Date(), day.day);
        for (const meal of day.meals) {
          if (meal.recipe_id) {
            await mealPlanApi.create({
              date: format(date, 'yyyy-MM-dd'),
              meal_type: meal.meal_type,
              recipe_id: meal.recipe_id,
            });
          }
        }
      }

      toast.success('Meal plan generated!');
      setShowAutoDialog(false);
      loadData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to generate meal plan');
    } finally {
      setAutoGenerating(false);
    }
  };

  const handleExportCalendar = async () => {
    setExporting(true);
    try {
      const res = await calendarApi.exportIcal(
        format(weekStart, 'yyyy-MM-dd'),
        format(addWeeks(weekEnd, 4), 'yyyy-MM-dd')
      );
      
      const blob = new Blob([res.data], { type: 'text/calendar' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'mise-meals.ics';
      a.click();
      window.URL.revokeObjectURL(url);
      
      toast.success('Calendar exported! Import it into Google Calendar, Apple Calendar, etc.');
    } catch (error) {
      toast.error('Failed to export calendar');
    } finally {
      setExporting(false);
    }
  };

  const openAddDialog = (date, mealType = 'Dinner') => {
    setSelectedDate(date);
    setSelectedMealType(mealType);
    setShowAddDialog(true);
  };

  return (
    <Layout>
      <div className="space-y-6" data-testid="meal-planner">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div>
            <h1 className="font-heading text-3xl font-bold">Meal Planner</h1>
            <p className="text-muted-foreground mt-1">Plan your weekly meals</p>
          </div>
          
          <div className="flex flex-wrap gap-2">
            {/* Auto Generate Button */}
            <Button 
              variant="outline" 
              className="rounded-full"
              onClick={() => setShowAutoDialog(true)}
              data-testid="auto-generate-btn"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Auto Plan
            </Button>

            {/* Export Button */}
            <Button 
              variant="outline" 
              className="rounded-full"
              onClick={handleExportCalendar}
              disabled={exporting}
              data-testid="export-calendar-btn"
            >
              {exporting ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : (
                <Download className="w-4 h-4 mr-2" />
              )}
              Export
            </Button>

            {/* Week Navigation */}
            <div className="flex items-center gap-2">
              <Button 
                variant="outline" 
                size="icon" 
                onClick={() => setCurrentDate(subWeeks(currentDate, 1))}
                className="rounded-full"
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <div className="px-4 py-2 bg-white rounded-full border border-border/60 min-w-[200px] text-center">
                <span className="font-medium">
                  {format(weekStart, 'MMM d')} - {format(weekEnd, 'MMM d, yyyy')}
                </span>
              </div>
              <Button 
                variant="outline" 
                size="icon" 
                onClick={() => setCurrentDate(addWeeks(currentDate, 1))}
                className="rounded-full"
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </motion.div>

        {/* Calendar Grid */}
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-mise" />
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.1 }}
            className="grid grid-cols-1 md:grid-cols-7 gap-4"
          >
            {weekDays.map((day) => {
              const meals = getMealsForDay(day);
              const isToday = isSameDay(day, new Date());
              
              return (
                <div 
                  key={day.toISOString()}
                  className={`bg-white rounded-2xl border p-4 min-h-[200px] ${
                    isToday ? 'border-mise border-2' : 'border-border/60'
                  }`}
                >
                  {/* Day Header */}
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="text-xs text-muted-foreground uppercase tracking-wide">
                        {format(day, 'EEE')}
                      </p>
                      <p className={`font-heading font-bold text-lg ${isToday ? 'text-mise' : ''}`}>
                        {format(day, 'd')}
                      </p>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="icon"
                      className="h-8 w-8 rounded-full"
                      onClick={() => openAddDialog(day)}
                      data-testid={`add-meal-${format(day, 'yyyy-MM-dd')}`}
                    >
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>

                  {/* Meals */}
                  <div className="space-y-2">
                    {meals.length === 0 ? (
                      <p className="text-sm text-muted-foreground text-center py-4">No meals planned</p>
                    ) : (
                      meals.map((meal) => (
                        <div 
                          key={meal.id}
                          className="group p-2 rounded-lg bg-cream-subtle hover:bg-mise-light transition-colors"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <p className="text-xs text-mise font-medium">{meal.meal_type}</p>
                              <p className="text-sm font-medium truncate">{meal.recipe_title}</p>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-destructive"
                              onClick={() => handleDeleteMeal(meal.id)}
                            >
                              <Trash2 className="w-3 h-3" />
                            </Button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </motion.div>
        )}

        {/* Add Meal Dialog */}
        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Meal</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              {selectedDate && (
                <p className="text-sm text-muted-foreground">
                  Adding meal for {format(selectedDate, 'EEEE, MMMM d')}
                </p>
              )}
              
              <div>
                <label className="text-sm font-medium mb-2 block">Meal Type</label>
                <Select value={selectedMealType} onValueChange={setSelectedMealType}>
                  <SelectTrigger className="rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {MEAL_TYPES.map((type) => (
                      <SelectItem key={type} value={type}>{type}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium mb-2 block">Select Recipe</label>
                {recipes.length === 0 ? (
                  <div className="text-center py-6 bg-cream-subtle rounded-xl">
                    <UtensilsCrossed className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">No recipes yet</p>
                  </div>
                ) : (
                  <Select value={selectedRecipe} onValueChange={setSelectedRecipe}>
                    <SelectTrigger className="rounded-xl">
                      <SelectValue placeholder="Choose a recipe" />
                    </SelectTrigger>
                    <SelectContent>
                      {recipes.map((recipe) => (
                        <SelectItem key={recipe.id} value={recipe.id}>
                          {recipe.title}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </div>

              <Button 
                onClick={handleAddMeal} 
                className="w-full rounded-full bg-mise hover:bg-mise-dark"
                disabled={adding || !selectedRecipe}
              >
                {adding ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                Add to Plan
              </Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Auto Generate Dialog */}
        <Dialog open={showAutoDialog} onOpenChange={setShowAutoDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-mise" />
                Auto-Generate Meal Plan
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-4">
              <p className="text-sm text-muted-foreground">
                AI will create a balanced weekly meal plan using your existing recipes.
              </p>
              
              <div>
                <label className="text-sm font-medium mb-2 block">Preferences (optional)</label>
                <Input
                  value={autoPreferences}
                  onChange={(e) => setAutoPreferences(e.target.value)}
                  placeholder="e.g., vegetarian, quick meals, low-carb..."
                  className="rounded-xl"
                />
              </div>

              <div className="p-3 bg-amber-50 rounded-xl text-sm text-amber-800">
                <p>This will replace your current week's meal plan.</p>
              </div>

              <Button 
                onClick={handleAutoGenerate} 
                className="w-full rounded-full bg-mise hover:bg-mise-dark"
                disabled={autoGenerating || recipes.length < 3}
              >
                {autoGenerating ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 mr-2" />
                    Generate Plan
                  </>
                )}
              </Button>

              {recipes.length < 3 && (
                <p className="text-xs text-muted-foreground text-center">
                  Add at least 3 recipes to use auto-generate
                </p>
              )}
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};
