import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import {
  Shield,
  Plus,
  Edit2,
  Trash2,
  Loader2,
  Save,
  X,
  Users,
  ChefHat,
  ShoppingCart,
  Calendar,
  Settings,
  Eye,
  Pencil
} from 'lucide-react';
import { toast } from 'sonner';
import { rolesApi } from '../lib/api';

const PERMISSION_CATEGORIES = {
  recipes: {
    label: 'Recipes',
    icon: ChefHat,
    permissions: [
      { key: 'create', label: 'Create recipes' },
      { key: 'read', label: 'View recipes' },
      { key: 'update_own', label: 'Edit own recipes' },
      { key: 'update_any', label: 'Edit any recipe' },
      { key: 'delete_own', label: 'Delete own recipes' },
      { key: 'delete_any', label: 'Delete any recipe' },
    ]
  },
  meal_plans: {
    label: 'Meal Plans',
    icon: Calendar,
    permissions: [
      { key: 'create', label: 'Create meal plans' },
      { key: 'read', label: 'View meal plans' },
      { key: 'update', label: 'Edit meal plans' },
      { key: 'delete', label: 'Delete meal plans' },
    ]
  },
  shopping_lists: {
    label: 'Shopping Lists',
    icon: ShoppingCart,
    permissions: [
      { key: 'create', label: 'Create lists' },
      { key: 'read', label: 'View lists' },
      { key: 'update', label: 'Edit lists' },
      { key: 'delete', label: 'Delete lists' },
    ]
  },
  household: {
    label: 'Household',
    icon: Users,
    permissions: [
      { key: 'view_members', label: 'View members' },
      { key: 'invite_members', label: 'Invite members' },
      { key: 'remove_members', label: 'Remove members' },
      { key: 'manage_settings', label: 'Manage settings' },
    ]
  },
  admin: {
    label: 'Admin',
    icon: Shield,
    permissions: [
      { key: 'view_users', label: 'View all users' },
      { key: 'manage_users', label: 'Manage users' },
      { key: 'view_settings', label: 'View settings' },
      { key: 'manage_settings', label: 'Manage settings' },
      { key: 'view_audit_log', label: 'View audit log' },
      { key: 'manage_backups', label: 'Manage backups' },
    ]
  }
};

