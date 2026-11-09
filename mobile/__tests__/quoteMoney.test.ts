import { centsToDollars, formatQuoteMoney, parseDollarsToCents } from '../src/utils/quoteMoney';

describe('S1 quoteMoney: dollars -> integer cents (no floating point)', () => {
  it.each([
    ['0', 0],
    ['12', 1200],
    ['12.3', 1230],
    ['12.34', 1234],
    ['  5.00 ', 500],
    ['0.07', 7],
    ['0.29', 29], // 0.29 * 100 === 28.999999999999996 in floating point
    ['19.99', 1999],
    ['1.10', 110],
    ['1000000', 100000000],
  ])('parses %p as %p cents', (input, cents) => {
    expect(parseDollarsToCents(input)).toEqual({ ok: true, cents });
  });

  it.each(['', '   ', '-1', '1.234', '1,000', 'abc', '.5', '5.', '1e3', '$5', '5.5.5', '+5'])(
    'rejects malformed input %p without reinterpreting it',
    input => {
      const r = parseDollarsToCents(input);
      expect(r.ok).toBe(false);
    }
  );

  it('rejects null/undefined and non-string input', () => {
    expect(parseDollarsToCents(undefined).ok).toBe(false);
    expect(parseDollarsToCents(null).ok).toBe(false);
  });

  it('rejects values beyond the safe-integer range instead of clamping', () => {
    const r = parseDollarsToCents('99999999999999999999');
    expect(r).toEqual({ ok: false, error: 'Amount is too large.' });
  });
});

describe('S1 quoteMoney: cents -> display string', () => {
  it.each([
    [0, '0.00'],
    [5, '0.05'],
    [10, '0.10'],
    [1234, '12.34'],
    [100000, '1000.00'],
    [null, '0.00'],
    [undefined, '0.00'],
    [-5, '0.00'],
    [12.5, '0.00'],
  ])('centsToDollars(%p) = %p', (input, expected) => {
    expect(centsToDollars(input)).toBe(expected);
  });

  it('round-trips parse(centsToDollars(n)) for representative values', () => {
    for (const n of [0, 1, 7, 99, 100, 101, 1999, 123456]) {
      expect(parseDollarsToCents(centsToDollars(n))).toEqual({ ok: true, cents: n });
    }
  });

  it('formatQuoteMoney uppercases and defaults the currency', () => {
    expect(formatQuoteMoney(1234, 'usd')).toBe('USD 12.34');
    expect(formatQuoteMoney(500, null)).toBe('USD 5.00');
  });
});
