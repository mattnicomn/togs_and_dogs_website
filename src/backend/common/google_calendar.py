import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
import boto3
from datetime import datetime
from common.service_contract import SERVICE_METADATA, WINDOW_METADATA
from common.check_in import check_in_window_start

secrets = boto3.client('secretsmanager')

def _get_google_config():
    """Internal: Retrieves Client ID and Secret from Secrets Manager."""
    secret_arn = os.environ.get('GOOGLE_CLIENT_CREDS_NAME')
    try:
        response = secrets.get_secret_value(SecretId=secret_arn)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"ERROR: Failed to retrieve Google client config: {e}")
        return None

def get_tenant_secret_path(company_id):
    """
    Parses GOOGLE_USER_TOKENS_NAME to extract prefix and returns:
    {prefix}/calendar/{company_id}/tokens
    """
    secret_name = os.environ.get('GOOGLE_USER_TOKENS_NAME', 'togs-and-dogs-prod/google/user-tokens')
    path = secret_name
    if ":secret:" in secret_name:
        path = secret_name.split(":secret:")[-1]
    
    parts = path.split('/')
    if not parts:
        prefix = 'togs-and-dogs-prod'
    else:
        prefix = parts[0]
        
    return f"{prefix}/calendar/{company_id}/tokens"

def resolve_google_token_secret_name(company_id=None):
    """
    Resolves the Secrets Manager secret name/path for the given tenant's Google Calendar tokens.
    """
    from common.auth import DEFAULT_COMPANY_ID
    if company_id is None:
        company_id = DEFAULT_COMPANY_ID
        
    # 1. Fetch tenant metadata
    from common.db import get_item
    tenant = get_item(f"TENANT#{company_id}", "METADATA")
    
    # 2. Check if explicit secret ref is configured in metadata
    if tenant and tenant.get("calendar_secret_ref"):
        return tenant.get("calendar_secret_ref")
        
    # 3. Legacy fallback for default tenant
    if company_id == DEFAULT_COMPANY_ID:
        return os.environ.get('GOOGLE_USER_TOKENS_NAME') or 'togs-and-dogs-prod/google/user-tokens'

        
    # 4. Construct path if Google provider is enabled for this tenant
    if tenant and (tenant.get("calendar_provider") == "google" or tenant.get("calendar_enabled") is True):
        return get_tenant_secret_path(company_id)
        
    return None

def _get_stored_tokens(company_id=None):
    """Internal: Retrieves tokens from Secrets Manager."""
    secret_name = resolve_google_token_secret_name(company_id)
    if not secret_name:
        return {}
    try:
        response = secrets.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"INFO: No existing tokens found for tenant {company_id}: {e}")
        return {}

