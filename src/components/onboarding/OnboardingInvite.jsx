import React from 'react';
import { ChefHat, X } from 'lucide-react';
import { Button } from '../ui/button';

/** Soft corner invite — does not block navigation. */
export function OnboardingInvite({ userName, t, onSkip, onStart }) {
  return (
    <div
      className="fixed bottom-20 sm:bottom-6 left-4 right-4 sm:left-auto sm:right-6 sm:w-[360px] z-[60] pointer-events-auto"
      data-testid="user-onboarding-invite"
    >
      <div className="rounded-2xl bg-background border border-border shadow-xl p-4">
        <div className="flex items-start gap-3 mb-3">
          <div className="w-10 h-10 rounded-xl bg-laro/10 flex items-center justify-center shrink-0">
            <ChefHat className="w-5 h-5 text-laro" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="font-heading font-semibold leading-tight">
              {t('welcomeToLaro', { name: userName || '' })}
            </p>
            <p className="text-sm text-muted-foreground mt-1">{t('onboardingInviteBody')}</p>
          </div>
          <button
            type="button"
            onClick={onSkip}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground shrink-0"
            aria-label={t('skip')}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            className="flex-1 rounded-full"
            onClick={onSkip}
            data-testid="onboarding-explore-first"
          >
            {t('onboardingExploreFirst')}
          </Button>
          <Button
            className="flex-1 rounded-full bg-laro hover:bg-laro-dark"
            onClick={onStart}
            data-testid="onboarding-start-setup"
          >
            {t('onboardingStartSetup')}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default OnboardingInvite;
