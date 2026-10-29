"""INACTIVE DynamoDB request builders. No SDK/client, I/O, execute method or enrollment.

Returned requests are design artifacts, NOT approved transactions. All plans retain
policy/integration blockers. Do not wire into a live caller without separate review.
"""
from dataclasses import dataclass
import re
from common.worker_identity import (
    Failure, require, row, shape, tenant_id, identifier, revision, next_revision,
    parse_worker, parse_link, parse_staff, validate_principal, operation_id, digest,
)
from common.assignment_contract import parse_assignment, parse_parent, assert_assignment_snapshot


@dataclass(frozen=True)
class InactivePlan:
    request: dict
    blockers: tuple


def attribute(value):
    if type(value) is bool:
        return {"BOOL": value}
    if type(value) is int:
        revision(value)
        return {"N": str(value)}
    require(type(value) is str and bool(value))
    return {"S": value}


def encoded(record):
    return {key: attribute(value) for key, value in record.items()}


def key(record):
    return encoded({k: record[k] for k in ("PK", "SK")})


def checked_plan(table_name, actions, blockers):
    require(type(table_name) is str and re.fullmatch(r"[A-Za-z0-9_.-]{3,255}", table_name) is not None)
    require(type(actions) is list and 1 <= len(actions) <= 100)
    require(type(blockers) is tuple and "NO_RUNTIME_INTEGRATION" in blockers)
    targets = set()
    for action in actions:
        require(type(action) is dict and len(action) == 1)
        kind, spec = next(iter(action.items()))
        require(kind in {"Put", "Update", "ConditionCheck"})
        require(spec["TableName"] == table_name and bool(spec.get("ConditionExpression")))
        target = spec.get("Key") or {k: spec["Item"][k] for k in ("PK", "SK")}
        identity = (table_name, target["PK"]["S"], target["SK"]["S"])
        require(identity not in targets)  # No ConditionCheck plus Update on same item.
        targets.add(identity)
    return InactivePlan({"TransactItems": actions}, tuple(blockers))


def build_linkage_request(table_name, principal, worker, link, staff, expected_staff_revision):
    """Prospective create-only linkage. No relink, enrollment approval or reverse cardinality policy."""
    validate_principal(principal)
    w = parse_worker(worker, principal.tenant)
    l = parse_link(link, principal)
    shape(staff, {"PK", "SK", "company_id", "staff_id", "cognito_sub", "is_active", "is_assignable"})
    require(staff["company_id"] == principal.tenant, Failure.WRONG_TENANT)
    require(staff["PK"] == "COMPANY#" + principal.tenant and staff["SK"] == "STAFF#" + identifier(staff["staff_id"]))
    require(staff["cognito_sub"] == principal.subject, Failure.MISMATCH)
    require(staff["is_active"] is True and staff["is_assignable"] is True, Failure.INACTIVE)
    require("canonical_worker_id" not in staff, Failure.POLICY_PENDING)
    require((w["worker_id"], w["staff_id"]) == (l["worker_id"], l["staff_id"])
            and w["staff_id"] == staff["staff_id"], Failure.MISMATCH)
    require(w["version"] == 1 and l["version"] == 1)
    if expected_staff_revision is None:
        require("identity_revision" not in staff, Failure.STALE)
        condition = "attribute_not_exists(identity_revision)"
        new_revision = 1
    else:
        expected_staff_revision = revision(expected_staff_revision)
        require(revision(staff.get("identity_revision")) == expected_staff_revision, Failure.STALE)
        condition = "identity_revision = :expected"
        new_revision = next_revision(expected_staff_revision)
    values = {":tenant": principal.tenant, ":sid": w["staff_id"], ":sub": principal.subject,
              ":yes": True, ":wid": w["worker_id"], ":next": new_revision}
    if expected_staff_revision is not None:
        values[":expected"] = expected_staff_revision
    actions = [
        {"Put": {"TableName": table_name, "Item": encoded(w),
                 "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)"}},
        {"Put": {"TableName": table_name, "Item": encoded(l),
                 "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)"}},
        {"Update": {"TableName": table_name, "Key": key(staff),
                    "UpdateExpression": "SET canonical_worker_id = :wid, identity_revision = :next",
                    "ConditionExpression": "attribute_exists(PK) AND company_id = :tenant AND staff_id = :sid AND cognito_sub = :sub AND is_active = :yes AND is_assignable = :yes AND attribute_not_exists(canonical_worker_id) AND " + condition,
                    "ExpressionAttributeValues": encoded(values)}},
    ]
    return checked_plan(table_name, actions, (
        "ENROLLMENT_PROOF_AND_OPERATOR_PENDING", "REVERSE_LINK_CARDINALITY_PENDING",
        "REVOCATION_AUDIT_AND_DURABLE_RECEIPT_PENDING", "NO_RUNTIME_INTEGRATION"))


