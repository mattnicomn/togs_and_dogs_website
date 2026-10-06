import React, { useCallback, useRef, useState } from 'react';
import {
  StyleSheet,
  View,
  Text,
  ScrollView,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect } from '@react-navigation/native';
import { getClientQuote } from '../api/client';
import { useAuth } from '../auth/useAuth';
import { COLORS } from '../theme/colors';
import { ClientQuote } from '../types';
import { getServiceTypeLabel } from '../utils/serviceLabels';

/**
 * OPS-3A.3B: Client-only request/booking detail shell with a READ-ONLY quote
 * section. Durable home for future request/visit/payment sections, but this slice
 * implements only client-safe booking context + read-only quote presentation.
 *
 * No Accept/Decline, no decline reason, no confirmation modal, no mutation calls,
 * no payment collection — those are OPS-3A.3C and later. Visibility of DRAFT /
 * SUPERSEDED is owned by the server (OPS-3A.3A.1/.2); this screen never fabricates
 * booking_ready (not part of the GET projection) and never filters DRAFT as a
 * client-side substitute for the server rule.
 */

const formatCurrency = (cents: number | null | undefined, currency: string | null | undefined): string => {
  const amount = ((cents ?? 0) / 100);
  const code = currency || 'USD';
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: code }).format(amount);
  } catch {
    // Fallback if the runtime/Intl lacks the currency: fixed 2-decimal + code.
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

export const ClientRequestDetailScreen = ({ route }: any) => {
  const requestId: string = route.params?.requestId;
  const { logout } = useAuth();

  const [quote, setQuote] = useState<ClientQuote | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [unavailable, setUnavailable] = useState(false);

  const mountedRef = useRef(true);
  const sequenceRef = useRef(0);

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
      // Session expiry: defer to the existing auth-layer logout convention.
      if (
        status === 401 ||
        msg.toLowerCase().includes('expired') ||
        msg.toLowerCase().includes('unauthorized')
      ) {
        await logout();
        return;
      }
      // No client-visible quote for this request (ownership miss, or server-side
      // DRAFT/SUPERSEDED visibility gate) -> non-disclosing "no quote available".
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
      </SafeAreaView>
    );
  }

  const status = (quote.quote_status || '').toUpperCase();
  const amount = formatCurrency(quote.quote_amount_cents, quote.currency);
  const hasDeposit = (quote.deposit_amount_cents ?? 0) > 0;
  const sentOn = formatTimestamp(quote.quote_sent_at);
  const acceptedOn = formatTimestamp(quote.quote_accepted_at);

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
            <Text style={styles.mutedSmall}>
              Your provider will follow up on next steps. Payment details, if any, are shown above.
            </Text>
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
        // DRAFT / SUPERSEDED should not reach the client (server returns 404 ->
        // handled as "unavailable" above). Any other/unknown status is shown
        // conservatively as no action required, never as draft pricing.
        return (
          <View style={styles.card}>
            <Text style={styles.sectionHeader} accessibilityRole="header">Your Quote</Text>
            <Text style={styles.mutedText}>No quote action is required for this booking.</Text>
          </View>
        );
    }
  };

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
      </ScrollView>
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
});
