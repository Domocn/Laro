import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { useLanguage } from '../context/LanguageContext';
import { ingredientsApi, shoppingListApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  ArrowLeft,
  Loader2,
  Merge,
  MapPin,
  Trash2,
  RefreshCw,
} from 'lucide-react';
import { toast } from 'sonner';

export const KitchenSettings = () => {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [aliases, setAliases] = useState([]);
  const [overrides, setOverrides] = useState({});
  const [loading, setLoading] = useState(true);
  const [fromName, setFromName] = useState('');
  const [toName, setToName] = useState('');
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [aliasRes, aisleRes] = await Promise.all([
        ingredientsApi.listAliases(),
        shoppingListApi.getAisleOverrides(),
      ]);
      setAliases(aliasRes.data?.aliases || []);
      setOverrides(aisleRes.data?.overrides || {});
    } catch (error) {
      console.error(error);
      toast.error(error.response?.data?.detail || t('kitchenSettingsLoadFailed'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRename = async (e) => {
    e.preventDefault();
    if (!fromName.trim() || !toName.trim()) return;
    setSaving(true);
    try {
      const res = await ingredientsApi.rename({
        from_name: fromName.trim(),
        to_name: toName.trim(),
        apply_to_recipes: true,
      });
      const updated = res.data?.recipes_updated ?? 0;
      const replacements = res.data?.replacements ?? 0;
      toast.success(
        `Merged into “${toName.trim()}” (${updated} recipes, ${replacements} replacements)`
      );
      setFromName('');
      setToName('');
      await load();
    } catch (error) {
      toast.error(error.response?.data?.detail || t('kitchenRenameFailed'));
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteAlias = async (fromKey) => {
    try {
      await ingredientsApi.deleteAlias(fromKey);
      toast.success(t('kitchenAliasDeleted'));
      await load();
    } catch (error) {
      toast.error(error.response?.data?.detail || t('error'));
    }
  };

  const handleDeleteAisle = async (ingredientKey) => {
    try {
      await shoppingListApi.deleteAisleOverride(ingredientKey);
      toast.success(t('kitchenAisleForgot'));
      await load();
    } catch (error) {
      toast.error(error.response?.data?.detail || t('error'));
    }
  };

  const overrideEntries = Object.entries(overrides).sort(([a], [b]) =>
    a.localeCompare(b)
  );

  return (
    <Layout>
      <div className="max-w-3xl mx-auto space-y-6" data-testid="kitchen-settings">
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
                {t('kitchenSettingsTitle')}
              </h1>
              <p className="text-sm text-muted-foreground mt-1">
                {t('kitchenSettingsDesc')}
              </p>
            </div>
          </div>
          <Button type="button" variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            {t('refresh')}
          </Button>
        </div>

        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-2xl border border-border/60 p-4 space-y-4"
        >
          <div className="flex items-center gap-2">
            <Merge className="w-5 h-5 text-laro" />
            <h2 className="font-medium">{t('kitchenRenameTitle')}</h2>
          </div>
          <p className="text-sm text-muted-foreground">{t('kitchenRenameDesc')}</p>
          <form onSubmit={handleRename} className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="from-name">{t('kitchenFromName')}</Label>
              <Input
                id="from-name"
                value={fromName}
                onChange={(e) => setFromName(e.target.value)}
                placeholder="e.g. scallion"
                data-testid="kitchen-from-name"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="to-name">{t('kitchenToName')}</Label>
              <Input
                id="to-name"
                value={toName}
                onChange={(e) => setToName(e.target.value)}
                placeholder="e.g. spring onion"
                data-testid="kitchen-to-name"
              />
            </div>
            <div className="sm:col-span-2">
              <Button
                type="submit"
                disabled={saving || !fromName.trim() || !toName.trim()}
                className="rounded-full bg-laro hover:bg-laro-dark"
                data-testid="kitchen-rename-submit"
              >
                {saving ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Merge className="w-4 h-4 mr-2" />
                )}
                {t('kitchenRenameSubmit')}
              </Button>
            </div>
          </form>

          {aliases.length > 0 && (
            <ul className="divide-y divide-border/60 border border-border/60 rounded-xl overflow-hidden">
              {aliases.map((a) => (
                <li
                  key={a.id || a.from_key}
                  className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
                >
                  <span>
                    <span className="font-medium">{a.from_key}</span>
                    <span className="text-muted-foreground"> → </span>
                    <span>{a.to_key}</span>
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDeleteAlias(a.from_key)}
                    aria-label={t('delete')}
                  >
                    <Trash2 className="w-4 h-4 text-muted-foreground" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </motion.section>

        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="bg-white rounded-2xl border border-border/60 p-4 space-y-4"
        >
          <div className="flex items-center gap-2">
            <MapPin className="w-5 h-5 text-laro" />
            <h2 className="font-medium">{t('kitchenAislesTitle')}</h2>
          </div>
          <p className="text-sm text-muted-foreground">{t('kitchenAislesDesc')}</p>
          {loading ? (
            <div className="flex justify-center py-6">
              <Loader2 className="w-6 h-6 animate-spin text-laro" />
            </div>
          ) : overrideEntries.length === 0 ? (
            <p className="text-sm text-muted-foreground py-2">{t('kitchenAislesEmpty')}</p>
          ) : (
            <ul className="divide-y divide-border/60 border border-border/60 rounded-xl overflow-hidden">
              {overrideEntries.map(([key, aisle]) => (
                <li
                  key={key}
                  className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
                  data-testid={`aisle-override-${key}`}
                >
                  <span>
                    <span className="font-medium">{key}</span>
                    <span className="text-muted-foreground"> · {aisle}</span>
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDeleteAisle(key)}
                    aria-label={t('delete')}
                  >
                    <Trash2 className="w-4 h-4 text-muted-foreground" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </motion.section>
      </div>
    </Layout>
  );
};
