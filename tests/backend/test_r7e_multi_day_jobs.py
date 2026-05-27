"""
Release 7E Phase 1: Tests for multi-day JOB expansion and cascade.
"""
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers.job_handler import handler as job_handler
from common.cascade import cascade_status_to_job
from common.status import JobStatus
from unittest.mock import MagicMock

# --- Mocks ---

def mock_get_item(pk, sk):
    req_id = pk.replace("REQ#", "")
    base = {
        "PK": pk,
        "SK": sk,
        "request_id": req_id,
        "client_id": "client-123",
        "company_id": "test-company",
        "service_type": "WALK_30MIN",
        "visit_window": "MORNING",
        "start_date": "2026-07-20",
    }
    
    if req_id == "req-single-no-end":
        return base
        
    if req_id == "req-single-same-end":
        base["end_date"] = "2026-07-20"
        return base
        
    if req_id == "req-multi-2":
        base["end_date"] = "2026-07-21"
        return base

    if req_id == "req-multi-5":
        base["end_date"] = "2026-07-24"
        return base
        
    if req_id == "req-multi-14":
        base["end_date"] = "2026-08-02" # 14 inclusive
        return base
        
    if req_id == "req-multi-15":
        base["end_date"] = "2026-08-03" # 15 inclusive
        return base

    if req_id == "req-multi-google-event":
        base["end_date"] = "2026-07-21"
        base["google_event_id"] = "existing_google_event_id"
        return base

    if req_id == "req-existing-job":
        base["job_id"] = "existing-job-id"
        return base

    if req_id == "req-existing-job-ids":
        base["job_ids"] = ["job1", "job2"]
        return base

    return None

def mock_put_item(item):
    return True

def mock_pet_create(*args, **kwargs):
    return {"pet_ids": ["pet-123"]}

# --- JOB Expansion Tests ---

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_single_day_no_end_date(mock_pet, mock_table, mock_put, mock_get):
    event = {"request_id": "req-single-no-end", "client_id": "client-123"}
    res = job_handler(event, None)
    
    assert mock_put.call_count == 1
    put_args = mock_put.call_args[0][0]
    assert put_args["start_date"] == "2026-07-20"
    assert "occurrence_date" not in put_args
    assert "is_multi_day" not in put_args
    assert res["status"] == JobStatus.JOB_CREATED.value
    assert len(res["job_ids"]) == 1

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_single_day_same_end_date(mock_pet, mock_table, mock_put, mock_get):
    event = {"request_id": "req-single-same-end", "client_id": "client-123"}
    job_handler(event, None)
    assert mock_put.call_count == 1

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
@patch('common.google_calendar.sync_calendar_event', return_value={"event_id": "child_cal_id"})
def test_two_day_range(mock_sync, mock_pet, mock_table, mock_put, mock_get):
    event = {"request_id": "req-multi-2", "client_id": "client-123"}
    res = job_handler(event, None)
    
    assert mock_put.call_count == 2
    put1 = mock_put.call_args_list[0][0][0]
    put2 = mock_put.call_args_list[1][0][0]
    
    assert put1["occurrence_date"] == "2026-07-20"
    assert put1["occurrence_index"] == 1
    assert put1["total_occurrences"] == 2
    assert put1["is_multi_day"] is True
    assert put1["google_event_id"] == "child_cal_id"
    
    assert put2["occurrence_date"] == "2026-07-21"
    assert put2["occurrence_index"] == 2
    assert put2["total_occurrences"] == 2
    assert put2["google_event_id"] == "child_cal_id"
    
    assert put1["end_date"] == put1["occurrence_date"]
    assert put2["end_date"] == put2["occurrence_date"]
    
    assert len(res["job_ids"]) == 2
    
    # Phase 1A check: sync_calendar_event called twice for child jobs
    assert mock_sync.call_count == 2

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_five_day_range(mock_pet, mock_table, mock_put, mock_get):
    event = {"request_id": "req-multi-5", "client_id": "client-123"}
    res = job_handler(event, None)
    assert mock_put.call_count == 5
    assert len(res["job_ids"]) == 5

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_fourteen_day_range(mock_pet, mock_table, mock_put, mock_get):
    event = {"request_id": "req-multi-14", "client_id": "client-123"}
    res = job_handler(event, None)
    assert mock_put.call_count == 14

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_fifteen_day_range_rejected(mock_pet, mock_table, mock_put, mock_get):
    event = {"request_id": "req-multi-15", "client_id": "client-123"}
    res = job_handler(event, None)
    assert "exceeds maximum of 14 days" in res.get("error", "")
    assert mock_put.call_count == 0

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_multi_day_jobs_inherit_visit_window(mock_pet, mock_table, mock_put, mock_get):
    event = {"request_id": "req-multi-2", "client_id": "client-123"}
    job_handler(event, None)
    put1 = mock_put.call_args_list[0][0][0]
    assert put1["visit_window"] == "MORNING"
    assert put1["service_type"] == "WALK_30MIN"

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_parent_req_updated_with_job_ids(mock_pet, mock_table, mock_put, mock_get):
    event = {"request_id": "req-multi-2", "client_id": "client-123"}
    res = job_handler(event, None)
    
    mock_table.update_item.assert_called_once()
    kwargs = mock_table.update_item.call_args[1]
    assert "job_ids" in kwargs["UpdateExpression"]
    assert "is_multi_day" in kwargs["UpdateExpression"]
    assert kwargs["ExpressionAttributeValues"][":to"] == 2

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_multi_day_jobs_do_not_inherit_google_event_id(mock_pet, mock_table, mock_put, mock_get):
    event = {"request_id": "req-multi-google-event", "client_id": "client-123"}
    job_handler(event, None)
    put1 = mock_put.call_args_list[0][0][0]
    assert "google_event_id" not in put1

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_existing_job_id_skips_creation(mock_pet, mock_table, mock_put, mock_get):
    event = {"request_id": "req-existing-job", "client_id": "client-123"}
    res = job_handler(event, None)
    assert res["status"] == "EXISTING_JOBS_SKIPPED"
    assert res["job_id"] == "existing-job-id"
    assert mock_put.call_count == 0

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_existing_job_ids_skips_creation(mock_pet, mock_table, mock_put, mock_get):
    event = {"request_id": "req-existing-job-ids", "client_id": "client-123"}
    res = job_handler(event, None)
    assert res["status"] == "EXISTING_JOBS_SKIPPED"
    assert "job1" in res["job_ids"]
    assert mock_put.call_count == 0

