import os
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# Set required env vars
os.environ.setdefault('DEFAULT_COMPANY_ID', 'tog_and_dogs')
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')
os.environ.setdefault('ADMIN_USER_POOL_ID', 'us-east-1_xxxx')
os.environ.setdefault('GOOGLE_CLIENT_CREDS_NAME', 'google-creds')
os.environ.setdefault('GOOGLE_USER_TOKENS_NAME', 'google-tokens')

from handlers.google_auth_handler import get_status, calendar_health_check, initiate_auth, handle_callback, disconnect_auth
from handlers.admin_handler import handler as admin_handler

def make_event(path, http_method='GET', groups=None, custom_company_id=None, email='user@example.com', sub='test-sub-123', body=None):
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
    }
    if body:
        event['body'] = json.dumps(body)
    return event


# ==============================================================================
# 1. Google Calendar Tenant Gate Tests
# ==============================================================================

class TestGoogleCalendarTenantGate:

    @patch('handlers.google_auth_handler.get_google_config')
    @patch('handlers.google_auth_handler.get_stored_tokens')
    def test_default_tenant_status_connected(self, mock_get_tokens, mock_get_config):
        """Default tenant status is fetched from Secrets Manager normally."""
        mock_get_config.return_value = {'client_id': 'some-client-id'}
        mock_get_tokens.return_value = {
            'access_token': 'valid-token',
            'refresh_token': 'refresh-token',
            'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'expires_in': 3600
        }
        
        event = make_event('/admin/auth/status', http_method='GET', groups=['owner'], custom_company_id='tog_and_dogs')
        resp = get_status(event)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['status'] == 'CONNECTED'
        mock_get_tokens.assert_called_once()

    @patch('handlers.google_auth_handler.get_google_config')
    @patch('handlers.google_auth_handler.get_stored_tokens')
    def test_non_default_tenant_status_not_connected(self, mock_get_tokens, mock_get_config):
        """Non-default tenant status returns NOT_CONNECTED immediately without Secrets Manager lookup."""
        event = make_event('/admin/auth/status', http_method='GET', groups=['owner'], custom_company_id='test_tenant_alpha')
        
        resp = get_status(event)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['status'] == 'NOT_CONNECTED'
        mock_get_tokens.assert_not_called()
        mock_get_config.assert_not_called()

    @patch('handlers.google_auth_handler.get_google_config')
    def test_non_default_tenant_initiate_oauth_blocked(self, mock_get_config):
        """Non-default tenant is blocked from initiating Google OAuth."""
        event = make_event('/admin/auth/google', http_method='GET', groups=['owner'], custom_company_id='test_tenant_alpha')
        
        resp = initiate_auth(event)
        assert resp['statusCode'] == 403
        body = json.loads(resp['body'])
        assert "not supported" in body['error']
        mock_get_config.assert_not_called()

    @patch('handlers.google_auth_handler.table')
    def test_non_default_tenant_callback_blocked(self, mock_table):
        """Non-default tenant callback exchange is blocked."""
        # Mock State validation
        mock_table.get_item.return_value = {
            'Item': {
                'PK': 'OAUTHSTATE#state123',
                'SK': 'META',
                'company_id': 'test_tenant_alpha'
            }
        }
        event = {
            'httpMethod': 'GET',
            'path': '/admin/auth/callback',
            'queryStringParameters': {
                'code': 'oauthcode123',
                'state': 'state123'
            }
        }
        resp = handle_callback(event)
        assert resp['statusCode'] == 403
        body = json.loads(resp['body'])
        assert "not supported" in body['error']

    def test_non_default_tenant_disconnect_noop(self):
        """Non-default tenant disconnect returns success without clearing Secrets Manager."""
        event = make_event('/admin/auth/google', http_method='DELETE', groups=['owner'], custom_company_id='test_tenant_alpha')
        with patch('handlers.google_auth_handler.secrets') as mock_secrets:
            resp = disconnect_auth(event)
            assert resp['statusCode'] == 200
            body = json.loads(resp['body'])
            assert "successfully" in body['message']
            mock_secrets.put_secret_value.assert_not_called()


# ==============================================================================
# 2. Cognito User Filtering Tests
# ==============================================================================

