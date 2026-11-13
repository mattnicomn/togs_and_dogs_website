import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';

const mockRead = jest.fn();
const mockDecide = jest.fn();
jest.mock('../src/api/client', () => ({
  getAdminRequest: (...a: any[]) => mockRead(...a),
  processCancellationDecision: (...a: any[]) => mockDecide(...a),
}));
jest.mock('../src/components/ConfirmationModal', () => {
  const { Text, TouchableOpacity } = require('react-native');
  return {
    ConfirmationModal: ({ visible, title, message, onConfirm, onCancel }: any) =>
      visible ? (
        <>
          <Text>{message}</Text>
          <TouchableOpacity onPress={onConfirm}><Text>{`Confirm ${title}`}</Text></TouchableOpacity>
          <TouchableOpacity onPress={onCancel}><Text>{`Cancel ${title}`}</Text></TouchableOpacity>
        </>
      ) : null,
  };
});

import { CancellationDecisionPanel } from '../src/components/CancellationDecisionPanel';

// ---- ordered, explicit authoritative-read queue (unexpected reads fail loudly) -------
type Step = { ok: any } | { fail: any } | { pending: (res: (v: any) => void) => void };
let reads: Step[] = [];
const ok = (v: any): Step => ({ ok: v });
const fail = (e: any): Step => ({ fail: e });
const queue = (...s: Step[]) => { reads.push(...s); };
const apiErr = (status: number, message = `HTTP ${status}`) => Object.assign(new Error(message), { status });

// D-4: BE-CANCEL-1 records a server-generated cycle id and the verified prior status.
const CYCLE = '6f1c2a3b-4d5e-4f60-8a7b-9c0d1e2f3a4b';
const CYCLE_B = '0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d';
const pending = (extra: any = {}) => ({
  request_id: 'req-1', client_id: 'client-1', status: 'CANCELLATION_REQUESTED',
  cancellation_reason: 'Family emergency', cancellation_requested_at: '2026-11-08T10:00:00Z',
  cancellation_request_id: CYCLE, cancellation_prior_status: 'ASSIGNED',
  sync_failures: [], ...extra,
});
/** A pre-BE-CANCEL-1 pending request: no cycle id and no verified prior status. */
const legacyPending = (extra: any = {}) => {
  const { cancellation_request_id, cancellation_prior_status, ...rest } = pending(extra);
  return rest;
};
const cancelled = (extra: any = {}) => pending({ status: 'CANCELLED', ...extra });
const denied = (extra: any = {}) => pending({ status: 'CANCELLATION_DENIED', ...extra });
/** BE-CANCEL-1 DENY: the booking is restored to its verified prior status. */
const restored = (status: string, extra: any = {}) => pending({ status, ...extra });
const conflict = (code?: string, message = 'Conflict') =>
  Object.assign(new Error(message), { status: 409, ...(code ? { code } : {}) });

let pushed: any[] = [];
let setReq: (u: any) => void = () => {};
const Harness = ({ initial, role, onSessionExpired }: any) => {
  const [req, set] = React.useState(initial);
  setReq = set;
  return (
    <CancellationDecisionPanel
      request={req}
      role={role}
      onAuthoritativeRequest={(fresh: any) => { pushed.push(fresh); set(fresh); }}
      onSessionExpired={onSessionExpired}
    />
  );
};

async function mount(initial: any, opts: { role?: any; hydration?: Step | null; onSessionExpired?: () => void; wait?: boolean } = {}) {
  const role = 'role' in opts ? opts.role : 'owner';
  if (opts.hydration) reads.unshift(opts.hydration);
  const v = await render(<Harness initial={initial} role={role} onSessionExpired={opts.onSessionExpired} />);
  if (opts.wait !== false && opts.hydration) {
    await waitFor(() => expect(v.queryByTestId('cancellation-loading')).toBeNull());
  }
  return v;
}
const mountReady = async (rec: any = pending(), opts: any = {}) => {
  const v = await mount(rec, { hydration: ok(rec), ...opts });
  await v.findByTestId('cancellation-decision');
  return v;
};
const confirm = async (v: any, decision: 'Approve' | 'Deny') => {
  await fireEvent.press(v.getByLabelText(`${decision} Cancellation`));
  await fireEvent.press(v.getByText(`Confirm ${decision} cancellation?`));
};

