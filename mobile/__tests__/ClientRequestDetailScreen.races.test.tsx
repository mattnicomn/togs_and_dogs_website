/**
 * OPS-3A.3D.1: ClientRequestDetailScreen authoritative-read stale-response race tests.
 *
 * All authoritative reads (initial/focus fetch, mutation reconciliation,
 * 409/ambiguous reconciliation) share ONE monotonic generation (sequenceRef); every
 * quote/unavailable/error/loading write is guarded by `isCurrentRead(token)`, so the
 * newest read that STARTED owns the committed result. `beginMutation` advances the
 * generation before the POST so any older in-flight focus GET is invalidated.
 *
 * These tests control promise-resolution ORDER with manual deferreds to exercise the
 * generation guard against reads that resolve out of order. The authoritative reads a
 * single screen instance can have in flight simultaneously are the mutation's
 * reconciliation read and any read that began before the mutation (invalidated at
 * beginMutation); these are what the deferreds below simulate. Running chained-async
 * interactions in one module may emit React `overlapping act()` warnings (the
 * documented OPS-3A.3C test-harness exception). Warning suppression is NOT used.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react-native';

const mockLogout = jest.fn();
jest.mock('../src/auth/useAuth', () => ({
  useAuth: () => ({ logout: mockLogout, role: 'client', isAuthenticated: true, isLoading: false }),
}));

const mockGetClientQuote = jest.fn();
const mockAcceptClientQuote = jest.fn();
const mockDeclineClientQuote = jest.fn();
jest.mock('../src/api/client', () => ({
  getClientQuote: (...a: any[]) => mockGetClientQuote(...a),
  acceptClientQuote: (...a: any[]) => mockAcceptClientQuote(...a),
  declineClientQuote: (...a: any[]) => mockDeclineClientQuote(...a),
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
  request_id: 'req-1', quote_status: 'SENT', quote_revision: 1, quote_amount_cents: 5000,
  currency: 'USD', deposit_amount_cents: 0, payment_requirement: 'FULL', payment_status: 'UNPAID',
  payment_required: true, quote_notes_client: null, quote_sent_at: '2026-10-05T00:00:00Z',
  quote_accepted_at: null, quote_accepted_revision: null, service_type: 'WALK_20MIN',
  pet_names: ['Rex'], selected_dates: ['2026-10-10'], start_date: '2026-10-10', end_date: '2026-10-10',
  ...overrides,
});

const acceptResp = (overrides: Record<string, any> = {}) => ({
  message: 'Quote accepted', request_id: 'req-1', quote_status: 'ACCEPTED', quote_revision: 1,
  quote_accepted_revision: 1, quote_accepted_at: '2026-10-06T00:00:00Z', booking_ready: false,
  booking_ready_reason: 'Awaiting payment', payment_requirement: 'FULL', payment_status: 'UNPAID',
  ...overrides,
});

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: any) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

// Press helpers wrap fireEvent in act() (matching the mutation suite) so async state
// updates stay inside an act scope — avoiding "not configured to support act"
// warnings. The accept confirmation modal's "Confirm" button is awaited before press.
const pressAccept = async () => {
  await act(async () => { fireEvent.press(screen.getByLabelText('Accept quote')); });
  await act(async () => { fireEvent.press(screen.getByText('Confirm')); });
};
const pressDecline = async () => {
  await act(async () => { fireEvent.press(screen.getByLabelText('Decline quote')); });
  await act(async () => { fireEvent.press(screen.getByLabelText('Confirm declining this quote')); });
};

beforeEach(() => {
  mockGetClientQuote.mockReset();
  mockAcceptClientQuote.mockReset();
  mockDeclineClientQuote.mockReset();
  mockLogout.mockReset();
});

describe('ClientRequestDetailScreen — reconciliation read paths (OPS-3A.3D.1)', () => {
  // COVERAGE NOTE (OPS-3A.3D.2): these component tests cover the REACHABLE current-read
  // reconciliation paths (success / 404 / ambiguous network). The genuine stale-order
  // guarantee — an older authoritative read resolving AFTER a newer one and being
  // refused — cannot be faithfully driven through this harness (one-shot
  // useFocusEffect + UI-gated controls prevent two overlapping in-flight component
  // reads with inverted resolution). That ordering is proven at the primitive level in
  // readGeneration.test.ts, which exercises the exact begin()/isCurrent()/applyIfCurrent
  // logic this screen composes with mountedRef.
  it('Accept: reconciliation read resolving ACCEPTED commits the reconciled state', async () => {
    const recon = deferred<any>();
    mockGetClientQuote
      .mockResolvedValueOnce(baseQuote())   // focus read -> SENT (controls render)
      .mockReturnValueOnce(recon.promise);  // reconciliation read (resolved on demand)
    mockAcceptClientQuote.mockResolvedValue(acceptResp());

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Accept quote')).toBeTruthy());
    await pressAccept();

    await act(async () => {
      recon.resolve(baseQuote({ quote_status: 'ACCEPTED', quote_accepted_at: '2026-10-06T00:00:00Z' }));
    });
    await waitFor(() => expect(screen.getAllByText('Quote accepted').length).toBe(2));
    expect(screen.queryByLabelText('Accept quote')).toBeNull();
  });

  // (The stale-pre-mutation-read-resolving-last ordering is NOT faithfully expressible
  // through this component harness; it is proven at the primitive level in
  // readGeneration.test.ts. See the coverage note above.)

  // Current-read reconciliation 404 clears to the non-disclosing unavailable state.
  it('reconciliation 404 (current read) clears to the non-disclosing unavailable state', async () => {
    mockGetClientQuote
      .mockResolvedValueOnce(baseQuote())  // focus -> SENT
      .mockRejectedValueOnce(Object.assign(new Error('Quote not found'), { status: 404 })); // reconciliation 404
    mockDeclineClientQuote.mockResolvedValue({ quote_status: 'DECLINED' });

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Decline quote')).toBeTruthy());
    await pressDecline();

    await waitFor(() => expect(screen.getByText('No quote available yet')).toBeTruthy());
    expect(screen.queryByText('$50.00')).toBeNull();
  });

  // Current-read ambiguous-network reconciliation: safe "couldn't confirm", no false success.
  it('ambiguous-network reconciliation (current read) surfaces a safe state, not stale success', async () => {
    mockGetClientQuote
      .mockResolvedValueOnce(baseQuote())  // focus -> SENT
      .mockResolvedValueOnce(baseQuote()); // ambiguous-network reconciliation -> still SENT
    mockAcceptClientQuote.mockRejectedValue(new Error('Network request failed')); // no status

    await render(<ClientRequestDetailScreen route={route()} />);
    await waitFor(() => expect(screen.getByLabelText('Accept quote')).toBeTruthy());
    await pressAccept();

    await waitFor(() => expect(screen.getByText(/couldn't confirm your action/)).toBeTruthy());
    // Not a false success; Accept remains for deliberate retry.
    expect(screen.getByLabelText('Accept quote')).toBeTruthy();
  });
});
