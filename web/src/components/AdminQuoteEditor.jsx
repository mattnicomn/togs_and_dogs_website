import { useMemo, useState } from 'react';
import { updateAdminRequestQuote, sendAdminRequestQuote } from '../api/client';

/**
 * W2B/W2C — Canonical owner/admin quote editor (OPS-3A).
 *
 * W2B: edits the canonical REQUEST-based quote via the deployed
 * `PATCH /admin/requests/{requestId}/quote` endpoint (`updateAdminRequestQuote`).
 * W2C: transitions a persisted DRAFT to SENT via `POST .../quote/send`
 * (`sendAdminRequestQuote`). The editor never calls Stripe/payment, never mutates
 * legacy PET quote fields, never auto-approves a booking, and never performs client
 * Accept/Decline.
 *
 * W2C scope note: only `DRAFT -> SENT` is exposed. The deployed send endpoint also
 * technically accepts a current `SENT` quote (refreshing `quote_sent_at`), but its
 * client-delivery/notification semantics are unproven, so NO "Resend" control is
 * exposed here; a current SENT quote renders read-only sent state with no send action.
 *
 * Read/reconciliation strategy (approved A_PLUS_C): initial state is derived from the
 * canonical REQUEST record (`request`, i.e. CareCard's `pet._originItem`); after a
 * successful PATCH or send the parent performs an authoritative refresh via
 * `onQuoteUpdated(requestId)` and this component re-renders from the refreshed record.
 * The partial PATCH/send response is intentionally NOT used as the editor truth.
 */

// Canonical commercial fields (a change to any of these on a SENT/ACCEPTED quote
// creates a new revision and invalidates acceptance — matches the backend
// COMMERCIAL_QUOTE_FIELDS set).
const COMMERCIAL_FIELDS = [
  'quote_amount_cents',
  'currency',
  'deposit_amount_cents',
  'payment_requirement',
  'quote_notes_client',
];

const PAYMENT_REQUIREMENTS = ['NONE', 'DEPOSIT', 'FULL'];

const EDITABLE_ROLES = ['owner', 'admin'];

/**
 * Deterministic string-based dollars -> integer cents parser (approved W2B rule).
 * Accepts only `^\d+(\.\d{1,2})?$` after trimming. No float math, no silent
 * rounding, no reinterpretation of malformed input.
 *
 * @returns {{ ok: true, cents: number } | { ok: false, error: string }}
 */
export function parseDollarsToCents(raw) {
  const s = String(raw ?? '').trim();
  if (s === '') {
    return { ok: false, error: 'Enter an amount.' };
  }
  if (!/^\d+(\.\d{1,2})?$/.test(s)) {
    return { ok: false, error: 'Enter a valid amount (digits, up to 2 decimals, no negatives).' };
  }
  const [whole, frac = ''] = s.split('.');
  const fracPadded = (frac + '00').slice(0, 2);
  const cents = parseInt(whole, 10) * 100 + parseInt(fracPadded, 10);
  // Safe-integer guard: a very large (but shape-valid) digit string can exceed
  // JavaScript's safe-integer range, which would silently submit an imprecise
  // value to the API. Reject rather than clamp/round.
  if (!Number.isSafeInteger(cents)) {
    return { ok: false, error: 'Amount is too large.' };
  }
  return { ok: true, cents };
}

/** Display-only: integer cents -> major-unit string (e.g. 1234 -> "12.34"). */
export function centsToDollars(cents) {
  const n = Number(cents || 0);
  return (n / 100).toFixed(2);
}

/** True when the request has no canonical quote lifecycle yet. */
function hasNoCanonicalQuote(request) {
  const status = request?.quote_status;
  return status === undefined || status === null;
}

function formatTimestamp(ts) {
  if (!ts) return null;
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return String(ts);
  return d.toLocaleString();
}

/**
 * @param {object}   props
 * @param {object}   props.request        Canonical REQUEST record (CareCard _originItem).
 * @param {string}   props.userRole       'owner' | 'admin' | 'staff' | 'client'.
 * @param {Function} props.onQuoteUpdated async (requestId) => void — parent authoritative refresh.
 */
