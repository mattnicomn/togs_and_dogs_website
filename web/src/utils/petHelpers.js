/**
 * Phase 1B.3: Sanitization helpers for PET records in client-facing contexts.
 */

const CLIENT_SAFE_PET_FIELDS = [
  'pet_id',
  'name',
  'species',
  'breed',
  'age',
  'care_instructions',
  'feeding_notes',
  'medication_notes',
  'behavior_notes',
  'is_active'
];

/**
 * Sanitizes a pet object to ensure only client-safe fields are returned.
 * Excludes internal-only pricing, quotes, and staff-only notes.
 * Does not mutate the original object.
 */
export function sanitizePetDetails(pet) {
  if (!pet) return null;
  
  const sanitized = {};
  CLIENT_SAFE_PET_FIELDS.forEach(field => {
    if (field in pet) {
      sanitized[field] = pet[field];
    }
  });
  
  return sanitized;
}

/**
 * Sanitizes a list of pet objects.
 */
export function sanitizePetsList(pets) {
  if (!Array.isArray(pets)) return [];
  return pets.map(sanitizePetDetails).filter(Boolean);
}
