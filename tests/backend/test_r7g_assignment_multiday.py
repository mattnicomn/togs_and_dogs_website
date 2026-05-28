"""
Release 7G: Tests for multi-day assignment handler batch updates.
"""
import sys
import os
import json
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers.assignment_handler import handler as assignment_handler
from common.status import JobStatus

# --- Mocks ---

def mock_get_effective_role(event):
    return 'admin'

def mock_get_claims(event):
    return {'email': 'admin@usmissionhero.com'}

def mock_get_item(pk, sk):
    # Mocking REQ and JOB retrieval
    if pk == "REQ#req-multi-3":
        return {
            "PK": pk, "SK": sk, "status": "APPROVED",
            "job_ids": ["job-1", "job-2", "job-3"],
            "client_id": "client-123"
        }
    if pk == "REQ#req-single":
        return {
            "PK": pk, "SK": sk, "status": "APPROVED",
            "job_id": "job-single",
            "client_id": "client-123"
        }
    if pk == "REQ#req-missing-job":
        return {
            "PK": pk, "SK": sk, "status": "APPROVED",
            "job_ids": ["job-ok-1", "job-missing", "job-ok-2"],
            "client_id": "client-123"
        }
        
    # Mocking JOB retrieval
    if pk.startswith("JOB#"):
        job_id = pk.split("#")[1]
        if job_id == "job-missing":
            return None # Simulate missing job
            
        return {
            "PK": pk, "SK": sk, "status": "APPROVED",
            "client_id": "client-123",
            "start_date": "2026-07-20",
            "google_event_id": f"cal-{job_id}"
        }
    
    return None

# --- Tests ---

@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.auth.get_claims', side_effect=mock_get_claims)
@patch('common.db.get_item', side_effect=mock_get_item)
@patch('common.db.table')
@patch('common.google_calendar.sync_calendar_event')
@patch('common.notifications.service.notify_event')
def test_multi_day_parent_assignment(mock_notify, mock_sync, mock_table, mock_get_item, mock_claims, mock_role):
    # UI passes req_id for a multi-day booking
    event = {
        "body": json.dumps({
            "job_id": "req-multi-3",
            "req_id": "req-multi-3",
            "client_id": "client-123",
            "worker_id": "worker-xyz",
            "worker_name": "Test Worker"
        })
    }
    
    # Let calendar sync succeed without changing ID
    mock_sync.return_value = {"event_id": "cal-same"}
    
    res = assignment_handler(event, None)
    
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert "Worker assigned to 3 job(s) successfully" in body["message"]
    assert len(body["job_ids"]) == 3
    assert set(body["job_ids"]) == {"job-1", "job-2", "job-3"}
    
    # 3 main jobs updated + up to 3 calendar updates + 1 req updated
    assert mock_table.update_item.call_count >= 4
    
    # Calendar synced for all 3 jobs
    assert mock_sync.call_count == 3
    
    # Notifications fired exactly TWICE (one STAFF_ASSIGNED, one VISIT_SCHEDULED) for the whole batch
    assert mock_notify.call_count == 2
    event_types = [call[0][0] for call in mock_notify.call_args_list]
    assert "STAFF_ASSIGNED" in event_types
    assert "VISIT_SCHEDULED" in event_types


@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.auth.get_claims', side_effect=mock_get_claims)
@patch('common.db.get_item', side_effect=mock_get_item)
@patch('common.db.table')
@patch('common.google_calendar.sync_calendar_event')
@patch('common.notifications.service.notify_event')
def test_legacy_single_day_assignment(mock_notify, mock_sync, mock_table, mock_get_item, mock_claims, mock_role):
    # UI passes req_id for a single-day booking
    event = {
        "body": json.dumps({
            "job_id": "req-single",
            "req_id": "req-single",
            "client_id": "client-123",
            "worker_id": "worker-xyz",
            "worker_name": "Test Worker"
        })
    }
    
    mock_sync.return_value = {"event_id": "cal-same"}
    
    res = assignment_handler(event, None)
    
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    assert "Worker assigned to 1 job(s)" in body["message"]
    assert body["job_ids"] == ["job-single"]
    
    # 1 job updated + up to 1 calendar update + 1 req updated
    assert mock_table.update_item.call_count >= 2
    assert mock_sync.call_count == 1
    assert mock_notify.call_count == 2


@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.auth.get_claims', side_effect=mock_get_claims)
@patch('common.db.get_item', side_effect=mock_get_item)
@patch('common.db.table')
@patch('common.google_calendar.sync_calendar_event')
@patch('common.notifications.service.notify_event')
def test_missing_child_job_graceful(mock_notify, mock_sync, mock_table, mock_get_item, mock_claims, mock_role):
    # UI passes req_id for a multi-day booking, but one job is missing from DB
    event = {
        "body": json.dumps({
            "job_id": "req-missing-job",
            "req_id": "req-missing-job",
            "client_id": "client-123",
            "worker_id": "worker-xyz",
            "worker_name": "Test Worker"
        })
    }
    
    mock_sync.return_value = {"event_id": "cal-same"}
    
    res = assignment_handler(event, None)
    
    assert res["statusCode"] == 200
    body = json.loads(res["body"])
    # Should only assign 2 jobs
    assert "Worker assigned to 2 job(s)" in body["message"]
    assert len(body["job_ids"]) == 2
    assert set(body["job_ids"]) == {"job-ok-1", "job-ok-2"}
    
    # 2 jobs updated + up to 2 calendar updates + 1 req updated
    assert mock_table.update_item.call_count >= 3
    assert mock_sync.call_count == 2
    assert mock_notify.call_count == 2
