"""
Phase 1B.5C-D.1 Test Suite — Platform-Managed Protected Admin Controls

Tests for data-driven protected admin status (`is_platform_protected`), computed `is_protected` status,
authorization rules, self-unprotect prevention, last protected admin guard, and audit logging.
"""

import pytest
import json
from unittest.mock import patch, MagicMock, ANY
from handlers.admin_handler import handler as admin_handler
from common.protected_accounts import is_protected_profile, is_config_protected, is_platform_protected


def make_event(method, path_params=None, body=None, sub='test-sub', email='test@toganddogs.com', groups='Admin'):
    return {
        'httpMethod': method,
        'path': f"/admin/staff/{path_params.get('staff_id', '')}" if path_params else '/admin/staff',
        'pathParameters': path_params or {},
        'requestContext': {
            'authorizer': {
                'claims': {
                    'sub': sub,
                    'email': email,
                    'cognito:groups': groups
                }
            }
        },
        'body': json.dumps(body) if body else None
    }


def make_table_get_item_side_effect(target_staff):
    def _side_effect(Key, **kwargs):
        pk = Key.get("PK", "")
        sk = Key.get("SK", "")
        if str(pk).startswith("TENANT#"):
            return {
                "Item": {
                    "PK": str(pk),
                    "SK": "METADATA",
                    "company_id": str(pk).replace("TENANT#", ""),
                    "subscription_status": "active",
                    "is_active": True
                }
            }
        if str(pk).startswith("COMPANY#") and str(sk).startswith("STAFF#"):
            return {"Item": dict(target_staff)}
        return {}
    return _side_effect


@pytest.fixture
def mock_audit():
    with patch('handlers.admin_handler.log_action') as mock_log:
        yield mock_log


def test_unit_protected_accounts_computed_status():
    # 1. Config-protected + data-unprotected -> remains protected
    config_only = {'email': 'support@usmissionhero.com', 'is_platform_protected': False}
    assert is_config_protected(config_only) is True
    assert is_platform_protected(config_only) is False
    assert is_protected_profile(config_only) is True

    # 2. Data-protected + config-unprotected -> remains protected
    data_only = {'email': 'regular_admin@example.com', 'is_platform_protected': True}
    assert is_config_protected(data_only) is False
    assert is_platform_protected(data_only) is True
    assert is_protected_profile(data_only) is True

    # 3. Neither -> unprotected
    neither = {'email': 'normal_staff@example.com', 'is_platform_protected': False}
    assert is_config_protected(neither) is False
    assert is_platform_protected(neither) is False
    assert is_protected_profile(neither) is False


def test_owner_can_set_protected_status(mock_audit):
    target_staff = {
        'PK': 'COMPANY#tog_and_dogs',
        'SK': 'STAFF#staff_2',
        'staff_id': 'staff_2',
        'email': 'staff2@example.com',
        'display_name': 'Staff Two',
        'role': 'Admin',
        'is_platform_protected': False
    }
    
    with patch('common.db.table') as mock_table, patch('handlers.admin_handler.table') as mock_handler_table:
        def side_effect(Key, **kwargs):
            pk = Key.get("PK", "")
            sk = Key.get("SK", "")
            if str(pk).startswith("TENANT#"):
                return {
                    "Item": {
                        "PK": str(pk),
                        "SK": "METADATA",
                        "company_id": str(pk).replace("TENANT#", ""),
                        "subscription_status": "active",
                        "is_active": True
                    }
                }
            if sk == 'STAFF#staff_2':
                return {'Item': target_staff}
            return {}

        mock_table.get_item.side_effect = side_effect
        mock_handler_table.get_item.side_effect = side_effect
        mock_table.query.return_value = {'Items': []}
        mock_handler_table.query.return_value = {'Items': []}

        # Caller is owner
        event = make_event('PATCH', path_params={'staff_id': 'staff_2'}, body={'action': 'set-protected'},
                           sub='owner-sub', email='owner@example.com', groups='owner')
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body['is_platform_protected'] is True
        mock_audit.assert_called_with(event, "SET_PROTECTED_ADMIN", ANY, ANY, metadata=ANY)


