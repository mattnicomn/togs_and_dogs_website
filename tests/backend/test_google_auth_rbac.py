import os
import json
import pytest
import datetime
from unittest.mock import patch, MagicMock

# Set required env vars
os.environ['DEFAULT_COMPANY_ID'] = 'tog_and_dogs'
os.environ['DATA_TABLE_NAME'] = 'test-table'
os.environ['ADMIN_USER_POOL_ID'] = 'us-east-1_xxxx'
os.environ['GOOGLE_CLIENT_CREDS_NAME'] = 'google-creds'
os.environ['GOOGLE_USER_TOKENS_NAME'] = 'togs-and-dogs-prod/google/user-tokens'

from handlers.google_auth_handler import handler as google_auth_handler

def make_event(path, http_method='GET', groups=None, custom_company_id='tog_and_dogs', email='user@example.com', sub='test-sub-123', body=None, query_params=None):
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

@pytest.fixture(autouse=True)
def _set_multi_tenant_mode():
    with patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'}):
        yield

class TestGoogleAuthRBAC:

    @pytest.fixture(autouse=True)
    def _owned_provider_metadata(self):
        owners = {'togs-and-dogs-prod/google/user-tokens': 'tog_and_dogs',
                  'opaque/alpha-token': 'test_tenant_alpha'}
        with patch('common.google_calendar.secrets') as sdk:
            sdk.meta.region_name = 'us-east-1'
            sdk.describe_secret.side_effect = lambda SecretId: {
                'Name': SecretId,
                'ARN': 'arn:aws:secretsmanager:us-east-1:123456789012:secret:' + SecretId + '-Ab1234',
                'Tags': [{'Key': 'CompanyId', 'Value': owners[SecretId]}]}
            sdk.get_secret_value.return_value = {'SecretString': '{}'}
            yield

    @patch('common.db.table.get_item')
    @patch('common.entitlement._get_entitlement_safely')
    @patch('handlers.google_auth_handler.get_google_config')
    @patch('common.db.table.put_item')
    def test_initiate_auth_by_role(self, mock_put_item, mock_config, mock_get_entitlement, mock_db_get_item):
        """Prove initiate_auth allows owner/admin but denies staff, client, and others."""
        mock_get_entitlement.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
        mock_db_get_item.return_value = {'Item': {
            "PK": "TENANT#tog_and_dogs", "SK": "METADATA",
            "company_id": "tog_and_dogs",
            "calendar_provider": "google",
            "calendar_enabled": True
        }}
        mock_config.return_value = {"client_id": "id", "client_secret": "secret"}

        # 1. Staff role - Denied
        event_staff = make_event('/admin/auth/google', http_method='GET', groups=['staff'], custom_company_id='tog_and_dogs')
        result = google_auth_handler(event_staff, None)
        assert result['statusCode'] == 403
        body = json.loads(result['body'])
        assert "Forbidden" in body['error']
        mock_put_item.assert_not_called()  # Proves state is not initialized for staff

        # 2. Client role - Denied
        event_client = make_event('/admin/auth/google', http_method='GET', groups=['client'], custom_company_id='tog_and_dogs')
        result = google_auth_handler(event_client, None)
        assert result['statusCode'] == 403
        body = json.loads(result['body'])
        assert "Forbidden" in body['error']
        mock_put_item.assert_not_called()

        # 3. platform_admin role - Denied (intentionally denied from normal tenant integrations)
        event_plat = make_event('/admin/auth/google', http_method='GET', groups=['platform_admin'], custom_company_id='tog_and_dogs')
        result = google_auth_handler(event_plat, None)
        assert result['statusCode'] == 403
        mock_put_item.assert_not_called()

        # 4. Unknown/No role - Denied
        event_unk = make_event('/admin/auth/google', http_method='GET', groups=[], custom_company_id='tog_and_dogs')
        result = google_auth_handler(event_unk, None)
        assert result['statusCode'] == 403
        mock_put_item.assert_not_called()

        # 5. Owner role - Allowed
        event_owner = make_event('/admin/auth/google', http_method='GET', groups=['owner'], custom_company_id='tog_and_dogs')
        result = google_auth_handler(event_owner, None)
        assert result['statusCode'] == 200
        mock_put_item.assert_called_once()  # State created for owner

        # Reset mock
        mock_put_item.reset_mock()

        # 6. Admin role - Allowed
        event_admin = make_event('/admin/auth/google', http_method='GET', groups=['admin'], custom_company_id='tog_and_dogs')
        result = google_auth_handler(event_admin, None)
        assert result['statusCode'] == 200
        mock_put_item.assert_called_once()

    @patch('handlers.google_auth_handler.secrets')
    @patch('common.db.table.get_item')
    @patch('common.entitlement._get_entitlement_safely')
    def test_disconnect_by_role(self, mock_get_entitlement, mock_db_get_item, mock_secrets):
        """Prove disconnect allows owner/admin but denies staff, client, and others."""
        mock_get_entitlement.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
        mock_db_get_item.return_value = {'Item': {
            "PK": "TENANT#test_tenant_alpha", "SK": "METADATA",
            "company_id": "test_tenant_alpha",
            "calendar_secret_ref": "opaque/alpha-token",
            "calendar_provider": "google",
            "calendar_enabled": True
        }}

        # 1. Staff role - Denied
        event_staff = make_event('/admin/auth/google', http_method='DELETE', groups=['staff'], custom_company_id='test_tenant_alpha')
        result = google_auth_handler(event_staff, None)
        assert result['statusCode'] == 403
        mock_secrets.put_secret_value.assert_not_called()

        # 2. Client role - Denied
        event_client = make_event('/admin/auth/google', http_method='DELETE', groups=['client'], custom_company_id='test_tenant_alpha')
        result = google_auth_handler(event_client, None)
        assert result['statusCode'] == 403
        mock_secrets.put_secret_value.assert_not_called()

        # 3. Owner role - Allowed
        event_owner = make_event('/admin/auth/google', http_method='DELETE', groups=['owner'], custom_company_id='test_tenant_alpha')
        result = google_auth_handler(event_owner, None)
        assert result['statusCode'] == 200
        mock_secrets.put_secret_value.assert_called_once()

        # Reset mock
        mock_secrets.put_secret_value.reset_mock()

        # 4. Admin role - Allowed
        event_admin = make_event('/admin/auth/google', http_method='DELETE', groups=['admin'], custom_company_id='test_tenant_alpha')
        result = google_auth_handler(event_admin, None)
        assert result['statusCode'] == 200
        mock_secrets.put_secret_value.assert_called_once()

    @patch('common.db.table.get_item')
    @patch('common.entitlement._get_entitlement_safely')
    @patch('handlers.google_auth_handler.get_google_config')
    @patch('handlers.google_auth_handler.get_stored_tokens')
    def test_get_status_allowed_for_staff(self, mock_tokens, mock_config, mock_get_entitlement, mock_db_get_item):
        """Prove read-only status remains readable by staff."""
        mock_get_entitlement.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
        mock_db_get_item.return_value = {'Item': {
            "PK": "TENANT#tog_and_dogs", "SK": "METADATA",
            "company_id": "tog_and_dogs",
            "calendar_provider": "google",
            "calendar_enabled": True
        }}
        mock_config.return_value = {"client_id": "id", "client_secret": "secret"}
        
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        mock_tokens.return_value = {
            "refresh_token": "some-token",
            "access_token": "valid-token",
            "updated_at": now_str,
            "expires_in": 3600
        }

        event_staff = make_event('/admin/auth/status', http_method='GET', groups=['staff'], custom_company_id='tog_and_dogs')
        result = google_auth_handler(event_staff, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert body['status'] == 'CONNECTED'
