import json
import uuid
import os
import datetime
import boto3
from common.db import table, get_item, put_item
from common.response import success, bad_request, internal_error, not_found, error
from common.auth import get_effective_role, sanitize_booking_for_role


def handler(event, context):
    try:
        http_method = event.get('httpMethod')
        path_params = event.get('pathParameters', {}) or {}
        pet_id = path_params.get('petId')
        
        role = get_effective_role(event)
        if role not in ['owner', 'admin', 'staff']:
            return error(403, "Forbidden", event)
            
        if http_method == 'GET':

            if not pet_id:
                return bad_request("Missing petId in path", event)
            
            # Need client_id for SK. In dispatcher view, we likely have it.
            # If not provided, we might need a GSI lookup by PET_ID (PK) if it's unique across clients.
            # For now, assume client_id is passed as query param.
            client_id = (event.get('queryStringParameters', {}) or {}).get('clientId')
            if not client_id:
                return bad_request("Missing clientId in query params", event)
            
            item = get_item(f"PET#{pet_id}", f"CLIENT#{client_id}")
            if item:
                item = sanitize_booking_for_role(item, role)
                return success(item, event)

            return not_found(f"Pet {pet_id} not found", event)

        elif http_method == 'POST' or http_method == 'PUT':
            role = get_effective_role(event)
            if role not in ['owner', 'admin', 'staff']:
                return error(403, "Forbidden", event)
                
            body = json.loads(event.get('body', '{}'))
            client_id = body.get('client_id')
            request_id = body.get('request_id') # Extract request_id if passed
            
            if role == 'staff':
                sensitive_fields = ['meet_and_greet_notes', 'internal_pricing_notes', 'quote_amount', 'deposit_required']
                for field in sensitive_fields:
                    if field in body:
                        del body[field]

            
            if not client_id:
                return bad_request("Missing client_id in body", event)
            
            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)

            if not pet_id or pet_id == 'NEW':
                pet_id = str(uuid.uuid4())
                existing_item = {}
            else:
                existing_item = get_item(f"PET#{pet_id}", f"CLIENT#{client_id}") or {}
            
            item = existing_item.copy()
            item.update({
                'PK': f"PET#{pet_id}",
                'SK': f"CLIENT#{client_id}",
                'company_id': item.get('company_id') or company_id,
                'pet_id': pet_id,
                'client_id': client_id,
                'entity_type': 'PET',
                'updated_at': datetime.datetime.utcnow().isoformat()
            })

            
            editable_fields = [
                'name', 'breed', 'age', 'photo_url', 'care_instructions',
                'behavior', 'logistics', 'health', 'document_links', 
                'meet_and_greet_completed', 'meet_and_greet_required', 
                'meet_and_greet_scheduled_at', 'meet_and_greet_completed_at', 
                'meet_and_greet_notes', 'quote_amount', 'deposit_required', 
                'deposit_paid', 'payment_status', 'quote_sent_date', 
                'quote_accepted_date', 'quote_notes', 'internal_pricing_notes'
            ]
            
            for field in editable_fields:
                if field in body:
                    item[field] = body[field]
            
            if put_item(item):
                if request_id:
                    try:
                        table.update_item(
                            Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                            UpdateExpression="SET pet_id = :pid",
                            ExpressionAttributeValues={":pid": pet_id}
                        )
                        print(f"INFO: [Req:{request_id}] Linked to Pet:{pet_id}")
                    except Exception as link_err:
                        print(f"ERROR: [Req:{request_id}] Failed to link to Pet:{pet_id}: {link_err}")
                
                return success(item, event)
            return internal_error("Failed to save pet record", event)

        return bad_request(f"Unsupported method: {http_method}", event)
            
    except Exception as e:
        print(f"Unhandled error in pet_handler: {e}")
        return internal_error(str(e), event)
