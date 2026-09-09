import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { shoppingListApi, pantryApi } from '../lib/api';
import { useLanguage } from '../context/LanguageContext';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { useAccessibility, confirmDestructive } from '../context/AccessibilityContext';
import {
  useLiveRefreshContext,
  useLiveRefreshEvent,
  EventType,
} from '../hooks/useLiveRefresh';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Checkbox } from '../components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import {
  Plus,
  Trash2,
  Loader2,
  ShoppingCart,
  X,
  ScanLine,
  MoreVertical,
  MapPin,
  Package,
  Refrigerator,
  Wifi,
  WifiOff,
  Filter,
} from 'lucide-react';
import { Label } from '../components/ui/label';
import { ReceiptScanner } from '../components/ReceiptScanner';
import { toast } from 'sonner';
import { formatDate } from '../lib/utils';

/** Group shopping items by aisle while keeping original indices for mutations. */
function groupItemsByAisle(items = [], autoSort = true) {
  const groups = new Map();
  items.forEach((item, index) => {
    const aisle = item.category || 'Other';
    if (!groups.has(aisle)) groups.set(aisle, []);
    groups.get(aisle).push({ item, index });
  });
  const entries = [...groups.entries()].sort(([a, rowsA], [b, rowsB]) => {
    const orderA = rowsA[0]?.item?.sort_order ?? (a === 'Other' ? 99 : 50);
    const orderB = rowsB[0]?.item?.sort_order ?? (b === 'Other' ? 99 : 50);
    if (orderA !== orderB) return orderA - orderB;
    return a.localeCompare(b);
  });
  if (autoSort) {
    for (const [, rows] of entries) {
      rows.sort((a, b) => {
        // Unchecked items first, then A→Z by name
        const ac = a.item.checked ? 1 : 0;
        const bc = b.item.checked ? 1 : 0;
        if (ac !== bc) return ac - bc;
        return String(a.item.name || '').localeCompare(String(b.item.name || ''), undefined, {
          sensitivity: 'base',
        });
      });
    }
  }
  return entries;
}

