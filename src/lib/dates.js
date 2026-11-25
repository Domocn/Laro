import { parse } from 'date-fns';

/**
 * Parse a calendar date as local midnight.
 * date-fns v4 parseISO('YYYY-MM-DD') is UTC midnight, which is the previous
 * local day in US timezones.
 */
export function parseLocalDate(value) {
  if (value instanceof Date) {
    return value;
  }
  const text = String(value ?? '').trim();
  if (!text) {
    return new Date(NaN);
  }
  const ymd = text.slice(0, 10);
  if (/^\d{4}-\d{2}-\d{2}$/.test(ymd)) {
    return parse(ymd, 'yyyy-MM-dd', new Date());
  }
  const parsed = new Date(text);
  return parsed;
}

export function isValidDate(value) {
  return value instanceof Date && !Number.isNaN(value.getTime());
}
