import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation } from '@react-navigation/native';
import { useAuth } from '../auth/useAuth';
import { submitClientRequest, getClientPets, getStaffOptions } from '../api/client';
import { COLORS } from '../theme/colors';
import { SERVICE_TYPES, PET_FIELDS } from '../contracts/generatedContracts';

// D2 uses the target booking-eligibility contract. The legacy
// availableInIntake flag remains unchanged for pre-D2 platform compatibility.
const INTAKE_SERVICE_OPTIONS = Object.entries(SERVICE_TYPES.services)
  .filter(([, service]) => (
    service.supportedOnMobile === true
    && service.lifecycle === 'active'
    && service.newBookingEligibility === 'eligible'
  ))
  .map(([key, service]) => ({
    key,
    label: service.label,
    labelLong: service.labelLong,
    durationMinutes: service.durationMinutes,
    durationStatus: service.durationStatus,
  }));

const INITIAL_SERVICE_TYPE = INTAKE_SERVICE_OPTIONS[0]?.key || '';

const formatCanonicalTime = (value: string | null) => {
  if (!value) return '';
  const [hourValue, minute] = value.split(':');
  const hour = Number(hourValue);
  const suffix = hour >= 12 ? 'PM' : 'AM';
  const displayHour = hour % 12 || 12;
  return `${displayHour}:${minute} ${suffix}`;
};

const formatCanonicalWindowRange = (start: string | null, end: string | null) => {
  const formattedStart = formatCanonicalTime(start);
  const formattedEnd = formatCanonicalTime(end);
  return formattedStart && formattedEnd ? `${formattedStart}–${formattedEnd}` : '';
};

const TERMS_VERSION = '1.0';
const PRIVACY_VERSION = '1.0';

