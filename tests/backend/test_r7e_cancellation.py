"""
Release 7E Phase 1A: Tests for multi-day JOB cancellation.
"""
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers.cancellation_handler import handle_admin_decision

# --- Mocks ---

def mock_get_item(pk, sk):
    req_id = pk.replace("REQ#", "").replace("JOB#", "")
    
    if pk.startswith("REQ#"):
        if req_id == "req-single":
            return {
                "PK": pk,
                "SK": sk,
                "request_id": req_id,
                "client_id": "client-123",
                "google_event_id": "parent_event_1",
            }
            
        if req_id == "req-multi":
            return {
                "PK": pk,
                "SK": sk,
                "request_id": req_id,
                "client_id": "client-123",
                "start_date": "2026-07-20",
                "end_date": "2026-07-21",
                "job_ids": ["job-1", "job-2"]
            }
            
    if pk.startswith("JOB#"):
        if req_id == "job-1":
            return {
                "PK": pk,
                "SK": sk,
                "google_event_id": "child_event_1",
            }
        if req_id == "job-2":
            return {
                "PK": pk,
                "SK": sk,
                # Missing google_event_id to test failure resilience
            }

    return None

def mock_get_effective_role(event):
    return 'admin'

# --- Tests ---

@patch('handlers.cancellation_handler.get_item', side_effect=mock_get_item)
@patch('handlers.cancellation_handler.table')
@patch('handlers.cancellation_handler.delete_event', return_value=True)
@patch('handlers.cancellation_handler.notify_event')
@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.cascade.cascade_status_to_job')
@patch('handlers.cancellation_handler.log_action')
def test_cancel_single_day_req(mock_log, mock_cascade, mock_role, mock_notify, mock_delete, mock_table, mock_get):
    event = {}
    body = {
        "request_id": "req-single",
        "client_id": "client-123",
        "decision": "APPROVE"
    }
    
    res = handle_admin_decision(body, event)
    
    assert res["statusCode"] == 200
    # Should delete the single parent event
    mock_delete.assert_called_once_with("parent_event_1", "req-single")

@patch('handlers.cancellation_handler.get_item', side_effect=mock_get_item)
@patch('handlers.cancellation_handler.table')
@patch('handlers.cancellation_handler.delete_event', return_value=True)
@patch('handlers.cancellation_handler.notify_event')
@patch('common.auth.get_effective_role', side_effect=mock_get_effective_role)
@patch('common.cascade.cascade_status_to_job')
@patch('handlers.cancellation_handler.log_action')
def test_cancel_multi_day_req(mock_log, mock_cascade, mock_role, mock_notify, mock_delete, mock_table, mock_get):
    event = {}
    body = {
        "request_id": "req-multi",
        "client_id": "client-123",
        "decision": "APPROVE"
    }
    
    res = handle_admin_decision(body, event)
    
    assert res["statusCode"] == 200
    # Should delete the child event only
    mock_delete.assert_called_once_with("child_event_1", "req-multi")
    
    import json
    res_body = json.loads(res["body"])
    # 1 child was successfully deleted since job-2 has no event
    assert "Deleted 1 child events" in res_body["message"]
