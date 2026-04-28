import json
from common.response import error

# Priority: owner > admin > staff > client
ROLE_PRIORITY = {
    'owner': 4,
    'admin': 3,
    'staff': 2,
    'client': 1,
    'unknown': 0
}

def get_authorizer(event):
    if not isinstance(event, dict):
        return {}
    return event.get("requestContext", {}).get("authorizer", {}) or {}

def get_claims(event):
    authorizer = get_authorizer(event)
    claims = authorizer.get("claims") or authorizer.get("jwt", {}).get("claims") or {}
    return claims

def get_groups(event):
    claims = get_claims(event)
    raw_groups = claims.get("cognito:groups", [])
    if isinstance(raw_groups, str):
        return [g.strip() for g in raw_groups.split(",") if g.strip()]
    if isinstance(raw_groups, list):
        return raw_groups
    return []

def get_user_groups(event):
    return get_groups(event)

def get_effective_role(event):
    if not isinstance(event, dict):
        return 'unknown'
        
    claims = get_claims(event)
    user_email = (claims.get('email') or "").lower().strip()
    groups = get_user_groups(event)

    
    # Normalize groups to lowercase
    normalized_groups = [g.lower() for g in groups]
    
    # Priority resolution
    if 'owner' in normalized_groups:
        return 'owner'
    if 'admin' in normalized_groups:
        return 'admin'
    if 'staff' in normalized_groups:
        return 'staff'
    if 'client' in normalized_groups:
        return 'client'
        
    # Fallback for hardcoded emails (Ryan/Devs)
    if user_email in ['mattnicomn10@gmail.com', 'support@toganddogs.usmissionhero.com']:
        return 'owner' # Ryan is the owner
        
    return 'unknown'

def is_owner(event):
    return get_effective_role(event) == 'owner'

def is_admin(event):
    return get_effective_role(event) in ['owner', 'admin']

def is_staff(event):
    return get_effective_role(event) in ['owner', 'admin', 'staff']

def is_client(event):
    return get_effective_role(event) in ['owner', 'admin', 'staff', 'client']

def sanitize_booking_for_role(record, role):
    if not isinstance(record, dict):
        return record
        
    if role in ['owner', 'admin']:
        return record
        
    sanitized = dict(record)
    
    # Fields to redact for staff and clients
    sensitive_fields = [
        'meet_and_greet_notes',
        'internal_pricing_notes',
        'internal_notes',
        'admin_notes',
        'staff_notes',
        'private_notes',
        'pricing_notes',
        'discount_rationale',
        'owner_comments',
        'operational_comments',
        'audit_log'
    ]
    
    redacted_any = False
    for field in sensitive_fields:
        if field in sanitized:
            sanitized[field] = None
            redacted_any = True
            
    if redacted_any:
        sanitized['notes_redacted'] = True
        
    if role == 'client':
        # Clients also shouldn't see staff/admin-only metadata
        # (Prepare for future tenant/business scoping)
        pass
        
    return sanitized

def require_group(event, allowed_groups):
    role = get_effective_role(event)
    if role not in allowed_groups:
        raise PermissionError("Forbidden: Insufficient permissions")
    return role

def require_staff_portal_access(event):
    return require_group(event, ['owner', 'admin', 'staff'])

def require_notes_access(event):
    return require_group(event, ['owner', 'admin'])

def require_owner_or_admin(event):
    return require_group(event, ['owner', 'admin'])

def require_client_booking_access(event, booking):
    role = get_effective_role(event)
    if role in ['owner', 'admin', 'staff']:
        return True
        
    # Client access check
    if role == 'client':
        claims = get_claims(event)
        user_email = (claims.get('email') or "").lower().strip()

        
        booking_email = (booking.get('client_email') or "").lower().strip()
        if user_email and booking_email == user_email:
            return True
            
    raise PermissionError("Forbidden: You do not have access to this booking")

import os
DEFAULT_COMPANY_ID = os.environ.get("DEFAULT_COMPANY_ID", "tog_and_dogs")

def get_current_company_id(event, claims=None):
    # Phase 4 current behavior:
    # 1. Use trusted custom claim if later configured.
    # 2. Use StaffProfile/user mapping if already implemented.
    # 3. Fallback to DEFAULT_COMPANY_ID for current production.
    if not claims:
        claims = get_claims(event) if isinstance(event, dict) else {}
    
    custom_company = claims.get('custom:company_id')
    if custom_company:
        return custom_company
        
    return DEFAULT_COMPANY_ID

def validate_tenant_ownership(item, event):
    if not isinstance(item, dict):
        return
    item_company = item.get('company_id')
    # If the item doesn't have a company_id, it belongs to the fallback 'tog_and_dogs'
    if not item_company:
        item_company = DEFAULT_COMPANY_ID
        
    caller_company = get_current_company_id(event)
    if item_company != caller_company:
        raise PermissionError("Forbidden: Cross-tenant data access detected")


