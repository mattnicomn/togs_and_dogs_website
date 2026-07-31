/**
 * Phase 1B.3: Sanitization helpers for PET records in client-facing contexts.
 * Phase 24A-2B.1: Wired to canonical PET_FIELDS contract adapter.
 */

import { PET_FIELDS } from '../generated/contracts.js';

const CLIENT_SAFE_PET_FIELDS = Array.isArray(PET_FIELDS?.clientReadFields)
  ? [...PET_FIELDS.clientReadFields]
  : [];

const CLIENT_HEALTH_SUBFIELDS = Array.isArray(PET_FIELDS?.clientWriteHealthSubfields)
  ? [...PET_FIELDS.clientWriteHealthSubfields]
  : [];

/**
 * Sanitizes a pet object to ensure only client-safe fields are returned.
 * Excludes internal-only pricing, quotes, and staff-only notes.
 * Preserves nested health fields (vet_name, vet_phone) via explicit helper logic.
 * Does not mutate the original object.
 */
export function sanitizePetDetails(pet) {
  if (!pet || typeof pet !== 'object') return null;

  const sanitized = {};
  CLIENT_SAFE_PET_FIELDS.forEach(field => {
    if (field in pet) {
      sanitized[field] = pet[field];
    }
  });

  if (pet.health && typeof pet.health === 'object' && !Array.isArray(pet.health)) {
    const sanitizedHealth = {};
    CLIENT_HEALTH_SUBFIELDS.forEach(sub => {
      if (sub in pet.health) {
        sanitizedHealth[sub] = pet.health[sub];
      }
    });
    if (Object.keys(sanitizedHealth).length > 0) {
      sanitized.health = sanitizedHealth;
    }
  }

  return sanitized;
}

/**
 * Sanitizes a list of pet objects.
 */
export function sanitizePetsList(pets) {
  if (!Array.isArray(pets)) return [];
  return pets.map(sanitizePetDetails).filter(Boolean);
}

