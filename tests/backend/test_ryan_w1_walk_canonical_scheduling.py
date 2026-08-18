"""Ryan W1 20-Minute Walk canonical scheduling coverage."""

import json
from unittest.mock import MagicMock, patch

import pytest

from common.check_in import (
    BookingWindowValidationError,
    validate_booking_window_fields,
)
from common.google_calendar import _build_event_body
from handlers.intake_handler import handler as intake_handler
from handlers.job_handler import handler as job_handler


def walk_record(window="MORNING", **overrides):
    record = {
        "service_type": "WALK_20MIN",
        "visit_windows": [window],
    }
    record.update(overrides)
    return record


@pytest.mark.parametrize("window", ["MORNING", "MIDDAY", "EVENING"])
def test_valid_walk_contract_selections(window):
    assert validate_booking_window_fields(walk_record(window)) == {
        "visits_per_day": None,
        "visit_windows": [window],
        "visit_window": window,
    }


@pytest.mark.parametrize(
    ("visit_windows", "overrides", "message"),
    [
        (None, {}, "requires exactly one"),
        ([], {}, "requires exactly one"),
        (["MORNING", "MIDDAY"], {}, "requires exactly one"),
        (["MORNING", "MORNING"], {}, "distinct"),
        (["AFTERNOON"], {}, "not allowed"),
        (["ANYTIME"], {}, "not allowed"),
        (["UNKNOWN"], {}, "not allowed"),
        (["MORNING"], {"visits_per_day": 1}, "does not accept"),
    ],
)
def test_invalid_walk_contract_selections(visit_windows, overrides, message):
    record = walk_record(**overrides)
    if visit_windows is None:
        record.pop("visit_windows")
    else:
        record["visit_windows"] = visit_windows
    with pytest.raises(BookingWindowValidationError, match=message):
        validate_booking_window_fields(record)


def _run_walk_job(day_count, window="MIDDAY", request_id="req-w1"):
    dates = [f"2026-09-{index + 1:02d}" for index in range(day_count)]
    request = {
        "PK": f"REQ#{request_id}",
        "SK": "CLIENT#client-w1",
        "request_id": request_id,
        "client_id": "client-w1",
        "company_id": "test-company",
        "client_name": "Walk Client",
        "pet_names": "Scout",
        "service_type": "WALK_20MIN",
        "visit_windows": [window],
        "visit_window": window,
        "selected_dates": dates,
        "start_date": dates[0],
        "end_date": dates[-1],
    }
    jobs = {}

    def get_item(pk, _sk):
        if pk == request["PK"]:
            return request
        return jobs.get(pk)

    def put_item(item):
        jobs[item["PK"]] = dict(item)
        return True

    calendar = MagicMock(side_effect=lambda item: {
        "event_id": f"event-{item['occurrence_date']}-{item['occurrence_window']}"
    })
    table = MagicMock()

    def update_item(**kwargs):
        key = kwargs["Key"]
        if key["PK"].startswith("JOB#") and ":gid" in kwargs["ExpressionAttributeValues"]:
            jobs[key["PK"]]["google_event_id"] = kwargs["ExpressionAttributeValues"][":gid"]

    table.update_item.side_effect = update_item
    patches = [
        patch("handlers.job_handler.get_item", side_effect=get_item),
        patch("handlers.job_handler.put_item", side_effect=put_item),
        patch("handlers.job_handler.table", table),
        patch("common.pet_profile.create_or_link_pets_from_request", return_value={"pet_ids": ["pet-w1"]}),
        patch("common.google_calendar.sync_calendar_event", calendar),
        patch("handlers.job_handler.time.sleep"),
    ]
    for context in patches:
        context.__enter__()
    try:
        result = job_handler({"request_id": request_id, "client_id": "client-w1"}, None)
        return request, jobs, result, calendar, patches
    except Exception:
        for context in reversed(patches):
            context.__exit__(None, None, None)
        raise


