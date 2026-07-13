"""
Tests for trusted domain-based public-intake tenant routing.

Covers:
- Domain-to-tenant resolution via PUBLIC_INTAKE_DOMAIN_MAP
- Anonymous intake succeeds through mapped Togs & Dogs domain
- Anonymous intake fails when no domain mapping exists
- Unknown domain fails closed
- Inactive domain mapping fails
- Domain not enabled for public intake fails
- Invalid JSON in domain map fails closed
- Request-body company_id is ignored
- Query-string company_id is ignored
- Authenticated intake uses Cognito claim
- Authenticated claim/domain match succeeds
- Authenticated claim/domain mismatch is denied
- No Cognito account created by anonymous intake
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

# The production API Gateway domain
PROD_API_DOMAIN = 'a022yxuiue.execute-api.us-east-1.amazonaws.com'

# Standard domain map for Togs & Dogs
TOGS_DOMAIN_MAP = json.dumps({
    PROD_API_DOMAIN: {
        "tenant_id": "tog_and_dogs",
        "active": True,
        "public_intake_enabled": True
    }
})


def _public_intake_event(body, path='/requests', claims=None, domain_name=PROD_API_DOMAIN):
    """Create a public intake event with API Gateway domain context."""
    event = {
        'requestContext': {
            'domainName': domain_name,
        },
        'httpMethod': 'POST',
        'path': path,
        'body': json.dumps(body),
    }
    if claims:
        event['requestContext']['authorizer'] = {'claims': claims}
    return event


# Active tenant record for tests that expect successful resolution
ACTIVE_TENANT_RECORD = {'subscription_status': 'active', 'is_active': True, 'company_id': 'tog_and_dogs'}


# ==============================================================================
# 1. resolve_public_intake_tenant Helper Tests
# ==============================================================================

class TestResolvePublicIntakeTenant:

    def test_authenticated_claim_takes_precedence(self):
        """If authenticated claims have custom:company_id matching domain, it resolves."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({}, claims={
            'custom:company_id': 'tog_and_dogs',
            'email': 'user@example.com',
            'sub': 'test-sub',
        })
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD):
                result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'

    def test_unauthenticated_uses_domain_mapping(self):
        """Unauthenticated request resolves tenant from domain map."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD):
                result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'

    def test_unknown_domain_fails_closed(self):
        """A domain not in the map raises PermissionError."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({}, domain_name='unknown.example.com')
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with pytest.raises(PermissionError, match="unrecognized service domain"):
                resolve_public_intake_tenant(event)

    def test_no_domain_map_configured_fails_closed(self):
        """If PUBLIC_INTAKE_DOMAIN_MAP is empty, fails closed."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': ''}):
            with pytest.raises(PermissionError, match="no trusted tenant mapping"):
                resolve_public_intake_tenant(event)

    def test_inactive_domain_mapping_fails(self):
        """Domain mapped but active=false is denied."""
        from common.auth import resolve_public_intake_tenant
        inactive_map = json.dumps({
            PROD_API_DOMAIN: {"tenant_id": "tog_and_dogs", "active": False, "public_intake_enabled": True}
        })
        event = _public_intake_event({})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': inactive_map}):
            with pytest.raises(PermissionError, match="not active"):
                resolve_public_intake_tenant(event)

    def test_public_intake_not_enabled_fails(self):
        """Domain mapped but public_intake_enabled=false is denied."""
        from common.auth import resolve_public_intake_tenant
        no_intake_map = json.dumps({
            PROD_API_DOMAIN: {"tenant_id": "tog_and_dogs", "active": True, "public_intake_enabled": False}
        })
        event = _public_intake_event({})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': no_intake_map}):
            with pytest.raises(PermissionError, match="not enabled"):
                resolve_public_intake_tenant(event)

    def test_invalid_json_domain_map_fails_closed(self):
        """Invalid JSON in domain map raises PermissionError."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': '{bad json'}):
            with pytest.raises(PermissionError, match="invalid domain configuration"):
                resolve_public_intake_tenant(event)

    def test_request_body_company_id_ignored(self):
        """Browser-supplied company_id in body is never used."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({'company_id': 'test_tenant_alpha'})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD):
                result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'
        assert result != 'test_tenant_alpha'

    def test_authenticated_domain_match_succeeds(self):
        """Authenticated claim matching domain tenant succeeds."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({}, claims={
            'custom:company_id': 'tog_and_dogs',
            'email': 'user@toganddogs.com',
            'sub': 'match-sub',
        })
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD):
                result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'

    def test_authenticated_domain_mismatch_denied(self):
        """Authenticated claim not matching domain tenant is denied."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({}, claims={
            'custom:company_id': 'test_tenant_alpha',
            'email': 'owner@alpha.com',
            'sub': 'alpha-sub',
        })
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with pytest.raises(PermissionError, match="MISMATCH"):
                resolve_public_intake_tenant(event)

    def test_direct_execute_api_mapped_succeeds(self):
        """The production execute-api domain is explicitly mapped and works."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({}, domain_name=PROD_API_DOMAIN)
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD):
                result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'

    def test_no_default_company_id_fallback_in_multi_mode(self):
        """Even with DEFAULT_COMPANY_ID set, does not fall back without domain map."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({})
        with patch.dict(os.environ, {
            'DEFAULT_COMPANY_ID': 'tog_and_dogs',
            'PUBLIC_INTAKE_DOMAIN_MAP': '',
            'TENANT_RESOLUTION_MODE': 'multi'
        }):
            with pytest.raises(PermissionError):
                resolve_public_intake_tenant(event)

    def test_error_does_not_reveal_tenant_id(self):
        """Error messages do not expose internal tenant identifiers."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({}, domain_name='unknown.example.com')
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            try:
                resolve_public_intake_tenant(event)
                assert False, "Should have raised"
            except PermissionError as e:
                assert 'tog_and_dogs' not in str(e)
                assert 'test_tenant_alpha' not in str(e)