export const RolesManager = () => {
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showEditor, setShowEditor] = useState(false);
  const [editingRole, setEditingRole] = useState(null);
  const [saving, setSaving] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    color: '#6C5CE7',
    permissions: {}
  });

  useEffect(() => {
    loadRoles();
  }, []);

  const loadRoles = async () => {
    setLoading(true);
    try {
      const res = await rolesApi.list();
      setRoles(res.data.roles || []);
    } catch (error) {
      toast.error('Failed to load roles');
    } finally {
      setLoading(false);
    }
  };

  const loadDefaultPermissions = async () => {
    try {
      const res = await rolesApi.getDefaultPermissions();
      return res.data.permissions;
    } catch (error) {
      return {};
    }
  };

  const handleCreateNew = async () => {
    const defaultPerms = await loadDefaultPermissions();
    setFormData({
      name: '',
      description: '',
      color: '#6C5CE7',
      permissions: defaultPerms
    });
    setEditingRole(null);
    setShowEditor(true);
  };

  const handleEdit = (role) => {
    if (role.is_builtin) {
      toast.error('Cannot edit built-in roles');
      return;
    }
    setFormData({
      name: role.name,
      description: role.description || '',
      color: role.color || '#6C5CE7',
      permissions: role.permissions || {}
    });
    setEditingRole(role);
    setShowEditor(true);
  };

  const handleDelete = async (role) => {
    if (role.is_builtin) {
      toast.error('Cannot delete built-in roles');
      return;
    }
    
    if (!window.confirm(`Delete role "${role.name}"? Users with this role will need to be reassigned.`)) {
      return;
    }

    try {
      await rolesApi.delete(role.id);
      toast.success('Role deleted');
      loadRoles();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to delete role');
    }
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      toast.error('Role name is required');
      return;
    }

    setSaving(true);
    try {
      if (editingRole) {
        await rolesApi.update(editingRole.id, formData);
        toast.success('Role updated');
      } else {
        await rolesApi.create(formData);
        toast.success('Role created');
      }
      setShowEditor(false);
      loadRoles();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save role');
    } finally {
      setSaving(false);
    }
  };

  const togglePermission = (category, permission) => {
    setFormData(prev => ({
      ...prev,
      permissions: {
        ...prev.permissions,
        [category]: {
          ...prev.permissions[category],
          [permission]: !prev.permissions[category]?.[permission]
        }
      }
    }));
  };

  const COLORS = [
    '#6C5CE7', '#00D2D3', '#FF6B6B', '#FFA502', 
    '#2ED573', '#5352ED', '#FF4757', '#747D8C'
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <Loader2 className="w-8 h-8 animate-spin text-mise" />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="roles-manager">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-heading font-semibold text-lg">Custom Roles</h2>
          <p className="text-sm text-muted-foreground">Create and manage user roles with custom permissions</p>
        </div>
        <Button
          onClick={handleCreateNew}
          className="rounded-full bg-mise hover:bg-mise-dark"
        >
          <Plus className="w-4 h-4 mr-2" />
          Create Role
        </Button>
      </div>

      {/* Roles List */}
      <div className="space-y-3">
        {roles.map((role) => (
          <div
            key={role.id}
            className="bg-white dark:bg-card rounded-xl border border-border/60 p-4 flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center"
                style={{ backgroundColor: `${role.color}20` }}
              >
                <Shield className="w-5 h-5" style={{ color: role.color }} />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <p className="font-medium">{role.name}</p>
                  {role.is_builtin && (
                    <span className="px-2 py-0.5 bg-gray-100 dark:bg-muted text-xs rounded-full">
                      Built-in
                    </span>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">{role.description || 'No description'}</p>
              </div>
            </div>
            
            {!role.is_builtin && (
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => handleEdit(role)}>
                  <Edit2 className="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="sm" onClick={() => handleDelete(role)}>
                  <Trash2 className="w-4 h-4 text-red-500" />
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Editor Modal */}
      <AnimatePresence>
        {showEditor && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-white dark:bg-card rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col"
            >
              {/* Header */}
              <div className="p-4 border-b border-border/60 flex items-center justify-between">
                <h3 className="font-heading font-semibold text-lg">
                  {editingRole ? 'Edit Role' : 'Create New Role'}
                </h3>
                <Button variant="ghost" size="sm" onClick={() => setShowEditor(false)}>
                  <X className="w-5 h-5" />
                </Button>
              </div>

              {/* Content */}
              <div className="flex-1 overflow-y-auto p-4 space-y-6">
                {/* Basic Info */}
                <div className="space-y-4">
                  <div>
                    <Label>Role Name *</Label>
                    <Input
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      placeholder="e.g., Editor, Viewer, Family Member"
                      className="mt-1 rounded-xl"
                    />
                  </div>
                  
                  <div>
                    <Label>Description</Label>
                    <Input
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      placeholder="What can users with this role do?"
                      className="mt-1 rounded-xl"
                    />
                  </div>

                  <div>
                    <Label>Color</Label>
                    <div className="flex gap-2 mt-2">
                      {COLORS.map((color) => (
                        <button
                          key={color}
                          onClick={() => setFormData({ ...formData, color })}
                          className={`w-8 h-8 rounded-full transition-transform ${
                            formData.color === color ? 'scale-110 ring-2 ring-offset-2 ring-mise' : ''
                          }`}
                          style={{ backgroundColor: color }}
                        />
                      ))}
                    </div>
                  </div>
                </div>

                {/* Permissions */}
                <div>
                  <h4 className="font-medium mb-4">Permissions</h4>
                  <div className="space-y-4">
                    {Object.entries(PERMISSION_CATEGORIES).map(([categoryKey, category]) => {
                      const Icon = category.icon;
                      return (
                        <div key={categoryKey} className="border border-border/60 rounded-xl overflow-hidden">
                          <div className="p-3 bg-cream-subtle dark:bg-muted flex items-center gap-2">
                            <Icon className="w-4 h-4 text-mise" />
                            <span className="font-medium text-sm">{category.label}</span>
                          </div>
                          <div className="p-3 grid grid-cols-2 gap-3">
                            {category.permissions.map((perm) => (
                              <label
                                key={perm.key}
                                className="flex items-center gap-2 cursor-pointer"
                              >
                                <Switch
                                  checked={formData.permissions[categoryKey]?.[perm.key] || false}
                                  onCheckedChange={() => togglePermission(categoryKey, perm.key)}
                                />
                                <span className="text-sm">{perm.label}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="p-4 border-t border-border/60 flex gap-2 justify-end">
                <Button variant="outline" onClick={() => setShowEditor(false)} className="rounded-full">
                  Cancel
                </Button>
                <Button
                  onClick={handleSave}
                  disabled={saving}
                  className="rounded-full bg-mise hover:bg-mise-dark"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />}
                  {editingRole ? 'Save Changes' : 'Create Role'}
                </Button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default RolesManager;
