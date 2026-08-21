"""Ryan Slice E3A: child Start contract and occurrence-aware exact-request reads."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from handlers.admin_handler import handler as admin_handler


TENANT_ID = "tenant-e3a"
REQUEST_ID = "req-e3a"
CLIENT_ID = "client-e3a"
STAFF_EMAIL = "staff@example.com"
REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def active_tenant():
    with patch("common.entitlement.require_active_tenant", return_value=None):
        yield


def make_event(method, path, role="staff", email=STAFF_EMAIL, body=None, path_params=None, query=None):
    event = {
        "httpMethod": method,
        "path": path,
        "pathParameters": path_params or {},
        "queryStringParameters": query or {},
        "requestContext": {
            "authorizer": {
                "claims": {
                    "email": email,
                    "custom:company_id": TENANT_ID,
                    "cognito:groups": [role],
                }
            }
        },
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return event


def make_job(job_id="job-1", status="ASSIGNED", worker_id=STAFF_EMAIL, **overrides):
    job = {
        "PK": f"JOB#{job_id}",
        "SK": f"REQ#{REQUEST_ID}",
        "company_id": TENANT_ID,
        "request_id": REQUEST_ID,
        "client_id": CLIENT_ID,
        "status": status,
        "worker_id": worker_id,
        "worker_name": "Assigned Sitter",
        "audit_log": [{"action": "WORKER_ASSIGNED"}],
    }
    job.update(overrides)
    return job


def make_parent(job_ids=None, job_id=None, worker_id=STAFF_EMAIL, **overrides):
    parent = {
        "PK": f"REQ#{REQUEST_ID}",
        "SK": f"CLIENT#{CLIENT_ID}",
        "company_id": TENANT_ID,
        "request_id": REQUEST_ID,
        "client_id": CLIENT_ID,
        "status": "ASSIGNED",
        "worker_id": worker_id,
    }
    if job_ids is not None:
        parent["job_ids"] = job_ids
    if job_id is not None:
        parent["job_id"] = job_id
    parent.update(overrides)
    return parent


def start_event(job_id="job-1", role="staff", email=STAFF_EMAIL):
    return make_event(
        "POST",
        "/admin/job/start",
        role=role,
        email=email,
        body={"job_id": job_id, "request_id": REQUEST_ID},
    )


def request_event(role="admin", email="admin@example.com"):
    return make_event(
        "GET",
        f"/admin/requests/{REQUEST_ID}",
        role=role,
        email=email,
        path_params={"requestId": REQUEST_ID},
        query={"clientId": CLIENT_ID},
    )


def response_body(response):
    return json.loads(response["body"])


def test_assigned_staff_start_is_atomic_and_has_no_external_or_parent_side_effects():
    job = make_job()
    mock_table = MagicMock()

    with (
        patch("handlers.admin_handler.get_item", return_value=job),
        patch("handlers.admin_handler.table", mock_table),
        patch("handlers.admin_handler.sync_calendar_event") as calendar,
        patch("handlers.admin_handler.notify_event") as notify,
    ):
        response = admin_handler(start_event(), None)

    assert response["statusCode"] == 200
    body = response_body(response)
    assert body["status"] == "ASSIGNED"
    assert body["request_id"] == REQUEST_ID
    assert body["started_by"] == STAFF_EMAIL
    assert body["started_at"].endswith("+00:00")
    assert body["idempotent_replay"] is False

    mock_table.update_item.assert_called_once()
    call = mock_table.update_item.call_args.kwargs
    assert call["Key"] == {"PK": "JOB#job-1", "SK": f"REQ#{REQUEST_ID}"}
    assert call["ConditionExpression"] == "attribute_not_exists(started_at) AND #stat = :assigned"
    assert call["ExpressionAttributeValues"][":assigned"] == "ASSIGNED"
    assert "#stat" not in call["UpdateExpression"]
    assert call["ExpressionAttributeValues"][":sat"] == body["started_at"]
    assert call["ExpressionAttributeValues"][":sby"] == STAFF_EMAIL
    audit_entry = call["ExpressionAttributeValues"][":n"][0]
    assert audit_entry == {
        "action": "JOB_STARTED",
        "timestamp": body["started_at"],
        "updated_by": STAFF_EMAIL,
        "job_id": "job-1",
        "request_id": REQUEST_ID,
    }
    assert not any(call_arg.kwargs.get("Key", {}).get("PK", "").startswith("REQ#") for call_arg in mock_table.update_item.call_args_list)
    calendar.assert_not_called()
    notify.assert_not_called()


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_existing_administrative_roles_can_start_assigned_job(role):
    with patch("handlers.admin_handler.get_item", return_value=make_job()), patch(
        "handlers.admin_handler.table", MagicMock()
    ):
        response = admin_handler(start_event(role=role, email=f"{role}@example.com"), None)

    assert response["statusCode"] == 200
    assert response_body(response)["started_by"] == f"{role}@example.com"


def test_staff_cannot_start_another_workers_job():
    with patch("handlers.admin_handler.get_item", return_value=make_job(worker_id="other@example.com")), patch(
        "handlers.admin_handler.table", MagicMock()
    ) as mock_table:
        response = admin_handler(start_event(), None)

    assert response["statusCode"] == 403
    assert "only start visits assigned to you" in response_body(response)["error"]
    mock_table.update_item.assert_not_called()


def test_start_enforces_tenant_isolation():
    cross_tenant_job = make_job(company_id="other-tenant")
    with patch("handlers.admin_handler.get_item", return_value=cross_tenant_job), patch(
        "handlers.admin_handler.table", MagicMock()
    ) as mock_table:
        response = admin_handler(start_event(), None)

    assert response["statusCode"] == 403
    mock_table.update_item.assert_not_called()


@pytest.mark.parametrize("status", ["COMPLETED", "CANCELLED", "ARCHIVED", "DELETED"])
def test_start_blocks_terminal_jobs_without_start_metadata(status):
    with patch("handlers.admin_handler.get_item", return_value=make_job(status=status)), patch(
        "handlers.admin_handler.table", MagicMock()
    ) as mock_table:
        response = admin_handler(start_event(), None)

    assert response["statusCode"] == 400
    assert response_body(response)["error"] == f"Cannot start job in status: {status}"
    mock_table.update_item.assert_not_called()


@pytest.mark.parametrize("status", ["JOB_CREATED", "SCHEDULED", "PENDING"])
def test_start_does_not_broaden_beyond_canonical_assigned(status):
    with patch("handlers.admin_handler.get_item", return_value=make_job(status=status)), patch(
        "handlers.admin_handler.table", MagicMock()
    ) as mock_table:
        response = admin_handler(start_event(), None)

    assert response["statusCode"] == 400
    mock_table.update_item.assert_not_called()


def test_start_replay_returns_original_timestamp_without_duplicate_audit_write():
    original = "2026-08-20T14:30:00+00:00"
    started_job = make_job(started_at=original, started_by=STAFF_EMAIL)
    with patch("handlers.admin_handler.get_item", return_value=started_job), patch(
        "handlers.admin_handler.table", MagicMock()
    ) as mock_table:
        response = admin_handler(start_event(), None)

    assert response["statusCode"] == 200
    body = response_body(response)
    assert body["started_at"] == original
    assert body["idempotent_replay"] is True
    mock_table.update_item.assert_not_called()


def test_concurrent_start_loser_resolves_from_strongly_consistent_persisted_result():
    original = "2026-08-20T14:31:00+00:00"
    latest_job = make_job(started_at=original, started_by=STAFF_EMAIL)
    conditional_failure = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "condition"}},
        "UpdateItem",
    )
    mock_table = MagicMock()
    mock_table.update_item.side_effect = conditional_failure
    mock_table.get_item.return_value = {"Item": latest_job}

    with patch("handlers.admin_handler.get_item", return_value=make_job()), patch(
        "handlers.admin_handler.table", mock_table
    ):
        response = admin_handler(start_event(), None)

    assert response["statusCode"] == 200
    body = response_body(response)
    assert body["started_at"] == original
    assert body["idempotent_replay"] is True
    mock_table.update_item.assert_called_once()
    mock_table.get_item.assert_called_once_with(
        Key={"PK": "JOB#job-1", "SK": f"REQ#{REQUEST_ID}"},
        ConsistentRead=True,
    )


@pytest.mark.parametrize("with_start", [False, True])
def test_complete_remains_compatible_with_or_without_start_metadata(with_start):
    job = make_job(**({"started_at": "2026-08-20T14:30:00+00:00", "started_by": STAFF_EMAIL} if with_start else {}))
    parent = make_parent(job_ids=["job-1"])

    def get_record(pk, _sk):
        return job if pk == "JOB#job-1" else parent if pk == f"REQ#{REQUEST_ID}" else None

    event = make_event(
        "POST",
        "/admin/job/complete",
        body={"job_id": "job-1", "request_id": REQUEST_ID},
    )
    mock_table = MagicMock()
    with patch("handlers.admin_handler.get_item", side_effect=get_record), patch(
        "handlers.admin_handler.table", mock_table
    ), patch("handlers.admin_handler.log_action"):
        response = admin_handler(event, None)

    assert response["statusCode"] == 200
    assert response_body(response)["status"] == "COMPLETED"
    assert mock_table.update_item.call_count == 2


def invoke_exact_read(parent, jobs, role="admin", email="admin@example.com"):
    records = {parent["PK"]: parent}
    records.update({job["PK"]: job for job in jobs})

    def get_record(pk, _sk):
        return deepcopy(records.get(pk))

    with patch("handlers.admin_handler.get_item", side_effect=get_record):
        return admin_handler(request_event(role=role, email=email), None)


def test_single_legacy_job_id_exposes_exact_child_and_missing_optional_metadata():
    parent = make_parent(job_id="single-job")
    job = make_job(job_id="single-job", start_date="2026-09-01")
    response = invoke_exact_read(parent, [job])

    assert response["statusCode"] == 200
    summary = response_body(response)["job_completion_summary"]
    assert summary["total"] == 1
    assert summary["started"] == 0
    occurrence = summary["jobs"][0]
    assert occurrence["job_id"] == "single-job"
    assert occurrence["request_id"] == REQUEST_ID
    assert occurrence["occurrence_date"] == "2026-09-01"
    assert occurrence["occurrence_window"] is None
    assert occurrence["started_at"] is None
    assert occurrence["completed_at"] is None


def test_multi_date_walk_exposes_every_child_in_occurrence_order():
    jobs = [
        make_job(job_id="walk-3", occurrence_date="2026-09-03", occurrence_window="MIDDAY", occurrence_index=3, total_occurrences=3),
        make_job(job_id="walk-1", occurrence_date="2026-09-01", occurrence_window="MIDDAY", occurrence_index=1, total_occurrences=3),
        make_job(job_id="walk-2", occurrence_date="2026-09-02", occurrence_window="MIDDAY", occurrence_index=2, total_occurrences=3),
    ]
    parent = make_parent(job_ids=[job["PK"].replace("JOB#", "") for job in jobs])
    response = invoke_exact_read(parent, jobs)

    occurrences = response_body(response)["job_completion_summary"]["jobs"]
    assert [job["job_id"] for job in occurrences] == ["walk-1", "walk-2", "walk-3"]
    assert len(occurrences) == 3


def test_multi_window_check_in_keeps_every_date_window_child_distinct_and_ordered():
    dates = ["2026-09-01", "2026-09-02"]
    windows = ["MORNING", "MIDDAY", "EVENING"]
    jobs = []
    index = 0
    for date in dates:
        for window in windows:
            index += 1
            jobs.append(
                make_job(
                    job_id=f"check-{index}",
                    occurrence_date=date,
                    occurrence_window=window,
                    occurrence_index=index,
                    total_occurrences=6,
                )
            )
    parent = make_parent(job_ids=[f"check-{index}" for index in [6, 2, 4, 1, 5, 3]])
    response = invoke_exact_read(parent, jobs)

    summary = response_body(response)["job_completion_summary"]
    occurrences = summary["jobs"]
    assert summary["total"] == 6
    assert [job["job_id"] for job in occurrences] == [f"check-{index}" for index in range(1, 7)]
    assert [(job["occurrence_date"], job["occurrence_window"]) for job in occurrences] == [
        (date, window) for date in dates for window in windows
    ]
    assert len({job["job_id"] for job in occurrences if job["occurrence_date"] == dates[0]}) == 3


def test_fixed_overnight_exposes_each_start_date_and_following_end_date():
    jobs = [
        make_job(
            job_id="overnight-2",
            occurrence_date="2026-11-02",
            occurrence_end_date="2026-11-03",
            occurrence_index=2,
            start_time="21:00",
            end_time="07:00",
        ),
        make_job(
            job_id="overnight-1",
            occurrence_date="2026-11-01",
            occurrence_end_date="2026-11-02",
            occurrence_index=1,
            start_time="21:00",
            end_time="07:00",
        ),
    ]
    response = invoke_exact_read(make_parent(job_ids=["overnight-2", "overnight-1"]), jobs)
    occurrences = response_body(response)["job_completion_summary"]["jobs"]

    assert [(job["occurrence_date"], job["occurrence_end_date"]) for job in occurrences] == [
        ("2026-11-01", "2026-11-02"),
        ("2026-11-02", "2026-11-03"),
    ]
    assert all(job["start_time"] == "21:00" and job["end_time"] == "07:00" for job in occurrences)


def test_occurrence_read_returns_start_and_completion_metadata():
    job = make_job(
        started_at="2026-09-01T12:00:00+00:00",
        started_by=STAFF_EMAIL,
        completed_at="2026-09-01T12:30:00+00:00",
        completed_by=STAFF_EMAIL,
        visit_notes="Visit complete",
        status="COMPLETED",
    )
    response = invoke_exact_read(make_parent(job_ids=["job-1"]), [job])
    summary = response_body(response)["job_completion_summary"]

    assert summary["started"] == 1
    assert summary["completed"] == 1
    occurrence = summary["jobs"][0]
    assert occurrence["started_at"] == "2026-09-01T12:00:00+00:00"
    assert occurrence["started_by"] == STAFF_EMAIL
    assert occurrence["completed_at"] == "2026-09-01T12:30:00+00:00"
    assert occurrence["completed_by"] == STAFF_EMAIL
    assert occurrence["visit_notes"] == "Visit complete"


def test_exact_occurrence_read_enforces_staff_parent_assignment_and_client_role_boundary():
    job = make_job()
    parent = make_parent(worker_id="other@example.com", job_ids=["job-1"])

    staff_response = invoke_exact_read(parent, [job], role="staff", email=STAFF_EMAIL)
    client_response = invoke_exact_read(parent, [job], role="client", email="client@example.com")

    assert staff_response["statusCode"] == 403
    assert client_response["statusCode"] == 403


def test_exact_occurrence_read_blocks_cross_tenant_child_reference():
    parent = make_parent(job_ids=["job-1"])
    cross_tenant_child = make_job(company_id="other-tenant")
    response = invoke_exact_read(parent, [cross_tenant_child])

    assert response["statusCode"] == 403


def test_api_gateway_wires_authenticated_start_and_exact_request_read_routes():
    terraform = (REPO_ROOT / "modules" / "api" / "main.tf").read_text(encoding="utf-8")

    assert 'resource "aws_api_gateway_resource" "admin_job_start"' in terraform
    assert 'resource "aws_api_gateway_method" "post_admin_job_start"' in terraform
    assert 'resource "aws_api_gateway_integration" "post_admin_job_start_lambda"' in terraform
    assert 'resource "aws_api_gateway_method" "get_admin_request"' in terraform
    assert 'resource "aws_api_gateway_integration" "get_admin_request_lambda"' in terraform
    assert terraform.count('authorization = "COGNITO_USER_POOLS"') >= 2
