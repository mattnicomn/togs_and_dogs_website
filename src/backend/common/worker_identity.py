"""INACTIVE contracts. No JWT verification, authorization grant, enrollment or I/O."""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re
from urllib.parse import urlsplit

MAX_REVISION = 2**63 - 1


class Failure(str, Enum):
    MALFORMED = "MALFORMED_RECORD"
    UNKNOWN_CONTRACT = "UNKNOWN_CONTRACT"
    WRONG_TENANT = "WRONG_TENANT"
    UNLINKED = "UNLINKED"
    INACTIVE = "INACTIVE"
    LEGACY_ONLY = "LEGACY_ONLY"
    STALE = "STALE_REVISION"
    WRONG_CHILD = "WRONG_CHILD"
    MISMATCH = "IDENTITY_MISMATCH"
    POLICY_PENDING = "POLICY_PENDING"


class ContractError(ValueError):
    def __init__(self, category):
        self.category = category
        super().__init__(category.value)  # Never echo record contents.


def require(condition, category=Failure.MALFORMED):
    if not condition:
        raise ContractError(category)


def identifier(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) is not None)
    return value


def tenant_id(value):
    require(type(value) is str and re.fullmatch(r"[a-z0-9_]{3,64}", value) is not None)
    return value


def worker_id(value):
    require(type(value) is str and re.fullmatch(r"wrk_[0-9a-f]{32}", value) is not None)
    return value


def revision(value):
    """DB boundary only: finite integral Decimal or exact int. No float/string/bool."""
    if type(value) is Decimal:
        require(value.is_finite())
        require(value == value.to_integral_value() and 1 <= value <= MAX_REVISION)
        value = int(value)
    require(type(value) is int and 1 <= value <= MAX_REVISION)
    return value


def next_revision(value):
    value = revision(value)
    require(value < MAX_REVISION)
    return value + 1


def contract_version(value):
    value = revision(value)
    require(value == 1, Failure.UNKNOWN_CONTRACT)
    return value


def flag(value):
    require(type(value) is bool)
    return value


def digest(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None)
    return value


def operation_id(value):
    require(type(value) is str and re.fullmatch(r"op_[0-9a-f]{32}", value) is not None)
    return value


def payload_digest(payload):
    """Caller must supply canonical serialized bytes derived from validated input."""
    require(type(payload) is bytes)
    return hashlib.sha256(payload).hexdigest()


def row(value):
    require(type(value) is dict)
    return value


def shape(record, required):
    row(record)
    require(required <= record.keys())


def same_tenant(record, tenant):
    require(record.get("company_id") == tenant_id(tenant), Failure.WRONG_TENANT)


@dataclass(frozen=True)
class Principal:
    tenant: str
    issuer: str
    subject: str
    role: str


def principal_from_verified_claims(claims, trusted_issuers, expected_tenant):
    """Precondition: upstream verified signature/client/token/current membership.

    Not an event adapter. Never call this with request-body claims. This function
    only validates shape/binding; it cannot attest that its precondition occurred.
    """
    row(claims)
    tenant = tenant_id(expected_tenant)
    require(claims.get("custom:company_id") == tenant, Failure.WRONG_TENANT)
    issuer, subject = claims.get("iss"), claims.get("sub")
    require(type(trusted_issuers) in (tuple, frozenset) and bool(trusted_issuers))
    require(type(issuer) is str and issuer in trusted_issuers)
    try:
        parts = urlsplit(issuer)
    except ValueError:
        raise ContractError(Failure.MALFORMED) from None
    require(parts.scheme == "https" and bool(parts.hostname) and not parts.username
            and not parts.password and not parts.query and not parts.fragment)
    identifier(subject)
    groups = claims.get("cognito:groups")
    require(type(groups) is list and all(type(g) is str for g in groups))
    # No email-derived role and no owner -> legacy staff fallback.
    role = next((r for r in ("owner", "admin", "staff", "client") if r in groups), "unknown")
    return Principal(tenant, issuer, subject, role)


