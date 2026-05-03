import pytest
import json
from unittest.mock import patch, MagicMock, ANY
from handlers.admin_handler import handler as admin_handler

@pytest.fixture
def mock_db():
    with patch('common.db.table') as mock_table:
        # get_item is used via items_table.get_item
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

def create_admin_event(method, path_params=None, body=None, sub='admin-sub', email='admin@toganddogs.com'):
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
    # Setup: Target is protected (admin@toganddogs.com)
    protected_staff = {
        'PK': 'COMPANY#1',
        'SK': 'STAFF#protected_1',
        'staff_id': 'protected_1',
        'email': 'admin@toganddogs.com',
        'cognito_sub': '74b86488-1011-7029-bb6d-dad984e1463c'
    }
    mock_db.get_item.return_value = {'Item': protected_staff}
    
    event = create_admin_event('DELETE', path_params={'staff_id': 'protected_1'}, sub='other-admin', email='other@test.com')
    
    # We also need to patch get_item if it's imported from common.db
    with patch('handlers.admin_handler.get_item', return_value=protected_staff):
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
    mock_db.get_item.return_value = {'Item': self_staff}
    
    event = create_admin_event('PATCH', path_params={'staff_id': 'self_1'}, body={'action': 'disable'}, sub='my-sub', email='me@test.com')
    
    with patch('handlers.admin_handler.get_item', return_value=self_staff):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 403
        assert "blocked" in resp["body"]

def test_protected_fields_patch_ignored(mock_db, mock_audit, mock_cognito):
    # Setup: Target is protected
    protected_staff = {
        'PK': 'COMPANY#1',
        'SK': 'STAFF#protected_1',
        'staff_id': 'protected_1',
        'email': 'admin@toganddogs.com',
        'role': 'owner',
        'display_name': 'Original Name',
        'cognito_sub': '74b86488-1011-7029-bb6d-dad984e1463c'
    }
    mock_db.get_item.return_value = {'Item': protected_staff}
    
    # PATCH event trying to change role and email
    event = create_admin_event('PATCH', path_params={'staff_id': 'protected_1'}, 
                               body={'role': 'Staff', 'email': 'hacker@test.com', 'display_name': 'New Name'}, 
                               sub='other-admin', email='other@test.com')
    
    with patch('handlers.admin_handler.get_item', return_value=protected_staff):
        # Mock query for display_name duplicate check
        mock_db.query.return_value = {'Items': [protected_staff]}
        
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        # The return value from handler should have updated display_name but NOT role or email
        body = json.loads(resp["body"])
        assert body['display_name'] == 'New Name'
        assert body['role'] == 'owner'
        assert body['email'] == 'admin@toganddogs.com'
