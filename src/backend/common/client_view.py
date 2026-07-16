"""
Client/Household view model normalization.

Phase 1A: Compatibility layer that treats existing CLIENT records as
household-like entities without creating parallel HOUSEHOLD records.

Rules:
- household_id = client_id (canonical, no separate HOUSEHOLD entity)
- account_status is derived from existing fields (cognito_sub, cognito_status, is_active, portal_enabled)
- No Cognito sub, internal DynamoDB keys, or auth details are exposed
- No unbounded scans or per-client N+1 queries
- No data migration or dual writes
"""


def derive_account_status(client):
    """
    Derive a normalized account status from existing client record fields.
    
    Returns one of:
    - profile_only: No Cognito account exists or is linked
    - invite_available: Profile exists with email, no Cognito link yet
    - invitation_sent: Cognito user exists in FORCE_CHANGE_PASSWORD state
    - linked_active: Cognito user is linked and active (CONFIRMED)
    - linked_disabled: Cognito user is linked but Cognito account is disabled
    - orphaned_identity: Cognito sub is set but user may not exist (stale link)
    - unlinked: Previously linked, now explicitly unlinked

    Important semantic distinction:
    - is_active: profile active/archived state (admin action)
    - cognito_enabled: Cognito user Enabled/Disabled state (identity state)
    - For virtual users (no DynamoDB profile), is_active carries Cognito Enabled
    - linked_disabled means the Cognito identity is disabled, NOT that the
      profile is archived. An archived profile with enabled Cognito remains
      linked_active from an identity perspective.
    """
    cognito_sub = client.get('cognito_sub')
    cognito_status = (client.get('cognito_status') or '').upper()
    is_active = client.get('is_active', True)
    portal_enabled = client.get('portal_enabled', False)
    email = (client.get('email') or '').strip()
    is_virtual = client.get('is_virtual', False)
    # cognito_enabled is merged from the Cognito user's Enabled field during
    # the GET /admin/clients merge. For virtual users, is_active carries
    # the Cognito Enabled value instead.
    cognito_enabled = client.get('cognito_enabled', True)
    
    # Explicitly unlinked
    if cognito_status == 'UNLINKED' or cognito_sub == 'unlinked':
        return 'unlinked'
    
    # Virtual Cognito-only user (no DynamoDB profile)
    # For virtual users, is_active is set from Cognito Enabled during merge
    if is_virtual:
        return 'linked_active' if is_active else 'linked_disabled'
    
    # Has a Cognito link
    if cognito_sub and cognito_sub != 'unlinked':
        if cognito_status in ('FORCE_CHANGE_PASSWORD',):
            return 'invitation_sent'
        if cognito_status in ('CONFIRMED', 'RESET_REQUIRED', 'EXTERNAL_PROVIDER'):
            # linked_disabled means the Cognito identity is disabled
            if not cognito_enabled:
                return 'linked_disabled'
            return 'linked_active'
        # Cognito sub exists but status is unknown/deleted — orphaned
        if cognito_status in ('DELETED', 'COMPROMISED', 'UNKNOWN', ''):
            return 'orphaned_identity'
        # Default linked state — check Cognito enabled
        if not cognito_enabled:
            return 'linked_disabled'
        return 'linked_active'
    
    # No Cognito link
    if email:
        return 'invite_available'
    
    return 'profile_only'


def normalize_client_response(client):
    """
    Normalize a client record into the household-compatible view model.
    
    Adds:
    - household_id (= client_id)
    - account_status (derived)
    
    Preserves ALL existing fields for backward compatibility, including:
    - PK, SK (used by frontend for record operations)
    - cognito_sub (used by frontend for account-status display)
    - cognito_status, portal_enabled, is_active
    
    This is an additive normalization — no fields are removed.
    """
    if not client or not isinstance(client, dict):
        return client
    
    result = dict(client)
    
    # Add household compatibility fields
    result['household_id'] = result.get('client_id')
    result['account_status'] = derive_account_status(client)
    
    return result
