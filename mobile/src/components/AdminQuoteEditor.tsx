import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, View, Text, TextInput, TouchableOpacity } from 'react-native';
import { COLORS } from '../theme/colors';
import { ConfirmationModal } from './ConfirmationModal';
import { getAdminRequest, sendAdminQuote, updateAdminQuote } from '../api/client';
import { centsToDollars, formatQuoteMoney, parseDollarsToCents } from '../utils/quoteMoney';
import type { AdminQuoteUpdatePayload } from '../types';

/**
 * S1 / S1-R1: owner/admin mobile quote editor (create/edit a DRAFT quote and send it).
 *
 * Uses the already-deployed admin quote contract:
 *   PATCH /admin/requests/{id}/quote        (last-write-wins; NO expected_revision)
 *   POST  /admin/requests/{id}/quote/send   (DRAFT -> SENT; server 409 on a concurrent change)
 *   GET   /admin/requests/{id}?clientId=    (authoritative REQUEST incl. quote fields)
 *
 * Safety model:
 *  - Owner/admin only; every other role (staff, client, unknown, null) renders nothing.
 *    The backend remains the authoritative 403 boundary.
 *  - S1-R1: the editor never trusts the navigation/list `request` for quote state. On open
 *    it performs an authoritative read ("hydration") and keeps its own server snapshot.
 *    No inputs, Save or Send are available until hydration succeeds; a failed hydration
 *    shows a truthful error and an explicit, read-only Retry.
 *  - Editable only when there is no canonical quote yet or it is DRAFT. SENT, ACCEPTED,
 *    DECLINED, NOT_REQUIRED, SUPERSEDED and unknown states are display-only, so mobile
 *    can never create a new commercial revision or reset an acceptance.
 *  - Before every save/send the request is re-read and compared with the version the
 *    user's edits are based on. A difference is refused. This is a CLIENT-SIDE check only;
 *    the PATCH endpoint does not enforce a revision guard on the server.
 *  - Unsaved edits are never silently overwritten by a refresh. If the server quote moved
 *    while the user has edits, the edits are kept and the user explicitly chooses to keep
 *    them (and save over the latest version) or discard them.
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

const QUOTE_KEYS = [
  'quote_status', 'quote_revision', 'quote_amount_cents', 'currency', 'deposit_amount_cents',
  'payment_requirement', 'quote_notes_client', 'quote_notes_internal', 'internal_pricing_notes',
  'quote_sent_at', 'quote_accepted_at',
];

/** True when a record actually carries canonical quote state (not an incomplete list item). */
const carriesQuoteState = (r: any) =>
  r?.quote_status !== undefined && r?.quote_status !== null;

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

const centsOrNaN = (raw: string) => {
  if (raw.trim() === '') return 0;
  const p = parseDollarsToCents(raw);
  return p.ok ? p.cents : NaN;
};

/** Whether `form` differs from the persisted quote in `record` (by integer cents, not strings). */
const formDiffersFrom = (form: FormState, record: any): boolean => {
  const persistedAmount = record?.quote_amount_cents != null ? Number(record.quote_amount_cents) : 0;
  const persistedDeposit = record?.deposit_amount_cents != null ? Number(record.deposit_amount_cents) : 0;
  const a = centsOrNaN(form.amount);
  if (Number.isNaN(a) || a !== persistedAmount) return true;
  if ((form.currency || 'USD').trim().toUpperCase() !== (record?.currency || 'USD')) return true;
  if (form.paymentRequirement !== (record?.payment_requirement || 'NONE')) return true;
  const d = centsOrNaN(form.deposit);
  if (Number.isNaN(d) || d !== persistedDeposit) return true;
  if (form.notesClient !== (record?.quote_notes_client || '')) return true;
  if (form.notesInternal !== (record?.quote_notes_internal || '')) return true;
  if (form.pricingNotes !== (record?.internal_pricing_notes || '')) return true;
  return false;
};

const STATUS_LABEL: Record<string, string> = {
  DRAFT: 'Draft (not sent)',
  SENT: 'Sent to client',
  ACCEPTED: 'Accepted by client',
  DECLINED: 'Declined by client',
  NOT_REQUIRED: 'No quote required',
  SUPERSEDED: 'Superseded',
};

type Hydration = 'loading' | 'ready' | 'failed';

