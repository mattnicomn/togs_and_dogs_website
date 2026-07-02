import json
import os
import uuid
import time
import urllib.parse
import urllib.request
import boto3
from common.response import success, error, bad_request, internal_error, ALLOWED_ORIGINS
from common.db import table
from common.auth import get_claims
from common.entitlement import EntitlementDenied


secrets = boto3.client('secretsmanager')

def get_google_config():
    """Retrieves Client ID and Secret from Secrets Manager."""
    secret_arn = os.environ.get('GOOGLE_CLIENT_CREDS_NAME')
    try:
        response = secrets.get_secret_value(SecretId=secret_arn)
        return json.loads(response['SecretString'])
    except Exception as e:
        print(f"Error retrieving Google config: {e}")
        return None

def get_stored_tokens(company_id=None):
    """Retrieves access and refresh tokens from Secrets Manager."""
    from common.google_calendar import resolve_google_token_secret_name
    from common.auth import DEFAULT_COMPANY_ID
    if company_id is None:
        company_id = DEFAULT_COMPANY_ID
        
    secret_name = resolve_google_token_secret_name(company_id)
    if not secret_name:
        return {}
    try:
        response = secrets.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        # LOGGING BREADCRUMB: If the secret is empty/new, this is expected
        print(f"INFO: No existing tokens to merge or secret uninitialized for tenant {company_id}: {e}")
        return {}

