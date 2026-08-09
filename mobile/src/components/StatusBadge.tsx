import React from 'react';
import { StyleSheet, View, Text } from 'react-native';
import { REQUEST_STATUSES } from '../contracts/generatedContracts';

interface StatusBadgeProps {
  status: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const normalizedStatus = (status || '').toUpperCase();
  const contractLabel = REQUEST_STATUSES.statuses[normalizedStatus as keyof typeof REQUEST_STATUSES.statuses]?.label;
  
  let badgeStyles = styles.badgeNew;
  let textStyles = styles.textNew;
  let label = (contractLabel || normalizedStatus || 'PENDING REVIEW').toUpperCase().replace(/_/g, ' ');

  if (normalizedStatus === 'APPROVED') {
    badgeStyles = styles.badgeApproved;
    textStyles = styles.textApproved;
    label = (REQUEST_STATUSES.statuses.APPROVED?.label || 'APPROVED').toUpperCase();
  } else if (normalizedStatus === 'ASSIGNED' || normalizedStatus === 'SCHEDULED' || normalizedStatus === 'JOB_CREATED') {
    badgeStyles = styles.badgeAssigned;
    textStyles = styles.textAssigned;
    const key = normalizedStatus === 'JOB_CREATED' ? 'ASSIGNED' : normalizedStatus;
    const mappedLabel = REQUEST_STATUSES.statuses[key as keyof typeof REQUEST_STATUSES.statuses]?.label || key;
    label = mappedLabel.toUpperCase();
  } else if (['CANCELLED', 'REJECTED', 'DECLINED'].includes(normalizedStatus)) {
    badgeStyles = styles.badgeCancelled;
    textStyles = styles.textCancelled;
    const mappedLabel = REQUEST_STATUSES.statuses[normalizedStatus as keyof typeof REQUEST_STATUSES.statuses]?.label || normalizedStatus;
    label = mappedLabel.toUpperCase();
  } else if (normalizedStatus === 'COMPLETED') {
    badgeStyles = styles.badgeCompleted;
    textStyles = styles.textCompleted;
    label = (REQUEST_STATUSES.statuses.COMPLETED?.label || 'COMPLETED').toUpperCase();
  } else if (normalizedStatus === 'PENDING_REVIEW' || normalizedStatus === 'NEEDS_REVIEW') {
    label = (REQUEST_STATUSES.statuses.PENDING_REVIEW?.label || 'PENDING REVIEW').toUpperCase();
  }

  return (
    <View style={[styles.badge, badgeStyles]} accessible={true} accessibilityLabel={`Status: ${label}`}>
      <Text style={[styles.text, textStyles]}>{label}</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 99,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  text: {
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  badgeNew: {
    backgroundColor: '#f3efe8',
    borderColor: '#e2e8f0',
  },
  textNew: {
    color: '#3c3c3b',
  },
  badgeApproved: {
    backgroundColor: '#edf2ee',
    borderColor: '#c9d9cc',
  },
  textApproved: {
    color: '#2e4d38',
  },
  badgeAssigned: {
    backgroundColor: '#fcf6e9',
    borderColor: '#f1e3c1',
  },
  textAssigned: {
    color: '#8c6412',
  },
  badgeCancelled: {
    backgroundColor: '#fdf2f0',
    borderColor: '#f9d7d2',
  },
  textCancelled: {
    color: '#9b2c1d',
  },
  badgeCompleted: {
    backgroundColor: '#ecfdf5',
    borderColor: '#a7f3d0',
  },
  textCompleted: {
    color: '#065f46',
  },
});