export const IntakeScreen = () => {
  const navigation = useNavigation<any>();
  const { user } = useAuth();

  const [step, setStep] = useState(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successRequestId, setSuccessRequestId] = useState<string | null>(null);

  // Form State
  const [clientName, setClientName] = useState('');
  const [clientEmail, setClientEmail] = useState(typeof user === 'string' ? user : '');
  const [serviceType, setServiceType] = useState(INITIAL_SERVICE_TYPE);
  const [selectedDates, setSelectedDates] = useState<string[]>([]);
  const [customDateInput, setCustomDateInput] = useState('');
  const [visitsPerDay, setVisitsPerDay] = useState<number | null>(null);
  const [visitWindows, setVisitWindows] = useState<string[]>([]);
  const [timingNotes, setTimingNotes] = useState('');
  const [preferredSitter, setPreferredSitter] = useState('');

  // Pet & Care State
  const [availablePets, setAvailablePets] = useState<any[]>([]);
  const [petsLoading, setPetsLoading] = useState(false);
  const [selectedPetNames, setSelectedPetNames] = useState<string[]>([]);
  const [fallbackPetName, setFallbackPetName] = useState('');
  const [feedingNotes, setFeedingNotes] = useState('');
  const [medicationNotes, setMedicationNotes] = useState('');
  const [vetClinic, setVetClinic] = useState('');
  const [vetPhone, setVetPhone] = useState('');
  const [emergencyName, setEmergencyName] = useState('');
  const [emergencyPhone, setEmergencyPhone] = useState('');

  // Staff options state
  const [staffOptions, setStaffOptions] = useState<any[]>([]);

  // Policy Agreement State
  const [acceptedTerms, setAcceptedTerms] = useState(false);

  const selectedService = SERVICE_TYPES.services[serviceType as keyof typeof SERVICE_TYPES.services];
  const usesCheckInSchedule = selectedService?.windowSelectionMode === 'match_visits_per_day';
  const usesExactWindowSchedule = selectedService?.windowSelectionMode === 'exactly_one';
  const usesCanonicalVisitWindows = usesCheckInSchedule || usesExactWindowSchedule;
  const allowedVisitWindows = usesCanonicalVisitWindows ? [...selectedService.allowedWindowIds] : [];
  const canonicalWindowOptions = allowedVisitWindows
    .map((key) => {
      const metadata = SERVICE_TYPES.windows[key as keyof typeof SERVICE_TYPES.windows];
      if (
        !metadata
        || metadata.lifecycle !== 'active'
        || metadata.newBookingEligibility !== 'eligible'
      ) {
        return null;
      }
      return {
        key,
        label: metadata.label,
        range: formatCanonicalWindowRange(metadata.start, metadata.end),
      };
    })
    .filter((window): window is NonNullable<typeof window> => window !== null);

  useEffect(() => {
    let isMounted = true;

    // Sync user email if loaded
    if (typeof user === 'string' && user && !clientEmail) {
      setClientEmail(user);
    }

    // Fetch existing read-only client pets
    setPetsLoading(true);
    getClientPets()
      .then((data) => {
        if (isMounted) {
          const petsList = Array.isArray(data) ? data : data?.pets || [];
          setAvailablePets(petsList);
          // Pre-select first pet if available
          if (petsList.length > 0 && petsList[0]?.name) {
            setSelectedPetNames([petsList[0].name]);
          }
        }
      })
      .catch(() => {
        if (isMounted) setAvailablePets([]);
      })
      .finally(() => {
        if (isMounted) setPetsLoading(false);
      });

    // Fetch staff options for preferred sitter dropdown
    getStaffOptions()
      .then((data) => {
        if (isMounted) setStaffOptions(data?.staff_options || []);
      })
      .catch(() => {
        if (isMounted) setStaffOptions([]);
      });

    return () => {
      isMounted = false;
    };
  }, [user]);

  // Quick date helper: Generate next 14 YYYY-MM-DD dates for chip selector
  const generateUpcomingDates = () => {
    const dates = [];
    const today = new Date();
    for (let i = 1; i <= 14; i++) {
      const nextDate = new Date(today);
      nextDate.setDate(today.getDate() + i);
      const yyyy = nextDate.getFullYear();
      const mm = String(nextDate.getMonth() + 1).padStart(2, '0');
      const dd = String(nextDate.getDate()).padStart(2, '0');
      const dateStr = `${yyyy}-${mm}-${dd}`;
      const labelStr = nextDate.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
      dates.push({ dateStr, labelStr });
    }
    return dates;
  };

  const toggleDate = (dateStr: string) => {
    if (selectedDates.includes(dateStr)) {
      setSelectedDates(selectedDates.filter((d) => d !== dateStr));
    } else {
      setSelectedDates([...selectedDates, dateStr].sort());
    }
  };

  const addCustomDate = () => {
    const trimmed = customDateInput.trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed) && !selectedDates.includes(trimmed)) {
      setSelectedDates([...selectedDates, trimmed].sort());
      setCustomDateInput('');
    }
  };

  const selectService = (key: string) => {
    setServiceType(key);
    setVisitsPerDay(null);
    setVisitWindows([]);
    setError(null);
  };

  const selectVisitsPerDay = (count: number) => {
    if (!(selectedService?.visitsPerDayOptions as readonly number[] | undefined)?.includes(count)) {
      return;
    }

    setVisitsPerDay(count);
    if (count === allowedVisitWindows.length) {
      setVisitWindows([...allowedVisitWindows]);
    } else {
      setVisitWindows(allowedVisitWindows.filter((window) => visitWindows.includes(window)).slice(0, count));
    }
    setError(null);
  };

  const toggleVisitWindow = (key: string) => {
    if (!usesCanonicalVisitWindows || !(allowedVisitWindows as readonly string[]).includes(key)) {
      return;
    }

    if (usesExactWindowSchedule) {
      setVisitsPerDay(null);
      setVisitWindows([key]);
      setError(null);
      return;
    }
    if (!visitsPerDay) return;

    if (visitWindows.includes(key)) {
      setVisitWindows(visitWindows.filter((window) => window !== key));
    } else if (visitWindows.length < visitsPerDay) {
      const selected = new Set([...visitWindows, key]);
      setVisitWindows(allowedVisitWindows.filter((window) => selected.has(window)));
    }
    setError(null);
  };

  const togglePetSelection = (petName: string) => {
    if (selectedPetNames.includes(petName)) {
      setSelectedPetNames(selectedPetNames.filter((p) => p !== petName));
    } else {
      setSelectedPetNames([...selectedPetNames, petName]);
    }
  };

  const validateStep1 = () => {
    if (!serviceType) {
      setError('Please select a service type.');
      return false;
    }
    if (usesCheckInSchedule && visitsPerDay === null) {
      setError('Choose how many visits you need each day.');
      return false;
    }
    if (usesCheckInSchedule && visitWindows.length !== visitsPerDay) {
      setError(`Choose ${visitsPerDay} visit window${visitsPerDay === 1 ? '' : 's'}.`);
      return false;
    }
    if (usesExactWindowSchedule && visitWindows.length !== 1) {
      setError('Choose exactly one visit window.');
      return false;
    }
    if (selectedDates.length === 0) {
      setError('Please select at least one visit date.');
      return false;
    }
    setError(null);
    return true;
  };

  const validateStep2 = () => {
    const hasSelectedPets = selectedPetNames.length > 0;
    const hasFallbackPet = fallbackPetName.trim().length > 0;
    if (!hasSelectedPets && !hasFallbackPet) {
      setError('Please select or specify at least one pet name.');
      return false;
    }
    setError(null);
    return true;
  };

  const handleNext = () => {
    if (step === 1 && validateStep1()) {
      setStep(2);
    } else if (step === 2 && validateStep2()) {
      setStep(3);
    }
  };

  const handlePrev = () => {
    setError(null);
    if (step > 1) setStep(step - 1);
  };

  const handleSubmit = async () => {
    if (!acceptedTerms) {
      setError('You must accept the Terms and Privacy Policy before submitting.');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const sortedDates = [...selectedDates].sort();
      const startDate = sortedDates[0] || '';
      const endDate = sortedDates.length > 1 ? sortedDates[sortedDates.length - 1] : '';

      // Construct pets payload array
      const petsPayload = selectedPetNames.map((name) => {
        const found = availablePets.find((p) => p.name === name);
        return {
          name,
          species: found?.species || 'DOG',
          breed: found?.breed || '',
          age: found?.age || '',
          feeding_notes: feedingNotes,
          medication_notes: medicationNotes,
        };
      });

      if (petsPayload.length === 0 && fallbackPetName.trim()) {
        petsPayload.push({
          name: fallbackPetName.trim(),
          species: 'DOG',
          breed: '',
          age: '',
          feeding_notes: feedingNotes,
          medication_notes: medicationNotes,
        });
      }

      const canonicalWindowPayload = usesCanonicalVisitWindows ? {
        visit_windows: allowedVisitWindows.filter((window) => visitWindows.includes(window)),
      } : {};
      const checkInPayload = usesCheckInSchedule ? {
        visits_per_day: visitsPerDay,
      } : {};

      const payload = {
        client_name: clientName.trim() || 'Valued Client',
        client_email: clientEmail.trim() || (typeof user === 'string' ? user : ''),
        service_type: serviceType,
        ...canonicalWindowPayload,
        ...checkInPayload,
        selected_dates: sortedDates,
        start_date: startDate,
        end_date: endDate,
        timing_notes: timingNotes.substring(0, 500),
        preferred_sitter: preferredSitter,
        pets: petsPayload,
        pet_names: petsPayload.map((p) => p.name).join(', '),
        vet_info: vetClinic ? { clinic_name: vetClinic, phone: vetPhone } : {},
        emergency_contact: emergencyName ? { name: emergencyName, phone: emergencyPhone } : {},
        accepted_terms: true,
        accepted_privacy: true,
        terms_version: TERMS_VERSION,
        privacy_version: PRIVACY_VERSION,
        accepted_at: new Date().toISOString(),
        accepted_by_email: clientEmail.trim() || (typeof user === 'string' ? user : ''),
      };

      const res = await submitClientRequest(payload);
      setSuccessRequestId(res.request_id || 'RECEIVED');
    } catch (err: any) {
      setError(err.message || 'Failed to submit booking request. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderHeader = () => (
    <View style={styles.header}>
      <TouchableOpacity style={styles.closeBtn} onPress={() => navigation?.goBack?.()}>
        <Text style={styles.closeText}>✕</Text>
      </TouchableOpacity>
      <Text style={styles.headerTitle}>Book Pet Care</Text>
      <View style={{ width: 32 }} />
    </View>
  );

  const renderStepper = () => (
    <View style={styles.stepperContainer}>
      {[
        { n: 1, label: 'Schedule' },
        { n: 2, label: 'Pets' },
        { n: 3, label: 'Review' },
      ].map((s) => (
        <View key={s.n} style={styles.stepItem}>
          <View style={[styles.stepBadge, step === s.n && styles.stepBadgeActive, step > s.n && styles.stepBadgeDone]}>
            <Text style={[styles.stepNumber, (step === s.n || step > s.n) && styles.stepNumberActive]}>
              {step > s.n ? '✓' : String(s.n)}
            </Text>
          </View>
          <Text style={[styles.stepLabel, step === s.n && styles.stepLabelActive]}>{s.label}</Text>
        </View>
      ))}
    </View>
  );

  if (successRequestId) {
    return (
      <SafeAreaView style={styles.container}>
        {renderHeader()}
        <View style={styles.successContainer} accessibilityLiveRegion="polite">
          <Text style={styles.successIcon}>🎉</Text>
          <Text style={styles.successTitle} accessibilityRole="header">Request Received!</Text>
          <Text style={styles.successSub}>
            Your request ID is <Text style={styles.reqIdText}>{successRequestId}</Text>. Our team will review your booking details and confirm shortly.
          </Text>
          <TouchableOpacity
            style={styles.primaryBtn}
            onPress={() => {
              // Bookings is nested under the ClientTabs route in ClientStack.
              navigation?.navigate?.('ClientTabs', { screen: 'Bookings' });
            }}
            accessibilityRole="button"
          >
            <Text style={styles.primaryBtnText}>View My Bookings</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  const upcomingDates = generateUpcomingDates();

  return (
    <SafeAreaView style={styles.container}>
      {renderHeader()}
      {renderStepper()}

      <KeyboardAvoidingView
        style={styles.keyboardAvoidingContainer}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        testID="intake-keyboard-container"
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          testID="intake-form-scroll"
        >
          {error ? (
            <View style={styles.errorBanner} accessibilityLiveRegion="assertive">
              <Text style={styles.errorText}>⚠️ {error}</Text>
            </View>
          ) : null}
        {/* STEP 1: SERVICE & SCHEDULE */}
        {step === 1 && (
          <View style={styles.stepContent}>
            <Text style={styles.sectionTitle} accessibilityRole="header">1. Select Service</Text>
            <View style={styles.optionsGrid}>
              {INTAKE_SERVICE_OPTIONS.map((item) => {
                const isSelected = serviceType === item.key;
                return (
                  <TouchableOpacity
                    key={item.key}
                    style={[styles.serviceOption, isSelected && styles.serviceOptionSelected]}
                    onPress={() => selectService(item.key)}
                    accessibilityRole="button"
                    accessibilityLabel={`Select service ${item.labelLong}`}
                    accessibilityState={{ selected: isSelected }}
                  >
                    <Text style={[styles.serviceOptionLabel, isSelected && styles.serviceOptionLabelSelected]}>
                      {item.labelLong}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            {usesCheckInSchedule && (
              <View>
                <Text style={[styles.sectionTitle, { marginTop: 24 }]} accessibilityRole="header">
                  2. Visits per day
                </Text>
                <Text
                  style={styles.fieldHint}
                  accessibilityLabel={visitsPerDay === null
                    ? 'Choose how many Check-In visits you need each day'
                    : `${visitsPerDay} Check-In visit${visitsPerDay === 1 ? '' : 's'} per day selected`}
                >
                  Choose how many Check-In visits you need each day.
                </Text>
                <View style={styles.visitsPerDayRow}>
                  {selectedService.visitsPerDayOptions.map((count) => {
                    const isSelected = visitsPerDay === count;
                    return (
                      <TouchableOpacity
                        key={count}
                        style={[styles.visitsPerDayOption, isSelected && styles.visitsPerDayOptionSelected]}
                        onPress={() => selectVisitsPerDay(count)}
                        accessibilityRole="button"
                        accessibilityLabel={`${count} visit${count === 1 ? '' : 's'} per day`}
                        accessibilityHint="Sets the number of daily Check-In visits"
                        accessibilityState={{ selected: isSelected }}
                      >
                        <Text style={[styles.visitsPerDayText, isSelected && styles.visitsPerDayTextSelected]}>
                          {count}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </View>

                <Text style={[styles.sectionTitle, { marginTop: 24 }]} accessibilityRole="header">
                  3. Preferred visit window{visitsPerDay === 1 ? '' : 's'}
                </Text>
                <Text
                  style={styles.fieldHint}
                  accessibilityLabel={visitsPerDay === null
                    ? 'Select visits per day before choosing visit windows'
                    : visitsPerDay === allowedVisitWindows.length
                      ? 'All three canonical visit windows are selected automatically'
                      : `Choose exactly ${visitsPerDay} visit window${visitsPerDay === 1 ? '' : 's'}`}
                >
                  {visitsPerDay === null
                    ? 'Select visits per day first.'
                    : visitsPerDay === allowedVisitWindows.length
                      ? 'All three daily windows are used automatically.'
                      : `Choose ${visitsPerDay} window${visitsPerDay === 1 ? '' : 's'} (${visitWindows.length} selected).`}
                </Text>
                {canonicalWindowOptions.map((window) => {
                  const isSelected = visitWindows.includes(window.key);
                  const isAllWindowsRule = visitsPerDay === allowedVisitWindows.length;
                  const isDisabled = visitsPerDay === null
                    || isAllWindowsRule
                    || (!isSelected && visitWindows.length >= visitsPerDay);
                  return (
                    <TouchableOpacity
                      key={window.key}
                      style={[
                        styles.windowOption,
                        isSelected && styles.windowOptionSelected,
                        isDisabled && !isSelected && styles.optionDisabled,
                      ]}
                      onPress={() => toggleVisitWindow(window.key)}
                      disabled={isDisabled}
                      accessibilityRole="button"
                      accessibilityLabel={`${window.label}, ${window.range.replace('–', ' to ')}`}
                      accessibilityHint={isAllWindowsRule
                        ? 'Selected automatically for three visits per day'
                        : `Choose ${visitsPerDay || 0} visit window${visitsPerDay === 1 ? '' : 's'}`}
                      accessibilityState={{ selected: isSelected, disabled: isDisabled }}
                    >
                      <Text style={[styles.windowOptionLabel, isSelected && styles.windowOptionLabelSelected]}>
                        {isSelected ? '☑ ' : '☐ '} {window.label}
                      </Text>
                      <Text style={[styles.windowOptionRange, isSelected && styles.windowOptionRangeSelected]}>
                        {window.range}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            )}

            {usesExactWindowSchedule && (
              <View>
                <Text style={[styles.sectionTitle, { marginTop: 24 }]} accessibilityRole="header">
                  2. Preferred visit window
                </Text>
                <Text style={styles.fieldHint}>
                  Choose one window. It applies to every selected date.
                </Text>
                {canonicalWindowOptions.map((window) => {
                  const isSelected = visitWindows[0] === window.key;
                  return (
                    <TouchableOpacity
                      key={window.key}
                      style={[styles.windowOption, isSelected && styles.windowOptionSelected]}
                      onPress={() => toggleVisitWindow(window.key)}
                      accessibilityRole="radio"
                      accessibilityLabel={`${window.label}, ${window.range.replace('–', ' to ')}`}
                      accessibilityHint="Selects this window for every Walk date"
                      accessibilityState={{ selected: isSelected, checked: isSelected }}
                    >
                      <Text style={[styles.windowOptionLabel, isSelected && styles.windowOptionLabelSelected]}>
                        {isSelected ? '◉ ' : '○ '} {window.label}
                      </Text>
                      <Text style={[styles.windowOptionRange, isSelected && styles.windowOptionRangeSelected]}>
                        {window.range}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            )}

            <Text style={[styles.sectionTitle, { marginTop: 24 }]} accessibilityRole="header">
              {usesCheckInSchedule ? '4. Visit Dates' : usesExactWindowSchedule ? '3. Visit Dates' : '2. Visit Dates'}
            </Text>
            <Text style={styles.fieldHint}>Tap to select upcoming care dates ({selectedDates.length} selected)</Text>

            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.datesScroll}>
              {upcomingDates.map((item) => {
                const isSelected = selectedDates.includes(item.dateStr);
                return (
                  <TouchableOpacity
                    key={item.dateStr}
                    style={[styles.dateChip, isSelected && styles.dateChipSelected]}
                    onPress={() => toggleDate(item.dateStr)}
                    accessibilityRole="button"
                    accessibilityLabel={item.labelStr}
                    accessibilityState={{ selected: isSelected }}
                  >
                    <Text style={[styles.dateChipText, isSelected && styles.dateChipTextSelected]}>
                      {item.labelStr}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </ScrollView>

            <View style={styles.customDateRow}>
              <TextInput
                style={styles.inputFlex}
                placeholder="Or YYYY-MM-DD (e.g. 2026-08-15)"
                placeholderTextColor={COLORS.textMuted}
                value={customDateInput}
                onChangeText={setCustomDateInput}
                accessibilityLabel="Custom YYYY-MM-DD date input"
              />
              <TouchableOpacity
                style={styles.addDateBtn}
                onPress={addCustomDate}
                accessibilityRole="button"
                accessibilityLabel="+ Add custom date"
              >
                <Text style={styles.addDateBtnText}>+ Add</Text>
              </TouchableOpacity>
            </View>

            {selectedDates.length > 0 && (
              <View style={styles.selectedDatesSummary}>
                <Text style={styles.selectedDatesLabel}>Selected ({selectedDates.length}):</Text>
                <Text style={styles.selectedDatesList}>{selectedDates.join(', ')}</Text>
              </View>
            )}

            <Text style={[styles.fieldLabel, { marginTop: 16 }]}>Timing Notes (Optional)</Text>
            <TextInput
              style={styles.textInput}
              placeholder="e.g. Morning walk preferred around 9:00 AM"
              placeholderTextColor={COLORS.textMuted}
              value={timingNotes}
              onChangeText={setTimingNotes}
              maxLength={500}
            />

            {staffOptions.length > 0 && (
              <View>
                <Text style={[styles.fieldLabel, { marginTop: 16 }]} accessibilityRole="header">Preferred Sitter (Optional)</Text>
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.datesScroll}>
                  <TouchableOpacity
                    style={[styles.dateChip, !preferredSitter && styles.dateChipSelected]}
                    onPress={() => setPreferredSitter('')}
                    accessibilityRole="button"
                    accessibilityLabel="No Preference for sitter"
                    accessibilityState={{ selected: !preferredSitter }}
                  >
                    <Text style={[styles.dateChipText, !preferredSitter && styles.dateChipTextSelected]}>
                      No Preference
                    </Text>
                  </TouchableOpacity>
                  {staffOptions.map((sitter) => {
                    const isSelected = preferredSitter === sitter.id || preferredSitter === sitter.name;
                    return (
                      <TouchableOpacity
                        key={sitter.id || sitter.name}
                        style={[styles.dateChip, isSelected && styles.dateChipSelected]}
                        onPress={() => setPreferredSitter(sitter.id || sitter.name)}
                        accessibilityRole="button"
                        accessibilityLabel={`Preferred sitter option ${sitter.name}`}
                        accessibilityState={{ selected: isSelected }}
                      >
                        <Text style={[styles.dateChipText, isSelected && styles.dateChipTextSelected]}>
                          👤 {sitter.name}
                        </Text>
                      </TouchableOpacity>
                    );
                  })}
                </ScrollView>
              </View>
            )}
          </View>
        )}

        {/* STEP 2: PETS & DETAILS */}
        {step === 2 && (
          <View style={styles.stepContent}>
            <Text style={styles.sectionTitle} accessibilityRole="header">Select Pets</Text>
            {petsLoading ? (
              <ActivityIndicator size="small" color={COLORS.primary} style={{ marginVertical: 12 }} accessibilityLabel="Loading pets" />
            ) : availablePets.length > 0 ? (
              <View style={styles.petsChipContainer}>
                {availablePets.map((pet) => {
                  const isSelected = selectedPetNames.includes(pet.name);
                  return (
                    <TouchableOpacity
                      key={pet.id || pet.name}
                      style={[styles.petChip, isSelected && styles.petChipSelected]}
                      onPress={() => togglePetSelection(pet.name)}
                      accessibilityRole="button"
                      accessibilityState={{ selected: isSelected }}
                    >
                      <Text style={[styles.petChipText, isSelected && styles.petChipTextSelected]}>
                        {isSelected ? '🐶 ' : '🐾 '} {pet.name} ({pet.breed || pet.species || 'Pet'})
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            ) : (
              <Text style={styles.fieldHint}>No pets on file. Specify your pet's name below:</Text>
            )}

            <Text style={[styles.fieldLabel, { marginTop: 16 }]}>Or Specify Pet Name</Text>
            <TextInput
              style={styles.textInput}
              placeholder="e.g. Buster"
              placeholderTextColor={COLORS.textMuted}
              value={fallbackPetName}
              onChangeText={setFallbackPetName}
              accessibilityLabel="Pet name input"
            />

            <Text style={[styles.fieldLabel, { marginTop: 16 }]}>Feeding Notes (Optional)</Text>
            <TextInput
              style={styles.textInput}
              placeholder="e.g. 1 scoop dry kibble twice daily"
              placeholderTextColor={COLORS.textMuted}
              value={feedingNotes}
              onChangeText={setFeedingNotes}
              accessibilityLabel="Feeding notes"
            />

            <Text style={[styles.fieldLabel, { marginTop: 16 }]}>Medication Notes (Optional)</Text>
            <TextInput
              style={styles.textInput}
              placeholder="e.g. Joint supplement with breakfast"
              placeholderTextColor={COLORS.textMuted}
              value={medicationNotes}
              onChangeText={setMedicationNotes}
              accessibilityLabel="Medication notes"
            />

            <Text style={[styles.sectionTitle, { marginTop: 24 }]} accessibilityRole="header">Veterinary & Emergency (Optional)</Text>
            <Text style={styles.fieldLabel}>Vet Clinic Name</Text>
            <TextInput
              style={styles.textInput}
              placeholder="e.g. City Vet Hospital"
              placeholderTextColor={COLORS.textMuted}
              value={vetClinic}
              onChangeText={setVetClinic}
              accessibilityLabel="Vet clinic name"
            />

            <Text style={[styles.fieldLabel, { marginTop: 12 }]}>Emergency Contact Name</Text>
            <TextInput
              style={styles.textInput}
              placeholder="e.g. Jane Doe"
              placeholderTextColor={COLORS.textMuted}
              value={emergencyName}
              onChangeText={setEmergencyName}
              accessibilityLabel="Emergency contact name"
            />
          </View>
        )}

        {/* STEP 3: REVIEW & SUBMIT */}
        {step === 3 && (
          <View style={styles.stepContent}>
            <Text style={styles.sectionTitle} accessibilityRole="header">Review Booking Request</Text>

            <View style={styles.reviewCard}>
              <View style={styles.reviewRow}>
                <Text style={styles.reviewLabel}>Client:</Text>
                <Text style={styles.reviewVal}>{clientName} ({clientEmail})</Text>
              </View>

              <View style={styles.reviewRow}>
                <Text style={styles.reviewLabel}>Service:</Text>
                <Text style={styles.reviewVal}>
                  {INTAKE_SERVICE_OPTIONS.find((service) => service.key === serviceType)?.label || serviceType}
                </Text>
              </View>

              {selectedService?.durationStatus === 'confirmed' && (
                <View style={styles.reviewRow}>
                  <Text style={styles.reviewLabel}>Duration:</Text>
                  <Text style={styles.reviewVal}>{selectedService.durationMinutes} minutes</Text>
                </View>
              )}

              {usesCheckInSchedule && (
                <View style={styles.reviewRow}>
                  <Text style={styles.reviewLabel}>Visits per day:</Text>
                  <Text style={styles.reviewVal}>{visitsPerDay}</Text>
                </View>
              )}

              {usesCanonicalVisitWindows && (
                <View style={styles.reviewRow}>
                  <Text style={styles.reviewLabel}>Visit window{usesCheckInSchedule ? 's' : ''}:</Text>
                  <Text style={styles.reviewVal}>
                    {canonicalWindowOptions
                      .filter((window) => visitWindows.includes(window.key))
                      .map((window) => usesExactWindowSchedule
                        ? `${window.label} (${window.range})`
                        : window.label)
                      .join(', ')}
                  </Text>
                </View>
              )}

              <View style={styles.reviewRow}>
                <Text style={styles.reviewLabel}>Dates ({selectedDates.length}):</Text>
                <Text style={styles.reviewVal}>{selectedDates.join(', ')}</Text>
              </View>

              <View style={styles.reviewRow}>
                <Text style={styles.reviewLabel}>Pets:</Text>
                <Text style={styles.reviewVal}>
                  {selectedPetNames.length > 0 ? selectedPetNames.join(', ') : fallbackPetName || 'Not specified'}
                </Text>
              </View>

              {timingNotes ? (
                <View style={styles.reviewRow}>
                  <Text style={styles.reviewLabel}>Timing Notes:</Text>
                  <Text style={styles.reviewVal}>{timingNotes}</Text>
                </View>
              ) : null}
            </View>

            <Text style={[styles.sectionTitle, { marginTop: 24 }]} accessibilityRole="header">Policy Agreement</Text>
            <TouchableOpacity
              style={styles.termsRow}
              onPress={() => setAcceptedTerms(!acceptedTerms)}
              accessibilityRole="checkbox"
              accessibilityLabel="Accept Tog & Dogs Terms of Service and Privacy Policy"
              accessibilityState={{ checked: acceptedTerms }}
            >
              <Text style={styles.checkboxText}>{acceptedTerms ? '☑' : '☐'}</Text>
              <Text style={styles.termsLabel}>
                I accept the Tog & Dogs Terms of Service and Privacy Policy.
              </Text>
            </TouchableOpacity>
          </View>
        )}

        {/* CONTROLS */}
        <View style={styles.actionRow}>
          {step > 1 ? (
            <TouchableOpacity
              style={styles.secondaryBtn}
              onPress={handlePrev}
              disabled={isSubmitting}
              accessibilityRole="button"
              accessibilityState={{ disabled: isSubmitting }}
            >
              <Text style={styles.secondaryBtnText}>Back</Text>
            </TouchableOpacity>
          ) : null}

          {step < 3 ? (
            <TouchableOpacity
              style={styles.primaryBtnFlex}
              onPress={handleNext}
              accessibilityRole="button"
              accessibilityLabel="Continue →"
            >
              <Text style={styles.primaryBtnText}>Continue →</Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity
              style={[styles.primaryBtnFlex, !acceptedTerms && styles.btnDisabled]}
              onPress={handleSubmit}
              disabled={!acceptedTerms || isSubmitting}
              accessibilityRole="button"
              accessibilityLabel="Submit Booking Request"
              accessibilityState={{ disabled: !acceptedTerms || isSubmitting, busy: isSubmitting }}
            >
              {isSubmitting ? (
                <ActivityIndicator color="#ffffff" size="small" accessibilityLabel="Submitting booking request" />
              ) : (
                <Text style={styles.primaryBtnText}>Submit Booking Request</Text>
              )}
            </TouchableOpacity>
          )}
        </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  keyboardAvoidingContainer: {
    flex: 1,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.borderSoft,
    backgroundColor: COLORS.cardBg,
  },
  closeBtn: {
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  closeText: {
    fontSize: 18,
    color: COLORS.textMuted,
    fontWeight: '700',
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: COLORS.text,
  },
  stepperContainer: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingVertical: 12,
    backgroundColor: COLORS.cardBg,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.borderSoft,
  },
  stepItem: {
    alignItems: 'center',
  },
  stepBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: COLORS.borderSoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 4,
  },
  stepBadgeActive: {
    backgroundColor: COLORS.primary,
  },
  stepBadgeDone: {
    backgroundColor: COLORS.primary,
  },
  stepNumber: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.textMuted,
  },
  stepNumberActive: {
    color: '#ffffff',
  },
  stepLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: COLORS.textMuted,
  },
  stepLabelActive: {
    color: COLORS.primary,
    fontWeight: '800',
  },
  scrollContent: {
    padding: 20,
    // Leave scrollable clearance below the last input while the keyboard is open.
    paddingBottom: 120,
  },
  errorBanner: {
    backgroundColor: '#fee2e2',
    borderWidth: 1,
    borderColor: '#fca5a5',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  errorText: {
    fontSize: 13,
    color: '#991b1b',
    fontWeight: '600',
  },
  stepContent: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '800',
    color: COLORS.text,
    marginBottom: 10,
  },
  fieldLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.text,
    marginBottom: 6,
  },
  fieldHint: {
    fontSize: 12,
    color: COLORS.textMuted,
    marginBottom: 10,
  },
  optionsGrid: {
    gap: 8,
  },
  serviceOption: {
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    borderRadius: 12,
    padding: 14,
  },
  serviceOptionSelected: {
    borderColor: COLORS.primary,
    backgroundColor: '#fffbeb',
  },
  serviceOptionLabel: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.text,
  },
  serviceOptionLabelSelected: {
    color: COLORS.primary,
  },
  visitsPerDayRow: {
    flexDirection: 'row',
    gap: 8,
  },
  visitsPerDayOption: {
    flex: 1,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    borderRadius: 8,
  },
  visitsPerDayOptionSelected: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  visitsPerDayText: {
    fontSize: 16,
    fontWeight: '800',
    color: COLORS.text,
  },
  visitsPerDayTextSelected: {
    color: COLORS.white,
  },
  datesScroll: {
    flexDirection: 'row',
    marginBottom: 12,
  },
  dateChip: {
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    marginRight: 8,
    minHeight: 44,
    justifyContent: 'center',
  },
  dateChipSelected: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  dateChipText: {
    fontSize: 12,
    fontWeight: '700',
    color: COLORS.text,
  },
  dateChipTextSelected: {
    color: COLORS.white,
  },
  customDateRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  inputFlex: {
    flex: 1,
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13,
    color: COLORS.text,
  },
  addDateBtn: {
    backgroundColor: COLORS.primary,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
    minHeight: 44,
    justifyContent: 'center',
  },
  addDateBtnText: {
    color: COLORS.white,
    fontWeight: '700',
    fontSize: 13,
  },
  selectedDatesSummary: {
    marginTop: 12,
    padding: 10,
    backgroundColor: COLORS.cardBg,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
  },
  selectedDatesLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: COLORS.primary,
  },
  selectedDatesList: {
    fontSize: 12,
    color: COLORS.text,
    marginTop: 2,
  },
  windowOption: {
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    borderRadius: 8,
    padding: 12,
    marginBottom: 6,
    minHeight: 44,
    justifyContent: 'center',
  },
  windowOptionSelected: {
    borderColor: COLORS.primary,
    backgroundColor: '#fffbeb',
  },
  windowOptionLabel: {
    fontSize: 13,
    fontWeight: '600',
    color: COLORS.text,
  },
  windowOptionLabelSelected: {
    color: COLORS.primary,
    fontWeight: '700',
  },
  windowOptionRange: {
    fontSize: 12,
    color: COLORS.textMuted,
    marginTop: 2,
  },
  windowOptionRangeSelected: {
    color: COLORS.primary,
  },
  optionDisabled: {
    opacity: 0.5,
  },
  textInput: {
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 13,
    color: COLORS.text,
  },
  petsChipContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  petChip: {
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    minHeight: 44,
    justifyContent: 'center',
  },
  petChipSelected: {
    backgroundColor: COLORS.primary,
    borderColor: COLORS.primary,
  },
  petChipText: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.text,
  },
  petChipTextSelected: {
    color: COLORS.white,
  },
  reviewCard: {
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    borderRadius: 12,
    padding: 16,
    gap: 8,
  },
  reviewRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  reviewLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.textMuted,
  },
  reviewVal: {
    fontSize: 13,
    fontWeight: '700',
    color: COLORS.text,
    flex: 1,
    textAlign: 'right',
  },
  termsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: COLORS.cardBg,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    minHeight: 44,
  },
  checkboxText: {
    fontSize: 18,
    color: COLORS.primary,
    marginRight: 10,
  },
  termsLabel: {
    fontSize: 12,
    color: COLORS.text,
    flex: 1,
    fontWeight: '600',
  },
  actionRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 10,
  },
  secondaryBtn: {
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderColor: COLORS.borderSoft,
    borderRadius: 8,
    paddingVertical: 14,
    paddingHorizontal: 20,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
  },
  secondaryBtnText: {
    fontSize: 14,
    fontWeight: '700',
    color: COLORS.text,
  },
  primaryBtnFlex: {
    flex: 1,
    backgroundColor: COLORS.primary,
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
  },
  primaryBtnText: {
    fontSize: 14,
    fontWeight: '800',
    color: COLORS.white,
  },
  btnDisabled: {
    opacity: 0.5,
  },
  successContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 30,
  },
  successIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  successTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: COLORS.text,
    marginBottom: 8,
  },
  successSub: {
    fontSize: 14,
    color: COLORS.textMuted,
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 20,
  },
  reqIdText: {
    color: COLORS.primary,
    fontWeight: '800',
  },
  primaryBtn: {
    backgroundColor: COLORS.primary,
    borderRadius: 8,
    paddingVertical: 14,
    paddingHorizontal: 24,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
  },
});
