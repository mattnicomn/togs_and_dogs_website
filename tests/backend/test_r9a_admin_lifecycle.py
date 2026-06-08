"""
Release 9A: Tests for Admin Booking Lifecycle and Test Data Controls.
"""
import pytest
import json
from unittest.mock import patch, MagicMock, ANY

import common.db
import handlers.admin_handler
import common.cascade
from common.auth import sanitize_booking_for_role

# --- Mock Data and Get Item Helper ---

MOCK_REQ = {
    "PK": "REQ#123",
    "SK": "CLIENT#1",
    "request_id": "123",
    "status": "ASSIGNED",
    "job_ids": ["active-job", "completed-job"],
    "client_id": "client-1",
    "worker_id": "staff@test.com"
}

MOCK_JOBS = {
    "JOB#active-job": {
        "PK": "JOB#active-job",
        "SK": "REQ#123",
        "status": "ASSIGNED",
        "google_event_id": "g-active"
    },
    "JOB#completed-job": {
        "PK": "JOB#completed-job",
        "SK": "REQ#123",
        "status": "COMPLETED",
        "visit_notes": "Preserve me!",
        "google_event_id": "g-completed"
    }
}

def mock_get_item(pk, sk):
    if pk == "REQ#123":
        return dict(MOCK_REQ)
    if pk in ["JOB#active-job", "JOB#completed-job"]:
        return dict(MOCK_JOBS[pk])
    return None

def mock_table_get_item(Key):
    pk = Key.get('PK')
    sk = Key.get('SK')
    item = mock_get_item(pk, sk)
    if item:
        return {"Item": item}
    return {}

# --- Monkeypatch DB Functions ---
common.db.get_item = mock_get_item
handlers.admin_handler.get_item = mock_get_item

# Create shared mock table and setup side effect
mock_table_obj = MagicMock()
mock_table_obj.get_item.side_effect = mock_table_get_item

common.db.table = mock_table_obj
handlers.admin_handler.table = mock_table_obj
common.cascade.table = mock_table_obj

# --- Event Helper ---

def create_event(role, body_dict=None, path="/admin/requests", method="POST"):
    claims = {"email": f"{role.lower()}@test.com"}
    if role.lower() == "admin":
        claims["cognito:groups"] = "Admin"
    elif role.lower() == "owner":
        claims["cognito:groups"] = "owner"
    elif role.lower() == "staff":
        claims["cognito:groups"] = "Staff"
    elif role.lower() == "client":
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

# --- Tests ---

@patch('handlers.admin_handler.log_action')
def test_rbac_new_actions(mock_log):
    """Verify owner/admin can perform new actions but staff/client cannot."""
    for action in ['MARK_TEST', 'UNMARK_TEST', 'UNARCHIVE']:
        body = {"action": action, "PK": "REQ#123", "SK": "CLIENT#1"}
        
        # Staff -> 403
        event = create_event("Staff", body)
        resp = handlers.admin_handler.handler(event, None)
        assert resp["statusCode"] == 403
        
        # Client -> 403
        event = create_event("Client", body)
        resp = handlers.admin_handler.handler(event, None)
        assert resp["statusCode"] == 403
        
        # Admin -> Allowed
        event = create_event("Admin", body)
        resp = handlers.admin_handler.handler(event, None)
        assert resp["statusCode"] == 200

@patch('handlers.admin_handler.log_action')
@patch('common.db.update_status', return_value=True)
def test_archive_parent_cascades_active_skips_completed(mock_update_status, mock_log):
    """Archiving parent cascades status to active child jobs but preserves completed ones."""
    # Reset mock table calls
    mock_table_obj.reset_mock()
    
    event = create_event("Admin", {
        "action": "ARCHIVE",
        "PK": "REQ#123",
        "SK": "CLIENT#1",
        "archive_reason": "Cleanup test"
    })
    
    resp = handlers.admin_handler.handler(event, None)
    assert resp["statusCode"] == 200
    
    # Verify parent status update has archive reason
    mock_update_status.assert_called_once()
    args, kwargs = mock_update_status.call_args
    assert args[2] == "ARCHIVED"
    assert kwargs["extra_attrs"]["archive_reason"] == "Cleanup test"
    assert "archived_at" in kwargs["extra_attrs"]
    assert kwargs["extra_attrs"]["archived_by"] == "admin@test.com"

    # Verify child job updates inside common.cascade
    update_calls = mock_table_obj.update_item.call_args_list
    
    calls_dict = {}
    for call in update_calls:
        pk = call[1]["Key"]["PK"]
        calls_dict.setdefault(pk, []).append(call[1])
    
    # Active job: status updated to ARCHIVED in one of the updates
    active_updates = calls_dict["JOB#active-job"]
    assert any("status" in u.get("ExpressionAttributeNames", {}).values() and u["ExpressionAttributeValues"][":s"] == "ARCHIVED" for u in active_updates)
    
    # Completed job: status NOT updated to ARCHIVED (preserves COMPLETED status)
    completed_updates = calls_dict["JOB#completed-job"]
    assert all("ExpressionAttributeNames" not in u or "#stat" not in u["ExpressionAttributeNames"] for u in completed_updates)

