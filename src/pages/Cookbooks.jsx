import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Layout } from '../components/Layout';
import { cookbooksApi } from '../lib/api';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Plus, Search, BookOpen, MoreVertical, Edit2, Trash2,
  BookMarked, Barcode, Loader2, X, ChefHat
} from 'lucide-react';
import { toast } from 'sonner';
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

export const Cookbooks = () => {
  const [cookbooks, setCookbooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingCookbook, setEditingCookbook] = useState(null);
  const [formData, setFormData] = useState({ title: '', author: '', isbn: '', notes: '' });
  const [saving, setSaving] = useState(false);
  const [lookingUpISBN, setLookingUpISBN] = useState(false);

  const loadCookbooks = useCallback(async () => {
    try {
      setLoading(true);
      const res = await cookbooksApi.getAll(search || undefined);
      setCookbooks(res.data || []);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Couldn\'t load your cookbooks. Please try again. (E-CK001)');
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    loadCookbooks();
  }, [loadCookbooks]);

  const handleSearch = (e) => {
    e.preventDefault();
    loadCookbooks();
  };

  const handleISBNLookup = async () => {
    if (!formData.isbn) {
      toast.error('Please enter an ISBN');
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
        toast.success('Book info found!');
      } else {
        toast.info('No book found with this ISBN');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Couldn\'t look up that ISBN. Please try again. (E-CK002)');
    } finally {
      setLookingUpISBN(false);
    }
  };

  const handleCreate = async () => {
    if (!formData.title.trim()) {
      toast.error('Title is required');
      return;
    }
    setSaving(true);
    try {
      const res = await cookbooksApi.create(formData);
      setCookbooks([res.data, ...cookbooks]);
      setShowCreateModal(false);
      setFormData({ title: '', author: '', isbn: '', notes: '' });
      toast.success('Cookbook added!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Couldn\'t create that cookbook. Please try again. (E-CK003)');
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = async () => {
    if (!formData.title.trim()) {
      toast.error('Title is required');
      return;
    }
    setSaving(true);
    try {
      const res = await cookbooksApi.update(editingCookbook.id, formData);
      setCookbooks(cookbooks.map(c => c.id === editingCookbook.id ? res.data : c));
      setShowEditModal(false);
      setEditingCookbook(null);
      setFormData({ title: '', author: '', isbn: '', notes: '' });
      toast.success('Cookbook updated!');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Couldn\'t update that cookbook. Please try again. (E-CK004)');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (cookbook) => {
    if (!window.confirm(`Delete "${cookbook.title}"? This cannot be undone.`)) return;
    try {
      await cookbooksApi.delete(cookbook.id);
      setCookbooks(cookbooks.filter(c => c.id !== cookbook.id));
      toast.success('Cookbook deleted');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Couldn\'t delete that cookbook. Please try again. (E-CK005)');
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

  const CookbookForm = ({ isEdit = false }) => (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="isbn">ISBN (optional)</Label>
        <div className="flex gap-2">
          <Input
            id="isbn"
            placeholder="978-0-123456-78-9"
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
        <p className="text-xs text-muted-foreground">Enter ISBN to auto-fill book details</p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="title">Title *</Label>
        <Input
          id="title"
          placeholder="The Joy of Cooking"
          value={formData.title}
          onChange={(e) => setFormData({ ...formData, title: e.target.value })}
          className="rounded-xl"
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="author">Author</Label>
        <Input
          id="author"
          placeholder="Irma S. Rombauer"
          value={formData.author}
          onChange={(e) => setFormData({ ...formData, author: e.target.value })}
          className="rounded-xl"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="notes">Notes</Label>
        <textarea
          id="notes"
          placeholder="Personal notes about this cookbook..."
          value={formData.notes}
          onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
          className="w-full px-3 py-2 rounded-xl border border-border/60 bg-white min-h-[80px] resize-none focus:outline-none focus:ring-2 focus:ring-laro"
        />
      </div>
    </div>
  );

  return (
    <Layout>
      <div className="space-y-8">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-center md:justify-between gap-4"
        >
          <div>
            <h1 className="font-heading text-3xl font-bold flex items-center gap-3">
              <BookMarked className="w-8 h-8 text-laro" />
              Cookbooks
            </h1>
            <p className="text-muted-foreground mt-1">
              {cookbooks.length} cookbook{cookbooks.length !== 1 ? 's' : ''} in your library
            </p>
          </div>
          <Button
            className="rounded-full bg-laro hover:bg-laro-dark"
            onClick={() => {
              setFormData({ title: '', author: '', isbn: '', notes: '' });
              setShowCreateModal(true);
            }}
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Cookbook
          </Button>
        </motion.div>

        {/* Search */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <form onSubmit={handleSearch} className="flex gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-muted-foreground" />
              <Input
                placeholder="Search cookbooks..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10 rounded-xl bg-white border-border/60"
              />
            </div>
            <Button type="submit" variant="outline" className="rounded-xl">
              Search
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
            <h3 className="font-heading text-lg font-semibold mb-2">No cookbooks yet</h3>
            <p className="text-muted-foreground mb-6">
              {search ? 'No cookbooks match your search' : 'Start building your cookbook library'}
            </p>
            <Button
              className="rounded-full bg-laro hover:bg-laro-dark"
              onClick={() => setShowCreateModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Your First Cookbook
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
                    <div className="w-12 h-12 rounded-xl bg-laro-light flex items-center justify-center">
                      <BookOpen className="w-6 h-6 text-laro" />
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
                          Edit
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onClick={() => handleDelete(cookbook)}
                          className="text-red-600"
                        >
                          <Trash2 className="w-4 h-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                  <h3 className="font-heading font-semibold text-lg mb-1 line-clamp-2">
                    {cookbook.title}
                  </h3>
                  {cookbook.author && (
                    <p className="text-sm text-muted-foreground mb-2">by {cookbook.author}</p>
                  )}
                  {cookbook.recipe_count !== undefined && (
                    <div className="flex items-center gap-1 text-sm text-muted-foreground">
                      <ChefHat className="w-4 h-4" />
                      {cookbook.recipe_count} recipe{cookbook.recipe_count !== 1 ? 's' : ''}
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
                Add Cookbook
              </DialogTitle>
            </DialogHeader>
            <CookbookForm />
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowCreateModal(false)} className="rounded-full">
                Cancel
              </Button>
              <Button onClick={handleCreate} disabled={saving} className="rounded-full bg-laro hover:bg-laro-dark">
                {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
                Add Cookbook
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
                Edit Cookbook
              </DialogTitle>
            </DialogHeader>
            <CookbookForm isEdit />
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowEditModal(false)} className="rounded-full">
                Cancel
              </Button>
              <Button onClick={handleEdit} disabled={saving} className="rounded-full bg-laro hover:bg-laro-dark">
                {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                Save Changes
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </Layout>
  );
};

export default Cookbooks;
