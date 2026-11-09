import React from 'react';
import { act, fireEvent, render, waitFor } from '@testing-library/react-native';

const mockRead = jest.fn();
const mockUpdate = jest.fn();
const mockSend = jest.fn();
jest.mock('../src/api/client', () => ({
  getAdminRequest: (...a: any[]) => mockRead(...a),
  updateAdminQuote: (...a: any[]) => mockUpdate(...a),
  sendAdminQuote: (...a: any[]) => mockSend(...a),
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

import { AdminQuoteEditor, mergeQuoteRefresh, quoteFingerprint } from '../src/components/AdminQuoteEditor';

// ---- ordered, explicit authoritative-read queue -------------------------------------
// Every GET /admin/requests/{id} (hydration, stale guard, post-save refresh, error
// reload, retry) consumes exactly one entry, in order. An unexpected read fails loudly.
type ReadStep = { ok: any } | { fail: any } | { pending: (resolve: (v: any) => void, reject: (e: any) => void) => void };
let reads: ReadStep[] = [];
const ok = (v: any): ReadStep => ({ ok: v });
const fail = (e: any): ReadStep => ({ fail: e });
const queue = (...steps: ReadStep[]) => { reads.push(...steps); };

const apiErr = (status: number, message = `HTTP ${status}`) => Object.assign(new Error(message), { status });

const listItem = { request_id: 'req-1', client_id: 'client-1', status: 'PENDING_REVIEW' }; // incomplete list payload
const base = { ...listItem };
const draft = (extra: any = {}) => ({
  ...base,
  status: 'QUOTE_NEEDED',
  quote_status: 'DRAFT',
  quote_revision: 1,
  quote_amount_cents: 12500,
  currency: 'USD',
  deposit_amount_cents: 0,
  payment_requirement: 'NONE',
  quote_notes_client: '',
  quote_notes_internal: '',
  internal_pricing_notes: '',
  ...extra,
});

let harnessSetReq: (updater: any) => void = () => {};
/** Simulates the screen replacing its `request` (e.g. PR #46 "Refresh booking"), inside act. */
const screenRefresh = async (updater: any) => {
  await act(async () => {
    harnessSetReq(updater);
  });
};
const Harness = ({ initial, role, onSessionExpired }: any) => {
  const [req, setReq] = React.useState(initial);
  harnessSetReq = setReq;
  return (
    <AdminQuoteEditor
      request={req}
      role={role}
      onRequestRefreshed={(fresh: any) => setReq((p: any) => mergeQuoteRefresh(p, fresh))}
      onSessionExpired={onSessionExpired}
    />
  );
};

/**
 * Renders the editor. For owner/admin, `authoritative` (default: `initial`) is the
 * hydration response and the helper waits until hydration has settled.
 */
async function mount(initial: any, opts: { role?: any; authoritative?: any; onSessionExpired?: () => void; skipWait?: boolean } = {}) {
  const role = 'role' in opts ? opts.role : 'owner';
  const willHydrate = role === 'owner' || role === 'admin';
  if (willHydrate && !opts.skipWait) reads.unshift(ok(opts.authoritative ?? initial));
  const v = await render(<Harness initial={initial} role={role} onSessionExpired={opts.onSessionExpired} />);
  if (willHydrate && !opts.skipWait) {
    await waitFor(() => expect(v.queryByTestId('admin-quote-loading')).toBeNull());
  }
  return v;
}

beforeEach(() => {
  reads = [];
  mockRead.mockReset().mockImplementation(() => {
    const step = reads.shift();
    if (!step) return Promise.reject(new Error('UNEXPECTED getAdminRequest call'));
    if ('ok' in step) return Promise.resolve(step.ok);
    if ('fail' in step) return Promise.reject(step.fail);
    return new Promise(step.pending);
  });
  mockUpdate.mockReset().mockResolvedValue({ message: 'Quote updated' });
  mockSend.mockReset().mockResolvedValue({ message: 'Quote sent' });
});

afterEach(() => {
  expect(reads).toEqual([]); // every queued read was consumed: no missing or extra GETs
});

// =====================================================================================
describe('S1 AdminQuoteEditor: RBAC', () => {
  it.each(['staff', 'client', 'unknown', null, undefined, '', 'Owner'])('renders nothing and reads nothing for role %p', async role => {
    const v = await mount(draft(), { role });
    expect(v.queryByText('Quote')).toBeNull();
    expect(v.queryByLabelText('Quote amount')).toBeNull();
    expect(v.queryByLabelText('Save quote draft')).toBeNull();
    expect(v.queryByTestId('admin-quote-loading')).toBeNull();
    expect(mockRead).not.toHaveBeenCalled();
  });

  it.each(['owner', 'admin'])('hydrates and renders the editor for %s', async role => {
    const v = await mount(draft(), { role });
    expect(mockRead).toHaveBeenCalledWith('req-1', 'client-1');
    expect(v.getByLabelText('Save quote draft')).toBeTruthy();
    expect(v.getByLabelText('Quote amount').props.value).toBe('125.00');
  });
});

// =====================================================================================
describe('S1-R1 AdminQuoteEditor: initial authoritative hydration', () => {
  it('shows a loading state with no inputs, Save or Send until hydration succeeds', async () => {
    let release: (v: any) => void = () => {};
    queue({ pending: res => { release = res; } });
    const v = await mount(listItem, { skipWait: true });
    expect(v.getByTestId('admin-quote-loading')).toBeTruthy();
    expect(v.getByText('Loading the latest quote…')).toBeTruthy();
    expect(v.queryByLabelText('Quote amount')).toBeNull();
    expect(v.queryByLabelText('Save quote draft')).toBeNull();
    expect(v.queryByLabelText('Send quote to client')).toBeNull();
    release(draft());
    await waitFor(() => expect(v.getByLabelText('Save quote draft')).toBeTruthy());
    expect(mockUpdate).not.toHaveBeenCalled();
    expect(mockSend).not.toHaveBeenCalled();
  });

  it('an incomplete list payload is replaced by the authoritative quote (form shows server values)', async () => {
    const v = await mount(listItem, { authoritative: draft({ quote_amount_cents: 5000, quote_notes_client: 'server note' }) });
    expect(v.getByText('Status: Draft (not sent)')).toBeTruthy();
    expect(v.getByLabelText('Quote amount').props.value).toBe('50.00');
    expect(v.getByLabelText('Client-facing quote notes').props.value).toBe('server note');
  });

  it('incomplete list payload: the FIRST save succeeds with no false stale refusal', async () => {
    const authoritative = draft({ quote_amount_cents: 5000, quote_notes_internal: 'internal only on full read' });
    const v = await mount(listItem, { authoritative });
    queue(ok(authoritative), ok(draft({ quote_amount_cents: 9900, quote_notes_internal: 'internal only on full read' })));
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '99');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    await waitFor(() => expect(v.getByText('Quote saved.')).toBeTruthy());
    expect(v.queryByText(/changed since it was loaded/)).toBeNull();
    expect(mockUpdate).toHaveBeenCalledTimes(1);
    expect(mockUpdate.mock.calls[0][1]).toMatchObject({ quote_amount_cents: 9900, quote_notes_internal: 'internal only on full read' });
  });

  it('incomplete list payload with no quote yet: first create succeeds', async () => {
    const v = await mount(listItem, { authoritative: base });
    expect(v.getByText('Status: No quote yet')).toBeTruthy();
    queue(ok(base), ok(draft({ quote_amount_cents: 12550 })));
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '125.50');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    await waitFor(() => expect(v.getByText('Quote saved.')).toBeTruthy());
    expect(mockUpdate).toHaveBeenCalledWith('req-1', expect.objectContaining({ quote_amount_cents: 12550 }));
    expect(v.getByText('Status: Draft (not sent)')).toBeTruthy();
  });

  it('a list payload that looks editable but is SENT on the server renders display-only', async () => {
    const v = await mount(draft(), { authoritative: draft({ quote_status: 'SENT' }) });
    expect(v.getByTestId('admin-quote-readonly')).toBeTruthy();
    expect(v.queryByLabelText('Save quote draft')).toBeNull();
  });

  it('pushes the hydrated quote to the screen (status mirror) via onRequestRefreshed', async () => {
    const v = await mount(listItem, { authoritative: draft({ quote_status: 'SENT', status: 'QUOTE_SENT' }) });
    expect(v.getByText('Status: Sent to client')).toBeTruthy();
  });

  it('hydration failure: truthful error, no editing, and an explicit read-only Retry', async () => {
    queue(fail(new Error('Network request failed')));
    const v = await mount(listItem, { skipWait: true });
    expect(await v.findByText("We couldn't load the latest quote, so editing is unavailable. Nothing has been changed.")).toBeTruthy();
    expect(v.getByTestId('admin-quote-load-failed')).toBeTruthy();
    expect(v.queryByLabelText('Quote amount')).toBeNull();
    expect(v.queryByLabelText('Save quote draft')).toBeNull();
    expect(v.queryByLabelText('Send quote to client')).toBeNull();
    expect(mockRead).toHaveBeenCalledTimes(1); // no automatic re-read
    queue(ok(draft()));
    await fireEvent.press(v.getByLabelText('Retry loading quote'));
    await waitFor(() => expect(v.getByLabelText('Save quote draft')).toBeTruthy());
    expect(mockRead).toHaveBeenCalledTimes(2);
    expect(mockUpdate).not.toHaveBeenCalled();
    expect(mockSend).not.toHaveBeenCalled();
  });

  it('retry that fails again stays failed and still offers Retry', async () => {
    queue(fail(apiErr(500)), fail(apiErr(500)));
    const v = await mount(listItem, { skipWait: true });
    await v.findByTestId('admin-quote-load-failed');
    await fireEvent.press(v.getByLabelText('Retry loading quote'));
    await waitFor(() => expect(mockRead).toHaveBeenCalledTimes(2));
    expect(await v.findByTestId('admin-quote-load-failed')).toBeTruthy();
    expect(v.getByLabelText('Retry loading quote')).toBeTruthy();
  });

  it.each([
    [403, "You don't have permission to view this quote."],
    [404, 'This request could not be found.'],
  ])('hydration HTTP %p is reported truthfully', async (status, text) => {
    queue(fail(apiErr(status as number)));
    const v = await mount(listItem, { skipWait: true });
    expect(await v.findByText(text as string)).toBeTruthy();
    expect(v.queryByLabelText('Save quote draft')).toBeNull();
  });

  it('hydration 401 triggers the session-expired path', async () => {
    queue(fail(apiErr(401, 'Your session expired. Please sign in again.')));
    const onExpired = jest.fn();
    const v = await mount(listItem, { skipWait: true, onSessionExpired: onExpired });
    await waitFor(() => expect(onExpired).toHaveBeenCalledTimes(1));
    expect(v.queryByLabelText('Save quote draft')).toBeNull();
  });

  it('hydration that returns a different request is refused', async () => {
    queue(ok({ ...draft(), request_id: 'someone-else' }));
    const v = await mount(listItem, { skipWait: true });
    expect(await v.findByTestId('admin-quote-load-failed')).toBeTruthy();
  });
});

// =====================================================================================
describe('S1-R1 AdminQuoteEditor: unsaved edits are preserved on refresh', () => {
  it('a background refresh with an unchanged quote keeps the user edits', async () => {
    const v = await mount(draft());
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '130');
    await screenRefresh((p: any) => ({ ...p, ...draft(), status: 'QUOTE_NEEDED', visit_notes: 'x' })); // screen "Refresh booking"
    await waitFor(() => expect(v.getByLabelText('Quote amount').props.value).toBe('130'));
    expect(v.queryByTestId('admin-quote-conflict')).toBeNull();
  });

  it('a background refresh with a CHANGED quote keeps edits and asks to keep or discard', async () => {
    const v = await mount(draft());
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '130');
    await screenRefresh((p: any) => ({ ...p, ...draft({ quote_amount_cents: 20000 }) }));
    expect(await v.findByTestId('admin-quote-conflict')).toBeTruthy();
    expect(v.getByLabelText('Quote amount').props.value).toBe('130'); // not silently overwritten
    expect(v.getByText(/Your unsaved changes were kept/)).toBeTruthy();
    expect(v.getByLabelText('Save quote draft').props.accessibilityState).toEqual(expect.objectContaining({ disabled: true }));
  });

  it('with no unsaved edits, a background refresh simply follows the server', async () => {
    const v = await mount(draft());
    await screenRefresh((p: any) => ({ ...p, ...draft({ quote_amount_cents: 20000 }) }));
    await waitFor(() => expect(v.getByLabelText('Quote amount').props.value).toBe('200.00'));
    expect(v.queryByTestId('admin-quote-conflict')).toBeNull();
  });

  it('an incomplete background payload (no quote state) never wipes the hydrated quote', async () => {
    const v = await mount(listItem, { authoritative: draft({ quote_amount_cents: 7700 }) });
    await screenRefresh(() => ({ ...listItem, status: 'ASSIGNED' })); // e.g. list-shaped object without quote fields
    await waitFor(() => expect(v.getByLabelText('Quote amount').props.value).toBe('77.00'));
    expect(v.getByText('Status: Draft (not sent)')).toBeTruthy();
  });

  it('"Discard my changes" resets to the latest server quote', async () => {
    const v = await mount(draft());
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '130');
    await screenRefresh((p: any) => ({ ...p, ...draft({ quote_amount_cents: 20000 }) }));
    await v.findByTestId('admin-quote-conflict');
    await fireEvent.press(v.getByLabelText('Discard my changes'));
    expect(v.getByLabelText('Quote amount').props.value).toBe('200.00');
    expect(v.queryByTestId('admin-quote-conflict')).toBeNull();
    expect(mockUpdate).not.toHaveBeenCalled();
  });

  it('"Keep my changes" then Save writes the user edits over the latest version (explicit choice)', async () => {
    const v = await mount(draft());
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '130');
    await screenRefresh((p: any) => ({ ...p, ...draft({ quote_amount_cents: 20000 }) }));
    await v.findByTestId('admin-quote-conflict');
    await fireEvent.press(v.getByLabelText('Keep my changes'));
    expect(v.getByText('Your changes are kept. Saving will replace the latest saved quote.')).toBeTruthy();
    queue(ok(draft({ quote_amount_cents: 20000 })), ok(draft({ quote_amount_cents: 13000 })));
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    await waitFor(() => expect(v.getByText('Quote saved.')).toBeTruthy());
    expect(mockUpdate).toHaveBeenCalledTimes(1);
    expect(mockUpdate.mock.calls[0][1]).toMatchObject({ quote_amount_cents: 13000 });
  });

  it('a stale refusal during Save keeps the unsaved edits and raises the explicit choice', async () => {
    const v = await mount(draft());
    queue(ok(draft({ quote_amount_cents: 5000 })));
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '99');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText(/Nothing was changed\. Your unsaved changes were kept/)).toBeTruthy();
    expect(mockUpdate).not.toHaveBeenCalled();
    expect(v.getByLabelText('Quote amount').props.value).toBe('99');
    expect(v.getByTestId('admin-quote-conflict')).toBeTruthy();
  });

  it('Send is blocked while a conflict is unresolved', async () => {
    const v = await mount(draft());
    await fireEvent.changeText(v.getByLabelText('Client-facing quote notes'), 'edited');
    await screenRefresh((p: any) => ({ ...p, ...draft({ quote_amount_cents: 20000 }) }));
    await v.findByTestId('admin-quote-conflict');
    expect(v.getByText('Keep or discard your changes before sending.')).toBeTruthy();
    expect(v.getByLabelText('Send quote to client').props.accessibilityState).toEqual(expect.objectContaining({ disabled: true }));
  });
});

