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
    - linked_disabled: Cognito user exists but client is disabled
    - orphaned_identity: Cognito sub is set but user may not exist (stale link)
    - unlinked: Previously linked, now explicitly unlinked
    """
    cognito_sub = client.get('cognito_sub')
    cognito_status = (client.get('cognito_status') or '').upper()
    is_active = client.get('is_active', True)
    portal_enabled = client.get('portal_enabled', False)
    email = (client.get('email') or '').strip()
    is_virtual = client.get('is_virtual', False)
    
    # Explicitly unlinked
    if cognito_status == 'UNLINKED' or cognito_sub == 'unlinked':
        return 'unlinked'
    
    # Virtual Cognito-only user (no DynamoDB profile)
    if is_virtual:
        return 'linked_active' if is_active else 'linked_disabled'
    
    # Has a Cognito link
    if cognito_sub and cognito_sub != 'unlinked':
        if cognito_status in ('FORCE_CHANGE_PASSWORD',):
            return 'invitation_sent'
        if cognito_status in ('CONFIRMED', 'RESET_REQUIRED', 'EXTERNAL_PROVIDER'):
            if is_active and portal_enabled:
                return 'linked_active'
            elif not is_active:
                return 'linked_disabled'
            else:
                return 'linked_active'
        # Cognito sub exists but status is unknown/deleted — orphaned
        if cognito_status in ('DELETED', 'COMPROMISED', 'UNKNOWN', ''):
            return 'orphaned_identity'
        # Default linked state
        return 'linked_active' if is_active else 'linked_disabled'
    
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
