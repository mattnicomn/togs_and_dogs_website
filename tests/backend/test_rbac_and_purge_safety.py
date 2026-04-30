import pytest
import json
from unittest.mock import patch, MagicMock, ANY
from handlers.admin_handler import handler as admin_handler

# --- Fixtures & Mocks ---

@pytest.fixture
def mock_db():
    with patch('common.db.table') as mock_table:
        # Mock get_item specifically as it's used via common.db.get_item or imported directly
        with patch('common.db.get_item') as mock_get:
            yield {"table": mock_table, "get_item": mock_get}

@pytest.fixture
def mock_audit():
    with patch('handlers.admin_handler.log_action') as mock_log:
        yield mock_log

# --- Events ---

def create_event(role, body_dict=None, path="/admin/requests", method="POST"):
    claims = {"email": f"{role.lower()}@test.com"}
    if role == "Admin":
        claims["cognito:groups"] = "Admin"
    elif role == "Owner":
        claims["cognito:groups"] = "owner"
    elif role == "Staff":
        claims["cognito:groups"] = "Staff"
    elif role == "Client":
        claims["cognito:groups"] = "Client"
    
    return {
        "requestContext": {
            "authorizer": {
                "claims": claims
            }
        },
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body_dict or {})
    }

# --- RBAC Tests ---

def test_admin_access_allowed(mock_db, mock_audit):
    event = create_event("Admin", {"action": "LIST"})
    # Admin LIST calls query_by_status or similar, but for simplicity we just check reachability
    resp = admin_handler(event, None)
    # The handler might return 400 for empty list or other things, but should NOT return 403
    assert resp["statusCode"] != 403

def test_staff_access_denied_to_admin_requests(mock_db, mock_audit):
    event = create_event("Staff", {"action": "DELETE", "PK": "REQ#1", "SK": "CLIENT#1"})
    resp = admin_handler(event, None)
    assert resp["statusCode"] == 403
    assert "Forbidden" in resp["body"]

def test_client_access_denied_to_admin_requests(mock_db, mock_audit):
    event = create_event("Client", {"action": "DELETE", "PK": "REQ#1", "SK": "CLIENT#1"})
    resp = admin_handler(event, None)
    assert resp["statusCode"] == 403
    assert "Forbidden" in resp["body"]

# --- Purge Safety Tests ---

def test_purge_safety_requires_deleted_status(mock_db, mock_audit):
    # Setup: Record is NOT in DELETED status
    mock_db["get_item"].return_value = {"PK": "REQ#1", "SK": "CLIENT#1", "status": "APPROVED"}
    
    event = create_event("Admin", {"action": "PURGE", "PK": "REQ#1", "SK": "CLIENT#1"})
    
    # We must patch get_item where it's imported in admin_handler
    with patch('handlers.admin_handler.get_item', return_value=mock_db["get_item"].return_value):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 400
        assert "not DELETED" in resp["body"]
        # Verify rejection was logged
        mock_audit.assert_called_with(ANY, 'PURGE_REJECTED', 'REQ#1', 'CLIENT#1', 
                                    previous_status='APPROVED', success=False, failure_reason='Status is APPROVED', bulk_op_id=None)

def test_purge_safety_allows_deleted_status(mock_db, mock_audit):
    # Setup: Record IS in DELETED status
    mock_db["get_item"].return_value = {"PK": "REQ#1", "SK": "CLIENT#1", "status": "DELETED", "client_name": "Test"}
    
    event = create_event("Admin", {"action": "PURGE", "PK": "REQ#1", "SK": "CLIENT#1"})
    
    with patch('handlers.admin_handler.get_item', return_value=mock_db["get_item"].return_value):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        # Verify success was logged
        mock_audit.assert_called_with(ANY, 'PURGE', 'REQ#1', 'CLIENT#1', 
                                    previous_status='DELETED', bulk_op_id=None, metadata={'client_name': 'Test', 'pet_names': None})

# --- Malformed Record Cleanup Tests ---

def test_admin_can_trash_malformed_record(mock_db, mock_audit):
    # Setup: Malformed record (missing status)
    mock_db["get_item"].return_value = {"PK": "REQ#MALFORMED", "SK": "CLIENT#1", "client_name": "Bad Data"}
    
    event = create_event("Admin", {"action": "DELETE", "PK": "REQ#MALFORMED", "SK": "CLIENT#1"})
    
    with patch('handlers.admin_handler.get_item', return_value=mock_db["get_item"].return_value), \
         patch('handlers.admin_handler.update_status', return_value=True):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        # Verify audit log
        mock_audit.assert_called()

# --- Bulk Purge Safety Tests ---

def test_bulk_purge_filters_non_deleted(mock_db, mock_audit):
    # Setup: Mix of DELETED and non-DELETED
    items = {
        "REQ#DELETED": {"PK": "REQ#DELETED", "SK": "CLIENT#1", "status": "DELETED"},
        "REQ#ACTIVE": {"PK": "REQ#ACTIVE", "SK": "CLIENT#2", "status": "PENDING_REVIEW"}
    }
    
    def side_effect(pk, sk):
        return items.get(pk)
    
    event = create_event("Admin", {
        "action": "PURGE",
        "records": [
            {"PK": "REQ#DELETED", "SK": "CLIENT#1"},
            {"PK": "REQ#ACTIVE", "SK": "CLIENT#2"}
        ]
    })
    
    with patch('handlers.admin_handler.get_item', side_effect=side_effect):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["deleted_count"] == 1
        assert body["skipped_count"] == 1
        # Verify both actions logged (one PURGE, one PURGE_REJECTED)
        assert mock_audit.call_count == 2
