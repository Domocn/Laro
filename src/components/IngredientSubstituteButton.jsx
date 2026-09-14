import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowLeftRight, Loader2, Lock, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import api, { recipeApi } from '../lib/api';
import { Button } from './ui/button';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from './ui/sheet';
import { useLanguage } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';

/**
 * Honeydew-style per-ingredient substitute control.
 *
 * Pass recipeContext so Laro AI can rank swaps for THIS dish.
 * Guests can browse (AI when recipe/share context is provided); Apply needs signup.
 */
export function IngredientSubstituteButton({
  ingredientName,
  onApply,
  canApply = false,
  /** When true, guests still see the feature but must sign up to use Apply. */
  previewForGuests = false,
  /** Recipe context for AI-appropriate swaps */
  recipeContext = null,
  /** Share code — public AI path loads the shared recipe server-side */
  shareCode = null,
  className = '',
}) {
  const { t } = useLanguage();
  const { isAuthenticated } = useAuth();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [aiUsed, setAiUsed] = useState(false);
  const [applied, setApplied] = useState('');

  const name = (ingredientName || '').trim();
  if (!name) return null;

  const guestPreview = previewForGuests && !isAuthenticated;
  const allowApply = canApply && isAuthenticated && typeof onApply === 'function';
  const signupHref = `/register?next=${encodeURIComponent(location.pathname + location.search + location.hash)}`;

  const load = async () => {
    setOpen(true);
    setLoading(true);
    setSuggestions([]);
    setAiUsed(false);
    setApplied('');
    try {
      const ctx = recipeContext || {};
      const payload = {
        ingredient: name,
        limit: 5,
        recipe_id: ctx.id || ctx.recipe_id || undefined,
        recipe_title: ctx.title || ctx.recipe_title || undefined,
        recipe_description: ctx.description || ctx.recipe_description || undefined,
        ingredients: ctx.ingredients || undefined,
        instructions: ctx.instructions || undefined,
        share_code: shareCode || undefined,
        use_ai: true,
      };
      let res;
      if (isAuthenticated) {
        res = await recipeApi.substitutions(payload);
      } else if (previewForGuests) {
        res = await api.post('/share/substitutions', payload, { timeout: 90000 });
      } else {
        setOpen(false);
        toast.message(t('substituteSignupTitle') || 'Sign up to substitute ingredients');
        return;
      }
      setSuggestions(res.data?.suggestions || []);
      setAiUsed(!!res.data?.ai_used);
    } catch (err) {
      toast.error(
        err.response?.data?.detail ||
          t('toastSubstituteLoadFailed') ||
          "Couldn't load substitutions."
      );
      setOpen(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={load}
        className={`shrink-0 inline-flex items-center justify-center w-8 h-8 rounded-full text-laro hover:bg-laro/10 transition-colors ${className}`}
        aria-label={t('substituteIngredientAria', { name }) || `Substitute ${name}`}
        title={t('substitute') || 'Substitute'}
        data-testid={`substitute-btn-${name}`}
      >
        <ArrowLeftRight className="w-4 h-4" aria-hidden="true" />
      </button>

      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent side="bottom" className="rounded-t-2xl max-h-[80vh] overflow-y-auto">
          <SheetHeader className="text-left">
            <SheetTitle className="font-heading flex items-center gap-2">
              {t('substituteTitle') || 'Substitute ingredient'}
              {aiUsed && !loading ? (
                <span
                  className="inline-flex items-center gap-1 text-xs font-normal text-laro bg-laro/10 rounded-full px-2 py-0.5"
                  data-testid="substitute-ai-badge"
                >
                  <Sparkles className="w-3 h-3" aria-hidden="true" />
                  {t('substituteAiBadge') || 'Laro AI'}
                </span>
              ) : null}
            </SheetTitle>
            <SheetDescription>
              {t('substituteHintAi', { name }) ||
                t('substituteHint', { name }) ||
                `Swaps for ${name} ranked for this recipe by Laro AI.`}
            </SheetDescription>
          </SheetHeader>

          {guestPreview && (
            <div
              className="mt-3 flex items-start gap-2 rounded-xl bg-laro/10 border border-laro/20 p-3 text-sm"
              data-testid="substitute-signup-gate"
            >
              <Lock className="w-4 h-4 text-laro shrink-0 mt-0.5" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-foreground">
                  {t('substituteSignupTitle') || 'Sign up to apply swaps'}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t('substituteSignupBody') ||
                    'Browse ideas free. Create a free account to apply them to your recipes and personalize by diet.'}
                </p>
                <Link to={signupHref} className="inline-block mt-2">
                  <Button size="sm" className="rounded-full bg-laro hover:bg-laro-dark">
                    {t('joinLaroFree') || 'Join Laro for Free'}
                  </Button>
                </Link>
              </div>
            </div>
          )}

          <div className="mt-4 space-y-2" data-testid="substitute-suggestions">
            {loading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground py-6 justify-center">
                <Loader2 className="w-4 h-4 animate-spin" />
                {t('substituteAiLoading') || 'Asking Laro AI for this recipe…'}
              </div>
            ) : suggestions.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                {t('substituteNone') || 'No swaps found for this ingredient yet.'}
              </p>
            ) : (
              suggestions.map((s) => {
                const done = applied === s.name;
                return (
                  <div
                    key={s.name}
                    className="flex items-start justify-between gap-3 p-3 rounded-xl bg-cream-subtle dark:bg-muted border border-border/40"
                    data-testid={`substitute-option-${s.name}`}
                  >
                    <div className="min-w-0">
                      <p className="font-medium text-sm">{s.name}</p>
                      {s.reason ? (
                        <p className="text-xs text-muted-foreground mt-0.5">{s.reason}</p>
                      ) : null}
                    </div>
                    {allowApply ? (
                      <Button
                        type="button"
                        size="sm"
                        variant={done ? 'secondary' : 'outline'}
                        className="rounded-full shrink-0"
                        disabled={done}
                        onClick={() => {
                          onApply(s.name);
                          setApplied(s.name);
                          toast.success(
                            t('toastSubstituted', { from: name, to: s.name }) ||
                              `Swapped ${name} → ${s.name}`
                          );
                          setOpen(false);
                        }}
                        data-testid={`substitute-apply-${s.name}`}
                      >
                        {done
                          ? t('applied') || 'Applied'
                          : t('vetoApplySwap') || 'Apply'}
                      </Button>
                    ) : guestPreview ? (
                      <Link to={signupHref}>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="rounded-full shrink-0"
                          data-testid={`substitute-signup-${s.name}`}
                        >
                          <Lock className="w-3 h-3 mr-1" aria-hidden="true" />
                          {t('signUpToUse') || 'Sign up'}
                        </Button>
                      </Link>
                    ) : null}
                  </div>
                );
              })
            )}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}

export default IngredientSubstituteButton;