interface InnerProps {
  request: any;
  onRequestRefreshed: (fresh: any) => void;
  onSessionExpired?: () => void | Promise<void>;
}

const AdminQuoteEditorInner: React.FC<InnerProps> = ({ request, onRequestRefreshed, onSessionExpired }) => {
  const requestId: string = request?.request_id;
  const clientId: string = request?.client_id;

  // Authoritative server snapshot (S1-R1). All gating, dirty checks and the stale check
  // use this, never the navigation/list `request` prop.
  const [hydration, setHydration] = useState<Hydration>('loading');
  const [hydrationError, setHydrationError] = useState('');
  const [server, setServer] = useState<any>(null);
  const [form, setForm] = useState<FormState>(() => formFromRecord(null));
  // Fingerprint of the server version the current form edits are based on.
  const [baseFp, setBaseFp] = useState<string>('');
  const [conflict, setConflict] = useState(false);

  const [busy, setBusy] = useState<null | 'save' | 'send'>(null);
  const [fieldError, setFieldError] = useState('');
  const [error, setError] = useState('');
  const [warning, setWarning] = useState('');
  const [notice, setNotice] = useState('');
  const [showSendConfirm, setShowSendConfirm] = useState(false);

  const busyRef = useRef(false);
  const mountedRef = useRef(true);
  const hydrateSeqRef = useRef(0);
  // Refs mirror state so async handlers decide on the latest values.
  const serverRef = useRef<any>(null);
  const formRef = useRef<FormState>(form);
  const baseFpRef = useRef<string>('');
  formRef.current = form;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      hydrateSeqRef.current += 1;
    };
  }, []);

  const clearMessages = () => {
    setFieldError('');
    setError('');
    setWarning('');
    setNotice('');
  };

  /** Adopt `fresh` and reset the form to it (used after hydration and successful mutations). */
  const adoptAndReset = (fresh: any) => {
    const fp = quoteFingerprint(fresh);
    serverRef.current = fresh;
    baseFpRef.current = fp;
    setServer(fresh);
    setBaseFp(fp);
    setForm(formFromRecord(fresh));
    setConflict(false);
  };

  /**
   * Adopt `fresh` WITHOUT discarding unsaved input. If the user has no edits against the
   * version they started from, the form follows the server. If they do, edits are kept;
   * when the server moved underneath them, a conflict is raised for an explicit choice.
   * Returns 'reset' | 'kept' | 'conflict'.
   */
  const adoptPreservingEdits = (fresh: any): 'reset' | 'kept' | 'conflict' => {
    const hasEdits = formDiffersFrom(formRef.current, serverRef.current);
    // No edits, or the edits already equal the new server state (e.g. an uncertain
    // save that actually landed): follow the server; nothing would be lost.
    if (!hasEdits || !formDiffersFrom(formRef.current, fresh)) {
      adoptAndReset(fresh);
      return 'reset';
    }
    serverRef.current = fresh;
    setServer(fresh);
    if (quoteFingerprint(fresh) !== baseFpRef.current) {
      setConflict(true);
      return 'conflict';
    }
    return 'kept';
  };

  const readAuthoritative = async (): Promise<any> => {
    const fresh = await getAdminRequest(requestId, clientId);
    if (!fresh || fresh.request_id !== requestId) {
      throw new Error('Booking identity could not be confirmed.');
    }
    return fresh;
  };

  // ---- initial / explicit-retry hydration (read-only) ------------------------------
  const hydrate = useCallback(async () => {
    const seq = ++hydrateSeqRef.current;
    setHydration('loading');
    setHydrationError('');
    try {
      const fresh = await readAuthoritative();
      if (!mountedRef.current || seq !== hydrateSeqRef.current) return;
      adoptAndReset(fresh);
      setHydration('ready');
      onRequestRefreshed(fresh);
    } catch (err: any) {
      if (!mountedRef.current || seq !== hydrateSeqRef.current) return;
      setHydration('failed');
      if (err?.status === 401) {
        setHydrationError('Your session expired. Please sign in again.');
        if (onSessionExpired) await onSessionExpired();
        return;
      }
      setHydrationError(
        err?.status === 403
          ? "You don't have permission to view this quote."
          : err?.status === 404
            ? 'This request could not be found.'
            : "We couldn't load the latest quote, so editing is unavailable. Nothing has been changed."
      );
    }
  }, [requestId, clientId]); // keyed on request identity only; callbacks are read at call time

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  // ---- background refresh from the screen (e.g. PR #46 "Refresh booking") ----------
  // Only records that actually carry canonical quote state are considered, so an
  // incomplete list payload can never wipe or "stale" the hydrated snapshot.
  const propFp = quoteFingerprint(request);
  useEffect(() => {
    if (hydration !== 'ready' || busyRef.current) return;
    if (!carriesQuoteState(request)) return;
    if (propFp === quoteFingerprint(serverRef.current)) return;
    const outcome = adoptPreservingEdits(request);
    if (outcome === 'conflict') {
      setWarning('The saved quote was updated elsewhere. Your unsaved changes were kept; choose whether to keep or discard them.');
    }
  }, [propFp, hydration]); // keyed on the prop's canonical quote fingerprint only

  const edit = (patch: Partial<FormState>) => {
    setForm(prev => ({ ...prev, ...patch }));
    clearMessages();
  };

  // ---- derived state from the authoritative snapshot ------------------------------
  const status: string | null = server?.quote_status ?? null;
  const noQuote = status === null;
  const isEditable = noQuote || status === 'DRAFT';
  const isDirty = hydration === 'ready' && formDiffersFrom(form, server);
  const persistedAmountCents = server?.quote_amount_cents != null ? Number(server.quote_amount_cents) : 0;
  const persistedAmountPositive = Number.isSafeInteger(persistedAmountCents) && persistedAmountCents > 0;

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

  /** Pre-mutation guard: the server must still equal the version the edits are based on. */
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
    if (quoteFingerprint(fresh) !== baseFpRef.current) {
      const outcome = adoptPreservingEdits(fresh);
      onRequestRefreshed(fresh);
      setError(
        outcome === 'conflict'
          ? 'This quote changed since it was loaded (for example on the web or another device). '
            + 'Nothing was changed. Your unsaved changes were kept; choose whether to keep or discard them.'
          : 'This quote changed since it was loaded (for example on the web or another device). '
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
      adoptAndReset(fresh);
      onRequestRefreshed(fresh);
      setNotice(done);
    } catch {
      if (!mountedRef.current) return;
      setWarning(`${done} However, the latest quote state could not be refreshed. Use Refresh booking to see the current status.`);
    }
  };

  /** Safe read-only reload after an error; never discards unsaved input. */
  const reloadLatestQuietly = async (): Promise<boolean> => {
    try {
      const fresh = await readAuthoritative();
      if (!mountedRef.current) return false;
      adoptPreservingEdits(fresh);
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
    if (busyRef.current || hydration !== 'ready' || !isEditable || conflict) return;
    clearMessages();
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

  const canSend = hydration === 'ready' && isEditable && status === 'DRAFT' && !isDirty
    && !conflict && persistedAmountPositive && !busy;
  const sendBlockedReason = (() => {
    if (status !== 'DRAFT') return null;
    if (conflict) return 'Keep or discard your changes before sending.';
    if (isDirty) return 'Save your changes before sending.';
    if (!persistedAmountPositive) return 'Set a quote amount greater than 0 and save before sending.';
    return null;
  })();

  const handleSend = async () => {
    setShowSendConfirm(false);
    if (busyRef.current || !canSend) return;
    clearMessages();
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

  /** Explicit choice: keep my edits and base them on the latest server version. */
  const keepMyChanges = () => {
    const fp = quoteFingerprint(serverRef.current);
    baseFpRef.current = fp;
    setBaseFp(fp);
    setConflict(false);
    clearMessages();
    setNotice('Your changes are kept. Saving will replace the latest saved quote.');
  };

  /** Explicit choice: discard my edits and show the latest server version. */
  const discardMyChanges = () => {
    adoptAndReset(serverRef.current);
    clearMessages();
    setNotice('Your unsaved changes were discarded. The latest quote is shown.');
  };

  // ---- render ---------------------------------------------------------------------
  const messages = (
    <>
      {!!fieldError && <Text accessibilityRole="alert" style={styles.errorText}>{fieldError}</Text>}
      {!!error && <Text accessibilityRole="alert" style={styles.errorText}>{error}</Text>}
      {!!warning && <Text accessibilityRole="alert" style={styles.warningText}>{warning}</Text>}
      {!!notice && <Text style={styles.noticeText}>{notice}</Text>}
    </>
  );

  if (hydration === 'loading') {
    return (
      <View style={styles.card} testID="admin-quote-loading">
        <Text style={styles.sectionHeader} accessibilityRole="header">Quote</Text>
        <Text style={styles.muted} accessibilityLiveRegion="polite">Loading the latest quote…</Text>
      </View>
    );
  }

  if (hydration === 'failed') {
    return (
      <View style={styles.card} testID="admin-quote-load-failed">
        <Text style={styles.sectionHeader} accessibilityRole="header">Quote</Text>
        <Text accessibilityRole="alert" style={styles.errorText}>{hydrationError}</Text>
        <TouchableOpacity
          style={styles.secondaryBtn}
          accessibilityRole="button"
          accessibilityLabel="Retry loading quote"
          onPress={hydrate}
        >
          <Text style={styles.secondaryBtnText}>Retry loading quote</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const statusText = noQuote ? 'No quote yet' : (STATUS_LABEL[status as string] || `Status unavailable (${status})`);

  if (!isEditable) {
    return (
      <View style={styles.card} testID="admin-quote-readonly">
        <Text style={styles.sectionHeader} accessibilityRole="header">Quote</Text>
        <Text style={styles.line}>Status: {statusText}</Text>
        {status !== 'NOT_REQUIRED' && (
          <>
            <Text style={styles.line}>Total: {formatQuoteMoney(server?.quote_amount_cents, server?.currency)}</Text>
            {server?.payment_requirement ? <Text style={styles.line}>Payment requirement: {server.payment_requirement}</Text> : null}
            {server?.payment_requirement === 'DEPOSIT'
              ? <Text style={styles.line}>Deposit: {formatQuoteMoney(server?.deposit_amount_cents, server?.currency)}</Text>
              : null}
            {server?.quote_notes_client ? <Text style={styles.line}>Client notes: {server.quote_notes_client}</Text> : null}
            {server?.quote_notes_internal ? <Text style={styles.line}>Internal notes: {server.quote_notes_internal}</Text> : null}
            {server?.internal_pricing_notes ? <Text style={styles.line}>Internal pricing notes: {server.internal_pricing_notes}</Text> : null}
          </>
        )}
        {server?.quote_sent_at ? <Text style={styles.muted}>Sent {server.quote_sent_at}</Text> : null}
        {server?.quote_accepted_at ? <Text style={styles.muted}>Accepted {server.quote_accepted_at}</Text> : null}
        <Text style={styles.muted}>
          This quote can't be changed on mobile once it has been sent or decided.
        </Text>
        {messages}
      </View>
    );
  }

  const inputsDisabled = !!busy;
  const saveDisabled = inputsDisabled || !isDirty || conflict;
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

      {conflict && (
        <View style={styles.conflictBox} testID="admin-quote-conflict">
          <Text style={styles.line}>
            The saved quote changed while you were editing. Latest saved total:{' '}
            {formatQuoteMoney(server?.quote_amount_cents, server?.currency)}.
          </Text>
          <TouchableOpacity
            style={styles.secondaryBtn}
            accessibilityRole="button"
            accessibilityLabel="Keep my changes"
            disabled={inputsDisabled}
            onPress={keepMyChanges}
          >
            <Text style={styles.secondaryBtnText}>Keep my changes</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={styles.secondaryBtn}
            accessibilityRole="button"
            accessibilityLabel="Discard my changes"
            disabled={inputsDisabled}
            onPress={discardMyChanges}
          >
            <Text style={styles.secondaryBtnText}>Discard my changes</Text>
          </TouchableOpacity>
        </View>
      )}

      <TouchableOpacity
        style={[styles.primaryBtn, saveDisabled && styles.btnDisabled]}
        accessibilityRole="button"
        accessibilityLabel="Save quote draft"
        accessibilityState={{ disabled: saveDisabled }}
        disabled={saveDisabled}
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
        message={`This sends the saved quote (${formatQuoteMoney(persistedAmountCents, server?.currency)}) to the client for acceptance. Sending does not approve or schedule the booking. A sent quote can't be edited on mobile.`}
        onConfirm={handleSend}
        onCancel={() => setShowSendConfirm(false)}
        isLoading={false}
      />
    </View>
  );
};

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

/** Owner/admin gate. Staff, client, unknown and null roles render nothing and make no calls. */
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
  conflictBox: {
    marginTop: 12,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.danger,
  },
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
