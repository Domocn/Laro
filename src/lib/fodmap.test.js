import {
  applyFodmapSwaps,
  buildAdaptations,
  findSwap,
  getLowFodmap,
  readFodmapView,
  writeFodmapView,
  FODMAP_VIEW_KEY,
} from './fodmap';

const swaps = [
  { from: 'garlic', to: 'garlic-infused oil' },
  { from: 'onion', to: 'green tops of spring onions or leek' },
  { from: 'red onion', to: 'chives' },
];

describe('fodmap', () => {
  it('reads the adaptation and ignores empty ones', () => {
    expect(getLowFodmap({ adaptations: { low_fodmap: { swaps, notes: ' Check lentils ' } } })).toEqual({
      swaps,
      notes: 'Check lentils',
    });
    expect(getLowFodmap({ adaptations: { low_fodmap: { swaps: [{ from: '', to: 'x' }], notes: '' } } })).toBeNull();
    expect(getLowFodmap({ adaptations: null })).toBeNull();
    expect(getLowFodmap(null)).toBeNull();
  });

  it('matches ingredient names case-insensitively, longest swap first', () => {
    expect(findSwap('2 Garlic cloves, crushed', swaps)?.to).toBe('garlic-infused oil');
    expect(findSwap('Red Onion, sliced', swaps)?.to).toBe('chives');
    expect(findSwap('white onion', swaps)?.to).toBe('green tops of spring onions or leek');
    expect(findSwap('red lentils', swaps)).toBeNull();
  });

  it('marks only swapped ingredients', () => {
    const out = applyFodmapSwaps([{ name: 'garlic', amount: '2', unit: 'cloves' }, { name: 'tofu' }, 'onion'], swaps);
    expect(out.map((r) => r.swap?.to ?? null)).toEqual([
      'garlic-infused oil',
      null,
      'green tops of spring onions or leek',
    ]);
  });

  it('builds the saved adaptations object from the edit form', () => {
    expect(buildAdaptations(null, [{ from: ' garlic ', to: 'garlic oil' }, { from: '', to: '' }], '')).toEqual({
      low_fodmap: { swaps: [{ from: 'garlic', to: 'garlic oil' }], notes: '' },
    });
    expect(buildAdaptations({ low_fodmap: { swaps, notes: 'x' } }, [], '  ')).toBeNull();
    expect(buildAdaptations({ vegan: { notes: 'y' } }, [], '')).toEqual({ vegan: { notes: 'y' } });
  });

  it('remembers the chosen view', () => {
    localStorage.removeItem(FODMAP_VIEW_KEY);
    expect(readFodmapView()).toBe('original');
    writeFodmapView('low_fodmap');
    expect(localStorage.getItem(FODMAP_VIEW_KEY)).toBe('low_fodmap');
    expect(readFodmapView()).toBe('low_fodmap');
    writeFodmapView('original');
    expect(readFodmapView()).toBe('original');
  });
});
