import os
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Set required env vars
os.environ['DEFAULT_COMPANY_ID'] = 'tog_and_dogs'
os.environ['DATA_TABLE_NAME'] = 'test-table'
os.environ['ADMIN_USER_POOL_ID'] = 'us-east-1_xxxx'
os.environ['GOOGLE_CLIENT_CREDS_NAME'] = 'google-creds'
os.environ['GOOGLE_USER_TOKENS_NAME'] = 'togs-and-dogs-prod/google/user-tokens'
os.environ['TENANT_RESOLUTION_MODE'] = 'multi'

from common.google_calendar import (
    resolve_google_token_secret_name,
    get_tenant_secret_path,
    _get_stored_tokens,
    _save_tokens
)
from handlers.google_auth_handler import (
    handler as google_auth_handler,
    get_stored_tokens,
    save_tokens
)

def make_event(path, http_method='GET', groups=None, custom_company_id=None, email='user@example.com', sub='test-sub-123', body=None, query_params=None):
    claims = {
        'email': email,
        'sub': sub,
        'email_verified': 'true',
    }
    if groups:
        claims['cognito:groups'] = ','.join(groups) if isinstance(groups, list) else groups
    if custom_company_id is not None:
        claims['custom:company_id'] = custom_company_id

    event = {
        'requestContext': {
            'authorizer': {
                'claims': claims
            }
        },
        'httpMethod': http_method,
        'path': path,
        'headers': {'origin': 'https://toganddogs.usmissionhero.com'},
        'queryStringParameters': query_params
    }
    if body:
        event['body'] = json.dumps(body)
    return event

