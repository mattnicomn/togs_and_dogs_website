import pytest
import json
from unittest.mock import patch, MagicMock, ANY
from handlers.admin_handler import handler as admin_handler

def make_get_item_mock(target_item):
    def _side_effect(pk_or_key, sk=None):
        if isinstance(pk_or_key, dict):
            pk = pk_or_key.get("PK", "")
        else:
            pk = pk_or_key
        if pk and str(pk).startswith("TENANT#"):
            return {
                "PK": str(pk),
                "SK": "METADATA",
                "company_id": str(pk).replace("TENANT#", ""),
                "subscription_status": "active",
                "is_active": True
            }
        return dict(target_item)
    return _side_effect

@pytest.fixture
def mock_db():
    with patch('common.db.table') as mock_table:
        def table_get_item_side_effect(Key, **kwargs):
            pk = Key.get("PK", "")
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
            val = getattr(mock_table, '_target_item', None)
            if val:
                return {"Item": val}
            return {}
        mock_table.get_item.side_effect = table_get_item_side_effect
        yield mock_table

@pytest.fixture
def mock_audit():
    with patch('handlers.admin_handler.log_action') as mock_log:
        yield mock_log

@pytest.fixture
def mock_cognito():
    with patch('boto3.client') as mock_client:
        cognito = MagicMock()
        mock_client.return_value = cognito
        yield cognito

def create_admin_event(method, path_params=None, body=None, sub='admin-sub', email='support@usmissionhero.com'):
    return {
        'httpMethod': method,
        'path': '/admin/staff',
        'pathParameters': path_params or {},
        'requestContext': {
            'authorizer': {
                'claims': {
                    'sub': sub,
                    'email': email,
                    'cognito:groups': 'Admin'
                }
            }
        },
        'body': json.dumps(body) if body else None
    }

def test_protected_account_delete_blocked(mock_db, mock_audit, mock_cognito):
    # Setup: Target is protected (support@usmissionhero.com)
    protected_staff = {
        'PK': 'COMPANY#1',
        'SK': 'STAFF#protected_1',
        'staff_id': 'protected_1',
        'email': 'support@usmissionhero.com',
        'cognito_sub': 'support-sub-123'
    }
    mock_db._target_item = protected_staff
    mock_db.get_item.return_value = {'Item': protected_staff}
    
    event = create_admin_event('DELETE', path_params={'staff_id': 'protected_1'}, sub='other-admin', email='other@test.com')
    
    # We also need to patch get_item if it's imported from common.db
    with patch('handlers.admin_handler.get_item', side_effect=make_get_item_mock(protected_staff)):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 403
        assert "Action blocked" in resp["body"]
        mock_audit.assert_called_with(event, "BLOCKED_PROTECTED_ACCOUNT_ACTION", ANY, ANY, metadata=ANY)

def test_self_account_disable_blocked(mock_db, mock_audit, mock_cognito):
    # Setup: Target is the same as current user
    self_staff = {
        'PK': 'COMPANY#1',
        'SK': 'STAFF#self_1',
        'staff_id': 'self_1',
        'email': 'me@test.com',
        'cognito_sub': 'my-sub'
    }
    mock_db._target_item = self_staff
    mock_db.get_item.return_value = {'Item': self_staff}
    
    event = create_admin_event('PATCH', path_params={'staff_id': 'self_1'}, body={'action': 'disable'}, sub='my-sub', email='me@test.com')
    
    with patch('handlers.admin_handler.get_item', side_effect=make_get_item_mock(self_staff)):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 403
        assert "blocked" in resp["body"]

def test_protected_fields_patch_ignored(mock_db, mock_audit, mock_cognito):
    # Setup: Target is protected
    protected_staff = {
        'PK': 'COMPANY#1',
        'SK': 'STAFF#protected_1',
        'staff_id': 'protected_1',
        'email': 'support@usmissionhero.com',
        'role': 'owner',
        'display_name': 'Original Name',
        'cognito_sub': 'support-sub-123'
    }
    mock_db._target_item = protected_staff
    mock_db.get_item.return_value = {'Item': protected_staff}
    
    # PATCH event trying to change role and email
    event = create_admin_event('PATCH', path_params={'staff_id': 'protected_1'}, 
                               body={'role': 'Staff', 'email': 'hacker@test.com', 'display_name': 'New Name'}, 
                               sub='other-admin', email='other@test.com')
    
    with patch('handlers.admin_handler.get_item', side_effect=make_get_item_mock(protected_staff)):
        # Mock query for display_name duplicate check
        mock_db.query.return_value = {'Items': [protected_staff]}
        
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        # The return value from handler should have updated display_name but NOT role or email
        body = json.loads(resp["body"])
        assert body['display_name'] == 'New Name'
        assert body['role'] == 'owner'
        assert body['email'] == 'support@usmissionhero.com'
