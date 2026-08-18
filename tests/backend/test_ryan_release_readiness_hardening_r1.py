"""Ryan release-readiness R1 Check-In resiliency characterization coverage."""

import json
import uuid
from unittest.mock import MagicMock, call, patch

from handlers.assignment_handler import handler as assignment_handler
from handlers.cancellation_handler import handle_admin_decision
from handlers.job_handler import handler as job_handler


def _check_in_request(request_id, dates, windows):
    return {
        "PK": f"REQ#{request_id}",
        "SK": "CLIENT#client-r1",
        "request_id": request_id,
        "client_id": "client-r1",
        "company_id": "test-company",
        "client_name": "R1 Client",
        "pet_names": "Scout",
        "service_type": "CHECK_IN",
        "visits_per_day": len(windows),
        "visit_windows": list(windows),
        "visit_window": windows[0],
        "selected_dates": list(dates),
        "start_date": dates[0],
        "end_date": dates[-1],
        "status": "APPROVED",
    }


def test_check_in_mid_batch_failure_retry_converges_to_exact_deterministic_children():
    dates = ["2026-08-20", "2026-08-21", "2026-08-22"]
    windows = ["MORNING", "EVENING"]
    request = _check_in_request("req-r1-retry", dates, windows)
    jobs = {}
    fail_on_third_write = {"enabled": True}
    write_attempts = {"count": 0}

    def get_item(pk, _sk):
        if pk == request["PK"]:
            return request
        return jobs.get(pk)

    def put_item(item):
        write_attempts["count"] += 1
        if fail_on_third_write["enabled"] and write_attempts["count"] == 3:
            raise RuntimeError("synthetic mid-batch interruption")
        jobs[item["PK"]] = dict(item)
        return True

    table = MagicMock()

    def update_item(**kwargs):
        key = kwargs["Key"]
        values = kwargs.get("ExpressionAttributeValues", {})
        if key["PK"].startswith("JOB#") and ":gid" in values:
            jobs[key["PK"]]["google_event_id"] = values[":gid"]
        if key["PK"] == request["PK"] and ":jids" in values:
            request["job_id"] = values[":jid"]
            request["job_ids"] = list(values[":jids"])
            request["is_multi_day"] = values.get(":imd", request.get("is_multi_day"))
            request["total_occurrences"] = values.get(":to")

    table.update_item.side_effect = update_item

    def calendar_sync(item, **_kwargs):
        return {"event_id": f"event-{item['occurrence_date']}-{item['occurrence_window']}"}

    with patch("handlers.job_handler.get_item", side_effect=get_item), patch(
        "handlers.job_handler.put_item", side_effect=put_item
    ), patch("handlers.job_handler.table", table), patch(
        "common.pet_profile.create_or_link_pets_from_request",
        return_value={"pet_ids": ["pet-r1"]},
    ), patch("common.google_calendar.sync_calendar_event", side_effect=calendar_sync) as calendar, patch(
        "handlers.job_handler.time.sleep"
    ):
        first = job_handler(
            {"request_id": request["request_id"], "client_id": request["client_id"]},
            None,
        )
        first_ids = {pk.removeprefix("JOB#") for pk in jobs}
        assert first == {"error": "synthetic mid-batch interruption"}
        assert len(first_ids) == 2
        assert "job_ids" not in request

        fail_on_third_write["enabled"] = False
        retry = job_handler(
            {"request_id": request["request_id"], "client_id": request["client_id"]},
            None,
        )

    expected_ids = [
        str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"togs-and-dogs:check-in:{request['request_id']}:{date}:{window}",
            )
        )
        for date in dates
        for window in windows
    ]
    assert retry["job_ids"] == expected_ids
    assert request["job_ids"] == expected_ids
    assert set(expected_ids) == {pk.removeprefix("JOB#") for pk in jobs}
    assert first_ids < set(expected_ids)
    assert len(jobs) == len(expected_ids) == 6
    assert len(set(retry["job_ids"])) == 6
    assert calendar.call_count == 6


class _CancellationTable:
    def __init__(self, request, jobs):
        self.request = request
        self.jobs = jobs
        self.update_calls = []

    def get_item(self, *, Key):
        return {"Item": self.jobs.get(Key["PK"])}

    def update_item(self, **kwargs):
        self.update_calls.append(kwargs)
        key = kwargs["Key"]
        record = self.request if key["PK"] == self.request["PK"] else self.jobs[key["PK"]]
        expression = kwargs["UpdateExpression"]
        values = kwargs.get("ExpressionAttributeValues", {})
        if values.get(":s"):
            record["status"] = values[":s"]
        if expression == "REMOVE google_event_id":
            record.pop("google_event_id", None)
        return {}


