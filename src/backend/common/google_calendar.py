import json
import os
import time
import urllib.request
import urllib.parse
import boto3
from datetime import datetime

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

def _get_stored_tokens():
    """Internal: Retrieves tokens from Secrets Manager."""
    secret_name = os.environ.get('GOOGLE_USER_TOKENS_NAME')
    try:
        response = secrets.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"INFO: No existing tokens found: {e}")
        return {}

def _save_tokens(new_tokens):
    """Internal: Saves/Updates tokens in Secrets Manager."""
    secret_name = os.environ.get('GOOGLE_USER_TOKENS_NAME')
    existing = _get_stored_tokens()
    merged = {**existing, **new_tokens}
    
    # Preserve refresh_token if not in new_tokens
    if 'refresh_token' not in new_tokens and 'refresh_token' in existing:
        merged['refresh_token'] = existing['refresh_token']
    
    merged['updated_at'] = datetime.utcnow().isoformat() + 'Z'
    
    try:
        secrets.put_secret_value(
            SecretId=secret_name,
            SecretString=json.dumps(merged)
        )
        return True
    except Exception as e:
        print(f"ERROR: Failed to persist refreshed tokens: {e}")
        return False

def _refresh_access_token(request_id="UNKNOWN"):
    """Internal: Refreshes the Google access token."""
    print(f"INFO: [Req:{request_id}] Starting Google access token refresh.")
    tokens = _get_stored_tokens()
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
            _save_tokens(res_data)
            print(f"SUCCESS: [Req:{request_id}] Google access token refreshed.")
            return res_data['access_token']
    except Exception as e:
        print(f"ERROR: [Req:{request_id}] Failed to refresh Google token: {e}")
        return None

def _get_valid_token(request_id="UNKNOWN"):
    """Internal: Gets a valid access token, refreshing if necessary."""
    # For MVP, we'll just always refresh to ensure it's fresh, 
    # as we don't track'local' expiry time precisely here.
    return _refresh_access_token(request_id)

def _build_event_body(item, assigned_worker=None):
    """Internal: Builds Google Calendar event resource."""
    client_name = item.get('client_name', 'Unknown')
    summary = f"[TEST] Pet Sitting - {client_name}"
    
    description = (
        f"Request ID: {item.get('request_id', 'N/A')}\n"
        f"Client: {client_name}\n"
        f"Email: {item.get('client_email', 'N/A')}\n"
        f"Service: {item.get('service_type', 'N/A')}\n"
        f"Start Date: {item.get('start_date', 'N/A')}\n"
        f"Worker: {assigned_worker or 'Not Assigned'}\n\n"
        f"Notes: {item.get('pet_info', 'None')}"
    )

    # Use all-day event format
    date_str = item.get('start_date')
    return {
        'summary': summary,
        'description': description,
        'start': { 'date': date_str },
        'end': { 'date': date_str }
    }

def sync_calendar_event(item, google_event_id=None, assigned_worker=None):
    """
    Creates or updates a Google Calendar event.
    Returns: event_id (str) or None on failure.
    """
    request_id = item.get('request_id', 'UNKNOWN')
    token = _get_valid_token(request_id)
    if not token:
        return None

    event_body = _build_event_body(item, assigned_worker)
    
    try:
        if google_event_id:
            # Update existing
            print(f"INFO: [Req:{request_id}] Updating Calendar Event: {google_event_id}")
            url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{google_event_id}"
            method = 'PUT'
        else:
            # Create new
            print(f"INFO: [Req:{request_id}] Creating new Calendar Event.")
            url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
            method = 'POST'

        data = json.dumps(event_body).encode('utf-8')
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('Content-Type', 'application/json')

        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            new_id = res_data.get('id')
            action = "Updated" if google_event_id else "Created"
            print(f"SUCCESS: [Req:{request_id}] {action} Calendar Event: {new_id}")
            return new_id

    except urllib.error.HTTPError as he:
        err_body = he.read().decode()
        print(f"ERROR: [Req:{request_id}] HTTP {he.code} from Google Calendar API: {err_body}")
        return google_event_id
    except Exception as e:
        print(f"ERROR: [Req:{request_id}] Failed to sync Calendar: {e}")
        return google_event_id # Return original ID if update failed to prevent losing it

def delete_event(google_event_id, request_id="UNKNOWN"):
    """Deletes a Google Calendar event."""
    token = _get_valid_token(request_id)
    if not token:
        return False

    try:
        url = f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{google_event_id}"
        req = urllib.request.Request(url, method='DELETE')
        req.add_header('Authorization', f'Bearer {token}')

        with urllib.request.urlopen(req) as response:
            print(f"SUCCESS: [Req:{request_id}] Deleted Calendar Event: {google_event_id}")
            return True

    except Exception as e:
        print(f"ERROR: [Req:{request_id}] Failed to delete Calendar event {google_event_id}: {e}")
        return False
