import json
import os
import boto3
from datetime import datetime, timezone
from common.db import query_by_status, get_item, update_status, table
from common.notifications.service import notify_event
from common.google_calendar import sync_calendar_event, delete_event
from common.response import success, bad_request, internal_error, not_found, error
from common.auth import get_effective_role, sanitize_booking_for_role, get_claims
from common.entitlement import EntitlementDenied
from common.audit import log_action
import uuid
import secrets
import string

def generate_temp_password(length=12):
    """Generates a secure temporary password meeting Cognito complexity requirements."""
    # Ensure at least one of each required type
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%^&*"
    
    password = [
        secrets.choice(lower),
        secrets.choice(upper),
        secrets.choice(digits),
        secrets.choice(special)
    ]
    
    # Fill the rest
    all_chars = lower + upper + digits + special
    password += [secrets.choice(all_chars) for _ in range(length - 4)]
    
    # Shuffle
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)

# Protected Accounts (US Mission Hero Platform Support)
# Release 6H: Now uses shared configurable module with env var + hardcoded fallback.
from common.protected_accounts import is_protected_profile, is_protected_email, is_protected_sub
PROTECTED_SUBS = None  # Deprecated — use is_protected_sub() instead
PROTECTED_USERNAMES = None  # Deprecated — use is_protected_email() instead

def is_cognito_user_in_company(user, company_id, mode):
    user_attrs = {a['Name']: a['Value'] for a in user.get('Attributes', [])}
    user_company = user_attrs.get('custom:company_id')
    
    if mode == "multi":
        return user_company == company_id
    else:
        if not user_company:
            from common.auth import DEFAULT_COMPANY_ID
            return company_id == DEFAULT_COMPANY_ID
        return user_company == company_id


def derive_staff_identity_state(profile, cog_match=None):
    """
    Release 22H: Derives the identity state for a staff profile.
    Returns a dict containing:
      - identity_state
      - identity_status_label
      - is_orphaned_identity
      - is_protected
      - can_manage_identity
      - identity_warning
    """
    is_protected = is_protected_profile(profile)
    
    if is_protected:
        return {
            "identity_state": "protected",
            "identity_status_label": "Protected",
            "is_orphaned_identity": False,
            "is_protected": True,
            "can_manage_identity": False,
            "identity_warning": None
        }
        
    if cog_match:
        enabled = cog_match.get('Enabled', True)
        if not enabled:
            return {
                "identity_state": "linked_disabled",
                "identity_status_label": "Login Disabled",
                "is_orphaned_identity": False,
                "is_protected": False,
                "can_manage_identity": True,
                "identity_warning": None
            }
        
        status = cog_match.get('UserStatus')
        if status == 'CONFIRMED':
            return {
                "identity_state": "linked_active",
                "identity_status_label": "Login Active",
                "is_orphaned_identity": False,
                "is_protected": False,
                "can_manage_identity": True,
                "identity_warning": None
            }
        else:
            return {
                "identity_state": "linked_invited",
                "identity_status_label": "Invited",
                "is_orphaned_identity": False,
                "is_protected": False,
                "can_manage_identity": True,
                "identity_warning": None
            }
            
    # No Cognito match found
    sub = profile.get('cognito_sub')
    if not sub or sub == 'unlinked':
        return {
            "identity_state": "profile_only",
            "identity_status_label": "No Login",
            "is_orphaned_identity": False,
            "is_protected": False,
            "can_manage_identity": True,
            "identity_warning": None
        }
    else:
        # Has a cognito_sub reference but user doesn't exist in Cognito
        return {
            "identity_state": "orphaned",
            "identity_status_label": "Orphaned Login",
            "is_orphaned_identity": True,
            "is_protected": False,
            "can_manage_identity": True,
            "identity_warning": "This profile references a login that no longer exists."
        }



def normalize_phone_e164(phone):
    """
    Release 6E: Normalize common US phone formats to E.164 for Cognito sync.
    Returns the normalized phone string, or None if it cannot be safely normalized.
    
    Examples:
        '5551234567'       -> '+15551234567'
        '(555) 123-4567'   -> '+15551234567'
        '1-555-123-4567'   -> '+15551234567'
        '+15551234567'     -> '+15551234567' (unchanged)
        'invalid'          -> None
    """
    import re
    if not phone:
        return None
    
    phone = phone.strip()
    
    # Already valid E.164
    if re.match(r'^\+\d{10,15}$', phone):
        return phone
    
    # Strip all non-digit characters
    digits = re.sub(r'\D', '', phone)
    
    # US number: 10 digits (no country code)
    if len(digits) == 10:
        return f'+1{digits}'
    
    # US number: 11 digits starting with 1
    if len(digits) == 11 and digits[0] == '1':
        return f'+{digits}'
    
    # Cannot safely normalize — return None (caller should skip Cognito sync)
    return None


DEFAULT_MAX_PAYMENT_AMOUNT_CENTS = 1000000

def validate_and_parse_amount_cents(amount):
    """
    Validates that the amount is a safe, positive integer within bounds.
    Blocks: None, bool, non-numeric, negative, zero, NaN, floats, and huge amounts.
    """
    if amount is None:
        raise ValueError("amount_cents is required")
        
    # Python bool is a subclass of int, so isinstance(True, int) is True!
    if isinstance(amount, bool):
        raise ValueError("amount_cents must be a positive integer, not boolean")
        
    if not isinstance(amount, int):
        raise ValueError("amount_cents must be a positive integer")

    if amount <= 0:
        raise ValueError("amount_cents must be greater than zero")

    # Prevent accidental huge charges with a reasonable configurable max amount.
    max_amount_cents = int(os.environ.get("MAX_PAYMENT_AMOUNT_CENTS", DEFAULT_MAX_PAYMENT_AMOUNT_CENTS))
    if amount > max_amount_cents:
        max_usd = max_amount_cents / 100
        raise ValueError(f"amount_cents exceeds the maximum limit of ${max_usd:,.2f} ({max_amount_cents} cents)")

    return amount


def _resolve_admin_record(pk, sk, company_id=None):
    """
    Robust record resolution for administrative cleanup.
    Handles swapped keys and malformed identifiers in 'Data Issues'.
    Release 11E: Optional company_id parameter for tenant-scoped scan fallback.
    """
    from common.db import get_item, table as _table
    from boto3.dynamodb.conditions import Attr

    # 1. Direct attempt
    item = get_item(pk, sk)
    if item:
        return item, pk, sk

    # 2. Swapped keys fallback
    item = get_item(sk, pk)
    if item:
        return item, sk, pk

    # 3. ID-healing Scan fallback (for malformed records)
    # Extracts raw IDs and looks for them in any key field
    raw_pk_id = pk.replace("JOB#", "").replace("REQ#", "")
    raw_sk_id = sk.replace("JOB#", "").replace("REQ#", "")
    
    if not raw_pk_id and not raw_sk_id:
        return None, pk, sk

    scan_kwargs = {
        "FilterExpression": Attr('PK').contains(raw_pk_id) | Attr('SK').contains(raw_pk_id) | \
                           Attr('PK').contains(raw_sk_id) | Attr('SK').contains(raw_sk_id)
    }
    
    response = _table.scan(**scan_kwargs)
    found_items = response.get('Items', [])
    while 'LastEvaluatedKey' in response and not found_items:
        scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        response = _table.scan(**scan_kwargs)
        found_items.extend(response.get('Items', []))

    # Release 11E: Post-filter scan results to the caller's tenant
    if company_id and found_items:
        from common.auth import DEFAULT_COMPANY_ID
        found_items = [
            i for i in found_items
            if (i.get('company_id') or DEFAULT_COMPANY_ID) == company_id
        ]
        
    if found_items:
        # Return first match and its actual keys
        target = found_items[0]
        return target, target.get('PK'), target.get('SK')

    return None, pk, sk





