import json
import os
import uuid
import re
import math
import time
import urllib.parse
import urllib.request
import boto3
from common.response import success, error, bad_request, internal_error, ALLOWED_ORIGINS
from common.db import table
from common.auth import get_claims, get_effective_role
from common.entitlement import EntitlementDenied


secrets = boto3.client('secretsmanager')

def get_google_config():
    """Retrieves Client ID and Secret from Secrets Manager."""
    secret_arn = os.environ.get('GOOGLE_CLIENT_CREDS_NAME')
    try:
        response = secrets.get_secret_value(SecretId=secret_arn)
        return json.loads(response['SecretString'])
    except Exception as e:
        print("PROVIDER_CONFIG_UNAVAILABLE")
        return None

def get_stored_tokens(company_id=None):
    """Retrieves access and refresh tokens from Secrets Manager."""
    from common.google_calendar import resolve_google_token_secret_name
    if company_id is None:
        raise PermissionError('INVALID_TENANT_CONTEXT')
        
    secret_name = resolve_google_token_secret_name(company_id)
    if not secret_name:
        return {}
    try:
        response = secrets.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except Exception as e:
        # LOGGING BREADCRUMB: If the secret is empty/new, this is expected
        print("PROVIDER_TOKEN_READ_FAILED")
        return {}

def save_tokens(new_tokens, company_id=None):
    """
    Saves/Updates tokens in Secrets Manager.
    Decision: Preserves existing refresh_token if new one is not provided.
    Release 6G: Clears revoked status when new valid tokens are saved.
    """
    from common.google_calendar import resolve_google_token_secret_name
    if company_id is None:
        raise PermissionError('INVALID_TENANT_CONTEXT')
        
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
        print("PROVIDER_TOKEN_SAVE_ATTEMPT")
        secrets.put_secret_value(
            SecretId=secret_name,
            SecretString=json.dumps(merged)
        )
        print("SUCCESS: Tokens persisted successfully.")
        return True
    except Exception as e:
        print("PROVIDER_TOKEN_SAVE_FAILED")
        return False


def _require_http_company_id(event):
    try:
        claims = get_claims(event)
        company_id = claims.get('custom:company_id')
        authorizer = event.get('requestContext', {}).get('authorizer', {}) or {}
        other_claims = (authorizer.get('jwt') or {}).get('claims') or {}
        if other_claims and other_claims.get('custom:company_id') != company_id:
            raise PermissionError('INVALID_TENANT_CONTEXT')
    except (AttributeError, TypeError):
        raise PermissionError('INVALID_TENANT_CONTEXT') from None
    if not isinstance(company_id, str) or not re.fullmatch(r'[a-z0-9_]{3,64}', company_id):
        raise PermissionError('INVALID_TENANT_CONTEXT')
    return company_id


def _is_http_event(event):
    return isinstance(event, dict) and any(key in event for key in (
        'httpMethod', 'requestContext', 'path', 'rawPath', 'routeKey'))


def _is_scheduled_health_event(event):
    return (isinstance(event, dict) and not _is_http_event(event)
            and event.get('source') == 'aws.events'
            and event.get('action') == 'health_check')


def get_company_id_safe(event):
    # Only the established IAM-authorized scheduled contract selects primary.
    if _is_scheduled_health_event(event):
        return 'tog_and_dogs'
    return _require_http_company_id(event)


def _provider_failure_response(exc, event):
    unavailable = str(exc) == 'PROVIDER_METADATA_INACCESSIBLE'
    return error(503 if unavailable else 403,
                 'PROVIDER_UNAVAILABLE' if unavailable else 'PROVIDER_ACCESS_DENIED', event)


