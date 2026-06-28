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

from common.entitlement import require_active_tenant, TenantEntitlement
from handlers.admin_handler import handler as admin_handler
from handlers.assignment_handler import handler as assignment_handler
from handlers.cancellation_handler import handler as cancellation_handler
from handlers.device_handler import handler as device_handler
from handlers.google_auth_handler import handler as google_auth_handler
from handlers.intake_handler import handler as intake_handler
from handlers.pet_handler import handler as pet_handler
from handlers.review_handler import handler as review_handler

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
        'headers': {'origin': 'https://toganddogs.usmissionhero.com'}
    }
    if body:
        event['body'] = json.dumps(body)
    return event

# ==============================================================================
# 1. require_active_tenant Helper Tests
# ==============================================================================

class TestRequireActiveTenantHelper:

    @patch('common.entitlement._get_entitlement_safely')
    def test_active_tenant_allowed(self, mock_get_entitlement):
        """Active tenant is allowed and returns None."""
        mock_get_entitlement.return_value = TenantEntitlement(
            company_id='test_tenant_alpha',
            subscription_tier='starter',
            subscription_status='active'
        )
        event = make_event('/admin/some-route', custom_company_id='test_tenant_alpha', groups=['owner'])
        result = require_active_tenant(event)
        assert result is None

    @patch('common.entitlement._get_entitlement_safely')
    def test_disabled_tenant_blocked(self, mock_get_entitlement):
        """Disabled tenant is blocked and returns 403 response."""
        mock_get_entitlement.return_value = TenantEntitlement(
            company_id='test_tenant_alpha',
            subscription_tier='starter',
            subscription_status='disabled'
        )
        event = make_event('/admin/some-route', custom_company_id='test_tenant_alpha', groups=['owner'])
        result = require_active_tenant(event)
        assert result is not None
        assert result['statusCode'] == 403
        body = json.loads(result['body'])
        assert body['error'] == 'TenantDisabled'

    @patch('common.entitlement._get_entitlement_safely')
    def test_platform_admin_bypass(self, mock_get_entitlement):
        """Platform admin bypasses tenant status check."""
        mock_get_entitlement.return_value = TenantEntitlement(
            company_id='test_tenant_alpha',
            subscription_tier='starter',
            subscription_status='disabled'
        )
        event = make_event('/admin/some-route', custom_company_id='test_tenant_alpha', groups=['platform_admin'])
        result = require_active_tenant(event)
        assert result is None

# ==============================================================================
# 2. Handler Route Gating Tests
# ==============================================================================