@patch('handlers.admin_handler.log_action')
def test_unarchive_restores_pending_preserves_completed(mock_log):
    """Unarchiving restores status to ASSIGNED/APPROVED and preserves completed child jobs."""
    mock_table_obj.reset_mock()
    
    # Modify MOCK_REQ status to ARCHIVED for this test
    local_req = dict(MOCK_REQ)
    local_req["status"] = "ARCHIVED"
    
    def local_get(pk, sk):
        if pk == "REQ#123":
            return local_req
        return mock_get_item(pk, sk)

    event = create_event("Admin", {
        "action": "UNARCHIVE",
        "PK": "REQ#123",
        "SK": "CLIENT#1"
    })
    
    with patch('handlers.admin_handler.get_item', side_effect=local_get), \
         patch('common.db.get_item', side_effect=local_get):
        resp = handlers.admin_handler.handler(event, None)
        assert resp["statusCode"] == 200
        
        # Verify parent request update expression has REMOVE for archive metadata
        update_calls = mock_table_obj.update_item.call_args_list
        parent_call = update_calls[0][1]
        assert parent_call["Key"]["PK"] == "REQ#123"
        assert "REMOVE archive_reason, archived_at, archived_by" in parent_call["UpdateExpression"]
        assert parent_call["ExpressionAttributeValues"][":s"] == "ASSIGNED"
        
        # Verify child jobs cascaded inside common.cascade
        child_calls = {}
        for call in update_calls[1:]:
            pk = call[1]["Key"]["PK"]
            child_calls.setdefault(pk, []).append(call[1])
        
        # Active job gets restored to ASSIGNED
        active_updates = child_calls["JOB#active-job"]
        assert any(u.get("ExpressionAttributeValues", {}).get(":s") == "ASSIGNED" for u in active_updates)
        
        # Completed job status update is skipped
        completed_updates = child_calls.get("JOB#completed-job", [])
        assert all("ExpressionAttributeNames" not in u or "#stat" not in u["ExpressionAttributeNames"] for u in completed_updates)

@patch('handlers.admin_handler.log_action')
def test_mark_and_unmark_test_booking(mock_log):
    """Marking and unmarking as test booking sets is_test_booking and cascades to child jobs."""
    mock_table_obj.reset_mock()
    
    # --- MARK TEST ---
    event = create_event("Admin", {
        "action": "MARK_TEST",
        "PK": "REQ#123",
        "SK": "CLIENT#1"
    })
    
    resp = handlers.admin_handler.handler(event, None)
    assert resp["statusCode"] == 200
    
    parent_call = mock_table_obj.update_item.call_args_list[0][1]
    assert parent_call["Key"]["PK"] == "REQ#123"
    assert parent_call["ExpressionAttributeValues"][":itb"] is True
    
    child_calls = mock_table_obj.update_item.call_args_list[1:]
    assert any(c[1]["ExpressionAttributeValues"].get(":itb") is True for c in child_calls)
    
    # Reset mocks for UNMARK
    mock_table_obj.reset_mock()
    
    # --- UNMARK TEST ---
    event = create_event("Admin", {
        "action": "UNMARK_TEST",
        "PK": "REQ#123",
        "SK": "CLIENT#1"
    })
    
    resp = handlers.admin_handler.handler(event, None)
    assert resp["statusCode"] == 200
    
    parent_call = mock_table_obj.update_item.call_args_list[0][1]
    assert parent_call["Key"]["PK"] == "REQ#123"
    assert parent_call["ExpressionAttributeValues"][":itb"] is False
    
    child_calls = mock_table_obj.update_item.call_args_list[1:]
    assert any(c[1]["ExpressionAttributeValues"].get(":itb") is False for c in child_calls)

@patch('handlers.admin_handler.log_action')
@patch('common.db.update_status', return_value=True)
@patch('handlers.admin_handler.delete_event')
def test_google_calendar_preserves_completed_events(mock_delete_event, mock_update_status, mock_log):
    """Archiving does not delete calendar events for completed child jobs."""
    mock_table_obj.reset_mock()
    
    event = create_event("Admin", {
        "action": "ARCHIVE",
        "PK": "REQ#123",
        "SK": "CLIENT#1"
    })
    
    resp = handlers.admin_handler.handler(event, None)
    assert resp["statusCode"] == 200
    
    # Verify calendar event deletion was ONLY called for the active job, not the completed one
    mock_delete_event.assert_called_once_with("g-active", "REQ#123")

def test_client_role_redacts_lifecycle_metadata():
    """Verify is_test_booking, archive_reason, archived_at, and archived_by are redacted for clients."""
    enriched_booking = {
        "PK": "REQ#req-123",
        "SK": "CLIENT#client-123",
        "status": "ARCHIVED",
        "is_test_booking": True,
        "archive_reason": "Secret test",
        "archived_at": "2026-06-07T12:00:00",
        "archived_by": "admin@test.com"
    }
    sanitized = sanitize_booking_for_role(enriched_booking, "client")
    assert sanitized.get("is_test_booking") is None
    assert sanitized.get("archive_reason") is None
    assert sanitized.get("archived_at") is None
    assert sanitized.get("archived_by") is None