def handler(event, context):
    if not isinstance(event, dict):
        return error(403, 'INVALID_TENANT_CONTEXT', {})
    path = event.get('path') or ''
    
    # Release 6G Phase 3: Support direct EventBridge invocation for scheduled health check
    if _is_scheduled_health_event(event):
        return calendar_health_check(event)
    
    try:
        if path.endswith('/callback'):
            return handle_callback(event)
        _require_http_company_id(event)
        from common.entitlement import require_active_tenant
        block_resp = require_active_tenant(event)
        if block_resp:
            return block_resp

        if path.endswith('/google'):
            method = event.get('httpMethod', 'GET')
            if method == 'DELETE':
                return disconnect_auth(event)
            return initiate_auth(event)
        elif path.endswith('/status'):
            return get_status(event)
        elif path.endswith('/health'):
            return error(403, 'SCHEDULED_HEALTH_ONLY', event)
        
        return bad_request(f"Unknown auth path: {path}", event)
    except PermissionError:
        return error(403, 'INVALID_TENANT_CONTEXT', event)
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
    role = get_effective_role(event)
    if role not in ['owner', 'admin']:
        return error(403, "Forbidden: Insufficient permissions to manage calendar integration.", event)

    from common.google_calendar import resolve_google_token_secret_name, ProviderBindingError
    try:
        company_id = _require_http_company_id(event)
        secret_name = resolve_google_token_secret_name(company_id)
    except (PermissionError, ProviderBindingError) as exc:
        return _provider_failure_response(exc, event)
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
        print("PROVIDER_TOKEN_WRITE_FAILED")
        return internal_error("Failed to disconnect Google Calendar.", event)


_OAUTH_PROD_REDIRECT = 'https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/admin/auth/callback'
_OAUTH_PROD_DESTINATION = 'https://toganddogs.usmissionhero.com/admin'
_OAUTH_LOCAL_ORIGIN = 'http://localhost:5173'
_OAUTH_STATE_PATTERN = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}')


class _OAuthFailure(Exception):
    def __init__(self, status, category):
        self.status = status
        self.category = category


def _oauth_text(value, limit):
    return isinstance(value, str) and 0 < len(value) <= limit and all(33 <= ord(c) <= 126 for c in value)


def _oauth_destinations(event):
    headers = event.get('headers') or {}
    origin = headers.get('origin') or headers.get('Origin')
    if origin is not None and origin not in ALLOWED_ORIGINS:
        raise _OAuthFailure(403, 'OAUTH_ORIGIN_DENIED')
    if origin == _OAUTH_LOCAL_ORIGIN:
        return (_OAUTH_LOCAL_ORIGIN + '/admin/auth/callback', _OAUTH_LOCAL_ORIGIN + '/admin')
    return _OAUTH_PROD_REDIRECT, _OAUTH_PROD_DESTINATION


def _require_oauth_binding(company_id, expected_arn=None):
    from common.google_calendar import _resolve_google_token_binding, ProviderBindingError
    try:
        binding = _resolve_google_token_binding(company_id)
    except ProviderBindingError as exc:
        if str(exc) == 'PROVIDER_METADATA_INACCESSIBLE':
            raise _OAuthFailure(503, 'OAUTH_UNAVAILABLE') from None
        raise _OAuthFailure(403, 'OAUTH_ACCESS_DENIED') from None
    if not binding or (expected_arn is not None and binding[1] != expected_arn):
        raise _OAuthFailure(403, 'OAUTH_ACCESS_DENIED')
    return binding[1]


def _require_oauth_tenant_eligible(company_id):
    # Never use the general fail-open entitlement loader for a public callback.
    response = table.get_item(Key={'PK': 'TENANT#' + company_id, 'SK': 'METADATA'}, ConsistentRead=True)
    tenant = response.get('Item')
    if not isinstance(tenant, dict) or any((
        tenant.get('PK') != 'TENANT#' + company_id,
        tenant.get('SK') != 'METADATA', tenant.get('company_id') != company_id,
    )):
        raise _OAuthFailure(403, 'OAUTH_ACCESS_DENIED')
    from common.billing import _build_entitlement
    ent = _build_entitlement(tenant)
    if (not ent.is_access_allowed or ent.is_blocked or
            ('is_active' in tenant and tenant['is_active'] is not True) or
            ('calendar_enabled' in tenant and tenant['calendar_enabled'] is not True) or
            tenant.get('calendar_provider', 'google') != 'google'):
        raise _OAuthFailure(403, 'OAUTH_ACCESS_DENIED')
    if os.environ.get('ENTITLEMENT_ENFORCEMENT_ENABLED', '').lower() == 'true':
        if not (ent.limits.get('google_calendar_enabled', False) or
                ent.feature_flags.get('google_calendar_enabled', False)):
            raise _OAuthFailure(403, 'OAUTH_ACCESS_DENIED')


