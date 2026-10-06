/**
 * OPS-3A.3C: ClientRequestDetailScreen Accept/Decline mutation UX tests.
 *
 * Split out of ClientRequestDetailScreen.test.tsx so the chained-async mutation
 * flow (POST -> reconciliation GET -> state settle, incl. the trailing
 * finally{setPending(null)}) is owned by its own module. Mocks/fixtures are
 * duplicated locally (small, safer than new shared infra).
 *
 * Covers: Accept, Decline, double-submit, expected_revision, booking_ready
 * (response-only), 409 reconciliation, 409->404, ambiguous-network reconciliation,
 * 401/403 mutation behavior, and in-flight disabling.
 *
 * ---------------------------------------------------------------------------
 * KNOWN TEST-HARNESS EXCEPTION (OPS-3A.3C)
 * ---------------------------------------------------------------------------
 * When run as a full module, this suite may emit up to four cumulative React
 * `overlapping act()` warnings. Individual and paired mutation tests are
 * warning-free, and ALL mutation assertions pass. During OPS-3A.3C investigation no
 * corresponding product lifecycle defect was identified, and the production screen
 * remained byte-identical throughout. These residual warnings are treated as a
 * test-harness lifecycle artifact under the current jest-expo / React Native Testing
 * Library / React configuration; no corresponding product defect was identified.
 * Warning suppression is intentionally NOT used (no console mocking, no output
 * filtering, no act-environment flags). See the OPS-3A.3C review/history for the
 * full exception rationale. Do not "fix" this by suppressing warnings or by changing
 * production code solely for test cleanliness.
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
const mockAcceptClientQuote = jest.fn();
const mockDeclineClientQuote = jest.fn();
jest.mock('../src/api/client', () => ({
  getClientQuote: (...args: any[]) => mockGetClientQuote(...args),
  acceptClientQuote: (...args: any[]) => mockAcceptClientQuote(...args),
  declineClientQuote: (...args: any[]) => mockDeclineClientQuote(...args),
}));

// useFocusEffect fires once on mount and honors the returned cleanup.
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

const acceptResp = (overrides: Record<string, any> = {}) => ({
  message: 'Quote accepted',
  request_id: 'req-1',
  quote_status: 'ACCEPTED',
  quote_revision: 1,
  quote_accepted_revision: 1,
  quote_accepted_at: '2026-10-06T00:00:00Z',
  booking_ready: false,
  booking_ready_reason: 'Awaiting payment',
  payment_requirement: 'FULL',
  payment_status: 'UNPAID',
  ...overrides,
});

const declineResp = (overrides: Record<string, any> = {}) => ({
  message: 'Quote declined',
  request_id: 'req-1',
  quote_status: 'DECLINED',
  quote_revision: 1,
  quote_declined_at: '2026-10-06T00:00:00Z',
  ...overrides,
});

beforeEach(() => {
  mockGetClientQuote.mockReset();
  mockAcceptClientQuote.mockReset();
  mockDeclineClientQuote.mockReset();
  mockLogout.mockReset();
});

describe('ClientRequestDetailScreen — Accept/Decline mutations (OPS-3A.3C)', () => {
  // Each discrete UI step is its own awaited act(); the trailing waitFor(...) in
  // each test drains the mutation + reconciliation chain.
  const pressAccept = async () => {
    await act(async () => { fireEvent.press(screen.getByLabelText('Accept quote')); });
    await act(async () => { fireEvent.press(screen.getByText('Confirm')); });
  };
  const openDecline = async (reason?: string) => {
    await act(async () => { fireEvent.press(screen.getByLabelText('Decline quote')); });
    if (reason !== undefined) {
      await act(async () => {
        fireEvent.changeText(screen.getByLabelText('Decline reason (optional)'), reason);
      });
    }
  };
  const confirmDecline = async () => {
    await act(async () => { fireEvent.press(screen.getByLabelText('Confirm declining this quote')); });
  };

  // ---- Accept ----
  it('SENT shows Accept and Decline controls', async () => {
    mockGetClientQuote.mockResolvedValue(baseQuote());
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Accept quote')).toBeTruthy());
    expect(screen.getByLabelText('Decline quote')).toBeTruthy();
  });

  it('does NOT show mutation controls outside SENT', async () => {
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'ACCEPTED' }));
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByText('Quote accepted')).toBeTruthy());
    expect(screen.queryByLabelText('Accept quote')).toBeNull();
    expect(screen.queryByLabelText('Decline quote')).toBeNull();
  });

  it('Accept confirms then sends the current quote_revision as expected_revision', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote({ quote_revision: 4 }));
    mockAcceptClientQuote.mockResolvedValue(acceptResp({ quote_revision: 4, quote_accepted_revision: 4 }));
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'ACCEPTED', quote_revision: 4, quote_accepted_at: '2026-10-06T00:00:00Z' }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await screen.findByLabelText('Accept quote');
    await pressAccept();

    await waitFor(() => expect(mockAcceptClientQuote).toHaveBeenCalledWith('req-1', 4));
    await waitFor(() => expect(screen.getAllByText('Quote accepted').length).toBe(2));
  });

  it('Accept does not double-submit on repeated confirm presses', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote());
    let resolveAccept: (v: any) => void = () => {};
    mockAcceptClientQuote.mockReturnValue(new Promise((r) => { resolveAccept = r; }));
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'ACCEPTED', quote_accepted_at: '2026-10-06T00:00:00Z' }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Accept quote')).toBeTruthy());
    await act(async () => { fireEvent.press(screen.getByLabelText('Accept quote')); });
    const confirm = screen.getByText('Confirm');
    await act(async () => {
      fireEvent.press(confirm);
      fireEvent.press(confirm);
      fireEvent.press(confirm);
    });
    expect(mockAcceptClientQuote).toHaveBeenCalledTimes(1);
    await act(async () => { resolveAccept(acceptResp()); });
    await waitFor(() => expect(screen.getAllByText('Quote accepted').length).toBe(2));
  });

  it('Accept uses response booking_ready only (no local inference, no overclaim)', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote());
    mockAcceptClientQuote.mockResolvedValue(acceptResp({ booking_ready: true, booking_ready_reason: 'Ready for your provider' }));
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'ACCEPTED', quote_accepted_at: '2026-10-06T00:00:00Z' }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Accept quote')).toBeTruthy());
    await pressAccept();

    await waitFor(() => expect(screen.getByText('Ready for your provider')).toBeTruthy());
    expect(screen.queryByText(/booking confirmed/i)).toBeNull();
  });

  it('Accept reconciles to the authoritative GET state (no local revision math)', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote({ quote_revision: 2 }));
    mockAcceptClientQuote.mockResolvedValue(acceptResp({ quote_revision: 2, quote_accepted_revision: 2 }));
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'ACCEPTED', quote_revision: 2, quote_accepted_at: '2026-10-06T00:00:00Z' }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Accept quote')).toBeTruthy());
    await pressAccept();
    await waitFor(() => expect(screen.getAllByText('Quote accepted').length).toBe(2));
    expect(mockAcceptClientQuote).toHaveBeenCalledWith('req-1', 2);
  });

  it('Accept disables both actions while the mutation is pending', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote());
    let resolveAccept: (v: any) => void = () => {};
    mockAcceptClientQuote.mockReturnValue(new Promise((r) => { resolveAccept = r; }));
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'ACCEPTED', quote_accepted_at: '2026-10-06T00:00:00Z' }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Accept quote')).toBeTruthy());
    await act(async () => { fireEvent.press(screen.getByLabelText('Accept quote')); });
    await act(async () => { fireEvent.press(screen.getByText('Confirm')); });

    // While pending, the Accept button reports a busy/disabled accessibility state.
    const acceptBtn = screen.getByLabelText('Accept quote');
    expect(acceptBtn.props.accessibilityState?.disabled).toBe(true);

    await act(async () => { resolveAccept(acceptResp()); });
    await waitFor(() => expect(screen.getAllByText('Quote accepted').length).toBe(2));
  });

  // ---- Decline ----
  it('Decline sends a trimmed reason when provided', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote());
    mockDeclineClientQuote.mockResolvedValue(declineResp());
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'DECLINED' }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Decline quote')).toBeTruthy());
    await openDecline('  too costly  ');
    await confirmDecline();

    await waitFor(() => expect(mockDeclineClientQuote).toHaveBeenCalledWith('req-1', 1, 'too costly'));
  });

  it('Decline omits a blank reason', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote());
    mockDeclineClientQuote.mockResolvedValue(declineResp());
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'DECLINED' }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Decline quote')).toBeTruthy());
    await openDecline('   ');
    await confirmDecline();

    await waitFor(() => expect(mockDeclineClientQuote).toHaveBeenCalledWith('req-1', 1, undefined));
  });

  it('Decline reason input enforces a 500-char max', async () => {
    mockGetClientQuote.mockResolvedValue(baseQuote());
    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Decline quote')).toBeTruthy());
    await openDecline();
    const input = screen.getByLabelText('Decline reason (optional)');
    expect(input.props.maxLength).toBe(500);
  });

  it('Decline reconciles to DECLINED and does not echo the reason or imply cancellation', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote());
    mockDeclineClientQuote.mockResolvedValue(declineResp());
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'DECLINED' }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Decline quote')).toBeTruthy());
    await openDecline('no thanks');
    await confirmDecline();

    await waitFor(() => expect(screen.getAllByText('Quote declined').length).toBe(2));
    expect(screen.getByText(/may revise it and send a new quote/)).toBeTruthy();
    expect(screen.queryByText('no thanks')).toBeNull();
    expect(screen.queryByText(/cancell/i)).toBeNull();
    expect(screen.queryByLabelText('Accept quote')).toBeNull();
  });

  // ---- 409 reconciliation ----
  it('Accept 409 does not auto-retry and refetches authoritative state', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote());
    mockAcceptClientQuote.mockRejectedValue(Object.assign(new Error('Conflict'), { status: 409 }));
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'ACCEPTED', quote_accepted_at: '2026-10-06T00:00:00Z' }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Accept quote')).toBeTruthy());
    await pressAccept();

    expect(mockAcceptClientQuote).toHaveBeenCalledTimes(1); // no auto-retry
    await waitFor(() => expect(screen.getByText(/This quote changed or was already acted on/)).toBeTruthy());
    expect(screen.getByText('Quote accepted')).toBeTruthy(); // reconciled to server state
  });

  it('Accept 409 then a server-DECLINED refetch shows the changed state', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote());
    mockAcceptClientQuote.mockRejectedValue(Object.assign(new Error('Conflict'), { status: 409 }));
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'DECLINED' }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Accept quote')).toBeTruthy());
    await pressAccept();

    await waitFor(() => expect(screen.getByText('Quote declined')).toBeTruthy());
    expect(screen.getByText(/This quote changed or was already acted on/)).toBeTruthy();
  });

  it('Decline 409 refetch returning 404 shows the unavailable state (no stale pricing)', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote());
    mockDeclineClientQuote.mockRejectedValue(Object.assign(new Error('Conflict'), { status: 409 }));
    mockGetClientQuote.mockRejectedValue(Object.assign(new Error('Quote not found'), { status: 404 }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Decline quote')).toBeTruthy());
    await openDecline();
    await confirmDecline();

    await waitFor(() => expect(screen.getByText('No quote available yet')).toBeTruthy());
    expect(screen.queryByText('$50.00')).toBeNull();
  });

  // ---- Ambiguous network ----
  it('Accept network failure does not assume success; reconciles ACCEPTED from refetch', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote());
    mockAcceptClientQuote.mockRejectedValue(new Error('Network request failed')); // no status
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'ACCEPTED', quote_accepted_at: '2026-10-06T00:00:00Z' }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Accept quote')).toBeTruthy());
    await pressAccept();

    expect(mockAcceptClientQuote).toHaveBeenCalledTimes(1); // no automatic second POST
    await waitFor(() => expect(screen.getAllByText('Quote accepted').length).toBe(2));
  });

  it('Accept network failure with still-SENT refetch leaves deliberate retry possible', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote());
    mockAcceptClientQuote.mockRejectedValue(new Error('Network request failed'));
    mockGetClientQuote.mockResolvedValue(baseQuote()); // still SENT

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Accept quote')).toBeTruthy());
    await pressAccept();

    await waitFor(() => expect(screen.getByText(/couldn't confirm your action/)).toBeTruthy());
    expect(screen.getByLabelText('Accept quote')).toBeTruthy();
    expect(mockAcceptClientQuote).toHaveBeenCalledTimes(1);
  });

  it('Decline network failure reconciles DECLINED from refetch without a second POST', async () => {
    mockGetClientQuote.mockResolvedValueOnce(baseQuote());
    mockDeclineClientQuote.mockRejectedValue(new Error('Network request failed'));
    mockGetClientQuote.mockResolvedValue(baseQuote({ quote_status: 'DECLINED' }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Decline quote')).toBeTruthy());
    await openDecline();
    await confirmDecline();

    expect(mockDeclineClientQuote).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.getAllByText('Quote declined').length).toBe(2));
  });

  // ---- Auth ----
  it('Accept 401 triggers logout', async () => {
    mockGetClientQuote.mockResolvedValue(baseQuote());
    mockAcceptClientQuote.mockRejectedValue(Object.assign(new Error('Your session expired. Please sign in again.'), { status: 401 }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Accept quote')).toBeTruthy());
    await pressAccept();
    await waitFor(() => expect(mockLogout).toHaveBeenCalled());
  });

  it('Accept 403 shows a permission message and does not treat it as 409', async () => {
    mockGetClientQuote.mockResolvedValue(baseQuote());
    mockAcceptClientQuote.mockRejectedValue(Object.assign(new Error('Forbidden'), { status: 403 }));

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Accept quote')).toBeTruthy());
    await pressAccept();

    await waitFor(() => expect(screen.getByText('Forbidden')).toBeTruthy());
    expect(screen.queryByText(/This quote changed or was already acted on/)).toBeNull();
    expect(mockGetClientQuote).toHaveBeenCalledTimes(1);
  });
});
