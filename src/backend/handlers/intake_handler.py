import json
import uuid
import os
import boto3
from datetime import datetime
from common.db import put_item, get_item, table
from common.response import success, bad_request, internal_error, error
from common.status import RequestStatus, WorkflowType
from common.notifications import notify_event

sfn = boto3.client('stepfunctions')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

# Release 2: Valid visit window values for multi-select validation.
VALID_VISIT_WINDOWS = ['MORNING', 'MIDDAY', 'AFTERNOON', 'EVENING', 'ANYTIME']


def _handle_staff_options(event):
    """
    Release 2: Public staff-options endpoint for preferred sitter selection.
    
    Security: Returns ONLY display_name and a safe public identifier (staff_id).
    Does NOT expose: email, Cognito username, phone, internal role, permissions,
    or protected admin metadata.
    
    This endpoint is accessible without authentication so that public intake
    form users (existing clients not logged in) can express a sitter preference.
    """
    from common.auth import get_current_company_id
    from boto3.dynamodb.conditions import Key

    try:
        company_id = get_current_company_id(event)

        response = table.query(
            KeyConditionExpression=Key('PK').eq(f"COMPANY#{company_id}") & Key('SK').begins_with("STAFF#")
        )
        staff_profiles = response.get('Items', [])

        # Filter to active, assignable staff only.
        # Return ONLY safe public fields: staff_id and display_name.
        options = []
        for s in staff_profiles:
            if s.get('is_active') == True and s.get('is_assignable') != False:
                options.append({
                    "id": s.get('staff_id', ''),
                    "name": s.get('display_name', 'Staff Member')
                })

        return success({"staff_options": options}, event)

    except Exception as e:
        print(f"Error fetching staff options: {e}")
        # Fail gracefully — return empty list, don't block intake
        return success({"staff_options": []}, event)


def _normalize_visit_windows(body):
    """
    Release 2: Normalizes visit window input to a consistent array format.
    
    Accepts:
    - visit_windows: ["MORNING", "AFTERNOON"] (new multi-select format)
    - visit_window: "MORNING" (legacy single-select format)
    
    Returns: List of valid window values. Defaults to ["ANYTIME"].
    ANYTIME is mutually exclusive with specific windows.
    """
    # Prefer the new array field
    windows = body.get('visit_windows')
    
    if windows and isinstance(windows, list):
        # Validate and sanitize
        valid = [w for w in windows if w in VALID_VISIT_WINDOWS]
        if not valid:
            return ['ANYTIME']
        # ANYTIME is mutually exclusive — if present with others, keep only ANYTIME
        if 'ANYTIME' in valid and len(valid) > 1:
            return ['ANYTIME']
        return valid
    
    # Fallback to legacy single value
    single = body.get('visit_window', 'ANYTIME')
    if single in VALID_VISIT_WINDOWS:
        return [single]
    return ['ANYTIME']


def _generate_pet_names_string(body):
    """
    Release 4: Generates legacy pet_names string from pets array for backward compatibility.
    
    If pets array exists, joins pet names with commas.
    Otherwise falls back to the raw pet_names field from the body.
    """
    pets = body.get('pets')
    if pets and isinstance(pets, list) and len(pets) > 0:
        names = [p.get('name', '').strip() for p in pets if p.get('name', '').strip()]
        if names:
            return ', '.join(names)
    # Fallback to legacy field
    return body.get('pet_names') or ''

