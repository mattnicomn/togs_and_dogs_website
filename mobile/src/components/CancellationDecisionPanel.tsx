import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, View, Text, TextInput, TouchableOpacity } from 'react-native';
import { COLORS } from '../theme/colors';
import { ConfirmationModal } from './ConfirmationModal';
import { getAdminRequest, processCancellationDecision } from '../api/client';
import type { CancellationDecision, SyncFailureEntry } from '../types';

/**
 * S2 / D-4: owner/admin cancellation decision (Approve / Deny a client's cancellation request).
 *
 * Contract (BE-CANCEL-1): PUT /admin/cancel/decision
 *   body { request_id, client_id, decision: 'APPROVE' | 'DENY', note, cancellation_request_id? }
 *   - The server accepts a decision only while the request is CANCELLATION_REQUESTED, only
 *     the exact literals, and (when supplied) only for the same cancellation cycle id, via a
 *     conditional write. Conflicts return 409 with a machine-readable `code`.
 *   APPROVE -> request CANCELLED, child jobs CANCELLED (COMPLETED preserved, missing jobs
 *              never created), best-effort Google Calendar cleanup + staff SNS; failures are
 *              appended to REQUEST.sync_failures.
 *   DENY    -> request restored to its verified prior status (exactly APPROVED or ASSIGNED,
 *              recorded when the client requested cancellation). No job cascade, no SNS or
 *              notification. Without a verified prior status the server refuses DENY with
 *              409 LEGACY_PRIOR_STATUS_UNKNOWN.
 *   This behaviour requires BE-CANCEL-1 to be deployed before this mobile change ships.
 *
 * Mobile safety model:
 *   - Owner/admin only (explicit allowlist); every other role renders nothing.
 *   - Actions appear only after an authoritative read confirms CANCELLATION_REQUESTED and
 *     the exact request/client identity. Before submitting, the request is re-read again;
 *     any change (status, cycle id, prior status, reason, timestamp) refuses the submission.
 *   - The cycle id sent is the one from that pre-submit read; it is omitted only when the
 *     record genuinely has none (legacy) and is never invented.
 *   - D-4 / O-1 A: Deny is offered only when the read shows a verified prior status
 *     (APPROVED or ASSIGNED). Otherwise owner review is required; Approve stays available.
 *   - A DENY is reported as successful only when the re-read shows exactly that prior status.
 *   - Explicit confirmation; exact literals only; one submission at a time; never retried.
 *   - After success the request is re-read; new sync_failures entries are shown truthfully.
 *     A refresh failure after success is reported as such, never as a failed decision.
 *   - 409s are classified by `code`; uncertain outcomes (network / 5xx / unexpected) are
 *     reconciled with a safe read.
 */

export const canDecideCancellation = (role: string | null | undefined) => role === 'owner' || role === 'admin';

const REQUESTED = 'CANCELLATION_REQUESTED';

const STATUS_LABEL: Record<string, string> = {
  CANCELLATION_REQUESTED: 'Cancellation Pending',
  CANCELLED: 'Cancelled',
  CANCELLATION_DENIED: 'Cancellation Denied',
  APPROVED: 'Approved',
  ASSIGNED: 'Assigned',
};
const statusLabel = (s: unknown) => (typeof s === 'string' && STATUS_LABEL[s]) || (typeof s === 'string' && s) || 'unknown';

/** D-4: the server-generated cancellation-cycle id, or null when the record has none (legacy). */
const cycleIdOf = (r: any): string | null =>
  (typeof r?.cancellation_request_id === 'string' && r.cancellation_request_id ? r.cancellation_request_id : null);

/** D-4: the only statuses a DENY may restore (recorded by the server, never inferred). */
const VERIFIED_PRIOR_STATUSES = ['APPROVED', 'ASSIGNED'];
const verifiedPriorOf = (r: any): string | null =>
  (typeof r?.cancellation_prior_status === 'string' && VERIFIED_PRIOR_STATUSES.includes(r.cancellation_prior_status)
    ? r.cancellation_prior_status
    : null);