def test_protected_admin_can_set_protected_status(mock_audit):
    target_staff = {
        'PK': 'COMPANY#tog_and_dogs',
        'SK': 'STAFF#staff_2',
        'staff_id': 'staff_2',
        'email': 'staff2@example.com',
        'display_name': 'Staff Two',
        'role': 'Admin',
        'is_platform_protected': False
    }

    with patch('common.db.table') as mock_table, patch('handlers.admin_handler.table') as mock_handler_table:
        def side_effect(Key, **kwargs):
            pk = Key.get("PK", "")
            sk = Key.get("SK", "")
            if str(pk).startswith("TENANT#"):
                return {
                    "Item": {
                        "PK": str(pk),
                        "SK": "METADATA",
                        "company_id": str(pk).replace("TENANT#", ""),
                        "subscription_status": "active",
                        "is_active": True
                    }
                }
            if sk == 'STAFF#staff_2':
                return {'Item': target_staff}
            return {}

        mock_table.get_item.side_effect = side_effect
        mock_handler_table.get_item.side_effect = side_effect
        mock_table.query.return_value = {'Items': []}
        mock_handler_table.query.return_value = {'Items': []}

        # Caller is protected admin via config email support@usmissionhero.com
        event = make_event('PATCH', path_params={'staff_id': 'staff_2'}, body={'action': 'set-protected'},
                           sub='protected-admin-sub', email='support@usmissionhero.com', groups='Admin')
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body['is_platform_protected'] is True
        mock_audit.assert_called_with(event, "SET_PROTECTED_ADMIN", ANY, ANY, metadata=ANY)


def test_normal_admin_cannot_set_or_unset_protected_status(mock_audit):
    target_staff = {
        'PK': 'COMPANY#tog_and_dogs',
        'SK': 'STAFF#staff_2',
        'staff_id': 'staff_2',
        'email': 'staff2@example.com',
        'display_name': 'Staff Two',
        'role': 'Admin',
        'is_platform_protected': False
    }
    
    with patch('common.db.table') as mock_table, patch('handlers.admin_handler.table') as mock_handler_table:
        side_effect = make_table_get_item_side_effect(target_staff)
        mock_table.get_item.side_effect = side_effect
        mock_handler_table.get_item.side_effect = side_effect
        mock_table.query.return_value = {'Items': []}
        mock_handler_table.query.return_value = {'Items': []}

        # Caller is normal admin (not owner, not platform admin, not protected)
        event = make_event('PATCH', path_params={'staff_id': 'staff_2'}, body={'action': 'set-protected'},
                           sub='normal-admin-sub', email='normaladmin@example.com', groups='Admin')
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 403
        assert "Forbidden" in resp["body"] or "Only Owner" in resp["body"]
        mock_audit.assert_called_with(event, "BLOCKED_PROTECTED_ACCOUNT_ACTION", ANY, ANY, metadata=ANY)


def test_user_cannot_unprotect_self(mock_audit):
    self_staff = {
        'PK': 'COMPANY#tog_and_dogs',
        'SK': 'STAFF#self_staff',
        'staff_id': 'self_staff',
        'email': 'myadmin@example.com',
        'cognito_sub': 'my-sub',
        'display_name': 'My Admin',
        'role': 'Admin',
        'is_platform_protected': True
    }
    
    with patch('common.db.table') as mock_table, patch('handlers.admin_handler.table') as mock_handler_table:
        side_effect = make_table_get_item_side_effect(self_staff)
        mock_table.get_item.side_effect = side_effect
        mock_handler_table.get_item.side_effect = side_effect
        mock_table.query.return_value = {'Items': []}
        mock_handler_table.query.return_value = {'Items': []}

        event = make_event('PATCH', path_params={'staff_id': 'self_staff'}, body={'action': 'unset-protected'},
                           sub='my-sub', email='myadmin@example.com', groups='Owner')
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 403
        assert "your own account" in resp["body"]
        mock_audit.assert_called_with(event, "BLOCKED_PROTECTED_ACCOUNT_ACTION", ANY, ANY, metadata=ANY)


def test_cannot_remove_last_protected_admin(mock_audit):
    target_staff = {
        'PK': 'COMPANY#tog_and_dogs',
        'SK': 'STAFF#staff_only_protected',
        'staff_id': 'staff_only_protected',
        'email': 'only_protected@example.com',
        'cognito_sub': 'sub-only-protected',
        'display_name': 'Only Protected',
        'role': 'Admin',
        'is_platform_protected': True
    }
    
    with patch('common.db.table') as mock_table, patch('handlers.admin_handler.table') as mock_handler_table:
        side_effect = make_table_get_item_side_effect(target_staff)
        mock_table.get_item.side_effect = side_effect
        mock_handler_table.get_item.side_effect = side_effect
        # Query returns ONLY this 1 protected staff member
        mock_table.query.return_value = {'Items': [dict(target_staff)]}
        mock_handler_table.query.return_value = {'Items': [dict(target_staff)]}

        # Caller is Owner (different sub/email to avoid self check)
        event = make_event('PATCH', path_params={'staff_id': 'staff_only_protected'}, body={'action': 'unset-protected'},
                           sub='owner-sub', email='owner@example.com', groups='Owner')
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 400
        assert "last protected admin" in resp["body"]
        mock_audit.assert_called_with(event, "BLOCKED_PROTECTED_ACCOUNT_ACTION", ANY, ANY, metadata=ANY)


