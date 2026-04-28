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
                
            company_id = 'tog_and_dogs'
            from common.db import table as items_table
            from boto3.dynamodb.conditions import Key
            
            response = items_table.query(
                KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("STAFF#")
            )
            staff_profiles = response.get('Items', [])
            # Only return active staff
            active_staff = [s for s in staff_profiles if s.get('is_active') == True]
            return success({"staff": active_staff}, event)

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
                
            query_kwargs = {

                "IndexName": "StatusIndex",
                "KeyConditionExpression": Key('status').eq(status),
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
