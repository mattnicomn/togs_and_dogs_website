import pytest
import json
from unittest.mock import patch, MagicMock
from handlers.admin_handler import handler as admin_handler
from botocore.exceptions import ClientError

def create_event(role, path, method, body_dict=None, path_params=None):
    claims = {"email": f"{role.lower()}@test.com", "sub": "admin-sub-123"}
    if role in ["Admin", "owner"]:
        claims["cognito:groups"] = role
    
    return {
        "requestContext": {
            "authorizer": {
                "claims": claims
            }
        },
        "httpMethod": method,
        "path": path,
        "pathParameters": path_params or {},
        "body": json.dumps(body_dict or {})
    }

@pytest.fixture
def mock_cognito():
    with patch('boto3.client') as mock_boto:
        mock_client = MagicMock()
        # Mock exceptions attribute on Cognito client
        mock_exceptions = MagicMock()
        mock_exceptions.UserNotFoundException = ClientError
        mock_client.exceptions = mock_exceptions
        mock_boto.return_value = mock_client
        yield mock_client

@pytest.fixture
def mock_db():
    with patch('common.db.table') as mock_table:
        yield mock_table

@pytest.fixture(autouse=True)
def mock_entitlement():
    with patch('common.entitlement._get_entitlement_safely') as mock_get:
        mock_get.return_value = MagicMock(is_access_allowed=True, is_blocked=False)
        yield mock_get

def test_unlink_staff_sets_sentinel(mock_db, mock_cognito):
    """PATCH /admin/staff/{id} with unlink action sets 'unlinked' sentinels."""
    staff_id = "staff_test_123"
    mock_db.get_item.return_value = {
        "Item": {
            "PK": "COMPANY#comp_123",
            "SK": f"STAFF#{staff_id}",
            "staff_id": staff_id,
            "email": "staff@test.com",
            "cognito_sub": "original-sub",
            "cognito_username": "original-username"
        }
    }
    
    event = create_event("Admin", f"/admin/staff/{staff_id}", "PATCH", {"action": "unlink"}, {"staff_id": staff_id})
    resp = admin_handler(event, None)
    
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["cognito_sub"] is None
    
    # Verify put_item was called with the unlinked sentinels saved in DynamoDB
    mock_db.put_item.assert_called_once()
    saved_item = mock_db.put_item.call_args[1]["Item"]
    assert saved_item["cognito_sub"] == "unlinked"
    assert saved_item["cognito_status"] == "unlinked"
    assert "cognito_username" not in saved_item

def test_get_staff_skips_unlinked_merge(mock_db, mock_cognito):
    """GET /admin/staff skips merging matching emails if staff is unlinked."""
    mock_db.query.return_value = {
        "Items": [
            {
                "PK": "COMPANY#comp_123",
                "SK": "STAFF#staff_unlinked",
                "staff_id": "staff_unlinked",
                "email": "mattnicomn10@yahoo.com",
                "cognito_sub": "unlinked",
                "cognito_status": "unlinked"
            }
        ]
    }
    
    mock_cognito.list_groups.return_value = {"Groups": [{"GroupName": "Staff"}]}
    mock_cognito.list_users_in_group.return_value = {
        "Users": [
            {
                "Username": "mattnicomn10_user",
                "UserStatus": "CONFIRMED",
                "Enabled": True,
                "Attributes": [
                    {"Name": "email", "Value": "mattnicomn10@yahoo.com"},
                    {"Name": "sub", "Value": "cognito-uuid-123"}
                ]
            }
        ]
    }
    
    event = create_event("Admin", "/admin/staff", "GET")
    resp = admin_handler(event, None)
    
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    staff_list = body["staff"]
    assert len(staff_list) == 1
    assert staff_list[0]["cognito_sub"] is None
    assert staff_list[0]["cognito_status"] == "unlinked"

def test_security_action_blocks_unlinked(mock_db, mock_cognito):
    """POST /admin/staff/{id}/set-temp-password blocks action if unlinked."""
    staff_id = "staff_unlinked"
    mock_db.get_item.return_value = {
        "Item": {
            "PK": "COMPANY#comp_123",
            "SK": f"STAFF#{staff_id}",
            "staff_id": staff_id,
            "email": "mattnicomn10@yahoo.com",
            "cognito_sub": "unlinked",
            "cognito_status": "unlinked"
        }
    }
    
    event = create_event("Admin", f"/admin/staff/{staff_id}/set-temp-password", "POST", {"password": "NewPassword123!"}, {"staff_id": staff_id})
    resp = admin_handler(event, None)
    
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert "Profile is not linked to a Cognito user" in body["error"]

def test_security_action_resolves_exact_username_and_falls_back(mock_db, mock_cognito):
    """Security actions pre-fetch Cognito Username and search by email on UserNotFoundException."""
    staff_id = "staff_linked"
    mock_db.get_item.return_value = {
        "Item": {
            "PK": "COMPANY#comp_123",
            "SK": f"STAFF#{staff_id}",
            "staff_id": staff_id,
            "email": "mattnicomn10@yahoo.com",
            "cognito_sub": "cognito-sub-uuid"
        }
    }
    
    # 1. First scenario: admin_get_user succeeds immediately
    mock_cognito.admin_get_user.return_value = {"Username": "mattnicomn10_exact_user"}
    
    event = create_event("Admin", f"/admin/staff/{staff_id}/set-temp-password", "POST", {"password": "NewPassword123!"}, {"staff_id": staff_id})
    resp = admin_handler(event, None)
    
    assert resp["statusCode"] == 200
    mock_cognito.admin_set_user_password.assert_called_with(
        UserPoolId=None,
        Username="mattnicomn10_exact_user",
        Password="NewPassword123!",
        Permanent=False
    )
    
    # Reset call counts and set side effect for scenario 2
    mock_cognito.admin_set_user_password.reset_mock()
    mock_cognito.admin_get_user.side_effect = ClientError(
        {"Error": {"Code": "UserNotFoundException", "Message": "User not found"}},
        "admin_get_user"
    )
    mock_cognito.list_users.return_value = {
        "Users": [{"Username": "mattnicomn10_fallback_user"}]
    }
    
    resp_fallback = admin_handler(event, None)
    assert resp_fallback["statusCode"] == 200
    mock_cognito.admin_set_user_password.assert_called_with(
        UserPoolId=None,
        Username="mattnicomn10_fallback_user",
        Password="NewPassword123!",
        Permanent=False
    )
