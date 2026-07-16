/**
 * Phase 1B.1A: Pure utility tests for client management helpers.
 * Uses Node built-in test runner (node:test).
 * Run: node --test web/tests/clientManagement.test.js
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  accountStatusLabel,
  normalizeAccountStatus,
  profileStatusLabel,
  clientMatchesSearch,
  filterClients,
  getVisibleClients,
  CLIENT_FILTERS,
} from '../src/utils/clientManagement.js';

// ---------------------------------------------------------------------------
// Account-status labels
// ---------------------------------------------------------------------------

describe('accountStatusLabel', () => {
  it('linked_active -> Login Active', () => {
    assert.equal(accountStatusLabel({ account_status: 'linked_active' }), 'Login Active');
  });

  it('linked_disabled -> Login Disabled', () => {
    assert.equal(accountStatusLabel({ account_status: 'linked_disabled' }), 'Login Disabled');
  });

  it('invitation_sent -> Invitation Pending', () => {
    assert.equal(accountStatusLabel({ account_status: 'invitation_sent' }), 'Invitation Pending');
  });

  it('invite_available -> Ready to Invite', () => {
    assert.equal(accountStatusLabel({ account_status: 'invite_available' }), 'Ready to Invite');
  });

  it('profile_only -> Profile Only', () => {
    assert.equal(accountStatusLabel({ account_status: 'profile_only' }), 'Profile Only');
  });

  it('orphaned_identity -> Login Needs Repair', () => {
    assert.equal(accountStatusLabel({ account_status: 'orphaned_identity' }), 'Login Needs Repair');
  });

  it('unlinked -> Unlinked', () => {
    assert.equal(accountStatusLabel({ account_status: 'unlinked' }), 'Unlinked');
  });

  it('null client returns Profile Only', () => {
    assert.equal(accountStatusLabel(null), 'Profile Only');
  });
});

// ---------------------------------------------------------------------------
// Archived profile does not conflate with linked_disabled
// ---------------------------------------------------------------------------

describe('profile and account status separation', () => {
  it('archived profile with linked_active remains Login Active', () => {
    const client = { is_active: false, account_status: 'linked_active' };
    assert.equal(accountStatusLabel(client), 'Login Active');
    assert.equal(profileStatusLabel(client), 'Archived Profile');
  });

  it('active profile with linked_disabled shows Login Disabled', () => {
    const client = { is_active: true, account_status: 'linked_disabled' };
    assert.equal(accountStatusLabel(client), 'Login Disabled');
    assert.equal(profileStatusLabel(client), 'Active Profile');
  });

  it('archived profile label is separate from account label', () => {
    const client = { is_active: false, account_status: 'linked_active' };
    assert.notEqual(profileStatusLabel(client), accountStatusLabel(client));
  });
});

// ---------------------------------------------------------------------------
// Profile-status labels
// ---------------------------------------------------------------------------

describe('profileStatusLabel', () => {
  it('active profile', () => {
    assert.equal(profileStatusLabel({ is_active: true }), 'Active Profile');
  });

  it('archived profile', () => {
    assert.equal(profileStatusLabel({ is_active: false }), 'Archived Profile');
  });

  it('null client', () => {
    assert.equal(profileStatusLabel(null), 'Unknown');
  });

  it('missing is_active defaults to Active Profile', () => {
    assert.equal(profileStatusLabel({}), 'Active Profile');
  });
});

// ---------------------------------------------------------------------------
// Legacy fallback (when account_status is absent)
// ---------------------------------------------------------------------------

describe('normalizeAccountStatus legacy fallback', () => {
  it('no cognito_sub and no email -> profile_only', () => {
    assert.equal(normalizeAccountStatus({ display_name: 'Test' }), 'profile_only');
  });

  it('has email but no cognito_sub -> invite_available', () => {
    assert.equal(normalizeAccountStatus({ email: 'a@b.com' }), 'invite_available');
  });

  it('FORCE_CHANGE_PASSWORD -> invitation_sent', () => {
    assert.equal(normalizeAccountStatus({ cognito_sub: 's1', cognito_status: 'FORCE_CHANGE_PASSWORD' }), 'invitation_sent');
  });

  it('CONFIRMED -> linked_active', () => {
    assert.equal(normalizeAccountStatus({ cognito_sub: 's1', cognito_status: 'CONFIRMED' }), 'linked_active');
  });

  it('server-provided account_status takes precedence', () => {
    assert.equal(normalizeAccountStatus({ account_status: 'orphaned_identity', cognito_status: 'CONFIRMED', cognito_sub: 's1' }), 'orphaned_identity');
  });
});

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

describe('clientMatchesSearch', () => {
  const client = {
    display_name: 'Alice Johnson',
    email: 'alice@example.com',
    phone: '555-1234',
    notes: 'VIP client',
    pet_names_summary: 'Buddy, Max',
    pet_breeds_summary: 'Golden Retriever',
    address: '123 Main St',
  };

  it('empty search matches all', () => {
    assert.equal(clientMatchesSearch(client, ''), true);
    assert.equal(clientMatchesSearch(client, '   '), true);
    assert.equal(clientMatchesSearch(client, null), true);
  });

  it('is case-insensitive', () => {
    assert.equal(clientMatchesSearch(client, 'ALICE'), true);
    assert.equal(clientMatchesSearch(client, 'alice'), true);
  });

  it('trims input', () => {
    assert.equal(clientMatchesSearch(client, '  alice  '), true);
  });

  it('matches display_name', () => {
    assert.equal(clientMatchesSearch(client, 'Johnson'), true);
  });

  it('matches email', () => {
    assert.equal(clientMatchesSearch(client, 'example.com'), true);
  });

  it('matches phone', () => {
    assert.equal(clientMatchesSearch(client, '555'), true);
  });

  it('matches notes', () => {
    assert.equal(clientMatchesSearch(client, 'VIP'), true);
  });

  it('matches pet_names_summary', () => {
    assert.equal(clientMatchesSearch(client, 'Buddy'), true);
  });

  it('matches pet_breeds_summary', () => {
    assert.equal(clientMatchesSearch(client, 'Retriever'), true);
  });

  it('matches address', () => {
    assert.equal(clientMatchesSearch(client, 'Main St'), true);
  });

  it('returns false for no match', () => {
    assert.equal(clientMatchesSearch(client, 'xyz123'), false);
  });

  it('handles missing optional fields safely', () => {
    const sparse = { display_name: 'Bob' };
    assert.equal(clientMatchesSearch(sparse, 'Bob'), true);
    assert.equal(clientMatchesSearch(sparse, 'xyz'), false);
  });
});

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

describe('filterClients', () => {
  const clients = [
    { client_id: '1', is_active: true, account_status: 'linked_active' },
    { client_id: '2', is_active: false, account_status: 'linked_active' },
    { client_id: '3', is_active: true, account_status: 'linked_disabled' },
    { client_id: '4', is_active: true, account_status: 'invitation_sent' },
    { client_id: '5', is_active: true, account_status: 'invite_available' },
    { client_id: '6', is_active: true, account_status: 'profile_only' },
    { client_id: '7', is_active: true, account_status: 'orphaned_identity' },
    { client_id: '8', is_active: false, account_status: 'unlinked' },
  ];

  it('all filter returns all', () => {
    assert.equal(filterClients(clients, 'all').length, 8);
  });

  it('active_profiles filter', () => {
    const result = filterClients(clients, 'active_profiles');
    assert.equal(result.length, 6);
    assert.ok(result.every(c => c.is_active !== false));
  });

  it('archived_profiles filter', () => {
    const result = filterClients(clients, 'archived_profiles');
    assert.equal(result.length, 2);
    assert.ok(result.every(c => c.is_active === false));
  });

  it('linked_active filter', () => {
    const result = filterClients(clients, 'linked_active');
    assert.equal(result.length, 2);
  });

  it('linked_disabled filter', () => {
    const result = filterClients(clients, 'linked_disabled');
    assert.equal(result.length, 1);
    assert.equal(result[0].client_id, '3');
  });

  it('invitation_sent filter', () => {
    const result = filterClients(clients, 'invitation_sent');
    assert.equal(result.length, 1);
    assert.equal(result[0].client_id, '4');
  });

  it('invite_available filter', () => {
    const result = filterClients(clients, 'invite_available');
    assert.equal(result.length, 1);
    assert.equal(result[0].client_id, '5');
  });

  it('profile_only filter', () => {
    const result = filterClients(clients, 'profile_only');
    assert.equal(result.length, 1);
    assert.equal(result[0].client_id, '6');
  });

  it('orphaned_identity filter', () => {
    const result = filterClients(clients, 'orphaned_identity');
    assert.equal(result.length, 1);
    assert.equal(result[0].client_id, '7');
  });

  it('unlinked filter', () => {
    const result = filterClients(clients, 'unlinked');
    assert.equal(result.length, 1);
    assert.equal(result[0].client_id, '8');
  });
});

// ---------------------------------------------------------------------------
// Search + filter composition
// ---------------------------------------------------------------------------

describe('getVisibleClients (search + filter)', () => {
  const clients = [
    { client_id: '1', display_name: 'Alice', is_active: true, account_status: 'linked_active' },
    { client_id: '2', display_name: 'Bob', is_active: false, account_status: 'linked_active' },
    { client_id: '3', display_name: 'Charlie', is_active: true, account_status: 'profile_only' },
  ];

  it('no search + all filter returns all', () => {
    assert.equal(getVisibleClients(clients, '', 'all').length, 3);
  });

  it('search + all filter narrows', () => {
    assert.equal(getVisibleClients(clients, 'alice', 'all').length, 1);
  });

  it('filter + search compose', () => {
    const result = getVisibleClients(clients, 'Bob', 'archived_profiles');
    assert.equal(result.length, 1);
    assert.equal(result[0].client_id, '2');
  });

  it('filter + search no match returns empty', () => {
    const result = getVisibleClients(clients, 'Alice', 'archived_profiles');
    assert.equal(result.length, 0);
  });
});

// ---------------------------------------------------------------------------
// household_id does not replace client_id
// ---------------------------------------------------------------------------

describe('household_id compatibility', () => {
  it('household_id is not required for label generation', () => {
    const client = { client_id: 'c1', account_status: 'linked_active', is_active: true };
    assert.equal(accountStatusLabel(client), 'Login Active');
  });

  it('client with household_id still uses account_status correctly', () => {
    const client = { client_id: 'c1', household_id: 'c1', account_status: 'invite_available', is_active: true };
    assert.equal(accountStatusLabel(client), 'Ready to Invite');
  });
});

// ---------------------------------------------------------------------------
// Internal fields not required for visible labels
// ---------------------------------------------------------------------------

describe('internal fields not needed for visible labels', () => {
  it('PK not required', () => {
    assert.equal(accountStatusLabel({ account_status: 'linked_active' }), 'Login Active');
  });

  it('SK not required', () => {
    assert.equal(profileStatusLabel({ is_active: true }), 'Active Profile');
  });

  it('cognito_sub not required when account_status present', () => {
    assert.equal(accountStatusLabel({ account_status: 'linked_disabled' }), 'Login Disabled');
  });
});

// ---------------------------------------------------------------------------
// CLIENT_FILTERS constant
// ---------------------------------------------------------------------------

describe('CLIENT_FILTERS', () => {
  it('contains expected filter values', () => {
    const values = CLIENT_FILTERS.map(f => f.value);
    assert.ok(values.includes('all'));
    assert.ok(values.includes('active_profiles'));
    assert.ok(values.includes('archived_profiles'));
    assert.ok(values.includes('linked_active'));
    assert.ok(values.includes('linked_disabled'));
    assert.ok(values.includes('invitation_sent'));
    assert.ok(values.includes('invite_available'));
    assert.ok(values.includes('profile_only'));
    assert.ok(values.includes('orphaned_identity'));
    assert.ok(values.includes('unlinked'));
  });
});


// ---------------------------------------------------------------------------
// buildClientDetailViewModel (Phase 1B.1B)
// ---------------------------------------------------------------------------

import { buildClientDetailViewModel } from '../src/utils/clientManagement.js';

describe('buildClientDetailViewModel', () => {
  it('linked active client', () => {
    const vm = buildClientDetailViewModel({
      display_name: 'Alice', email: 'a@b.com', phone: '555-1234',
      account_status: 'linked_active', is_active: true, portal_enabled: true,
      cognito_status: 'CONFIRMED',
    });
    assert.equal(vm.displayName, 'Alice');
    assert.equal(vm.accountStatusLabel, 'Login Active');
    assert.equal(vm.profileStatus, 'Active Profile');
    assert.equal(vm.portalAvailable, true);
    assert.equal(vm.cognitoLifecycleLabel, 'Confirmed');
  });

  it('linked disabled client', () => {
    const vm = buildClientDetailViewModel({
      display_name: 'Bob', account_status: 'linked_disabled', is_active: true,
      cognito_status: 'CONFIRMED',
    });
    assert.equal(vm.accountStatusLabel, 'Login Disabled');
    assert.equal(vm.profileStatus, 'Active Profile');
  });

  it('invitation pending', () => {
    const vm = buildClientDetailViewModel({
      display_name: 'Carol', account_status: 'invitation_sent', is_active: true,
      cognito_status: 'FORCE_CHANGE_PASSWORD',
    });
    assert.equal(vm.accountStatusLabel, 'Invitation Pending');
    assert.equal(vm.cognitoLifecycleLabel, 'Awaiting First Login');
  });

  it('ready to invite', () => {
    const vm = buildClientDetailViewModel({
      display_name: 'Dan', email: 'dan@x.com', account_status: 'invite_available', is_active: true,
    });
    assert.equal(vm.accountStatusLabel, 'Ready to Invite');
    assert.equal(vm.email, 'dan@x.com');
  });

  it('profile only', () => {
    const vm = buildClientDetailViewModel({
      display_name: 'Eve', account_status: 'profile_only', is_active: true,
    });
    assert.equal(vm.accountStatusLabel, 'Profile Only');
    assert.equal(vm.email, null);
  });

  it('orphaned identity', () => {
    const vm = buildClientDetailViewModel({
      display_name: 'Frank', account_status: 'orphaned_identity', is_active: true,
      cognito_status: 'DELETED',
    });
    assert.equal(vm.accountStatusLabel, 'Login Needs Repair');
    assert.equal(vm.cognitoLifecycleLabel, 'Deleted');
  });

  it('archived profile with linked_active account', () => {
    const vm = buildClientDetailViewModel({
      display_name: 'Grace', account_status: 'linked_active', is_active: false,
    });
    assert.equal(vm.profileStatus, 'Archived Profile');
    assert.equal(vm.accountStatusLabel, 'Login Active');
  });

  it('missing optional fields', () => {
    const vm = buildClientDetailViewModel({ display_name: 'Minimal' });
    assert.equal(vm.displayName, 'Minimal');
    assert.equal(vm.email, null);
    assert.equal(vm.phone, null);
    assert.equal(vm.address, null);
    assert.equal(vm.emergencyContact, null);
    assert.equal(vm.notes, null);
    assert.equal(vm.petNames, null);
    assert.equal(vm.petBreeds, null);
    assert.equal(vm.petSummary, null);
    assert.equal(vm.requestCount, null);
    assert.equal(vm.cognitoLifecycleLabel, null);
  });

  it('emergency contact', () => {
    const vm = buildClientDetailViewModel({ display_name: 'H', emergency_contact: 'Jane 555-9876' });
    assert.equal(vm.emergencyContact, 'Jane 555-9876');
  });

  it('service address', () => {
    const vm = buildClientDetailViewModel({ display_name: 'I', address: '123 Oak Dr' });
    assert.equal(vm.address, '123 Oak Dr');
  });

  it('pet summaries', () => {
    const vm = buildClientDetailViewModel({
      display_name: 'J', pet_names_summary: 'Buddy, Max', pet_breeds_summary: 'Lab, Poodle',
    });
    assert.equal(vm.petNames, 'Buddy, Max');
    assert.equal(vm.petBreeds, 'Lab, Poodle');
    assert.equal(vm.petSummary, 'Buddy, Max (Lab, Poodle)');
  });

  it('request_count when available', () => {
    const vm = buildClientDetailViewModel({ display_name: 'K', request_count: 3 });
    assert.equal(vm.requestCount, 3);
  });

  it('request_count absent', () => {
    const vm = buildClientDetailViewModel({ display_name: 'L' });
    assert.equal(vm.requestCount, null);
  });

  it('household_id does not replace client_id in view model', () => {
    const vm = buildClientDetailViewModel({ display_name: 'M', client_id: 'c1', household_id: 'c1' });
    assert.ok(!('client_id' in vm));
    assert.ok(!('household_id' in vm));
  });

  it('PK is absent from view model', () => {
    const vm = buildClientDetailViewModel({ display_name: 'N', PK: 'COMPANY#x' });
    assert.ok(!('PK' in vm));
  });

  it('SK is absent from view model', () => {
    const vm = buildClientDetailViewModel({ display_name: 'O', SK: 'CLIENT#c1' });
    assert.ok(!('SK' in vm));
  });

  it('cognito_sub is absent from view model', () => {
    const vm = buildClientDetailViewModel({ display_name: 'P', cognito_sub: 'sub-123' });
    assert.ok(!('cognito_sub' in vm));
  });

  it('company_id and tenant identifiers absent', () => {
    const vm = buildClientDetailViewModel({ display_name: 'Q', company_id: 'tog_and_dogs' });
    assert.ok(!('company_id' in vm));
  });

  it('raw Cognito username absent', () => {
    const vm = buildClientDetailViewModel({ display_name: 'R', cognito_username: 'user@example.com' });
    assert.ok(!('cognito_username' in vm));
  });

  it('input client object is not mutated', () => {
    const original = { display_name: 'S', email: 'x@y.com', is_active: true, account_status: 'linked_active' };
    const frozen = { ...original };
    buildClientDetailViewModel(original);
    assert.deepEqual(original, frozen);
  });

  it('null client returns null', () => {
    assert.equal(buildClientDetailViewModel(null), null);
  });
});
