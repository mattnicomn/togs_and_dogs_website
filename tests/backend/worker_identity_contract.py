"""OFFLINE SPECIFICATION ONLY. Not JWT verification, a live authorizer, or a DB writer.

All records are synthetic trusted snapshots supplied by tests. ELIGIBLE means
eligible at that snapshot, never permission to perform a production mutation.
The existing staff path is deliberately delegated, not reimplemented.
"""
from dataclasses import dataclass, replace
from enum import Enum
from decimal import Decimal
import re
from typing import FrozenSet, Optional


class Outcome(str, Enum):
    ELIGIBLE = "ELIGIBLE_AT_SNAPSHOT"
    DENIED = "DENIED"
    PENDING = "POLICY_PENDING"
    STAFF_COMPATIBILITY = "EXISTING_STAFF_PATH_REQUIRED"


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reason: str


@dataclass(frozen=True)
class Caller:
    issuer: str
    subject: str
    tenant: str
    role: str
    trusted_authorizer: bool = False
    token_current: bool = False


@dataclass(frozen=True)
class Worker:
    worker_id: str
    tenant: str
    staff_id: str
    active: bool = False
    assignable: bool = False
    version: int = 0


@dataclass(frozen=True)
class Link:
    issuer: str
    subject: str
    tenant: str
    worker_id: str
    staff_id: str
    active: bool = False
    version: int = 0


@dataclass(frozen=True)
class Visit:
    job_id: str
    request_id: str
    tenant: str
    assigned_worker_id: Optional[str]
    assignment_revision: int = 0
    canonical: bool = False
    assignment_contract_version: int = 0
    hydrated: bool = False
    status: str = "ASSIGNED"
    started: bool = False
    started_assignment_revision: Optional[int] = None
    execution_revision: int = 1
    legacy_worker_reference: Optional[str] = None  # display/compatibility ONLY


@dataclass(frozen=True)
class Snapshot:
    caller: Caller
    worker: Optional[Worker]
    link: Optional[Link]
    visit: Visit
    active_link_count: int = 1


@dataclass(frozen=True)
class Operation:
    action: str
    request_id: str
    job_id: str
    expected_assignment_revision: int
    operation_id: str
    payload_digest: str
    expected_execution_revision: int


def deny(reason: str) -> Decision:
    return Decision(Outcome.DENIED, reason)


def pending(reason: str) -> Decision:
    return Decision(Outcome.PENDING, reason)


MAX_REVISION = 2**63 - 1  # Explicit storage contract bound, not coercion.


def valid_revision(value: int) -> bool:
    return type(value) is int and 1 <= value <= MAX_REVISION


def parse_dynamo_revision(value) -> int:
    """Explicit DB-boundary conversion; domain records accept exact ints only."""
    if type(value) is Decimal:
        if not value.is_finite() or value != value.to_integral_value() or not 1 <= value <= MAX_REVISION:
            raise ValueError("INVALID_REVISION")
        value = int(value)
    if not valid_revision(value):
        raise ValueError("INVALID_REVISION")
    return value


