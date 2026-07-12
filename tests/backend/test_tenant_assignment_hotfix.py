"""
Tests for tenant assignment hotfix: custom:company_id must be set on all
Cognito identity provisioning paths using trusted server-side context.

Covers:
- build_tenant_user_attribute helper
- ensure_cognito_tenant_attribute helper
- Staff onboarding includes tenant attribute
- Client onboarding includes tenant attribute
- Link-cognito repairs missing tenant attribute
- Link-cognito preserves matching tenant
- Link-cognito denies cross-tenant mismatch
- Tenant resolution: valid claim resolves, missing claim denied in multi mode
- Public intake: documents current behavior
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime

# Set required env vars before imports
os.environ.setdefault('DEFAULT_COMPANY_ID', 'tog_and_dogs')
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')
os.environ.setdefault('ADMIN_USER_POOL_ID', 'us-east-1_TestPool')
os.environ.setdefault('GOOGLE_CLIENT_CREDS_NAME', 'google-creds')
os.environ.setdefault('GOOGLE_USER_TOKENS_NAME', 'google-tokens')


def make_admin_event(path, http_method='POST', groups=None, custom_company_id='tog_and_dogs',
                     email='admin@example.com', sub='admin-sub-123', body=None):
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
            'authorizer': {'claims': claims},
            'requestId': 'test-req-id'
        },
        'httpMethod': http_method,
        'path': path,
        'pathParameters': {},
    }
    if body:
        event['body'] = json.dumps(body)
    return event


# ==============================================================================
# 1. build_tenant_user_attribute Helper Tests
# ==============================================================================

class TestBuildTenantUserAttribute:

    def test_valid_company_id(self):
        from common.auth import build_tenant_user_attribute
        result = build_tenant_user_attribute('tog_and_dogs')
        assert result == {'Name': 'custom:company_id', 'Value': 'tog_and_dogs'}

    def test_strips_whitespace(self):
        from common.auth import build_tenant_user_attribute
        result = build_tenant_user_attribute('  tog_and_dogs  ')
        assert result == {'Name': 'custom:company_id', 'Value': 'tog_and_dogs'}

    def test_empty_string_raises(self):
        from common.auth import build_tenant_user_attribute
        with pytest.raises(ValueError, match="company_id is empty"):
            build_tenant_user_attribute('')

    def test_none_raises(self):
        from common.auth import build_tenant_user_attribute
        with pytest.raises(ValueError, match="company_id is empty"):
            build_tenant_user_attribute(None)

    def test_whitespace_only_raises(self):
        from common.auth import build_tenant_user_attribute
        with pytest.raises(ValueError, match="company_id is empty"):
            build_tenant_user_attribute('   ')


# ==============================================================================
# 2. ensure_cognito_tenant_attribute Helper Tests
# ==============================================================================

class TestEnsureCognitoTenantAttribute:

    def test_sets_attribute_when_missing(self):
        from common.auth import ensure_cognito_tenant_attribute
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.return_value = {
            'UserAttributes': [
                {'Name': 'email', 'Value': 'user@example.com'},
                {'Name': 'sub', 'Value': 'some-sub'},
            ]
        }

        ensure_cognito_tenant_attribute(mock_cognito, 'pool-id', 'user@example.com', 'tog_and_dogs')

        mock_cognito.admin_update_user_attributes.assert_called_once_with(
            UserPoolId='pool-id',
            Username='user@example.com',
            UserAttributes=[{'Name': 'custom:company_id', 'Value': 'tog_and_dogs'}]
        )

    def test_no_update_when_already_correct(self):
        from common.auth import ensure_cognito_tenant_attribute
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.return_value = {
            'UserAttributes': [
                {'Name': 'custom:company_id', 'Value': 'tog_and_dogs'},
            ]
        }

        ensure_cognito_tenant_attribute(mock_cognito, 'pool-id', 'user@example.com', 'tog_and_dogs')

        mock_cognito.admin_update_user_attributes.assert_not_called()

    def test_denies_cross_tenant_mismatch(self):
        from common.auth import ensure_cognito_tenant_attribute
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.return_value = {
            'UserAttributes': [
                {'Name': 'custom:company_id', 'Value': 'other_tenant'},
            ]
        }

        with pytest.raises(PermissionError, match="Cross-tenant identity conflict"):
            ensure_cognito_tenant_attribute(mock_cognito, 'pool-id', 'user@example.com', 'tog_and_dogs')

        mock_cognito.admin_update_user_attributes.assert_not_called()

    def test_empty_company_id_raises(self):
        from common.auth import ensure_cognito_tenant_attribute
        mock_cognito = MagicMock()

        with pytest.raises(ValueError, match="company_id is empty"):
            ensure_cognito_tenant_attribute(mock_cognito, 'pool-id', 'user@example.com', '')


# ==============================================================================
# 3. Staff Onboarding — Trusted Tenant Assignment (Code Verification)
# ==============================================================================

class TestStaffOnboardingTenantAssignment:

    def test_build_tenant_attribute_used_in_staff_onboard(self):
        """Verify the staff onboarding code path uses build_tenant_user_attribute."""
        import inspect
        from handlers.admin_handler import handler
        source = inspect.getsource(handler)
        # The staff onboard section should reference build_tenant_user_attribute
        assert 'build_tenant_user_attribute' in source
        # And it should be called with company_id
        assert 'build_tenant_user_attribute(company_id)' in source

    def test_build_tenant_attribute_produces_correct_value(self):
        """build_tenant_user_attribute produces the correct Cognito attribute for staff creation."""
        from common.auth import build_tenant_user_attribute
        attr = build_tenant_user_attribute('tog_and_dogs')
        assert attr == {'Name': 'custom:company_id', 'Value': 'tog_and_dogs'}
        # This attribute would be included in the UserAttributes list for admin_create_user


# ==============================================================================
# 4. Client Onboarding — Trusted Tenant Assignment (Code Verification)
# ==============================================================================

class TestClientOnboardingTenantAssignment:

    def test_build_tenant_attribute_used_in_client_onboard(self):
        """Verify the client onboarding code path uses build_tenant_user_attribute."""
        import inspect
        from handlers.admin_handler import handler
        source = inspect.getsource(handler)
        # Count occurrences — should appear at least twice (staff + client)
        occurrences = source.count('build_tenant_user_attribute(company_id)')
        assert occurrences >= 2, f"Expected at least 2 uses of build_tenant_user_attribute, found {occurrences}"


# ==============================================================================
# 5. Link-Cognito — Tenant Repair and Mismatch Protection
# ==============================================================================

class TestLinkCognitoTenantProtection:

    def test_ensure_tenant_attribute_used_in_link_cognito(self):
        """Verify the link-cognito code path uses ensure_cognito_tenant_attribute."""
        import inspect
        from handlers.admin_handler import handler
        source = inspect.getsource(handler)
        assert 'ensure_cognito_tenant_attribute' in source

    def test_ensure_repairs_missing(self):
        """ensure_cognito_tenant_attribute sets attribute when missing."""
        from common.auth import ensure_cognito_tenant_attribute
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.return_value = {
            'UserAttributes': [
                {'Name': 'email', 'Value': 'user@example.com'},
            ]
        }
        ensure_cognito_tenant_attribute(mock_cognito, 'pool', 'user@example.com', 'tog_and_dogs')
        mock_cognito.admin_update_user_attributes.assert_called_once()
        call_attrs = mock_cognito.admin_update_user_attributes.call_args
        attrs = call_attrs.kwargs.get('UserAttributes') or call_attrs[1].get('UserAttributes')
        assert {'Name': 'custom:company_id', 'Value': 'tog_and_dogs'} in attrs

    def test_ensure_denies_cross_tenant(self):
        """ensure_cognito_tenant_attribute raises PermissionError on cross-tenant."""
        from common.auth import ensure_cognito_tenant_attribute
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.return_value = {
            'UserAttributes': [
                {'Name': 'custom:company_id', 'Value': 'test_tenant_alpha'},
            ]
        }
        with pytest.raises(PermissionError, match="Cross-tenant"):
            ensure_cognito_tenant_attribute(mock_cognito, 'pool', 'user@example.com', 'tog_and_dogs')

    def test_ensure_preserves_matching_tenant(self):
        """ensure_cognito_tenant_attribute does nothing when already correct."""
        from common.auth import ensure_cognito_tenant_attribute
        mock_cognito = MagicMock()
        mock_cognito.admin_get_user.return_value = {
            'UserAttributes': [
                {'Name': 'custom:company_id', 'Value': 'tog_and_dogs'},
            ]
        }
        ensure_cognito_tenant_attribute(mock_cognito, 'pool', 'user@example.com', 'tog_and_dogs')
        mock_cognito.admin_update_user_attributes.assert_not_called()


# ==============================================================================
# 6. Tenant Resolution Tests
# ==============================================================================

class TestTenantResolution:

    def test_valid_claim_resolves(self):
        from common.auth import get_current_company_id
        event = make_admin_event('/admin/test', custom_company_id='tog_and_dogs')
        result = get_current_company_id(event)
        assert result == 'tog_and_dogs'

    def test_missing_claim_denied_in_multi_mode(self):
        from common.auth import get_current_company_id
        event = make_admin_event('/admin/test', custom_company_id=None)
        # When custom_company_id=None, the key is not added by make_admin_event
        # Ensure it doesn't exist
        event['requestContext']['authorizer']['claims'].pop('custom:company_id', None)

        with patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'}):
            with pytest.raises(PermissionError, match="TENANT_RESOLUTION_FAILED"):
                get_current_company_id(event)

    def test_empty_claim_denied_in_multi_mode(self):
        from common.auth import get_current_company_id
        event = make_admin_event('/admin/test', custom_company_id='')

        with patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'}):
            with pytest.raises(PermissionError, match="TENANT_RESOLUTION_FAILED"):
                get_current_company_id(event)

    def test_unknown_tenant_still_resolves_if_present(self):
        """An unknown tenant value still resolves — enforcement is at the data layer."""
        from common.auth import get_current_company_id
        event = make_admin_event('/admin/test', custom_company_id='nonexistent_tenant')
        result = get_current_company_id(event)
        assert result == 'nonexistent_tenant'


# ==============================================================================
# 7. Public Intake Tenant Resolution (Documenting Current Behavior)
# ==============================================================================

class TestPublicIntakeTenantResolution:

    def test_unauthenticated_request_denied_in_multi_mode(self):
        """Public intake with no auth claims raises TENANT_RESOLUTION_FAILED in multi mode."""
        from common.auth import get_current_company_id
        # Simulate an unauthenticated request (no authorizer claims)
        event = {
            'requestContext': {},
            'httpMethod': 'POST',
            'path': '/requests',
            'body': json.dumps({'client_name': 'Test', 'start_date': '2026-08-01'}),
        }

        with patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'}):
            with pytest.raises(PermissionError, match="TENANT_RESOLUTION_FAILED"):
                get_current_company_id(event)
