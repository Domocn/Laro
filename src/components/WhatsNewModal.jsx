import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useLanguage } from '../context/LanguageContext';
import { onboardingKey } from '../lib/onboarding';
import { usePopupTurn } from '../lib/popupQueue';
import { getSeen, markSeen } from '../lib/uiSeen';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from './ui/dialog';
import { Button } from './ui/button';
import { ListTree, Leaf, Scale, BookOpen, ShieldCheck, Sparkles } from 'lucide-react';

/**
 * "What's new" popup, shown once per user per release after they sign in.
 *
 * To announce a new release: change WHATS_NEW_RELEASE and the items below.
 * Everyone who has not seen that release id gets the popup once.
 */
export const WHATS_NEW_RELEASE = '2026-11';

const ITEMS = [
  { icon: ListTree, titleKey: 'whatsNewSectionsTitle', bodyKey: 'whatsNewSectionsBody' },
  { icon: Leaf, titleKey: 'whatsNewVersionsTitle', bodyKey: 'whatsNewVersionsBody' },
  { icon: Scale, titleKey: 'whatsNewMacrosTitle', bodyKey: 'whatsNewMacrosBody' },
  { icon: BookOpen, titleKey: 'whatsNewCookbooksTitle', bodyKey: 'whatsNewCookbooksBody' },
  { icon: ShieldCheck, titleKey: 'whatsNewSecurityTitle', bodyKey: 'whatsNewSecurityBody' },
];

const seenKey = (userId) => `laro_whats_new_${userId}`;

function read(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function markSeenLocal(userId) {
  try {
    localStorage.setItem(seenKey(userId), WHATS_NEW_RELEASE);
  } catch {
    /* private mode: it may show again next visit, which is harmless */
  }
}

export const WhatsNewModal = () => {
  const { user, isAuthenticated } = useAuth();
  const { t } = useLanguage();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || !user?.id) return undefined;
    if (read(seenKey(user.id)) === WHATS_NEW_RELEASE) return undefined;

    // Brand-new accounts get the onboarding instead; everything is new to them.
    const onboarding = read(onboardingKey(user.id));
    if (onboarding === 'pending') {
      markSeenLocal(user.id);
      markSeen(user.id, 'whats_new', WHATS_NEW_RELEASE);
      return undefined;
    }

    let cancelled = false;
    let timer;
    // Once per ACCOUNT per release (server), not per browser.
    getSeen(user.id).then((seen) => {
      if (cancelled) return;
      if (seen.whats_new === WHATS_NEW_RELEASE) {
        try { localStorage.setItem(seenKey(user.id), WHATS_NEW_RELEASE); } catch { /* ignore */ }
        return;
      }
      timer = setTimeout(() => setOpen(true), 1200);
    });
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [isAuthenticated, user?.id]);

  // Waits its turn behind password/name prompts, onboarding and the tour (lib/popupQueue).
  const myTurn = usePopupTurn('whats-new', open);

  const close = () => {
    if (user?.id) {
      markSeenLocal(user.id);
      markSeen(user.id, 'whats_new', WHATS_NEW_RELEASE);
    }
    setOpen(false);
  };

  if (!isAuthenticated) return null;

  return (
    <Dialog open={open && myTurn} onOpenChange={(next) => (next ? setOpen(true) : close())}>
      <DialogContent className="max-w-md rounded-2xl">
        <DialogHeader>
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-laro/10">
            <Sparkles className="h-6 w-6 text-laro" aria-hidden="true" />
          </div>
          <DialogTitle className="text-center">{t('whatsNewTitle')}</DialogTitle>
          <DialogDescription className="text-center">{t('whatsNewSubtitle')}</DialogDescription>
        </DialogHeader>

        <ul className="mt-2 space-y-4">
          {ITEMS.map(({ icon: Icon, titleKey, bodyKey }) => (
            <li key={titleKey} className="flex gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-muted">
                <Icon className="h-5 w-5 text-laro" aria-hidden="true" />
              </div>
              <div>
                <p className="text-sm font-semibold text-foreground">{t(titleKey)}</p>
                <p className="text-sm text-muted-foreground">{t(bodyKey)}</p>
              </div>
            </li>
          ))}
        </ul>

        <DialogFooter className="mt-4">
          <Button className="w-full rounded-full bg-laro hover:bg-laro-dark" onClick={close}>
            {t('whatsNewGotIt')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
