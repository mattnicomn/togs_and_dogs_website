"""INACTIVE shared REQUEST write-safety contract (S0a). Standard library only.

DESIGN SCOPE (S0a + S0b): PURE functions that DECIDE and CONSTRUCT the
security-relevant surface of a REQUEST mutation. NOTHING here executes a write,
opens a boto3/SDK client, touches the network or a DynamoDB table, imports a
handler, or is imported by any production module. There is no create/delete/
tombstone/transaction EXECUTION here; S0b constructs (but never executes) a
create-only transaction specification. Delete/tombstone-on-delete (S0c) and
real execution (S0d) are later, separately approved slices.

What this module provides:
  * classify_adoption(snapshot)                 -> AdoptionDisposition   [S0a]
  * build_update(key, expected, plan, disposition) -> UpdateSpec | Refusal  [S0a]
  * interpret_failure(evidence)                 -> FailureClassification [S0a]
  * build_create(key, intent, lifetime_evidence) -> CreateSpec | Refusal [S0b]

Security posture (see the acceptance doc for the full contract):
  * A helper CANNOT protect legacy writers. It only fences writes that call it.
    Missing/invalid version or lifetime evidence is QUARANTINED, never silently
    adopted. There is NO operational SEEDING / bypass mode in this slice.
  * Conditions bind tenant (company_id), the exact prior revision (and advance
    it), incarnation when present, and the source status ONLY for a status
    transition the caller declares.
  * A protected CLIENT write must carry PR54-complete ownership coverage:
    present/absent identity fields that are well-formed, duplicate-free,
    DISJOINT and EXHAUSTIVE over the identity universe. Present fields are
    equality-fenced; absent fields are attribute_not_exists-fenced so an insert
    without a revision bump is still rejected.
  * Only named SET / REMOVE operations. Never a whole-item/unconditional upsert.
    Unknown persisted fields are preserved (they are simply never named).
  * Failure causes are NOT inferred from a bare conditional failure; the default
    is INDETERMINATE unless specific evidence justifies a precise classification.

These are STRUCTURAL evidence checks. They do NOT authenticate provenance: a
well-formed snapshot/plan is a shape, not proof that the trusted adapter really
observed it. Real provenance/freshness/authentication remain separate, still
pending gates.
"""
from dataclasses import dataclass
from hashlib import sha256
import json
import re


IDENTITY_UNIVERSE = ("client_email", "linked_client_profile_id", "cognito_sub")
# Identity fields that constitute an immutable subject/profile fence; an email
# alone is never a sufficient ownership fence (mirrors the inactive contract).
SUBJECT_IDENTITY = ("linked_client_profile_id", "cognito_sub")
_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}")
# Reserved attribute names a caller plan may never SET/REMOVE through this helper
# because the helper owns their write-time semantics (tenant key, versioning,
# lifecycle, audit append). Preventing a caller from naming them stops a plan
# from, e.g., clearing record_incarnation or rewriting legacy_write_revision.
RESERVED_FIELDS = frozenset({
    "PK", "SK", "company_id", "client_id", "request_id",
    "legacy_write_revision", "record_incarnation",
})


# ---------------------------------------------------------------------------
# Result / input value types (immutable, inspectable)
# ---------------------------------------------------------------------------

# Adoption dispositions.
ADOPT_ELIGIBLE = "ADOPT_ELIGIBLE"            # well-formed version (and incarnation) -> fence normally
QUARANTINE_UNVERSIONED = "QUARANTINE_UNVERSIONED"  # compatible but missing/invalid version/lifetime -> refuse by default
REFUSE_INELIGIBLE = "REFUSE_INELIGIBLE"      # not a protected-path candidate -> hard refuse

# Failure classifications.
STALE = "STALE"
TENANT_MISMATCH = "TENANT_MISMATCH"
RETIRED = "RETIRED"
ABSENT = "ABSENT"
INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True)
class AdoptionDisposition:
    disposition: str
    reasons: tuple


@dataclass(frozen=True)
class ExpectedState:
    """Immutable snapshot the caller read and is writing against.

    revision/incarnation are None when the persisted row did not carry them.
    source_status is supplied ONLY when the write is a status transition that
    must be pinned to the observed status; otherwise None (and no status clause
    is emitted - matching field-disjoint writers that must not depend on status).
    present_identity: tuple of (field, value) the caller relies on as present.
    absent_identity:  tuple of fields the trusted adapter observed ABSENT.
    protected_client: True iff this is a protected CLIENT write (role == client)
                      and must therefore satisfy PR54-complete ownership coverage.
    """
    tenant: str
    revision: object = None          # int or None
    incarnation: object = None       # str or None
    source_status: object = None     # str or None
    read_id: str = ""
    present_identity: tuple = ()
    absent_identity: tuple = ()
    protected_client: bool = False
    # Optional identifiers the caller read for the SAME row. When supplied they
    # must match the identifiers encoded in the target key (see build_update);
    # a mismatch is a hard refusal (a caller must not pair one row's expected
    # state with another row's key). None means "not separately asserted" - the
    # key-derived identifiers are still bound into the write condition regardless.
    request_id: object = None        # str or None
    client_id: object = None         # str or None