class TestHandlerRouteGating:

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        self.get_item_patch = patch('handlers.admin_handler.get_item')
        self.mock_get_item = self.get_item_patch.start()
        
        self.ent_patch = patch('common.entitlement._get_entitlement_safely')
        self.mock_ent = self.ent_patch.start()
        
        yield
        
        self.get_item_patch.stop()
        self.ent_patch.stop()

    def test_tenant_info_disabled_minimal_status(self):
        """tenant-info returns 200 with minimal fields when tenant is disabled."""
        self.mock_get_item.return_value = {
            'company_id': 'test_tenant_alpha',
            'display_name': 'Test Tenant Alpha',
            'subscription_tier': 'starter',
            'subscription_status': 'disabled'
        }
        self.mock_ent.return_value = TenantEntitlement(
            company_id='test_tenant_alpha',
            subscription_tier='starter',
            subscription_status='disabled'
        )
        
        event = make_event('/admin/tenant-info', http_method='GET', custom_company_id='test_tenant_alpha', groups=['owner'])
        resp = admin_handler(event, None)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['company_id'] == 'test_tenant_alpha'
        assert body['display_name'] == 'Test Tenant Alpha'
        assert body['subscription_status'] == 'disabled'
        assert body['is_access_allowed'] is False
        assert body['is_blocked'] is True
        assert 'google_calendar_status' not in body

    def test_tenant_info_active_full_status(self):
        """tenant-info returns 200 with full status when tenant is active."""
        self.mock_get_item.return_value = {
            'company_id': 'test_tenant_alpha',
            'display_name': 'Test Tenant Alpha',
            'subscription_tier': 'starter',
            'subscription_status': 'active'
        }
        self.mock_ent.return_value = TenantEntitlement(
            company_id='test_tenant_alpha',
            subscription_tier='starter',
            subscription_status='active'
        )
        
        event = make_event('/admin/tenant-info', http_method='GET', custom_company_id='test_tenant_alpha', groups=['owner'])
        resp = admin_handler(event, None)
        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert body['company_id'] == 'test_tenant_alpha'
        assert body['subscription_status'] == 'active'
        assert body['is_access_allowed'] is True
        assert body['is_blocked'] is False
        assert body['google_calendar_status'] == 'NOT_CONNECTED'

    def test_admin_handler_other_routes_blocked(self):
        """Other routes in admin_handler return 403 when tenant is disabled."""
        self.mock_ent.return_value = TenantEntitlement(
            company_id='test_tenant_alpha',
            subscription_tier='starter',
            subscription_status='disabled'
        )
        
        event = make_event('/admin/export-data', http_method='GET', custom_company_id='test_tenant_alpha', groups=['owner'])
        resp = admin_handler(event, None)
        assert resp['statusCode'] == 403
        body = json.loads(resp['body'])
        assert body['error'] == 'TenantDisabled'

    def test_assignment_handler_blocked(self):
        """assignment_handler returns 403 when tenant is disabled."""
        self.mock_ent.return_value = TenantEntitlement(
            company_id='test_tenant_alpha',
            subscription_tier='starter',
            subscription_status='disabled'
        )
        event = make_event('/admin/assign', http_method='POST', custom_company_id='test_tenant_alpha', groups=['owner'], body={'job_id': '123'})
        resp = assignment_handler(event, None)
        assert resp['statusCode'] == 403
        body = json.loads(resp['body'])
        assert body['error'] == 'TenantDisabled'

    def test_cancellation_handler_blocked(self):
        """cancellation_handler returns 403 when tenant is disabled."""
        self.mock_ent.return_value = TenantEntitlement(
            company_id='test_tenant_alpha',
            subscription_tier='starter',
            subscription_status='disabled'
        )
        event = make_event('/admin/cancel', http_method='POST', custom_company_id='test_tenant_alpha', groups=['owner'], body={'request_id': '123'})
        resp = cancellation_handler(event, None)
        assert resp['statusCode'] == 403
        body = json.loads(resp['body'])
        assert body['error'] == 'TenantDisabled'

    def test_device_handler_blocked(self):
        """device_handler returns 403 when tenant is disabled."""
        self.mock_ent.return_value = TenantEntitlement(
            company_id='test_tenant_alpha',
            subscription_tier='starter',
            subscription_status='disabled'
        )
        event = make_event('/device/register', http_method='POST', custom_company_id='test_tenant_alpha', groups=['owner'], body={'push_token': 'ExponentPushToken[xxx]'})
        resp = device_handler(event, None)
        assert resp['statusCode'] == 403
        body = json.loads(resp['body'])
        assert body['error'] == 'TenantDisabled'

    @patch('handlers.google_auth_handler.secrets')
    def test_google_auth_handler_blocked_for_users(self, mock_secrets):
        """google_auth_handler returns 403 for user OAuth requests when tenant is disabled."""
        self.mock_ent.return_value = TenantEntitlement(
            company_id='test_tenant_alpha',
            subscription_tier='starter',
            subscription_status='disabled'
        )
        event = make_event('/admin/auth/google', http_method='GET', custom_company_id='test_tenant_alpha', groups=['owner'])
        resp = google_auth_handler(event, None)
        assert resp['statusCode'] == 403
        body = json.loads(resp['body'])
        assert body['error'] == 'TenantDisabled'

    @patch('handlers.google_auth_handler.calendar_health_check')
    def test_google_auth_handler_allowed_for_scheduler(self, mock_health_check):
        """google_auth_handler allows scheduled EventBridge health check even if disabled."""
        mock_health_check.return_value = {'statusCode': 200, 'body': '{"status":"OK"}'}
        event = {
            'source': 'aws.scheduler',
            'action': 'health_check'
        }
        resp = google_auth_handler(event, None)
        assert resp['statusCode'] == 200
        mock_health_check.assert_called_once()

    def test_intake_handler_blocked(self):
        """intake_handler returns 403 when tenant is disabled."""
        self.mock_ent.return_value = TenantEntitlement(
            company_id='test_tenant_alpha',
            subscription_tier='starter',
            subscription_status='disabled'
        )
        event = make_event('/client/requests', http_method='POST', custom_company_id='test_tenant_alpha', groups=['client'], body={'client_name': 'Test', 'client_email': 'test@example.com'})
        resp = intake_handler(event, None)
        assert resp['statusCode'] == 403
        body = json.loads(resp['body'])
        assert body['error'] == 'TenantDisabled'

    def test_pet_handler_blocked(self):
        """pet_handler returns 403 when tenant is disabled."""
        self.mock_ent.return_value = TenantEntitlement(
            company_id='test_tenant_alpha',
            subscription_tier='starter',
            subscription_status='disabled'
        )
        event = make_event('/client/pets', http_method='GET', custom_company_id='test_tenant_alpha', groups=['client'])
        resp = pet_handler(event, None)
        assert resp['statusCode'] == 403
        body = json.loads(resp['body'])
        assert body['error'] == 'TenantDisabled'

    def test_review_handler_blocked(self):
        """review_handler returns 403 when tenant is disabled."""
        self.mock_ent.return_value = TenantEntitlement(
            company_id='test_tenant_alpha',
            subscription_tier='starter',
            subscription_status='disabled'
        )
        event = make_event('/admin/review', http_method='POST', custom_company_id='test_tenant_alpha', groups=['owner'], body={'client_id': '123', 'status': 'APPROVED'})
        resp = review_handler(event, None)
        assert resp['statusCode'] == 403
        body = json.loads(resp['body'])
        assert body['error'] == 'TenantDisabled'
