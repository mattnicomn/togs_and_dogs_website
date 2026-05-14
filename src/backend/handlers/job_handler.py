import uuid
from datetime import datetime, timezone
import boto3
from common.db import put_item, get_item, table
from common.status import JobStatus

def handler(event, context):
    """
    Intended to be triggered by Step Function or Review Handler.
    Creates a JOB record when a REQUEST is APPROVED.
    Ensures a PET entity exists and is linked.
    """
    try:
        # Extract metadata from event
        request_id = event.get('request_id')
        client_id = event.get('client_id')
        
        if not (request_id and client_id):
            print("Error: Missing request_id or client_id in event")
            return {"error": "Missing metadata"}

        # Fetch original request to get metadata
        request_item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
        if not request_item:
            print(f"Error: Request REQ#{request_id} not found")
            return {"error": "Request not found"}

        from common.auth import get_current_company_id
        company_id = request_item.get('company_id') or get_current_company_id(event if 'event' in locals() else {})

        # Release 4: Use multi-pet profile utility for PET# record creation.
        # This replaces the inline single-pet creation with a utility that:
        # - Supports multiple pets from the 'pets' array
        # - Falls back to legacy pet_names string for old requests
        # - Uses pet_ids array as idempotency guard
        # - Links PET# records to client profile ID when available
        # - Handles name matching and duplicate detection
        from common.pet_profile import create_or_link_pets_from_request
        pet_result = create_or_link_pets_from_request(
            request_item=request_item,
            request_id=request_id,
            client_id=client_id,
            company_id=company_id,
            updated_by='system_job_handler'
        )
        pet_ids = pet_result.get('pet_ids', [])
        pet_id = pet_ids[0] if pet_ids else None

        job_id = str(uuid.uuid4())
        
        # 2. Create the Job record linked to the PET
        item = {
            'PK': f"JOB#{job_id}",
            'SK': f"REQ#{request_id}",
            'company_id': company_id,
            'request_id': request_id,
            'client_id': client_id,
            'pet_id': pet_id,
            'pet_name': request_item.get('pet_names') or "Unnamed Pet",

            'client_name': request_item.get('client_name'),
            'client_email': request_item.get('client_email'),
            'service_type': request_item.get('service_type'),
            'start_date': request_item.get('start_date'),
            # Release 1: Copy end_date and visit_window so JOB records have full scheduling context.
            # Previously only start_date was copied, causing date-range bookings to display
            # inconsistently between REQ and JOB records.
            'end_date': request_item.get('end_date'),
            'visit_window': request_item.get('visit_window'),
            # Release 2: Copy visit_windows array and preferred_sitter for scheduling context.
            'visit_windows': request_item.get('visit_windows'),
            'preferred_sitter': request_item.get('preferred_sitter'),
            'preferred_sitter_name': request_item.get('preferred_sitter_name'),
            'pet_info': request_item.get('pet_info'),
            'status': JobStatus.JOB_CREATED.value,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'entity_type': 'JOB',
            'audit_log': [{
                "action": "JOB_INITIALIZED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "note": f"Automatically created from approved request. Linked Pet: {pet_id}"
            }]
        }
        
        event_id = event.get('google_event_id') or request_item.get('google_event_id')
        if event_id:
            item['google_event_id'] = event_id
        
        if put_item(item):
            print(f"Job {job_id} created successfully. Pet: {pet_id}")
            
            # Link back to original request
            try:
                table.update_item(
                    Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                    UpdateExpression="SET job_id = :jid",
                    ExpressionAttributeValues={":jid": job_id}
                )
            except Exception as e:
                print(f"WARNING: Failed to link job_id back to request: {e}")
                
            return {
                "job_id": job_id,
                "pet_id": pet_id,
                "status": item['status']
            }
        else:
            return {"error": "Failed to save job"}
            
    except Exception as e:
        print(f"Unhandled error: {e}")
        return {"error": str(e)}