class TestCognitoUserFiltering:

    @patch('handlers.admin_handler.boto3.client')
    @patch('common.db.table.query')
    @patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'})
    def test_staff_list_filtering_multi_mode(self, mock_query, mock_cognito_client):
        """Under multi-tenant mode, staff list returns only Cognito users matching company_id."""
        mock_query.return_value = {'Items': []} # Empty DynamoDB profiles
        
        mock_cog = MagicMock()
        mock_cognito_client.return_value = mock_cog
        mock_cog.list_groups.return_value = {
            'Groups': [{'GroupName': 'Staff'}, {'GroupName': 'owner'}]
        }
        
        mock_cog.list_users_in_group.return_value = {
            'Users': [
                {
                    'Username': 'staff1',
                    'Enabled': True,
                    'UserStatus': 'CONFIRMED',
                    'Attributes': [
                        {'Name': 'email', 'Value': 'staff1@test.com'},
                        {'Name': 'sub', 'Value': 'sub1'},
                        {'Name': 'custom:company_id', 'Value': 'test_tenant_alpha'}
                    ]
                },
                {
                    'Username': 'staff2',
                    'Enabled': True,
                    'UserStatus': 'CONFIRMED',
                    'Attributes': [
                        {'Name': 'email', 'Value': 'staff2@test.com'},
                        {'Name': 'sub', 'Value': 'sub2'},
                        {'Name': 'custom:company_id', 'Value': 'tog_and_dogs'}
                    ]
                },
                {
                    'Username': 'staff3',
                    'Enabled': True,
                    'UserStatus': 'CONFIRMED',
                    'Attributes': [
                        {'Name': 'email', 'Value': 'staff3@test.com'},
                        {'Name': 'sub', 'Value': 'sub3'}
                    ]
                }
            ]
        }
        
        event = make_event('/admin/staff', http_method='GET', groups=['owner'], custom_company_id='test_tenant_alpha')
        resp = admin_handler(event, None)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        
        staff_list = body['staff']
        assert len(staff_list) == 1
        assert staff_list[0]['email'] == 'staff1@test.com'
        assert staff_list[0]['company_id'] == 'test_tenant_alpha'

    @patch('handlers.admin_handler.boto3.client')
    @patch('common.db.table.query')
    @patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'single'})
    def test_staff_list_filtering_single_mode_fallback(self, mock_query, mock_cognito_client):
        """Under single-tenant mode, users missing custom:company_id fall back to default company."""
        mock_query.return_value = {'Items': []}
        mock_cog = MagicMock()
        mock_cognito_client.return_value = mock_cog
        mock_cog.list_groups.return_value = {
            'Groups': [{'GroupName': 'Staff'}]
        }
        mock_cog.list_users_in_group.return_value = {
            'Users': [
                {
                    'Username': 'staff_legacy',
                    'Enabled': True,
                    'UserStatus': 'CONFIRMED',
                    'Attributes': [
                        {'Name': 'email', 'Value': 'legacy@test.com'},
                        {'Name': 'sub', 'Value': 'sub_leg'}
                    ]
                }
            ]
        }
        
        event = make_event('/admin/staff', http_method='GET', groups=['owner'], custom_company_id='tog_and_dogs')
        resp = admin_handler(event, None)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert len(body['staff']) == 1
        assert body['staff'][0]['email'] == 'legacy@test.com'

        event2 = make_event('/admin/staff', http_method='GET', groups=['owner'], custom_company_id='test_tenant_alpha')
        resp2 = admin_handler(event2, None)
        assert resp2['statusCode'] == 200
        body2 = json.loads(resp2['body'])
        assert len(body2['staff']) == 0


# ==============================================================================
# 3. Tenant Info Endpoint Tests
# ==============================================================================

class TestTenantInfoEndpoint:

    @patch('handlers.admin_handler.get_item')
    @patch('handlers.google_auth_handler.get_google_config')
    @patch('handlers.google_auth_handler.get_stored_tokens')
    def test_tenant_info_default_company(self, mock_get_tokens, mock_get_config, mock_get_item):
        """tenant-info returns correct metadata for default tenant including calendar status."""
        mock_get_item.return_value = {
            'company_id': 'tog_and_dogs',
            'display_name': 'Tog & Dogs Production',
            'subscription_tier': 'premium',
            'subscription_status': 'active'
        }
        mock_get_config.return_value = {'client_id': 'client-id'}
        mock_get_tokens.return_value = {
            'access_token': 'tok',
            'refresh_token': 'ref',
            'updated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'expires_in': 3600
        }
        
        event = make_event('/admin/tenant-info', http_method='GET', groups=['owner'], custom_company_id='tog_and_dogs')
        resp = admin_handler(event, None)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['company_id'] == 'tog_and_dogs'
        assert body['display_name'] == 'Tog & Dogs Production'
        assert body['subscription_tier'] == 'premium'
        assert body['subscription_status'] == 'active'
        assert body['google_calendar_status'] == 'CONNECTED'
        assert 'refresh_token' not in body
        assert 'access_token' not in body

    @patch('handlers.admin_handler.get_item')
    def test_tenant_info_second_company(self, mock_get_item):
        """tenant-info returns correct metadata for second tenant, calendar shows NOT_CONNECTED."""
        mock_get_item.return_value = {
            'company_id': 'test_tenant_alpha',
            'display_name': 'Test Tenant Alpha LLC',
            'subscription_tier': 'starter',
            'subscription_status': 'active'
        }
        
        event = make_event('/admin/tenant-info', http_method='GET', groups=['owner'], custom_company_id='test_tenant_alpha')
        resp = admin_handler(event, None)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['company_id'] == 'test_tenant_alpha'
        assert body['display_name'] == 'Test Tenant Alpha LLC'
        assert body['subscription_tier'] == 'starter'
        assert body['subscription_status'] == 'active'
        assert body['google_calendar_status'] == 'NOT_CONNECTED'