def build_assignment_request(table_name, tenant, request_id, job_id, worker, staff, job, parent,
                             expected_assignment, expected_execution, expected_parent,
                             operation, payload_hash):
    """Proposed exact-child writer shape only; no actor authorization or side effects."""
    tenant_id(tenant)
    w = parse_worker(worker, tenant)
    s = parse_staff(staff, tenant)
    j = parse_assignment(job, tenant, request_id, job_id)
    p = parse_parent(parent, tenant, request_id)
    assert_assignment_snapshot(j, p, expected_assignment, expected_execution, expected_parent)
    require((s["canonical_worker_id"], s["staff_id"]) == (w["worker_id"], w["staff_id"]), Failure.MISMATCH)
    require(w["is_active"] and w["is_assignable"] and s["is_active"] and s["is_assignable"], Failure.INACTIVE)
    operation_id(operation)
    digest(payload_hash)
    child_values = {":tenant": tenant, ":rid": request_id, ":cid": j["client_id"],
                    ":ar": j["assignment_revision"], ":er": j["execution_revision"],
                    ":cv": 1, ":oldstatus": j["status"], ":assigned": "ASSIGNED",
                    ":wid": w["worker_id"], ":next": next_revision(j["assignment_revision"]),
                    ":op": operation, ":digest": payload_hash}
    parent_values = {":tenant": tenant, ":rid": request_id, ":cid": j["client_id"],
                     ":rev": p["workflow_revision"], ":next": next_revision(p["workflow_revision"]),
                     ":status": p["status"], ":jid": job_id}
    if j["assigned_worker_id"] is None:
        old_assignment_condition = "attribute_type(assigned_worker_id, :nulltype)"
        child_values[":nulltype"] = "NULL"
    else:
        old_assignment_condition = "assigned_worker_id = :oldwid"
        child_values[":oldwid"] = j["assigned_worker_id"]
    actions = [
        {"ConditionCheck": {"TableName": table_name, "Key": key(w),
                            "ConditionExpression": "attribute_exists(PK) AND company_id = :tenant AND worker_id = :wid AND staff_id = :sid AND #v = :version AND contract_version = :cv AND is_active = :yes AND is_assignable = :yes",
                            "ExpressionAttributeNames": {"#v": "version"},
                            "ExpressionAttributeValues": encoded({":tenant": tenant, ":wid": w["worker_id"], ":sid": w["staff_id"], ":version": w["version"], ":cv": 1, ":yes": True})}},
        {"ConditionCheck": {"TableName": table_name, "Key": key(s),
                            "ConditionExpression": "attribute_exists(PK) AND company_id = :tenant AND staff_id = :sid AND canonical_worker_id = :wid AND identity_revision = :revision AND cognito_sub = :sub AND is_active = :yes AND is_assignable = :yes",
                            "ExpressionAttributeValues": encoded({":tenant": tenant, ":sid": s["staff_id"], ":wid": w["worker_id"], ":revision": s["identity_revision"], ":sub": s["cognito_sub"], ":yes": True})}},
        {"Update": {"TableName": table_name, "Key": key(j),
                    "UpdateExpression": "SET assigned_worker_id = :wid, assignment_revision = :next, #status = :assigned, assignment_operation_id = :op, assignment_payload_digest = :digest",
                    "ConditionExpression": "attribute_exists(PK) AND company_id = :tenant AND request_id = :rid AND client_id = :cid AND assignment_contract_version = :cv AND assignment_revision = :ar AND execution_revision = :er AND #status = :oldstatus AND attribute_not_exists(started_at) AND " + old_assignment_condition,
                    "ExpressionAttributeNames": {"#status": "status"}, "ExpressionAttributeValues": encoded(child_values)}},
        {"Update": {"TableName": table_name, "Key": key(p),
                    "UpdateExpression": "SET workflow_revision = :next",
                    "ConditionExpression": "attribute_exists(PK) AND company_id = :tenant AND request_id = :rid AND client_id = :cid AND workflow_revision = :rev AND #status = :status AND contains(job_ids, :jid)",
                    "ExpressionAttributeNames": {"#status": "status"}, "ExpressionAttributeValues": encoded(parent_values)}},
    ]
    return checked_plan(table_name, actions, (
        "ACTOR_AUTHORIZATION_PENDING", "ASSIGNMENT_AND_STARTED_POLICY_PENDING",
        "ALL_WRITERS_AND_MIXED_VERSION_COVERAGE_PENDING", "AUDIT_AND_DURABLE_RECEIPT_PENDING",
        "LEGACY_MIRROR_AND_PARENT_PRESENTATION_PENDING", "NO_RUNTIME_INTEGRATION"))
