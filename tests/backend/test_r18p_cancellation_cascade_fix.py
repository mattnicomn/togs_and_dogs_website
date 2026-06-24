"""
Release 18P: Tests for defensive calendar cancellation cascade fix.
"""
import sys
import os
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers.cancellation_handler import handle_admin_decision

# --- Mock Data and Functions ---

def mock_get_effective_role(event):
    return 'admin'

# Define a flexible mock generator for DynamoDB items
class DynamoDBMock:
    def __init__(self, request_item, job_items=None):
        self.request_item = request_item
        self.job_items = job_items or {}

    def get_item(self, pk, sk):
        if pk.startswith("REQ#"):
            return self.request_item
        if pk.startswith("JOB#"):
            job_id = pk.replace("JOB#", "")
            return self.job_items.get(job_id)
        return None

# --- Scenarios ---

@patch('handlers.cancellation_handler.table')
@patch('common.google_calendar.delete_event_detailed')
@patch('handlers.cancellation_handler.notify_event')
@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.cascade.cascade_status_to_job')
@patch('handlers.cancellation_handler.log_action')
@patch('handlers.cancellation_handler.get_item')
def test_18p_parent_only(mock_get_item, mock_log, mock_cascade, mock_role, mock_notify, mock_delete_detailed, mock_table):
    """Scenario 1: Parent has google_event_id, child job is missing it -> event deleted."""
    request_item = {
        "PK": "REQ#req-parent-only",
        "SK": "CLIENT#client-123",
        "request_id": "req-parent-only",
        "client_id": "client-123",
        "company_id": "tog_and_dogs",
        "google_event_id": "parent-event-id",
        "job_ids": ["job-1"]
    }
    job_items = {
        "job-1": {
            "PK": "JOB#job-1",
            "SK": "REQ#req-parent-only"
            # google_event_id is missing
        }
    }
    db_mock = DynamoDBMock(request_item, job_items)
    mock_get_item.side_effect = db_mock.get_item
    mock_delete_detailed.return_value = (True, False, None) # success, already_gone, err_msg

    body = {
        "request_id": "req-parent-only",
        "client_id": "client-123",
        "decision": "APPROVE"
    }

    res = handle_admin_decision(body, {})
    assert res["statusCode"] == 200
    
    # Assert delete_event_detailed was called for parent event id
    mock_delete_detailed.assert_called_once_with("parent-event-id", "req-parent-only")
    
    # Assert database REMOVE update is triggered
    mock_table.update_item.assert_any_call(
        Key={"PK": "REQ#req-parent-only", "SK": "CLIENT#client-123"},
        UpdateExpression="REMOVE google_event_id"
    )

@patch('handlers.cancellation_handler.table')
@patch('common.google_calendar.delete_event_detailed')
@patch('handlers.cancellation_handler.notify_event')
@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.cascade.cascade_status_to_job')
@patch('handlers.cancellation_handler.log_action')
@patch('handlers.cancellation_handler.get_item')
def test_18p_child_only(mock_get_item, mock_log, mock_cascade, mock_role, mock_notify, mock_delete_detailed, mock_table):
    """Scenario 2: Child job has google_event_id, parent is missing it -> event deleted."""
    request_item = {
        "PK": "REQ#req-child-only",
        "SK": "CLIENT#client-123",
        "request_id": "req-child-only",
        "client_id": "client-123",
        "company_id": "tog_and_dogs",
        "job_ids": ["job-1"]
    }
    job_items = {
        "job-1": {
            "PK": "JOB#job-1",
            "SK": "REQ#req-child-only",
            "google_event_id": "child-event-id"
        }
    }
    db_mock = DynamoDBMock(request_item, job_items)
    mock_get_item.side_effect = db_mock.get_item
    mock_delete_detailed.return_value = (True, False, None)

    body = {
        "request_id": "req-child-only",
        "client_id": "client-123",
        "decision": "APPROVE"
    }

    res = handle_admin_decision(body, {})
    assert res["statusCode"] == 200
    
    mock_delete_detailed.assert_called_once_with("child-event-id", "req-child-only")
    mock_table.update_item.assert_any_call(
        Key={"PK": "JOB#job-1", "SK": "REQ#req-child-only"},
        UpdateExpression="REMOVE google_event_id"
    )