def save_tokens(new_tokens, company_id=None):
    """
    Saves/Updates tokens in Secrets Manager.
    Decision: Preserves existing refresh_token if new one is not provided.
    Release 6G: Clears revoked status when new valid tokens are saved.
    """
    from common.google_calendar import resolve_google_token_secret_name
    from common.auth import DEFAULT_COMPANY_ID
    if company_id is None:
        company_id = DEFAULT_COMPANY_ID
        
    secret_name = resolve_google_token_secret_name(company_id)
    if not secret_name:
        print(f"ERROR: Cannot save tokens, Google integration not configured/supported for tenant {company_id}")
        return False
        
    existing = get_stored_tokens(company_id)
    
    # Merge
    merged = {**existing, **new_tokens}
    
    # Ensure refresh_token is not lost if it was already stored but not returned now
    if 'refresh_token' not in new_tokens and 'refresh_token' in existing:
        merged['refresh_token'] = existing['refresh_token']
    
    # Release 6G Phase 0C: Clear revoked status on successful token save
    merged.pop('token_status', None)
    merged.pop('revoked_at', None)
    merged.pop('revoked_reason', None)
    
    merged['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    
    try:
        print(f"INFO: Attempting to persist tokens for tenant {company_id} to {secret_name}")
        secrets.put_secret_value(
            SecretId=secret_name,
            SecretString=json.dumps(merged)
        )
        print("SUCCESS: Tokens persisted successfully.")
        return True
    except Exception as e:
        print(f"ERROR: Failed to save tokens to Secrets Manager for tenant {company_id}: {e}")
        return False


def get_company_id_safe(event):
    if not isinstance(event, dict):
        from common.auth import DEFAULT_COMPANY_ID
        return DEFAULT_COMPANY_ID
    if event.get('source') in ['aws.scheduler', 'aws.events'] or event.get('detail-type') == 'Scheduled Event' or event.get('action') == 'health_check':
        from common.auth import DEFAULT_COMPANY_ID
        return DEFAULT_COMPANY_ID
    try:
        from common.auth import get_current_company_id
        return get_current_company_id(event)
    except Exception:
        from common.auth import DEFAULT_COMPANY_ID
        return DEFAULT_COMPANY_ID

def handler(event, context):
    path = event.get('path', '')
    
    # Release 6G Phase 3: Support direct EventBridge invocation for scheduled health check
    if event.get('source') == 'aws.scheduler' or event.get('source') == 'aws.events' or event.get('detail-type') == 'Scheduled Event' or event.get('action') == 'health_check':
        return calendar_health_check(event)
    
    try:
        from common.entitlement import require_active_tenant
        block_resp = require_active_tenant(event)
        if block_resp:
            return block_resp

        if path.endswith('/google'):
            method = event.get('httpMethod', 'GET')
            if method == 'DELETE':
                return disconnect_auth(event)
            return initiate_auth(event)
        elif path.endswith('/callback'):
            return handle_callback(event)
        elif path.endswith('/status'):
            return get_status(event)
        elif path.endswith('/health'):
            return calendar_health_check(event)
        
        return bad_request(f"Unknown auth path: {path}", event)
    except EntitlementDenied as e:
        from common.response import format_response
        body = {
            "error": "EntitlementDenied",
            "message": str(e)
        }
        if getattr(e, "feature", None) is not None:
            body["feature"] = e.feature
        if getattr(e, "limit", None) is not None:
            body["limit"] = e.limit
        if getattr(e, "upgrade_hint", None) is not None:
            body["upgrade_hint"] = e.upgrade_hint
        return format_response(403, body, event)

def disconnect_auth(event):
    """
    DELETE /admin/auth/google
    Clears the stored tokens in Secrets Manager to disconnect Google Calendar.
    """
    company_id = get_company_id_safe(event)
    from common.google_calendar import resolve_google_token_secret_name
    secret_name = resolve_google_token_secret_name(company_id)
    if not secret_name:
        return success({"message": "Google Calendar disconnected successfully."}, event)
        
    # Disconnect clears only tenant-specific secret path and never global fallback
    if secret_name == os.environ.get('GOOGLE_USER_TOKENS_NAME'):
        return success({"message": "Google Calendar disconnected successfully."}, event)
        
    try:
        # Clear the tokens to effectively disconnect
        secrets.put_secret_value(
            SecretId=secret_name,
            SecretString=json.dumps({})
        )
        # Also mark it as explicitly disconnected/revoked for good measure
        from common.google_calendar import _mark_token_revoked
        _mark_token_revoked("admin_disconnect", company_id)
        
        return success({"message": "Google Calendar disconnected successfully."}, event)
    except Exception as e:
        print(f"ERROR: Failed to clear tokens in Secrets Manager: {e}")
        return internal_error("Failed to disconnect Google Calendar.", event)


def initiate_auth(event):
    """
    GET /admin/auth/google
    Generates auth URL and stores state in DynamoDB.
    """
    try:
        from common.auth import get_current_company_id
        company_id = get_current_company_id(event)
        
        from common.google_calendar import resolve_google_token_secret_name
        secret_name = resolve_google_token_secret_name(company_id)
        if not secret_name:
            return error(403, "Google Calendar integration is not supported for this tenant in this release.", event)
        
        # Release 17D: Entitlement gate for google calendar enabled
        from common.entitlement import check_feature
        check_feature(company_id, 'google_calendar_enabled', context=event)
    except EntitlementDenied:
        raise
    except Exception as e:
        print(f"Error resolving company/entitlement: {e}")
        return internal_error("Failed to authenticate request.", event)

    config = get_google_config()
    if not config:
        return internal_error("Google OAuth credentials not configured in Secrets Manager.", event)
    
    client_id = config.get('client_id')
    
    # Identify redirect URI based on origin
    headers = event.get('headers', {})
    origin = headers.get('origin') or headers.get('Origin') or "https://app.toganddogs.com"
    
    # Decisions: support both local and prod
    redirect_uri = "https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/admin/auth/callback"
    if "localhost" in origin:
        redirect_uri = "http://localhost:5173/admin/auth/callback"
    
    # Generate secure state
    state = str(uuid.uuid4())
    expires_at = int(time.time()) + 600 # 10 minutes
    
    try:
        table.put_item(Item={
            'PK': f"OAUTHSTATE#{state}",
            'SK': 'META',
            'company_id': company_id,
            'expires_at': expires_at,
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            # Link to admin if available in context
            'admin_id': get_claims(event).get('sub', 'dynamic-admin')
        })
    except Exception as e:
        print(f"Error saving OAuth state: {e}")
        return internal_error("Failed to initialize security state.", event)

    # Google OAuth URL Construction (Manual to avoid heavy library dependency for scaffolding)
    scopes = "https://www.googleapis.com/auth/calendar.events"
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope={scopes}&"
        f"state={state}&"
        "access_type=offline&"
        "prompt=consent"
    )

    return success({"auth_url": auth_url}, event)

