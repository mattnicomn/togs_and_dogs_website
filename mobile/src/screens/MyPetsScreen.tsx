/**
 * Phase 24A-5: My Pets Screen (Read & Edit)
 *
 * Displays the authenticated customer's saved pets from GET /client/pets
 * and supports inline editing of existing pet profiles via PUT /client/pets/{petId}.
 * Client editing only — no pet creation, deletion, archiving, or restoring.
 */
import React, { useState, useCallback, useMemo } from 'react';
import {
  StyleSheet,
  View,
  Text,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  TextInput,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '../auth/useAuth';
import { useFocusEffect } from '@react-navigation/native';
import { getClientPets, updateClientPet } from '../api/client';
import { COLORS } from '../theme/colors';
import { PET_FIELDS } from '../contracts/generatedContracts';

interface Pet {
  pet_id: string;
  name: unknown;
  species?: unknown;
  breed?: unknown;
  age?: unknown;
  care_instructions?: unknown;
  feeding_notes?: unknown;
  medication_notes?: unknown;
  behavior_notes?: unknown;
  is_active?: boolean;
  health?: {
    vet_name?: unknown;
    vet_phone?: unknown;
  } | null;
}

interface FormValues {
  name: string;
  species: string;
  breed: string;
  age: string;
  care_instructions: string;
  feeding_notes: string;
  medication_notes: string;
  behavior_notes: string;
  health_vet_name: string;
  health_vet_phone: string;
}

// Normalize legacy API read values before rendering them or placing them in a
// TextInput. Only strings and finite numbers are valid editable text values;
// malformed values become empty strings and cannot leak into an update payload.
const toPetFieldString = (value: unknown): string => {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return '';
};

// Helper to extract editable form values from a pet record
const getInitialFormValues = (pet: Pet): FormValues => ({
  name: toPetFieldString(pet.name),
  species: toPetFieldString(pet.species),
  breed: toPetFieldString(pet.breed),
  age: toPetFieldString(pet.age),
  care_instructions: toPetFieldString(pet.care_instructions),
  feeding_notes: toPetFieldString(pet.feeding_notes),
  medication_notes: toPetFieldString(pet.medication_notes),
  behavior_notes: toPetFieldString(pet.behavior_notes),
  health_vet_name: toPetFieldString(pet.health?.vet_name),
  health_vet_phone: toPetFieldString(pet.health?.vet_phone),
});

// --- Pet Detail & Inline Editor View ---
const PetDetail = ({
  pet,
  onClose,
  onSaveSuccess,
}: {
  pet: Pet;
  onClose: () => void;
  onSaveSuccess: (updatedPet: Pet) => void;
}) => {
  const { logout } = useAuth();
  const [isEditing, setIsEditing] = useState(false);
  const [formValues, setFormValues] = useState<FormValues>(() => getInitialFormValues(pet));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [saveSuccessMessage, setSaveSuccessMessage] = useState<string | null>(null);

  const initialFormValues = useMemo(() => getInitialFormValues(pet), [pet]);

  const isDirty = useMemo(() => {
    return (
      formValues.name !== initialFormValues.name ||
      formValues.species !== initialFormValues.species ||
      formValues.breed !== initialFormValues.breed ||
      formValues.age !== initialFormValues.age ||
      formValues.care_instructions !== initialFormValues.care_instructions ||
      formValues.feeding_notes !== initialFormValues.feeding_notes ||
      formValues.medication_notes !== initialFormValues.medication_notes ||
      formValues.behavior_notes !== initialFormValues.behavior_notes ||
      formValues.health_vet_name !== initialFormValues.health_vet_name ||
      formValues.health_vet_phone !== initialFormValues.health_vet_phone
    );
  }, [formValues, initialFormValues]);

  const isNameValid = formValues.name.trim().length > 0 && formValues.name.trim().length <= PET_FIELDS.fieldLimits.name;

  const handleStartEdit = () => {
    setFormValues(getInitialFormValues(pet));
    setEditError(null);
    setSaveSuccessMessage(null);
    setIsEditing(true);
  };

  const performCancelEdit = () => {
    setFormValues(getInitialFormValues(pet));
    setEditError(null);
    setIsEditing(false);
  };

  const handleCancel = () => {
    if (isDirty) {
      Alert.alert(
        'Discard Unsaved Changes?',
        'You have unsaved pet edits. Are you sure you want to discard them?',
        [
          { text: 'Keep Editing', style: 'cancel' },
          { text: 'Discard', style: 'destructive', onPress: performCancelEdit },
        ]
      );
    } else {
      performCancelEdit();
    }
  };

  const handleBack = () => {
    if (isEditing && isDirty) {
      Alert.alert(
        'Discard Unsaved Changes?',
        'You have unsaved pet edits. Are you sure you want to discard them?',
        [
          { text: 'Keep Editing', style: 'cancel' },
          {
            text: 'Discard',
            style: 'destructive',
            onPress: () => {
              performCancelEdit();
              onClose();
            },
          },
        ]
      );
    } else {
      if (isEditing) {
        performCancelEdit();
      }
      onClose();
    }
  };

  const handleSave = async () => {
    const trimmedName = formValues.name.trim();
    if (!trimmedName) {
      setEditError('Pet name cannot be empty.');
      return;
    }

    setIsSubmitting(true);
    setEditError(null);
    setSaveSuccessMessage(null);

    const payload = {
      name: trimmedName,
      species: formValues.species.trim(),
      breed: formValues.breed.trim(),
      age: formValues.age.trim(),
      care_instructions: formValues.care_instructions.trim(),
      feeding_notes: formValues.feeding_notes.trim(),
      medication_notes: formValues.medication_notes.trim(),
      behavior_notes: formValues.behavior_notes.trim(),
      health: {
        vet_name: formValues.health_vet_name.trim(),
        vet_phone: formValues.health_vet_phone.trim(),
      },
    };

    try {
      const result = await updateClientPet(pet.pet_id, payload);
      const updatedPet: Pet = {
        ...pet,
        ...payload,
        ...(result && typeof result === 'object' ? result : {}),
      };
      onSaveSuccess(updatedPet);
      setIsEditing(false);
      setSaveSuccessMessage('Pet details saved successfully.');
    } catch (e: any) {
      const msg = e.message || '';
      if (
        msg.includes('session expired') ||
        msg.toLowerCase().includes('expired') ||
        msg.toLowerCase().includes('unauthorized')
      ) {
        await logout();
      } else {
        setEditError(msg || 'Failed to update pet. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const petName = toPetFieldString(pet.name);
  const petSpecies = toPetFieldString(pet.species);

  // Normalize every read value before filtering or rendering it.
  const fields: { label: string; value: string }[] = [
    { label: 'Species', value: petSpecies },
    { label: 'Breed', value: toPetFieldString(pet.breed) },
    { label: 'Age', value: toPetFieldString(pet.age) },
    { label: 'Care Instructions', value: toPetFieldString(pet.care_instructions) },
    { label: 'Feeding Notes', value: toPetFieldString(pet.feeding_notes) },
    { label: 'Medication Notes', value: toPetFieldString(pet.medication_notes) },
    { label: 'Behavior Notes', value: toPetFieldString(pet.behavior_notes) },
    { label: 'Vet Name', value: toPetFieldString(pet.health?.vet_name) },
    { label: 'Vet Phone', value: toPetFieldString(pet.health?.vet_phone) },
  ];

  const visibleFields = fields.filter(f => f.value.trim().length > 0);

  return (
    <KeyboardAvoidingView
      style={styles.detailContainer}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      testID="my-pets-keyboard-container"
    >
      <ScrollView
        style={styles.detailScrollView}
        contentContainerStyle={styles.detailContent}
        keyboardShouldPersistTaps="handled"
        testID="my-pets-detail-scroll"
      >
      <View style={styles.detailHeader}>
        <View style={styles.headerTitleRow}>
          <Text style={styles.detailName} accessibilityRole="header">
            🐾 {petName}
          </Text>
          {!isEditing && (
            <TouchableOpacity
              style={styles.editButton}
              onPress={handleStartEdit}
              accessibilityRole="button"
              accessibilityLabel={`Edit profile for ${petName}`}
            >
              <Text style={styles.editButtonText}>Edit Profile</Text>
            </TouchableOpacity>
          )}
        </View>
        {petSpecies && !isEditing && <Text style={styles.detailSpecies}>{petSpecies}</Text>}
      </View>

      {saveSuccessMessage && (
        <View style={styles.successBanner}>
          <Text style={styles.successBannerText}>✓ {saveSuccessMessage}</Text>
        </View>
      )}

      {editError && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorBannerText}>⚠️ {editError}</Text>
        </View>
      )}

      {isEditing ? (
        <View style={styles.formContainer}>
          <View style={styles.editFieldRow}>
            <Text style={styles.detailLabel}>Pet Name *</Text>
            <TextInput
              style={styles.input}
              value={formValues.name}
              onChangeText={(text) => setFormValues(prev => ({ ...prev, name: text }))}
              maxLength={PET_FIELDS.fieldLimits.name}
              placeholder="Pet Name"
              accessibilityLabel="Pet Name"
              accessibilityHint="Enter pet name"
            />
          </View>

          <View style={styles.editFieldRow}>
            <Text style={styles.detailLabel}>Species</Text>
            <TextInput
              style={styles.input}
              value={formValues.species}
              onChangeText={(text) => setFormValues(prev => ({ ...prev, species: text }))}
              maxLength={PET_FIELDS.fieldLimits.species}
              placeholder="e.g. Dog, Cat"
              accessibilityLabel="Species"
              accessibilityHint="Enter species"
            />
          </View>

          <View style={styles.editFieldRow}>
            <Text style={styles.detailLabel}>Breed</Text>
            <TextInput
              style={styles.input}
              value={formValues.breed}
              onChangeText={(text) => setFormValues(prev => ({ ...prev, breed: text }))}
              maxLength={PET_FIELDS.fieldLimits.breed}
              placeholder="e.g. Golden Retriever"
              accessibilityLabel="Breed"
              accessibilityHint="Enter breed"
            />
          </View>

          <View style={styles.editFieldRow}>
            <Text style={styles.detailLabel}>Age</Text>
            <TextInput
              style={styles.input}
              value={formValues.age}
              onChangeText={(text) => setFormValues(prev => ({ ...prev, age: text }))}
              maxLength={PET_FIELDS.fieldLimits.age}
              placeholder="e.g. 3 years"
              accessibilityLabel="Age"
              accessibilityHint="Enter pet age"
            />
          </View>

          <View style={styles.editFieldRow}>
            <Text style={styles.detailLabel}>Care Instructions</Text>
            <TextInput
              style={[styles.input, styles.multilineInput]}
              value={formValues.care_instructions}
              onChangeText={(text) => setFormValues(prev => ({ ...prev, care_instructions: text }))}
              maxLength={PET_FIELDS.fieldLimits.care_instructions}
              multiline
              numberOfLines={3}
              placeholder="General care instructions"
              accessibilityLabel="Care Instructions"
              accessibilityHint="Enter general care instructions"
            />
          </View>

          <View style={styles.editFieldRow}>
            <Text style={styles.detailLabel}>Feeding Notes</Text>
            <TextInput
              style={[styles.input, styles.multilineInput]}
              value={formValues.feeding_notes}
              onChangeText={(text) => setFormValues(prev => ({ ...prev, feeding_notes: text }))}
              maxLength={PET_FIELDS.fieldLimits.feeding_notes}
              multiline
              numberOfLines={3}
              placeholder="Feeding schedule & diet notes"
              accessibilityLabel="Feeding Notes"
              accessibilityHint="Enter feeding schedule and notes"
            />
          </View>

          <View style={styles.editFieldRow}>
            <Text style={styles.detailLabel}>Medication Notes</Text>
            <TextInput
              style={[styles.input, styles.multilineInput]}
              value={formValues.medication_notes}
              onChangeText={(text) => setFormValues(prev => ({ ...prev, medication_notes: text }))}
              maxLength={PET_FIELDS.fieldLimits.medication_notes}
              multiline
              numberOfLines={3}
              placeholder="Medication details & dosage"
              accessibilityLabel="Medication Notes"
              accessibilityHint="Enter medication details"
            />
          </View>

          <View style={styles.editFieldRow}>
            <Text style={styles.detailLabel}>Behavior Notes</Text>
            <TextInput
              style={[styles.input, styles.multilineInput]}
              value={formValues.behavior_notes}
              onChangeText={(text) => setFormValues(prev => ({ ...prev, behavior_notes: text }))}
              maxLength={PET_FIELDS.fieldLimits.behavior_notes}
              multiline
              numberOfLines={3}
              placeholder="Behavioral traits & warnings"
              accessibilityLabel="Behavior Notes"
              accessibilityHint="Enter behavioral traits"
            />
          </View>

          <View style={styles.editFieldRow}>
            <Text style={styles.detailLabel}>Vet Name</Text>
            <TextInput
              style={styles.input}
              value={formValues.health_vet_name}
              onChangeText={(text) => setFormValues(prev => ({ ...prev, health_vet_name: text }))}
              maxLength={PET_FIELDS.clientWriteHealthFieldLimits.vet_name}
              placeholder="Veterinarian or clinic name"
              accessibilityLabel="Vet Name"
              accessibilityHint="Enter veterinarian name"
            />
          </View>

          <View style={styles.editFieldRow}>
            <Text style={styles.detailLabel}>Vet Phone</Text>
            <TextInput
              style={styles.input}
              value={formValues.health_vet_phone}
              onChangeText={(text) => setFormValues(prev => ({ ...prev, health_vet_phone: text }))}
              maxLength={PET_FIELDS.clientWriteHealthFieldLimits.vet_phone}
              keyboardType="phone-pad"
              placeholder="Veterinarian phone number"
              accessibilityLabel="Vet Phone"
              accessibilityHint="Enter veterinarian phone number"
            />
          </View>

          <View style={styles.actionRow}>
            <TouchableOpacity
              style={[
                styles.saveButton,
                (!isDirty || !isNameValid || isSubmitting) && styles.disabledButton,
              ]}
              onPress={handleSave}
              disabled={!isDirty || !isNameValid || isSubmitting}
              accessibilityRole="button"
              accessibilityLabel="Save pet changes"
              accessibilityState={{ disabled: !isDirty || !isNameValid || isSubmitting, busy: isSubmitting }}
            >
              {isSubmitting ? (
                <ActivityIndicator size="small" color={COLORS.white} />
              ) : (
                <Text style={styles.saveButtonText}>Save Changes</Text>
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.cancelButton}
              onPress={handleCancel}
              disabled={isSubmitting}
              accessibilityRole="button"
              accessibilityLabel="Cancel editing pet details"
            >
              <Text style={styles.cancelButtonText}>Cancel</Text>
            </TouchableOpacity>
          </View>
        </View>
      ) : (
        <>
          {visibleFields.length === 0 ? (
            <View style={styles.emptyDetail}>
              <Text style={styles.emptyDetailText}>No additional details available for this pet.</Text>
            </View>
          ) : (
            visibleFields.map((field) => (
              <View key={field.label} style={styles.detailRow}>
                <Text style={styles.detailLabel}>{field.label}</Text>
                <Text style={styles.detailValue}>{field.value}</Text>
              </View>
            ))
          )}

          <TouchableOpacity
            style={styles.backButton}
            onPress={handleBack}
            accessibilityRole="button"
            accessibilityLabel="Back to pet list"
          >
            <Text style={styles.backButtonText}>← Back to My Pets</Text>
          </TouchableOpacity>
        </>
      )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
};

// --- Main Screen ---
export const MyPetsScreen = () => {
  const { logout } = useAuth();
  const [pets, setPets] = useState<Pet[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedPet, setSelectedPet] = useState<Pet | null>(null);

  const fetchPets = useCallback(async (showRefresh = false) => {
    if (showRefresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);

    try {
      const data = await getClientPets();
      const list: Pet[] = Array.isArray(data) ? data : data.pets || [];
      setPets(list);
    } catch (e: any) {
      const msg = e.message || '';
      if (
        msg.includes('session expired') ||
        msg.toLowerCase().includes('expired') ||
        msg.toLowerCase().includes('unauthorized')
      ) {
        await logout();
      } else {
        setError(msg || 'Unable to load your pets. Please try again.');
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [logout]);

  useFocusEffect(
    useCallback(() => {
      fetchPets();
    }, [fetchPets])
  );

  const handleSaveSuccess = (updatedPet: Pet) => {
    setSelectedPet(updatedPet);
    setPets((prev) =>
      prev.map((p) => (p.pet_id === updatedPet.pet_id ? updatedPet : p))
    );
  };

  // Detail view
  if (selectedPet) {
    return (
      <SafeAreaView style={styles.container}>
        <PetDetail
          pet={selectedPet}
          onClose={() => setSelectedPet(null)}
          onSaveSuccess={handleSaveSuccess}
        />
      </SafeAreaView>
    );
  }

  const renderPetCard = ({ item }: { item: Pet }) => {
    const name = toPetFieldString(item.name);
    const species = toPetFieldString(item.species);
    const breed = toPetFieldString(item.breed);
    const age = toPetFieldString(item.age);

    return (
      <TouchableOpacity
        style={styles.card}
        onPress={() => setSelectedPet(item)}
        accessibilityRole="button"
        accessibilityLabel={`View details for ${name}`}
      >
        <View style={styles.cardHeader}>
          <Text style={styles.petName}>🐾 {name}</Text>
          {species && (
            <View style={styles.speciesBadge}>
              <Text style={styles.speciesText}>{species}</Text>
            </View>
          )}
        </View>
        {breed && <Text style={styles.petBreed}>{breed}</Text>}
        {age && <Text style={styles.petAge}>Age: {age}</Text>}
      </TouchableOpacity>
    );
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title} accessibilityRole="header">My Pets</Text>
        <Text style={styles.subtitle}>Your saved pet profiles</Text>
      </View>

      {isLoading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color={COLORS.primary} accessibilityLabel="Loading pets" />
          <Text style={styles.loadingText}>Loading your pets...</Text>
        </View>
      ) : error ? (
        <View style={styles.centerContainer}>
          <Text style={styles.errorIcon}>⚠️</Text>
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity
            style={styles.retryBtn}
            onPress={() => fetchPets()}
            accessibilityRole="button"
            accessibilityLabel="Retry loading pets"
          >
            <Text style={styles.retryText}>Retry</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={pets}
          keyExtractor={(item) => item.pet_id}
          renderItem={renderPetCard}
          refreshControl={
            <RefreshControl
              refreshing={isRefreshing}
              onRefresh={() => fetchPets(true)}
              tintColor={COLORS.primary}
            />
          }
          contentContainerStyle={styles.listContent}
          showsVerticalScrollIndicator={false}
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyIcon}>🐕</Text>
              <Text style={styles.emptyTitle}>No Pets Yet</Text>
              <Text style={styles.emptySub}>
                You don't have any saved pet profiles yet. Pets are added when you submit a care request.
              </Text>
            </View>
          }
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
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  petName: {
    fontSize: 16,
    fontWeight: '800',
    color: COLORS.primary,
    flex: 1,
  },
  speciesBadge: {
    backgroundColor: COLORS.borderSoft,
    borderRadius: 99,
    paddingHorizontal: 10,
    paddingVertical: 3,
  },
  speciesText: {
    fontSize: 11,
    fontWeight: '700',
    color: COLORS.textMuted,
    textTransform: 'uppercase',
  },
  petBreed: {
    fontSize: 13,
    color: COLORS.text,
    fontWeight: '600',
  },
  petAge: {
    fontSize: 12,
    color: COLORS.textMuted,
    marginTop: 4,
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
  // Detail view styles
  detailContainer: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  detailScrollView: {
    flex: 1,
    backgroundColor: COLORS.background,
  },
  detailContent: {
    padding: 24,
    paddingBottom: 120,
  },
  detailHeader: {
    marginBottom: 24,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.borderSoft,
    paddingBottom: 16,
  },
  headerTitleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  detailName: {
    fontSize: 22,
    fontWeight: '800',
    color: COLORS.text,
    flex: 1,
  },
  editButton: {
    backgroundColor: COLORS.primary,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  editButtonText: {
    color: COLORS.white,
    fontSize: 13,
    fontWeight: '700',
  },
  detailSpecies: {
    fontSize: 14,
    color: COLORS.textMuted,
    marginTop: 4,
    fontWeight: '600',
  },
  detailRow: {
    marginBottom: 16,
  },
  detailLabel: {
    fontSize: 12,
    fontWeight: '800',
    color: COLORS.textMuted,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  detailValue: {
    fontSize: 15,
    color: COLORS.text,
    lineHeight: 22,
  },
  emptyDetail: {
    paddingVertical: 32,
    alignItems: 'center',
  },
  emptyDetailText: {
    fontSize: 14,
    color: COLORS.textMuted,
    fontStyle: 'italic',
  },
  backButton: {
    marginTop: 32,
    paddingVertical: 12,
    alignItems: 'center',
  },
  backButtonText: {
    color: COLORS.primary,
    fontSize: 15,
    fontWeight: '700',
  },
  // Form Editor Styles
  formContainer: {
    marginTop: 8,
  },
  editFieldRow: {
    marginBottom: 16,
  },
  input: {
    backgroundColor: COLORS.cardBg,
    borderWidth: 1,
    borderColor: COLORS.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
    color: COLORS.text,
  },
  multilineInput: {
    minHeight: 72,
    textAlignVertical: 'top',
  },
  actionRow: {
    marginTop: 16,
    marginBottom: 24,
    gap: 12,
  },
  saveButton: {
    backgroundColor: COLORS.primary,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  disabledButton: {
    opacity: 0.5,
  },
  saveButtonText: {
    color: COLORS.white,
    fontSize: 15,
    fontWeight: '700',
  },
  cancelButton: {
    backgroundColor: COLORS.borderSoft,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  cancelButtonText: {
    color: COLORS.text,
    fontSize: 15,
    fontWeight: '700',
  },
  errorBanner: {
    backgroundColor: '#fff5f5',
    borderWidth: 1,
    borderColor: COLORS.danger,
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  errorBannerText: {
    color: COLORS.danger,
    fontSize: 13,
    fontWeight: '600',
  },
  successBanner: {
    backgroundColor: '#f0fff4',
    borderWidth: 1,
    borderColor: COLORS.success,
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  successBannerText: {
    color: COLORS.success,
    fontSize: 13,
    fontWeight: '600',
  },
});