def _load_oauth_transaction(state, now):
    from decimal import Decimal
    record = table.get_item(Key={'PK': 'OAUTHSTATE#' + state, 'SK': 'META'}, ConsistentRead=True).get('Item')
    if not isinstance(record, dict):
        raise _OAuthFailure(400, 'INVALID_OAUTH_STATE')
    created, expires = record.get('created_at'), record.get('expires_at')
    def integer(value):
        try:
            return (not isinstance(value, bool) and isinstance(value, (int, Decimal))
                    and value == int(value))
        except (ValueError, OverflowError):
            return False
    from common.google_calendar import _SECRET_ARN
    destinations = {(_OAUTH_PROD_REDIRECT, _OAUTH_PROD_DESTINATION),
                    (_OAUTH_LOCAL_ORIGIN + '/admin/auth/callback', _OAUTH_LOCAL_ORIGIN + '/admin')}
    if (record.get('PK') != 'OAUTHSTATE#' + state or record.get('SK') != 'META' or
            record.get('schema_version') != 'v2' or record.get('status') != 'PENDING' or
            not isinstance(record.get('company_id'), str) or
            not re.fullmatch(r'[a-z0-9_]{3,64}', record['company_id']) or
            not _oauth_text(record.get('initiating_principal'), 128) or
            not _oauth_text(record.get('provider_secret_arn'), 2048) or
            not _SECRET_ARN.fullmatch(record['provider_secret_arn']) or
            not isinstance(record.get('redirect_uri'), str) or
            not isinstance(record.get('post_auth_destination'), str) or
            (record['redirect_uri'], record['post_auth_destination']) not in destinations or
            not integer(created) or not integer(expires) or
            not (created <= now < expires <= created + 600)):
        raise _OAuthFailure(400, 'INVALID_OAUTH_STATE')
    return record


def _claim_oauth_transaction(record):
    from botocore.exceptions import ClientError
    names, values, conditions = {}, {':now': int(time.time()), ':consumed': 'CONSUMED'}, []
    fields = ('schema_version', 'status', 'company_id', 'initiating_principal',
              'provider_secret_arn', 'redirect_uri', 'post_auth_destination', 'created_at', 'expires_at')
    for field in fields:
        names['#' + field] = field
        values[':' + field] = record[field]
        conditions.append('#' + field + ' = :' + field)
    try:
        table.update_item(
            Key={'PK': record['PK'], 'SK': record['SK']},
            UpdateExpression='SET #status = :consumed',
            ConditionExpression='attribute_exists(PK) AND attribute_exists(SK) AND #expires_at > :now AND ' + ' AND '.join(conditions),
            ExpressionAttributeNames=names, ExpressionAttributeValues=values)
    except ClientError as exc:
        if exc.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
            raise _OAuthFailure(400, 'INVALID_OAUTH_STATE') from None
        raise _OAuthFailure(503, 'OAUTH_UNAVAILABLE') from None


