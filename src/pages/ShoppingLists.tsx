import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { shoppingListApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Checkbox } from '../components/ui/checkbox';
import { useLiveRefreshContext, useLiveRefreshEvent, EventType } from '../hooks/useLiveRefresh';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../components/ui/dialog';
import {
  Plus,
  Trash2,
  Loader2,
  ShoppingCart,
  Check,
  Edit,
  X,
  ScanLine
} from 'lucide-react';
import { ReceiptScanner } from '../components/ReceiptScanner';
import { toast } from 'sonner';
import { formatDate } from '../lib/utils';

export const ShoppingLists = () => {
  const [lists, setLists] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedList, setSelectedList] = useState(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newListName, setNewListName] = useState('');
  const [creating, setCreating] = useState(false);
  const [newItemName, setNewItemName] = useState('');
  const [newItemAmount, setNewItemAmount] = useState('');
  const [showReceiptScanner, setShowReceiptScanner] = useState(false);

  // Real-time WebSocket connection
  const liveRefresh = useLiveRefreshContext();

  // Handle real-time shopping list events
  const handleListCreated = useCallback((data: any) => {
    setLists((prev: any[]) => {
      // Avoid duplicates
      if (prev.some(l => l.id === data.id)) return prev;
      return [data, ...prev];
    });
  }, []);

  const handleListUpdated = useCallback((data: any) => {
    setLists((prev: any[]) => prev.map(l => l.id === data.id ? data : l));
    setSelectedList((prev: any) => prev?.id === data.id ? data : prev);
  }, []);

  const handleListDeleted = useCallback((data: any) => {
    setLists((prev: any[]) => prev.filter(l => l.id !== data.id));
    setSelectedList((prev: any) => prev?.id === data.id ? null : prev);
  }, []);

  const handleItemChecked = useCallback((data: any) => {
    const { list_id, item_index, checked } = data;
    setLists((prev: any[]) => prev.map(l => {
      if (l.id !== list_id) return l;
      const updatedItems = [...l.items];
      if (updatedItems[item_index]) {
        updatedItems[item_index] = { ...updatedItems[item_index], checked };
      }
      return { ...l, items: updatedItems };
    }));
    setSelectedList((prev: any) => {
      if (prev?.id !== list_id) return prev;
      const updatedItems = [...prev.items];
      if (updatedItems[item_index]) {
        updatedItems[item_index] = { ...updatedItems[item_index], checked };
      }
      return { ...prev, items: updatedItems };
    });
  }, []);

  // Subscribe to WebSocket events
  useLiveRefreshEvent(EventType.SHOPPING_LIST_CREATED, handleListCreated, liveRefresh);
  useLiveRefreshEvent(EventType.SHOPPING_LIST_UPDATED, handleListUpdated, liveRefresh);
  useLiveRefreshEvent(EventType.SHOPPING_LIST_DELETED, handleListDeleted, liveRefresh);
  useLiveRefreshEvent(EventType.SHOPPING_LIST_ITEM_CHECKED, handleItemChecked, liveRefresh);

  useEffect(() => {
    loadLists();
  }, []);

  const loadLists = async () => {
    try {
      const res = await shoppingListApi.getAll();
      setLists(res.data);
      if (res.data.length > 0 && !selectedList) {
        setSelectedList(res.data[0]);
      }
    } catch (error) {
      toast.error('Failed to load shopping lists');
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
      toast.success('List created');
    } catch (error) {
      toast.error('Failed to create list');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteList = async (listId) => {
    if (!window.confirm('Delete this shopping list?')) return;
    
    try {
      await shoppingListApi.delete(listId);
      const newLists = lists.filter(l => l.id !== listId);
      setLists(newLists);
      if (selectedList?.id === listId) {
        setSelectedList(newLists[0] || null);
      }
      toast.success('List deleted');
    } catch (error) {
      toast.error('Failed to delete list');
    }
  };

  const handleToggleItem = async (itemIndex) => {
    if (!selectedList) return;
    
    const updatedItems = [...selectedList.items];
    updatedItems[itemIndex] = {
      ...updatedItems[itemIndex],
      checked: !updatedItems[itemIndex].checked,
    };

    try {
      const res = await shoppingListApi.update(selectedList.id, {
        name: selectedList.name,
        items: updatedItems,
      });
      setSelectedList(res.data);
      setLists(lists.map(l => l.id === res.data.id ? res.data : l));
    } catch (error) {
      toast.error('Failed to update item');
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
      toast.error('Failed to add item');
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
      toast.error('Failed to remove item');
    }
  };

  const handleReceiptScanComplete = async () => {
    // Reload the list to get updated checked items
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

  return (
    <Layout>
      <div className="space-y-6" data-testid="shopping-lists">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4"
        >
          <div>
            <h1 className="font-heading text-3xl font-bold">Shopping Lists</h1>
            <p className="text-muted-foreground mt-1">Manage your grocery shopping</p>
          </div>
          
          <div className="flex gap-2">
            {selectedList && (
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => setShowReceiptScanner(true)}
              >
                <ScanLine className="w-4 h-4 mr-2" />
                Scan Receipt
              </Button>
            )}
            <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
              <DialogTrigger asChild>
                <Button className="rounded-full bg-mise hover:bg-mise-dark" data-testid="create-list-btn">
                  <Plus className="w-4 h-4 mr-2" />
                  New List
                </Button>
              </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create Shopping List</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-4">
                <Input
                  placeholder="List name..."
                  value={newListName}
                  onChange={(e) => setNewListName(e.target.value)}
                  className="rounded-xl"
                  data-testid="new-list-name"
                />
                <Button 
                  onClick={handleCreateList}
                  className="w-full rounded-full bg-mise hover:bg-mise-dark"
                  disabled={creating || !newListName.trim()}
                >
                  {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                  Create List
                </Button>
              </div>
            </DialogContent>
            </Dialog>
          </div>
        </motion.div>

        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-mise" />
          </div>
        ) : lists.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-white rounded-2xl border border-border/60 p-12 text-center"
          >
            <ShoppingCart className="w-16 h-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="font-heading text-lg font-semibold mb-2">No shopping lists yet</h3>
            <p className="text-muted-foreground mb-6">
              Create a list or generate one from your meal plan
            </p>
            <Button 
              onClick={() => setShowCreateDialog(true)}
              className="rounded-full bg-mise hover:bg-mise-dark"
            >
              <Plus className="w-4 h-4 mr-2" />
              Create Your First List
            </Button>
          </motion.div>
        ) : (
          <div className="grid lg:grid-cols-3 gap-6">
            {/* Lists Sidebar */}
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="space-y-2"
            >
              {lists.map((list) => (
                <div
                  key={list.id}
                  className={`group p-4 rounded-xl cursor-pointer transition-all ${
                    selectedList?.id === list.id
                      ? 'bg-mise text-white'
                      : 'bg-white border border-border/60 hover:border-mise'
                  }`}
                  onClick={() => setSelectedList(list)}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">{list.name}</p>
                      <p className={`text-sm ${selectedList?.id === list.id ? 'text-mise-light' : 'text-muted-foreground'}`}>
                        {list.items.length} items
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className={`h-8 w-8 opacity-0 group-hover:opacity-100 ${
                        selectedList?.id === list.id ? 'text-white hover:text-white hover:bg-mise-dark' : ''
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
                className="lg:col-span-2 bg-white rounded-2xl border border-border/60 p-6"
              >
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h2 className="font-heading text-xl font-semibold">{selectedList.name}</h2>
                    <p className="text-sm text-muted-foreground">
                      {checkedCount} of {totalCount} items checked
                    </p>
                  </div>
                  {totalCount > 0 && (
                    <div className="w-20 h-2 bg-cream-subtle rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-mise rounded-full transition-all"
                        style={{ width: `${(checkedCount / totalCount) * 100}%` }}
                      />
                    </div>
                  )}
                </div>

                {/* Add Item */}
                <div className="flex gap-2 mb-6">
                  <Input
                    placeholder="Item name"
                    value={newItemName}
                    onChange={(e) => setNewItemName(e.target.value)}
                    className="flex-1 rounded-xl"
                    onKeyPress={(e) => e.key === 'Enter' && handleAddItem()}
                    data-testid="new-item-name"
                  />
                  <Input
                    placeholder="Qty"
                    value={newItemAmount}
                    onChange={(e) => setNewItemAmount(e.target.value)}
                    className="w-20 rounded-xl"
                    onKeyPress={(e) => e.key === 'Enter' && handleAddItem()}
                  />
                  <Button 
                    onClick={handleAddItem}
                    className="rounded-xl bg-mise hover:bg-mise-dark"
                    disabled={!newItemName.trim()}
                    data-testid="add-item-btn"
                  >
                    <Plus className="w-4 h-4" />
                  </Button>
                </div>

                {/* Items List */}
                <div className="space-y-2" data-testid="shopping-items">
                  {selectedList.items.length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">
                      No items in this list yet
                    </p>
                  ) : (
                    selectedList.items.map((item, idx) => (
                      <div
                        key={`${item.name}-${idx}`}
                        className={`group flex items-center gap-3 p-3 rounded-xl transition-colors ${
                          item.checked ? 'bg-mise-light/50' : 'bg-cream-subtle hover:bg-cream'
                        }`}
                      >
                        <Checkbox
                          checked={item.checked}
                          onCheckedChange={() => handleToggleItem(idx)}
                          className="data-[state=checked]:bg-mise data-[state=checked]:border-mise"
                        />
                        <span className={`flex-1 ${item.checked ? 'line-through text-muted-foreground' : ''}`}>
                          <span className="font-medium">{item.amount}</span>
                          {item.unit && <span> {item.unit}</span>}
                          <span> {item.name}</span>
                        </span>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-destructive"
                          onClick={() => handleRemoveItem(idx)}
                        >
                          <X className="w-4 h-4" />
                        </Button>
                      </div>
                    ))
                  )}
                </div>
              </motion.div>
            )}
          </div>
        )}

        {/* Receipt Scanner Modal */}
        {selectedList && (
          <ReceiptScanner
            listId={selectedList.id}
            onScanComplete={handleReceiptScanComplete}
            open={showReceiptScanner}
            onOpenChange={setShowReceiptScanner}
          />
        )}
      </div>
    </Layout>
  );
};
