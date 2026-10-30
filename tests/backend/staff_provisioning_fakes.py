"""Synthetic persistence/identity/outbox doubles and test-only coordinator.

MemoryState simulates durable backing across coordinator restarts; it is not a
production database. No SDK, network, credentials, secrets or real identities.
"""
from dataclasses import dataclass, field, replace
from common.staff_provisioning_contract import (
    State, Proof, ProvisioningError, ensure, stage, reservation_for,
    claim_effect, confirm_identity, confirm_group, activate, fail, retry_failed,
)

ISSUER = "https://issuer.example.invalid/pool-a"


class PersistenceRefused(ProvisioningError):
    pass


class UnknownOutcome(ProvisioningError):
    pass


class KnownExternalFailure(ProvisioningError):
    pass


@dataclass
class MemoryState:
    rows: dict = field(default_factory=dict)
    receipts: dict = field(default_factory=dict)
    claims: dict = field(default_factory=dict)
    reservations: dict = field(default_factory=dict)
    actors: dict = field(default_factory=dict)
    markers: set = field(default_factory=set)
    revoked: set = field(default_factory=set)
    outbox: dict = field(default_factory=dict)
    quota_versions: dict = field(default_factory=dict)


class Store:
    def __init__(self, backing=None, capacity=2, legacy_active=0):
        self.data = backing or MemoryState()
        self.capacity = capacity
        self.legacy_active = legacy_active
        self.refuse = set()
        self.events = []

    def key(self, request):
        return (request.tenant, request.staff_id)

    def guard(self, profile):
        key = self.key(profile.request)
        ensure(self.legacy_active + sum(k[0] == profile.request.tenant for k in self.data.rows) <= self.capacity, "STAFF_LIMIT")
        ensure(key not in self.data.markers, "CANONICAL_MARKER_CONFLICT")
        ensure(key not in self.data.revoked, "REVOKED")
        reservation = self.data.reservations.get(key)
        ensure(reservation == reservation_for(profile.request) and not reservation.retired, "RESERVATION_CONFLICT")

    def begin(self, request, admission):
        candidate = stage(request, admission)
        key, op = self.key(request), (request.tenant, request.operation)
        if op in self.data.receipts:
            ensure(self.data.receipts[op] == key, "OPERATION_CONFLICT")
            stored = self.data.rows[key]
            ensure(stored.request == request, "OPERATION_CONFLICT")
            ensure(self.data.actors[key] == admission.actor_subject, "ACTOR_MISMATCH")
            self.guard(stored)
            return stored
        if "stage" in self.refuse:
            raise PersistenceRefused("STAGE_REFUSED")
        ensure(key not in self.data.rows and key not in self.data.reservations, "IDENTITY_REUSE_DENIED")
        ensure(key not in self.data.markers, "CANONICAL_MARKER_CONFLICT")
        ensure(admission.max_staff == self.capacity and admission.legacy_active_count == self.legacy_active, "ENTITLEMENT_SNAPSHOT_MISMATCH")
        version = self.data.quota_versions.get(request.tenant, 1)
        ensure(admission.quota_revision == version, "STALE_QUOTA")
        pending_or_active = sum(k[0] == request.tenant for k in self.data.rows)
        ensure(self.legacy_active + pending_or_active < self.capacity, "STAFF_LIMIT")
        for claim in request.uniqueness_keys + (request.identity_handle,):
            ensure((request.tenant, claim) not in self.data.claims, "DUPLICATE_STAFF")
        # One simulated atomic commit: profile + operation receipt + uniqueness +
        # quota admission + non-expiring exact-key reservation. No external effect.
        self.data.rows[key] = candidate
        self.data.receipts[op] = key
        self.data.actors[key] = admission.actor_subject
        self.data.reservations[key] = reservation_for(request)
        for claim in request.uniqueness_keys + (request.identity_handle,):
            self.data.claims[(request.tenant, claim)] = op
        self.data.quota_versions[request.tenant] = version + 1
        self.events.append("STAGED")
        return candidate

    def save(self, current, updated, label):
        self.guard(current)
        key = self.key(current.request)
        ensure(self.data.rows.get(key) == current, "STALE_PROFILE")
        ensure(updated.request == current.request and updated.version == current.version + 1, "INVALID_UPDATE")
        if label in self.refuse:
            raise PersistenceRefused("PERSISTENCE_REFUSED")
        self.data.rows[key] = updated
        if label == "finalize":
            # Outbox creation is part of the same simulated commit as ACTIVE.
            self.data.outbox[key] = {"state": "PENDING", "key": (current.request.operation, current.request.incarnation, "welcome-v1")}
        self.events.append(label)
        return updated

    def claim_invitation(self, request, expected_version):
        key = self.key(request)
        profile = self.data.rows[key]
        self.guard(profile)
        ensure(profile.version == expected_version and profile.state == State.ACTIVE
               and profile.is_active is True, "STALE_INVITATION_PROFILE")
        entry = self.data.outbox[key]
        ensure(entry["state"] == "PENDING", "INVITATION_ALREADY_CLAIMED")
        entry["state"] = "INFLIGHT"  # Simulated atomic profile/outbox CAS.
        return entry["key"]

    def revoke(self, request):
        key = self.key(request)
        old = self.data.rows[key]
        self.data.rows[key] = fail(old, old.version, "REVOKED")
        self.data.revoked.add(key)
        if key in self.data.outbox:
            self.data.outbox[key]["state"] = "CANCELLED"

    def abandon(self, request):
        key = self.key(request)
        old = self.data.rows[key]
        self.data.rows[key] = fail(old, old.version, "ABANDONED")
        # Keep all claims, receipts and reservation; no identity deletion or reuse.


