import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { useLanguage } from '../context/LanguageContext';
import { aiApi } from '../lib/api';
import { Button } from '../components/ui/button';
import {
  ArrowLeft,
  CheckCircle2,
  ExternalLink,
  Loader2,
  RefreshCw,
  AlertCircle,
  Download,
} from 'lucide-react';
import { toast } from 'sonner';

function statusMeta(status, t) {
  switch (status) {
    case 'importing':
      return {
        label: t('importStatusImporting'),
        className: 'text-laro bg-laro/10',
        Icon: Loader2,
        spin: true,
      };
    case 'succeeded':
      return {
        label: t('importStatusSucceeded'),
        className: 'text-emerald-700 bg-emerald-50',
        Icon: CheckCircle2,
        spin: false,
      };
    default:
      return {
        label: t('importStatusFailed'),
        className: 'text-red-700 bg-red-50',
        Icon: AlertCircle,
        spin: false,
      };
  }
}

export const ImportsSettings = () => {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [imports, setImports] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await aiApi.listImports({ limit: 50 });
      setImports(res.data?.imports || []);
    } catch (error) {
      console.error(error);
      toast.error(error.response?.data?.detail || t('importHistoryLoadFailed'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const hasLive = imports.some((item) => item.status === 'importing');
    if (!hasLive) return undefined;
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
  }, [imports, load]);

  return (
    <Layout>
      <div className="max-w-3xl mx-auto space-y-6" data-testid="imports-settings">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => navigate('/settings')}
              aria-label={t('back')}
            >
              <ArrowLeft className="w-5 h-5" />
            </Button>
            <div>
              <h1 className="font-heading text-2xl sm:text-3xl font-semibold text-laro-brand tracking-tight">
                {t('yourImports')}
              </h1>
              <p className="text-sm text-muted-foreground mt-1">{t('yourImportsDesc')}</p>
            </div>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            {t('refresh')}
          </Button>
        </div>

        {loading && imports.length === 0 ? (
          <div className="flex justify-center py-16">
            <Loader2 className="w-7 h-7 animate-spin text-laro" />
          </div>
        ) : imports.length === 0 ? (
          <div className="rounded-2xl border border-border/60 bg-white p-8 text-center space-y-3">
            <Download className="w-8 h-8 mx-auto text-muted-foreground" />
            <p className="text-muted-foreground">{t('yourImportsEmpty')}</p>
            <Link to="/recipes/import">
              <Button className="rounded-full mt-2">{t('importRecipe')}</Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {imports.map((item, index) => {
              const meta = statusMeta(item.status, t);
              const Icon = meta.Icon;
              return (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(index * 0.03, 0.3) }}
                  className="rounded-2xl border border-border/60 bg-white p-4"
                  data-testid={`import-row-${item.status}`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`mt-0.5 rounded-full p-2 ${meta.className}`}>
                      <Icon className={`w-4 h-4 ${meta.spin ? 'animate-spin' : ''}`} />
                    </div>
                    <div className="min-w-0 flex-1 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-medium text-sm truncate">
                          {item.title || item.url || meta.label}
                        </p>
                        <span className={`text-[11px] px-2 py-0.5 rounded-full ${meta.className}`}>
                          {meta.label}
                        </span>
                      </div>
                      {item.url ? (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-laro hover:underline inline-flex items-center gap-1 break-all"
                        >
                          {item.url}
                          <ExternalLink className="w-3 h-3 shrink-0" />
                        </a>
                      ) : null}
                      {item.error && item.status === 'failed' ? (
                        <p className="text-xs text-red-600">{item.error}</p>
                      ) : null}
                      {item.kind ? (
                        <p className="text-[11px] text-muted-foreground">{item.kind}</p>
                      ) : null}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </div>
    </Layout>
  );
};

export default ImportsSettings;
