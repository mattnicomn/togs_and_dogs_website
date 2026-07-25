/**
 * Phase 24A-4: My Pets Read-Only Screen
 *
 * Displays the authenticated customer's saved pets from GET /client/pets.
 * Read-only — no editing, creating, or deleting pets.
 */
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
import { useAuth } from '../auth/useAuth';
import { useFocusEffect } from '@react-navigation/native';
import { getClientPets } from '../api/client';
import { COLORS } from '../theme/colors';

interface Pet {
  pet_id: string;
  name: string;
  species?: string;
  breed?: string;
  age?: string;
  care_instructions?: string;
  feeding_notes?: string;
  medication_notes?: string;
  behavior_notes?: string;
  is_active?: boolean;
  health?: {
    vet_name?: string;
    vet_phone?: string;
  };
}

// --- Pet Detail Modal/View ---
const PetDetail = ({ pet, onClose }: { pet: Pet; onClose: () => void }) => {
  const fields: { label: string; value: string | undefined }[] = [
    { label: 'Species', value: pet.species },
    { label: 'Breed', value: pet.breed },
    { label: 'Age', value: pet.age },
    { label: 'Care Instructions', value: pet.care_instructions },
    { label: 'Feeding Notes', value: pet.feeding_notes },
    { label: 'Medication Notes', value: pet.medication_notes },
    { label: 'Behavior Notes', value: pet.behavior_notes },
    { label: 'Vet Name', value: pet.health?.vet_name },
    { label: 'Vet Phone', value: pet.health?.vet_phone },
  ];

  const visibleFields = fields.filter(f => f.value && f.value.trim());

  return (
    <ScrollView style={styles.detailContainer} contentContainerStyle={styles.detailContent}>
      <View style={styles.detailHeader}>
        <Text style={styles.detailName} accessibilityRole="header">🐾 {pet.name}</Text>
        {pet.species && <Text style={styles.detailSpecies}>{pet.species}</Text>}
      </View>

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
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Back to pet list"
      >
        <Text style={styles.backButtonText}>← Back to My Pets</Text>
      </TouchableOpacity>
    </ScrollView>
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

  // Detail view
  if (selectedPet) {
    return (
      <SafeAreaView style={styles.container}>
        <PetDetail pet={selectedPet} onClose={() => setSelectedPet(null)} />
      </SafeAreaView>
    );
  }

  const renderPetCard = ({ item }: { item: Pet }) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() => setSelectedPet(item)}
      accessibilityRole="button"
      accessibilityLabel={`View details for ${item.name}`}
    >
      <View style={styles.cardHeader}>
        <Text style={styles.petName}>🐾 {item.name}</Text>
        {item.species && (
          <View style={styles.speciesBadge}>
            <Text style={styles.speciesText}>{item.species}</Text>
          </View>
        )}
      </View>
      {item.breed && (
        <Text style={styles.petBreed}>{item.breed}</Text>
      )}
      {item.age && (
        <Text style={styles.petAge}>Age: {item.age}</Text>
      )}
    </TouchableOpacity>
  );

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
  detailContent: {
    padding: 24,
  },
  detailHeader: {
    marginBottom: 24,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.borderSoft,
    paddingBottom: 16,
  },
  detailName: {
    fontSize: 22,
    fontWeight: '800',
    color: COLORS.text,
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
});