def handler(event, context):
    try:
        http_method = event.get('httpMethod')
        path_params = event.get('pathParameters', {}) or {}
        query_params = event.get('queryStringParameters', {}) or {}
        
        path = event.get('path', '')

        # --- NEW TENANT INFO ENDPOINT ---
        if http_method == 'GET' and (path == '/admin/tenant-info' or path.endswith('/admin/tenant-info')):
            role = get_effective_role(event)
            if role not in ['owner', 'admin', 'staff', 'client', 'platform_admin']:
                return error(403, "Forbidden", event)
                
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            
            tenant = get_item(f"TENANT#{company_id}", "METADATA")
            
            if tenant:
                display_name = tenant.get('display_name')
                subscription_tier = tenant.get('subscription_tier', 'starter')
                subscription_status = tenant.get('subscription_status', 'disabled')
            else:
                from common.auth import DEFAULT_COMPANY_ID
                if company_id == DEFAULT_COMPANY_ID:
                    display_name = "Tog and Dogs"
                    subscription_tier = "starter"
                    subscription_status = "active"
                else:
                    display_name = company_id
                    subscription_tier = "starter"
                    subscription_status = "disabled"
                    
            from common.entitlement import _get_entitlement_safely
            ent = _get_entitlement_safely(company_id)
            
            if not ent.is_access_allowed or ent.is_blocked:
                return success({
                    "company_id": company_id,
                    "display_name": display_name,
                    "subscription_status": subscription_status,
                    "is_access_allowed": False,
                    "is_blocked": True
                }, event)
                    
            # Safe calendar check
            calendar_status = "NOT_CONNECTED"
            from common.auth import DEFAULT_COMPANY_ID
            if company_id == DEFAULT_COMPANY_ID:
                try:
                    from handlers.google_auth_handler import get_status as _get_status
                    status_resp = _get_status(event)
                    body = json.loads(status_resp.get('body', '{}'))
                    calendar_status = body.get('status', 'NOT_CONNECTED')
                except Exception as e:
                    print(f"Warning: Failed to resolve calendar status: {e}")
                    
            from common.calendar_metadata import get_tenant_calendar_config
            calendar_config = get_tenant_calendar_config(tenant, company_id, calendar_status)
                    
            return success({
                "company_id": company_id,
                "display_name": display_name,
                "subscription_tier": subscription_tier,
                "subscription_status": subscription_status,
                "google_calendar_status": calendar_status,
                "is_access_allowed": True,
                "is_blocked": False,
                **calendar_config
            }, event)

            
        # Enforce active tenant check for all other routes
        from common.entitlement import require_active_tenant
        block_resp = require_active_tenant(event)
        if block_resp:
            return block_resp

            
        # --- CLIENT PORTAL BOUNDARIES ---
        if path.startswith('/client/'):
            role = get_effective_role(event)
            if role != 'client':
                # Allow staff/admin to impersonate or access if needed, but primarily client
                pass
                
            from common.auth import resolve_client_identity
            client_id = resolve_client_identity(event)
            if not client_id:
                # If they have no local profile linked, they have no data.
                return success({"requests": [], "pets": [], "message": "No local profile linked"}, event)
                
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            from common.db import table as items_table
            from boto3.dynamodb.conditions import Key
            
            if http_method == 'GET' and path == '/client/requests':
                # Fetch only requests belonging to this client using table scan with filter
                # (Since requests use PK=REQ#..., we scan and filter by client_id)
                from boto3.dynamodb.conditions import Attr
                
                scan_kwargs = {
                    "FilterExpression": Attr("client_id").eq(client_id) & Attr("entity_type").eq("REQUEST")
                }
                
                response = items_table.scan(**scan_kwargs)
                items = response.get('Items', [])
                
                # Aggressively redact staff notes and pricing metadata
                items = [sanitize_booking_for_role(item, 'client') for item in items]
                
                # Sort newest first based on start_date
                items.sort(key=lambda x: x.get('start_date', ''), reverse=True)
                
                return success({
                    "requests": items,
                    "lastKey": None # Pagination omitted for client context locally
                }, event)
                
        # --- END CLIENT PORTAL BOUNDARIES ---
        
        if http_method == 'GET' and path == '/admin/export-data':
            role = get_effective_role(event)
            if role not in ['owner', 'admin']:
                return error(403, "Forbidden", event)
            
            from common.db import table as _table
            from common.auth import get_current_company_id as _get_company_id, DEFAULT_COMPANY_ID
            from boto3.dynamodb.conditions import Attr as _Attr

            # Release 11E: Filter export to caller's company only
            _company_id = _get_company_id(event)
            
            # Release 17D: Entitlement gate for export
            from common.entitlement import check_feature
            check_feature(_company_id, 'export_enabled', context=event)
            
            # Fetch all records for backup
            # Low-volume operational scale allows for periodic admin scans
            scan_kwargs = {
                "FilterExpression": _Attr('company_id').eq(_company_id) | _Attr('company_id').not_exists()
            }
            response = _table.scan(**scan_kwargs)
            items = response.get('Items', [])
            while 'LastEvaluatedKey' in response:
                scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
                response = _table.scan(**scan_kwargs)
                items.extend(response.get('Items', []))
            
            # Categorize by entity type or key pattern (robust fallbacks)
            requests = [i for i in items if i.get('entity_type') == 'REQUEST' or i.get('PK', '').startswith('REQ#')]
            pets = [i for i in items if i.get('entity_type') == 'PET' or i.get('PK', '').startswith('PET#')]
            jobs = [i for i in items if i.get('entity_type') == 'JOB' or i.get('PK', '').startswith('JOB#')]
            
            # Clients and Staff share COMPANY# PK
            clients = [i for i in items if (i.get('SK', '').startswith('CLIENT#') and i.get('PK', '').startswith('COMPANY#')) or i.get('entity_type') == 'CLIENT']
            staff = [i for i in items if (i.get('SK', '').startswith('STAFF#') and i.get('PK', '').startswith('COMPANY#')) or i.get('entity_type') == 'STAFF']
            
            # Audit the export action
            log_action(event, 'EXPORT_BACKUP', 'SYSTEM', 'DATA_BACKUP', metadata={
                "request_count": len(requests),
                "client_count": len(clients),
                "pet_count": len(pets),
                "staff_count": len(staff)
            })
            
            return success({
                "requests": requests,
                "clients": clients,
                "pets": pets,
                "staff": staff,
                "jobs": jobs
            }, event)
        
        if http_method == 'GET' and (path == '/admin/staff' or path.endswith('/admin/staff')):
            role = get_effective_role(event)
            if role not in ['owner', 'admin']:
                return error(403, "Forbidden", event)
                
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            from common.db import table as items_table
            from boto3.dynamodb.conditions import Key
            
            from boto3.dynamodb.conditions import Key
            response = items_table.query(
                KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("STAFF#")
            )
            staff_profiles = response.get('Items', [])
            
            # Fetch Cognito users for staff
            import boto3
            cognito_client = boto3.client('cognito-idp')
            user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
            
            cognito_staff = []
            # Get groups matching Staff, owner, Admin, or company-scoped
            groups_resp = cognito_client.list_groups(UserPoolId=user_pool_id)
            target_groups = []
            for g in groups_resp.get('Groups', []):
                g_name = g['GroupName']
                g_lower = g_name.lower()
                if any(term in g_lower for term in ['staff', 'owner', 'admin']):
                    target_groups.append(g_name)
            
            # Fetch users from those groups
            seen_usernames = set()
            for grp in target_groups:
                u_resp = cognito_client.list_users_in_group(UserPoolId=user_pool_id, GroupName=grp)
                for u in u_resp.get('Users', []):
                    if u['Username'] not in seen_usernames:
                        mode = os.environ.get("TENANT_RESOLUTION_MODE", "single").lower().strip()
                        if is_cognito_user_in_company(u, company_id, mode):
                            seen_usernames.add(u['Username'])
                            cognito_staff.append(u)

            # Merge Cognito + DynamoDB
            merged_staff = []
            matched_subs = set()
            matched_emails = set()
            
            # 1. Start with DynamoDB staff records
            for s in staff_profiles:
                # Enrich with Cognito info if possible
                s_email = (s.get('email') or '').lower()
                s_sub = s.get('cognito_sub')
                
                if s_sub == 'unlinked':
                    s['cognito_sub'] = None
                    s['cognito_status'] = 'unlinked'
                    s['is_protected'] = is_protected_profile(s)
                    # Release 8U: Unlinked profiles are never assignable
                    s['is_assignable'] = False
                    
                    # Derive and apply identity state
                    identity_info = derive_staff_identity_state(s, None)
                    s.update(identity_info)
                    
                    merged_staff.append(s)
                    # Find and mark Cognito user as matched by email to prevent virtual user duplication
                    for cu in cognito_staff:
                        cu_email = next((a['Value'] for a in cu['Attributes'] if a['Name'] == 'email'), '').lower()
                        cu_sub = next((a['Value'] for a in cu['Attributes'] if a['Name'] == 'sub'), '')
                        if s_email and s_email == cu_email:
                            if cu_sub: matched_subs.add(cu_sub)
                            if cu_email: matched_emails.add(cu_email)
                            break
                    continue
                
                cog_match = None
                for cu in cognito_staff:
                    cu_email = next((a['Value'] for a in cu['Attributes'] if a['Name'] == 'email'), '').lower()
                    cu_sub = next((a['Value'] for a in cu['Attributes'] if a['Name'] == 'sub'), '')
                    if (s_sub and s_sub == cu_sub) or (s_email and s_email == cu_email):
                        cog_match = cu
                        if cu_sub: matched_subs.add(cu_sub)
                        if cu_email: matched_emails.add(cu_email)
                        break
                        
                if cog_match:
                    s['cognito_status'] = cog_match.get('UserStatus')
                    s['cognito_username'] = cog_match.get('Username')
                    if not s.get('cognito_sub'):
                        s['cognito_sub'] = next((a['Value'] for a in cog_match['Attributes'] if a['Name'] == 'sub'), None)
                        
                # Derive and apply identity state
                identity_info = derive_staff_identity_state(s, cog_match)
                s.update(identity_info)
                
                # Release 6H Phase 2: Include is_protected flag for frontend consumption
                s['is_protected'] = is_protected_profile(s)
                # Release 8U: Enforce assignment eligibility — profiles with invalid email or no
                # real Cognito sub must not appear in assignment dropdowns regardless of DB flag.
                import re as _re
                _VALID_EMAIL_RE = _re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
                _s_email_check = (s.get('email') or '').strip()
                _s_sub_check = s.get('cognito_sub')
                if not _VALID_EMAIL_RE.match(_s_email_check) or not _s_sub_check or _s_sub_check == 'unlinked':
                    s['is_assignable'] = False
                merged_staff.append(s)
                    
            # 2. Add Cognito-only staff users
            for cu in cognito_staff:
                cu_email = next((a['Value'] for a in cu['Attributes'] if a['Name'] == 'email'), '').lower()
                cu_sub = next((a['Value'] for a in cu['Attributes'] if a['Name'] == 'sub'), '')
                
                if cu_sub in matched_subs or cu_email in matched_emails:
                    continue
                    
                virtual_id = f"cognito_{cu['Username']}"
                v_profile = {
                    "PK": f"COMPANY#{company_id}",
                    "SK": f"STAFF#{virtual_id}",
                    "company_id": company_id,
                    "staff_id": virtual_id,
                    "display_name": cu['Username'],
                    "role": 'Staff',
                    "email": cu_email,
                    "cognito_sub": cu_sub,
                    "is_active": cu.get('Enabled', True),
                    "is_assignable": True, # Virtual staff are now assignable by default
                    "assignment_color": 'var(--staff-ryan)',
                    "cognito_status": cu.get('UserStatus'),
                    "is_virtual": True
                }
                
                # Derive and apply identity state
                identity_info = derive_staff_identity_state(v_profile, cu)
                v_profile.update(identity_info)
                
                # Release 6H Phase 2: Include is_protected flag for frontend
                v_profile['is_protected'] = is_protected_profile(v_profile)
                # Release 8U: Virtual profiles already have a real cognito_sub; no override needed.
                # But guard against any edge case where virtual profile has no valid sub.
                if not cu_sub:
                    v_profile['is_assignable'] = False
                merged_staff.append(v_profile)
                
            return success({"staff": merged_staff}, event)

        if http_method == 'POST' and (path == '/admin/staff' or path.endswith('/admin/staff')):
            role = get_effective_role(event)
            if role not in ['owner', 'admin']:
                return error(403, "Forbidden", event)
                
            try:
                body = json.loads(event.get('body', '{}'))
            except Exception:
                return bad_request("Invalid JSON body", event)
                
            display_name = body.get('display_name', '').strip()
            if not display_name:
                return bad_request("display_name is required", event)
                
            if display_name.lower() == 'unassigned':
                return bad_request("Unassigned is a reserved system option", event)
                
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            from common.db import table as items_table
            from boto3.dynamodb.conditions import Key
            
            # Check duplicate active display_name
            resp = items_table.query(
                KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("STAFF#")
            )

            existing_staff = resp.get('Items', [])
            
            # Release 17D: Entitlement gate for staff limits
            from common.entitlement import check_limit
            check_limit(company_id, 'max_staff', len(existing_staff), context=event)

            for s in existing_staff:
                if (s.get('display_name') or '').lower() == display_name.lower() and s.get('is_active') == True:
                    return error(409, f"Active staff with display_name {display_name} already exists", event)

            # Release 6H: Block creation with protected admin email
            creation_email = (body.get('email') or '').strip().lower()
            if creation_email and is_protected_email(creation_email):
                return error(403, "Cannot create a standard profile using a protected account identity.", event)
                    
            staff_id = f"staff_{str(uuid.uuid4())[:8]}"
            
            new_profile = {
                "PK": f"COMPANY#{company_id}",
                "SK": f"STAFF#{staff_id}",
                "company_id": company_id,
                "staff_id": staff_id,
                "display_name": display_name,
                "role": body.get('role', 'Staff'),
                "email": body.get('email', '').strip() or None,
                "cognito_sub": body.get('cognito_sub', '').strip() or None,
                "is_active": True,
                "is_assignable": body.get('is_assignable', False) if body.get('role', 'Staff').lower() in ['owner', 'admin'] else body.get('is_assignable', True),
                "assignment_color": body.get('assignment_color', 'var(--staff-ryan)'),

                "phone": body.get('phone', '').strip() or None,
                "notes": body.get('notes', '').strip() or None,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            items_table.put_item(Item=new_profile)
            return success(new_profile, event)

        # --- Phase 3 Onboarding Routes ---
        if http_method == 'POST' and '/admin/staff/onboard' in path:
            role = get_effective_role(event)
            if role not in ['owner', 'admin']:
                return error(403, "Forbidden", event)
                
            try:
                body = json.loads(event.get('body', '{}'))
            except Exception:
                return bad_request("Invalid JSON body", event)
                
            display_name = body.get('display_name', '').strip()
            email = body.get('email', '').strip().lower()
            
            if not display_name:
                return bad_request("display_name is required", event)
            if not email:
                return bad_request("email is required", event)
            if display_name.lower() == 'unassigned':
                return bad_request("Unassigned is a reserved system option", event)
                
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            from common.db import table as items_table
            from boto3.dynamodb.conditions import Key
            
            # Check duplicate active display_name & email
            resp = items_table.query(
                KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("STAFF#")
            )

            existing_staff = resp.get('Items', [])
            
            # Release 17D: Entitlement gate for staff limits
            from common.entitlement import check_limit
            check_limit(company_id, 'max_staff', len(existing_staff), context=event)

            for s in existing_staff:
                if s.get('is_active') == True:
                    if (s.get('display_name') or '').lower() == display_name.lower():
                        return error(409, f"Active staff with display_name {display_name} already exists", event)
                    if (s.get('email') or '').lower() == email:
                        return error(409, f"Active staff with email {email} already exists", event)

            # Release 6H: Block onboarding with protected admin email
            if is_protected_email(email):
                return error(403, "Cannot create a standard profile using a protected account identity.", event)
                        
            # Create Cognito User
            import boto3
            cognito = boto3.client('cognito-idp')
            user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
            
            try:
                # Map role to Cognito group
                role_input = body.get('role', 'Staff')
                cognito_group = 'Staff'
                if role_input.lower() == 'owner':
                    cognito_group = 'owner'
                elif role_input.lower() == 'admin':
                    cognito_group = 'Admin'
                    
                # Generate a secure temporary password and suppress Cognito's default email
                temp_password = generate_temp_password()
                
                # Create user in FORCE_CHANGE_PASSWORD
                cog_resp = cognito.admin_create_user(
                    UserPoolId=user_pool_id,
                    Username=email,
                    TemporaryPassword=temp_password,
                    UserAttributes=[
                        {'Name': 'email', 'Value': email},
                        {'Name': 'email_verified', 'Value': 'true'},
                    ],
                    MessageAction='SUPPRESS', # Suppress Cognito's default invite
                    DesiredDeliveryMediums=['EMAIL']
                )
                
                # Assign to Cognito group
                cognito.admin_add_user_to_group(
                    UserPoolId=user_pool_id,
                    Username=email,
                    GroupName=cognito_group
                )
                
                # Fetch Cognito Sub
                cognito_sub = None
                for attr in cog_resp.get('User', {}).get('Attributes', []):
                    if attr.get('Name') == 'sub':
                        cognito_sub = attr.get('Value')
                        break
                        
                staff_id = f"staff_{str(uuid.uuid4())[:8]}"
                
                new_profile = {
                    "PK": f"COMPANY#{company_id}",
                    "SK": f"STAFF#{staff_id}",
                    "company_id": company_id,
                    "staff_id": staff_id,
                    "display_name": display_name,
                    "role": role_input,
                    "email": email,
                    "cognito_sub": cognito_sub,
                    "is_active": True,
                    "is_assignable": body.get('is_assignable', False) if role_input.lower() in ['owner', 'admin'] else body.get('is_assignable', True),
                    "assignment_color": body.get('assignment_color', 'blue'),

                    "phone": body.get('phone', '').strip() or None,
                    "cognito_status": "FORCE_CHANGE_PASSWORD",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                items_table.put_item(Item=new_profile)

                # Send branded welcome email with the temporary password
                try:
                    result = notify_event(
                        event_type='WELCOME_INVITE_STAFF',
                        context={
                            "staff_name": display_name,
                            "email": email,
                            "temp_password": temp_password,
                            "portal_url": os.environ.get('NOTIFICATION_PORTAL_URL', 'https://toganddogs.usmissionhero.com')
                        }
                    )
                    if not result.get('success'):
                        return error(500, f"Staff account was prepared, but the welcome email could not be sent. {result.get('message', '')}", event)
                except Exception as notify_err:
                    print(f"Warning: Branded staff invite failed: {notify_err}")
                    return error(500, f"Staff account was prepared, but an unexpected error occurred while sending the email: {str(notify_err)}", event)

                return success(new_profile, event)
                
            except cognito.exceptions.UsernameExistsException:
                if body.get('mode') == 'create_or_link' or body.get('mode') == 'link_existing':
                    try:
                        cog_user = cognito.admin_get_user(
                            UserPoolId=user_pool_id,
                            Username=email
                        )
                        
                        cognito_sub = None
                        for attr in cog_user.get('UserAttributes', []):
                            if attr.get('Name') == 'sub':
                                cognito_sub = attr.get('Value')
                                break
                                
                        role_input = body.get('role', 'Staff')
                        cognito_group = 'Staff'
                        if role_input.lower() == 'owner':
                            cognito_group = 'owner'
                        elif role_input.lower() == 'admin':
                            cognito_group = 'Admin'
                            
                        try:
                            cognito.admin_add_user_to_group(
                                UserPoolId=user_pool_id,
                                Username=email,
                                GroupName=cognito_group
                            )
                        except Exception as group_err:
                            print(f"Warn: Add to group failed or user already in group: {group_err}")
                            
                        existing_by_email = None
                        existing_by_sub = None
                        for s in existing_staff:
                            if (s.get('email') or '').lower() == email:
                                existing_by_email = s
                            if s.get('cognito_sub') == cognito_sub:
                                existing_by_sub = s
                                
                        target_profile = existing_by_email or existing_by_sub
                        
                        if target_profile:
                            if target_profile.get('cognito_sub') == cognito_sub:
                                return success({
                                    "message": "Staff profile is already linked to this Cognito user.",
                                    "profile": target_profile
                                }, event)
                                
                            # Update existing profile with new Cognito link AND form values
                            target_profile['cognito_sub'] = cognito_sub
                            target_profile['cognito_status'] = cog_user.get('UserStatus')
                            target_profile['updated_at'] = datetime.utcnow().isoformat()
                            
                            # Preserve form values during link
                            if 'display_name' in body: target_profile['display_name'] = body['display_name']
                            if 'role' in body: target_profile['role'] = body['role']
                            if 'phone' in body: target_profile['phone'] = body['phone']
                            if 'notes' in body: target_profile['notes'] = body['notes']
                            if 'is_assignable' in body: target_profile['is_assignable'] = body['is_assignable']
                            if 'assignment_color' in body: target_profile['assignment_color'] = body['assignment_color']
                            
                            if not target_profile.get('email'):
                                target_profile['email'] = email
                            
                            items_table.put_item(Item=target_profile)
                            return success(target_profile, event)
                        else:
                            staff_id = f"staff_{str(uuid.uuid4())[:8]}"
                            
                            new_profile = {
                                "PK": f"COMPANY#{company_id}",
                                "SK": f"STAFF#{staff_id}",
                                "company_id": company_id,
                                "staff_id": staff_id,
                                "display_name": display_name,
                                "role": role_input,
                                "email": email,
                                "cognito_sub": cognito_sub,
                                "is_active": True,
                                "is_assignable": body.get('is_assignable', True),
                                "assignment_color": body.get('assignment_color', 'blue'),
                                "phone": body.get('phone', '').strip() or None,
                                "cognito_status": cog_user.get('UserStatus'),
                                "created_at": datetime.utcnow().isoformat(),
                                "updated_at": datetime.utcnow().isoformat()
                            }
                            items_table.put_item(Item=new_profile)
                            return success(new_profile, event)
                    except Exception as fallback_err:
                        print(f"Fallback link error: {fallback_err}")
                        return internal_error(f"Failed to link existing user: {fallback_err}", event)
                        
                return error(409, "Cognito user already exists with this email. Use Link Existing User instead.", event)
            except Exception as e:
                print(f"Cognito onboard error: {e}")
                return internal_error(str(e), event)

        # POST /admin/clients/onboard
        if http_method == 'POST' and '/admin/clients/onboard' in path:
            role = get_effective_role(event)
            if role not in ['owner', 'admin']:
                return error(403, "Forbidden", event)
                
            try:
                body = json.loads(event.get('body', '{}'))
            except Exception:
                return bad_request("Invalid JSON body", event)
                
            display_name = body.get('display_name', '').strip()
            email = body.get('email', '').strip().lower()
            
            if not display_name or not email:
                return bad_request("display_name and email are required", event)
                
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            from common.db import table as items_table
            from boto3.dynamodb.conditions import Key
            
            # Check duplicate active email
            resp = items_table.query(
                KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("CLIENT#")
            )
            existing_clients = resp.get('Items', [])
            for c in existing_clients:
                if c.get('is_active') == True and (c.get('email') or '').lower() == email:
                    return error(409, f"Active client with email {email} already exists", event)

            # Release 6H: Block client onboarding with protected admin email
            if is_protected_email(email):
                return error(403, "Cannot create a standard profile using a protected account identity.", event)

            # Entitlement Check
            try:
                from common.entitlement import check_limit, get_active_client_count
                current_count = get_active_client_count(company_id)
                check_limit(company_id, 'max_active_clients', current_count, context=event)
            except EntitlementDenied as ed:
                return error(403, str(ed), event)

            import boto3
            cognito = boto3.client('cognito-idp')
            user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
            
            try:
                # Generate a secure temporary password and suppress Cognito's default email
                temp_password = generate_temp_password()
                
                # Create user in FORCE_CHANGE_PASSWORD
                cog_resp = cognito.admin_create_user(
                    UserPoolId=user_pool_id,
                    Username=email,
                    TemporaryPassword=temp_password,
                    UserAttributes=[
                        {'Name': 'email', 'Value': email},
                        {'Name': 'email_verified', 'Value': 'true'},
                    ],
                    MessageAction='SUPPRESS', # Suppress Cognito's default invite
                    DesiredDeliveryMediums=['EMAIL']
                )
                
                # Assign to 'client' group
                cognito.admin_add_user_to_group(
                    UserPoolId=user_pool_id,
                    Username=email,
                    GroupName='client'
                )
                
                # Fetch Cognito Sub
                cognito_sub = None
                for attr in cog_resp.get('User', {}).get('Attributes', []):
                    if attr.get('Name') == 'sub':
                        cognito_sub = attr.get('Value')
                        break
                        
                client_id = f"client_{str(uuid.uuid4())[:8]}"
                
                new_profile = {
                    "PK": f"COMPANY#{company_id}",
                    "SK": f"CLIENT#{client_id}",
                    "company_id": company_id,
                    "client_id": client_id,
                    "display_name": display_name,
                    "email": email,
                    "cognito_sub": cognito_sub,
                    "is_active": True,
                    "portal_enabled": True,
                    "phone": body.get('phone', '').strip() or None,
                    "address": body.get('address', '').strip() or None,
                    "emergency_contact": body.get('emergency_contact', '').strip() or None,
                    "notes": body.get('notes', '').strip() or None,
                    "cognito_status": "FORCE_CHANGE_PASSWORD",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                items_table.put_item(Item=new_profile)

                # Send branded welcome email with the temporary password
                try:
                    result = notify_event(
                        event_type='WELCOME_INVITE_CLIENT',
                        context={
                            "client_name": display_name,
                            "email": email,
                            "temp_password": temp_password,
                            "portal_url": os.environ.get('NOTIFICATION_PORTAL_URL', 'https://toganddogs.usmissionhero.com')
                        }
                    )
                    if not result.get('success'):
                        return error(500, f"Client profile was prepared, but the welcome email could not be sent. {result.get('message', '')}", event)
                except Exception as notify_err:
                    print(f"Warning: Branded client invite failed: {notify_err}")
                    return error(500, f"Client profile was prepared, but an unexpected error occurred while sending the email: {str(notify_err)}", event)

                return success(new_profile, event)
                
            except cognito.exceptions.UsernameExistsException:
                if body.get('mode') in ['create_or_link', 'link_existing']:
                    try:
                        cog_user = cognito.admin_get_user(UserPoolId=user_pool_id, Username=email)
                        cognito_sub = next((a['Value'] for a in cog_user.get('UserAttributes', []) if a['Name'] == 'sub'), None)
                        
                        # Ensure in 'client' group
                        try:
                            cognito.admin_add_user_to_group(UserPoolId=user_pool_id, Username=email, GroupName='client')
                        except: pass
                            
                        existing_profile = next((c for c in existing_clients if (c.get('email') or '').lower() == email or c.get('cognito_sub') == cognito_sub), None)
                        
                        if existing_profile:
                            existing_profile['cognito_sub'] = cognito_sub
                            existing_profile['cognito_status'] = cog_user.get('UserStatus')
                            existing_profile['portal_enabled'] = True
                            existing_profile['updated_at'] = datetime.utcnow().isoformat()
                            
                            # Merge fields if provided
                            for field in ['display_name', 'phone', 'address', 'emergency_contact', 'notes']:
                                if field in body: existing_profile[field] = body[field]
                            
                            items_table.put_item(Item=existing_profile)
                            return success(existing_profile, event)
                        else:
                            client_id = f"client_{str(uuid.uuid4())[:8]}"
                            new_profile = {
                                "PK": f"COMPANY#{company_id}",
                                "SK": f"CLIENT#{client_id}",
                                "company_id": company_id,
                                "client_id": client_id,
                                "display_name": display_name,
                                "email": email,
                                "cognito_sub": cognito_sub,
                                "is_active": True,
                                "portal_enabled": True,
                                "cognito_status": cog_user.get('UserStatus'),
                                "created_at": datetime.utcnow().isoformat(),
                                "updated_at": datetime.utcnow().isoformat()
                            }
                            items_table.put_item(Item=new_profile)
                            return success(new_profile, event)
                    except Exception as e:
                        return internal_error(f"Failed to link existing client: {e}", event)
                return error(409, "Cognito user already exists. Use Link Existing User instead.", event)
            except Exception as e:
                return internal_error(str(e), event)


        # POST /admin/staff/{id}/link-cognito & /admin/clients/{id}/link-cognito
        if http_method == 'POST' and '/link-cognito' in path:
            role = get_effective_role(event)
            if role not in ['owner', 'admin']:
                return error(403, "Forbidden", event)
                
            try:
                body = json.loads(event.get('body', '{}'))
            except Exception:
                return bad_request("Invalid JSON body", event)
                
            username = body.get('username', '').strip()
            if not username:
                return bad_request("username is required", event)
                
            is_client_path = '/admin/clients/' in path
            user_id = path_params.get('client_id' if is_client_path else 'staff_id')
            if not user_id:
                user_id = path.split('/')[-2]
                
            prefix = 'CLIENT' if is_client_path else 'STAFF'
            sk = f"{prefix}#{user_id}"
            
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            from common.db import table as items_table
            
            resp = items_table.get_item(Key={"PK": f"COMPANY#{company_id}", "SK": sk})
            user_profile = resp.get('Item')
            if not user_profile:
                return not_found(f"Profile {user_id} not found", event)
                
            import boto3
            cognito = boto3.client('cognito-idp')
            user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
            
            try:
                cog_user = cognito.admin_get_user(UserPoolId=user_pool_id, Username=username)
                cognito_sub = next((a['Value'] for a in cog_user.get('UserAttributes', []) if a['Name'] == 'sub'), None)
                
                # Release 6H: link-cognito guardrails
                cog_email = next((a['Value'] for a in cog_user.get('UserAttributes', []) if a['Name'] == 'email'), None)
                if is_protected_email(username) or is_protected_email(cog_email) or is_protected_sub(cognito_sub):
                    if not is_protected_profile(user_profile):
                        return error(403, "Cannot link a protected admin account to a non-protected profile.", event)
                
                # Ensure correct group
                target_group = 'client' if is_client_path else (user_profile.get('role') or 'Staff')
                if target_group.lower() == 'owner': target_group = 'owner'
                elif target_group.lower() == 'admin': target_group = 'Admin'
                elif target_group.lower() == 'staff': target_group = 'Staff'
                
                try:
                    cognito.admin_add_user_to_group(UserPoolId=user_pool_id, Username=username, GroupName=target_group)
                except: pass
                
                user_profile['cognito_sub'] = cognito_sub
                user_profile['cognito_status'] = cog_user.get('UserStatus')
                if is_client_path: user_profile['portal_enabled'] = True
                user_profile['updated_at'] = datetime.utcnow().isoformat()
                
                items_table.put_item(Item=user_profile)
                return success(user_profile, event)
            except Exception as e:
                return internal_error(f"Failed to link Cognito user: {e}", event)

                
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            from common.db import table as items_table
            
            resp = items_table.get_item(Key={"PK": f"COMPANY#{company_id}", "SK": f"STAFF#{staff_id}"})

            staff_profile = resp.get('Item')
            if not staff_profile:
                return not_found(f"Staff profile {staff_id} not found", event)
                
            import boto3
            cognito = boto3.client('cognito-idp')
            user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
            
            try:
                cog_user = cognito.admin_get_user(
                    UserPoolId=user_pool_id,
                    Username=username
                )
                
                cognito_sub = None
                email = None
                for attr in cog_user.get('UserAttributes', []):
                    if attr.get('Name') == 'sub':
                        cognito_sub = attr.get('Value')
                    if attr.get('Name') == 'email':
                        email = attr.get('Value')
                        
                # Verify no duplicate active cognito_sub
                from boto3.dynamodb.conditions import Key
                chk_resp = items_table.query(
                    KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("STAFF#")
                )
                for s in chk_resp.get('Items', []):
                    if s.get('cognito_sub') == cognito_sub and s.get('is_active') == True and s.get('staff_id') != staff_id:
                        return error(409, "Cognito user already linked to another active staff profile in this company", event)
                
                # Assign to proper Cognito group
                role_input = staff_profile.get('role', 'Staff')
                cognito_group = 'Staff'
                if role_input.lower() == 'owner':
                    cognito_group = 'owner'
                elif role_input.lower() == 'admin':
                    cognito_group = 'Admin'
                    
                try:
                    cognito.admin_add_user_to_group(
                        UserPoolId=user_pool_id,
                        Username=username,
                        GroupName=cognito_group
                    )
                except Exception as group_err:
                    print(f"Warn: Add to group failed during manual link: {group_err}")

                # Update profile with link AND any provided form values
                staff_profile['cognito_sub'] = cognito_sub
                if email:
                    staff_profile['email'] = email
                staff_profile['cognito_status'] = cog_user.get('UserStatus')
                staff_profile['updated_at'] = datetime.utcnow().isoformat()
                
                # Apply other form values if present
                if 'display_name' in body: staff_profile['display_name'] = body['display_name']
                if 'role' in body: staff_profile['role'] = body['role']
                if 'phone' in body: staff_profile['phone'] = body['phone']
                if 'is_assignable' in body: staff_profile['is_assignable'] = body['is_assignable']
                
                items_table.put_item(Item=staff_profile)
                return success(staff_profile, event)
                
            except cognito.exceptions.UserNotFoundException:
                return not_found(f"Cognito user {username} not found", event)
            except Exception as e:
                print(f"Cognito link error: {e}")
                return internal_error(str(e), event)



        if http_method in ['PATCH', 'DELETE'] and '/admin/staff' in path:

            role = get_effective_role(event)
            if role not in ['owner', 'admin']:
                return error(403, "Forbidden", event)
                
            staff_id = path_params.get('staff_id')
            if not staff_id:
                staff_id = path.split('/')[-1]
                
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            from common.db import table as items_table
            from boto3.dynamodb.conditions import Key
            
            resp = items_table.get_item(Key={"PK": f"COMPANY#{company_id}", "SK": f"STAFF#{staff_id}"})

            staff_profile = resp.get('Item')
            if not staff_profile:
                if staff_id.startswith('cognito_'):
                    username = staff_id.replace('cognito_', '')
                    import boto3
                    cog_client = boto3.client('cognito-idp')
                    user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
                    try:
                        cog_u = cog_client.admin_get_user(UserPoolId=user_pool_id, Username=username)
                        cu_email = next((a['Value'] for a in cog_u['UserAttributes'] if a['Name'] == 'email'), '').lower()
                        cu_sub = next((a['Value'] for a in cog_u['UserAttributes'] if a['Name'] == 'sub'), '')
                        
                        staff_profile = {
                            "PK": f"COMPANY#{company_id}",
                            "SK": f"STAFF#{staff_id}",
                            "company_id": company_id,
                            "staff_id": staff_id,
                            "display_name": username,
                            "role": 'Staff',
                            "email": cu_email,
                            "cognito_sub": cu_sub,
                            "is_active": cog_u.get('Enabled', True),
                            "is_assignable": False,
                            "assignment_color": 'var(--staff-ryan)',
                            "created_at": datetime.utcnow().isoformat(),
                            "updated_at": datetime.utcnow().isoformat()
                        }
                    except cog_client.exceptions.UserNotFoundException:
                        return not_found(f"Staff profile {staff_id} and Cognito user not found", event)
                    except Exception as e:
                        return internal_error(f"Error resolving virtual user: {e}", event)
                else:
                    return not_found(f"Staff profile {staff_id} not found", event)
                
            # --- PROTECTED ACCOUNT GUARDRAILS ---
            claims = get_claims(event)
            current_user_sub = claims.get('sub')
            current_user_email = (claims.get('email') or '').lower().strip()
            
            is_protected = is_protected_profile(staff_profile)
            is_self = (staff_profile.get('cognito_sub') == current_user_sub) or \
                      (staff_profile.get('email') and staff_profile.get('email').lower().strip() == current_user_email)

            if http_method == 'DELETE':

                body = {}
                try:
                    if event.get('body'):
                        body = json.loads(event.get('body'))
                except Exception:
                    pass
                    
                if is_protected or is_self:
                    log_action(event, "BLOCKED_PROTECTED_ACCOUNT_ACTION", f"COMPANY#{company_id}", f"STAFF#{staff_id}", 
                               metadata={"reason": "Cannot delete protected or self account", "staff_id": staff_id})
                    return error(403, "Action blocked: This is a protected platform account or your own account.", event)

                staff_profile['is_active'] = False
                staff_profile['is_assignable'] = False

                staff_profile['updated_at'] = datetime.utcnow().isoformat()
                
                if body.get('disable_cognito') == True and (staff_profile.get('cognito_sub') or staff_profile.get('email')):
                    import boto3
                    cognito = boto3.client('cognito-idp')
                    user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
                    username = staff_profile.get('email') or staff_profile.get('cognito_sub')
                    try:
                        cognito.admin_disable_user(UserPoolId=user_pool_id, Username=username)
                    except Exception as e:
                        print(f"Failed to disable Cognito user {username}: {e}")
                        
                items_table.put_item(Item=staff_profile)
                return success(staff_profile, event)

                
            if http_method == 'PATCH':
                try:
                    body = json.loads(event.get('body', '{}'))
                except Exception:
                    return bad_request("Invalid JSON body", event)
                    
                # Release 6H: Prevent promotion hijacking under PATCH
                if 'email' in body:
                    new_email = body['email'].strip().lower()
                    if is_protected_email(new_email) and not is_protected:
                        return error(403, "Cannot assign a protected admin email to a non-protected profile.", event)
                if 'cognito_sub' in body:
                    new_sub = body['cognito_sub'].strip()
                    if is_protected_sub(new_sub) and not is_protected:
                        return error(403, "Cannot assign a protected admin sub to a non-protected profile.", event)
                    
                action = body.get('action')
                if action:
                    import boto3
                    cognito = boto3.client('cognito-idp')
                    user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
                    username = staff_profile.get('email') or staff_profile.get('cognito_username') or staff_id.replace('cognito_', '')
                    
                    if action in ['disable', 'unlink', 'delete_profile', 'delete_cognito']:
                        if is_protected or is_self:
                            log_action(event, "BLOCKED_PROTECTED_ACCOUNT_ACTION", f"COMPANY#{company_id}", f"STAFF#{staff_id}", 
                                       metadata={"action": action, "reason": "Protected/self account protection", "staff_id": staff_id})
                            return error(403, f"Action '{action}' blocked: This is a protected platform account or your own account.", event)

                    if action == 'disable':

                        staff_profile['is_active'] = False
                        staff_profile['is_assignable'] = False
                        staff_profile['updated_at'] = datetime.utcnow().isoformat()
                        if staff_profile.get('cognito_sub') or staff_profile.get('email'):
                            try:
                                cognito.admin_disable_user(UserPoolId=user_pool_id, Username=username)
                            except Exception as e:
                                print(f"Cognito disable fail: {e}")
                        items_table.put_item(Item=staff_profile)
                        return success(staff_profile, event)
                        
                    elif action == 'enable':
                        staff_profile['is_active'] = True
                        staff_profile['updated_at'] = datetime.utcnow().isoformat()
                        if staff_profile.get('cognito_sub') or staff_profile.get('email'):
                            try:
                                cognito.admin_enable_user(UserPoolId=user_pool_id, Username=username)
                            except Exception as e:
                                print(f"Cognito enable fail: {e}")
                        items_table.put_item(Item=staff_profile)
                        return success(staff_profile, event)
                        
                    elif action == 'unlink':
                        staff_profile['cognito_sub'] = 'unlinked'
                        staff_profile['cognito_status'] = 'unlinked'
                        staff_profile.pop('cognito_username', None)
                        staff_profile['updated_at'] = datetime.utcnow().isoformat()
                        items_table.put_item(Item=staff_profile)
                        resp_profile = dict(staff_profile)
                        resp_profile['cognito_sub'] = None
                        return success(resp_profile, event)
                        
                    elif action == 'delete_profile':
                        if staff_profile.get('is_active') == True:
                            return error(400, "Cannot delete active profile. Disable it first.", event)
                        from boto3.dynamodb.conditions import Key
                        jobs_resp = items_table.query(
                            KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("JOB#")
                        )
                        has_upcoming = False
                        for job in jobs_resp.get('Items', []):
                            if job.get('staff_id') == staff_id and job.get('status') in ['PENDING', 'ASSIGNED', 'IN_PROGRESS']:
                                has_upcoming = True
                                break
                        if has_upcoming:
                            return error(400, "Cannot delete staff with active/upcoming assignments.", event)
                        items_table.delete_item(Key={"PK": f"COMPANY#{company_id}", "SK": f"STAFF#{staff_id}"})
                        return success({"deleted_profile": staff_id}, event)
                        
                    elif action == 'delete_cognito':
                        try:
                            cognito.admin_disable_user(UserPoolId=user_pool_id, Username=username)
                        except Exception: pass
                        try:
                            cognito.admin_delete_user(UserPoolId=user_pool_id, Username=username)
                        except Exception as e:
                            return internal_error(f"Failed to delete Cognito user: {e}", event)
                        if 'cognito_status' in staff_profile:
                            staff_profile['cognito_status'] = 'deleted'
                            staff_profile.pop('cognito_sub', None)
                            staff_profile['updated_at'] = datetime.utcnow().isoformat()
                            items_table.put_item(Item=staff_profile)
                        return success({"deleted_cognito": username}, event)

                editable_fields = [
                    'display_name', 'role', 'email', 'cognito_sub', 
                    'is_active', 'is_assignable', 'assignment_color', 'phone', 'notes'
                ]
                
                if 'display_name' in body:
                    new_display_name = body.get('display_name', '').strip()
                    if not new_display_name:
                        return bad_request("display_name is required", event)
                    if new_display_name.lower() == 'unassigned':
                        return bad_request("Unassigned is a reserved system option", event)
                        
                    resp_all = items_table.query(
                        KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("STAFF#")
                    )
                    for s in resp_all.get('Items', []):
                        if s['SK'] != f"STAFF#{staff_id}" and (s.get('display_name') or '').lower() == new_display_name.lower() and s.get('is_active') == True:
                            return error(409, f"Active staff with display_name {new_display_name} already exists", event)

                    
                    staff_profile['display_name'] = new_display_name
                    
                for field in editable_fields:
                    if field != 'display_name' and field in body:
                        # Guardrail: Prevent changing email/sub for protected accounts
                        if is_protected and field in ['email', 'cognito_sub', 'role']:
                            continue
                        staff_profile[field] = body[field]

                        
                if body.get('disable_cognito') == True and (staff_profile.get('cognito_sub') or staff_profile.get('email')):
                    import boto3
                    cognito = boto3.client('cognito-idp')
                    user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
                    username = staff_profile.get('email') or staff_profile.get('cognito_sub')
                    try:
                        cognito.admin_disable_user(UserPoolId=user_pool_id, Username=username)
                    except Exception as e:
                        print(f"Failed to disable Cognito user {username}: {e}")
                        
                staff_profile['updated_at'] = datetime.utcnow().isoformat()
                items_table.put_item(Item=staff_profile)
                
                # Best-effort Cognito Sync
                warnings = []
                if staff_profile.get('cognito_sub') or staff_profile.get('email'):
                    import boto3
                    import re
                    cognito = boto3.client('cognito-idp')
                    user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
                    username = staff_profile.get('email') or staff_profile.get('cognito_sub')
                    
                    attributes_to_sync = []
                    if 'display_name' in body:
                        attributes_to_sync.append({'Name': 'name', 'Value': body['display_name']})
                    
                    if 'phone' in body:
                        phone = body['phone'].strip()
                        # Release 6E: Normalize phone to E.164 before Cognito sync
                        normalized = normalize_phone_e164(phone)
                        if normalized:
                            attributes_to_sync.append({'Name': 'phone_number', 'Value': normalized})
                        elif phone:
                            warnings.append(f"Cognito phone sync skipped: '{phone}' could not be normalized to E.164 format (+1...)")
                            
                    if attributes_to_sync:
                        try:
                            cognito.admin_update_user_attributes(
                                UserPoolId=user_pool_id,
                                Username=username,
                                UserAttributes=attributes_to_sync
                            )
                        except Exception as cog_err:
                            print(f"Cognito attribute sync failed: {cog_err}")
                            warnings.append(f"Cognito sync failed: {str(cog_err)}")

                resp_body = staff_profile
                if warnings:
                    resp_body['_warnings'] = warnings
                    
                return success(resp_body, event)



        # --- Account Security Routes (Generalized) ---
        if http_method == 'POST' and ('/reset-password' in path or '/set-temp-password' in path or '/resend-invite' in path):
            role = get_effective_role(event)
            if role not in ['owner', 'admin']:
                return error(403, "Forbidden", event)
                
            is_client_path = '/admin/clients/' in path
            user_id = path_params.get('client_id' if is_client_path else 'staff_id')
            if not user_id:
                user_id = path.split('/')[-2]
                
            prefix = 'CLIENT' if is_client_path else 'STAFF'
            sk = f"{prefix}#{user_id}"
                
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            from common.db import table as items_table
            
            resp = items_table.get_item(Key={"PK": f"COMPANY#{company_id}", "SK": sk})
            user_profile = resp.get('Item')
            
            # Fallback for virtual users (Cognito only)
            if not user_profile and user_id.startswith('cognito_'):
                username = user_id.replace('cognito_', '')
                user_profile = {
                    "display_name": username,
                    "email": username, # Default to username, will be refined if needed
                    "is_virtual": True
                }
            elif not user_profile:
                return not_found(f"Profile {user_id} not found", event)
                
            import boto3
            cognito = boto3.client('cognito-idp')
            user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
            
            # Resolve actual email/username for security actions
            cognito_user_id = None
            if not user_profile.get('is_virtual'):
                cognito_sub = user_profile.get('cognito_sub')
                cognito_username = user_profile.get('cognito_username')
                email = user_profile.get('email')
                
                # Check for explicit 'unlinked' sentinel
                if cognito_sub == 'unlinked' or user_profile.get('cognito_status') == 'unlinked':
                    return bad_request("Profile is not linked to a Cognito user", event)
                
                cognito_user_id = cognito_sub or cognito_username or email
            else:
                cognito_user_id = user_profile['display_name']
                
            if not cognito_user_id or cognito_user_id == 'unlinked':
                return bad_request("Profile is not linked to a Cognito user", event)

            resolved_username = None
            try:
                cog_resp = cognito.admin_get_user(UserPoolId=user_pool_id, Username=cognito_user_id)
                resolved_username = cog_resp.get('Username')
                if user_profile.get('is_virtual'):
                    for attr in cog_resp.get('UserAttributes', []):
                        if attr['Name'] == 'email':
                            user_profile['email'] = attr['Value']
                        if attr['Name'] == 'name' or attr['Name'] == 'nickname':
                            user_profile['display_name'] = attr['Value']
            except cognito.exceptions.UserNotFoundException:
                # Fallback to search by email attribute if available
                email_val = user_profile.get('email')
                if email_val:
                    try:
                        list_resp = cognito.list_users(
                            UserPoolId=user_pool_id,
                            Filter=f'email = "{email_val}"'
                        )
                        users = list_resp.get('Users', [])
                        if users:
                            resolved_username = users[0].get('Username')
                    except Exception as list_err:
                        print(f"Cognito list_users filter error: {list_err}")
                
                if not resolved_username:
                    return bad_request("Cognito user not found", event)
            except Exception as e:
                print(f"Cognito admin_get_user error: {e}")
                # Fallback to search by email attribute if available
                email_val = user_profile.get('email')
                if email_val:
                    try:
                        list_resp = cognito.list_users(
                            UserPoolId=user_pool_id,
                            Filter=f'email = "{email_val}"'
                        )
                        users = list_resp.get('Users', [])
                        if users:
                            resolved_username = users[0].get('Username')
                    except Exception as list_err:
                        pass
                if not resolved_username:
                    return internal_error(f"Failed to retrieve Cognito user: {str(e)}", event)

            username = resolved_username
            
            try:
                if '/reset-password' in path:
                    cognito.admin_reset_user_password(UserPoolId=user_pool_id, Username=username)
                    return success({"message": "Password reset triggered. User will receive an email."}, event)
                    
                elif '/set-temp-password' in path:
                    try:
                        body = json.loads(event.get('body', '{}'))
                    except: body = {}
                    temp_password = body.get('password')
                    if not temp_password: return bad_request("password is required", event)
                    cognito.admin_set_user_password(UserPoolId=user_pool_id, Username=username, Password=temp_password, Permanent=False)
                    return success({"message": "Temporary password set successfully."}, event)

                elif '/resend-invite' in path:
                    # Generate a new secure temporary password for the resend
                    temp_password = generate_temp_password()
                    
                    # Reset the user's password to the new temporary one (this does not send an email)
                    try:
                        cognito.admin_set_user_password(
                            UserPoolId=user_pool_id,
                            Username=username,
                            Password=temp_password,
                            Permanent=False
                        )
                    except Exception as e:
                        print(f"Resend password reset failed: {e}")
                        return internal_error(f"Could not reset temporary password: {str(e)}", event)

                    # Send ONE branded welcome email containing the new temporary password
                    try:
                        is_client_path = '/admin/clients/' in path
                        event_type = 'WELCOME_INVITE_CLIENT' if is_client_path else 'WELCOME_INVITE_STAFF'
                        result = notify_event(
                            event_type=event_type,
                            context={
                                "client_name": user_profile.get('display_name') if is_client_path else None,
                                "staff_name": user_profile.get('display_name') if not is_client_path else None,
                                "email": username,
                                "temp_password": temp_password,
                                "portal_url": os.environ.get('NOTIFICATION_PORTAL_URL', 'https://toganddogs.usmissionhero.com')
                            }
                        )
                        if not result.get('success'):
                            return error(500, f"Invite was prepared, but the email could not be sent. Please check notification delivery logs or recipient suppression status. Error: {result.get('message', '')}", event)
                    except Exception as notify_err:
                        print(f"Warning: Failed to send branded resend email: {notify_err}")
                        return error(500, f"Invite was prepared, but an unexpected error occurred while sending the email: {str(notify_err)}", event)

                    return success({"message": "Invitation resent successfully with new temporary password."}, event)
                    
            except Exception as e:
                print(f"Cognito security action error: {e}")
                return internal_error(str(e), event)


        if path == '/admin/clients' or path.endswith('/admin/clients'):
            role = get_effective_role(event)
            # GET /admin/clients
            if http_method == 'GET':
                if role not in ['owner', 'admin']:
                    return error(403, "Forbidden", event)
                
                from common.auth import get_current_company_id
                company_id = get_current_company_id(event)
                from common.db import table as items_table
                from boto3.dynamodb.conditions import Key
                
                from boto3.dynamodb.conditions import Key
                response = items_table.query(
                    KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("CLIENT#")
                )
                client_profiles = response.get('Items', [])
                
                # Fetch Cognito users for clients
                import boto3
                cognito_client = boto3.client('cognito-idp')
                user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
                
                cognito_clients = []
                # Get groups matching client or company-scoped client group
                groups_resp = cognito_client.list_groups(UserPoolId=user_pool_id)
                target_groups = []
                for g in groups_resp.get('Groups', []):
                    g_name = g['GroupName']
                    g_lower = g_name.lower()
                    if 'client' in g_lower:
                        target_groups.append(g_name)
                
                # Fetch users
                seen_usernames = set()
                for grp in target_groups:
                    u_resp = cognito_client.list_users_in_group(UserPoolId=user_pool_id, GroupName=grp)
                    for u in u_resp.get('Users', []):
                        if u['Username'] not in seen_usernames:
                            mode = os.environ.get("TENANT_RESOLUTION_MODE", "single").lower().strip()
                            if is_cognito_user_in_company(u, company_id, mode):
                                seen_usernames.add(u['Username'])
                                cognito_clients.append(u)

                # Merge
                merged_clients = []
                matched_subs = set()
                matched_emails = set()
                
                # 1. DynamoDB Clients
                for c in client_profiles:
                    c_email = (c.get('email') or '').lower()
                    c_sub = c.get('cognito_sub')
                    
                    if c_sub == 'unlinked':
                        c['cognito_sub'] = None
                        c['cognito_status'] = 'unlinked'
                        c['portal_enabled'] = False
                        merged_clients.append(c)
                        # Find and mark Cognito user as matched by email to prevent virtual user duplication
                        for cu in cognito_clients:
                            cu_email = next((a['Value'] for a in cu['Attributes'] if a['Name'] == 'email'), '').lower()
                            cu_sub = next((a['Value'] for a in cu['Attributes'] if a['Name'] == 'sub'), '')
                            if c_email and c_email == cu_email:
                                if cu_sub: matched_subs.add(cu_sub)
                                if cu_email: matched_emails.add(cu_email)
                                break
                        continue
                        
                    cog_match = None
                    for cu in cognito_clients:
                        cu_email = next((a['Value'] for a in cu['Attributes'] if a['Name'] == 'email'), '').lower()
                        cu_sub = next((a['Value'] for a in cu['Attributes'] if a['Name'] == 'sub'), '')
                        if (c_sub and c_sub == cu_sub) or (c_email and c_email == cu_email):
                            cog_match = cu
                            if cu_sub: matched_subs.add(cu_sub)
                            if cu_email: matched_emails.add(cu_email)
                            break
                            
                    if cog_match:
                        c['cognito_status'] = cog_match.get('UserStatus')
                        c['cognito_username'] = cog_match.get('Username')
                        c['portal_enabled'] = True
                        if not c.get('cognito_sub'):
                            c['cognito_sub'] = next((a['Value'] for a in cog_match['Attributes'] if a['Name'] == 'sub'), None)
                    merged_clients.append(c)
                    
                # 2. Cognito-only Clients
                for cu in cognito_clients:
                    cu_email = next((a['Value'] for a in cu['Attributes'] if a['Name'] == 'email'), '').lower()
                    cu_sub = next((a['Value'] for a in cu['Attributes'] if a['Name'] == 'sub'), '')
                    
                    if cu_sub in matched_subs or cu_email in matched_emails:
                        continue
                        
                    virtual_id = f"cognito_{cu['Username']}"
                    v_client = {
                        "PK": f"COMPANY#{company_id}",
                        "SK": f"CLIENT#{virtual_id}",
                        "company_id": company_id,
                        "client_id": virtual_id,
                        "display_name": cu['Username'],
                        "email": cu_email,
                        "cognito_sub": cu_sub,
                        "is_active": cu.get('Enabled', True),
                        "portal_enabled": True,
                        "cognito_status": cu.get('UserStatus'),
                        "is_virtual": True
                    }
                    merged_clients.append(v_client)
                    
                return success({"clients": merged_clients}, event)

            # POST /admin/clients
            if http_method == 'POST':
                if role not in ['owner', 'admin']:
                    return error(403, "Forbidden", event)
                
                try:
                    body = json.loads(event.get('body', '{}'))
                except Exception:
                    return bad_request("Invalid JSON body", event)
                    
                display_name = body.get('display_name', '').strip()
                email = body.get('email', '').strip().lower()
                
                if not display_name:
                    return bad_request("display_name is required", event)
                    
                from common.auth import get_current_company_id
                company_id = get_current_company_id(event)
                from common.db import table as items_table
                
                if email:
                    from boto3.dynamodb.conditions import Key
                    
                    # Check duplicate active email within company_id
                    resp = items_table.query(
                        KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("CLIENT#")
                    )
                    existing_clients = resp.get('Items', [])
                    for c in existing_clients:
                        if (c.get('email') or '').lower() == email and c.get('is_active') == True:
                            return error(409, f"Active client with email {email} already exists", event)
                            
                    # Release 6H: Block client creation with protected admin email
                    if is_protected_email(email):
                        return error(403, "Cannot create a standard profile using a protected account identity.", event)

                # Entitlement Check
                try:
                    from common.entitlement import check_limit, get_active_client_count
                    current_count = get_active_client_count(company_id)
                    check_limit(company_id, 'max_active_clients', current_count, context=event)
                except EntitlementDenied as ed:
                    return error(403, str(ed), event)
                        
                client_id = f"client_{str(uuid.uuid4())[:8]}"
                
                new_profile = {
                    "PK": f"COMPANY#{company_id}",
                    "SK": f"CLIENT#{client_id}",
                    "company_id": company_id,
                    "client_id": client_id,
                    "email": email or None,
                    "display_name": display_name,
                    "phone": body.get('phone', '').strip(),
                    "address": body.get('address', '').strip(),
                    "emergency_contact": body.get('emergency_contact', '').strip(),
                    "notes": body.get('notes', '').strip(),
                    "portal_enabled": False,
                    "is_active": True,
                    "cognito_status": "not_linked",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                items_table.put_item(Item=new_profile)
                return success(new_profile, event)

        # PATCH /admin/clients/{client_id} & /disable
        if '/admin/clients/' in path:
            role = get_effective_role(event)
            if role not in ['owner', 'admin']:
                return error(403, "Forbidden", event)
                
            client_id = path_params.get('client_id')
            if not client_id:
                client_id = path.split('/')[-1]
                if client_id == 'disable':
                    client_id = path.split('/')[-2]
                    
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            from common.db import table as items_table
            
            resp = items_table.get_item(Key={"PK": f"COMPANY#{company_id}", "SK": f"CLIENT#{client_id}"})
            client_profile = resp.get('Item')
            if not client_profile:
                if client_id.startswith('cognito_'):
                    username = client_id.replace('cognito_', '')
                    import boto3
                    cog_client = boto3.client('cognito-idp')
                    user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
                    try:
                        cog_u = cog_client.admin_get_user(UserPoolId=user_pool_id, Username=username)
                        cu_email = next((a['Value'] for a in cog_u['UserAttributes'] if a['Name'] == 'email'), '').lower()
                        cu_sub = next((a['Value'] for a in cog_u['UserAttributes'] if a['Name'] == 'sub'), '')
                        
                        client_profile = {
                            "PK": f"COMPANY#{company_id}",
                            "SK": f"CLIENT#{client_id}",
                            "company_id": company_id,
                            "client_id": client_id,
                            "display_name": username,
                            "email": cu_email,
                            "cognito_sub": cu_sub,
                            "is_active": cog_u.get('Enabled', True),
                            "portal_enabled": True,
                            "created_at": datetime.utcnow().isoformat(),
                            "updated_at": datetime.utcnow().isoformat()
                        }
                    except cog_client.exceptions.UserNotFoundException:
                        return not_found(f"Client profile {client_id} and Cognito user not found", event)
                    except Exception as e:
                        return internal_error(f"Error resolving virtual user: {e}", event)
                else:
                    return not_found(f"Client profile {client_id} not found", event)
                
            if http_method == 'POST' and path.endswith('/disable'):
                client_profile['is_active'] = False
                client_profile['portal_enabled'] = False
                client_profile['updated_at'] = datetime.utcnow().isoformat()
                items_table.put_item(Item=client_profile)
                return success(client_profile, event)
                
            if http_method == 'PATCH':
                try:
                    body = json.loads(event.get('body', '{}'))
                except Exception:
                    return bad_request("Invalid JSON body", event)
                    
                action = body.get('action')
                if action:
                    import boto3
                    cognito = boto3.client('cognito-idp')
                    user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
                    username = client_profile.get('email') or client_profile.get('cognito_username') or client_id.replace('cognito_', '')
                    
                    if action == 'disable':
                        client_profile['is_active'] = False
                        client_profile['portal_enabled'] = False
                        client_profile['updated_at'] = datetime.utcnow().isoformat()
                        if client_profile.get('cognito_sub') or client_profile.get('email'):
                            try:
                                cognito.admin_disable_user(UserPoolId=user_pool_id, Username=username)
                            except Exception as e:
                                print(f"Cognito client disable fail: {e}")
                        items_table.put_item(Item=client_profile)
                        return success(client_profile, event)
                        
                    elif action == 'enable':
                        client_profile['is_active'] = True
                        client_profile['portal_enabled'] = True
                        client_profile['updated_at'] = datetime.utcnow().isoformat()
                        if client_profile.get('cognito_sub') or client_profile.get('email'):
                            try:
                                cognito.admin_enable_user(UserPoolId=user_pool_id, Username=username)
                            except Exception as e:
                                print(f"Cognito client enable fail: {e}")
                        items_table.put_item(Item=client_profile)
                        return success(client_profile, event)
                        
                    elif action == 'unlink':
                        client_profile['cognito_sub'] = 'unlinked'
                        client_profile['cognito_status'] = 'unlinked'
                        client_profile.pop('cognito_username', None)
                        client_profile['portal_enabled'] = False
                        client_profile['updated_at'] = datetime.utcnow().isoformat()
                        items_table.put_item(Item=client_profile)
                        resp_profile = dict(client_profile)
                        resp_profile['cognito_sub'] = None
                        return success(resp_profile, event)
                        
                    elif action == 'delete_profile':
                        if client_profile.get('is_active') == True:
                            return error(400, "Cannot delete active profile. Disable it first.", event)
                        from boto3.dynamodb.conditions import Key
                        req_resp = items_table.query(
                            KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("REQ#")
                        )
                        has_active = False
                        for r in req_resp.get('Items', []):
                            if r.get('client_id') == client_id and r.get('status') not in ['CANCELLED', 'REJECTED']:
                                has_active = True
                                break
                        if has_active:
                            return error(400, "Cannot delete client with active/unresolved request workflows.", event)
                        items_table.delete_item(Key={"PK": f"COMPANY#{company_id}", "SK": f"CLIENT#{client_id}"})
                        return success({"deleted_profile": client_id}, event)
                        
                    elif action == 'delete_cognito':
                        try:
                            cognito.admin_disable_user(UserPoolId=user_pool_id, Username=username)
                        except Exception: pass
                        try:
                            cognito.admin_delete_user(UserPoolId=user_pool_id, Username=username)
                        except Exception as e:
                            return internal_error(f"Failed to delete client Cognito user: {e}", event)
                        if 'cognito_status' in client_profile:
                            client_profile['cognito_status'] = 'deleted'
                            client_profile.pop('cognito_sub', None)
                            client_profile['portal_enabled'] = False
                            client_profile['updated_at'] = datetime.utcnow().isoformat()
                            items_table.put_item(Item=client_profile)
                        return success({"deleted_cognito": username}, event)

                editable_fields = ['display_name', 'email', 'phone', 'address', 'emergency_contact', 'notes', 'is_active']
                
                if 'email' in body:
                    new_email = body.get('email', '').strip().lower()
                    has_cognito = bool(client_profile.get('cognito_sub') or client_profile.get('cognito_status') == 'onboard')
                    if not new_email:
                        if has_cognito:
                            return bad_request("email cannot be blank for active login accounts", event)
                        client_profile['email'] = None
                    else:
                        # Release 6H: Prevent client promotion hijacking
                        if is_protected_email(new_email):
                            return error(403, "Cannot assign a protected admin email to a standard profile.", event)
                        if new_email != client_profile.get('email'):
                            from boto3.dynamodb.conditions import Key
                            resp_all = items_table.query(
                                KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("CLIENT#")
                            )
                            for c in resp_all.get('Items', []):
                                if c['SK'] != f"CLIENT#{client_id}" and (c.get('email') or '').lower() == new_email and c.get('is_active') == True:
                                    return error(409, f"Active client with email {new_email} already exists", event)
                            client_profile['email'] = new_email
                        
                if 'display_name' in body:
                    new_name = body.get('display_name', '').strip()
                    if not new_name:
                        return bad_request("display_name cannot be blank", event)
                    client_profile['display_name'] = new_name
                    
                for field in editable_fields:
                    if field not in ['email', 'display_name'] and field in body:
                        client_profile[field] = body[field]
                        
                client_profile['updated_at'] = datetime.utcnow().isoformat()
                items_table.put_item(Item=client_profile)

                # Best-effort Cognito Sync
                if client_profile.get('cognito_sub') or client_profile.get('email'):
                    import boto3
                    import re
                    cognito = boto3.client('cognito-idp')
                    user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
                    username = client_profile.get('email') or client_profile.get('cognito_sub')
                    
                    attributes_to_sync = []
                    if 'display_name' in body:
                        attributes_to_sync.append({'Name': 'name', 'Value': body['display_name']})
                    
                    if 'phone' in body:
                        phone = body['phone'].strip()
                        # Release 6E: Normalize phone to E.164 before Cognito sync
                        normalized = normalize_phone_e164(phone)
                        if normalized:
                            attributes_to_sync.append({'Name': 'phone_number', 'Value': normalized})
                            
                    if attributes_to_sync:
                        try:
                            cognito.admin_update_user_attributes(
                                UserPoolId=user_pool_id,
                                Username=username,
                                UserAttributes=attributes_to_sync
                            )
                        except Exception as cog_err:
                            print(f"Cognito client attribute sync failed: {cog_err}")

                return success(client_profile, event)


        if http_method == 'GET':


            request_id = path_params.get('requestId')

            client_id = query_params.get('clientId')
            
            if request_id and client_id:
                item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
                if item:
                    # Release 11E: Post-read tenant ownership validation
                    from common.auth import validate_tenant_ownership, get_claims as _gc
                    try:
                        validate_tenant_ownership(item, event)
                    except PermissionError:
                        _c = _gc(event)
                        print(f"SECURITY: Cross-tenant GET attempt by {_c.get('email')} for REQ#{request_id}")
                        return error(403, "Forbidden", event)

                    if item.get('job_ids'):
                        jobs_summary = []
                        completed_count = 0
                        pending_count = 0
                        total_count = len(item.get('job_ids'))
                        
                        for jid in item.get('job_ids'):
                            job_record = get_item(f"JOB#{jid}", f"REQ#{request_id}")
                            if job_record:
                                status = job_record.get('status', 'JOB_CREATED')
                                if status == 'COMPLETED':
                                    completed_count += 1
                                else:
                                    pending_count += 1
                                    
                                jobs_summary.append({
                                    'job_id': jid,
                                    'occurrence_date': job_record.get('occurrence_date') or job_record.get('scheduled_date') or job_record.get('start_date'),
                                    'occurrence_index': job_record.get('occurrence_index'),
                                    'status': status,
                                    'worker_id': job_record.get('worker_id'),
                                    'worker_name': job_record.get('worker_name'),
                                    'completed_at': job_record.get('completed_at'),
                                    'completed_by': job_record.get('completed_by'),
                                    'visit_notes': job_record.get('visit_notes')
                                })
                        
                        # Sort jobs by date and occurrence index
                        jobs_summary.sort(key=lambda x: (x.get('occurrence_date') or '', x.get('occurrence_index') or 0))
                        
                        item['job_completion_summary'] = {
                            'total': total_count,
                            'completed': completed_count,
                            'pending': pending_count,
                            'jobs': jobs_summary
                        }
                    
                    role = get_effective_role(event)
                    item = sanitize_booking_for_role(item, role)
                    return success(item, event)
                return not_found(f"Request {request_id} not found", event)

            
            # List with Pagination & Filters
            status = query_params.get('status', 'PENDING_REVIEW')
            limit = int(query_params.get('limit', 20))
            last_key = query_params.get('startKey') # JSON string
            timeframe = query_params.get('timeframe') # DAILY, WEEKLY, etc.
            
            from common.db import table as items_table, Key
            
            # SPECIAL CASE: ALL (Scan fallback for scheduler & Client Portal)
            if status == 'ALL':
                role = get_effective_role(event)
                if role not in ['owner', 'admin', 'staff', 'client']:
                    return error(403, "Forbidden", event)
                    
                claims = get_claims(event)
                user_email = (claims.get('email') or "").lower().strip()

                is_admin = role in ['owner', 'admin', 'staff']


                scan_kwargs = {"Limit": 1000}
                
                # Filter logic: 
                # 1. Clients only see their own records
                # 2. Admins see 'All Active' (excludes DELETED and ARCHIVED) by default in this view
                # 3. EXCLUSION: Only include records that look like requests or jobs (REQ# or JOB#)
                #    to prevent system metadata (COMPANY#) or audit logs (AUDIT#) from polluting the list.
                filter_expressions = []
                expression_values = {}
                expression_names = {"#stat": "status"}

                from common.auth import get_current_company_id
                company_id = get_current_company_id(event)
                
                # Scope to company or shared/orphaned records
                filter_expressions.append("(company_id = :cid OR attribute_not_exists(company_id))")
                expression_values[":cid"] = company_id

                # Identity Scoping
                if role == 'staff' and user_email:
                    # Staff only see jobs assigned to them
                    filter_expressions.append("worker_id = :wid")
                    expression_values[":wid"] = user_email
                elif not is_admin and user_email:
                    # Clients only see their own records
                    filter_expressions.append("client_email = :email")
                    expression_values[":email"] = user_email
                
                # Terminal State Exclusion
                filter_expressions.append("#stat <> :deleted")
                filter_expressions.append("#stat <> :archived")
                expression_values[":deleted"] = 'DELETED'
                expression_values[":archived"] = 'ARCHIVED'

                # Release 1: Request List shows parent REQ# records only.
                # JOB# records are internal child records used for worker assignment and calendar sync.
                # They should not appear as separate rows in the admin request list.
                # Previously this included JOB# which caused duplicate rows for the same booking.
                filter_expressions.append("contains(PK, :req_tag)")
                expression_values[":req_tag"] = "REQ#"
                
                scan_kwargs["FilterExpression"] = " AND ".join(filter_expressions)
                scan_kwargs["ExpressionAttributeValues"] = expression_values
                scan_kwargs["ExpressionAttributeNames"] = expression_names
                
                if last_key:
                    scan_kwargs["ExclusiveStartKey"] = json.loads(last_key)
                
                response = items_table.scan(**scan_kwargs)
                items = response.get('Items', [])
                items = [sanitize_booking_for_role(item, role) for item in items]
                
                return success({
                    "requests": items,

                    "lastKey": json.dumps(response.get('LastEvaluatedKey')) if response.get('LastEvaluatedKey') else None
                }, event)

            # INDEXED QUERY: Specific Status
            role = get_effective_role(event)
            if role not in ['owner', 'admin']:
                return error(403, "Forbidden: Only owners and admins can query specific workflow statuses", event)
                
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)

            query_kwargs = {
                "IndexName": "StatusIndex",
                "KeyConditionExpression": Key('status').eq(status),
                # Release 1: Exclude JOB# records from status-specific queries.
                # Only parent REQ# records should appear in the admin request list.
                "FilterExpression": "(company_id = :cid OR attribute_not_exists(company_id)) AND contains(PK, :req_tag)",
                "ExpressionAttributeValues": {":cid": company_id, ":req_tag": "REQ#"},
                "Limit": limit,
                "ScanIndexForward": False # Newest first
            }
            
            if last_key:
                query_kwargs["ExclusiveStartKey"] = json.loads(last_key)
            
            response = items_table.query(**query_kwargs)
            items = response.get('Items', [])
            items = [sanitize_booking_for_role(item, role) for item in items]

            
            return success({
                "requests": items,

                "lastKey": json.dumps(response.get('LastEvaluatedKey')) if response.get('LastEvaluatedKey') else None
            }, event)

        elif http_method == 'POST' and '/admin/requests/' in path and path.endswith('/payment-session'):
            role = get_effective_role(event)
            if role not in ['owner', 'admin']:
                return error(403, "Forbidden", event)

            claims = get_claims(event)
            user_email = (claims.get('email') or "").lower().strip() or claims.get('username') or 'admin-api'

            # 1. Parse request_id from path
            request_id = path_params.get('request_id') or path_params.get('requestId')
            if not request_id:
                parts = [p for p in path.split('/') if p]
                if len(parts) >= 4 and parts[0] == 'admin' and parts[1] == 'requests' and parts[3] == 'payment-session':
                    request_id = parts[2]

            if not request_id:
                return bad_request("Missing request_id in path", event)

            # 2. Parse client_id and amount_cents
            client_id = query_params.get('clientId') or query_params.get('client_id')
            
            try:
                body = json.loads(event.get('body', '{}')) if event.get('body') else {}
            except Exception:
                return bad_request("Invalid JSON body", event)

            if not client_id:
                client_id = body.get('client_id')

            if not client_id:
                return bad_request("Missing required client_id (clientId query param or client_id in body)", event)

            amount_cents = body.get('amount_cents')
            try:
                amount_cents = validate_and_parse_amount_cents(amount_cents)
            except ValueError as val_err:
                return bad_request(f"amount_cents validation failed: {str(val_err)}", event)

            # 3. Retrieve request item
            request_item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
            if not request_item:
                return not_found(f"Request {request_id} not found for client {client_id}", event)

            # 4. Validate tenant ownership
            from common.auth import validate_tenant_ownership as _vto, get_claims as _gc
            try:
                _vto(request_item, event)
            except PermissionError:
                _c = _gc(event)
                print(f"SECURITY: Cross-tenant payment session attempt by {_c.get('email')} for REQ#{request_id}")
                return error(403, "Forbidden", event)

            # 4.1. Validate payment status guard and duplicate payment protection
            current_payment_status = request_item.get('payment_status')
            if current_payment_status:
                current_payment_status = current_payment_status.strip().lower()

            if current_payment_status in ['paid', 'refunded', 'waived']:
                return error(409, f"Conflict: Payment session cannot be created for request with status '{request_item.get('payment_status')}'", event)
            
            elif current_payment_status == 'payment_link_sent':
                existing_url = request_item.get('stripe_payment_url')
                existing_session_id = request_item.get('stripe_checkout_session_id')
                if existing_url and existing_session_id:
                    return success({
                        "message": "Payment session retrieved successfully",
                        "stripe_checkout_session_id": existing_session_id,
                        "stripe_payment_url": existing_url,
                        "payment_status": "payment_link_sent"
                    }, event)

            # 5. Create Stripe Checkout Session
            from common.stripe_client import create_checkout_session, StripeAPIError
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            stripe_env = os.environ.get("STRIPE_ENV") or os.environ.get("STRIPE_ENVIRONMENT") or "sandbox"

            try:
                session = create_checkout_session(
                    company_id=company_id,
                    request_id=request_id,
                    client_id=client_id,
                    amount_cents=amount_cents,
                    environment=stripe_env
                )
            except StripeAPIError as e:
                return error(500, f"Stripe session creation failed: {str(e)}", event)

            # 6. Update Request Record in DynamoDB
            now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

            try:
                table.update_item(
                    Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                    UpdateExpression=(
                        "SET payment_status = :ps, "
                        "stripe_checkout_session_id = :sid, "
                        "stripe_payment_url = :surl, "
                        "payment_requested_at = :pat, "
                        "payment_amount_cents = :pac, "
                        "payment_requested_by = :prb, "
                        "updated_at = :now"
                    ),
                    ExpressionAttributeValues={
                        ":ps": "payment_link_sent",
                        ":sid": session.get('id'),
                        ":surl": session.get('url'),
                        ":pat": now_iso,
                        ":pac": amount_cents,
                        ":prb": user_email,
                        ":now": now_iso
                    }
                )
            except Exception as db_err:
                print(f"DATABASE ERROR: Failed to update request {request_id} billing fields: {db_err}")
                return error(500, "Database update failed after Stripe session creation", event)

            # Audit log
            log_action(
                event,
                "PAYMENT_SESSION_CREATED",
                f"REQ#{request_id}",
                f"CLIENT#{client_id}",
                metadata={
                    "stripe_checkout_session_id": session.get('id'),
                    "amount_cents": amount_cents,
                    "stripe_payment_url": session.get('url')
                }
            )

            return success({
                "message": "Payment session created successfully",
                "stripe_checkout_session_id": session.get('id'),
                "stripe_payment_url": session.get('url'),
                "payment_status": "payment_link_sent"
            }, event)

        elif http_method == 'POST' and '/admin/requests/' in path and path.endswith('/send-payment-email'):
            role = get_effective_role(event)
            if role not in ['owner', 'admin']:
                return error(403, "Forbidden", event)

            claims = get_claims(event)
            user_email = (claims.get('email') or "").lower().strip() or claims.get('username') or 'admin-api'

            # 1. Parse request_id from path
            request_id = path_params.get('request_id') or path_params.get('requestId')
            if not request_id:
                parts = [p for p in path.split('/') if p]
                if len(parts) >= 4 and parts[0] == 'admin' and parts[1] == 'requests' and parts[3] == 'send-payment-email':
                    request_id = parts[2]

            if not request_id:
                return bad_request("Missing request_id in path", event)

            # 2. Parse client_id if available, but we can query it from DynamoDB
            client_id = query_params.get('clientId') or query_params.get('client_id')
            try:
                body = json.loads(event.get('body', '{}')) if event.get('body') else {}
            except Exception:
                return bad_request("Invalid JSON body", event)

            if not client_id:
                client_id = body.get('client_id')

            request_item = None
            if client_id:
                request_item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")

            if not request_item:
                from boto3.dynamodb.conditions import Key
                try:
                    response = table.query(
                        KeyConditionExpression=Key('PK').eq(f"REQ#{request_id}") & Key('SK').begins_with("CLIENT#")
                    )
                    items = response.get('Items', [])
                    if items:
                        request_item = items[0]
                        client_id = request_item.get('client_id')
                except Exception as db_err:
                    print(f"DATABASE ERROR: Failed to query request {request_id}: {db_err}")
                    return error(500, "Database query failed", event)

            # 3. Request must exist
            if not request_item:
                return not_found(f"Request {request_id} not found", event)

            # 4. Validate tenant ownership
            from common.auth import validate_tenant_ownership as _vto
            try:
                _vto(request_item, event)
            except PermissionError:
                _c = get_claims(event)
                print(f"SECURITY: Cross-tenant payment email attempt by {_c.get('email')} for REQ#{request_id}")
                return error(403, "Forbidden", event)

            # 5. Check payment status guard: block paid, refunded, waived
            current_payment_status = request_item.get('payment_status')
            if current_payment_status:
                current_payment_status = current_payment_status.strip().lower()

            if current_payment_status in ['paid', 'refunded', 'waived']:
                return error(409, f"Conflict: Payment email cannot be sent for request with status '{request_item.get('payment_status')}'", event)

            # 6. Require existing payment link / session URL and ID
            payment_url = request_item.get('stripe_payment_url')
            session_id = request_item.get('stripe_checkout_session_id')
            if not payment_url or not session_id:
                return bad_request("Request does not have an active payment link or session", event)

            # 7. Require client email present
            client_email = request_item.get('client_email')
            if not client_email:
                return bad_request("Client email is missing on request", event)

            # 8. Rate limit: Max 3 sends per hour per request
            from common.notifications.service import check_payment_email_rate_limit
            if check_payment_email_rate_limit(request_id):
                return error(429, "Too Many Requests: Rate limit exceeded. Maximum 3 payment email sends per request per hour.", event)

            # 8.5. Short cooldown guard (e.g. 60 seconds)
            last_sent_str = request_item.get('payment_email_sent_at')
            if last_sent_str:
                try:
                    if last_sent_str.endswith('Z'):
                        last_sent_str = last_sent_str[:-1] + '+00:00'
                    last_sent = datetime.fromisoformat(last_sent_str)
                    now = datetime.now(timezone.utc)
                    elapsed_seconds = (now - last_sent).total_seconds()
                    
                    cooldown_seconds = int(os.environ.get("PAYMENT_EMAIL_COOLDOWN_SECONDS", 60))
                    if elapsed_seconds < cooldown_seconds:
                        remaining = int(cooldown_seconds - elapsed_seconds)
                        return error(429, f"Too Many Requests: Please wait {remaining} more seconds before sending another payment email.", event)
                except Exception as parse_err:
                    print(f"WARNING: Failed to parse payment_email_sent_at '{last_sent_str}': {parse_err}")

            # 9. Trigger email send (mocked/stubbed if dry run / disabled)
            notify_res = notify_event('PAYMENT_LINK_EMAIL', request_item)
            if not notify_res.get('success'):
                # Safe error handling if the send failed
                return error(500, f"Notification delivery failed: {notify_res.get('message', 'Unknown error')}", event)

            # 10. Update Request record only after successful send
            now_iso = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
            try:
                table.update_item(
                    Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                    UpdateExpression=(
                        "SET payment_email_sent_at = :pat, "
                        "payment_email_last_recipient = :plr, "
                        "payment_email_send_count = if_not_exists(payment_email_send_count, :zero) + :inc, "
                        "updated_at = :now"
                    ),
                    ExpressionAttributeValues={
                        ":pat": now_iso,
                        ":plr": client_email,
                        ":zero": 0,
                        ":inc": 1,
                        ":now": now_iso
                    }
                )
            except Exception as db_err:
                print(f"DATABASE ERROR: Failed to update request {request_id} payment email fields: {db_err}")
                return error(500, "Database update failed after sending payment email", event)

            # Audit log
            log_action(
                event,
                "PAYMENT_LINK_EMAIL_SENT",
                f"REQ#{request_id}",
                f"CLIENT#{client_id}",
                metadata={
                    "recipient_email": client_email,
                    "stripe_checkout_session_id": session_id,
                    "stripe_payment_url": payment_url
                }
            )

            return success({
                "message": "Payment email sent successfully",
                "recipient_email": client_email,
                "payment_status": request_item.get('payment_status')
            }, event)

        elif http_method == 'POST' and '/admin/job/complete' in path:

            role = get_effective_role(event)
            if role not in ['owner', 'admin', 'staff']:
                return error(403, "Forbidden", event)
                
            claims = get_claims(event)
            user_email = (claims.get('email') or "").lower().strip() or claims.get('username') or 'admin-api'
            
            try:
                body = json.loads(event.get('body', '{}'))
            except Exception:
                return bad_request("Invalid JSON body", event)
                
            job_id = body.get('job_id')
            request_id = body.get('request_id')
            visit_notes = (body.get('visit_notes') or '').strip()
            
            if not job_id or not request_id:
                return bad_request("Missing required fields: job_id, request_id", event)
                
            if len(visit_notes) > 500:
                return bad_request("Visit notes must not exceed 500 characters.", event)
                
            # 1. Get the JOB record
            job = get_item(f"JOB#{job_id}", f"REQ#{request_id}")
            if not job:
                return not_found(f"Job {job_id} not found under request {request_id}", event)

            # Release 11E: Post-read tenant ownership validation
            from common.auth import validate_tenant_ownership as _vto, get_claims as _gc
            try:
                _vto(job, event)
            except PermissionError:
                _c = _gc(event)
                print(f"SECURITY: Cross-tenant job/complete attempt by {_c.get('email')} for JOB#{job_id}")
                return error(403, "Forbidden", event)
                
            # 2. Staff ownership check
            if role == 'staff':
                worker_id = (job.get('worker_id') or '').lower().strip()
                if not worker_id or worker_id != user_email:
                    return error(403, "You can only complete visits assigned to you.", event)
                    
            # 3. Idempotency Check: Already completed
            current_status = job.get('status', 'ASSIGNED')
            if current_status == 'COMPLETED':
                parent_req = get_item(f"REQ#{request_id}", f"CLIENT#{job.get('client_id')}")
                parent_status = parent_req.get('status', 'ASSIGNED') if parent_req else 'COMPLETED'
                all_job_ids = []
                if parent_req:
                    all_job_ids = parent_req.get('job_ids') or [parent_req.get('job_id')]
                
                remaining = 0
                for jid in all_job_ids:
                    if jid == job_id:
                        continue
                    sib = get_item(f"JOB#{jid}", f"REQ#{request_id}")
                    if sib and sib.get('status') != 'COMPLETED':
                        remaining += 1
                
                return success({
                    "message": "Already completed",
                    "job_id": job_id,
                    "status": "COMPLETED",
                    "parent_status": parent_status,
                    "remaining_active_jobs": remaining
                }, event)
                
            if current_status not in ['ASSIGNED', 'JOB_CREATED', 'SCHEDULED', 'PENDING']:
                return bad_request(f"Cannot complete job in status: {current_status}", event)
                
            # 4. Update JOB to COMPLETED
            now = datetime.utcnow().isoformat()
            update_expr = "SET #stat = :s, completed_at = :cat, completed_by = :cby, updated_at = :now"
            expr_vals = {":s": "COMPLETED", ":cat": now, ":cby": user_email, ":now": now}
            expr_names = {"#stat": "status"}
            
            if visit_notes:
                update_expr += ", visit_notes = :vn"
                expr_vals[":vn"] = visit_notes
                
            table.update_item(
                Key={'PK': f"JOB#{job_id}", 'SK': f"REQ#{request_id}"},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_vals
            )
            
            # Audit log
            log_action(
                event,
                "JOB_COMPLETED",
                f"JOB#{job_id}",
                f"REQ#{request_id}",
                previous_status=current_status,
                new_status="COMPLETED",
                metadata={"client_id": job.get('client_id'), "visit_notes": visit_notes}
            )
            
            # 5. Check all sibling JOBs for auto-rollup
            parent_req = get_item(f"REQ#{request_id}", f"CLIENT#{job.get('client_id')}")
            if not parent_req:
                return success({
                    "message": "Visit completed successfully. Sibling/parent record not found.",
                    "job_id": job_id,
                    "status": "COMPLETED",
                    "parent_status": "UNKNOWN",
                    "remaining_active_jobs": 0
                }, event)
                
            all_job_ids = parent_req.get('job_ids') or [parent_req.get('job_id')]
            all_completed = True
            remaining = 0
            
            for jid in all_job_ids:
                if jid == job_id:
                    continue
                sibling = get_item(f"JOB#{jid}", f"REQ#{request_id}")
                if sibling and sibling.get('status') != 'COMPLETED':
                    all_completed = False
                    remaining += 1
                    
            # Track completed job IDs on parent REQ
            completed_jobs = parent_req.get('completed_job_ids') or []
            is_new_completion = job_id not in completed_jobs
            if is_new_completion:
                completed_jobs.append(job_id)

            parent_update_expr = "SET completed_job_ids = :cj, updated_at = :now"
            parent_expr_vals = {
                ":cj": completed_jobs,
                ":now": now
            }
            parent_expr_names = {}

            if is_new_completion:
                parent_update_expr += ", completed_count = if_not_exists(completed_count, :zero) + :one"
                parent_expr_vals.update({
                    ":zero": 0,
                    ":one": 1
                })

            parent_status = parent_req.get('status')
            if all_completed and parent_status != 'COMPLETED':
                # Auto-rollup: complete parent
                parent_update_expr += ", #stat = :s, completed_at = :cat, completed_by = :cby"
                parent_expr_vals.update({
                    ":s": "COMPLETED",
                    ":cat": now,
                    ":cby": user_email
                })
                parent_expr_names["#stat"] = "status"
                parent_status = "COMPLETED"

            table.update_item(
                Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{job.get('client_id')}"},
                UpdateExpression=parent_update_expr,
                ExpressionAttributeValues=parent_expr_vals,
                **(dict(ExpressionAttributeNames=parent_expr_names) if parent_expr_names else {})
            )


            if all_completed and parent_req.get('status') != 'COMPLETED':
                log_action(
                    event,
                    "AUTO_ROLLUP_COMPLETED",
                    f"REQ#{request_id}",
                    f"CLIENT#{job.get('client_id')}",
                    previous_status=parent_req.get('status'),
                    new_status="COMPLETED",
                    metadata={"reason": "All child jobs completed"}
                )
                
            return success({
                "message": "Visit completed successfully.",
                "job_id": job_id,
                "status": "COMPLETED",
                "parent_status": parent_status,
                "remaining_active_jobs": remaining
            }, event)

        elif http_method == 'POST':
            role = get_effective_role(event)
            if role not in ['owner', 'admin', 'staff']:
                return error(403, "Forbidden", event)
                
            claims = get_claims(event)
            user_email = (claims.get('email') or "").lower().strip() or claims.get('username') or 'admin-api'

            # --- Archive / Delete / Purge Actions ---
            body = json.loads(event.get('body', '{}'))
            action = (body.get('action') or '').upper()
            dry_run = body.get('dry_run', False)
            
            # Resolve target records (single or bulk)
            records_to_process = []
            if 'records' in body:
                records_to_process = body.get('records', [])
            elif body.get('PK') and body.get('SK'):
                records_to_process = [{'PK': body.get('PK'), 'SK': body.get('SK')}]

            if not action or not records_to_process:
                return bad_request("Missing action or records to process", event)

            if action in ['ARCHIVE', 'DELETE', 'PURGE', 'MARK_TEST', 'UNMARK_TEST', 'UNARCHIVE'] and role not in ['owner', 'admin']:
                return error(403, "Forbidden: Insufficient permissions for lifecycle action", event)


            from common.db import table as _table, update_status
            now_iso = datetime.now(timezone.utc).isoformat()
            
            results = {
                "success": 0,
                "failed": 0,
                "skipped": 0,
                "processed": [],
                "failures": []
            }

            # --- PURGE: Permanent deletion (Only for DELETED/TRASH records) ---
            if action == 'PURGE':
                bulk_op_id = str(uuid.uuid4()) if len(records_to_process) > 1 else None
                
                for rec in records_to_process:
                    item_pk = rec.get('PK')
                    item_sk = rec.get('SK')
                    
                    if not item_pk or not item_sk:
                        results["failed"] += 1
                        results["failures"].append({"record": "Unknown", "reason": "Missing PK or SK"})
                        continue

                    # ID Healing Resolution — pass company_id for tenant-scoped scan fallback (Release 11E)
                    from common.auth import get_current_company_id as _gcc
                    _purge_company_id = _gcc(event)
                    current_item, actual_pk, actual_sk = _resolve_admin_record(item_pk, item_sk, company_id=_purge_company_id)
                    
                    if not current_item:
                        results["failed"] += 1
                        results["failures"].append({"record": f"{item_pk}/{item_sk}", "reason": "Record not found"})
                        continue

                    current_status = (current_item.get('status') or '').upper()
                    has_trash_marker = current_item.get('deleted_at') or current_item.get('is_deleted')
                    is_purgeable = current_status in ['DELETED', 'TRASH'] or (not current_status and has_trash_marker)
                    
                    if not is_purgeable:
                        results["skipped"] += 1
                        reason = f"Record status is {current_status or 'MISSING'}. Move to Trash first."
                        results["failures"].append({"record": f"{actual_pk}/{actual_sk}", "reason": reason})
                        continue

                    if dry_run:
                        results["success"] += 1
                        results["processed"].append({"PK": actual_pk, "SK": actual_sk, "status": current_status, "purgeable": True})
                        continue

                    try:
                        _table.delete_item(Key={'PK': actual_pk, 'SK': actual_sk})
                        results["success"] += 1
                        log_action(event, 'PURGE', actual_pk, actual_sk, previous_status=current_status, bulk_op_id=bulk_op_id)
                        
                        # Release 7E Phase 1: Purge child JOBs best-effort
                        if actual_pk.startswith("REQ#"):
                            job_ids_to_purge = current_item.get('job_ids') or []
                            if not job_ids_to_purge and current_item.get('job_id'):
                                job_ids_to_purge = [current_item.get('job_id')]
                                
                            for j_id in job_ids_to_purge:
                                try:
                                    _table.delete_item(Key={'PK': f"JOB#{j_id}", 'SK': actual_pk})
                                    print(f"INFO: [PURGE] Purged child JOB#{j_id} for REQ {actual_pk}")
                                except Exception as e:
                                    print(f"WARNING: [PURGE] Failed to purge child JOB#{j_id}: {e}")
                                    
                    except Exception as e:
                        results["failed"] += 1
                        results["failures"].append({"record": f"{actual_pk}/{actual_sk}", "reason": str(e)})

                summary_msg = f"Bulk purge {'analysis' if dry_run else 'complete'}. Purgeable: {results['success']}, Skipped: {results['skipped']}, Failed: {results['failed']}"
                return success({
                    "message": summary_msg,
                    **results
                }, event)

            # --- DELETE / ARCHIVE / TEST DATA: Soft lifecycle transitions ---
            is_valid_action = False
            new_status = None
            if action == 'DELETE':
                new_status = 'DELETED'
                is_valid_action = True
            elif action == 'ARCHIVE':
                new_status = 'ARCHIVED'
                is_valid_action = True
            elif action in ['MARK_TEST', 'UNMARK_TEST', 'UNARCHIVE']:
                is_valid_action = True
            elif action in ['COMPLETED', 'CANCELLED', 'ASSIGNED', 'APPROVED', 'PENDING_REVIEW', 'DECLINED', 'PROFILE_CREATED', 'READY_FOR_APPROVAL', 'QUOTED', 'MG_COMPLETED']:
                new_status = action
                is_valid_action = True

            if is_valid_action:
                bulk_op_id = str(uuid.uuid4()) if len(records_to_process) > 1 else None
                
                for rec in records_to_process:
                    item_pk = rec.get('PK')
                    item_sk = rec.get('SK')
                    
                    if not item_pk or not item_sk:
                        results["failed"] += 1
                        results["failures"].append({"record": "Unknown", "reason": "Missing PK or SK"})
                        continue

                    # ID Healing Resolution — pass company_id for tenant-scoped scan fallback (Release 11E)
                    from common.auth import get_current_company_id as _gcc
                    _action_company_id = _gcc(event)
                    current_item, actual_pk, actual_sk = _resolve_admin_record(item_pk, item_sk, company_id=_action_company_id)
                    
                    if not current_item:
                        results["failed"] += 1
                        results["failures"].append({"record": f"{item_pk}/{item_sk}", "reason": "Record not found (even after healing)"})
                        continue

                    prev_status = (current_item.get('status') or 'UNKNOWN').upper()
                    
                    # Release 6D: Reject DELETE on active/scheduled records.
                    if action == 'DELETE':
                        protected_statuses = ['ASSIGNED', 'SCHEDULED', 'IN_PROGRESS', 'BOOKED']
                        if prev_status in protected_statuses:
                            results["skipped"] += 1
                            results["failures"].append({"record": f"{actual_pk}/{actual_sk}", "reason": f"Cannot delete active record (status: {prev_status}). Cancel or archive first."})
                            print(f"WARNING: [AdminBulk] Rejected DELETE on active record {actual_pk} (status: {prev_status})")
                            continue

                    # Safety: Only skip if already in the target status or already DELETED
                    if action == 'DELETE' and prev_status == 'DELETED':
                        results["skipped"] += 1
                        results["failures"].append({"record": f"{actual_pk}/{actual_sk}", "reason": "Already in Trash"})
                        continue
                    
                    if action == 'ARCHIVE' and prev_status == 'ARCHIVED':
                        results["skipped"] += 1
                        results["failures"].append({"record": f"{actual_pk}/{actual_sk}", "reason": "Already Archived"})
                        continue

                    if action == 'UNARCHIVE' and prev_status != 'ARCHIVED':
                        results["skipped"] += 1
                        results["failures"].append({"record": f"{actual_pk}/{actual_sk}", "reason": "Record is not Archived"})
                        continue

                    db_success = False
                    effective_new_status = new_status

                    if action in ['MARK_TEST', 'UNMARK_TEST', 'UNARCHIVE']:
                        if action == 'UNARCHIVE':
                            effective_new_status = 'ASSIGNED' if current_item.get('worker_id') else 'APPROVED'
                            update_expr = "SET #stat = :s, updated_at = :now, updated_by = :ub"
                            expr_attr_names = {"#stat": "status"}
                            expr_attr_vals = {
                                ":s": effective_new_status,
                                ":now": now_iso,
                                ":ub": user_email
                            }
                            audit_note = {"action": "ADMIN_UNARCHIVE", "timestamp": now_iso}
                            update_expr += ", audit_log = list_append(if_not_exists(audit_log, :empty_list), :n)"
                            expr_attr_vals[":n"] = [audit_note]
                            expr_attr_vals[":empty_list"] = []
                            
                            update_expr += " REMOVE archive_reason, archived_at, archived_by"
                            
                            try:
                                _table.update_item(
                                    Key={'PK': actual_pk, 'SK': actual_sk},
                                    UpdateExpression=update_expr,
                                    ExpressionAttributeNames=expr_attr_names,
                                    ExpressionAttributeValues=expr_attr_vals
                                )
                                db_success = True
                            except Exception as e:
                                print(f"ERROR: [UNARCHIVE] Failed updating {actual_pk}: {e}")
                        else:
                            is_test = (action == 'MARK_TEST')
                            update_expr = "SET is_test_booking = :itb, updated_at = :now, updated_by = :ub"
                            expr_attr_vals = {
                                ":itb": is_test,
                                ":now": now_iso,
                                ":ub": user_email
                            }
                            audit_note = {"action": f"ADMIN_{action}", "timestamp": now_iso}
                            update_expr += ", audit_log = list_append(if_not_exists(audit_log, :empty_list), :n)"
                            expr_attr_vals[":n"] = [audit_note]
                            expr_attr_vals[":empty_list"] = []
                            
                            try:
                                _table.update_item(
                                    Key={'PK': actual_pk, 'SK': actual_sk},
                                    UpdateExpression=update_expr,
                                    ExpressionAttributeValues=expr_attr_vals
                                )
                                current_item['is_test_booking'] = is_test
                                db_success = True
                                effective_new_status = prev_status
                            except Exception as e:
                                print(f"ERROR: [{action}] Failed updating {actual_pk}: {e}")
                    else:
                        extra_attrs = {}
                        if action == 'DELETE':
                            extra_attrs['deleted_at'] = now_iso
                        elif action == 'ARCHIVE':
                            extra_attrs['archive_reason'] = body.get('archive_reason') or 'Admin archived'
                            extra_attrs['archived_at'] = now_iso
                            extra_attrs['archived_by'] = user_email
                            
                        db_success = update_status(actual_pk, actual_sk, new_status, {"action": f"ADMIN_{action}", "timestamp": now_iso}, extra_attrs=extra_attrs)
                        effective_new_status = new_status

                    if db_success:
                        results["success"] += 1
                        log_action(event, action, actual_pk, actual_sk, previous_status=prev_status, new_status=effective_new_status, bulk_op_id=bulk_op_id)
                        
                        # --- GOOGLE CALENDAR SYNC (ADMIN BULK) ---
                        try:
                            is_multi_day_req = False
                            if actual_pk.startswith("REQ#"):
                                if current_item.get('end_date') and current_item.get('start_date') != current_item.get('end_date'):
                                    is_multi_day_req = True
                                if current_item.get('job_ids'):
                                    is_multi_day_req = True

                            if effective_new_status in ['APPROVED', 'ASSIGNED', 'BOOKED', 'SCHEDULED']:
                                if not is_multi_day_req:
                                    sync_data = {**current_item, 'status': effective_new_status}
                                    if action == 'ARCHIVE' or action == 'DELETE':
                                        pass
                                    else:
                                        cal_res = sync_calendar_event(sync_data, google_event_id=current_item.get('google_event_id'))
                                        if cal_res.get('event_id') and cal_res.get('event_id') != current_item.get('google_event_id'):
                                            _table.update_item(
                                                Key={'PK': actual_pk, 'SK': actual_sk},
                                                UpdateExpression="SET google_event_id = :gid",
                                                ExpressionAttributeValues={":gid": cal_res['event_id']}
                                            )
                            elif effective_new_status in ['CANCELLED', 'ARCHIVED', 'DELETED']:
                                if not is_multi_day_req:
                                    eid = current_item.get('google_event_id')
                                    if eid:
                                        if delete_event(eid, actual_pk):
                                            _table.update_item(Key={'PK': actual_pk, 'SK': actual_sk}, UpdateExpression="REMOVE google_event_id")
                                else:
                                    if current_item.get('job_ids'):
                                        for jid in current_item.get('job_ids'):
                                            job_item = get_item(f"JOB#{jid}", actual_pk)
                                            if job_item and job_item.get('status') == 'COMPLETED':
                                                print(f"INFO: [GoogleCalendar] Preserving Google Calendar event for completed JOB#{jid}")
                                                continue
                                            if job_item and job_item.get('google_event_id'):
                                                try:
                                                    delete_event(job_item['google_event_id'], actual_pk)
                                                    _table.update_item(
                                                        Key={'PK': f"JOB#{jid}", 'SK': actual_pk},
                                                        UpdateExpression="REMOVE google_event_id"
                                                    )
                                                except Exception as cal_err:
                                                    print(f"WARNING: [AdminBulk] Failed to delete child JOB cal event: {cal_err}")
                        except Exception as cal_err:
                            print(f"WARNING: [AdminBulk] Calendar sync failed for {actual_pk}: {cal_err}")

                        # Trigger notifications for relevant changes
                        if effective_new_status == 'APPROVED' and current_item.get('workflow_type') == 'CUSTOMER_INTAKE':
                            notify_event('CUSTOMER_APPROVED', current_item)
                        elif effective_new_status == 'CANCELLED':
                            notify_event('VISIT_CANCELLED', current_item)
                        
                        # Cascade REQ → JOB for admin actions.
                        if actual_pk.startswith('REQ#') and (current_item.get('job_id') or current_item.get('job_ids')):
                            try:
                                from common.cascade import cascade_status_to_job
                                remove_worker = (prev_status == 'ASSIGNED' and effective_new_status == 'APPROVED')
                                cascade_status_to_job(current_item, effective_new_status, updated_by=user_email, remove_worker=remove_worker)
                            except Exception as cascade_err:
                                print(f"WARNING: [AdminBulk] Cascade failed for {actual_pk}: {cascade_err}")
                    else:
                        results["failed"] += 1
                        results["failures"].append({"record": f"{actual_pk}/{actual_sk}", "reason": "Database update failed"})

                return success({
                    "message": f"Bulk {action} complete. Success: {results['success']}, Failed: {results['failed']}, Skipped: {results['skipped']}",
                    **results
                }, event)

            return bad_request(f"Unsupported action: {action}. Please use ARCHIVE, DELETE, PURGE, or a valid terminal status.", event)
            
    except EntitlementDenied as e:
        from common.response import format_response
        body = {
            "error": "EntitlementDenied",
            "message": str(e)
        }
        if getattr(e, "feature", None) is not None:
            body["feature"] = e.feature
        if getattr(e, "limit", None) is not None:
            body["limit"] = e.limit
        if getattr(e, "upgrade_hint", None) is not None:
            body["upgrade_hint"] = e.upgrade_hint
        return format_response(403, body, event)
    except Exception as e:
        print(f"Unhandled error: {e}")
        return internal_error(str(e), event)
