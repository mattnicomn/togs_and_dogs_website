import pytest
import json
from unittest.mock import patch, MagicMock, ANY
from handlers.admin_handler import handler as admin_handler

# --- Fixtures & Mocks ---

@pytest.fixture
def mock_db():
    with patch('common.db.table') as mock_table:
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
    resp = admin_handler(event, None)
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
    """Non-DELETED records must be skipped (not purged) by the bulk-compatible API."""
    mock_record = {"PK": "REQ#1", "SK": "CLIENT#1", "status": "APPROVED"}
    
    event = create_event("Admin", {"action": "PURGE", "PK": "REQ#1", "SK": "CLIENT#1"})
    
    # Patch _resolve_admin_record to return the mock record with correct keys
    with patch('handlers.admin_handler._resolve_admin_record', return_value=(mock_record, "REQ#1", "CLIENT#1")):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        # Record was skipped (not purged) because status is APPROVED
        assert body["skipped"] >= 1
        assert body["success"] == 0
        # Verify the skip reason mentions the status
        assert any("APPROVED" in f.get("reason", "") for f in body.get("failures", []))
        # Table delete_item should NOT have been called
        mock_db["table"].delete_item.assert_not_called()

def test_purge_safety_allows_deleted_status(mock_db, mock_audit):
    """DELETED records should be purged successfully."""
    mock_record = {"PK": "REQ#1", "SK": "CLIENT#1", "status": "DELETED", "client_name": "Test"}
    
    event = create_event("Admin", {"action": "PURGE", "PK": "REQ#1", "SK": "CLIENT#1"})
    
    with patch('handlers.admin_handler._resolve_admin_record', return_value=(mock_record, "REQ#1", "CLIENT#1")):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        # Record was successfully purged
        assert body["success"] == 1
        assert body["skipped"] == 0
        # Table delete_item should have been called
        mock_db["table"].delete_item.assert_called_once_with(Key={'PK': 'REQ#1', 'SK': 'CLIENT#1'})
        # Verify audit log was written
        mock_audit.assert_called_with(ANY, 'PURGE', 'REQ#1', 'CLIENT#1',
                                      previous_status='DELETED', bulk_op_id=None)

# --- Malformed Record Cleanup Tests ---

def test_admin_can_trash_malformed_record(mock_db, mock_audit):
    """Malformed records (missing status) can be moved to Trash."""
    mock_record = {"PK": "REQ#MALFORMED", "SK": "CLIENT#1", "client_name": "Bad Data"}
    
    event = create_event("Admin", {"action": "DELETE", "PK": "REQ#MALFORMED", "SK": "CLIENT#1"})
    
    with patch('handlers.admin_handler._resolve_admin_record', return_value=(mock_record, "REQ#MALFORMED", "CLIENT#1")), \
         patch('handlers.admin_handler.update_status', return_value=True):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["success"] >= 1
        mock_audit.assert_called()

# --- Bulk Purge Safety Tests ---

def test_bulk_purge_filters_non_deleted(mock_db, mock_audit):
    """Bulk purge must skip non-DELETED records and only purge DELETED ones."""
    items = {
        "REQ#DELETED": ({"PK": "REQ#DELETED", "SK": "CLIENT#1", "status": "DELETED"}, "REQ#DELETED", "CLIENT#1"),
        "REQ#ACTIVE": ({"PK": "REQ#ACTIVE", "SK": "CLIENT#2", "status": "PENDING_REVIEW"}, "REQ#ACTIVE", "CLIENT#2")
    }
    
    def resolve_side_effect(pk, sk, *args, **kwargs):
        return items.get(pk, (None, pk, sk))
    
    event = create_event("Admin", {
        "action": "PURGE",
        "records": [
            {"PK": "REQ#DELETED", "SK": "CLIENT#1"},
            {"PK": "REQ#ACTIVE", "SK": "CLIENT#2"}
        ]
    })
    
    with patch('handlers.admin_handler._resolve_admin_record', side_effect=resolve_side_effect):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        # One purged, one skipped
        assert body["success"] == 1
        assert body["skipped"] == 1
        # Table delete_item called only for the DELETED record
        mock_db["table"].delete_item.assert_called_once_with(Key={'PK': 'REQ#DELETED', 'SK': 'CLIENT#1'})

# --- Release 6D: Active Record Delete Protection ---

def test_delete_rejects_active_assigned_record(mock_db, mock_audit):
    """DELETE action must reject records in ASSIGNED status."""
    mock_record = {"PK": "REQ#1", "SK": "CLIENT#1", "status": "ASSIGNED", "worker_id": "staff@test.com"}
    
    event = create_event("Admin", {"action": "DELETE", "PK": "REQ#1", "SK": "CLIENT#1"})
    
    with patch('handlers.admin_handler._resolve_admin_record', return_value=(mock_record, "REQ#1", "CLIENT#1")), \
         patch('handlers.admin_handler.update_status', return_value=True) as mock_update:
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        # Record should be skipped, not deleted
        assert body["skipped"] >= 1
        assert any("Cannot delete active record" in f.get("reason", "") for f in body.get("failures", []))
        # update_status should NOT have been called for this record
        mock_update.assert_not_called()

def test_delete_allows_cancelled_record(mock_db, mock_audit):
    """DELETE action should allow CANCELLED records to be moved to Trash."""
    mock_record = {"PK": "REQ#1", "SK": "CLIENT#1", "status": "CANCELLED"}
    
    event = create_event("Admin", {"action": "DELETE", "PK": "REQ#1", "SK": "CLIENT#1"})
    
    with patch('handlers.admin_handler._resolve_admin_record', return_value=(mock_record, "REQ#1", "CLIENT#1")), \
         patch('handlers.admin_handler.update_status', return_value=True):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["success"] >= 1
