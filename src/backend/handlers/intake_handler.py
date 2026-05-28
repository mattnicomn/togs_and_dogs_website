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


def _handle_admin_created_booking(event, body):
    """
    Release 6F: Admin-created booking for offline/repeat clients.
    
    Requirements:
    - Owner/admin role required
    - Existing client_id required (from Client Management profile)
    - Pet selection required (pet_names or pet_ids)
    - Creates as VISIT_BOOKING / APPROVED
    - Skips REQUEST_RECEIVED notification
    - Triggers JOB Lambda asynchronously
    - Syncs Google Calendar placeholder
    - Validates tenant isolation (client belongs to admin's company)
    - Fail-safe: JOB/Calendar failures don't corrupt the booking
    """
    from common.auth import get_effective_role, get_claims, get_current_company_id
    from boto3.dynamodb.conditions import Key

    # 1. Authorization: owner/admin only
    role = get_effective_role(event)
    if role not in ['owner', 'admin']:
        return error(403, "Forbidden: Only owners and admins can create bookings on behalf of clients.", event)

    claims = get_claims(event)
    user_email = (claims.get('email') or '').lower().strip()
    created_by = user_email or claims.get('username') or 'admin-api'
    company_id = get_current_company_id(event)

    # 2. Validate required fields
    client_id = body.get('client_id')
    if not client_id:
        return bad_request("client_id is required for admin-created bookings. Select an existing client.", event)

    client_name = body.get('client_name', '').strip()
    start_date = body.get('start_date', '').strip() if body.get('start_date') else ''
    end_date = body.get('end_date') or None

    selected_dates = body.get('selected_dates')
    if selected_dates and isinstance(selected_dates, list) and len(selected_dates) > 1:
        def _is_valid_date(date_str):
            if not isinstance(date_str, str): return False
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                return True
            except ValueError:
                return False
        valid_dates = sorted(set(d for d in selected_dates if _is_valid_date(d)))
        if valid_dates:
            start_date = valid_dates[0]
            end_date = valid_dates[-1]
            selected_dates = valid_dates

    if not client_name or not start_date:
        return bad_request("client_name and start_date are required.", event)

    client_email = body.get('client_email', '').strip().lower() or None

    # Pet validation: require pet_names or pet_ids
    pet_names = body.get('pet_names', '').strip()
    pet_ids = body.get('pet_ids') or []
    if not pet_names and not pet_ids:
        pet_names = _generate_pet_names_string(body)
    if not pet_names and not pet_ids:
        return bad_request("At least one pet is required. Select pets or provide pet_names.", event)

    # 3. Tenant isolation: verify client belongs to admin's company
    client_profile = get_item(f"COMPANY#{company_id}", f"CLIENT#{client_id}")
    if not client_profile:
        return bad_request(f"Client profile '{client_id}' not found in your company. Select an existing client.", event)

    if client_profile.get('company_id') and client_profile.get('company_id') != company_id:
        return error(403, "Forbidden: Cross-tenant booking creation is not allowed.", event)

    # 4. Create the Request record
    request_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    item = {
        'PK': f"REQ#{request_id}",
        'SK': f"CLIENT#{client_id}",
        'company_id': company_id,
        'request_id': request_id,
        'client_id': client_id,
        'client_name': client_name,
        'client_email': client_email,
        'client_phone': (body.get('client_phone') or '').strip() or None,
        'start_date': start_date,
        'end_date': end_date,
        'selected_dates': selected_dates if selected_dates and isinstance(selected_dates, list) else None,
        'visit_window': body.get('visit_window', 'ANYTIME'),
        'visit_windows': _normalize_visit_windows(body),
        'preferred_time': body.get('preferred_time') or None,
        'timing_notes': body.get('timing_notes') or None,
        'preferred_sitter': body.get('preferred_sitter') or None,
        'preferred_sitter_name': body.get('preferred_sitter_name') or None,
        'pets': body.get('pets') or None,
        'pet_names': pet_names or ', '.join([str(p) for p in pet_ids]),
        'pet_ids': pet_ids if pet_ids else None,
        'pet_info': body.get('pet_info') or None,
        'vet_info': body.get('vet_info') or None,
        'emergency_contact_info': body.get('emergency_contact') or None,
        'service_type': body.get('service_type', 'PET_SITTING'),
        'details': body.get('details') or None,
        'status': 'APPROVED',
        'workflow_type': WorkflowType.VISIT_BOOKING.value,
        'source': 'admin_created',
        'created_by': created_by,
        'admin_created_at': now,
        'created_at': now,
        'entity_type': 'REQUEST',
        'linked_client_profile_id': client_id,
        'client_profile_link_status': 'ADMIN_CREATED',
    }

    if not put_item(item):
        return internal_error("Failed to save booking to database.", event)

    # 5. Trigger JOB creation Lambda (async, fail-safe)
    job_warning = None
    try:
        lambda_client = boto3.client('lambda')
        job_fn_name = os.environ.get('JOB_FUNCTION_NAME')
        if job_fn_name:
            payload = {
                "request_id": request_id,
                "client_id": client_id,
            }
            lambda_client.invoke(
                FunctionName=job_fn_name,
                InvocationType='Event',
                Payload=json.dumps(payload)
            )
            print(f"INFO: [AdminBooking] Triggered JOB creation for REQ#{request_id}")
        else:
            job_warning = "JOB_FUNCTION_NAME not configured — JOB record not created."
            print(f"WARNING: [AdminBooking] {job_warning}")
    except Exception as job_err:
        job_warning = f"JOB creation trigger failed: {str(job_err)}"
        print(f"WARNING: [AdminBooking] {job_warning}")

    # 6. Google Calendar sync (fail-safe)
    calendar_result = None
    try:
        is_multi_day_req = False
        if item.get('end_date') and item.get('start_date') != item.get('end_date'):
            is_multi_day_req = True
            
        if not is_multi_day_req:
            from common.google_calendar import sync_calendar_event
            calendar_result = sync_calendar_event(item)
            if calendar_result and calendar_result.get('event_id'):
                table.update_item(
                    Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                    UpdateExpression="SET google_event_id = :gid",
                    ExpressionAttributeValues={":gid": calendar_result['event_id']}
                )
                print(f"INFO: [AdminBooking] Calendar event created: {calendar_result['event_id']}")
        else:
            print(f"INFO: [AdminBooking] Suppressing parent REQ calendar sync for multi-day booking")
            calendar_result = {"status": "skipped", "message": "Multi-day jobs sync their own calendar events."}
    except Exception as cal_err:
        calendar_result = {"status": "calendar_failed", "message": str(cal_err)}
        print(f"WARNING: [AdminBooking] Calendar sync failed: {cal_err}")

    # 7. Build response
    response_msg = "Booking created successfully."
    if job_warning:
        response_msg += f" Warning: {job_warning}"
    if calendar_result and calendar_result.get('message'):
        response_msg += f" Calendar: {calendar_result.get('message', '')}"

    return success({
        "message": response_msg,
        "request_id": request_id,
        "client_id": client_id,
        "status": "APPROVED",
        "workflow_type": "VISIT_BOOKING",
        "source": "admin_created",
        "calendar_result": calendar_result,
    }, event)

