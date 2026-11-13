/**
 * S1: deterministic money helpers for the owner/admin quote editor.
 *
 * Rules mirror the web AdminQuoteEditor (W2B): input is a plain decimal string,
 * `^\d+(\.\d{1,2})?$` after trimming, converted to INTEGER cents by string/integer
 * arithmetic only. No floating-point math, no silent rounding, no reinterpretation
 * of malformed input.
 */

export type MoneyParse = { ok: true; cents: number } | { ok: false; error: string };

export const parseDollarsToCents = (raw: unknown): MoneyParse => {
  const s = String(raw ?? '').trim();
  if (s === '') return { ok: false, error: 'Enter an amount.' };
  if (!/^\d+(\.\d{1,2})?$/.test(s)) {
    return { ok: false, error: 'Enter a valid amount (digits, up to 2 decimals, no negatives).' };
  }
  const [whole, frac = ''] = s.split('.');
  const cents = parseInt(whole, 10) * 100 + parseInt((frac + '00').slice(0, 2), 10);
  // A shape-valid but huge digit string can exceed the safe-integer range; reject
  // rather than submit an imprecise value.
  if (!Number.isSafeInteger(cents)) return { ok: false, error: 'Amount is too large.' };
  return { ok: true, cents };
};

/** Display/edit string for stored integer cents (e.g. 1234 -> "12.34"). Integer math only. */
export const centsToDollars = (cents: unknown): string => {
  const n = Number(cents ?? 0);
  if (!Number.isSafeInteger(n) || n < 0) return '0.00';
  const whole = Math.floor(n / 100);
  const frac = n % 100;
  return `${whole}.${frac < 10 ? '0' : ''}${frac}`;
};

/** Read-only label such as "USD 12.34". */
export const formatQuoteMoney = (cents: unknown, currency?: string | null): string =>
  `${(currency || 'USD').toUpperCase()} ${centsToDollars(cents)}`;