def handle_callback(event):
    """
    GET /admin/auth/callback?code=...&state=...
    Validates state and exchanges code for refresh token.
    """
    query_params = event.get('queryStringParameters', {}) or {}
    code = query_params.get('code')
    state = query_params.get('state')

    if not code or not state:
        return bad_request("Missing code or state in callback.", event)

    # 1. Validate state exists in DynamoDB
    try:
        response = table.get_item(Key={'PK': f"OAUTHSTATE#{state}", 'SK': 'META'})
        state_record = response.get('Item')
        
        if not state_record:
            return bad_request("Invalid or expired OAuth state.", event)
        
        company_id = state_record.get('company_id')
        from common.google_calendar import resolve_google_token_secret_name
        secret_name = resolve_google_token_secret_name(company_id)
        if not secret_name:
            return error(403, "Google Calendar integration is not supported for this tenant in this release.", event)
            
        # Cleanup state immediately
        table.delete_item(Key={'PK': f"OAUTHSTATE#{state}", 'SK': 'META'})
        
    except Exception as e:
        print(f"Error validating state: {e}")
        return internal_error("Error during security validation.", event)

    # 2. Exchange code for token
    config = get_google_config()
    if not config:
        return internal_error("Google config lost during callback.", event)
    
    # Re-derive redirect_uri used in initiation (must match exactly)
    headers = event.get('headers', {})
    origin = headers.get('origin') or headers.get('Origin') or "https://toganddogs.usmissionhero.com"
    redirect_uri = "https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/admin/auth/callback"
    if origin not in ALLOWED_ORIGINS:
        origin = "https://toganddogs.usmissionhero.com"
    if "localhost" in origin:
        redirect_uri = "http://localhost:5173/admin/auth/callback"

    params = {
        'client_id': config['client_id'],
        'client_secret': config['client_secret'],
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri
    }
    
    try:
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
        with urllib.request.urlopen(req) as res:
            token_response = json.loads(res.read().decode())
            
            if save_tokens(token_response, company_id):
                # Decision: redirect back to admin dashboard on success
                frontend_base = "https://toganddogs.usmissionhero.com"
                if "localhost" in origin:
                    frontend_base = "http://localhost:5173"
                
                return {
                    "statusCode": 302,
                    "headers": {
                        "Location": f"{frontend_base}/admin"
                    },
                    "body": ""
                }
            else:
                return internal_error("Validated state but failed to persist tokens.", event)
                
    except Exception as e:
        print(f"Token exchange failed: {e}")
        return internal_error(f"Failed to exchange Google authorization code: {str(e)}", event)


