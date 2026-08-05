"""Phase 24A-2C.2D.1 service contract/calendar parity characterization."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from common.google_calendar import _build_event_body


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICE_CONTRACT_PATH = ROOT_DIR / "shared" / "constants" / "service-types.json"
SERVICE_CONTRACT = json.loads(SERVICE_CONTRACT_PATH.read_text(encoding="utf-8"))
CANONICAL_SERVICES = SERVICE_CONTRACT["services"]
MISSING = object()


def build_timed_item(service_type=MISSING, **overrides):
    item = {
        "request_id": "phase24a-duration-parity",
        "client_name": "Test Client",
        "pet_names": "Rex",
        "start_date": "2030-01-15",
        "scheduled_time": "09:15",
    }
    if service_type is not MISSING:
        item["service_type"] = service_type
    item.update(overrides)
    return item


def build_event(item):
    body, skip_reason = _build_event_body(item)
    assert skip_reason is None
    assert body is not None
    return body


def timed_bounds(body):
    return (
        datetime.fromisoformat(body["start"]["dateTime"]),
        datetime.fromisoformat(body["end"]["dateTime"]),
    )


@pytest.mark.parametrize(
    ("service_type", "metadata"),
    list(CANONICAL_SERVICES.items()),
    ids=CANONICAL_SERVICES.keys(),
)
def test_canonical_timed_duration_matches_contract(service_type, metadata):
    body = build_event(build_timed_item(service_type))
    start, end = timed_bounds(body)

    assert start == datetime(2030, 1, 15, 9, 15)
    assert end - start == timedelta(minutes=metadata["durationMinutes"])
    assert body["start"]["timeZone"] == "America/New_York"
    assert body["end"]["timeZone"] == "America/New_York"


@pytest.mark.parametrize(
    ("service_type", "metadata"),
    list(CANONICAL_SERVICES.items()),
    ids=CANONICAL_SERVICES.keys(),
)
def test_canonical_calendar_friendly_name_matches_contract_label(service_type, metadata):
    body = build_event(build_timed_item(service_type))

    assert body["summary"] == f"🐾 Rex — {metadata['label']} (Exact Time)"
    assert f"Service: {metadata['label']}\n" in body["description"]


@pytest.mark.parametrize(
    ("override", "expected_minutes"),
    [
        pytest.param(75, 75, id="numeric-override"),
        pytest.param("90", 90, id="numeric-string-override"),
    ],
)
def test_truthy_scheduled_duration_overrides_canonical_default(override, expected_minutes):
    body = build_event(build_timed_item("WALK_30MIN", scheduled_duration=override))
    start, end = timed_bounds(body)

    assert end - start == timedelta(minutes=expected_minutes)


@pytest.mark.parametrize(
    "override",
    [
        pytest.param(MISSING, id="missing"),
        pytest.param(0, id="zero"),
        pytest.param("", id="empty-string"),
        pytest.param(None, id="null"),
    ],
)
def test_falsey_scheduled_duration_falls_through_to_canonical_default(override):
    item = build_timed_item("WALK_30MIN")
    if override is not MISSING:
        item["scheduled_duration"] = override

    body = build_event(item)
    start, end = timed_bounds(body)

    assert end - start == timedelta(
        minutes=CANONICAL_SERVICES["WALK_30MIN"]["durationMinutes"]
    )


@pytest.mark.parametrize(
    "override",
    [
        pytest.param(MISSING, id="missing"),
        pytest.param(0, id="zero"),
        pytest.param("", id="empty-string"),
        pytest.param(None, id="null"),
    ],
)
def test_falsey_scheduled_duration_falls_through_to_unresolved_fallback(override):
    item = build_timed_item("HOUSE_SITTING")
    if override is not MISSING:
        item["scheduled_duration"] = override

    body = build_event(item)
    start, end = timed_bounds(body)

    assert end - start == timedelta(minutes=60)


@pytest.mark.parametrize(
    ("case_id", "service_type", "expected_label"),
    [
        ("dog-walking", "DOG_WALKING", "DOG_WALKING"),
        ("walking", "WALKING", "WALKING"),
        ("other", "OTHER", "OTHER"),
        ("unknown", "HOUSE_SITTING", "HOUSE_SITTING"),
        ("lowercase", "walk_30min", "walk_30min"),
        ("mixed-case", "Walk_30Min", "Walk_30Min"),
        ("null", None, "None"),
        ("blank", "", ""),
        ("missing", MISSING, "Service"),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_unresolved_service_uses_exact_current_fallback(case_id, service_type, expected_label):
    del case_id
    body = build_event(build_timed_item(service_type))
    start, end = timed_bounds(body)

    assert end - start == timedelta(minutes=60)
    assert body["summary"] == f"🐾 Rex — {expected_label} (Exact Time)"
    assert f"Service: {expected_label}\n" in body["description"]
    assert body["colorId"] == "8"


@pytest.mark.parametrize(
    ("service_type", "expected_color"),
    [
        ("WALK_30MIN", "9"),
        ("WALK_60MIN", "9"),
        ("DROPIN_1HR", "7"),
        ("DROPIN_3HR", "7"),
        ("OVERNIGHT", "6"),
        ("PET_SITTING", "10"),
        ("MEET_GREET", "3"),
    ],
)
def test_canonical_calendar_colors_remain_backend_characterization(service_type, expected_color):
    body = build_event(build_timed_item(service_type))

    assert body["colorId"] == expected_color


@pytest.mark.parametrize(
    ("case_id", "service_type"),
    [
        ("short-canonical", "WALK_30MIN"),
        ("overnight-canonical", "OVERNIGHT"),
        ("legacy", "DOG_WALKING"),
        ("missing", MISSING),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_all_day_shape_is_independent_of_service_duration(case_id, service_type):
    del case_id
    item = build_timed_item(service_type, visit_windows=["ANYTIME"])
    item.pop("scheduled_time")

    body = build_event(item)

    assert body["start"] == {"date": "2030-01-15"}
    assert body["end"] == {"date": "2030-01-16"}
    assert "All Day" in body["summary"]


@pytest.mark.parametrize(
    ("service_type", "window", "expected_start"),
    [
        ("WALK_30MIN", "MORNING", datetime(2030, 1, 15, 8, 0)),
        ("DROPIN_1HR", "MIDDAY", datetime(2030, 1, 15, 11, 0)),
        ("DROPIN_3HR", "AFTERNOON", datetime(2030, 1, 15, 14, 0)),
        ("MEET_GREET", "EVENING", datetime(2030, 1, 15, 17, 0)),
    ],
)
def test_window_derived_start_retains_current_time_and_applies_contract_duration(
    service_type,
    window,
    expected_start,
):
    item = build_timed_item(
        service_type,
        visit_windows=[window],
        window_type="UNRELATED_WINDOW_TYPE",
    )
    item.pop("scheduled_time")

    body = build_event(item)
    start, end = timed_bounds(body)

    assert start == expected_start
    assert end - start == timedelta(
        minutes=CANONICAL_SERVICES[service_type]["durationMinutes"]
    )
    assert f"({window.capitalize()})" in body["summary"]
    assert body["start"]["timeZone"] == "America/New_York"
    assert body["end"]["timeZone"] == "America/New_York"
