import React from 'react';
import { fireEvent, render, waitFor } from '@testing-library/react-native';

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

const apiErr = (status: number, message = `HTTP ${status}`) => Object.assign(new Error(message), { status });

const base = { request_id: 'req-1', client_id: 'client-1', status: 'PENDING_REVIEW' };
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

const Harness = ({ initial, role, onSessionExpired }: any) => {
  const [req, setReq] = React.useState(initial);
  return (
    <AdminQuoteEditor
      request={req}
      role={role}
      onRequestRefreshed={(fresh: any) => setReq((p: any) => mergeQuoteRefresh(p, fresh))}
      onSessionExpired={onSessionExpired}
    />
  );
};

// Role is passed explicitly when given (including undefined/null); defaults to owner only when omitted.
function mount(initial: any, ...rest: any[]) {
  const role = rest.length >= 1 ? rest[0] : 'owner';
  const onSessionExpired = rest[1];
  return render(<Harness initial={initial} role={role} onSessionExpired={onSessionExpired} />);
}

beforeEach(() => {
  mockRead.mockReset();
  mockUpdate.mockReset().mockResolvedValue({ message: 'Quote updated' });
  mockSend.mockReset().mockResolvedValue({ message: 'Quote sent' });
});

describe('S1 AdminQuoteEditor: RBAC', () => {
  it.each(['staff', 'client', 'unknown', null, undefined, '', 'Owner'])('renders nothing for role %p', async role => {
    const v = await mount(draft(), role as any);
    expect(v.queryByText('Quote')).toBeNull();
    expect(v.queryByLabelText('Quote amount')).toBeNull();
    expect(v.queryByLabelText('Save quote draft')).toBeNull();
    expect(mockRead).not.toHaveBeenCalled();
  });

  it.each(['owner', 'admin'])('renders the editor for %s', async role => {
    const v = await mount(draft(), role);
    expect(v.getByLabelText('Save quote draft')).toBeTruthy();
    expect(v.getByLabelText('Quote amount').props.value).toBe('125.00');
  });
});

describe('S1 AdminQuoteEditor: create / edit DRAFT', () => {
  it('creates the first draft: re-reads, PATCHes integer cents, then refreshes authoritatively', async () => {
    mockRead.mockResolvedValueOnce(base).mockResolvedValueOnce(draft({ quote_amount_cents: 12550 }));
    const v = await mount(base);
    expect(v.getByText('Status: No quote yet')).toBeTruthy();
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '125.50');
    await fireEvent.changeText(v.getByLabelText('Client-facing quote notes'), 'Thanks!');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    await waitFor(() => expect(v.getByText('Quote saved.')).toBeTruthy());
    expect(mockRead).toHaveBeenCalledTimes(2);
    expect(mockRead).toHaveBeenCalledWith('req-1', 'client-1');
    expect(mockUpdate).toHaveBeenCalledTimes(1);
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
    expect(v.getByText('Status: Draft (not sent)')).toBeTruthy();
    expect(v.getByLabelText('Quote amount').props.value).toBe('125.50');
  });

  it('sends payment requirement DEPOSIT with integer deposit cents', async () => {
    mockRead.mockResolvedValue(draft());
    const v = await mount(draft());
    await fireEvent.press(v.getByLabelText('Payment requirement Deposit'));
    await fireEvent.changeText(v.getByLabelText('Deposit amount'), '30');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    await waitFor(() => expect(mockUpdate).toHaveBeenCalledTimes(1));
    expect(mockUpdate.mock.calls[0][1]).toMatchObject({ payment_requirement: 'DEPOSIT', deposit_amount_cents: 3000, quote_amount_cents: 12500 });
  });

  it('clears a stale deposit when the requirement is not DEPOSIT', async () => {
    mockRead.mockResolvedValue(draft({ payment_requirement: 'DEPOSIT', deposit_amount_cents: 3000 }));
    const v = await mount(draft({ payment_requirement: 'DEPOSIT', deposit_amount_cents: 3000 }));
    await fireEvent.press(v.getByLabelText('Payment requirement Full payment'));
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    await waitFor(() => expect(mockUpdate).toHaveBeenCalledTimes(1));
    expect(mockUpdate.mock.calls[0][1]).toMatchObject({ payment_requirement: 'FULL', deposit_amount_cents: 0 });
  });

  it.each([
    ['abc', 'Quote amount:'],
    ['-5', 'Quote amount:'],
    ['1.234', 'Quote amount:'],
    ['', 'Quote amount:'],
  ])('rejects invalid first-create amount %p locally with no API call', async (amount, expected) => {
    const v = await mount(base);
    await fireEvent.changeText(v.getByLabelText('Quote amount'), amount);
    await fireEvent.changeText(v.getByLabelText('Internal quote notes'), 'x'); // make it dirty
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText(new RegExp(expected))).toBeTruthy();
    expect(mockRead).not.toHaveBeenCalled();
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
    expect(mockRead).not.toHaveBeenCalled();
  });

  it('does not call the API when nothing changed (Save disabled)', async () => {
    const v = await mount(draft());
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(mockRead).not.toHaveBeenCalled();
    expect(mockUpdate).not.toHaveBeenCalled();
  });

});

