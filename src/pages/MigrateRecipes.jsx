import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { useLanguage } from '../context/LanguageContext';
import { importApi } from '../lib/api';
import { toast } from 'sonner';
import {
  ArrowLeft,
  Check,
  AlertCircle,
  Loader2,
  PlaneTakeoff,
  CalendarDays,
  ShoppingCart,
} from 'lucide-react';

function mergeResults(a, b) {
  return {
    successful: [...(a?.successful || []), ...(b?.successful || [])],
    failed: [...(a?.failed || []), ...(b?.failed || [])],
    skipped: [...(a?.skipped || []), ...(b?.skipped || [])],
  };
}

export const MigrateRecipes = () => {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [status, setStatus] = useState(null);
  const [importing, setImporting] = useState(false);
  const [planning, setPlanning] = useState(false);
  const [result, setResult] = useState(null);
  const [batchNote, setBatchNote] = useState('');

  useEffect(() => {
    importApi
      .migrateStatus()
      .then((res) => setStatus(res.data))
      .catch(() => setStatus(null));
  }, []);

  const handleMigrate = async () => {
    if (!text.trim()) {
      toast.error(t('migrateNeedLines'));
      return;
    }
    setImporting(true);
    setResult(null);
    setBatchNote('');
    let paste = text;
    let combined = { successful: [], failed: [], skipped: [] };
    let lastMessage = '';
    try {
      for (let i = 0; i < 40; i += 1) {
        const res = await importApi.migrateClosingApps(paste);
        lastMessage = res.data.message;
        combined = mergeResults(combined, res.data.results);
        setResult({ ...res.data, results: combined, message: lastMessage });
        const leftover = res.data.remaining_text || '';
        const remaining = res.data.remaining_in_paste || 0;
        if (remaining > 0 && leftover.trim()) {
          paste = leftover;
          setText(leftover);
          setBatchNote(t('migrateAutoBatch', { remaining }));
          continue;
        }
        setText(leftover);
        break;
      }
      toast.success(lastMessage || t('migrateOk', { count: combined.successful.length }));
      try {
        const next = await importApi.migrateStatus();
        setStatus(next.data);
      } catch {
        /* keep previous status */
      }
    } catch (error) {
      toast.error(
        error.response?.data?.detail || t('migrateFailed')
      );
    } finally {
      setImporting(false);
      setBatchNote('');
    }
  };

  const handlePlanWeek = async () => {
    const ids = (result?.results?.successful || []).map((row) => row.id).filter(Boolean);
    if (!ids.length) {
      toast.error(t('migrateNeedLines'));
      return;
    }
    setPlanning(true);
    try {
      const res = await importApi.planMigratedWeek(ids);
      toast.success(res.data.message);
      navigate('/meal-planner');
    } catch (error) {
      toast.error(error.response?.data?.detail || t('migratePlanFailed'));
    } finally {
      setPlanning(false);
    }
  };

  const ok = result?.results?.successful || [];
  const failed = result?.results?.failed || [];
  const skipped = result?.results?.skipped || [];

  return (
    <Layout>
      <div className="max-w-2xl mx-auto space-y-6" data-testid="migrate-closing-apps">
        <div>
          <Link
            to="/recipes/add"
            className="inline-flex items-center text-muted-foreground hover:text-foreground mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t('backToAddRecipe')}
          </Link>
          <h1 className="font-heading text-3xl font-bold flex items-center gap-3">
            <PlaneTakeoff className="w-8 h-8 text-laro" />
            {t('migrateTitle')}
          </h1>
          <p className="text-muted-foreground mt-2">{t('migrateLead')}</p>
        </div>

        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 rounded-2xl p-4"
        >
          <p className="text-sm text-amber-950 dark:text-amber-100 font-medium">
            {t('migrateMealimeDeadline')}
          </p>
          <p className="text-sm text-amber-900/80 dark:text-amber-100/80 mt-2">
            {t('migrateMealimeHow')}
          </p>
          <p className="text-sm text-amber-900/80 dark:text-amber-100/80 mt-2">
            {t('migrateScreenshotHint')}
          </p>
          {status && (
            <p className="text-sm text-amber-900/80 dark:text-amber-100/80 mt-2" data-testid="migrate-remaining">
              {t('migrateRemaining', {
                remaining: status.remaining,
                allowance: status.allowance,
              })}
            </p>
          )}
        </motion.section>

        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-card rounded-2xl border border-border/60 p-4 space-y-3"
        >
          <label htmlFor="migrate-paste" className="text-sm font-medium">
            {t('migratePasteLabel')}
          </label>
          <textarea
            id="migrate-paste"
            data-testid="migrate-paste"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            className="w-full rounded-xl border border-border/60 bg-background p-3 text-sm"
            placeholder={t('migratePastePlaceholder')}
          />
          <p className="text-xs text-muted-foreground">{t('migrateBatchHint')}</p>
          {batchNote && (
            <p className="text-xs text-laro" data-testid="migrate-auto-batch">
              {batchNote}
            </p>
          )}
          <Button
            onClick={handleMigrate}
            disabled={importing}
            className="rounded-full bg-laro hover:bg-laro-dark"
            data-testid="migrate-submit"
          >
            {importing ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <PlaneTakeoff className="w-4 h-4 mr-2" />
            )}
            {t('migrateCta')}
          </Button>
        </motion.section>

        {result && (
          <motion.section
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-3"
            data-testid="migrate-result"
          >
            {ok.length > 0 && (
              <div className="bg-white dark:bg-card rounded-2xl border border-border/60 p-4">
                <p className="font-medium flex items-center gap-2 mb-2">
                  <Check className="w-4 h-4 text-laro" />
                  {t('migrateOk', { count: ok.length })}
                </p>
                <ul className="text-sm text-muted-foreground space-y-1">
                  {ok.map((row) => (
                    <li key={row.id || row.url}>{row.title || row.input}</li>
                  ))}
                </ul>
              </div>
            )}
            {failed.length > 0 && (
              <div className="bg-white dark:bg-card rounded-2xl border border-red-200 p-4">
                <p className="font-medium flex items-center gap-2 mb-2">
                  <AlertCircle className="w-4 h-4 text-red-600" />
                  {t('migrateFail', { count: failed.length })}
                </p>
                <ul className="text-sm text-muted-foreground space-y-1">
                  {failed.map((row, i) => (
                    <li key={`${row.input}-${i}`}>
                      {row.input}: {row.error}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {skipped.length > 0 && (
              <p className="text-sm text-muted-foreground">
                {skipped[0]?.error}
              </p>
            )}
            {ok.length > 0 && (
              <div className="flex flex-wrap gap-2">
                <Button
                  className="rounded-full bg-laro hover:bg-laro-dark"
                  onClick={handlePlanWeek}
                  disabled={planning}
                  data-testid="migrate-plan-week"
                >
                  {planning ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <CalendarDays className="w-4 h-4 mr-2" />
                  )}
                  {t('migratePlanWeek')}
                </Button>
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => navigate('/meal-planner')}
                >
                  <ShoppingCart className="w-4 h-4 mr-2" />
                  {t('migrateShopHint')}
                </Button>
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => navigate('/recipes')}
                >
                  {t('viewRecipes')}
                </Button>
              </div>
            )}
          </motion.section>
        )}

        <p className="text-sm text-muted-foreground pb-6">
          {t('migrateOtherApps')}{' '}
          <Link to="/recipes/import-batch" className="text-laro hover:underline">
            {t('importFromApp')}
          </Link>
          {' · '}
          <Link to="/recipes/add" className="text-laro hover:underline">
            {t('importRecipeArchive')}
          </Link>
        </p>
      </div>
    </Layout>
  );
};

export default MigrateRecipes;
