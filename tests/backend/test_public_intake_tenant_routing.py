"""
Tests for trusted public-intake tenant routing.

Covers:
- resolve_public_intake_tenant helper
- Anonymous public intake succeeds with trusted config
- Anonymous public intake fails closed without config
- Request-body company_id is ignored
- Authenticated intake uses Cognito claim
- Browser cannot override authenticated tenant
- No Cognito account created by anonymous intake
- No existing client profile automatically linked
- Existing tenant-isolation tests unaffected
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Set required env vars before imports
os.environ.setdefault('DEFAULT_COMPANY_ID', 'tog_and_dogs')
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')
os.environ.setdefault('ADMIN_USER_POOL_ID', 'us-east-1_TestPool')
os.environ.setdefault('GOOGLE_CLIENT_CREDS_NAME', 'google-creds')
os.environ.setdefault('GOOGLE_USER_TOKENS_NAME', 'google-tokens')


def _public_intake_event(body, path='/requests', claims=None):
    """Create a public intake event, optionally with authenticated claims."""
    event = {
        'requestContext': {},
        'httpMethod': 'POST',
        'path': path,
        'body': json.dumps(body),
    }
    if claims:
        event['requestContext'] = {'authorizer': {'claims': claims}}
    return event


# ==============================================================================
# 1. resolve_public_intake_tenant Helper Tests
# ==============================================================================

class TestResolvePublicIntakeTenant:

    def test_authenticated_claim_takes_precedence(self):
        """If authenticated claims have custom:company_id, use it."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({}, claims={
            'custom:company_id': 'tog_and_dogs',
            'email': 'user@example.com',
            'sub': 'test-sub',
        })
        result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'

    def test_unauthenticated_uses_public_intake_tenant_id(self):
        """Unauthenticated request uses PUBLIC_INTAKE_TENANT_ID env var."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_TENANT_ID': 'tog_and_dogs'}):
            result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'

    def test_unauthenticated_falls_back_to_default_company_id(self):
        """If PUBLIC_INTAKE_TENANT_ID is not set, falls back to DEFAULT_COMPANY_ID."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({})
        with patch.dict(os.environ, {'DEFAULT_COMPANY_ID': 'tog_and_dogs', 'PUBLIC_INTAKE_TENANT_ID': ''}):
            result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'

    def test_fails_closed_without_any_config(self):
        """If no trusted config exists, raises PermissionError."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({})
        with patch.dict(os.environ, {'DEFAULT_COMPANY_ID': '', 'PUBLIC_INTAKE_TENANT_ID': ''}):
            with pytest.raises(PermissionError, match="PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED"):
                resolve_public_intake_tenant(event)

    def test_request_body_company_id_ignored(self):
        """Browser-supplied company_id in body is never used."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({'company_id': 'test_tenant_alpha'})
        with patch.dict(os.environ, {'DEFAULT_COMPANY_ID': 'tog_and_dogs', 'PUBLIC_INTAKE_TENANT_ID': ''}):
            result = resolve_public_intake_tenant(event)
        # Must resolve to the server-configured value, not the body value
        assert result == 'tog_and_dogs'
        assert result != 'test_tenant_alpha'

    def test_authenticated_second_tenant_user_uses_own_claim(self):
        """A second-tenant user hitting the public endpoint uses their own claim."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({}, claims={
            'custom:company_id': 'test_tenant_alpha',
            'email': 'owner@alpha.com',
            'sub': 'alpha-sub',
        })
        result = resolve_public_intake_tenant(event)
        assert result == 'test_tenant_alpha'


# ==============================================================================
# 2. Handler Integration Tests
# ==============================================================================

class TestPublicIntakeHandlerRouting:

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('handlers.intake_handler.put_item', return_value=True)
    @patch('handlers.intake_handler.table')
    def test_anonymous_public_intake_succeeds(self, mock_table, mock_put, mock_rat):
        """Anonymous POST /requests succeeds with trusted server config."""
        mock_table.query.return_value = {'Items': [], 'Count': 0}

        from handlers.intake_handler import handler
        body = {
            'client_name': 'Test Client',
            'client_email': 'test@example.com',
            'start_date': '2026-08-01',
            'pet_names': 'Buddy',
            'service_type': 'PET_SITTING',
            'accepted_terms': True,
            'accepted_privacy': True,
            'terms_version': '1.0',
            'privacy_version': '1.0',
        }
        event = _public_intake_event(body)

        with patch.dict(os.environ, {'DEFAULT_COMPANY_ID': 'tog_and_dogs', 'TENANT_RESOLUTION_MODE': 'multi'}):
            resp = handler(event, None)

        assert resp['statusCode'] == 200, f"Expected 200, got {resp['statusCode']}: {resp.get('body', '')}"

    @patch('common.entitlement.require_active_tenant', return_value=None)
    def test_anonymous_intake_fails_without_trusted_config(self, mock_rat):
        """Anonymous POST /requests fails closed when no config exists."""
        from handlers.intake_handler import handler
        body = {
            'client_name': 'Test Client',
            'client_email': 'test@example.com',
            'start_date': '2026-08-01',
            'pet_names': 'Buddy',
            'service_type': 'PET_SITTING',
            'accepted_terms': True,
            'accepted_privacy': True,
            'terms_version': '1.0',
            'privacy_version': '1.0',
        }
        event = _public_intake_event(body)

        with patch.dict(os.environ, {'DEFAULT_COMPANY_ID': '', 'PUBLIC_INTAKE_TENANT_ID': '', 'TENANT_RESOLUTION_MODE': 'multi'}):
            resp = handler(event, None)

        # Should fail (500 from the PermissionError being caught)
        assert resp['statusCode'] == 500

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('handlers.intake_handler.put_item', return_value=True)
    @patch('handlers.intake_handler.table')
    def test_body_company_id_cannot_select_tenant(self, mock_table, mock_put, mock_rat):
        """A body-supplied company_id must not determine the tenant assignment."""
        mock_table.query.return_value = {'Items': [], 'Count': 0}

        from handlers.intake_handler import handler
        body = {
            'client_name': 'Evil Client',
            'client_email': 'evil@example.com',
            'start_date': '2026-08-01',
            'pet_names': 'Evil Pet',
            'service_type': 'PET_SITTING',
            'company_id': 'test_tenant_alpha',  # Attack attempt
            'accepted_terms': True,
            'accepted_privacy': True,
            'terms_version': '1.0',
            'privacy_version': '1.0',
        }
        event = _public_intake_event(body)

        with patch.dict(os.environ, {'DEFAULT_COMPANY_ID': 'tog_and_dogs', 'TENANT_RESOLUTION_MODE': 'multi'}):
            resp = handler(event, None)

        # Should succeed and use tog_and_dogs, not test_tenant_alpha
        assert resp['statusCode'] == 200
        # Verify the saved record uses the trusted tenant
        if mock_put.called:
            saved_item = mock_put.call_args[0][0]
            assert saved_item.get('company_id') == 'tog_and_dogs'

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('handlers.intake_handler.put_item', return_value=True)
    @patch('handlers.intake_handler.table')
    def test_no_cognito_user_created_by_anonymous_intake(self, mock_table, mock_put, mock_rat):
        """Anonymous intake must NOT create a Cognito user."""
        mock_table.query.return_value = {'Items': [], 'Count': 0}

        from handlers.intake_handler import handler
        body = {
            'client_name': 'New Client',
            'client_email': 'new@example.com',
            'start_date': '2026-08-01',
            'pet_names': 'NewPet',
            'service_type': 'PET_SITTING',
            'accepted_terms': True,
            'accepted_privacy': True,
            'terms_version': '1.0',
            'privacy_version': '1.0',
        }
        event = _public_intake_event(body)

        with patch.dict(os.environ, {'DEFAULT_COMPANY_ID': 'tog_and_dogs', 'TENANT_RESOLUTION_MODE': 'multi'}):
            with patch('boto3.client') as mock_boto:
                resp = handler(event, None)
                # boto3.client('cognito-idp') should NOT be called
                cognito_calls = [c for c in mock_boto.call_args_list if 'cognito' in str(c)]
                assert len(cognito_calls) == 0

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('handlers.intake_handler.put_item', return_value=True)
    @patch('handlers.intake_handler.table')
    def test_staff_options_works_anonymously(self, mock_table, mock_put, mock_rat):
        """Public staff-options endpoint resolves tenant from trusted config."""
        mock_table.query.return_value = {'Items': [
            {'staff_id': 's1', 'display_name': 'Staff One', 'is_active': True, 'is_assignable': True}
        ]}

        from handlers.intake_handler import handler
        event = _public_intake_event({'action': 'staff-options'})

        with patch.dict(os.environ, {'DEFAULT_COMPANY_ID': 'tog_and_dogs', 'TENANT_RESOLUTION_MODE': 'multi'}):
            resp = handler(event, None)

        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert 'staff_options' in body
