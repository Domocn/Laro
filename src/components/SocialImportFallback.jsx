import React, { useState } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Loader2, Sparkles, Video, ClipboardPaste, Image as ImageIcon } from 'lucide-react';
import { toast } from 'sonner';
import { aiApi } from '../lib/api';
import { getAiQuotaErrorMessage } from '../lib/aiQuota';
import { useLanguage } from '../context/LanguageContext';

/**
 * Shown after a social/URL import fails.
 * Steps: 1) paste caption  2) optional mp4  3) tip to use photo tab
 */
export function SocialImportFallback({
  failedUrl = '',
  onSuccess,
  onSwitchToPhoto,
}) {
  const { t } = useLanguage();
  const [caption, setCaption] = useState('');
  const [videoFile, setVideoFile] = useState(null);
  const [loading, setLoading] = useState(false);

  const looksSocial = /tiktok|instagram|youtu\.?be|facebook|fb\.watch|reel/i.test(
    failedUrl || ''
  );

  const handleSubmit = async () => {
    if (!caption.trim() && !videoFile) {
      toast.error(t('toastNeedCaptionOrVideo'));
      return;
    }
    if (videoFile && videoFile.size > 80_000_000) {
      toast.error(t('toastVideoTooLarge'));
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('caption', caption.trim());
      if (videoFile) formData.append('file', videoFile);
      const res = await aiApi.importVideo(formData);
      const recipe = res.data.recipe || res.data;
      toast.success(t('toastRecipeExtractedSuccess'));
      onSuccess?.(recipe, res.data);
    } catch (error) {
      toast.error(
        getAiQuotaErrorMessage(error, error.response?.data?.detail || t('toastVideoImportFailed'))
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4 space-y-4"
      data-testid="social-import-fallback"
    >
      <div>
        <p className="font-semibold text-sm">{t('urlImportFailedTitle')}</p>
        <p className="text-xs text-muted-foreground mt-1">
          {looksSocial ? t('urlImportFailedSocialHint') : t('urlImportFailedGenericHint')}
        </p>
      </div>

      <ol className="space-y-4 list-decimal list-inside text-sm">
        <li className="space-y-2">
          <Label className="inline-flex items-center gap-1.5 font-medium">
            <ClipboardPaste className="w-3.5 h-3.5" />
            {t('stepPasteCaption')}
          </Label>
          <Textarea
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            placeholder={t('captionPlaceholder')}
            className="min-h-[100px] rounded-xl mt-1"
            data-testid="fallback-caption-input"
          />
        </li>

        <li className="space-y-2">
          <Label className="inline-flex items-center gap-1.5 font-medium">
            <Video className="w-3.5 h-3.5" />
            {t('stepUploadVideoOptional')}
          </Label>
          <Input
            type="file"
            accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm"
            onChange={(e) => setVideoFile(e.target.files?.[0] || null)}
            className="rounded-xl mt-1"
            data-testid="fallback-video-input"
          />
          <p className="text-xs text-muted-foreground">{t('videoUploadHint')}</p>
        </li>

        {onSwitchToPhoto && (
          <li>
            <button
              type="button"
              onClick={onSwitchToPhoto}
              className="inline-flex items-center gap-1.5 text-laro hover:underline text-sm font-medium"
            >
              <ImageIcon className="w-3.5 h-3.5" />
              {t('stepTryPhotoInstead')}
            </button>
          </li>
        )}
      </ol>

      <Button
        onClick={handleSubmit}
        disabled={loading || (!caption.trim() && !videoFile)}
        className="w-full rounded-full bg-laro hover:bg-laro-dark h-11"
        data-testid="fallback-import-btn"
      >
        {loading ? (
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : (
          <>
            <Sparkles className="w-4 h-4 mr-2" />
            {t('importFromCaptionVideo')}
          </>
        )}
      </Button>
    </div>
  );
}

export default SocialImportFallback;
