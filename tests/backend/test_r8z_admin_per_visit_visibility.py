"""
Release 8Z: Tests for Admin per-visit completion visibility, enrichment, and completed_count.
"""
import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers.admin_handler import handler as admin_handler
from common.auth import sanitize_booking_for_role

# Mock Data
MOCK_JOBS = {
    "JOB#job-1": {
        "PK": "JOB#job-1",
        "SK": "REQ#req-123",
        "status": "COMPLETED",
        "worker_id": "staff@example.com",
        "worker_name": "Sitter A",
        "client_id": "client-123",
        "occurrence_date": "2026-06-12",
        "occurrence_index": 2,
        "completed_at": "2026-06-07T12:00:00",
        "completed_by": "staff@example.com",
        "visit_notes": "All good!"
    },
    "JOB#job-2": {
        "PK": "JOB#job-2",
        "SK": "REQ#req-123",
        "status": "ASSIGNED",
        "worker_id": "staff@example.com",
        "worker_name": "Sitter A",
        "client_id": "client-123",
        "occurrence_date": "2026-06-10",
        "occurrence_index": 1
    }
}

MOCK_REQS = {
    "REQ#req-123": {
        "PK": "REQ#req-123",
        "SK": "CLIENT#client-123",
        "status": "ASSIGNED",
        "job_ids": ["job-1", "job-2"],
        "client_id": "client-123",
        "is_multi_day": True,
        "completed_job_ids": ["job-1"]
    },
    "REQ#req-single": {
        "PK": "REQ#req-single",
        "SK": "CLIENT#client-123",
        "status": "ASSIGNED",
        "client_id": "client-123",
        "is_multi_day": False
    }
}

def mock_get_item(pk, sk):
    if pk.startswith("JOB#"):
        return MOCK_JOBS.get(pk)
    if pk.startswith("REQ#"):
        return MOCK_REQS.get(pk)
    return None

def make_get_event(role, request_id, client_id):
    return {
        "httpMethod": "GET",
        "path": f"/admin/request/{request_id}",
        "pathParameters": {
            "requestId": request_id
        },
        "queryStringParameters": {
            "clientId": client_id
        },
        "requestContext": {
            "authorizer": {
                "claims": {
                    "email": "admin@example.com",
                    "cognito:groups": [role]
                }
            }
        }
    }

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
@patch('handlers.admin_handler.get_effective_role', return_value='admin')
def test_single_request_enriched_with_job_summary(mock_role, mock_get):
    event = make_get_event('admin', 'req-123', 'client-123')
    res = admin_handler(event, None)
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    
    assert "job_completion_summary" in body
    summary = body["job_completion_summary"]
    assert summary["total"] == 2
    assert summary["completed"] == 1
    assert summary["pending"] == 1
    
    jobs = summary["jobs"]
    assert len(jobs) == 2
    # Sorted by date: job-2 (June 10) should be first, then job-1 (June 12)
    assert jobs[0]["job_id"] == "job-2"
    assert jobs[0]["occurrence_date"] == "2026-06-10"
    assert jobs[0]["status"] == "ASSIGNED"
    
    assert jobs[1]["job_id"] == "job-1"
    assert jobs[1]["occurrence_date"] == "2026-06-12"
    assert jobs[1]["status"] == "COMPLETED"
    assert jobs[1]["visit_notes"] == "All good!"
    assert jobs[1]["worker_name"] == "Sitter A"

@patch('handlers.admin_handler.get_item', side_effect=mock_get_item)
@patch('handlers.admin_handler.get_effective_role', return_value='admin')
def test_single_request_no_jobs_no_summary(mock_role, mock_get):
    event = make_get_event('admin', 'req-single', 'client-123')
    res = admin_handler(event, None)
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert "job_completion_summary" not in body

@patch('handlers.admin_handler.get_item', side_effect=mock_get_item)
@patch('handlers.admin_handler.table')
@patch('handlers.admin_handler.log_action')
@patch('handlers.admin_handler.get_effective_role', return_value='staff')
@patch('handlers.admin_handler.get_claims', return_value={'email': 'staff@example.com'})
def test_completed_count_incremented_on_job_complete(mock_claims, mock_role, mock_log, mock_table, mock_get):
    # Complete job-2 (which is currently ASSIGNED, not in completed_job_ids)
    event = make_job_event('staff', 'staff@example.com', {
        "job_id": "job-2",
        "request_id": "req-123",
        "visit_notes": "Completed day 1"
    })
    res = admin_handler(event, None)
    assert res["statusCode"] == 200
    
    # Assert parent update call includes completed_count increment
    parent_call = mock_table.update_item.call_args_list[1][1]
    update_expr = parent_call["UpdateExpression"]
    expr_vals = parent_call["ExpressionAttributeValues"]
    
    assert "completed_count = if_not_exists(completed_count, :zero) + :one" in update_expr
    assert expr_vals[":zero"] == 0
    assert expr_vals[":one"] == 1
    assert "job-2" in expr_vals[":cj"]

@patch('handlers.admin_handler.get_item', side_effect=mock_get_item)
@patch('handlers.admin_handler.table')
@patch('handlers.admin_handler.log_action')
@patch('handlers.admin_handler.get_effective_role', return_value='staff')
@patch('handlers.admin_handler.get_claims', return_value={'email': 'staff@example.com'})
def test_completed_count_incremented_only_once(mock_claims, mock_role, mock_log, mock_table, mock_get):
    # Try to complete job-1 which is ALREADY COMPLETED (idempotency check)
    event = make_job_event('staff', 'staff@example.com', {
        "job_id": "job-1",
        "request_id": "req-123"
    })
    res = admin_handler(event, None)
    assert res["statusCode"] == 200
    
    body = json.loads(res["body"])
    assert body["message"] == "Already completed"
    
    # Verify no updates are executed (idempotent early return)
    mock_table.update_item.assert_not_called()

def test_client_role_redacts_metadata():
    enriched_booking = {
        "PK": "REQ#req-123",
        "SK": "CLIENT#client-123",
        "status": "ASSIGNED",
        "job_ids": ["job-1"],
        "job_completion_summary": {
            "total": 1,
            "completed": 1,
            "jobs": [{
                "job_id": "job-1",
                "visit_notes": "Internal note",
                "completed_by": "staff@example.com",
                "worker_id": "staff@example.com"
            }]
        }
    }
    sanitized = sanitize_booking_for_role(enriched_booking, "client")
    assert sanitized["job_completion_summary"] is None