beforeEach(() => {
  reads = [];
  pushed = [];
  mockRead.mockReset().mockImplementation(() => {
    const step = reads.shift();
    if (!step) return Promise.reject(new Error('UNEXPECTED getAdminRequest call'));
    if ('ok' in step) return Promise.resolve(step.ok);
    if ('fail' in step) return Promise.reject(step.fail);
    return new Promise(step.pending);
  });
  mockDecide.mockReset().mockResolvedValue({ message: 'Cancellation request approved.', new_status: 'CANCELLED' });
});
afterEach(() => {
  expect(reads).toEqual([]); // every queued read consumed: no missing or extra GETs
});

// =====================================================================================
describe('S2 CancellationDecisionPanel: role and status gating', () => {
  it.each(['staff', 'client', 'unknown', null, undefined, '', 'Owner', 'ADMIN'])('renders nothing and reads nothing for role %p', async role => {
    const v = await mount(pending(), { role, hydration: null });
    expect(v.queryByText(/Cancellation/)).toBeNull();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    expect(mockRead).not.toHaveBeenCalled();
  });

  it.each(['ASSIGNED', 'APPROVED', 'CANCELLED', 'CANCELLATION_DENIED', 'PENDING_REVIEW', undefined])(
    'owner sees nothing and reads nothing when the screen status is %p',
    async status => {
      const v = await mount(pending({ status }), { hydration: null });
      expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
      expect(v.queryByTestId('cancellation-loading')).toBeNull();
      expect(mockRead).not.toHaveBeenCalled();
    }
  );

  it.each(['owner', 'admin'])('%s: hydrates, then shows Approve/Deny with reason', async role => {
    const v = await mountReady(pending(), { role });
    expect(mockRead).toHaveBeenCalledWith('req-1', 'client-1');
    expect(v.getByText('Reason: Family emergency')).toBeTruthy();
    expect(v.getByLabelText('Approve Cancellation')).toBeTruthy();
    expect(v.getByLabelText('Deny Cancellation')).toBeTruthy();
  });

  it('no actions while hydration is in flight', async () => {
    let release: (x: any) => void = () => {};
    const v = await mount(pending(), { hydration: { pending: r => { release = r; } }, wait: false });
    expect(v.getByTestId('cancellation-loading')).toBeTruthy();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    release(pending());
    expect(await v.findByLabelText('Approve Cancellation')).toBeTruthy();
  });

  it('authoritative status that is no longer CANCELLATION_REQUESTED: no actions, screen updated', async () => {
    const v = await mount(pending(), { hydration: ok(cancelled()) });
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    expect(pushed).toHaveLength(1);
    expect(pushed[0].status).toBe('CANCELLED');
  });

  it.each([
    ['request_id', { request_id: 'other' }],
    ['client_id', { client_id: 'other' }],
  ])('refuses hydration when %s differs', async (_k, diff) => {
    const v = await mount(pending(), { hydration: ok(pending(diff)) });
    expect(await v.findByText(/Booking identity could not be confirmed/)).toBeTruthy();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    expect(pushed).toHaveLength(0);
  });

  it('hydration failure: truthful error and explicit read-only Retry', async () => {
    const v = await mount(pending(), { hydration: fail(new Error('Network request failed')) });
    expect(await v.findByText(/We couldn't load the latest cancellation request/)).toBeTruthy();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    expect(mockRead).toHaveBeenCalledTimes(1);
    queue(ok(pending()));
    await fireEvent.press(v.getByLabelText('Retry loading cancellation request'));
    expect(await v.findByLabelText('Approve Cancellation')).toBeTruthy();
    expect(mockDecide).not.toHaveBeenCalled();
  });

  it.each([
    [403, /don't have permission to view/],
    [404, /could not be found/],
  ])('hydration HTTP %p is reported', async (status, text) => {
    const v = await mount(pending(), { hydration: fail(apiErr(status as number)) });
    expect(await v.findByText(text as RegExp)).toBeTruthy();
  });

  it('hydration 401 triggers session recovery', async () => {
    const onExpired = jest.fn();
    await mount(pending(), { hydration: fail(apiErr(401)), onSessionExpired: onExpired });
    await waitFor(() => expect(onExpired).toHaveBeenCalledTimes(1));
  });
});

// =====================================================================================
describe('S2 CancellationDecisionPanel: decisions', () => {
  it('Approve: confirm, re-read, exact literal + note, then authoritative refresh', async () => {
    const v = await mountReady();
    queue(ok(pending()), ok(cancelled()));
    await fireEvent.changeText(v.getByLabelText('Cancellation decision note'), '  Refund issued  ');
    await fireEvent.press(v.getByLabelText('Approve Cancellation'));
    expect(mockDecide).not.toHaveBeenCalled(); // confirmation required
    expect(v.getByText(/Completed visits are kept/)).toBeTruthy();
    await fireEvent.press(v.getByText('Confirm Approve cancellation?'));
    await waitFor(() => expect(mockDecide).toHaveBeenCalledTimes(1));
    expect(mockDecide).toHaveBeenCalledWith('req-1', 'client-1', 'APPROVE', 'Refund issued', CYCLE);
    expect(await v.findByText(/Cancellation request approved\. No calendar-cleanup or staff-notification failures were recorded/)).toBeTruthy();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull(); // no second decision
    expect(pushed.map(p => p.status)).toEqual(['CANCELLED']);
    expect(mockRead).toHaveBeenCalledTimes(3); // hydrate + guard + refresh
  });

  it.each(['ASSIGNED', 'APPROVED'])('Deny: sends DENY + cycle id and reports restoration to the verified prior %s', async prior => {
    mockDecide.mockResolvedValueOnce({ message: `Cancellation request denied. Booking status restored to ${prior}.`, new_status: prior });
    const rec = pending({ cancellation_prior_status: prior });
    const v = await mountReady(rec);
    expect(v.getByLabelText('Deny Cancellation')).toBeTruthy();
    queue(ok(rec), ok(restored(prior, { cancellation_prior_status: prior })));
    await fireEvent.press(v.getByLabelText('Deny Cancellation'));
    const label = prior === 'ASSIGNED' ? 'Assigned' : 'Approved';
    expect(v.getByText(new RegExp(`returns it to its previous status \\(${label}\\)\\. Visits are not changed\\.`))).toBeTruthy();
    await fireEvent.press(v.getByText('Confirm Deny cancellation?'));
    await waitFor(() => expect(mockDecide).toHaveBeenCalledWith('req-1', 'client-1', 'DENY', '', CYCLE));
    expect(await v.findByText(new RegExp(`The booking is back to ${label}\\. Visits were not changed\\.`))).toBeTruthy();
    expect(v.queryByText(/The latest read shows status/)).toBeNull();
    expect(pushed.map(p => p.status)).toEqual([prior]);
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['CANCELLATION_DENIED', 'Cancellation Denied'],
    ['APPROVED', 'Approved'], // a different restoration than the verified prior ASSIGNED
    ['COMPLETED', 'COMPLETED'],
  ])('Deny: a re-read showing %s is never reported as a successful denial', async (status, label) => {
    mockDecide.mockResolvedValueOnce({ message: 'Cancellation request denied.' });
    const v = await mountReady();
    queue(ok(pending()), ok(pending({ status })));
    await confirm(v, 'Deny');
    expect(await v.findByText(new RegExp(`The latest read shows status ${label}, not Assigned`))).toBeTruthy();
    expect(v.queryByText(/The booking is back to/)).toBeNull();
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });

  it('cancelling the confirmation submits nothing and reads nothing more', async () => {
    const v = await mountReady();
    await fireEvent.press(v.getByLabelText('Approve Cancellation'));
    await fireEvent.press(v.getByText('Cancel Approve cancellation?'));
    expect(mockDecide).not.toHaveBeenCalled();
    expect(mockRead).toHaveBeenCalledTimes(1);
  });

  it('shows calendar/SNS sync failures recorded by the server without implying success', async () => {
    const v = await mountReady(pending({ sync_failures: [{ type: 'GOOGLE_CALENDAR', error: 'old failure' }] }));
    queue(
      ok(pending({ sync_failures: [{ type: 'GOOGLE_CALENDAR', error: 'old failure' }] })),
      ok(cancelled({ sync_failures: [
        { type: 'GOOGLE_CALENDAR', error: 'old failure' },
        { type: 'GOOGLE_CALENDAR', error: 'Event ID e1 cleanup failed: 403' },
        { type: 'SNS_NOTIFICATION', error: 'SNS notification failed: x' },
      ] })),
    );
    await confirm(v, 'Approve');
    expect(await v.findByText(/Some follow-up steps reported problems/)).toBeTruthy();
    expect(v.getByText(/Google Calendar cleanup failed: Event ID e1 cleanup failed: 403/)).toBeTruthy();
    expect(v.getByText(/Staff notification failed: SNS notification failed: x/)).toBeTruthy();
    expect(v.queryByText(/old failure/)).toBeNull(); // only failures new since the decision
    expect(v.queryByText(/No calendar-cleanup or staff-notification failures/)).toBeNull();
  });

  it('server-reported calendar deletions are relayed verbatim', async () => {
    mockDecide.mockResolvedValueOnce({ message: 'Cancellation request approved. Deleted 2 calendar event(s).', new_status: 'CANCELLED' });
    const v = await mountReady();
    queue(ok(pending()), ok(cancelled()));
    await confirm(v, 'Approve');
    expect(await v.findByText(/Deleted 2 calendar event\(s\)\./)).toBeTruthy();
  });

  it('success followed by refresh failure is reported as success-not-refreshed (never a failed decision)', async () => {
    const v = await mountReady();
    queue(ok(pending()), fail(new Error('offline')));
    await confirm(v, 'Approve');
    expect(await v.findByText(/Cancellation request approved\. However, the latest booking state could not be refreshed, so calendar cleanup and staff notification results are unknown/)).toBeTruthy();
    expect(v.queryByText(/couldn't confirm your decision/)).toBeNull();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull(); // no double decision
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });

  it('authoritative refresh showing an unexpected status is flagged', async () => {
    const v = await mountReady();
    queue(ok(pending()), ok(denied()));
    await confirm(v, 'Approve');
    expect(await v.findByText(/The latest read shows status Cancellation Denied, not Cancelled/)).toBeTruthy();
  });

  it('locks against a duplicate submission while in flight', async () => {
    const v = await mountReady();
    let release: (x: any) => void = () => {};
    queue({ pending: r => { release = r; } }, ok(cancelled()));
    await fireEvent.press(v.getByLabelText('Approve Cancellation'));
    const first = fireEvent.press(v.getByText('Confirm Approve cancellation?'));
    await waitFor(() => expect(mockRead).toHaveBeenCalledTimes(2));
    expect(v.getByLabelText('Approve Cancellation').props.accessibilityState).toEqual(expect.objectContaining({ disabled: true }));
    expect(v.getByLabelText('Deny Cancellation').props.accessibilityState).toEqual(expect.objectContaining({ disabled: true }));
    expect(v.getByLabelText('Cancellation decision note').props.editable).toBe(false);
    await act(async () => { release(pending()); await first; });
    await waitFor(() => expect(mockDecide).toHaveBeenCalledTimes(1));
    await v.findByText(/Cancellation request approved/);
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });
});

// =====================================================================================
describe('S2 CancellationDecisionPanel: stale / ineligible refusal (client-side only)', () => {
  it('refuses when the request is no longer CANCELLATION_REQUESTED at submit time', async () => {
    const v = await mountReady();
    queue(ok(cancelled()));
    await confirm(v, 'Deny');
    expect(await v.findByText(/no longer awaiting a cancellation decision \(current status: Cancelled\)\. No decision was submitted\./)).toBeTruthy();
    expect(mockDecide).not.toHaveBeenCalled();
    expect(v.queryByLabelText('Deny Cancellation')).toBeNull();
    expect(pushed.map(p => p.status)).toEqual(['CANCELLED']);
  });

  it('refuses when the pending request changed (new reason/time) and shows the latest', async () => {
    const v = await mountReady();
    queue(ok(pending({ cancellation_reason: 'Changed plans', cancellation_requested_at: '2026-11-09T09:00:00Z' })));
    await confirm(v, 'Approve');
    expect(await v.findByText(/changed since it was loaded.*no decision was submitted/)).toBeTruthy();
    expect(mockDecide).not.toHaveBeenCalled();
    expect(v.getByText('Reason: Changed plans')).toBeTruthy();
    // A fresh, deliberate decision on the latest data is then allowed.
    queue(ok(pending({ cancellation_reason: 'Changed plans', cancellation_requested_at: '2026-11-09T09:00:00Z' })), ok(cancelled()));
    await confirm(v, 'Approve');
    await waitFor(() => expect(mockDecide).toHaveBeenCalledTimes(1));
  });

  it.each([
    ['request_id', { request_id: 'other' }],
    ['client_id', { client_id: 'other' }],
  ])('refuses when the pre-submit read %s differs', async (_k, diff) => {
    const v = await mountReady();
    queue(ok(pending(diff)));
    await confirm(v, 'Approve');
    expect(await v.findByText(/Couldn't verify the latest booking state, so no decision was submitted/)).toBeTruthy();
    expect(mockDecide).not.toHaveBeenCalled();
  });

  it('refuses when the pre-submit read fails', async () => {
    const v = await mountReady();
    queue(fail(new Error('offline')));
    await confirm(v, 'Approve');
    expect(await v.findByText(/no decision was submitted/)).toBeTruthy();
    expect(mockDecide).not.toHaveBeenCalled();
  });

  it('pre-submit 401 triggers session recovery without submitting', async () => {
    const onExpired = jest.fn();
    const v = await mountReady(pending(), { onSessionExpired: onExpired });
    queue(fail(apiErr(401)));
    await confirm(v, 'Approve');
    await waitFor(() => expect(onExpired).toHaveBeenCalledTimes(1));
    expect(mockDecide).not.toHaveBeenCalled();
  });
});

// =====================================================================================
describe('S2 CancellationDecisionPanel: mutation errors, never retried', () => {
  it.each([
    [400, 'Missing required decision fields', 'Missing required decision fields'],
    [403, 'Forbidden', "You don't have permission to approve this cancellation."],
    [404, 'Booking request not found', 'This booking request could not be found.'],
  ])('HTTP %p is mapped without a reconciliation read', async (status, message, expected) => {
    const v = await mountReady();
    queue(ok(pending()));
    mockDecide.mockRejectedValueOnce(apiErr(status as number, message as string));
    await confirm(v, 'Approve');
    expect(await v.findByText(expected as string)).toBeTruthy();
    expect(mockDecide).toHaveBeenCalledTimes(1);
    expect(v.getByLabelText('Approve Cancellation')).toBeTruthy(); // manual decision still possible
  });

  it('401 during the decision triggers session recovery', async () => {
    const onExpired = jest.fn();
    const v = await mountReady(pending(), { onSessionExpired: onExpired });
    queue(ok(pending()));
    mockDecide.mockRejectedValueOnce(apiErr(401, 'Your session expired. Please sign in again.'));
    await confirm(v, 'Approve');
    await waitFor(() => expect(onExpired).toHaveBeenCalledTimes(1));
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['network failure', new Error('Network request failed')],
    ['HTTP 500', apiErr(500, 'Failed to update cancellation decision')],
    ['unexpected HTTP 418', apiErr(418)],
  ])('%s with the request still pending: safe read, truthful "may not have been applied"', async (_l, err) => {
    const v = await mountReady();
    queue(ok(pending()), ok(pending()));
    mockDecide.mockRejectedValueOnce(err);
    await confirm(v, 'Approve');
    expect(await v.findByText(/couldn't confirm your decision, and the latest read still shows the cancellation awaiting a decision/)).toBeTruthy();
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });

  it('network failure where the decision actually landed: reports the new status and sync failures without claiming certainty', async () => {
    const v = await mountReady();
    queue(ok(pending()), ok(cancelled({ sync_failures: [{ type: 'GOOGLE_CALENDAR', error: 'cleanup failed' }] })));
    mockDecide.mockRejectedValueOnce(new Error('Network request failed'));
    await confirm(v, 'Approve');
    expect(await v.findByText(/couldn't confirm your decision\. The booking now shows Cancelled/)).toBeTruthy();
    expect(v.getByText(/Google Calendar cleanup failed: cleanup failed/)).toBeTruthy();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });

  it('409 without a code: reloads and explains, without resubmitting', async () => {
    const v = await mountReady();
    queue(ok(pending()), ok(pending()));
    mockDecide.mockRejectedValueOnce(conflict());
    await confirm(v, 'Deny');
    expect(await v.findByText(/booking changed before the decision could be applied/)).toBeTruthy();
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });

  it('unknown outcome with a failing reload: no actions until an explicit reload', async () => {
    const v = await mountReady();
    queue(ok(pending()), fail(new Error('offline')));
    mockDecide.mockRejectedValueOnce(new Error('Network request failed'));
    await confirm(v, 'Approve');
    expect(await v.findByText(/couldn't confirm your decision or reload the booking/)).toBeTruthy();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    queue(ok(cancelled()));
    await fireEvent.press(v.getByLabelText('Retry loading cancellation request'));
    await waitFor(() => expect(pushed.map(p => p.status)).toContain('CANCELLED'));
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });
});

// =====================================================================================
describe('S2 CancellationDecisionPanel: screen-driven state changes', () => {
  it('a screen refresh that moves the booking out of CANCELLATION_REQUESTED withdraws the actions', async () => {
    const v = await mountReady();
    await act(async () => { setReq(cancelled()); });
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    expect(v.queryByLabelText('Deny Cancellation')).toBeNull();
    expect(mockDecide).not.toHaveBeenCalled();
  });

  it('withdrawing during an open confirmation closes it without submitting', async () => {
    const v = await mountReady();
    await fireEvent.press(v.getByLabelText('Approve Cancellation'));
    expect(v.getByText('Confirm Approve cancellation?')).toBeTruthy();
    await act(async () => { setReq(denied()); });
    expect(v.queryByText('Confirm Approve cancellation?')).toBeNull();
    expect(mockDecide).not.toHaveBeenCalled();
  });

  it('a screen refresh back into CANCELLATION_REQUESTED re-hydrates before offering actions', async () => {
    const v = await mount(pending({ status: 'ASSIGNED' }), { hydration: null });
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    queue(ok(pending()));
    await act(async () => { setReq(pending()); });
    expect(await v.findByLabelText('Approve Cancellation')).toBeTruthy();
    expect(mockRead).toHaveBeenCalledTimes(1);
  });
});

// =====================================================================================
describe('D-4: cycle identity, verified prior status (O-1 A) and 409 classification', () => {
  it('legacy request (no cycle id, no prior status): Deny is not offered; Approve sends no cycle id', async () => {
    const v = await mountReady(legacyPending());
    expect(v.queryByLabelText('Deny Cancellation')).toBeNull();
    expect(v.getByTestId('cancellation-deny-unavailable')).toBeTruthy();
    expect(v.getByText(/no verified prior booking status \(Approved or Assigned\).*Owner review is required\./)).toBeTruthy();
    queue(ok(legacyPending()), ok(cancelled()));
    await confirm(v, 'Approve');
    await waitFor(() => expect(mockDecide).toHaveBeenCalledTimes(1));
    expect(mockDecide.mock.calls[0]).toEqual(['req-1', 'client-1', 'APPROVE', '', undefined]);
    expect(await v.findByText(/Cancellation request approved/)).toBeTruthy();
  });

  it('cycle id present but no prior status (repeat request on a legacy record): Approve sends the id; Deny unavailable', async () => {
    const rec = pending({ cancellation_prior_status: undefined });
    const v = await mountReady(rec);
    expect(v.queryByLabelText('Deny Cancellation')).toBeNull();
    queue(ok(rec), ok(cancelled()));
    await confirm(v, 'Approve');
    await waitFor(() => expect(mockDecide).toHaveBeenCalledWith('req-1', 'client-1', 'APPROVE', '', CYCLE));
  });

  it.each(['BOOKED', 'SCHEDULED', 'JOB_CREATED', 'CANCELLATION_DENIED', 'assigned', ''])(
    'a non-verified prior status %p never enables Deny', async prior => {
      const v = await mountReady(pending({ cancellation_prior_status: prior }));
      expect(v.queryByLabelText('Deny Cancellation')).toBeNull();
      expect(v.getByLabelText('Approve Cancellation')).toBeTruthy();
    }
  );

  it('a cycle id that changed between hydration and submit refuses the submission', async () => {
    const v = await mountReady();
    queue(ok(pending({ cancellation_request_id: CYCLE_B })));
    await confirm(v, 'Approve');
    expect(await v.findByText(/changed since it was loaded/)).toBeTruthy();
    expect(mockDecide).not.toHaveBeenCalled();
  });

  it('a cycle id that disappeared between hydration and submit refuses the submission', async () => {
    const v = await mountReady();
    queue(ok(pending({ cancellation_request_id: undefined })));
    await confirm(v, 'Approve');
    expect(await v.findByText(/changed since it was loaded/)).toBeTruthy();
    expect(mockDecide).not.toHaveBeenCalled();
  });

  it('a prior status that changed between hydration and submit refuses the submission', async () => {
    const v = await mountReady();
    queue(ok(pending({ cancellation_prior_status: 'APPROVED' })));
    await confirm(v, 'Deny');
    expect(await v.findByText(/changed since it was loaded/)).toBeTruthy();
    expect(mockDecide).not.toHaveBeenCalled();
  });

  it('409 LEGACY_PRIOR_STATUS_UNKNOWN: owner review message, Deny withdrawn, Approve kept, no resubmit', async () => {
    const v = await mountReady();
    queue(ok(pending()), ok(pending()));
    mockDecide.mockRejectedValueOnce(conflict('LEGACY_PRIOR_STATUS_UNKNOWN', 'cannot be denied automatically'));
    await confirm(v, 'Deny');
    expect(await v.findByText(/cannot be denied automatically\. Owner review is required\. No decision was applied\./)).toBeTruthy();
    expect(v.queryByLabelText('Deny Cancellation')).toBeNull();
    expect(v.getByLabelText('Approve Cancellation')).toBeTruthy();
    expect(v.queryByText(/booking changed before the decision could be applied/)).toBeNull();
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });

  it('409 CANCELLATION_CYCLE_MISMATCH: shows the current request; a later Approve uses the new cycle id', async () => {
    const v = await mountReady();
    queue(ok(pending()), ok(pending({ cancellation_request_id: CYCLE_B })));
    mockDecide.mockRejectedValueOnce(conflict('CANCELLATION_CYCLE_MISMATCH'));
    await confirm(v, 'Approve');
    expect(await v.findByText(/decision was for an earlier cancellation request\. The current request is shown/)).toBeTruthy();
    expect(mockDecide).toHaveBeenCalledTimes(1);
    expect(pushed.map(p => p.cancellation_request_id)).toEqual([CYCLE_B]);
    queue(ok(pending({ cancellation_request_id: CYCLE_B })), ok(cancelled()));
    await confirm(v, 'Approve');
    await waitFor(() => expect(mockDecide).toHaveBeenCalledTimes(2));
    expect(mockDecide.mock.calls[1]).toEqual(['req-1', 'client-1', 'APPROVE', '', CYCLE_B]);
  });

  it('409 CANCELLATION_CYCLE_MISMATCH when the booking is no longer pending: no actions', async () => {
    const v = await mountReady();
    queue(ok(pending()), ok(cancelled({ cancellation_request_id: CYCLE_B })));
    mockDecide.mockRejectedValueOnce(conflict('CANCELLATION_CYCLE_MISMATCH'));
    await confirm(v, 'Deny');
    expect(await v.findByText(/no longer awaiting a cancellation decision \(current status: Cancelled\)\. No decision was applied\./)).toBeTruthy();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });

  it('409 CANCELLATION_STATE_CHANGED: latest details shown for review, no resubmit', async () => {
    const v = await mountReady();
    queue(ok(pending()), ok(pending({ cancellation_reason: 'Updated reason' })));
    mockDecide.mockRejectedValueOnce(conflict('CANCELLATION_STATE_CHANGED'));
    await confirm(v, 'Approve');
    expect(await v.findByText(/This cancellation request changed before the decision could be applied\. The latest details are shown/)).toBeTruthy();
    expect(v.getByText('Reason: Updated reason')).toBeTruthy();
    expect(v.getByLabelText('Approve Cancellation')).toBeTruthy();
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });

  it('409 CANCELLATION_NOT_PENDING: shows the current status and offers no decision', async () => {
    const v = await mountReady();
    queue(ok(pending()), ok(restored('ASSIGNED')));
    mockDecide.mockRejectedValueOnce(conflict('CANCELLATION_NOT_PENDING'));
    await confirm(v, 'Approve');
    expect(await v.findByText(/no longer awaiting a cancellation decision \(current status: Assigned\)\. No decision was applied\./)).toBeTruthy();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    expect(v.queryByLabelText('Deny Cancellation')).toBeNull();
    expect(pushed.map(p => p.status)).toEqual(['ASSIGNED']);
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });

  it('409 with a known code and a failing reload: actions withheld until an explicit reload', async () => {
    const v = await mountReady();
    queue(ok(pending()), fail(new Error('offline')));
    mockDecide.mockRejectedValueOnce(conflict('CANCELLATION_STATE_CHANGED'));
    await confirm(v, 'Approve');
    expect(await v.findByText(/decision was not applied, and the latest booking could not be reloaded/)).toBeTruthy();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull();
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });

  it('409 with an unknown code falls back to the generic safe-read path', async () => {
    const v = await mountReady();
    queue(ok(pending()), ok(pending()));
    mockDecide.mockRejectedValueOnce(conflict('SOMETHING_NEW'));
    await confirm(v, 'Approve');
    expect(await v.findByText(/booking changed before the decision could be applied/)).toBeTruthy();
    expect(mockDecide).toHaveBeenCalledTimes(1);
  });
});