def _persist_oauth_tokens(record, new_tokens):
    # This reconnect-specific operation intentionally clears revocation markers.
    if (not isinstance(new_tokens, dict) or not _oauth_text(new_tokens.get('access_token'), 16384) or
            isinstance(new_tokens.get('expires_in'), bool) or
            not isinstance(new_tokens.get('expires_in'), (int, float)) or
            not math.isfinite(new_tokens['expires_in']) or new_tokens['expires_in'] <= 0 or
            ('refresh_token' in new_tokens and not _oauth_text(new_tokens['refresh_token'], 16384))):
        raise _OAuthFailure(502, 'OAUTH_EXCHANGE_FAILED')
    arn = _require_oauth_binding(record['company_id'], record['provider_secret_arn'])
    existing = json.loads(secrets.get_secret_value(SecretId=arn)['SecretString'])
    if not isinstance(existing, dict):
        raise _OAuthFailure(503, 'OAUTH_UNAVAILABLE')
    merged = {**existing, **new_tokens}
    if not _oauth_text(merged.get('refresh_token'), 16384):
        raise _OAuthFailure(502, 'OAUTH_EXCHANGE_FAILED')
    for key in ('token_status', 'revoked_at', 'revoked_reason'):
        merged.pop(key, None)
    merged['updated_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    _require_oauth_binding(record['company_id'], arn)
    secrets.put_secret_value(SecretId=arn, SecretString=json.dumps(merged))


def initiate_auth(event):
    """Create a server-held, single-use OAuth transaction for an authorized tenant."""
    if get_effective_role(event) not in ['owner', 'admin']:
        return error(403, 'Forbidden: Insufficient permissions to manage calendar integration.', event)
    try:
        company_id = _require_http_company_id(event)
        principal = get_claims(event).get('sub')
        if not _oauth_text(principal, 128):
            raise _OAuthFailure(403, 'OAUTH_PRINCIPAL_REQUIRED')
        redirect, destination = _oauth_destinations(event)
        arn = _require_oauth_binding(company_id)
        _require_oauth_tenant_eligible(company_id)
        config = get_google_config()
        if not isinstance(config, dict) or not _oauth_text(config.get('client_id'), 2048):
            raise _OAuthFailure(503, 'OAUTH_UNAVAILABLE')
        state, now = str(uuid.uuid4()), int(time.time())
        table.put_item(Item={
            'PK': 'OAUTHSTATE#' + state, 'SK': 'META', 'schema_version': 'v2',
            'company_id': company_id, 'initiating_principal': principal,
            'provider_secret_arn': arn, 'redirect_uri': redirect,
            'post_auth_destination': destination, 'created_at': now,
            'expires_at': now + 600, 'status': 'PENDING',
        }, ConditionExpression='attribute_not_exists(PK) AND attribute_not_exists(SK)')
        params = {'client_id': config['client_id'], 'redirect_uri': redirect,
                  'response_type': 'code', 'scope': 'https://www.googleapis.com/auth/calendar.events',
                  'state': state, 'access_type': 'offline', 'prompt': 'consent'}
        return success({'auth_url': 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params)}, event)
    except PermissionError:
        return error(403, 'OAUTH_ACCESS_DENIED', event)
    except _OAuthFailure as exc:
        return error(exc.status, exc.category, event)
    except Exception:
        return error(503, 'OAUTH_UNAVAILABLE', event)


def handle_callback(event):
    """Consume v2 state before exchange; failures never reopen the transaction."""
    try:
        params = event.get('queryStringParameters') or {}
        if not isinstance(params, dict):
            raise _OAuthFailure(400, 'INVALID_OAUTH_STATE')
        code, state = params.get('code'), params.get('state')
        if (not _oauth_text(code, 4096) or not isinstance(state, str) or
                not _OAUTH_STATE_PATTERN.fullmatch(state)):
            raise _OAuthFailure(400, 'INVALID_OAUTH_STATE')
        record = _load_oauth_transaction(state, int(time.time()))
        _require_oauth_tenant_eligible(record['company_id'])
        _require_oauth_binding(record['company_id'], record['provider_secret_arn'])
        _claim_oauth_transaction(record)
        config = get_google_config()
        if not isinstance(config, dict) or not all(_oauth_text(config.get(k), 2048) for k in ('client_id', 'client_secret')):
            raise _OAuthFailure(503, 'OAUTH_UNAVAILABLE')
        data = urllib.parse.urlencode({
            'client_id': config['client_id'], 'client_secret': config['client_secret'],
            'code': code, 'grant_type': 'authorization_code', 'redirect_uri': record['redirect_uri']}).encode()
        try:
            request = urllib.request.Request('https://oauth2.googleapis.com/token', data=data)
            with urllib.request.urlopen(request, timeout=10) as response:
                tokens = json.loads(response.read().decode())
        except Exception:
            raise _OAuthFailure(502, 'OAUTH_EXCHANGE_FAILED') from None
        _persist_oauth_tokens(record, tokens)
        return {'statusCode': 302, 'headers': {'Location': record['post_auth_destination']}, 'body': ''}
    except _OAuthFailure as exc:
        return error(exc.status, exc.category, event)
    except Exception:
        return error(503, 'OAUTH_UNAVAILABLE', event)


