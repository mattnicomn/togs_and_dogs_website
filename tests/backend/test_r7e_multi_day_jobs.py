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
    if pk in ('JOB#existing-job-id', 'JOB#job1', 'JOB#job2'):
        return {'PK': pk, 'SK': sk, 'company_id': 'test_company'}
    req_id = pk.replace("REQ#", "")
    base = {
        "PK": pk,
        "SK": sk,
        "request_id": req_id,
        "client_id": "client-123",
        "company_id": "test_company",
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

    if req_id == "req-selected-4":
        base["selected_dates"] = ["2026-08-01", "2026-08-03", "2026-08-05", "2026-08-08"]
        return base
    if req_id == "req-selected-priority":
        base["selected_dates"] = ["2026-08-01", "2026-08-03"]
        base["end_date"] = "2026-08-10"
        return base
    if req_id == "req-selected-dedup":
        base["selected_dates"] = ["2026-08-01", "2026-08-01", "2026-08-03"]
        return base
    if req_id == "req-selected-unsorted":
        base["selected_dates"] = ["2026-08-05", "2026-08-01", "2026-08-03"]
        return base
    if req_id == "req-selected-invalid":
        base["selected_dates"] = ["2026-08-01", "not-a-date", "2026-08-03", None]
        return base
    if req_id == "req-selected-15":
        base["selected_dates"] = [f"2026-08-{i:02d}" for i in range(1, 16)]
        return base
    if req_id == "req-selected-1":
        base["selected_dates"] = ["2026-08-01"]
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
    event = {"expected_company_id": "test_company", "request_id": "req-single-no-end", "client_id": "client-123"}
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
    event = {"expected_company_id": "test_company", "request_id": "req-single-same-end", "client_id": "client-123"}
    job_handler(event, None)
    assert mock_put.call_count == 1

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
@patch('common.google_calendar.sync_calendar_event', return_value={"event_id": "child_cal_id"})
def test_two_day_range(mock_sync, mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-multi-2", "client_id": "client-123"}
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
    event = {"expected_company_id": "test_company", "request_id": "req-multi-5", "client_id": "client-123"}
    res = job_handler(event, None)
    assert mock_put.call_count == 5
    assert len(res["job_ids"]) == 5

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_fourteen_day_range(mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-multi-14", "client_id": "client-123"}
    res = job_handler(event, None)
    assert mock_put.call_count == 14

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_fifteen_day_range_rejected(mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-multi-15", "client_id": "client-123"}
    res = job_handler(event, None)
    assert "exceeds maximum of 14 days" in res.get("error", "")
    assert mock_put.call_count == 0

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_multi_day_jobs_inherit_visit_window(mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-multi-2", "client_id": "client-123"}
    job_handler(event, None)
    put1 = mock_put.call_args_list[0][0][0]
    assert put1["visit_window"] == "MORNING"
    assert put1["service_type"] == "WALK_30MIN"

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_parent_req_updated_with_job_ids(mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-multi-2", "client_id": "client-123"}
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
    event = {"expected_company_id": "test_company", "request_id": "req-multi-google-event", "client_id": "client-123"}
    job_handler(event, None)
    put1 = mock_put.call_args_list[0][0][0]
    assert "google_event_id" not in put1

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_existing_job_id_skips_creation(mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-existing-job", "client_id": "client-123"}
    res = job_handler(event, None)
    assert res["status"] == "EXISTING_JOBS_SKIPPED"
    assert res["job_id"] == "existing-job-id"
    assert mock_put.call_count == 0

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_existing_job_ids_skips_creation(mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-existing-job-ids", "client_id": "client-123"}
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
    
    event = {"expected_company_id": "test_company", "request_id": "req-multi-2", "client_id": "client-123"}
    res = job_handler(event, None)
    
    assert mock_put.call_count == 2
    # Ensure only 1 job is in job_ids
    assert len(res["job_ids"]) == 1
    
    # And table.update_item was called with only the 1 successful id
    mock_table.update_item.assert_called_once()
    kwargs = mock_table.update_item.call_args[1]
    assert len(kwargs["ExpressionAttributeValues"][":jids"]) == 1
    assert res["job_ids"][0] == kwargs["ExpressionAttributeValues"][":jids"][0]

# --- Selected Dates Tests ---

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
@patch('common.google_calendar.sync_calendar_event', return_value={"event_id": "child_cal_id"})
def test_selected_dates_creates_correct_jobs(mock_sync, mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-selected-4", "client_id": "client-123"}
    res = job_handler(event, None)
    
    assert mock_put.call_count == 4
    put1 = mock_put.call_args_list[0][0][0]
    put4 = mock_put.call_args_list[3][0][0]
    
    assert put1["occurrence_date"] == "2026-08-01"
    assert put1["occurrence_index"] == 1
    assert put1["total_occurrences"] == 4
    
    assert put4["occurrence_date"] == "2026-08-08"
    assert put4["occurrence_index"] == 4
    assert put4["total_occurrences"] == 4
    
    assert len(res["job_ids"]) == 4

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_selected_dates_priority_over_range(mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-selected-priority", "client_id": "client-123"}
    res = job_handler(event, None)
    
    assert mock_put.call_count == 2
    put1 = mock_put.call_args_list[0][0][0]
    assert put1["occurrence_date"] == "2026-08-01"

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_selected_dates_dedup(mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-selected-dedup", "client_id": "client-123"}
    res = job_handler(event, None)
    assert mock_put.call_count == 2

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_selected_dates_sorted(mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-selected-unsorted", "client_id": "client-123"}
    res = job_handler(event, None)
    assert mock_put.call_count == 3
    put1 = mock_put.call_args_list[0][0][0]
    put2 = mock_put.call_args_list[1][0][0]
    put3 = mock_put.call_args_list[2][0][0]
    assert put1["occurrence_date"] == "2026-08-01"
    assert put2["occurrence_date"] == "2026-08-03"
    assert put3["occurrence_date"] == "2026-08-05"

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_selected_dates_invalid_filtered(mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-selected-invalid", "client_id": "client-123"}
    res = job_handler(event, None)
    assert mock_put.call_count == 2

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_selected_dates_single_treated_as_single_day(mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-selected-1", "client_id": "client-123"}
    res = job_handler(event, None)
    assert mock_put.call_count == 1
    put1 = mock_put.call_args_list[0][0][0]
    assert "is_multi_day" not in put1

@patch('handlers.job_handler.get_item', side_effect=mock_get_item)
@patch('handlers.job_handler.put_item', side_effect=mock_put_item)
@patch('handlers.job_handler.table')
@patch('common.pet_profile.create_or_link_pets_from_request', side_effect=mock_pet_create)
def test_selected_dates_max_14(mock_pet, mock_table, mock_put, mock_get):
    event = {"expected_company_id": "test_company", "request_id": "req-selected-15", "client_id": "client-123"}
    res = job_handler(event, None)
    assert "exceeds maximum of 14" in res.get("error", "")
    assert mock_put.call_count == 0


# =====================================================================
# Gate C3b.3k.4 — Legacy multi-day visit-window fidelity
# =====================================================================
#
# These tests verify that non-canonical (legacy) multi-day child jobs
# inherit a single, explicit, unambiguous parent request window as a
# label-only value, that Google Calendar renders such an inherited
# window as an all-day event (never an inferred appointment time), that
# a read-time fallback surfaces the parent window for historical
# children without mutating any record, and that canonical and
# fixed-time behavior is left completely unchanged.

import pytest

from common.google_calendar import (
    _build_event_body,
    resolve_inherited_request_window,
    INHERITED_REQUEST_WINDOW_SOURCE,
)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Function-scoped, auto-restored guard that fails any real HTTP egress.

    Patches both the botocore transport and urllib so no test in this module
    can reach AWS or Google. monkeypatch restores everything automatically at
    the end of each test.
    """
    def _raise_botocore(*args, **kwargs):
        raise AssertionError("Unexpected network call via botocore in r7e tests")

    def _raise_urllib(*args, **kwargs):
        raise AssertionError("Unexpected network call via urllib in r7e tests")

    monkeypatch.setattr(
        "botocore.httpsession.URLLib3Session.send", _raise_botocore, raising=False
    )
    import common.google_calendar as _gc
    monkeypatch.setattr(_gc.urllib.request, "urlopen", _raise_urllib, raising=False)
    yield


# --- Child-job inheritance (job_handler) ---

def _legacy_multiday_request(window=None, windows=None, extra=None):
    """Synthetic non-canonical (WALK_30MIN) two-day parent request."""
    req = {
        "PK": "REQ#req-legacy-mw",
        "SK": "CLIENT#client-123",
        "request_id": "req-legacy-mw",
        "client_id": "client-123",
        "company_id": "test_company",
        "service_type": "WALK_30MIN",
        "start_date": "2026-07-20",
        "end_date": "2026-07-21",
        "pet_names": "Rex",
    }
    if window is not None:
        req["visit_window"] = window
    if windows is not None:
        req["visit_windows"] = windows
    if extra:
        req.update(extra)
    return req


def _run_legacy_multiday(monkeypatch, request_item):
    """Drive job_handler for a synthetic legacy multi-day request, capturing puts."""
    import handlers.job_handler as jh

    captured = []
    monkeypatch.setattr(jh, "get_item", lambda pk, sk: request_item
                        if pk == request_item["PK"] else None)
    monkeypatch.setattr(jh, "put_item", lambda item: captured.append(item) or True)
    monkeypatch.setattr(jh, "table", MagicMock())
    monkeypatch.setattr(
        "common.pet_profile.create_or_link_pets_from_request",
        lambda *a, **k: {"pet_ids": ["pet-123"]},
    )
    monkeypatch.setattr(
        "common.google_calendar.sync_calendar_event",
        lambda *a, **k: {"event_id": "child_cal_id"},
    )
    event = {
        "expected_company_id": "test_company",
        "request_id": request_item["request_id"],
        "client_id": "client-123",
    }
    jh.handler(event, None)
    return captured


def test_legacy_multiday_inherits_morning_window(monkeypatch):
    captured = _run_legacy_multiday(monkeypatch, _legacy_multiday_request(window="MORNING"))
    assert len(captured) == 2
    for child in captured:
        assert child["occurrence_window"] == "MORNING"
        assert child["visit_window"] == "MORNING"
        assert child["visit_windows"] == ["MORNING"]
        # (B) Identified as inherited, NOT an exact appointment.
        assert child["window_source"] == INHERITED_REQUEST_WINDOW_SOURCE
        # Never fabricate a precise time from a window label.
        assert "start_time" not in child
        assert "scheduled_time" not in child


def test_legacy_multiday_inherits_midday_window(monkeypatch):
    captured = _run_legacy_multiday(monkeypatch, _legacy_multiday_request(window="MIDDAY"))
    assert captured[0]["occurrence_window"] == "MIDDAY"
    assert captured[0]["window_source"] == INHERITED_REQUEST_WINDOW_SOURCE
    assert "start_time" not in captured[0]


def test_legacy_multiday_inherits_evening_window(monkeypatch):
    captured = _run_legacy_multiday(monkeypatch, _legacy_multiday_request(window="EVENING"))
    assert captured[0]["occurrence_window"] == "EVENING"
    assert captured[0]["window_source"] == INHERITED_REQUEST_WINDOW_SOURCE
    assert "start_time" not in captured[0]


def test_legacy_multiday_anytime_not_inherited(monkeypatch):
    captured = _run_legacy_multiday(monkeypatch, _legacy_multiday_request(window="ANYTIME"))
    for child in captured:
        assert "occurrence_window" not in child
        assert "visit_window" not in child
        assert "window_source" not in child


def test_legacy_multiday_afternoon_not_inherited(monkeypatch):
    captured = _run_legacy_multiday(monkeypatch, _legacy_multiday_request(window="AFTERNOON"))
    for child in captured:
        assert "window_source" not in child
        assert "occurrence_window" not in child


def test_legacy_multiday_missing_window_not_inherited(monkeypatch):
    captured = _run_legacy_multiday(monkeypatch, _legacy_multiday_request())
    for child in captured:
        assert "window_source" not in child
        assert "occurrence_window" not in child


def test_legacy_multiday_invalid_window_not_inherited(monkeypatch):
    captured = _run_legacy_multiday(monkeypatch, _legacy_multiday_request(window="NOON_ISH"))
    for child in captured:
        assert "window_source" not in child


def test_legacy_multiday_multiple_distinct_windows_not_inherited(monkeypatch):
    captured = _run_legacy_multiday(
        monkeypatch, _legacy_multiday_request(windows=["MORNING", "EVENING"])
    )
    for child in captured:
        assert "window_source" not in child
        assert "occurrence_window" not in child


def test_legacy_multiday_conflicting_window_fields_ambiguous(monkeypatch):
    captured = _run_legacy_multiday(
        monkeypatch,
        _legacy_multiday_request(window="MORNING", windows=["EVENING"]),
    )
    for child in captured:
        assert "window_source" not in child
        assert "occurrence_window" not in child


# --- resolve_inherited_request_window unit coverage ---

@pytest.mark.parametrize("req,expected", [
    ({"visit_window": "MORNING"}, "MORNING"),
    ({"visit_window": "midday"}, "MIDDAY"),
    ({"visit_windows": ["EVENING"]}, "EVENING"),
    ({"visit_window": "MORNING", "visit_windows": ["MORNING"]}, "MORNING"),
    ({"visit_window": "ANYTIME"}, None),
    ({"visit_window": "AFTERNOON"}, None),
    ({"visit_windows": ["MORNING", "EVENING"]}, None),
    ({"visit_window": "MORNING", "visit_windows": ["EVENING"]}, None),
    ({"visit_windows": []}, None),
    ({}, None),
    (None, None),
    ("not-a-dict", None),
])
def test_resolve_inherited_request_window(req, expected):
    assert resolve_inherited_request_window(req) == expected


# --- Google Calendar all-day semantics ---

def _calendar_item(window_source=None, extra=None):
    item = {
        "request_id": "req-legacy-mw",
        "client_name": "Jane Client",
        "pet_names": "Rex",
        "service_type": "WALK_30MIN",
        "scheduled_date": "2026-07-20",
        "occurrence_window": "MORNING",
        "visit_window": "MORNING",
        "visit_windows": ["MORNING"],
    }
    if window_source is not None:
        item["window_source"] = window_source
    if extra:
        item.update(extra)
    return item


def test_calendar_inherited_window_is_all_day_with_label():
    item = _calendar_item(window_source=INHERITED_REQUEST_WINDOW_SOURCE)
    body, skip = _build_event_body(item)
    assert skip is None
    # (C) All-day event: date-only start/end, no dateTime timestamps.
    assert "date" in body["start"] and "dateTime" not in body["start"]
    assert "date" in body["end"] and "dateTime" not in body["end"]
    assert body["start"]["date"] == "2026-07-20"
    # Window label preserved in summary and description.
    assert "Morning" in body["summary"]
    assert "Window: Morning" in body["description"]
    # No "estimated from booking window" timing note for an inherited label.
    assert "Estimated from booking window" not in body["description"]


def test_calendar_inherited_window_without_source_would_infer_time():
    # Control: identical item WITHOUT the provenance marker takes the legacy
    # path and DOES synthesize a timed event — proving the marker is what
    # suppresses the inferred clock time (non-vacuous assertion).
    item = _calendar_item(window_source=None)
    body, skip = _build_event_body(item)
    assert skip is None
    assert "dateTime" in body["start"]


def test_calendar_explicit_time_overrides_inherited_window():
    # An explicit scheduled_time must win over inherited-window display.
    item = _calendar_item(
        window_source=INHERITED_REQUEST_WINDOW_SOURCE,
        extra={"scheduled_time": "13:30"},
    )
    body, skip = _build_event_body(item)
    assert skip is None
    assert "dateTime" in body["start"]
    assert body["start"]["dateTime"].startswith("2026-07-20T13:30")


# --- Canonical regression: unchanged behavior ---

def test_calendar_canonical_walk20_unchanged():
    item = {
        "request_id": "r1", "client_name": "Jane", "pet_names": "Rex",
        "service_type": "WALK_20MIN", "scheduled_date": "2026-07-20",
        "occurrence_window": "MORNING", "visit_window": "MORNING",
        "visit_windows": ["MORNING"],
    }
    body, skip = _build_event_body(item)
    assert skip is None
    # Canonical WALK_20MIN resolves to its contract window start (timed event).
    assert "dateTime" in body["start"]
    assert body["start"]["dateTime"].startswith("2026-07-20T06:30")


def test_calendar_overnight_fixed_unchanged():
    item = {
        "request_id": "r2", "client_name": "Jane", "pet_names": "Rex",
        "service_type": "OVERNIGHT", "scheduled_date": "2026-07-20",
        "occurrence_schedule_mode": "fixed",
    }
    body, skip = _build_event_body(item)
    assert skip is None
    assert "dateTime" in body["start"]
    assert body["start"]["dateTime"].startswith("2026-07-20T21:00")
    # Crosses midnight -> ends next day at 07:00.
    assert body["end"]["dateTime"].startswith("2026-07-21T07:00")


def test_calendar_explicit_time_service_unchanged():
    item = {
        "request_id": "r3", "client_name": "Jane", "pet_names": "Rex",
        "service_type": "WALK_30MIN", "scheduled_date": "2026-07-20",
        "scheduled_time": "09:15",
    }
    body, skip = _build_event_body(item)
    assert skip is None
    assert body["start"]["dateTime"].startswith("2026-07-20T09:15")


# --- Historical read-time fallback (admin_handler, no writes) ---

def _run_occurrence_summary(monkeypatch, parent_req, child_record):
    import handlers.admin_handler as ah

    writes = []
    for name in ("put_item", "update_item", "delete_item"):
        if hasattr(ah.table, name):
            monkeypatch.setattr(ah.table, name,
                                lambda *a, **k: writes.append(name), raising=False)
    monkeypatch.setattr(ah, "get_item", lambda pk, sk: child_record)
    monkeypatch.setattr("common.auth.validate_tenant_ownership", lambda rec, ev: None)
    summary = ah._build_job_occurrence_summary(parent_req, {}, "admin", "admin@x")
    return summary, writes


def test_historical_child_without_window_gets_readtime_fallback(monkeypatch):
    parent = {
        "request_id": "req-hist",
        "PK": "REQ#req-hist",
        "job_ids": ["jobH"],
        "service_type": "WALK_30MIN",
        "visit_window": "MORNING",
        "company_id": "test_company",
    }
    child = {
        "PK": "JOB#jobH", "SK": "REQ#req-hist",
        "company_id": "test_company",
        "occurrence_date": "2026-07-20", "status": "JOB_CREATED",
        # No occurrence_window / visit_window: historical record.
    }
    summary, writes = _run_occurrence_summary(monkeypatch, parent, child)
    job = summary["jobs"][0]
    assert job["occurrence_window"] == "MORNING"
    assert job["occurrence_window_source"] == INHERITED_REQUEST_WINDOW_SOURCE
    # No database mutation during a read.
    assert writes == []
    assert "occurrence_window" not in child  # source record untouched


def test_historical_child_with_window_is_authoritative(monkeypatch):
    parent = {
        "request_id": "req-hist2", "PK": "REQ#req-hist2",
        "job_ids": ["jobH2"], "service_type": "WALK_30MIN",
        "visit_window": "EVENING", "company_id": "test_company",
    }
    child = {
        "PK": "JOB#jobH2", "SK": "REQ#req-hist2",
        "company_id": "test_company", "occurrence_date": "2026-07-20",
        "status": "JOB_CREATED",
        "occurrence_window": "MIDDAY",  # child value wins over parent EVENING
    }
    summary, writes = _run_occurrence_summary(monkeypatch, parent, child)
    job = summary["jobs"][0]
    assert job["occurrence_window"] == "MIDDAY"
    assert writes == []


def test_historical_child_anytime_parent_no_fallback(monkeypatch):
    parent = {
        "request_id": "req-hist3", "PK": "REQ#req-hist3",
        "job_ids": ["jobH3"], "service_type": "WALK_30MIN",
        "visit_window": "ANYTIME", "company_id": "test_company",
    }
    child = {
        "PK": "JOB#jobH3", "SK": "REQ#req-hist3",
        "company_id": "test_company", "occurrence_date": "2026-07-20",
        "status": "JOB_CREATED",
    }
    summary, writes = _run_occurrence_summary(monkeypatch, parent, child)
    job = summary["jobs"][0]
    assert job["occurrence_window"] is None
    assert job["occurrence_window_source"] is None
    assert writes == []
