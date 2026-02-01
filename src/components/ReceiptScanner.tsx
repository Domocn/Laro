import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from './ui/button';
import { Checkbox } from './ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import {
  Camera,
  Upload,
  Loader2,
  Check,
  X,
  Receipt,
  AlertCircle,
  CheckCircle2
} from 'lucide-react';
import { toast } from 'sonner';
import { shoppingListApi } from '../lib/api';

export const ReceiptScanner = ({ listId, onScanComplete, open, onOpenChange }) => {
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [matches, setMatches] = useState([]);
  const [selectedMatches, setSelectedMatches] = useState(new Set());
  const [previewUrl, setPreviewUrl] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Show preview
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);

    // Scan the receipt
    await scanReceipt(file);
  };

  const scanReceipt = async (file) => {
    setScanning(true);
    setScanResult(null);
    setMatches([]);

    try {
      const res = await shoppingListApi.scanReceipt(listId, file, true);
      setScanResult(res.data.scan_result);
      setMatches(res.data.matches);

      // Pre-select high and medium confidence matches
      const preSelected = new Set();
      res.data.matches.forEach((match, idx) => {
        if ((match.confidence === 'high' || match.confidence === 'medium') && match.matched_item) {
          preSelected.add(idx);
        }
      });
      setSelectedMatches(preSelected);

      if (res.data.auto_checked_count > 0) {
        toast.success(`Automatically checked ${res.data.auto_checked_count} items`);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to scan receipt');
    } finally {
      setScanning(false);
    }
  };

  const handleApplyMatches = async () => {
    const matchesToApply = matches.filter((_, idx) => selectedMatches.has(idx) && !matches[idx].auto_checked);

    if (matchesToApply.length === 0) {
      toast.info('No additional items to check');
      handleClose();
      return;
    }

    try {
      const res = await shoppingListApi.applyMatches(listId, matchesToApply);
      toast.success(res.data.message);
      onScanComplete?.();
      handleClose();
    } catch (error) {
      toast.error('Failed to apply matches');
    }
  };

  const handleClose = () => {
    setScanResult(null);
    setMatches([]);
    setSelectedMatches(new Set());
    setPreviewUrl(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
    onOpenChange(false);
  };

  const toggleMatch = (idx) => {
    const newSelected = new Set(selectedMatches);
    if (newSelected.has(idx)) {
      newSelected.delete(idx);
    } else {
      newSelected.add(idx);
    }
    setSelectedMatches(newSelected);
  };

  const getConfidenceBadge = (confidence) => {
    const styles = {
      high: 'bg-green-100 text-green-800',
      medium: 'bg-yellow-100 text-yellow-800',
      low: 'bg-gray-100 text-gray-600'
    };
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[confidence]}`}>
        {confidence}
      </span>
    );
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Receipt className="w-5 h-5" />
            Scan Receipt
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 pt-2">
          {/* Upload Section */}
          {!scanResult && !scanning && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Take a photo or upload an image of your receipt to automatically check off purchased items.
              </p>

              <div className="flex gap-3">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  capture="environment"
                  onChange={handleFileSelect}
                  className="hidden"
                  id="receipt-camera"
                />
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleFileSelect}
                  className="hidden"
                  id="receipt-upload"
                />

                <Button
                  onClick={() => document.getElementById('receipt-camera').click()}
                  className="flex-1 rounded-xl bg-mise hover:bg-mise-dark"
                >
                  <Camera className="w-4 h-4 mr-2" />
                  Take Photo
                </Button>

                <Button
                  variant="outline"
                  onClick={() => document.getElementById('receipt-upload').click()}
                  className="flex-1 rounded-xl"
                >
                  <Upload className="w-4 h-4 mr-2" />
                  Upload
                </Button>
              </div>
            </div>
          )}

          {/* Scanning State */}
          {scanning && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="py-8 text-center"
            >
              <Loader2 className="w-12 h-12 animate-spin text-mise mx-auto mb-4" />
              <p className="text-muted-foreground">Scanning receipt...</p>
              <p className="text-sm text-muted-foreground mt-1">This may take a few seconds</p>

              {previewUrl && (
                <div className="mt-4 rounded-xl overflow-hidden border border-border/60">
                  <img
                    src={previewUrl}
                    alt="Receipt preview"
                    className="max-h-32 mx-auto object-contain"
                  />
                </div>
              )}
            </motion.div>
          )}

          {/* Results */}
          {scanResult && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-4"
            >
              {/* Receipt Info */}
              {(scanResult.store_name || scanResult.date) && (
                <div className="bg-cream-subtle rounded-xl p-3">
                  <div className="flex justify-between text-sm">
                    {scanResult.store_name && (
                      <span className="font-medium">{scanResult.store_name}</span>
                    )}
                    {scanResult.date && (
                      <span className="text-muted-foreground">{scanResult.date}</span>
                    )}
                  </div>
                  {scanResult.total && (
                    <p className="text-sm text-muted-foreground mt-1">
                      Total: {scanResult.total}
                    </p>
                  )}
                </div>
              )}

              {/* Match Results */}
              <div>
                <h3 className="font-medium mb-2">
                  Found {scanResult.items.length} items
                </h3>

                {matches.length === 0 ? (
                  <div className="text-center py-4 text-muted-foreground">
                    <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>No items matched your shopping list</p>
                  </div>
                ) : (
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {matches.map((match, idx) => (
                      <div
                        key={idx}
                        className={`flex items-center gap-3 p-3 rounded-xl transition-colors ${
                          match.matched_item
                            ? match.auto_checked
                              ? 'bg-green-50 border border-green-200'
                              : 'bg-cream-subtle hover:bg-cream'
                            : 'bg-gray-50 opacity-60'
                        }`}
                      >
                        {match.matched_item && !match.auto_checked && (
                          <Checkbox
                            checked={selectedMatches.has(idx)}
                            onCheckedChange={() => toggleMatch(idx)}
                            className="data-[state=checked]:bg-mise data-[state=checked]:border-mise"
                          />
                        )}
                        {match.auto_checked && (
                          <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0" />
                        )}
                        {!match.matched_item && (
                          <X className="w-5 h-5 text-gray-400 flex-shrink-0" />
                        )}

                        <div className="flex-1 min-w-0">
                          <p className={`text-sm truncate ${match.auto_checked ? 'line-through text-muted-foreground' : ''}`}>
                            {match.scanned_item}
                          </p>
                          {match.matched_item && (
                            <p className="text-xs text-muted-foreground truncate">
                              {match.auto_checked ? 'Checked: ' : 'Matches: '}
                              {match.matched_item}
                            </p>
                          )}
                        </div>

                        {match.matched_item && getConfidenceBadge(match.confidence)}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex gap-3 pt-2">
                <Button
                  variant="outline"
                  onClick={handleClose}
                  className="flex-1 rounded-xl"
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleApplyMatches}
                  className="flex-1 rounded-xl bg-mise hover:bg-mise-dark"
                  disabled={selectedMatches.size === 0 && !matches.some(m => m.auto_checked)}
                >
                  <Check className="w-4 h-4 mr-2" />
                  Apply ({selectedMatches.size} items)
                </Button>
              </div>
            </motion.div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};
