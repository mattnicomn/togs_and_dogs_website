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

        # 1. Ensure PET entity exists or create a new one
        pet_id = request_item.get('pet_id')
        if not pet_id:
            # Create a new PET record from the intake info
            pet_id = str(uuid.uuid4())
            pet_item = {
                'PK': f"PET#{pet_id}",
                'SK': f"CLIENT#{client_id}",
                'company_id': company_id,
                'entity_type': 'PET',
                'name': request_item.get('pet_names') or "Unnamed Pet", 
                'client_id': client_id,
                'pet_id': pet_id,

                'care_instructions': request_item.get('pet_info'),
                'meet_and_greet_completed': True, # Only approved requests get here
                'created_at': datetime.now(timezone.utc).isoformat(),
                'status': 'ACTIVE'
            }
            if put_item(pet_item):
                print(f"INFO: Created new PET entity {pet_id} for client {client_id}")
                # Link back to original request
                try:
                    table.update_item(
                        Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                        UpdateExpression="SET pet_id = :pid",
                        ExpressionAttributeValues={":pid": pet_id}
                    )
                except Exception as e:
                    print(f"WARNING: Failed to link pet_id back to request: {e}")
            else:
                print("ERROR: Failed to create PET entity")
                return {"error": "Pet creation failed"}

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
            'pet_info': request_item.get('pet_info'),
            'google_event_id': event.get('google_event_id') or request_item.get('google_event_id'),
            'status': JobStatus.JOB_CREATED.value,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'entity_type': 'JOB',
            'audit_log': [{
                "action": "JOB_INITIALIZED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "note": f"Automatically created from approved request. Linked Pet: {pet_id}"
            }]
        }
        
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
