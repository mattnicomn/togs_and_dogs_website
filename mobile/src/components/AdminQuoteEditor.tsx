import React, { useEffect, useRef, useState } from 'react';
import { StyleSheet, View, Text, TextInput, TouchableOpacity } from 'react-native';
import { COLORS } from '../theme/colors';
import { ConfirmationModal } from './ConfirmationModal';
import { getAdminRequest, sendAdminQuote, updateAdminQuote } from '../api/client';
import { centsToDollars, formatQuoteMoney, parseDollarsToCents } from '../utils/quoteMoney';
import type { AdminQuoteUpdatePayload } from '../types';

/**
 * S1: owner/admin mobile quote editor (create/edit a DRAFT quote and send it).
 *
 * Uses the already-deployed admin quote contract:
 *   PATCH /admin/requests/{id}/quote        (last-write-wins; NO expected_revision)
 *   POST  /admin/requests/{id}/quote/send   (DRAFT -> SENT; server 409 on a concurrent change)
 *
 * Safety model:
 *  - Owner/admin only; every other role (staff, client, unknown, null) renders nothing.
 *    The backend remains the authoritative 403 boundary.
 *  - Editable only when there is no canonical quote yet or it is DRAFT. SENT, ACCEPTED,
 *    DECLINED, NOT_REQUIRED, SUPERSEDED and unknown states are display-only, so mobile
 *    can never create a new commercial revision or reset an acceptance.
 *  - Before every save/send the authoritative request is re-read and compared with what
 *    is displayed. A difference is refused and the latest data is loaded. This is a
 *    CLIENT-SIDE check only; the PATCH endpoint is not server-enforced for staleness.
 *  - A mutation is never retried automatically. When the outcome is uncertain (network
 *    failure / 5xx) the quote is re-read (a safe GET) and the user is told to verify.
 *  - After a successful mutation the request is re-read; if that re-read fails the user
 *    is told the mutation SUCCEEDED but the refresh did not.
 */

export const canEditQuotes = (role: string | null | undefined) => role === 'owner' || role === 'admin';

const PAYMENT_REQUIREMENTS: Array<{ value: 'NONE' | 'DEPOSIT' | 'FULL'; label: string }> = [
  { value: 'NONE', label: 'None' },
  { value: 'DEPOSIT', label: 'Deposit' },
  { value: 'FULL', label: 'Full payment' },
];

const num = (v: unknown) => (v === null || v === undefined || v === '' ? null : Number(v));

/** Canonical quote fingerprint used for the client-side stale check. */
export const quoteFingerprint = (r: any): string =>
  JSON.stringify([
    r?.quote_status ?? null,
    num(r?.quote_revision),
    num(r?.quote_amount_cents),
    r?.currency ?? null,
    num(r?.deposit_amount_cents),
    r?.payment_requirement ?? null,
    r?.quote_notes_client ?? '',
    r?.quote_notes_internal ?? '',
    r?.internal_pricing_notes ?? '',
  ]);

interface FormState {
  amount: string;
  currency: string;
  deposit: string;
  paymentRequirement: 'NONE' | 'DEPOSIT' | 'FULL';
  notesClient: string;
  notesInternal: string;
  pricingNotes: string;
}

const formFromRecord = (r: any): FormState => ({
  amount: r?.quote_amount_cents != null ? centsToDollars(r.quote_amount_cents) : '',
  currency: r?.currency || 'USD',
  deposit: r?.deposit_amount_cents != null ? centsToDollars(r.deposit_amount_cents) : '',
  paymentRequirement: (['NONE', 'DEPOSIT', 'FULL'].includes(r?.payment_requirement) ? r.payment_requirement : 'NONE'),
  notesClient: r?.quote_notes_client || '',
  notesInternal: r?.quote_notes_internal || '',
  pricingNotes: r?.internal_pricing_notes || '',
});

