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

def get_user_groups(event):
    if not isinstance(event, dict):
        return []
    authorizer = event.get('requestContext', {}).get('authorizer', {}) or {}
    claims = authorizer.get('claims', {}) or {}
    groups = claims.get('cognito:groups', [])
    if isinstance(groups, str):
        # Sometimes claims can be a string if not parsed correctly by API Gateway (rare but possible)
        groups = [groups]
    return groups

def get_effective_role(event):
    if not isinstance(event, dict):
        return 'unknown'
        
    authorizer = event.get('requestContext', {}).get('authorizer', {}) or {}
    claims = authorizer.get('claims', {}) or {}
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
        authorizer = event.get('requestContext', {}).get('authorizer', {}) or {}
        claims = authorizer.get('claims', {}) or {}
        user_email = (claims.get('email') or "").lower().strip()
        
        booking_email = (booking.get('client_email') or "").lower().strip()
        if user_email and booking_email == user_email:
            return True
            
    raise PermissionError("Forbidden: You do not have access to this booking")