@patch('handlers.cancellation_handler.table')
@patch('common.google_calendar.delete_event_detailed')
@patch('handlers.cancellation_handler.notify_event')
@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.cascade.cascade_status_to_job')
@patch('handlers.cancellation_handler.log_action')
@patch('handlers.cancellation_handler.get_item')
def test_18p_duplicate_event_ids(mock_get_item, mock_log, mock_cascade, mock_role, mock_notify, mock_delete_detailed, mock_table):
    """Scenario 3: Both parent and child have the same event ID -> event deleted exactly once."""
    request_item = {
        "PK": "REQ#req-dup",
        "SK": "CLIENT#client-123",
        "request_id": "req-dup",
        "client_id": "client-123",
        "company_id": "tog_and_dogs",
        "google_event_id": "shared-event-id",
        "job_ids": ["job-1"]
    }
    job_items = {
        "job-1": {
            "PK": "JOB#job-1",
            "SK": "REQ#req-dup",
            "google_event_id": "shared-event-id"
        }
    }
    db_mock = DynamoDBMock(request_item, job_items)
    mock_get_item.side_effect = db_mock.get_item
    mock_delete_detailed.return_value = (True, False, None)

    body = {
        "request_id": "req-dup",
        "client_id": "client-123",
        "decision": "APPROVE"
    }

    res = handle_admin_decision(body, {})
    assert res["statusCode"] == 200
    
    # Assert it was only called once (deduplicated)
    mock_delete_detailed.assert_called_once_with("shared-event-id", "req-dup")
    
    # Updates should be sent for both records
    mock_table.update_item.assert_any_call(
        Key={"PK": "REQ#req-dup", "SK": "CLIENT#client-123"},
        UpdateExpression="REMOVE google_event_id"
    )
    mock_table.update_item.assert_any_call(
        Key={"PK": "JOB#job-1", "SK": "REQ#req-dup"},
        UpdateExpression="REMOVE google_event_id"
    )

@patch('handlers.cancellation_handler.table')
@patch('common.google_calendar.delete_event_detailed')
@patch('handlers.cancellation_handler.notify_event')
@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.cascade.cascade_status_to_job')
@patch('handlers.cancellation_handler.log_action')
@patch('handlers.cancellation_handler.get_item')
def test_18p_different_event_ids(mock_get_item, mock_log, mock_cascade, mock_role, mock_notify, mock_delete_detailed, mock_table):
    """Scenario 4: Parent and child have different event IDs -> both events deleted."""
    request_item = {
        "PK": "REQ#req-diff",
        "SK": "CLIENT#client-123",
        "request_id": "req-diff",
        "client_id": "client-123",
        "company_id": "tog_and_dogs",
        "google_event_id": "parent-event-id",
        "job_ids": ["job-1"]
    }
    job_items = {
        "job-1": {
            "PK": "JOB#job-1",
            "SK": "REQ#req-diff",
            "google_event_id": "child-event-id"
        }
    }
    db_mock = DynamoDBMock(request_item, job_items)
    mock_get_item.side_effect = db_mock.get_item
    mock_delete_detailed.return_value = (True, False, None)

    body = {
        "request_id": "req-diff",
        "client_id": "client-123",
        "decision": "APPROVE"
    }

    res = handle_admin_decision(body, {})
    assert res["statusCode"] == 200
    
    assert mock_delete_detailed.call_count == 2
    mock_delete_detailed.assert_any_call("parent-event-id", "req-diff")
    mock_delete_detailed.assert_any_call("child-event-id", "req-diff")
    
    mock_table.update_item.assert_any_call(
        Key={"PK": "REQ#req-diff", "SK": "CLIENT#client-123"},
        UpdateExpression="REMOVE google_event_id"
    )
    mock_table.update_item.assert_any_call(
        Key={"PK": "JOB#job-1", "SK": "REQ#req-diff"},
        UpdateExpression="REMOVE google_event_id"
    )