@dataclass(frozen=True)
class WritePlan:
    """Named field operations only. No whole-item form exists by construction."""
    set_fields: tuple = ()           # tuple of (name, value)
    remove_fields: tuple = ()        # tuple of names
    append_audit: object = None      # optional single audit entry (dict) for audit_log list_append


@dataclass(frozen=True)
class UpdateSpec:
    """A constructed (not executed) single-item conditional UpdateItem spec."""
    key: dict
    condition_expression: str
    update_expression: str
    names: dict
    values: dict
    advances_revision: bool
    fenced_present: tuple
    fenced_absent: tuple


@dataclass(frozen=True)
class Refusal:
    reason: str
    detail: str = ""


@dataclass(frozen=True)
class FailureEvidence:
    """Evidence available after a failed write.

    kind:
      "conditional_check_failed" - a bare single-item condition failure
                                   (cause NOT observable from the API alone)
      "transaction_cancellation" - carries per-item cancellation reason codes
      "reread"                   - a deliberate post-failure re-read snapshot
    For "transaction_cancellation" supply cancellation_reasons (tuple of codes).
    For "reread" supply the observed row (dict or None) and the ExpectedState the
    write was built from, so the specific divergence can be proven.
    """
    kind: str
    cancellation_reasons: tuple = ()
    observed_row: object = None
    expected: object = None
    tombstone_present: object = None  # True/False/None(unknown)


@dataclass(frozen=True)
class FailureClassification:
    classification: str
    evidence_backed: bool
    reasons: tuple = ()


# ---------------------------------------------------------------------------
# 1. classify_adoption
# ---------------------------------------------------------------------------

def _valid_revision(value):
    # Accept only exact positive bounded integers. bool is a subclass of int and
    # is rejected; floats/Decimals/strings are rejected (parse at the DB boundary
    # belongs elsewhere - here we require an already-canonical integer).
    return type(value) is int and 1 <= value < 2 ** 63


def _valid_incarnation(value):
    return type(value) is str and bool(_ID_RE.fullmatch(value))


def _valid_identifier(value):
    return type(value) is str and bool(_ID_RE.fullmatch(value))


def _is_sequence(value):
    # A real sequence of elements - explicitly NOT a str/bytes (which iterate by
    # character and would otherwise be silently treated as a collection of
    # single-character elements). Only tuple/list are accepted as collections.
    return type(value) in (tuple, list)


def _parse_request_key(key):
    """Validate a REQUEST key and return (request_id, client_id) or None.

    A valid REQUEST key is exactly {"PK": "REQ#<id>", "SK": "CLIENT#<id>"} with
    well-formed identifiers. Anything else (non-dict, extra/missing keys, wrong
    prefixes, malformed ids) returns None so the caller can refuse.
    """
    if type(key) is not dict or set(key) != {"PK", "SK"}:
        return None
    pk, sk = key.get("PK"), key.get("SK")
    if type(pk) is not str or type(sk) is not str:
        return None
    if not pk.startswith("REQ#") or not sk.startswith("CLIENT#"):
        return None
    request_id = pk[len("REQ#"):]
    client_id = sk[len("CLIENT#"):]
    if not _valid_identifier(request_id) or not _valid_identifier(client_id):
        return None
    return request_id, client_id


