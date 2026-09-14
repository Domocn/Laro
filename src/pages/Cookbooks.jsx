import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { cookbooksApi } from '../lib/api';
import { useAccessibility, confirmDestructive } from '../context/AccessibilityContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Plus, Search, BookOpen, MoreVertical, Edit2, Trash2,
  BookMarked, Barcode, Loader2, ExternalLink, ShoppingBag, FileUp
} from 'lucide-react';
import { toast } from 'sonner';
import { useLanguage } from '../context/LanguageContext';
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

const BUY_LINK_LABEL_KEYS = {
  amazon: 'buyOnAmazon',
  bookshop: 'buyOnBookshop',
  open_library: 'buyOpenLibrary',
  archive: 'buyInternetArchive',
  publisher: 'buyPublisherSearch',
  drm_free_search: 'buyDrmFreeSearch',
};

export const Cookbooks = () => {
  const { t } = useLanguage();
  const { confirmActions } = useAccessibility();
  const [cookbooks, setCookbooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingCookbook, setEditingCookbook] = useState(null);
  const [formData, setFormData] = useState({ title: '', author: '', isbn: '', notes: '' });
  const [saving, setSaving] = useState(false);
  const [lookingUpISBN, setLookingUpISBN] = useState(false);

  const [buyQuery, setBuyQuery] = useState('');
  const [buyResults, setBuyResults] = useState([]);
  const [buySearching, setBuySearching] = useState(false);
  const [buySearched, setBuySearched] = useState(false);
  const [addingBuyKey, setAddingBuyKey] = useState(null);

  const loadCookbooks = useCallback(async () => {
    try {
      setLoading(true);
      const res = await cookbooksApi.getAll(search || undefined);
      setCookbooks(res.data || []);
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastLoadCookbooksFailed'));
    } finally {
      setLoading(false);
    }
  }, [search, t]);

  useEffect(() => {
    loadCookbooks();
  }, [loadCookbooks]);

  const handleSearch = (e) => {
    e.preventDefault();
    loadCookbooks();
  };

  const handleBuySearch = async (e) => {
    e?.preventDefault?.();
    const q = buyQuery.trim();
    if (q.length < 2) {
      toast.error(t('buySearchQueryTooShort'));
      return;
    }
    setBuySearching(true);
    setBuySearched(true);
    try {
      const res = await cookbooksApi.searchBuy(q);
      setBuyResults(res.data?.results || []);
    } catch (error) {
      setBuyResults([]);
      toast.error(error.response?.data?.detail || t('buySearchFailed'));
    } finally {
      setBuySearching(false);
    }
  };

  const handleAddFromBuyResult = async (result) => {
    const key = result.isbn || `${result.title}|${result.author || ''}`;
    setAddingBuyKey(key);
    try {
      const payload = {
        title: result.title,
        author: result.author || undefined,
        isbn: result.isbn || undefined,
        publisher: result.publisher || undefined,
        year: result.year || undefined,
        cover_image_url: result.cover_image_url || undefined,
      };
      const res = await cookbooksApi.create(payload);
      setCookbooks((prev) => [res.data, ...prev.filter((c) => c.id !== res.data.id)]);
      toast.success(t('toastBuyCookbookAdded'));
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastCreateCookbookFailed'));
    } finally {
      setAddingBuyKey(null);
    }
  };

  const handleISBNLookup = async () => {
    if (!formData.isbn) {
      toast.error(t('toastEnterIsbn'));
      return;
    }
    setLookingUpISBN(true);
    try {
      const res = await cookbooksApi.lookupISBN(formData.isbn);
      if (res.data) {
        setFormData({
          ...formData,
          title: res.data.title || formData.title,
          author: res.data.author || formData.author,
        });
        toast.success(t('toastBookInfoFound'));
      } else {
        toast.info(t('toastNoBookFoundIsbn'));
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastLookupIsbnFailed'));
    } finally {
      setLookingUpISBN(false);
    }
  };

  const handleCreate = async () => {
    if (!formData.title.trim()) {
      toast.error(t('toastTitleRequired'));
      return;
    }
    setSaving(true);
    try {
      const res = await cookbooksApi.create(formData);
      setCookbooks([res.data, ...cookbooks]);
      setShowCreateModal(false);
      setFormData({ title: '', author: '', isbn: '', notes: '' });
      toast.success(t('toastCookbookAdded'));
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastCreateCookbookFailed'));
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = async () => {
    if (!formData.title.trim()) {
      toast.error(t('toastTitleRequired'));
      return;
    }
    setSaving(true);
    try {
      const res = await cookbooksApi.update(editingCookbook.id, formData);
      setCookbooks(cookbooks.map(c => c.id === editingCookbook.id ? res.data : c));
      setShowEditModal(false);
      setEditingCookbook(null);
      setFormData({ title: '', author: '', isbn: '', notes: '' });
      toast.success(t('toastCookbookUpdated'));
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastUpdateCookbookFailed'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (cookbook) => {
    if (!confirmDestructive(confirmActions, t('confirmDeleteCookbook', { title: cookbook.title }))) return;
    try {
      await cookbooksApi.delete(cookbook.id);
      setCookbooks(cookbooks.filter(c => c.id !== cookbook.id));
      toast.success(t('toastCookbookDeleted'));
    } catch (error) {
      toast.error(error.response?.data?.detail || t('toastDeleteCookbookFailed'));
    }
  };

  const openEditModal = (cookbook) => {
    setEditingCookbook(cookbook);
    setFormData({
      title: cookbook.title || '',
      author: cookbook.author || '',
      isbn: cookbook.isbn || '',
      notes: cookbook.notes || '',
    });
    setShowEditModal(true);
  };

  const buyLinkLabel = (link) => {
    const key = BUY_LINK_LABEL_KEYS[link.kind];
    return key ? t(key) : link.label;
  };

  const CookbookForm = ({ isEdit = false }) => (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="isbn">{t('isbnOptional')}</Label>
        <div className="flex gap-2">
          <Input
            id="isbn"
            placeholder={t('isbnPlaceholder')}
            value={formData.isbn}
            onChange={(e) => setFormData({ ...formData, isbn: e.target.value })}
            className="rounded-xl"
          />
          <Button
            type="button"
            variant="outline"
            onClick={handleISBNLookup}
            disabled={lookingUpISBN}
            className="rounded-xl"
          >
            {lookingUpISBN ? <Loader2 className="w-4 h-4 animate-spin" /> : <Barcode className="w-4 h-4" />}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">{t('isbnAutofillHint')}</p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="title">{t('titleRequired')}</Label>
        <Input
          id="title"
          placeholder={t('cookbookTitlePlaceholder')}
          value={formData.title}
          onChange={(e) => setFormData({ ...formData, title: e.target.value })}
          className="rounded-xl"
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="author">{t('author')}</Label>
        <Input
          id="author"
          placeholder={t('authorPlaceholder')}
          value={formData.author}
          onChange={(e) => setFormData({ ...formData, author: e.target.value })}
          className="rounded-xl"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="notes">{t('notes')}</Label>
        <textarea
          id="notes"
          placeholder={t('cookbookNotesPlaceholder')}
          value={formData.notes}
          onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
          className="w-full px-3 py-2 rounded-xl border border-border/60 bg-white min-h-[80px] resize-none focus:outline-none focus:ring-2 focus:ring-laro"
        />
      </div>
    </div>
  );

  return (
    <Layout>
      <div className="space-y-8" data-testid="cookbooks-page">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-center md:justify-between gap-4"
        >
          <div>
            <h1 className="font-heading text-3xl font-bold flex items-center gap-3">
              <BookMarked className="w-8 h-8 text-laro" />
              {t('cookbooks')}
            </h1>
            <p className="text-muted-foreground mt-1">
              {t('cookbooksCountInLibrary', { count: cookbooks.length })}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" className="rounded-full" asChild>
              <Link to="/recipes/quick-add">
                <FileUp className="w-4 h-4 mr-2" />
                {t('importPdfCta')}
              </Link>
            </Button>
            <Button
              className="rounded-full bg-laro hover:bg-laro-dark"
              onClick={() => {
                setFormData({ title: '', author: '', isbn: '', notes: '' });
                setShowCreateModal(true);
              }}
            >
              <Plus className="w-4 h-4 mr-2" />
              {t('addCookbook')}
            </Button>
          </div>
        </motion.div>

        {/* Find a cookbook to buy */}
        <motion.section
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="rounded-2xl border border-border/60 bg-gradient-to-br from-laro-light/40 via-white to-white p-5 md:p-6"
          data-testid="cookbook-buy-search"
        >
          <div className="flex items-start gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-laro/15 flex items-center justify-center shrink-0">
              <ShoppingBag className="w-5 h-5 text-laro" />
            </div>
            <div>
              <h2 className="font-heading text-lg font-semibold">{t('findCookbookToBuy')}</h2>
              <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
                {t('findCookbookToBuyHint')}
              </p>
            </div>
          </div>

          <form onSubmit={handleBuySearch} className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <Input
                placeholder={t('findCookbookToBuyPlaceholder')}
                value={buyQuery}
                onChange={(e) => setBuyQuery(e.target.value)}
                className="pl-10 rounded-xl bg-white border-border/60"
                data-testid="cookbook-buy-search-input"
              />
            </div>
            <Button
              type="submit"
              className="rounded-xl bg-laro hover:bg-laro-dark"
              disabled={buySearching}
              data-testid="cookbook-buy-search-submit"
            >
              {buySearching ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Search className="w-4 h-4 mr-2" />}
              {t('search')}
            </Button>
          </form>

          {buySearching && (
            <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-28 rounded-xl bg-white/80 animate-pulse border border-border/40" />
              ))}
            </div>
          )}

          {!buySearching && buySearched && buyResults.length === 0 && (
            <p className="mt-4 text-sm text-muted-foreground" data-testid="cookbook-buy-search-empty">
              {t('buySearchEmpty')}
            </p>
          )}

          {!buySearching && buyResults.length > 0 && (
            <ul className="mt-6 space-y-4" data-testid="cookbook-buy-search-results">
              {buyResults.map((result) => {
                const addKey = result.isbn || `${result.title}|${result.author || ''}`;
                const isAdding = addingBuyKey === addKey;
                return (
                  <li
                    key={addKey + (result.open_library_key || '')}
                    className="flex flex-col sm:flex-row gap-4 p-4 rounded-xl bg-white border border-border/50"
                    data-testid="cookbook-buy-result"
                  >
                    <div className="w-16 h-20 sm:w-20 sm:h-24 rounded-lg bg-laro-light/60 overflow-hidden shrink-0 flex items-center justify-center">
                      {result.cover_image_url ? (
                        <img
                          src={result.cover_image_url}
                          alt=""
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <BookOpen className="w-8 h-8 text-laro" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="font-heading font-semibold text-base leading-snug">{result.title}</h3>
                      {result.author && (
                        <p className="text-sm text-muted-foreground mt-0.5">
                          {t('byAuthorPrefix', { author: result.author })}
                        </p>
                      )}
                      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-xs text-muted-foreground">
                        {result.year ? <span>{result.year}</span> : null}
                        {result.isbn ? <span>{t('isbnLabelShort', { isbn: result.isbn })}</span> : null}
                        {result.publisher ? <span className="truncate max-w-[14rem]">{result.publisher}</span> : null}
                      </div>

                      <div className="flex flex-wrap gap-2 mt-3">
                        {(result.buy_links || []).map((link) => (
                          <a
                            key={`${link.kind}-${link.url}`}
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-full border border-border/70 hover:border-laro hover:text-laro transition-colors bg-white"
                          >
                            {buyLinkLabel(link)}
                            <ExternalLink className="w-3 h-3 opacity-60" />
                          </a>
                        ))}
                      </div>

                      <div className="mt-3">
                        <Button
                          size="sm"
                          variant="outline"
                          className="rounded-full"
                          disabled={isAdding}
                          onClick={() => handleAddFromBuyResult(result)}
                          data-testid="cookbook-buy-add"
                        >
                          {isAdding ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                          ) : (
                            <Plus className="w-3.5 h-3.5 mr-1.5" />
                          )}
                          {t('addToMyCookbooks')}
                        </Button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </motion.section>

        {/* Library search */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <form onSubmit={handleSearch} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <Input
                placeholder={t('searchCookbooksPlaceholder')}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 rounded-xl bg-white border-border/60"
              />
            </div>
            <Button type="submit" variant="outline" className="rounded-xl">
              {t('search')}
            </Button>
          </form>
        </motion.div>

        {/* Cookbooks Grid */}
        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="bg-white rounded-2xl h-48 animate-pulse" />
            ))}
          </div>
        ) : cookbooks.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-white rounded-2xl border border-border/60 p-12 text-center"
          >
            <div className="w-16 h-16 rounded-full bg-laro-light mx-auto mb-4 flex items-center justify-center">
              <BookOpen className="w-8 h-8 text-laro" />
            </div>
            <h3 className="font-heading text-lg font-semibold mb-2">{t('noCookbooksYet')}</h3>
            <p className="text-muted-foreground mb-6">
              {search ? t('noCookbooksMatchSearch') : t('startBuildingCookbookLibrary')}
            </p>
            <Button
              className="rounded-full bg-laro hover:bg-laro-dark"
              onClick={() => setShowCreateModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              {t('addYourFirstCookbook')}
            </Button>
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
          >
            {cookbooks.map((cookbook, index) => (
              <motion.div
                key={cookbook.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
                className="bg-white rounded-2xl border border-border/60 overflow-hidden hover:shadow-lg transition-shadow"
              >
                <div className="p-5">
                  <div className="flex items-start justify-between mb-3">
                    <div className="w-12 h-12 rounded-xl bg-laro-light flex items-center justify-center overflow-hidden">
                      {cookbook.cover_image_url ? (
                        <img src={cookbook.cover_image_url} alt="" className="w-full h-full object-cover" />
                      ) : (
                        <BookOpen className="w-6 h-6 text-laro" />
                      )}
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                          <MoreVertical className="w-4 h-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => openEditModal(cookbook)}>
                          <Edit2 className="w-4 h-4 mr-2" />
                          {t('edit')}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => handleDelete(cookbook)}
                          className="text-red-600"
                        >
                          <Trash2 className="w-4 h-4 mr-2" />
                          {t('delete')}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                  <h3 className="font-heading font-semibold text-lg mb-1 line-clamp-2">
                    {cookbook.title}
                  </h3>
                  {cookbook.author && (
                    <p className="text-sm text-muted-foreground mb-2">{t('byAuthorPrefix', { author: cookbook.author })}</p>
                  )}
                  {cookbook.recipe_count !== undefined && (
                    <div className="flex items-center gap-1 text-sm text-muted-foreground">
                      {t('recipeCountLabel', { count: cookbook.recipe_count })}
                    </div>
                  )}
                  {cookbook.notes && (
                    <p className="text-sm text-muted-foreground mt-2 line-clamp-2">{cookbook.notes}</p>
                  )}
                </div>
              </motion.div>
            ))}
          </motion.div>
        )}

        {/* Create Modal */}
        <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <BookOpen className="w-5 h-5 text-laro" />
                {t('addCookbook')}
              </DialogTitle>
            </DialogHeader>
            <CookbookForm />
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowCreateModal(false)} className="rounded-full">
                {t('cancel')}
              </Button>
              <Button onClick={handleCreate} disabled={saving} className="rounded-full bg-laro hover:bg-laro-dark">
                {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
                {t('addCookbook')}
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
                {t('editCookbook')}
              </DialogTitle>
            </DialogHeader>
            <CookbookForm isEdit />
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowEditModal(false)} className="rounded-full">
                {t('cancel')}
              </Button>
              <Button onClick={handleEdit} disabled={saving} className="rounded-full bg-laro hover:bg-laro-dark">
                {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                {t('saveChanges')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default Cookbooks;