export const ShoppingLists = () => {
  const { t } = useLanguage();
  const { confirmActions } = useAccessibility();
  const { preferences } = useUserPreferences();
  const autoSort = preferences.shoppingListAutoSort !== false;
  const liveRefresh = useLiveRefreshContext();
  const [lists, setLists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedList, setSelectedList] = useState(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newListName, setNewListName] = useState('');
  const [creating, setCreating] = useState(false);
  const [newItemName, setNewItemName] = useState('');
  const [newItemAmount, setNewItemAmount] = useState('');
  const [showReceiptScanner, setShowReceiptScanner] = useState(false);
  const [aisles, setAisles] = useState([]);
  const [livePing, setLivePing] = useState(null);
  const [pantryDialog, setPantryDialog] = useState(null); // { index, name, amount, unit }
  const [pantryExpiry, setPantryExpiry] = useState('');
  const [pantrySaving, setPantrySaving] = useState(false);

  useEffect(() => {
    loadLists();
    shoppingListApi.getAisles()
      .then((res) => setAisles(res.data.aisles || []))
      .catch(() => {});
  }, []);

  const aisleGroups = useMemo(
    () => groupItemsByAisle(selectedList?.items, autoSort),
    [selectedList, autoSort]
  );

  const recipeFilters = useMemo(() => {
    const map = new Map();
    (selectedList?.items || []).forEach((item) => {
      const ids = item.recipe_ids?.length
        ? item.recipe_ids
        : item.recipe_id
          ? [item.recipe_id]
          : [];
      const names = item.recipe_names?.length
        ? item.recipe_names
        : item.recipe_name
          ? [item.recipe_name]
          : [];
      ids.forEach((id, i) => {
        if (!id) return;
        map.set(id, names[i] || item.recipe_name || 'Recipe');
      });
      if (!ids.length && item.recipe_name) {
        map.set(`name:${item.recipe_name}`, item.recipe_name);
      }
    });
    return [...map.entries()];
  }, [selectedList]);

  const applyListUpdate = useCallback((updated) => {
    if (!updated?.id) return;
    setLists((prev) => prev.map((l) => (l.id === updated.id ? { ...l, ...updated } : l)));
    setSelectedList((prev) => (prev?.id === updated.id ? { ...prev, ...updated } : prev));
  }, []);

  const onLiveEvent = useCallback((data) => {
    if (!data) return;
    const listId = data.list_id || data.id;
    if (!listId) return;

    if (data.items) {
      applyListUpdate({ id: listId, items: data.items, updated_at: data.updated_at });
      return;
    }

    // Item check broadcast — patch local state optimistically for other users
    if (typeof data.checked === 'boolean' && (data.item_index != null || data.item_id)) {
      setSelectedList((prev) => {
        if (!prev || prev.id !== listId) return prev;
        const items = [...(prev.items || [])];
        let idx = data.item_index;
        if (data.item_id) {
          const byId = items.findIndex((i) => i.id === data.item_id);
          if (byId >= 0) idx = byId;
        }
        if (idx == null || idx < 0 || idx >= items.length) return prev;
        items[idx] = { ...items[idx], checked: data.checked };
        const next = { ...prev, items };
        setLists((ls) => ls.map((l) => (l.id === listId ? next : l)));
        if (data.updated_by_name) {
          setLivePing(`${data.updated_by_name} ${data.checked ? 'checked' : 'unchecked'} an item`);
          setTimeout(() => setLivePing(null), 2500);
        }
        return next;
      });
    }
  }, [applyListUpdate]);

  useLiveRefreshEvent(
    [
      EventType.SHOPPING_LIST_ITEM_CHECKED,
      EventType.SHOPPING_LIST_UPDATED,
      EventType.SHOPPING_LIST_CREATED,
      EventType.SHOPPING_LIST_DELETED,
    ],
    (data) => {
      // CREATED / DELETED — reload lightly
      if (!data) return;
      if (data.items || typeof data.checked === 'boolean') {
        onLiveEvent(data);
      } else if (data.id || data.list_id) {
        loadLists();
      }
    },
    liveRefresh
  );

  const loadLists = async () => {
    try {
      const res = await shoppingListApi.getAll();
      const sorted = [...res.data].sort(
        (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
      );
      setLists(sorted);
      if (sorted.length > 0) {
        setSelectedList((prev) => {
          if (prev) {
            const fresh = sorted.find((l) => l.id === prev.id);
            return fresh || sorted[0];
          }
          return sorted[0];
        });
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('toastLoadListsFailed')} (E-SL001)`);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateList = async () => {
    if (!newListName.trim()) return;

    setCreating(true);
    try {
      const res = await shoppingListApi.create({ name: newListName, items: [] });
      setLists([res.data, ...lists]);
      setSelectedList(res.data);
      setShowCreateDialog(false);
      setNewListName('');
      toast.success(t('toastListCreated'));
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('toastCreateListFailed')} (E-SL002)`);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteList = async (listId) => {
    if (!confirmDestructive(confirmActions, t('toastDeleteListConfirm'))) return;

    try {
      await shoppingListApi.delete(listId);
      const newLists = lists.filter(l => l.id !== listId);
      setLists(newLists);
      if (selectedList?.id === listId) {
        setSelectedList(newLists[0] || null);
      }
      toast.success(t('toastListDeleted'));
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('toastDeleteListFailed')} (E-SL003)`);
    }
  };

  const handleToggleItem = async (itemIndex, checkedOverride) => {
    if (!selectedList) return;

    const current = !!selectedList.items[itemIndex]?.checked;
    const nextChecked =
      typeof checkedOverride === 'boolean' ? checkedOverride : !current;
    // Optimistic local update for snappy checkoffs / unchecks
    const optimistic = {
      ...selectedList,
      items: selectedList.items.map((it, i) =>
        i === itemIndex ? { ...it, checked: nextChecked } : it
      ),
    };
    setSelectedList(optimistic);
    setLists(lists.map((l) => (l.id === optimistic.id ? optimistic : l)));

    try {
      await shoppingListApi.checkItem(selectedList.id, itemIndex, nextChecked);
    } catch (error) {
      // Revert
      setSelectedList(selectedList);
      setLists(lists.map((l) => (l.id === selectedList.id ? selectedList : l)));
      toast.error(error.response?.data?.detail || `${t('toastUpdateItemFailed')} (E-SL004)`);
    }
  };

  const openPantryDialog = (itemIndex) => {
    if (!selectedList) return;
    const item = selectedList.items[itemIndex];
    if (!item) return;
    setPantryDialog({
      index: itemIndex,
      name: item.name,
      amount: item.amount || item.quantity || '',
      unit: item.unit || '',
    });
    setPantryExpiry('');
  };

  const handleAddToPantry = async () => {
    if (!selectedList || !pantryDialog) return;
    setPantrySaving(true);
    try {
      await pantryApi.create({
        name: pantryDialog.name,
        quantity: pantryDialog.amount ? String(pantryDialog.amount) : null,
        unit: pantryDialog.unit || '',
        category: 'Other',
        expiry_date: pantryExpiry || null,
        notes: 'Added from shopping list',
        is_staple: false,
      });
      // Check off on the list so it feels "bought & stored"
      if (!selectedList.items[pantryDialog.index]?.checked) {
        await handleToggleItem(pantryDialog.index, true);
      }
      toast.success(t('toastItemAdded'));
      setPantryDialog(null);
      setPantryExpiry('');
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('addToPantry')} — ${t('error')}.`);
    } finally {
      setPantrySaving(false);
    }
  };

  const handleAddItem = async () => {
    if (!newItemName.trim() || !selectedList) return;

    const newItem = {
      name: newItemName,
      amount: newItemAmount || '1',
      unit: '',
      checked: false,
    };

    try {
      const res = await shoppingListApi.update(selectedList.id, {
        name: selectedList.name,
        items: [...selectedList.items, newItem],
      });
      setSelectedList(res.data);
      setLists(lists.map(l => l.id === res.data.id ? res.data : l));
      setNewItemName('');
      setNewItemAmount('');
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('toastAddItemFailed')} (E-SL005)`);
    }
  };

  const handleRemoveItem = async (itemIndex) => {
    if (!selectedList) return;

    const updatedItems = selectedList.items.filter((_, idx) => idx !== itemIndex);

    try {
      const res = await shoppingListApi.update(selectedList.id, {
        name: selectedList.name,
        items: updatedItems,
      });
      setSelectedList(res.data);
      setLists(lists.map(l => l.id === res.data.id ? res.data : l));
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('toastRemoveItemFailed')} (E-SL006)`);
    }
  };

  const handleSetAisle = async (itemIndex, aisle) => {
    if (!selectedList) return;
    try {
      const res = await shoppingListApi.setItemAisle(selectedList.id, itemIndex, aisle, true);
      applyListUpdate(res.data);
      toast.success(t('toastMovedToAisle', { aisle }));
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('moveAisle')} — ${t('error')}. (E-SL008)`);
    }
  };

  const handleMarkStaple = async (itemIndex) => {
    if (!selectedList) return;
    try {
      const res = await shoppingListApi.markStaple(selectedList.id, itemIndex, true);
      if (res.data.list) applyListUpdate(res.data.list);
      else loadLists();
      toast.success(t('toastSavedAsStaple'));
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('markAsStaple')} — ${t('error')}. (E-SL009)`);
    }
  };

  const handleRemoveRecipe = async (key, name) => {
    if (!selectedList) return;
    const recipeId = key.startsWith('name:') ? null : key;
    const recipeName = key.startsWith('name:') ? key.slice(5) : name;
    try {
      const res = await shoppingListApi.removeRecipe(selectedList.id, { recipeId, recipeName });
      if (res.data.list) applyListUpdate(res.data.list);
      toast.success(res.data.message || t('toastRecipeItemsRemoved'));
    } catch (error) {
      toast.error(error.response?.data?.detail || `${t('removeItem')} — ${t('error')}. (E-SL010)`);
    }
  };

  const handleReceiptScanComplete = async () => {
    if (selectedList) {
      try {
        const res = await shoppingListApi.getOne(selectedList.id);
        setSelectedList(res.data);
        setLists(lists.map(l => l.id === res.data.id ? res.data : l));
      } catch (error) {
        // Silent fail, list will sync via websocket
      }
    }
  };

  const checkedCount = selectedList?.items.filter(i => i.checked).length || 0;
  const totalCount = selectedList?.items.length || 0;
  const isLive = !!liveRefresh?.isConnected;

  return (
    <Layout>
      <div className="space-y-6 min-w-0 max-w-full overflow-x-hidden" data-testid="shopping-lists">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 min-w-0"
        >
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 sm:gap-3">
              <h1 className="font-heading text-3xl font-bold break-words">{t('shoppingLists')}</h1>
              <span
                className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full shrink-0 ${
                  isLive
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-muted text-muted-foreground'
                }`}
                title={isLive ? t('liveSyncOn') : t('liveSyncOffline')}
              >
                {isLive ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
                {isLive ? t('live') : t('offline')}
              </span>
            </div>
            <p className="text-muted-foreground mt-1">
              {livePing || t('manageGroceryShopping')}
            </p>
          </div>

          <div className="flex flex-wrap gap-2 w-full sm:w-auto">
            {selectedList && (
              <Button
                variant="outline"
                className="rounded-full flex-1 sm:flex-initial min-w-0"
                onClick={() => setShowReceiptScanner(true)}
              >
                <ScanLine className="w-4 h-4 mr-2 shrink-0" />
                <span className="truncate">{t('scanReceipt')}</span>
              </Button>
            )}
            <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
              <DialogTrigger asChild>
                <Button className="rounded-full bg-laro hover:bg-laro-dark flex-1 sm:flex-initial min-w-0" data-testid="create-list-btn">
                  <Plus className="w-4 h-4 mr-2 shrink-0" />
                  <span className="truncate">{t('newList')}</span>
                </Button>
              </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t('createShoppingList')}</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-4">
                <Input
                  placeholder={t('listNamePlaceholder')}
                  value={newListName}
                  onChange={(e) => setNewListName(e.target.value)}
                  className="rounded-xl"
                  data-testid="new-list-name"
                />
                <Button
                  onClick={handleCreateList}
                  className="w-full rounded-full bg-laro hover:bg-laro-dark"
                  disabled={creating || !newListName.trim()}
                >
                  {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                  {t('createList')}
                </Button>
              </div>
            </DialogContent>
            </Dialog>
          </div>
        </motion.div>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-laro" />
          </div>
        ) : lists.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-white rounded-2xl border border-border/60 p-12 text-center"
          >
            <ShoppingCart className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="font-heading text-lg font-semibold mb-2">{t('noShoppingListsYet')}</h3>
            <p className="text-muted-foreground mb-6">{t('emptyListsHint')}</p>
            <div className="flex flex-wrap gap-3 justify-center">
              <Button asChild className="rounded-full bg-laro hover:bg-laro-dark">
                <Link to="/meal-planner">{t('shopFromMealPlan')}</Link>
              </Button>
              <Button
                variant="outline"
                onClick={() => setShowCreateDialog(true)}
                className="rounded-full"
              >
                <Plus className="w-4 h-4 mr-2" />
                {t('createEmptyList')}
              </Button>
            </div>
          </motion.div>
        ) : (
          <div className="grid lg:grid-cols-3 gap-6 min-w-0">
            {/* Lists Sidebar */}
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="space-y-2 min-w-0"
            >
              {lists.map((list) => (
                <div
                  key={list.id}
                  className={`group p-4 rounded-xl cursor-pointer transition-all min-w-0 max-w-full overflow-hidden ${
                    selectedList?.id === list.id
                      ? 'bg-laro text-white'
                      : 'bg-card border border-border/60 hover:border-laro'
                  }`}
                  onClick={() => setSelectedList(list)}
                >
                  <div className="flex items-center justify-between gap-2 min-w-0">
                    <div className="min-w-0 flex-1 overflow-hidden">
                      <p className="font-medium truncate">{list.name}</p>
                      {/* text-laro-light is a pastel/dark tint token — unreadable on bg-laro (~1.8:1). Use white/80 on the solid accent. */}
                      <p className={`text-sm truncate ${selectedList?.id === list.id ? 'text-white/80' : 'text-muted-foreground'}`}>
                        {t('itemsCount', { count: list.items.length })}
                        {list.created_at ? ` · ${formatDate(list.created_at)}` : ''}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className={`h-8 w-8 shrink-0 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 ${
                        selectedList?.id === list.id ? 'text-white hover:text-white hover:bg-laro-dark' : ''
                      }`}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDeleteList(list.id);
                      }}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </motion.div>

            {/* Selected List */}
            {selectedList && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="lg:col-span-2 bg-white rounded-2xl border border-border/60 p-4 sm:p-6 min-w-0 max-w-full overflow-hidden"
              >
                <div className="flex items-center justify-between mb-6 gap-3">
                  <div className="min-w-0">
                    <h2 className="font-heading text-xl font-semibold truncate">{selectedList.name}</h2>
                    <p className="text-sm text-muted-foreground">
                      {t('itemsCheckedProgress', { checked: checkedCount, total: totalCount })}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {recipeFilters.length > 0 && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="outline" size="sm" className="rounded-full">
                            <Filter className="w-4 h-4 mr-1" />
                            {t('recipes')}
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-56">
                          {recipeFilters.map(([key, name]) => (
                            <DropdownMenuItem
                              key={key}
                              onClick={() => handleRemoveRecipe(key, name)}
                            >
                              <Trash2 className="w-4 h-4 mr-2" />
                              {t('remove')} {name}
                            </DropdownMenuItem>
                          ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                    {totalCount > 0 && (
                      <div className="w-20 h-2 bg-cream-subtle rounded-full overflow-hidden">
                        <div
                          className="h-full bg-laro rounded-full transition-all"
                          style={{ width: `${(checkedCount / totalCount) * 100}%` }}
                        />
                      </div>
                    )}
                  </div>
                </div>

                {/* Add Item */}
                <div className="flex flex-col sm:flex-row gap-2 mb-6">
                  <Input
                    placeholder={t('itemNamePlaceholder')}
                    value={newItemName}
                    onChange={(e) => setNewItemName(e.target.value)}
                    className="flex-1 rounded-xl min-w-0"
                    onKeyPress={(e) => e.key === 'Enter' && handleAddItem()}
                    data-testid="new-item-name"
                  />
                  <div className="flex gap-2">
                    <Input
                      placeholder={t('qty')}
                      value={newItemAmount}
                      onChange={(e) => setNewItemAmount(e.target.value)}
                      className="w-full sm:w-20 rounded-xl"
                      onKeyPress={(e) => e.key === 'Enter' && handleAddItem()}
                    />
                    <Button
                      onClick={handleAddItem}
                      className="rounded-xl bg-laro hover:bg-laro-dark shrink-0"
                      disabled={!newItemName.trim()}
                      data-testid="add-item-btn"
                    >
                      <Plus className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                {/* Items List — aisle grouped */}
                <div className="space-y-5" data-testid="shopping-items">
                  {selectedList.items.length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">
                      {t('noItemsYetShopPlan')}
                    </p>
                  ) : (
                    aisleGroups.map(([aisle, rows]) => (
                      <div key={aisle}>
                        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2 px-1">
                          {aisle}
                        </h3>
                        <div className="space-y-2">
                          {rows.map(({ item, index }) => (
                            <div
                              key={item.id || `${item.name}-${index}`}
                              className={`group flex items-center gap-3 p-3 rounded-xl transition-colors min-w-0 cursor-pointer ${
                                item.checked ? 'bg-laro-light/50' : 'bg-cream-subtle hover:bg-cream'
                              }`}
                              onClick={() => handleToggleItem(index)}
                              role="button"
                              tabIndex={0}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') {
                                  e.preventDefault();
                                  handleToggleItem(index);
                                }
                              }}
                            >
                              <Checkbox
                                checked={!!item.checked}
                                onCheckedChange={(v) => handleToggleItem(index, v === true)}
                                onClick={(e) => e.stopPropagation()}
                                className="shrink-0 data-[state=checked]:bg-laro data-[state=checked]:border-laro"
                              />
                              <div className={`flex-1 min-w-0 overflow-hidden ${item.checked ? 'line-through text-muted-foreground' : ''}`}>
                                <div className="truncate">
                                  {(item.amount || item.quantity) && (
                                    <span className="font-medium">{item.amount || item.quantity}</span>
                                  )}
                                  {item.unit && <span> {item.unit}</span>}
                                  <span> {item.name}</span>
                                  {item.in_pantry && (
                                    <span className="ml-2 text-[10px] uppercase tracking-wide text-laro not-italic no-underline">
                                      {t('inPantry')}
                                    </span>
                                  )}
                                </div>
                                {(item.recipe_name || item.recipe_names?.length) && (
                                  <p className="text-xs text-muted-foreground truncate mt-0.5 no-underline">
                                    {(item.recipe_names || [item.recipe_name]).filter(Boolean).join(' · ')}
                                  </p>
                                )}
                              </div>
                              <DropdownMenu>
                                <DropdownMenuTrigger asChild>
                                  <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-8 w-8 shrink-0 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 text-muted-foreground"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <MoreVertical className="w-4 h-4" />
                                  </Button>
                                </DropdownMenuTrigger>
                                <DropdownMenuContent align="end" className="w-52" onClick={(e) => e.stopPropagation()}>
                                  <DropdownMenuSub>
                                    <DropdownMenuSubTrigger>
                                      <MapPin className="w-4 h-4 mr-2" />
                                      {t('moveAisle')}
                                    </DropdownMenuSubTrigger>
                                    <DropdownMenuSubContent className="max-h-64 overflow-y-auto">
                                      {aisles.map((a) => (
                                        <DropdownMenuItem
                                          key={a}
                                          onClick={() => handleSetAisle(index, a)}
                                          disabled={a === (item.category || 'Other')}
                                        >
                                          {a}
                                        </DropdownMenuItem>
                                      ))}
                                    </DropdownMenuSubContent>
                                  </DropdownMenuSub>
                                  <DropdownMenuItem onClick={() => openPantryDialog(index)}>
                                    <Refrigerator className="w-4 h-4 mr-2" />
                                    {t('addToPantry')}
                                  </DropdownMenuItem>
                                  <DropdownMenuItem onClick={() => handleMarkStaple(index)}>
                                    <Package className="w-4 h-4 mr-2" />
                                    {t('alwaysHaveStaple')}
                                  </DropdownMenuItem>
                                  <DropdownMenuSeparator />
                                  <DropdownMenuItem
                                    className="text-destructive"
                                    onClick={() => handleRemoveItem(index)}
                                  >
                                    <X className="w-4 h-4 mr-2" />
                                    {t('removeItem')}
                                  </DropdownMenuItem>
                                </DropdownMenuContent>
                              </DropdownMenu>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </motion.div>
            )}
          </div>
        )}

        {selectedList && (
          <ReceiptScanner
            listId={selectedList.id}
            onScanComplete={handleReceiptScanComplete}
            open={showReceiptScanner}
            onOpenChange={setShowReceiptScanner}
          />
        )}

        <Dialog
          open={!!pantryDialog}
          onOpenChange={(open) => {
            if (!open) {
              setPantryDialog(null);
              setPantryExpiry('');
            }
          }}
        >
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>{t('addToPantry')}</DialogTitle>
            </DialogHeader>
            {pantryDialog && (
              <div className="space-y-4 pt-2">
                <p className="text-sm text-muted-foreground">
                  {pantryDialog.name}
                  {(pantryDialog.amount || pantryDialog.unit) && (
                    <span>
                      {' '}
                      ({[pantryDialog.amount, pantryDialog.unit].filter(Boolean).join(' ')})
                    </span>
                  )}
                </p>
                <div>
                  <Label htmlFor="pantry-expiry" className="mb-2 block">
                    {t('expiryDate')}
                  </Label>
                  <Input
                    id="pantry-expiry"
                    type="date"
                    value={pantryExpiry}
                    onChange={(e) => setPantryExpiry(e.target.value)}
                    className="rounded-xl"
                  />
                  <p className="text-xs text-muted-foreground mt-1.5">
                    Optional — great after scanning a receipt for fresh items.
                  </p>
                </div>
                <Button
                  onClick={handleAddToPantry}
                  disabled={pantrySaving}
                  className="w-full rounded-full bg-laro hover:bg-laro-dark"
                >
                  {pantrySaving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Refrigerator className="w-4 h-4 mr-2" />}
                  {t('addToPantry')}
                </Button>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};
