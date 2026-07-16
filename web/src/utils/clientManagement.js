/**
 * Phase 1B.1A: Client Management pure utilities.
 *
 * Uses the server-provided `account_status` field from Phase 1A backend.
 * A temporary fallback derives status from legacy fields only when
 * `account_status` is absent (pre-deployment responses). This fallback
 * should be removed once all production responses include account_status.
 */

// ---------------------------------------------------------------------------
// Account-status labels
// ---------------------------------------------------------------------------

const ACCOUNT_STATUS_LABELS = {
  linked_active: 'Login Active',
  linked_disabled: 'Login Disabled',
  invitation_sent: 'Invitation Pending',
  invite_available: 'Ready to Invite',
  profile_only: 'Profile Only',
  orphaned_identity: 'Login Needs Repair',
  unlinked: 'Unlinked',
};

const ACCOUNT_STATUS_CLASSES = {
  linked_active: 'status-active',
  linked_disabled: 'status-disabled',
  invitation_sent: 'status-invited',
  invite_available: 'status-no-login',
  profile_only: 'status-offline',
  orphaned_identity: 'status-disabled',
  unlinked: 'status-no-login',
};

/**
 * Returns a human-readable label for the server-provided account_status.
 * Falls back to a legacy derivation if account_status is not present.
 */
export function accountStatusLabel(client) {
  const status = normalizeAccountStatus(client);
  return ACCOUNT_STATUS_LABELS[status] || status || 'Unknown';
}

/**
 * Returns the CSS class for the account-status badge.
 */
export function accountStatusClass(client) {
  const status = normalizeAccountStatus(client);
  return ACCOUNT_STATUS_CLASSES[status] || 'status-offline';
}

/**
 * Returns the canonical account_status value.
 * Uses server-provided field when present; falls back to legacy derivation.
 */
export function normalizeAccountStatus(client) {
  if (!client) return 'profile_only';

  // Prefer server-provided account_status (Phase 1A deployed)
  if (client.account_status) {
    return client.account_status;
  }

  // --- Temporary legacy fallback (remove after all responses include account_status) ---
  const cognitoSub = client.cognito_sub;
  const cognitoStatus = (client.cognito_status || '').toUpperCase();
  const email = (client.email || '').trim();

  if (cognitoStatus === 'UNLINKED' || cognitoSub === 'unlinked') return 'unlinked';
  if (client.is_virtual) return client.is_active !== false ? 'linked_active' : 'linked_disabled';

  if (cognitoSub && cognitoSub !== 'unlinked') {
    if (cognitoStatus === 'FORCE_CHANGE_PASSWORD' || cognitoStatus === 'UNCONFIRMED') return 'invitation_sent';
    if (['CONFIRMED', 'RESET_REQUIRED', 'EXTERNAL_PROVIDER'].includes(cognitoStatus)) return 'linked_active';
    if (['DELETED', 'COMPROMISED', 'UNKNOWN', ''].includes(cognitoStatus)) return 'orphaned_identity';
    return 'linked_active';
  }

  if (email) return 'invite_available';
  return 'profile_only';
}

// ---------------------------------------------------------------------------
// Profile-status labels
// ---------------------------------------------------------------------------

/**
 * Returns the profile (active/archived) label.
 * This is separate from account status and must not conflate the two.
 */
export function profileStatusLabel(client) {
  if (!client) return 'Unknown';
  return client.is_active === false ? 'Archived Profile' : 'Active Profile';
}

/**
 * Returns a CSS class for the profile-status badge.
 */
export function profileStatusClass(client) {
  if (!client) return '';
  return client.is_active === false ? 'status-archived' : 'status-profile-active';
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

/**
 * Returns true if the client matches the given search term.
 * Case-insensitive, trims input, searches across multiple text fields.
 */
export function clientMatchesSearch(client, rawTerm) {
  if (!rawTerm || !rawTerm.trim()) return true;
  const term = rawTerm.trim().toLowerCase();

  const fields = [
    client.display_name,
    client.email,
    client.phone,
    client.notes,
    client.pet_names_summary,
    client.pet_breeds_summary,
    client.address,
  ];

  return fields.some(f => f && String(f).toLowerCase().includes(term));
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

export const CLIENT_FILTERS = [
  { value: 'all', label: 'All Clients' },
  { value: 'active_profiles', label: 'Active Profiles' },
  { value: 'archived_profiles', label: 'Archived Profiles' },
  { value: 'linked_active', label: 'Login Active' },
  { value: 'linked_disabled', label: 'Login Disabled' },
  { value: 'invitation_sent', label: 'Invitation Pending' },
  { value: 'invite_available', label: 'Ready to Invite' },
  { value: 'profile_only', label: 'Profile Only' },
  { value: 'orphaned_identity', label: 'Login Needs Repair' },
  { value: 'unlinked', label: 'Unlinked' },
];

/**
 * Filters an array of clients by the given filter value.
 * Uses is_active for profile filters and account_status for account filters.
 */
export function filterClients(clients, filterValue) {
  if (!filterValue || filterValue === 'all') return clients;

  if (filterValue === 'active_profiles') {
    return clients.filter(c => c.is_active !== false);
  }
  if (filterValue === 'archived_profiles') {
    return clients.filter(c => c.is_active === false);
  }

  // Account-status filters use the normalized account_status
  return clients.filter(c => normalizeAccountStatus(c) === filterValue);
}

/**
 * Applies both search and filter, returning the visible client subset.
 */
export function getVisibleClients(clients, searchTerm, filterValue) {
  const filtered = filterClients(clients, filterValue);
  if (!searchTerm || !searchTerm.trim()) return filtered;
  return filtered.filter(c => clientMatchesSearch(c, searchTerm));
}
