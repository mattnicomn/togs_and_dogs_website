"""
Release 7D: Tests for Google Calendar Visit Scheduling Hardening.
Tests window-based time inference, service durations, color coding, and title/description formatting.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from common.google_calendar import _build_event_body

def build_mock_item(overrides=None):
    item = {
        "request_id": "req-7d-test",
        "client_name": "John Doe",
        "pet_names": "Rex",
        "service_type": "PET_SITTING",
        "start_date": "2026-07-20",
    }
    if overrides:
        item.update(overrides)
    return item

def test_window_morning_creates_timed_event():
    body, skip = _build_event_body(build_mock_item({"visit_windows": ["MORNING"]}))
    assert skip is None
    assert 'dateTime' in body['start']
    assert '2026-07-20T08:00:00' in body['start']['dateTime']
    assert 'Morning' in body['summary']

def test_window_midday_creates_timed_event():
    body, skip = _build_event_body(build_mock_item({"visit_windows": ["MIDDAY"]}))
    assert skip is None
    assert '2026-07-20T11:00:00' in body['start']['dateTime']

def test_window_afternoon_creates_timed_event():
    body, skip = _build_event_body(build_mock_item({"visit_windows": ["AFTERNOON"]}))
    assert skip is None
    assert '2026-07-20T14:00:00' in body['start']['dateTime']

def test_window_evening_creates_timed_event():
    body, skip = _build_event_body(build_mock_item({"visit_windows": ["EVENING"]}))
    assert skip is None
    assert '2026-07-20T17:00:00' in body['start']['dateTime']

def test_window_anytime_creates_all_day():
    body, skip = _build_event_body(build_mock_item({"visit_windows": ["ANYTIME"]}))
    assert skip is None
    assert 'date' in body['start']
    assert body['start']['date'] == '2026-07-20'
    assert 'All Day' in body['summary']

def test_multi_window_uses_first():
    body, skip = _build_event_body(build_mock_item({"visit_windows": ["AFTERNOON", "EVENING"]}))
    assert skip is None
    assert '2026-07-20T14:00:00' in body['start']['dateTime']

def test_scheduled_time_overrides_window():
    body, skip = _build_event_body(build_mock_item({
        "visit_windows": ["MORNING"],
        "scheduled_time": "15:00"
    }))
    assert skip is None
    assert '2026-07-20T15:00:00' in body['start']['dateTime']
    assert 'Exact Time' in body['summary']

def test_service_type_duration_walk_30():
    body, skip = _build_event_body(build_mock_item({
        "visit_windows": ["MORNING"],
        "service_type": "WALK_30MIN"
    }))
    assert skip is None
    assert '2026-07-20T08:30:00' in body['end']['dateTime']

def test_service_type_duration_dropin_3hr():
    body, skip = _build_event_body(build_mock_item({
        "visit_windows": ["MIDDAY"],
        "service_type": "DROPIN_3HR"
    }))
    assert skip is None
    # 11:00 + 3 hours = 14:00
    assert '2026-07-20T14:00:00' in body['end']['dateTime']

def test_service_type_duration_overnight():
    body, skip = _build_event_body(build_mock_item({
        "visit_windows": ["EVENING"],
        "service_type": "OVERNIGHT"
    }))
    assert skip is None
    # 17:00 + 12 hours = 05:00 next day
    assert '2026-07-21T05:00:00' in body['end']['dateTime']

def test_color_id_walk():
    body, skip = _build_event_body(build_mock_item({"service_type": "WALK_30MIN"}))
    assert skip is None
    assert body['colorId'] == '9'

def test_color_id_dropin():
    body, skip = _build_event_body(build_mock_item({"service_type": "DROPIN_1HR"}))
    assert skip is None
    assert body['colorId'] == '7'

def test_color_id_overnight():
    body, skip = _build_event_body(build_mock_item({"service_type": "OVERNIGHT"}))
    assert skip is None
    assert body['colorId'] == '6'

def test_title_format_with_emoji():
    body, skip = _build_event_body(build_mock_item({
        "pet_names": "Bella",
        "service_type": "WALK_60MIN",
        "visit_windows": ["MORNING"]
    }))
    assert skip is None
    assert body['summary'] == '🐾 Bella \u2014 60-Min Walk (Morning)'

def test_description_includes_client_phone():
    body, skip = _build_event_body(build_mock_item({
        "client_phone": "555-1234"
    }))
    assert skip is None
    assert 'Phone: 555-1234' in body['description']

def test_description_includes_source_label():
    body, skip = _build_event_body(build_mock_item({
        "source": "admin_created"
    }))
    assert skip is None
    assert 'Source: Admin Created' in body['description']
    
    body2, skip2 = _build_event_body(build_mock_item({}))
    assert skip2 is None
    assert 'Source: Client Booking' in body2['description']

def test_legacy_visit_window_string_fallback():
    body, skip = _build_event_body(build_mock_item({"visit_window": "MORNING"}))
    assert skip is None
    assert '2026-07-20T08:00:00' in body['start']['dateTime']

def test_no_window_no_time_still_all_day():
    body, skip = _build_event_body(build_mock_item())
    assert skip is None
    assert 'date' in body['start']
    assert body['start']['date'] == '2026-07-20'
    assert 'All Day' in body['summary']
