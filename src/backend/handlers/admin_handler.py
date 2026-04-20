import json
import os
import boto3
from common.db import query_by_status, get_item
from common.response import success, bad_request, internal_error, not_found

def handler(event, context):
    try:
        http_method = event.get('httpMethod')
        path_params = event.get('pathParameters', {}) or {}
        query_params = event.get('queryStringParameters', {}) or {}
        
        if http_method == 'GET':
            request_id = path_params.get('requestId')
            client_id = query_params.get('clientId') # SK is required for get_item

            if request_id and client_id:
                # Retrieve specific request
                item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
                if item:
                    return success(item, event)
                return not_found(f"Request {request_id} not found", event)
            else:
                # List requests (Updated for Milestone 2)
                # Defaults to PENDING_REVIEW if no status provided
                status = query_params.get('status', 'PENDING_REVIEW')
                
                # Allow 'ALL' to get a snapshot for the scheduler (MVP optimization)
                if status == 'ALL':
                    from common.db import table as items_table
                    response = items_table.scan(
                        FilterExpression="entity_type = :et",
                        ExpressionAttributeValues={":et": "REQUEST"}
                    )
                    items = response.get('Items', [])
                    
                    # Also fetch Jobs to populate the scheduler
                    job_res = items_table.scan(
                        FilterExpression="entity_type = :et",
                        ExpressionAttributeValues={":et": "JOB"}
                    )
                    items.extend(job_res.get('Items', []))
                else:
                    items = query_by_status(status)
                
                return success({"requests": items}, event)
        
        return bad_request(f"Unsupported method: {http_method}", event)
            
    except Exception as e:
        print(f"Unhandled error: {e}")
        return internal_error(str(e), event)
