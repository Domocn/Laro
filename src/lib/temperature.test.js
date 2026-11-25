import { describe, it, expect } from 'vitest';
import { cToF, temperaturesForStyle } from './temperature';

const us = (s) => temperaturesForStyle(s, 'us');

describe('°C → °F for US instructions', () => {
  it('rounds oven temperatures like a dial, others to the degree', () => {
    expect(cToF(180)).toBe(350);
    expect(cToF(200)).toBe(400);
    expect(cToF(220)).toBe(425);
    expect(cToF(160)).toBe(325);
    expect(cToF(190)).toBe(375);
    expect(cToF(75)).toBe(167);
    expect(cToF(100)).toBe(212);
  });

  it.each([
    ['Bake at 180C for 20 min', 'Bake at 350°F for 20 min'],
    ['Bake at 180°C for 20 min', 'Bake at 350°F for 20 min'],
    ['Bake at 180 °C.', 'Bake at 350°F.'],
    ['Heat to 200 degrees C', 'Heat to 400°F'],
    ['Heat to 200 degrees Celsius', 'Heat to 400°F'],
    ['Preheat to 180°C fan', 'Preheat to 350°F fan'],
    ['cook until it reaches 75°C inside', 'cook until it reaches 167°F inside'],
    ['Roast at 180-200C', 'Roast at 350-400°F'],
  ])('%s', (input, want) => {
    expect(us(input)).toBe(want);
  });

  it.each([
    ['Heat oven to 200°C (400°F).', 'Heat oven to 400°F.'],
    ['Heat oven to 180 C (350F)', 'Heat oven to 350°F'],
    ['Bake at 350F / 180C', 'Bake at 350°F'],
    ['Bake at 400°F (200°C)', 'Bake at 400°F'],
    ['(200C/400F) for an hour', '(400°F) for an hour'],
  ])('text that gives both keeps the °F one: %s', (input, want) => {
    expect(us(input)).toBe(want);
  });

  it('leaves non-temperatures alone', () => {
    expect(us('Add 2 C flour')).toBe('Add 2 C flour');
    expect(us('Add 250 c flour')).toBe('Add 250 c flour');
    expect(us('Serves 12 Children')).toBe('Serves 12 Children');
    expect(us('Already 350°F')).toBe('Already 350°F');
    expect(us('Use 50 C')).toBe('Use 50 C'); // too cool for a bare "C" temperature
  });

  it('only changes text for the US', () => {
    for (const style of ['uk', 'au', 'ca']) {
      expect(temperaturesForStyle('Bake at 180C (350F)', style)).toBe('Bake at 180C (350F)');
    }
    expect(temperaturesForStyle(null, 'us')).toBeNull();
  });
});