def classify_adoption(snapshot):
    """Decide whether a persisted REQUEST snapshot is safe to fence.

    snapshot: dict of the persisted row (or None).

    Returns AdoptionDisposition:
      REFUSE_INELIGIBLE      - not a protected-path candidate (missing/mismatched
                               keys/tenant, canonical markers, malformed shape).
      QUARANTINE_UNVERSIONED - compatible BUT missing or invalid version metadata
                               (legacy_write_revision) and/or incarnation. The
                               default is to REFUSE a write on such a row: a
                               missing revision is NOT a safe zero, because an
                               unversioned concurrent writer could change the row
                               without advancing the (absent) revision and a
                               revision fence cannot detect it. There is no
                               SEEDING override in this slice.
      ADOPT_ELIGIBLE         - well-formed revision (and incarnation) present.
    """
    reasons = []
    if type(snapshot) is not dict:
        return AdoptionDisposition(REFUSE_INELIGIBLE, ("MISSING_OR_MALFORMED_SNAPSHOT",))
    # Structural key/tenant presence (a protected-path candidate must at least be
    # an exact REQUEST row with tenant binding). This is structure, not provenance.
    for key_field in ("PK", "SK", "company_id", "client_id", "request_id"):
        if not snapshot.get(key_field):
            reasons.append("MISSING_" + key_field)
    pk = snapshot.get("PK")
    sk = snapshot.get("SK")
    # Correction 2 (PR55 hardening): the PK/SK must be an EXACT, well-formed
    # REQ#<request_id> / CLIENT#<client_id> pair, AND the persisted request_id /
    # client_id attributes must MATCH the identifiers encoded in PK/SK. A row
    # whose own identifiers disagree with its key (or whose key ids are
    # malformed) is REFUSE_INELIGIBLE - not merely quarantined - because its
    # identity is internally inconsistent and must never be adopted.
    parsed = _parse_request_key({"PK": pk, "SK": sk}) if type(pk) is str and type(sk) is str else None
    if type(pk) is str and not pk.startswith("REQ#"):
        reasons.append("NOT_A_REQUEST_PK")
    if type(sk) is str and not sk.startswith("CLIENT#"):
        reasons.append("NOT_A_REQUEST_SK")
    if parsed is None:
        # PK/SK present and prefixed but ids malformed (or key shape invalid).
        if "NOT_A_REQUEST_PK" not in reasons and "NOT_A_REQUEST_SK" not in reasons \
                and not any(r.startswith("MISSING_") for r in reasons):
            reasons.append("MALFORMED_KEY_IDENTIFIER")
    else:
        key_request_id, key_client_id = parsed
        if snapshot.get("request_id") != key_request_id:
            reasons.append("REQUEST_ID_KEY_MISMATCH")
        if snapshot.get("client_id") != key_client_id:
            reasons.append("CLIENT_ID_KEY_MISMATCH")
    if reasons:
        return AdoptionDisposition(REFUSE_INELIGIBLE, tuple(sorted(set(reasons))))

    # Versioning / lifetime evidence. Absent or invalid -> quarantine (never adopt).
    rev = snapshot.get("legacy_write_revision", None)
    if rev is None:
        reasons.append("MISSING_REVISION")
    elif not _valid_revision(rev):
        reasons.append("MALFORMED_REVISION")
    inc = snapshot.get("record_incarnation", None)
    if inc is None:
        reasons.append("MISSING_INCARNATION")
    elif not _valid_incarnation(inc):
        reasons.append("MALFORMED_INCARNATION")

    if reasons:
        return AdoptionDisposition(QUARANTINE_UNVERSIONED, tuple(sorted(set(reasons))))
    return AdoptionDisposition(ADOPT_ELIGIBLE, ())


# ---------------------------------------------------------------------------
# Ownership-coverage validation (PR54-complete) for protected client writes
# ---------------------------------------------------------------------------

def _validate_ownership_coverage(expected):
    """Return None if coverage is valid, else a reason string.

    Mirrors PR54 transaction() mandatory coverage for the protected client path:
    present/absent fields must be known identity fields, duplicate-free within
    each set, DISJOINT across sets, and together EXHAUST the identity universe.
    Also requires a subject/profile identity in the present fence (email alone is
    never a sufficient ownership fence).
    """
    if not _is_sequence(expected.present_identity) or not _is_sequence(expected.absent_identity):
        return "OWNERSHIP_EVIDENCE_SHAPE"
    present = []
    for pair in expected.present_identity:
        if type(pair) is not tuple or len(pair) != 2:
            return "OWNERSHIP_PRESENT_SHAPE"
        f, v = pair
        if f not in IDENTITY_UNIVERSE or type(v) is not str or not v:
            return "OWNERSHIP_PRESENT_FIELD"
        present.append(f)
    absent = list(expected.absent_identity)
    for f in absent:
        if f not in IDENTITY_UNIVERSE:
            return "OWNERSHIP_ABSENT_FIELD"
    if len(present) != len(set(present)) or len(absent) != len(set(absent)):
        return "OWNERSHIP_DUPLICATE"
    if not set(present).isdisjoint(set(absent)):
        return "OWNERSHIP_CONTRADICTION"
    if set(present) | set(absent) != set(IDENTITY_UNIVERSE):
        return "OWNERSHIP_INCOMPLETE"
    if not any(f in SUBJECT_IDENTITY for f in present):
        return "OWNERSHIP_SUBJECT_REQUIRED"
    return None


# ---------------------------------------------------------------------------
# 2. build_update
# ---------------------------------------------------------------------------

