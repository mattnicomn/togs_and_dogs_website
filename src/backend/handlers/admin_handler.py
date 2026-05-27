import json
import os
import boto3
from datetime import datetime
from common.db import query_by_status, get_item, update_status, table
from common.notifications.service import notify_event
from common.google_calendar import sync_calendar_event, delete_event
from common.response import success, bad_request, internal_error, not_found, error
from common.auth import get_effective_role, sanitize_booking_for_role, get_claims
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


def _resolve_admin_record(pk, sk):
    """
    Robust record resolution for administrative cleanup.
    Handles swapped keys and malformed identifiers in 'Data Issues'.
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
            
            # Fetch all records for backup
            # Low-volume operational scale allows for periodic admin scans
            scan_kwargs = {}
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
                # Release 6H Phase 2: Include is_protected flag for frontend consumption
                s['is_protected'] = is_protected_profile(s)
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
                # Release 6H Phase 2: Include is_protected flag for frontend
                v_profile['is_protected'] = is_protected_profile(v_profile)
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
                        staff_profile.pop('cognito_sub', None)
                        staff_profile.pop('cognito_username', None)
                        staff_profile.pop('cognito_status', None)
                        staff_profile['updated_at'] = datetime.utcnow().isoformat()
                        items_table.put_item(Item=staff_profile)
                        return success(staff_profile, event)
                        
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
            if user_profile.get('is_virtual'):
                try:
                    cog_user = cognito.admin_get_user(UserPoolId=user_pool_id, Username=user_profile['display_name'])
                    username = cog_user.get('Username')
                    # Update profile with actual email from attributes for notification
                    for attr in cog_user.get('UserAttributes', []):
                        if attr['Name'] == 'email':
                            user_profile['email'] = attr['Value']
                        if attr['Name'] == 'name' or attr['Name'] == 'nickname':
                            user_profile['display_name'] = attr['Value']
                except Exception as e:
                    print(f"Virtual user resolution error: {e}")
                    username = user_profile['display_name']
            else:
                username = user_profile.get('email') or user_profile.get('cognito_sub') or user_profile.get('cognito_username')
            
            if not username:
                return bad_request("Profile is not linked to a Cognito user", event)
            
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
                        client_profile.pop('cognito_sub', None)
                        client_profile.pop('cognito_username', None)
                        client_profile.pop('cognito_status', None)
                        client_profile['portal_enabled'] = False
                        client_profile['updated_at'] = datetime.utcnow().isoformat()
                        items_table.put_item(Item=client_profile)
                        return success(client_profile, event)
                        
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
                return success(item, event) if item else not_found(f"Request {request_id} not found", event)
            
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

            if action in ['ARCHIVE', 'DELETE', 'PURGE'] and role not in ['owner', 'admin']:
                return error(403, "Forbidden: Insufficient permissions for lifecycle action", event)

            from common.db import table as _table, update_status
            from datetime import timezone
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

                    # ID Healing Resolution
                    current_item, actual_pk, actual_sk = _resolve_admin_record(item_pk, item_sk)
                    
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

            # --- DELETE / ARCHIVE: Soft lifecycle transitions ---
            new_status = None
            if action == 'DELETE':
                new_status = 'DELETED'
            elif action == 'ARCHIVE':
                new_status = 'ARCHIVED'
            elif action in ['COMPLETED', 'CANCELLED', 'ASSIGNED', 'APPROVED', 'PENDING_REVIEW', 'DECLINED', 'PROFILE_CREATED', 'READY_FOR_APPROVAL', 'QUOTED', 'MG_COMPLETED']:
                new_status = action

            if new_status:
                bulk_op_id = str(uuid.uuid4()) if len(records_to_process) > 1 else None
                
                for rec in records_to_process:
                    item_pk = rec.get('PK')
                    item_sk = rec.get('SK')
                    
                    if not item_pk or not item_sk:
                        results["failed"] += 1
                        results["failures"].append({"record": "Unknown", "reason": "Missing PK or SK"})
                        continue

                    # ID Healing Resolution
                    current_item, actual_pk, actual_sk = _resolve_admin_record(item_pk, item_sk)
                    
                    if not current_item:
                        # For Data Issues, we might want to move to Trash even if not found in a strict way?
                        # No, if we can't find it via resolution chain, we can't update it.
                        results["failed"] += 1
                        results["failures"].append({"record": f"{item_pk}/{item_sk}", "reason": "Record not found (even after healing)"})
                        continue

                    prev_status = (current_item.get('status') or 'UNKNOWN').upper()
                    
                    # Release 6D: Reject DELETE on active/scheduled records.
                    # Prevents accidental soft-delete of records that are in active workflow states.
                    # Admin must CANCEL or ARCHIVE first before moving to Trash.
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

                    extra_attrs = {}
                    if action == 'DELETE':
                        extra_attrs['deleted_at'] = now_iso

                    if update_status(actual_pk, actual_sk, new_status, {"action": f"ADMIN_{action}", "timestamp": now_iso}, extra_attrs=extra_attrs):
                        results["success"] += 1
                        log_action(event, action, actual_pk, actual_sk, previous_status=prev_status, new_status=new_status, bulk_op_id=bulk_op_id)
                        
                        # --- GOOGLE CALENDAR SYNC (ADMIN BULK) ---
                        try:
                            is_multi_day_req = False
                            if actual_pk.startswith("REQ#"):
                                if current_item.get('end_date') and current_item.get('start_date') != current_item.get('end_date'):
                                    is_multi_day_req = True
                                if current_item.get('job_ids'):
                                    is_multi_day_req = True

                            if new_status in ['APPROVED', 'ASSIGNED', 'BOOKED', 'SCHEDULED']:
                                if not is_multi_day_req:
                                    sync_data = {**current_item, 'status': new_status}
                                    if extra_attrs: sync_data.update(extra_attrs)
                                    
                                    cal_res = sync_calendar_event(sync_data, google_event_id=current_item.get('google_event_id'))
                                    if cal_res.get('event_id') and cal_res.get('event_id') != current_item.get('google_event_id'):
                                        table.update_item(
                                            Key={'PK': actual_pk, 'SK': actual_sk},
                                            UpdateExpression="SET google_event_id = :gid",
                                            ExpressionAttributeValues={":gid": cal_res['event_id']}
                                        )
                            elif new_status in ['CANCELLED', 'ARCHIVED', 'DELETED']:
                                if not is_multi_day_req:
                                    eid = current_item.get('google_event_id')
                                    if eid:
                                        if delete_event(eid, actual_pk):
                                            table.update_item(Key={'PK': actual_pk, 'SK': actual_sk}, UpdateExpression="REMOVE google_event_id")
                                else:
                                    if current_item.get('job_ids'):
                                        for jid in current_item.get('job_ids'):
                                            job_item = get_item(f"JOB#{jid}", actual_pk)
                                            if job_item and job_item.get('google_event_id'):
                                                try:
                                                    delete_event(job_item['google_event_id'], actual_pk)
                                                    table.update_item(
                                                        Key={'PK': f"JOB#{jid}", 'SK': actual_pk},
                                                        UpdateExpression="REMOVE google_event_id"
                                                    )
                                                except Exception as cal_err:
                                                    print(f"WARNING: [AdminBulk] Failed to delete child JOB cal event: {cal_err}")
                        except Exception as cal_err:
                            print(f"WARNING: [AdminBulk] Calendar sync failed for {actual_pk}: {cal_err}")

                        # Trigger notifications for relevant changes
                        if new_status == 'APPROVED' and current_item.get('workflow_type') == 'CUSTOMER_INTAKE':
                            notify_event('CUSTOMER_APPROVED', current_item)
                        elif new_status == 'CANCELLED':
                            notify_event('VISIT_CANCELLED', current_item)
                        
                        # Release 1: Cascade REQ → JOB for bulk admin actions.
                        # Ensures linked JOB records stay consistent when parent REQ is
                        # archived, deleted, cancelled, or recovered via bulk action.
                        if actual_pk.startswith('REQ#') and current_item.get('job_id'):
                            try:
                                from common.cascade import cascade_status_to_job
                                remove_worker = (prev_status == 'ASSIGNED' and new_status == 'APPROVED')
                                cascade_status_to_job(current_item, new_status, updated_by=user_email, remove_worker=remove_worker)
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
            
    except Exception as e:
        print(f"Unhandled error: {e}")
        return internal_error(str(e), event)
