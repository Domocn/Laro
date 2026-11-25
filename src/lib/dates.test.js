/**
 * @jest-environment node
 */
import { parseISO } from 'date-fns';
import { isValidDate, parseLocalDate } from './dates';

describe('parseLocalDate', () => {
  it('treats YYYY-MM-DD as local midnight, not UTC', () => {
    const local = parseLocalDate('2026-09-17');
    expect(isValidDate(local)).toBe(true);
    expect(local.getFullYear()).toBe(2026);
    expect(local.getMonth()).toBe(8);
    expect(local.getDate()).toBe(17);
    expect(local.getHours()).toBe(0);

    const utc = parseISO('2026-09-17');
    // In timezones west of UTC, parseISO lands on the previous local day.
    const tzOffsetMinutes = new Date(2026, 8, 17).getTimezoneOffset();
    if (tzOffsetMinutes > 0) {
      expect(utc.getDate()).not.toBe(local.getDate());
    }
  });

  it('accepts Date instances and ISO datetimes by prefix', () => {
    const fromDate = parseLocalDate(new Date(2026, 0, 2, 15));
    expect(fromDate.getFullYear()).toBe(2026);
    const fromIso = parseLocalDate('2026-01-02T19:00:00.000Z');
    expect(fromIso.getFullYear()).toBe(2026);
    expect(fromIso.getMonth()).toBe(0);
    expect(fromIso.getDate()).toBe(2);
  });

  it('returns an invalid date for empty input', () => {
    expect(isValidDate(parseLocalDate(''))).toBe(false);
    expect(isValidDate(parseLocalDate(null))).toBe(false);
  });
});
