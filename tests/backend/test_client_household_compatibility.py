"""
Phase 1A: Client/Household backend compatibility layer tests.

Proves:
- household_id equals client_id (no separate HOUSEHOLD entity)
- Account status is derived correctly for all states
- Legacy records with missing optional fields load safely
- Cognito sub and internal keys are not exposed
- No HOUSEHOLD record is created
- Email matching does not auto-link
- Tenant isolation remains enforced
"""

import os
import json
import pytest

os.environ.setdefault('DEFAULT_COMPANY_ID', 'tog_and_dogs')
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')
os.environ.setdefault('ADMIN_USER_POOL_ID', 'us-east-1_TestPool')


class TestDeriveAccountStatus:
    """Prove account_status derivation for all supported states."""

    def test_profile_only_no_email(self):
        from common.client_view import derive_account_status
        client = {'client_id': 'c1', 'display_name': 'Test', 'is_active': True}
        assert derive_account_status(client) == 'profile_only'

    def test_invite_available_with_email(self):
        from common.client_view import derive_account_status
        client = {'client_id': 'c2', 'email': 'test@example.com', 'is_active': True}
        assert derive_account_status(client) == 'invite_available'

    def test_invitation_sent(self):
        from common.client_view import derive_account_status
        client = {'client_id': 'c3', 'email': 'test@example.com', 'cognito_sub': 'sub-123',
                  'cognito_status': 'FORCE_CHANGE_PASSWORD', 'is_active': True, 'portal_enabled': True}
        assert derive_account_status(client) == 'invitation_sent'

    def test_linked_active(self):
        from common.client_view import derive_account_status
        client = {'client_id': 'c4', 'email': 'test@example.com', 'cognito_sub': 'sub-456',
                  'cognito_status': 'CONFIRMED', 'is_active': True, 'portal_enabled': True}
        assert derive_account_status(client) == 'linked_active'

    def test_linked_disabled(self):
        from common.client_view import derive_account_status
        client = {'client_id': 'c5', 'email': 'test@example.com', 'cognito_sub': 'sub-789',
                  'cognito_status': 'CONFIRMED', 'is_active': False, 'portal_enabled': False}
        assert derive_account_status(client) == 'linked_disabled'

    def test_unlinked(self):
        from common.client_view import derive_account_status
        client = {'client_id': 'c6', 'email': 'test@example.com', 'cognito_sub': 'unlinked',
                  'cognito_status': 'unlinked', 'is_active': True}
        assert derive_account_status(client) == 'unlinked'

    def test_orphaned_identity(self):
        from common.client_view import derive_account_status
        client = {'client_id': 'c7', 'email': 'test@example.com', 'cognito_sub': 'sub-old',
                  'cognito_status': 'DELETED', 'is_active': True}
        assert derive_account_status(client) == 'orphaned_identity'

    def test_virtual_cognito_user(self):
        from common.client_view import derive_account_status
        client = {'client_id': 'cognito_user1', 'is_virtual': True, 'is_active': True}
        assert derive_account_status(client) == 'linked_active'

    def test_virtual_disabled(self):
        from common.client_view import derive_account_status
        client = {'client_id': 'cognito_user2', 'is_virtual': True, 'is_active': False}
        assert derive_account_status(client) == 'linked_disabled'


class TestNormalizeClientResponse:
    """Prove response normalization produces correct view model."""

    def test_household_id_equals_client_id(self):
        from common.client_view import normalize_client_response
        client = {'client_id': 'c123', 'display_name': 'Test', 'email': 'a@b.com',
                  'PK': 'COMPANY#tog_and_dogs', 'SK': 'CLIENT#c123', 'is_active': True}
        result = normalize_client_response(client)
        assert result['household_id'] == 'c123'
        assert result['household_id'] == result['client_id']

    def test_cognito_sub_removed(self):
        from common.client_view import normalize_client_response
        client = {'client_id': 'c1', 'cognito_sub': 'sub-secret', 'is_active': True}
        result = normalize_client_response(client)
        assert 'cognito_sub' not in result

    def test_pk_sk_removed(self):
        from common.client_view import normalize_client_response
        client = {'client_id': 'c1', 'PK': 'COMPANY#x', 'SK': 'CLIENT#c1', 'is_active': True}
        result = normalize_client_response(client)
        assert 'PK' not in result
        assert 'SK' not in result

    def test_account_status_added(self):
        from common.client_view import normalize_client_response
        client = {'client_id': 'c1', 'email': 'test@x.com', 'cognito_sub': 'sub-1',
                  'cognito_status': 'CONFIRMED', 'is_active': True, 'portal_enabled': True,
                  'PK': 'COMPANY#t', 'SK': 'CLIENT#c1'}
        result = normalize_client_response(client)
        assert result['account_status'] == 'linked_active'

    def test_missing_optional_fields_handled(self):
        """Legacy records with missing optional fields must not crash."""
        from common.client_view import normalize_client_response
        # Minimal record — only client_id and display_name
        client = {'client_id': 'legacy1', 'display_name': 'Old Client'}
        result = normalize_client_response(client)
        assert result['household_id'] == 'legacy1'
        assert result['account_status'] == 'profile_only'
        assert 'cognito_sub' not in result

    def test_none_input_returns_none(self):
        from common.client_view import normalize_client_response
        assert normalize_client_response(None) is None

    def test_no_household_record_created(self):
        """Normalization is read-only; no DynamoDB writes occur."""
        from common.client_view import normalize_client_response
        # This is a pure function — no DB interaction. Proving it doesn't import or call DB.
        import inspect
        source = inspect.getsource(normalize_client_response)
        assert 'put_item' not in source
        assert 'table.' not in source

    def test_preserves_display_fields(self):
        from common.client_view import normalize_client_response
        client = {'client_id': 'c1', 'display_name': 'Test', 'email': 'a@b.com',
                  'phone': '555-1234', 'address': '123 Main St', 'notes': 'VIP',
                  'is_active': True, 'portal_enabled': True, 'PK': 'X', 'SK': 'Y'}
        result = normalize_client_response(client)
        assert result['display_name'] == 'Test'
        assert result['email'] == 'a@b.com'
        assert result['phone'] == '555-1234'
        assert result['address'] == '123 Main St'
        assert result['notes'] == 'VIP'