/** D-4: 409 classifications returned by the BE-CANCEL-1 decision route. */
const CODE_LEGACY_PRIOR_STATUS_UNKNOWN = 'LEGACY_PRIOR_STATUS_UNKNOWN';
const CODE_CYCLE_MISMATCH = 'CANCELLATION_CYCLE_MISMATCH';
const CODE_STATE_CHANGED = 'CANCELLATION_STATE_CHANGED';
const CODE_NOT_PENDING = 'CANCELLATION_NOT_PENDING';
const CONFLICT_CODES = [CODE_LEGACY_PRIOR_STATUS_UNKNOWN, CODE_CYCLE_MISMATCH, CODE_STATE_CHANGED, CODE_NOT_PENDING];

const DENY_UNAVAILABLE_MESSAGE =
  'Deny is unavailable: this cancellation request has no verified prior booking status (Approved or Assigned), '
  + 'so it cannot be denied automatically. Owner review is required.';

/** Fields that define "the same pending cancellation request" for the client-side stale check. */
const requestFingerprint = (r: any) =>
  JSON.stringify([
    r?.status ?? null,
    cycleIdOf(r),
    verifiedPriorOf(r),
    r?.cancellation_requested_at ?? null,
    r?.cancellation_reason ?? null,
  ]);

const syncFailures = (r: any): SyncFailureEntry[] => (Array.isArray(r?.sync_failures) ? r.sync_failures : []);

const describeSyncFailure = (f: SyncFailureEntry) => {
  const type = f?.type === 'GOOGLE_CALENDAR'
    ? 'Google Calendar cleanup'
    : f?.type === 'SNS_NOTIFICATION'
      ? 'Staff notification'
      : (f?.type || 'Follow-up step');
  return `${type} failed${f?.error ? `: ${String(f.error).slice(0, 200)}` : ''}`;
};

type Phase = 'idle' | 'loading' | 'ready' | 'failed' | 'ineligible' | 'decided';

interface Props {
  request: any;
  role: string | null | undefined;
  /** Hands an authoritative REQUEST read to the screen (identity already verified). */
  onAuthoritativeRequest: (fresh: any) => void;
  onSessionExpired?: () => void | Promise<void>;
}

