"""UNWIRED local STAFF provisioning specification. No SDK, I/O or authentication.

Proof/context instances model server-verified preconditions, never client JSON.
Production persistence, identity proof and invitation providers are not implemented.
"""
from dataclasses import dataclass, replace
from enum import Enum
import re
from urllib.parse import urlsplit


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
    evidence_revision: int = 1


def validate_proof(request, proof, allowed_issuer):
    validate_request(request)
    ensure(type(proof) is Proof and proof.verified is True, "OWNERSHIP_UNVERIFIED")
    ensure(type(allowed_issuer) is str, "UNTRUSTED_ISSUER")
    try:
        issuer = urlsplit(allowed_issuer)
    except ValueError:
        raise ProvisioningError("UNTRUSTED_ISSUER") from None
    ensure(issuer.scheme == "https" and bool(issuer.hostname) and not issuer.username
           and not issuer.password and not issuer.query and not issuer.fragment, "UNTRUSTED_ISSUER")
    ensure(proof.issuer == allowed_issuer, "WRONG_ISSUER")
    ensure((proof.tenant, proof.operation, proof.staff_id, proof.incarnation, proof.payload_hash, proof.identity_handle)
           == (request.tenant, request.operation, request.staff_id, request.incarnation, request.payload_hash, request.identity_handle), "OWNERSHIP_BINDING_MISMATCH")
    identifier(proof.subject)
    revision(proof.evidence_revision)
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
    confirmed_subject: object = None
    proof_revision: int = 0
    group_subject: object = None
    group_role: object = None
    group_proof_revision: int = 0


def validate_persisted_proof(profile, allowed_issuer):
    ensure(type(profile) is Profile, "MALFORMED_PROFILE")
    proof = validate_proof(profile.request, profile.proof, allowed_issuer)
    identifier(profile.confirmed_subject)
    ensure(proof.subject == profile.confirmed_subject, "PERSISTED_SUBJECT_MISMATCH")
    ensure(proof.evidence_revision == revision(profile.proof_revision), "STALE_PROOF")
    return proof


def validate_group_proof(profile):
    ensure(profile.group_confirmed is True and profile.group_subject == profile.confirmed_subject
           and profile.group_role == profile.request.target_role
           and revision(profile.group_proof_revision) == profile.proof_revision, "STALE_GROUP_PROOF")


def validate_active_profile(profile, allowed_issuer):
    ensure(type(profile) is Profile and profile.state == State.ACTIVE and profile.is_active is True
           and profile.revoked is False and type(profile.is_assignable) is bool, "INVALID_ACTIVE_PROFILE")
    validate_persisted_proof(profile, allowed_issuer)
    validate_group_proof(profile)


def fence(profile, expected):
    ensure(type(profile) is Profile, "MALFORMED_PROFILE")
    ensure(revision(expected) == revision(profile.version), "STALE_PROFILE")
    ensure(profile.revoked is False, "REVOKED")
    ensure(profile.state in {State.PENDING, State.IDENTITY}, "NOT_PROVISIONING")
    ensure(profile.is_active is False and profile.is_assignable is False, "UNSAFE_PENDING_FLAGS")


def stage(request, admission):
    validate_admission(request, admission)
    return Profile(request)


def claim_effect(profile, expected, effect, allowed_issuer=None):
    fence(profile, expected)
    ensure(profile.intent == "NONE", "RECONCILIATION_REQUIRED")
    ensure(effect in {"CREATE", "LINK", "GROUP"}, "INVALID_EFFECT")
    if effect in {"CREATE", "LINK"}:
        ensure(profile.proof is None, "IDENTITY_ALREADY_KNOWN")
        ensure((effect == "LINK") == (profile.request.mode == "LINK_EXISTING" or profile.request.expected_subject is not None), "MODE_MISMATCH")
    else:
        validate_persisted_proof(profile, allowed_issuer)
        ensure(profile.group_confirmed is False, "IDENTITY_PROOF_REQUIRED")
    return replace(profile, state=State.IDENTITY, version=next_revision(profile.version), intent=effect)


def confirm_identity(profile, expected, proof, allowed_issuer):
    fence(profile, expected)
    ensure(profile.intent in {"CREATE", "LINK"}, "NO_IDENTITY_INTENT")
    ensure(profile.proof is None and profile.confirmed_subject is None and profile.proof_revision == 0,
           "IDENTITY_ALREADY_KNOWN")
    validate_proof(profile.request, proof, allowed_issuer)
    return replace(profile, version=next_revision(profile.version), proof=proof, intent="NONE",
                   confirmed_subject=proof.subject, proof_revision=proof.evidence_revision)