# ==============================================================================
# 2. Handler Integration Tests
# ==============================================================================

class TestPublicIntakeHandlerRouting:

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD)
    @patch('handlers.intake_handler.put_item', return_value=True)
    @patch('handlers.intake_handler.table')
    def test_anonymous_public_intake_succeeds(self, mock_table, mock_put, mock_get, mock_rat):
        """Anonymous POST /requests succeeds through mapped domain."""
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

        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP, 'TENANT_RESOLUTION_MODE': 'multi'}):
            resp = handler(event, None)

        assert resp['statusCode'] == 200, f"Expected 200, got {resp['statusCode']}: {resp.get('body', '')}"

    @patch('common.entitlement.require_active_tenant', return_value=None)
    def test_anonymous_intake_fails_without_domain_map(self, mock_rat):
        """Anonymous POST /requests fails when no domain map configured."""
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

        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': '', 'TENANT_RESOLUTION_MODE': 'multi'}):
            resp = handler(event, None)

        assert resp['statusCode'] == 500

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD)
    @patch('handlers.intake_handler.put_item', return_value=True)
    @patch('handlers.intake_handler.table')
    def test_body_company_id_cannot_override_tenant(self, mock_table, mock_put, mock_get, mock_rat):
        """A body-supplied company_id does not determine tenant assignment."""
        mock_table.query.return_value = {'Items': [], 'Count': 0}

        from handlers.intake_handler import handler
        body = {
            'client_name': 'Evil Client',
            'client_email': 'evil@example.com',
            'start_date': '2026-08-01',
            'pet_names': 'Evil Pet',
            'service_type': 'PET_SITTING',
            'company_id': 'test_tenant_alpha',
            'accepted_terms': True,
            'accepted_privacy': True,
            'terms_version': '1.0',
            'privacy_version': '1.0',
        }
        event = _public_intake_event(body)

        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP, 'TENANT_RESOLUTION_MODE': 'multi'}):
            resp = handler(event, None)

        assert resp['statusCode'] == 200
        if mock_put.called:
            saved_item = mock_put.call_args[0][0]
            assert saved_item.get('company_id') == 'tog_and_dogs'

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD)
    @patch('handlers.intake_handler.put_item', return_value=True)
    @patch('handlers.intake_handler.table')
    def test_no_cognito_user_created(self, mock_table, mock_put, mock_get, mock_rat):
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

        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP, 'TENANT_RESOLUTION_MODE': 'multi'}):
            with patch('boto3.client') as mock_boto:
                resp = handler(event, None)
                cognito_calls = [c for c in mock_boto.call_args_list if 'cognito' in str(c)]
                assert len(cognito_calls) == 0

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD)
    @patch('handlers.intake_handler.put_item', return_value=True)
    @patch('handlers.intake_handler.table')
    def test_staff_options_works_with_domain_map(self, mock_table, mock_put, mock_get, mock_rat):
        """Staff-options endpoint resolves tenant from domain map."""
        mock_table.query.return_value = {'Items': [
            {'staff_id': 's1', 'display_name': 'Staff One', 'is_active': True, 'is_assignable': True}
        ]}

        from handlers.intake_handler import handler
        event = _public_intake_event({'action': 'staff-options'})

        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP, 'TENANT_RESOLUTION_MODE': 'multi'}):
            resp = handler(event, None)

        assert resp['statusCode'] == 200
        body = json.loads(resp['body'])
        assert 'staff_options' in body