// =====================================================================================
describe('S1 AdminQuoteEditor: create / edit DRAFT', () => {
  it('re-reads, PATCHes integer cents, then refreshes authoritatively', async () => {
    const v = await mount(base);
    queue(ok(base), ok(draft({ quote_amount_cents: 12550, quote_notes_client: 'Thanks!' })));
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '125.50');
    await fireEvent.changeText(v.getByLabelText('Client-facing quote notes'), 'Thanks!');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    await waitFor(() => expect(v.getByText('Quote saved.')).toBeTruthy());
    expect(mockRead).toHaveBeenCalledTimes(3); // hydration + guard + refresh
    expect(mockUpdate).toHaveBeenCalledWith('req-1', {
      quote_amount_cents: 12550,
      currency: 'USD',
      payment_requirement: 'NONE',
      deposit_amount_cents: 0,
      quote_notes_client: 'Thanks!',
      quote_notes_internal: '',
      internal_pricing_notes: '',
    });
    expect(mockUpdate.mock.calls[0][1]).not.toHaveProperty('expected_revision');
    expect(v.getByLabelText('Quote amount').props.value).toBe('125.50');
  });

  it('sends payment requirement DEPOSIT with integer deposit cents', async () => {
    const v = await mount(draft());
    queue(ok(draft()), ok(draft({ payment_requirement: 'DEPOSIT', deposit_amount_cents: 3000 })));
    await fireEvent.press(v.getByLabelText('Payment requirement Deposit'));
    await fireEvent.changeText(v.getByLabelText('Deposit amount'), '30');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    await waitFor(() => expect(mockUpdate).toHaveBeenCalledTimes(1));
    expect(mockUpdate.mock.calls[0][1]).toMatchObject({ payment_requirement: 'DEPOSIT', deposit_amount_cents: 3000, quote_amount_cents: 12500 });
    await waitFor(() => expect(v.getByText('Quote saved.')).toBeTruthy());
  });

  it('clears a stale deposit when the requirement is not DEPOSIT', async () => {
    const withDeposit = draft({ payment_requirement: 'DEPOSIT', deposit_amount_cents: 3000 });
    const v = await mount(withDeposit);
    queue(ok(withDeposit), ok(draft({ payment_requirement: 'FULL' })));
    await fireEvent.press(v.getByLabelText('Payment requirement Full payment'));
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    await waitFor(() => expect(mockUpdate).toHaveBeenCalledTimes(1));
    expect(mockUpdate.mock.calls[0][1]).toMatchObject({ payment_requirement: 'FULL', deposit_amount_cents: 0 });
    await waitFor(() => expect(v.getByText('Quote saved.')).toBeTruthy());
  });

  it.each(['abc', '-5', '1.234', ''])('rejects invalid first-create amount %p locally with no API call', async amount => {
    const v = await mount(base);
    await fireEvent.changeText(v.getByLabelText('Quote amount'), amount);
    await fireEvent.changeText(v.getByLabelText('Internal quote notes'), 'x'); // make it dirty
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText(/Quote amount:/)).toBeTruthy();
    expect(mockRead).toHaveBeenCalledTimes(1); // hydration only
    expect(mockUpdate).not.toHaveBeenCalled();
  });

  it('rejects a deposit above the total, a zero deposit, and a bad currency locally', async () => {
    const v = await mount(draft());
    await fireEvent.press(v.getByLabelText('Payment requirement Deposit'));
    await fireEvent.changeText(v.getByLabelText('Deposit amount'), '200');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText('Deposit amount cannot exceed the quote total.')).toBeTruthy();
    await fireEvent.changeText(v.getByLabelText('Deposit amount'), '0');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText('Deposit amount must be greater than 0 when a deposit is required.')).toBeTruthy();
    await fireEvent.press(v.getByLabelText('Payment requirement None'));
    await fireEvent.changeText(v.getByLabelText('Quote currency'), 'US');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText('Currency must be a 3-letter code such as USD.')).toBeTruthy();
    expect(mockUpdate).not.toHaveBeenCalled();
    expect(mockRead).toHaveBeenCalledTimes(1);
  });

  it('does not call the API when nothing changed (Save disabled)', async () => {
    const v = await mount(draft());
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(mockRead).toHaveBeenCalledTimes(1);
    expect(mockUpdate).not.toHaveBeenCalled();
  });
});

