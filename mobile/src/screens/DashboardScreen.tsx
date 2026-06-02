import React from 'react';
import { StyleSheet, View, Text, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../auth/useAuth';
import { COLORS } from '../theme/colors';

export const DashboardScreen = () => {
  const { user, role, logout } = useAuth();

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Admin Dashboard</Text>
        <Text style={styles.subtitle}>Welcome back, Ryan</Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardHeader}>User Identity Details</Text>
        <View style={styles.row}>
          <Text style={styles.label}>Active Email:</Text>
          <Text style={styles.value}>{user}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>Effective Role:</Text>
          <Text style={styles.roleBadge}>{role}</Text>
        </View>
      </View>

      <View style={styles.infoCard}>
        <Text style={styles.infoTitle}>🚀 Mobile Operations Foundation</Text>
        <Text style={styles.infoText}>
          API connections and secure Cognito sessions are successfully established. 
          Real-time queues and intake reviews will render in subsequent phase updates.
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
  card: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 12,
    padding: 20,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    shadowColor: COLORS.text,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.02,
    shadowRadius: 8,
    elevation: 2,
    marginBottom: 20,
  },
  cardHeader: {
    fontSize: 16,
    fontWeight: '700',
    color: COLORS.text,
    marginBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
    paddingBottom: 8,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  label: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.textMuted,
  },
  value: {
    fontSize: 14,
    fontWeight: '600',
    color: COLORS.text,
  },
  roleBadge: {
    backgroundColor: '#edf2ee',
    color: '#2e4d38',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 99,
    fontSize: 12,
    fontWeight: '800',
    textTransform: 'uppercase',
  },
  infoCard: {
    backgroundColor: '#fffbeb',
    borderColor: '#fef3c7',
    borderWidth: 1,
    borderRadius: 12,
    padding: 20,
    marginBottom: 32,
  },
  infoTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#854d0e',
    marginBottom: 8,
  },
  infoText: {
    fontSize: 14,
    color: '#713f12',
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
