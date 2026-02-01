import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from './ui/button';
import { recipeVersionsApi } from '../lib/api';
import {
  History,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  Loader2,
  GitCompare,
  Check,
  X,
  Clock,
  User
} from 'lucide-react';
import { toast } from 'sonner';
import { format } from 'date-fns';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';

export const RecipeVersions = ({ recipeId, currentVersion, onRestore }) => {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [restoring, setRestoring] = useState(null);
  const [compareDialogOpen, setCompareDialogOpen] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [comparison, setComparison] = useState(null);
  const [selectedVersions, setSelectedVersions] = useState([]);

  const loadVersions = async () => {
    setLoading(true);
    try {
      const res = await recipeVersionsApi.list(recipeId);
      setVersions(res.data.versions || []);
    } catch (err) {
      console.error('Failed to load versions:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (expanded && versions.length === 0) {
      loadVersions();
    }
  }, [expanded]);

  const handleRestore = async (version) => {
    setRestoring(version);
    try {
      await recipeVersionsApi.restore(recipeId, version);
      toast.success(`Restored to version ${version}`);
      loadVersions();
      if (onRestore) onRestore();
    } catch (err) {
      toast.error('Failed to restore version');
    } finally {
      setRestoring(null);
    }
  };

  const handleCompare = async () => {
    if (selectedVersions.length !== 2) {
      toast.error('Select exactly 2 versions to compare');
      return;
    }

    setComparing(true);
    try {
      const res = await recipeVersionsApi.compare(
        recipeId,
        selectedVersions[0],
        selectedVersions[1]
      );
      setComparison(res.data);
      setCompareDialogOpen(true);
    } catch (err) {
      toast.error('Failed to compare versions');
    } finally {
      setComparing(false);
    }
  };

  const toggleVersionSelection = (version) => {
    setSelectedVersions(prev => {
      if (prev.includes(version)) {
        return prev.filter(v => v !== version);
      }
      if (prev.length >= 2) {
        return [prev[1], version];
      }
      return [...prev, version];
    });
  };

  return (
    <div className="bg-white dark:bg-card rounded-2xl border border-border/60 overflow-hidden" data-testid="recipe-versions">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full p-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-mise" />
          <span className="font-medium">Version History</span>
          {currentVersion && (
            <span className="text-sm text-muted-foreground">
              (v{currentVersion})
            </span>
          )}
        </div>
        {expanded ? (
          <ChevronUp className="w-5 h-5 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-5 h-5 text-muted-foreground" />
        )}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            <div className="px-4 pb-4 border-t border-border/60">
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin text-mise" />
                </div>
              ) : versions.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground">
                  No version history yet
                </div>
              ) : (
                <div className="space-y-3 pt-4">
                  {/* Compare Button */}
                  {versions.length >= 2 && (
                    <div className="flex items-center justify-between pb-3 border-b border-border/60">
                      <p className="text-sm text-muted-foreground">
                        {selectedVersions.length === 0 
                          ? 'Select 2 versions to compare'
                          : `${selectedVersions.length}/2 selected`
                        }
                      </p>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={handleCompare}
                        disabled={selectedVersions.length !== 2 || comparing}
                        className="rounded-full"
                      >
                        {comparing ? (
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        ) : (
                          <GitCompare className="w-4 h-4 mr-2" />
                        )}
                        Compare
                      </Button>
                    </div>
                  )}

                  {/* Version List */}
                  {versions.map((version) => (
                    <div
                      key={version.version}
                      className={`flex items-center justify-between p-3 rounded-xl border transition-colors ${
                        selectedVersions.includes(version.version)
                          ? 'border-mise bg-mise-light/50'
                          : 'border-border/60 hover:bg-muted/50'
                      }`}
                    >
                      <div 
                        className="flex-1 cursor-pointer"
                        onClick={() => toggleVersionSelection(version.version)}
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-medium">Version {version.version}</span>
                          {version.version === currentVersion && (
                            <span className="px-2 py-0.5 bg-mise text-white text-xs rounded-full">
                              Current
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {format(new Date(version.created_at), 'MMM d, yyyy h:mm a')}
                          </span>
                          <span className="flex items-center gap-1">
                            <User className="w-3 h-3" />
                            {version.created_by_name}
                          </span>
                        </div>
                        {version.change_note && (
                          <p className="text-xs text-muted-foreground mt-1 italic">
                            "{version.change_note}"
                          </p>
                        )}
                      </div>
                      
                      {version.version !== currentVersion && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => handleRestore(version.version)}
                          disabled={restoring === version.version}
                          className="ml-2"
                        >
                          {restoring === version.version ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                          ) : (
                            <RotateCcw className="w-4 h-4" />
                          )}
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Compare Dialog */}
      <Dialog open={compareDialogOpen} onOpenChange={setCompareDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <GitCompare className="w-5 h-5 text-mise" />
              Version Comparison
            </DialogTitle>
          </DialogHeader>

          {comparison && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-sm text-muted-foreground">
                <span>Version {comparison.version_a.version}</span>
                <span>vs</span>
                <span>Version {comparison.version_b.version}</span>
              </div>

              {comparison.has_changes ? (
                <div className="space-y-3">
                  {comparison.differences.map((diff, i) => (
                    <div key={i} className="p-3 bg-muted/50 rounded-xl">
                      <p className="font-medium capitalize mb-2">{diff.field.replace('_', ' ')}</p>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div className="p-2 bg-red-50 dark:bg-red-900/20 rounded-lg">
                          <p className="text-xs text-red-600 dark:text-red-400 mb-1">
                            Version {comparison.version_a.version}
                          </p>
                          <p className="text-red-800 dark:text-red-200">
                            {Array.isArray(diff.version_a) 
                              ? diff.version_a.join(', ') 
                              : String(diff.version_a || '(empty)')}
                          </p>
                        </div>
                        <div className="p-2 bg-green-50 dark:bg-green-900/20 rounded-lg">
                          <p className="text-xs text-green-600 dark:text-green-400 mb-1">
                            Version {comparison.version_b.version}
                          </p>
                          <p className="text-green-800 dark:text-green-200">
                            {Array.isArray(diff.version_b) 
                              ? diff.version_b.join(', ') 
                              : String(diff.version_b || '(empty)')}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <Check className="w-12 h-12 text-teal mx-auto mb-2" />
                  <p>No differences found between these versions</p>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};