def valid_operation(operation: Operation) -> bool:
    return (operation.action in {"START", "COMPLETE"}
            and isinstance(operation.operation_id, str)
            and re.fullmatch(r"op_[0-9a-f]{32}", operation.operation_id) is not None
            and isinstance(operation.payload_digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", operation.payload_digest) is not None
            and valid_revision(operation.expected_assignment_revision)
            and valid_revision(operation.expected_execution_revision))


def assess_owner(snapshot: Snapshot, operation: Operation) -> Decision:
    """No email/name comparison and no authorization from client role assertions."""
    caller, worker, link, visit = snapshot.caller, snapshot.worker, snapshot.link, snapshot.visit
    if caller.trusted_authorizer is not True or caller.token_current is not True:
        return deny("UNTRUSTED_OR_EXPIRED_CALLER")
    if not all((caller.issuer, caller.subject, caller.tenant)):
        return deny("MISSING_PRINCIPAL_OR_TENANT")
    if caller.role == "staff":
        return Decision(Outcome.STAFF_COMPATIBILITY, "NOT_AN_OWNER_GRANT")
    if caller.role != "owner":
        return deny("ROLE_NOT_OWNER")
    if operation.action not in {"START", "COMPLETE"}:
        return deny("UNSUPPORTED_ACTION")
    if not valid_operation(operation):
        return deny("INVALID_OPERATION_BINDING")
    if visit.request_id != operation.request_id or visit.job_id != operation.job_id:
        return deny("WRONG_CHILD_OR_PARENT")
    if visit.tenant != caller.tenant:
        return deny("WRONG_TENANT")
    if visit.hydrated is not True:
        return deny("UNHYDRATED_VISIT")
    if visit.canonical is not True:
        return deny("LEGACY_ONLY_ASSIGNMENT")
    if type(visit.assignment_contract_version) is not int or visit.assignment_contract_version != 1:
        return deny("UNSUPPORTED_ASSIGNMENT_CONTRACT")
    if not visit.assigned_worker_id:
        return deny("UNASSIGNED_VISIT")
    if type(snapshot.active_link_count) is not int or snapshot.active_link_count != 1:
        return deny("AMBIGUOUS_LINKAGE")
    if link is None or worker is None:
        return deny("UNLINKED_OWNER")
    if link.tenant != caller.tenant or worker.tenant != caller.tenant:
        return deny("WRONG_TENANT")
    if (link.issuer, link.subject) != (caller.issuer, caller.subject):
        return deny("PRINCIPAL_LINK_MISMATCH")
    if link.active is not True:
        return deny("REVOKED_LINK")
    if worker.active is not True or worker.assignable is not True:
        return deny("INACTIVE_OR_UNASSIGNABLE_WORKER")
    if not all((worker.worker_id, worker.staff_id, link.worker_id, link.staff_id)):
        return deny("MISSING_CANONICAL_IDENTITY")
    if not isinstance(worker.worker_id, str) or re.fullmatch(r"wrk_[0-9a-f]{32}", worker.worker_id) is None:
        return deny("INVALID_CANONICAL_WORKER_ID")
    if (worker.worker_id, worker.staff_id) != (link.worker_id, link.staff_id):
        return deny("RECIPROCAL_LINK_MISMATCH")
    if worker.worker_id != visit.assigned_worker_id:
        return deny("ASSIGNED_WORKER_MISMATCH")
    revisions = (worker.version, link.version, visit.assignment_revision, operation.expected_assignment_revision,
                 visit.execution_revision, operation.expected_execution_revision)
    if not all(valid_revision(value) for value in revisions):
        return deny("INVALID_REVISION")
    if visit.assignment_revision != operation.expected_assignment_revision:
        return deny("STALE_ASSIGNMENT_REVISION")
    if visit.execution_revision != operation.expected_execution_revision:
        return deny("STALE_EXECUTION_REVISION")
    if visit.started and not valid_revision(visit.started_assignment_revision):
        return deny("INVALID_EXECUTION_PROVENANCE")
    if type(visit.started) is not bool:
        return deny("INVALID_EXECUTION_PROVENANCE")
    if visit.status == "COMPLETED" or (operation.action == "START" and visit.started):
        return pending("REPLAY_POLICY")
    if visit.status != "ASSIGNED":
        return deny("INVALID_VISIT_STATE")
    if visit.started and visit.started_assignment_revision != visit.assignment_revision:
        return pending("REASSIGNMENT_AFTER_START_POLICY")
    if operation.action == "COMPLETE" and not visit.started:
        return pending("OWNER_COMPLETE_WITHOUT_START_POLICY")
    return Decision(Outcome.ELIGIBLE, "CURRENT_CANONICAL_OWNER_ASSIGNMENT")


@dataclass(frozen=True)
class CommitFence:
    """Fields requiring atomic conditions, not a signed capability or DB transaction."""
    principal: tuple
    worker_identity: tuple
    child_identity: tuple
    link_version: int
    worker_version: int
    assignment_revision: int
    parent_revision: int
    execution_revision: int
    operation_binding: tuple


def capture_fence(snapshot: Snapshot, operation: Operation, parent_revision: int) -> CommitFence:
    if snapshot.worker is None or snapshot.link is None or not valid_revision(parent_revision):
        raise ValueError("Cannot fence missing linkage or parent revision")
    if not valid_operation(operation) or not all(valid_revision(v) for v in (
            snapshot.link.version, snapshot.worker.version, snapshot.visit.assignment_revision,
            snapshot.visit.execution_revision)):
        raise ValueError("INVALID_FENCE")
    if (operation.job_id, operation.request_id, operation.expected_assignment_revision,
            operation.expected_execution_revision) != (snapshot.visit.job_id, snapshot.visit.request_id,
            snapshot.visit.assignment_revision, snapshot.visit.execution_revision):
        raise ValueError("STALE_OPERATION")
    return CommitFence(
        (snapshot.caller.issuer, snapshot.caller.subject, snapshot.caller.tenant),
        (snapshot.worker.worker_id, snapshot.worker.staff_id),
        (snapshot.visit.job_id, snapshot.visit.request_id, snapshot.visit.tenant),
        snapshot.link.version, snapshot.worker.version,
        snapshot.visit.assignment_revision, parent_revision, snapshot.visit.execution_revision,
        (operation.action, operation.operation_id, operation.payload_digest),
    )


def assess_atomic_fence(current: Snapshot, operation: Operation, expected: CommitFence,
                        current_parent_revision: int) -> Decision:
    decision = assess_owner(current, operation)
    if decision.outcome != Outcome.ELIGIBLE:
        return decision
    if not valid_revision(current_parent_revision):
        return deny("INVALID_PARENT_REVISION")
    if not isinstance(expected, CommitFence) or not all(valid_revision(v) for v in (
            expected.link_version, expected.worker_version, expected.assignment_revision,
            expected.parent_revision, expected.execution_revision)):
        return deny("INVALID_FENCE")
    if capture_fence(current, operation, current_parent_revision) != expected:
        return deny("COMMIT_FENCE_CHANGED")
    return decision


def legacy_assignment_invalidation(visit: Visit, expected_revision: int) -> Visit:
    """Synthetic postcondition of an ALREADY-authorized legacy writer, not permission."""
    if not valid_revision(expected_revision) or not valid_revision(visit.assignment_revision) or visit.assignment_revision >= MAX_REVISION or visit.assignment_revision != expected_revision:
        raise ValueError("STALE_ASSIGNMENT_REVISION")
    return replace(visit, canonical=False, assignment_contract_version=0, assigned_worker_id=None,
                   assignment_revision=visit.assignment_revision + 1)


@dataclass(frozen=True)
class ParentModel:
    """Set semantics model only; does not propose replacing production list storage."""
    request_id: str
    tenant: str
    children: FrozenSet[str]
    completed: FrozenSet[str] = frozenset()
    revision: int = 1


def completion_rollup_cas(parent: ParentModel, job_id: str, expected_revision: int) -> ParentModel:
    """Pure model of parent CAS AFTER eligibility; no child update or external effect."""
    if not valid_revision(expected_revision) or not valid_revision(parent.revision) or parent.revision != expected_revision:
        raise ValueError("STALE_PARENT_REVISION")
    if parent.revision >= MAX_REVISION:
        raise ValueError("INVALID_PARENT_REVISION")
    if not parent.completed <= parent.children or job_id not in parent.children:
        raise ValueError("WRONG_CHILD_OR_CORRUPT_PARENT")
    if job_id in parent.completed:
        return parent  # counting invariant only; replay authorization remains pending
    return replace(parent, completed=parent.completed | {job_id}, revision=parent.revision + 1)