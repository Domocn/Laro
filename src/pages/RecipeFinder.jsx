import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { recommendationsApi } from '../lib/api';
import { useLanguage } from '../context/LanguageContext';
import { getAiQuotaErrorMessage } from '../lib/aiQuota';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { Textarea } from '../components/ui/textarea';
import { Loader2, Sparkles, X, ChefHat } from 'lucide-react';
import { toast } from 'sonner';

const DIET_OPTIONS = ['vegetarian', 'vegan', 'gluten-free', 'dairy-free', 'nut-free', 'low-carb', 'halal'];

const ChipInput = ({ id, label, placeholder, values, onChange }) => {
  const [draft, setDraft] = useState('');
  const add = () => {
    const parts = draft.split(',').map((s) => s.trim()).filter(Boolean);
    if (parts.length) onChange([...new Set([...values, ...parts])]);
    setDraft('');
  };
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        value={draft}
        placeholder={placeholder}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add(); }
        }}
        onBlur={add}
      />
      {values.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {values.map((v) => (
            <Badge key={v} variant="secondary" className="gap-1">
              {v}
              <button type="button" aria-label={`Remove ${v}`} onClick={() => onChange(values.filter((x) => x !== v))}>
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
};

export const RecipeFinder = () => {
  const { t } = useLanguage();
  const [description, setDescription] = useState('');
  const [ingredients, setIngredients] = useState([]);
  const [dietaryNeeds, setDietaryNeeds] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const toggleDiet = (d) =>
    setDietaryNeeds((cur) => (cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d]));

  const submit = async (e) => {
    e.preventDefault();
    if (!description.trim() && ingredients.length === 0) {
      toast.error(t('finderNeedInput'));
      return;
    }
    setLoading(true);
    try {
      const { data } = await recommendationsApi.recommend({ description, ingredients, dietaryNeeds });
      setResult(data);
    } catch (err) {
      toast.error(getAiQuotaErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="space-y-8 max-w-3xl" data-testid="recipe-finder-page">
        <div>
          <h1 className="font-heading text-3xl font-bold">{t('finderTitle')}</h1>
          <p className="text-muted-foreground mt-1">{t('finderSubtitle')}</p>
        </div>

        <form onSubmit={submit} className="space-y-6 rounded-2xl border bg-card p-6">
          <div className="space-y-2">
            <Label htmlFor="finder-description">{t('finderDescribeLabel')}</Label>
            <Textarea
              id="finder-description"
              value={description}
              maxLength={1000}
              placeholder={t('finderDescribePlaceholder')}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <ChipInput
            id="finder-ingredients"
            label={t('finderIngredientsLabel')}
            placeholder={t('finderIngredientsPlaceholder')}
            values={ingredients}
            onChange={setIngredients}
          />
          <div className="space-y-2">
            <Label>{t('finderDietLabel')}</Label>
            <div className="flex flex-wrap gap-2">
              {DIET_OPTIONS.map((d) => (
                <Button
                  key={d}
                  type="button"
                  size="sm"
                  variant={dietaryNeeds.includes(d) ? 'default' : 'outline'}
                  className="rounded-full"
                  aria-pressed={dietaryNeeds.includes(d)}
                  onClick={() => toggleDiet(d)}
                >
                  {d}
                </Button>
              ))}
            </div>
            <ChipInput
              id="finder-diet-other"
              label={t('finderDietOtherLabel')}
              placeholder={t('finderDietOtherPlaceholder')}
              values={dietaryNeeds.filter((d) => !DIET_OPTIONS.includes(d))}
              onChange={(custom) => setDietaryNeeds([...dietaryNeeds.filter((d) => DIET_OPTIONS.includes(d)), ...custom])}
            />
          </div>
          <Button type="submit" className="rounded-full" disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Sparkles className="h-4 w-4 mr-2" />}
            {t('finderSubmit')}
          </Button>
        </form>

        {result && (
          <section aria-live="polite" className="space-y-4">
            {result.library_size === 0 ? (
              <p className="text-muted-foreground">{t('finderEmptyLibrary')}</p>
            ) : result.recommendations.length === 0 ? (
              <p className="text-muted-foreground">{t('finderNoMatches')}</p>
            ) : (
              <>
                {!result.used_ai && <p className="text-sm text-muted-foreground">{t('finderFallbackNote')}</p>}
                <ul className="grid gap-4 sm:grid-cols-2">
                  {result.recommendations.map(({ recipe, reason, missing_ingredients }) => (
                    <li key={recipe.id}>
                      <Link
                        to={`/recipes/${recipe.id}`}
                        className="block h-full rounded-2xl border bg-card overflow-hidden hover:shadow-md transition-shadow"
                      >
                        {recipe.image_url ? (
                          <img src={recipe.image_url} alt="" className="h-36 w-full object-cover" loading="lazy" />
                        ) : (
                          <div className="h-36 w-full bg-muted flex items-center justify-center">
                            <ChefHat className="h-8 w-8 text-muted-foreground" />
                          </div>
                        )}
                        <div className="p-4 space-y-2">
                          <h2 className="font-semibold">{recipe.title}</h2>
                          {reason && <p className="text-sm text-muted-foreground">{reason}</p>}
                          {missing_ingredients?.length > 0 && (
                            <p className="text-xs text-muted-foreground">
                              {t('finderYouMayNeed')} {missing_ingredients.join(', ')}
                            </p>
                          )}
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
        )}
      </div>
    </Layout>
  );
};

export default RecipeFinder;
