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

from common.calendar_metadata import get_tenant_calendar_config
from handlers.admin_handler import handler as admin_handler
from handlers.google_auth_handler import handler as google_auth_handler

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

class TestCalendarMetadataDerivation:
    def test_default_tenant_derives_google_defaults(self):
        """1. Tenant with no calendar fields and company_id=tog_and_dogs derives Google defaults."""
        tenant_record = {
            "company_id": "tog_and_dogs",
            "display_name": "Tog and Dogs"
        }
        config = get_tenant_calendar_config(tenant_record, google_status="CONNECTED")
        assert config["calendar_provider"] == "google"
        assert config["calendar_enabled"] is True
        assert config["calendar_connection_status"] == "connected"
        assert config["calendar_connected_account_label"] == "Google Calendar"
        assert config["calendar_secret_ref"] == "togs-and-dogs-prod/google/user-tokens"
        assert config["calendar_capabilities"]["create_events"] is True

    def test_non_default_tenant_derives_none_defaults(self):
        """2. Tenant with no calendar fields and non-default company derives none/not_configured."""
        tenant_record = {
            "company_id": "test_tenant_alpha",
            "display_name": "Test Tenant Alpha"
        }
        config = get_tenant_calendar_config(tenant_record)
        assert config["calendar_provider"] == "none"
        assert config["calendar_enabled"] is False
        assert config["calendar_connection_status"] == "not_configured"
        assert config["calendar_connected_account_label"] is None
        assert config["calendar_secret_ref"] is None
        assert config["calendar_capabilities"]["create_events"] is False

    def test_explicit_metadata_overrides_defaults(self):
        """3. Explicit metadata values override code defaults safely."""
        tenant_record = {
            "company_id": "test_tenant_alpha",
            "display_name": "Test Tenant Alpha",
            "calendar_provider": "microsoft",
            "calendar_enabled": True,
            "calendar_connection_status": "connected",
            "calendar_connected_account_label": "Office365 Sitter Calendar",
            "calendar_secret_ref": "togs-and-dogs-prod/calendar/test_tenant_alpha/tokens",
            "calendar_capabilities": {
                "create_events": True,
                "update_events": True,
                "delete_events": True,
                "read_events": True,
                "disconnect_supported": False
            }
        }
        config = get_tenant_calendar_config(tenant_record)
        assert config["calendar_provider"] == "microsoft"
        assert config["calendar_enabled"] is True
        assert config["calendar_connection_status"] == "connected"
        assert config["calendar_connected_account_label"] == "Office365 Sitter Calendar"
        assert config["calendar_secret_ref"] == "togs-and-dogs-prod/calendar/test_tenant_alpha/tokens"
        assert config["calendar_capabilities"]["disconnect_supported"] is False

class TestAdminTenantInfoEndpoint:
    @patch('handlers.admin_handler.get_item')
    @patch('common.entitlement._get_entitlement_safely')
    @patch('handlers.google_auth_handler.get_status')
    def test_tenant_info_includes_calendar_metadata(self, mock_google_status, mock_get_entitlement, mock_get_item):
        """4. /admin/tenant-info includes safe calendar metadata."""
        mock_get_item.return_value = {
            "company_id": "test_tenant_alpha",
            "display_name": "Test Tenant Alpha",
            "subscription_tier": "starter",
            "subscription_status": "active"
        }
        mock_get_entitlement.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
        
        event = make_event('/admin/tenant-info', custom_company_id='test_tenant_alpha', groups=['owner'])
        result = admin_handler(event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        
        assert body["calendar_provider"] == "none"
        assert body["calendar_enabled"] is False
        assert body["calendar_connection_status"] == "not_configured"
        assert "calendar_capabilities" in body
        # 8. Confirm no secret/token values are returned in API payloads.
        assert "token" not in result['body']
        assert "refresh_token" not in result['body']

    @patch('handlers.admin_handler.get_item')
    @patch('common.entitlement._get_entitlement_safely')
    def test_disabled_tenant_info_minimal_only(self, mock_get_entitlement, mock_get_item):
        """5. Disabled tenant /admin/tenant-info still returns minimal safe status only."""
        mock_get_item.return_value = {
            "company_id": "test_tenant_alpha",
            "display_name": "Test Tenant Alpha",
            "subscription_tier": "starter",
            "subscription_status": "disabled"
        }
        mock_get_entitlement.return_value = MagicMock(is_access_allowed=False, is_blocked=True)
        
        event = make_event('/admin/tenant-info', custom_company_id='test_tenant_alpha', groups=['owner'])
        result = admin_handler(event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        
        assert body["company_id"] == "test_tenant_alpha"
        assert body["display_name"] == "Test Tenant Alpha"
        assert body["subscription_status"] == "disabled"
        assert body["is_access_allowed"] is False
        assert body["is_blocked"] is True
        # Ensure no calendar metadata is included
        assert "calendar_provider" not in body
        assert "calendar_capabilities" not in body

class TestCalendarGatingAndPreservation:
    @patch('common.db.table.get_item')
    @patch('common.entitlement._get_entitlement_safely')
    def test_non_default_tenant_blocks_google_connect(self, entitlement, metadata):
        """6. Non-default tenant does not trigger Google auth/connect path."""
        entitlement.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
        metadata.return_value = {'Item': {
            'PK': 'TENANT#test_tenant_alpha', 'SK': 'METADATA',
            'company_id': 'test_tenant_alpha', 'calendar_provider': 'none'}}
        event = make_event('/admin/auth/google', custom_company_id='test_tenant_alpha', groups=['owner'])
        result = google_auth_handler(event, None)
        assert result['statusCode'] == 403
        body = json.loads(result['body'])
        assert "not supported for this tenant" in body['error']



    @patch('handlers.admin_handler.get_item')
    @patch('common.entitlement._get_entitlement_safely')
    @patch('handlers.google_auth_handler.get_status')
    def test_default_tenant_google_calendar_preserved(self, mock_google_status, mock_get_entitlement, mock_get_item):
        """7. Existing Google Calendar behavior for tog_and_dogs is preserved."""
        mock_get_item.return_value = {
            "company_id": "tog_and_dogs",
            "display_name": "Togs & Dogs",
            "subscription_tier": "starter",
            "subscription_status": "active"
        }
        mock_get_entitlement.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
        mock_google_status.return_value = {
            "statusCode": 200,
            "body": json.dumps({"status": "CONNECTED"})
        }
        
        event = make_event('/admin/tenant-info', custom_company_id='tog_and_dogs', groups=['owner'])
        result = admin_handler(event, None)
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        
        assert body["calendar_provider"] == "google"
        assert body["calendar_enabled"] is True
        assert body["calendar_connection_status"] == "connected"
        assert body["calendar_connected_account_label"] == "Google Calendar"
        assert body["calendar_capabilities"]["create_events"] is True
