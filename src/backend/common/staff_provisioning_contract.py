"""UNWIRED local STAFF provisioning specification. No SDK, I/O or authentication.

Proof/context instances model server-verified preconditions, never client JSON.
Production persistence, identity proof and invitation providers are not implemented.
"""
from dataclasses import dataclass, replace
from enum import Enum
import re


class ProvisioningError(ValueError):
    pass


def ensure(condition, code):
    if not condition:
        raise ProvisioningError(code)


def identifier(value):
    ensure(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is not None, "INVALID_IDENTIFIER")
    return value


def tenant_id(value):
    ensure(type(value) is str and re.fullmatch(r"[a-z0-9_]{3,64}", value) is not None, "INVALID_TENANT")
    return value


def operation_id(value):
    ensure(type(value) is str and re.fullmatch(r"op_[0-9a-f]{32}", value) is not None, "INVALID_OPERATION")
    return value


def digest(value):
    ensure(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "INVALID_DIGEST")
    return value


def revision(value):
    ensure(type(value) is int and 1 <= value <= 2**63-1, "INVALID_REVISION")
    return value


def next_revision(value):
    value = revision(value)
    ensure(value < 2**63-1, "REVISION_EXHAUSTED")
    return value + 1


class State(str, Enum):
    PENDING = "PROVISIONING_PENDING"
    IDENTITY = "IDENTITY_PROVISIONING"
    FAILED = "PROVISIONING_FAILED"
    ACTIVE = "ACTIVE"


@dataclass(frozen=True)
class Request:
    tenant: str
    staff_id: str
    operation: str
    payload_hash: str
    incarnation: str
    identity_handle: str
    uniqueness_keys: tuple
    mode: str = "CREATE"
    target_role: str = "staff"
    assignable: bool = True
    expected_subject: object = None


def validate_request(request):
    ensure(type(request) is Request, "MALFORMED_REQUEST")
    tenant_id(request.tenant)
    identifier(request.staff_id)
    identifier(request.identity_handle)
    operation_id(request.operation)
    digest(request.payload_hash)
    ensure(type(request.incarnation) is str and re.fullmatch(r"inc_[0-9a-f]{32}", request.incarnation) is not None, "INVALID_INCARNATION")
    ensure(type(request.mode) is str and request.mode in {"CREATE", "CREATE_OR_LINK", "LINK_EXISTING"}, "INVALID_MODE")
    if request.mode == "LINK_EXISTING":
        ensure(type(request.expected_subject) is str, "APPROVED_SUBJECT_REQUIRED")
    if request.expected_subject is not None:
        identifier(request.expected_subject)
        ensure(request.mode != "CREATE", "MODE_MISMATCH")
    ensure(request.target_role == "staff", "PRIVILEGED_ROLE_POLICY_PENDING")
    ensure(type(request.assignable) is bool, "INVALID_ASSIGNABILITY")
    ensure(type(request.uniqueness_keys) is tuple and len(request.uniqueness_keys) == 2, "INVALID_UNIQUENESS_KEYS")
    for value in request.uniqueness_keys:
        digest(value)  # Proposed normalized name/email claim digests; never ownership proof.
    ensure(len(set(request.uniqueness_keys)) == 2, "INVALID_UNIQUENESS_KEYS")


@dataclass(frozen=True)
class Admission:
    tenant: str
    actor_subject: str
    actor_role: str
    quota_revision: int
    max_staff: int
    legacy_active_count: int
    verified: bool = False
    current: bool = False
    protected_target: bool = True


def validate_admission(request, admission):
    validate_request(request)
    ensure(type(admission) is Admission, "MALFORMED_ADMISSION")
    ensure(admission.verified is True and admission.current is True, "UNVERIFIED_OR_REVOKED_ACTOR")
    ensure(admission.protected_target is False, "PROTECTED_TARGET")
    ensure(admission.tenant == request.tenant, "WRONG_TENANT")
    identifier(admission.actor_subject)
    ensure(type(admission.actor_role) is str and admission.actor_role in {"owner", "admin"}, "DENIED_ROLE")
    revision(admission.quota_revision)
    ensure(type(admission.max_staff) is int and admission.max_staff >= 0, "INVALID_LIMIT")
    ensure(type(admission.legacy_active_count) is int and admission.legacy_active_count >= 0, "INVALID_COUNT")


@dataclass(frozen=True)
class Reservation:
    tenant: str
    staff_id: str
    incarnation: str
    retired: bool = False


def reservation_for(request):
    validate_request(request)
    return Reservation(request.tenant, request.staff_id, request.incarnation)


@dataclass(frozen=True)
class Proof:
    tenant: str
    issuer: str
    subject: str
    operation: str
    staff_id: str
    incarnation: str
    payload_hash: str
    identity_handle: str
    verified: bool = False


