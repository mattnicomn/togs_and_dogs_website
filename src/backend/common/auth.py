import json
import logging
import os
from common.response import error

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Priority: owner > admin > staff > client > platform_admin
ROLE_PRIORITY = {
    'owner': 4,
    'admin': 3,
    'staff': 2,
    'client': 1,
    'platform_admin': 0.5,
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
    if 'platform_admin' in normalized_groups:
        return 'platform_admin'
        
    # Fallback for hardcoded emails (Ryan/Devs)
    if user_email in ['mattnicomn10@gmail.com', 'support@toganddogs.usmissionhero.com']:
        return 'owner' # Ryan is the owner
        
    return 'unknown'

def is_platform_admin(event):
    groups = get_user_groups(event)
    normalized_groups = [g.lower() for g in groups]
    return 'platform_admin' in normalized_groups

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
    
    # Fields to additionally redact for clients only
    client_sensitive_fields = [
        'staff_assignment',
        'worker_id',
        'job_id',
        'assignment_color',
        'visit_notes',
        'completed_at',
        'completed_by',
        'job_completion_summary',
        'is_test_booking',
        'archive_reason',
        'archived_at',
        'archived_by'
    ]


    
    redacted_any = False
    for field in sensitive_fields:
        if field in sanitized:
            sanitized[field] = None
            redacted_any = True
            
    if role == 'client':
        for field in client_sensitive_fields:
            if field in sanitized:
                sanitized[field] = None
                redacted_any = True
        
    if redacted_any:
        sanitized['notes_redacted'] = True
        
    return sanitized

def resolve_client_identity(event):
    """
    Resolves the logged-in Cognito user to a local client profile.
    Matches by cognito_sub first, then falls back to verified email.
    Returns: The client_id string, or None if unlinked/unresolvable.
    """
    if get_effective_role(event) != 'client':
        return None
        
    claims = get_claims(event)
    cognito_sub = claims.get('sub')
    email = (claims.get('email') or "").lower().strip()
    
    if not cognito_sub and not email:
        return None
        
    company_id = get_current_company_id(event)
    from common.db import table as items_table
    from boto3.dynamodb.conditions import Key, Attr
    
    # Query DynamoDB for matching client profiles
    resp = items_table.query(
        KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("CLIENT#")
    )
    items = resp.get('Items', [])
    
    # 1. Match by exact cognito_sub first
    for client in items:
        if client.get('cognito_sub') == cognito_sub:
            return client.get('client_id')
            
    # 2. Fall back to email match (if email is verified)
    if email and claims.get('email_verified') in [True, 'true']:
        for client in items:
            client_email = (client.get('email') or "").lower().strip()
            if client_email == email:
                return client.get('client_id')
                
    return None

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

DEFAULT_COMPANY_ID = os.environ.get("DEFAULT_COMPANY_ID", "tog_and_dogs")

def _get_request_id(event):
    if not isinstance(event, dict):
        return None
    request_context = event.get('requestContext')
    if isinstance(request_context, dict):
        req_id = request_context.get('requestId')
        if req_id:
            return req_id
    return event.get('requestId') or event.get('request_id')

def _log_tenant_resolution(event_name, mode, is_empty_company_id, has_claims, default_company_id=None, event=None):
    log_payload = {
        "event": event_name,
        "mode": mode,
        "is_empty_company_id": is_empty_company_id,
        "has_claims": has_claims
    }
    if default_company_id is not None:
        log_payload["default_company_id"] = default_company_id
        
    req_id = _get_request_id(event)
    if req_id:
        log_payload["request_id"] = req_id
        
    logger.info(json.dumps(log_payload))

def get_current_company_id(event, claims=None):
    # Phase 4 current behavior:
    # 1. Use trusted custom claim if later configured.
    # 2. Use StaffProfile/user mapping if already implemented.
    # 3. Fallback to DEFAULT_COMPANY_ID for current production.
    if not claims:
        claims = get_claims(event) if isinstance(event, dict) else {}
    
    custom_company = claims.get('custom:company_id')
    if isinstance(custom_company, str):
        custom_company = custom_company.strip()
        
    if custom_company:
        return custom_company
        
    has_claims = bool(claims)
    is_empty_company = (custom_company == "") or (custom_company is None)
    mode = os.environ.get("TENANT_RESOLUTION_MODE", "single").lower().strip()
    
    if mode == "multi":
        _log_tenant_resolution(
            event_name="TENANT_RESOLUTION_FAILED",
            mode=mode,
            is_empty_company_id=is_empty_company,
            has_claims=has_claims,
            event=event
        )
        raise PermissionError("TENANT_RESOLUTION_FAILED: user missing custom:company_id in multi-tenant mode")
        
    # Single mode fallback
    _log_tenant_resolution(
        event_name="TENANT_RESOLUTION_FALLBACK",
        mode=mode,
        is_empty_company_id=is_empty_company,
        has_claims=has_claims,
        default_company_id=DEFAULT_COMPANY_ID,
        event=event
    )
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


def resolve_public_intake_tenant(event):
    """
    Resolve the tenant for a public (potentially unauthenticated) intake request.
    
    This resolver is used ONLY on public routes (/requests and staff-options).
    Portal routes use the strict get_current_company_id resolver.
    
    Resolution rules:
    1. The domain mapping (PUBLIC_INTAKE_DOMAIN_MAP) is ALWAYS required on public routes.
       An unmapped or unknown domain fails closed regardless of authentication state.
    2. If the request is also authenticated (custom:company_id present), the authenticated
       claim must MATCH the domain-mapped tenant. Mismatch is denied.
    3. After resolution, the authoritative tenant record must be active.
    4. No fallback to DEFAULT_COMPANY_ID.
    
    SECURITY:
    - Never reads company_id from request body, query string, or browser headers.
    - Domain mapping comes from server-side environment configuration only.
    - The domain is read from requestContext.domainName (set by API Gateway infrastructure).
    - Unknown domains, missing mappings, inactive tenants, and mismatches all fail closed.
    - Authenticated claims cannot bypass a missing domain mapping on public routes.
    """
    import json as _json
    
    # 1. Resolve domain-to-tenant mapping (REQUIRED on public routes)
    domain_tenant = _resolve_domain_tenant(event)
    
    if not domain_tenant:
        # No valid domain mapping — fail closed even if authenticated
        raise PermissionError(
            "PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED: no trusted tenant mapping for this request"
        )
    
    # 2. If authenticated, claim must match domain tenant
    claims = get_claims(event) if isinstance(event, dict) else {}
    custom_company = claims.get('custom:company_id')
    if isinstance(custom_company, str):
        custom_company = custom_company.strip()
    if not custom_company:
        custom_company = None
    
    if custom_company and custom_company != domain_tenant:
        raise PermissionError(
            "PUBLIC_INTAKE_TENANT_MISMATCH: authenticated identity does not match this service domain"
        )
    
    # 3. Validate the authoritative tenant record is active
    _validate_tenant_active(domain_tenant)
    
    return domain_tenant


def _validate_tenant_active(company_id):
    """
    Validate that the resolved tenant is active using an authoritative DynamoDB lookup.
    
    STRICT behavior (unlike _get_entitlement_safely which fails open):
    - Missing tenant record: DENY
    - Lookup failure/exception: DENY
    - Disabled/suspended/inactive tenant: DENY
    - Active tenant: ALLOW
    
    This must not use _get_entitlement_safely because that helper fails open
    for missing tenants (returns active starter). Public intake routing must
    fail closed when the authoritative tenant record is absent or invalid.
    """
    from common.db import get_item
    
    try:
        tenant = get_item(f"TENANT#{company_id}", "METADATA")
    except Exception:
        # Lookup failure — fail closed
        raise PermissionError(
            "PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED: service is not currently available"
        )
    
    if not tenant or not isinstance(tenant, dict):
        # Missing or malformed tenant record — fail closed
        raise PermissionError(
            "PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED: service is not currently available"
        )
    
    # Check subscription/access status using the same fields as require_active_tenant
    subscription_status = (tenant.get('subscription_status') or '').lower().strip()
    is_active = tenant.get('is_active', False)
    
    # Deny: disabled, suspended, canceled, or explicitly inactive
    if subscription_status in ('disabled', 'suspended', 'canceled', 'cancelled', 'paused'):
        raise PermissionError(
            "PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED: service is not currently available"
        )
    
    if not is_active and subscription_status != 'active':
        raise PermissionError(
            "PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED: service is not currently available"
        )
    
    # Active tenant — allow
    return


def _resolve_domain_tenant(event):
    """
    Look up the tenant from the request's API Gateway domain using the
    server-configured PUBLIC_INTAKE_DOMAIN_MAP.
    
    The map is a JSON object: {"domain": {"tenant_id": "...", "active": true, "public_intake_enabled": true}}
    
    Returns the tenant_id if the domain is mapped, verified, active, and intake-enabled.
    Returns None if no mapping is configured or the domain doesn't match.
    Raises PermissionError if the domain maps to an inactive or disabled entry.
    """
    import json as _json
    
    # Get the domain from API Gateway request context (server-controlled)
    request_context = event.get('requestContext', {}) if isinstance(event, dict) else {}
    domain_name = request_context.get('domainName', '').strip().lower()
    
    if not domain_name:
        return None
    
    # Load the domain map from environment
    domain_map_raw = os.environ.get("PUBLIC_INTAKE_DOMAIN_MAP", "").strip()
    if not domain_map_raw:
        return None
    
    try:
        domain_map = _json.loads(domain_map_raw)
    except (ValueError, TypeError):
        # Invalid JSON — fail closed
        logger.error("PUBLIC_INTAKE_DOMAIN_MAP contains invalid JSON")
        raise PermissionError("PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED: invalid domain configuration")
    
    if not isinstance(domain_map, dict):
        raise PermissionError("PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED: invalid domain configuration")
    
    # Look up this domain
    entry = domain_map.get(domain_name)
    if not entry or not isinstance(entry, dict):
        # Domain not in the allowlist — fail closed
        raise PermissionError("PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED: unrecognized service domain")
    
    # Validate entry fields
    tenant_id = entry.get('tenant_id', '').strip()
    if not tenant_id:
        raise PermissionError("PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED: domain mapping has no tenant")
    
    if not entry.get('active', False):
        raise PermissionError("PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED: domain mapping is not active")
    
    if not entry.get('public_intake_enabled', False):
        raise PermissionError("PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED: public intake is not enabled for this domain")
    
    return tenant_id


def build_tenant_user_attribute(company_id):
    """
    Build the Cognito custom:company_id attribute for a trusted tenant assignment.
    
    This helper MUST be used for all Cognito admin_create_user and admin_update_user_attributes
    calls that need to assign a user to a tenant. The company_id value MUST come exclusively
    from the server-side trusted context (get_current_company_id), never from browser input.
    
    Raises ValueError if company_id is empty or invalid.
    Returns a single Cognito UserAttribute dict.
    """
    if not company_id or not isinstance(company_id, str) or not company_id.strip():
        raise ValueError("Cannot assign tenant: company_id is empty or invalid")
    return {'Name': 'custom:company_id', 'Value': company_id.strip()}


def ensure_cognito_tenant_attribute(cognito_client, user_pool_id, username, company_id):
    """
    Ensure a Cognito user has the correct custom:company_id attribute set.
    
    Used during link-cognito flows to repair missing tenant assignment or verify
    existing assignment matches the expected tenant.
    
    Args:
        cognito_client: boto3 cognito-idp client
        user_pool_id: Cognito User Pool ID
        username: Cognito username (email)
        company_id: trusted company_id from server-side context
    
    Raises:
        ValueError: if company_id is empty
        PermissionError: if user already has a different non-empty company_id (cross-tenant conflict)
    """
    if not company_id or not company_id.strip():
        raise ValueError("Cannot assign tenant: company_id is empty or invalid")
    
    # Read the user's current custom:company_id
    try:
        user_resp = cognito_client.admin_get_user(UserPoolId=user_pool_id, Username=username)
        current_company = None
        for attr in user_resp.get('UserAttributes', []):
            if attr.get('Name') == 'custom:company_id':
                current_company = attr.get('Value', '').strip()
                break
    except Exception as e:
        raise RuntimeError(f"Failed to read Cognito user attributes: {e}")
    
    # If already set to a different non-empty tenant, deny the operation
    if current_company and current_company != company_id.strip():
        raise PermissionError(
            "Cross-tenant identity conflict: user is already assigned to a different tenant. "
            "Cannot reassign between tenants without explicit platform admin action."
        )
    
    # If already correctly set, no update needed
    if current_company == company_id.strip():
        return
    
    # Set the attribute
    cognito_client.admin_update_user_attributes(
        UserPoolId=user_pool_id,
        Username=username,
        UserAttributes=[build_tenant_user_attribute(company_id)]
    )
