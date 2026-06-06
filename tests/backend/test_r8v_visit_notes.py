"""
Release 8V: Tests for optional staff visit notes and completion metadata.
"""
import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers.review_handler import handler as review_handler

def mock_get_item(pk, sk):
    if pk == "REQ#req-123":
        return {
            "PK": pk,
            "SK": sk,
            "request_id": "req-123",
            "client_id": "client-123",
            "status": "ASSIGNED",
            "worker_id": "staff@example.com"
        }
    if pk == "REQ#req-admin":
        return {
            "PK": pk,
            "SK": sk,
            "request_id": "req-admin",
            "client_id": "client-123",
            "status": "MG_COMPLETED"
        }
    return None

def make_review_event(role, email, body_dict):
    return {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "email": email,
                    "cognito:groups": [role]
                }
            }
        },
        "body": json.dumps(body_dict)
    }

@patch('handlers.review_handler.get_item', side_effect=mock_get_item)
@patch('handlers.review_handler.table')
@patch('handlers.review_handler.log_action')
@patch('handlers.review_handler.notify_event', return_value={"success": True, "message": "Mock notification sent."})
@patch('common.cascade.cascade_status_to_job')
@patch('common.auth.get_effective_role', return_value='staff')
@patch('common.auth.get_claims', return_value={'email': 'staff@example.com'})
def test_completed_stores_visit_notes(mock_claims, mock_role, mock_cascade, mock_notify, mock_log, mock_table, mock_get):
    event = make_review_event('staff', 'staff@example.com', {
        "request_id": "req-123",
        "client_id": "client-123",
        "status": "COMPLETED",
        "visit_notes": " Buddy walked for 30 mins, fed him,gate latched. "
    })

    res = review_handler(event, None)
    assert res["statusCode"] == 200

    # Ensure update_item was called
    mock_table.update_item.assert_called_once()
    kwargs = mock_table.update_item.call_args[1]
    
    update_expression = kwargs["UpdateExpression"]
    attr_values = kwargs["ExpressionAttributeValues"]

    # Verify visit_notes got persisted
    assert "visit_notes = :vn" in update_expression
    # Trimmed whitespace check
    assert attr_values[":vn"] == "Buddy walked for 30 mins, fed him,gate latched."
    
    # Verify completion metadata got persisted
    assert "completed_at = :cat" in update_expression
    assert "completed_by = :cby" in update_expression
    assert attr_values[":cby"] == "staff@example.com"

@patch('handlers.review_handler.get_item', side_effect=mock_get_item)
@patch('handlers.review_handler.table')
@patch('handlers.review_handler.log_action')
@patch('handlers.review_handler.notify_event', return_value={"success": True, "message": "Mock notification sent."})
@patch('common.cascade.cascade_status_to_job')
@patch('common.auth.get_effective_role', return_value='staff')
@patch('common.auth.get_claims', return_value={'email': 'staff@example.com'})
def test_completed_without_notes_ok(mock_claims, mock_role, mock_cascade, mock_notify, mock_log, mock_table, mock_get):
    # Empty notes
    event = make_review_event('staff', 'staff@example.com', {
        "request_id": "req-123",
        "client_id": "client-123",
        "status": "COMPLETED",
        "visit_notes": "   "
    })

    res = review_handler(event, None)
    assert res["statusCode"] == 200

    kwargs = mock_table.update_item.call_args[1]
    update_expression = kwargs["UpdateExpression"]
    attr_values = kwargs["ExpressionAttributeValues"]

    # Ensure visit_notes is NOT in update expression but metadata IS
    assert "visit_notes" not in update_expression
    assert ":vn" not in attr_values
    assert "completed_at = :cat" in update_expression
    assert "completed_by = :cby" in update_expression

@patch('handlers.review_handler.get_item', side_effect=mock_get_item)
@patch('handlers.review_handler.table')
@patch('handlers.review_handler.log_action')
@patch('handlers.review_handler.notify_event', return_value={"success": True, "message": "Mock notification sent."})
@patch('common.cascade.cascade_status_to_job')
@patch('common.auth.get_effective_role', return_value='staff')
@patch('common.auth.get_claims', return_value={'email': 'staff@example.com'})
def test_visit_notes_over_500_chars_rejected(mock_claims, mock_role, mock_cascade, mock_notify, mock_log, mock_table, mock_get):
    # Over 500 chars
    oversized_notes = "A" * 501
    event = make_review_event('staff', 'staff@example.com', {
        "request_id": "req-123",
        "client_id": "client-123",
        "status": "COMPLETED",
        "visit_notes": oversized_notes
    })

    res = review_handler(event, None)
    assert res["statusCode"] == 400
    body = json.loads(res["body"])
    assert "exceed 500 characters" in body["error"]

    # update_item should not have been called
    mock_table.update_item.assert_not_called()

@patch('handlers.review_handler.get_item', side_effect=mock_get_item)
@patch('handlers.review_handler.table')
@patch('handlers.review_handler.log_action')
@patch('handlers.review_handler.notify_event', return_value={"success": True, "message": "Mock notification sent."})
@patch('common.cascade.cascade_status_to_job')
@patch('common.auth.get_effective_role', return_value='admin')
@patch('common.auth.get_claims', return_value={'email': 'admin@example.com'})
def test_non_completed_transition_ignores_notes(mock_claims, mock_role, mock_cascade, mock_notify, mock_log, mock_table, mock_get):
    event = make_review_event('admin', 'admin@example.com', {
        "request_id": "req-admin",
        "client_id": "client-123",
        "status": "APPROVED",
        "visit_notes": "Should be ignored since status is APPROVED"
    })

    res = review_handler(event, None)
    assert res["statusCode"] == 200

    kwargs = mock_table.update_item.call_args[1]
    update_expression = kwargs["UpdateExpression"]
    attr_values = kwargs["ExpressionAttributeValues"]

    # Ensure no completion metadata or notes are stored
    assert "visit_notes" not in update_expression
    assert "completed_at" not in update_expression
    assert "completed_by" not in update_expression
    assert ":vn" not in attr_values
    assert ":cat" not in attr_values
    assert ":cby" not in attr_values
