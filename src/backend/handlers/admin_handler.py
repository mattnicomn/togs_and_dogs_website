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
        if http_method == 'GET' and (path == '/admin/staff' or path.endswith('/admin/staff')):
            role = get_effective_role(event)
            if role not in ['owner', 'admin', 'staff']:
                return error(403, "Forbidden", event)
                
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            from common.db import table as items_table
            from boto3.dynamodb.conditions import Key
            
            response = items_table.query(
                KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("STAFF#")
            )

            staff_profiles = response.get('Items', [])
            # Only return active staff
            active_staff = [s for s in staff_profiles if s.get('is_active') == True]
            return success({"staff": active_staff}, event)

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

                if not is_admin and user_email:
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
                
            # Archive/Delete/Purge Actions
            body = json.loads(event.get('body', '{}'))
            action = body.get('action')
            pk = body.get('PK')
            sk = body.get('SK')

            if action in ['ARCHIVE', 'DELETE', 'PURGE'] and role not in ['owner', 'admin']:
                return error(403, "Forbidden: Insufficient permissions for lifecycle action", event)

            if not (action and pk and sk):

                return bad_request("Missing action, PK, or SK", event)

            # --- PURGE: Permanent deletion — only allowed for already-DELETED records ---
            if action == 'PURGE':
                if role not in ['owner', 'admin']:
                    return error(403, "Forbidden: Only owners and admins can permanently delete records", event)


                # Fetch current record to verify status before purging
                current_item = get_item(pk, sk)
                if not current_item:
                    return not_found(f"Record not found: {pk} / {sk}", event)

                current_status = (current_item.get('status') or '').upper()
                if current_status != 'DELETED':
                    print(
                        f"PURGE REJECTED: [{pk}] status is '{current_status}', not DELETED. "
                        f"Requester: {user_email}"
                    )
                    return bad_request(
                        f"Only records with status DELETED can be permanently removed. "
                        f"This record is currently '{current_status}'.",
                        event
                    )

                # Perform permanent deletion
                from datetime import timezone
                from common.db import table as _table
                try:
                    _table.delete_item(Key={'PK': pk, 'SK': sk})
                    print(
                        f"PURGE COMPLETE: [{pk}] permanently deleted by {user_email} "
                        f"at {datetime.now(timezone.utc).isoformat()}. "
                        f"Previous status: DELETED."
                    )
                    return success({
                        "message": "Record permanently deleted.",
                        "PK": pk,
                        "SK": sk,
                        "previous_status": current_status,
                        "purged_by": user_email
                    }, event)
                except Exception as purge_err:
                    print(f"ERROR: PURGE failed for [{pk}]: {purge_err}")
                    return internal_error("Failed to permanently delete record.", event)

            # --- Standard soft-state transitions ---
            new_status = None
            if action == 'ARCHIVE':
                new_status = 'ARCHIVED'
            elif action == 'DELETE':
                new_status = 'DELETED'
            elif action in ['COMPLETED', 'CANCELLED', 'ASSIGNED', 'APPROVED', 'PENDING_REVIEW']:
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