def build_update(key, expected, plan, disposition):
    """Construct (NOT execute) a conditional single-item UpdateItem spec.

    Returns an UpdateSpec on success, or a Refusal. Never returns an
    unconditional/upsert spec and never performs a write.

    Refuses when:
      * key/expected/plan/disposition are malformed,
      * disposition is not ADOPT_ELIGIBLE (quarantined/ineligible rows are
        refused - no SEEDING override exists here),
      * the plan is empty or names a reserved/identity field or is malformed,
      * a protected client write lacks PR54-complete ownership coverage, or the
        ownership evidence is contradictory/incomplete/malformed.
    """
    # --- shape checks -------------------------------------------------------
    if type(expected) is not ExpectedState:
        return Refusal("MALFORMED_EXPECTED")
    if type(plan) is not WritePlan:
        return Refusal("MALFORMED_PLAN")
    if type(disposition) is not AdoptionDisposition:
        return Refusal("MALFORMED_DISPOSITION")
    if disposition.disposition != ADOPT_ELIGIBLE:
        # Quarantined or ineligible rows are refused by default.
        return Refusal("ADOPTION_REFUSED", disposition.disposition)

    # Finding A: the key must be an EXACT, well-formed REQUEST key; a
    # non-REQUEST key (wrong prefix, extra attributes, malformed ids) is refused
    # rather than producing a spec that targets an arbitrary item.
    parsed = _parse_request_key(key)
    if parsed is None:
        return Refusal("MALFORMED_KEY")
    key_request_id, key_client_id = parsed

    if type(expected.tenant) is not str or not expected.tenant:
        return Refusal("MALFORMED_TENANT")
    # Finding A: when the caller separately asserts request_id/client_id on the
    # ExpectedState, they MUST match the key - a caller must not pair one row's
    # expected state with another row's key. When not asserted, the key-derived
    # identifiers are still bound into the condition (below). This is a
    # STRUCTURAL consistency check, not proof the adapter actually observed them.
    if expected.request_id is not None and expected.request_id != key_request_id:
        return Refusal("KEY_EXPECTED_MISMATCH", "request_id")
    if expected.client_id is not None and expected.client_id != key_client_id:
        return Refusal("KEY_EXPECTED_MISMATCH", "client_id")
    if not _valid_revision(expected.revision):
        # ADOPT_ELIGIBLE must carry a canonical revision to pin and advance.
        return Refusal("MALFORMED_REVISION")
    # Correction 1 (PR55 hardening): an ADOPT_ELIGIBLE row BY DEFINITION carries a
    # well-formed record_incarnation (classify_adoption quarantines any row that
    # lacks/malforms it). The write MUST therefore pin that incarnation. Require a
    # valid, non-None ExpectedState.incarnation here so the lifetime fence can
    # never be silently omitted on an eligible write - a None or malformed
    # incarnation is refused BEFORE any UpdateSpec is generated. This is not a
    # seeding/adoption override: it tightens (never relaxes) the eligible path.
    if not _valid_incarnation(expected.incarnation):
        return Refusal("MALFORMED_INCARNATION")

    # --- plan checks (named SET/REMOVE only, no reserved/identity fields) ----
    # Finding D: set_fields / remove_fields must be real sequences (tuple/list),
    # NEVER a str/bytes - a string would otherwise be iterated character by
    # character and silently build bogus per-character fields.
    if not _is_sequence(plan.set_fields) or not _is_sequence(plan.remove_fields):
        return Refusal("MALFORMED_PLAN_COLLECTION")
    set_fields = tuple(plan.set_fields)
    remove_fields = tuple(plan.remove_fields)
    if not set_fields and not remove_fields and plan.append_audit is None:
        return Refusal("EMPTY_PLAN")
    named = []
    for pair in set_fields:
        if type(pair) is not tuple or len(pair) != 2 or type(pair[0]) is not str or not pair[0]:
            return Refusal("MALFORMED_SET")
        named.append(pair[0])
    for name in remove_fields:
        if type(name) is not str or not name:
            return Refusal("MALFORMED_REMOVE")
        named.append(name)
    if len(named) != len(set(named)):
        return Refusal("DUPLICATE_FIELD")
    for name in named:
        if name in RESERVED_FIELDS:
            return Refusal("RESERVED_FIELD", name)
        if name in IDENTITY_UNIVERSE:
            # Identity fields are immutable through this helper. A protected
            # client proves ownership via expected.present/absent coverage, never
            # by SET-ing an identity field in the plan.
            return Refusal("IDENTITY_FIELD_IMMUTABLE", name)
        # Finding C: audit_log is owned by the helper's append path. A plan that
        # SETs or REMOVEs audit_log directly would overlap the list_append and
        # produce a DynamoDB-invalid update (two actions on one document path).
        if name == "audit_log":
            return Refusal("AUDIT_FIELD_CONFLICT", name)
    if plan.append_audit is not None and type(plan.append_audit) is not dict:
        return Refusal("MALFORMED_AUDIT")

    # --- protected client ownership coverage (PR54-complete) ----------------
    if expected.protected_client:
        why = _validate_ownership_coverage(expected)
        if why is not None:
            return Refusal(why)
    else:
        # Non-protected callers must not smuggle partial identity evidence that
        # would be silently unenforced; any supplied identity evidence here is
        # still validated for internal consistency (disjoint/known), but not
        # required to be exhaustive.
        # Finding D: guard the identity collections before iterating.
        if not _is_sequence(expected.present_identity) or not _is_sequence(expected.absent_identity):
            return Refusal("OWNERSHIP_EVIDENCE_SHAPE")
        present = []
        for p in expected.present_identity:
            if type(p) is not tuple or len(p) != 2:
                return Refusal("OWNERSHIP_PRESENT_SHAPE")
            present.append(p[0])
        if any(f not in IDENTITY_UNIVERSE for f in present):
            return Refusal("OWNERSHIP_PRESENT_FIELD")
        if any(f not in IDENTITY_UNIVERSE for f in expected.absent_identity):
            return Refusal("OWNERSHIP_ABSENT_FIELD")
        if not set(present).isdisjoint(set(expected.absent_identity)):
            return Refusal("OWNERSHIP_CONTRADICTION")

    # --- condition construction ---------------------------------------------
    names = {"#rev": "legacy_write_revision"}
    values = {":tenant": expected.tenant, ":rev": expected.revision, ":next": expected.revision + 1,
              ":reqid": key_request_id, ":cliid": key_client_id}
    # Finding A: bind tenant AND the key-derived request_id / client_id into the
    # write-time condition so the row's own identifiers must match the key being
    # written (defence in depth beside the key itself).
    conditions = [
        "attribute_exists(PK)", "attribute_exists(SK)",
        "company_id = :tenant",
        "request_id = :reqid",
        "client_id = :cliid",
        "#rev = :rev",
    ]
    # Incarnation pin. Correction 1: always emitted for an eligible write - the
    # incarnation was validated non-None/well-formed above, so the lifetime fence
    # is mandatory and can never be omitted.
    names["#inc"] = "record_incarnation"
    values[":inc"] = expected.incarnation
    conditions.append("#inc = :inc")
    # Source-status pin ONLY for a declared status transition.
    if expected.source_status is not None:
        if type(expected.source_status) is not str or not expected.source_status:
            return Refusal("MALFORMED_SOURCE_STATUS")
        names["#sstat"] = "status"
        values[":sstat"] = expected.source_status
        conditions.append("#sstat = :sstat")
    # Present-identity equality fences.
    fenced_present = []
    for i, (f, v) in enumerate(expected.present_identity):
        nk = "#id" + str(i)
        vk = ":id" + str(i)
        names[nk] = f
        values[vk] = v
        conditions.append(nk + " = " + vk)
        fenced_present.append(f)
    # Absent-identity attribute_not_exists fences (closes the insert-without-bump race).
    fenced_absent = []
    for i, f in enumerate(expected.absent_identity):
        nk = "#na" + str(i)
        names[nk] = f
        conditions.append("attribute_not_exists(" + nk + ")")
        fenced_absent.append(f)

    # --- update expression (named SET/REMOVE + mandatory revision advance) ---
    set_clauses = []
    for i, (f, v) in enumerate(set_fields):
        nk = "#s" + str(i)
        vk = ":s" + str(i)
        names[nk] = f
        values[vk] = v
        set_clauses.append(nk + " = " + vk)
    if plan.append_audit is not None:
        names["#audit"] = "audit_log"
        values[":auditentry"] = [plan.append_audit]
        values[":emptylist"] = []
        set_clauses.append("#audit = list_append(if_not_exists(#audit, :emptylist), :auditentry)")
    # Revision advance is ALWAYS part of the update (never optional).
    set_clauses.append("#rev = :next")

    remove_clauses = []
    for i, f in enumerate(remove_fields):
        nk = "#r" + str(i)
        names[nk] = f
        remove_clauses.append(nk)

    update_expression = "SET " + ", ".join(set_clauses)
    if remove_clauses:
        update_expression += " REMOVE " + ", ".join(remove_clauses)

    return UpdateSpec(
        key={"PK": key["PK"], "SK": key["SK"]},
        condition_expression=" AND ".join(conditions),
        update_expression=update_expression,
        names=names,
        values=values,
        advances_revision=True,
        fenced_present=tuple(fenced_present),
        fenced_absent=tuple(fenced_absent),
    )


