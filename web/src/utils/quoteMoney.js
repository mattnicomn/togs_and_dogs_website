/**
 * Quote money helpers (extracted from AdminQuoteEditor for Fast Refresh / Gate C3b.2b Batch 1).
 *
 * Pure, framework-agnostic conversion/validation for the canonical owner/admin
 * quote editor (OPS-3A / W2B). Behavior is identical to the previous in-component
 * implementation — only the file location changed.
 */

/**
 * Deterministic string-based dollars -> integer cents parser (approved W2B rule).
 * Accepts only `^\d+(\.\d{1,2})?$` after trimming. No float math, no silent
 * rounding, no reinterpretation of malformed input.
 *
 * @returns {{ ok: true, cents: number } | { ok: false, error: string }}
 */
export function parseDollarsToCents(raw) {
  const s = String(raw ?? '').trim();
  if (s === '') {
    return { ok: false, error: 'Enter an amount.' };
  }
  if (!/^\d+(\.\d{1,2})?$/.test(s)) {
    return { ok: false, error: 'Enter a valid amount (digits, up to 2 decimals, no negatives).' };
  }
  const [whole, frac = ''] = s.split('.');
  const fracPadded = (frac + '00').slice(0, 2);
  const cents = parseInt(whole, 10) * 100 + parseInt(fracPadded, 10);
  // Safe-integer guard: a very large (but shape-valid) digit string can exceed
  // JavaScript's safe-integer range, which would silently submit an imprecise
  // value to the API. Reject rather than clamp/round.
  if (!Number.isSafeInteger(cents)) {
    return { ok: false, error: 'Amount is too large.' };
  }
  return { ok: true, cents };
}

/** Display-only: integer cents -> major-unit string (e.g. 1234 -> "12.34"). */
export function centsToDollars(cents) {
  const n = Number(cents || 0);
  return (n / 100).toFixed(2);
}
