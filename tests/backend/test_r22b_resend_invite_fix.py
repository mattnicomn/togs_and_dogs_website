import pytest
import json
from unittest.mock import patch, MagicMock
from handlers.admin_handler import handler as admin_handler
from botocore.exceptions import ClientError

def create_event(role, path, method, body_dict=None, path_params=None):
    claims = {"email": f"{role.lower()}@test.com", "sub": "admin-sub-123"}
    if role in ["Admin", "owner"]:
        claims["cognito:groups"] = role
    claims["custom:company_id"] = "tog_and_dogs"
    
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
        mock_exceptions = MagicMock()
        mock_exceptions.UserNotFoundException = ClientError
        mock_client.exceptions = mock_exceptions
        mock_boto.return_value = mock_client
        yield mock_client

@pytest.fixture
def mock_db():
    with patch('common.db.table') as mock_table:
        yield mock_table

@patch('handlers.admin_handler.notify_event')
def test_resend_invite_no_unbound_local_error(mock_notify, mock_db, mock_cognito):
    """POST /admin/staff/{id}/resend-invite successfully executes and calls notify_event."""
    staff_id = "staff_test_123"
    
    # Mock DynamoDB side_effect to handle both profile and metadata queries
    def get_item_side_effect(Key, **kwargs):
        pk = Key.get("PK")
        sk = Key.get("SK")
        if pk == "COMPANY#tog_and_dogs" and sk.startswith("STAFF#"):
            return {
                "Item": {
                    "PK": "COMPANY#tog_and_dogs",
                    "SK": f"STAFF#{staff_id}",
                    "staff_id": staff_id,
                    "display_name": "Test Sitter",
                    "email": "sitter@test.com",
                    "cognito_sub": "sitter-sub-abc"
                }
            }
        elif pk == "COMPANY#tog_and_dogs" and sk == "METADATA#tog_and_dogs":
            return {
                "Item": {
                    "PK": "COMPANY#tog_and_dogs",
                    "SK": "METADATA#tog_and_dogs",
                    "company_id": "tog_and_dogs",
                    "subscription_status": "active",
                    "subscription_tier": "pro",
                    "is_active": True
                }
            }
        return {}

    mock_db.get_item.side_effect = get_item_side_effect
    
    # Mock Cognito admin_get_user
    mock_cognito.admin_get_user.return_value = {
        "Username": "sitter@test.com",
        "UserAttributes": [
            {"Name": "email", "Value": "sitter@test.com"}
        ]
    }
    
    # Mock Cognito set user password (done during resend invite)
    mock_cognito.admin_set_user_password.return_value = {}
    
    # Mock notify_event success return
    mock_notify.return_value = {"success": True}
    
    event = create_event(
        role="Admin",
        path=f"/admin/staff/{staff_id}/resend-invite",
        method="POST",
        path_params={"staff_id": staff_id}
    )
    
    resp = admin_handler(event, None)
    
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["message"] == "Invitation resent successfully with new temporary password."
    
    # Verify mock_notify was called with correct arguments
    mock_notify.assert_called_once()
    args, kwargs = mock_notify.call_args
    assert kwargs["event_type"] == "WELCOME_INVITE_STAFF"
    assert kwargs["context"]["email"] == "sitter@test.com"
    assert "temp_password" in kwargs["context"]
