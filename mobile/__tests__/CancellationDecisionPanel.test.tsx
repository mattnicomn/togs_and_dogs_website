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

const pending = (extra: any = {}) => ({
  request_id: 'req-1', client_id: 'client-1', status: 'CANCELLATION_REQUESTED',
  cancellation_reason: 'Family emergency', cancellation_requested_at: '2026-11-08T10:00:00Z',
  sync_failures: [], ...extra,
});
const cancelled = (extra: any = {}) => pending({ status: 'CANCELLED', ...extra });
const denied = (extra: any = {}) => pending({ status: 'CANCELLATION_DENIED', ...extra });

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
    expect(mockDecide).toHaveBeenCalledWith('req-1', 'client-1', 'APPROVE', 'Refund issued');
    expect(await v.findByText(/Cancellation request approved\. No calendar-cleanup or staff-notification failures were recorded/)).toBeTruthy();
    expect(v.queryByLabelText('Approve Cancellation')).toBeNull(); // no second decision
    expect(pushed.map(p => p.status)).toEqual(['CANCELLED']);
    expect(mockRead).toHaveBeenCalledTimes(3); // hydrate + guard + refresh
  });

  it('Deny: sends the exact DENY literal and reports the denied state', async () => {
    mockDecide.mockResolvedValueOnce({ message: 'Cancellation request denied.', new_status: 'CANCELLATION_DENIED' });
    const v = await mountReady();
    queue(ok(pending()), ok(denied()));
    await confirm(v, 'Deny');
    await waitFor(() => expect(mockDecide).toHaveBeenCalledWith('req-1', 'client-1', 'DENY', ''));
    expect(await v.findByText(/Cancellation request denied\. The booking stays active as Cancellation Denied\./)).toBeTruthy();
    expect(pushed.map(p => p.status)).toEqual(['CANCELLATION_DENIED']);
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

  it('409: reloads and explains, without resubmitting', async () => {
    const v = await mountReady();
    queue(ok(pending()), ok(pending()));
    mockDecide.mockRejectedValueOnce(apiErr(409, 'Conflict'));
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
