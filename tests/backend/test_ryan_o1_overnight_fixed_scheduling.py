"""Ryan O1 fixed 21:00-to-07:00 Overnight scheduling coverage."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch
from zoneinfo import ZoneInfo

import pytest

from common.check_in import BookingWindowValidationError, validate_booking_window_fields
from common.google_calendar import _build_event_body
from handlers.assignment_handler import handler as assignment_handler
from handlers.cancellation_handler import handle_admin_decision
from handlers.intake_handler import handler as intake_handler
from handlers.job_handler import handler as job_handler


EXPECTED_FIXED_FIELDS = {
    "canonical_schedule_mode": "fixed",
    "canonical_fixed_start_time": "21:00",
    "canonical_fixed_end_time": "07:00",
    "canonical_crosses_midnight": True,
    "scheduled_duration": 600,
}


def test_valid_overnight_derives_fixed_schedule_without_client_scheduling_fields():
    assert validate_booking_window_fields({"service_type": "OVERNIGHT"}) == EXPECTED_FIXED_FIELDS


@pytest.mark.parametrize(
    "field,value",
    [
        ("visit_windows", []),
        ("visit_window", "ANYTIME"),
        ("visits_per_day", 1),
        ("preferred_time", "21:00"),
        ("scheduled_time", "21:00"),
        ("start_time", "21:00"),
        ("end_time", "07:00"),
        ("fixed_start_time", "21:00"),
        ("fixed_end_time", "07:00"),
    ],
)
def test_overnight_rejects_client_scheduling_fields(field, value):
    with pytest.raises(BookingWindowValidationError, match="fixed canonical schedule"):
        validate_booking_window_fields({"service_type": "OVERNIGHT", field: value})


def test_unmarked_historical_overnight_is_not_reinterpreted_at_persisted_boundary():
    assert validate_booking_window_fields(
        {
            "service_type": "OVERNIGHT",
            "visit_window": "ANYTIME",
            "visit_windows": ["ANYTIME"],
        },
        persisted=True,
    ) is None


def _admin_event(body):
    return {
        "requestContext": {"authorizer": {"claims": {
            "email": "owner@example.com", "cognito:groups": "owner"
        }}},
        "httpMethod": "POST",
        "path": "/requests",
        "body": json.dumps(body),
    }


def test_admin_overnight_write_derives_marker_and_defers_parent_calendar():
    saved = {}
    body = {
        "source": "admin_created",
        "client_id": "client-o1",
        "client_name": "Overnight Client",
        "pet_names": "Scout",
        "service_type": "OVERNIGHT",
        "selected_dates": ["2026-09-10"],
        "start_date": "2026-09-10",
        "is_test_booking": True,
    }
    with patch("handlers.intake_handler.get_item", return_value={"company_id": "tog_and_dogs"}), patch(
        "handlers.intake_handler.put_item", side_effect=lambda item: saved.update(item) or True
    ), patch("handlers.intake_handler.table"), patch("boto3.client"), patch(
        "common.google_calendar.sync_calendar_event"
    ) as calendar:
        response = intake_handler(_admin_event(body), None)

    assert response["statusCode"] == 200
    assert all(saved[key] == value for key, value in EXPECTED_FIXED_FIELDS.items())
    assert "visit_windows" not in saved
    assert "visit_window" not in saved
    assert "visits_per_day" not in saved
    assert "preferred_time" not in saved
    assert saved["status"] == "APPROVED"
    assert saved["workflow_type"] == "VISIT_BOOKING"
    assert saved["source"] == "admin_created"
    calendar.assert_not_called()


def test_invalid_overnight_write_is_rejected_before_persistence():
    body = {
        "source": "admin_created",
        "client_id": "client-o1",
        "client_name": "Overnight Client",
        "pet_names": "Scout",
        "service_type": "OVERNIGHT",
        "start_date": "2026-09-10",
        "visit_windows": ["EVENING"],
    }
    with patch("handlers.intake_handler.put_item") as put:
        response = intake_handler(_admin_event(body), None)
    assert response["statusCode"] == 400
    assert "fixed canonical schedule" in response["body"]
    put.assert_not_called()


def _run_overnight_job(day_count, request_id="req-o1"):
    dates = [f"2026-09-{index + 10:02d}" for index in range(day_count)]
    request = {
        "PK": f"REQ#{request_id}",
        "SK": "CLIENT#client-o1",
        "request_id": request_id,
        "client_id": "client-o1",
        "company_id": "test-company",
        "client_name": "Overnight Client",
        "pet_names": "Scout",
        "service_type": "OVERNIGHT",
        "selected_dates": dates,
        "start_date": dates[0],
        "end_date": dates[-1],
        **EXPECTED_FIXED_FIELDS,
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
        "event_id": f"event-{item['occurrence_date']}"
    })
    table = MagicMock()

    def update_item(**kwargs):
        key = kwargs["Key"]
        values = kwargs.get("ExpressionAttributeValues", {})
        if key["PK"].startswith("JOB#") and ":gid" in values:
            jobs[key["PK"]]["google_event_id"] = values[":gid"]

    table.update_item.side_effect = update_item
    contexts = [
        patch("handlers.job_handler.get_item", side_effect=get_item),
        patch("handlers.job_handler.put_item", side_effect=put_item),
        patch("handlers.job_handler.table", table),
        patch("common.pet_profile.create_or_link_pets_from_request", return_value={"pet_ids": ["pet-o1"]}),
        patch("common.google_calendar.sync_calendar_event", calendar),
        patch("handlers.job_handler.time.sleep"),
    ]
    for context in contexts:
        context.__enter__()
    return request, jobs, calendar, contexts


@pytest.mark.parametrize("day_count", [1, 3, 7])
def test_overnight_creates_one_deterministic_child_per_selected_start_date(day_count):
    request, jobs, calendar, contexts = _run_overnight_job(day_count)
    try:
        result = job_handler({"request_id": request["request_id"], "client_id": request["client_id"]}, None)
        assert len(result["job_ids"]) == day_count
        assert len(jobs) == day_count
        assert calendar.call_count == day_count
        for job in jobs.values():
            start = datetime.strptime(job["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(job["end_date"], "%Y-%m-%d").date()
            assert (end - start).days == 1
            assert job["start_time"] == "21:00"
            assert job["end_time"] == "07:00"
            assert job["occurrence_schedule_mode"] == "fixed"
            assert job["scheduled_duration"] == 600
            assert "visit_window" not in job
            assert "visit_windows" not in job
        first_ids = list(result["job_ids"])
        replay = job_handler({"request_id": request["request_id"], "client_id": request["client_id"]}, None)
        assert replay["job_ids"] == first_ids
        assert len(jobs) == day_count
        assert calendar.call_count == day_count
    finally:
        for context in reversed(contexts):
            context.__exit__(None, None, None)


@pytest.mark.parametrize(
    "start_date,end_date,elapsed_hours",
    [
        ("2026-09-10", "2026-09-11", 10),
        ("2026-03-07", "2026-03-08", 9),
        ("2026-10-31", "2026-11-01", 11),
    ],
)
def test_overnight_calendar_preserves_local_wall_clocks_across_dst(start_date, end_date, elapsed_hours):
    body, skip = _build_event_body({
        "request_id": f"req-o1-{start_date}",
        "client_name": "Overnight Client",
        "pet_names": "Scout",
        "service_type": "OVERNIGHT",
        "scheduled_date": start_date,
        "occurrence_schedule_mode": "fixed",
        "scheduled_duration": 600,
    })
    assert skip is None
    assert body["start"] == {
        "dateTime": f"{start_date}T21:00:00",
        "timeZone": "America/New_York",
    }
    assert body["end"] == {
        "dateTime": f"{end_date}T07:00:00",
        "timeZone": "America/New_York",
    }
    assert "date" not in body["start"]
    start = datetime.fromisoformat(body["start"]["dateTime"]).replace(tzinfo=ZoneInfo("America/New_York"))
    end = datetime.fromisoformat(body["end"]["dateTime"]).replace(tzinfo=ZoneInfo("America/New_York"))
    elapsed = end.astimezone(timezone.utc) - start.astimezone(timezone.utc)
    assert elapsed.total_seconds() / 3600 == elapsed_hours


def test_historical_overnight_keeps_all_day_and_720_minute_exact_time_compatibility():
    all_day, skip = _build_event_body({
        "request_id": "req-o1-history-all-day",
        "client_name": "Historical Client",
        "pet_names": "Scout",
        "service_type": "OVERNIGHT",
        "start_date": "2026-09-10",
        "visit_window": "ANYTIME",
    })
    assert skip is None
    assert all_day["start"] == {"date": "2026-09-10"}
    assert all_day["end"] == {"date": "2026-09-11"}

    exact, skip = _build_event_body({
        "request_id": "req-o1-history-exact",
        "client_name": "Historical Client",
        "pet_names": "Scout",
        "service_type": "OVERNIGHT",
        "start_date": "2026-09-10",
        "scheduled_time": "21:00",
    })
    assert skip is None
    assert exact["start"]["dateTime"] == "2026-09-10T21:00:00"
    assert exact["end"]["dateTime"] == "2026-09-11T09:00:00"


class _CancellationTable:
    def __init__(self, request, jobs):
        self.request = request
        self.jobs = jobs

    def get_item(self, *, Key):
        return {"Item": self.jobs.get(Key["PK"])}

    def update_item(self, **kwargs):
        key = kwargs["Key"]
        record = self.request if key["PK"] == self.request["PK"] else self.jobs[key["PK"]]
        values = kwargs.get("ExpressionAttributeValues", {})
        if values.get(":s"):
            record["status"] = values[":s"]
        if kwargs["UpdateExpression"] == "REMOVE google_event_id":
            record.pop("google_event_id", None)
        return {}


def _overnight_children(request_id, child_ids):
    return {
        f"JOB#{child_id}": {
            "PK": f"JOB#{child_id}",
            "SK": f"REQ#{request_id}",
            "request_id": request_id,
            "company_id": "test-company",
            "client_id": "client-o1",
            "service_type": "OVERNIGHT",
            "status": "JOB_CREATED",
            "start_date": f"2026-09-{10 + index:02d}",
            "end_date": f"2026-09-{11 + index:02d}",
            "start_time": "21:00",
            "end_time": "07:00",
            "occurrence_schedule_mode": "fixed",
            "google_event_id": f"event-{child_id}",
        }
        for index, child_id in enumerate(child_ids)
    }


def test_overnight_cancellation_reaches_each_child_and_only_its_calendar_event():
    request_id = "req-o1-cancel"
    child_ids = ["overnight-1", "overnight-2", "overnight-3"]
    request = {
        "PK": f"REQ#{request_id}", "SK": "CLIENT#client-o1", "request_id": request_id,
        "client_id": "client-o1", "service_type": "OVERNIGHT", "job_ids": child_ids,
        "status": "CANCELLATION_REQUESTED", **EXPECTED_FIXED_FIELDS,
    }
    jobs = _overnight_children(request_id, child_ids)
    unrelated = {"PK": "JOB#unrelated", "status": "ASSIGNED", "google_event_id": "other"}
    jobs[unrelated["PK"]] = unrelated
    table = _CancellationTable(request, jobs)

    def get_item(pk, _sk):
        return request if pk == request["PK"] else jobs.get(pk)

    with patch("common.auth.get_effective_role", return_value="admin"), patch(
        "common.auth.validate_tenant_ownership", return_value=None
    ), patch("handlers.cancellation_handler.get_item", side_effect=get_item), patch(
        "handlers.cancellation_handler.table", table
    ), patch("common.cascade.table", table), patch(
        "common.google_calendar.delete_event_detailed",
        side_effect=[(True, False, None), (False, True, None), (True, False, None)],
    ) as calendar_delete, patch("handlers.cancellation_handler.log_action"), patch(
        "handlers.cancellation_handler.notify_event"
    ):
        response = handle_admin_decision({
            "request_id": request_id, "client_id": "client-o1", "decision": "APPROVE"
        }, {})

    assert response["statusCode"] == 200
    assert all(jobs[f"JOB#{child_id}"]["status"] == "CANCELLED" for child_id in child_ids)
    assert calendar_delete.call_args_list == [
        call(f"event-{child_id}", request_id) for child_id in child_ids
    ]
    assert unrelated["status"] == "ASSIGNED"


def test_overnight_assignment_reaches_all_children_and_batches_notifications():
    request_id = "req-o1-assign"
    child_ids = ["overnight-1", "overnight-2", "overnight-3"]
    request = {
        "PK": f"REQ#{request_id}", "SK": "CLIENT#client-o1", "request_id": request_id,
        "client_id": "client-o1", "company_id": "test-company", "service_type": "OVERNIGHT",
        "job_id": child_ids[0], "job_ids": child_ids, "is_multi_day": True, **EXPECTED_FIXED_FIELDS,
    }
    jobs = _overnight_children(request_id, child_ids)
    table = MagicMock()
    table.query.return_value = {"Items": [{
        "email": "sitter@example.com", "is_active": True, "is_assignable": True,
        "cognito_sub": "linked-sitter",
    }]}

    def get_item(pk, _sk):
        return request if pk == request["PK"] else jobs.get(pk)

    def update_item(**kwargs):
        key = kwargs["Key"]
        values = kwargs.get("ExpressionAttributeValues", {})
        record = request if key["PK"] == request["PK"] else jobs[key["PK"]]
        if ":s" in values:
            record.update(status=values[":s"], worker_id=values[":w"], worker_name=values[":wn"])

    table.update_item.side_effect = update_item
    event = {"body": json.dumps({
        "job_id": request_id, "req_id": request_id, "client_id": "client-o1",
        "worker_id": "sitter@example.com", "worker_name": "O1 Sitter",
    })}
    with patch("common.entitlement.require_active_tenant", return_value=None), patch(
        "common.auth.get_effective_role", return_value="admin"
    ), patch("common.auth.get_claims", return_value={"email": "owner@example.com"}), patch(
        "common.auth.get_current_company_id", return_value="test-company"
    ), patch("common.auth.validate_tenant_ownership", return_value=None), patch(
        "common.db.get_item", side_effect=get_item
    ), patch("common.db.table", table), patch(
        "common.google_calendar.sync_calendar_event",
        side_effect=lambda item, **_kwargs: {"event_id": item["google_event_id"]},
    ) as calendar_sync, patch("common.notifications.service.notify_event") as notify:
        response = assignment_handler(event, None)

    assert response["statusCode"] == 200
    assert all(jobs[f"JOB#{child_id}"]["status"] == "ASSIGNED" for child_id in child_ids)
    assert calendar_sync.call_count == 3
    assert notify.call_args_list == [
        call("STAFF_ASSIGNED", jobs["JOB#overnight-1"]),
        call("VISIT_SCHEDULED", jobs["JOB#overnight-1"]),
    ]
