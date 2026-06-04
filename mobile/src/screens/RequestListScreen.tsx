import React, { useState, useCallback } from 'react';
import {
  StyleSheet,
  View,
  Text,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect } from '@react-navigation/native';
import { ContentContainer } from '../components/ContentContainer';
import { getAdminRequests } from '../api/client';
import { RequestCard } from '../components/RequestCard';
import { PetRequest } from '../types';
import { COLORS } from '../theme/colors';
import { useAuth } from '../auth/useAuth';
import { useStaff } from '../hooks/useStaff';

interface FilterPill {
  label: string;
  status: string;
}

export const RequestListScreen = () => {
  const { logout } = useAuth();
  const { staff, isLoading: isStaffLoading, error: staffError, refresh: refreshStaff } = useStaff();
  const [requests, setRequests] = useState<PetRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState('PENDING_REVIEW');

  const filters: FilterPill[] = [
    { label: 'Pending', status: 'PENDING_REVIEW' },
    { label: 'Approved', status: 'APPROVED' },
    { label: 'Assigned', status: 'ASSIGNED' },
    { label: 'All Active', status: 'ALL' },
    { label: 'Completed', status: 'COMPLETED' },
    { label: 'Cancelled', status: 'CANCELLED' },
  ];

  const fetchRequests = useCallback(async (filterStatus: string, showRefreshingIndicator = false) => {
    if (showRefreshingIndicator) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const data = await getAdminRequests(filterStatus);
      // Backend returns either array directly or { requests: [] }
      const requestList = Array.isArray(data) ? data : data.requests || [];
      
      // Sort requestList to put newest first (by created_at or request_id)
      const sorted = [...requestList].sort((a, b) => {
        return (b.created_at || b.request_id || '').localeCompare(a.created_at || a.request_id || '');
      });

      setRequests(sorted);
    } catch (e: any) {
      const msg = e.message || '';
      if (msg.includes('session expired') || msg.toLowerCase().includes('expired') || msg.toLowerCase().includes('unauthorized')) {
        setError('Your session expired. Please sign in again.');
        await logout();
      } else {
        setError(msg || 'Failed to retrieve operational requests. Please retry.');
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      fetchRequests(activeFilter);
    }, [activeFilter, fetchRequests])
  );

  const handleRefresh = () => {
    fetchRequests(activeFilter, true);
  };

  const handleFilterChange = (status: string) => {
    setActiveFilter(status);
  };

  // Stable header + filter pills rendered outside VirtualizedList context
  const ListHeader = () => (
    <View>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Intake Requests</Text>
          <Text style={styles.subtitle}>Review booking queue details</Text>
        </View>
        <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
          <Text style={styles.logoutText}>Log Out</Text>
        </TouchableOpacity>
      </View>

      {/* Categories Filter Pills — horizontal ScrollView is NOT a sibling of the FlatList */}
      <View style={styles.filterOuterContainer}>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.filterContainer}
        >
          {filters.map((filter) => {
            const isActive = activeFilter === filter.status;
            return (
              <TouchableOpacity
                key={filter.status}
                style={[styles.pill, isActive && styles.pillActive]}
                onPress={() => handleFilterChange(filter.status)}
              >
                <Text style={[styles.pillText, isActive && styles.pillTextActive]}>
                  {filter.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </ScrollView>
      </View>
    </View>
  );

  const getEmptyStateDetails = () => {
    switch (activeFilter) {
      case 'PENDING_REVIEW':
        return {
          title: 'All Caught Up',
          message: 'No pending requests to review. ✓',
          icon: '✨',
        };
      case 'APPROVED':
        return {
          title: 'Fully Handled',
          message: 'All approved bookings have been assigned.',
          icon: '👍',
        };
      case 'ASSIGNED':
        return {
          title: 'No Assigned Bookings',
          message: 'No assigned visits in this view.',
          icon: '👥',
        };
      case 'ALL':
        return {
          title: 'No Active Bookings',
          message: 'No active bookings at this time.',
          icon: '📋',
        };
      case 'COMPLETED':
        return {
          title: 'No Completed Visits',
          message: 'No completed visits recorded.',
          icon: '✅',
        };
      case 'CANCELLED':
        return {
          title: 'No Cancelled Bookings',
          message: 'No cancelled bookings.',
          icon: '❌',
        };
      default:
        return {
          title: 'Queue is Empty',
          message: 'No requests currently match the selected status category filter.',
          icon: '📋',
        };
    }
  };

  const emptyState = getEmptyStateDetails();

  // Body content when list is loading or errored
  if (isLoading) {
    return (
      <SafeAreaView style={styles.container}>
        <ContentContainer>
          <ListHeader />
          <View style={styles.centerContainer}>
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text style={styles.loadingText}>Fetching booking details...</Text>
          </View>
        </ContentContainer>
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={styles.container}>
        <ContentContainer>
          <ListHeader />
          <View style={styles.centerContainer}>
            <Text style={styles.errorIcon}>⚠️</Text>
            <Text style={styles.errorText}>{error}</Text>
            <TouchableOpacity style={styles.retryBtn} onPress={() => fetchRequests(activeFilter)}>
              <Text style={styles.retryText}>Retry Connection</Text>
            </TouchableOpacity>
          </View>
        </ContentContainer>
      </SafeAreaView>
    );
  }

  // Single FlatList owns the full scroll surface — header is in ListHeaderComponent,
  // not a ScrollView sibling, which eliminates the VirtualizedList key warning.
  return (
    <SafeAreaView style={styles.container}>
      <ContentContainer>
        <FlatList
          data={requests}
          keyExtractor={(item) => item.request_id || `req-${item.client_id}-${item.created_at}`}
          renderItem={({ item }) => (
            <RequestCard
              request={item}
              onApproveSuccess={handleRefresh}
              staffList={staff}
              isStaffLoading={isStaffLoading}
              staffError={staffError}
              refreshStaff={refreshStaff}
            />
          )}
          ListHeaderComponent={<ListHeader />}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={handleRefresh}
              tintColor={COLORS.primary}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon}>{emptyState.icon}</Text>
              <Text style={styles.emptyTitle}>{emptyState.title}</Text>
              <Text style={styles.emptySub}>{emptyState.message}</Text>
            </View>
          }
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
        />
      </ContentContainer>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 8,
  },
  title: {
    fontSize: 24,
    fontWeight: '800',
    color: COLORS.text,
  },
  subtitle: {
    fontSize: 14,
    color: COLORS.textMuted,
    marginTop: 2,
    fontWeight: '600',
  },
  logoutBtn: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: COLORS.danger,
    backgroundColor: 'transparent',
  },
  logoutText: {
    color: COLORS.danger,
    fontSize: 12,
    fontWeight: '700',
  },
  filterOuterContainer: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.borderSoft,
  },
  filterContainer: {
    paddingHorizontal: 24,
    gap: 8,
  },
  pill: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 99,
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderColor: COLORS.border,
  },
  pillActive: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  pillText: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.text,
  },
  pillTextActive: {
    color: COLORS.white,
  },
  listContent: {
    padding: 24,
    flexGrow: 1,
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
});