# ==============================================================================
# 3. Additional Security and Guardrail Tests
# ==============================================================================

class TestBrowserInputRejection:
    """Prove that no browser-controlled value can influence tenant resolution."""

    def test_query_string_company_id_ignored(self):
        """Query-string company_id cannot select a tenant."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({})
        event['queryStringParameters'] = {'company_id': 'test_tenant_alpha'}
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD):
                result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'

    def test_origin_header_cannot_select_tenant(self):
        """Origin header cannot influence tenant resolution."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({})
        event['headers'] = {'Origin': 'https://test-tenant-alpha.example.com'}
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD):
                result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'

    def test_referer_header_cannot_select_tenant(self):
        """Referer header cannot influence tenant resolution."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({})
        event['headers'] = {'Referer': 'https://malicious.com/test_tenant_alpha'}
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD):
                result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'

    def test_custom_tenant_header_cannot_select_tenant(self):
        """Arbitrary X-Tenant-ID header cannot influence tenant resolution."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({})
        event['headers'] = {'X-Tenant-ID': 'test_tenant_alpha', 'X-Company-ID': 'test_tenant_alpha'}
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD):
                result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'


class TestNoPersistenceOnFailure:
    """Prove no request is written when tenant resolution fails."""

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('handlers.intake_handler.put_item', return_value=True)
    @patch('handlers.intake_handler.table')
    def test_no_persistence_when_domain_unknown(self, mock_table, mock_put, mock_rat):
        """No DynamoDB write when domain mapping fails."""
        from handlers.intake_handler import handler
        body = {
            'client_name': 'Test', 'client_email': 'test@x.com',
            'start_date': '2026-08-01', 'pet_names': 'Pet',
            'accepted_terms': True, 'accepted_privacy': True,
            'terms_version': '1.0', 'privacy_version': '1.0',
        }
        event = _public_intake_event(body, domain_name='unknown.example.com')
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP, 'TENANT_RESOLUTION_MODE': 'multi'}):
            resp = handler(event, None)
        assert resp['statusCode'] == 500
        mock_put.assert_not_called()

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('handlers.intake_handler.put_item', return_value=True)
    @patch('handlers.intake_handler.table')
    def test_no_persistence_when_mapping_empty(self, mock_table, mock_put, mock_rat):
        """No DynamoDB write when no domain map configured."""
        from handlers.intake_handler import handler
        body = {
            'client_name': 'Test', 'client_email': 'test@x.com',
            'start_date': '2026-08-01', 'pet_names': 'Pet',
            'accepted_terms': True, 'accepted_privacy': True,
            'terms_version': '1.0', 'privacy_version': '1.0',
        }
        event = _public_intake_event(body)
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': '', 'TENANT_RESOLUTION_MODE': 'multi'}):
            resp = handler(event, None)
        assert resp['statusCode'] == 500
        mock_put.assert_not_called()


class TestTransitionalGuardrail:
    """Document that the execute-api mapping is transitional and single-tenant."""

    def test_only_explicitly_mapped_domain_works(self):
        """A second execute-api domain would not resolve without explicit mapping."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({}, domain_name='b999zzz.execute-api.us-east-1.amazonaws.com')
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with pytest.raises(PermissionError, match="unrecognized"):
                resolve_public_intake_tenant(event)

    def test_mapping_is_tenant_specific_not_global(self):
        """The mapping resolves to a specific tenant, not a wildcard."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=ACTIVE_TENANT_RECORD):
                result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'
        assert result != 'test_tenant_alpha'


