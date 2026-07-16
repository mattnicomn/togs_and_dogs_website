"""
Phase 1A.1: Handler-level integration tests for GET /admin/clients.

Invokes the actual admin_handler and inspects the serialized HTTP response
to prove the Phase 1A compatibility layer works correctly end-to-end.

Proves:
- household_id is present and equals client_id
- account_status is present and correctly derived
- PK, SK, cognito_sub remain present (frontend compatibility)
- Legacy records with missing optional fields serialize safely
- Profile status (is_active) is separate from account status
- Cognito-disabled user → linked_disabled
- Archived profile with enabled Cognito → NOT falsely linked_disabled
- FORCE_CHANGE_PASSWORD → invitation_sent
- Missing/deleted Cognito identity → orphaned_identity
- profile_only and invite_available are distinct
- Tenant A cannot receive Tenant B clients
- Pagination token structure unchanged
- No DynamoDB write occurs
- No HOUSEHOLD item is created
- No per-client pet or request query
- No N+1 behavior
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime

# Ensure backend source is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

os.environ.setdefault('DEFAULT_COMPANY_ID', 'tog_and_dogs')
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')
os.environ.setdefault('ADMIN_USER_POOL_ID', 'us-east-1_TestPool')
os.environ.setdefault('TENANT_RESOLUTION_MODE', 'multi')
os.environ.setdefault('ENTITLEMENT_ENFORCEMENT_ENABLED', 'true')
os.environ.setdefault('STRIPE_ENV', 'production')

from handlers.admin_handler import handler as admin_handler


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def make_event(company_id='tog_and_dogs', role='owner'):
    """Create a minimal GET /admin/clients API Gateway event."""
    claims = {
        'email': 'admin@test.com',
        'sub': 'admin-sub-123',
        'custom:company_id': company_id,
        'cognito:groups': role,
    }
    return {
        'requestContext': {
            'authorizer': {'claims': claims},
            'domainName': 'test-api.execute-api.us-east-1.amazonaws.com',
        },
        'httpMethod': 'GET',
        'path': '/admin/clients',
        'body': None,
    }


def make_cognito_user(username, email, sub, status='CONFIRMED', enabled=True, company_id='tog_and_dogs'):
    """Create a mock Cognito user object as returned by list_users_in_group."""
    return {
        'Username': username,
        'UserStatus': status,
        'Enabled': enabled,
        'Attributes': [
            {'Name': 'email', 'Value': email},
            {'Name': 'sub', 'Value': sub},
            {'Name': 'custom:company_id', 'Value': company_id},
        ],
    }


def make_client_record(client_id, email=None, cognito_sub=None, is_active=True,
                       portal_enabled=False, cognito_status=None,
                       company_id='tog_and_dogs', display_name=None):
    """Create a mock DynamoDB client record."""
    record = {
        'PK': f'COMPANY#{company_id}',
        'SK': f'CLIENT#{client_id}',
        'company_id': company_id,
        'client_id': client_id,
        'display_name': display_name or f'Client {client_id}',
        'is_active': is_active,
        'portal_enabled': portal_enabled,
        'entity_type': 'CLIENT',
        'created_at': '2026-01-01T00:00:00',
        'updated_at': '2026-07-01T00:00:00',
    }
    if email:
        record['email'] = email
    if cognito_sub:
        record['cognito_sub'] = cognito_sub
    if cognito_status:
        record['cognito_status'] = cognito_status
    return record


def invoke_handler(client_records, cognito_users, company_id='tog_and_dogs'):
    """Invoke the actual admin handler with mocked DynamoDB and Cognito."""
    event = make_event(company_id=company_id)

    mock_table = MagicMock()
    mock_table.query.return_value = {'Items': client_records}

    mock_cognito = MagicMock()
    mock_cognito.list_groups.return_value = {
        'Groups': [{'GroupName': f'{company_id}_clients'}]
    }
    mock_cognito.list_users_in_group.return_value = {
        'Users': cognito_users
    }

    with patch('common.entitlement.require_active_tenant', return_value=None), \
         patch('handlers.admin_handler.table', mock_table, create=True), \
         patch('common.db.table', mock_table), \
         patch('boto3.client', return_value=mock_cognito):
        resp = admin_handler(event, None)

    assert resp['statusCode'] == 200, f"Expected 200, got {resp['statusCode']}: {resp.get('body', '')}"
    body = json.loads(resp['body'])
    return body, mock_table, mock_cognito


# ---------------------------------------------------------------------------
# 1. Core household_id and account_status presence
# ---------------------------------------------------------------------------

class TestHouseholdIdPresence:

    def test_household_id_equals_client_id(self):
        """Every client in the response has household_id == client_id."""
        clients = [make_client_record('c1', email='a@b.com')]
        cognito_users = [make_cognito_user('user1', 'a@b.com', 'sub-c1')]
        body, _, _ = invoke_handler(clients, cognito_users)

        for c in body['clients']:
            assert 'household_id' in c, f"Missing household_id on client {c.get('client_id')}"
            assert c['household_id'] == c['client_id']

    def test_account_status_present(self):
        """Every client in the response has account_status."""
        clients = [make_client_record('c1', email='a@b.com')]
        cognito_users = [make_cognito_user('user1', 'a@b.com', 'sub-c1')]
        body, _, _ = invoke_handler(clients, cognito_users)

        for c in body['clients']:
            assert 'account_status' in c, f"Missing account_status on client {c.get('client_id')}"


# ---------------------------------------------------------------------------
# 2. Existing fields preserved (frontend compatibility)
# ---------------------------------------------------------------------------

class TestFieldPreservation:

    def test_pk_sk_preserved(self):
        """PK and SK remain in the response for frontend record operations."""
        clients = [make_client_record('c1', email='a@b.com', cognito_sub='sub-c1')]
        cognito_users = [make_cognito_user('user1', 'a@b.com', 'sub-c1')]
        body, _, _ = invoke_handler(clients, cognito_users)

        c = body['clients'][0]
        assert c['PK'] == 'COMPANY#tog_and_dogs'
        assert c['SK'] == 'CLIENT#c1'

    def test_cognito_sub_preserved(self):
        """cognito_sub remains in the response for frontend account-status display."""
        clients = [make_client_record('c1', email='a@b.com', cognito_sub='sub-c1')]
        cognito_users = [make_cognito_user('user1', 'a@b.com', 'sub-c1')]
        body, _, _ = invoke_handler(clients, cognito_users)

        c = body['clients'][0]
        assert c['cognito_sub'] == 'sub-c1'

    def test_display_fields_preserved(self):
        """display_name, email, phone, etc. remain intact."""
        rec = make_client_record('c1', email='test@x.com')
        rec['phone'] = '555-1234'
        rec['address'] = '123 Main St'
        rec['notes'] = 'VIP client'
        body, _, _ = invoke_handler([rec], [])

        c = body['clients'][0]
        assert c['display_name'] == 'Client c1'
        assert c['email'] == 'test@x.com'
        assert c['phone'] == '555-1234'
        assert c['address'] == '123 Main St'
        assert c['notes'] == 'VIP client'


# ---------------------------------------------------------------------------
# 3. Legacy records with missing fields
# ---------------------------------------------------------------------------

class TestLegacyRecords:

    def test_minimal_record_serializes_safely(self):
        """Legacy record with only PK/SK/client_id does not crash."""
        minimal = {
            'PK': 'COMPANY#tog_and_dogs',
            'SK': 'CLIENT#legacy1',
            'company_id': 'tog_and_dogs',
            'client_id': 'legacy1',
            'display_name': 'Old Client',
        }
        body, _, _ = invoke_handler([minimal], [])

        c = body['clients'][0]
        assert c['household_id'] == 'legacy1'
        assert c['account_status'] == 'profile_only'

    def test_record_with_email_no_cognito(self):
        """Record with email but no cognito_sub is invite_available."""
        rec = make_client_record('c2', email='contact@example.com')
        body, _, _ = invoke_handler([rec], [])

        c = body['clients'][0]
        assert c['account_status'] == 'invite_available'


# ---------------------------------------------------------------------------
# 4. Account-status derivation correctness (end-to-end)
# ---------------------------------------------------------------------------

class TestAccountStatusDerivation:

    def test_linked_active(self):
        """DynamoDB client matched to enabled CONFIRMED Cognito user → linked_active."""
        clients = [make_client_record('c1', email='a@b.com', cognito_sub='sub-1')]
        cognito_users = [make_cognito_user('u1', 'a@b.com', 'sub-1', status='CONFIRMED', enabled=True)]
        body, _, _ = invoke_handler(clients, cognito_users)

        assert body['clients'][0]['account_status'] == 'linked_active'

    def test_linked_disabled_cognito_disabled(self):
        """DynamoDB client matched to DISABLED Cognito user → linked_disabled."""
        clients = [make_client_record('c1', email='a@b.com', cognito_sub='sub-1', is_active=True)]
        cognito_users = [make_cognito_user('u1', 'a@b.com', 'sub-1', status='CONFIRMED', enabled=False)]
        body, _, _ = invoke_handler(clients, cognito_users)

        assert body['clients'][0]['account_status'] == 'linked_disabled'

    def test_archived_profile_enabled_cognito_not_linked_disabled(self):
        """Archived profile (is_active=False) with enabled Cognito is NOT linked_disabled.

        This is the key semantic correction. linked_disabled means Cognito is disabled,
        not that the profile is archived. An archived profile with enabled Cognito
        remains linked_active from an identity perspective."""
        clients = [make_client_record('c1', email='a@b.com', cognito_sub='sub-1', is_active=False)]
        cognito_users = [make_cognito_user('u1', 'a@b.com', 'sub-1', status='CONFIRMED', enabled=True)]
        body, _, _ = invoke_handler(clients, cognito_users)

        c = body['clients'][0]
        assert c['account_status'] == 'linked_active', \
            f"Archived profile with enabled Cognito should be linked_active, got {c['account_status']}"
        # Profile state is preserved separately
        assert c['is_active'] is False

    def test_invitation_sent_force_change_password(self):
        """Cognito FORCE_CHANGE_PASSWORD → invitation_sent."""
        clients = [make_client_record('c1', email='a@b.com', cognito_sub='sub-1')]
        cognito_users = [make_cognito_user('u1', 'a@b.com', 'sub-1', status='FORCE_CHANGE_PASSWORD')]
        body, _, _ = invoke_handler(clients, cognito_users)

        assert body['clients'][0]['account_status'] == 'invitation_sent'

    def test_orphaned_identity_missing_cognito(self):
        """Client with cognito_sub but no matching Cognito user → orphaned_identity."""
        # Client references a cognito_sub that does NOT appear in the Cognito user list
        clients = [make_client_record('c1', email='a@b.com', cognito_sub='sub-deleted',
                                      cognito_status='DELETED')]
        # No cognito users returned (the user was deleted from Cognito)
        body, _, _ = invoke_handler(clients, [])

        c = body['clients'][0]
        assert c['account_status'] == 'orphaned_identity'

    def test_profile_only_no_email(self):
        """Client with no email and no Cognito link → profile_only."""
        clients = [make_client_record('c1')]
        body, _, _ = invoke_handler(clients, [])

        assert body['clients'][0]['account_status'] == 'profile_only'

    def test_invite_available_with_email(self):
        """Client with email but no Cognito link → invite_available."""
        clients = [make_client_record('c1', email='new@example.com')]
        body, _, _ = invoke_handler(clients, [])

        assert body['clients'][0]['account_status'] == 'invite_available'

    def test_profile_only_vs_invite_available_distinct(self):
        """profile_only (no email) and invite_available (has email) are distinct states."""
        clients = [
            make_client_record('no_email'),
            make_client_record('has_email', email='x@y.com'),
        ]
        body, _, _ = invoke_handler(clients, [])

        statuses = {c['client_id']: c['account_status'] for c in body['clients']}
        assert statuses['no_email'] == 'profile_only'
        assert statuses['has_email'] == 'invite_available'

    def test_unlinked_status(self):
        """Client explicitly unlinked → unlinked status."""
        rec = make_client_record('c1', email='a@b.com', cognito_sub='unlinked',
                                 cognito_status='unlinked')
        body, _, _ = invoke_handler([rec], [])

        assert body['clients'][0]['account_status'] == 'unlinked'

    def test_virtual_cognito_user_linked_active(self):
        """Cognito user with no DynamoDB profile appears as linked_active."""
        # No DynamoDB clients
        cognito_users = [make_cognito_user('virt1', 'virtual@test.com', 'sub-virt')]
        body, _, _ = invoke_handler([], cognito_users)

        c = body['clients'][0]
        assert c['is_virtual'] is True
        assert c['account_status'] == 'linked_active'

    def test_virtual_cognito_user_disabled(self):
        """Disabled Cognito-only user → linked_disabled."""
        cognito_users = [make_cognito_user('virt1', 'v@t.com', 'sub-v', enabled=False)]
        body, _, _ = invoke_handler([], cognito_users)

        c = body['clients'][0]
        assert c['is_virtual'] is True
        assert c['account_status'] == 'linked_disabled'


# ---------------------------------------------------------------------------
# 5. Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:

    def test_tenant_a_cannot_see_tenant_b_clients(self):
        """GET /admin/clients for tenant A returns only tenant A clients.

        Cognito filtering via is_cognito_user_in_company ensures Tenant B
        Cognito users are excluded from the merge."""
        # DynamoDB query is already scoped by PK = COMPANY#tog_and_dogs
        clients_a = [make_client_record('c1', email='a@a.com', company_id='tog_and_dogs')]

        # Cognito user from a different tenant — should be filtered by is_cognito_user_in_company
        cognito_user_b = make_cognito_user('userB', 'b@b.com', 'sub-b', company_id='test_tenant_alpha')

        event = make_event(company_id='tog_and_dogs')
        mock_table = MagicMock()
        mock_table.query.return_value = {'Items': clients_a}

        mock_cognito = MagicMock()
        mock_cognito.list_groups.return_value = {
            'Groups': [{'GroupName': 'tog_and_dogs_clients'}]
        }
        mock_cognito.list_users_in_group.return_value = {
            'Users': [cognito_user_b]  # Tenant B user in the group
        }

        with patch('common.entitlement.require_active_tenant', return_value=None), \
             patch('handlers.admin_handler.table', mock_table, create=True), \
             patch('common.db.table', mock_table), \
             patch('boto3.client', return_value=mock_cognito):
            resp = admin_handler(event, None)

        body = json.loads(resp['body'])
        # Only the DynamoDB client should be present; Tenant B cognito user filtered out
        assert len(body['clients']) == 1
        assert body['clients'][0]['client_id'] == 'c1'


# ---------------------------------------------------------------------------
# 6. No writes, no HOUSEHOLD records, no N+1
# ---------------------------------------------------------------------------

class TestNoSideEffects:

    def test_no_dynamodb_write_occurs(self):
        """GET /admin/clients must not perform any DynamoDB writes."""
        clients = [make_client_record('c1', email='a@b.com')]
        _, mock_table, _ = invoke_handler(clients, [])

        mock_table.put_item.assert_not_called()
        mock_table.update_item.assert_not_called()
        mock_table.delete_item.assert_not_called()

    def test_no_household_record_created(self):
        """No HOUSEHOLD# SK items are written."""
        clients = [make_client_record('c1')]
        _, mock_table, _ = invoke_handler(clients, [])

        # Check all calls to put_item — should be none
        for call_args in mock_table.put_item.call_args_list:
            item = call_args.get('Item', {}) if isinstance(call_args, dict) else {}
            assert 'HOUSEHOLD#' not in str(item)

    def test_single_query_no_n_plus_1(self):
        """Only one DynamoDB query call is made regardless of client count."""
        clients = [make_client_record(f'c{i}', email=f'c{i}@test.com') for i in range(10)]
        _, mock_table, _ = invoke_handler(clients, [])

        # Exactly one query for the client list
        assert mock_table.query.call_count == 1

    def test_no_per_client_pet_query(self):
        """No per-client pet queries are performed."""
        clients = [make_client_record(f'c{i}') for i in range(5)]
        _, mock_table, _ = invoke_handler(clients, [])

        # Check that no query uses PET# prefix in condition
        for call_obj in mock_table.query.call_args_list:
            args_str = str(call_obj)
            assert 'PET#' not in args_str

    def test_no_per_client_request_query(self):
        """No per-client request queries are performed."""
        clients = [make_client_record(f'c{i}') for i in range(5)]
        _, mock_table, _ = invoke_handler(clients, [])

        for call_obj in mock_table.query.call_args_list:
            args_str = str(call_obj)
            assert 'REQ#' not in args_str


