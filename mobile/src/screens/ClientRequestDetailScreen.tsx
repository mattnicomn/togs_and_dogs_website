import React, { useCallback, useRef, useState } from 'react';
import {
  StyleSheet,
  View,
  Text,
  ScrollView,
  ActivityIndicator,
  TouchableOpacity,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect } from '@react-navigation/native';
import {
  getClientQuote,
  acceptClientQuote,
  declineClientQuote,
} from '../api/client';
import { useAuth } from '../auth/useAuth';
import { ConfirmationModal } from '../components/ConfirmationModal';
import { COLORS } from '../theme/colors';
import { ClientQuote, ClientQuoteAcceptResponse } from '../types';
import { getServiceTypeLabel } from '../utils/serviceLabels';

/**
 * OPS-3A.3B/.3C: Client-only request/booking detail shell.
 *
 * .3B added the read-only quote presentation; .3C adds Accept/Decline mutation UX
 * with 409 and ambiguous-network reconciliation.
 *
 * Invariants:
 *  - Accept/Decline are shown ONLY for quote_status === 'SENT'.
 *  - No optimistic commercial state: success is rendered only after the server
 *    confirms (via mutation response + an authoritative GET refetch).
 *  - expected_revision is always the current authoritative quote_revision.
 *  - 409 and ambiguous network failures never auto-retry; they refetch the
 *    authoritative quote and reconcile.
 *  - booking_ready is used ONLY as returned by the accept response; it is never
 *    inferred locally and never persisted into the GET-derived ClientQuote.
 *  - Visibility of DRAFT/SUPERSEDED is owned by the server (OPS-3A.3A.1/.2).
 */

const MAX_DECLINE_REASON = 500;