const PanelInner: React.FC<Omit<Props, 'role'>> = ({ request, onAuthoritativeRequest, onSessionExpired }) => {
  const requestId: string = request?.request_id;
  const clientId: string = request?.client_id;
  const propIsRequested = request?.status === REQUESTED;

  const [phase, setPhase] = useState<Phase>('idle');
  const [snapshot, setSnapshot] = useState<any>(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState<CancellationDecision | null>(null);
  const [pendingConfirm, setPendingConfirm] = useState<CancellationDecision | null>(null);
  const [error, setError] = useState('');
  const [warning, setWarning] = useState('');
  const [notice, setNotice] = useState('');
  const [syncWarnings, setSyncWarnings] = useState<string[]>([]);
  // D-4: set when the server refused DENY with LEGACY_PRIOR_STATUS_UNKNOWN for this request.
  const [denyRefused, setDenyRefused] = useState(false);

  const busyRef = useRef(false);
  const mountedRef = useRef(true);
  const seqRef = useRef(0);
  const snapshotRef = useRef<any>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      seqRef.current += 1;
    };
  }, []);

  const clearMessages = () => {
    setError('');
    setWarning('');
    setNotice('');
    setSyncWarnings([]);
  };

  /** Authoritative read with exact request AND client identity verification. */
  const readAuthoritative = async (): Promise<any> => {
    const fresh = await getAdminRequest(requestId, clientId);
    if (!fresh || fresh.request_id !== requestId || fresh.client_id !== clientId) {
      throw Object.assign(new Error('Booking identity could not be confirmed.'), { identityMismatch: true });
    }
    return fresh;
  };

  const adopt = (fresh: any) => {
    snapshotRef.current = fresh;
    setSnapshot(fresh);
  };

  // ---- hydration (read-only) whenever the screen shows a pending cancellation ------
  const hydrate = useCallback(async () => {
    const seq = ++seqRef.current;
    setPhase('loading');
    setError('');
    setDenyRefused(false);
    try {
      const fresh = await readAuthoritative();
      if (!mountedRef.current || seq !== seqRef.current) return;
      adopt(fresh);
      if (fresh.status === REQUESTED) {
        setPhase('ready');
      } else {
        setPhase('ineligible');
        onAuthoritativeRequest(fresh); // let the screen show the real status
      }
    } catch (err: any) {
      if (!mountedRef.current || seq !== seqRef.current) return;
      setPhase('failed');
      if (err?.status === 401) {
        setError('Your session expired. Please sign in again.');
        if (onSessionExpired) await onSessionExpired();
        return;
      }
      setError(
        err?.status === 403
          ? "You don't have permission to view this booking's cancellation request."
          : err?.status === 404
            ? 'This request could not be found.'
            : err?.identityMismatch
              ? 'Booking identity could not be confirmed. No decision can be made from this screen; reopen the booking.'
              : "We couldn't load the latest cancellation request, so no decision is available. Nothing has been changed."
      );
    }
  }, [requestId, clientId]); // keyed on identity; callbacks are read at call time

  useEffect(() => {
    if (propIsRequested && (phase === 'idle' || phase === 'ineligible' || phase === 'decided')) {
      clearMessages();
      hydrate();
    }
  }, [propIsRequested, requestId, clientId]); // re-check whenever the screen shows a pending request

  // If the screen's authoritative state stops showing a pending cancellation (e.g. a
  // "Refresh booking"), withdraw any offered actions and cancel an in-flight hydration.
  // A decision in flight finishes on its own path (it sets 'decided').
  useEffect(() => {
    if (propIsRequested || busyRef.current) return;
    if (phase === 'ready' || phase === 'loading' || phase === 'failed') {
      seqRef.current += 1;
      setPendingConfirm(null);
      clearMessages();
      setPhase('idle');
    }
  }, [propIsRequested]); // keyed on the screen's pending-cancellation state only

  // ---- decision ---------------------------------------------------------------------
  const decide = async (decision: CancellationDecision) => {
    setPendingConfirm(null);
    if (busyRef.current || phase !== 'ready') return;
    if (decision !== 'APPROVE' && decision !== 'DENY') return; // exact literals only
    busyRef.current = true;
    setBusy(decision);
    clearMessages();
    try {
      // 1. Pre-mutation authoritative re-read: never decide a stale or ineligible request.
      let current: any;
      try {
        current = await readAuthoritative();
      } catch (err: any) {
        if (!mountedRef.current) return;
        if (err?.status === 401) {
          setError('Your session expired. Please sign in again.');
          if (onSessionExpired) await onSessionExpired();
          return;
        }
        setError("Couldn't verify the latest booking state, so no decision was submitted. Check your connection and try again.");
        return;
      }
      if (!mountedRef.current) return;
      if (current.status !== REQUESTED || requestFingerprint(current) !== requestFingerprint(snapshotRef.current)) {
        adopt(current);
        onAuthoritativeRequest(current);
        if (current.status === REQUESTED) {
          setError('This cancellation request changed since it was loaded. The latest details are shown and no decision was submitted. Review it and try again.');
        } else {
          setPhase('ineligible');
          setError(`This booking is no longer awaiting a cancellation decision (current status: ${statusLabel(current.status)}). No decision was submitted.`);
        }
        return;
      }
      // D-4 / O-1 A: DENY requires a verified prior status on the authoritative read.
      const verifiedPrior = verifiedPriorOf(current);
      if (decision === 'DENY' && !verifiedPrior) {
        setError(`${DENY_UNAVAILABLE_MESSAGE} No decision was submitted.`);
        return;
      }
      const baselineFailures = syncFailures(current).length;

      // 2. The mutation. Exact literal + the cycle id from this read (omitted only when the
      //    record has none). Never retried automatically.
      let response: any;
      try {
        response = await processCancellationDecision(
          requestId, clientId, decision, note.trim(), cycleIdOf(current) ?? undefined,
        );
      } catch (err: any) {
        if (!mountedRef.current) return;
        await handleMutationError(decision, err, baselineFailures);
        return;
      }
      if (!mountedRef.current) return;
      setPhase('decided');
      setNote('');
      // DENY succeeds only by restoring exactly the verified prior status read above.
      const expected = decision === 'APPROVE' ? 'CANCELLED' : (verifiedPrior as string);
      const serverMessage = (typeof response?.message === 'string' && response.message.trim())
        || (decision === 'APPROVE' ? 'Cancellation request approved.' : 'Cancellation request denied.');

      // 3. Authoritative reconciliation.
      try {
        const fresh = await readAuthoritative();
        if (!mountedRef.current) return;
        adopt(fresh);
        onAuthoritativeRequest(fresh);
        reportOutcome(decision, fresh, baselineFailures, serverMessage, expected);
      } catch {
        if (!mountedRef.current) return;
        setWarning(
          `${serverMessage} However, the latest booking state could not be refreshed, so calendar cleanup `
          + 'and staff notification results are unknown. Use Refresh booking to see the current status.'
        );
      }
    } finally {
      busyRef.current = false;
      if (mountedRef.current) setBusy(null);
    }
  };

  /** Truthful post-decision summary from the authoritative record. */
  const reportOutcome = (decision: CancellationDecision, fresh: any, baselineFailures: number, serverMessage: string, expected: string) => {
    const newFailures = syncFailures(fresh).slice(baselineFailures);
    setSyncWarnings(newFailures.map(describeSyncFailure));
    if (fresh.status !== expected) {
      setWarning(`${serverMessage} The latest read shows status ${statusLabel(fresh.status)}, not ${statusLabel(expected)}. Review the booking before taking further action.`);
      return;
    }
    if (decision === 'APPROVE') {
      setNotice(
        newFailures.length > 0
          ? `${serverMessage} Some follow-up steps reported problems (listed below); the calendar and staff may not be up to date.`
          : `${serverMessage} No calendar-cleanup or staff-notification failures were recorded. These steps are best-effort; confirm the calendar if this booking had events.`
      );
    } else {
      setNotice(`${serverMessage} The booking is back to ${statusLabel(expected)}. Visits were not changed.`);
    }
  };

  /** D-4: a 409 with a known BE-CANCEL-1 code. One safe read; never resubmits. */
  const handleConflict = async (conflictCode: string, baselineFailures: number) => {
    let fresh: any;
    try {
      fresh = await readAuthoritative();
    } catch {
      if (!mountedRef.current) return;
      setPhase('failed');
      setError('The decision was not applied, and the latest booking could not be reloaded. Use Refresh booking or retry loading before deciding again.');
      return;
    }
    if (!mountedRef.current) return;
    adopt(fresh);
    onAuthoritativeRequest(fresh);
    const stillPending = fresh.status === REQUESTED;
    if (conflictCode === CODE_LEGACY_PRIOR_STATUS_UNKNOWN) {
      setDenyRefused(true);
    }
    if (!stillPending || conflictCode === CODE_NOT_PENDING) {
      setPhase('decided');
      setSyncWarnings(syncFailures(fresh).slice(baselineFailures).map(describeSyncFailure));
      setWarning(`This booking is no longer awaiting a cancellation decision (current status: ${statusLabel(fresh.status)}). No decision was applied.`);
      return;
    }
    setPhase('ready');
    if (conflictCode === CODE_LEGACY_PRIOR_STATUS_UNKNOWN) {
      setError(`${DENY_UNAVAILABLE_MESSAGE} No decision was applied.`);
    } else if (conflictCode === CODE_CYCLE_MISMATCH) {
      setError('This decision was for an earlier cancellation request. The current request is shown; review it before deciding. No decision was applied.');
    } else {
      setError('This cancellation request changed before the decision could be applied. The latest details are shown; review them before deciding.');
    }
  };

  const handleMutationError = async (decision: CancellationDecision, err: any, baselineFailures: number) => {
    const code: number | undefined = typeof err?.status === 'number' ? err.status : undefined;
    const message = String(err?.message || '').trim();
    const verb = decision === 'APPROVE' ? 'approve' : 'deny';
    if (code === 401) {
      setError('Your session expired. Please sign in again.');
      if (onSessionExpired) await onSessionExpired();
      return;
    }
    if (code === 403) {
      setError(`You don't have permission to ${verb} this cancellation.`);
      return;
    }
    if (code === 404) {
      setError('This booking request could not be found.');
      return;
    }
    if (code === 400) {
      setError(message || 'The cancellation decision was rejected.');
      return;
    }
    if (code === 409 && typeof err?.code === 'string' && CONFLICT_CODES.includes(err.code)) {
      await handleConflict(err.code, baselineFailures);
      return;
    }
    // 409, network failure, 5xx or unexpected: the outcome may be unknown. Reconcile with
    // a safe read; never resubmit.
    try {
      const fresh = await readAuthoritative();
      if (!mountedRef.current) return;
      adopt(fresh);
      onAuthoritativeRequest(fresh);
      if (fresh.status === REQUESTED) {
        setPhase('ready');
        setError(
          code === 409
            ? 'The booking changed before the decision could be applied. The latest details are shown; review them before deciding.'
            : "We couldn't confirm your decision, and the latest read still shows the cancellation awaiting a decision. "
              + 'It may not have been applied; check again before deciding.'
        );
      } else {
        setPhase('decided');
        setSyncWarnings(syncFailures(fresh).slice(baselineFailures).map(describeSyncFailure));
        setWarning(
          `We couldn't confirm your decision. The booking now shows ${statusLabel(fresh.status)}. `
          + 'Check the booking history to confirm whether this was your decision or another change.'
        );
      }
    } catch {
      if (!mountedRef.current) return;
      setPhase('failed');
      setError("We couldn't confirm your decision or reload the booking. Use Refresh booking or retry loading before deciding again.");
    }
  };

  // ---- render -----------------------------------------------------------------------
  const messages = (
    <>
      {!!error && <Text accessibilityRole="alert" style={styles.errorText}>{error}</Text>}
      {!!warning && <Text accessibilityRole="alert" style={styles.warningText}>{warning}</Text>}
      {!!notice && <Text style={styles.noticeText}>{notice}</Text>}
      {syncWarnings.map((w, i) => (
        <Text key={`sync-${i}`} accessibilityRole="alert" style={styles.warningText}>⚠️ {w}</Text>
      ))}
    </>
  );

  const hasMessages = !!(error || warning || notice || syncWarnings.length);
  if (phase === 'idle' && !hasMessages) return null;
  if ((phase === 'ineligible' || phase === 'decided') && !hasMessages) return null;

  if (phase === 'loading') {
    return (
      <View style={styles.card} testID="cancellation-loading">
        <Text style={styles.sectionHeader} accessibilityRole="header">Cancellation request</Text>
        <Text style={styles.muted}>Checking the latest cancellation request…</Text>
      </View>
    );
  }

  if (phase === 'failed') {
    return (
      <View style={styles.card} testID="cancellation-load-failed">
        <Text style={styles.sectionHeader} accessibilityRole="header">Cancellation request</Text>
        {messages}
        <TouchableOpacity style={styles.secondaryBtn} accessibilityRole="button" accessibilityLabel="Retry loading cancellation request" onPress={() => { clearMessages(); hydrate(); }}>
          <Text style={styles.secondaryBtnText}>Retry loading cancellation request</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (phase !== 'ready') {
    return (
      <View style={styles.card} testID="cancellation-result">
        <Text style={styles.sectionHeader} accessibilityRole="header">Cancellation request</Text>
        {messages}
      </View>
    );
  }

  const disabled = busy !== null;
  // D-4 / O-1 A: Deny only with a verified prior status that the server has not refused.
  const snapshotPrior = verifiedPriorOf(snapshot);
  const canDeny = !!snapshotPrior && !denyRefused;
  return (
    <View style={styles.card} testID="cancellation-decision">
      <Text style={styles.sectionHeader} accessibilityRole="header">Cancellation requested</Text>
      <Text style={styles.line}>The client asked to cancel this booking.</Text>
      {snapshot?.cancellation_reason ? <Text style={styles.line}>Reason: {snapshot.cancellation_reason}</Text> : null}
      {snapshot?.cancellation_requested_at ? <Text style={styles.muted}>Requested {snapshot.cancellation_requested_at}</Text> : null}

      <Text style={styles.label}>Decision note (optional)</Text>
      <TextInput
        style={styles.input}
        accessibilityLabel="Cancellation decision note"
        placeholder="Optional note recorded with your decision"
        placeholderTextColor={COLORS.textMuted}
        multiline
        maxLength={500}
        value={note}
        editable={!disabled}
        onChangeText={value => { setNote(value); setError(''); }}
      />

      {messages}

      <TouchableOpacity
        style={[styles.dangerBtn, disabled && styles.btnDisabled]}
        accessibilityRole="button"
        accessibilityLabel="Approve Cancellation"
        accessibilityState={{ disabled, busy: busy === 'APPROVE' }}
        disabled={disabled}
        onPress={() => setPendingConfirm('APPROVE')}
      >
        <Text style={styles.dangerBtnText}>{busy === 'APPROVE' ? 'Approving…' : 'Approve Cancellation'}</Text>
      </TouchableOpacity>
      {canDeny ? (
        <TouchableOpacity
          style={[styles.secondaryBtn, disabled && styles.btnDisabled]}
          accessibilityRole="button"
          accessibilityLabel="Deny Cancellation"
          accessibilityState={{ disabled, busy: busy === 'DENY' }}
          disabled={disabled}
          onPress={() => setPendingConfirm('DENY')}
        >
          <Text style={styles.secondaryBtnText}>{busy === 'DENY' ? 'Denying…' : 'Deny Cancellation'}</Text>
        </TouchableOpacity>
      ) : (
        !denyRefused && <Text style={styles.muted} testID="cancellation-deny-unavailable">{DENY_UNAVAILABLE_MESSAGE}</Text>
      )}

      <ConfirmationModal
        visible={pendingConfirm === 'APPROVE'}
        title="Approve cancellation?"
        message={'This cancels the booking and its remaining visits. Completed visits are kept. The server will then try to remove calendar events and notify assigned staff; those steps are best-effort and can fail. This cannot be undone from the app.'}
        onConfirm={() => decide('APPROVE')}
        onCancel={() => setPendingConfirm(null)}
        isLoading={busy !== null}
      />
      <ConfirmationModal
        visible={canDeny && pendingConfirm === 'DENY'}
        title="Deny cancellation?"
        message={`This keeps the booking and returns it to its previous status (${statusLabel(snapshotPrior)}). Visits are not changed. The client is not emailed about this decision.`}
        onConfirm={() => decide('DENY')}
        onCancel={() => setPendingConfirm(null)}
        isLoading={busy !== null}
      />
    </View>
  );
};

/** Owner/admin gate. Staff, client, unknown, empty and null roles render nothing and read nothing. */
export const CancellationDecisionPanel: React.FC<Props> = ({ role, ...rest }) => {
  if (!canDecideCancellation(role) || !rest.request) return null;
  return <PanelInner {...rest} />;
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
    minHeight: 56,
    textAlignVertical: 'top',
    color: COLORS.text,
    backgroundColor: COLORS.background,
  },
  errorText: { color: COLORS.danger, fontSize: 13, marginTop: 8 },
  warningText: { color: COLORS.text, fontSize: 13, marginTop: 8, fontWeight: '600' },
  noticeText: { color: COLORS.success, fontSize: 13, marginTop: 8 },
  dangerBtn: {
    backgroundColor: COLORS.danger,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 16,
  },
  dangerBtnText: { color: COLORS.white, fontWeight: '700', fontSize: 14 },
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
