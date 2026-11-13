import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CancellationDecisionModal } from '../src/components/AdminDashboard';
import { getAdminRequest, processCancellationDecision, reviewRequest } from '../src/api/client';

vi.mock('../src/api/auth', () => ({
  signIn: vi.fn(), forgotPassword: vi.fn(), confirmForgotPassword: vi.fn(),
  getSession: vi.fn(), getEffectiveRole: vi.fn(),
}));

vi.mock('../src/api/client', () => ({
  getAdminRequest: vi.fn(),
  processCancellationDecision: vi.fn(),
  reviewRequest: vi.fn(),
}));

const CYCLE = '6f1c2a3b-4d5e-4f60-8a7b-9c0d1e2f3a4b';
const OTHER_CYCLE = '0a1b2c3d-4e5f-4a6b-9c7d-8e9f0a1b2c3d';

const pending = (overrides = {}) => ({
  PK: 'REQ#req-1', SK: 'CLIENT#client-1',
  request_id: 'req-1', client_id: 'client-1',
  status: 'CANCELLATION_REQUESTED',
  cancellation_request_id: CYCLE,
  cancellation_requested_at: '2030-01-01T10:00:00Z',
  cancellation_reason: 'Plans changed',
  ...overrides,
});

const httpError = (status, message, code) => Object.assign(new Error(message), { status, code });

const renderModal = (props = {}) => {
  const onClose = vi.fn();
  render(<CancellationDecisionModal request={pending()} role="owner" onClose={onClose} {...props} />);
  return { onClose };
};

const choose = async (label) => {
  fireEvent.click(await screen.findByRole('button', { name: label }));
};