# ---------------------------------------------------------------------------
# 3. interpret_failure
# ---------------------------------------------------------------------------

def interpret_failure(evidence):
    """Classify a write failure. Default INDETERMINATE unless evidence justifies.

    A bare conditional-check failure does NOT reveal which clause failed, so it
    is INDETERMINATE (not evidence-backed). A transaction cancellation reason or
    a deliberate post-failure re-read can justify a specific classification.
    Never infers a specific cause from a generic failure alone.
    """
    if type(evidence) is not FailureEvidence:
        return FailureClassification(INDETERMINATE, False, ("MALFORMED_EVIDENCE",))

    if evidence.kind == "conditional_check_failed":
        # Not observable from the API alone.
        return FailureClassification(INDETERMINATE, False, ("CONDITION_FAILED_CAUSE_UNOBSERVABLE",))

    if evidence.kind == "transaction_cancellation":
        reasons = evidence.cancellation_reasons
        # Finding D: cancellation_reasons must be a real sequence, never a str.
        if not _is_sequence(reasons):
            return FailureClassification(INDETERMINATE, False, ("MALFORMED_CANCELLATION_REASONS",))
        # A transaction cancellation reason ALONE never identifies the specific
        # failed condition: DynamoDB does not say WHICH clause failed. Even a
        # ConditionalCheckFailed reason only tells us a precondition was unmet,
        # so without a deliberate, well-formed re-read we stay INDETERMINATE.
        if "ConditionalCheckFailed" not in tuple(reasons):
            return FailureClassification(INDETERMINATE, False, ("NO_CONDITIONAL_REASON",))
        return _classify_from_reread(evidence, require_reread=True)

    if evidence.kind == "reread":
        return _classify_from_reread(evidence, require_reread=True)

    return FailureClassification(INDETERMINATE, False, ("UNKNOWN_EVIDENCE_KIND",))


