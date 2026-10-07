/**
 * OPS-3A.4 M3 regression: client request/booking detail must not crash when a
 * production quote projection returns `pet_names` / `selected_dates` in a legacy
 * NON-ARRAY shape.
 *
 * ROOT CAUSE (captured from device logcat + sourcemap of the exact crash offset):
 * a real production REQUEST record can store `pet_names` / `selected_dates` as a
 * single string (or omit/null them) rather than a JS array. The client-safe
 * projection passes these through verbatim, and the screen then called
 * `.join(', ')` / `.map(...)` on a non-array, which Hermes reported as a
 * render-phase "TypeError: undefined is not a function" — crashing the Booking
 * Details card the moment a fetched quote rendered. The original unit tests all
 * used array fixtures, so they passed while the device crashed.
 *
 * These tests FAITHFULLY reproduce the production shapes (string / null /
 * missing) and prove the screen renders without crashing after the defensive
 * `toStringArray` coercion. All data is fully synthetic — no production values.
 */
import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react-native';

const mockLogout = jest.fn();
jest.mock('../src/auth/useAuth', () => ({
  useAuth: () => ({
    logout: mockLogout,
    role: 'client',
    isAuthenticated: true,
    isLoading: false,
  }),
}));

const mockGetClientQuote = jest.fn();
jest.mock('../src/api/client', () => ({
  getClientQuote: (...args: any[]) => mockGetClientQuote(...args),
}));

jest.mock('@react-navigation/native', () => ({
  useFocusEffect: (cb: () => void | (() => void)) => {
    const React = require('react');
    React.useEffect(() => {
      const cleanup = cb();
      return typeof cleanup === 'function' ? cleanup : undefined;
    }, []);
  },
}));

import { ClientRequestDetailScreen } from '../src/screens/ClientRequestDetailScreen';

const route = (requestId = 'req-1') => ({ params: { requestId } });

const baseQuote = (overrides: Record<string, any> = {}) => ({
  request_id: 'req-1',
  quote_status: 'SENT',
  quote_revision: 1,
  quote_amount_cents: 5000,
  currency: 'USD',
  deposit_amount_cents: 0,
  payment_requirement: 'FULL',
  payment_status: 'UNPAID',
  payment_required: true,
  quote_notes_client: null,
  quote_sent_at: '2026-10-05T00:00:00Z',
  quote_accepted_at: null,
  quote_accepted_revision: null,
  service_type: 'WALK_20MIN',
  pet_names: ['Rex'],
  selected_dates: ['2026-10-10'],
  start_date: '2026-10-10',
  end_date: '2026-10-10',
  ...overrides,
});

beforeEach(() => {
  mockGetClientQuote.mockReset();
  mockLogout.mockReset();
});

describe('ClientRequestDetailScreen — legacy non-array field shapes (M3 crash regression)', () => {
  it('does not crash when pet_names is a plain string (legacy shape)', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote({ pet_names: 'Rex' }));
    await act(async () => {
      render(<ClientRequestDetailScreen route={route()} />);
    });
    // Before the fix this threw "undefined is not a function" (string has no .join).
    await waitFor(() => expect(screen.getByText('Booking Details')).toBeTruthy());
    expect(screen.getByText('Rex')).toBeTruthy();
    expect(screen.getByText('Quote ready for review')).toBeTruthy();
  });

  it('does not crash when selected_dates is a plain string (legacy shape)', async () => {
    mockGetClientQuote.mockResolvedValueOnce(
      baseQuote({ selected_dates: '2026-10-10', start_date: null, end_date: null }),
    );
    await act(async () => {
      render(<ClientRequestDetailScreen route={route()} />);
    });
    // Before the fix this threw "undefined is not a function" (string has no .map).
    await waitFor(() => expect(screen.getByText('Booking Details')).toBeTruthy());
    expect(screen.getByText('Oct 10, 2026')).toBeTruthy();
  });

  it('does not crash when both fields are null and falls back to start/end date', async () => {
    mockGetClientQuote.mockResolvedValueOnce(
      baseQuote({ pet_names: null, selected_dates: null, start_date: '2026-10-12', end_date: '2026-10-12' }),
    );
    await act(async () => {
      render(<ClientRequestDetailScreen route={route()} />);
    });
    await waitFor(() => expect(screen.getByText('Booking Details')).toBeTruthy());
    expect(screen.getByText('Oct 12, 2026')).toBeTruthy();
    // No Pets row rendered when there are no names.
    expect(screen.queryByText('Pets')).toBeNull();
  });

  it('does not crash when fields are entirely absent (no dates -> TBC)', async () => {
    const q = baseQuote();
    delete (q as any).pet_names;
    delete (q as any).selected_dates;
    delete (q as any).start_date;
    delete (q as any).end_date;
    mockGetClientQuote.mockResolvedValueOnce(q);
    await act(async () => {
      render(<ClientRequestDetailScreen route={route()} />);
    });
    await waitFor(() => expect(screen.getByText('Booking Details')).toBeTruthy());
    expect(screen.getByText('Date to be confirmed')).toBeTruthy();
  });

  it('still renders a normal array shape correctly (no regression)', async () => {
    mockGetClientQuote.mockResolvedValueOnce(
      baseQuote({ pet_names: ['Rex', 'Luna'], selected_dates: ['2026-10-10', '2026-10-11'] }),
    );
    await act(async () => {
      render(<ClientRequestDetailScreen route={route()} />);
    });
    await waitFor(() => expect(screen.getByText('Booking Details')).toBeTruthy());
    expect(screen.getByText('Rex, Luna')).toBeTruthy();
    expect(screen.getByText('Oct 10, 2026, Oct 11, 2026')).toBeTruthy();
  });
});
