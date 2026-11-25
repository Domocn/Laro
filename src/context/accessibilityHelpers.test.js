import { confirmDestructive } from './accessibilityHelpers';

describe('confirmDestructive', () => {
  it('skips the browser confirm when confirmActions is off', () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockImplementation(() => false);
    expect(confirmDestructive(false, 'Delete?')).toBe(true);
    expect(confirmSpy).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it('uses window.confirm when confirmActions is on', () => {
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(false);
    expect(confirmDestructive(true, 'Delete?')).toBe(false);
    expect(confirmSpy).toHaveBeenCalledWith('Delete?');
    confirmSpy.mockRestore();
  });
});
