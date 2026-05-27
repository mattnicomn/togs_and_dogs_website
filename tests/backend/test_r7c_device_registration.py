import pytest
import json
from unittest.mock import patch, MagicMock

# Import the handler
from handlers import device_handler

@pytest.fixture
def mock_db():
    with patch('handlers.device_handler.table') as mock_table, \
         patch('handlers.device_handler.put_item') as mock_put_item:
        yield mock_table, mock_put_item

@pytest.fixture
def mock_auth():
    with patch('handlers.device_handler.get_effective_role') as mock_role, \
         patch('handlers.device_handler.get_claims') as mock_claims, \
         patch('handlers.device_handler.get_current_company_id') as mock_company, \
         patch('handlers.device_handler.resolve_client_identity') as mock_resolve:
        mock_role.return_value = 'client'
        mock_claims.return_value = {'sub': 'user-sub-123', 'email': 'user@example.com'}
        mock_company.return_value = 'tog_and_dogs'
        mock_resolve.return_value = 'client-123'
        yield mock_role, mock_claims, mock_company, mock_resolve

def test_register_device_success(mock_db, mock_auth):
    mock_table, mock_put_item = mock_db
    mock_put_item.return_value = True
    
    mock_table.scan.return_value = {'Items': []}
    
    event = {
        'httpMethod': 'POST',
        'body': json.dumps({
            'push_token': 'ExponentPushToken[12345]',
            'platform': 'ios'
        })
    }
    
    response = device_handler.handler(event, {})
    
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['status'] == 'registered'
    assert 'device_id' in body
    
    mock_put_item.assert_called_once()
    saved_item = mock_put_item.call_args[0][0]
    assert saved_item['entity_type'] == 'PUSH_DEVICE'
    assert saved_item['cognito_sub'] == 'user-sub-123'
    assert saved_item['push_token'] == 'ExponentPushToken[12345]'
    assert saved_item['profile_id'] == 'client-123'

def test_register_device_unauthenticated(mock_db, mock_auth):
    _, mock_claims, _, _ = mock_auth
    mock_claims.return_value = {} # No sub
    
    event = {
        'httpMethod': 'POST',
        'body': json.dumps({'push_token': 'ExponentPushToken[12345]'})
    }
    
    response = device_handler.handler(event, {})
    assert response['statusCode'] == 401

def test_register_device_invalid_token_format(mock_db, mock_auth):
    event = {
        'httpMethod': 'POST',
        'body': json.dumps({'push_token': 'invalid-token-format'})
    }
    response = device_handler.handler(event, {})
    assert response['statusCode'] == 400
    assert 'Invalid push_token format' in response['body']

def test_register_device_duplicate_token_same_user(mock_db, mock_auth):
    mock_table, mock_put_item = mock_db
    
    # Return an existing device for this user
    existing_device = {
        'device_id': 'd-123',
        'cognito_sub': 'user-sub-123',
        'push_token': 'ExponentPushToken[12345]',
        'is_active': False
    }
    mock_table.scan.return_value = {'Items': [existing_device]}
    mock_put_item.return_value = True
    
    event = {
        'httpMethod': 'POST',
        'body': json.dumps({'push_token': 'ExponentPushToken[12345]'})
    }
    
    response = device_handler.handler(event, {})
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['status'] == 'updated'
    assert body['device_id'] == 'd-123'
    
    saved_item = mock_put_item.call_args[0][0]
    assert saved_item['is_active'] is True

def test_register_device_duplicate_token_different_user(mock_db, mock_auth):
    mock_table, mock_put_item = mock_db
    
    # Return an existing device for a DIFFERENT user
    existing_device = {
        'device_id': 'd-999',
        'cognito_sub': 'other-sub',
        'push_token': 'ExponentPushToken[12345]',
        'is_active': True
    }
    mock_table.scan.return_value = {'Items': [existing_device]}
    mock_put_item.return_value = True
    
    event = {
        'httpMethod': 'POST',
        'body': json.dumps({'push_token': 'ExponentPushToken[12345]'})
    }
    
    response = device_handler.handler(event, {})
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['status'] == 'registered'
    
    # Should call put_item twice: once to deactivate old, once to create new
    assert mock_put_item.call_count == 2
    
    # Check first call (deactivate old)
    old_item = mock_put_item.call_args_list[0][0][0]
    assert old_item['device_id'] == 'd-999'
    assert old_item['is_active'] is False
    
    # Check second call (create new)
    new_item = mock_put_item.call_args_list[1][0][0]
    assert new_item['cognito_sub'] == 'user-sub-123'
    assert new_item['push_token'] == 'ExponentPushToken[12345]'

def test_remove_device_own(mock_db, mock_auth):
    mock_table, mock_put_item = mock_db
    
    mock_table.query.return_value = {'Items': [{
        'device_id': 'd-123',
        'cognito_sub': 'user-sub-123',
        'is_active': True
    }]}
    mock_put_item.return_value = True
    
    event = {
        'httpMethod': 'DELETE',
        'pathParameters': {'device_id': 'd-123'}
    }
    
    response = device_handler.handler(event, {})
    assert response['statusCode'] == 200
    
    saved_item = mock_put_item.call_args[0][0]
    assert saved_item['is_active'] is False

def test_remove_device_other_user_denied(mock_db, mock_auth):
    mock_table, mock_put_item = mock_db
    mock_role, _, _, _ = mock_auth
    mock_role.return_value = 'client'
    
    # Device belongs to someone else
    mock_table.query.return_value = {'Items': [{
        'device_id': 'd-123',
        'cognito_sub': 'other-sub',
        'is_active': True
    }]}
    
    event = {
        'httpMethod': 'DELETE',
        'pathParameters': {'device_id': 'd-123'}
    }
    
    response = device_handler.handler(event, {})
    assert response['statusCode'] == 403

def test_remove_device_admin_allowed(mock_db, mock_auth):
    mock_table, mock_put_item = mock_db
    mock_role, _, _, _ = mock_auth
    mock_role.return_value = 'admin' # Admin role!
    
    # Device belongs to someone else
    mock_table.query.return_value = {'Items': [{
        'device_id': 'd-123',
        'cognito_sub': 'other-sub',
        'is_active': True
    }]}
    mock_put_item.return_value = True
    
    event = {
        'httpMethod': 'DELETE',
        'pathParameters': {'device_id': 'd-123'}
    }
    
    response = device_handler.handler(event, {})
    assert response['statusCode'] == 200 # Allowed because admin
    
    saved_item = mock_put_item.call_args[0][0]
    assert saved_item['is_active'] is False
