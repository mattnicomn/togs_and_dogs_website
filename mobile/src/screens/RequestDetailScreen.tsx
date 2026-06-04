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
import { StatusBadge } from '../components/StatusBadge';
import { COLORS } from '../theme/colors';
import { ContentContainer } from '../components/ContentContainer';
import { reviewRequest, assignWorker } from '../api/client';
import { useAuth } from '../auth/useAuth';
import { ConfirmationModal } from '../components/ConfirmationModal';
import { StaffPickerSheet } from '../components/StaffPickerSheet';

export const RequestDetailScreen = ({ route }: any) => {
  const { logout } = useAuth();
  const initialRequest = route.params?.request || null;
  const [request, setRequest] = useState<any>(initialRequest);
  const { staff, isLoading: isStaffLoading, error: staffError, refresh: refreshStaff } = useStaff();

  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showStaffPicker, setShowStaffPicker] = useState(false);
  const [showAssignConfirmModal, setShowAssignConfirmModal] = useState(false);
  const [selectedStaff, setSelectedStaff] = useState<{ emailOrDisplayName: string; displayName: string } | null>(null);
  const [isMutating, setIsMutating] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);

  const handleApprove = async () => {
    setMutationError(null);
    setIsMutating(true);
    try {
      await reviewRequest(request.request_id, request.client_id, 'APPROVED');
      setShowConfirmModal(false);
      const updated = {
        ...request,
        status: 'APPROVED',
      };
      setRequest(updated);
    } catch (error: any) {
      const msg = error.message || '';
      if (msg.toLowerCase().includes('unauthorized') || msg.toLowerCase().includes('expired')) {
        await logout();
      } else {
        setMutationError(msg || 'An error occurred during approval.');
      }
    } finally {
      setIsMutating(false);
    }
  };

  const handleAssignPress = () => {
    const jobId = request.job_id || (request.job_ids && request.job_ids.length > 0 ? request.job_ids[0] : null);
    if (!jobId) {
      setMutationError("This booking is still initializing and cannot be assigned yet.");
      return;
    }
    setMutationError(null);
    setShowStaffPicker(true);
  };

  const handleSelectStaff = (emailOrDisplayName: string, displayName: string) => {
    setSelectedStaff({ emailOrDisplayName, displayName });
    setShowStaffPicker(false);
    setShowAssignConfirmModal(true);
  };

  const handleConfirmAssignment = async () => {
    if (!selectedStaff) return;
    setMutationError(null);
    setIsMutating(true);
    try {
      const reqId = request.request_id;
      const jobId = request.job_id || (request.job_ids && request.job_ids.length > 0 ? request.job_ids[0] : null);
      const clientId = request.client_id;
      const workerId = selectedStaff.emailOrDisplayName;
      const workerName = selectedStaff.displayName;

      if (!jobId) {
        throw new Error('This booking is still initializing and cannot be assigned yet.');
      }

      if (!reqId || !clientId) {
        throw new Error('Error: Record has no valid Request or Client ID.');
      }

      await assignWorker(jobId, reqId, clientId, workerId, workerName);
      setShowAssignConfirmModal(false);
      const updated = {
        ...request,
        status: 'ASSIGNED',
        worker_id: workerId,
        worker_name: workerName,
        assigned_sitter_id: workerId,
        assigned_sitter: workerName,
      };
      setRequest(updated);
    } catch (error: any) {
      const msg = error.message || '';
      if (msg.toLowerCase().includes('unauthorized') || msg.toLowerCase().includes('expired')) {
        await logout();
      } else {
        setMutationError(msg || 'An error occurred during staff assignment.');
      }
    } finally {
      setIsMutating(false);
      setSelectedStaff(null);
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

  const isPending = request.status === 'PENDING_REVIEW';
  const isApproved = request.status === 'APPROVED';
  const isAssigned = ['ASSIGNED', 'SCHEDULED', 'JOB_CREATED'].includes(request.status);
  const showFooter = isPending || isApproved || isAssigned;

  return (
    <SafeAreaView style={styles.container}>
      <ContentContainer>
        <ScrollView 
          showsVerticalScrollIndicator={false} 
          contentContainerStyle={[styles.scrollContent, { paddingBottom: showFooter ? 110 : 24 }]}
        >
          
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
        </ScrollView>

        {/* Sticky Action Footer */}
        {showFooter && (
          <View style={styles.actionFooter}>
            {mutationError && (
              <View style={styles.footerErrorContainer}>
                <Text style={styles.footerErrorText}>⚠️ {mutationError}</Text>
              </View>
            )}

            {isPending && (
              <TouchableOpacity
                style={styles.approveBtn}
                onPress={() => setShowConfirmModal(true)}
                disabled={isMutating}
                activeOpacity={0.8}
              >
                <Text style={styles.approveBtnText}>Approve Booking</Text>
              </TouchableOpacity>
            )}

            {isApproved && (
              <TouchableOpacity
                style={styles.assignBtn}
                onPress={handleAssignPress}
                disabled={isMutating}
                activeOpacity={0.8}
              >
                <Text style={styles.assignBtnText}>Assign Staff</Text>
              </TouchableOpacity>
            )}

            {isAssigned && (
              <TouchableOpacity
                style={styles.changeBtn}
                onPress={handleAssignPress}
                disabled={isMutating}
                activeOpacity={0.8}
              >
                <Text style={styles.changeBtnText}>Change Staff</Text>
              </TouchableOpacity>
            )}
          </View>
        )}
      </ContentContainer>

      {/* Modals */}
      <ConfirmationModal
        visible={showConfirmModal}
        title="Approve Pet Booking?"
        message={`This will update ${request.pet_name}'s status to APPROVED. This triggers production calendar syncs and notification emails. Are you sure you want to proceed?`}
        onConfirm={handleApprove}
        onCancel={() => setShowConfirmModal(false)}
        isLoading={isMutating}
      />

      <StaffPickerSheet
        visible={showStaffPicker}
        onClose={() => setShowStaffPicker(false)}
        onSelect={handleSelectStaff}
        currentStaffId={request.worker_id || request.assigned_sitter_id || null}
        staff={staff}
        isLoading={isStaffLoading}
        error={staffError}
        onRefresh={refreshStaff}
      />

      <ConfirmationModal
        visible={showAssignConfirmModal}
        title={request.worker_id ? "Change Staff Assignment?" : "Assign Staff Member?"}
        message={`Are you sure you want to assign ${selectedStaff?.displayName} to care for ${request.pet_name}? This triggers production calendar syncs and staff notifications.`}
        onConfirm={handleConfirmAssignment}
        onCancel={() => setShowAssignConfirmModal(false)}
        isLoading={isMutating}
      />
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
    marginBottom: 16,
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
    fontSize: 11,
    fontWeight: '800',
    color: COLORS.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.8,
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
  errorText: {
    fontSize: 14,
    color: COLORS.danger,
    fontWeight: '700',
  },
  actionFooter: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: COLORS.cardBg,
    borderTopWidth: 1,
    borderTopColor: COLORS.borderSoft,
    padding: 16,
    shadowColor: COLORS.text,
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 8,
  },
  approveBtn: {
    backgroundColor: COLORS.success,
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
  },
  approveBtnText: {
    color: COLORS.white,
    fontSize: 16,
    fontWeight: '700',
  },
  assignBtn: {
    backgroundColor: COLORS.primary,
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
  },
  assignBtnText: {
    color: COLORS.white,
    fontSize: 16,
    fontWeight: '700',
  },
  changeBtn: {
    backgroundColor: 'transparent',
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: COLORS.primary,
  },
  changeBtnText: {
    color: COLORS.primary,
    fontSize: 16,
    fontWeight: '700',
  },
  footerErrorContainer: {
    backgroundColor: '#fef2f2',
    borderRadius: 6,
    padding: 8,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#fee2e2',
  },
  footerErrorText: {
    color: COLORS.danger,
    fontSize: 13,
    fontWeight: '600',
  },
});