def _classify_cached_status(tokens, now):
    if tokens == {}:
        return 'NOT_CONNECTED'
    if not isinstance(tokens, dict):
        return 'UNKNOWN'
    if tokens.get('token_status') == 'revoked':
        return 'VALIDATION_FAILED'
    if not all(isinstance(tokens.get(k), str) and tokens[k] for k in ('access_token', 'refresh_token')):
        return 'UNKNOWN'
    try:
        from datetime import datetime
        updated = datetime.fromisoformat(tokens['updated_at'].replace('Z', '+00:00'))
        if updated.tzinfo is None:
            return 'UNKNOWN'
        lifetime = tokens.get('expires_in', 3600)
        if (isinstance(lifetime, bool) or not isinstance(lifetime, (int, float))
                or not math.isfinite(lifetime)):
            return 'UNKNOWN'
        elapsed = now - updated.timestamp()
        if 0 <= elapsed < lifetime - 300:
            return 'CONNECTED'
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        pass
    return 'UNKNOWN'


def get_status(event):
    """Passive cached readiness only: never refresh or persist credentials."""
    from common.google_calendar import _resolve_google_token_binding, ProviderBindingError
    try:
        company_id = _require_http_company_id(event)
        binding = _resolve_google_token_binding(company_id)
    except (PermissionError, ProviderBindingError) as exc:
        return _provider_failure_response(exc, event)
    if not binding:
        return success({'status': 'NOT_CONNECTED'}, event)
    try:
        stored = secrets.get_secret_value(SecretId=binding[1])
    except Exception:
        return error(503, 'PROVIDER_UNAVAILABLE', event)
    try:
        tokens = json.loads(stored['SecretString'])
    except (KeyError, TypeError, ValueError):
        return success({'status': 'UNKNOWN'}, event)
    status = _classify_cached_status(tokens, time.time())
    payload = {'status': status}
    if status == 'VALIDATION_FAILED':
        payload['message'] = 'Google Calendar connection was revoked. Please reconnect.'
    return success(payload, event)


def calendar_health_check(event):
    """
    Release 6G Phase 3: Scheduled Google Calendar health check.
    
    Invoked only through the established EventBridge health contract.
    Verifies the Google Calendar connection is healthy without blocking business operations.
    
    Returns structured status and emits CloudWatch log markers for metric filters/alarms.
    """
    if not _is_scheduled_health_event(event):
        return error(403, 'SCHEDULED_HEALTH_ONLY', event)
    print("CALENDAR_HEALTH_CHECK: Starting scheduled health check.")
    
    company_id = 'tog_and_dogs'
    from common.google_calendar import resolve_google_token_secret_name, ProviderBindingError
    try:
        secret_name = resolve_google_token_secret_name(company_id)
    except ProviderBindingError:
        return _health_response('REFRESH_FAILED', 'PROVIDER_BINDING_UNAVAILABLE', event)
    if not secret_name:
        return _health_response("NOT_CONNECTED", "Google Calendar is not configured for this tenant.", event)
        
    # 1. Check Google client credentials exist
    config = get_google_config()
    if not config or not config.get('client_id'):
        print("CALENDAR_HEALTH_CHECK_FAILED: Google client credentials not configured.")
        return _health_response("CREDENTIALS_MISSING", "Google OAuth credentials not configured in Secrets Manager.", event)
    
    # 2. Check stored tokens; binding drift/read failures remain failures.
    try:
        tokens = get_stored_tokens(company_id)
    except Exception:
        return _health_response('REFRESH_FAILED', 'PROVIDER_UNAVAILABLE', event)
    
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
            if not save_tokens(token_data, company_id):
                return _health_response("REFRESH_FAILED", "PROVIDER_PERSISTENCE_FAILED", event)
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
            print("CALENDAR_HEALTH_CHECK_FAILED: PROVIDER_REFRESH_FAILED")
            return _health_response("REFRESH_FAILED", "PROVIDER_REFRESH_FAILED", event)
    
    except Exception as e:
        print("CALENDAR_HEALTH_CHECK_FAILED: PROVIDER_REFRESH_FAILED")
        return _health_response("REFRESH_FAILED", "PROVIDER_REFRESH_FAILED", event)



def _health_response(status, message, event):
    """Helper to return a consistent health check response."""
    result = {"status": status, "message": message, "check": "calendar_health"}
    # For EventBridge invocations, just return the dict (no API Gateway wrapper needed)
    if _is_scheduled_health_event(event):
        print(f"CALENDAR_HEALTH_CHECK_RESULT: {json.dumps(result)}")
        return result
    # For API Gateway invocations, wrap in standard response
    return success(result, event)
