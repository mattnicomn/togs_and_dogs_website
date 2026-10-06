/**
 * OPS-3A.3B: ClientRequestDetailScreen read-only quote presentation tests.
 *
 * Read-only slice: proves loading/fetch, client-safe context + quote rendering per
 * visible status, unavailable/error handling, and the ABSENCE of any Accept/Decline
 * or admin/internal fields. No mutation tests (those are OPS-3A.3C).
 */
import React from 'react';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react-native';

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

// useFocusEffect -> run as a mount effect so fetch fires in tests.
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
  jest.clearAllMocks();
});

describe('ClientRequestDetailScreen', () => {
  it('shows a loading state while the fetch is pending', async () => {
    let resolve: (v: any) => void = () => {};
    mockGetClientQuote.mockReturnValue(new Promise((r) => { resolve = r; }));
    // Await render so the focus effect runs inside act(); the fetch promise stays
    // pending, so the component remains in its loading state.
    await render(<ClientRequestDetailScreen route={route()} />);
    expect(screen.getByLabelText('Loading booking details')).toBeTruthy();
    // Resolve inside act() so the resulting state update is wrapped.
    await act(async () => {
      resolve(baseQuote());
    });
    await waitFor(() => expect(screen.getByText('Your Quote')).toBeTruthy());
  });

  it('fetches by requestId', async () => {
    mockGetClientQuote.mockResolvedValue(baseQuote());
    await render(<ClientRequestDetailScreen route={route('req-99')} />);
    await waitFor(() => expect(mockGetClientQuote).toHaveBeenCalledWith('req-99'));
  });

  it('SENT renders total, ready-for-review status, and booking context', async () => {
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_notes_client: 'Standard walk' }));
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByText('Quote ready for review')).toBeTruthy());
    expect(screen.getByText('$50.00')).toBeTruthy();
    expect(screen.getByText('20-Min Walk')).toBeTruthy();
    expect(screen.getByText('Rex')).toBeTruthy();
    expect(screen.getByText('Standard walk')).toBeTruthy();
    expect(screen.getByText('Full payment required')).toBeTruthy();
  });

  it('ACCEPTED renders accepted status and accepted timestamp', async () => {
    mockGetClientQuote.mockResolvedValue(
      baseQuote({ quote_status: 'ACCEPTED', quote_accepted_at: '2026-10-06T00:00:00Z', quote_accepted_revision: 1 })
    );
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByText('Quote accepted')).toBeTruthy());
    expect(screen.getByText(/Accepted/)).toBeTruthy();
  });

  it('DECLINED renders declined messaging and does not imply cancellation', async () => {
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'DECLINED' }));
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByText('Quote declined')).toBeTruthy());
    expect(screen.getByText(/may revise it and send a new quote/)).toBeTruthy();
    expect(screen.queryByText(/cancell/i)).toBeNull();
  });

  it('NOT_REQUIRED renders a no-action state (not an error)', async () => {
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'NOT_REQUIRED', quote_amount_cents: 0, payment_requirement: 'NONE' }));
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByText('No quote action is required for this booking.')).toBeTruthy());
  });

  it('renders a deposit line when a deposit is present', async () => {
    mockGetClientQuote.mockResolvedValue(baseQuote({ deposit_amount_cents: 1500 }));
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByText('Deposit')).toBeTruthy());
    expect(screen.getByText('$15.00')).toBeTruthy();
  });

  it('does NOT render Accept or Decline controls (read-only slice)', async () => {
    mockGetClientQuote.mockResolvedValue(baseQuote());
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByText('Your Quote')).toBeTruthy());
    expect(screen.queryByText(/^Accept$/i)).toBeNull();
    expect(screen.queryByText(/^Decline$/i)).toBeNull();
    expect(screen.queryByLabelText(/accept quote/i)).toBeNull();
    expect(screen.queryByLabelText(/decline quote/i)).toBeNull();
  });

  it('does NOT render internal/admin fields', async () => {
    mockGetClientQuote.mockResolvedValue(baseQuote());
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByText('Your Quote')).toBeTruthy());
    // These must never appear in the client detail UI.
    expect(screen.queryByText(/internal/i)).toBeNull();
    expect(screen.queryByText(/audit/i)).toBeNull();
    expect(screen.queryByText(/history/i)).toBeNull();
    expect(screen.queryByText(/stripe/i)).toBeNull();
  });

  // Defense-in-depth: the server (OPS-3A.3A.1/.2) hides DRAFT/SUPERSEDED behind a
  // non-disclosing 404, so these statuses should never reach the client. If one
  // ever did (or an unknown/future status appeared), the screen must fall back to a
  // non-commercial no-action view and never render pricing/notes. These statuses are
  // injected directly to simulate that impossible/server-hidden state — this is NOT
  // client-side DRAFT filtering, just a guarantee the UI leaks nothing if it slips
  // through. (quote_status is typed as string, so no cast is needed.)
  it('does NOT render commercial details for a DRAFT status (defense-in-depth)', async () => {
    mockGetClientQuote.mockResolvedValue(
      baseQuote({ quote_status: 'DRAFT', quote_amount_cents: 5000, deposit_amount_cents: 1500, quote_notes_client: 'draft notes' })
    );
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByText('No quote action is required for this booking.')).toBeTruthy());
    // No commercial terms leak.
    expect(screen.queryByText('$50.00')).toBeNull();
    expect(screen.queryByText('Deposit')).toBeNull();
    expect(screen.queryByText('Full payment required')).toBeNull();
    expect(screen.queryByText('Unpaid')).toBeNull();
    expect(screen.queryByText('draft notes')).toBeNull();
    // No mutation controls.
    expect(screen.queryByText(/^Accept$/i)).toBeNull();
    expect(screen.queryByText(/^Decline$/i)).toBeNull();
  });

  it('does NOT render commercial details for an unknown/future status (defense-in-depth)', async () => {
    mockGetClientQuote.mockResolvedValue(
      baseQuote({ quote_status: 'FUTURE_UNKNOWN', quote_amount_cents: 9900, deposit_amount_cents: 2000, quote_notes_client: 'secret' })
    );
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByText('No quote action is required for this booking.')).toBeTruthy());
    expect(screen.queryByText('$99.00')).toBeNull();
    expect(screen.queryByText('Deposit')).toBeNull();
    expect(screen.queryByText('secret')).toBeNull();
    expect(screen.queryByText(/^Accept$/i)).toBeNull();
    expect(screen.queryByText(/^Decline$/i)).toBeNull();
  });

  it('shows a retryable error on a non-auth/non-404 failure', async () => {
    mockGetClientQuote.mockRejectedValue(Object.assign(new Error('Server error'), { status: 500 }));
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByText('Server error')).toBeTruthy());
    const retry = screen.getByLabelText('Retry loading booking details');
    mockGetClientQuote.mockResolvedValue(baseQuote());
    await act(async () => {
      fireEvent.press(retry);
    });
    await waitFor(() => expect(screen.getByText('Your Quote')).toBeTruthy());
  });

  it('shows the non-disclosing "no quote available" state on 404', async () => {
    mockGetClientQuote.mockRejectedValue(Object.assign(new Error('Quote not found'), { status: 404 }));
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByText('No quote available yet')).toBeTruthy());
    // No pricing leaks in the unavailable state.
    expect(screen.queryByText('$50.00')).toBeNull();
  });

  it('logs out on a 401 session expiry', async () => {
    mockGetClientQuote.mockRejectedValue(Object.assign(new Error('Your session expired. Please sign in again.'), { status: 401 }));
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(mockLogout).toHaveBeenCalled());
  });
});
