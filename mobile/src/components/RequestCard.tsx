import React, { useState } from 'react';
import { StyleSheet, View, Text, TouchableOpacity, LayoutAnimation, Platform, UIManager } from 'react-native';
import { PetRequest } from '../types';
import { StatusBadge } from './StatusBadge';
import { COLORS } from '../theme/colors';

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}

interface RequestCardProps {
  request: PetRequest;
}

export const RequestCard: React.FC<RequestCardProps> = ({ request }) => {
  const [expanded, setExpanded] = useState(false);

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

  return (
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
          <Text style={styles.value} numberOfLines={1}>
            {formatDateRange(request.selected_dates)}
          </Text>
        </View>
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

          <Text style={styles.actionDeferredText}>
            ⚠️ Mutations are disabled (Release 8I Read-Only).
          </Text>
        </View>
      )}

      <Text style={styles.tapPrompt}>
        {expanded ? 'Tap to collapse' : 'Tap to expand details'}
      </Text>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
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
  actionDeferredText: {
    fontSize: 11,
    color: COLORS.primary,
    fontWeight: '700',
    marginTop: 8,
    textAlign: 'center',
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