describe('S1 AdminQuoteEditor: stale / concurrency (client-side checks only)', () => {
  it('refuses to save when the server quote differs from what is displayed, and loads the latest', async () => {
    mockRead.mockResolvedValueOnce(draft({ quote_amount_cents: 5000 }));
    const v = await mount(base);
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '99');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText(/changed since it was loaded/)).toBeTruthy();
    expect(mockUpdate).not.toHaveBeenCalled();
    expect(v.getByText('Status: Draft (not sent)')).toBeTruthy();
    expect(v.getByLabelText('Quote amount').props.value).toBe('50.00');
  });

  it('refuses to save when the server quote has already been SENT elsewhere', async () => {
    mockRead.mockResolvedValueOnce(draft({ quote_status: 'SENT' }));
    const v = await mount(draft());
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '99');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText(/changed since it was loaded/)).toBeTruthy();
    expect(mockUpdate).not.toHaveBeenCalled();
    expect(v.queryByLabelText('Save quote draft')).toBeNull(); // now display-only
  });

  it('does nothing when the pre-save verification read fails', async () => {
    mockRead.mockRejectedValueOnce(new Error('offline'));
    const v = await mount(draft());
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '99');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText(/Couldn't verify the latest quote, so nothing was changed/)).toBeTruthy();
    expect(mockUpdate).not.toHaveBeenCalled();
  });

  it('refuses when the re-read belongs to a different request', async () => {
    mockRead.mockResolvedValueOnce({ ...draft(), request_id: 'someone-else' });
    const v = await mount(draft());
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '99');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
    expect(await v.findByText(/Couldn't verify the latest quote/)).toBeTruthy();
    expect(mockUpdate).not.toHaveBeenCalled();
  });
});

