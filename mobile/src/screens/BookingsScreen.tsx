import React, { useState, useCallback } from 'react';
import {
  StyleSheet,
  View,
  Text,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../auth/useAuth';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import { getClientRequests } from '../api/client';
import { COLORS } from '../theme/colors';
import { PetRequest } from '../types';
import { getServiceTypeLabel } from '../utils/serviceLabels';
import { REQUEST_STATUSES } from '../contracts/generatedContracts';

const formatDate = (dateStr: string) => {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'T00:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

const STATUS_LABEL: Record<string, string> = {
  PENDING_REVIEW: REQUEST_STATUSES.statuses.PENDING_REVIEW?.label || 'Pending Review',
  APPROVED: REQUEST_STATUSES.statuses.APPROVED?.label || 'Approved',
  ASSIGNED: 'Scheduled',
  JOB_CREATED: 'Scheduled',
  COMPLETED: REQUEST_STATUSES.statuses.COMPLETED?.label || 'Completed',
  CANCELLED: REQUEST_STATUSES.statuses.CANCELLED?.label || 'Cancelled',
};

const STATUS_COLOR: Record<string, string> = {
  PENDING_REVIEW: '#f59e0b',
  APPROVED: '#3b82f6',
  ASSIGNED: '#10b981',
  JOB_CREATED: '#10b981',
  COMPLETED: '#6b7280',
  CANCELLED: '#ef4444',
};

export const BookingsScreen = () => {
  const navigation = useNavigation<any>();
  const { logout } = useAuth();
  const [requests, setRequests] = useState<PetRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBookings = useCallback(async (showRefreshingIndicator = false) => {
    if (showRefreshingIndicator) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const data = await getClientRequests();
      const list: PetRequest[] = Array.isArray(data)
        ? data
        : (data as any).requests || [];

      // Sort: active first (PENDING/APPROVED/ASSIGNED), then completed, then cancelled
      const statusOrder: Record<string, number> = {
        PENDING_REVIEW: 0,
        APPROVED: 1,
        JOB_CREATED: 2,
        ASSIGNED: 2,
        COMPLETED: 3,
        CANCELLED: 4,
      };
      list.sort((a, b) => {
        const aOrd = statusOrder[a.status] ?? 5;
        const bOrd = statusOrder[b.status] ?? 5;
        if (aOrd !== bOrd) return aOrd - bOrd;
        return (b.created_at || '').localeCompare(a.created_at || '');
      });

      setRequests(list);
    } catch (e: any) {
      const msg = e.message || '';
      if (
        msg.includes('session expired') ||
        msg.toLowerCase().includes('expired') ||
        msg.toLowerCase().includes('unauthorized')
      ) {
        setError('Your session expired. Please sign in again.');
        await logout();
      } else {
        setError(msg || 'Failed to load your appointments. Please try again.');
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      fetchBookings();
    }, [fetchBookings])
  );

  const handleRefresh = () => fetchBookings(true);

  const renderItem = ({ item }: { item: PetRequest }) => {
    const statusLabel = STATUS_LABEL[item.status] ?? item.status;
    const statusColor = STATUS_COLOR[item.status] ?? COLORS.textMuted;
    const dates = item.selected_dates?.length
      ? item.selected_dates.map(formatDate).join(', ')
      : 'Date TBD';

    return (
      <View style={styles.card}>
        <View style={styles.cardHeader}>
          <Text style={styles.petName}>🐾 {item.pet_name}</Text>
          <View style={[styles.statusBadge, { backgroundColor: statusColor + '22', borderColor: statusColor }]}>
            <Text style={[styles.statusText, { color: statusColor }]}>{statusLabel}</Text>
          </View>
        </View>

        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Service:</Text>
          <Text style={styles.detailValue}>{getServiceTypeLabel(item.service_type)}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Date(s):</Text>
          <Text style={styles.detailValue} numberOfLines={2}>{dates}</Text>
        </View>
        {item.worker_name || item.assigned_sitter ? (
          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Sitter:</Text>
            <Text style={styles.detailValue}>👤 {item.worker_name || item.assigned_sitter}</Text>
          </View>
        ) : null}
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerTitleRow}>
          <View>
            <Text style={styles.title}>My Appointments</Text>
            <Text style={styles.subtitle}>Your booked pet care visits</Text>
          </View>
          <TouchableOpacity
            style={styles.bookCareBtn}
            onPress={() => navigation.navigate('IntakeScreen')}
          >
            <Text style={styles.bookCareBtnText}>+ Book Care</Text>
          </TouchableOpacity>
        </View>
      </View>

      {isLoading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={COLORS.primary} />
          <Text style={styles.loadingText}>Loading your appointments...</Text>
        </View>
      ) : error ? (
        <View style={styles.centerContainer}>
          <Text style={styles.errorIcon}>⚠️</Text>
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => fetchBookings()}>
            <Text style={styles.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={requests}
          keyExtractor={(item) => item.request_id}
          renderItem={renderItem}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={handleRefresh}
              tintColor={COLORS.primary}
            />
          }
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon}>🐕</Text>
              <Text style={styles.emptyTitle}>No Appointments Yet</Text>
              <Text style={styles.emptySub}>
                You don't have any bookings on file yet. Book your first pet care visit below!
              </Text>
              <TouchableOpacity
                style={styles.emptyBookBtn}
                onPress={() => navigation.navigate('IntakeScreen')}
              >
                <Text style={styles.emptyBookBtnText}>+ Book Pet Care</Text>
              </TouchableOpacity>
            </View>
          }
        />
      )}

      <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
        <Text style={styles.logoutText}>Log Out</Text>
      </TouchableOpacity>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  header: {
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.borderSoft,
  },
  title: {
    fontSize: 24,
    fontWeight: '800',
    color: COLORS.text,
  },
  subtitle: {
    fontSize: 15,
    color: COLORS.textMuted,
    marginTop: 4,
    fontWeight: '600',
  },
  listContent: {
    padding: 24,
    paddingBottom: 8,
    flexGrow: 1,
  },
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
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.borderSoft,
    paddingBottom: 10,
  },
  petName: {
    fontSize: 15,
    fontWeight: '800',
    color: COLORS.primary,
    flex: 1,
  },
  statusBadge: {
    borderWidth: 1,
    borderRadius: 99,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '700',
  },
  detailRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 6,
  },
  detailLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.textMuted,
    width: 70,
  },
  detailValue: {
    fontSize: 13,
    color: COLORS.text,
    fontWeight: '600',
    flex: 1,
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: COLORS.textMuted,
    fontWeight: '600',
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
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 80,
  },
  emptyIcon: {
    fontSize: 64,
    marginBottom: 16,
    opacity: 0.8,
  },
  emptyTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: COLORS.text,
    marginBottom: 8,
  },
  emptySub: {
    fontSize: 13,
    color: COLORS.textMuted,
    textAlign: 'center',
    lineHeight: 18,
    paddingHorizontal: 32,
  },
  logoutBtn: {
    backgroundColor: COLORS.danger,
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    margin: 24,
    marginTop: 8,
  },
  logoutText: {
    color: COLORS.white,
    fontSize: 16,
    fontWeight: '700',
  },
  headerTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  bookCareBtn: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  bookCareBtnText: {
    color: COLORS.white,
    fontWeight: '800',
    fontSize: 13,
  },
  emptyBookBtn: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderRadius: 8,
    marginTop: 16,
  },
  emptyBookBtnText: {
    color: COLORS.white,
    fontWeight: '800',
    fontSize: 14,
  },
});
