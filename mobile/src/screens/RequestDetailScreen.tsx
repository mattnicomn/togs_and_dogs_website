import React, { useState } from 'react';
import {
  StyleSheet,
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  Linking,
  Platform,
  Alert,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useStaff } from '../hooks/useStaff';
import { StatusBadge } from '../components/StatusBadge';
import { COLORS } from '../theme/colors';
import { ContentContainer } from '../components/ContentContainer';
import { reviewRequest, assignWorker, completeJob, getAdminRequest, startJob } from '../api/client';
import { useAuth } from '../auth/useAuth';
import { ConfirmationModal } from '../components/ConfirmationModal';
import { StaffPickerSheet } from '../components/StaffPickerSheet';
import { getServiceTypeLabel } from '../utils/serviceLabels';

export const RequestDetailScreen = ({ route, navigation }: any) => {
  const { logout, role } = useAuth();
  const initialRequest = route.params?.request || null;
  const selectedDate = route.params?.selectedDate || null;
  const jobId = route.params?.jobId || null;
  const initialOccurrence = route.params?.occurrence || null;
  const [request, setRequest] = useState<any>(initialRequest);
  const [occurrence, setOccurrence] = useState<any>(initialOccurrence);
  const { staff, isLoading: isStaffLoading, error: staffError, refresh: refreshStaff } = useStaff(role === 'staff');

  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showCompleteConfirmModal, setShowCompleteConfirmModal] = useState(false);
  const [showStaffPicker, setShowStaffPicker] = useState(false);
  const [showAssignConfirmModal, setShowAssignConfirmModal] = useState(false);
  const [selectedStaff, setSelectedStaff] = useState<{ emailOrDisplayName: string; displayName: string } | null>(null);
  const [isMutating, setIsMutating] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [visitNotes, setVisitNotes] = useState('');

  const refreshOccurrence = async () => {
    const fresh = await getAdminRequest(request.request_id, request.client_id);
    setRequest(fresh);
    const jobs = fresh.job_completion_summary?.jobs || [];
    const exact = jobs.find((job: any) => job.job_id === jobId);
    if (exact) setOccurrence(exact);
    return exact;
  };

  const handleStart = async () => {
    if (isMutating || !jobId) return;
    setMutationError(null);
    setIsMutating(true);
    try {
      const result = await startJob(jobId, request.request_id);
      setOccurrence({ ...(occurrence || {}), job_id: jobId, request_id: request.request_id, status: occurrence?.status || 'ASSIGNED', started_at: result.started_at, started_by: result.started_by });
    } catch (error: any) {
      try {
        const exact = await refreshOccurrence();
        if (!exact?.started_at) throw error;
      } catch {
        setMutationError(error.message || 'Could not confirm Start. Check your connection and retry.');
      }
    } finally { setIsMutating(false); }
  };

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
      const clientId = request.client_id;
      const workerId = selectedStaff.emailOrDisplayName;
      const workerName = selectedStaff.displayName;

      if (!reqId || !clientId) {
        throw new Error('Error: Record has no valid Request or Client ID.');
      }

      await assignWorker(reqId, reqId, clientId, workerId, workerName);
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

  const handleMarkCompleted = async () => {
    setMutationError(null);
    setIsMutating(true);
    try {
      const exactJobId = jobId || ((request.job_id && (!request.job_ids || request.job_ids.length <= 1)) ? request.job_id : null);
      if (exactJobId) {
        await completeJob(exactJobId, request.request_id, visitNotes.trim());
        setShowCompleteConfirmModal(false);
        const completedJobs = request.completed_job_ids ? [...request.completed_job_ids] : [];
        if (!completedJobs.includes(exactJobId)) {
          completedJobs.push(exactJobId);
        }
        const updated = {
          ...request,
          completed_job_ids: completedJobs,
        };
        const allJobIds = request.job_ids || [request.job_id];
        const allDone = allJobIds.every((id: string) => completedJobs.includes(id));
        if (allDone) {
          updated.status = 'COMPLETED';
        }
        setRequest(updated);
        Alert.alert('Success', 'Visit marked as completed ✓');
        setOccurrence({ ...(occurrence || {}), status: 'COMPLETED', completed_at: new Date().toISOString() });
      } else throw new Error('This visit cannot be completed until its exact occurrence is refreshed.');
      navigation.goBack();
    } catch (error: any) {
      const msg = error.message || '';
      if (msg.toLowerCase().includes('unauthorized') || msg.toLowerCase().includes('expired')) {
        await logout();
      } else {
        setMutationError(msg || 'Failed to update visit status');
        Alert.alert('Error', msg || 'Failed to update visit status');
      }
    } finally {
      setIsMutating(false);
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

  const formatDateRange = (dates: string[]) => {
    if (!dates || dates.length === 0) return 'No dates selected';
    if (dates.length === 1) return dates[0];
    return `${dates[0]} to ${dates[dates.length - 1]} (${dates.length} days)`;
  };

  const renderPaymentStatusBadge = (status: string | undefined) => {
    const s = (status || '').trim().toLowerCase();
    let label = 'Unpaid / Not Set';
    let color = '#374151'; // Dark gray
    let bgColor = '#f9fafb';
    let borderColor = '#f3f4f6';

    if (s === 'paid') {
      label = 'Paid';
      color = '#065f46'; // Emerald text
      bgColor = '#ecfdf5'; // Emerald bg
      borderColor = '#a7f3d0';
    } else if (s === 'payment_link_sent') {
      label = 'Link Sent — payment pending';
      color = '#b45309'; // Amber text
      bgColor = '#fffbeb'; // Amber bg
      borderColor = '#fde68a';
    } else if (s === 'waived') {
      label = 'Waived';
      color = '#4b5563'; // Gray text
      bgColor = '#f3f4f6'; // Gray bg
      borderColor = '#e5e7eb';
    } else if (s === 'refunded') {
      label = 'Refunded';
      color = '#dc2626'; // Red text
      bgColor = '#fef2f2'; // Red bg
      borderColor = '#fecaca';
    }

    const info = role === 'staff' ? ' (Informational only)' : '';

    return (
      <View style={[styles.paymentBadge, { backgroundColor: bgColor, borderColor: borderColor }]}>
        <Text style={[styles.paymentBadgeText, { color: color }]}>
          {label}{info}
        </Text>
      </View>
    );
  };

  // Resolve emergency contact
  const emergencyContact = request.emergency_contact_info || request.emergency_contact;
  const hasEmergencyContact = emergencyContact && (emergencyContact.name || emergencyContact.phone);

  // Resolve vet info
  const vetInfo = request.vet_info;
  const hasVetInfo = vetInfo && (vetInfo.vet_name || vetInfo.clinic_name || vetInfo.clinic_phone || vetInfo.clinic_address);

  const getCompleteModalMessage = () => {
    const pet = request.pet_name || 'Buddy';
    const client = request.client_name || 'Jane Smith';
    const isMultiDay = request.selected_dates && request.selected_dates.length > 1;
    
    let dateInfo = '';
    if (selectedDate) {
      dateInfo = `Selected Visit Date: ${selectedDate}\nFull Booking Range: ${formatDateRange(request.selected_dates)}`;
    } else {
      dateInfo = `Booking Range: ${formatDateRange(request.selected_dates)}`;
    }

    let warning = '';
    if (isMultiDay) {
      if (jobId) {
        warning = `\n\nNote: This will mark ONLY the visit on ${selectedDate} as completed. Other visits in this booking will remain active.`;
      } else {
        warning = `\n\n⚠️ WARNING: This is a multi-day booking. Completing this will mark ALL dates in the booking completed.`;
      }
    }

    return `Confirm you've completed the care visit for ${pet} (${client}).\n\n${dateInfo}${warning}`;
  };

  const isPending = request.status === 'PENDING_REVIEW';
  const isApproved = request.status === 'APPROVED';
  const childStatus = occurrence?.status || request.status;
  const isAssigned = childStatus === 'ASSIGNED';
  const hasExactJob = Boolean(jobId || (request.job_id && (!request.job_ids || request.job_ids.length <= 1)));
  const isStarted = Boolean(occurrence?.started_at);
  const canComplete = isStarted || Boolean(occurrence?.legacy);
  const showFooter = (role !== 'staff' && (isPending || isApproved || isAssigned)) || (role === 'staff' && isAssigned);

  return (
    <SafeAreaView style={styles.container}>
      <ContentContainer>
        <ScrollView 
          showsVerticalScrollIndicator={false} 
          contentContainerStyle={[styles.scrollContent, { paddingBottom: showFooter ? 110 : 24 }]}
        >
          
          {/* Core Status Summary */}
          <View style={styles.card}>
            {selectedDate && (
              <View style={styles.selectedDateBanner}>
                <Text style={styles.selectedDateBannerLabel}>Target Visit Date</Text>
                <Text style={styles.selectedDateBannerValue}>🗓️ {selectedDate}</Text>
              </View>
            )}
            {isStarted && <Text style={styles.datesSubText}>Started {new Date(occurrence.started_at).toLocaleString()}</Text>}
            <View style={styles.rowBetween}>
              <Text style={styles.petTitle}>🐾 {request.pet_name}</Text>
              <StatusBadge status={request.status} />
            </View>
            
            <View style={styles.divider} />
            
            <View style={styles.detailGrid}>
              <View style={styles.detailCol}>
                <Text style={styles.metaLabel}>Service</Text>
                <Text style={styles.metaValue}>{getServiceTypeLabel(request.service_type)}</Text>
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

            <View style={styles.metaRow}>
              <Text style={styles.metaLabel}>Payment Status</Text>
              {renderPaymentStatusBadge(request.payment_status)}
            </View>
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

          {/* Visit Notes (Read-only if present) */}
          {request.visit_notes && (
            <View style={styles.card}>
              <Text style={styles.sectionHeader}>Visit Notes</Text>
              <Text style={styles.instructionText}>{request.visit_notes}</Text>
              {request.completed_at && (
                <Text style={styles.datesSubText}>
                  Completed on {request.completed_at.split('T')[0]} by {request.completed_by}
                </Text>
              )}
            </View>
          )}

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

          {/* Optional Visit Notes Input for Staff (only when status is ASSIGNED and role is staff) */}
          {isAssigned && role === 'staff' && (
            <View style={styles.card}>
              <Text style={styles.sectionHeader}>Visit Notes (optional)</Text>
              <TextInput
                style={styles.notesInput}
                placeholder="How did the visit go? Any observations..."
                placeholderTextColor={COLORS.textMuted}
                multiline={true}
                numberOfLines={4}
                maxLength={500}
                value={visitNotes}
                onChangeText={setVisitNotes}
              />
              <Text style={styles.charCounter}>{visitNotes.length}/500 characters</Text>
            </View>
          )}
        </ScrollView>

        {/* Sticky Action Footer */}
        {showFooter && (
          <View style={styles.actionFooter}>
            {role === 'staff' && isAssigned && !hasExactJob && (
              <View style={styles.footerErrorContainer}>
                <Text style={styles.footerErrorText}>Refresh required to identify this visit safely.</Text>
              </View>
            )}
            {mutationError && (
              <View style={styles.footerErrorContainer}>
                <Text style={styles.footerErrorText}>⚠️ {mutationError}</Text>
              </View>
            )}

            {isPending && role !== 'staff' && (
              <TouchableOpacity
                style={styles.approveBtn}
                onPress={() => setShowConfirmModal(true)}
                disabled={isMutating}
                activeOpacity={0.8}
              >
                <Text style={styles.approveBtnText}>Approve Booking</Text>
              </TouchableOpacity>
            )}

            {isApproved && role !== 'staff' && (
              <TouchableOpacity
                style={styles.assignBtn}
                onPress={handleAssignPress}
                disabled={isMutating}
                activeOpacity={0.8}
              >
                <Text style={styles.assignBtnText}>Assign Staff</Text>
              </TouchableOpacity>
            )}

            {isAssigned && role !== 'staff' && (
              <TouchableOpacity
                style={styles.changeBtn}
                onPress={handleAssignPress}
                disabled={isMutating}
                activeOpacity={0.8}
              >
                <Text style={styles.changeBtnText}>Change Staff</Text>
              </TouchableOpacity>
            )}

            {isAssigned && role === 'staff' && !isStarted && !occurrence?.legacy && (
              <TouchableOpacity style={styles.completeBtn} onPress={handleStart} disabled={isMutating || !hasExactJob}>
                <Text style={styles.completeBtnText}>Start Visit</Text>
              </TouchableOpacity>
            )}

            {isAssigned && role === 'staff' && canComplete && (
              <TouchableOpacity
                style={styles.completeBtn}
                onPress={() => setShowCompleteConfirmModal(true)}
                disabled={isMutating}
                activeOpacity={0.8}
              >
                <Text style={styles.completeBtnText}>Complete Visit</Text>
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

      <ConfirmationModal
        visible={showCompleteConfirmModal}
        title="Mark Visit Completed?"
        message={getCompleteModalMessage()}
        onConfirm={handleMarkCompleted}
        onCancel={() => setShowCompleteConfirmModal(false)}
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
  completeBtn: {
    backgroundColor: COLORS.success,
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
  },
  completeBtnText: {
    color: COLORS.white,
    fontSize: 16,
    fontWeight: '700',
  },
  notesInput: {
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    color: COLORS.text,
    minHeight: 100,
    textAlignVertical: 'top',
    backgroundColor: COLORS.background,
  },
  charCounter: {
    fontSize: 12,
    color: COLORS.textMuted,
    textAlign: 'right',
    marginTop: 6,
    fontWeight: '500',
  },
  selectedDateBanner: {
    backgroundColor: '#eff6ff',
    borderColor: '#bfdbfe',
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  selectedDateBannerLabel: {
    fontSize: 10,
    fontWeight: '800',
    color: '#1e40af',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  selectedDateBannerValue: {
    fontSize: 16,
    fontWeight: '800',
    color: '#1e3a8a',
    marginTop: 4,
  },
  paymentBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  paymentBadgeText: {
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
});