def _classify_from_reread(evidence, require_reread):
    """Classify from a deliberate post-failure re-read, with proof per cause.

    Finding B: a specific classification (ABSENT/RETIRED/TENANT_MISMATCH/STALE)
    is returned ONLY when the evidence actually proves it. A missing re-read is
    distinguished from an observed absence: without a valid ExpectedState
    baseline AND a definite observation (row dict, row-None-with-proof, or an
    exact-True tombstone) the result is INDETERMINATE, never a confident ABSENT.
    """
    expected = evidence.expected
    # A trustworthy classification needs the baseline the write was built from.
    if type(expected) is not ExpectedState:
        return FailureClassification(INDETERMINATE, False, ("MISSING_OR_MALFORMED_EXPECTED",))

    # Tombstone must be an EXACT bool. Any other type (truthy ints/strings/lists)
    # is malformed evidence, NOT a proven retirement.
    tomb = evidence.tombstone_present
    if tomb is not None and type(tomb) is not bool:
        return FailureClassification(INDETERMINATE, False, ("MALFORMED_TOMBSTONE_EVIDENCE",))
    if tomb is True:
        return FailureClassification(RETIRED, True, ("TOMBSTONE_OBSERVED",))

    row = evidence.observed_row
    # Distinguish "no re-read supplied" from "re-read observed the row is gone".
    # A caller signals an observed absence with observed_row=None AND
    # tombstone_present=False (an explicit, deliberate observation). A re-read
    # that supplied neither a row nor an explicit False tombstone is treated as
    # MISSING, not as ABSENT.
    if row is None:
        if tomb is False:
            return FailureClassification(ABSENT, True, ("ROW_ABSENT_ON_REREAD",))
        return FailureClassification(INDETERMINATE, False, ("REREAD_MISSING",))
    if type(row) is not dict:
        return FailureClassification(INDETERMINATE, False, ("INSUFFICIENT_REREAD",))

    # Tenant mismatch: observed company_id differs from what we wrote against.
    if row.get("company_id") != expected.tenant:
        return FailureClassification(TENANT_MISMATCH, True, ("TENANT_DIVERGED",))
    # Stale: revision moved relative to expected.
    if row.get("legacy_write_revision") != expected.revision:
        return FailureClassification(STALE, True, ("REVISION_DIVERGED",))
    # Incarnation diverged (lifecycle change).
    if expected.incarnation is not None and row.get("record_incarnation") != expected.incarnation:
        return FailureClassification(STALE, True, ("INCARNATION_DIVERGED",))
    # Source status diverged.
    if expected.source_status is not None and row.get("status") != expected.source_status:
        return FailureClassification(STALE, True, ("SOURCE_STATUS_DIVERGED",))
    # A re-read that shows no divergence does not prove a cause (e.g. an absent
    # identity field may have been inserted-then-removed): stay honest.
    return FailureClassification(INDETERMINATE, False, ("REREAD_SHOWS_NO_DIVERGENCE",))


# ===========================================================================
# S0b - create-only REQUEST + permanent lifetime transaction specification
# ===========================================================================
#
# build_create CONSTRUCTS (never executes) a single, indivisible transaction
# specification containing two conditional, create-only Puts: the new REQUEST
# and its permanent lifetime record. It opens no client and performs no write.
#
# Lifetime evidence is a TAGGED state (not free booleans): only a well-formed,
# token-bound LIFETIME_ABSENT permits a plan; every other/uncertain state
# refuses. Structural validation here is NOT provenance authentication - that a
# trusted reader actually produced the evidence, and that the incarnation is
# globally unique / created_at came from a trusted clock, remain adoption-time
# obligations and pending gates.

