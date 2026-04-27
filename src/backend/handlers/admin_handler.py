import json
import os
import boto3
from datetime import datetime
from common.db import query_by_status, get_item, update_status
from common.response import success, bad_request, internal_error, not_found

def handler(event, context):
    try:
        http_method = event.get('httpMethod')
        path_params = event.get('pathParameters', {}) or {}
        query_params = event.get('queryStringParameters', {}) or {}
        
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
                # SECURITY: Data Isolation for Clients
                authorizer = event.get('requestContext', {}).get('authorizer', {})
                claims = authorizer.get('claims', {})
                user_email = (claims.get('email') or "").lower().strip()
                groups = claims.get('cognito:groups', [])
                is_admin = 'Staff' in groups or 'Admin' in groups or user_email in ['mattnicomn10@gmail.com', 'support@toganddogs.usmissionhero.com']

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
                
                return success({
                    "requests": items,
                    "lastKey": json.dumps(response.get('LastEvaluatedKey')) if response.get('LastEvaluatedKey') else None
                }, event)

            # INDEXED QUERY: Specific Status
            query_kwargs = {
                "IndexName": "StatusIndex",
                "KeyConditionExpression": Key('status').eq(status),
                "Limit": limit,
                "ScanIndexForward": False # Newest first
            }
            
            if last_key:
                query_kwargs["ExclusiveStartKey"] = json.loads(last_key)
            
            response = items_table.query(**query_kwargs)
            
            return success({
                "requests": response.get('Items', []),
                "lastKey": json.dumps(response.get('LastEvaluatedKey')) if response.get('LastEvaluatedKey') else None
            }, event)

        elif http_method == 'POST':
            # Archive/Delete/Purge Actions
            body = json.loads(event.get('body', '{}'))
            action = body.get('action')
            pk = body.get('PK')
            sk = body.get('SK')

            if not (action and pk and sk):
                return bad_request("Missing action, PK, or SK", event)

            # --- PURGE: Permanent deletion — only allowed for already-DELETED records ---
            if action == 'PURGE':
                # Auth guard: only admins may purge
                authorizer = event.get('requestContext', {}).get('authorizer', {})
                claims = authorizer.get('claims', {})
                user_email = (claims.get('email') or "").lower().strip()
                groups = claims.get('cognito:groups', [])
                is_admin = (
                    'Staff' in groups or
                    'Admin' in groups or
                    user_email in ['mattnicomn10@gmail.com', 'support@toganddogs.usmissionhero.com']
                )
                if not is_admin:
                    return bad_request("Administrative access required for permanent deletion.", event)

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
