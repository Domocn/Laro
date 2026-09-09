import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Link, useSearchParams, useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { RecipeCard } from '../components/RecipeCard';
import { recipeApi, rewardsApi } from '../lib/api';
import { useLanguage } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import { useAccessibility, confirmDestructive } from '../context/AccessibilityContext';
import { useUserPreferences } from '../hooks/useUserPreferences';
import {
  useLiveRefreshContext,
  useLiveRefreshEvent,
  EventType,
} from '../hooks/useLiveRefresh';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { CATEGORIES } from '../lib/utils';
import {
  Plus, Search, Filter, Link as LinkIcon, Heart, Download, Sparkles,
  BookOpen, Crown, CheckSquare, Trash2, X,
} from 'lucide-react';
import { toast } from 'sonner';

const CATEGORY_KEYS = {
  All: 'all',
  Breakfast: 'breakfast',
  Lunch: 'lunch',
  Dinner: 'dinner',
  Dessert: 'dessert',
  Appetizer: 'appetizer',
  Snack: 'snack',
  Beverage: 'beverage',
  'Meal Pack': 'mealPack',
  Other: 'other',
};

export const Recipes = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useLanguage();
  const { user } = useAuth();
  const { confirmActions } = useAccessibility();
  const { preferences } = useUserPreferences();
  const liveRefresh = useLiveRefreshContext();
  const compactView = !!preferences.compactView;
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [category, setCategory] = useState(searchParams.get('category') || 'All');
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(searchParams.get('favorites') === 'true');
  const [needsReviewOnly, setNeedsReviewOnly] = useState(searchParams.get('review') === '1');
  const [recipeLimit, setRecipeLimit] = useState(15);
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState(() => new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const gridClass = compactView
    ? 'grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 sm:gap-4'
    : 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6';

  const isPro = Boolean(user?.is_pro || user?.is_owner || user?.subscription_active);
  const isAdmin = ['admin', 'super_admin'].includes((user?.role || '').toLowerCase());

  const canDeleteRecipe = useCallback((recipe) => {
    if (!user?.id || !recipe) return false;
    if (isAdmin) return true;
    return recipe.author_id === user.id;
  }, [user?.id, isAdmin]);

  const loadRecipes = useCallback(async (opts = {}) => {
    const silent = !!opts.silent;
    try {
      if (!silent) setLoading(true);
      const params = {};
      if (category !== 'All') params.category = category;
      if (search) params.search = search;
      if (showFavoritesOnly) params.favorites_only = true;

      const res = await recipeApi.getAll(params);
      setRecipes(res.data);
    } catch (error) {
      if (!silent) {
        toast.error(error.response?.data?.detail || `${t('toastLoadRecipesFailed')} (E-RC001)`);
      }
    } finally {
      if (!silent) setLoading(false);
    }
  }, [category, search, showFavoritesOnly, t]);

  useEffect(() => {
    loadRecipes();
  }, [loadRecipes]);

  // If we navigated here after deleting a recipe, drop it immediately in case a
  // racing refetch still carried a stale card for one paint.
  useEffect(() => {
    const deletedId = location.state?.deletedRecipeId;
    if (!deletedId) return;
    setRecipes((prev) => prev.filter((r) => r.id !== deletedId));
    navigate(location.pathname + location.search, { replace: true, state: {} });
  }, [location.state, location.pathname, location.search, navigate]);

  // Live update when recipes change elsewhere (Android app, other tabs, household)
  useLiveRefreshEvent(
    EventType.RECIPE_DELETED,
    useCallback((data) => {
      const id = data?.id;
      if (!id) {
        loadRecipes({ silent: true });
        return;
      }
      setRecipes((prev) => prev.filter((r) => r.id !== id));
      setSelectedIds((prev) => {
        if (!prev.has(id)) return prev;
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }, [loadRecipes]),
    liveRefresh
  );
  useLiveRefreshEvent(
    [EventType.RECIPE_CREATED, EventType.RECIPE_UPDATED],
    useCallback(() => {
      loadRecipes({ silent: true });
    }, [loadRecipes]),
    liveRefresh
  );

  useEffect(() => {
    if (isPro) return;
    rewardsApi.balance()
      .then((res) => {
        const limit = res.data?.limits?.recipes;
        if (typeof limit === 'number') setRecipeLimit(limit);
      })
      .catch(() => {});
  }, [isPro]);

  useEffect(() => {
    setNeedsReviewOnly(searchParams.get('review') === '1');
  }, [searchParams]);

  const visibleRecipes = useMemo(() => {
    if (!needsReviewOnly) return recipes;
    return recipes.filter((r) =>
      (r.tags || []).some((tag) => String(tag).toLowerCase() === 'needs-review')
    );
  }, [recipes, needsReviewOnly]);

  const deletableVisible = useMemo(
    () => visibleRecipes.filter(canDeleteRecipe),
    [visibleRecipes, canDeleteRecipe]
  );

  const atRecipeLimit = !isPro && recipes.length >= recipeLimit;

  const exitSelectMode = useCallback(() => {
    setSelectMode(false);
    setSelectedIds(new Set());
  }, []);

  const toggleSelect = useCallback((id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const selectAllDeletable = useCallback(() => {
    setSelectedIds(new Set(deletableVisible.map((r) => r.id)));
  }, [deletableVisible]);

  const handleBulkDelete = useCallback(async () => {
    const ids = [...selectedIds];
    if (!ids.length) return;
    const ok = confirmDestructive(
      confirmActions,
      t('bulkDeleteRecipesConfirm', { count: ids.length })
    );
    if (!ok) return;

    setBulkDeleting(true);
    try {
      const res = await recipeApi.bulkDelete(ids);
      const deleted = res.data?.deleted_count ?? 0;
      const skippedRows = res.data?.skipped || [];
      const skipped = res.data?.skipped_count ?? skippedRows.length;
      const goneIds = new Set([
        ...(res.data?.deleted || []).map((d) => d.id),
        // Already removed server-side — drop from stale UI / cache
        ...skippedRows.filter((s) => s.reason === 'not_found').map((s) => s.id),
      ]);
      // Always purge selection from local list (covers SW/in-memory GET cache races)
      if (goneIds.size) {
        setRecipes((prev) => prev.filter((r) => !goneIds.has(r.id)));
      } else if (deleted === 0 && skipped > 0) {
        // Fallback: remove everything we tried if server only reported counts
        setRecipes((prev) => prev.filter((r) => !ids.includes(r.id)));
      }
      const forbidden = skippedRows.filter((s) => s.reason === 'forbidden').length;
      const notFound = skippedRows.filter((s) => s.reason === 'not_found').length;
      if (deleted > 0 && skipped === 0) {
        toast.success(t('toastBulkRecipesDeleted', { count: deleted }));
      } else if (deleted > 0) {
        toast.success(t('toastBulkRecipesPartial', { deleted, skipped }));
      } else if (notFound > 0 && forbidden === 0) {
        toast.success(t('toastBulkRecipesAlreadyGone', { count: notFound }));
      } else if (forbidden > 0) {
        toast.error(t('toastBulkRecipesForbidden', { count: forbidden }));
      } else {
        toast.success(t('toastBulkRecipesPartial', { deleted, skipped }));
      }
      exitSelectMode();
      await loadRecipes({ silent: true });
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('toastBulkDeleteFailed')} (E-RC002)`);
    } finally {
      setBulkDeleting(false);
    }
  }, [selectedIds, confirmActions, t, exitSelectMode, loadRecipes]);

  const handleSearch = useCallback((e) => {
    e.preventDefault();
    loadRecipes();
    const next = { search, category, favorites: showFavoritesOnly };
    if (needsReviewOnly) next.review = '1';
    setSearchParams(next);
  }, [loadRecipes, search, category, showFavoritesOnly, needsReviewOnly, setSearchParams]);

  const handleCategoryChange = useCallback((cat) => {
    setCategory(cat);
    const next = { search, category: cat, favorites: showFavoritesOnly };
    if (needsReviewOnly) next.review = '1';
    setSearchParams(next);
  }, [search, showFavoritesOnly, needsReviewOnly, setSearchParams]);

  const handleToggleFavorites = useCallback(() => {
    setShowFavoritesOnly(!showFavoritesOnly);
    const next = { search, category, favorites: !showFavoritesOnly };
    if (needsReviewOnly) next.review = '1';
    setSearchParams(next);
  }, [showFavoritesOnly, search, category, needsReviewOnly, setSearchParams]);

  const handleToggleReview = useCallback(() => {
    const nextVal = !needsReviewOnly;
    setNeedsReviewOnly(nextVal);
    const next = { search, category, favorites: showFavoritesOnly };
    if (nextVal) next.review = '1';
    setSearchParams(next);
  }, [needsReviewOnly, search, category, showFavoritesOnly, setSearchParams]);

  return (
    <Layout>
      <div className="space-y-8" data-testid="recipes-page">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-center md:justify-between gap-4"
        >
          <div>
            <h1 className="font-heading text-3xl font-bold">
              {needsReviewOnly
                ? t('needsReview')
                : showFavoritesOnly
                  ? t('favoriteRecipes')
                  : t('recipes')}
            </h1>
            <p className="text-muted-foreground mt-1">
              {selectMode
                ? `${selectedIds.size} selected`
                : needsReviewOnly
                  ? t('recipeCountAwaitingReview', { count: visibleRecipes.length })
                  : showFavoritesOnly
                    ? t('recipeCountFavorited', { count: visibleRecipes.length })
                    : t('recipeCountCollection', { count: visibleRecipes.length })}
            </p>
          </div>
          <div className="flex gap-3 flex-wrap">
            {selectMode ? (
              <>
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={selectAllDeletable}
                  disabled={!deletableVisible.length}
                  data-testid="select-all-recipes-btn"
                >
                  {t('selectAllRecipes')}
                </Button>
                <Button
                  variant="destructive"
                  className="rounded-full"
                  onClick={handleBulkDelete}
                  disabled={bulkDeleting || selectedIds.size === 0}
                  data-testid="bulk-delete-recipes-btn"
                >
                  {bulkDeleting ? (
                    <span className="animate-pulse">{t('deleteSelectedRecipes')}…</span>
                  ) : (
                    <>
                      <Trash2 className="w-4 h-4 mr-2" />
                      {t('deleteSelectedRecipes')} ({selectedIds.size})
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={exitSelectMode}
                  data-testid="cancel-select-recipes-btn"
                >
                  <X className="w-4 h-4 mr-2" />
                  {t('cancelSelect')}
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => setSelectMode(true)}
                  disabled={!deletableVisible.length}
                  data-testid="select-recipes-btn"
                >
                  <CheckSquare className="w-4 h-4 mr-2" />
                  {t('selectRecipes')}
                </Button>
                <Link to="/cookbooks">
                  <Button variant="outline" className="rounded-full">
                    <BookOpen className="w-4 h-4 mr-2" />
                    {t('cookbooks')}
                  </Button>
                </Link>
                <Button
                  variant={needsReviewOnly ? "default" : "outline"}
                  className={`rounded-full ${needsReviewOnly ? 'bg-laro hover:bg-laro-dark' : ''}`}
                  onClick={handleToggleReview}
                  data-testid="needs-review-filter-btn"
                >
                  {t('needsReview')}
                </Button>
                <Button
                  variant={showFavoritesOnly ? "default" : "outline"}
                  className={`rounded-full ${showFavoritesOnly ? 'bg-red-500 hover:bg-red-600' : ''}`}
                  onClick={handleToggleFavorites}
                  data-testid="favorites-filter-btn"
                >
                  <Heart className={`w-4 h-4 mr-2 ${showFavoritesOnly ? 'fill-current' : ''}`} />
                  {t('favorites')}
                </Button>
                <Link to="/recipes/import">
                  <Button
                    variant="outline"
                    className="rounded-full"
                    data-testid="import-recipe-btn"
                  >
                    <Sparkles className="w-4 h-4 mr-2" />
                    {t('importRecipe')}
                  </Button>
                </Link>
                <Link to="/recipes/new">
                  <Button className="rounded-full bg-laro hover:bg-laro-dark" data-testid="new-recipe-btn">
                    <Plus className="w-4 h-4 mr-2" />
                    {t('newRecipe')}
                  </Button>
                </Link>
              </>
            )}
          </div>
        </motion.div>

        {atRecipeLimit && (
          <div
            className="rounded-2xl border border-laro/30 bg-laro/5 p-4 flex flex-col sm:flex-row sm:items-center gap-3"
            data-testid="recipe-limit-banner"
          >
            <div className="flex-1 min-w-0">
              <p className="font-medium flex items-center gap-2">
                <Crown className="w-4 h-4 text-laro" aria-hidden="true" />
                {t('recipeLimitBannerTitle')}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {t('recipeLimitBannerBody', { count: recipes.length, limit: recipeLimit })}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link to="/settings">
                <Button size="sm" className="rounded-full bg-laro hover:bg-laro-dark">
                  {t('upgradeToPro')}
                </Button>
              </Link>
              <Link to="/settings">
                <Button size="sm" variant="outline" className="rounded-full">
                  {t('openRewards')}
                </Button>
              </Link>
            </div>
          </div>
        )}

        {/* Search & Filter */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="space-y-4"
        >
          {/* Search */}
          <form onSubmit={handleSearch} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <Input
                placeholder={t('searchRecipesPlaceholder')}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 rounded-xl bg-white border-border/60"
                data-testid="recipe-search"
              />
            </div>
            <Button type="submit" variant="outline" className="rounded-xl" data-testid="recipe-search-btn">
              {t('search')}
            </Button>
          </form>

          {/* Categories */}
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((cat) => (
              <button
                key={cat}
                onClick={() => handleCategoryChange(cat)}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                  category === cat
                    ? 'bg-laro text-white shadow-sm'
                    : 'bg-white text-foreground border border-border/60 hover:bg-laro-light'
                }`}
                data-testid={`category-${cat.toLowerCase()}`}
              >
                {CATEGORY_KEYS[cat] ? t(CATEGORY_KEYS[cat]) : cat}
              </button>
            ))}
          </div>
        </motion.div>

        {/* Recipe Grid */}
        {loading ? (
          <div className={gridClass}>
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className={`bg-white rounded-2xl animate-pulse ${compactView ? 'h-48' : 'h-80'}`} />
            ))}
          </div>
        ) : visibleRecipes.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-white rounded-2xl border border-border/60 p-12 text-center"
          >
            <div className="w-16 h-16 rounded-full bg-laro-light mx-auto mb-4 flex items-center justify-center">
              <Search className="w-8 h-8 text-laro" />
            </div>
            <h3 className="font-heading text-lg font-semibold mb-2">{t('noRecipesFound')}</h3>
            <p className="text-muted-foreground mb-6">
              {needsReviewOnly
                ? t('nothingAwaitingReview')
                : search || category !== 'All'
                  ? t('tryAdjustingFilters')
                  : t('startAddingRecipes')}
            </p>
            <Link to="/recipes/new">
              <Button className="rounded-full bg-laro hover:bg-laro-dark">
                <Plus className="w-4 h-4 mr-2" />
                {t('addYourFirstRecipe')}
              </Button>
            </Link>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className={gridClass}
            data-compact={compactView ? 'true' : 'false'}
          >
            {visibleRecipes.map((recipe, index) => (
              <motion.div
                key={recipe.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <RecipeCard
                  recipe={recipe}
                  selectMode={selectMode}
                  selected={selectedIds.has(recipe.id)}
                  selectable={canDeleteRecipe(recipe)}
                  onToggleSelect={toggleSelect}
                />
              </motion.div>
            ))}
          </motion.div>
        )}
      </div>
    </Layout>
  );
};