class Identity:
    def __init__(self):
        self.identities = {}
        self.existing_proofs = {}
        self.groups = set()
        self.calls = []
        self.create_timeout = False
        self.group_timeout = False
        self.group_failure = False
        self.unknown_reconciliation = False
        self.after_create = None
        self.after_group = None

    def proof(self, request):
        return Proof(request.tenant, ISSUER, "subject-" + request.identity_handle,
                     request.operation, request.staff_id, request.incarnation,
                     request.payload_hash, request.identity_handle, verified=True)

    def create(self, request):
        self.calls.append("CREATE")
        key = (request.tenant, request.identity_handle)
        if key in self.identities:
            ensure(request.mode == "CREATE_OR_LINK", "EXISTING_IDENTITY")
            ensure(request.expected_subject is not None, "OWNERSHIP_UNVERIFIED")
            proof = self.existing_proofs.get(key)
            ensure(proof is not None, "OWNERSHIP_UNVERIFIED")
            return proof
        result = self.proof(request)
        self.identities[key] = result
        if self.after_create:
            self.after_create()
        if self.create_timeout:
            raise UnknownOutcome("CREATE_OUTCOME_UNKNOWN")
        return result

    def link(self, request):
        self.calls.append("VERIFY_EXISTING")
        proof = self.existing_proofs.get((request.tenant, request.identity_handle))
        ensure(proof is not None, "OWNERSHIP_UNVERIFIED")
        return proof

    def reconcile_identity(self, request):
        self.calls.append("RECONCILE_IDENTITY")
        if self.unknown_reconciliation:
            raise UnknownOutcome("OWNERSHIP_OUTCOME_UNKNOWN")
        proof = self.identities.get((request.tenant, request.identity_handle))
        if request.mode in {"CREATE_OR_LINK", "LINK_EXISTING"}:
            proof = self.existing_proofs.get((request.tenant, request.identity_handle), proof)
        ensure(proof is not None, "OWNERSHIP_UNVERIFIED")
        return proof

    def ensure_group(self, profile):
        self.calls.append("GROUP")
        if self.group_failure:
            raise KnownExternalFailure("GROUP_FAILED")
        self.groups.add((profile.proof.subject, profile.request.target_role))
        if self.after_group:
            self.after_group()
        if self.group_timeout:
            raise UnknownOutcome("GROUP_OUTCOME_UNKNOWN")

    def group_present(self, profile):
        self.calls.append("RECONCILE_GROUP")
        if self.unknown_reconciliation:
            raise UnknownOutcome("GROUP_OUTCOME_UNKNOWN")
        return (profile.proof.subject, profile.request.target_role) in self.groups


def provision(store, identity, request, admission):
    profile = store.begin(request, admission)
    if profile.state == State.ACTIVE:
        return profile
    if profile.state == State.FAILED:
        profile = store.save(profile, retry_failed(profile, profile.version), "retry")
    try:
        if profile.proof is None:
            store.guard(profile)
            if profile.intent == "NONE":
                effect = "LINK" if request.mode == "LINK_EXISTING" or request.expected_subject is not None else "CREATE"
                profile = store.save(profile, claim_effect(profile, profile.version, effect), "identity-intent")
                proof = identity.link(request) if effect == "LINK" else identity.create(request)
            else:
                proof = identity.reconcile_identity(request)  # Never blind retry after ambiguity.
            profile = store.save(profile, confirm_identity(profile, profile.version, proof, ISSUER), "identity-confirmed")
        if not profile.group_confirmed:
            store.guard(profile)
            if profile.intent == "NONE":
                profile = store.save(profile, claim_effect(profile, profile.version, "GROUP"), "group-intent")
                identity.ensure_group(profile)
            elif not identity.group_present(profile):
                identity.ensure_group(profile)  # Mock contract: authoritative absence + idempotent ensure.
            profile = store.save(profile, confirm_group(profile, profile.version, profile.proof.subject, request.target_role), "group-confirmed")
        return store.save(profile, activate(profile, profile.version), "finalize")
    except KnownExternalFailure:
        store.save(profile, fail(profile, profile.version, "EXTERNAL_FAILURE"), "failed")
        raise
    except ProvisioningError as exc:
        if str(exc) in {"OWNERSHIP_UNVERIFIED", "OWNERSHIP_BINDING_MISMATCH", "WRONG_ISSUER", "EXISTING_IDENTITY"}:
            store.save(profile, fail(profile, profile.version, "OWNERSHIP_UNVERIFIED"), "failed")
        raise


class Invitations:
    def __init__(self):
        self.attempts = []
        self.timeout = False

    def send(self, key):
        self.attempts.append(key)
        if self.timeout:
            raise UnknownOutcome("INVITATION_OUTCOME_UNKNOWN")


def dispatch_invitation(store, invitations, request):
    key = store.key(request)
    profile = store.data.rows[key]
    store.guard(profile)
    ensure(profile.state == State.ACTIVE and profile.is_active is True, "NOT_ACTIVE")
    entry = store.data.outbox[key]
    if entry["state"] != "PENDING":
        return entry["state"]  # SENT/INFLIGHT/UNKNOWN never automatically retried.
    delivery_key = store.claim_invitation(request, profile.version)
    store.guard(store.data.rows[key])
    try:
        invitations.send(delivery_key)
    except UnknownOutcome:
        entry["state"] = "UNKNOWN"
        raise
    if "invitation-ack" in store.refuse:
        raise PersistenceRefused("INVITATION_ACK_REFUSED")
    entry["state"] = "SENT"
    return "SENT"