// =====================================================================================
describe('S1 AdminQuoteEditor: stale / concurrency (client-side checks only)', () => {
  it('edits that already equal a changed server quote converge without a conflict; nothing is written', async () => {
    const v = await mount(draft());
    queue(ok(draft({ quote_amount_cents: 5000 })));
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '50');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText(/changed since it was loaded.*latest version is now shown/)).toBeTruthy();
    expect(mockUpdate).not.toHaveBeenCalled();
    expect(v.queryByTestId('admin-quote-conflict')).toBeNull();
    expect(v.getByLabelText('Quote amount').props.value).toBe('50.00');
  });

  it('refuses to save when the server quote has already been SENT elsewhere', async () => {
    const v = await mount(draft());
    queue(ok(draft({ quote_status: 'SENT' })));
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '99');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText(/changed since it was loaded/)).toBeTruthy();
    expect(mockUpdate).not.toHaveBeenCalled();
    expect(v.queryByLabelText('Save quote draft')).toBeNull(); // now display-only
  });

  it('does nothing when the pre-save verification read fails', async () => {
    const v = await mount(draft());
    queue(fail(new Error('offline')));
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '99');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText(/Couldn't verify the latest quote, so nothing was changed/)).toBeTruthy();
    expect(mockUpdate).not.toHaveBeenCalled();
    expect(v.getByLabelText('Quote amount').props.value).toBe('99');
  });

  it('refuses when the re-read belongs to a different request', async () => {
    const v = await mount(draft());
    queue(ok({ ...draft(), request_id: 'someone-else' }));
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '99');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText(/Couldn't verify the latest quote/)).toBeTruthy();
    expect(mockUpdate).not.toHaveBeenCalled();
  });
});