@patch('handlers.cancellation_handler.table')
@patch('common.google_calendar.delete_event_detailed')
@patch('handlers.cancellation_handler.notify_event')
@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.cascade.cascade_status_to_job')
@patch('handlers.cancellation_handler.log_action')
@patch('handlers.cancellation_handler.get_item')
def test_18p_already_deleted(mock_get_item, mock_log, mock_cascade, mock_role, mock_notify, mock_delete_detailed, mock_table):
    """Scenario 5: Event already deleted (404/410) -> tolerated, database event ID removed, cancellation succeeds."""
    request_item = {
        "PK": "REQ#req-404",
        "SK": "CLIENT#client-123",
        "request_id": "req-404",
        "client_id": "client-123",
        "company_id": "tog_and_dogs",
        "google_event_id": "missing-event-id",
        "job_ids": []
    }
    db_mock = DynamoDBMock(request_item)
    mock_get_item.side_effect = db_mock.get_item
    
    # GCal API returns already_gone=True
    mock_delete_detailed.return_value = (True, True, None)

    body = {
        "request_id": "req-404",
        "client_id": "client-123",
        "decision": "APPROVE"
    }

    res = handle_admin_decision(body, {})
    assert res["statusCode"] == 200
    
    mock_delete_detailed.assert_called_once_with("missing-event-id", "req-404")
    
    # Even if 404, we clean it up from database
    mock_table.update_item.assert_any_call(
        Key={"PK": "REQ#req-404", "SK": "CLIENT#client-123"},
        UpdateExpression="REMOVE google_event_id"
    )

@patch('handlers.cancellation_handler.table')
@patch('common.google_calendar.delete_event_detailed')
@patch('handlers.cancellation_handler.notify_event')
@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.cascade.cascade_status_to_job')
@patch('handlers.cancellation_handler.log_action')
@patch('handlers.cancellation_handler.get_item')
def test_18p_generic_api_error(mock_get_item, mock_log, mock_cascade, mock_role, mock_notify, mock_delete_detailed, mock_table):
    """Scenario 6: Generic Calendar API error -> tolerated, logged as warning, status transitions complete."""
    request_item = {
        "PK": "REQ#req-error",
        "SK": "CLIENT#client-123",
        "request_id": "req-error",
        "client_id": "client-123",
        "company_id": "tog_and_dogs",
        "google_event_id": "erroneous-event-id",
        "job_ids": []
    }
    db_mock = DynamoDBMock(request_item)
    mock_get_item.side_effect = db_mock.get_item
    
    # GCal API returns success=False
    mock_delete_detailed.return_value = (False, False, "API connection timeout")

    body = {
        "request_id": "req-error",
        "client_id": "client-123",
        "decision": "APPROVE"
    }

    res = handle_admin_decision(body, {})
    
    # Deletion failure must NOT block overall cancellation workflow success
    assert res["statusCode"] == 200
    mock_delete_detailed.assert_called_once_with("erroneous-event-id", "req-error")
    
    # Check that it did NOT remove the event ID from DB because it was a failure
    # (So it only updated the status and audit_log, not REMOVE google_event_id)
    # The first update is to set status and audit_log.
    # Let's verify that a REMOVE update expression was not executed.
    for call in mock_table.update_item.call_args_list:
        args, kwargs = call
        if "UpdateExpression" in kwargs:
            assert "REMOVE google_event_id" not in kwargs["UpdateExpression"]

@patch('handlers.cancellation_handler.table')
@patch('common.google_calendar.delete_event_detailed')
@patch('handlers.cancellation_handler.notify_event')
@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.cascade.cascade_status_to_job')
@patch('handlers.cancellation_handler.log_action')
@patch('handlers.cancellation_handler.get_item')
def test_18p_no_event_ids(mock_get_item, mock_log, mock_cascade, mock_role, mock_notify, mock_delete_detailed, mock_table):
    """Scenario 7: Neither parent nor child has event ID -> completes with CALENDAR_CLEANUP_NONE."""
    request_item = {
        "PK": "REQ#req-none",
        "SK": "CLIENT#client-123",
        "request_id": "req-none",
        "client_id": "client-123",
        "company_id": "tog_and_dogs",
        "job_ids": ["job-1"]
    }
    job_items = {
        "job-1": {
            "PK": "JOB#job-1",
            "SK": "REQ#req-none"
        }
    }
    db_mock = DynamoDBMock(request_item, job_items)
    mock_get_item.side_effect = db_mock.get_item

    body = {
        "request_id": "req-none",
        "client_id": "client-123",
        "decision": "APPROVE"
    }

    res = handle_admin_decision(body, {})
    assert res["statusCode"] == 200
    mock_delete_detailed.assert_not_called()