# ==============================================================================
# 4. Authoritative Tenant Validation Tests
# ==============================================================================

class TestTenantStatusValidation:
    """Prove that domain-mapped tenants must also be active in authoritative metadata."""

    def test_mapped_tenant_disabled_fails(self):
        """A domain-mapped tenant that is disabled in metadata is denied."""
        from common.auth import resolve_public_intake_tenant
        
        disabled_tenant = {'subscription_status': 'disabled', 'is_active': False}
        event = _public_intake_event({})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=disabled_tenant):
                with pytest.raises(PermissionError, match="not currently available"):
                    resolve_public_intake_tenant(event)

    def test_mapped_tenant_active_succeeds(self):
        """A domain-mapped tenant that is active in metadata succeeds."""
        from common.auth import resolve_public_intake_tenant
        
        active_tenant = {'subscription_status': 'active', 'is_active': True}
        event = _public_intake_event({})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=active_tenant):
                result = resolve_public_intake_tenant(event)
        assert result == 'tog_and_dogs'

    def test_active_mapping_cannot_override_inactive_tenant(self):
        """An active domain mapping does not bypass an inactive authoritative tenant."""
        from common.auth import resolve_public_intake_tenant
        
        suspended_tenant = {'subscription_status': 'suspended', 'is_active': False}
        event = _public_intake_event({})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=suspended_tenant):
                with pytest.raises(PermissionError, match="not currently available"):
                    resolve_public_intake_tenant(event)

    def test_missing_tenant_record_fails_closed(self):
        """A domain-mapped tenant with no DynamoDB record fails closed."""
        from common.auth import resolve_public_intake_tenant
        
        event = _public_intake_event({})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value=None):
                with pytest.raises(PermissionError, match="not currently available"):
                    resolve_public_intake_tenant(event)

    def test_tenant_lookup_exception_fails_closed(self):
        """A DynamoDB lookup failure fails closed."""
        from common.auth import resolve_public_intake_tenant
        
        event = _public_intake_event({})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', side_effect=Exception("DynamoDB error")):
                with pytest.raises(PermissionError, match="not currently available"):
                    resolve_public_intake_tenant(event)

    def test_malformed_tenant_record_fails_closed(self):
        """A non-dict tenant record fails closed."""
        from common.auth import resolve_public_intake_tenant
        
        event = _public_intake_event({})
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with patch('common.db.get_item', return_value="not a dict"):
                with pytest.raises(PermissionError, match="not currently available"):
                    resolve_public_intake_tenant(event)


class TestAuthenticatedCannotBypassDomainMapping:
    """Prove that authenticated claims cannot bypass a missing or invalid domain mapping."""

    def test_authenticated_claim_with_unmapped_domain_fails(self):
        """Authenticated user on an unmapped domain fails closed."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({}, claims={
            'custom:company_id': 'tog_and_dogs',
            'email': 'user@example.com',
            'sub': 'sub-1',
        }, domain_name='unknown.example.com')
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with pytest.raises(PermissionError):
                resolve_public_intake_tenant(event)

    def test_authenticated_claim_with_no_domain_map_fails(self):
        """Authenticated user with no domain map configured fails closed."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({}, claims={
            'custom:company_id': 'tog_and_dogs',
            'email': 'user@example.com',
            'sub': 'sub-2',
        })
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': ''}):
            with pytest.raises(PermissionError, match="no trusted tenant mapping"):
                resolve_public_intake_tenant(event)

    def test_authenticated_claim_with_empty_domain_fails(self):
        """Authenticated user with empty requestContext.domainName fails closed."""
        from common.auth import resolve_public_intake_tenant
        event = _public_intake_event({}, claims={
            'custom:company_id': 'tog_and_dogs',
            'email': 'user@example.com',
            'sub': 'sub-3',
        }, domain_name='')
        with patch.dict(os.environ, {'PUBLIC_INTAKE_DOMAIN_MAP': TOGS_DOMAIN_MAP}):
            with pytest.raises(PermissionError, match="no trusted tenant mapping"):
                resolve_public_intake_tenant(event)