def validate_proof(request, proof, allowed_issuer):
    ensure(type(proof) is Proof and proof.verified is True, "OWNERSHIP_UNVERIFIED")
    ensure(type(allowed_issuer) is str and allowed_issuer.startswith("https://"), "UNTRUSTED_ISSUER")
    ensure(proof.issuer == allowed_issuer, "WRONG_ISSUER")
    ensure((proof.tenant, proof.operation, proof.staff_id, proof.incarnation, proof.payload_hash, proof.identity_handle)
           == (request.tenant, request.operation, request.staff_id, request.incarnation, request.payload_hash, request.identity_handle), "OWNERSHIP_BINDING_MISMATCH")
    identifier(proof.subject)
    if request.expected_subject is not None:
        ensure(proof.subject == request.expected_subject, "OWNERSHIP_BINDING_MISMATCH")
    return proof


@dataclass(frozen=True)
class Profile:
    request: Request
    state: State = State.PENDING
    version: int = 1
    intent: str = "NONE"
    proof: object = None
    group_confirmed: bool = False
    revoked: bool = False
    failure: str = "NONE"
    is_active: bool = False
    is_assignable: bool = False
    invitation: str = "NONE"


def fence(profile, expected):
    ensure(type(profile) is Profile, "MALFORMED_PROFILE")
    ensure(revision(expected) == revision(profile.version), "STALE_PROFILE")
    ensure(profile.revoked is False, "REVOKED")
    ensure(profile.state in {State.PENDING, State.IDENTITY}, "NOT_PROVISIONING")
    ensure(profile.is_active is False and profile.is_assignable is False, "UNSAFE_PENDING_FLAGS")


def stage(request, admission):
    validate_admission(request, admission)
    return Profile(request)


def claim_effect(profile, expected, effect):
    fence(profile, expected)
    ensure(profile.intent == "NONE", "RECONCILIATION_REQUIRED")
    ensure(effect in {"CREATE", "LINK", "GROUP"}, "INVALID_EFFECT")
    if effect in {"CREATE", "LINK"}:
        ensure(profile.proof is None, "IDENTITY_ALREADY_KNOWN")
        ensure((effect == "LINK") == (profile.request.mode == "LINK_EXISTING" or profile.request.expected_subject is not None), "MODE_MISMATCH")
    else:
        ensure(type(profile.proof) is Proof and not profile.group_confirmed, "IDENTITY_PROOF_REQUIRED")
    return replace(profile, state=State.IDENTITY, version=next_revision(profile.version), intent=effect)


def confirm_identity(profile, expected, proof, allowed_issuer):
    fence(profile, expected)
    ensure(profile.intent in {"CREATE", "LINK"}, "NO_IDENTITY_INTENT")
    validate_proof(profile.request, proof, allowed_issuer)
    return replace(profile, version=next_revision(profile.version), proof=proof, intent="NONE")


def confirm_group(profile, expected, subject, group):
    fence(profile, expected)
    ensure(profile.intent == "GROUP" and type(profile.proof) is Proof, "NO_GROUP_INTENT")
    ensure(subject == profile.proof.subject and group == profile.request.target_role, "GROUP_BINDING_MISMATCH")
    return replace(profile, version=next_revision(profile.version), group_confirmed=True, intent="NONE")


def activate(profile, expected):
    fence(profile, expected)
    ensure(type(profile.proof) is Proof and profile.group_confirmed is True and profile.intent == "NONE", "INCOMPLETE_PROVISIONING")
    return replace(profile, state=State.ACTIVE, version=next_revision(profile.version),
                   is_active=True, is_assignable=profile.request.assignable, invitation="PENDING")


def fail(profile, expected, reason):
    ensure(type(profile) is Profile and revision(expected) == revision(profile.version), "STALE_PROFILE")
    ensure(reason in {"OWNERSHIP_UNVERIFIED", "EXTERNAL_FAILURE", "ABANDONED", "REVOKED"}, "INVALID_FAILURE")
    return replace(profile, state=State.FAILED, version=next_revision(profile.version),
                   failure=reason, is_active=False, is_assignable=False,
                   revoked=profile.revoked or reason == "REVOKED", invitation="CANCELLED")


def retry_failed(profile, expected):
    ensure(type(profile) is Profile and revision(expected) == revision(profile.version), "STALE_PROFILE")
    ensure(profile.state == State.FAILED and profile.failure == "EXTERNAL_FAILURE"
           and profile.revoked is False, "MANUAL_RECOVERY_REQUIRED")
    # Intent retained: unknown external outcome must be reconciled, not reissued.
    return replace(profile, state=State.IDENTITY, version=next_revision(profile.version), failure="NONE", invitation="NONE")


def assignment_disposition(record):
    if type(record) is dict:
        return "LEGACY_PATH_REQUIRED" if "provisioning_state" not in record else "PROVISIONING_CONTRACT_REQUIRED"
    ensure(type(record) is Profile, "MALFORMED_PROFILE")
    return "PROFILE_READY_ONLY" if (record.state == State.ACTIVE and record.is_active is True
        and record.is_assignable is True and record.revoked is False) else "DENIED_INCOMPLETE"


def owner_execution_eligible(_record):
    return False  # No canonical worker linkage or execution authorization in this package.
