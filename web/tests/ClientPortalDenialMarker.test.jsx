import { describe, test, expect, beforeEach, afterEach, vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import ClientPortal from '../src/components/ClientPortal.jsx';
import { REQUEST_STATUSES } from '../src/generated/contracts.js';
import { getSession, getEffectiveRole } from '../src/api/auth';
import { getClientRequests, requestCancellation } from '../src/api/client';

vi.mock('../src/api/auth', () => ({
  getSession: vi.fn(),
  signIn: vi.fn(() => Promise.resolve({})),
  getEffectiveRole: vi.fn()
}));

vi.mock('../src/api/client', () => ({
  getClientRequests: vi.fn(),
  requestCancellation: vi.fn(() => Promise.resolve({}))
}));

// D-1: the client portal shows a "Cancellation request declined" notice only when the API
// derived cancellation_denied === true. The normal status badge and Cancel button are
// unchanged; nothing from an admin note, actor or audit entry is ever rendered.

const DENIED_AT = '2026-11-10T15:30:00+00:00';
const expectedDate = (iso) => new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

const booking = (id, overrides = {}) => ({
  request_id: id,
  client_id: 'client-1',
  status: 'ASSIGNED',
  pet_name: `Pet ${id}`,
  start_date: '2026-11-20',
  service_type: 'WALK_30MIN',
  ...overrides
});

const NOTICE_ID = 'cancellation-denied-notice';
const noticeText = (date) =>
  `Your cancellation request was declined${date ? ` on ${date}` : ''}. Your booking remains active. `
  + 'You can submit another cancellation request or contact the business for assistance.';

describe('D-1 ClientPortal cancellation-denial marker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Shape matches the real Cognito session object closely enough for ClientPortal and
    // UserProfile (getIdToken().payload), so the suite runs without console errors.
    getSession.mockResolvedValue({ getIdToken: () => ({ payload: { email: 'client@example.test', name: 'Client' } }) });
    getEffectiveRole.mockReturnValue('client');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  test.each(['ASSIGNED', 'APPROVED'])('shows the declined notice with the date for a %s booking, keeping the normal status', async (status) => {
    getClientRequests.mockResolvedValue({
      requests: [booking('1', { status, cancellation_denied: true, cancellation_denied_at: DENIED_AT })]
    });
    render(<ClientPortal />);

    const notice = await screen.findByTestId(NOTICE_ID);
    expect(within(notice).getByText('Cancellation request declined')).toBeInTheDocument();
    expect(notice).toHaveTextContent(noticeText(expectedDate(DENIED_AT)));
    // The normal status display is unchanged and independent of the notice.
    expect(screen.getByText(status === 'ASSIGNED' ? 'Scheduled' : REQUEST_STATUSES.statuses.APPROVED.label)).toBeInTheDocument();
    // The notice does not claim a booking status of its own.
    for (const word of ['Scheduled', 'Assigned', 'Approved', 'Cancelled']) {
      expect(notice).not.toHaveTextContent(word);
    }
    expect(screen.queryByText('Cancellation Pending')).not.toBeInTheDocument();
  });

  test('keeps the Cancel button available after a denial (P-2)', async () => {
    getClientRequests.mockResolvedValue({
      requests: [booking('1', { cancellation_denied: true, cancellation_denied_at: DENIED_AT })]
    });
    render(<ClientPortal />);
    await screen.findByTestId(NOTICE_ID);
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
  });

  test('a client can submit another cancellation request from a denied booking', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true));
    vi.stubGlobal('prompt', vi.fn(() => 'Changed plans'));
    vi.stubGlobal('alert', vi.fn());
    getClientRequests.mockResolvedValue({
      requests: [booking('req-9', { cancellation_denied: true, cancellation_denied_at: DENIED_AT })]
    });
    render(<ClientPortal />);
    await screen.findByTestId(NOTICE_ID);

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(requestCancellation).toHaveBeenCalledTimes(1));
    expect(requestCancellation).toHaveBeenCalledWith('req-9', 'client-1', 'Changed plans');
  });

  test('omits the date, but still shows the notice, when no date is sent', async () => {
    getClientRequests.mockResolvedValue({ requests: [booking('1', { cancellation_denied: true })] });
    render(<ClientPortal />);
    const notice = await screen.findByTestId(NOTICE_ID);
    expect(notice).toHaveTextContent(noticeText(null));
    expect(notice).not.toHaveTextContent(/declined on /);
  });

  test.each(['', 'not-a-date', 'Invalid Date', 12345, null, { at: DENIED_AT }, ['2026-11-10']])(
    'omits an unusable date (%p) without breaking the notice', async (bad) => {
      getClientRequests.mockResolvedValue({
        requests: [booking('1', { cancellation_denied: true, cancellation_denied_at: bad })]
      });
      render(<ClientPortal />);
      const notice = await screen.findByTestId(NOTICE_ID);
      expect(notice).toHaveTextContent(noticeText(null));
      expect(notice).not.toHaveTextContent(/declined on /);
    }
  );

  test.each([false, undefined, null, 'true', 1, 'yes', {}])('shows no notice when cancellation_denied is %p', async (flag) => {
    getClientRequests.mockResolvedValue({
      requests: [booking('1', { cancellation_denied: flag, cancellation_denied_at: DENIED_AT })]
    });
    render(<ClientPortal />);
    await screen.findByText('Scheduled');
    expect(screen.queryByTestId(NOTICE_ID)).not.toBeInTheDocument();
    expect(screen.queryByText('Cancellation request declined')).not.toBeInTheDocument();
  });

  test('a new cancellation request clears the marker: pending booking shows only Cancellation Pending', async () => {
    getClientRequests.mockResolvedValue({
      requests: [booking('1', { status: 'CANCELLATION_REQUESTED' })]
    });
    render(<ClientPortal />);
    expect(await screen.findByText('Cancellation Pending')).toBeInTheDocument();
    expect(screen.queryByTestId(NOTICE_ID)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument();
  });

  test('the marker is per booking: only the flagged booking shows the notice', async () => {
    getClientRequests.mockResolvedValue({
      requests: [
        booking('1', { cancellation_denied: true, cancellation_denied_at: DENIED_AT }),
        booking('2'),
        booking('3', { status: 'APPROVED' })
      ]
    });
    render(<ClientPortal />);
    await screen.findByTestId(NOTICE_ID);
    expect(screen.getAllByTestId(NOTICE_ID)).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: 'Cancel' })).toHaveLength(3);
  });

  test('legacy CANCELLATION_DENIED records are unchanged (P-6): old wording, no new notice', async () => {
    getClientRequests.mockResolvedValue({
      requests: [booking('1', { status: 'CANCELLATION_DENIED' })]
    });
    render(<ClientPortal />);
    expect(await screen.findByText('Your cancellation request was denied.')).toBeInTheDocument();
    expect(screen.queryByTestId(NOTICE_ID)).not.toBeInTheDocument();
    expect(screen.queryByText('Cancellation request declined')).not.toBeInTheDocument();
  });

  test('never renders admin notes, actors or audit data even if a record carried them', async () => {
    getClientRequests.mockResolvedValue({
      requests: [booking('1', {
        cancellation_denied: true,
        cancellation_denied_at: DENIED_AT,
        // Not sent by the API; present here to prove the UI would never render them.
        cancellation_decision_note: 'SECRET-ADMIN-NOTE',
        cancellation_decision_actor: 'owner-actor@secret.example',
        cancellation_prior_status: 'ASSIGNED',
        cancellation_request_id: '6f1c2a3b-4d5e-4f60-8a7b-9c0d1e2f3a4b',
        audit_log: [{ note: 'SECRET-AUDIT-ENTRY' }]
      })]
    });
    render(<ClientPortal />);
    await screen.findByTestId(NOTICE_ID);
    const text = document.body.textContent;
    for (const secret of ['SECRET-ADMIN-NOTE', 'owner-actor@secret.example', 'SECRET-AUDIT-ENTRY',
      '6f1c2a3b-4d5e-4f60-8a7b-9c0d1e2f3a4b']) {
      expect(text).not.toContain(secret);
    }
  });

  test('the notice is exposed as a labelled note region with text, not colour alone', async () => {
    getClientRequests.mockResolvedValue({
      requests: [booking('1', { cancellation_denied: true, cancellation_denied_at: DENIED_AT })]
    });
    render(<ClientPortal />);
    const notice = await screen.findByRole('note');
    expect(notice).toHaveAttribute('data-testid', NOTICE_ID);
    expect(notice).toHaveTextContent('Cancellation request declined');
  });
});
