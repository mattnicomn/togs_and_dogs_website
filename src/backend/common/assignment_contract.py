"""INACTIVE assignment adapters. No handler wiring or mutation implementation."""
from common.worker_identity import (
    Failure, ContractError, require, shape, same_tenant, identifier, worker_id,
    revision, contract_version, flag, operation_id, digest,
)


def parse_assignment(record, tenant, request_id, job_id):
    shape(record, {"PK", "SK", "company_id", "request_id", "client_id", "status"})
    same_tenant(record, tenant)
    identifier(request_id)
    identifier(job_id)
    require(record["PK"] == "JOB#" + job_id and record["SK"] == "REQ#" + request_id
            and record["request_id"] == request_id, Failure.WRONG_CHILD)
    identifier(record["client_id"])
    if "assignment_contract_version" not in record:
        raise ContractError(Failure.LEGACY_ONLY)
    shape(record, {"assignment_contract_version", "assignment_revision", "execution_revision",
                   "assigned_worker_id"})
    result = {k: record[k] for k in ("PK", "SK", "company_id", "request_id", "client_id", "status")}
    require(type(record["status"]) is str and record["status"] in {
        "JOB_CREATED", "ASSIGNED", "COMPLETED", "CANCELLED", "ARCHIVED", "DELETED"})
    result.update(assignment_contract_version=contract_version(record["assignment_contract_version"]),
                  assignment_revision=revision(record["assignment_revision"]),
                  execution_revision=revision(record["execution_revision"]))
    result["assigned_worker_id"] = (None if record["assigned_worker_id"] is None
                                    else worker_id(record["assigned_worker_id"]))
    if "started_at" in record:
        require(record["started_at"] is not None)
        require(type(record["started_at"]) is str and bool(record["started_at"]))
        shape(record, {"started_worker_id", "started_assignment_revision"})
        result.update(started_at=record["started_at"], started_worker_id=worker_id(record["started_worker_id"]),
                      started_assignment_revision=revision(record["started_assignment_revision"]))
    else:
        require("started_worker_id" not in record and "started_assignment_revision" not in record)
    return result


def parse_parent(record, tenant, request_id):
    shape(record, {"PK", "SK", "company_id", "request_id", "client_id", "job_ids", "workflow_revision", "status"})
    same_tenant(record, tenant)
    identifier(request_id)
    cid = identifier(record["client_id"])
    require(record["PK"] == "REQ#" + request_id and record["SK"] == "CLIENT#" + cid
            and record["request_id"] == request_id, Failure.WRONG_CHILD)
    children = record["job_ids"]
    require(type(children) is list and bool(children))
    for child in children:
        identifier(child)
    require(len(children) == len(set(children)))
    require(type(record["status"]) is str and record["status"] in {"APPROVED", "ASSIGNED", "COMPLETED", "CANCELLED", "ARCHIVED", "DELETED"})
    return dict(record, job_ids=list(children), workflow_revision=revision(record["workflow_revision"]))


def execution_binding(action, operation, payload_hash, assignment_revision, execution_revision):
    """Opaque immutable tuple only; not an execution capability or receipt."""
    require(action in ("START", "COMPLETE"))
    return (action, operation_id(operation), digest(payload_hash),
            revision(assignment_revision), revision(execution_revision))


def assert_assignment_snapshot(job, parent, expected_assignment, expected_execution, expected_parent):
    require(job["assignment_revision"] == revision(expected_assignment)
            and job["execution_revision"] == revision(expected_execution)
            and parent["workflow_revision"] == revision(expected_parent), Failure.STALE)
    require(job["PK"].removeprefix("JOB#") in parent["job_ids"]
            and job["client_id"] == parent["client_id"]
            and job["request_id"] == parent["request_id"], Failure.WRONG_CHILD)
    # Proposed no-reassignment-after-Start assumption. Pending, never a grant.
    require("started_at" not in job, Failure.POLICY_PENDING)
    require(job["status"] in {"JOB_CREATED", "ASSIGNED"}
            and parent["status"] in {"APPROVED", "ASSIGNED"}, Failure.POLICY_PENDING)