def test_data_protected_profile_blocks_delete_disable_unlink(mock_audit):
    data_protected_staff = {
        'PK': 'COMPANY#tog_and_dogs',
        'SK': 'STAFF#staff_data_prot',
        'staff_id': 'staff_data_prot',
        'email': 'dataprot@example.com',
        'cognito_sub': 'sub-data-prot',
        'display_name': 'Data Protected Staff',
        'role': 'Admin',
        'is_platform_protected': True
    }
    
    with patch('common.db.table') as mock_table, patch('handlers.admin_handler.table') as mock_handler_table:
        side_effect = make_table_get_item_side_effect(data_protected_staff)
        mock_table.get_item.side_effect = side_effect
        mock_handler_table.get_item.side_effect = side_effect

        # Try disable
        event_disable = make_event('PATCH', path_params={'staff_id': 'staff_data_prot'}, body={'action': 'disable'},
                                   sub='other-owner', email='owner@example.com', groups='Owner')
        resp = admin_handler(event_disable, None)
        assert resp["statusCode"] == 403
        assert "protected platform account" in resp["body"]

        # Try unlink
        event_unlink = make_event('PATCH', path_params={'staff_id': 'staff_data_prot'}, body={'action': 'unlink'},
                                  sub='other-owner', email='owner@example.com', groups='Owner')
        resp_unlink = admin_handler(event_unlink, None)
        assert resp_unlink["statusCode"] == 403

        # Try DELETE
        event_delete = make_event('DELETE', path_params={'staff_id': 'staff_data_prot'},
                                  sub='other-owner', email='owner@example.com', groups='Owner')
        resp_delete = admin_handler(event_delete, None)
        assert resp_delete["statusCode"] == 403


def test_audit_event_logged_for_set_and_unset_protected(mock_audit):
    staff_1 = {
        'PK': 'COMPANY#tog_and_dogs',
        'SK': 'STAFF#staff_1',
        'staff_id': 'staff_1',
        'email': 'staff1@example.com',
        'cognito_sub': 'sub-1',
        'display_name': 'Staff One',
        'role': 'Admin',
        'is_platform_protected': True
    }
    staff_2 = {
        'PK': 'COMPANY#tog_and_dogs',
        'SK': 'STAFF#staff_2',
        'staff_id': 'staff_2',
        'email': 'staff2@example.com',
        'cognito_sub': 'sub-2',
        'display_name': 'Staff Two',
        'role': 'Admin',
        'is_platform_protected': True
    }
    
    with patch('common.db.table') as mock_table, patch('handlers.admin_handler.table') as mock_handler_table:
        # Query returns 2 protected profiles so unprotecting staff_2 won't hit last admin check
        mock_table.query.return_value = {'Items': [dict(staff_1), dict(staff_2)]}
        mock_handler_table.query.return_value = {'Items': [dict(staff_1), dict(staff_2)]}

        side_effect_1 = make_table_get_item_side_effect(staff_1)
        mock_table.get_item.side_effect = side_effect_1
        mock_handler_table.get_item.side_effect = side_effect_1

        event_set = make_event('PATCH', path_params={'staff_id': 'staff_1'}, body={'action': 'set-protected'},
                               sub='owner-sub', email='owner@example.com', groups='Owner')
        resp_set = admin_handler(event_set, None)
        assert resp_set["statusCode"] == 200
        mock_audit.assert_called_with(event_set, "SET_PROTECTED_ADMIN", ANY, ANY, metadata=ANY)

        side_effect_2 = make_table_get_item_side_effect(staff_2)
        mock_table.get_item.side_effect = side_effect_2
        mock_handler_table.get_item.side_effect = side_effect_2

        event_unset = make_event('PATCH', path_params={'staff_id': 'staff_2'}, body={'action': 'unset-protected'},
                                 sub='owner-sub', email='owner@example.com', groups='Owner')
        resp_unset = admin_handler(event_unset, None)
        assert resp_unset["statusCode"] == 200
        mock_audit.assert_called_with(event_unset, "UNSET_PROTECTED_ADMIN", ANY, ANY, metadata=ANY)