const formatCurrency = (cents: number | null | undefined, currency: string | null | undefined): string => {
  const amount = ((cents ?? 0) / 100);
  const code = currency || 'USD';
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: code }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${code}`;
  }
};

const formatDate = (dateStr: string | null | undefined): string => {
  if (!dateStr) return '';
  const d = new Date(`${dateStr}T00:00:00`);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

const formatTimestamp = (iso: string | null | undefined): string | null => {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

const PAYMENT_REQUIREMENT_LABEL: Record<string, string> = {
  NONE: 'No payment required',
  DEPOSIT: 'Deposit required',
  FULL: 'Full payment required',
};

const PAYMENT_STATUS_LABEL: Record<string, string> = {
  NOT_REQUIRED: 'Not required',
  UNPAID: 'Unpaid',
  PAYMENT_LINK_SENT: 'Payment link sent',
  PARTIALLY_PAID: 'Partially paid',
  PAID: 'Paid',
  REFUNDED: 'Refunded',
};

type PendingAction = 'accept' | 'decline' | null;

const isSessionError = (status: number | undefined, msg: string): boolean =>
  status === 401 ||
  msg.toLowerCase().includes('expired') ||
  msg.toLowerCase().includes('unauthorized');

export const ClientRequestDetailScreen = ({ route }: any) => {
  const requestId: string = route.params?.requestId;
  const { logout } = useAuth();

  const [quote, setQuote] = useState<ClientQuote | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  // Mutation state
  const [pending, setPending] = useState<PendingAction>(null);
  const [showAcceptConfirm, setShowAcceptConfirm] = useState(false);
  const [showDeclineConfirm, setShowDeclineConfirm] = useState(false);
  const [declineReason, setDeclineReason] = useState('');
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  // booking_ready is transient action-response state (NOT part of ClientQuote).
  const [bookingReady, setBookingReady] = useState<boolean | null>(null);
  const [bookingReadyReason, setBookingReadyReason] = useState<string | null>(null);

  const mountedRef = useRef(true);
  const sequenceRef = useRef(0);
  // Guards against a double-submit between the press and the state flip.
  const mutationLockRef = useRef(false);

  const applyQuote = (data: ClientQuote | null) => {
    if (!mountedRef.current) return;
    setQuote(data);
  };

  const fetchQuote = useCallback(async () => {
    if (!requestId) {
      setIsLoading(false);
      setUnavailable(true);
      return;
    }
    const sequence = ++sequenceRef.current;
    setIsLoading(true);
    setError(null);
    setUnavailable(false);
    try {
      const data = await getClientQuote(requestId);
      if (!mountedRef.current || sequence !== sequenceRef.current) return;
      setQuote(data);
    } catch (e: any) {
      if (!mountedRef.current || sequence !== sequenceRef.current) return;
      const msg = e?.message || '';
      const status = e?.status;
      if (isSessionError(status, msg)) {
        await logout();
        return;
      }
      if (status === 404) {
        setUnavailable(true);
        setQuote(null);
        return;
      }
      setError(msg || 'Could not load this booking. Please try again.');
    } finally {
      if (mountedRef.current && sequence === sequenceRef.current) setIsLoading(false);
    }
  }, [requestId]);

  useFocusEffect(
    useCallback(() => {
      mountedRef.current = true;
      fetchQuote();
      return () => {
        mountedRef.current = false;
      };
    }, [fetchQuote])
  );

  /**
   * Authoritative refetch used after a mutation, a 409, or an ambiguous network
   * failure. Returns the fetched quote (or null if unavailable) so callers can
   * reconcile against the attempted action. Never throws for 404 (-> unavailable).
   */
  const refetchAuthoritative = async (): Promise<ClientQuote | null> => {
    try {
      const data = await getClientQuote(requestId);
      if (!mountedRef.current) return null;
      setUnavailable(false);
      setQuote(data);
      return data;
    } catch (e: any) {
      if (!mountedRef.current) return null;
      const msg = e?.message || '';
      const status = e?.status;
      if (isSessionError(status, msg)) {
        await logout();
        return null;
      }
      if (status === 404) {
        // Quote no longer client-visible: clear commercial state, show unavailable.
        setQuote(null);
        setUnavailable(true);
        return null;
      }
      // Preserve a safe error state; do NOT auto-retry the original mutation.
      setError(msg || 'Could not refresh this booking. Please try again.');
      return null;
    }
  };

  const beginMutation = (action: PendingAction) => {
    if (mutationLockRef.current) return false;
    mutationLockRef.current = true;
    setPending(action);
    setActionMessage(null);
    return true;
  };

  const endMutation = () => {
    mutationLockRef.current = false;
    if (mountedRef.current) setPending(null);
  };

  // ---- Accept ----
  const handleAcceptConfirm = async () => {
    if (!quote) return;
    if (!beginMutation('accept')) return;
    const expectedRevision = quote.quote_revision;
    try {
      const resp: ClientQuoteAcceptResponse = await acceptClientQuote(requestId, expectedRevision);
      if (!mountedRef.current) return;
      setShowAcceptConfirm(false);
      // Consume server-returned action fields (authoritative), including booking_ready.
      setBookingReady(typeof resp.booking_ready === 'boolean' ? resp.booking_ready : null);
      setBookingReadyReason(resp.booking_ready_reason ?? null);
      // Synchronize the full GET-shaped projection before rendering final state.
      await refetchAuthoritative();
      if (mountedRef.current) setActionMessage('Quote accepted');
    } catch (e: any) {
      await handleMutationError(e, 'accept');
    } finally {
      endMutation();
    }
  };

  // ---- Decline ----
  const handleDeclineConfirm = async () => {
    if (!quote) return;
    const trimmed = declineReason.trim();
    if (trimmed.length > MAX_DECLINE_REASON) return; // guarded by input, defensive
    if (!beginMutation('decline')) return;
    const expectedRevision = quote.quote_revision;
    try {
      await declineClientQuote(requestId, expectedRevision, trimmed || undefined);
      if (!mountedRef.current) return;
      setShowDeclineConfirm(false);
      setDeclineReason(''); // do not echo the reason after success
      await refetchAuthoritative();
      if (mountedRef.current) setActionMessage('Quote declined');
    } catch (e: any) {
      await handleMutationError(e, 'decline');
    } finally {
      endMutation();
    }
  };

  /**
   * Unified mutation-error handling for Accept/Decline.
   * - 401 -> logout (existing convention)
   * - 403 -> generic permission message (not treated as 409)
   * - 409 -> no auto-retry; refetch authoritative and explain the quote changed
   * - ambiguous network/other -> no success assumption; refetch and reconcile,
   *   leaving a deliberate retry possible when still SENT.
   */
  const handleMutationError = async (e: any, action: 'accept' | 'decline') => {
    if (!mountedRef.current) return;
    const msg = e?.message || '';
    const status = e?.status;

    if (isSessionError(status, msg)) {
      await logout();
      return;
    }
    if (status === 403) {
      setShowAcceptConfirm(false);
      setShowDeclineConfirm(false);
      setActionMessage(msg || 'You do not have permission to perform this action.');
      return;
    }
    if (status === 409) {
      setShowAcceptConfirm(false);
      setShowDeclineConfirm(false);
      await refetchAuthoritative();
      if (mountedRef.current) {
        setActionMessage('This quote changed or was already acted on. The latest quote has been loaded.');
      }
      return;
    }

    // Ambiguous network / timeout / unknown: do NOT assume success or failure.
    setShowAcceptConfirm(false);
    setShowDeclineConfirm(false);
    const latest = await refetchAuthoritative();
    if (!mountedRef.current) return;
    const latestStatus = (latest?.quote_status || '').toUpperCase();
    if (action === 'accept' && latestStatus === 'ACCEPTED') {
      setActionMessage('Quote accepted');
    } else if (action === 'decline' && latestStatus === 'DECLINED') {
      setActionMessage('Quote declined');
    } else if (latestStatus === 'SENT') {
      setActionMessage("We couldn't confirm your action. Please check the quote and try again.");
    } else if (latest) {
      setActionMessage('This quote changed or was already acted on. The latest quote has been loaded.');
    }
    // If latest is null (unavailable/error), refetchAuthoritative already set the state.
  };

  const openDecline = () => {
    setDeclineReason('');
    setActionMessage(null);
    setShowDeclineConfirm(true);
  };

  // ---- Loading ----
  if (isLoading) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <ActivityIndicator size="large" color={COLORS.primary} accessibilityLabel="Loading booking details" />
        <Text style={styles.mutedText}>Loading your booking...</Text>
      </SafeAreaView>
    );
  }

  // ---- Error (retryable) ----
  if (error) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <Text style={styles.errorIcon}>⚠️</Text>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity
          style={styles.retryBtn}
          onPress={fetchQuote}
          accessibilityRole="button"
          accessibilityLabel="Retry loading booking details"
        >
          <Text style={styles.retryText}>Retry</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  // ---- Unavailable (no client-visible quote) ----
  if (unavailable || !quote) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <Text style={styles.emptyIcon}>🐾</Text>
        <Text style={styles.emptyTitle}>No quote available yet</Text>
        <Text style={styles.mutedText}>
          There is no quote to review for this booking right now. We'll update this
          page when your provider sends one.
        </Text>
        {actionMessage ? <Text style={styles.actionMessage}>{actionMessage}</Text> : null}
      </SafeAreaView>
    );
  }

  const status = (quote.quote_status || '').toUpperCase();
  const isSent = status === 'SENT';
  const amount = formatCurrency(quote.quote_amount_cents, quote.currency);
  const hasDeposit = (quote.deposit_amount_cents ?? 0) > 0;
  const sentOn = formatTimestamp(quote.quote_sent_at);
  const acceptedOn = formatTimestamp(quote.quote_accepted_at);
  const mutating = pending !== null;

  const renderPricing = () => (
    <>
      <View style={styles.row}>
        <Text style={styles.rowLabel}>Total</Text>
        <Text style={styles.amount} accessibilityLabel={`Quote total ${amount}`}>{amount}</Text>
      </View>
      {hasDeposit ? (
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Deposit</Text>
          <Text style={styles.rowValue}>{formatCurrency(quote.deposit_amount_cents, quote.currency)}</Text>
        </View>
      ) : null}
      {quote.payment_requirement ? (
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Payment</Text>
          <Text style={styles.rowValue}>
            {PAYMENT_REQUIREMENT_LABEL[quote.payment_requirement] || quote.payment_requirement}
          </Text>
        </View>
      ) : null}
      {quote.payment_status ? (
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Payment status</Text>
          <Text style={styles.rowValue}>
            {PAYMENT_STATUS_LABEL[quote.payment_status] || quote.payment_status}
          </Text>
        </View>
      ) : null}
    </>
  );

  const renderNotes = () =>
    quote.quote_notes_client ? (
      <View style={styles.notesBlock}>
        <Text style={styles.rowLabel}>Notes from your provider</Text>
        <Text style={styles.notesText}>{quote.quote_notes_client}</Text>
      </View>
    ) : null;

  const renderQuoteSection = () => {
    switch (status) {
      case 'SENT':
        return (
          <View style={styles.card}>
            <Text style={styles.sectionHeader} accessibilityRole="header">Your Quote</Text>
            <View style={styles.statusLine}>
              <Text style={styles.statusPill} accessibilityLabel="Quote status: ready for review">
                Quote ready for review
              </Text>
            </View>
            {renderPricing()}
            {renderNotes()}
            {sentOn ? <Text style={styles.mutedSmall}>Sent {sentOn}</Text> : null}
          </View>
        );
      case 'ACCEPTED':
        return (
          <View style={styles.card}>
            <Text style={styles.sectionHeader} accessibilityRole="header">Your Quote</Text>
            <View style={styles.statusLine}>
              <Text style={[styles.statusPill, styles.statusPillSuccess]} accessibilityLabel="Quote status: accepted">
                Quote accepted
              </Text>
            </View>
            {acceptedOn ? <Text style={styles.mutedSmall}>Accepted {acceptedOn}</Text> : null}
            {renderPricing()}
            {renderNotes()}
            {bookingReady === true ? (
              <Text style={styles.mutedSmall}>
                {bookingReadyReason || 'Your booking is ready. Your provider will follow up on next steps.'}
              </Text>
            ) : (
              <Text style={styles.mutedSmall}>
                Your provider will follow up on next steps. Payment details, if any, are shown above.
              </Text>
            )}
          </View>
        );
      case 'DECLINED':
        return (
          <View style={styles.card}>
            <Text style={styles.sectionHeader} accessibilityRole="header">Your Quote</Text>
            <View style={styles.statusLine}>
              <Text style={[styles.statusPill, styles.statusPillDanger]} accessibilityLabel="Quote status: declined">
                Quote declined
              </Text>
            </View>
            <Text style={styles.mutedText}>
              This quote was declined. Your provider may revise it and send a new quote.
            </Text>
          </View>
        );
      case 'NOT_REQUIRED':
        return (
          <View style={styles.card}>
            <Text style={styles.sectionHeader} accessibilityRole="header">Your Quote</Text>
            <Text style={styles.mutedText}>No quote action is required for this booking.</Text>
          </View>
        );
      default:
        return (
          <View style={styles.card}>
            <Text style={styles.sectionHeader} accessibilityRole="header">Your Quote</Text>
            <Text style={styles.mutedText}>No quote action is required for this booking.</Text>
          </View>
        );
    }
  };

  const dates =
    quote.selected_dates && quote.selected_dates.length
      ? quote.selected_dates.map(formatDate).join(', ')
      : quote.start_date
      ? `${formatDate(quote.start_date)}${quote.end_date && quote.end_date !== quote.start_date ? ` – ${formatDate(quote.end_date)}` : ''}`
      : 'Date to be confirmed';

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
        {/* Booking context (client-safe) */}
        <View style={styles.card}>
          <Text style={styles.sectionHeader} accessibilityRole="header">Booking Details</Text>
          <View style={styles.row}>
            <Text style={styles.rowLabel}>Service</Text>
            <Text style={styles.rowValue}>{getServiceTypeLabel(quote.service_type)}</Text>
          </View>
          {quote.pet_names && quote.pet_names.length ? (
            <View style={styles.row}>
              <Text style={styles.rowLabel}>Pets</Text>
              <Text style={styles.rowValue}>{quote.pet_names.join(', ')}</Text>
            </View>
          ) : null}
          <View style={styles.row}>
            <Text style={styles.rowLabel}>Date(s)</Text>
            <Text style={styles.rowValue} numberOfLines={3}>{dates}</Text>
          </View>
        </View>

        {/* Read-only quote section */}
        {renderQuoteSection()}

        {/* Action-level message (reconciliation / permission / result) */}
        {actionMessage ? (
          <Text style={styles.actionMessage} accessibilityLiveRegion="polite">{actionMessage}</Text>
        ) : null}

        {/* Accept / Decline — SENT only */}
        {isSent ? (
          <View style={styles.card}>
            {showDeclineConfirm ? (
              <View>
                <Text style={styles.sectionHeader} accessibilityRole="header">Decline this quote?</Text>
                <Text style={styles.rowLabel}>Reason (optional)</Text>
                <TextInput
                  style={styles.reasonInput}
                  placeholder="Let your provider know why (optional)"
                  placeholderTextColor={COLORS.textMuted}
                  multiline
                  numberOfLines={3}
                  maxLength={MAX_DECLINE_REASON}
                  value={declineReason}
                  onChangeText={setDeclineReason}
                  editable={!mutating}
                  accessibilityLabel="Decline reason (optional)"
                />
                <Text style={styles.charCount}>{declineReason.length}/{MAX_DECLINE_REASON} characters</Text>
                <View style={styles.actionRow}>
                  <TouchableOpacity
                    style={[styles.btn, styles.btnCancel]}
                    onPress={() => { if (!mutating) setShowDeclineConfirm(false); }}
                    disabled={mutating}
                    accessibilityRole="button"
                    accessibilityLabel="Cancel declining this quote"
                  >
                    <Text style={styles.btnCancelText}>Cancel</Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.btn, styles.btnDecline]}
                    onPress={handleDeclineConfirm}
                    disabled={mutating}
                    accessibilityRole="button"
                    accessibilityLabel="Confirm declining this quote"
                    accessibilityState={{ disabled: mutating, busy: pending === 'decline' }}
                  >
                    {pending === 'decline' ? (
                      <ActivityIndicator color={COLORS.white} size="small" />
                    ) : (
                      <Text style={styles.btnDeclineText}>Confirm decline</Text>
                    )}
                  </TouchableOpacity>
                </View>
              </View>
            ) : (
              <View style={styles.actionRow}>
                <TouchableOpacity
                  style={[styles.btn, styles.btnDeclineOutline]}
                  onPress={openDecline}
                  disabled={mutating}
                  accessibilityRole="button"
                  accessibilityLabel="Decline quote"
                  accessibilityState={{ disabled: mutating }}
                >
                  <Text style={styles.btnDeclineOutlineText}>Decline</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={[styles.btn, styles.btnAccept]}
                  onPress={() => { setActionMessage(null); setShowAcceptConfirm(true); }}
                  disabled={mutating}
                  accessibilityRole="button"
                  accessibilityLabel="Accept quote"
                  accessibilityState={{ disabled: mutating, busy: pending === 'accept' }}
                >
                  {pending === 'accept' ? (
                    <ActivityIndicator color={COLORS.white} size="small" />
                  ) : (
                    <Text style={styles.btnAcceptText}>Accept</Text>
                  )}
                </TouchableOpacity>
              </View>
            )}
          </View>
        ) : null}
      </ScrollView>

      {/* Accept confirmation */}
      <ConfirmationModal
        visible={showAcceptConfirm}
        title="Accept this quote?"
        message={`You're accepting a quote of ${amount}. Your provider will follow up on next steps.`}
        onConfirm={handleAcceptConfirm}
        onCancel={() => { if (!mutating) setShowAcceptConfirm(false); }}
        isLoading={pending === 'accept'}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  scrollContent: {
    padding: 20,
    paddingBottom: 32,
  },
  centerContainer: {
    flex: 1,
    backgroundColor: COLORS.background,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  card: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 12,
    padding: 16,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
  },
  sectionHeader: {
    fontSize: 16,
    fontWeight: '800',
    color: COLORS.text,
    marginBottom: 12,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  rowLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.textMuted,
    marginRight: 12,
    flexShrink: 0,
  },
  rowValue: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.text,
    flex: 1,
    textAlign: 'right',
  },
  amount: {
    fontSize: 20,
    fontWeight: '800',
    color: COLORS.primary,
    flex: 1,
    textAlign: 'right',
  },
  statusLine: {
    marginBottom: 12,
  },
  statusPill: {
    alignSelf: 'flex-start',
    fontSize: 12,
    fontWeight: '800',
    color: COLORS.primaryHover,
    backgroundColor: '#fcf6e9',
    borderColor: '#f1e3c1',
    borderWidth: 1,
    borderRadius: 99,
    paddingHorizontal: 12,
    paddingVertical: 4,
    overflow: 'hidden',
  },
  statusPillSuccess: {
    color: '#065f46',
    backgroundColor: '#ecfdf5',
    borderColor: '#a7f3d0',
  },
  statusPillDanger: {
    color: '#9b2c1d',
    backgroundColor: '#fdf2f0',
    borderColor: '#f9d7d2',
  },
  notesBlock: {
    marginTop: 6,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: COLORS.borderSoft,
  },
  notesText: {
    fontSize: 14,
    color: COLORS.text,
    lineHeight: 20,
    marginTop: 4,
  },
  mutedText: {
    fontSize: 14,
    color: COLORS.textMuted,
    textAlign: 'center',
    lineHeight: 20,
    marginTop: 8,
  },
  mutedSmall: {
    fontSize: 12,
    color: COLORS.textMuted,
    marginTop: 8,
  },
  actionMessage: {
    fontSize: 14,
    color: COLORS.text,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 14,
  },
  errorIcon: {
    fontSize: 48,
    marginBottom: 12,
  },
  errorText: {
    fontSize: 14,
    color: COLORS.danger,
    textAlign: 'center',
    lineHeight: 20,
    fontWeight: '600',
    marginBottom: 20,
  },
  emptyIcon: {
    fontSize: 56,
    marginBottom: 12,
    opacity: 0.85,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: COLORS.text,
    marginBottom: 4,
  },
  retryBtn: {
    backgroundColor: COLORS.primary,
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 8,
  },
  retryText: {
    color: COLORS.white,
    fontSize: 14,
    fontWeight: '700',
  },
  actionRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
    marginTop: 8,
  },
  btn: {
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderRadius: 8,
    minWidth: 110,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnAccept: {
    backgroundColor: COLORS.success,
  },
  btnAcceptText: {
    color: COLORS.white,
    fontSize: 14,
    fontWeight: '800',
  },
  btnDecline: {
    backgroundColor: COLORS.danger,
  },
  btnDeclineText: {
    color: COLORS.white,
    fontSize: 14,
    fontWeight: '800',
  },
  btnDeclineOutline: {
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  btnDeclineOutlineText: {
    color: COLORS.text,
    fontSize: 14,
    fontWeight: '700',
  },
  btnCancel: {
    backgroundColor: COLORS.background,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  btnCancelText: {
    color: COLORS.text,
    fontSize: 14,
    fontWeight: '700',
  },
  reasonInput: {
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    color: COLORS.text,
    minHeight: 72,
    textAlignVertical: 'top',
    marginTop: 4,
  },
  charCount: {
    fontSize: 12,
    color: COLORS.textMuted,
    marginTop: 4,
    textAlign: 'right',
  },
});
