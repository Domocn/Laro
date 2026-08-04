import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { RecipeCard } from '../components/RecipeCard';
import { pantryApi, recipeApi, aiApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Checkbox } from '../components/ui/checkbox';
import {
  Plus, Search, Refrigerator, MoreVertical, Edit2, Trash2,
  AlertTriangle, Calendar, Package, Loader2, ChefHat, Sparkles, X
} from 'lucide-react';
import { toast } from 'sonner';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';

const PANTRY_CATEGORIES = [
  'All',
  'Produce',
  'Dairy',
  'Meat & Seafood',
  'Grains & Pasta',
  'Canned Goods',
  'Spices & Seasonings',
  'Baking',
  'Condiments',
  'Snacks',
  'Beverages',
  'Frozen',
  'Other'
];

const commonIngredients = [
  'Chicken', 'Beef', 'Pork', 'Fish', 'Eggs', 'Tofu',
  'Rice', 'Pasta', 'Bread', 'Potatoes',
  'Tomatoes', 'Onions', 'Garlic', 'Carrots', 'Broccoli',
  'Cheese', 'Milk', 'Butter', 'Cream',
  'Olive Oil', 'Soy Sauce', 'Lemon'
];

export const Pantry = () => {
  // Pantry state
  const [items, setItems] = useState([]);
  const [expiringItems, setExpiringItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('All');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingItem, setEditingItem] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    quantity: '',
    unit: '',
    category: 'Other',
    expiry_date: '',
    notes: ''
  });
  const [saving, setSaving] = useState(false);
  const [showRecipeSuggestions, setShowRecipeSuggestions] = useState(false);
  const [suggestedRecipes, setSuggestedRecipes] = useState([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  // Fridge search state
  const [ingredients, setIngredients] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchOnline, setSearchOnline] = useState(false);
  const [results, setResults] = useState(null);
  const [savingRecipe, setSavingRecipe] = useState(false);
  const [savedRecipeId, setSavedRecipeId] = useState(null);

  const loadPantry = useCallback(async () => {
    try {
      setLoading(true);
      const params = {};
      if (category !== 'All') params.category = category;
      if (search) params.search = search;

      const [itemsRes, expiringRes] = await Promise.all([
        pantryApi.getAll(params),
        pantryApi.getExpiring(7)
      ]);

      setItems(itemsRes.data || []);
      setExpiringItems(expiringRes.data || []);
    } catch (error) {
      toast.error('Couldn\'t load your pantry. Check your connection and try again. (E-PT001)');
    } finally {
      setLoading(false);
    }
  }, [category, search]);

  useEffect(() => {
    loadPantry();
  }, [loadPantry]);

  // Auto-populate fridge search with pantry items when loaded
  useEffect(() => {
    if (items.length > 0 && ingredients.length === 0) {
      setIngredients(items.slice(0, 10).map(i => i.name));
    }
  }, [items, ingredients.length]);

  const handleSearch = (e) => {
    e.preventDefault();
    loadPantry();
  };

  const handleCreate = async () => {
    if (!formData.name.trim()) {
      toast.error('Name is required');
      return;
    }
    setSaving(true);
    try {
      const res = await pantryApi.create({
        ...formData,
        quantity: formData.quantity ? parseFloat(formData.quantity) : null,
        expiry_date: formData.expiry_date || null
      });
      setItems([res.data, ...items]);
      setShowCreateModal(false);
      setFormData({ name: '', quantity: '', unit: '', category: 'Other', expiry_date: '', notes: '' });
      toast.success('Item added to pantry!');
    } catch (error) {
      toast.error('Couldn\'t add that item. Please try again. (E-PT002)');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = async () => {
    if (!formData.name.trim()) {
      toast.error('Name is required');
      return;
    }
    setSaving(true);
    try {
      const res = await pantryApi.update(editingItem.id, {
        ...formData,
        quantity: formData.quantity ? parseFloat(formData.quantity) : null,
        expiry_date: formData.expiry_date || null
      });
      setItems(items.map(i => i.id === editingItem.id ? res.data : i));
      setShowEditModal(false);
      setEditingItem(null);
      setFormData({ name: '', quantity: '', unit: '', category: 'Other', expiry_date: '', notes: '' });
      toast.success('Item updated!');
    } catch (error) {
      toast.error('Couldn\'t update that item. Please try again. (E-PT003)');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (item) => {
    if (!window.confirm(`Remove "${item.name}" from pantry?`)) return;
    try {
      await pantryApi.delete(item.id);
      setItems(items.filter(i => i.id !== item.id));
      toast.success('Item removed');
    } catch (error) {
      toast.error('Couldn\'t remove that item. Please try again. (E-PT004)');
    }
  };

  const openEditModal = (item) => {
    setEditingItem(item);
    setFormData({
      name: item.name || '',
      quantity: item.quantity?.toString() || '',
      unit: item.unit || '',
      category: item.category || 'Other',
      expiry_date: item.expiry_date ? item.expiry_date.split('T')[0] : '',
      notes: item.notes || '',
    });
    setShowEditModal(true);
  };

  const findRecipes = async () => {
    setLoadingSuggestions(true);
    setShowRecipeSuggestions(true);
    try {
      const ingredientNames = items.slice(0, 10).map(i => i.name);
      const res = await pantryApi.matchRecipes({ ingredients: ingredientNames, limit: 6 });
      setSuggestedRecipes(res.data || []);
    } catch (error) {
      toast.error('Couldn\'t find matching recipes. Please try again. (E-PT005)');
      setSuggestedRecipes([]);
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const getDaysUntilExpiry = (expiryDate) => {
    if (!expiryDate) return null;
    const today = new Date();
    const expiry = new Date(expiryDate);
    const diffTime = expiry - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    return diffDays;
  };

  const getExpiryStatus = (expiryDate) => {
    const days = getDaysUntilExpiry(expiryDate);
    if (days === null) return null;
    if (days < 0) return 'expired';
    if (days <= 3) return 'urgent';
    if (days <= 7) return 'warning';
    return 'ok';
  };

  // Fridge search functions
  const saveAiRecipe = async () => {
    if (!results?.ai_recipe_suggestion) return;

    setSavingRecipe(true);
    try {
      const suggestion = results.ai_recipe_suggestion;
      const recipeData = {
        title: suggestion.title,
        description: suggestion.description || '',
        ingredients: suggestion.ingredients || [],
        instructions: suggestion.instructions || [],
        prep_time: suggestion.prep_time || suggestion.prepTime,
        cook_time: suggestion.cook_time || suggestion.cookTime,
        servings: suggestion.servings,
        source_type: 'ai_generated'
      };

      const res = await recipeApi.create(recipeData);
      setSavedRecipeId(res.data.id);
      toast.success('Recipe saved to your collection!');
    } catch (error) {
      toast.error('Couldn\'t save the recipe. Please try again. (E-PT006)');
    } finally {
      setSavingRecipe(false);
    }
  };

  const addIngredient = (ingredient) => {
    const trimmed = ingredient.trim();
    if (trimmed && !ingredients.includes(trimmed)) {
      setIngredients([...ingredients, trimmed]);
    }
    setInputValue('');
  };

  const removeIngredient = (ingredient) => {
    setIngredients(ingredients.filter(i => i !== ingredient));
  };

  const handleFridgeSearch = async () => {
    if (ingredients.length === 0) {
      toast.error('Please add at least one ingredient');
      return;
    }

    setSearchLoading(true);
    setResults(null);

    try {
      const res = await aiApi.fridgeSearch(ingredients, searchOnline);
      setResults(res.data);

      if (res.data.matching_recipes.length === 0 && !res.data.ai_recipe_suggestion) {
        toast.info('No exact matches found. Try adding more ingredients or enable AI suggestions.');
      }
    } catch (error) {
      toast.error('Couldn\'t search for recipes. Please try again. (E-PT007)');
    } finally {
      setSearchLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && inputValue.trim()) {
      e.preventDefault();
      addIngredient(inputValue);
    }
  };

  const PantryItemForm = () => (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="name">Item Name *</Label>
        <Input
          id="name"
          placeholder="Milk, Eggs, Chicken..."
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          className="rounded-xl"
          required
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-2">
          <Label htmlFor="quantity">Quantity</Label>
          <Input
            id="quantity"
            type="number"
            step="0.1"
            placeholder="1"
            value={formData.quantity}
            onChange={(e) => setFormData({ ...formData, quantity: e.target.value })}
            className="rounded-xl"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="unit">Unit</Label>
          <Input
            id="unit"
            placeholder="lbs, oz, cups..."
            value={formData.unit}
            onChange={(e) => setFormData({ ...formData, unit: e.target.value })}
            className="rounded-xl"
          />
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="category">Category</Label>
        <Select value={formData.category} onValueChange={(v) => setFormData({ ...formData, category: v })}>
          <SelectTrigger className="rounded-xl">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PANTRY_CATEGORIES.filter(c => c !== 'All').map(cat => (
              <SelectItem key={cat} value={cat}>{cat}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="expiry_date">Expiry Date</Label>
        <Input
          id="expiry_date"
          type="date"
          value={formData.expiry_date}
          onChange={(e) => setFormData({ ...formData, expiry_date: e.target.value })}
          className="rounded-xl"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="notes">Notes</Label>
        <Input
          id="notes"
          placeholder="Location, brand, etc..."
          value={formData.notes}
          onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
          className="rounded-xl"
        />
      </div>
    </div>
  );

  return (
    <Layout>
      <div className="space-y-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-center md:justify-between gap-4"
        >
          <div>
            <h1 className="font-heading text-3xl font-bold flex items-center gap-3">
              <Refrigerator className="w-8 h-8 text-laro" />
              My Fridge
            </h1>
            <p className="text-muted-foreground mt-1">
              Track ingredients and find recipes you can make
            </p>
          </div>
          <Button
            className="rounded-full bg-laro hover:bg-laro-dark"
            onClick={() => {
              setFormData({ name: '', quantity: '', unit: '', category: 'Other', expiry_date: '', notes: '' });
              setShowCreateModal(true);
            }}
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Item
          </Button>
        </motion.div>

        {/* ===== PANTRY SECTION ===== */}
        <section className="space-y-4">
          <div className="flex items-center gap-2">
            <Package className="w-5 h-5 text-laro" />
            <h2 className="font-heading text-xl font-semibold">My Pantry</h2>
            <span className="text-muted-foreground text-sm">({items.length} items)</span>
          </div>

            {/* Expiring Soon Alert */}
            {expiringItems.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-amber-50 border border-amber-200 rounded-2xl p-4"
              >
                <div className="flex items-center gap-3 mb-3">
                  <AlertTriangle className="w-5 h-5 text-amber-600" />
                  <h3 className="font-semibold text-amber-800">Expiring Soon</h3>
                </div>
                <div className="flex flex-wrap gap-2">
                  {expiringItems.slice(0, 5).map(item => (
                    <span
                      key={item.id}
                      className="px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm"
                    >
                      {item.name} ({getDaysUntilExpiry(item.expiry_date)}d)
                    </span>
                  ))}
                  {expiringItems.length > 5 && (
                    <span className="px-3 py-1 bg-amber-100 text-amber-800 rounded-full text-sm">
                      +{expiringItems.length - 5} more
                    </span>
                  )}
                </div>
              </motion.div>
            )}

            {/* Search & Filter */}
            <div className="space-y-4">
              <form onSubmit={handleSearch} className="flex gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
                  <Input
                    placeholder="Search pantry..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-10 rounded-xl bg-white border-border/60"
                  />
                </div>
                <Button type="submit" variant="outline" className="rounded-xl">
                  Search
                </Button>
              </form>

              {/* Categories */}
              <div className="flex flex-wrap gap-2">
                {PANTRY_CATEGORIES.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setCategory(cat)}
                    className={`px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                      category === cat
                        ? 'bg-laro text-white shadow-sm'
                        : 'bg-white text-foreground border border-border/60 hover:bg-laro-light'
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>

            {/* Pantry Items Grid */}
            {loading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <div key={i} className="bg-white rounded-2xl h-32 animate-pulse" />
                ))}
              </div>
            ) : items.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="bg-white rounded-2xl border border-border/60 p-12 text-center"
              >
                <div className="w-16 h-16 rounded-full bg-laro-light mx-auto mb-4 flex items-center justify-center">
                  <Package className="w-8 h-8 text-laro" />
                </div>
                <h3 className="font-heading text-lg font-semibold mb-2">Your pantry is empty</h3>
                <p className="text-muted-foreground mb-6">
                  {search || category !== 'All'
                    ? 'No items match your search'
                    : 'Start tracking your ingredients'}
                </p>
                <Button
                  className="rounded-full bg-laro hover:bg-laro-dark"
                  onClick={() => setShowCreateModal(true)}
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Add Your First Item
                </Button>
              </motion.div>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
              >
                {items.map((item, index) => {
                  const expiryStatus = getExpiryStatus(item.expiry_date);
                  return (
                    <motion.div
                      key={item.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.03 }}
                      className={`bg-white rounded-2xl border p-4 hover:shadow-md transition-shadow ${
                        expiryStatus === 'expired' ? 'border-red-300 bg-red-50' :
                        expiryStatus === 'urgent' ? 'border-orange-300 bg-orange-50' :
                        expiryStatus === 'warning' ? 'border-amber-200' :
                        'border-border/60'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold truncate">{item.name}</h3>
                          <div className="flex items-center gap-2 text-sm text-muted-foreground mt-1">
                            {item.quantity && (
                              <span>{item.quantity} {item.unit}</span>
                            )}
                            {item.category && item.category !== 'Other' && (
                              <span className="px-2 py-0.5 bg-cream rounded-full text-xs">
                                {item.category}
                              </span>
                            )}
                          </div>
                          {item.expiry_date && (
                            <div className={`flex items-center gap-1 text-xs mt-2 ${
                              expiryStatus === 'expired' ? 'text-red-600' :
                              expiryStatus === 'urgent' ? 'text-orange-600' :
                              expiryStatus === 'warning' ? 'text-amber-600' :
                              'text-muted-foreground'
                            }`}>
                              <Calendar className="w-3 h-3" />
                              {expiryStatus === 'expired' ? 'Expired' :
                               `Expires in ${getDaysUntilExpiry(item.expiry_date)} days`}
                            </div>
                          )}
                        </div>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                              <MoreVertical className="w-4 h-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={() => openEditModal(item)}>
                              <Edit2 className="w-4 h-4 mr-2" />
                              Edit
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              onClick={() => handleDelete(item)}
                              className="text-red-600"
                            >
                              <Trash2 className="w-4 h-4 mr-2" />
                              Remove
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </motion.div>
                  );
                })}
              </motion.div>
            )}
        </section>

        {/* ===== FIND RECIPES SECTION ===== */}
        <section className="space-y-6">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-coral" />
            <h2 className="font-heading text-xl font-semibold">What Can I Make?</h2>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-2xl border border-border/60 p-6 shadow-card"
          >

              <div className="flex gap-3 mb-4">
                <Input
                  placeholder="Type an ingredient and press Enter..."
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  className="rounded-xl"
                />
                <Button
                  onClick={() => inputValue.trim() && addIngredient(inputValue)}
                  className="rounded-xl bg-laro hover:bg-laro-dark"
                  disabled={!inputValue.trim()}
                >
                  <Plus className="w-4 h-4" />
                </Button>
              </div>

              {/* Selected Ingredients */}
              {ingredients.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-4">
                  {ingredients.map((ing) => (
                    <Badge
                      key={ing}
                      variant="secondary"
                      className="bg-laro-light text-laro px-3 py-1.5 text-sm"
                    >
                      {ing}
                      <button
                        onClick={() => removeIngredient(ing)}
                        className="ml-2 hover:text-laro-dark"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}

              {/* Quick Add */}
              <div className="border-t border-border/60 pt-4 mt-4">
                <p className="text-sm text-muted-foreground mb-3">Quick add:</p>
                <div className="flex flex-wrap gap-2">
                  {commonIngredients.filter(i => !ingredients.includes(i)).slice(0, 12).map((ing) => (
                    <button
                      key={ing}
                      onClick={() => addIngredient(ing)}
                      className="px-3 py-1.5 rounded-full text-sm bg-cream-subtle hover:bg-laro-light text-foreground transition-colors"
                    >
                      + {ing}
                    </button>
                  ))}
                </div>
              </div>

              {/* Options */}
              <div className="flex items-center gap-6 mt-6 pt-4 border-t border-border/60">
                <label className="flex items-center gap-2 cursor-pointer">
                  <Checkbox
                    checked={searchOnline}
                    onCheckedChange={(checked) => setSearchOnline(checked)}
                  />
                  <span className="text-sm">
                    <Sparkles className="w-4 h-4 inline mr-1 text-coral" />
                    Suggest new recipes with AI
                  </span>
                </label>
              </div>

              {/* Search Button */}
              <Button
                onClick={handleFridgeSearch}
                className="w-full mt-6 rounded-full bg-laro hover:bg-laro-dark h-12"
                disabled={searchLoading || ingredients.length === 0}
              >
                {searchLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <>
                    <Search className="w-5 h-5 mr-2" />
                    Find Recipes
                  </>
                )}
              </Button>
            </motion.div>

            {/* Results */}
            {results && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-8"
              >
                {/* Matching Recipes */}
                {results.matching_recipes.length > 0 && (
                  <div>
                    <h2 className="font-heading text-xl font-semibold mb-4">
                      Matching Recipes ({results.matching_recipes.length})
                    </h2>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                      {results.matching_recipes.map((recipe) => (
                        <RecipeCard key={recipe.id} recipe={recipe} />
                      ))}
                    </div>
                  </div>
                )}

                {/* AI Suggestion */}
                {results.ai_recipe_suggestion && (
                  <div className="bg-coral-light rounded-2xl border border-coral/20 p-6">
                    <div className="flex items-center gap-2 mb-4">
                      <Sparkles className="w-5 h-5 text-coral" />
                      <h2 className="font-heading text-lg font-semibold">AI Recipe Suggestion</h2>
                    </div>
                    <div className="bg-white rounded-xl p-4">
                      <h3 className="font-heading font-semibold text-lg">
                        {results.ai_recipe_suggestion.title || 'Suggested Recipe'}
                      </h3>
                      {results.ai_recipe_suggestion.description && (
                        <p className="text-muted-foreground mt-2">{results.ai_recipe_suggestion.description}</p>
                      )}
                      {results.ai_recipe_suggestion.ingredients && (
                        <div className="mt-4">
                          <p className="text-sm font-medium mb-2">Ingredients:</p>
                          <div className="flex flex-wrap gap-2">
                            {results.ai_recipe_suggestion.ingredients.map((ing, idx) => (
                              <span key={idx} className="px-2 py-1 bg-cream-subtle rounded text-sm">
                                {ing.amount} {ing.unit} {ing.name}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      {results.ai_recipe_suggestion.instructions && (
                        <div className="mt-4">
                          <p className="text-sm font-medium mb-2">Instructions:</p>
                          <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground">
                            {results.ai_recipe_suggestion.instructions.map((step, idx) => (
                              <li key={idx}>{step}</li>
                            ))}
                          </ol>
                        </div>
                      )}
                      <div className="mt-4 pt-4 border-t">
                        {savedRecipeId ? (
                          <div className="flex items-center gap-2 text-green-600">
                            <span>✓ Recipe saved!</span>
                            <Link to={`/recipes/${savedRecipeId}`}>
                              <Button variant="outline" size="sm">View Recipe</Button>
                            </Link>
                          </div>
                        ) : (
                          <Button
                            onClick={saveAiRecipe}
                            disabled={savingRecipe}
                            className="bg-coral hover:bg-coral/90"
                          >
                            {savingRecipe ? (
                              <>
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                Saving...
                              </>
                            ) : (
                              <>
                                <Plus className="w-4 h-4 mr-2" />
                                Save Recipe
                              </>
                            )}
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                {/* No Results */}
                {results.matching_recipes.length === 0 &&
                 (!results.suggestions || results.suggestions.length === 0) &&
                 !results.ai_recipe_suggestion && (
                  <div className="bg-white rounded-2xl border border-border/60 p-8 text-center">
                    <ChefHat className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                    <h3 className="font-heading text-lg font-semibold mb-2">No matching recipes</h3>
                    <p className="text-muted-foreground mb-4">
                      Try adding more ingredients or enable AI suggestions!
                    </p>
                    <Link to="/recipes/new">
                      <Button className="rounded-full bg-laro hover:bg-laro-dark">
                        <Plus className="w-4 h-4 mr-2" />
                        Create Recipe
                      </Button>
                    </Link>
                  </div>
                )}
              </motion.div>
            )}
        </section>

        {/* Create Modal */}
        <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Package className="w-5 h-5 text-laro" />
                Add to Pantry
              </DialogTitle>
            </DialogHeader>
            <PantryItemForm />
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowCreateModal(false)} className="rounded-full">
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={saving} className="rounded-full bg-laro hover:bg-laro-dark">
                {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
                Add Item
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Edit Modal */}
        <Dialog open={showEditModal} onOpenChange={setShowEditModal}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <Edit2 className="w-5 h-5 text-laro" />
                Edit Item
              </DialogTitle>
            </DialogHeader>
            <PantryItemForm />
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowEditModal(false)} className="rounded-full">
                Cancel
              </Button>
              <Button onClick={handleEdit} disabled={saving} className="rounded-full bg-laro hover:bg-laro-dark">
                {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                Save Changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Recipe Suggestions Modal */}
        <Dialog open={showRecipeSuggestions} onOpenChange={setShowRecipeSuggestions}>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <ChefHat className="w-5 h-5 text-laro" />
                Recipes from Your Pantry
              </DialogTitle>
            </DialogHeader>
            {loadingSuggestions ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-8 h-8 animate-spin text-laro" />
              </div>
            ) : suggestedRecipes.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-muted-foreground">No matching recipes found</p>
                <p className="text-sm text-muted-foreground mt-2">
                  Try the "What Can I Make?" section below with AI suggestions enabled
                </p>
              </div>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {suggestedRecipes.map(recipe => (
                  <Link
                    key={recipe.id}
                    to={`/recipes/${recipe.id}`}
                    className="block p-3 bg-cream rounded-xl hover:bg-laro-light transition-colors"
                  >
                    <h4 className="font-semibold">{recipe.title}</h4>
                    {recipe.match_count && (
                      <p className="text-sm text-muted-foreground">
                        {recipe.match_count} matching ingredient{recipe.match_count !== 1 ? 's' : ''}
                      </p>
                    )}
                  </Link>
                ))}
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default Pantry;
