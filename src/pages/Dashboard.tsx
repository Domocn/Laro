import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { RecipeCard } from '../components/RecipeCard';
import { TonightSuggestions } from '../components/TonightSuggestions';
import { useAuth } from '../context/AuthContext';
import { recipeApi, mealPlanApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { 
  Plus, 
  UtensilsCrossed, 
  CalendarDays, 
  ShoppingCart,
  Refrigerator,
  ArrowRight,
  ChefHat,
  Download
} from 'lucide-react';
import { toast } from 'sonner';
import { format, startOfWeek, endOfWeek } from 'date-fns';

export const Dashboard = () => {
  const { user, household } = useAuth();
  const [recipes, setRecipes] = useState([]);
  const [mealPlans, setMealPlans] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [recipesRes, plansRes] = await Promise.all([
        recipeApi.getAll(),
        mealPlanApi.getAll({
          start_date: format(startOfWeek(new Date()), 'yyyy-MM-dd'),
          end_date: format(endOfWeek(new Date()), 'yyyy-MM-dd'),
        }),
      ]);
      setRecipes(recipesRes.data.slice(0, 6));
      setMealPlans(plansRes.data);
    } catch (error) {
      console.error('Failed to load data:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const quickActions = [
    { icon: Plus, label: 'Add Recipe', path: '/recipes/new', color: 'bg-coral', shadowColor: 'shadow-coral' },
    { icon: CalendarDays, label: 'Meal Plan', path: '/meal-planner', color: 'bg-mise', shadowColor: 'shadow-card' },
    { icon: ShoppingCart, label: 'Shopping', path: '/shopping', color: 'bg-tangerine', shadowColor: 'shadow-tangerine' },
    { icon: Refrigerator, label: 'My Fridge', path: '/fridge', color: 'bg-teal', shadowColor: 'shadow-teal' },
  ];

  return (
    <Layout>
      <div className="space-y-10" data-testid="dashboard">
        {/* Welcome Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <h1 className="font-heading text-3xl sm:text-4xl font-bold text-foreground">
                Welcome back, {user?.name?.split(' ')[0]}!
              </h1>
              <p className="text-muted-foreground mt-2">
                {household ? `${household.name} Kitchen` : 'Your personal recipe collection'}
              </p>
            </div>
            <Link to="/recipes/new">
              <Button className="rounded-full bg-mise hover:bg-mise-dark shadow-sm" data-testid="dashboard-add-recipe">
                <Plus className="w-4 h-4 mr-2" />
                Add Recipe
              </Button>
            </Link>
          </div>
        </motion.div>

        {/* Quick Actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-4"
        >
          {quickActions.map((action, index) => {
            const Icon = action.icon;
            return (
              <Link key={action.label} to={action.path}>
                <div className="group p-6 rounded-2xl bg-white border border-border/60 shadow-soft hover:shadow-hover transition-all duration-300 hover:-translate-y-1">
                  <div className={`w-12 h-12 rounded-xl ${action.color} flex items-center justify-center mb-4`}>
                    <Icon className="w-6 h-6 text-white" />
                  </div>
                  <p className="font-medium text-foreground">{action.label}</p>
                </div>
              </Link>
            );
          })}
        </motion.div>

        {/* Tonight's Suggestions - The Core MVP Experience */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
        >
          <TonightSuggestions />
        </motion.section>

        {/* This Week's Meals */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.2 }}
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-heading text-xl font-semibold">This Week's Meals</h2>
            <Link to="/meal-planner" className="text-mise hover:text-mise-dark text-sm font-medium flex items-center gap-1">
              View All
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {mealPlans.length === 0 ? (
            <div className="bg-white rounded-2xl border border-border/60 p-8 text-center">
              <CalendarDays className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-muted-foreground mb-4">No meals planned for this week</p>
              <Link to="/meal-planner">
                <Button variant="outline" className="rounded-full">
                  Plan Your Meals
                </Button>
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {mealPlans.slice(0, 4).map((plan) => (
                <div key={plan.id} className="bg-white rounded-xl border border-border/60 p-4 shadow-soft">
                  <p className="text-xs text-muted-foreground uppercase tracking-wide">{plan.meal_type}</p>
                  <p className="font-medium mt-1 line-clamp-1">{plan.recipe_title}</p>
                  <p className="text-sm text-mise mt-2">{format(new Date(plan.date), 'EEE, MMM d')}</p>
                </div>
              ))}
            </div>
          )}
        </motion.section>

        {/* Recent Recipes */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.3 }}
        >
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-heading text-xl font-semibold">Recent Recipes</h2>
            <Link to="/recipes" className="text-mise hover:text-mise-dark text-sm font-medium flex items-center gap-1">
              View All
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="bg-white rounded-2xl h-72 animate-pulse" />
              ))}
            </div>
          ) : recipes.length === 0 ? (
            <div className="bg-white rounded-2xl border border-border/60 p-12 text-center">
              <ChefHat className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
              <h3 className="font-heading text-lg font-semibold mb-2">No recipes yet</h3>
              <p className="text-muted-foreground mb-6">Start building your recipe collection!</p>
              <div className="flex justify-center gap-3 flex-wrap">
                <Link to="/recipes/new">
                  <Button className="rounded-full bg-mise hover:bg-mise-dark">
                    <Plus className="w-4 h-4 mr-2" />
                    Create Recipe
                  </Button>
                </Link>
                <Link to="/recipes/import">
                  <Button variant="outline" className="rounded-full">
                    Import from URL
                  </Button>
                </Link>
                <Link to="/recipes/import-batch">
                  <Button variant="outline" className="rounded-full">
                    <Download className="w-4 h-4 mr-2" />
                    Import from App
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {recipes.map((recipe) => (
                <RecipeCard key={recipe.id} recipe={recipe} />
              ))}
            </div>
          )}
        </motion.section>
      </div>
    </Layout>
  );
};
