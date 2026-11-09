import React, { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, View, Text, TextInput, TouchableOpacity } from 'react-native';
import { COLORS } from '../theme/colors';
import { ConfirmationModal } from './ConfirmationModal';
import { getAdminRequest, processCancellationDecision } from '../api/client';
import type { CancellationDecision, SyncFailureEntry } from '../types';

/**
 * S2: owner/admin cancellation decision (Approve / Deny a client's cancellation request).
 *
 * Contract (existing backend): PUT /admin/cancel/decision
 *   body { request_id, client_id, decision: 'APPROVE' | 'DENY', note }
 *   APPROVE -> request CANCELLED, child jobs CANCELLED (COMPLETED preserved), best-effort
 *              Google Calendar cleanup + staff SNS; failures are appended to
 *              REQUEST.sync_failures (they are NOT in the HTTP response).
 *   DENY    -> request CANCELLATION_DENIED, non-completed child jobs set to ASSIGNED.
 *
 * Backend safety limitations (NOT fixed here; documented release-safety blockers):
 *   - no server-side check that the request is CANCELLATION_REQUESTED;
 *   - any decision other than the exact 'APPROVE' is treated as DENY;
 *   - no revision / concurrency guard.
 * The client-side checks below reduce, but do not replace, server enforcement.
 *
 * Mobile safety model:
 *   - Owner/admin only (explicit allowlist); every other role renders nothing.
 *   - Actions appear only after an authoritative read confirms CANCELLATION_REQUESTED and
 *     the exact request/client identity. Before submitting, the request is re-read again;
 *     any change refuses the submission.
 *   - Explicit confirmation; exact literals only; one submission at a time; never retried.
 *   - After success the request is re-read; new sync_failures entries are shown truthfully.
 *     A refresh failure after success is reported as such, never as a failed decision.
 *   - Uncertain outcomes (network / 5xx / unexpected) are reconciled with a safe read.
 */

export const canDecideCancellation = (role: string | null | undefined) => role === 'owner' || role === 'admin';

const REQUESTED = 'CANCELLATION_REQUESTED';

const STATUS_LABEL: Record<string, string> = {
  CANCELLATION_REQUESTED: 'Cancellation Pending',
  CANCELLED: 'Cancelled',
  CANCELLATION_DENIED: 'Cancellation Denied',
};
const statusLabel = (s: unknown) => (typeof s === 'string' && STATUS_LABEL[s]) || (typeof s === 'string' && s) || 'unknown';

/** Fields that define "the same pending cancellation request" for the client-side stale check. */
const requestFingerprint = (r: any) =>
  JSON.stringify([r?.status ?? null, r?.cancellation_requested_at ?? null, r?.cancellation_reason ?? null]);

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
      const baselineFailures = syncFailures(current).length;

      // 2. The mutation. Never retried automatically.
      let response: any;
      try {
        response = await processCancellationDecision(requestId, clientId, decision, note.trim());
      } catch (err: any) {
        if (!mountedRef.current) return;
        await handleMutationError(decision, err, baselineFailures);
        return;
      }
      if (!mountedRef.current) return;
      setPhase('decided');
      setNote('');
      const expected = decision === 'APPROVE' ? 'CANCELLED' : 'CANCELLATION_DENIED';
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
      setNotice(`${serverMessage} The booking stays active as Cancellation Denied.`);
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

      <ConfirmationModal
        visible={pendingConfirm === 'APPROVE'}
        title="Approve cancellation?"
        message={'This cancels the booking and its remaining visits. Completed visits are kept. The server will then try to remove calendar events and notify assigned staff; those steps are best-effort and can fail. This cannot be undone from the app.'}
        onConfirm={() => decide('APPROVE')}
        onCancel={() => setPendingConfirm(null)}
        isLoading={busy !== null}
      />
      <ConfirmationModal
        visible={pendingConfirm === 'DENY'}
        title="Deny cancellation?"
        message={'This keeps the booking and marks the request Cancellation Denied. Remaining visits stay assigned. The client is not automatically notified by this action.'}
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
