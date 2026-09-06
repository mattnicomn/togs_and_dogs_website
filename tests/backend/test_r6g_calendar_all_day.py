"""
Release 6G Phase 2: Tests for all-day event fallback in Google Calendar sync.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from unittest.mock import patch, MagicMock
from common.google_calendar import _build_event_body, sync_calendar_event


# --- Timed Event (Existing Behavior) ---

def test_timed_event_with_scheduled_time():
    """When scheduled_time exists, a timed event should be created."""
    item = {
        "request_id": "req-001",
        "client_name": "Jane Smith",
        "pet_names": "Buddy",
        "service_type": "WALK_30MIN",
        "start_date": "2026-07-15",
        "scheduled_time": "09:30",
    }
    body, skip = _build_event_body(item, assigned_worker="Ryan")
    assert skip is None
    assert body is not None
    assert 'dateTime' in body['start']
    assert 'dateTime' in body['end']
    assert '2026-07-15T09:30:00' in body['start']['dateTime']
    assert 'timeZone' in body['start']
    assert 'Jane Smith' in body['description']
    assert '🐾 Buddy' in body['summary']
    assert 'Exact Time' in body['summary']
    print("PASS: test_timed_event_with_scheduled_time")


def test_timed_event_with_hh_mm_ss():
    """scheduled_time in HH:MM:SS format should work."""
    item = {
        "request_id": "req-002",
        "client_name": "Test",
        "pet_names": "Max",
        "service_type": "PET_SITTING",
        "start_date": "2026-08-01",
        "scheduled_time": "14:00:00",
    }
    body, skip = _build_event_body(item)
    assert skip is None
    assert '2026-08-01T14:00:00' in body['start']['dateTime']
    print("PASS: test_timed_event_with_hh_mm_ss")


# --- All-Day Fallback (New Behavior) ---

def test_all_day_fallback_no_scheduled_time():
    """When start_date exists but no scheduled_time, create an all-day event."""
    item = {
        "request_id": "req-003",
        "client_name": "Joey Rockwell",
        "pet_names": "Fido",
        "service_type": "DROPIN_1HR",
        "start_date": "2026-09-10",
    }
    body, skip = _build_event_body(item)
    assert skip is None
    assert body is not None
    # All-day events use 'date' not 'dateTime'
    assert 'date' in body['start']
    assert 'date' in body['end']
    assert body['start']['date'] == '2026-09-10'
    # End date is exclusive (next day for single-day event)
    assert body['end']['date'] == '2026-09-11'
    assert 'dateTime' not in body['start']
    assert 'Joey Rockwell' in body['description']
    assert '🐾 Fido' in body['summary']
    assert 'All Day' in body['summary']
    print("PASS: test_all_day_fallback_no_scheduled_time")


def test_all_day_fallback_empty_scheduled_time():
    """Empty string scheduled_time should trigger all-day fallback."""
    item = {
        "request_id": "req-004",
        "client_name": "Test Client",
        "pet_names": "Luna",
        "service_type": "OVERNIGHT",
        "start_date": "2026-10-01",
        "scheduled_time": "",
    }
    body, skip = _build_event_body(item)
    assert skip is None
    assert 'date' in body['start']
    assert body['start']['date'] == '2026-10-01'
    print("PASS: test_all_day_fallback_empty_scheduled_time")


def test_all_day_fallback_none_scheduled_time():
    """None scheduled_time should trigger all-day fallback."""
    item = {
        "request_id": "req-005",
        "client_name": "Test",
        "pet_names": "Rex",
        "service_type": "WALK_60MIN",
        "start_date": "2026-11-15",
        "scheduled_time": None,
    }
    body, skip = _build_event_body(item)
    assert skip is None
    assert 'date' in body['start']
    assert body['start']['date'] == '2026-11-15'
    print("PASS: test_all_day_fallback_none_scheduled_time")


# --- Missing start_date ---

def test_missing_start_date_returns_skip():
    """Missing start_date should return a skip reason."""
    item = {
        "request_id": "req-006",
        "client_name": "Test",
        "pet_names": "Dog",
        "service_type": "PET_SITTING",
    }
    body, skip = _build_event_body(item)
    assert body is None
    assert skip is not None
    assert "scheduled_date" in skip or "missing" in skip
    print("PASS: test_missing_start_date_returns_skip")


# --- DST / Date Boundary Tests ---

def test_all_day_dst_spring_forward():
    """All-day event on DST spring-forward date should not shift days."""
    # March 9, 2026 is DST spring-forward in US Eastern
    item = {
        "request_id": "req-dst1",
        "client_name": "DST Test",
        "pet_names": "Buddy",
        "service_type": "WALK_30MIN",
        "start_date": "2026-03-09",
    }
    body, skip = _build_event_body(item)
    assert skip is None
    assert body['start']['date'] == '2026-03-09'
    assert body['end']['date'] == '2026-03-10'
    print("PASS: test_all_day_dst_spring_forward")


def test_all_day_dst_fall_back():
    """All-day event on DST fall-back date should not shift days."""
    # November 1, 2026 is DST fall-back in US Eastern
    item = {
        "request_id": "req-dst2",
        "client_name": "DST Test",
        "pet_names": "Max",
        "service_type": "DROPIN_3HR",
        "start_date": "2026-11-01",
    }
    body, skip = _build_event_body(item)
    assert skip is None
    assert body['start']['date'] == '2026-11-01'
    assert body['end']['date'] == '2026-11-02'
    print("PASS: test_all_day_dst_fall_back")


def test_all_day_year_boundary():
    """All-day event on Dec 31 should have end date Jan 1 next year."""
    item = {
        "request_id": "req-year",
        "client_name": "Year End",
        "pet_names": "Spot",
        "service_type": "OVERNIGHT",
        "start_date": "2026-12-31",
    }
    body, skip = _build_event_body(item)
    assert skip is None
    assert body['start']['date'] == '2026-12-31'
    assert body['end']['date'] == '2027-01-01'
    print("PASS: test_all_day_year_boundary")


def test_all_day_leap_year():
    """All-day event on Feb 28 in a non-leap year."""
    item = {
        "request_id": "req-leap",
        "client_name": "Leap Test",
        "pet_names": "Cat",
        "service_type": "PET_SITTING",
        "start_date": "2026-02-28",
    }
    body, skip = _build_event_body(item)
    assert skip is None
    assert body['start']['date'] == '2026-02-28'
    assert body['end']['date'] == '2026-03-01'
    print("PASS: test_all_day_leap_year")


# --- Non-Blocking Behavior ---

def test_sync_nonblocking_on_invalid_date(primary_google_binding):
    """sync_calendar_event must not raise even with an invalid date format."""
    item = {
        "company_id": "tog_and_dogs",
        "request_id": "req-bad",
        "client_name": "Bad Date",
        "pet_names": "Dog",
        "service_type": "WALK_30MIN",
        "start_date": "not-a-date",
    }
    # Mock token retrieval to isolate _build_event_body behavior
    with patch('common.google_calendar._get_valid_token', return_value="fake_token"):
        result = sync_calendar_event(item)

    assert result is not None
    # Should be skipped, not crashed
    assert result.get("status") == "calendar_skipped_invalid_date_format"
    print("PASS: test_sync_nonblocking_on_invalid_date")


def test_sync_nonblocking_on_missing_fields(primary_google_binding):
    """sync_calendar_event must not raise when required fields are missing."""
    item = {"request_id": "req-empty", "company_id": "tog_and_dogs"}
    with patch('common.google_calendar._get_valid_token', return_value="fake_token"):
        result = sync_calendar_event(item)

    assert result is not None
    assert "skipped" in result.get("status", "")
    print("PASS: test_sync_nonblocking_on_missing_fields")


if __name__ == '__main__':
    test_timed_event_with_scheduled_time()
    test_timed_event_with_hh_mm_ss()
    test_all_day_fallback_no_scheduled_time()
    test_all_day_fallback_empty_scheduled_time()
    test_all_day_fallback_none_scheduled_time()
    test_missing_start_date_returns_skip()
    test_all_day_dst_spring_forward()
    test_all_day_dst_fall_back()
    test_all_day_year_boundary()
    test_all_day_leap_year()
    test_sync_nonblocking_on_invalid_date()
    test_sync_nonblocking_on_missing_fields()
    print("\nAll Release 6G all-day event tests PASSED.")
