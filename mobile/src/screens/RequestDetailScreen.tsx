import React, { useState } from 'react';
import {
  StyleSheet,
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Linking,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useStaff } from '../hooks/useStaff';
import { RequestCard } from '../components/RequestCard';
import { StatusBadge } from '../components/StatusBadge';
import { COLORS } from '../theme/colors';

export const RequestDetailScreen = ({ route }: any) => {
  const initialRequest = route.params?.request || null;
  const [request, setRequest] = useState<any>(initialRequest);
  const { staff, isLoading: isStaffLoading, error: staffError, refresh: refreshStaff } = useStaff();

  const handleActionSuccess = (updatedRequest?: any) => {
    if (updatedRequest) {
      setRequest(updatedRequest);
    }
  };

  if (!request) {
    return (
      <SafeAreaView style={styles.centerContainer}>
        <Text style={styles.errorText}>No booking details provided.</Text>
      </SafeAreaView>
    );
  }

  const openMaps = (address: string) => {
    if (!address) return;
    const query = encodeURIComponent(address);
    const url = Platform.OS === 'ios' ? `maps://app?q=${query}` : `geo:0,0?q=${query}`;
    Linking.openURL(url).catch((err) => console.warn('Failed to open Maps', err));
  };

  const openPhone = (phone: string) => {
    if (!phone) return;
    const cleaned = phone.replace(/[^\d+]/g, '');
    Linking.openURL(`tel:${cleaned}`).catch((err) => console.warn('Failed to open phone dialer', err));
  };

  const openEmail = (email: string) => {
    if (!email) return;
    Linking.openURL(`mailto:${email}`).catch((err) => console.warn('Failed to open email client', err));
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

  // Resolve emergency contact
  const emergencyContact = request.emergency_contact_info || request.emergency_contact;
  const hasEmergencyContact = emergencyContact && (emergencyContact.name || emergencyContact.phone);

  // Resolve vet info
  const vetInfo = request.vet_info;
  const hasVetInfo = vetInfo && (vetInfo.vet_name || vetInfo.clinic_name || vetInfo.clinic_phone || vetInfo.clinic_address);

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scrollContent}>
        
        {/* Core Status Summary */}
        <View style={styles.card}>
          <View style={styles.rowBetween}>
            <Text style={styles.petTitle}>🐾 {request.pet_name}</Text>
            <StatusBadge status={request.status} />
          </View>
          
          <View style={styles.divider} />
          
          <View style={styles.detailGrid}>
            <View style={styles.detailCol}>
              <Text style={styles.metaLabel}>Service</Text>
              <Text style={styles.metaValue}>{formatServiceType(request.service_type)}</Text>
            </View>
            <View style={styles.detailCol}>
              <Text style={styles.metaLabel}>Window</Text>
              <Text style={styles.metaValue}>{request.timeframe || 'Anytime'}</Text>
            </View>
          </View>

          <View style={styles.metaRow}>
            <Text style={styles.metaLabel}>Selected Dates</Text>
            <Text style={styles.metaValue}>{formatDateRange(request.selected_dates)}</Text>
          </View>
          {request.selected_dates && request.selected_dates.length > 1 && (
            <Text style={styles.datesSubText}>
              Dates: {request.selected_dates.join(', ')}
            </Text>
          )}

          {(request.worker_name || request.assigned_sitter) && (
            <View style={styles.metaRow}>
              <Text style={styles.metaLabel}>Assigned Sitter</Text>
              <Text style={[styles.metaValue, { color: COLORS.primary }]}>
                👤 {request.worker_name || request.assigned_sitter}
              </Text>
            </View>
          )}
        </View>

        {/* Client Contact Info */}
        <View style={styles.card}>
          <Text style={styles.sectionHeader}>Client Information</Text>
          
          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Owner Name:</Text>
            <Text style={styles.infoValue}>{request.client_name || 'Not provided'}</Text>
          </View>

          {request.phone || request.client_phone ? (
            <TouchableOpacity 
              style={styles.actionRow} 
              onPress={() => openPhone(request.phone || request.client_phone)}
              activeOpacity={0.7}
            >
              <Text style={styles.infoLabel}>Phone:</Text>
              <Text style={[styles.infoValue, styles.linkText]}>
                📞 {request.phone || request.client_phone}
              </Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Phone:</Text>
              <Text style={styles.infoValue}>Not provided</Text>
            </View>
          )}

          {request.client_email || request.email ? (
            <TouchableOpacity 
              style={styles.actionRow} 
              onPress={() => openEmail(request.client_email || request.email)}
              activeOpacity={0.7}
            >
              <Text style={styles.infoLabel}>Email Address:</Text>
              <Text style={[styles.infoValue, styles.linkText]}>
                ✉️ {request.client_email || request.email}
              </Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Email:</Text>
              <Text style={styles.infoValue}>Not provided</Text>
            </View>
          )}

          {request.address ? (
            <TouchableOpacity 
              style={styles.actionRow} 
              onPress={() => openMaps(request.address)}
              activeOpacity={0.7}
            >
              <Text style={styles.infoLabel}>Service Address:</Text>
              <Text style={[styles.infoValue, styles.linkText]}>
                📍 {request.address}
              </Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Address:</Text>
              <Text style={styles.infoValue}>Not provided</Text>
            </View>
          )}
        </View>

        {/* Pet Profiles Details */}
        {request.pets && Array.isArray(request.pets) && request.pets.length > 0 ? (
          request.pets.map((pet: any, idx: number) => (
            <View key={pet.name || idx} style={styles.card}>
              <Text style={styles.sectionHeader}>🐾 Pet Profile: {pet.name || 'Unknown'}</Text>
              
              <View style={styles.detailGrid}>
                <View style={styles.detailCol}>
                  <Text style={styles.metaLabel}>Species / Breed</Text>
                  <Text style={styles.metaValue}>
                    {pet.species || 'Not provided'} {pet.breed ? `(${pet.breed})` : ''}
                  </Text>
                </View>
                <View style={styles.detailCol}>
                  <Text style={styles.metaLabel}>Age</Text>
                  <Text style={styles.metaValue}>{pet.age || 'Not provided'}</Text>
                </View>
              </View>

              <View style={styles.divider} />

              <View style={styles.noteSection}>
                <Text style={styles.noteLabel}>Feeding Notes</Text>
                <Text style={styles.noteText}>{pet.feeding_notes || 'None provided'}</Text>
              </View>

              <View style={styles.noteSection}>
                <Text style={styles.noteLabel}>Medication Notes</Text>
                <Text style={styles.noteText}>{pet.medication_notes || 'None provided'}</Text>
              </View>

              <View style={styles.noteSection}>
                <Text style={styles.noteLabel}>Behavioral / Care Notes</Text>
                <Text style={styles.noteText}>{pet.behavior_notes || 'None provided'}</Text>
              </View>
            </View>
          ))
        ) : (
          <View style={styles.card}>
            <Text style={styles.sectionHeader}>Pet Information</Text>
            <Text style={styles.infoValue}>No detailed pet profile list provided.</Text>
          </View>
        )}

        {/* Emergency Contact */}
        {hasEmergencyContact && (
          <View style={styles.card}>
            <Text style={styles.sectionHeader}>Emergency Contact</Text>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Name:</Text>
              <Text style={styles.infoValue}>{emergencyContact.name || 'Not provided'}</Text>
            </View>
            {emergencyContact.phone ? (
              <TouchableOpacity 
                style={styles.actionRow} 
                onPress={() => openPhone(emergencyContact.phone)}
                activeOpacity={0.7}
              >
                <Text style={styles.infoLabel}>Phone:</Text>
                <Text style={[styles.infoValue, styles.linkText]}>
                  📞 {emergencyContact.phone}
                </Text>
              </TouchableOpacity>
            ) : (
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Phone:</Text>
                <Text style={styles.infoValue}>Not provided</Text>
              </View>
            )}
          </View>
        )}

        {/* Vet Information */}
        {hasVetInfo && (
          <View style={styles.card}>
            <Text style={styles.sectionHeader}>Veterinary Information</Text>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Clinic:</Text>
              <Text style={styles.infoValue}>{vetInfo.clinic_name || 'Not provided'}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Vet Name:</Text>
              <Text style={styles.infoValue}>{vetInfo.vet_name || 'Not provided'}</Text>
            </View>
            {vetInfo.clinic_phone ? (
              <TouchableOpacity 
                style={styles.actionRow} 
                onPress={() => openPhone(vetInfo.clinic_phone)}
                activeOpacity={0.7}
              >
                <Text style={styles.infoLabel}>Clinic Phone:</Text>
                <Text style={[styles.infoValue, styles.linkText]}>
                  📞 {vetInfo.clinic_phone}
                </Text>
              </TouchableOpacity>
            ) : (
              <View style={styles.infoRow}>
                <Text style={styles.infoLabel}>Phone:</Text>
                <Text style={styles.infoValue}>Not provided</Text>
              </View>
            )}
            {vetInfo.clinic_address && (
              <TouchableOpacity 
                style={styles.actionRow} 
                onPress={() => openMaps(vetInfo.clinic_address)}
                activeOpacity={0.7}
              >
                <Text style={styles.infoLabel}>Clinic Address:</Text>
                <Text style={[styles.infoValue, styles.linkText]}>
                  📍 {vetInfo.clinic_address}
                </Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        {/* Special Instructions */}
        {request.special_instructions && (
          <View style={styles.card}>
            <Text style={styles.sectionHeader}>Special Instructions</Text>
            <Text style={styles.instructionText}>{request.special_instructions}</Text>
          </View>
        )}

        {/* Administrative Quick Actions Card */}
        <Text style={styles.quickActionsTitle}>Administrative Actions</Text>
        <RequestCard
          request={request}
          onApproveSuccess={handleActionSuccess}
          staffList={staff}
          isStaffLoading={isStaffLoading}
          staffError={staffError}
          refreshStaff={refreshStaff}
          defaultExpanded={true}
          isDetailView={true}
        />
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  scrollContent: {
    padding: 16,
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    backgroundColor: COLORS.background,
  },
  card: {
    backgroundColor: COLORS.cardBg,
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    shadowColor: COLORS.text,
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.02,
    shadowRadius: 6,
    elevation: 2,
    marginBottom: 12,
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  petTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: COLORS.text,
  },
  divider: {
    height: 1,
    backgroundColor: COLORS.borderSoft,
    marginVertical: 12,
  },
  detailGrid: {
    flexDirection: 'row',
    marginBottom: 10,
  },
  detailCol: {
    flex: 1,
  },
  metaLabel: {
    fontSize: 11,
    fontWeight: '800',
    color: COLORS.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  metaValue: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.text,
    marginTop: 2,
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 6,
  },
  datesSubText: {
    fontSize: 12,
    color: COLORS.textMuted,
    marginTop: 4,
    fontWeight: '500',
  },
  sectionHeader: {
    fontSize: 15,
    fontWeight: '800',
    color: COLORS.text,
    marginBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.borderSoft,
    paddingBottom: 6,
  },
  infoRow: {
    flexDirection: 'row',
    paddingVertical: 4,
    alignItems: 'flex-start',
  },
  actionRow: {
    flexDirection: 'row',
    paddingVertical: 6,
    alignItems: 'flex-start',
  },
  infoLabel: {
    width: 120,
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.textMuted,
  },
  infoValue: {
    flex: 1,
    fontSize: 13,
    color: COLORS.text,
    fontWeight: '600',
  },
  linkText: {
    color: COLORS.info,
    fontWeight: '700',
  },
  noteSection: {
    marginBottom: 10,
  },
  noteLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: COLORS.textMuted,
  },
  noteText: {
    fontSize: 13,
    color: COLORS.text,
    marginTop: 2,
    fontWeight: '500',
  },
  instructionText: {
    fontSize: 13,
    color: COLORS.text,
    lineHeight: 18,
    fontWeight: '500',
  },
  quickActionsTitle: {
    fontSize: 13,
    fontWeight: '800',
    color: COLORS.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: 12,
    marginBottom: 8,
    paddingLeft: 4,
  },
  errorText: {
    fontSize: 14,
    color: COLORS.danger,
    fontWeight: '700',
  },
});
