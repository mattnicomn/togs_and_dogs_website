"""Ryan Slice B Check-In validation, job, Calendar, and compatibility coverage."""

import json
import io
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from common.check_in import CheckInValidationError, validate_check_in_booking_fields
from common.google_calendar import _build_event_body, sync_calendar_event
from handlers.intake_handler import handler as intake_handler
from handlers.job_handler import handler as job_handler


def check_in_record(visits_per_day=1, visit_windows=None, **overrides):
    record = {
        "service_type": "CHECK_IN",
        "visits_per_day": visits_per_day,
        "visit_windows": visit_windows if visit_windows is not None else ["MORNING"],
    }
    record.update(overrides)
    return record


@pytest.mark.parametrize(
    ("visits_per_day", "windows", "canonical"),
    [
        (1, ["MORNING"], ["MORNING"]),
        (2, ["EVENING", "MORNING"], ["MORNING", "EVENING"]),
        (3, ["EVENING", "MORNING", "MIDDAY"], ["MORNING", "MIDDAY", "EVENING"]),
    ],
)
def test_valid_check_in_contract_selections(visits_per_day, windows, canonical):
    fields = validate_check_in_booking_fields(check_in_record(visits_per_day, windows))
    assert fields == {
        "visits_per_day": visits_per_day,
        "visit_windows": canonical,
        "visit_window": canonical[0],
    }


@pytest.mark.parametrize(
    ("visits_per_day", "windows", "message"),
    [
        (2, ["MORNING", "MORNING"], "distinct"),
        (2, ["MORNING"], "count"),
        (1, ["AFTERNOON"], "not allowed"),
        (1, ["UNKNOWN"], "not allowed"),
        (0, ["MORNING"], "not allowed"),
        (4, ["MORNING", "MIDDAY", "EVENING", "UNKNOWN"], "not allowed"),
        (None, ["MORNING"], "requires visits_per_day"),
        (1, None, "requires visit_windows"),
    ],
)
def test_invalid_check_in_contract_selections(visits_per_day, windows, message):
    record = check_in_record(visits_per_day, windows)
    if windows is None:
        record.pop("visit_windows")
    with pytest.raises(CheckInValidationError, match=message):
        validate_check_in_booking_fields(record)


def _run_check_in_job(dates, windows, *, request_id="req-slice-b"):
    request = {
        "PK": f"REQ#{request_id}",
        "SK": "CLIENT#client-slice-b",
        "request_id": request_id,
        "client_id": "client-slice-b",
        "company_id": "test-company",
        "client_name": "Slice B Client",
        "pet_names": "Scout",
        "service_type": "CHECK_IN",
        "visits_per_day": len(windows),
        "visit_windows": list(windows),
        "visit_window": windows[0],
        "selected_dates": list(dates),
        "start_date": dates[0],
        "end_date": dates[-1],
    }
    jobs = {}

    def get_item(pk, sk):
        if pk == request["PK"]:
            return request
        return jobs.get(pk)

    def put_item(item):
        jobs[item["PK"]] = dict(item)
        return True

    def calendar_sync(item, **_kwargs):
        return {
            "event_id": (
                f"event-{item['occurrence_date']}-{item['occurrence_window']}"
            )
        }

    table = MagicMock()

    def update_item(**kwargs):
        key = kwargs["Key"]
        if key["PK"].startswith("JOB#") and ":gid" in kwargs["ExpressionAttributeValues"]:
            jobs[key["PK"]]["google_event_id"] = kwargs["ExpressionAttributeValues"][":gid"]

    table.update_item.side_effect = update_item
    patches = (
        patch("handlers.job_handler.get_item", side_effect=get_item),
        patch("handlers.job_handler.put_item", side_effect=put_item),
        patch("handlers.job_handler.table", table),
        patch(
            "common.pet_profile.create_or_link_pets_from_request",
            return_value={"pet_ids": ["pet-slice-b"]},
        ),
        patch("common.google_calendar.sync_calendar_event", side_effect=calendar_sync),
        patch("handlers.job_handler.time.sleep"),
    )
    entered = [context.__enter__() for context in patches]
    try:
        result = job_handler(
            {"request_id": request_id, "client_id": "client-slice-b"}, None
        )
        return request, jobs, result, table, entered[4], patches
    except Exception:
        for context in reversed(patches):
            context.__exit__(None, None, None)
        raise


def _close_patches(patches):
    for context in reversed(patches):
        context.__exit__(None, None, None)