@pytest.mark.parametrize("day_count", [1, 3, 7])
def test_walk_creates_one_deterministic_child_per_selected_date(day_count):
    request, jobs, result, calendar, patches = _run_walk_job(day_count)
    try:
        assert len(result["job_ids"]) == day_count
        assert len(jobs) == day_count
        assert calendar.call_count == day_count
        assert all(job["visit_windows"] == ["MIDDAY"] for job in jobs.values())
        assert all(job["occurrence_window"] == "MIDDAY" for job in jobs.values())
        assert all(job["start_time"] == "10:30" for job in jobs.values())
        assert all("visits_per_day" not in job for job in jobs.values())
        assert len({job["calendar_event_id"] for job in jobs.values()}) == day_count

        first_ids = list(result["job_ids"])
        replay = job_handler(
            {"request_id": request["request_id"], "client_id": request["client_id"]}, None
        )
        assert replay["job_ids"] == first_ids
        assert len(jobs) == day_count
        assert calendar.call_count == day_count
    finally:
        for context in reversed(patches):
            context.__exit__(None, None, None)


@pytest.mark.parametrize(
    ("window", "start", "end"),
    [
        ("MORNING", "06:30:00", "06:50:00"),
        ("MIDDAY", "10:30:00", "10:50:00"),
        ("EVENING", "18:00:00", "18:20:00"),
    ],
)
def test_walk_calendar_uses_canonical_start_and_twenty_minute_duration(window, start, end):
    body, skip = _build_event_body({
        "request_id": f"req-w1-{window}",
        "client_name": "Walk Client",
        "pet_names": "Scout",
        "service_type": "WALK_20MIN",
        "scheduled_date": "2026-09-01",
        "visit_windows": [window],
        "occurrence_window": window,
    })
    assert skip is None
    assert body["start"]["dateTime"].endswith(start)
    assert body["end"]["dateTime"].endswith(end)


def test_historical_walk_without_occurrence_marker_keeps_legacy_calendar_timing():
    body, skip = _build_event_body({
        "request_id": "req-historical-walk",
        "client_name": "Historical Walk Client",
        "pet_names": "Scout",
        "service_type": "WALK_20MIN",
        "start_date": "2026-09-01",
        "visit_windows": ["MORNING"],
    })
    assert skip is None
    assert body["start"]["dateTime"].endswith("08:00:00")
    assert body["end"]["dateTime"].endswith("08:20:00")


def _admin_event(body):
    return {
        "requestContext": {"authorizer": {"claims": {
            "email": "owner@example.com", "cognito:groups": "owner"
        }}},
        "httpMethod": "POST",
        "path": "/requests",
        "body": json.dumps(body),
    }


def test_admin_walk_write_persists_canonical_window_and_defers_parent_calendar():
    saved = {}
    body = {
        "source": "admin_created",
        "client_id": "client-w1",
        "client_name": "Walk Client",
        "pet_names": "Scout",
        "service_type": "WALK_20MIN",
        "visit_windows": ["EVENING"],
        "start_date": "2026-09-01",
        "is_test_booking": True,
    }
    with patch("handlers.intake_handler.get_item", return_value={"company_id": "tog_and_dogs"}), patch(
        "handlers.intake_handler.put_item", side_effect=lambda item: saved.update(item) or True
    ), patch("handlers.intake_handler.table"), patch("boto3.client"), patch(
        "common.google_calendar.sync_calendar_event"
    ) as calendar:
        response = intake_handler(_admin_event(body), None)

    assert response["statusCode"] == 200
    assert saved["visit_windows"] == ["EVENING"]
    assert saved["visit_window"] == "EVENING"
    assert "visits_per_day" not in saved
    calendar.assert_not_called()


def test_invalid_walk_write_is_rejected_before_persistence():
    body = {
        "source": "admin_created",
        "client_id": "client-w1",
        "client_name": "Walk Client",
        "pet_names": "Scout",
        "service_type": "WALK_20MIN",
        "visit_windows": ["ANYTIME"],
        "start_date": "2026-09-01",
    }
    with patch("handlers.intake_handler.put_item") as put:
        response = intake_handler(_admin_event(body), None)
    assert response["statusCode"] == 400
    assert "not allowed" in response["body"]
    put.assert_not_called()