def validate_principal(principal):
    require(type(principal) is Principal)
    tenant_id(principal.tenant)
    identifier(principal.subject)
    require(type(principal.role) is str and principal.role in {"owner", "admin", "staff", "client", "unknown"})
    require(type(principal.issuer) is str)
    try:
        parts = urlsplit(principal.issuer)
    except ValueError:
        raise ContractError(Failure.MALFORMED) from None
    require(parts.scheme == "https" and bool(parts.hostname) and not parts.username
            and not parts.password and not parts.query and not parts.fragment)


def principal_key(principal):
    validate_principal(principal)
    tenant = principal.tenant
    encoded = json.dumps([principal.issuer, principal.subject], separators=(",", ":")).encode("utf-8")
    return {"PK": "COMPANY#" + tenant, "SK": "PRINCIPAL_WORKER#" + hashlib.sha256(encoded).hexdigest()}


def parse_worker(record, tenant):
    required = {"PK", "SK", "entity_type", "company_id", "worker_id", "staff_id",
                "contract_version", "version", "is_active", "is_assignable"}
    shape(record, required)
    require(set(record) == required)  # Proposed canonical record has no implicit extras.
    same_tenant(record, tenant)
    wid, sid = worker_id(record["worker_id"]), identifier(record["staff_id"])
    require(record["PK"] == "COMPANY#" + tenant and record["SK"] == "WORKER#" + wid)
    require(record["entity_type"] == "WORKER")
    return dict(record, contract_version=contract_version(record["contract_version"]),
                version=revision(record["version"]), worker_id=wid, staff_id=sid,
                is_active=flag(record["is_active"]), is_assignable=flag(record["is_assignable"]))


def parse_link(record, principal):
    validate_principal(principal)
    if record is None:
        raise ContractError(Failure.UNLINKED)
    required = {"PK", "SK", "entity_type", "company_id", "issuer", "subject", "worker_id",
                "staff_id", "contract_version", "version", "is_active"}
    shape(record, required)
    require(set(record) == required)
    same_tenant(record, principal.tenant)
    require({k: record[k] for k in ("PK", "SK")} == principal_key(principal))
    require(record["entity_type"] == "PRINCIPAL_WORKER_LINK")
    require((record["issuer"], record["subject"]) == (principal.issuer, principal.subject), Failure.MISMATCH)
    return dict(record, worker_id=worker_id(record["worker_id"]), staff_id=identifier(record["staff_id"]),
                version=revision(record["version"]), contract_version=contract_version(record["contract_version"]),
                is_active=flag(record["is_active"]))


def parse_staff(record, tenant):
    shape(record, {"PK", "SK", "company_id", "staff_id", "canonical_worker_id",
                   "identity_revision", "cognito_sub", "is_active", "is_assignable"})
    same_tenant(record, tenant)
    sid = identifier(record["staff_id"])
    require(record["PK"] == "COMPANY#" + tenant and record["SK"] == "STAFF#" + sid)
    identifier(record["cognito_sub"])
    require(record["cognito_sub"] != "unlinked", Failure.UNLINKED)
    return {k: record[k] for k in ("PK", "SK", "company_id", "staff_id", "cognito_sub")} | {
        "canonical_worker_id": worker_id(record["canonical_worker_id"]),
        "identity_revision": revision(record["identity_revision"]),
        "is_active": flag(record["is_active"]), "is_assignable": flag(record["is_assignable"])}


def assess_linkage(principal, worker, link, staff):
    """Validate consistency only. All well-formed owner cases remain pending."""
    try:
        validate_principal(principal)
        w = parse_worker(worker, principal.tenant)
        l = parse_link(link, principal)
        s = parse_staff(staff, principal.tenant)
        require((w["worker_id"], w["staff_id"]) == (l["worker_id"], l["staff_id"])
                == (s["canonical_worker_id"], s["staff_id"]), Failure.MISMATCH)
        require(s["cognito_sub"] == principal.subject, Failure.MISMATCH)
        require(w["is_active"] and w["is_assignable"] and l["is_active"]
                and s["is_active"] and s["is_assignable"], Failure.INACTIVE)
    except ContractError as exc:
        return exc.category
    return Failure.POLICY_PENDING  # Never an authorization grant, including staff/admin.
