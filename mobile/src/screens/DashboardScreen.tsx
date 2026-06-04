import React, { useState } from 'react';
import { StyleSheet, View, Text, TouchableOpacity, ActivityIndicator, ScrollView, useWindowDimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ContentContainer } from '../components/ContentContainer';
import { useAuth } from '../auth/useAuth';
import { getAdminRequests } from '../api/client';
import { COLORS } from '../theme/colors';
import { useFocusEffect } from '@react-navigation/native';
import { PetRequest } from '../types';

export const DashboardScreen = () => {
  const { user, role, logout } = useAuth();
  const { width } = useWindowDimensions();
  const isTablet = width >= 768;
  const [stats, setStats] = useState<{
    pending: number;
    approved: number;
    assigned: number;
    todayVisits: number;
    weekVisits: number;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchDashboardStats = async () => {
    setIsLoading(true);
    try {
      const data = await getAdminRequests('ALL');
      const list: PetRequest[] = Array.isArray(data) ? data : data.requests || [];
      
      const pending = list.filter(r => r.status === 'PENDING_REVIEW').length;
      const approved = list.filter(r => r.status === 'APPROVED').length;
      const assigned = list.filter(r => r.status === 'ASSIGNED' || r.status === 'SCHEDULED' || r.status === 'JOB_CREATED').length;
      
      const getLocalDateString = (d: Date) => {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const date = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${date}`;
      };
      
      const today = new Date();
      const todayStr = getLocalDateString(today);
      
      const sevenDaysLater = new Date();
      sevenDaysLater.setDate(today.getDate() + 6); // next 7 days inclusive of today
      const sevenDaysLaterStr = getLocalDateString(sevenDaysLater);
      
      let todayVisits = 0;
      let weekVisits = 0;
      
      list.forEach(r => {
        if (r.selected_dates && Array.isArray(r.selected_dates)) {
          r.selected_dates.forEach(dateStr => {
            if (dateStr === todayStr) {
              todayVisits++;
            }
            if (dateStr >= todayStr && dateStr <= sevenDaysLaterStr) {
              weekVisits++;
            }
          });
        }
      });
      
      setStats({
        pending,
        approved,
        assigned,
        todayVisits,
        weekVisits
      });
    } catch (e: any) {
      console.warn('Failed to retrieve dashboard stats', e);
      const msg = e.message || '';
      if (msg.includes('session expired') || msg.toLowerCase().includes('expired') || msg.toLowerCase().includes('unauthorized')) {
        await logout();
      }
      setStats(null);
    } finally {
      setIsLoading(false);
    }
  };

  useFocusEffect(
    React.useCallback(() => {
      fetchDashboardStats();
    }, [])
  );

  return (
    <SafeAreaView style={styles.container}>
      <ContentContainer>
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
          <View style={styles.header}>
            <Text style={styles.title}>Admin Dashboard</Text>
            <Text style={styles.subtitle}>Welcome back, Ryan</Text>
          </View>

          {/* Stats Grid */}
          <View style={styles.statsGrid}>
            {/* Row 1 */}
            <View style={isTablet ? styles.statsRow : styles.statsRowColumn}>
              <View style={styles.statCardHalf}>
                <Text style={styles.statLabel}>Pending Review</Text>
                {isLoading ? (
                  <ActivityIndicator color={COLORS.primary} size="small" style={styles.spinner} />
                ) : (
                  <Text style={styles.statValue}>{stats !== null ? stats.pending : '--'}</Text>
                )}
                <Text style={styles.statSubText}>Intake queue items</Text>
              </View>

              <View style={styles.statCardHalf}>
                <Text style={styles.statLabel}>Needs Sitter</Text>
                {isLoading ? (
                  <ActivityIndicator color={COLORS.primary} size="small" style={styles.spinner} />
                ) : (
                  <Text style={styles.statValue}>{stats !== null ? stats.approved : '--'}</Text>
                )}
                <Text style={styles.statSubText}>Approved requests</Text>
              </View>
            </View>

            {/* Row 2 */}
            <View style={isTablet ? styles.statsRow : styles.statsRowColumn}>
              <View style={styles.statCardHalf}>
                <Text style={styles.statLabel}>Scheduled</Text>
                {isLoading ? (
                  <ActivityIndicator color={COLORS.primary} size="small" style={styles.spinner} />
                ) : (
                  <Text style={styles.statValue}>{stats !== null ? stats.assigned : '--'}</Text>
                )}
                <Text style={styles.statSubText}>Assigned bookings</Text>
              </View>

              <View style={styles.statCardHalf}>
                <Text style={styles.statLabel}>Today's Visits</Text>
                {isLoading ? (
                  <ActivityIndicator color={COLORS.primary} size="small" style={styles.spinner} />
                ) : (
                  <Text style={[styles.statValue, { color: COLORS.success }]}>{stats !== null ? stats.todayVisits : '--'}</Text>
                )}
                <Text style={styles.statSubText}>Scheduled for today</Text>
              </View>
            </View>

          {/* Row 3 - Full Width */}
          <View style={styles.statCardFull}>
            <Text style={styles.statLabel}>This Week's Visits</Text>
            {isLoading ? (
              <ActivityIndicator color={COLORS.primary} size="small" style={styles.spinner} />
            ) : (
              <Text style={[styles.statValue, { color: COLORS.primary }]}>{stats !== null ? stats.weekVisits : '--'}</Text>
            )}
            <Text style={styles.statSubText}>Next 7 days visits</Text>
          </View>
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
          <Text style={styles.infoTitle}>🚀 Mobile Operations Active</Text>
          <Text style={styles.infoText}>
            Connected directly to the live production API Gateway. 
            All statistics and calendar features are live.
          </Text>
        </View>

        <TouchableOpacity style={styles.button} onPress={logout}>
          <Text style={styles.buttonText}>Log Out</Text>
        </TouchableOpacity>
        </ScrollView>
      </ContentContainer>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  scrollContent: {
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
  statsGrid: {
    marginBottom: 20,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
    gap: 12,
  },
  statsRowColumn: {
    flexDirection: 'column',
    marginBottom: 12,
    gap: 12,
  },
  statCardHalf: {
    flex: 1,
    backgroundColor: COLORS.cardBg,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    shadowColor: COLORS.text,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.02,
    shadowRadius: 8,
    elevation: 2,
  },
  statCardFull: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    shadowColor: COLORS.text,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.02,
    shadowRadius: 8,
    elevation: 2,
    marginBottom: 12,
  },
  statLabel: {
    fontSize: 12,
    fontWeight: '800',
    color: COLORS.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  statValue: {
    fontSize: 28,
    fontWeight: '800',
    color: COLORS.primary,
    marginVertical: 6,
  },
  spinner: {
    marginVertical: 12,
    alignSelf: 'flex-start',
  },
  statSubText: {
    fontSize: 11,
    color: COLORS.textMuted,
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
    marginBottom: 24,
  },
  buttonText: {
    color: COLORS.white,
    fontSize: 16,
    fontWeight: '700',
  },
});
