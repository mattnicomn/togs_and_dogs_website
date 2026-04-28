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

def get_stored_tokens():
    """Retrieves access and refresh tokens from Secrets Manager."""
    secret_name = os.environ.get('GOOGLE_USER_TOKENS_NAME')
    try:
        response = secrets.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        # LOGGING BREADCRUMB: If the secret is empty/new, this is expected
        print(f"INFO: No existing tokens to merge or secret uninitialized: {e}")
        return {}

def save_tokens(new_tokens):
    """
    Saves/Updates tokens in Secrets Manager.
    Decision: Preserves existing refresh_token if new one is not provided.
    """
    secret_name = os.environ.get('GOOGLE_USER_TOKENS_NAME')
    existing = get_stored_tokens()
    
    # Merge
    merged = {**existing, **new_tokens}
    
    # Ensure refresh_token is not lost if it was already stored but not returned now
    if 'refresh_token' not in new_tokens and 'refresh_token' in existing:
        merged['refresh_token'] = existing['refresh_token']
    
    merged['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    
    try:
        print(f"INFO: Attempting to persist tokens to {secret_name}")
        secrets.put_secret_value(
            SecretId=secret_name,
            SecretString=json.dumps(merged)
        )
        print("SUCCESS: Tokens persisted successfully.")
        return True
    except Exception as e:
        print(f"ERROR: Failed to save tokens to Secrets Manager: {e}")
        return False

def handler(event, context):
    path = event.get('path', '')
    
    if path.endswith('/google'):
        return initiate_auth(event)
    elif path.endswith('/callback'):
        return handle_callback(event)
    elif path.endswith('/status'):
        return get_status(event)
    
    return bad_request(f"Unknown auth path: {path}", event)

def initiate_auth(event):
    """
    GET /admin/auth/google
    Generates auth URL and stores state in DynamoDB.
    """
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
        from common.auth import get_current_company_id
        company_id = get_current_company_id(event)

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
            
            if save_tokens(token_response):
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
    config = get_google_config()
    if not config or not config.get('client_id'):
        return success({"status": "CREDENTIALS_MISSING"}, event)
    
    # Check if user tokens exist
    tokens = get_stored_tokens()
    refresh_token = tokens.get('refresh_token')
    
    if not refresh_token:
        return success({"status": "NOT_CONNECTED"}, event)
        
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
            save_tokens(token_data)
            return success({"status": "CONNECTED"}, event)
    except Exception as e:
        print(f"Connectivity check failed: {e}")
        return success({
            "status": "VALIDATION_FAILED", 
            "message": "Token exchange failed. Connection may be revoked or expired."
        }, event)
        
    return success({"status": "NOT_CONNECTED"}, event)
