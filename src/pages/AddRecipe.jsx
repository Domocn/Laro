import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { Button } from '../components/ui/button';
import { useLanguage } from '../context/LanguageContext';
import { importApi } from '../lib/api';
import { toast } from 'sonner';
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  ClipboardPaste,
  FileUp,
  Image as ImageIcon,
  Link as LinkIcon,
  Loader2,
  PenLine,
  ChevronDown,
  Upload,
  Download,
  PlaneTakeoff,
} from 'lucide-react';

const PRIMARY = [
  {
    id: 'migrate',
    to: '/recipes/migrate',
    icon: PlaneTakeoff,
    titleKey: 'migrateTitle',
    descKey: 'migrateHubDesc',
    testId: 'add-hub-migrate',
  },
  {
    id: 'paste',
    to: '/recipes/quick-add',
    icon: ClipboardPaste,
    titleKey: 'pasteAndGo',
    descKey: 'addHubPasteDesc',
    testId: 'add-hub-paste',
  },
  {
    id: 'url',
    to: '/recipes/import',
    icon: LinkIcon,
    titleKey: 'importFromUrl',
    descKey: 'addHubUrlDesc',
    testId: 'add-hub-url',
  },
  {
    id: 'photo',
    to: '/recipes/quick-add?tab=photo',
    icon: ImageIcon,
    titleKey: 'addHubScanTitle',
    descKey: 'addHubScanDesc',
    testId: 'add-hub-photo',
  },
  {
    id: 'manual',
    to: '/recipes/new',
    icon: PenLine,
    titleKey: 'createManually',
    descKey: 'addHubManualDesc',
    testId: 'add-hub-manual',
  },
];

const MORE = [
  {
    id: 'pdf',
    to: '/recipes/quick-add?tab=pdf',
    icon: FileUp,
    titleKey: 'importPdfCta',
    descKey: 'addHubPdfDesc',
    testId: 'add-hub-pdf',
  },
  {
    id: 'app',
    to: '/recipes/import-batch',
    icon: Download,
    titleKey: 'importFromApp',
    descKey: 'addHubAppDesc',
    testId: 'add-hub-app',
  },
  {
    id: 'store',
    to: '/recipes/store-meal',
    icon: Camera,
    titleKey: 'storeMealTitle',
    descKey: 'storeMealSubtitle',
    testId: 'add-hub-store-meal',
  },
];

function HubRow({ opt, t }) {
  const Icon = opt.icon;
  return (
    <Link
      to={opt.to}
      data-testid={opt.testId}
      className="flex items-center gap-4 p-4 hover:bg-cream-subtle dark:hover:bg-muted/40 transition-colors"
    >
      <div className="w-11 h-11 rounded-full bg-laro/10 flex items-center justify-center shrink-0">
        <Icon className="w-5 h-5 text-laro" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{t(opt.titleKey)}</p>
        <p className="text-sm text-muted-foreground">{t(opt.descKey)}</p>
      </div>
      <ArrowRight className="w-4 h-4 text-muted-foreground shrink-0" />
    </Link>
  );
}

export const AddRecipe = () => {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [importing, setImporting] = useState(false);
  const [showMore, setShowMore] = useState(false);

  const handleImportFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    try {
      const content = await file.text();
      let platform = 'json';
      const name = file.name.toLowerCase();
      if (name.endsWith('.paprikarecipes') || name.includes('paprika')) {
        platform = 'paprika';
      } else if (name.includes('mealie') || name.includes('tandoor')) {
        platform = 'cookmate';
      }
      const res = await importApi.fromPlatform(platform, content);
      toast.success(res.data.message || `Imported ${res.data.imported} recipes!`);
      navigate('/recipes');
    } catch (error) {
      toast.error(error.response?.data?.detail || "Couldn't import those recipes. Please try again. (E-AR001)");
    } finally {
      setImporting(false);
      e.target.value = '';
    }
  };

  return (
    <Layout>
      <div className="max-w-2xl mx-auto space-y-5" data-testid="add-recipe-hub" data-tour="add-recipe-hub">
        <div>
          <Link
            to="/recipes"
            className="inline-flex items-center text-muted-foreground hover:text-foreground mb-3"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t('backToRecipes')}
          </Link>
          <h1 className="font-heading text-2xl font-bold">{t('addRecipe')}</h1>
          <p className="text-muted-foreground mt-1">{t('addHubSubtitle')}</p>
        </div>

        <div className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden divide-y divide-border/60">
          {PRIMARY.map((opt) => (
            <HubRow key={opt.id} opt={opt} t={t} />
          ))}
        </div>

        <div>
          <button
            type="button"
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
            onClick={() => setShowMore((v) => !v)}
            data-testid="add-hub-more"
          >
            <ChevronDown className={`w-4 h-4 mr-1 transition-transform ${showMore ? 'rotate-180' : ''}`} />
            {t('addHubMore')}
          </button>
          {showMore && (
            <div className="mt-3 bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden divide-y divide-border/60">
              {MORE.map((opt) => (
                <HubRow key={opt.id} opt={opt} t={t} />
              ))}
              <div className="p-4 space-y-3">
                <p className="text-sm font-medium">{t('importRecipeArchive')}</p>
                <p className="text-sm text-muted-foreground">{t('addHubArchiveDesc')}</p>
                <label className="flex flex-col items-center justify-center w-full h-24 border-2 border-dashed border-border/60 rounded-xl cursor-pointer hover:bg-cream-subtle dark:hover:bg-muted/40">
                  <div className="flex flex-col items-center justify-center">
                    {importing ? (
                      <Loader2 className="w-6 h-6 text-laro animate-spin mb-1" />
                    ) : (
                      <Upload className="w-6 h-6 text-muted-foreground mb-1" />
                    )}
                    <p className="text-sm">
                      <span className="font-medium text-laro">{t('addHubUploadCta')}</span>
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">{t('addHubArchiveFormats')}</p>
                  </div>
                  <input
                    type="file"
                    className="hidden"
                    accept=".json,.zip,.melarecipes,.html,.paprikarecipes"
                    onChange={handleImportFile}
                    disabled={importing}
                    data-testid="add-hub-archive-input"
                  />
                </label>
              </div>
            </div>
          )}
        </div>

        <div className="text-center pb-4">
          <Link to="/settings/imports">
            <Button variant="ghost" className="rounded-full" data-testid="add-hub-history">
              {t('yourImports')}
            </Button>
          </Link>
        </div>
      </div>
    </Layout>
  );
};

export default AddRecipe;