describe('S1 AdminQuoteEditor: save errors (ApiError.status), no automatic retry', () => {
  const dirtyAndSave = async (v: any) => {
    await fireEvent.changeText(v.getByLabelText('Quote amount'), '99');
    await fireEvent.press(v.getByLabelText('Save quote draft'));
  };

  it('400 shows the server message', async () => {
    mockRead.mockResolvedValue(draft());
    mockUpdate.mockRejectedValueOnce(apiErr(400, 'Quote update rejected: deposit exceeds total'));
    const v = await mount(draft());
    await dirtyAndSave(v);
    expect(await v.findByText('Quote update rejected: deposit exceeds total')).toBeTruthy();
    expect(mockUpdate).toHaveBeenCalledTimes(1);
  });

  it('403 reports a permission problem', async () => {
    mockRead.mockResolvedValue(draft());
    mockUpdate.mockRejectedValueOnce(apiErr(403, 'Forbidden'));
    const v = await mount(draft());
    await dirtyAndSave(v);
    expect(await v.findByText("You don't have permission to edit this quote.")).toBeTruthy();
  });

  it('404 reports the request could not be found', async () => {
    mockRead.mockResolvedValue(draft());
    mockUpdate.mockRejectedValueOnce(apiErr(404, 'nope'));
    const v = await mount(draft());
    await dirtyAndSave(v);
    expect(await v.findByText('This request could not be found.')).toBeTruthy();
  });

  it('401 triggers the session-expired callback', async () => {
    mockRead.mockResolvedValue(draft());
    mockUpdate.mockRejectedValueOnce(apiErr(401, 'Your session expired. Please sign in again.'));
    const onExpired = jest.fn();
    const v = await mount(draft(), 'owner', onExpired);
    await dirtyAndSave(v);
    await waitFor(() => expect(onExpired).toHaveBeenCalledTimes(1));
  });

  it.each([
    ['network failure (no status)', new Error('Network request failed')],
    ['HTTP 500', apiErr(500, 'Database update failed')],
    ['unexpected HTTP 418', apiErr(418, 'teapot')],
  ])('%s: outcome unknown, reloads read-only, never re-sends the PATCH', async (_label, err) => {
    mockRead.mockResolvedValue(draft());
    mockUpdate.mockRejectedValueOnce(err);
    const v = await mount(draft());
    await dirtyAndSave(v);
    expect(await v.findByText(/We couldn't confirm that the quote was saved/)).toBeTruthy();
    expect(v.getByText(/The latest quote has been reloaded; check it before trying again\./)).toBeTruthy();
    expect(mockUpdate).toHaveBeenCalledTimes(1);
    expect(mockRead).toHaveBeenCalledTimes(2); // guard + safe reload
  });

  it('uncertain outcome with a failing reload tells the user to refresh manually', async () => {
    mockRead.mockResolvedValueOnce(draft()).mockRejectedValueOnce(new Error('offline'));
    mockUpdate.mockRejectedValueOnce(new Error('Network request failed'));
    const v = await mount(draft());
    await dirtyAndSave(v);
    expect(await v.findByText(/Use Refresh booking to check its current state/)).toBeTruthy();
    expect(mockUpdate).toHaveBeenCalledTimes(1);
  });

  it('reports a successful save accurately when only the follow-up refresh fails', async () => {
    mockRead.mockResolvedValueOnce(draft()).mockRejectedValueOnce(new Error('offline'));
    const v = await mount(draft());
    await dirtyAndSave(v);
    expect(await v.findByText(/Quote saved\. However, the latest quote state could not be refreshed/)).toBeTruthy();
    expect(v.queryByText(/couldn't save|could not be saved|nothing was changed/i)).toBeNull();
    expect(mockUpdate).toHaveBeenCalledTimes(1);
  });
});

describe('S1 AdminQuoteEditor: sending', () => {
  it('requires confirmation, re-reads, sends once without a body arg, then shows the SENT state', async () => {
    mockRead.mockResolvedValueOnce(draft()).mockResolvedValueOnce(draft({ quote_status: 'SENT', status: 'QUOTE_SENT', quote_sent_at: '2026-11-10T10:00:00Z' }));
    const v = await mount(draft());
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

  it('cancelling the confirmation sends nothing', async () => {
    const v = await mount(draft());
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    await fireEvent.press(v.getByText('Cancel Send quote to client?'));
    expect(mockSend).not.toHaveBeenCalled();
    expect(mockRead).not.toHaveBeenCalled();
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
    mockRead.mockResolvedValueOnce(draft({ quote_amount_cents: 99999 }));
    const v = await mount(draft());
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    await fireEvent.press(v.getByText('Confirm Send quote to client?'));
    expect(await v.findByText(/changed since it was loaded/)).toBeTruthy();
    expect(mockSend).not.toHaveBeenCalled();
    expect(v.getByLabelText('Quote amount').props.value).toBe('999.99');
  });

  it('409 from the server: reloads, explains, and does not retry', async () => {
    mockRead.mockResolvedValue(draft());
    mockSend.mockRejectedValueOnce(apiErr(409, 'Conflict: the quote changed since it was loaded; reload and retry'));
    const v = await mount(draft());
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
    mockRead.mockResolvedValue(draft());
    mockSend.mockRejectedValueOnce(apiErr(status as number, message as string));
    const v = await mount(draft());
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    await fireEvent.press(v.getByText('Confirm Send quote to client?'));
    expect(await v.findByText(expected as string)).toBeTruthy();
    expect(mockSend).toHaveBeenCalledTimes(1);
  });

  it('network failure on send: outcome unknown, reload only, no second POST', async () => {
    mockRead.mockResolvedValue(draft());
    mockSend.mockRejectedValueOnce(new Error('Network request failed'));
    const v = await mount(draft());
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    await fireEvent.press(v.getByText('Confirm Send quote to client?'));
    expect(await v.findByText(/We couldn't confirm that the quote was sent/)).toBeTruthy();
    expect(mockSend).toHaveBeenCalledTimes(1);
  });

  it('reports a successful send accurately when only the follow-up refresh fails', async () => {
    mockRead.mockResolvedValueOnce(draft()).mockRejectedValueOnce(new Error('offline'));
    const v = await mount(draft());
    await fireEvent.press(v.getByLabelText('Send quote to client'));
    await fireEvent.press(v.getByText('Confirm Send quote to client?'));
    expect(await v.findByText(/Quote sent to the client\. However, the latest quote state could not be refreshed/)).toBeTruthy();
    expect(v.queryByText(/couldn't send|could not be sent/i)).toBeNull();
  });
});

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
    expect(merged.quote_notes_client).toBeUndefined(); // cleared so the record converges to the server
  });

  it('fingerprints are equal for null/absent/empty-equivalent values and differ on real changes', () => {
    expect(quoteFingerprint({})).toBe(quoteFingerprint({ quote_notes_client: null, quote_status: undefined }));
    expect(quoteFingerprint(draft())).not.toBe(quoteFingerprint(draft({ quote_amount_cents: 12501 })));
    expect(quoteFingerprint(draft())).not.toBe(quoteFingerprint(draft({ quote_revision: 2 })));
    expect(quoteFingerprint(draft({ quote_amount_cents: '12500' }))).toBe(quoteFingerprint(draft()));
  });
});

describe('S1 AdminQuoteEditor: in-flight lock', () => {
  it('disables Save/Send and inputs while a save is in flight, and PATCHes exactly once', async () => {
    let release: (v: any) => void = () => {};
    mockRead
      .mockImplementationOnce(() => new Promise(res => { release = res; }))
      .mockResolvedValue(draft({ quote_notes_client: 'a' }));
    const v = await mount(draft());
    await fireEvent.changeText(v.getByLabelText('Client-facing quote notes'), 'a');
    const pending = fireEvent.press(v.getByLabelText('Save quote draft')); // held open by the pending guard read
    await waitFor(() => expect(mockRead).toHaveBeenCalledTimes(1));
    expect(v.getByLabelText('Save quote draft').props.accessibilityState).toEqual(expect.objectContaining({ disabled: true }));
    expect(v.getByLabelText('Send quote to client').props.accessibilityState).toEqual(expect.objectContaining({ disabled: true }));
    expect(v.getByLabelText('Quote amount').props.editable).toBe(false);
    release(draft());
    await pending;
    await waitFor(() => expect(v.getByText('Quote saved.')).toBeTruthy());
    expect(mockUpdate).toHaveBeenCalledTimes(1);
    expect(mockRead).toHaveBeenCalledTimes(2); // one guard read + one post-save refresh
  });
});
