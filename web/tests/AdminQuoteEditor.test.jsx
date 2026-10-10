/**
 * W2B — AdminQuoteEditor focused tests.
 *
 * Verifies the canonical owner/admin quote editor: rendering of canonical state,
 * create/edit payloads via the W2A `updateAdminRequestQuote` client, the
 * deterministic string-based money parser, payment-requirement UX, commercial-vs-
 * internal detection, SENT/ACCEPTED confirmation, DECLINED/NOT_REQUIRED display-only
 * behavior, authoritative-refresh callback, error handling, and the W2C boundary
 * (never calls sendAdminRequestQuote, never touches Stripe/payment or legacy PET).
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mock the API client module. updateAdminRequestQuote is the only call the editor
// should make; sendAdminRequestQuote is mocked so we can assert it is NEVER called.
const updateAdminRequestQuote = vi.fn();
const sendAdminRequestQuote = vi.fn();
const createPaymentSession = vi.fn();
const sendPaymentEmail = vi.fn();

vi.mock('../src/api/client', () => ({
  updateAdminRequestQuote: (...args) => updateAdminRequestQuote(...args),
  sendAdminRequestQuote: (...args) => sendAdminRequestQuote(...args),
  createPaymentSession: (...args) => createPaymentSession(...args),
  sendPaymentEmail: (...args) => sendPaymentEmail(...args),
}));

import AdminQuoteEditor, { parseDollarsToCents, centsToDollars } from '../src/components/AdminQuoteEditor';

const makeRequest = (overrides = {}) => ({
  request_id: 'req-123',
  client_id: 'client-1',
  ...overrides,
});

const renderEditor = (requestOverrides = {}, props = {}) => {
  const onQuoteUpdated = props.onQuoteUpdated || vi.fn().mockResolvedValue(undefined);
  const userRole = props.userRole || 'owner';
  render(
    <AdminQuoteEditor
      request={makeRequest(requestOverrides)}
      userRole={userRole}
      onQuoteUpdated={onQuoteUpdated}
    />
  );
  return { onQuoteUpdated };
};

const typeInto = (labelText, value) => {
  const el = screen.getByLabelText(labelText);
  fireEvent.change(el, { target: { value } });
  return el;
};

beforeEach(() => {
  updateAdminRequestQuote.mockReset().mockResolvedValue({ message: 'Quote updated' });
  sendAdminRequestQuote.mockReset().mockResolvedValue({ message: 'Quote sent', quote_status: 'SENT' });
  createPaymentSession.mockReset();
  sendPaymentEmail.mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Money parser (pure)
// ---------------------------------------------------------------------------
describe('parseDollarsToCents (deterministic string parser)', () => {
  it.each([
    ['150', 15000],
    ['150.00', 15000],
    ['10.01', 1001],
    ['10.10', 1010],
    ['0.10', 10],
    ['0.29', 29],
    ['9999.99', 999999],
    ['0', 0],
    ['  42.5  ', 4250],
  ])('parses %s -> %i cents', (input, expected) => {
    const res = parseDollarsToCents(input);
    expect(res.ok).toBe(true);
    expect(res.cents).toBe(expected);
  });

  it.each(['10.005', '1.2.3', '10.999', '-5', '', '   ', 'abc', '1,000', '$10'])(
    'rejects malformed input %p without silent reinterpretation',
    (input) => {
      const res = parseDollarsToCents(input);
      expect(res.ok).toBe(false);
      expect(res.error).toBeTruthy();
    }
  );

  it('does not use float rounding (10.005 is rejected, not rounded to 1001/1000)', () => {
    expect(parseDollarsToCents('10.005').ok).toBe(false);
  });

  // Safe-integer guard (pre-commit hardening). Shape-valid but out-of-range digit
  // strings must be rejected, never silently submitted as an imprecise integer.
  it('accepts the highest realistic pet-care amounts', () => {
    expect(parseDollarsToCents('9999.99')).toEqual({ ok: true, cents: 999999 });
    expect(parseDollarsToCents('100000.00')).toEqual({ ok: true, cents: 10000000 });
  });

  it('accepts a value whose cents equal exactly Number.MAX_SAFE_INTEGER', () => {
    const res = parseDollarsToCents('90071992547409.91'); // 9007199254740991 = MAX_SAFE
    expect(res.ok).toBe(true);
    expect(res.cents).toBe(Number.MAX_SAFE_INTEGER);
    expect(Number.isSafeInteger(res.cents)).toBe(true);
  });

  it('rejects a very large whole-number string that would exceed safe-integer range', () => {
    const res = parseDollarsToCents('999999999999999'); // *100 is not a safe integer
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/too large/i);
  });

  it('rejects a very large decimal string one cent past the safe-integer boundary', () => {
    const res = parseDollarsToCents('90071992547410.00'); // 9007199254741000 > MAX_SAFE
    expect(res.ok).toBe(false);
    expect(res.error).toMatch(/too large/i);
  });

  it('never returns an unsafe integer when ok is true', () => {
    for (const input of ['0', '9999.99', '90071992547409.91', '123456.78']) {
      const res = parseDollarsToCents(input);
      if (res.ok) expect(Number.isSafeInteger(res.cents)).toBe(true);
    }
  });
});

describe('centsToDollars (display only)', () => {
  it.each([
    [15000, '150.00'],
    [1001, '10.01'],
    [10, '0.10'],
    [0, '0.00'],
    [null, '0.00'],
  ])('formats %p -> %s', (cents, expected) => {
    expect(centsToDollars(cents)).toBe(expected);
  });
});

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
describe('rendering canonical state', () => {
  it('renders status, revision, amount (cents->dollars), payment requirement, deposit and notes', () => {
    renderEditor({
      quote_status: 'DRAFT',
      quote_revision: 2,
      quote_amount_cents: 15000,
      currency: 'USD',
      deposit_amount_cents: 5000,
      payment_requirement: 'DEPOSIT',
      quote_notes_client: 'Standard walk',
      quote_notes_internal: 'internal note',
      internal_pricing_notes: 'pricing note',
    });

    expect(screen.getByTestId('aqe-status')).toHaveTextContent('DRAFT');
    expect(screen.getByTestId('aqe-revision')).toHaveTextContent('2');
    expect(screen.getByLabelText('Quote amount in dollars')).toHaveValue('150.00');
    expect(screen.getByLabelText('Payment requirement')).toHaveValue('DEPOSIT');
    expect(screen.getByLabelText('Deposit amount in dollars')).toHaveValue('50.00');
    expect(screen.getByLabelText('Client-facing note')).toHaveValue('Standard walk');
    expect(screen.getByLabelText('Internal note')).toHaveValue('internal note');
    expect(screen.getByLabelText('Internal pricing note')).toHaveValue('pricing note');
  });

  it('shows "No quote yet" when the request has no canonical quote_status', () => {
    renderEditor({});
    expect(screen.getByTestId('aqe-status')).toHaveTextContent('No quote yet');
  });
});

// ---------------------------------------------------------------------------
// Create (no canonical quote)
// ---------------------------------------------------------------------------
describe('create (no canonical quote)', () => {
  it('first save requires an amount (blocks statusless create)', async () => {
    renderEditor({});
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(screen.getByTestId('aqe-field-error')).toBeInTheDocument());
    expect(updateAdminRequestQuote).not.toHaveBeenCalled();
  });

  it('sends a correct canonical PATCH payload when an amount is provided', async () => {
    const { onQuoteUpdated } = renderEditor({});
    typeInto('Quote amount in dollars', '150.00');
    typeInto('Client-facing note', 'Welcome');
    fireEvent.click(screen.getByTestId('aqe-save'));

    await waitFor(() => expect(updateAdminRequestQuote).toHaveBeenCalledTimes(1));
    const [reqId, payload] = updateAdminRequestQuote.mock.calls[0];
    expect(reqId).toBe('req-123');
    expect(payload.quote_amount_cents).toBe(15000);
    expect(payload.currency).toBe('USD');
    expect(payload.payment_requirement).toBe('NONE');
    expect(payload.deposit_amount_cents).toBe(0);
    expect(payload.quote_notes_client).toBe('Welcome');
    // No legacy / fabricated fields.
    expect(payload).not.toHaveProperty('quote_amount');
    expect(payload).not.toHaveProperty('payment_status');
    expect(payload).not.toHaveProperty('expected_revision');
    await waitFor(() => expect(onQuoteUpdated).toHaveBeenCalledWith('req-123'));
  });

  it('button reads "Save Draft" with no canonical quote', () => {
    renderEditor({});
    expect(screen.getByTestId('aqe-save')).toHaveTextContent('Save Draft');
  });
});

// ---------------------------------------------------------------------------
// DRAFT
// ---------------------------------------------------------------------------
describe('DRAFT', () => {
  it('is editable and sends an updated payload with Save Draft', async () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000, currency: 'USD' });
    expect(screen.getByTestId('aqe-save')).toHaveTextContent('Save Draft');
    typeInto('Quote amount in dollars', '125.50');
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(updateAdminRequestQuote).toHaveBeenCalledTimes(1));
    expect(updateAdminRequestQuote.mock.calls[0][1].quote_amount_cents).toBe(12550);
    // No confirmation dialog for DRAFT.
    expect(screen.queryByTestId('aqe-confirm')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// SENT
// ---------------------------------------------------------------------------
describe('SENT', () => {
  const sent = { quote_status: 'SENT', quote_revision: 1, quote_amount_cents: 10000, currency: 'USD', quote_notes_internal: '' };

  it('internal-only edit saves without confirmation and uses "Save Notes"', async () => {
    renderEditor(sent);
    typeInto('Internal note', 'ping the client later');
    expect(screen.getByTestId('aqe-save')).toHaveTextContent('Save Notes');
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(updateAdminRequestQuote).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId('aqe-confirm')).not.toBeInTheDocument();
  });

  it('commercial edit requires confirmation and does not PATCH until confirmed', async () => {
    renderEditor(sent);
    typeInto('Quote amount in dollars', '175.00');
    expect(screen.getByTestId('aqe-save')).toHaveTextContent('Save Revised Draft');
    fireEvent.click(screen.getByTestId('aqe-save'));
    // Confirmation shown, no PATCH yet.
    expect(screen.getByTestId('aqe-confirm')).toBeInTheDocument();
    expect(updateAdminRequestQuote).not.toHaveBeenCalled();
    // Copy explains new revision / return to draft / re-send.
    const copy = screen.getByTestId('aqe-confirm-copy').textContent.toLowerCase();
    expect(copy).toContain('new revision');
    expect(copy).toContain('draft');
    expect(copy).toContain('re-sent');
    fireEvent.click(screen.getByTestId('aqe-confirm-save'));
    await waitFor(() => expect(updateAdminRequestQuote).toHaveBeenCalledTimes(1));
    expect(updateAdminRequestQuote.mock.calls[0][1].quote_amount_cents).toBe(17500);
  });
});

// ---------------------------------------------------------------------------
// ACCEPTED
// ---------------------------------------------------------------------------
describe('ACCEPTED', () => {
  const accepted = {
    quote_status: 'ACCEPTED', quote_revision: 1, quote_amount_cents: 10000, currency: 'USD',
    quote_accepted_at: '2026-09-01T00:00:00Z', quote_notes_internal: '',
  };

  it('internal-only edit preserves acceptance and does not confirm', async () => {
    renderEditor(accepted);
    typeInto('Internal pricing note', 'margin ok');
    expect(screen.getByTestId('aqe-save')).toHaveTextContent('Save Notes');
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(updateAdminRequestQuote).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId('aqe-confirm')).not.toBeInTheDocument();
  });

  it('commercial edit requires confirmation whose copy mentions invalidating acceptance', async () => {
    renderEditor(accepted);
    typeInto('Quote amount in dollars', '200.00');
    fireEvent.click(screen.getByTestId('aqe-save'));
    expect(screen.getByTestId('aqe-confirm')).toBeInTheDocument();
    const copy = screen.getByTestId('aqe-confirm-copy').textContent.toLowerCase();
    expect(copy).toContain('invalidate');
    expect(copy).toContain('acceptance');
    expect(updateAdminRequestQuote).not.toHaveBeenCalled();
  });

  it('cancelling the confirmation prevents the PATCH', async () => {
    renderEditor(accepted);
    typeInto('Quote amount in dollars', '200.00');
    fireEvent.click(screen.getByTestId('aqe-save'));
    fireEvent.click(screen.getByTestId('aqe-confirm-cancel'));
    expect(screen.queryByTestId('aqe-confirm')).not.toBeInTheDocument();
    expect(updateAdminRequestQuote).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// DECLINED / NOT_REQUIRED / SUPERSEDED (display-only)
// ---------------------------------------------------------------------------
describe('display-only states', () => {
  it('DECLINED shows display-only content and no editable amount input / no save', () => {
    renderEditor({ quote_status: 'DECLINED', quote_revision: 1, quote_amount_cents: 10000, quote_declined_at: '2026-09-02T00:00:00Z' });
    expect(screen.getByTestId('aqe-display-only')).toBeInTheDocument();
    expect(screen.queryByLabelText('Quote amount in dollars')).not.toBeInTheDocument();
    expect(screen.queryByTestId('aqe-save')).not.toBeInTheDocument();
    // Does not imply it can be revived.
    expect(screen.getByTestId('aqe-display-only').textContent.toLowerCase()).toContain('not available');
  });

  it('NOT_REQUIRED shows display-only content and no create/edit action', () => {
    renderEditor({ quote_status: 'NOT_REQUIRED', quote_revision: 1, quote_amount_cents: 0 });
    expect(screen.getByTestId('aqe-display-only')).toBeInTheDocument();
    expect(screen.queryByTestId('aqe-save')).not.toBeInTheDocument();
  });

  it('SUPERSEDED is treated as display-only history', () => {
    renderEditor({ quote_status: 'SUPERSEDED', quote_revision: 1 });
    expect(screen.getByTestId('aqe-display-only')).toBeInTheDocument();
    expect(screen.queryByTestId('aqe-save')).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Payment requirement UX
// ---------------------------------------------------------------------------
describe('payment requirement UX', () => {
  it('NONE hides the deposit input and sends deposit_amount_cents: 0', async () => {
    renderEditor({ quote_status: 'DRAFT', quote_amount_cents: 10000, payment_requirement: 'NONE' });
    expect(screen.queryByLabelText('Deposit amount in dollars')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(updateAdminRequestQuote).toHaveBeenCalledTimes(1));
    expect(updateAdminRequestQuote.mock.calls[0][1].deposit_amount_cents).toBe(0);
  });

  it('DEPOSIT shows the deposit input and requires a positive deposit', async () => {
    renderEditor({ quote_status: 'DRAFT', quote_amount_cents: 10000, payment_requirement: 'NONE' });
    fireEvent.change(screen.getByLabelText('Payment requirement'), { target: { value: 'DEPOSIT' } });
    const dep = screen.getByLabelText('Deposit amount in dollars');
    expect(dep).toBeInTheDocument();
    // zero deposit rejected
    fireEvent.change(dep, { target: { value: '0' } });
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(screen.getByTestId('aqe-field-error')).toBeInTheDocument());
    expect(updateAdminRequestQuote).not.toHaveBeenCalled();
  });

  it('DEPOSIT rejects a deposit greater than the quote total (UI guard)', async () => {
    renderEditor({ quote_status: 'DRAFT', quote_amount_cents: 10000, payment_requirement: 'DEPOSIT', deposit_amount_cents: 2000 });
    typeInto('Deposit amount in dollars', '250.00'); // > 100.00 total
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(screen.getByTestId('aqe-field-error')).toBeInTheDocument());
    expect(updateAdminRequestQuote).not.toHaveBeenCalled();
  });

  it('DEPOSIT allows a deposit equal to the quote total', async () => {
    renderEditor({ quote_status: 'DRAFT', quote_amount_cents: 10000, payment_requirement: 'DEPOSIT', deposit_amount_cents: 2000 });
    typeInto('Deposit amount in dollars', '100.00');
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(updateAdminRequestQuote).toHaveBeenCalledTimes(1));
    expect(updateAdminRequestQuote.mock.calls[0][1].deposit_amount_cents).toBe(10000);
  });

  it('FULL hides the deposit input and sends deposit_amount_cents: 0', async () => {
    renderEditor({ quote_status: 'DRAFT', quote_amount_cents: 10000, payment_requirement: 'FULL', deposit_amount_cents: 3000 });
    expect(screen.queryByLabelText('Deposit amount in dollars')).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(updateAdminRequestQuote).toHaveBeenCalledTimes(1));
    expect(updateAdminRequestQuote.mock.calls[0][1].deposit_amount_cents).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// Save + reconciliation
// ---------------------------------------------------------------------------
describe('save and reconciliation', () => {
  it('invokes onQuoteUpdated(requestId) on success for the authoritative refresh', async () => {
    const onQuoteUpdated = vi.fn().mockResolvedValue(undefined);
    renderEditor({ quote_status: 'DRAFT', quote_amount_cents: 10000 }, { onQuoteUpdated });
    typeInto('Quote amount in dollars', '120.00');
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(onQuoteUpdated).toHaveBeenCalledWith('req-123'));
  });

  it('does not call onQuoteUpdated when the PATCH fails', async () => {
    const onQuoteUpdated = vi.fn().mockResolvedValue(undefined);
    updateAdminRequestQuote.mockRejectedValueOnce(new Error('Request failed with status 500'));
    renderEditor({ quote_status: 'DRAFT', quote_amount_cents: 10000 }, { onQuoteUpdated });
    typeInto('Quote amount in dollars', '120.00');
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(screen.getByTestId('aqe-save-error')).toBeInTheDocument());
    expect(onQuoteUpdated).not.toHaveBeenCalled();
  });

  it('never submits an over-range (unsafe-integer) amount to the API', async () => {
    renderEditor({ quote_status: 'DRAFT', quote_amount_cents: 10000 });
    typeInto('Quote amount in dollars', '999999999999999'); // *100 is not safe
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(screen.getByTestId('aqe-field-error')).toBeInTheDocument());
    expect(screen.getByTestId('aqe-field-error').textContent).toMatch(/too large/i);
    expect(updateAdminRequestQuote).not.toHaveBeenCalled();
  });

  // Pre-commit hardening: PATCH succeeds but the authoritative refresh fails.
  it('shows a non-destructive "saved but not refreshed" warning when PATCH succeeds but refresh rejects', async () => {
    const onQuoteUpdated = vi.fn().mockRejectedValueOnce(new Error('Network error during reload'));
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000 }, { onQuoteUpdated });
    typeInto('Quote amount in dollars', '120.00');
    fireEvent.click(screen.getByTestId('aqe-save'));

    // PATCH ran exactly once and the refresh was attempted.
    await waitFor(() => expect(updateAdminRequestQuote).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(onQuoteUpdated).toHaveBeenCalledTimes(1));

    // Warning (not a save-failure) is surfaced.
    await waitFor(() => expect(screen.getByTestId('aqe-save-warning')).toBeInTheDocument());
    const warn = screen.getByTestId('aqe-save-warning').textContent;
    expect(warn).toMatch(/saved/i);
    expect(warn).toMatch(/could not be refreshed|reopen/i);
    // Must NOT claim the save failed.
    expect(screen.queryByTestId('aqe-save-error')).not.toBeInTheDocument();
    expect(warn).not.toMatch(/couldn.t save/i);

    // No second PATCH, no Send call.
    expect(updateAdminRequestQuote).toHaveBeenCalledTimes(1);
    expect(sendAdminRequestQuote).not.toHaveBeenCalled();

    // Entered values are not destructively cleared, and the displayed status/revision
    // are the ORIGINAL record values (no fabricated post-save state).
    expect(screen.getByLabelText('Quote amount in dollars')).toHaveValue('120.00');
    expect(screen.getByTestId('aqe-status')).toHaveTextContent('DRAFT');
    expect(screen.getByTestId('aqe-revision')).toHaveTextContent('1');
  });
});

// ---------------------------------------------------------------------------
// Errors
// ---------------------------------------------------------------------------
describe('error handling', () => {
  const base = { quote_status: 'DRAFT', quote_amount_cents: 10000 };

  it.each([
    ['Request failed with status 400 — Quote update rejected: bad', /rejected|400/i],
    ['Forbidden', /permission/i],
    ['Request failed with status 404 not found', /could not be found/i],
    ['NetworkError when attempting to fetch', /couldn.t save the quote/i],
  ])('maps server error %s to a friendly message', async (message, matcher) => {
    updateAdminRequestQuote.mockRejectedValueOnce(new Error(message));
    renderEditor(base);
    typeInto('Quote amount in dollars', '120.00');
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(screen.getByTestId('aqe-save-error')).toBeInTheDocument());
    expect(screen.getByTestId('aqe-save-error').textContent).toMatch(matcher);
  });

  it('preserves entered form values on error (does not clear inputs)', async () => {
    updateAdminRequestQuote.mockRejectedValueOnce(new Error('Request failed with status 500'));
    renderEditor(base);
    typeInto('Quote amount in dollars', '133.33');
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(screen.getByTestId('aqe-save-error')).toBeInTheDocument());
    expect(screen.getByLabelText('Quote amount in dollars')).toHaveValue('133.33');
  });
});

// ---------------------------------------------------------------------------
// Boundaries
// ---------------------------------------------------------------------------
describe('W2C / Stripe / legacy boundaries', () => {
  it('never calls sendAdminRequestQuote and never calls Stripe/payment APIs', async () => {
    renderEditor({ quote_status: 'DRAFT', quote_amount_cents: 10000 });
    typeInto('Quote amount in dollars', '120.00');
    fireEvent.click(screen.getByTestId('aqe-save'));
    await waitFor(() => expect(updateAdminRequestQuote).toHaveBeenCalledTimes(1));
    expect(sendAdminRequestQuote).not.toHaveBeenCalled();
    expect(createPaymentSession).not.toHaveBeenCalled();
    expect(sendPaymentEmail).not.toHaveBeenCalled();
  });

  it('renders no Resend control on a SENT quote (W2C exposes DRAFT->SENT only)', () => {
    renderEditor({ quote_status: 'SENT', quote_amount_cents: 10000, quote_revision: 1 });
    expect(screen.queryByText(/resend/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId('aqe-send')).not.toBeInTheDocument();
  });

  it('renders nothing editable for staff', () => {
    const { container } = render(
      <AdminQuoteEditor request={makeRequest({ quote_status: 'DRAFT', quote_amount_cents: 10000 })} userRole="staff" onQuoteUpdated={vi.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing editable for client', () => {
    const { container } = render(
      <AdminQuoteEditor request={makeRequest({ quote_status: 'DRAFT', quote_amount_cents: 10000 })} userRole="client" onQuoteUpdated={vi.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });
});

// ---------------------------------------------------------------------------
// W2C — Send Quote (DRAFT -> SENT)
// ---------------------------------------------------------------------------
describe('W2C — Send Quote visibility', () => {
  it('shows an enabled Send Quote on a clean persisted DRAFT with amount > 0', () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000, currency: 'USD' });
    const btn = screen.getByTestId('aqe-send');
    expect(btn).toBeInTheDocument();
    expect(btn).not.toBeDisabled();
  });

  it('shows no Send on a no-status request', () => {
    renderEditor({});
    expect(screen.queryByTestId('aqe-send')).not.toBeInTheDocument();
  });

  it.each(['SENT', 'ACCEPTED', 'DECLINED', 'NOT_REQUIRED', 'SUPERSEDED'])(
    'shows no Send control for %s',
    (quote_status) => {
      renderEditor({ quote_status, quote_revision: 1, quote_amount_cents: 10000 });
      expect(screen.queryByTestId('aqe-send')).not.toBeInTheDocument();
    }
  );
});

describe('W2C — dirty-state protection', () => {
  const draft = { quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000, currency: 'USD' };

  it('Send is enabled on an unchanged canonical DRAFT', () => {
    renderEditor(draft);
    expect(screen.getByTestId('aqe-send')).not.toBeDisabled();
    expect(screen.queryByTestId('aqe-send-blocked')).not.toBeInTheDocument();
  });

  it.each([
    ['Quote amount in dollars', '175.00'],
    ['Currency', 'EUR'],
    ['Client-facing note', 'hello'],
    ['Internal note', 'note'],
    ['Internal pricing note', 'cost'],
  ])('disables Send when %s is edited but unsaved', (label, value) => {
    renderEditor(draft);
    typeInto(label, value);
    expect(screen.getByTestId('aqe-send')).toBeDisabled();
    expect(screen.getByTestId('aqe-send-blocked')).toHaveTextContent(/save your changes/i);
  });

  it('disables Send when payment requirement is edited but unsaved', () => {
    renderEditor(draft);
    fireEvent.change(screen.getByLabelText('Payment requirement'), { target: { value: 'DEPOSIT' } });
    expect(screen.getByTestId('aqe-send')).toBeDisabled();
  });

  it('disables Send when deposit is edited but unsaved', () => {
    renderEditor({ ...draft, payment_requirement: 'DEPOSIT', deposit_amount_cents: 2000 });
    typeInto('Deposit amount in dollars', '30.00');
    expect(screen.getByTestId('aqe-send')).toBeDisabled();
  });

  // Effective-default normalization: a legacy/absent record field must NOT appear dirty.
  it('is NOT dirty when currency is absent on the record and form shows effective USD', () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000 }); // no currency
    expect(screen.getByLabelText('Currency')).toHaveValue('USD');
    expect(screen.getByTestId('aqe-send')).not.toBeDisabled();
  });

  it('is NOT dirty when payment_requirement is absent and form shows effective NONE', () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000 }); // no payment_requirement
    expect(screen.getByLabelText('Payment requirement')).toHaveValue('NONE');
    expect(screen.getByTestId('aqe-send')).not.toBeDisabled();
  });

  it('is NOT dirty when deposit/notes are absent and form shows effective empty', () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000 });
    // No deposit field is shown (NONE), notes empty — nothing edited.
    expect(screen.getByTestId('aqe-send')).not.toBeDisabled();
  });

  it('is NOT dirty when the persisted amount formats to a different-but-equal string', () => {
    // Record 15000 cents -> form "150.00"; equal by cents, so not dirty.
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 15000, currency: 'USD' });
    expect(screen.getByLabelText('Quote amount in dollars')).toHaveValue('150.00');
    expect(screen.getByTestId('aqe-send')).not.toBeDisabled();
  });
});

describe('W2C — persisted amount precondition', () => {
  it('disables Send when the persisted amount is missing', () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1 }); // no amount
    expect(screen.getByTestId('aqe-send')).toBeDisabled();
    expect(screen.getByTestId('aqe-send-blocked')).toHaveTextContent(/greater than \$0/i);
  });

  it('disables Send when the persisted amount is 0', () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 0 });
    expect(screen.getByTestId('aqe-send')).toBeDisabled();
    expect(screen.getByTestId('aqe-send-blocked')).toHaveTextContent(/greater than \$0/i);
  });

  it('enables Send for a positive persisted amount with no unsaved edits', () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 5000, currency: 'USD' });
    expect(screen.getByTestId('aqe-send')).not.toBeDisabled();
  });
});

describe('W2C — malformed form input blocks Send', () => {
  // Proves the W2C guard (not just the pure parser): an unparseable unsaved money
  // field makes the editor dirty (parse -> NaN -> dirty), so Send stays disabled and
  // no POST is issued. The user must fix/save first.
  it('keeps Send disabled when the amount field holds a malformed value (10.999)', () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 15000, currency: 'USD' });
    typeInto('Quote amount in dollars', '10.999'); // >2 decimals -> parser rejects
    const btn = screen.getByTestId('aqe-send');
    expect(btn).toBeInTheDocument();
    expect(btn).toBeDisabled();
    expect(screen.getByTestId('aqe-send-blocked')).toHaveTextContent(/save your changes/i);
    fireEvent.click(btn);
    expect(screen.queryByTestId('aqe-send-confirm')).not.toBeInTheDocument();
    expect(sendAdminRequestQuote).not.toHaveBeenCalled();
  });

  it('keeps Send disabled when the amount exceeds the safe-integer range (90071992547410.00)', () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 15000, currency: 'USD' });
    typeInto('Quote amount in dollars', '90071992547410.00'); // cents > MAX_SAFE_INTEGER
    const btn = screen.getByTestId('aqe-send');
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(sendAdminRequestQuote).not.toHaveBeenCalled();
  });

  it('keeps Send disabled when the deposit field holds a malformed value (shared parser path)', () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 20000, currency: 'USD', payment_requirement: 'DEPOSIT', deposit_amount_cents: 5000 });
    typeInto('Deposit amount in dollars', '1.2.3'); // malformed -> parser rejects
    const btn = screen.getByTestId('aqe-send');
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(sendAdminRequestQuote).not.toHaveBeenCalled();
  });
});

describe('W2C — confirmation', () => {
  it('shows a confirmation using persisted values and does not POST until confirmed', () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 12500, currency: 'USD', payment_requirement: 'FULL' });
    fireEvent.click(screen.getByTestId('aqe-send'));
    expect(screen.getByTestId('aqe-send-confirm')).toBeInTheDocument();
    const summary = screen.getByTestId('aqe-send-summary').textContent;
    expect(summary).toContain('125.00');
    expect(summary).toContain('FULL');
    expect(sendAdminRequestQuote).not.toHaveBeenCalled();
  });

  it('includes the persisted deposit in the summary when requirement is DEPOSIT', () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 20000, currency: 'USD', payment_requirement: 'DEPOSIT', deposit_amount_cents: 5000 });
    fireEvent.click(screen.getByTestId('aqe-send'));
    const summary = screen.getByTestId('aqe-send-summary').textContent;
    expect(summary).toMatch(/deposit/i);
    expect(summary).toContain('50.00');
  });

  it('cancel closes the confirmation and performs no POST', () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000 });
    fireEvent.click(screen.getByTestId('aqe-send'));
    fireEvent.click(screen.getByTestId('aqe-send-confirm-cancel'));
    expect(screen.queryByTestId('aqe-send-confirm')).not.toBeInTheDocument();
    expect(sendAdminRequestQuote).not.toHaveBeenCalled();
  });

  it('confirm invokes sendAdminRequestQuote exactly once with requestId and no body', async () => {
    const { onQuoteUpdated } = renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000 });
    fireEvent.click(screen.getByTestId('aqe-send'));
    fireEvent.click(screen.getByTestId('aqe-send-confirm-ok'));
    await waitFor(() => expect(sendAdminRequestQuote).toHaveBeenCalledTimes(1));
    expect(sendAdminRequestQuote).toHaveBeenCalledWith('req-123');
    // No body / expected_revision at the component call site (single string arg).
    expect(sendAdminRequestQuote.mock.calls[0]).toHaveLength(1);
    await waitFor(() => expect(onQuoteUpdated).toHaveBeenCalledWith('req-123'));
  });
});

describe('W2C — send success / reconciliation', () => {
  it('calls onQuoteUpdated and does not fabricate a local SENT status', async () => {
    const onQuoteUpdated = vi.fn().mockResolvedValue(undefined);
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000 }, { onQuoteUpdated });
    fireEvent.click(screen.getByTestId('aqe-send'));
    fireEvent.click(screen.getByTestId('aqe-send-confirm-ok'));
    await waitFor(() => expect(onQuoteUpdated).toHaveBeenCalledWith('req-123'));
    // Status display still reflects the (unchanged) record prop — no local fabrication.
    expect(screen.getByTestId('aqe-status')).toHaveTextContent('DRAFT');
  });
});

describe('W2C — send failures', () => {
  const draft = { quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000 };

  it.each([
    ['Request failed with status 400 — Quote send rejected: bad', /rejected|could not be sent/i],
    ['Forbidden', /permission/i],
    ['Request failed with status 404 not found', /could not be found/i],
    ['NetworkError when attempting to fetch', /couldn.t send the quote/i],
  ])('maps POST error %s to a friendly send error', async (message, matcher) => {
    sendAdminRequestQuote.mockRejectedValueOnce(new Error(message));
    renderEditor(draft);
    fireEvent.click(screen.getByTestId('aqe-send'));
    fireEvent.click(screen.getByTestId('aqe-send-confirm-ok'));
    await waitFor(() => expect(screen.getByTestId('aqe-send-error')).toBeInTheDocument());
    expect(screen.getByTestId('aqe-send-error').textContent).toMatch(matcher);
  });

  it('409 shows the conflict message, refreshes authoritatively, and does not retry', async () => {
    const onQuoteUpdated = vi.fn().mockResolvedValue(undefined);
    sendAdminRequestQuote.mockRejectedValueOnce(new Error('Conflict: the quote changed since it was loaded; reload and retry'));
    renderEditor(draft, { onQuoteUpdated });
    fireEvent.click(screen.getByTestId('aqe-send'));
    fireEvent.click(screen.getByTestId('aqe-send-confirm-ok'));
    await waitFor(() => expect(screen.getByTestId('aqe-send-error')).toBeInTheDocument());
    expect(screen.getByTestId('aqe-send-error').textContent).toMatch(/changed before it could be sent/i);
    // Exactly one POST (no auto-retry), and an authoritative refresh attempt.
    expect(sendAdminRequestQuote).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(onQuoteUpdated).toHaveBeenCalledWith('req-123'));
  });

  it('send success + refresh failure shows a non-destructive warning, not a send-failure', async () => {
    const onQuoteUpdated = vi.fn().mockRejectedValueOnce(new Error('Network error during reload'));
    renderEditor(draft, { onQuoteUpdated });
    fireEvent.click(screen.getByTestId('aqe-send'));
    fireEvent.click(screen.getByTestId('aqe-send-confirm-ok'));
    await waitFor(() => expect(sendAdminRequestQuote).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByTestId('aqe-send-warning')).toBeInTheDocument());
    const warn = screen.getByTestId('aqe-send-warning').textContent;
    expect(warn).toMatch(/was sent/i);
    expect(warn).toMatch(/could not be refreshed|reopen/i);
    expect(screen.queryByTestId('aqe-send-error')).not.toBeInTheDocument();
    expect(warn).not.toMatch(/couldn.t send/i);
    // No second POST, no fabricated SENT status.
    expect(sendAdminRequestQuote).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('aqe-status')).toHaveTextContent('DRAFT');
  });
});

describe('W2C — boundaries', () => {
  it('never calls Stripe/payment APIs or sendPaymentEmail when sending', async () => {
    renderEditor({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000 });
    fireEvent.click(screen.getByTestId('aqe-send'));
    fireEvent.click(screen.getByTestId('aqe-send-confirm-ok'));
    await waitFor(() => expect(sendAdminRequestQuote).toHaveBeenCalledTimes(1));
    expect(createPaymentSession).not.toHaveBeenCalled();
    expect(sendPaymentEmail).not.toHaveBeenCalled();
  });

  it('does not expose Send for staff/client even on a valid DRAFT', () => {
    const { container } = render(
      <AdminQuoteEditor request={makeRequest({ quote_status: 'DRAFT', quote_revision: 1, quote_amount_cents: 10000 })} userRole="staff" onQuoteUpdated={vi.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('exposes no "resend"/"notify again" wording anywhere in the editor', () => {
    renderEditor({ quote_status: 'SENT', quote_revision: 1, quote_amount_cents: 10000 });
    expect(screen.queryByText(/resend|notify .*again|send again/i)).not.toBeInTheDocument();
  });
});