# Lifetime evidence state tags.
LIFETIME_ABSENT = "LIFETIME_ABSENT"          # looked up; no record exists -> may mint (subject to ABA gates)
LIFETIME_ACTIVE = "LIFETIME_ACTIVE"          # looked up; record exists, retired is False -> refuse
LIFETIME_RETIRED = "LIFETIME_RETIRED"        # looked up; record exists, retired is True -> refuse (never recreate)
LIFETIME_NOT_OBSERVED = "LIFETIME_NOT_OBSERVED"  # no lookup performed -> refuse
_LIFETIME_STATES = (LIFETIME_ABSENT, LIFETIME_ACTIVE, LIFETIME_RETIRED, LIFETIME_NOT_OBSERVED)

# System-owned fields the create helper computes; a caller item must not supply
# a contradictory value for these. legacy_write_revision is fully helper-owned.
_CREATE_RESERVED_ITEM_FIELDS = frozenset({
    "PK", "SK", "legacy_write_revision", "record_incarnation",
})


@dataclass(frozen=True)
class CreateIntent:
    """A caller's intent to create a brand-new REQUEST.

    request_id/client_id MUST equal the identifiers encoded in the target key.
    incarnation and created_at are caller-supplied (minted by a trusted creator
    and a trusted clock, respectively) - the pure builder VALIDATES their shape
    but cannot authenticate uniqueness or clock trust. No revision field: the
    builder initializes legacy_write_revision=1 itself.
    """
    tenant: str
    request_id: str
    client_id: str
    incarnation: str
    created_at: str
    item: dict


@dataclass(frozen=True)
class LifetimeEvidence:
    """Tagged, attested lifetime-lookup state bound to a specific token.

    state: one of _LIFETIME_STATES.
    token: the lifetime token the lookup was bound to (must equal the builder's
           deterministically derived token).
    retired: exact bool for ACTIVE/RETIRED (False/True); None otherwise.
    record: the observed lifetime snapshot (dict) for ACTIVE/RETIRED; None
            otherwise. Used only for internal-consistency validation.
    """
    state: str
    token: object = None
    retired: object = None
    record: object = None


@dataclass(frozen=True)
class CreateSpec:
    """A constructed (NOT executed) single transaction of two create-only Puts.

    transact_items is an ordered tuple of two {"Put": {...}} operands - the
    REQUEST and the permanent lifetime - each carrying a create-only
    ConditionExpression. There is no TableName and no client here; wiring to a
    low-level transact_write_items is a later (S0d) concern. advances_revision
    is False because this is initialization (revision := 1), not an advance.
    """
    transact_items: tuple
    lifetime_token: str
    minted_incarnation: str
    advances_revision: bool


