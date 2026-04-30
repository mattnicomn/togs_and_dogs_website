import json
import os
import boto3
from datetime import datetime
from common.db import query_by_status, get_item, update_status
from common.response import success, bad_request, internal_error, not_found, error
from common.auth import get_effective_role, sanitize_booking_for_role, get_claims



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
        
        if http_method == 'GET' and (path == '/admin/staff' or path.endswith('/admin/staff')):
            role = get_effective_role(event)
            if role not in ['owner', 'admin', 'staff']:
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

                    
            import uuid
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
                "is_assignable": body.get('is_assignable', True),
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
                    
                # Create user in FORCE_CHANGE_PASSWORD
                cog_resp = cognito.admin_create_user(
                    UserPoolId=user_pool_id,
                    Username=email,
                    UserAttributes=[
                        {'Name': 'email', 'Value': email},
                        {'Name': 'email_verified', 'Value': 'true'},
                    ],
                    DesiredDeliveryMediums=['EMAIL'] if body.get('send_invite', True) else []
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
                        
                import uuid
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
                    "cognito_status": "FORCE_CHANGE_PASSWORD",
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                items_table.put_item(Item=new_profile)
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
                                
                            target_profile['cognito_sub'] = cognito_sub
                            target_profile['cognito_status'] = cog_user.get('UserStatus')
                            target_profile['updated_at'] = datetime.utcnow().isoformat()
                            if not target_profile.get('email'):
                                target_profile['email'] = email
                            
                            items_table.put_item(Item=target_profile)
                            return success(target_profile, event)
                        else:
                            import uuid
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
                
            staff_id = path_params.get('staff_id')
            if not staff_id:
                staff_id = path.split('/')[-2]
                
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

                # Update profile
                staff_profile['cognito_sub'] = cognito_sub
                if email:
                    staff_profile['email'] = email
                staff_profile['cognito_status'] = cog_user.get('UserStatus')
                staff_profile['updated_at'] = datetime.utcnow().isoformat()
                
                items_table.put_item(Item=staff_profile)
                return success(staff_profile, event)
                
            except cognito.exceptions.UserNotFoundException:
                return not_found(f"Cognito user {username} not found", event)
            except Exception as e:
                print(f"Cognito link error: {e}")
                return internal_error(str(e), event)

        if http_method == 'POST' and '/resend-invite' in path:
            role = get_effective_role(event)
            if role not in ['owner', 'admin']:
                return error(403, "Forbidden", event)
                
            staff_id = path_params.get('staff_id')
            if not staff_id:
                staff_id = path.split('/')[-2]
                
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            from common.db import table as items_table
            
            resp = items_table.get_item(Key={"PK": f"COMPANY#{company_id}", "SK": f"STAFF#{staff_id}"})

            staff_profile = resp.get('Item')
            if not staff_profile:
                return not_found(f"Staff profile {staff_id} not found", event)
                
            cognito_sub = staff_profile.get('cognito_sub')
            email = staff_profile.get('email')
            
            if not cognito_sub and not email:
                return bad_request("Staff profile is not linked to a Cognito user", event)
                
            username = email or cognito_sub
            import boto3
            cognito = boto3.client('cognito-idp')
            user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
            
            try:
                cognito.admin_create_user(
                    UserPoolId=user_pool_id,
                    Username=username,
                    MessageAction='RESEND'
                )
                return success({"message": "Invite resent successfully"}, event)
                
            except cognito.exceptions.UserNotFoundException:
                return not_found(f"Cognito user {username} not found", event)
            except Exception as e:
                print(f"Cognito resend error: {e}")
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
                
            if http_method == 'DELETE':
                body = {}
                try:
                    if event.get('body'):
                        body = json.loads(event.get('body'))
                except Exception:
                    pass
                    
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
                    
                action = body.get('action')
                if action:
                    import boto3
                    cognito = boto3.client('cognito-idp')
                    user_pool_id = os.environ.get('ADMIN_USER_POOL_ID')
                    username = staff_profile.get('email') or staff_profile.get('cognito_username') or staff_id.replace('cognito_', '')
                    
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
                return success(staff_profile, event)


        if path == '/admin/clients' or path.endswith('/admin/clients'):
            role = get_effective_role(event)
            # GET /admin/clients
            if http_method == 'GET':
                if role not in ['owner', 'admin', 'staff']:
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
                
                if not display_name or not email:
                    return bad_request("display_name and email are required", event)
                    
                from common.auth import get_current_company_id
                company_id = get_current_company_id(event)
                from common.db import table as items_table
                from boto3.dynamodb.conditions import Key
                
                # Check duplicate active email within company_id
                resp = items_table.query(
                    KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("CLIENT#")
                )
                existing_clients = resp.get('Items', [])
                for c in existing_clients:
                    if (c.get('email') or '').lower() == email and c.get('is_active') == True:
                        return error(409, f"Active client with email {email} already exists", event)
                        
                import uuid
                client_id = f"client_{str(uuid.uuid4())[:8]}"
                
                new_profile = {
                    "PK": f"COMPANY#{company_id}",
                    "SK": f"CLIENT#{client_id}",
                    "company_id": company_id,
                    "client_id": client_id,
                    "email": email,
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
                    if not new_email:
                        return bad_request("email cannot be blank", event)
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
                filter_expressions = []
                expression_values = {}

                from common.auth import get_current_company_id
                company_id = get_current_company_id(event)
                filter_expressions.append("(company_id = :cid OR attribute_not_exists(company_id))")
                expression_values[":cid"] = company_id

                if role == 'staff' and user_email:
                    # Staff only see jobs assigned to them
                    filter_expressions.append("worker_id = :wid")
                    expression_values[":wid"] = user_email
                elif not is_admin and user_email:
                    # Clients only see their own records
                    filter_expressions.append("client_email = :email")
                    expression_values[":email"] = user_email
                
                # Exclude deleted and archived from the general 'ALL' view
                filter_expressions.append("#stat <> :deleted")

                filter_expressions.append("#stat <> :archived")
                expression_values[":deleted"] = 'DELETED'
                expression_values[":archived"] = 'ARCHIVED'
                
                scan_kwargs["FilterExpression"] = " AND ".join(filter_expressions)
                scan_kwargs["ExpressionAttributeValues"] = expression_values
                scan_kwargs["ExpressionAttributeNames"] = {"#stat": "status"}
                
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
            if role not in ['owner', 'admin', 'staff']:
                return error(403, "Forbidden: Clients cannot query arbitrary statuses", event)
                
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)

            query_kwargs = {
                "IndexName": "StatusIndex",
                "KeyConditionExpression": Key('status').eq(status),
                "FilterExpression": "company_id = :cid OR attribute_not_exists(company_id)",
                "ExpressionAttributeValues": {":cid": company_id},
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

            # Archive/Delete/Purge Actions
            body = json.loads(event.get('body', '{}'))
            action = body.get('action')
            pk = body.get('PK')
            sk = body.get('SK')

            if action in ['ARCHIVE', 'DELETE', 'PURGE'] and role not in ['owner', 'admin']:
                return error(403, "Forbidden: Insufficient permissions for lifecycle action", event)

            if not action or (not (pk and sk) and 'records' not in body):
                return bad_request("Missing action, PK, SK, or records array", event)

            # --- PURGE: Permanent deletion — only allowed for already-DELETED records ---
            if action == 'PURGE':
                if role not in ['owner', 'admin']:
                    return error(403, "Forbidden: Only owners and admins can permanently delete records", event)

                records_to_purge = []
                if 'records' in body:
                    records_to_purge = body.get('records', [])
                else:
                    pk = body.get('PK')
                    sk = body.get('SK')
                    if pk and sk:
                        records_to_purge = [{'PK': pk, 'SK': sk}]

                if not records_to_purge:
                    return bad_request("Missing PK/SK or records array for PURGE action", event)

                deleted_count = 0
                skipped_count = 0
                failed_count = 0
                failures = []

                from common.db import table as _table

                for rec in records_to_purge:
                    item_pk = rec.get('PK')
                    item_sk = rec.get('SK')
                    
                    if not item_pk or not item_sk:
                        failed_count += 1
                        failures.append({"record": f"{item_pk}/{item_sk}", "reason": "Missing PK or SK"})
                        continue

                    # Resolution chain
                    current_item = get_item(item_pk, item_sk)
                    if not current_item:
                        # Fallback 1: Swap PK/SK
                        current_item = get_item(item_sk, item_pk)
                        if current_item:
                            item_pk, item_sk = item_sk, item_pk

                    if not current_item:
                        # Fallback 2: Scan for matching embedded IDs
                        from boto3.dynamodb.conditions import Attr
                        raw_pk_id = item_pk.replace("JOB#", "").replace("REQ#", "")
                        raw_sk_id = item_sk.replace("JOB#", "").replace("REQ#", "")
                        
                        scan_kwargs = {
                            "FilterExpression": Attr('PK').contains(raw_pk_id) | Attr('SK').contains(raw_pk_id) | Attr('PK').contains(raw_sk_id) | Attr('SK').contains(raw_sk_id)
                        }
                        
                        found_items = []
                        response = _table.scan(**scan_kwargs)
                        found_items.extend(response.get('Items', []))
                        while 'LastEvaluatedKey' in response and not found_items:
                            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
                            response = _table.scan(**scan_kwargs)
                            found_items.extend(response.get('Items', []))
                            
                        if found_items:
                            current_item = found_items[0]
                            item_pk = current_item['PK']
                            item_sk = current_item['SK']

                    if not current_item:
                        failed_count += 1
                        failures.append({"record": f"{item_pk}/{item_sk}", "reason": "Record not found"})
                        continue

                    current_status = (current_item.get('status') or '').upper()
                    if current_status != 'DELETED':
                        skipped_count += 1
                        failures.append({"record": f"{item_pk}/{item_sk}", "reason": f"Record status is {current_status}, not DELETED"})
                        continue

                    try:
                        _table.delete_item(Key={'PK': item_pk, 'SK': item_sk})
                        deleted_count += 1
                        print(f"PURGE COMPLETE: [{item_pk}] permanently deleted by {user_email}")
                    except Exception as e:
                        failed_count += 1
                        failures.append({"record": f"{item_pk}/{item_sk}", "reason": str(e)})

                if 'records' in body:
                    return success({
                        "message": f"Bulk purge complete. Deleted: {deleted_count}, Skipped: {skipped_count}, Failed: {failed_count}",
                        "deleted_count": deleted_count,
                        "skipped_count": skipped_count,
                        "failed_count": failed_count,
                        "failures": failures
                    }, event)
                else:
                    if failed_count > 0:
                        return not_found(f"Permanent delete failed: {failures[0]['reason']}: {item_pk} / {item_sk}", event)
                    if skipped_count > 0:
                        return bad_request(f"Permanent delete rejected: {failures[0]['reason']}", event)
                        
                    return success({
                        "message": "Record permanently deleted.",
                        "PK": item_pk,
                        "SK": item_sk,
                        "previous_status": 'DELETED',
                        "purged_by": user_email
                    }, event)

            # --- Standard soft-state transitions ---
            new_status = None
            if action == 'ARCHIVE':
                new_status = 'ARCHIVED'
            elif action == 'DELETE':
                new_status = 'DELETED'
            elif action in ['COMPLETED', 'CANCELLED', 'ASSIGNED', 'APPROVED', 'PENDING_REVIEW', 'DECLINED', 'PROFILE_CREATED', 'READY_FOR_APPROVAL', 'QUOTED', 'MG_COMPLETED']:
                # Support direct status mapping for canonical record updates
                new_status = action

            if new_status:
                from datetime import timezone
                if update_status(pk, sk, new_status, {"action": f"ADMIN_{action}", "timestamp": datetime.now(timezone.utc).isoformat()}):
                    return success({"message": f"Record status update to {new_status} success", "status": new_status}, event)

            return bad_request(f"Unsupported action: {action}. Please use ARCHIVE, DELETE, PURGE, or a valid terminal status.", event)
            
    except Exception as e:
        print(f"Unhandled error: {e}")
        return internal_error(str(e), event)
