import { useEffect, useRef } from 'react';

/**
 * Expose Cook Mode to system / Chromecast-adjacent media controls
 * (lock-screen next, headset next, some Google TV remotes via Media Session).
 */
export function useCookMediaSession({
  title,
  stepIndex,
  totalSteps,
  stepText,
  artworkUrl,
  onNext,
  onPrev,
  onTogglePlay,
  enabled = true,
}) {
  const handlersRef = useRef({ onNext, onPrev, onTogglePlay });
  handlersRef.current = { onNext, onPrev, onTogglePlay };
  const audioRef = useRef(null);

  useEffect(() => {
    if (!enabled || typeof navigator === 'undefined' || !('mediaSession' in navigator)) {
      return undefined;
    }

    // Keep a near-silent looping tone so Media Session stays active for "next"
    try {
      if (!audioRef.current) {
        // Tiny silent WAV
        const silent =
          'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQQAAAAAAA==';
        const audio = new Audio(silent);
        audio.loop = true;
        audio.volume = 0.001;
        audioRef.current = audio;
      }
      audioRef.current.play().catch(() => {});
    } catch {
      /* ignore */
    }

    const artwork = artworkUrl
      ? [{ src: artworkUrl, sizes: '512x512', type: 'image/png' }]
      : [];

    try {
      navigator.mediaSession.metadata = new window.MediaMetadata({
        title: totalSteps
          ? `Step ${stepIndex + 1} of ${totalSteps}`
          : 'Cook Mode',
        artist: title || 'Laro',
        album: 'Laro Cook Mode',
        artwork,
      });
      navigator.mediaSession.playbackState = 'playing';
    } catch {
      /* ignore */
    }

    const bind = (action, fn) => {
      try {
        navigator.mediaSession.setActionHandler(action, fn);
      } catch {
        /* unsupported action */
      }
    };

    bind('nexttrack', () => handlersRef.current.onNext?.());
    bind('previoustrack', () => handlersRef.current.onPrev?.());
    bind('play', () => handlersRef.current.onTogglePlay?.(true));
    bind('pause', () => handlersRef.current.onTogglePlay?.(false));
    bind('stop', () => handlersRef.current.onTogglePlay?.(false));

    return () => {
      try {
        audioRef.current?.pause();
      } catch {
        /* ignore */
      }
      ['nexttrack', 'previoustrack', 'play', 'pause', 'stop'].forEach((action) => {
        try {
          navigator.mediaSession.setActionHandler(action, null);
        } catch {
          /* ignore */
        }
      });
      try {
        navigator.mediaSession.playbackState = 'none';
        navigator.mediaSession.metadata = null;
      } catch {
        /* ignore */
      }
    };
  }, [enabled, title, stepIndex, totalSteps, stepText, artworkUrl]);
}
