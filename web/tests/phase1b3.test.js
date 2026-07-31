/**
 * Phase 1B.3: Focused tests for pet helper utilities and card semantics, focus, and request-race guards.
 * Uses Node built-in test runner (node:test).
 * Run: node --test web/tests/phase1b3.test.js
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { sanitizePetDetails, sanitizePetsList } from '../src/utils/petHelpers.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

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

  it('should preserve health.vet_name and health.vet_phone while stripping unknown health fields', () => {
    const rawPet = {
      pet_id: 'pet-456',
      name: 'Rover',
      health: {
        vet_name: 'Dr. Smith',
        vet_phone: '555-0199',
        internal_vet_id: 'VET-99',
        admin_notes: 'Do not contact without owner approval'
      }
    };

    const result = sanitizePetDetails(rawPet);
    assert.deepEqual(result, {
      pet_id: 'pet-456',
      name: 'Rover',
      health: {
        vet_name: 'Dr. Smith',
        vet_phone: '555-0199'
      }
    });
    assert.equal(result.health.internal_vet_id, undefined);
    assert.equal(result.health.admin_notes, undefined);
  });

  it('should handle missing, null, empty, and non-object health values safely', () => {
    assert.deepEqual(sanitizePetDetails({ name: 'Pet A', health: null }), { name: 'Pet A' });
    assert.deepEqual(sanitizePetDetails({ name: 'Pet B', health: {} }), { name: 'Pet B' });
    assert.deepEqual(sanitizePetDetails({ name: 'Pet C', health: 'invalid' }), { name: 'Pet C' });
  });

  it('should not mutate the input pet object', () => {
    const rawPet = { name: 'Max', health: { vet_name: 'Dr. Jones', extra: 'secret' } };
    const original = JSON.parse(JSON.stringify(rawPet));
    sanitizePetDetails(rawPet);
    assert.deepEqual(rawPet, original);
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

describe('AdminDashboard Code Structure Validation', () => {
  const adminDashboardPath = path.resolve(__dirname, '../src/components/AdminDashboard.jsx');
  const clientCardPath = path.resolve(__dirname, '../src/components/ClientProfileCard.jsx');
  const staffCardPath = path.resolve(__dirname, '../src/components/StaffProfileCard.jsx');
  
  const code = fs.readFileSync(adminDashboardPath, 'utf8');
  const clientCardCode = fs.readFileSync(clientCardPath, 'utf8');
  const staffCardCode = fs.readFileSync(staffCardPath, 'utf8');

  it('should not contain role="button" inside client-profile-card markup', () => {
    assert.equal(clientCardCode.includes('role="button"'), false);
    assert.equal(clientCardCode.includes('tabIndex='), false);
    assert.equal(clientCardCode.includes('onKeyDown='), false);
  });

  it('should not contain role="button" inside staff-profile-card markup', () => {
    assert.equal(staffCardCode.includes('role="button"'), false);
    assert.equal(staffCardCode.includes('tabIndex='), false);
    assert.equal(staffCardCode.includes('onKeyDown='), false);
  });

  it('should define a native card-summary-button-link for client cards and staff cards', () => {
    assert.ok(clientCardCode.includes('className="card-summary-button-link"'), 'Client card should have card-summary-button-link');
    assert.ok(staffCardCode.includes('className="card-summary-button-link"'), 'Staff card should have card-summary-button-link');
  });

  it('should pass explicit triggerElement parameter to openClientDetail and openStaffDetail', () => {
    assert.ok(code.includes('const openClientDetail = (client, triggerElement)'), 'openClientDetail should accept triggerElement');
    assert.ok(code.includes('const openStaffDetail = (staff, triggerElement)'), 'openStaffDetail should accept triggerElement');
  });

  it('should use explicit triggerElement instead of document.activeElement as primary source', () => {
    // Assert that we fallback to document.activeElement but store the triggerElement
    assert.ok(code.includes('clientDrawerTriggerRef.current = el'), 'openClientDetail must store triggerElement');
    assert.ok(code.includes('staffDrawerTriggerRef.current = el'), 'openStaffDetail must store triggerElement');
  });

  it('should verify document.body.contains(trigger) before restoring focus', () => {
    assert.ok(code.includes('document.body.contains(trigger)'), 'Focus restoration must check if trigger is still in DOM');
  });

  it('should clear trigger refs after focus restoration', () => {
    assert.ok(code.includes('clientDrawerTriggerRef.current = null'), 'clientDrawerTriggerRef should be cleared on close');
    assert.ok(code.includes('staffDrawerTriggerRef.current = null'), 'staffDrawerTriggerRef should be cleared on close');
  });

  it('should define clientPetRequestSeqRef and activeClientDetailIdRef request sequence guards', () => {
    assert.ok(code.includes('clientPetRequestSeqRef = useRef(0)'), 'clientPetRequestSeqRef should be initialized');
    assert.ok(code.includes('activeClientDetailIdRef = useRef(null)'), 'activeClientDetailIdRef should be initialized');
  });

  it('should increment request sequence and check sequence matches before updating pet state', () => {
    assert.ok(code.includes('clientPetRequestSeqRef.current += 1'), 'sequence should be incremented');
    assert.ok(code.includes('currentSeq === clientPetRequestSeqRef.current'), 'sequence matches check should be present');
    assert.ok(code.includes('activeClientDetailIdRef.current === currentClientId'), 'client identity match check should be present');
  });

  it('should invalidate active request sequence when the client detail drawer closes', () => {
    // On close, sequence should be incremented and client ID cleared to ignore late results
    assert.ok(code.includes('clientPetRequestSeqRef.current += 1'), 'sequence should increment on close');
    assert.ok(code.includes('activeClientDetailIdRef.current = null'), 'active ID ref should clear on close');
  });

  it('should declare clientDrawerTriggerRef exactly once before the authentication check early return', () => {
    const matches = code.match(/clientDrawerTriggerRef\s*=\s*useRef/g);
    assert.equal(matches ? matches.length : 0, 1, 'clientDrawerTriggerRef must be declared exactly once');

    const declIndex = code.indexOf('clientDrawerTriggerRef = useRef');
    const earlyReturnIndex = code.indexOf('if (!isAuthenticated)');
    assert.ok(declIndex > 0, 'clientDrawerTriggerRef must be declared');
    assert.ok(earlyReturnIndex > 0, 'if (!isAuthenticated) early return check must be defined');
    assert.ok(declIndex < earlyReturnIndex, 'clientDrawerTriggerRef must be declared BEFORE the authentication early return check');
  });

  it('should not declare any React hooks after the authentication check early return block', () => {
    const earlyReturnIndex = code.indexOf('if (!isAuthenticated)');
    const codeAfterEarlyReturn = code.substring(earlyReturnIndex);
    const hooksRegex = /\b(useState|useEffect|useRef|useMemo|useCallback|useContext)\b/g;
    const hooksFound = codeAfterEarlyReturn.match(hooksRegex);
    assert.equal(hooksFound, null, 'No React hooks should be declared after the authentication check early return: ' + (hooksFound ? hooksFound.join(', ') : ''));
  });
});
