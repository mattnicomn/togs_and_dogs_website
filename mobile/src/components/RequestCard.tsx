import React, { useState } from 'react';
import { StyleSheet, View, Text, TouchableOpacity, LayoutAnimation, Platform, UIManager } from 'react-native';
import { PetRequest } from '../types';
import { StatusBadge } from './StatusBadge';
import { ConfirmationModal } from './ConfirmationModal';
import { reviewRequest } from '../api/client';
import { useAuth } from '../auth/useAuth';
import { COLORS } from '../theme/colors';

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

interface RequestCardProps {
  request: PetRequest;
  onApproveSuccess?: () => void;
}

export const RequestCard: React.FC<RequestCardProps> = ({ request, onApproveSuccess }) => {
  const { logout } = useAuth();
  const [expanded, setExpanded] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [isMutating, setIsMutating] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const toggleExpand = () => {
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    setExpanded(!expanded);
  };

  const formatServiceType = (service: string) => {
    return (service || '')
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  };

  const formatDateRange = (dates: string[]) => {
    if (!dates || dates.length === 0) return 'No dates selected';
    if (dates.length === 1) return dates[0];
    return `${dates[0]} to ${dates[dates.length - 1]} (${dates.length} days)`;
  };

  const handleApprove = async () => {
    setMutationError(null);
    setIsMutating(true);
    try {
      await reviewRequest(request.request_id, request.client_id, 'APPROVED');
      setShowConfirmModal(false);
      if (onApproveSuccess) {
        onApproveSuccess();
      }
    } catch (error: any) {
      const msg = error.message || '';
      if (msg.toLowerCase().includes('unauthorized') || msg.toLowerCase().includes('expired')) {
        // Safe redirect/session purge if token is expired/unauthorized
        await logout();
      } else {
        setMutationError(msg || 'An error occurred during approval.');
      }
    } finally {
      setIsMutating(false);
    }
  };

  const isPending = request.status === 'PENDING_REVIEW';

  return (
    <View style={styles.cardWrapper}>
      <TouchableOpacity style={styles.card} onPress={toggleExpand} activeOpacity={0.7}>
        <View style={styles.header}>
          <View style={styles.headerLeft}>
            <Text style={styles.clientName}>{request.client_name}</Text>
            <Text style={styles.petText}>🐾 {request.pet_name}</Text>
          </View>
          <StatusBadge status={request.status} />
        </View>

        <View style={styles.details}>
          <View style={styles.row}>
            <Text style={styles.label}>Service:</Text>
            <Text style={styles.value}>{formatServiceType(request.service_type)}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.label}>Dates:</Text>
            <Text style={styles.value}>
              {formatDateRange(request.selected_dates)}
            </Text>
          </View>
          {request.timeframe ? (
            <View style={styles.row}>
              <Text style={styles.label}>Window:</Text>
              <Text style={styles.value}>{request.timeframe}</Text>
            </View>
          ) : null}
          {(request.worker_name || request.assigned_sitter) ? (
            <View style={styles.row}>
              <Text style={styles.label}>Staff:</Text>
              <Text style={styles.value}>👤 {request.worker_name || request.assigned_sitter}</Text>
            </View>
          ) : null}
        </View>

        {expanded && (
          <View style={styles.expandedContent}>
            {request.special_instructions ? (
              <View style={styles.instructionsContainer}>
                <Text style={styles.instructionLabel}>Special Instructions:</Text>
                <Text style={styles.instructionText}>{request.special_instructions}</Text>
              </View>
            ) : (
              <Text style={styles.noInstructions}>No special instructions provided.</Text>
            )}

            {request.timeframe && (
              <View style={styles.metaRow}>
                <Text style={styles.metaLabel}>Preferred Timeframe:</Text>
                <Text style={styles.metaValue}>{request.timeframe}</Text>
              </View>
            )}

            {request.preferred_sitter && (
              <View style={styles.metaRow}>
                <Text style={styles.metaLabel}>Preferred Sitter:</Text>
                <Text style={styles.metaValue}>{request.preferred_sitter}</Text>
              </View>
            )}

            {mutationError && (
              <View style={styles.errorContainer}>
                <Text style={styles.errorText}>⚠️ {mutationError}</Text>
              </View>
            )}

            {isPending && (
              <TouchableOpacity
                style={styles.approveBtn}
                onPress={() => setShowConfirmModal(true)}
                disabled={isMutating}
                activeOpacity={0.8}
              >
                <Text style={styles.approveBtnText}>Approve Booking</Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        <Text style={styles.tapPrompt}>
          {expanded ? 'Tap to collapse' : 'Tap to expand details'}
        </Text>
      </TouchableOpacity>

      <ConfirmationModal
        visible={showConfirmModal}
        title="Approve Pet Booking?"
        message={`This will update ${request.pet_name}'s status to APPROVED. This triggers production calendar syncs and notification emails. Are you sure you want to proceed?`}
        onConfirm={handleApprove}
        onCancel={() => setShowConfirmModal(false)}
        isLoading={isMutating}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  cardWrapper: {
    marginBottom: 12,
  },
  card: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    shadowColor: COLORS.text,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.02,
    shadowRadius: 6,
    elevation: 2,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  headerLeft: {
    flex: 1,
  },
  clientName: {
    fontSize: 16,
    fontWeight: '800',
    color: COLORS.text,
  },
  petText: {
    fontSize: 13,
    color: COLORS.primary,
    fontWeight: '700',
    marginTop: 2,
  },
  details: {
    borderTopWidth: 1,
    borderTopColor: COLORS.borderSoft,
    paddingTop: 12,
    gap: 6,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  label: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.textMuted,
    width: 65,
  },
  value: {
    fontSize: 13,
    color: COLORS.text,
    fontWeight: '600',
    flex: 1,
  },
  expandedContent: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: COLORS.borderSoft,
  },
  instructionsContainer: {
    backgroundColor: COLORS.background,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
    marginBottom: 12,
  },
  instructionLabel: {
    fontSize: 12,
    fontWeight: '800',
    color: COLORS.text,
    marginBottom: 4,
  },
  instructionText: {
    fontSize: 13,
    color: COLORS.text,
    lineHeight: 18,
    fontWeight: '500',
  },
  noInstructions: {
    fontSize: 13,
    color: COLORS.textMuted,
    fontStyle: 'italic',
    marginBottom: 12,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  metaLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: COLORS.textMuted,
  },
  metaValue: {
    fontSize: 12,
    color: COLORS.text,
    fontWeight: '600',
  },
  errorContainer: {
    backgroundColor: '#fff1f2',
    borderWidth: 1,
    borderColor: '#fecdd3',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  errorText: {
    color: COLORS.danger,
    fontSize: 13,
    fontWeight: '600',
  },
  approveBtn: {
    backgroundColor: COLORS.success,
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 8,
    shadowColor: COLORS.success,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 2,
  },
  approveBtnText: {
    color: COLORS.white,
    fontSize: 15,
    fontWeight: '700',
  },
  tapPrompt: {
    fontSize: 10,
    color: COLORS.textMuted,
    fontWeight: '600',
    textAlign: 'center',
    marginTop: 10,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
});