class TestGoogleTokenIsolation:

    @patch('common.db.get_item')
    def test_default_tenant_legacy_fallback(self, mock_get_item):
        """1. tog_and_dogs with no calendar_secret_ref uses legacy fallback."""
        mock_get_item.return_value = {
            "company_id": "tog_and_dogs",
            "display_name": "Tog & Dogs"
        }
        secret_name = resolve_google_token_secret_name("tog_and_dogs")
        assert secret_name == "togs-and-dogs-prod/google/user-tokens"

    @patch('common.db.get_item')
    def test_tenant_explicit_secret_ref(self, mock_get_item):
        """2. Tenant with explicit calendar_secret_ref uses tenant-specific secret path."""
        mock_get_item.return_value = {
            "company_id": "test_tenant_alpha",
            "calendar_secret_ref": "custom/path/to/tokens"
        }
        secret_name = resolve_google_token_secret_name("test_tenant_alpha")
        assert secret_name == "custom/path/to/tokens"

    @patch('common.db.get_item')
    def test_non_default_tenant_not_enabled_returns_none(self, mock_get_item):
        """3. non-default tenant without Google enabled does not resolve secret path (None)."""
        mock_get_item.return_value = {
            "company_id": "test_tenant_alpha",
            "calendar_provider": "none",
            "calendar_enabled": False
        }
        secret_name = resolve_google_token_secret_name("test_tenant_alpha")
        assert secret_name is None

    @patch('common.db.get_item')
    @patch('common.entitlement._get_entitlement_safely')
    def test_non_default_tenant_blocked_from_connect(self, mock_get_entitlement, mock_get_item):
        """4. non-default tenant cannot trigger Google connect unless metadata/provider says Google is enabled."""
        mock_get_item.return_value = {
            "company_id": "test_tenant_alpha",
            "calendar_provider": "none",
            "calendar_enabled": False
        }
        mock_get_entitlement.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
        
        event = make_event('/admin/auth/google', http_method='GET', custom_company_id='test_tenant_alpha', groups=['owner'])
        result = google_auth_handler(event, None)
        assert result['statusCode'] == 403
        body = json.loads(result['body'])
        assert "not supported for this tenant" in body['error']

    @patch('handlers.google_auth_handler.secrets')
    @patch('common.db.table.delete_item')
    @patch('common.db.table.get_item')
    @patch('common.db.get_item')
    @patch('common.entitlement._get_entitlement_safely')
    @patch('handlers.google_auth_handler.get_google_config')
    @patch('urllib.request.urlopen')
    def test_oauth_callback_resolves_tenant_and_saves(self, mock_urlopen, mock_config, mock_get_entitlement, mock_db_get_item, mock_table_get_item, mock_table_delete_item, mock_secrets):
        """5. OAuth callback resolves tenant context safely and writes to tenant-specific secret."""
        # Mock entitlement to pass
        mock_get_entitlement.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
        
        # Mock state record
        mock_table_get_item.return_value = {
            "Item": {
                "PK": "OAUTHSTATE#some-state",
                "company_id": "custom_tenant_beta"
            }
        }
        # Mock tenant enabled Google
        mock_db_get_item.return_value = {
            "company_id": "custom_tenant_beta",
            "calendar_provider": "google",
            "calendar_enabled": True
        }
        # Mock google OAuth client credentials
        mock_config.return_value = {"client_id": "id", "client_secret": "secret"}
        
        # Mock google token exchange response
        mock_res = MagicMock()
        mock_res.read.return_value = b'{"access_token": "abc", "refresh_token": "xyz", "expires_in": 3600}'
        mock_urlopen.return_value.__enter__.return_value = mock_res
        
        # Mock get_secret_value (no existing tokens)
        mock_secrets.get_secret_value.return_value = {"SecretString": "{}"}
        
        event = make_event('/admin/auth/callback', http_method='GET', custom_company_id='custom_tenant_beta', groups=['owner'], query_params={"code": "auth-code", "state": "some-state"})
        result = google_auth_handler(event, None)
        
        assert result['statusCode'] == 302
        # Check that it saves to the correct per-tenant secret name: togs-and-dogs-prod/calendar/custom_tenant_beta/tokens
        mock_secrets.put_secret_value.assert_called_once()
        call_args = mock_secrets.put_secret_value.call_args[1]
        assert call_args['SecretId'] == "togs-and-dogs-prod/calendar/custom_tenant_beta/tokens"
        saved_body = json.loads(call_args['SecretString'])
        assert saved_body['access_token'] == "abc"
        assert saved_body['refresh_token'] == "xyz"

    @patch('handlers.google_auth_handler.secrets')
    @patch('common.db.get_item')
    @patch('common.entitlement._get_entitlement_safely')
    def test_disconnect_preserves_global_fallback(self, mock_get_entitlement, mock_db_get_item, mock_secrets):
        """7. disconnect clears only tenant-specific secret path and never global fallback."""
        # Mock entitlement to pass
        mock_get_entitlement.return_value = MagicMock(is_access_allowed=True, is_blocked=False)

        # Scenario A: Default tenant using global fallback
        mock_db_get_item.return_value = {
            "company_id": "tog_and_dogs"
        }
        event = make_event('/admin/auth/google', http_method='DELETE', custom_company_id='tog_and_dogs', groups=['owner'])
        result = google_auth_handler(event, None)
        assert result['statusCode'] == 200
        # Assert secrets.put_secret_value was not called (legacy global fallback preserved)
        mock_secrets.put_secret_value.assert_not_called()

        # Scenario B: Custom tenant using per-tenant secret path
        mock_db_get_item.return_value = {
            "company_id": "test_tenant_alpha",
            "calendar_provider": "google",
            "calendar_enabled": True
        }
        event = make_event('/admin/auth/google', http_method='DELETE', custom_company_id='test_tenant_alpha', groups=['owner'])
        result = google_auth_handler(event, None)
        assert result['statusCode'] == 200
        # Assert secrets.put_secret_value was called to clear the per-tenant secret
        mock_secrets.put_secret_value.assert_called_once()
        call_args = mock_secrets.put_secret_value.call_args[1]
        assert call_args['SecretId'] == "togs-and-dogs-prod/calendar/test_tenant_alpha/tokens"
        assert call_args['SecretString'] == "{}"

    @patch('common.entitlement._get_entitlement_safely')
    def test_disabled_tenant_blocked_from_all_operations(self, mock_get_entitlement):
        """8. disabled tenant cannot connect/reconnect/disconnect/sync."""
        mock_get_entitlement.return_value = MagicMock(is_access_allowed=False, is_blocked=True)
        
        # Test GET /admin/auth/google
        event = make_event('/admin/auth/google', http_method='GET', custom_company_id='test_tenant_alpha', groups=['owner'])
        result = google_auth_handler(event, None)
        assert result['statusCode'] == 403
        body = json.loads(result['body'])
        assert body['error'] == 'TenantDisabled'
        
        # Test DELETE /admin/auth/google
        event = make_event('/admin/auth/google', http_method='DELETE', custom_company_id='test_tenant_alpha', groups=['owner'])
        result = google_auth_handler(event, None)
        assert result['statusCode'] == 403

    @patch('common.db.table.get_item')
    @patch('common.entitlement._get_entitlement_safely')
    def test_no_raw_tokens_exposed_in_responses(self, mock_get_entitlement, mock_table_get_item):
        """9. no API payload includes raw token or secret values."""
        # Mock entitlement to pass
        mock_get_entitlement.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
        # Mock state record lookup to return None (expired/invalid)
        mock_table_get_item.return_value = {}

        event = make_event('/admin/auth/callback', http_method='GET', custom_company_id='tog_and_dogs', groups=['owner'], query_params={"code": "secret-auth-code", "state": "bad-state"})
        result = google_auth_handler(event, None)
        assert result['statusCode'] == 400
        assert "secret-auth-code" not in result['body']
        assert "token" not in result['body']
