import json
import uuid
import os
import datetime
import boto3
from decimal import Decimal
from common.db import table, get_item, put_item
from common.response import success, bad_request, internal_error, not_found, error
from common.auth import get_effective_role, sanitize_booking_for_role


def sanitize_pet_for_client(item):
    if not isinstance(item, dict):
        return item
    
    sanitized = {
        "pet_id": item.get("pet_id"),
        "name": item.get("name"),
        "species": item.get("species"),
        "breed": item.get("breed"),
        "age": item.get("age"),
        "care_instructions": item.get("care_instructions"),
        "feeding_notes": item.get("feeding_notes"),
        "medication_notes": item.get("medication_notes"),
        "behavior_notes": item.get("behavior_notes"),
    }
    
    if "is_active" in item:
        sanitized["is_active"] = item["is_active"]
        
    health = item.get("health")
    if isinstance(health, dict):
        sanitized_health = {}
        if "vet_name" in health:
            sanitized_health["vet_name"] = health["vet_name"]
        if "vet_phone" in health:
            sanitized_health["vet_phone"] = health["vet_phone"]
        sanitized["health"] = sanitized_health
    
    return sanitized


def handler(event, context):
    try:
        from common.entitlement import require_active_tenant
        block_resp = require_active_tenant(event)
        if block_resp:
            return block_resp

        http_method = event.get('httpMethod')
        path_params = event.get('pathParameters', {}) or {}
        pet_id = path_params.get('petId')

        role = get_effective_role(event)
        path = event.get('path', '')

        # Determine allowed roles
        allowed_roles = ['owner', 'admin', 'staff']
        if path.startswith('/client/'):
            allowed_roles.append('client')

        if role not in allowed_roles:
            if path.startswith('/client/') and role == 'unknown':
                return error(401, "Unauthenticated", event)
            return error(403, "Forbidden", event)

        if http_method == 'GET':
            if path == '/client/pets':
                from common.auth import resolve_client_identity
                client_id = resolve_client_identity(event)
                if not client_id:
                    return success({"pets": [], "message": "No local profile linked", "linked_profile": False}, event)

                from common.auth import get_current_company_id
                company_id = get_current_company_id(event)

                # Security: Validate the client exists under the trusted company
                from common.db import table as items_table
                client_key = {'PK': f"COMPANY#{company_id}", 'SK': f"CLIENT#{client_id}"}
                client_resp = items_table.get_item(Key=client_key)
                if 'Item' not in client_resp:
                    return success({"pets": [], "message": "No local profile linked", "linked_profile": False}, event)

                # Query ClientPetIndex with pagination
                from boto3.dynamodb.conditions import Key
                query_kwargs = {
                    'IndexName': 'ClientPetIndex',
                    'KeyConditionExpression': Key('client_id').eq(client_id)
                }
                items = []
                while True:
                    resp = items_table.query(**query_kwargs)
                    items.extend(resp.get('Items', []))
                    last_key = resp.get('LastEvaluatedKey')
                    if not last_key:
                        break
                    query_kwargs['ExclusiveStartKey'] = last_key

                # Result filtering
                filtered_items = []
                for p in items:
                    if p.get('entity_type') != 'PET':
                        continue
                    p_company = p.get('company_id')
                    if not p_company or p_company != company_id:
                        continue
                    if p.get('is_active') is False:
                        continue
                    filtered_items.append(p)

                sanitized_items = [sanitize_pet_for_client(item) for item in filtered_items]
                return success({"pets": sanitized_items}, event)

            # Release 6F: Admin pet listing for a specific client
            # GET /admin/pets?clientId={client_id} — returns all active pets for the client
            if role in ['owner', 'admin', 'staff'] and not pet_id:
                query_params = event.get('queryStringParameters', {}) or {}
                client_id = query_params.get('clientId')
                include_inactive = query_params.get('includeInactive') == 'true'
                if client_id:
                    from common.auth import get_current_company_id
                    company_id = get_current_company_id(event)

                    # Security: Validate client exists under the trusted company
                    from common.db import table as items_table
                    client_key = {'PK': f"COMPANY#{company_id}", 'SK': f"CLIENT#{client_id}"}
                    client_resp = items_table.get_item(Key=client_key)
                    if 'Item' not in client_resp:
                        return success({"pets": []}, event)

                    # Query ClientPetIndex with pagination
                    from boto3.dynamodb.conditions import Key
                    query_kwargs = {
                        'IndexName': 'ClientPetIndex',
                        'KeyConditionExpression': Key('client_id').eq(client_id)
                    }
                    items = []
                    while True:
                        resp = items_table.query(**query_kwargs)
                        items.extend(resp.get('Items', []))
                        last_key = resp.get('LastEvaluatedKey')
                        if not last_key:
                            break
                        query_kwargs['ExclusiveStartKey'] = last_key

                    # Result filtering
                    filtered_items = []
                    for p in items:
                        if p.get('entity_type') != 'PET':
                            continue
                        p_company = p.get('company_id')
                        if not p_company or p_company != company_id:
                            continue
                        if p.get('is_active') is False and not include_inactive:
                            continue
                        filtered_items.append(p)

                    return success({"pets": filtered_items}, event)

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
                # Release 11E: Indirect PET tenant validation — verify client belongs to caller's company
                from common.auth import get_current_company_id as _get_cid
                from common.db import table as _pet_table
                _cid = _get_cid(event)
                _client_check = _pet_table.get_item(Key={"PK": f"COMPANY#{_cid}", "SK": f"CLIENT#{client_id}"}).get('Item')
                if not _client_check:
                    from common.auth import get_claims as _gc
                    _c = _gc(event)
                    print(f"SECURITY: Cross-tenant PET access attempt by {_c.get('email')} for PET#{pet_id} (client {client_id})")
                    return error(403, "Forbidden", event)
                item = sanitize_booking_for_role(item, role)
                return success(item, event)

            return not_found(f"Pet {pet_id} not found", event)

        elif http_method == 'PUT' and path.startswith('/client/pets/'):
            if role == 'unknown':
                return error(401, "Unauthenticated", event)
            if role != 'client':
                return error(403, "Forbidden: Only clients can access this customer endpoint", event)

            from common.auth import resolve_client_identity
            client_id = resolve_client_identity(event)
            if not client_id:
                return error(403, "Forbidden: No linked client profile", event)

            from common.auth import get_current_company_id
            company_id = get_current_company_id(event)
            if not company_id:
                return error(403, "Forbidden: No tenant context", event)

            if not pet_id:
                return bad_request("Missing petId in path", event)

            existing_pet = get_item(f"PET#{pet_id}", f"CLIENT#{client_id}")
            if not existing_pet or existing_pet.get('is_active') is False or existing_pet.get('company_id') != company_id or existing_pet.get('client_id') != client_id:
                return not_found(f"Pet {pet_id} not found", event)

            # 1. Parse JSON body safely
            raw_body = event.get('body')
            if raw_body is None:
                return bad_request("Missing request body", event)
            
            try:
                body = json.loads(raw_body)
            except Exception:
                return bad_request("Malformed JSON body", event)

            if body is None:
                return bad_request("Request body cannot be null", event)

            if not isinstance(body, dict):
                return bad_request("Request body must be a JSON object", event)

            if not body:
                return bad_request("Request body cannot be empty", event)

            # 2. Field Allowlist validation
            allowed_fields = {'name', 'species', 'breed', 'age', 'care_instructions', 'feeding_notes', 'medication_notes', 'behavior_notes', 'health'}
            for k in body.keys():
                if k not in allowed_fields:
                    return bad_request(f"Field {k} is not allowed to be modified by clients", event)

            # 3. Type & length validation
            limits = {
                'name': 100,
                'species': 100,
                'breed': 100,
                'age': 100,
                'care_instructions': 2000,
                'feeding_notes': 2000,
                'medication_notes': 2000,
                'behavior_notes': 2000
            }
            for field, max_len in limits.items():
                if field in body:
                    val = body[field]
                    if val is not None and not isinstance(val, str):
                        return bad_request(f"Field {field} must be a string", event)
                    if val is not None and len(val) > max_len:
                        return bad_request(f"Field {field} exceeds maximum length of {max_len} characters", event)

            if 'name' in body:
                name_val = body['name']
                if name_val is None or not str(name_val).strip():
                    return bad_request("Name cannot be empty or blank", event)

            # 4. Nested health object validation
            if 'health' in body:
                health_val = body['health']
                if health_val is None:
                    return bad_request("health must be a non-null JSON object", event)
                if not isinstance(health_val, dict):
                    return bad_request("health must be a non-null JSON object", event)
                
                # Check for unknown health keys
                allowed_health_fields = {'vet_name', 'vet_phone'}
                for hk in health_val.keys():
                    if hk not in allowed_health_fields:
                        return bad_request(f"Health field {hk} is not allowed to be modified by clients", event)
                
                # Check types and limits of health fields
                for hk in ['vet_name', 'vet_phone']:
                    if hk in health_val:
                        val = health_val[hk]
                        if val is not None and not isinstance(val, str):
                            return bad_request(f"Health field {hk} must be a string", event)
                        if val is not None and len(val) > 100:
                            return bad_request(f"Health field {hk} exceeds maximum length of 100 characters", event)

            item = existing_pet.copy()
            item['updated_at'] = datetime.datetime.utcnow().isoformat()

            changed_fields = []
            for field in ['name', 'species', 'breed', 'age', 'care_instructions', 'feeding_notes', 'medication_notes', 'behavior_notes']:
                if field in body:
                    if item.get(field) != body[field]:
                        changed_fields.append(field)
                    item[field] = body[field]

            if 'health' in body:
                existing_health = item.get('health') or {}
                if not isinstance(existing_health, dict):
                    existing_health = {}
                new_health = existing_health.copy()
                body_health = body['health'] or {}
                if 'vet_name' in body_health:
                    if existing_health.get('vet_name') != body_health['vet_name']:
                        changed_fields.append('health.vet_name')
                    new_health['vet_name'] = body_health['vet_name']
                if 'vet_phone' in body_health:
                    if existing_health.get('vet_phone') != body_health['vet_phone']:
                        changed_fields.append('health.vet_phone')
                    new_health['vet_phone'] = body_health['vet_phone']
                item['health'] = new_health

            if put_item(item):
                from common.audit import log_action
                try:
                    log_action(
                        event=event,
                        action="CUSTOMER_PET_UPDATE",
                        target_pk=f"PET#{pet_id}",
                        target_sk=f"CLIENT#{client_id}",
                        success=True,
                        metadata={
                            "company_id": company_id,
                            "client_id": client_id,
                            "pet_id": pet_id,
                            "changed_fields": changed_fields
                        }
                    )
                except Exception as log_err:
                    print(f"WARNING: failed to write audit log: {log_err}")

                rebuild_warning = None
                try:
                    from common.pet_profile import _rebuild_pet_summary
                    _rebuild_pet_summary(client_id, company_id)
                except Exception as rebuild_err:
                    print(f"WARNING: failed to rebuild pet summary for client {client_id}: {rebuild_err}")
                    rebuild_warning = "Pet updated successfully, but secondary summary refresh failed."

                response_body = sanitize_pet_for_client(item)
                if rebuild_warning:
                    response_body["_warning"] = rebuild_warning

                return success(response_body, event)

            return internal_error("Failed to save pet record", event)

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

            # Step C: Client tenant validation BEFORE pet existence/ownership check
            from common.db import table as items_table
            client_verify = items_table.get_item(Key={"PK": f"COMPANY#{company_id}", "SK": f"CLIENT#{client_id}"}).get('Item')
            if not client_verify:
                from common.auth import get_claims as _gc
                _cp = _gc(event)
                print(f"SECURITY: Cross-tenant PET write attempt by {_cp.get('email')} for client {client_id}")
                return error(403, "Forbidden", event)

            # Step D: Pet resolution for POST vs PUT
            if http_method == 'POST' or not pet_id or pet_id == 'NEW':
                pet_id = str(uuid.uuid4())
                existing_item = {}
            else:
                existing_item = get_item(f"PET#{pet_id}", f"CLIENT#{client_id}") or {}
                if existing_item:
                    if existing_item.get('client_id') != client_id:
                        return bad_request("Cannot reassign client ownership of a pet", event)
                    if existing_item.get('company_id') and existing_item.get('company_id') != company_id:
                        return error(403, "Forbidden", event)
                else:
                    # Bounded partition-key Query by PK to check if pet exists under another client/tenant
                    from boto3.dynamodb.conditions import Key
                    query_resp = items_table.query(
                        KeyConditionExpression=Key('PK').eq(f"PET#{pet_id}")
                    )
                    items = []
                    if isinstance(query_resp, dict) and "Items" in query_resp:
                        items = query_resp.get('Items', [])

                    if len(items) > 1:
                        return error(500, "Inconsistent pet data state", event)
                    elif len(items) == 1:
                        other_pet = items[0]
                        if other_pet.get('company_id') and other_pet.get('company_id') != company_id:
                            return error(403, "Forbidden", event)
                        if other_pet.get('client_id') != client_id:
                            return bad_request("Cannot reassign client ownership of a pet", event)
                        existing_item = other_pet
                    elif http_method == 'PUT':
                        return not_found(f"Pet {pet_id} not found", event)

            is_new_record = not existing_item
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

            # Hardening new PET creation: default is_active to True on new records when omitted
            if is_new_record and 'is_active' not in body:
                item['is_active'] = True


            editable_fields = [
                'name', 'breed', 'age', 'photo_url', 'care_instructions',
                'behavior', 'logistics', 'health', 'document_links',
                'meet_and_greet_completed', 'meet_and_greet_required',
                'meet_and_greet_scheduled_at', 'meet_and_greet_completed_at',
                'meet_and_greet_notes', 'quote_amount', 'deposit_required',
                'deposit_paid', 'payment_status', 'quote_sent_date',
                'quote_accepted_date', 'quote_notes', 'internal_pricing_notes',
                # Release 4: Per-pet structured fields
                'species', 'feeding_notes', 'medication_notes', 'behavior_notes',
                'vet_notes', 'emergency_notes', 'is_active'
            ]

            for field in editable_fields:
                if field in body:
                    val = body[field]
                    if field in ['quote_amount', 'deposit_amount']:
                        if val in [None, ""]:
                            if field in item:
                                del item[field]
                            continue
                        try:
                            # Convert to Decimal via string to avoid float precision loss
                            val = Decimal(str(val))
                        except Exception:
                            pass # Fallback to original value if casting fails
                    item[field] = val

            if put_item(item):
                if request_id:
                    try:
                        # Release 5B Hotfix 3: Append new pet_id to the REQ record's pet_ids array
                        # so future CareCard loads include the new pet persistently.
                        # Also update the legacy singular pet_id field.
                        table.update_item(
                            Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                            UpdateExpression="SET pet_id = if_not_exists(pet_id, :pid), pet_ids = list_append(if_not_exists(pet_ids, :empty), :new_pid)",
                            ExpressionAttributeValues={
                                ":pid": pet_id,
                                ":new_pid": [pet_id],
                                ":empty": []
                            }
                        )
                        print(f"INFO: [Req:{request_id}] Linked Pet:{pet_id} to pet_ids array")
                    except Exception as link_err:
                        print(f"ERROR: [Req:{request_id}] Failed to link to Pet:{pet_id}: {link_err}")

                return success(item, event)
            return internal_error("Failed to save pet record", event)

        return bad_request(f"Unsupported method: {http_method}", event)

    except Exception as e:
        print(f"Unhandled error in pet_handler: {e}")
        return internal_error(str(e), event)