@pytest.mark.parametrize(
    ("day_count", "windows", "expected"),
    [
        (1, ["MORNING"], 1),
        (1, ["MORNING", "EVENING"], 2),
        (1, ["MORNING", "MIDDAY", "EVENING"], 3),
        (3, ["MORNING"], 3),
        (3, ["MORNING", "EVENING"], 6),
        (3, ["MORNING", "MIDDAY", "EVENING"], 9),
        (7, ["MORNING", "MIDDAY", "EVENING"], 21),
    ],
)
def test_check_in_date_window_job_multiplication(day_count, windows, expected):
    dates = [f"2026-08-{20 + index:02d}" for index in range(day_count)]
    request, jobs, result, table, calendar, patches = _run_check_in_job(dates, windows)
    try:
        assert len(result["job_ids"]) == expected
        assert len(jobs) == expected
        assert calendar.call_count == expected
        assert len(set(result["job_ids"])) == expected
        assert sorted(job["occurrence_index"] for job in jobs.values()) == list(
            range(1, expected + 1)
        )
        assert all(job["total_occurrences"] == expected for job in jobs.values())
        assert all(job["calendar_event_id"].startswith("td") for job in jobs.values())
        assert len({job["calendar_event_id"] for job in jobs.values()}) == expected
    finally:
        _close_patches(patches)


def test_check_in_same_date_windows_are_distinct_and_replay_is_idempotent():
    request, jobs, first, table, calendar, patches = _run_check_in_job(
        ["2026-08-20"], ["MORNING", "EVENING"]
    )
    try:
        first_ids = list(first["job_ids"])
        assert len(first_ids) == 2
        assert first_ids[0] != first_ids[1]
        assert {job["occurrence_window"] for job in jobs.values()} == {
            "MORNING",
            "EVENING",
        }

        replay = job_handler(
            {"request_id": request["request_id"], "client_id": request["client_id"]},
            None,
        )
        assert replay["job_ids"] == first_ids
        assert len(jobs) == 2
        assert calendar.call_count == 2

        request["job_ids"] = first_ids
        request["job_id"] = first_ids[0]
        linked_replay = job_handler(
            {"request_id": request["request_id"], "client_id": request["client_id"]},
            None,
        )
        assert linked_replay["status"] == "EXISTING_JOBS_SKIPPED"
        assert calendar.call_count == 2
    finally:
        _close_patches(patches)


def test_each_check_in_child_has_one_window_and_one_calendar_event():
    _, jobs, result, _, calendar, patches = _run_check_in_job(
        ["2026-08-20", "2026-08-21"], ["MORNING", "EVENING"]
    )
    try:
        assert len(result["job_ids"]) == 4
        assert calendar.call_count == 4
        assert all(job["visit_windows"] == [job["occurrence_window"]] for job in jobs.values())
        assert all(job["google_event_id"] for job in jobs.values())
    finally:
        _close_patches(patches)


def test_deterministic_calendar_insert_conflict_resolves_to_existing_event():
    item = {
        "request_id": "req-calendar-replay",
        "company_id": "test-company",
        "client_name": "Calendar Client",
        "pet_names": "Scout",
        "service_type": "CHECK_IN",
        "scheduled_date": "2026-08-20",
        "visit_windows": ["MORNING"],
        "calendar_event_id": "td0123456789abcdef0123456789abcdef",
    }
    conflict = urllib.error.HTTPError(
        "https://calendar.invalid",
        409,
        "Conflict",
        {},
        io.BytesIO(b"{}"),
    )
    with patch("common.google_calendar.resolve_google_token_secret_name", return_value="secret"), patch(
        "common.google_calendar._get_valid_token", return_value="token"
    ), patch("common.google_calendar._execute_calendar_api", side_effect=conflict):
        result = sync_calendar_event(item)

    assert result == {
        "status": "calendar_existing",
        "event_id": item["calendar_event_id"],
        "message": "Calendar event already exists.",
    }


@pytest.mark.parametrize(
    ("window", "start", "end"),
    [
        ("MORNING", "06:30:00", "07:00:00"),
        ("MIDDAY", "10:30:00", "11:00:00"),
        ("EVENING", "18:00:00", "18:30:00"),
    ],
)
def test_check_in_calendar_uses_canonical_start_and_duration(window, start, end):
    item = {
        "request_id": "req-calendar",
        "client_name": "Calendar Client",
        "pet_names": "Scout",
        "service_type": "CHECK_IN",
        "scheduled_date": "2026-08-20",
        "visit_window": window,
        "visit_windows": [window],
    }
    body, skip = _build_event_body(item)
    assert skip is None
    assert body["start"]["dateTime"].endswith(start)
    assert body["end"]["dateTime"].endswith(end)


def test_non_check_in_services_do_not_receive_check_in_transaction_rules():
    assert validate_check_in_booking_fields({"service_type": "WALK_20MIN"}) is None
    assert validate_check_in_booking_fields({"service_type": "OVERNIGHT"}) is None

    body, skip = _build_event_body(
        {
            "request_id": "req-overnight",
            "client_name": "Legacy Client",
            "pet_names": "Scout",
            "service_type": "OVERNIGHT",
            "start_date": "2026-08-20",
            "visit_windows": ["MORNING"],
        }
    )
    assert skip is None
    assert body["start"]["dateTime"].endswith("08:00:00")


