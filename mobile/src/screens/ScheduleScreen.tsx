import React from 'react';
import { StyleSheet, View, Text, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../auth/useAuth';
import { COLORS } from '../theme/colors';

export const ScheduleScreen = () => {
  const { logout } = useAuth();

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>My Daily Schedule</Text>
        <Text style={styles.subtitle}>Visits and pet care assignments</Text>
      </View>

      <View style={styles.placeholderCard}>
        <Text style={styles.placeholderIcon}>🗓️</Text>
        <Text style={styles.placeholderTitle}>Staff Visits Calendar</Text>
        <Text style={styles.placeholderText}>
          Your daily schedule list will render here.
          This placeholder verifies the tab router correctly segments staff-specific screens and permissions.
        </Text>
      </View>

      <TouchableOpacity style={styles.button} onPress={logout}>
        <Text style={styles.buttonText}>Log Out</Text>
      </TouchableOpacity>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
    padding: 24,
  },
  header: {
    marginBottom: 24,
  },
  title: {
    fontSize: 24,
    fontWeight: '800',
    color: COLORS.text,
  },
  subtitle: {
    fontSize: 16,
    color: COLORS.textMuted,
    marginTop: 4,
    fontWeight: '600',
  },
  placeholderCard: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 12,
    padding: 32,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    shadowColor: COLORS.text,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.02,
    shadowRadius: 8,
    elevation: 2,
    marginBottom: 32,
  },
  placeholderIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  placeholderTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: COLORS.text,
    marginBottom: 8,
  },
  placeholderText: {
    fontSize: 14,
    color: COLORS.textMuted,
    textAlign: 'center',
    lineHeight: 20,
  },
  button: {
    backgroundColor: COLORS.danger,
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 'auto',
  },
  buttonText: {
    color: COLORS.white,
    fontSize: 16,
    fontWeight: '700',
  },
});
