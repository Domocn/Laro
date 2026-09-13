/**
 * @jest-environment jsdom
 */
import {
  guidedTourKey,
  isOnboardingPending,
  markOnboardingPending,
  notifyFindAgainOnce,
  onboardingKey,
  requestAppTour,
  requestOnboarding,
} from './onboarding';

describe('onboarding helpers', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('does not treat missing localStorage as pending (returning users)', () => {
    expect(isOnboardingPending('user-a')).toBe(false);
    expect(localStorage.getItem(onboardingKey('user-a'))).toBeNull();
  });

  it('marks signup as pending only when explicitly set', () => {
    markOnboardingPending('user-a');
    expect(isOnboardingPending('user-a')).toBe(true);
    expect(localStorage.getItem(onboardingKey('user-a'))).toBe('pending');
  });

  it('requestOnboarding sets pending and dispatches start event', () => {
    const seen = [];
    const handler = () => seen.push('start');
    window.addEventListener('laro-start-onboarding', handler);
    requestOnboarding('user-b');
    window.removeEventListener('laro-start-onboarding', handler);
    expect(isOnboardingPending('user-b')).toBe(true);
    expect(seen).toEqual(['start']);
  });

  it('requestAppTour queues guided tour without opening kitchen invite', () => {
    const seen = [];
    const handler = () => seen.push('tour');
    window.addEventListener('laro-start-guided-tour', handler);
    requestAppTour('user-c');
    window.removeEventListener('laro-start-guided-tour', handler);
    expect(localStorage.getItem(guidedTourKey('user-c'))).toBe('pending');
    expect(isOnboardingPending('user-c')).toBe(false);
    expect(seen).toEqual(['tour']);
  });

  it('notifyFindAgainOnce only allows one toast per session', () => {
    expect(notifyFindAgainOnce('first')).toBe(true);
    expect(notifyFindAgainOnce('second')).toBe(false);
  });
});