def get_status(event):
    """
    GET /admin/auth/status
    Returns the current connection state.
    """
    company_id = get_company_id_safe(event)
    from common.google_calendar import resolve_google_token_secret_name
    secret_name = resolve_google_token_secret_name(company_id)
    if not secret_name:
        return success({"status": "NOT_CONNECTED"}, event)
        
    config = get_google_config()
    if not config or not config.get('client_id'):
        return success({"status": "CREDENTIALS_MISSING"}, event)
    
    # Check if user tokens exist
    tokens = get_stored_tokens(company_id)
    refresh_token = tokens.get('refresh_token')
    
    # Release 6G Phase 0C: Check if token is marked as revoked
    if tokens.get('token_status') == 'revoked':
        return success({
            "status": "VALIDATION_FAILED",
            "message": "Google Calendar connection was revoked. Please reconnect via the Connect button."
        }, event)
    
    if not refresh_token:
        return success({"status": "NOT_CONNECTED"}, event)
        
    # Check if cached access_token is still valid (5-minute buffer) to avoid redundant Google API calls
    access_token = tokens.get('access_token')
    updated_at = tokens.get('updated_at')
    expires_in = tokens.get('expires_in', 3600)
    
    if access_token and updated_at:
        try:
            from datetime import datetime, timezone
            # updated_at format is '%Y-%m-%dT%H:%M:%SZ'
            update_time = datetime.strptime(updated_at, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - update_time).total_seconds()
            if elapsed < (expires_in - 300):
                return success({"status": "CONNECTED"}, event)
        except Exception as cache_err:
            print(f"WARNING: Cached token validation failed: {cache_err}")

    # Validation: Try to refresh access token or check tokeninfo
    # We'll do a lightweight refresh test to confirm "Usable"
    try:
        # Dry-run: Attempt to refresh the access token
        refresh_params = {
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        data = urllib.parse.urlencode(refresh_params).encode()
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
        with urllib.request.urlopen(req) as res:
            # If we get a 200, it's usable. We can even save the new access token.
            token_data = json.loads(res.read().decode())
            save_tokens(token_data, company_id)
            return success({"status": "CONNECTED"}, event)
    except Exception as e:
        print(f"Connectivity check failed: {e}")
        return success({
            "status": "VALIDATION_FAILED", 
            "message": "Token exchange failed. Connection may be revoked or expired."
        }, event)
        
    return success({"status": "NOT_CONNECTED"}, event)


def calendar_health_check(event):
    """
    Release 6G Phase 3: Scheduled Google Calendar health check.
    
    Invoked by EventBridge on a daily schedule or manually via /admin/auth/health.
    Verifies the Google Calendar connection is healthy without blocking business operations.
    
    Returns structured status and emits CloudWatch log markers for metric filters/alarms.
    """
    print("CALENDAR_HEALTH_CHECK: Starting scheduled health check.")
    
    company_id = get_company_id_safe(event)
    from common.google_calendar import resolve_google_token_secret_name
    secret_name = resolve_google_token_secret_name(company_id)
    if not secret_name:
        return _health_response("NOT_CONNECTED", "Google Calendar is not configured for this tenant.", event)
        
    # 1. Check Google client credentials exist
    config = get_google_config()
    if not config or not config.get('client_id'):
        print("CALENDAR_HEALTH_CHECK_FAILED: Google client credentials not configured.")
        return _health_response("CREDENTIALS_MISSING", "Google OAuth credentials not configured in Secrets Manager.", event)
    
    # 2. Check stored tokens
    tokens = get_stored_tokens(company_id)
    
    if not tokens or not tokens.get('refresh_token'):
        print("CALENDAR_HEALTH_CHECK_FAILED: No refresh token stored. Google Calendar is not connected.")
        return _health_response("TOKEN_MISSING", "No refresh token found. Google Calendar is not connected.", event)
    
    # 3. Check if token is marked as revoked (Phase 0C)
    if tokens.get('token_status') == 'revoked':
        print("CALENDAR_HEALTH_CHECK_TOKEN_REVOKED: Google token is marked as revoked. Admin must reconnect.")
        return _health_response("TOKEN_REVOKED", "Google Calendar token is revoked. Admin must reconnect via the Connect button.", event)
    
    # 4. Attempt a live token refresh to verify connectivity
    try:
        refresh_params = {
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'refresh_token': tokens['refresh_token'],
            'grant_type': 'refresh_token'
        }
        data = urllib.parse.urlencode(refresh_params).encode()
        req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
        
        with urllib.request.urlopen(req, timeout=10) as res:
            token_data = json.loads(res.read().decode())
            save_tokens(token_data, company_id)
            print("CALENDAR_HEALTH_CHECK_SUCCESS: Google Calendar connection is healthy. Token refreshed.")
            return _health_response("CONNECTED", "Google Calendar connection is healthy.", event)
    
    except urllib.error.HTTPError as http_err:
        try:
            error_body = http_err.read().decode()
            error_data = json.loads(error_body)
            error_code = error_data.get('error', '')
        except Exception:
            error_code = ''
            error_body = str(http_err)
        
        if error_code == 'invalid_grant':
            print("CALENDAR_HEALTH_CHECK_TOKEN_REVOKED: Token refresh returned invalid_grant. Token is revoked.")
            # Mark as revoked so subsequent operations skip immediately
            from common.google_calendar import _mark_token_revoked
            _mark_token_revoked("health_check", company_id)
            return _health_response("TOKEN_REVOKED", "Google Calendar token is revoked (invalid_grant). Admin must reconnect.", event)
        else:
            print(f"CALENDAR_HEALTH_CHECK_FAILED: Token refresh failed: HTTP {http_err.code} - {error_body}")
            return _health_response("REFRESH_FAILED", f"Token refresh failed: {error_code or error_body}", event)
    
    except Exception as e:
        print(f"CALENDAR_HEALTH_CHECK_FAILED: Unexpected error during health check: {e}")
        return _health_response("REFRESH_FAILED", f"Health check error: {str(e)}", event)



def _health_response(status, message, event):
    """Helper to return a consistent health check response."""
    result = {"status": status, "message": message, "check": "calendar_health"}
    # For EventBridge invocations, just return the dict (no API Gateway wrapper needed)
    if event.get('source') in ['aws.scheduler', 'aws.events'] or event.get('detail-type') == 'Scheduled Event' or event.get('action') == 'health_check':
        print(f"CALENDAR_HEALTH_CHECK_RESULT: {json.dumps(result)}")
        return result
    # For API Gateway invocations, wrap in standard response
    return success(result, event)