const STATUS_LABEL: Record<string, string> = {
  DRAFT: 'Draft (not sent)',
  SENT: 'Sent to client',
  ACCEPTED: 'Accepted by client',
  DECLINED: 'Declined by client',
  NOT_REQUIRED: 'No quote required',
  SUPERSEDED: 'Superseded',
};

interface InnerProps {
  request: any;
  onRequestRefreshed: (fresh: any) => void;
  onSessionExpired?: () => void | Promise<void>;
}

const AdminQuoteEditorInner: React.FC<InnerProps> = ({ request, onRequestRefreshed, onSessionExpired }) => {
  const requestId: string = request?.request_id;
  const status: string | null = request?.quote_status ?? null;
  const noQuote = status === null;
  const isEditable = noQuote || status === 'DRAFT';
  const fingerprint = quoteFingerprint(request);

  const [form, setForm] = useState<FormState>(() => formFromRecord(request));
  const [busy, setBusy] = useState<null | 'save' | 'send'>(null);
  const [fieldError, setFieldError] = useState('');
  const [error, setError] = useState('');
  const [warning, setWarning] = useState('');
  const [notice, setNotice] = useState('');
  const [showSendConfirm, setShowSendConfirm] = useState(false);
  const busyRef = useRef(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Re-initialise the form whenever the authoritative record changes (after a
  // save/send refresh or a conflict reload).
  useEffect(() => {
    setForm(formFromRecord(request));
  }, [fingerprint]); // intentionally keyed on the canonical quote fingerprint only

  const edit = (patch: Partial<FormState>) => {
    setForm(prev => ({ ...prev, ...patch }));
    setFieldError('');
    setError('');
    setWarning('');
    setNotice('');
  };

  // ---- persisted values / dirty detection (by integer cents, not by string) ----
  const persistedAmountCents = request?.quote_amount_cents != null ? Number(request.quote_amount_cents) : 0;
  const persistedDepositCents = request?.deposit_amount_cents != null ? Number(request.deposit_amount_cents) : 0;
  const persistedAmountPositive = Number.isSafeInteger(persistedAmountCents) && persistedAmountCents > 0;

  const centsOrNaN = (raw: string) => {
    if (raw.trim() === '') return 0;
    const p = parseDollarsToCents(raw);
    return p.ok ? p.cents : NaN;
  };
  const isDirty = (() => {
    const a = centsOrNaN(form.amount);
    if (Number.isNaN(a) || a !== persistedAmountCents) return true;
    if ((form.currency || 'USD').trim().toUpperCase() !== (request?.currency || 'USD')) return true;
    if (form.paymentRequirement !== (request?.payment_requirement || 'NONE')) return true;
    const d = centsOrNaN(form.deposit);
    if (Number.isNaN(d) || d !== persistedDepositCents) return true;
    if (form.notesClient !== (request?.quote_notes_client || '')) return true;
    if (form.notesInternal !== (request?.quote_notes_internal || '')) return true;
    if (form.pricingNotes !== (request?.internal_pricing_notes || '')) return true;
    return false;
  })();

  // ---- payload ----------------------------------------------------------------
  const buildPayload = (): { payload: AdminQuoteUpdatePayload } | { error: string } => {
    const payload: any = {};
    const amountProvided = form.amount.trim() !== '';
    if (noQuote || amountProvided) {
      const parsed = parseDollarsToCents(form.amount);
      if (!parsed.ok) return { error: `Quote amount: ${parsed.error}` };
      payload.quote_amount_cents = parsed.cents;
    }
    const currency = (form.currency || 'USD').trim().toUpperCase() || 'USD';
    if (!/^[A-Z]{3}$/.test(currency)) return { error: 'Currency must be a 3-letter code such as USD.' };
    payload.currency = currency;
    payload.payment_requirement = form.paymentRequirement;
    if (form.paymentRequirement === 'DEPOSIT') {
      const dep = parseDollarsToCents(form.deposit);
      if (!dep.ok) return { error: `Deposit amount: ${dep.error}` };
      if (dep.cents <= 0) return { error: 'Deposit amount must be greater than 0 when a deposit is required.' };
      if (payload.quote_amount_cents != null && dep.cents > payload.quote_amount_cents) {
        return { error: 'Deposit amount cannot exceed the quote total.' };
      }
      payload.deposit_amount_cents = dep.cents;
    } else {
      payload.deposit_amount_cents = 0;
    }
    payload.quote_notes_client = form.notesClient || '';
    payload.quote_notes_internal = form.notesInternal || '';
    payload.internal_pricing_notes = form.pricingNotes || '';
    return { payload: payload as AdminQuoteUpdatePayload };
  };

  // ---- authoritative reads ------------------------------------------------------
  const readAuthoritative = async (): Promise<any> => {
    const fresh = await getAdminRequest(request.request_id, request.client_id);
    if (!fresh || fresh.request_id !== request.request_id) {
      throw new Error('Booking identity could not be confirmed.');
    }
    return fresh;
  };

  /** Pre-mutation guard. Returns true only when the displayed quote matches the server. */
  const guardAgainstStale = async (): Promise<boolean> => {
    let fresh: any;
    try {
      fresh = await readAuthoritative();
    } catch {
      if (mountedRef.current) {
        setError("Couldn't verify the latest quote, so nothing was changed. Check your connection and try again.");
      }
      return false;
    }
    if (!mountedRef.current) return false;
    if (quoteFingerprint(fresh) !== fingerprint) {
      onRequestRefreshed(fresh);
      setError(
        'This quote changed since it was loaded (for example on the web or another device). '
        + 'The latest version is now shown and nothing was changed. Review it and try again.'
      );
      return false;
    }
    return true;
  };

  /** Post-mutation reconciliation. `done` is what the user is told on success. */
  const reconcileAfterSuccess = async (done: string) => {
    try {
      const fresh = await readAuthoritative();
      if (!mountedRef.current) return;
      onRequestRefreshed(fresh);
      setNotice(done);
    } catch {
      if (!mountedRef.current) return;
      setWarning(`${done} However, the latest quote state could not be refreshed. Use Refresh booking to see the current status.`);
    }
  };

  const reloadLatestQuietly = async (): Promise<boolean> => {
    try {
      const fresh = await readAuthoritative();
      if (!mountedRef.current) return false;
      onRequestRefreshed(fresh);
      return true;
    } catch {
      return false;
    }
  };

  const handleMutationError = async (kind: 'save' | 'send', err: any) => {
    const code: number | undefined = typeof err?.status === 'number' ? err.status : undefined;
    const verb = kind === 'save' ? 'saved' : 'sent';
    const message = String(err?.message || '').trim();
    if (code === 401) {
      setError('Your session expired. Please sign in again.');
      if (onSessionExpired) await onSessionExpired();
      return;
    }
    if (code === 403) {
      setError(`You don't have permission to ${kind === 'save' ? 'edit' : 'send'} this quote.`);
    } else if (code === 404) {
      setError('This request could not be found.');
    } else if (code === 409) {
      await reloadLatestQuietly();
      setError('This quote changed before it could be sent. The latest version is shown; review it before trying again.');
    } else if (code === 400) {
      setError(message || `The quote could not be ${verb}.`);
    } else {
      // Unknown outcome (network failure, 5xx, or unexpected status). Never retry
      // automatically; re-read (a safe GET) so the user can see the true state.
      const reloaded = await reloadLatestQuietly();
      setError(
        `We couldn't confirm that the quote was ${verb}. `
        + (reloaded
          ? 'The latest quote has been reloaded; check it before trying again.'
          : 'Use Refresh booking to check its current state before trying again.')
      );
    }
  };

  // ---- actions --------------------------------------------------------------------
  const handleSave = async () => {
    if (busyRef.current || !isEditable) return;
    setFieldError('');
    setError('');
    setWarning('');
    setNotice('');
    const built = buildPayload();
    if ('error' in built) {
      setFieldError(built.error);
      return;
    }
    busyRef.current = true;
    setBusy('save');
    try {
      if (!(await guardAgainstStale())) return;
      try {
        await updateAdminQuote(requestId, built.payload);
      } catch (err) {
        if (mountedRef.current) await handleMutationError('save', err);
        return;
      }
      await reconcileAfterSuccess('Quote saved.');
    } finally {
      busyRef.current = false;
      if (mountedRef.current) setBusy(null);
    }
  };

  const canSend = isEditable && status === 'DRAFT' && !isDirty && persistedAmountPositive && !busy;
  const sendBlockedReason = (() => {
    if (status !== 'DRAFT') return null;
    if (isDirty) return 'Save your changes before sending.';
    if (!persistedAmountPositive) return 'Set a quote amount greater than 0 and save before sending.';
    return null;
  })();

  const handleSend = async () => {
    setShowSendConfirm(false);
    if (busyRef.current || !canSend) return;
    setError('');
    setWarning('');
    setNotice('');
    busyRef.current = true;
    setBusy('send');
    try {
      if (!(await guardAgainstStale())) return;
      try {
        await sendAdminQuote(requestId);
      } catch (err) {
        if (mountedRef.current) await handleMutationError('send', err);
        return;
      }
      await reconcileAfterSuccess('Quote sent to the client.');
    } finally {
      busyRef.current = false;
      if (mountedRef.current) setBusy(null);
    }
  };

  // ---- render ---------------------------------------------------------------------
  const statusText = noQuote ? 'No quote yet' : (STATUS_LABEL[status as string] || `Status unavailable (${status})`);
  const messages = (
    <>
      {!!fieldError && <Text accessibilityRole="alert" style={styles.errorText}>{fieldError}</Text>}
      {!!error && <Text accessibilityRole="alert" style={styles.errorText}>{error}</Text>}
      {!!warning && <Text accessibilityRole="alert" style={styles.warningText}>{warning}</Text>}
      {!!notice && <Text style={styles.noticeText}>{notice}</Text>}
    </>
  );

  if (!isEditable) {
    return (
      <View style={styles.card} testID="admin-quote-readonly">
        <Text style={styles.sectionHeader} accessibilityRole="header">Quote</Text>
        <Text style={styles.line}>Status: {statusText}</Text>
        {status !== 'NOT_REQUIRED' && (
          <>
            <Text style={styles.line}>Total: {formatQuoteMoney(request?.quote_amount_cents, request?.currency)}</Text>
            {request?.payment_requirement ? <Text style={styles.line}>Payment requirement: {request.payment_requirement}</Text> : null}
            {request?.payment_requirement === 'DEPOSIT'
              ? <Text style={styles.line}>Deposit: {formatQuoteMoney(request?.deposit_amount_cents, request?.currency)}</Text>
              : null}
            {request?.quote_notes_client ? <Text style={styles.line}>Client notes: {request.quote_notes_client}</Text> : null}
            {request?.quote_notes_internal ? <Text style={styles.line}>Internal notes: {request.quote_notes_internal}</Text> : null}
            {request?.internal_pricing_notes ? <Text style={styles.line}>Internal pricing notes: {request.internal_pricing_notes}</Text> : null}
          </>
        )}
        {request?.quote_sent_at ? <Text style={styles.muted}>Sent {request.quote_sent_at}</Text> : null}
        {request?.quote_accepted_at ? <Text style={styles.muted}>Accepted {request.quote_accepted_at}</Text> : null}
        <Text style={styles.muted}>
          This quote can't be changed on mobile once it has been sent or decided.
        </Text>
        {messages}
      </View>
    );
  }

  const inputsDisabled = !!busy;
  return (
    <View style={styles.card} testID="admin-quote-editor">
      <Text style={styles.sectionHeader} accessibilityRole="header">Quote</Text>
      <Text style={styles.line}>Status: {statusText}</Text>

      <Text style={styles.label}>Amount ({form.currency || 'USD'})</Text>
      <TextInput
        style={styles.input}
        accessibilityLabel="Quote amount"
        keyboardType="decimal-pad"
        placeholder="0.00"
        placeholderTextColor={COLORS.textMuted}
        value={form.amount}
        editable={!inputsDisabled}
        onChangeText={amount => edit({ amount })}
      />

      <Text style={styles.label}>Currency</Text>
      <TextInput
        style={styles.input}
        accessibilityLabel="Quote currency"
        autoCapitalize="characters"
        maxLength={3}
        value={form.currency}
        editable={!inputsDisabled}
        onChangeText={currency => edit({ currency })}
      />

      <Text style={styles.label}>Payment requirement</Text>
      <View style={styles.chipRow}>
        {PAYMENT_REQUIREMENTS.map(opt => {
          const selected = form.paymentRequirement === opt.value;
          return (
            <TouchableOpacity
              key={opt.value}
              style={[styles.chip, selected && styles.chipSelected]}
              accessibilityRole="radio"
              accessibilityState={{ selected, disabled: inputsDisabled }}
              accessibilityLabel={`Payment requirement ${opt.label}`}
              disabled={inputsDisabled}
              onPress={() => edit({ paymentRequirement: opt.value })}
            >
              <Text style={[styles.chipText, selected && styles.chipTextSelected]}>{opt.label}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {form.paymentRequirement === 'DEPOSIT' && (
        <>
          <Text style={styles.label}>Deposit amount ({form.currency || 'USD'})</Text>
          <TextInput
            style={styles.input}
            accessibilityLabel="Deposit amount"
            keyboardType="decimal-pad"
            placeholder="0.00"
            placeholderTextColor={COLORS.textMuted}
            value={form.deposit}
            editable={!inputsDisabled}
            onChangeText={deposit => edit({ deposit })}
          />
        </>
      )}

      <Text style={styles.label}>Notes shown to the client</Text>
      <TextInput
        style={[styles.input, styles.multiline]}
        accessibilityLabel="Client-facing quote notes"
        multiline
        value={form.notesClient}
        editable={!inputsDisabled}
        onChangeText={notesClient => edit({ notesClient })}
      />

      <Text style={styles.label}>Internal notes (not shown to the client)</Text>
      <TextInput
        style={[styles.input, styles.multiline]}
        accessibilityLabel="Internal quote notes"
        multiline
        value={form.notesInternal}
        editable={!inputsDisabled}
        onChangeText={notesInternal => edit({ notesInternal })}
      />

      <Text style={styles.label}>Internal pricing notes (not shown to the client)</Text>
      <TextInput
        style={[styles.input, styles.multiline]}
        accessibilityLabel="Internal pricing notes"
        multiline
        value={form.pricingNotes}
        editable={!inputsDisabled}
        onChangeText={pricingNotes => edit({ pricingNotes })}
      />

      {messages}

      <TouchableOpacity
        style={[styles.primaryBtn, (inputsDisabled || !isDirty) && styles.btnDisabled]}
        accessibilityRole="button"
        accessibilityLabel="Save quote draft"
        accessibilityState={{ disabled: inputsDisabled || !isDirty }}
        disabled={inputsDisabled || !isDirty}
        onPress={handleSave}
      >
        <Text style={styles.primaryBtnText}>{busy === 'save' ? 'Saving…' : 'Save quote draft'}</Text>
      </TouchableOpacity>

      {status === 'DRAFT' && (
        <>
          {!!sendBlockedReason && <Text style={styles.muted}>{sendBlockedReason}</Text>}
          <TouchableOpacity
            style={[styles.secondaryBtn, !canSend && styles.btnDisabled]}
            accessibilityRole="button"
            accessibilityLabel="Send quote to client"
            accessibilityState={{ disabled: !canSend }}
            disabled={!canSend}
            onPress={() => setShowSendConfirm(true)}
          >
            <Text style={styles.secondaryBtnText}>{busy === 'send' ? 'Sending…' : 'Send quote to client'}</Text>
          </TouchableOpacity>
        </>
      )}

      <ConfirmationModal
        visible={showSendConfirm}
        title="Send quote to client?"
        message={`This sends the saved quote (${formatQuoteMoney(persistedAmountCents, request?.currency)}) to the client for acceptance. Sending does not approve or schedule the booking. A sent quote can't be edited on mobile.`}
        onConfirm={handleSend}
        onCancel={() => setShowSendConfirm(false)}
        isLoading={false}
      />
    </View>
  );
};

const QUOTE_KEYS = [
  'quote_status', 'quote_revision', 'quote_amount_cents', 'currency', 'deposit_amount_cents',
  'payment_requirement', 'quote_notes_client', 'quote_notes_internal', 'internal_pricing_notes',
  'quote_sent_at', 'quote_accepted_at',
];

/**
 * Copies ONLY the quote fields (plus the derived RequestStatus mirror) from an
 * authoritative re-read onto the screen's request, so PR #46's visit/occurrence/draft
 * state is never overwritten. Quote keys absent from the server record are cleared so
 * the displayed record always converges to the server (no permanent stale mismatch).
 */
export const mergeQuoteRefresh = (previous: any, fresh: any) => {
  const next = { ...previous };
  for (const key of QUOTE_KEYS) next[key] = fresh?.[key];
  if (fresh?.status !== undefined) next.status = fresh.status;
  if (fresh?.updated_at !== undefined) next.updated_at = fresh.updated_at;
  return next;
};

interface Props {
  request: any;
  role: string | null | undefined;
  onRequestRefreshed: (fresh: any) => void;
  onSessionExpired?: () => void | Promise<void>;
}

/** Owner/admin gate. Staff, client, unknown and null roles render nothing. */
export const AdminQuoteEditor: React.FC<Props> = ({ role, ...rest }) => {
  if (!canEditQuotes(role) || !rest.request) return null;
  return <AdminQuoteEditorInner {...rest} />;
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
  },
  sectionHeader: { fontSize: 16, fontWeight: '700', color: COLORS.text, marginBottom: 8 },
  line: { fontSize: 14, color: COLORS.text, marginBottom: 4 },
  muted: { fontSize: 12, color: COLORS.textMuted, marginTop: 4 },
  label: { fontSize: 12, fontWeight: '600', color: COLORS.textMuted, marginTop: 12, marginBottom: 4 },
  input: {
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    borderRadius: 8,
    padding: 10,
    fontSize: 14,
    color: COLORS.text,
    backgroundColor: COLORS.background,
  },
  multiline: { minHeight: 64, textAlignVertical: 'top' },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
  },
  chipSelected: { backgroundColor: COLORS.primary, borderColor: COLORS.primary },
  chipText: { fontSize: 13, color: COLORS.text },
  chipTextSelected: { color: COLORS.white, fontWeight: '600' },
  errorText: { color: COLORS.danger, fontSize: 13, marginTop: 8 },
  warningText: { color: COLORS.text, fontSize: 13, marginTop: 8, fontWeight: '600' },
  noticeText: { color: COLORS.success, fontSize: 13, marginTop: 8 },
  primaryBtn: {
    backgroundColor: COLORS.primary,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 16,
  },
  primaryBtnText: { color: COLORS.white, fontWeight: '700', fontSize: 14 },
  secondaryBtn: {
    borderWidth: 1,
    borderColor: COLORS.primary,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 10,
  },
  secondaryBtnText: { color: COLORS.primary, fontWeight: '700', fontSize: 14 },
  btnDisabled: { opacity: 0.45 },
});
