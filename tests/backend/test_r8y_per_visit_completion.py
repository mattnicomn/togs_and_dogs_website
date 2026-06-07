"""
Release 8Y: Tests for per-visit / per-day completion and parent auto-rollup.
"""
import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers.admin_handler import handler as admin_handler

# Mock Data
MOCK_JOBS = {
    "JOB#job-1": {
        "PK": "JOB#job-1",
        "SK": "REQ#req-123",
        "status": "ASSIGNED",
        "worker_id": "staff@example.com",
        "client_id": "client-123",
        "occurrence_date": "2026-06-10"
    },
    "JOB#job-2": {
        "PK": "JOB#job-2",
        "SK": "REQ#req-123",
        "status": "ASSIGNED",
        "worker_id": "staff@example.com",
        "client_id": "client-123",
        "occurrence_date": "2026-06-11"
    },
    "JOB#job-completed": {
        "PK": "JOB#job-completed",
        "SK": "REQ#req-123",
        "status": "COMPLETED",
        "worker_id": "staff@example.com",
        "client_id": "client-123",
        "occurrence_date": "2026-06-12"
    }
}

MOCK_REQS = {
    "REQ#req-123": {
        "PK": "REQ#req-123",
        "SK": "CLIENT#client-123",
        "status": "ASSIGNED",
        "job_ids": ["job-1", "job-2"],
        "client_id": "client-123",
        "is_multi_day": True
    }
}

def mock_get_item(pk, sk):
    if pk.startswith("JOB#"):
        return MOCK_JOBS.get(pk)
    if pk.startswith("REQ#"):
        return MOCK_REQS.get(pk)
    return None

def make_job_event(role, email, body_dict):
    return {
        "httpMethod": "POST",
        "path": "/admin/job/complete",
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

@patch('handlers.admin_handler.get_item', side_effect=mock_get_item)
@patch('handlers.admin_handler.table')
@patch('handlers.admin_handler.log_action')
@patch('handlers.admin_handler.get_effective_role', return_value='staff')
@patch('handlers.admin_handler.get_claims', return_value={'email': 'staff@example.com'})
def test_complete_single_job_success(mock_claims, mock_role, mock_log, mock_table, mock_get):
    event = make_job_event('staff', 'staff@example.com', {
        "job_id": "job-1",
        "request_id": "req-123",
        "visit_notes": "First day walk completed successfully! "
    })

    res = admin_handler(event, None)
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["status"] == "COMPLETED"
    assert body["parent_status"] == "ASSIGNED"  # Sibling job-2 is still active
    assert body["remaining_active_jobs"] == 1

    # Verify both updates were called
    assert mock_table.update_item.call_count == 2
    
    # Verify JOB update
    job_call = mock_table.update_item.call_args_list[0][1]
    assert job_call["Key"] == {"PK": "JOB#job-1", "SK": "REQ#req-123"}
    update_expression = job_call["UpdateExpression"]
    attr_values = job_call["ExpressionAttributeValues"]
    assert "visit_notes = :vn" in update_expression
    assert attr_values[":vn"] == "First day walk completed successfully!"
    assert attr_values[":cby"] == "staff@example.com"

    # Verify parent update (completed_job_ids)
    parent_call = mock_table.update_item.call_args_list[1][1]
    assert parent_call["Key"] == {"PK": "REQ#req-123", "SK": "CLIENT#client-123"}
    assert "completed_job_ids = :cj" in parent_call["UpdateExpression"]
    assert parent_call["ExpressionAttributeValues"][":cj"] == ["job-1"]


@patch('handlers.admin_handler.get_item', side_effect=mock_get_item)
@patch('handlers.admin_handler.table')
@patch('handlers.admin_handler.log_action')
@patch('handlers.admin_handler.get_effective_role', return_value='staff')
@patch('handlers.admin_handler.get_claims', return_value={'email': 'other_staff@example.com'})
def test_complete_job_staff_ownership_check(mock_claims, mock_role, mock_log, mock_table, mock_get):
    # staff@example.com is assigned, but other_staff@example.com tries to complete it
    event = make_job_event('staff', 'other_staff@example.com', {
        "job_id": "job-1",
        "request_id": "req-123"
    })

    res = admin_handler(event, None)
    assert res["statusCode"] == 403
    body = json.loads(res["body"])
    assert "only complete visits assigned to you" in body["error"]
    mock_table.update_item.assert_not_called()

@patch('handlers.admin_handler.get_item', side_effect=mock_get_item)
@patch('handlers.admin_handler.table')
@patch('handlers.admin_handler.log_action')
@patch('handlers.admin_handler.get_effective_role', return_value='staff')
@patch('handlers.admin_handler.get_claims', return_value={'email': 'staff@example.com'})
def test_complete_already_completed_idempotent(mock_claims, mock_role, mock_log, mock_table, mock_get):
    event = make_job_event('staff', 'staff@example.com', {
        "job_id": "job-completed",
        "request_id": "req-123"
    })

    res = admin_handler(event, None)
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["message"] == "Already completed"
    assert body["status"] == "COMPLETED"
    mock_table.update_item.assert_not_called()

@patch('handlers.admin_handler.get_item')
@patch('handlers.admin_handler.table')
@patch('handlers.admin_handler.log_action')
@patch('handlers.admin_handler.get_effective_role', return_value='staff')
@patch('handlers.admin_handler.get_claims', return_value={'email': 'staff@example.com'})
def test_auto_rollup_when_all_jobs_done(mock_claims, mock_role, mock_log, mock_table, mock_get):
    # In this mock, job-1 is active, but sibling job-2 is already COMPLETED.
    # Completing job-1 should rollup the parent.
    def local_get_item(pk, sk):
        if pk == "JOB#job-1":
            return MOCK_JOBS["JOB#job-1"]
        if pk == "JOB#job-2":
            # Sibling already completed
            return {
                "PK": "JOB#job-2",
                "SK": "REQ#req-123",
                "status": "COMPLETED",
                "worker_id": "staff@example.com",
                "client_id": "client-123"
            }
        if pk == "REQ#req-123":
            return MOCK_REQS["REQ#req-123"]
        return None

    mock_get.side_effect = local_get_item

    event = make_job_event('staff', 'staff@example.com', {
        "job_id": "job-1",
        "request_id": "req-123"
    })

    res = admin_handler(event, None)
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert body["status"] == "COMPLETED"
    assert body["parent_status"] == "COMPLETED"  # Rolled up successfully
    assert body["remaining_active_jobs"] == 0

    # Ensure update_item was called twice: once for the JOB, once for the REQ rollup
    assert mock_table.update_item.call_count == 2

@patch('handlers.admin_handler.get_item', side_effect=mock_get_item)
@patch('handlers.admin_handler.table')
@patch('handlers.admin_handler.log_action')
@patch('handlers.admin_handler.get_effective_role', return_value='staff')
@patch('handlers.admin_handler.get_claims', return_value={'email': 'staff@example.com'})
def test_notes_over_500_rejected(mock_claims, mock_role, mock_log, mock_table, mock_get):
    event = make_job_event('staff', 'staff@example.com', {
        "job_id": "job-1",
        "request_id": "req-123",
        "visit_notes": "A" * 501
    })

    res = admin_handler(event, None)
    assert res["statusCode"] == 400
    body = json.loads(res["body"])
    assert "exceed 500 characters" in body["error"]
    mock_table.update_item.assert_not_called()
