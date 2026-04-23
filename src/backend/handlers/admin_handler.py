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
                # If the user is a client (detected by lack of admin group or presence of email), 
                # we must restrict the scan or filter the results server-side.
                authorizer = event.get('requestContext', {}).get('authorizer', {})
                claims = authorizer.get('claims', {})
                user_email = (claims.get('email') or "").lower().strip()
                groups = claims.get('cognito:groups', [])
                is_admin = 'Staff' in groups or 'Admin' in groups or user_email in ['mattnicomn10@gmail.com', 'support@toganddogs.usmissionhero.com']

                scan_kwargs = {"Limit": 1000} # Increased limit for production stability
                
                if not is_admin and user_email:
                    # CLIENT-ONLY: Restrict to their email
                    print(f"INFO: Restricting scan for client: {user_email}")
                    scan_kwargs["FilterExpression"] = "client_email = :email"
                    scan_kwargs["ExpressionAttributeValues"] = {":email": user_email}
                
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
            # Archive/Delete Actions
            body = json.loads(event.get('body', '{}'))
            action = body.get('action')
            pk = body.get('PK')
            sk = body.get('SK')
            
            if not (action and pk and sk):
                return bad_request("Missing action, PK, or SK", event)
            
            new_status = None
            if action == 'ARCHIVE':
                new_status = 'ARCHIVED'
            elif action == 'DELETE':
                new_status = 'CANCELLED'
            
            if new_status:
                from datetime import timezone
                if update_status(pk, sk, new_status, {"action": action, "timestamp": datetime.now(timezone.utc).isoformat()}):
                    return success({"message": f"Record {action} success", "status": new_status}, event)
            
            return bad_request(f"Unsupported action: {action}", event)
            
    except Exception as e:
        print(f"Unhandled error: {e}")
        return internal_error(str(e), event)
