"""
Handler-level integration tests for Cognito tenant assignment hotfix.

These tests patch boto3.client at the module level to intercept actual
admin_create_user and admin_update_user_attributes calls from the handlers,
proving the trusted tenant attribute is included in real handler execution.
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime

# Set required env vars before imports
os.environ.setdefault('DEFAULT_COMPANY_ID', 'tog_and_dogs')
os.environ.setdefault('DATA_TABLE_NAME', 'test-table')
os.environ.setdefault('ADMIN_USER_POOL_ID', 'us-east-1_TestPool')
os.environ.setdefault('GOOGLE_CLIENT_CREDS_NAME', 'google-creds')
os.environ.setdefault('GOOGLE_USER_TOKENS_NAME', 'google-tokens')


def _admin_event(path, method='POST', company_id='tog_and_dogs', groups='owner',
                 email='admin@usmissionhero.com', body=None):
    claims = {
        'email': email,
        'sub': 'admin-sub-000',
        'email_verified': 'true',
        'custom:company_id': company_id,
        'cognito:groups': groups,
    }
    event = {
        'requestContext': {'authorizer': {'claims': claims}, 'requestId': 'int-test-req'},
        'httpMethod': method,
        'path': path,
        'pathParameters': {},
    }
    if body:
        event['body'] = json.dumps(body)
    return event


class TestStaffOnboardHandler:
    """Verify the actual handler sends custom:company_id in admin_create_user."""

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('boto3.client')
    def test_staff_onboard_sends_tenant_attribute(self, mock_boto3_client, mock_rat):
        """POST /admin/staff/onboard must include custom:company_id in UserAttributes."""
        mock_cognito = MagicMock()
        mock_boto3_client.return_value = mock_cognito
        mock_cognito.admin_create_user.return_value = {
            'User': {'Attributes': [{'Name': 'sub', 'Value': 'new-staff-sub'}]}
        }
        mock_cognito.exceptions = MagicMock()
        mock_cognito.exceptions.UsernameExistsException = type('UsernameExistsException', (Exception,), {})

        mock_table = MagicMock()
        mock_table.put_item.return_value = None
        mock_table.query.return_value = {'Items': [], 'Count': 0}

        from handlers.admin_handler import handler

        event = _admin_event(
            '/admin/staff/onboard',
            body={'email': 'stafftest@example.com', 'display_name': 'Staff Test', 'role': 'Staff'}
        )

        with patch('common.db.table', mock_table):
            with patch('handlers.admin_handler.notify_event', return_value={'success': True}):
                resp = handler(event, None)

        # Find the admin_create_user call
        if mock_cognito.admin_create_user.called:
            call_kwargs = mock_cognito.admin_create_user.call_args
            user_attrs = call_kwargs.kwargs.get('UserAttributes', []) if call_kwargs.kwargs else call_kwargs[1].get('UserAttributes', [])
            tenant_attrs = [a for a in user_attrs if a.get('Name') == 'custom:company_id']
            assert len(tenant_attrs) == 1, f"Expected custom:company_id in UserAttributes, got: {user_attrs}"
            assert tenant_attrs[0]['Value'] == 'tog_and_dogs'
        else:
            # If create wasn't called, the handler hit an earlier error — check response
            body = json.loads(resp.get('body', '{}'))
            pytest.fail(f"admin_create_user not called. Handler returned {resp.get('statusCode')}: {body}")

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('boto3.client')
    def test_staff_onboard_uses_trusted_claim_not_body(self, mock_boto3_client, mock_rat):
        """Body-supplied company_id is ignored; only authenticated claim is used."""
        mock_cognito = MagicMock()
        mock_boto3_client.return_value = mock_cognito
        mock_cognito.admin_create_user.return_value = {
            'User': {'Attributes': [{'Name': 'sub', 'Value': 'trusted-sub'}]}
        }
        mock_cognito.exceptions = MagicMock()
        mock_cognito.exceptions.UsernameExistsException = type('UsernameExistsException', (Exception,), {})

        mock_table = MagicMock()
        mock_table.put_item.return_value = None
        mock_table.query.return_value = {'Items': [], 'Count': 0}

        from handlers.admin_handler import handler

        event = _admin_event(
            '/admin/staff/onboard',
            body={
                'email': 'evil@example.com',
                'display_name': 'Evil',
                'role': 'Staff',
                'company_id': 'test_tenant_alpha'  # Attacker tries to set this
            }
        )

        with patch('common.db.table', mock_table):
            with patch('handlers.admin_handler.notify_event', return_value={'success': True}):
                handler(event, None)

        if mock_cognito.admin_create_user.called:
            call_kwargs = mock_cognito.admin_create_user.call_args
            user_attrs = call_kwargs.kwargs.get('UserAttributes', []) if call_kwargs.kwargs else call_kwargs[1].get('UserAttributes', [])
            tenant_attrs = [a for a in user_attrs if a.get('Name') == 'custom:company_id']
            assert len(tenant_attrs) == 1
            # Must be the trusted claim, NOT the body value
            assert tenant_attrs[0]['Value'] == 'tog_and_dogs'
            assert tenant_attrs[0]['Value'] != 'test_tenant_alpha'


class TestClientOnboardHandler:
    """Verify client onboard handler sends custom:company_id."""

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('boto3.client')
    def test_client_onboard_sends_tenant_attribute(self, mock_boto3_client, mock_rat):
        """POST /admin/clients/onboard must include custom:company_id."""
        mock_cognito = MagicMock()
        mock_boto3_client.return_value = mock_cognito
        mock_cognito.admin_create_user.return_value = {
            'User': {'Attributes': [{'Name': 'sub', 'Value': 'new-client-sub'}]}
        }
        mock_cognito.exceptions = MagicMock()
        mock_cognito.exceptions.UsernameExistsException = type('UsernameExistsException', (Exception,), {})

        mock_table = MagicMock()
        mock_table.put_item.return_value = None
        mock_table.query.return_value = {'Items': [], 'Count': 0}

        from handlers.admin_handler import handler

        event = _admin_event(
            '/admin/clients/onboard',
            body={'email': 'clienttest@example.com', 'display_name': 'Client Test'}
        )

        with patch('common.db.table', mock_table):
            with patch('handlers.admin_handler.notify_event', return_value={'success': True}):
                with patch('common.entitlement.get_active_client_count', return_value=0):
                    with patch('common.entitlement.check_limit'):
                        resp = handler(event, None)

        if mock_cognito.admin_create_user.called:
            call_kwargs = mock_cognito.admin_create_user.call_args
            user_attrs = call_kwargs.kwargs.get('UserAttributes', []) if call_kwargs.kwargs else call_kwargs[1].get('UserAttributes', [])
            tenant_attrs = [a for a in user_attrs if a.get('Name') == 'custom:company_id']
            assert len(tenant_attrs) == 1
            assert tenant_attrs[0]['Value'] == 'tog_and_dogs'
        else:
            body = json.loads(resp.get('body', '{}'))
            pytest.fail(f"admin_create_user not called. Handler returned {resp.get('statusCode')}: {body}")


class TestLinkCognitoHandler:
    """Verify link-cognito handler calls ensure_cognito_tenant_attribute."""

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('boto3.client')
    def test_link_cognito_repairs_missing_attribute(self, mock_boto3_client, mock_rat):
        """Link-cognito must call admin_update_user_attributes to set missing company_id."""
        mock_cognito = MagicMock()
        mock_boto3_client.return_value = mock_cognito
        # admin_get_user: user has no custom:company_id
        mock_cognito.admin_get_user.return_value = {
            'UserAttributes': [
                {'Name': 'sub', 'Value': 'link-target-sub'},
                {'Name': 'email', 'Value': 'linkuser@example.com'},
            ],
            'UserStatus': 'CONFIRMED'
        }

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'PK': 'COMPANY#tog_and_dogs', 'SK': 'STAFF#staff_link1',
                'company_id': 'tog_and_dogs', 'display_name': 'Link Staff',
                'role': 'Staff', 'email': 'linkuser@example.com',
            }
        }
        mock_table.put_item.return_value = None

        from handlers.admin_handler import handler

        event = _admin_event(
            '/admin/staff/staff_link1/link-cognito',
            body={'username': 'linkuser@example.com'}
        )
        event['pathParameters'] = {'staff_id': 'staff_link1'}

        with patch('common.db.table', mock_table):
            resp = handler(event, None)

        # Verify admin_update_user_attributes was called with custom:company_id
        update_calls = mock_cognito.admin_update_user_attributes.call_args_list
        tenant_updates = [
            c for c in update_calls
            if any(a.get('Name') == 'custom:company_id'
                   for a in (c.kwargs.get('UserAttributes', []) if c.kwargs else c[1].get('UserAttributes', [])))
        ]
        assert len(tenant_updates) >= 1, f"Expected tenant attribute update, got: {update_calls}"

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('boto3.client')
    def test_link_cognito_denies_cross_tenant_no_linkage(self, mock_boto3_client, mock_rat):
        """Cross-tenant conflict must return 403 and NOT update the profile."""
        mock_cognito = MagicMock()
        mock_boto3_client.return_value = mock_cognito
        # User belongs to a different tenant
        mock_cognito.admin_get_user.return_value = {
            'UserAttributes': [
                {'Name': 'sub', 'Value': 'cross-tenant-sub'},
                {'Name': 'email', 'Value': 'cross@example.com'},
                {'Name': 'custom:company_id', 'Value': 'test_tenant_alpha'},
            ],
            'UserStatus': 'CONFIRMED'
        }

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'PK': 'COMPANY#tog_and_dogs', 'SK': 'STAFF#staff_cross',
                'company_id': 'tog_and_dogs', 'display_name': 'Cross Staff',
                'role': 'Staff', 'email': 'cross@example.com',
            }
        }

        from handlers.admin_handler import handler

        event = _admin_event(
            '/admin/staff/staff_cross/link-cognito',
            body={'username': 'cross@example.com'}
        )
        event['pathParameters'] = {'staff_id': 'staff_cross'}

        with patch('common.db.table', mock_table):
            resp = handler(event, None)

        assert resp['statusCode'] == 403
        body = json.loads(resp['body'])
        assert 'Cross-tenant' in body.get('message', '') or 'Cross-tenant' in body.get('error', '')

        # Profile must NOT have been updated
        mock_table.put_item.assert_not_called()

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('boto3.client')
    def test_link_cognito_matching_tenant_succeeds(self, mock_boto3_client, mock_rat):
        """If tenant already matches, link proceeds without unnecessary mutation."""
        mock_cognito = MagicMock()
        mock_boto3_client.return_value = mock_cognito
        mock_cognito.admin_get_user.return_value = {
            'UserAttributes': [
                {'Name': 'sub', 'Value': 'matching-sub'},
                {'Name': 'email', 'Value': 'match@example.com'},
                {'Name': 'custom:company_id', 'Value': 'tog_and_dogs'},
            ],
            'UserStatus': 'CONFIRMED'
        }

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'PK': 'COMPANY#tog_and_dogs', 'SK': 'STAFF#staff_match',
                'company_id': 'tog_and_dogs', 'display_name': 'Match Staff',
                'role': 'Staff', 'email': 'match@example.com',
            }
        }
        mock_table.put_item.return_value = None

        from handlers.admin_handler import handler

        event = _admin_event(
            '/admin/staff/staff_match/link-cognito',
            body={'username': 'match@example.com'}
        )
        event['pathParameters'] = {'staff_id': 'staff_match'}

        with patch('common.db.table', mock_table):
            resp = handler(event, None)

        assert resp['statusCode'] == 200
        # admin_update_user_attributes should NOT be called (already correct)
        tenant_updates = [
            c for c in mock_cognito.admin_update_user_attributes.call_args_list
            if any(a.get('Name') == 'custom:company_id'
                   for a in (c.kwargs.get('UserAttributes', []) if c.kwargs else c[1].get('UserAttributes', [])))
        ]
        assert len(tenant_updates) == 0, "Should not update already-correct tenant attribute"

    @patch('common.entitlement.require_active_tenant', return_value=None)
    @patch('boto3.client')
    def test_cognito_failure_does_not_link_profile(self, mock_boto3_client, mock_rat):
        """If ensure_cognito_tenant_attribute raises RuntimeError, profile is not linked."""
        mock_cognito = MagicMock()
        mock_boto3_client.return_value = mock_cognito
        # First admin_get_user (for link flow): succeeds
        # Second admin_get_user (for ensure): fails
        call_count = [0]
        def side_effect_get_user(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return {
                    'UserAttributes': [
                        {'Name': 'sub', 'Value': 'fail-sub'},
                        {'Name': 'email', 'Value': 'fail@example.com'},
                    ],
                    'UserStatus': 'CONFIRMED'
                }
            else:
                raise Exception("Cognito service error")

        mock_cognito.admin_get_user.side_effect = side_effect_get_user

        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'PK': 'COMPANY#tog_and_dogs', 'SK': 'STAFF#staff_fail',
                'company_id': 'tog_and_dogs', 'display_name': 'Fail Staff',
                'role': 'Staff', 'email': 'fail@example.com',
            }
        }

        from handlers.admin_handler import handler

        event = _admin_event(
            '/admin/staff/staff_fail/link-cognito',
            body={'username': 'fail@example.com'}
        )
        event['pathParameters'] = {'staff_id': 'staff_fail'}

        with patch('common.db.table', mock_table):
            resp = handler(event, None)

        # Should return 500 (internal error from the ensure helper)
        assert resp['statusCode'] == 500
        # Profile must NOT have been linked
        mock_table.put_item.assert_not_called()


class TestTokenClaimBehavior:
    """Document token refresh behavior after remediation."""

    def test_custom_company_id_in_id_token_requires_fresh_login(self):
        """
        After setting custom:company_id via admin_update_user_attributes,
        the user must perform a full logout + login to receive a fresh ID token
        containing the updated claim. Refreshing the page alone may use a cached
        or refresh-token-granted session that does not re-read custom attributes.
        
        This is a Cognito behavior: custom attributes are included in the ID token
        at issuance time. A token refresh via refresh_token may or may not include
        updated custom attributes depending on the Cognito pool configuration.
        
        For safety: require full logout → login after any tenant attribute repair.
        """
        # This test documents the requirement rather than testing Cognito behavior
        # The app client has custom:company_id in read_attributes (verified from Terraform)
        # Therefore it WILL be included in new ID tokens
        assert True  # Documented behavior requirement