def _save_tokens(new_tokens, company_id=None):
    """Internal: Saves/Updates tokens in Secrets Manager."""
    secret_name = resolve_google_token_secret_name(company_id)
    if not secret_name:
        return False
    existing = _get_stored_tokens(company_id)
    merged = {**existing, **new_tokens}
    
    # Preserve refresh_token if not in new_tokens
    if 'refresh_token' not in new_tokens and 'refresh_token' in existing:
        merged['refresh_token'] = existing['refresh_token']
    
    from datetime import timezone
    merged['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    try:
        secrets.put_secret_value(
            SecretId=secret_name,
            SecretString=json.dumps(merged)
        )
        return True
    except Exception as e:
        print(f"ERROR: Failed to persist refreshed tokens for tenant {company_id}: {e}")
        return False


def _refresh_access_token(tokens, request_id="UNKNOWN", company_id=None):
    """Internal: Refreshes the Google access token."""
    print(f"INFO: [Req:{request_id}] Starting Google access token refresh.")
    refresh_token = tokens.get('refresh_token')
    
    if not refresh_token:
        print(f"ERROR: [Req:{request_id}] No refresh token available.")
        return None
    
    config = _get_google_config()
    if not config:
        return None

    data = urllib.parse.urlencode({
        'client_id': config['client_id'],
        'client_secret': config['client_secret'],
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token'
    }).encode()

    try:
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            _save_tokens(res_data, company_id)
            print(f"SUCCESS: [Req:{request_id}] Google access token refreshed.")
            return res_data['access_token']
    except urllib.error.HTTPError as http_err:
        # Release 6G Phase 0C: Detect invalid_grant (revoked/expired refresh token)
        try:
            error_body = http_err.read().decode()
            error_data = json.loads(error_body)
            error_code = error_data.get('error', '')
        except Exception:
            error_code = ''
            error_body = str(http_err)

        if error_code == 'invalid_grant':
            print(f"CALENDAR_SYNC_TOKEN_REVOKED: [Req:{request_id}] Google refresh token is revoked or expired (invalid_grant). Admin must reconnect Google Calendar.")
            # Mark the stored tokens as revoked so status endpoint reflects reality
            if company_id is not None:
                _mark_token_revoked(request_id, company_id)
            else:
                _mark_token_revoked(request_id)
            return None

        else:
            print(f"ERROR: [Req:{request_id}] Failed to refresh Google token: HTTP {http_err.code} - {error_body}")
            return None
    except Exception as e:
        print(f"ERROR: [Req:{request_id}] Failed to refresh Google token: {e}")
        return None


def _mark_token_revoked(request_id="UNKNOWN", company_id=None):
    """
    Release 6G Phase 0C: Marks the stored Google token as revoked.
    This ensures the /admin/auth/status endpoint returns VALIDATION_FAILED
    and the admin knows they need to reconnect.
    """
    from common.auth import DEFAULT_COMPANY_ID
    if company_id is None:
        company_id = DEFAULT_COMPANY_ID
    try:
        secret_name = resolve_google_token_secret_name(company_id)
        if not secret_name:
            return
        existing = _get_stored_tokens(company_id)
        existing['token_status'] = 'revoked'
        from datetime import timezone
        existing['revoked_at'] = datetime.now(timezone.utc).isoformat()
        existing['revoked_reason'] = 'invalid_grant'
        # Clear the access_token so it's not reused
        existing.pop('access_token', None)
        existing.pop('expires_in', None)
        
        secrets.put_secret_value(
            SecretId=secret_name,
            SecretString=json.dumps(existing)
        )
        print(f"INFO: [Req:{request_id}] Marked Google token as revoked in Secrets Manager for tenant {company_id}.")
    except Exception as e:
        print(f"WARNING: [Req:{request_id}] Failed to mark token as revoked for tenant {company_id}: {e}")


def _get_valid_token(request_id="UNKNOWN", company_id=None):
    """Internal: Gets a valid access token, refreshing if necessary."""
    tokens = _get_stored_tokens(company_id)
    
    # Release 6G Phase 0C: Check if token is marked as revoked
    if tokens.get('token_status') == 'revoked':
        print(f"CALENDAR_SYNC_SKIPPED: [Req:{request_id}] Google token is marked as revoked. Admin must reconnect Google Calendar.")
        return None
    
    access_token = tokens.get('access_token')
    updated_at = tokens.get('updated_at')
    expires_in = tokens.get('expires_in', 3600)

    if access_token and updated_at:
        try:
            # Check if token is still valid (with 5-minute buffer)
            update_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
            if update_time.tzinfo is None:
                from datetime import timezone
                update_time = update_time.replace(tzinfo=timezone.utc)
            
            from datetime import timezone
            elapsed = (datetime.now(timezone.utc) - update_time).total_seconds()
            if elapsed < (expires_in - 300):
                print(f"INFO: [Req:{request_id}] Using cached Google access token.")
                return access_token
        except Exception as e:
            print(f"WARNING: Token expiry check failed: {e}")

    return _refresh_access_token(tokens, request_id, company_id)

SERVICE_DURATIONS = {
    service_type: metadata["durationMinutes"]
    for service_type, metadata in SERVICE_METADATA.items()
}

WINDOW_START_HOURS = {
    'MORNING': 8, 'MIDDAY': 11, 'AFTERNOON': 14, 'EVENING': 17,
}

SERVICE_COLORS = {
    'WALK_30MIN': '9', 'WALK_60MIN': '9', 'DROPIN_1HR': '7',
    'DROPIN_3HR': '7', 'OVERNIGHT': '6', 'PET_SITTING': '10', 'MEET_GREET': '3',
}

FRIENDLY_SERVICE_NAMES = {
    service_type: metadata["label"]
    for service_type, metadata in SERVICE_METADATA.items()
}

def _build_event_body(item, assigned_worker=None):
    """
    Internal: Builds Google Calendar event resource with strict timing support.
    Returns (body, skip_reason)
    """
    client_name = item.get('client_name', 'Unknown')
    pet_names = item.get('pet_names') or item.get('pet_name', 'Unknown Pet')
    service_type = item.get('service_type', 'Service')
    request_id = item.get('request_id') or item.get('PK', '').replace('REQ#', '').replace('JOB#', '')

    # Validation check for required fields
    if not request_id:
        return None, "missing_required_fields (request_id)"
    if not client_name or client_name == 'Unknown':
        return None, "missing_required_fields (client_name)"
    if not pet_names or pet_names == 'Unknown Pet':
        return None, "missing_required_fields (pet_names)"

    scheduled_time = item.get('scheduled_time')
    scheduled_date = item.get('scheduled_date') or item.get('start_date')
    duration_mins = int(item.get('scheduled_duration') or SERVICE_DURATIONS.get(service_type, 60))
    color_id = SERVICE_COLORS.get(service_type, '8')
    friendly_service_name = FRIENDLY_SERVICE_NAMES.get(service_type, service_type)

    resolved_start_time = None
    window_label = "All Day"

    if not scheduled_time:
        windows = item.get('visit_windows') or []
        if not windows:
            single_window = item.get('visit_window', 'ANYTIME')
            windows = [single_window] if single_window else ['ANYTIME']

        if service_type == 'CHECK_IN':
            for w in windows:
                canonical_start = check_in_window_start(w)
                if canonical_start:
                    resolved_start_time = canonical_start
                    window_label = WINDOW_METADATA[w]['label']
                    break
        else:
            # Historical scheduling compatibility. Walk/Overnight policy remains
            # unresolved; do not apply the new Check-In timing model to them.
            for w in windows:
                if w in WINDOW_START_HOURS:
                    resolved_start_time = f"{WINDOW_START_HOURS[w]:02d}:00"
                    window_label = w.capitalize()
                    break
    else:
        window_label = "Exact Time"

    summary = f"🐾 {pet_names} \u2014 {friendly_service_name} ({window_label})"

    client_phone = item.get('client_phone', '')
    phone_line = f"Phone: {client_phone}\n" if client_phone else ""
    
    source = item.get('source', '')
    source_label = "Admin Created" if source == 'admin_created' else "Client Booking"

    timing_note = "⏰ Estimated from booking window\n" if resolved_start_time is not None else ""

    description = (
        f"Client: {client_name}\n"
        f"{phone_line}"
        f"Pet(s): {pet_names}\n"
        f"Service: {friendly_service_name}\n"
        f"Window: {window_label}\n"
        f"Staff: {assigned_worker or 'Not Assigned'}\n\n"
        f"Notes: {item.get('pet_info', 'None')}\n"
        f"{timing_note}\n"
        f"---\n"
        f"Request ID: {request_id}\n"
        f"Source: {source_label}"
    )

    timezone = 'America/New_York'

    if not scheduled_date:
        return None, "missing_required_fields (scheduled_date)"

    # Case 1: Exact explicit time
    if scheduled_time:
        try:
            time_part = scheduled_time
            if len(time_part) == 5: # HH:MM
                time_part += ":00"
            start_dt_str = f"{scheduled_date}T{time_part}"
            start_dt = datetime.fromisoformat(start_dt_str)
            
            from datetime import timedelta
            end_dt = start_dt + timedelta(minutes=duration_mins)
            
            body = {
                'summary': summary,
                'description': description,
                'colorId': color_id,
                'start': { 'dateTime': start_dt.isoformat(), 'timeZone': timezone },
                'end': { 'dateTime': end_dt.isoformat(), 'timeZone': timezone }
            }
            return body, None
        except Exception as e:
            print(f"WARNING: Failed to parse exact timing ({scheduled_date} {scheduled_time}): {e}")
            return None, "invalid_time_format"

    # Case 2: Inferred time from visit window
    elif resolved_start_time is not None:
        try:
            start_dt_str = f"{scheduled_date}T{resolved_start_time}:00"
            start_dt = datetime.fromisoformat(start_dt_str)
            
            from datetime import timedelta
            end_dt = start_dt + timedelta(minutes=duration_mins)
            
            body = {
                'summary': summary,
                'description': description,
                'colorId': color_id,
                'start': { 'dateTime': start_dt.isoformat(), 'timeZone': timezone },
                'end': { 'dateTime': end_dt.isoformat(), 'timeZone': timezone }
            }
            return body, None
        except Exception as e:
            print(f"WARNING: Failed to parse window timing ({scheduled_date} {resolved_start_time}): {e}")
            return None, "invalid_time_format"

    # Case 3: All-day fallback
    try:
        datetime.strptime(scheduled_date, '%Y-%m-%d')
        from datetime import timedelta
        start_date_obj = datetime.strptime(scheduled_date, '%Y-%m-%d')
        end_date_str = (start_date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
        
        body = {
            'summary': summary,
            'description': description,
            'colorId': color_id,
            'start': {'date': scheduled_date},
            'end': {'date': end_date_str}
        }
        return body, None
    except (ValueError, TypeError) as e:
        print(f"WARNING: Failed to create all-day event for date '{scheduled_date}': {e}")
        return None, "invalid_date_format"

# Release 6G Phase 4: Transient error codes eligible for retry
_RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
_MAX_RETRY_ATTEMPTS = 2
_RETRY_BACKOFF_SECONDS = [0.5, 1.5]


def _is_retryable_error(error):
    """Determines if an error is transient and eligible for retry."""
    if isinstance(error, urllib.error.HTTPError):
        return error.code in _RETRYABLE_HTTP_CODES
    if isinstance(error, (urllib.error.URLError, OSError, TimeoutError)):
        return True
    return False


def _execute_calendar_api(url, method, data, token, request_id):
    """
    Executes a single Google Calendar API call.
    Returns (result_dict, None) on success, or (None, error) on failure.
    """
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', f'Bearer {token}')
    req.add_header('Content-Type', 'application/json')

    with urllib.request.urlopen(req, timeout=10) as response:
        res_data = json.loads(response.read().decode())
        return res_data, None


def sync_calendar_event(item, google_event_id=None, assigned_worker=None):
    """
    Creates or updates a Google Calendar event.
    Returns: { "status": str, "event_id": str, "message": str }
    """
    request_id = item.get('request_id') or item.get('PK', '').replace('REQ#', '').replace('JOB#', 'UNKNOWN')
    company_id = item.get('company_id')
    
    try:
        from common.google_calendar import resolve_google_token_secret_name
        secret_name = resolve_google_token_secret_name(company_id)
        token = _get_valid_token(request_id, company_id)
        if not token:
            if not secret_name:
                print(f"CALENDAR_SYNC_SKIPPED: [Req:{request_id}] Google Calendar not configured for this tenant.")
                return {
                    "status": "calendar_skipped",
                    "message": "Google Calendar integration not configured for this tenant."
                }
            else:
                print(f"CALENDAR_SYNC_FAILED: [Req:{request_id}] No valid token available (disconnected or revoked).")
                return {
                    "status": "calendar_failed",
                    "message": "Google Calendar disconnected or token expired."
                }

    except Exception as e:
        print(f"CALENDAR_SYNC_FAILED: [Req:{request_id}] Auth error: {e}")
        return {
            "status": "calendar_failed",
            "message": f"Auth error: {str(e)}"
        }

    event_body, skip_reason = _build_event_body(item, assigned_worker)
    if skip_reason:
        print(f"CALENDAR_SYNC_SKIPPED: [Req:{request_id}] Reason: {skip_reason}")
        return {
            "status": f"calendar_skipped_{skip_reason}",
            "message": f"Calendar sync skipped: {skip_reason.replace('_', ' ')}."
        }
    
    # CHECK_IN child jobs may provide a stable, API-compatible event ID. Google
    # treats a repeated insert of that ID as a conflict rather than a duplicate.
    requested_event_id = item.get('calendar_event_id') if not google_event_id else None
    if requested_event_id:
        event_body['id'] = requested_event_id

    # Determine URL and method
    if google_event_id:
        print(f"INFO: [Req:{request_id}] Updating Calendar Event: {google_event_id}")
        url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{google_event_id}"
        method = 'PUT'
    else:
        print(f"INFO: [Req:{request_id}] Creating new Calendar Event.")
        url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
        method = 'POST'

    data = json.dumps(event_body).encode('utf-8')

    # Release 6G Phase 4: Retry loop for transient errors
    last_error = None
    for attempt in range(_MAX_RETRY_ATTEMPTS + 1):  # 0 = first attempt, 1-2 = retries
        try:
            res_data, _ = _execute_calendar_api(url, method, data, token, request_id)
            new_id = res_data.get('id')
            action = "calendar_updated" if google_event_id else "calendar_created"
            
            if attempt > 0:
                print(f"CALENDAR_SYNC_RETRY_SUCCESS: [Req:{request_id}] Succeeded on attempt {attempt + 1}")
            
            print(f"CALENDAR_SYNC_SUCCESS: [Req:{request_id}] Event {action.split('_')[1]} (id: {new_id})")
            return {
                "status": action,
                "event_id": new_id,
                "message": f"Calendar event {action.split('_')[1]}."
            }

        except urllib.error.HTTPError as he:
            err_body = he.read().decode()

            if he.code == 409 and requested_event_id:
                print(
                    f"INFO: [Req:{request_id}] Deterministic Calendar Event "
                    f"already exists: {requested_event_id}"
                )
                return {
                    "status": "calendar_existing",
                    "event_id": requested_event_id,
                    "message": "Calendar event already exists."
                }
            
            # Handle 404 if event was deleted externally (not retryable — re-create instead)
            if he.code == 404 and google_event_id:
                print(f"WARNING: [Req:{request_id}] Event {google_event_id} not found, attempting re-creation.")
                return sync_calendar_event(item, google_event_id=None, assigned_worker=assigned_worker)
            
            # Check if retryable
            if _is_retryable_error(he) and attempt < _MAX_RETRY_ATTEMPTS:
                print(f"CALENDAR_SYNC_RETRY_ATTEMPT: [Req:{request_id}] Transient error (HTTP {he.code}), retry {attempt + 1}/{_MAX_RETRY_ATTEMPTS}")
                time.sleep(_RETRY_BACKOFF_SECONDS[attempt])
                last_error = f"Google API Error {he.code}: {err_body}"
                continue
            
            # Non-retryable or retries exhausted
            error_msg = f"Google API Error {he.code}: {err_body}"
            if attempt > 0:
                print(f"CALENDAR_SYNC_RETRY_EXHAUSTED: [Req:{request_id}] Failed after {attempt + 1} attempts. Last error: {error_msg}")
            print(f"CALENDAR_SYNC_FAILED: [Req:{request_id}] {error_msg}")
            return {
                "status": "calendar_failed",
                "message": error_msg
            }

        except (urllib.error.URLError, OSError, TimeoutError) as net_err:
            # Network/timeout errors — retryable
            if attempt < _MAX_RETRY_ATTEMPTS:
                print(f"CALENDAR_SYNC_RETRY_ATTEMPT: [Req:{request_id}] Network error ({type(net_err).__name__}), retry {attempt + 1}/{_MAX_RETRY_ATTEMPTS}")
                time.sleep(_RETRY_BACKOFF_SECONDS[attempt])
                last_error = str(net_err)
                continue
            
            if attempt > 0:
                print(f"CALENDAR_SYNC_RETRY_EXHAUSTED: [Req:{request_id}] Failed after {attempt + 1} attempts. Last error: {net_err}")
            print(f"CALENDAR_SYNC_FAILED: [Req:{request_id}] {net_err}")
            return {
                "status": "calendar_failed",
                "message": str(net_err)
            }

        except Exception as e:
            # Unexpected errors — do not retry
            print(f"CALENDAR_SYNC_FAILED: [Req:{request_id}] {e}")
            return {
                "status": "calendar_failed",
                "message": str(e)
            }

    # Should not reach here, but safety fallback
    print(f"CALENDAR_SYNC_FAILED: [Req:{request_id}] Exhausted all attempts. Last: {last_error}")
    return {"status": "calendar_failed", "message": last_error or "Unknown error"}


def delete_event_detailed(google_event_id, request_id="UNKNOWN", company_id=None):
    """
    Deletes a Google Calendar event and returns detailed status:
    (success, already_gone, error_str)
    """
    token = _get_valid_token(request_id, company_id)
    if not token:
        return True, True, "Not configured"

    try:
        url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{google_event_id}"
        req = urllib.request.Request(url, method='DELETE')
        req.add_header('Authorization', f'Bearer {token}')

        with urllib.request.urlopen(req) as response:
            print(f"SUCCESS: [Req:{request_id}] Deleted Calendar Event: {google_event_id}")
            return True, False, None

    except urllib.error.HTTPError as he:
        if he.code in [404, 410]:
            print(f"INFO: [Req:{request_id}] Calendar event {google_event_id} is already gone (HTTP {he.code}).")
            return True, True, None
        err_msg = f"HTTP Error {he.code}: {he.reason}"
        print(f"ERROR: [Req:{request_id}] Failed to delete Calendar event {google_event_id}: {err_msg}")
        return False, False, err_msg
    except Exception as e:
        err_msg = str(e)
        print(f"ERROR: [Req:{request_id}] Failed to delete Calendar event {google_event_id}: {err_msg}")
        return False, False, err_msg


def delete_event(google_event_id, request_id="UNKNOWN", company_id=None):
    """Deletes a Google Calendar event (backward compatible wrapper)."""
    success, _, _ = delete_event_detailed(google_event_id, request_id, company_id)
    return success