def confirm_group(profile, expected, subject, group, allowed_issuer=None):
    fence(profile, expected)
    validate_persisted_proof(profile, allowed_issuer)
    ensure(profile.intent == "GROUP", "NO_GROUP_INTENT")
    ensure(subject == profile.proof.subject and group == profile.request.target_role, "GROUP_BINDING_MISMATCH")
    return replace(profile, version=next_revision(profile.version), group_confirmed=True, intent="NONE",
                   group_subject=subject, group_role=group, group_proof_revision=profile.proof_revision)


def activate(profile, expected, allowed_issuer=None):
    fence(profile, expected)
    ensure(type(profile.proof) is Proof and profile.group_confirmed is True and profile.intent == "NONE", "INCOMPLETE_PROVISIONING")
    validate_persisted_proof(profile, allowed_issuer)
    validate_group_proof(profile)
    return replace(profile, state=State.ACTIVE, version=next_revision(profile.version),
                   is_active=True, is_assignable=profile.request.assignable, invitation="PENDING")


def fail(profile, expected, reason, request=None, authorization=None, initiating_subject=None):
    ensure(type(profile) is Profile and revision(expected) == revision(profile.version), "STALE_PROFILE")
    ensure(reason in {"OWNERSHIP_UNVERIFIED", "EXTERNAL_FAILURE", "ABANDONED", "REVOKED"}, "INVALID_FAILURE")
    if reason in {"ABANDONED", "REVOKED"}:
        authorize_recovery(profile, request, authorization, initiating_subject,
                           "ABANDON" if reason == "ABANDONED" else "REVOKE")
    return replace(profile, state=State.FAILED, version=next_revision(profile.version),
                   failure=reason, is_active=False, is_assignable=False,
                   revoked=profile.revoked or reason == "REVOKED", invitation="CANCELLED")


def authorize_resume(profile, admission, initiating_subject, allowed_issuer):
    ensure(type(profile) is Profile, "MALFORMED_PROFILE")
    validate_admission(profile.request, admission)
    ensure(admission.actor_subject == initiating_subject, "ACTOR_MISMATCH")
    if profile.proof is not None:
        validate_persisted_proof(profile, allowed_issuer)


@dataclass(frozen=True)
class RecoveryAuthorization:
    tenant: str
    staff_id: str
    operation: str
    incarnation: str
    expected_version: int
    actor_subject: str
    actor_role: str
    action: str
    verified: bool = False
    current: bool = False
    protected_target: bool = True


def authorize_recovery(profile, request, authorization, initiating_subject, action):
    ensure(type(profile) is Profile and type(authorization) is RecoveryAuthorization, "TRUSTED_RECOVERY_REQUIRED")
    validate_request(request)
    ensure(authorization.verified is True and authorization.current is True, "UNAUTHORIZED_RECOVERY")
    ensure(authorization.protected_target is False, "PROTECTED_TARGET")
    ensure(type(authorization.actor_role) is str and authorization.actor_role in {"owner", "admin"}, "DENIED_ROLE")
    identifier(authorization.actor_subject)
    ensure(authorization.actor_subject == initiating_subject, "DELEGATED_RECOVERY_POLICY_PENDING")
    ensure(action in {"ABANDON", "REVOKE"} and authorization.action == action, "RECOVERY_ACTION_MISMATCH")
    ensure(request == profile.request, "RECOVERY_TARGET_MISMATCH")
    ensure((authorization.tenant, authorization.staff_id, authorization.operation, authorization.incarnation)
           == (request.tenant, request.staff_id, request.operation, request.incarnation), "RECOVERY_TARGET_MISMATCH")
    ensure(revision(authorization.expected_version) == revision(profile.version), "STALE_RECOVERY")


def retry_failed(profile, expected, admission=None, initiating_subject=None, allowed_issuer=None):
    authorize_resume(profile, admission, initiating_subject, allowed_issuer)
    ensure(type(profile) is Profile and revision(expected) == revision(profile.version), "STALE_PROFILE")
    ensure(profile.state == State.FAILED and profile.failure == "EXTERNAL_FAILURE"
           and profile.revoked is False, "MANUAL_RECOVERY_REQUIRED")
    # Intent retained: unknown external outcome must be reconciled, not reissued.
    return replace(profile, state=State.IDENTITY, version=next_revision(profile.version), failure="NONE", invitation="NONE")


def assignment_disposition(record, allowed_issuer=None):
    if type(record) is dict:
        return "LEGACY_PATH_REQUIRED" if "provisioning_state" not in record else "PROVISIONING_CONTRACT_REQUIRED"
    ensure(type(record) is Profile, "MALFORMED_PROFILE")
    if record.state == State.ACTIVE:
        validate_active_profile(record, allowed_issuer)
        return "PROFILE_READY_ONLY" if record.is_assignable is True else "DENIED_INCOMPLETE"
    return "DENIED_INCOMPLETE"


def owner_execution_eligible(_record):
    return False  # No canonical worker linkage or execution authorization in this package.