export default function AdminQuoteEditor({ request, userRole, onQuoteUpdated }) {
  const requestId = request?.request_id;
  const status = request?.quote_status ?? null;
  const noQuote = hasNoCanonicalQuote(request);
  const revision = request?.quote_revision ?? null;

  const isLive = status === 'SENT' || status === 'ACCEPTED';
  // DECLINED and NOT_REQUIRED are display-only in W2B (GAP-1 / GAP-2 deferred).
  const isDisplayOnlyState = status === 'DECLINED' || status === 'NOT_REQUIRED' || status === 'SUPERSEDED';
  const canEdit = EDITABLE_ROLES.includes(userRole) && !isDisplayOnlyState;

  // Initialize form state from the canonical record (never from legacy PET fields).
  const initial = useMemo(() => ({
    quote_amount: request?.quote_amount_cents != null ? centsToDollars(request.quote_amount_cents) : '',
    currency: request?.currency || 'USD',
    deposit_amount: request?.deposit_amount_cents != null ? centsToDollars(request.deposit_amount_cents) : '',
    payment_requirement: request?.payment_requirement || 'NONE',
    quote_notes_client: request?.quote_notes_client || '',
    quote_notes_internal: request?.quote_notes_internal || '',
    internal_pricing_notes: request?.internal_pricing_notes || '',
  }), [request]);

  const [form, setForm] = useState(initial);
  const [fieldError, setFieldError] = useState('');
  const [saveError, setSaveError] = useState('');
  const [saveWarning, setSaveWarning] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [pendingConfirm, setPendingConfirm] = useState(null); // { payload, isCommercial }
  // W2C send state (kept separate from save state for unambiguous messaging).
  const [sendError, setSendError] = useState('');
  const [sendWarning, setSendWarning] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [pendingSendConfirm, setPendingSendConfirm] = useState(false);

  const setField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setFieldError('');
    setSaveError('');
    setSaveWarning('');
    setSendError('');
    setSendWarning('');
  };

  // Owner/admin gating: render nothing editable for other roles. The backend remains
  // the authoritative 403 boundary; this is defense-in-depth.
  if (!EDITABLE_ROLES.includes(userRole)) {
    return null;
  }

  const showDeposit = form.payment_requirement === 'DEPOSIT';

  // --- Build and validate the canonical payload --------------------------------
  // Only canonical recognized fields are ever sent. Returns {payload} or {error}.
  const buildPayload = () => {
    const payload = {};

    // Amount: required on first create; for existing quotes, send when present.
    const amountRequired = noQuote; // first create must include a valid amount
    const amountRaw = form.quote_amount;
    const amountProvided = String(amountRaw ?? '').trim() !== '';
    if (amountRequired || amountProvided) {
      const parsed = parseDollarsToCents(amountRaw);
      if (!parsed.ok) {
        return { error: `Quote amount: ${parsed.error}` };
      }
      payload.quote_amount_cents = parsed.cents;
    }

    payload.currency = (form.currency || 'USD').trim().toUpperCase() || 'USD';
    payload.payment_requirement = form.payment_requirement;

    // Deposit handling by payment_requirement.
    if (form.payment_requirement === 'DEPOSIT') {
      const dep = parseDollarsToCents(form.deposit_amount);
      if (!dep.ok) {
        return { error: `Deposit amount: ${dep.error}` };
      }
      // UI data-quality guard (NOT backend-enforced): 0 < deposit <= quote total.
      if (dep.cents <= 0) {
        return { error: 'Deposit amount must be greater than 0 when a deposit is required.' };
      }
      if (payload.quote_amount_cents != null && dep.cents > payload.quote_amount_cents) {
        return { error: 'Deposit amount cannot exceed the quote total.' };
      }
      payload.deposit_amount_cents = dep.cents;
    } else {
      // NONE / FULL: clear any prior deposit so stale data is never misleading.
      payload.deposit_amount_cents = 0;
    }

    payload.quote_notes_client = form.quote_notes_client || '';
    payload.quote_notes_internal = form.quote_notes_internal || '';
    payload.internal_pricing_notes = form.internal_pricing_notes || '';

    return { payload };
  };

  // Determine whether the pending payload changes any COMMERCIAL field vs the record.
  // Non-amount fields are compared against the record's EFFECTIVE value using the
  // same defaults the form/payload applies (currency -> 'USD', payment_requirement
  // -> 'NONE'), so a payload default never counts as a change against an absent
  // record field.
  const effectiveCurrentFor = (field) => {
    if (field === 'currency') return request?.currency || 'USD';
    if (field === 'payment_requirement') return request?.payment_requirement || 'NONE';
    return request?.[field] ?? '';
  };
  const isCommercialChange = (payload) => {
    for (const field of COMMERCIAL_FIELDS) {
      if (!(field in payload)) continue;
      if (field === 'quote_amount_cents' || field === 'deposit_amount_cents') {
        const current = Number(request?.[field] ?? 0);
        if (Number(payload[field] ?? 0) !== current) return true;
      } else {
        if ((payload[field] ?? '') !== (effectiveCurrentFor(field) ?? '')) return true;
      }
    }
    return false;
  };

  const performSave = async (payload) => {
    setIsSaving(true);
    setSaveError('');
    setSaveWarning('');
    // Phase 1: the PATCH itself. A failure here means the save did not persist.
    try {
      await updateAdminRequestQuote(requestId, payload);
    } catch (err) {
      const msg = String(err?.message || '');
      if (/403|forbidden/i.test(msg)) {
        setSaveError("You don't have permission to edit this quote.");
      } else if (/404|not found/i.test(msg)) {
        setSaveError('This request could not be found.');
      } else if (/\b400\b|rejected|invalid/i.test(msg)) {
        setSaveError(msg || 'The quote update was rejected.');
      } else {
        setSaveError("Couldn't save the quote. Please try again.");
      }
      // Preserve entered form values on error (do not clear inputs).
      setIsSaving(false);
      return;
    }

    // Phase 2: authoritative reconciliation. The PATCH already SUCCEEDED, so a
    // failure here must NOT be reported as a save failure. We surface a
    // non-destructive warning and keep the current (now-stale) displayed metadata
    // without fabricating any post-save quote_status/revision. The authoritative
    // source remains the reloaded REQUEST; the user is told to reopen to see it.
    try {
      if (onQuoteUpdated) {
        await onQuoteUpdated(requestId);
      }
    } catch (refreshErr) {
      console.error('Quote saved, but authoritative refresh failed:', refreshErr);
      setSaveWarning(
        'Quote saved, but the latest quote state could not be refreshed. '
        + 'Reopen this request to see the current status.'
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveClick = () => {
    setFieldError('');
    setSaveError('');
    const built = buildPayload();
    if (built.error) {
      setFieldError(built.error);
      return;
    }
    const commercial = isCommercialChange(built.payload);
    // A commercial change to a live (SENT/ACCEPTED) quote requires explicit
    // confirmation because it creates a new revision and (for ACCEPTED) invalidates
    // the client's acceptance.
    if (commercial && isLive) {
      setPendingConfirm({ payload: built.payload, isCommercial: true });
      return;
    }
    performSave(built.payload);
  };

  const confirmAndSave = () => {
    const payload = pendingConfirm?.payload;
    setPendingConfirm(null);
    if (payload) performSave(payload);
  };

  const cancelConfirm = () => setPendingConfirm(null);

  // --- W2C: Send Quote (DRAFT -> SENT) -----------------------------------------
  // Dirty detection: compare the live form against the canonical record using the
  // SAME effective-default normalization used elsewhere, so a legacy/absent record
  // field never appears dirty merely because it differs from a form default.
  // Amount/deposit are compared by parsed integer cents (so "150" vs "150.00" is not
  // dirty); other fields by their effective-normalized string value.
  const isDirty = (() => {
    // Amount: effective persisted cents vs parsed form cents.
    const persistedAmountCents = request?.quote_amount_cents != null
      ? Number(request.quote_amount_cents) : 0;
    const amountRaw = String(form.quote_amount ?? '').trim();
    const parsedAmount = amountRaw === '' ? { ok: true, cents: 0 } : parseDollarsToCents(amountRaw);
    const formAmountCents = parsedAmount.ok ? parsedAmount.cents : NaN;
    if (Number.isNaN(formAmountCents) || formAmountCents !== persistedAmountCents) return true;

    // Currency: effective 'USD'.
    if ((form.currency || 'USD').trim().toUpperCase() !== (request?.currency || 'USD')) return true;

    // Payment requirement: effective 'NONE'.
    if ((form.payment_requirement || 'NONE') !== (request?.payment_requirement || 'NONE')) return true;

    // Deposit: effective persisted cents vs parsed form cents.
    const persistedDepositCents = request?.deposit_amount_cents != null
      ? Number(request.deposit_amount_cents) : 0;
    const depRaw = String(form.deposit_amount ?? '').trim();
    const parsedDep = depRaw === '' ? { ok: true, cents: 0 } : parseDollarsToCents(depRaw);
    const formDepositCents = parsedDep.ok ? parsedDep.cents : NaN;
    if (Number.isNaN(formDepositCents) || formDepositCents !== persistedDepositCents) return true;

    // Notes: effective empty string.
    if ((form.quote_notes_client || '') !== (request?.quote_notes_client || '')) return true;
    if ((form.quote_notes_internal || '') !== (request?.quote_notes_internal || '')) return true;
    if ((form.internal_pricing_notes || '') !== (request?.internal_pricing_notes || '')) return true;

    return false;
  })();

  // Persisted canonical amount (cents) is the authority for send eligibility — the
  // backend sends persisted state, not unsaved form values.
  const persistedAmountCents = request?.quote_amount_cents != null
    ? Number(request.quote_amount_cents) : 0;
  const persistedAmountPositive = Number.isSafeInteger(persistedAmountCents) && persistedAmountCents > 0;

  // Send is exposed ONLY for a persisted DRAFT (W2C scope). No Resend on SENT.
  const canSendState = status === 'DRAFT';
  const sendBlockedReason = (() => {
    if (!canSendState) return null;
    if (isDirty) return 'Save your changes before sending.';
    if (!persistedAmountPositive) return 'Set a quote amount greater than $0 and save before sending.';
    return null;
  })();
  const canSend = EDITABLE_ROLES.includes(userRole) && canSendState && !isDirty && persistedAmountPositive;

  const performSend = async () => {
    setIsSending(true);
    setSendError('');
    setSendWarning('');
    // Phase 1: the send POST. A failure here means the quote was NOT sent.
    try {
      await sendAdminRequestQuote(requestId);
    } catch (err) {
      const msg = String(err?.message || '');
      if (/409|conflict|changed since/i.test(msg)) {
        setSendError(
          'This quote changed before it could be sent. Refresh the request and review '
          + 'the latest draft before sending.'
        );
        // Authoritatively refresh so the owner sees the current draft; do NOT retry
        // the POST and do NOT resend a stale revision.
        try {
          if (onQuoteUpdated) await onQuoteUpdated(requestId);
        } catch (refreshErr) {
          console.error('Send conflict refresh failed:', refreshErr);
          setSendWarning('The latest quote state could not be refreshed. Reopen this request.');
        }
        setIsSending(false);
        return;
      }
      if (/403|forbidden/i.test(msg)) {
        setSendError("You don't have permission to send this quote.");
      } else if (/404|not found/i.test(msg)) {
        setSendError('This request could not be found.');
      } else if (/\b400\b|rejected|invalid/i.test(msg)) {
        setSendError(msg || 'The quote could not be sent.');
      } else {
        setSendError("Couldn't send the quote. Please try again.");
      }
      setIsSending(false);
      return;
    }

    // Phase 2: authoritative reconciliation. The send already SUCCEEDED, so a refresh
    // failure must NOT be reported as a send failure. No fabricated SENT status.
    try {
      if (onQuoteUpdated) {
        await onQuoteUpdated(requestId);
      }
    } catch (refreshErr) {
      console.error('Quote sent, but authoritative refresh failed:', refreshErr);
      setSendWarning(
        'Quote was sent, but the latest quote state could not be refreshed. '
        + 'Reopen this request to see the current status.'
      );
    } finally {
      setIsSending(false);
    }
  };

  const handleSendClick = () => {
    setSendError('');
    setSendWarning('');
    if (!canSend) return;
    setPendingSendConfirm(true);
  };

  const confirmAndSend = () => {
    setPendingSendConfirm(false);
    performSend();
  };

  const cancelSendConfirm = () => setPendingSendConfirm(false);

  // Save button label by state and pending-change kind.
  const pendingBuilt = null; // computed lazily in label logic to avoid double-build
  const saveLabel = (() => {
    if (noQuote || status === 'DRAFT') return 'Save Draft';
    if (isLive) {
      // Internal-only edit uses "Save Notes"; a commercial edit uses "Save Revised Draft".
      const built = buildPayload();
      if (!built.error && !isCommercialChange(built.payload)) return 'Save Notes';
      return 'Save Revised Draft';
    }
    return 'Save';
  })();
  void pendingBuilt;

  // --- Render ------------------------------------------------------------------

  const statusLabel = status || 'No quote yet';

  const Metadata = (
    <div className="aqe-metadata" style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', fontSize: '0.85rem', color: 'var(--text-muted, #6c757d)', marginBottom: '12px' }}>
      <span data-testid="aqe-status"><strong>Status:</strong> {statusLabel}</span>
      {revision != null && <span data-testid="aqe-revision"><strong>Revision:</strong> {revision}</span>}
      {request?.quote_sent_at && <span><strong>Sent:</strong> {formatTimestamp(request.quote_sent_at)}</span>}
      {request?.quote_accepted_at && <span><strong>Accepted:</strong> {formatTimestamp(request.quote_accepted_at)}</span>}
      {request?.quote_declined_at && <span><strong>Declined:</strong> {formatTimestamp(request.quote_declined_at)}</span>}
    </div>
  );

  // Display-only states: show canonical state, no editable commercial controls.
  if (isDisplayOnlyState) {
    return (
      <section className="card-section aqe-root" data-testid="admin-quote-editor" style={{ marginTop: '24px' }}>
        <h3>Quote</h3>
        <div className="content-box">
          {Metadata}
          <p data-testid="aqe-display-only" style={{ fontSize: '0.9rem' }}>
            {status === 'NOT_REQUIRED' && 'This booking does not require a quote.'}
            {status === 'DECLINED' && 'The client declined this quote. Re-quoting a declined quote is not available in this release.'}
            {status === 'SUPERSEDED' && 'This quote revision has been superseded.'}
          </p>
          <div className="aqe-readonly" style={{ marginTop: '12px', fontSize: '0.9rem' }}>
            <p><strong>Amount:</strong> {request?.quote_amount_cents != null ? `${centsToDollars(request.quote_amount_cents)} ${request?.currency || 'USD'}` : '—'}</p>
            {request?.payment_requirement && <p><strong>Payment requirement:</strong> {request.payment_requirement}</p>}
            {request?.deposit_amount_cents ? <p><strong>Deposit:</strong> {centsToDollars(request.deposit_amount_cents)}</p> : null}
            {request?.quote_notes_client && <p><strong>Client note:</strong> {request.quote_notes_client}</p>}
          </div>
        </div>
      </section>
    );
  }

  const confirmCopy = (() => {
    if (!pendingConfirm) return '';
    if (status === 'ACCEPTED') {
      return 'This is a commercial change to an accepted quote. Saving will invalidate the client\u2019s acceptance, create a new revision, return the quote to draft, and it must be re-sent.';
    }
    // SENT
    return 'This is a commercial change to a sent quote. Saving will create a new revision, return the quote to draft, and it will need to be re-sent.';
  })();

  return (
    <section className="card-section aqe-root" data-testid="admin-quote-editor" style={{ marginTop: '24px' }}>
      <h3>Quote</h3>
      <div className="content-box">
        {Metadata}

        <div className="grid-2">
          <div className="aqe-field">
            <label className="micro-text" htmlFor="aqe-amount">Quote Amount{noQuote ? ' (required)' : ''}</label>
            <input
              id="aqe-amount"
              type="text"
              inputMode="decimal"
              aria-label="Quote amount in dollars"
              value={form.quote_amount}
              placeholder="0.00"
              disabled={!canEdit || isSaving}
              onChange={(e) => setField('quote_amount', e.target.value)}
              style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }}
            />
          </div>
          <div className="aqe-field">
            <label className="micro-text" htmlFor="aqe-currency">Currency</label>
            <input
              id="aqe-currency"
              type="text"
              aria-label="Currency"
              value={form.currency}
              disabled={!canEdit || isSaving}
              onChange={(e) => setField('currency', e.target.value)}
              style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }}
            />
          </div>
        </div>

        <div className="grid-2" style={{ marginTop: '12px' }}>
          <div className="aqe-field">
            <label className="micro-text" htmlFor="aqe-payreq">Payment Requirement</label>
            <select
              id="aqe-payreq"
              aria-label="Payment requirement"
              value={form.payment_requirement}
              disabled={!canEdit || isSaving}
              onChange={(e) => setField('payment_requirement', e.target.value)}
              style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }}
            >
              {PAYMENT_REQUIREMENTS.map((pr) => (
                <option key={pr} value={pr}>{pr}</option>
              ))}
            </select>
          </div>
          {showDeposit && (
            <div className="aqe-field">
              <label className="micro-text" htmlFor="aqe-deposit">Deposit Amount</label>
              <input
                id="aqe-deposit"
                type="text"
                inputMode="decimal"
                aria-label="Deposit amount in dollars"
                value={form.deposit_amount}
                placeholder="0.00"
                disabled={!canEdit || isSaving}
                onChange={(e) => setField('deposit_amount', e.target.value)}
                style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }}
              />
            </div>
          )}
        </div>

        <div style={{ marginTop: '12px' }}>
          <label className="micro-text" htmlFor="aqe-notes-client">Client-facing Note</label>
          <textarea
            id="aqe-notes-client"
            rows="2"
            aria-label="Client-facing note"
            value={form.quote_notes_client}
            disabled={!canEdit || isSaving}
            onChange={(e) => setField('quote_notes_client', e.target.value)}
            style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)', marginTop: '4px' }}
          />
        </div>

        <div style={{ marginTop: '12px' }}>
          <label className="micro-text" htmlFor="aqe-notes-internal">Internal Note (not client-visible)</label>
          <textarea
            id="aqe-notes-internal"
            rows="2"
            aria-label="Internal note"
            value={form.quote_notes_internal}
            disabled={!canEdit || isSaving}
            onChange={(e) => setField('quote_notes_internal', e.target.value)}
            style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)', marginTop: '4px' }}
          />
        </div>

        <div style={{ marginTop: '12px' }}>
          <label className="micro-text" htmlFor="aqe-notes-pricing">Internal Pricing Note (not client-visible)</label>
          <textarea
            id="aqe-notes-pricing"
            rows="2"
            aria-label="Internal pricing note"
            value={form.internal_pricing_notes}
            disabled={!canEdit || isSaving}
            onChange={(e) => setField('internal_pricing_notes', e.target.value)}
            style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)', marginTop: '4px' }}
          />
        </div>

        {fieldError && (
          <p data-testid="aqe-field-error" role="alert" style={{ color: 'var(--danger, #dc2626)', fontSize: '0.85rem', marginTop: '12px' }}>{fieldError}</p>
        )}
        {saveError && (
          <p data-testid="aqe-save-error" role="alert" style={{ color: 'var(--danger, #dc2626)', fontSize: '0.85rem', marginTop: '12px' }}>{saveError}</p>
        )}
        {saveWarning && (
          <p data-testid="aqe-save-warning" role="status" style={{ color: 'var(--warning, #b45309)', fontSize: '0.85rem', marginTop: '12px' }}>{saveWarning}</p>
        )}
        {sendError && (
          <p data-testid="aqe-send-error" role="alert" style={{ color: 'var(--danger, #dc2626)', fontSize: '0.85rem', marginTop: '12px' }}>{sendError}</p>
        )}
        {sendWarning && (
          <p data-testid="aqe-send-warning" role="status" style={{ color: 'var(--warning, #b45309)', fontSize: '0.85rem', marginTop: '12px' }}>{sendWarning}</p>
        )}

        <div style={{ marginTop: '16px', display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn-small primary"
            data-testid="aqe-save"
            disabled={!canEdit || isSaving}
            onClick={handleSaveClick}
          >
            {isSaving ? 'Saving\u2026' : saveLabel}
          </button>
          {/* W2C: Send Quote (DRAFT -> SENT only). No Resend control on SENT. */}
          {canSendState && (
            <button
              type="button"
              className="btn-small primary-outline"
              data-testid="aqe-send"
              disabled={!canSend || isSending}
              onClick={handleSendClick}
            >
              {isSending ? 'Sending\u2026' : 'Send Quote'}
            </button>
          )}
          {canSendState && sendBlockedReason && (
            <span data-testid="aqe-send-blocked" style={{ fontSize: '0.8rem', color: 'var(--text-muted, #6c757d)' }}>{sendBlockedReason}</span>
          )}
        </div>
      </div>

      {pendingConfirm && (
        <div className="aqe-confirm" role="dialog" aria-modal="true" data-testid="aqe-confirm" style={{ marginTop: '16px', padding: '16px', border: '1px solid var(--border)', borderRadius: '8px', background: 'rgba(245,158,11,0.08)' }}>
          <p data-testid="aqe-confirm-copy" style={{ fontSize: '0.9rem', marginBottom: '12px' }}>{confirmCopy}</p>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button type="button" className="btn-small primary" data-testid="aqe-confirm-save" disabled={isSaving} onClick={confirmAndSave}>
              Confirm & Save Revised Draft
            </button>
            <button type="button" className="btn-small primary-outline" data-testid="aqe-confirm-cancel" disabled={isSaving} onClick={cancelConfirm}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {pendingSendConfirm && (
        <div className="aqe-send-confirm" role="dialog" aria-modal="true" data-testid="aqe-send-confirm" style={{ marginTop: '16px', padding: '16px', border: '1px solid var(--border)', borderRadius: '8px', background: 'rgba(37,99,235,0.08)' }}>
          <p data-testid="aqe-send-confirm-copy" style={{ fontSize: '0.9rem', marginBottom: '8px' }}>Send this quote to the client?</p>
          {/* Summary uses PERSISTED canonical request values, not unsaved form state. */}
          <div data-testid="aqe-send-summary" style={{ fontSize: '0.85rem', marginBottom: '12px' }}>
            <p><strong>Total:</strong> {centsToDollars(request?.quote_amount_cents)} {request?.currency || 'USD'}</p>
            <p><strong>Payment requirement:</strong> {request?.payment_requirement || 'NONE'}</p>
            {(request?.payment_requirement === 'DEPOSIT') && (
              <p><strong>Deposit:</strong> {centsToDollars(request?.deposit_amount_cents)} {request?.currency || 'USD'}</p>
            )}
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button type="button" className="btn-small primary" data-testid="aqe-send-confirm-ok" disabled={isSending} onClick={confirmAndSend}>
              Send Quote
            </button>
            <button type="button" className="btn-small primary-outline" data-testid="aqe-send-confirm-cancel" disabled={isSending} onClick={cancelSendConfirm}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