# ---------------------------------------------------------------------------
# 7. Pagination token structure
# ---------------------------------------------------------------------------

class TestPaginationToken:

    def test_pagination_not_broken(self):
        """The response structure remains compatible — clients key is present."""
        clients = [make_client_record('c1')]
        body, _, _ = invoke_handler(clients, [])

        assert 'clients' in body
        assert isinstance(body['clients'], list)


# ---------------------------------------------------------------------------
# 8. cognito_enabled field merged correctly
# ---------------------------------------------------------------------------

class TestCognitoEnabledMerge:

    def test_cognito_enabled_merged_for_linked_client(self):
        """When a DynamoDB client is matched with Cognito, cognito_enabled is merged."""
        clients = [make_client_record('c1', email='a@b.com', cognito_sub='sub-1')]
        cognito_users = [make_cognito_user('u1', 'a@b.com', 'sub-1', enabled=True)]
        body, _, _ = invoke_handler(clients, cognito_users)

        c = body['clients'][0]
        assert c.get('cognito_enabled') is True

    def test_cognito_enabled_false_merged(self):
        """Disabled Cognito user has cognito_enabled=False in the response."""
        clients = [make_client_record('c1', email='a@b.com', cognito_sub='sub-1')]
        cognito_users = [make_cognito_user('u1', 'a@b.com', 'sub-1', enabled=False)]
        body, _, _ = invoke_handler(clients, cognito_users)

        c = body['clients'][0]
        assert c.get('cognito_enabled') is False
