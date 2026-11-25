import React, { useState, useEffect, useMemo } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { RecipeCard } from '../components/RecipeCard';
import { cookbooksApi } from '../lib/api';
import { useLanguage } from '../context/LanguageContext';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { ArrowLeft, BookOpen, Plus, Search } from 'lucide-react';
import { toast } from 'sonner';

// One cookbook and the recipes that came from it.
export const CookbookDetail = () => {
  const { id } = useParams();
  const { t } = useLanguage();
  const { preferences } = useUserPreferences();
  const [cookbook, setCookbook] = useState(null);
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const gridClass = preferences.compactView
    ? 'grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 sm:gap-4'
    : 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6';

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    cookbooksApi.getRecipes(id)
      .then((res) => {
        if (cancelled) return;
        setCookbook(res.data?.cookbook || null);
        setRecipes(Array.isArray(res.data?.recipes) ? res.data.recipes : []);
      })
      .catch((error) => {
        if (!cancelled) toast.error(error.response?.data?.detail || t('cookbookLoadFailed'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [id, t]);

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return recipes;
    return recipes.filter((r) => (r.title || '').toLowerCase().includes(q));
  }, [recipes, search]);

  return (
    <Layout>
      <div className="space-y-6" data-testid="cookbook-detail-page">
        <Link to="/cookbooks" className="inline-flex items-center text-sm text-muted-foreground hover:text-laro">
          <ArrowLeft className="w-4 h-4 mr-1" />
          {t('backToCookbooks')}
        </Link>

        <div className="flex items-start gap-4">
          <div className="w-16 h-20 rounded-xl bg-laro-light flex items-center justify-center overflow-hidden shrink-0">
            {cookbook?.cover_image_url ? (
              <img src={cookbook.cover_image_url} alt="" className="w-full h-full object-cover" />
            ) : (
              <BookOpen className="w-7 h-7 text-laro" />
            )}
          </div>
          <div className="min-w-0">
            <h1 className="font-heading text-2xl sm:text-3xl font-bold">{cookbook?.title || t('cookbooks')}</h1>
            {cookbook?.author && (
              <p className="text-muted-foreground">{t('byAuthorPrefix', { author: cookbook.author })}</p>
            )}
            {!loading && (
              <p className="text-sm text-muted-foreground mt-1">{t('recipeCountLabel', { count: recipes.length })}</p>
            )}
          </div>
        </div>

        {recipes.length > 8 && (
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <Input
              placeholder={t('searchThisBook')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 rounded-xl bg-white border-border/60"
            />
          </div>
        )}

        {loading ? (
          <div className={gridClass}>
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="bg-white rounded-2xl h-48 animate-pulse" />
            ))}
          </div>
        ) : recipes.length === 0 ? (
          <div className="bg-white rounded-2xl border border-border/60 p-12 text-center">
            <p className="text-muted-foreground mb-6">{t('cookbookNoRecipesYet')}</p>
            <Link to="/recipes/add">
              <Button className="rounded-full bg-laro hover:bg-laro-dark">
                <Plus className="w-4 h-4 mr-2" />
                {t('addRecipe')}
              </Button>
            </Link>
          </div>
        ) : (
          <div className={gridClass}>
            {shown.map((recipe) => (
              <RecipeCard key={recipe.id} recipe={recipe} />
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default CookbookDetail;