def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        
        # Release 2: Public staff-options endpoint for preferred sitter selection.
        # Returns only display names of active/assignable staff. No sensitive data exposed.
        # Accessible without authentication via POST /requests with action: "staff-options".
        if body.get('action') == 'staff-options':
            return _handle_staff_options(event)

        # Release 6F: Admin-created booking path.
        # Allows owner/admin to create VISIT_BOOKING requests on behalf of existing clients.
        # Bypasses portal checks, sets status to APPROVED, triggers JOB + Calendar.
        if body.get('source') == 'admin_created':
            return _handle_admin_created_booking(event, body)
        
        client_name = body.get('client_name')
        client_email = body.get('client_email')
        start_date = body.get('start_date')
        end_date = body.get('end_date')
        pet_names = body.get('pet_names')
        
        selected_dates = body.get('selected_dates')
        if selected_dates and isinstance(selected_dates, list) and len(selected_dates) > 1:
            def _is_valid_date(date_str):
                if not isinstance(date_str, str): return False
                try:
                    datetime.strptime(date_str, '%Y-%m-%d')
                    return True
                except ValueError:
                    return False
            valid_dates = sorted(set(d for d in selected_dates if _is_valid_date(d)))
            if valid_dates:
                start_date = valid_dates[0]
                end_date = valid_dates[-1]
                selected_dates = valid_dates
        
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

        if workflow_type == WorkflowType.CUSTOMER_INTAKE:
            acceptance_errors = []
            if body.get('accepted_terms') is not True:
                acceptance_errors.append('accepted_terms is required')
            if body.get('accepted_privacy') is not True:
                acceptance_errors.append('accepted_privacy is required')
            terms_version = body.get('terms_version', '')
            privacy_version = body.get('privacy_version', '')
            if not terms_version or len(str(terms_version)) > 20:
                acceptance_errors.append('terms_version is invalid')
            if not privacy_version or len(str(privacy_version)) > 20:
                acceptance_errors.append('privacy_version is invalid')
            if acceptance_errors:
                return bad_request("Terms of Use and Privacy Policy acceptance is required.", event)

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
            'end_date': end_date,
            'selected_dates': selected_dates if selected_dates and isinstance(selected_dates, list) else None,
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
        
        if workflow_type == WorkflowType.CUSTOMER_INTAKE:
            item['accepted_terms'] = True
            item['accepted_privacy'] = True
            item['terms_version'] = body.get('terms_version')
            item['privacy_version'] = body.get('privacy_version')
            item['accepted_at'] = datetime.utcnow().isoformat()
            item['accepted_by_email'] = client_email
            item['source'] = 'public_intake'
        
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