describe('WEB-CANCEL-1 cancellation decision modal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Owner/admin allowlist (covered through the component; the helper is not exported).
  it.each(['staff', 'client', 'platform_admin', 'unknown', 'OWNER', '', null, undefined])(
    'renders nothing and reads nothing for role %p', (role) => {
    render(<CancellationDecisionModal request={pending()} role={role} onClose={vi.fn()} />);
    expect(screen.queryByTestId('cancellation-decision-modal')).toBeNull();
    expect(getAdminRequest).not.toHaveBeenCalled();
  });

  it.each(['owner', 'admin'])('%s sees explicit Approve / Deny / Dismiss after an authoritative read', async (role) => {
    getAdminRequest.mockResolvedValue(pending());
    renderModal({ role });
    expect(await screen.findByRole('button', { name: 'Approve Cancellation' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Deny Cancellation' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Dismiss' })).toBeTruthy();
    expect(getAdminRequest).toHaveBeenCalledWith('req-1', 'client-1');
  });

  it('Dismiss closes without any decision', async () => {
    getAdminRequest.mockResolvedValue(pending());
    const { onClose } = renderModal();
    await choose('Dismiss');
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(processCancellationDecision).not.toHaveBeenCalled();
    expect(reviewRequest).not.toHaveBeenCalled();
  });

  it('Dismiss on the confirmation step also sends nothing', async () => {
    getAdminRequest.mockResolvedValue(pending());
    const { onClose } = renderModal();
    await choose('Approve Cancellation');
    await choose('Dismiss');
    expect(onClose).toHaveBeenCalled();
    expect(processCancellationDecision).not.toHaveBeenCalled();
  });

  it('choosing a decision requires an explicit confirmation before submitting', async () => {
    getAdminRequest.mockResolvedValue(pending());
    renderModal();
    await choose('Deny Cancellation');
    expect(processCancellationDecision).not.toHaveBeenCalled();
    expect(await screen.findByRole('button', { name: 'Confirm Deny Cancellation' })).toBeTruthy();
    await choose('Back');
    expect(await screen.findByRole('button', { name: 'Approve Cancellation' })).toBeTruthy();
    expect(processCancellationDecision).not.toHaveBeenCalled();
  });

  it.each([['APPROVE', 'Approve Cancellation', 'Confirm Approve Cancellation'],
           ['DENY', 'Deny Cancellation', 'Confirm Deny Cancellation']])(
    'sends the exact %s payload with the cycle id after a fresh re-read', async (decision, choice, confirm) => {
      getAdminRequest.mockResolvedValue(pending());
      processCancellationDecision.mockResolvedValue({ message: 'ok', new_status: decision === 'APPROVE' ? 'CANCELLED' : 'ASSIGNED', warnings: [] });
      renderModal();
      await choose(choice);
      fireEvent.change(screen.getByLabelText('Decision note (optional)'), { target: { value: '  audit note  ' } });
      getAdminRequest.mockResolvedValueOnce(pending())                      // pre-mutation re-read
        .mockResolvedValueOnce(pending({ status: decision === 'APPROVE' ? 'CANCELLED' : 'ASSIGNED' }));
      await choose(confirm);
      await waitFor(() => expect(processCancellationDecision).toHaveBeenCalledTimes(1));
      expect(processCancellationDecision).toHaveBeenCalledWith('req-1', 'client-1', decision, 'audit note', CYCLE);
      expect(getAdminRequest).toHaveBeenCalledTimes(3);                   // load, re-read, reconcile
      expect(reviewRequest).not.toHaveBeenCalled();
    });

  it('missing cycle id blocks the decision', async () => {
    getAdminRequest.mockResolvedValue(pending({ cancellation_request_id: undefined }));
    renderModal();
    expect(await screen.findByRole('alert')).toHaveTextContent(/no cancellation identity/);
    expect(screen.queryByRole('button', { name: 'Approve Cancellation' })).toBeNull();
    expect(processCancellationDecision).not.toHaveBeenCalled();
  });

  it.each(['', '   ', 42, null])('blank or non-string cycle id %p blocks the decision', async (bad) => {
    getAdminRequest.mockResolvedValue(pending({ cancellation_request_id: bad }));
    renderModal();
    expect(await screen.findByRole('alert')).toHaveTextContent(/no cancellation identity/);
    expect(screen.queryByRole('button', { name: 'Deny Cancellation' })).toBeNull();
  });

  it('a changed cycle id on the pre-mutation re-read refuses the submission', async () => {
    getAdminRequest.mockResolvedValue(pending());
    renderModal();
    await choose('Approve Cancellation');
    getAdminRequest.mockResolvedValueOnce(pending({ cancellation_request_id: OTHER_CYCLE }));
    await choose('Confirm Approve Cancellation');
    expect(await screen.findByRole('alert')).toHaveTextContent(/changed since it was loaded/);
    expect(processCancellationDecision).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Approve Cancellation' })).toBeTruthy();   // must choose again
  });

  it('a decided booking on the pre-mutation re-read refuses the submission', async () => {
    getAdminRequest.mockResolvedValue(pending());
    renderModal();
    await choose('Deny Cancellation');
    getAdminRequest.mockResolvedValueOnce(pending({ status: 'CANCELLED' }));
    await choose('Confirm Deny Cancellation');
    expect(await screen.findByRole('alert')).toHaveTextContent(/not awaiting a cancellation decision/);
    expect(processCancellationDecision).not.toHaveBeenCalled();
  });

  it('a non-pending booking offers no decision', async () => {
    getAdminRequest.mockResolvedValue(pending({ status: 'APPROVED' }));
    renderModal();
    expect(await screen.findByRole('alert')).toHaveTextContent(/current status: Approved/);
    expect(screen.queryByRole('button', { name: 'Approve Cancellation' })).toBeNull();
  });

  it.each([
    [{ request_id: 'req-OTHER' }],
    [{ client_id: 'client-OTHER' }],
  ])('identity mismatch %p blocks the decision', async (override) => {
    getAdminRequest.mockResolvedValue(pending(override));
    renderModal();
    expect(await screen.findByRole('alert')).toHaveTextContent(/identity could not be confirmed/);
    expect(processCancellationDecision).not.toHaveBeenCalled();
  });

  it('missing request or client identity reads nothing', async () => {
    render(<CancellationDecisionModal request={{ status: 'CANCELLATION_REQUESTED' }} role="owner" onClose={vi.fn()} />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/Missing request or client identity/);
    expect(getAdminRequest).not.toHaveBeenCalled();
  });

  it('prevents duplicate submissions while one is in flight', async () => {
    getAdminRequest.mockResolvedValue(pending());
    let resolveDecision;
    processCancellationDecision.mockImplementation(() => new Promise(r => { resolveDecision = r; }));
    renderModal();
    await choose('Approve Cancellation');
    const confirm = await screen.findByRole('button', { name: 'Confirm Approve Cancellation' });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    await waitFor(() => expect(processCancellationDecision).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('button', { name: 'Submitting…' })).toBeDisabled();
    await act(async () => { resolveDecision({ message: 'Cancellation request approved.', warnings: [] }); });
    expect(processCancellationDecision).toHaveBeenCalledTimes(1);
  });

  it('409 shows the server conflict without implying success, and reconciles', async () => {
    getAdminRequest.mockResolvedValue(pending());
    processCancellationDecision.mockRejectedValue(httpError(409, 'This decision was made for an earlier cancellation request.', 'CANCELLATION_CYCLE_MISMATCH'));
    renderModal();
    await choose('Approve Cancellation');
    getAdminRequest.mockResolvedValueOnce(pending()).mockResolvedValueOnce(pending({ status: 'ASSIGNED' }));
    await choose('Confirm Approve Cancellation');
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/was not applied: This decision was made for an earlier cancellation request/);
    expect(alert).toHaveTextContent(/now shows Assigned/);
    expect(screen.queryByText(/approved\./i)).toBeNull();
    expect(processCancellationDecision).toHaveBeenCalledTimes(1);     // never retried
  });

  it.each([
    [401, /session expired/i],
    [403, /permission to approve/i],
    [404, /could not be found/i],
  ])('%s is reported truthfully', async (status, text) => {
    getAdminRequest.mockResolvedValue(pending());
    processCancellationDecision.mockRejectedValue(httpError(status, 'server says no'));
    renderModal();
    await choose('Approve Cancellation');
    await choose('Confirm Approve Cancellation');
    expect(await screen.findByRole('alert')).toHaveTextContent(text);
    expect(processCancellationDecision).toHaveBeenCalledTimes(1);
  });

  it('400 shows the validation message and keeps the confirmation step', async () => {
    getAdminRequest.mockResolvedValue(pending());
    processCancellationDecision.mockRejectedValue(httpError(400, 'note must be at most 500 characters'));
    renderModal();
    await choose('Deny Cancellation');
    await choose('Confirm Deny Cancellation');
    expect(await screen.findByRole('alert')).toHaveTextContent('note must be at most 500 characters');
    expect(screen.getByRole('button', { name: 'Confirm Deny Cancellation' })).toBeTruthy();
  });

  it.each([
    ['network', new TypeError('Failed to fetch')],
    ['5xx', httpError(502, 'Bad gateway')],
  ])('%s failure is reported as uncertain and reconciled, never retried', async (_, err) => {
    getAdminRequest.mockResolvedValue(pending());
    processCancellationDecision.mockRejectedValue(err);
    renderModal();
    await choose('Approve Cancellation');
    getAdminRequest.mockResolvedValueOnce(pending()).mockResolvedValueOnce(pending({ status: 'CANCELLED' }));
    await choose('Confirm Approve Cancellation');
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/couldn't confirm whether your decision was applied/);
    expect(alert).toHaveTextContent(/now shows Cancelled/);
    expect(processCancellationDecision).toHaveBeenCalledTimes(1);
  });

  it('success reconciles the authoritative status and never claims Calendar or staff notification success', async () => {
    getAdminRequest.mockResolvedValue(pending());
    processCancellationDecision.mockResolvedValue({ message: 'Cancellation request approved.', warnings: [] });
    renderModal();
    await choose('Approve Cancellation');
    getAdminRequest.mockResolvedValueOnce(pending()).mockResolvedValueOnce(pending({ status: 'CANCELLED' }));
    await choose('Confirm Approve Cancellation');
    expect(await screen.findByText('Latest status: Cancelled.')).toBeTruthy();
    expect(screen.getByText(/best-effort\. No failures were reported, but delivery is not confirmed/)).toBeTruthy();
    expect(screen.queryByText(/calendar (event|events) (deleted|removed)/i)).toBeNull();
    expect(screen.queryByText(/staff (were )?notified/i)).toBeNull();
  });

  it('server-reported side-effect failures are shown', async () => {
    getAdminRequest.mockResolvedValue(pending());
    processCancellationDecision.mockResolvedValue({
      message: 'Cancellation request approved.',
      warnings: [{ type: 'GOOGLE_CALENDAR', error: 'API timeout' }, { type: 'SNS_NOTIFICATION', error: 'SNS down' }],
    });
    renderModal();
    await choose('Approve Cancellation');
    getAdminRequest.mockResolvedValueOnce(pending()).mockResolvedValueOnce(pending({ status: 'CANCELLED' }));
    await choose('Confirm Approve Cancellation');
    expect(await screen.findByText(/GOOGLE_CALENDAR failed: API timeout/)).toBeTruthy();
    expect(screen.getByText(/SNS_NOTIFICATION failed: SNS down/)).toBeTruthy();
    expect(screen.queryByText(/delivery is not confirmed/)).toBeNull();
  });

  it('a success whose reconcile read disagrees is flagged, not reported as done', async () => {
    getAdminRequest.mockResolvedValue(pending());
    processCancellationDecision.mockResolvedValue({ message: 'Cancellation request approved.', warnings: [] });
    renderModal();
    await choose('Approve Cancellation');
    getAdminRequest.mockResolvedValueOnce(pending()).mockResolvedValueOnce(pending());
    await choose('Confirm Approve Cancellation');
    expect(await screen.findByText(/does not match this decision/)).toBeTruthy();
  });

  it('DENY accepts either restored status (new backend) or CANCELLATION_DENIED (deployed backend)', async () => {
    for (const after of ['ASSIGNED', 'CANCELLATION_DENIED']) {
      vi.clearAllMocks();
      getAdminRequest.mockResolvedValue(pending());
      processCancellationDecision.mockResolvedValue({ message: 'Cancellation request denied.', warnings: [] });
      const { unmount } = render(<CancellationDecisionModal request={pending()} role="admin" onClose={vi.fn()} />);
      await choose('Deny Cancellation');
      getAdminRequest.mockResolvedValueOnce(pending()).mockResolvedValueOnce(pending({ status: after }));
      await choose('Confirm Deny Cancellation');
      expect(await screen.findByText(/^Latest status:/)).toBeTruthy();
      unmount();
    }
  });

  it('a failed initial read offers no decision and can be retried', async () => {
    getAdminRequest.mockRejectedValueOnce(httpError(403, 'Forbidden'));
    renderModal();
    expect(await screen.findByRole('alert')).toHaveTextContent(/don't have permission to view/);
    expect(screen.queryByRole('button', { name: 'Approve Cancellation' })).toBeNull();
    getAdminRequest.mockResolvedValueOnce(pending());
    await choose('Retry loading');
    expect(await screen.findByRole('button', { name: 'Approve Cancellation' })).toBeTruthy();
  });
});