def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        
        # Release 2: Public staff-options endpoint for preferred sitter selection.
        # Returns only display names of active/assignable staff. No sensitive data exposed.
        # Accessible without authentication via POST /requests with action: "staff-options".
        if body.get('action') == 'staff-options':
            return _handle_staff_options(event)
        
        client_name = body.get('client_name')
        client_email = body.get('client_email')
        start_date = body.get('start_date')
        pet_names = body.get('pet_names')
        
        from common.auth import get_effective_role, resolve_client_identity, get_claims, get_current_company_id
        role = get_effective_role(event)
        client_id = body.get('client_id')
        company_id = get_current_company_id(event)
        
        is_portal_path = event.get('path', '') == '/client/requests'
        workflow_type = WorkflowType.CUSTOMER_INTAKE
        
        if is_portal_path and role == 'client':
            resolved_id = resolve_client_identity(event)
            if resolved_id:
                client_id = resolved_id
                claims = get_claims(event)
                client_email = claims.get('email') or client_email
                
                # Check if the client is APPROVED
                client_profile = get_item(f"COMPANY#{company_id}", f"CLIENT#{client_id}")
                if not client_profile:
                    # Fallback check if PK/SK are different for clients
                    client_profile = get_item(f"CLIENT#{client_id}", "METADATA")
                
                # Heuristic for "Approved": is_active=True AND portal_enabled=True
                # Also check meet_and_greet_completed as an extra indicator of onboarding success
                is_approved = client_profile and client_profile.get('is_active') and client_profile.get('portal_enabled')
                
                if not is_approved:
                    return error(403, "Your profile is still under review. Once approved, you’ll be able to request visits from your client portal.", event)
                
                workflow_type = WorkflowType.VISIT_BOOKING
            else:
                return error(403, "You must have a linked client profile to request visits.", event)
        elif is_portal_path and role != 'client':
             # Admin/Staff hitting portal path - allow as VISIT_BOOKING
             workflow_type = WorkflowType.VISIT_BOOKING
        else:
            # Public path /requests
            workflow_type = WorkflowType.CUSTOMER_INTAKE
        
        # Basic validation for required fields (non-empty, non-whitespace)
        # Release 4A Hotfix: Generate pet_names from pets[] BEFORE validation.
        # The frontend sends pets[] array instead of pet_names string.
        # We must normalize first so validation doesn't reject valid multi-pet submissions.
        pet_names = body.get('pet_names')
        if not pet_names or not pet_names.strip():
            pet_names = _generate_pet_names_string(body)
        
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
        
        client_id = client_id or body.get('client_id', str(uuid.uuid4()))

        # Create the Request record
        item = {
            'PK': f"REQ#{request_id}",
            'SK': f"CLIENT#{client_id}",
            'company_id': company_id,
            'request_id': request_id,
            'client_id': client_id,

            'client_name': client_name,
            'client_email': client_email,
            # Release 4C: Client phone — optional, stored for admin visibility and profile propagation.
            'client_phone': (body.get('client_phone') or '').strip() or None,
            'start_date': start_date,
            'end_date': body.get('end_date'),
            # Release 2: visit_windows (array) for multi-select support.
            # Legacy visit_window (string) preserved for backward compatibility.
            'visit_window': body.get('visit_window', 'ANYTIME'),
            'visit_windows': _normalize_visit_windows(body),
            'preferred_time': body.get('preferred_time'),
            'timing_notes': body.get('timing_notes'),
            # Release 2: Preferred sitter — informational only, does NOT auto-assign.
            'preferred_sitter': body.get('preferred_sitter') or None,
            'preferred_sitter_name': body.get('preferred_sitter_name') or None,
            # Release 4: Multi-pet structured data.
            # pets array stores per-pet fields. Legacy pet_names auto-generated for backward compat.
            'pets': body.get('pets') or None,
            'pet_names': pet_names,  # Already generated/normalized before validation
            'pet_info': body.get('pet_info'),
            # Release 4: Household-level vet/emergency info.
            'vet_info': body.get('vet_info') or None,
            'emergency_contact_info': body.get('emergency_contact') or None,
            'service_type': body.get('service_type', 'PET_SITTING'),
            'status': RequestStatus.PENDING_REVIEW.value,
            'workflow_type': workflow_type.value,
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
            
            # Phase 3A: Trigger Notification (Dry Run / Configurable)
            if workflow_type == WorkflowType.CUSTOMER_INTAKE:
                notify_event('REQUEST_RECEIVED', item)
            
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