@pytest.mark.parametrize("window", ["AFTERNOON", "ANYTIME"])
def test_legacy_windows_remain_calendar_readable(window):
    body, skip = _build_event_body(
        {
            "request_id": f"req-{window}",
            "client_name": "Legacy Client",
            "pet_names": "Scout",
            "service_type": "PET_SITTING",
            "start_date": "2026-08-20",
            "visit_windows": [window],
        }
    )
    assert skip is None
    if window == "AFTERNOON":
        assert body["start"]["dateTime"].endswith("14:00:00")
    else:
        assert body["start"]["date"] == "2026-08-20"


def _admin_event(body):
    return {
        "requestContext": {
            "authorizer": {
                "claims": {"email": "owner@example.com", "cognito:groups": "owner"}
            }
        },
        "httpMethod": "POST",
        "path": "/requests",
        "body": json.dumps(body),
    }


def test_admin_check_in_write_persists_model_and_defers_parent_calendar():
    body = {
        "source": "admin_created",
        "client_id": "client-slice-b",
        "client_name": "Slice B Client",
        "client_email": "client@example.com",
        "pet_names": "Scout",
        "service_type": "CHECK_IN",
        "visits_per_day": 2,
        "visit_windows": ["EVENING", "MORNING"],
        "start_date": "2026-08-20",
        "is_test_booking": True,
    }
    saved = {}

    def capture(item):
        saved.update(item)
        return True

    with patch("handlers.intake_handler.get_item", return_value={"company_id": "tog_and_dogs"}), patch(
        "handlers.intake_handler.put_item", side_effect=capture
    ), patch("handlers.intake_handler.table"), patch("boto3.client"), patch(
        "common.google_calendar.sync_calendar_event"
    ) as calendar:
        response = intake_handler(_admin_event(body), None)

    assert response["statusCode"] == 200
    assert saved["visits_per_day"] == 2
    assert saved["visit_windows"] == ["MORNING", "EVENING"]
    assert saved["visit_window"] == "MORNING"
    calendar.assert_not_called()


def test_admin_invalid_check_in_write_is_rejected_before_persistence():
    body = {
        "source": "admin_created",
        "client_id": "client-slice-b",
        "client_name": "Slice B Client",
        "pet_names": "Scout",
        "service_type": "CHECK_IN",
        "visits_per_day": 2,
        "visit_windows": ["MORNING"],
        "start_date": "2026-08-20",
    }
    with patch("handlers.intake_handler.put_item") as put:
        response = intake_handler(_admin_event(body), None)
    assert response["statusCode"] == 400
    assert "count must equal" in response["body"]
    put.assert_not_called()


def test_client_portal_check_in_write_accepts_and_persists_contract_fields():
    body = {
        "client_name": "Slice B Client",
        "client_email": "client@example.com",
        "pet_names": "Scout",
        "service_type": "CHECK_IN",
        "visits_per_day": 3,
        "visit_windows": ["EVENING", "MORNING", "MIDDAY"],
        "start_date": "2026-08-20",
        "is_test_booking": True,
    }
    event = _admin_event(body)
    event["path"] = "/client/requests"
    event["requestContext"]["authorizer"]["claims"]["cognito:groups"] = "client"
    saved = {}

    def capture(item):
        saved.update(item)
        return True

    profile = {"is_active": True, "portal_enabled": True, "company_id": "tog_and_dogs"}
    with patch("common.entitlement.require_active_tenant", return_value=None), patch(
        "common.auth.resolve_client_identity", return_value="client-slice-b"
    ), patch("common.auth.get_current_company_id", return_value="tog_and_dogs"), patch(
        "handlers.intake_handler.get_item", return_value=profile
    ), patch("handlers.intake_handler.put_item", side_effect=capture):
        response = intake_handler(event, None)

    assert response["statusCode"] == 200
    assert saved["workflow_type"] == "VISIT_BOOKING"
    assert saved["visits_per_day"] == 3
    assert saved["visit_windows"] == ["MORNING", "MIDDAY", "EVENING"]


def test_job_handler_rejects_invalid_persisted_check_in_before_side_effects():
    request = {
        "request_id": "req-invalid-check-in",
        "client_id": "client-slice-b",
        "service_type": "CHECK_IN",
        "visits_per_day": 2,
        "visit_windows": ["MORNING"],
    }
    with patch("handlers.job_handler.get_item", return_value=request), patch(
        "handlers.job_handler.put_item"
    ) as put, patch("common.pet_profile.create_or_link_pets_from_request") as pets:
        result = job_handler(
            {"request_id": request["request_id"], "client_id": request["client_id"]},
            None,
        )

    assert "count must equal" in result["error"]
    put.assert_not_called()
    pets.assert_not_called()
