import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, Loader2, RefreshCw, X } from 'lucide-react';
import { recipeApi } from '../lib/api';
import { Button } from './ui/button';
import { useLanguage } from '../context/LanguageContext';

/**
 * Banner + apply-swap UI when recipe ingredients hit adult/kid veto lists.
 *
 * @param {Array<{name?: string, amount?: string, unit?: string}|string>} ingredients
 * @param {(index: number, suggestionName: string) => void} [onApply] — when provided, shows Apply buttons
 * @param {boolean} [enabled=true]
 * @param {any} [refreshKey] — change to force re-check (e.g. after import)
 */
export function VetoReplacementBanner({
  ingredients = [],
  onApply,
  enabled = true,
  refreshKey,
  className = '',
}) {
  const { t } = useLanguage();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [dismissed, setDismissed] = useState(false);
  const [applied, setApplied] = useState({});
  const reqId = useRef(0);

  const runCheck = useCallback(async () => {
    if (!enabled) {
      setResult(null);
      return;
    }
    const cleaned = (ingredients || [])
      .map((ing) => {
        if (typeof ing === 'string') return { name: ing };
        return {
          name: (ing?.name || '').trim(),
          amount: ing?.amount || '',
          unit: ing?.unit || '',
        };
      })
      .filter((ing) => ing.name);

    if (cleaned.length === 0) {
      setResult(null);
      return;
    }

    const id = ++reqId.current;
    setLoading(true);
    try {
      const res = await recipeApi.checkVeto(cleaned);
      if (id !== reqId.current) return;
      setResult(res.data);
      setDismissed(false);
    } catch {
      if (id !== reqId.current) return;
      setResult(null);
    } finally {
      if (id === reqId.current) setLoading(false);
    }
  }, [ingredients, enabled]);

  useEffect(() => {
    const timer = setTimeout(runCheck, 350);
    return () => clearTimeout(timer);
  }, [runCheck, refreshKey]);

  if (!enabled || dismissed) return null;
  if (loading && !result?.has_hits) {
    return (
      <div
        className={`flex items-center gap-2 text-sm text-muted-foreground ${className}`}
        data-testid="veto-check-loading"
      >
        <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
        <span>{t('vetoChecking') || 'Checking veto lists…'}</span>
      </div>
    );
  }
  if (!result?.has_hits) return null;

  const listLabel = (list) => {
    if (list === 'kid') return t('vetoListKid') || 'kid veto';
    return t('vetoListAdult') || 'adult veto';
  };

  return (
    <div
      className={`p-3 bg-amber-50 border border-amber-200 rounded-lg ${className}`}
      data-testid="veto-replacement-banner"
      role="status"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" aria-hidden="true" />
        <div className="flex-1 min-w-0 space-y-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-medium text-amber-900">
                {t('vetoWarningTitle') || 'Veto list ingredients found'}
              </p>
              <p className="text-sm text-amber-800 mt-0.5">
                {t('vetoWarningHint') ||
                  'Some ingredients match your adult or kid veto lists. Suggested swaps below.'}
              </p>
            </div>
            <div className="flex items-center gap-1 flex-shrink-0">
              <button
                type="button"
                onClick={runCheck}
                className="p-1 rounded-md text-amber-700 hover:bg-amber-100"
                title={t('refresh') || 'Refresh'}
                data-testid="veto-refresh-btn"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </button>
              <button
                type="button"
                onClick={() => setDismissed(true)}
                className="p-1 rounded-md text-amber-700 hover:bg-amber-100"
                aria-label={t('dismiss') || 'Dismiss'}
                data-testid="veto-dismiss-btn"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          <ul className="space-y-3">
            {(result.replacements || []).map((row) => {
              const lists = row.lists?.length ? row.lists : [row.list];
              const key = `${row.ingredient_index}-${row.matched_veto}`;
              return (
                <li
                  key={key}
                  className="text-sm text-amber-900 border-t border-amber-200/80 pt-3 first:border-0 first:pt-0"
                  data-testid={`veto-hit-${row.ingredient_index}`}
                >
                  <p>
                    <span className="font-medium">{row.ingredient}</span>
                    <span className="text-amber-700">
                      {' '}
                      ({lists.map(listLabel).join(', ')})
                    </span>
                  </p>
                  {row.suggestions?.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {row.suggestions.map((s) => {
                        const appliedKey = `${key}:${s.name}`;
                        const wasApplied = !!applied[appliedKey];
                        return (
                          <div
                            key={s.name}
                            className="inline-flex items-center gap-1.5 px-2 py-1 bg-white border border-amber-200 rounded-lg"
                          >
                            <span className="text-xs">
                              <span className="font-medium">{s.name}</span>
                              {s.reason ? (
                                <span className="text-muted-foreground"> — {s.reason}</span>
                              ) : null}
                            </span>
                            {typeof onApply === 'function' && (
                              <Button
                                type="button"
                                size="sm"
                                variant="outline"
                                className="h-7 text-xs rounded-full border-amber-300 text-amber-900 hover:bg-amber-100"
                                disabled={wasApplied}
                                onClick={() => {
                                  onApply(row.ingredient_index, s.name);
                                  setApplied((prev) => ({ ...prev, [appliedKey]: true }));
                                }}
                                data-testid={`veto-apply-${row.ingredient_index}-${s.name}`}
                              >
                                {wasApplied
                                  ? t('applied') || 'Applied'
                                  : t('vetoApplySwap') || 'Apply'}
                              </Button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default VetoReplacementBanner;