# --- Cascade Tests ---

@patch('common.cascade.table')
def test_cascade_with_job_ids(mock_table):
    req = {
        "request_id": "req-1",
        "job_ids": ["job1", "job2", "job3"]
    }
    res = cascade_status_to_job(req, "APPROVED")
    assert res["success"] is True
    assert mock_table.update_item.call_count == 3
    assert "Cascaded to 3 JOB" in res["message"]

@patch('common.cascade.table')
def test_cascade_with_single_job_id(mock_table):
    req = {
        "request_id": "req-1",
        "job_id": "job1"
    }
    res = cascade_status_to_job(req, "APPROVED")
    assert res["success"] is True
    assert mock_table.update_item.call_count == 1

@patch('common.cascade.table')
def test_cascade_failure_does_not_block(mock_table):
    req = {
        "request_id": "req-1",
        "job_ids": ["job1", "job2", "job3"]
    }
    
    # Fail on job2
    def side_effect(*args, **kwargs):
        if "job2" in kwargs["Key"]["PK"]:
            raise Exception("Dynamo Error")
        return {}
        
    mock_table.update_item.side_effect = side_effect
    
    res = cascade_status_to_job(req, "APPROVED")
    assert res["success"] is False
    assert "2 succeeded, 1 failed" in res["message"]

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item')
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_partial_put_item_failure(mock_pet, mock_table, mock_put, mock_get):
    # Simulate first job succeeds, second fails
    mock_put.side_effect = [True, False]
    
    event = {"request_id": "req-multi-2", "client_id": "client-123"}
    res = job_handler(event, None)
    
    assert mock_put.call_count == 2
    # Ensure only 1 job is in job_ids
    assert len(res["job_ids"]) == 1
    
    # And table.update_item was called with only the 1 successful id
    mock_table.update_item.assert_called_once()
    kwargs = mock_table.update_item.call_args[1]
    assert len(kwargs["ExpressionAttributeValues"][":jids"]) == 1
    assert res["job_ids"][0] == kwargs["ExpressionAttributeValues"][":jids"][0]