def test_check_in_multi_window_cancellation_cascades_and_deduplicates_calendar_cleanup():
    request_id = "req-r1-cancel"
    child_ids = [f"child-{index}" for index in range(1, 7)]
    request = _check_in_request(
        request_id,
        ["2026-08-20", "2026-08-21"],
        ["MORNING", "MIDDAY", "EVENING"],
    )
    request.update({"job_ids": child_ids, "status": "CANCELLATION_REQUESTED"})
    event_ids = ["event-a", "event-b", "event-b", "event-404", "event-410", None]
    jobs = {
        f"JOB#{child_id}": {
            "PK": f"JOB#{child_id}",
            "SK": f"REQ#{request_id}",
            "request_id": request_id,
            "status": "ASSIGNED",
            **({"google_event_id": event_id} if event_id else {}),
        }
        for child_id, event_id in zip(child_ids, event_ids)
    }
    unrelated = {
        "PK": "JOB#unrelated",
        "SK": "REQ#another-request",
        "status": "ASSIGNED",
        "google_event_id": "unrelated-event",
    }
    jobs[unrelated["PK"]] = unrelated
    table = _CancellationTable(request, jobs)

    def get_item(pk, _sk):
        if pk == request["PK"]:
            return request
        return jobs.get(pk)

    def delete_event(event_id, _request_id):
        return (True, event_id in {"event-404", "event-410"}, None)

    with patch("common.auth.get_effective_role", return_value="admin"), patch(
        "common.auth.validate_tenant_ownership", return_value=None
    ), patch("handlers.cancellation_handler.get_item", side_effect=get_item), patch(
        "handlers.cancellation_handler.table", table
    ), patch("common.cascade.table", table), patch(
        "common.google_calendar.delete_event_detailed", side_effect=delete_event
    ) as calendar_delete, patch("handlers.cancellation_handler.log_action"), patch(
        "handlers.cancellation_handler.notify_event"
    ) as notify:
        response = handle_admin_decision(
            {
                "request_id": request_id,
                "client_id": request["client_id"],
                "decision": "APPROVE",
            },
            {},
        )

    assert response["statusCode"] == 200
    assert request["status"] == "CANCELLED"
    assert all(jobs[f"JOB#{child_id}"]["status"] == "CANCELLED" for child_id in child_ids)
    assert unrelated == {
        "PK": "JOB#unrelated",
        "SK": "REQ#another-request",
        "status": "ASSIGNED",
        "google_event_id": "unrelated-event",
    }
    assert calendar_delete.call_args_list == [
        call("event-a", request_id),
        call("event-b", request_id),
        call("event-404", request_id),
        call("event-410", request_id),
    ]
    assert "google_event_id" not in jobs["JOB#child-1"]
    assert "google_event_id" not in jobs["JOB#child-2"]
    assert "google_event_id" not in jobs["JOB#child-3"]
    assert "google_event_id" not in jobs["JOB#child-4"]
    assert "google_event_id" not in jobs["JOB#child-5"]
    notify.assert_called_once_with("VISIT_CANCELLED", request)


def test_check_in_multi_window_assignment_cascades_to_all_children_and_batches_notifications():
    request_id = "req-r1-assign"
    child_ids = [f"child-{index}" for index in range(1, 7)]
    request = _check_in_request(
        request_id,
        ["2026-08-20", "2026-08-21"],
        ["MORNING", "MIDDAY", "EVENING"],
    )
    request.update({
        "job_id": child_ids[0],
        "job_ids": child_ids,
        "is_multi_day": True,
    })
    jobs = {
        f"JOB#{child_id}": {
            "PK": f"JOB#{child_id}",
            "SK": f"REQ#{request_id}",
            "company_id": "test-company",
            "request_id": request_id,
            "client_id": request["client_id"],
            "service_type": "CHECK_IN",
            "status": "JOB_CREATED",
            "start_date": "2026-08-20" if index < 3 else "2026-08-21",
            "occurrence_window": ["MORNING", "MIDDAY", "EVENING"][index % 3],
            "google_event_id": f"event-{child_id}",
        }
        for index, child_id in enumerate(child_ids)
    }
    table = MagicMock()
    table.query.return_value = {
        "Items": [{
            "email": "sitter@example.com",
            "is_active": True,
            "is_assignable": True,
            "cognito_sub": "linked-sitter",
        }]
    }

    def get_item(pk, _sk):
        if pk == request["PK"]:
            return request
        return jobs.get(pk)

    def update_item(**kwargs):
        key = kwargs["Key"]
        values = kwargs.get("ExpressionAttributeValues", {})
        if key["PK"] in jobs and ":s" in values:
            jobs[key["PK"]].update({
                "status": values[":s"],
                "worker_id": values[":w"],
                "worker_name": values[":wn"],
            })
        if key["PK"] == request["PK"] and ":s" in values:
            request.update({
                "status": values[":s"],
                "worker_id": values[":w"],
                "worker_name": values[":wn"],
            })

    table.update_item.side_effect = update_item
    event = {
        "body": json.dumps({
            "job_id": request_id,
            "req_id": request_id,
            "client_id": request["client_id"],
            "worker_id": "sitter@example.com",
            "worker_name": "R1 Sitter",
        })
    }

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
    body = json.loads(response["body"])
    assert body["job_ids"] == child_ids
    assert all(jobs[f"JOB#{child_id}"]["status"] == "ASSIGNED" for child_id in child_ids)
    assert all(
        jobs[f"JOB#{child_id}"]["worker_id"] == "sitter@example.com"
        for child_id in child_ids
    )
    assert request["status"] == "ASSIGNED"
    assert request["worker_id"] == "sitter@example.com"
    assert calendar_sync.call_count == 6
    assert notify.call_args_list == [
        call("STAFF_ASSIGNED", jobs["JOB#child-1"]),
        call("VISIT_SCHEDULED", jobs["JOB#child-1"]),
    ]
