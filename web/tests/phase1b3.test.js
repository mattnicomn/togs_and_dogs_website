/**
 * Phase 1B.3: Focused tests for pet helper utilities.
 * Uses Node built-in test runner (node:test).
 * Run: node --test web/tests/phase1b3.test.js
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { sanitizePetDetails, sanitizePetsList } from '../src/utils/petHelpers.js';

describe('sanitizePetDetails', () => {
  it('should preserve all client-safe fields and exclude internal/quote fields', () => {
    const rawPet = {
      pet_id: 'pet-123',
      name: 'Fluffy',
      species: 'Dog',
      breed: 'Golden Retriever',
      age: '3 years',
      care_instructions: 'Feed twice daily',
      feeding_notes: 'Wet food only',
      medication_notes: 'None',
      behavior_notes: 'Friendly but energetic',
      is_active: true,
      internal_pricing_notes: ' charge extra on weekends',
      quote_amount: 150,
      meet_and_greet_notes: 'Owners were very nice'
    };

    const expected = {
      pet_id: 'pet-123',
      name: 'Fluffy',
      species: 'Dog',
      breed: 'Golden Retriever',
      age: '3 years',
      care_instructions: 'Feed twice daily',
      feeding_notes: 'Wet food only',
      medication_notes: 'None',
      behavior_notes: 'Friendly but energetic',
      is_active: true
    };

    const result = sanitizePetDetails(rawPet);
    assert.deepEqual(result, expected);

    // Verify raw Cognito/pricing fields are absent
    assert.equal(result.internal_pricing_notes, undefined);
    assert.equal(result.quote_amount, undefined);
    assert.equal(result.meet_and_greet_notes, undefined);
  });

  it('should return null for null or undefined pet input', () => {
    assert.equal(sanitizePetDetails(null), null);
    assert.equal(sanitizePetDetails(undefined), null);
  });

  it('should ignore fields not present in input pet', () => {
    const rawPet = {
      name: 'Fido',
      species: 'Dog'
    };

    const result = sanitizePetDetails(rawPet);
    assert.deepEqual(result, { name: 'Fido', species: 'Dog' });
    assert.equal('breed' in result, false);
  });
});

describe('sanitizePetsList', () => {
  it('should sanitize all pets in the list', () => {
    const rawPets = [
      {
        name: 'Buddy',
        internal_pricing_notes: 'Discount applied'
      },
      {
        name: 'Mittens',
        quote_amount: 100
      }
    ];

    const result = sanitizePetsList(rawPets);
    assert.equal(result.length, 2);
    assert.deepEqual(result[0], { name: 'Buddy' });
    assert.deepEqual(result[1], { name: 'Mittens' });
  });

  it('should return empty list for non-array or empty input', () => {
    assert.deepEqual(sanitizePetsList(null), []);
    assert.deepEqual(sanitizePetsList(undefined), []);
    assert.deepEqual(sanitizePetsList({}), []);
    assert.deepEqual(sanitizePetsList([]), []);
  });
});