def _request_lifetime_token(tenant, request_key):
    """Canonical lifetime token, byte-identical to the inactive cancellation
    contracts' Submission/Query token encoding.

    Computes sha256(json.dumps([tenant, pk, sk], sort_keys=True,
    separators=(",",":"), ensure_ascii=True)).hexdigest(), where pk/sk are the
    already-validated "REQ#<id>" / "CLIENT#<id>" key. Byte-equivalence with the
    sibling inactive contracts' token() is asserted by the test suite, so this
    helper stays the single importable source without naming those modules.
    request_key is (pk, sk).
    """
    pk, sk = request_key
    payload = json.dumps([tenant, pk, sk], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(payload.encode()).hexdigest()


def _valid_iso_utc(value):
    # Shape-only check (NOT clock authentication): a non-empty ISO-8601 string
    # that parses and is timezone-aware or a bare date/naive stamp the creator
    # supplied. We require a str; deeper clock trust is an adoption obligation.
    return type(value) is str and bool(value)


def build_create(key, intent, lifetime_evidence):
    """Construct (NOT execute) a create-only REQUEST+lifetime transaction spec.

    Returns a CreateSpec on success, or a Refusal. Never executes, never emits
    an unconditional/upsert Put, and never infers a never-used key from a
    missing REQUEST (it requires token-bound LIFETIME_ABSENT evidence - which
    is necessary but NOT sufficient for global ABA; see the acceptance doc).
    """
    # --- shape checks -------------------------------------------------------
    if type(intent) is not CreateIntent:
        return Refusal("MALFORMED_INTENT")
    if type(lifetime_evidence) is not LifetimeEvidence:
        return Refusal("MALFORMED_LIFETIME_EVIDENCE")

    # Finding A reuse: exact, well-formed REQUEST key.
    parsed = _parse_request_key(key)
    if parsed is None:
        return Refusal("MALFORMED_KEY")
    key_request_id, key_client_id = parsed

    # Intent identifiers must match the key.
    if intent.request_id != key_request_id or intent.client_id != key_client_id:
        return Refusal("KEY_INTENT_MISMATCH")
    if type(intent.tenant) is not str or not intent.tenant:
        return Refusal("MALFORMED_TENANT")

    # Caller-supplied, trusted-minted metadata: validate SHAPE only.
    if not _valid_incarnation(intent.incarnation):
        return Refusal("MALFORMED_INCARNATION")
    if not _valid_iso_utc(intent.created_at):
        return Refusal("MALFORMED_CREATED_AT")

    # --- item checks: tenant consistency + no contradictory system fields ---
    if type(intent.item) is not dict:
        return Refusal("MALFORMED_ITEM")
    item = intent.item
    # The item's own identifiers must agree with the key/intent.
    if item.get("company_id") != intent.tenant:
        return Refusal("TENANT_MISMATCH")
    if item.get("request_id") not in (None, key_request_id):
        return Refusal("ITEM_IDENTIFIER_CONFLICT", "request_id")
    if item.get("client_id") not in (None, key_client_id):
        return Refusal("ITEM_IDENTIFIER_CONFLICT", "client_id")
    if item.get("PK") not in (None, key["PK"]):
        return Refusal("ITEM_IDENTIFIER_CONFLICT", "PK")
    if item.get("SK") not in (None, key["SK"]):
        return Refusal("ITEM_IDENTIFIER_CONFLICT", "SK")
    # Caller item may not carry helper-owned version/incarnation (the builder
    # owns these); a supplied legacy_write_revision or record_incarnation is a
    # conflict even if it happens to match, to keep a single source of truth.
    for reserved in ("legacy_write_revision", "record_incarnation"):
        if reserved in item:
            return Refusal("RESERVED_FIELD_IN_ITEM", reserved)
    if "audit_log" in item and type(item["audit_log"]) is not list:
        return Refusal("MALFORMED_AUDIT")

    # --- lifetime evidence: tagged state, token binding, exact bools --------
    lifetime_token = _request_lifetime_token(intent.tenant, (key["PK"], key["SK"]))
    ev = lifetime_evidence
    if ev.state not in _LIFETIME_STATES:
        return Refusal("MALFORMED_LIFETIME_EVIDENCE", "STATE")
    if ev.state == LIFETIME_NOT_OBSERVED:
        return Refusal("LIFETIME_NOT_OBSERVED")
    # Any observed state must be bound to THIS key's derived token.
    if ev.token != lifetime_token:
        return Refusal("MALFORMED_LIFETIME_EVIDENCE", "TOKEN")
    if ev.state == LIFETIME_ACTIVE:
        # Internal consistency: ACTIVE must carry retired is False.
        if ev.retired is not False:
            return Refusal("MALFORMED_LIFETIME_EVIDENCE", "RETIRED")
        return Refusal("LIFETIME_PRESENT")
    if ev.state == LIFETIME_RETIRED:
        if ev.retired is not True:
            return Refusal("MALFORMED_LIFETIME_EVIDENCE", "RETIRED")
        return Refusal("KEY_RETIRED")
    # state == LIFETIME_ABSENT. An absent lookup must NOT carry a record or a
    # retired flag; such a mix is malformed, not an absence.
    if ev.record is not None or ev.retired is not None:
        return Refusal("MALFORMED_LIFETIME_EVIDENCE", "ABSENT_SHAPE")

    # --- construct the two create-only Puts (single transaction) ------------
    # The REQUEST item: caller fields plus helper-owned revision/incarnation.
    # Named explicitly so the helper is the single source of truth for them.
    request_item = dict(item)
    request_item["PK"] = key["PK"]
    request_item["SK"] = key["SK"]
    request_item["company_id"] = intent.tenant
    request_item["request_id"] = key_request_id
    request_item["client_id"] = key_client_id
    request_item["legacy_write_revision"] = 1
    request_item["record_incarnation"] = intent.incarnation
    request_item["created_at"] = intent.created_at

    request_put = {
        "Put": {
            "Item": request_item,
            # Create-only: both key attributes must be absent. No upsert.
            "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)",
        }
    }

    lifetime_item = {
        "PK": "LIFETIME#" + lifetime_token,
        "SK": "PERMANENT",
        "incarnation": intent.incarnation,
        "retired": False,
    }
    lifetime_put = {
        "Put": {
            "Item": lifetime_item,
            "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)",
        }
    }

    return CreateSpec(
        transact_items=(request_put, lifetime_put),
        lifetime_token=lifetime_token,
        minted_incarnation=intent.incarnation,
        advances_revision=False,
    )