@patch('handlers.cancellation_handler.table')
@patch('common.google_calendar.delete_event_detailed')
@patch('handlers.cancellation_handler.notify_event')
@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.cascade.cascade_status_to_job')
@patch('handlers.cancellation_handler.log_action')
@patch('handlers.cancellation_handler.get_item')
def test_18p_cancellation_transitions_and_cascade(mock_get_item, mock_log, mock_cascade, mock_role, mock_notify, mock_delete_detailed, mock_table):
    """Scenario 8: Status cascades are preserved (parent request and child jobs transition to CANCELLED)."""
    request_item = {
        "PK": "REQ#req-cascade",
        "SK": "CLIENT#client-123",
        "request_id": "req-cascade",
        "client_id": "client-123",
        "company_id": "tog_and_dogs",
        "status": "CANCELLATION_REQUESTED",
        "job_ids": ["job-1"]
    }
    job_items = {
        "job-1": {
            "PK": "JOB#job-1",
            "SK": "REQ#req-cascade",
            "status": "ASSIGNED"
        }
    }
    db_mock = DynamoDBMock(request_item, job_items)
    mock_get_item.side_effect = db_mock.get_item

    body = {
        "request_id": "req-cascade",
        "client_id": "client-123",
        "decision": "APPROVE"
    }

    res = handle_admin_decision(body, {})
    assert res["statusCode"] == 200
    
    # Assert database update is called for the request record to set status to CANCELLED
    update_called = False
    for call in mock_table.update_item.call_args_list:
        args, kwargs = call
        if kwargs.get('Key') == {'PK': 'REQ#req-cascade', 'SK': 'CLIENT#client-123'}:
            expr_vals = kwargs.get('ExpressionAttributeValues', {})
            if expr_vals.get(':s') == 'CANCELLED':
                update_called = True
                break
    assert update_called, "Should update the request record status to CANCELLED in DynamoDB"
    
    # Assert cascade to job is called
    mock_cascade.assert_called_once()
    args, kwargs = mock_cascade.call_args
    # First argument is the request item, second is the new status
    assert args[1] == "CANCELLED"

@patch('handlers.cancellation_handler.table')
@patch('common.google_calendar.delete_event_detailed')
@patch('handlers.cancellation_handler.notify_event')
@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.cascade.cascade_status_to_job')
@patch('handlers.cancellation_handler.log_action')
@patch('handlers.cancellation_handler.get_item')
def test_18p_notification_behavior(mock_get_item, mock_log, mock_cascade, mock_role, mock_notify, mock_delete_detailed, mock_table):
    """Scenario 9: Notification checks.

    Verify modular notifications are called and worker notification is bypassed if no worker is assigned.
    """
    request_item = {
        "PK": "REQ#req-notify",
        "SK": "CLIENT#client-123",
        "request_id": "req-notify",
        "client_id": "client-123",
        "company_id": "tog_and_dogs",
        # no worker_id, so no SMS notification sent
        "client_name": "Test Client",
        "start_date": "2026-07-20"
    }
    db_mock = DynamoDBMock(request_item)
    mock_get_item.side_effect = db_mock.get_item

    body = {
        "request_id": "req-notify",
        "client_id": "client-123",
        "decision": "APPROVE"
    }

    res = handle_admin_decision(body, {})
    assert res["statusCode"] == 200
    
    # Assert new modular notification was fired
    mock_notify.assert_called_once_with('VISIT_CANCELLED', request_item)
