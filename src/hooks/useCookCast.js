import { useCallback, useEffect, useRef, useState } from 'react';
import {
  buildSetStepMessage,
  buildShowMessage,
  getCastSession,
  initCastContext,
  isCastConfigured,
  sendCookCastMessage,
} from '../lib/castCook';

/**
 * Chromecast cook-mode sender: Cast button state + push step updates to TV.
 */
export function useCookCast({ title, steps, stepIndex, timerLabel, enabled = true }) {
  const [available, setAvailable] = useState(false);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  const readyRef = useRef(false);
  const payloadRef = useRef({ title, steps, stepIndex, timerLabel });

  payloadRef.current = { title, steps, stepIndex, timerLabel };

  const syncFull = useCallback(() => {
    const p = payloadRef.current;
    return sendCookCastMessage(
      buildShowMessage({
        title: p.title,
        steps: p.steps,
        stepIndex: p.stepIndex,
        timerLabel: p.timerLabel,
      })
    );
  }, []);

  useEffect(() => {
    if (!enabled || !isCastConfigured()) {
      setAvailable(false);
      return undefined;
    }

    let cancelled = false;
    let context;

    const onSessionState = (event) => {
      const state = event.sessionState;
      const SessionState = window.cast.framework.SessionState;
      const isConnected =
        state === SessionState.SESSION_STARTED || state === SessionState.SESSION_RESUMED;
      setConnected(isConnected);
      if (isConnected) {
        syncFull();
      }
    };

    (async () => {
      try {
        context = await initCastContext();
        if (cancelled) return;
        readyRef.current = true;
        setAvailable(true);
        setError(null);
        context.addEventListener(
          window.cast.framework.CastContextEventType.SESSION_STATE_CHANGED,
          onSessionState
        );
        setConnected(Boolean(getCastSession()));
        if (getCastSession()) syncFull();
      } catch (err) {
        if (!cancelled) {
          setAvailable(false);
          setError(err?.message || 'Cast unavailable');
        }
      }
    })();

    return () => {
      cancelled = true;
      try {
        context?.removeEventListener(
          window.cast.framework.CastContextEventType.SESSION_STATE_CHANGED,
          onSessionState
        );
      } catch {
        /* ignore */
      }
    };
  }, [enabled, syncFull]);

  // Push step / timer changes while connected
  useEffect(() => {
    if (!connected) return;
    sendCookCastMessage(buildSetStepMessage(stepIndex, timerLabel));
  }, [connected, stepIndex, timerLabel]);

  // Re-send full recipe if steps/title change mid-session
  useEffect(() => {
    if (!connected) return;
    syncFull();
  }, [connected, title, steps, syncFull]);

  const requestSession = useCallback(async () => {
    if (!isCastConfigured()) {
      setError('Add a Cast App ID in Settings / env to enable Chromecast');
      return false;
    }
    try {
      await initCastContext();
      await window.cast.framework.CastContext.getInstance().requestSession();
      setConnected(true);
      await syncFull();
      return true;
    } catch (err) {
      // User cancel is normal
      if (String(err?.code || err?.message || err).toLowerCase().includes('cancel')) {
        return false;
      }
      setError(err?.message || 'Could not start Cast');
      return false;
    }
  }, [syncFull]);

  const endSession = useCallback(async () => {
    try {
      await sendCookCastMessage({ type: 'clear' });
      await window.cast.framework.CastContext.getInstance().endCurrentSession(true);
    } catch {
      /* ignore */
    }
    setConnected(false);
  }, []);

  return {
    castConfigured: isCastConfigured(),
    castAvailable: available,
    castConnected: connected,
    castError: error,
    requestSession,
    endSession,
    syncFull,
  };
}
