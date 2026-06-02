import React, { useState, useEffect, useCallback } from 'react';
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
import { getAdminRequests } from '../api/client';
import { RequestCard } from '../components/RequestCard';
import { PetRequest } from '../types';
import { COLORS } from '../theme/colors';
import { useAuth } from '../auth/useAuth';

interface FilterPill {
  label: string;
  status: string;
}

export const RequestListScreen = () => {
  const { logout } = useAuth();
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
      setError(e.message || 'Failed to retrieve operational requests. Please retry.');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchRequests(activeFilter);
  }, [activeFilter, fetchRequests]);

  const handleRefresh = () => {
    fetchRequests(activeFilter, true);
  };

  const handleFilterChange = (status: string) => {
    setActiveFilter(status);
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View>
          <Text style={styles.title}>Intake Requests</Text>
          <Text style={styles.subtitle}>Review booking queue details</Text>
        </View>
        <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
          <Text style={styles.logoutText}>Log Out</Text>
        </TouchableOpacity>
      </View>

      {/* Categories Filter Pills */}
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

      {/* Requests Feed */}
      {isLoading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={COLORS.primary} />
          <Text style={styles.loadingText}>Fetching booking details...</Text>
        </View>
      ) : error ? (
        <View style={styles.centerContainer}>
          <Text style={styles.errorIcon}>⚠️</Text>
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.retryBtn} onPress={() => fetchRequests(activeFilter)}>
            <Text style={styles.retryText}>Retry Connection</Text>
          </TouchableOpacity>
        </View>
      ) : requests.length === 0 ? (
        <FlatList
          data={[]}
          renderItem={null}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={handleRefresh}
              tintColor={COLORS.primary}
            />
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon}>📋</Text>
              <Text style={styles.emptyTitle}>Queue is Empty</Text>
              <Text style={styles.emptySub}>
                No requests currently match the selected status category filter.
              </Text>
            </View>
          }
          contentContainerStyle={styles.listContent}
        />
      ) : (
        <FlatList
          data={requests}
          keyExtractor={(item) => item.request_id}
          renderItem={({ item }) => <RequestCard request={item} onApproveSuccess={handleRefresh} />}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={handleRefresh}
              tintColor={COLORS.primary}
            />
          }
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
        />
      )}
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
