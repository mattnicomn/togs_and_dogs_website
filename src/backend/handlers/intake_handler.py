import json
import uuid
import os
import boto3
from datetime import datetime
from common.db import put_item
from common.response import success, bad_request, internal_error
from common.status import RequestStatus

sfn = boto3.client('stepfunctions')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        
        client_name = body.get('client_name')
        client_email = body.get('client_email')
        start_date = body.get('start_date')
        pet_names = body.get('pet_names')
        
        # --- CLIENT BOUNDARY: Auto-resolve identity if submitted via /client/requests ---
        from common.auth import get_effective_role, resolve_client_identity, get_claims
        role = get_effective_role(event)
        client_id = body.get('client_id')
        
        if event.get('path', '') == '/client/requests' and role == 'client':
            resolved_id = resolve_client_identity(event)
            if resolved_id:
                client_id = resolved_id
                claims = get_claims(event)
                client_email = claims.get('email') or client_email
                # Note: We still might need client_name from the body if the token lacks it.
        
        # Basic validation for required fields (non-empty, non-whitespace)
        required_fields = {
            'client_name': client_name,
            'client_email': client_email,
            'start_date': start_date,
            'pet_names': pet_names
        }
        
        missing = [k for k, v in required_fields.items() if not v or (isinstance(v, str) and not v.strip())]
        if missing:
            return bad_request(f"Missing or invalid required fields: {', '.join(missing)}", event)

        client_email = client_email.lower().strip()

        request_id = str(uuid.uuid4())
        client_id = client_id or body.get('client_id', str(uuid.uuid4()))
        
        from common.auth import get_current_company_id
        company_id = get_current_company_id(event)

        # Create the Request record
        item = {
            'PK': f"REQ#{request_id}",
            'SK': f"CLIENT#{client_id}",
            'company_id': company_id,
            'request_id': request_id,
            'client_id': client_id,

            'client_name': client_name,
            'client_email': client_email,
            'start_date': start_date,
            'end_date': body.get('end_date'),
            'visit_window': body.get('visit_window', 'ANYTIME'),
            'preferred_time': body.get('preferred_time'),
            'timing_notes': body.get('timing_notes'),
            'pet_names': body.get('pet_names'),
            'pet_info': body.get('pet_info'),
            'service_type': body.get('service_type', 'PET_SITTING'),
            'status': RequestStatus.PENDING_REVIEW.value,
            'created_at': datetime.utcnow().isoformat(),
            'entity_type': 'REQUEST'
        }
        
        if put_item(item):
            # Trigger Step Function Lifecycle
            if STATE_MACHINE_ARN:
                try:
                    sfn.start_execution(
                        stateMachineArn=STATE_MACHINE_ARN,
                        name=f"req-{request_id}", # Unique execution name
                        input=json.dumps({
                            "request_id": request_id, 
                            "client_id": client_id,
                            "status": item['status']
                        })
                    )
                except Exception as sfn_err:
                    print(f"Error starting Step Function: {sfn_err}")
                    # We continue because the record is saved
            
            return success({
                "message": "Request submitted successfully",
                "request_id": request_id,
                "status": item['status']
            }, event)
        else:
            return internal_error("Failed to save request to database", event)
            
    except Exception as e:
        print(f"Unhandled error: {e}")
        return internal_error(str(e), event)
