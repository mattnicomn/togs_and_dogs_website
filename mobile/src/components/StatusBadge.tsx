import React from 'react';
import { StyleSheet, View, Text } from 'react-native';

interface StatusBadgeProps {
  status: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const normalizedStatus = (status || '').toUpperCase();
  
  let badgeStyles = styles.badgeNew;
  let textStyles = styles.textNew;
  let label = 'PENDING REVIEW';

  if (normalizedStatus === 'APPROVED') {
    badgeStyles = styles.badgeApproved;
    textStyles = styles.textApproved;
    label = 'APPROVED';
  } else if (normalizedStatus === 'ASSIGNED' || normalizedStatus === 'JOB_CREATED') {
    badgeStyles = styles.badgeAssigned;
    textStyles = styles.textAssigned;
    label = 'ASSIGNED';
  } else if (['CANCELLED', 'REJECTED', 'DECLINED'].includes(normalizedStatus)) {
    badgeStyles = styles.badgeCancelled;
    textStyles = styles.textCancelled;
    label = normalizedStatus;
  } else if (normalizedStatus === 'COMPLETED') {
    badgeStyles = styles.badgeCompleted;
    textStyles = styles.textCompleted;
    label = 'COMPLETED';
  } else {
    label = normalizedStatus || 'PENDING REVIEW';
  }

  return (
    <View style={[styles.badge, badgeStyles]}>
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
