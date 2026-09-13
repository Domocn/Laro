import { matchLocalVoiceCommand, getHandsFreePreference, setHandsFreePreference } from './voiceCommands';
import { buildSetStepMessage, buildShowMessage, getCastAppId } from './castCook';

describe('matchLocalVoiceCommand', () => {
  it('matches next and nexty', () => {
    expect(matchLocalVoiceCommand('next')).toEqual({ type: 'navigate', direction: 'next' });
    expect(matchLocalVoiceCommand('Nexty')).toEqual({ type: 'navigate', direction: 'next' });
    expect(matchLocalVoiceCommand('please go to the next step')).toEqual({
      type: 'navigate',
      direction: 'next',
    });
  });

  it('matches previous and repeat', () => {
    expect(matchLocalVoiceCommand('go back')).toEqual({ type: 'navigate', direction: 'previous' });
    expect(matchLocalVoiceCommand('repeat that')).toEqual({ type: 'repeat' });
  });
});

describe('castCook messages', () => {
  it('builds show and set_step payloads', () => {
    expect(
      buildShowMessage({
        title: 'Soup',
        steps: ['Chop', 'Boil'],
        stepIndex: 1,
        timerLabel: '1:00',
      })
    ).toEqual({
      type: 'show',
      title: 'Soup',
      steps: ['Chop', 'Boil'],
      stepIndex: 1,
      timerLabel: '1:00',
    });
    expect(buildSetStepMessage(2, '0:30')).toEqual({
      type: 'set_step',
      stepIndex: 2,
      timerLabel: '0:30',
    });
  });

  it('reads cast app id from placeholder safely', () => {
    expect(typeof getCastAppId()).toBe('string');
  });
});

describe('hands-free preference helpers', () => {
  it('round-trips localStorage preference', () => {
    setHandsFreePreference(true);
    expect(getHandsFreePreference()).toBe(true);
    setHandsFreePreference(false);
    expect(getHandsFreePreference()).toBe(false);
  });
});
