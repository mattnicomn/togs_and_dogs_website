"""
tests/backend/test_r17w_company_id_resolution.py
Release 17W: Company ID Resolution Verification Tests

Tests for common/auth.py covering:
  - get_current_company_id: custom:company_id claim takes precedence
  - get_current_company_id: DEFAULT_COMPANY_ID fallback behavior
  - Fallback safety: missing custom:company_id routes to DEFAULT_COMPANY_ID only
  - Cross-tenant isolation: validate_tenant_ownership rejects mismatched company_id
  - platform_admin users are separate from tenant company_id resolution
  - Resolution for a second (placeholder) tenant ID is independent of tog_and_dogs
  - Explicit test that a missing claim does NOT silently route into another tenant

FINDINGS FROM RELEASE 17W AUDIT:
  common/auth.py line 215:
    DEFAULT_COMPANY_ID = os.environ.get("DEFAULT_COMPANY_ID", "tog_and_dogs")

  This is intentional for the current single-tenant deployment, but creates a
  risk for multi-tenant: if a second-tenant Cognito user does NOT have
  custom:company_id set in their JWT, they would silently fall through to
  the DEFAULT_COMPANY_ID ("tog_and_dogs") and gain access to the wrong tenant's data.

  REMEDIATION REQUIREMENT (future gate):
    Before any second-tenant user is created in Cognito, ensure:
    1. custom:company_id is set on the Cognito user attribute (admin-create-user step).
    2. The Lambda authorizer (or post-auth trigger) validates custom:company_id is present.
    3. Do NOT rely on DEFAULT_COMPANY_ID to correctly route multi-tenant users.

  These tests document the current behavior explicitly to make the risk visible.
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock

# The auth module uses os.environ for DEFAULT_COMPANY_ID — patch before import
os.environ.setdefault('DEFAULT_COMPANY_ID', 'tog_and_dogs')
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')

from common.auth import (
    get_current_company_id,
    get_claims,
    validate_tenant_ownership,
    is_platform_admin,
    get_effective_role,
    get_groups,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_event(groups=None, custom_company_id=None, email='user@example.com', sub='test-sub-123'):
    """Build a minimal API Gateway event with Cognito JWT claims."""
    claims = {
        'email': email,
        'sub': sub,
        'email_verified': 'true',
    }
    if groups:
        claims['cognito:groups'] = ','.join(groups) if isinstance(groups, list) else groups
    if custom_company_id is not None:
        claims['custom:company_id'] = custom_company_id

    return {
        'requestContext': {
            'authorizer': {
                'claims': claims
            }
        },
        'httpMethod': 'GET',
        'path': '/admin/requests',
    }


# ---------------------------------------------------------------------------
# 1. get_current_company_id — Custom Claim Resolution
# ---------------------------------------------------------------------------

class TestGetCurrentCompanyIdCustomClaim:

    def test_custom_company_id_takes_precedence(self):
        """A user with custom:company_id set should resolve to that tenant."""
        event = make_event(groups=['owner'], custom_company_id='tog_and_dogs')
        result = get_current_company_id(event)
        assert result == 'tog_and_dogs'

    def test_second_tenant_custom_claim_resolves_independently(self):
        """A user with custom:company_id=<second_tenant> resolves to that tenant, not tog_and_dogs."""
        event = make_event(groups=['owner'], custom_company_id='acme_pets')
        result = get_current_company_id(event)
        assert result == 'acme_pets'
        assert result != 'tog_and_dogs', (
            "Second-tenant user must NOT resolve to tog_and_dogs when custom:company_id is set"
        )

    def test_custom_company_id_overrides_default(self):
        """Even if DEFAULT_COMPANY_ID is tog_and_dogs, a different custom claim wins."""
        with patch.dict(os.environ, {'DEFAULT_COMPANY_ID': 'tog_and_dogs'}):
            event = make_event(groups=['staff'], custom_company_id='other_company')
            result = get_current_company_id(event)
            assert result == 'other_company'

    def test_empty_custom_company_id_falls_through_to_default(self):
        """An empty string custom:company_id is falsy and should fall through to default."""
        event = make_event(groups=['owner'], custom_company_id='')
        result = get_current_company_id(event)
        # Empty string is falsy, so should fall to DEFAULT_COMPANY_ID
        assert result == os.environ.get('DEFAULT_COMPANY_ID', 'tog_and_dogs')


# ---------------------------------------------------------------------------
# 2. get_current_company_id — DEFAULT_COMPANY_ID Fallback Behavior
# ---------------------------------------------------------------------------

class TestGetCurrentCompanyIdDefaultFallback:

    def test_missing_custom_claim_falls_to_default(self):
        """
        KNOWN RISK: A user without custom:company_id set falls to DEFAULT_COMPANY_ID.

        This is safe for the current single-tenant deployment (tog_and_dogs).
        For multi-tenant: all second-tenant Cognito users MUST have custom:company_id set.
        """
        event = make_event(groups=['owner'])  # No custom_company_id
        result = get_current_company_id(event)
        # Must fall back to DEFAULT_COMPANY_ID, not None or anything else
        expected_default = os.environ.get('DEFAULT_COMPANY_ID', 'tog_and_dogs')
        assert result == expected_default

    def test_default_company_id_is_tog_and_dogs_in_production_config(self):
        """Verify the hardcoded fallback default matches the production tenant."""
        with patch.dict(os.environ, {}, clear=False):
            # Without DEFAULT_COMPANY_ID env var set, hardcoded default is 'tog_and_dogs'
            env_without_default = {k: v for k, v in os.environ.items() if k != 'DEFAULT_COMPANY_ID'}
            with patch.dict(os.environ, env_without_default, clear=True):
                # Re-import to pick up cleared env, or test module-level behavior
                import importlib
                import common.auth as auth_module
                importlib.reload(auth_module)
                default = auth_module.DEFAULT_COMPANY_ID
                assert default == 'tog_and_dogs', (
                    "Default fallback must be 'tog_and_dogs' when DEFAULT_COMPANY_ID env var is absent"
                )
                # Restore
                importlib.reload(auth_module)

    def test_no_claims_falls_to_default(self):
        """Event with no claims at all falls through to DEFAULT_COMPANY_ID safely."""
        event = {'requestContext': {}, 'httpMethod': 'GET', 'path': '/admin/requests'}
        result = get_current_company_id(event)
        expected = os.environ.get('DEFAULT_COMPANY_ID', 'tog_and_dogs')
        assert result == expected

    def test_claims_dict_passed_directly(self):
        """get_current_company_id accepts a pre-extracted claims dict."""
        claims = {'custom:company_id': 'direct_company'}
        result = get_current_company_id(event={}, claims=claims)
        assert result == 'direct_company'

    def test_claims_without_custom_company_id_uses_default(self):
        claims = {'email': 'user@example.com', 'sub': 'abc-123'}
        result = get_current_company_id(event={}, claims=claims)
        expected = os.environ.get('DEFAULT_COMPANY_ID', 'tog_and_dogs')
        assert result == expected


# ---------------------------------------------------------------------------
# 3. Cross-Tenant Isolation: validate_tenant_ownership
# ---------------------------------------------------------------------------

class TestValidateTenantOwnership:

    def test_same_company_id_passes(self):
        """User from tog_and_dogs can access tog_and_dogs items without error."""
        item = {'company_id': 'tog_and_dogs', 'request_id': 'req_1'}
        event = make_event(groups=['owner'], custom_company_id='tog_and_dogs')
        # Should not raise
        validate_tenant_ownership(item, event)

    def test_cross_tenant_access_raises_permission_error(self):
        """A user from acme_pets must NOT access tog_and_dogs data."""
        item = {'company_id': 'tog_and_dogs', 'request_id': 'req_1'}
        event = make_event(groups=['owner'], custom_company_id='acme_pets')
        with pytest.raises(PermissionError, match="Cross-tenant"):
            validate_tenant_ownership(item, event)

    def test_second_tenant_user_cannot_access_first_tenant_data(self):
        """Second tenant user with correct custom:company_id cannot see first tenant data."""
        item = {'company_id': 'tog_and_dogs'}
        event = make_event(groups=['staff'], custom_company_id='acme_pets')
        with pytest.raises(PermissionError):
            validate_tenant_ownership(item, event)

    def test_second_tenant_user_can_access_own_data(self):
        """Second tenant user can access their own company_id data."""
        item = {'company_id': 'acme_pets'}
        event = make_event(groups=['owner'], custom_company_id='acme_pets')
        # Should not raise
        validate_tenant_ownership(item, event)

    def test_item_without_company_id_assumes_default(self):
        """
        Items without a company_id field are assumed to belong to DEFAULT_COMPANY_ID.
        This is legacy behavior (pre-multi-tenant items).
        A tog_and_dogs user can access them; a second-tenant user cannot.
        """
        item = {}  # No company_id — treated as DEFAULT_COMPANY_ID (tog_and_dogs)
        event_default = make_event(groups=['owner'])  # Falls back to tog_and_dogs
        validate_tenant_ownership(item, event_default)  # Should pass

        event_other = make_event(groups=['owner'], custom_company_id='acme_pets')
        with pytest.raises(PermissionError):
            validate_tenant_ownership(item, event_other)  # Should fail (cross-tenant)

    def test_non_dict_item_does_not_raise(self):
        """Non-dict items (None, string) are treated as no-ops."""
        event = make_event(groups=['owner'])
        validate_tenant_ownership(None, event)   # Should not raise
        validate_tenant_ownership("string", event)  # Should not raise


# ---------------------------------------------------------------------------
# 4. platform_admin Separation from Tenant Resolution
# ---------------------------------------------------------------------------

class TestPlatformAdminSeparation:

    def test_platform_admin_resolves_company_id_from_claim(self):
        """
        platform_admin users may have their own custom:company_id if needed,
        but primarily interact via platform_handler (not tenant-bound handlers).
        They should resolve company_id normally if custom:company_id is present.
        """
        event = make_event(groups=['platform_admin'], custom_company_id='acme_pets')
        result = get_current_company_id(event)
        assert result == 'acme_pets'

    def test_platform_admin_without_custom_claim_gets_default(self):
        """
        platform_admin without custom:company_id resolves to DEFAULT_COMPANY_ID.
        This is acceptable since platform_admin bypasses tenant enforcement in platform_handler.
        """
        event = make_event(groups=['platform_admin'])
        result = get_current_company_id(event)
        expected = os.environ.get('DEFAULT_COMPANY_ID', 'tog_and_dogs')
        assert result == expected

    def test_platform_admin_is_detected_correctly(self):
        event = make_event(groups=['platform_admin'])
        assert is_platform_admin(event) is True

    def test_owner_is_not_platform_admin(self):
        event = make_event(groups=['owner'], custom_company_id='tog_and_dogs')
        assert is_platform_admin(event) is False

    def test_staff_is_not_platform_admin(self):
        event = make_event(groups=['staff'], custom_company_id='tog_and_dogs')
        assert is_platform_admin(event) is False

    def test_second_tenant_owner_must_not_be_platform_admin(self):
        """A second-tenant owner should have 'owner' group only, not platform_admin."""
        event = make_event(groups=['owner'], custom_company_id='acme_pets')
        assert is_platform_admin(event) is False
        assert get_effective_role(event) == 'owner'

    def test_platform_admin_effective_role(self):
        """platform_admin is detected as a distinct role."""
        event = make_event(groups=['platform_admin'])
        role = get_effective_role(event)
        assert role == 'platform_admin'


# ---------------------------------------------------------------------------
# 5. Explicit Missing company_id Safety Documentation
# ---------------------------------------------------------------------------

class TestMissingCompanyIdSafetyDocumentation:

    def test_missing_claim_does_not_resolve_to_none(self):
        """
        get_current_company_id must NEVER return None.
        It must always return a string (the default if nothing else).
        A None company_id would break all DynamoDB key construction.
        """
        event = make_event(groups=['owner'])  # No custom:company_id
        result = get_current_company_id(event)
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 0

    def test_completely_empty_event_does_not_return_none(self):
        """Even with a completely empty event, a string company_id is returned."""
        result = get_current_company_id({})
        assert result is not None
        assert isinstance(result, str)

    def test_known_risk_missing_claim_routes_to_tog_and_dogs(self):
        """
        KNOWN RISK DOCUMENTATION TEST:
        A new Cognito user created WITHOUT custom:company_id will silently resolve
        to 'tog_and_dogs' via the DEFAULT_COMPANY_ID fallback.

        This is safe today (single-tenant) but DANGEROUS for multi-tenant.
        REMEDIATION: Ensure all second-tenant Cognito users have custom:company_id set.
        This test explicitly documents this behavior so the risk is visible.
        """
        event = make_event(groups=['owner'])  # Simulates a user WITHOUT custom:company_id
        result = get_current_company_id(event)

        # The fallback is tog_and_dogs — this is the known risk
        assert result == 'tog_and_dogs', (
            "KNOWN RISK: A user without custom:company_id silently routes to 'tog_and_dogs'. "
            "All second-tenant Cognito users must have custom:company_id set before first login."
        )

    def test_second_tenant_user_with_correct_claim_does_not_route_to_tog_and_dogs(self):
        """
        Positive case: with correct custom:company_id, second-tenant users
        are correctly isolated from tog_and_dogs.
        """
        event = make_event(groups=['owner'], custom_company_id='acme_pets')
        result = get_current_company_id(event)
        assert result == 'acme_pets'
        assert result != 'tog_and_dogs'


# ---------------------------------------------------------------------------
# 6. Tenant Resolution Mode: single | multi (Release 17Y)
# ---------------------------------------------------------------------------

class TestTenantResolutionMode:

    @pytest.fixture(autouse=True)
    def set_up_logging(self, caplog):
        caplog.set_level("INFO")

    def test_default_mode_is_single(self):
        """By default, when env var is unset, it behaves as single mode."""
        with patch.dict(os.environ, {}):
            if 'TENANT_RESOLUTION_MODE' in os.environ:
                del os.environ['TENANT_RESOLUTION_MODE']
            event = make_event(groups=['owner'])  # Missing company_id
            result = get_current_company_id(event)
            assert result == 'tog_and_dogs'

    def test_single_mode_missing_company_id_fallback(self, caplog):
        """In single mode, missing company_id falls back to default and logs fallback."""
        with patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'single'}):
            event = make_event(groups=['owner'])
            result = get_current_company_id(event)
            assert result == 'tog_and_dogs'
            
            # Check log
            assert len(caplog.records) == 1
            log_data = json.loads(caplog.records[0].message)
            assert log_data['event'] == 'TENANT_RESOLUTION_FALLBACK'
            assert log_data['mode'] == 'single'
            assert log_data['is_empty_company_id'] is True
            assert log_data['has_claims'] is True
            assert log_data['default_company_id'] == 'tog_and_dogs'
            # Verify no sensitive claims are present
            for key in ['email', 'sub', 'username', 'cognito:groups', 'claims']:
                assert key not in log_data

    def test_single_mode_empty_company_id_fallback(self, caplog):
        """In single mode, empty/whitespace company_id falls back to default."""
        with patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'single'}):
            event = make_event(groups=['owner'], custom_company_id='   ')
            result = get_current_company_id(event)
            assert result == 'tog_and_dogs'
            
            assert len(caplog.records) == 1
            log_data = json.loads(caplog.records[0].message)
            assert log_data['event'] == 'TENANT_RESOLUTION_FALLBACK'
            assert log_data['is_empty_company_id'] is True

    def test_single_mode_with_valid_company_id_does_not_log_fallback(self, caplog):
        """In single mode, a valid company_id resolves and does not log anything."""
        with patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'single'}):
            event = make_event(groups=['owner'], custom_company_id='my_company')
            result = get_current_company_id(event)
            assert result == 'my_company'
            assert len(caplog.records) == 0

    def test_multi_mode_missing_company_id_raises_and_logs(self, caplog):
        """In multi mode, missing company_id raises PermissionError and logs failure."""
        with patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'}):
            event = make_event(groups=['owner'])
            with pytest.raises(PermissionError, match="TENANT_RESOLUTION_FAILED"):
                get_current_company_id(event)
                
            assert len(caplog.records) == 1
            log_data = json.loads(caplog.records[0].message)
            assert log_data['event'] == 'TENANT_RESOLUTION_FAILED'
            assert log_data['mode'] == 'multi'
            assert log_data['is_empty_company_id'] is True
            assert log_data['has_claims'] is True
            assert 'default_company_id' not in log_data
            # Verify no sensitive claims are present
            for key in ['email', 'sub', 'username', 'cognito:groups', 'claims']:
                assert key not in log_data

    def test_multi_mode_empty_company_id_raises_and_logs(self, caplog):
        """In multi mode, empty/whitespace company_id raises PermissionError and logs."""
        with patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'}):
            event = make_event(groups=['owner'], custom_company_id='')
            with pytest.raises(PermissionError, match="TENANT_RESOLUTION_FAILED"):
                get_current_company_id(event)
                
            assert len(caplog.records) == 1
            log_data = json.loads(caplog.records[0].message)
            assert log_data['event'] == 'TENANT_RESOLUTION_FAILED'
            assert log_data['is_empty_company_id'] is True

    def test_multi_mode_with_valid_company_id_passes(self, caplog):
        """In multi mode, a valid company_id resolves and does not raise or log."""
        with patch.dict(os.environ, {'TENANT_RESOLUTION_MODE': 'multi'}):
            event = make_event(groups=['owner'], custom_company_id='other_tenant')
            result = get_current_company_id(event)
            assert result == 'other_tenant'
            assert len(caplog.records) == 0