// =====================================================================================
describe('S1 AdminQuoteEditor: save errors (ApiError.status), no automatic retry', () => {
  const dirtyAndSave = async (v: any) => {
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '99');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
  };

  it('400 shows the server message', async () => {
    const v = await mount(draft());
    queue(ok(draft()));
    mockUpdate.mockRejectedValueOnce(apiErr(400, 'Quote update rejected: deposit exceeds total'));
    await dirtyAndSave(v);
    expect(await v.findByText('Quote update rejected: deposit exceeds total')).toBeTruthy();
    expect(mockUpdate).toHaveBeenCalledTimes(1);
  });

  it('403 reports a permission problem', async () => {
    const v = await mount(draft());
    queue(ok(draft()));
    mockUpdate.mockRejectedValueOnce(apiErr(403, 'Forbidden'));
    await dirtyAndSave(v);
    expect(await v.findByText("You don't have permission to edit this quote.")).toBeTruthy();
  });

  it('404 reports the request could not be found', async () => {
    const v = await mount(draft());
    queue(ok(draft()));
    mockUpdate.mockRejectedValueOnce(apiErr(404, 'nope'));
    await dirtyAndSave(v);
    expect(await v.findByText('This request could not be found.')).toBeTruthy();
  });

  it('401 triggers the session-expired callback', async () => {
    const onExpired = jest.fn();
    const v = await mount(draft(), { onSessionExpired: onExpired });
    queue(ok(draft()));
    mockUpdate.mockRejectedValueOnce(apiErr(401, 'Your session expired. Please sign in again.'));
    await dirtyAndSave(v);
    await waitFor(() => expect(onExpired).toHaveBeenCalledTimes(1));
  });

  it.each([
    ['network failure (no status)', new Error('Network request failed')],
    ['HTTP 500', apiErr(500, 'Database update failed')],
    ['unexpected HTTP 418', apiErr(418, 'teapot')],
  ])('%s: outcome unknown, reloads read-only, never re-sends the PATCH, keeps edits', async (_label, err) => {
    const v = await mount(draft());
    queue(ok(draft()), ok(draft()));
    mockUpdate.mockRejectedValueOnce(err);
    await dirtyAndSave(v);
    expect(await v.findByText(/We couldn't confirm that the quote was saved/)).toBeTruthy();
    expect(v.getByText(/The latest quote has been reloaded; check it before trying again\./)).toBeTruthy();
    expect(mockUpdate).toHaveBeenCalledTimes(1);
    expect(mockRead).toHaveBeenCalledTimes(3); // hydration + guard + safe reload
    expect(v.getByLabelText('Quote amount').props.value).toBe('99'); // unsaved input not discarded
  });

  it('unknown outcome where the write actually landed converges with no conflict', async () => {
    const v = await mount(draft());
    queue(ok(draft()), ok(draft({ quote_amount_cents: 9900 })));
    mockUpdate.mockRejectedValueOnce(new Error('Network request failed'));
    await dirtyAndSave(v);
    expect(await v.findByText(/We couldn't confirm that the quote was saved/)).toBeTruthy();
    expect(v.queryByTestId('admin-quote-conflict')).toBeNull();
    expect(v.getByLabelText('Quote amount').props.value).toBe('99.00');
    expect(v.getByLabelText('Save quote draft').props.accessibilityState).toEqual(expect.objectContaining({ disabled: true })); // not dirty
    expect(mockUpdate).toHaveBeenCalledTimes(1);
  });

  it('uncertain outcome with a failing reload tells the user to refresh manually', async () => {
    const v = await mount(draft());
    queue(ok(draft()), fail(new Error('offline')));
    mockUpdate.mockRejectedValueOnce(new Error('Network request failed'));
    await dirtyAndSave(v);
    expect(await v.findByText(/Use Refresh booking to check its current state/)).toBeTruthy();
    expect(mockUpdate).toHaveBeenCalledTimes(1);
  });

  it('reports a successful save accurately when only the follow-up refresh fails', async () => {
    const v = await mount(draft());
    queue(ok(draft()), fail(new Error('offline')));
    await dirtyAndSave(v);
    expect(await v.findByText(/Quote saved\. However, the latest quote state could not be refreshed/)).toBeTruthy();
    expect(v.queryByText(/couldn't save|could not be saved|nothing was changed/i)).toBeNull();
    expect(mockUpdate).toHaveBeenCalledTimes(1);
  });
});

// =====================================================================================
describe('S1 AdminQuoteEditor: sending', () => {
  it('requires confirmation, re-reads, sends once, then shows the SENT state', async () => {
    const v = await mount(draft());
    queue(ok(draft()), ok(draft({ quote_status: 'SENT', status: 'QUOTE_SENT', quote_sent_at: '2026-11-10T10:00:00Z' })));
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    expect(mockSend).not.toHaveBeenCalled();
    expect(v.getByText(/Sending does not approve or schedule the booking/)).toBeTruthy();
    await fireEvent.press(v.getByText('Confirm Send quote to client?'));
    await waitFor(() => expect(v.getByText('Quote sent to the client.')).toBeTruthy());
    expect(mockSend).toHaveBeenCalledTimes(1);
    expect(mockSend).toHaveBeenCalledWith('req-1');
    expect(mockUpdate).not.toHaveBeenCalled();
    expect(v.getByText('Status: Sent to client')).toBeTruthy();
    expect(v.queryByLabelText('Send quote to client')).toBeNull(); // no Resend
    expect(v.queryByLabelText('Save quote draft')).toBeNull();
  });

  it('first send from an incomplete list payload succeeds without a false stale refusal', async () => {
    const authoritative = draft({ quote_notes_internal: 'only on the full read' });
    const v = await mount(listItem, { authoritative });
    queue(ok(authoritative), ok({ ...authoritative, quote_status: 'SENT' }));
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    await fireEvent.press(v.getByText('Confirm Send quote to client?'));
    await waitFor(() => expect(v.getByText('Quote sent to the client.')).toBeTruthy());
    expect(v.queryByText(/changed since it was loaded/)).toBeNull();
    expect(mockSend).toHaveBeenCalledTimes(1);
  });

  it('cancelling the confirmation sends nothing', async () => {
    const v = await mount(draft());
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    await fireEvent.press(v.getByText('Cancel Send quote to client?'));
    expect(mockSend).not.toHaveBeenCalled();
    expect(mockRead).toHaveBeenCalledTimes(1);
  });

  it('blocks sending unsaved changes', async () => {
    const v = await mount(draft());
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '130');
    expect(v.getByText('Save your changes before sending.')).toBeTruthy();
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    expect(v.queryByText('Confirm Send quote to client?')).toBeNull();
    expect(mockSend).not.toHaveBeenCalled();
  });

  it('blocks sending a draft whose persisted amount is not positive', async () => {
    const v = await mount(draft({ quote_amount_cents: 0 }));
    expect(v.getByText('Set a quote amount greater than 0 and save before sending.')).toBeTruthy();
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    expect(v.queryByText('Confirm Send quote to client?')).toBeNull();
    expect(mockSend).not.toHaveBeenCalled();
  });

  it('does not offer Send before a draft exists', async () => {
    const v = await mount(base);
    expect(v.queryByLabelText('Send quote to client')).toBeNull();
  });

  it('refuses to send when the server quote changed since it was loaded', async () => {
    const v = await mount(draft());
    queue(ok(draft({ quote_amount_cents: 99999 })));
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    await fireEvent.press(v.getByText('Confirm Send quote to client?'));
    expect(await v.findByText(/changed since it was loaded/)).toBeTruthy();
    expect(mockSend).not.toHaveBeenCalled();
    expect(v.getByLabelText('Quote amount').props.value).toBe('999.99'); // no edits -> follows server
  });

  it('409 from the server: reloads, explains, and does not retry', async () => {
    const v = await mount(draft());
    queue(ok(draft()), ok(draft()));
    mockSend.mockRejectedValueOnce(apiErr(409, 'Conflict: the quote changed since it was loaded; reload and retry'));
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    await fireEvent.press(v.getByText('Confirm Send quote to client?'));
    expect(await v.findByText(/This quote changed before it could be sent/)).toBeTruthy();
    expect(mockSend).toHaveBeenCalledTimes(1);
  });

  it.each([
    [400, 'Quote send rejected: cannot send a quote with no amount', 'Quote send rejected: cannot send a quote with no amount'],
    [403, 'Forbidden', "You don't have permission to send this quote."],
    [404, 'gone', 'This request could not be found.'],
  ])('send HTTP %p is mapped', async (status, message, expected) => {
    const v = await mount(draft());
    queue(ok(draft()));
    mockSend.mockRejectedValueOnce(apiErr(status as number, message as string));
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    await fireEvent.press(v.getByText('Confirm Send quote to client?'));
    expect(await v.findByText(expected as string)).toBeTruthy();
    expect(mockSend).toHaveBeenCalledTimes(1);
  });

  it('network failure on send: outcome unknown, reload only, no second POST', async () => {
    const v = await mount(draft());
    queue(ok(draft()), ok(draft()));
    mockSend.mockRejectedValueOnce(new Error('Network request failed'));
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    await fireEvent.press(v.getByText('Confirm Send quote to client?'));
    expect(await v.findByText(/We couldn't confirm that the quote was sent/)).toBeTruthy();
    expect(mockSend).toHaveBeenCalledTimes(1);
  });

  it('reports a successful send accurately when only the follow-up refresh fails', async () => {
    const v = await mount(draft());
    queue(ok(draft()), fail(new Error('offline')));
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    await fireEvent.press(v.getByText('Confirm Send quote to client?'));
    expect(await v.findByText(/Quote sent to the client\. However, the latest quote state could not be refreshed/)).toBeTruthy();
    expect(v.queryByText(/couldn't send|could not be sent/i)).toBeNull();
  });
});

// =====================================================================================
describe('S1 AdminQuoteEditor: display-only states', () => {
  it.each(['SENT', 'ACCEPTED', 'DECLINED', 'NOT_REQUIRED', 'SUPERSEDED', 'SOMETHING_NEW'])(
    '%s is display-only: no inputs, Save, Send or Resend',
    async quoteStatus => {
      const v = await mount(draft({ quote_status: quoteStatus, quote_notes_internal: 'secret-internal' }));
      expect(v.getByTestId('admin-quote-readonly')).toBeTruthy();
      expect(v.queryByLabelText('Quote amount')).toBeNull();
      expect(v.queryByLabelText('Save quote draft')).toBeNull();
      expect(v.queryByLabelText('Send quote to client')).toBeNull();
      expect(v.queryByText(/Resend/i)).toBeNull();
      expect(mockUpdate).not.toHaveBeenCalled();
      expect(mockSend).not.toHaveBeenCalled();
    }
  );

  it('shows the amount, requirement and deposit read-only for an accepted quote', async () => {
    const v = await mount(draft({ quote_status: 'ACCEPTED', payment_requirement: 'DEPOSIT', deposit_amount_cents: 3000, quote_accepted_at: '2026-11-10T10:00:00Z' }));
    expect(v.getByText('Status: Accepted by client')).toBeTruthy();
    expect(v.getByText('Total: USD 125.00')).toBeTruthy();
    expect(v.getByText('Deposit: USD 30.00')).toBeTruthy();
  });

  it('shows unknown statuses neutrally instead of crashing', async () => {
    const v = await mount(draft({ quote_status: 'SOMETHING_NEW' }));
    expect(v.getByText('Status: Status unavailable (SOMETHING_NEW)')).toBeTruthy();
  });
});

// =====================================================================================
describe('S1 mergeQuoteRefresh / quoteFingerprint', () => {
  it('copies only quote fields and status, preserving visit/occurrence state', () => {
    const previous = { request_id: 'r', status: 'ASSIGNED', job_completion_summary: { jobs: [{ job_id: 'a', started_at: 'x' }] }, visit_notes: 'keep', quote_status: 'DRAFT', quote_notes_client: 'old' };
    const fresh = { request_id: 'r', status: 'QUOTE_SENT', quote_status: 'SENT', quote_revision: 2, job_completion_summary: { jobs: [] }, visit_notes: 'DIFFERENT' };
    const merged = mergeQuoteRefresh(previous, fresh);
    expect(merged.quote_status).toBe('SENT');
    expect(merged.quote_revision).toBe(2);
    expect(merged.status).toBe('QUOTE_SENT');
    expect(merged.job_completion_summary).toBe(previous.job_completion_summary);
    expect(merged.visit_notes).toBe('keep');
    expect(merged.quote_notes_client).toBeUndefined();
  });

  it('fingerprints are equal for null/absent/empty-equivalent values and differ on real changes', () => {
    expect(quoteFingerprint({})).toBe(quoteFingerprint({ quote_notes_client: null, quote_status: undefined }));
    expect(quoteFingerprint(draft())).not.toBe(quoteFingerprint(draft({ quote_amount_cents: 12501 })));
    expect(quoteFingerprint(draft())).not.toBe(quoteFingerprint(draft({ quote_revision: 2 })));
    expect(quoteFingerprint(draft({ quote_amount_cents: '12500' }))).toBe(quoteFingerprint(draft()));
  });
});

// =====================================================================================
describe('S1 AdminQuoteEditor: in-flight lock', () => {
  it('disables Save/Send and inputs while a save is in flight, and PATCHes exactly once', async () => {
    const v = await mount(draft());
    let release: (val: any) => void = () => {};
    queue({ pending: res => { release = res; } }, ok(draft({ quote_notes_client: 'a' })));
    await fireEvent.changeText(v.getByLabelText('Client-facing quote notes'), 'a');
    const pending = fireEvent.press(v.getByLabelText('Save quote draft')); // held open by the pending guard read
    await waitFor(() => expect(mockRead).toHaveBeenCalledTimes(2));
    expect(v.getByLabelText('Save quote draft').props.accessibilityState).toEqual(expect.objectContaining({ disabled: true }));
    expect(v.getByLabelText('Send quote to client').props.accessibilityState).toEqual(expect.objectContaining({ disabled: true }));
    expect(v.getByLabelText('Quote amount').props.editable).toBe(false);
    release(draft());
    await pending;
    await waitFor(() => expect(v.getByText('Quote saved.')).toBeTruthy());
    expect(mockUpdate).toHaveBeenCalledTimes(1);
    expect(mockRead).toHaveBeenCalledTimes(3); // hydration + guard + post-save refresh
  });
});
