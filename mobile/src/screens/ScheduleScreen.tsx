import React, { useState, useEffect, useCallback } from 'react';
import {
  StyleSheet,
  View,
  Text,
  FlatList,
  SectionList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../auth/useAuth';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import { getAdminRequests } from '../api/client';
import { PetRequest } from '../types';
import { StatusBadge } from '../components/StatusBadge';
import { COLORS } from '../theme/colors';
import { ContentContainer } from '../components/ContentContainer';

interface ExpandedVisit {
  request_id: string;
  client_id: string;
  client_name: string;
  pet_name: string;
  service_type: string;
  date: string;
  timeframe: string;
  status: string;
  worker_name?: string;
  assigned_sitter?: string;
}

export const ScheduleScreen = () => {
  const { logout, role } = useAuth();
  const navigation = useNavigation<any>();
  const [visits, setVisits] = useState<ExpandedVisit[]>([]);
  const [originalRequests, setOriginalRequests] = useState<PetRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'today' | 'upcoming'>('today');

  const formatServiceType = (service: string) => {
    return (service || '')
      .split('_')
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(' ');
  };

  const formatDisplayDate = (dateStr: string) => {
    if (!dateStr) return '';
    const dateObj = new Date(dateStr + 'T00:00:00');
    return dateObj.toLocaleDateString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const fetchSchedule = useCallback(async (showRefreshingIndicator = false) => {
    if (showRefreshingIndicator) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const data = await getAdminRequests('ALL');
      const requestList = Array.isArray(data) ? data : data.requests || [];
      
      // Filter for active bookings
      const activeStatuses = ['APPROVED', 'ASSIGNED', 'SCHEDULED', 'JOB_CREATED'];
      const activeRequests = requestList.filter((r: PetRequest) => activeStatuses.includes(r.status));

      const getLocalDateString = (d: Date = new Date()) => {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const date = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${date}`;
      };
      
      const todayStr = getLocalDateString();
      const expanded: ExpandedVisit[] = [];

      activeRequests.forEach((req: PetRequest) => {
        if (req.selected_dates && Array.isArray(req.selected_dates)) {
          req.selected_dates.forEach((dateStr: string) => {
            if (dateStr >= todayStr) {
              expanded.push({
                request_id: req.request_id,
                client_id: req.client_id,
                client_name: req.client_name,
                pet_name: req.pet_name,
                service_type: req.service_type,
                date: dateStr,
                timeframe: req.timeframe || 'Anytime',
                status: req.status,
                worker_name: req.worker_name,
                assigned_sitter: req.assigned_sitter,
              });
            }
          });
        }
      });

      // Sort chronologically by date
      expanded.sort((a, b) => a.date.localeCompare(b.date));
      setVisits(expanded);
      setOriginalRequests(requestList);
    } catch (e: any) {
      const msg = e.message || '';
      if (msg.includes('session expired') || msg.toLowerCase().includes('expired') || msg.toLowerCase().includes('unauthorized')) {
        setError('Your session expired. Please sign in again.');
        await logout();
      } else {
        setError(msg || 'Failed to retrieve dispatch schedule. Please retry.');
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      fetchSchedule();
    }, [fetchSchedule])
  );

  const handleRefresh = () => {
    fetchSchedule(true);
  };

  const handleVisitPress = (item: ExpandedVisit) => {
    const original = originalRequests.find((r) => r.request_id === item.request_id);
    if (original) {
      navigation.navigate('RequestDetail', {
        request: original,
      });
    }
  };

  const getLocalDateString = (d: Date = new Date()) => {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const date = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${date}`;
  };

  const getSections = () => {
    const todayStr = getLocalDateString(new Date());
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = getLocalDateString(tomorrow);

    // Filter visits based on activeTab for staff
    const filteredVisits = visits.filter((visit) => {
      if (role === 'staff') {
        if (activeTab === 'today') {
          return visit.date === todayStr;
        } else {
          return visit.date > todayStr;
        }
      }
      return true; // admins/owners see all
    });

    const sectionsMap: { [dateStr: string]: ExpandedVisit[] } = {};
    filteredVisits.forEach((visit) => {
      if (!sectionsMap[visit.date]) {
        sectionsMap[visit.date] = [];
      }
      sectionsMap[visit.date].push(visit);
    });

    const sections = Object.keys(sectionsMap)
      .sort((a, b) => a.localeCompare(b))
      .map((dateStr) => {
        let title = formatDisplayDate(dateStr);
        if (dateStr === todayStr) {
          title = `Today (${title})`;
        } else if (dateStr === tomorrowStr) {
          title = `Tomorrow (${title})`;
        }

        return {
          title,
          dateStr,
          data: sectionsMap[dateStr],
        };
      });

    return sections;
  };

  const renderSectionHeader = ({ section }: { section: { title: string; dateStr: string } }) => {
    const todayStr = getLocalDateString(new Date());
    const isToday = section.dateStr === todayStr;

    return (
      <View style={[styles.sectionHeader, isToday && styles.sectionHeaderToday]}>
        <Text style={[styles.sectionHeaderText, isToday && styles.sectionHeaderTextToday]}>
          {section.title}
        </Text>
      </View>
    );
  };

  const renderVisitCard = ({ item }: { item: ExpandedVisit }) => {
    return (
      <TouchableOpacity
        style={styles.visitCard}
        onPress={() => handleVisitPress(item)}
        activeOpacity={0.7}
      >
        <View style={styles.visitHeader}>
          <Text style={styles.clientPetText}>🐾 {item.pet_name}</Text>
          <StatusBadge status={item.status} />
        </View>
        
        <View style={styles.visitBody}>
          <View style={styles.visitDetails}>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Client:</Text>
              <Text style={styles.detailValue}>{item.client_name}</Text>
            </View>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Service:</Text>
              <Text style={styles.detailValue}>{formatServiceType(item.service_type)}</Text>
            </View>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Window:</Text>
              <Text style={styles.detailValue}>{item.timeframe}</Text>
            </View>
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Staff:</Text>
              <Text style={styles.detailValue}>
                👤 {item.worker_name || item.assigned_sitter || 'Unassigned'}
              </Text>
            </View>
          </View>
        </View>
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.title}>
            {role === 'staff' ? 'My Schedule' : 'Dispatch Schedule'}
          </Text>
          <Text style={styles.subtitle}>
            {role === 'staff' ? 'Your assigned visits and pet care' : 'Visits and pet care assignments'}
          </Text>
        </View>
        <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
          <Text style={styles.logoutText}>Log Out</Text>
        </TouchableOpacity>
      </View>

      {isLoading ? (
        <ContentContainer>
          <View style={styles.centerContainer}>
            <ActivityIndicator size="large" color={COLORS.primary} />
            <Text style={styles.loadingText}>Loading calendar schedule...</Text>
          </View>
        </ContentContainer>
      ) : error ? (
        <ContentContainer>
          <View style={styles.centerContainer}>
            <Text style={styles.errorIcon}>⚠️</Text>
            <Text style={styles.errorText}>{error}</Text>
            <TouchableOpacity style={styles.retryBtn} onPress={() => fetchSchedule()}>
              <Text style={styles.retryText}>Retry Connection</Text>
            </TouchableOpacity>
          </View>
        </ContentContainer>
      ) : (
        <ContentContainer>
          {role === 'staff' && (
            <View style={styles.tabContainer}>
              <TouchableOpacity
                style={[styles.tabButton, activeTab === 'today' && styles.tabButtonActive]}
                onPress={() => setActiveTab('today')}
                activeOpacity={0.7}
              >
                <Text style={[styles.tabButtonText, activeTab === 'today' && styles.tabButtonTextActive]}>
                  Today
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.tabButton, activeTab === 'upcoming' && styles.tabButtonActive]}
                onPress={() => setActiveTab('upcoming')}
                activeOpacity={0.7}
              >
                <Text style={[styles.tabButtonText, activeTab === 'upcoming' && styles.tabButtonTextActive]}>
                  Upcoming
                </Text>
              </TouchableOpacity>
            </View>
          )}
          <SectionList
            sections={getSections()}
            keyExtractor={(item, index) => `${item.request_id}-${item.date}-${index}`}
            renderItem={renderVisitCard}
            renderSectionHeader={renderSectionHeader}
            refreshControl={
              <RefreshControl
                refreshing={isRefreshing}
                onRefresh={handleRefresh}
                tintColor={COLORS.primary}
              />
            }
            ListEmptyComponent={
              role === 'staff' ? (
                activeTab === 'today' ? (
                  <View style={styles.emptyContainer}>
                    <Text style={styles.emptyIcon}>☀️</Text>
                    <Text style={styles.emptyTitle}>No Visits Today</Text>
                    <Text style={styles.emptySub}>
                      You have no assigned visits scheduled for today. Enjoy your day off!
                    </Text>
                  </View>
                ) : (
                  <View style={styles.emptyContainer}>
                    <Text style={styles.emptyIcon}>🗓️</Text>
                    <Text style={styles.emptyTitle}>No Upcoming Visits</Text>
                    <Text style={styles.emptySub}>
                      You have no upcoming assigned visits scheduled. Check back later.
                    </Text>
                  </View>
                )
              ) : (
                <View style={styles.emptyContainer}>
                  <Text style={styles.emptyIcon}>🗓️</Text>
                  <Text style={styles.emptyTitle}>No Upcoming Visits</Text>
                  <Text style={styles.emptySub}>
                    No visits scheduled for today or this week. Check Requests tab for pending approvals.
                  </Text>
                </View>
              )
            }
            contentContainerStyle={styles.listContent}
            showsVerticalScrollIndicator={false}
            stickySectionHeadersEnabled={true}
          />
        </ContentContainer>
      )}
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  sectionHeader: {
    backgroundColor: COLORS.background,
    paddingVertical: 10,
    paddingHorizontal: 24,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.borderSoft,
  },
  sectionHeaderToday: {
    backgroundColor: '#fffbeb',
    borderBottomColor: '#fef3c7',
  },
  sectionHeaderText: {
    fontSize: 12,
    fontWeight: '800',
    color: COLORS.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sectionHeaderTextToday: {
    color: '#854d0e',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.borderSoft,
  },
  headerLeft: {
    flex: 1,
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
  listContent: {
    paddingHorizontal: 24,
    paddingBottom: 24,
    paddingTop: 16,
    flexGrow: 1,
  },
  visitCard: {
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
  visitHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: COLORS.borderSoft,
    paddingBottom: 10,
    marginBottom: 10,
  },
  visitDateText: {
    fontSize: 15,
    fontWeight: '800',
    color: COLORS.text,
  },
  visitBody: {
    gap: 8,
  },
  clientPetText: {
    fontSize: 14,
    color: COLORS.primary,
    fontWeight: '800',
  },
  visitDetails: {
    gap: 4,
  },
  detailRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  detailLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.textMuted,
    width: 80,
  },
  detailValue: {
    fontSize: 13,
    color: COLORS.text,
    fontWeight: '600',
    flex: 1,
  },
  tabContainer: {
    flexDirection: 'row',
    backgroundColor: COLORS.border,
    borderRadius: 8,
    padding: 4,
    marginHorizontal: 24,
    marginTop: 16,
  },
  tabButton: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 6,
  },
  tabButtonActive: {
    backgroundColor: COLORS.white,
    shadowColor: COLORS.text,
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 1,
  },
  tabButtonText: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.textMuted,
  },
  tabButtonTextActive: {
    color: COLORS.primary,
  },
});
