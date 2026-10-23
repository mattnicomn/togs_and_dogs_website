"""
W3-B — Provider-neutral payment domain (Option D foundation).

This module is the canonical, PROVIDER-NEUTRAL payment domain selected by Matthew
(W3 Option D: `PROVIDER_ABSTRACTION + MANUAL_EXTERNAL` first, `STRIPE_CONNECT_DIRECT`
later). It is deliberately free of any Stripe / HTTP / network coupling and performs
NO money movement. It is built ALONGSIDE the existing deployed payment path
(`stripe_client` / `stripe_webhook_handler` / `admin_handler` payment routes) and does
NOT switch runtime execution to the new domain. See
`docs/planning/petcare-hero-tenant-customer-payment-architecture.md` (§§9–16).

Hard boundaries (enforced by having no such code here):
  - No Stripe API calls, no Stripe SDK/urllib Stripe import, no Checkout Sessions,
    no PaymentIntents, no Connect, no OAuth, no webhooks, no secrets.
  - No auto-approval: nothing here sets RequestStatus=APPROVED, creates bookings/jobs,
    schedules, assigns, notifies, or charges money. Readiness is a computed result only.
  - No client self-assertion of payment: a client can never mark a payment PAID; a
    browser success redirect is never settlement proof. MANUAL_EXTERNAL confirmation is
    a future owner/admin-authorized + audited operation (not built here).
  - Money is integer minor units (cents); never float authority. PAN/CVC/secrets are
    never stored or accepted.

Canonical enums (`PaymentRequirement`, `PaymentStatus`) and money/normalization helpers
are REUSED from `common.quote_contract` — this module does not define competing enums.
"""

from datetime import datetime, timezone

from common.quote_contract import (
    PaymentRequirement,
    PaymentStatus,
    QuoteStatus,
    DEFAULT_CURRENCY,
    normalize_stored_cents,
    normalize_legacy_payment_status,
    QuoteContractError,
)

# NOTE: ``to_cents`` is intentionally NOT imported here. It treats non-int
# (Decimal/float/str) as MAJOR units and multiplies by 100, which would inflate
# canonical ``*_cents`` fields read back from DynamoDB as Decimal. All W3-B money
# goes through ``canonical_cents`` -> ``normalize_stored_cents`` (strict minor units).


class PaymentDomainError(ValueError):
    """Raised for invalid payment-domain operations (caller maps to HTTP 400/409)."""


# ---------------------------------------------------------------------------
# Canonical minor-unit (cents) handling
# ---------------------------------------------------------------------------

def canonical_cents(value):
    """Normalize a CANONICAL ``*_cents`` field to a non-negative integer of minor units.

    All W3-B money fields — ``amount_required_cents``, ``amount_paid_cents``,
    ``deposit_amount_cents``, ``amount_delta_cents`` — are canonical minor units and
    MUST preserve magnitude across the DynamoDB ``Decimal`` round-trip. This delegates
    to :func:`quote_contract.normalize_stored_cents`, which is the strict minor-unit
    helper:

      - ``int`` 5000 -> 5000; ``Decimal('5000')`` -> 5000; ``'5000'`` -> 5000;
      - ``Decimal('50.5')`` / non-integral -> reject;
      - negative -> reject; ``bool`` -> reject; ``None`` -> 0.

    It deliberately does NOT use :func:`quote_contract.to_cents`, which treats a
    non-``int`` (Decimal/float/str) as MAJOR units and multiplies by 100 — that would
    silently inflate a canonical ``Decimal('5000')`` read from DynamoDB to 500000.
    Normalized to a ``PaymentDomainError`` so callers get a consistent 400/409 mapping.
    """
    try:
        return normalize_stored_cents(value)
    except QuoteContractError as exc:
        raise PaymentDomainError(f"invalid canonical cents value: {value!r} ({exc})") from exc


# ---------------------------------------------------------------------------
# Providers (provider-neutral; Option D)
# ---------------------------------------------------------------------------

class PaymentProvider:
    """Canonical provider identifiers for the selected architecture.

    Only MANUAL_EXTERNAL is the selected/active MVP boundary. STRIPE_CONNECT_DIRECT is
    the selected long-term direction (adapter built in a later, separately authorized
    phase — W3-C). STRIPE_CONNECT_MARKETPLACE exists only as a forward-compatibility
    label; it was NOT selected and MUST NOT be executable.
    """
    MANUAL_EXTERNAL = "MANUAL_EXTERNAL"
    STRIPE_CONNECT_DIRECT = "STRIPE_CONNECT_DIRECT"   # long-term direction (not built here)
    STRIPE_CONNECT_MARKETPLACE = "STRIPE_CONNECT_MARKETPLACE"  # NOT selected; label only

    #: Providers a W3-B record may legitimately carry.
    ALL = frozenset({MANUAL_EXTERNAL, STRIPE_CONNECT_DIRECT, STRIPE_CONNECT_MARKETPLACE})
    #: Providers whose domain boundary W3-B actually supports (MVP).
    W3B_SUPPORTED = frozenset({MANUAL_EXTERNAL})


def validate_known_provider(value):
    """Validate that ``value`` is a KNOWN provider identifier (any of ``ALL``).

    Used for schema/introspection/forward-compatibility contexts where a provider may
    be *named* (e.g. a marketplace label on a non-executable record) without being
    executable in W3-B. Being known does NOT imply being allowed for active operations.
    """
    if value not in PaymentProvider.ALL:
        raise PaymentDomainError(f"invalid payment_provider: {value!r}")
    return value


def validate_active_provider(value):
    """Validate that ``value`` is a provider ALLOWED for active W3-B operations.

    W3-B only supports ``MANUAL_EXTERNAL``. ``STRIPE_CONNECT_DIRECT`` (selected
    long-term direction) and ``STRIPE_CONNECT_MARKETPLACE`` (forward label only) are
    known identifiers but are NOT executable in W3-B — any builder/persistence path
    that represents an active payment event or summary must reject them. This is the
    provider execution boundary: no Stripe Connect code runs in W3-B.
    """
    # First ensure it is at least a known identifier (clearer error for junk).
    validate_known_provider(value)
    if value not in PaymentProvider.W3B_SUPPORTED:
        raise PaymentDomainError(
            f"provider {value!r} is known but NOT executable in W3-B "
            f"(W3B_SUPPORTED={sorted(PaymentProvider.W3B_SUPPORTED)}); "
            f"Stripe Connect is a future, separately authorized phase"
        )
    return value


#: Back-compat alias. ``validate_provider`` historically meant "known provider";
#: active-operation paths must use ``validate_active_provider``.
validate_provider = validate_known_provider


# ---------------------------------------------------------------------------
# PaymentStatus — canonical set + normalization + state machine
# ---------------------------------------------------------------------------

#: W3B_PAYMENT_STATUS_SET — exactly the existing canonical set from quote_contract.
#: No speculative states (PENDING/FAILED/PARTIALLY_REFUNDED) are added: PAYMENT_LINK_SENT
#: already represents "payment requested / waiting", and provider failures are recorded
#: as PAYMENT_EVENT metadata rather than as a new authoritative status.
PAYMENT_STATUS_SET = frozenset({
    PaymentStatus.NOT_REQUIRED,
    PaymentStatus.UNPAID,
    PaymentStatus.PAYMENT_LINK_SENT,
    PaymentStatus.PARTIALLY_PAID,
    PaymentStatus.PAID,
    PaymentStatus.REFUNDED,
})

#: Sentinel for an unrecognized incoming status — never silently treated as paid or
#: as NOT_REQUIRED. Callers must handle it explicitly (fail safe).
PAYMENT_STATUS_UNKNOWN = "UNKNOWN"


def normalize_payment_status(raw):
    """Single authoritative payment-status normalizer (provider-neutral).

    - Canonical uppercase values pass through.
    - Documented legacy/live compatibility values (e.g. lowercase ``paid`` /
      ``payment_link_sent`` written by the current Stripe path, and legacy PET
      vocabulary) map to canonical via ``quote_contract.normalize_legacy_payment_status``.
    - ``None``/empty -> ``NOT_REQUIRED`` (matches the quote-contract convention).
    - An unknown non-empty value returns ``PAYMENT_STATUS_UNKNOWN`` — it is NEVER
      coerced to a successful/paid state and is distinguishable from NOT_REQUIRED.

    No Stripe/provider-specific assumptions.
    """
    if raw in (None, ""):
        return PaymentStatus.NOT_REQUIRED
    if isinstance(raw, str) and raw in PAYMENT_STATUS_SET:
        return raw
    key = str(raw).strip().lower()
    # Known canonical (case-insensitive) and known legacy values.
    canonical_lower = {s.lower(): s for s in PAYMENT_STATUS_SET}
    if key in canonical_lower:
        return canonical_lower[key]
    known_legacy = {
        "not quoted", "quote sent", "payment pending", "accepted",
        "deposit paid", "paid in full", "waived",
    }
    if key in known_legacy:
        return normalize_legacy_payment_status(raw)
    # Unknown → fail safe (never paid, never NOT_REQUIRED).
    return PAYMENT_STATUS_UNKNOWN


#: Allowed canonical payment-status transitions (provider-neutral, deterministic).
#: NOT_REQUIRED is terminal for collection; a provider event can never flip it to PAID.
#: No backward/illegal transitions (PAID->PAYMENT_LINK_SENT, REFUNDED->PAID,
#: NOT_REQUIRED->PAID) are permitted. Re-open/reset is explicitly out of W3-B scope.
_ALLOWED_TRANSITIONS = {
    PaymentStatus.NOT_REQUIRED: frozenset(),                       # terminal
    PaymentStatus.UNPAID: frozenset({
        PaymentStatus.PAYMENT_LINK_SENT,
        PaymentStatus.PARTIALLY_PAID,
        PaymentStatus.PAID,
    }),
    PaymentStatus.PAYMENT_LINK_SENT: frozenset({
        PaymentStatus.UNPAID,            # link/session voided/expired/cancelled
        PaymentStatus.PARTIALLY_PAID,
        PaymentStatus.PAID,
    }),
    PaymentStatus.PARTIALLY_PAID: frozenset({
        PaymentStatus.PAID,
        PaymentStatus.REFUNDED,
    }),
    PaymentStatus.PAID: frozenset({
        PaymentStatus.REFUNDED,
    }),
    PaymentStatus.REFUNDED: frozenset(),                           # terminal
}


def can_transition(from_status, to_status):
    """True iff the canonical payment-status transition is allowed (pure)."""
    f = normalize_payment_status(from_status)
    t = normalize_payment_status(to_status)
    if f == PAYMENT_STATUS_UNKNOWN or t == PAYMENT_STATUS_UNKNOWN:
        return False
    if f == t:
        return True  # idempotent no-op transition is always allowed
    return t in _ALLOWED_TRANSITIONS.get(f, frozenset())


def validate_transition(from_status, to_status):
    """Validate a canonical payment-status transition; raise on an illegal one."""
    f = normalize_payment_status(from_status)
    t = normalize_payment_status(to_status)
    if f == PAYMENT_STATUS_UNKNOWN:
        raise PaymentDomainError(f"unknown current payment_status: {from_status!r}")
    if t == PAYMENT_STATUS_UNKNOWN or t not in PAYMENT_STATUS_SET:
        raise PaymentDomainError(f"invalid target payment_status: {to_status!r}")
    if not can_transition(f, t):
        raise PaymentDomainError(f"illegal payment transition {f} -> {t}")
    return t


# ---------------------------------------------------------------------------
# Amount invariants (integer minor units; no float authority)
# ---------------------------------------------------------------------------

def validate_payment_amounts(
    payment_requirement,
    amount_required_cents,
    amount_paid_cents=0,
    currency=DEFAULT_CURRENCY,
    deposit_amount_cents=0,
):
    """Validate provider-neutral payment amounts in integer minor units.

    Returns a normalized dict of integer-cent amounts + currency. Rules:
      - all amounts are non-negative integer cents via :func:`canonical_cents`
        (strict minor units — magnitude preserved across DynamoDB ``Decimal``, no ×100);
      - currency is required whenever money is required (requirement != NONE and a
        positive required amount);
      - overpayment is NOT modeled in W3-B: ``amount_paid_cents`` must not exceed the
        relevant required amount (deposit for DEPOSIT, total for FULL);
      - NONE requires no payment (required/paid normalized but not gating).

    Raises ``PaymentDomainError`` on any violation. Pure; no I/O.
    """
    if payment_requirement is not None and payment_requirement not in PaymentRequirement.ALL:
        raise PaymentDomainError(f"invalid payment_requirement: {payment_requirement!r}")

    req = canonical_cents(amount_required_cents)
    paid = canonical_cents(amount_paid_cents)
    dep = canonical_cents(deposit_amount_cents)

    requires_money = (
        payment_requirement in (PaymentRequirement.DEPOSIT, PaymentRequirement.FULL)
        and req > 0
    )
    if requires_money and not currency:
        raise PaymentDomainError("currency is required when payment is required")

    if payment_requirement == PaymentRequirement.FULL:
        if paid > req:
            raise PaymentDomainError("amount_paid_cents exceeds required total (overpayment not modeled in W3-B)")
    elif payment_requirement == PaymentRequirement.DEPOSIT:
        # For a deposit path the ceiling is the full total; a deposit payment must not
        # exceed the total, and the deposit threshold itself must not exceed the total.
        if dep > req and req > 0:
            raise PaymentDomainError("deposit_amount_cents exceeds required total")
        if paid > req and req > 0:
            raise PaymentDomainError("amount_paid_cents exceeds required total (overpayment not modeled in W3-B)")

    return {
        "payment_requirement": payment_requirement,
        "amount_required_cents": req,
        "amount_paid_cents": paid,
        "deposit_amount_cents": dep,
        "currency": currency or DEFAULT_CURRENCY,
    }


# ---------------------------------------------------------------------------
# Booking-readiness predicate (provider-neutral; amount-aware)
# ---------------------------------------------------------------------------

def is_booking_payment_ready(
    quote_status,
    payment_requirement,
    payment_status,
    quote_amount_cents=0,
    deposit_amount_cents=0,
    amount_paid_cents=0,
    currency=DEFAULT_CURRENCY,
):
    """Return ``(ready: bool, reason: str)`` for booking payment-readiness.

    Provider-neutral and PURE. Preserves ``quote acceptance != payment complete !=
    APPROVED`` — this NEVER transitions RequestStatus, creates bookings, or approves
    anything. It is an amount-aware strengthening of
    ``quote_contract.evaluate_booking_approval_predicate``: in addition to the
    status-based gate, DEPOSIT/FULL also require the paid AMOUNT to meet the threshold.

    Semantics:
      - NONE: ready iff quote_status == ACCEPTED (no payment required).
      - DEPOSIT: ready iff quote_status == ACCEPTED AND amount_paid_cents >=
        deposit_amount_cents AND payment_status in {PARTIALLY_PAID, PAID}.
      - FULL: ready iff quote_status == ACCEPTED AND amount_paid_cents >=
        quote_amount_cents AND payment_status == PAID.
      - DRAFT/SENT/DECLINED (or any non-ACCEPTED) are never ready.
    """
    if payment_requirement is not None and payment_requirement not in PaymentRequirement.ALL:
        raise PaymentDomainError(f"invalid payment_requirement: {payment_requirement!r}")

    status = normalize_payment_status(payment_status)
    total = normalize_stored_cents(quote_amount_cents)
    deposit = normalize_stored_cents(deposit_amount_cents)
    paid = normalize_stored_cents(amount_paid_cents)

    if quote_status != QuoteStatus.ACCEPTED:
        return False, f"quote not accepted (quote_status={quote_status})"

    if payment_requirement in (None, PaymentRequirement.NONE):
        return True, "ready: no payment required (quote accepted)"

    if payment_requirement == PaymentRequirement.DEPOSIT:
        if status not in (PaymentStatus.PARTIALLY_PAID, PaymentStatus.PAID):
            return False, f"deposit not settled (payment_status={status})"
        if paid < deposit:
            return False, f"deposit amount not met ({paid} < {deposit})"
        return True, "ready: deposit satisfied"

    if payment_requirement == PaymentRequirement.FULL:
        if status != PaymentStatus.PAID:
            return False, f"full payment not settled (payment_status={status})"
        if paid < total:
            return False, f"full amount not met ({paid} < {total})"
        return True, "ready: paid in full"

    return False, f"unknown payment_requirement={payment_requirement}"


# ---------------------------------------------------------------------------
# REQUEST payment summary (provider-neutral; fast-read)
# ---------------------------------------------------------------------------

#: Provider-neutral REQUEST-level payment summary fields (fast read for card/detail).
#: These reuse the existing deployed field names where compatible and add the
#: provider-neutral amount/provider fields. NOT client-exposed by this module (the
#: client projection in quote_contract remains the single client-facing allowlist).
PAYMENT_SUMMARY_FIELDS = (
    "payment_requirement",
    "payment_status",
    "amount_required_cents",
    "amount_paid_cents",
    "currency",
    "payment_provider",
    "payment_completed_at",
)


def build_payment_summary(
    payment_requirement=PaymentRequirement.NONE,
    payment_status=PaymentStatus.NOT_REQUIRED,
    amount_required_cents=0,
    amount_paid_cents=0,
    currency=DEFAULT_CURRENCY,
    payment_provider=PaymentProvider.MANUAL_EXTERNAL,
    payment_completed_at=None,
):
    """Build a validated provider-neutral REQUEST payment summary (pure).

    Normalizes amounts, validates the provider and status, and returns a dict of
    exactly ``PAYMENT_SUMMARY_FIELDS``. An active summary must carry an EXECUTABLE
    provider (W3-B: ``MANUAL_EXTERNAL`` only) — a known-but-inactive provider (Stripe
    Connect Direct/Marketplace) is rejected here. Does not persist.
    """
    validate_active_provider(payment_provider)
    status = normalize_payment_status(payment_status)
    if status == PAYMENT_STATUS_UNKNOWN:
        raise PaymentDomainError(f"unknown payment_status: {payment_status!r}")
    amounts = validate_payment_amounts(
        payment_requirement, amount_required_cents, amount_paid_cents, currency
    )
    return {
        "payment_requirement": payment_requirement,
        "payment_status": status,
        "amount_required_cents": amounts["amount_required_cents"],
        "amount_paid_cents": amounts["amount_paid_cents"],
        "currency": amounts["currency"],
        "payment_provider": payment_provider,
        "payment_completed_at": payment_completed_at,
    }


# ---------------------------------------------------------------------------
# PAYMENT_EVENT — append-only provider-neutral event records
# ---------------------------------------------------------------------------

#: Event types (provider-neutral). Deliberately small; extend only as adapters need.
class PaymentEventType:
    PAYMENT_REQUESTED = "PAYMENT_REQUESTED"        # e.g. link/session requested
    PAYMENT_SETTLED = "PAYMENT_SETTLED"            # funds confirmed (full or deposit)
    PAYMENT_PARTIALLY_SETTLED = "PAYMENT_PARTIALLY_SETTLED"
    PAYMENT_REFUNDED = "PAYMENT_REFUNDED"
    PAYMENT_FAILED = "PAYMENT_FAILED"              # recorded as event metadata, not a status
    PAYMENT_VOIDED = "PAYMENT_VOIDED"              # link/session cancelled/expired

    ALL = frozenset({
        PAYMENT_REQUESTED, PAYMENT_SETTLED, PAYMENT_PARTIALLY_SETTLED,
        PAYMENT_REFUNDED, PAYMENT_FAILED, PAYMENT_VOIDED,
    })


#: Exact forbidden metadata keys (retained for explicitness/back-compat). The
#: substring patterns below are the primary, broader defense.
PAYMENT_EVENT_FORBIDDEN_METADATA = frozenset({
    "pan", "card_number", "cvc", "cvv", "payment_method", "raw", "secret",
    "stripe_secret_key", "api_key", "authorization", "jwt", "token", "id_token",
    "access_token", "password",
})

#: Substring patterns: any metadata key CONTAINING one of these (case-insensitive) is
#: rejected, at any nesting depth. This catches variants like ``access_token``,
#: ``card_pan``, ``client_secret``, ``auth_token``, ``cvv2`` without enumerating each.
PAYMENT_EVENT_SENSITIVE_KEY_PATTERNS = (
    "secret", "password", "passwd", "token", "authorization", "api_key", "apikey",
    "card", "pan", "cvc", "cvv", "credential", "private_key", "privatekey", "bearer",
    "session_key", "access_key",
)

#: Audit metadata safety caps (reject pathological nested payloads / raw provider
#: objects). These are conservative defaults for append-only audit notes, not a
#: general document store.
PAYMENT_EVENT_METADATA_MAX_DEPTH = 3
PAYMENT_EVENT_METADATA_MAX_KEYS = 25
PAYMENT_EVENT_METADATA_MAX_STRLEN = 1024

#: Audit-safe scalar leaf types (no arbitrary opaque objects / provider payloads).
_AUDIT_SCALAR_TYPES = (str, int, float, bool, type(None))


def _reject_if_sensitive_key(key):
    k = str(key).strip().lower()
    if k in PAYMENT_EVENT_FORBIDDEN_METADATA:
        raise PaymentDomainError(f"forbidden metadata key: {key!r}")
    for pat in PAYMENT_EVENT_SENSITIVE_KEY_PATTERNS:
        if pat in k:
            raise PaymentDomainError(f"forbidden (sensitive) metadata key: {key!r}")


def _sanitize_audit_value(value, depth):
    """Recursively validate an audit metadata value against the safety contract.

    Allowed: audit-safe scalars (str/int/float/bool/None), lists of allowed values, and
    nested dicts (string keys, no sensitive patterns) up to the depth cap. Rejected:
    sensitive keys at any depth, raw/opaque provider payload objects (anything that is
    not a scalar/list/dict), over-long strings, and excessive breadth/depth.
    """
    if depth > PAYMENT_EVENT_METADATA_MAX_DEPTH:
        raise PaymentDomainError("metadata nesting too deep")
    # bool is an int subclass — fine as an audit scalar, handled by the tuple above.
    if isinstance(value, str):
        if len(value) > PAYMENT_EVENT_METADATA_MAX_STRLEN:
            raise PaymentDomainError("metadata string value too long")
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        if len(value) > PAYMENT_EVENT_METADATA_MAX_KEYS:
            raise PaymentDomainError("metadata list too large")
        return [_sanitize_audit_value(v, depth + 1) for v in value]
    if isinstance(value, dict):
        if len(value) > PAYMENT_EVENT_METADATA_MAX_KEYS:
            raise PaymentDomainError("metadata object too large")
        out = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise PaymentDomainError(f"metadata keys must be strings: {k!r}")
            _reject_if_sensitive_key(k)
            out[k] = _sanitize_audit_value(v, depth + 1)
        return out
    # Anything else (raw provider payload object, bytes, custom class, etc.) is rejected.
    raise PaymentDomainError(
        f"unsupported metadata value type {type(value).__name__} "
        f"(raw provider payloads must not be stored)"
    )


def sanitize_payment_event_metadata(metadata):
    """Return allowlist-sanitized audit metadata, or raise ``PaymentDomainError``.

    ``None``/empty -> ``None``. A non-dict top level is rejected. Sensitive keys
    (secret/password/token/authorization/api_key/card/pan/cvc/cvv/... at ANY depth),
    raw/opaque objects, and over-sized structures are rejected rather than silently
    dropped — so a leak attempt fails loudly instead of being partially stored.
    """
    if not metadata:
        return None
    if not isinstance(metadata, dict):
        raise PaymentDomainError("metadata must be a dict")
    return _sanitize_audit_value(metadata, depth=1) or None


def payment_event_sk(idempotency_key):
    """Deterministic, append-only SK for a PAYMENT_EVENT under its REQUEST item.

    Events live in the SAME application table, in the REQUEST's item collection:
      PK = ``REQ#{request_id}``   (tenant/request-scoped; same as the REQUEST record)
      SK = ``PAYEVENT#{idempotency_key}``
    The idempotency key makes the SK deterministic; combined with a conditional
    ``attribute_not_exists(PK) AND attribute_not_exists(SK)`` put (see
    :func:`persist_payment_event`) the write is duplicate-safe, and events are queryable
    with ``begins_with(SK, 'PAYEVENT#')``. No new table or GSI is required.
    """
    if not idempotency_key or not isinstance(idempotency_key, str):
        raise PaymentDomainError("idempotency_key must be a non-empty string")
    return f"PAYEVENT#{idempotency_key.strip()}"


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_payment_event(
    request_id,
    company_id,
    event_type,
    idempotency_key,
    previous_status,
    resulting_status,
    client_id=None,
    provider=PaymentProvider.MANUAL_EXTERNAL,
    amount_delta_cents=0,
    currency=DEFAULT_CURRENCY,
    provider_txn_ref=None,
    actor="system",
    metadata=None,
    now_iso=None,
):
    """Build an immutable, provider-neutral PAYMENT_EVENT item (pure; no I/O).

    Validates identity/type/transition/amount, enforces the provider EXECUTION boundary
    (active provider must be ``MANUAL_EXTERNAL`` in W3-B), and recursively allowlist-
    sanitizes audit metadata. The resulting status must be a legal transition from the
    previous status (an idempotent same-status event is allowed, e.g. a replayed
    settlement). Amounts are canonical minor units (no ×100 inflation).

    Never stores PAN/CVC/payment-method/secrets/auth material or raw provider payloads.
    """
    if not request_id or not company_id:
        raise PaymentDomainError("request_id and company_id (trusted) are required")
    if event_type not in PaymentEventType.ALL:
        raise PaymentDomainError(f"invalid payment event_type: {event_type!r}")
    # Active payment event -> executable provider only (MANUAL_EXTERNAL in W3-B).
    validate_active_provider(provider)

    prev = normalize_payment_status(previous_status)
    result = normalize_payment_status(resulting_status)
    if result == PAYMENT_STATUS_UNKNOWN or result not in PAYMENT_STATUS_SET:
        raise PaymentDomainError(f"invalid resulting payment_status: {resulting_status!r}")
    # Transition legality (same-status replay allowed).
    validate_transition(prev, result)

    delta = canonical_cents(amount_delta_cents)

    safe_metadata = sanitize_payment_event_metadata(metadata)

    sk = payment_event_sk(idempotency_key)
    return {
        "PK": f"REQ#{request_id}",
        "SK": sk,
        "entity_type": "PAYMENT_EVENT",
        "company_id": company_id,
        "request_id": request_id,
        "client_id": client_id,
        "payment_provider": provider,
        "event_type": event_type,
        "idempotency_key": idempotency_key.strip(),
        "previous_payment_status": prev,
        "resulting_payment_status": result,
        "amount_delta_cents": delta,
        "currency": currency or DEFAULT_CURRENCY,
        "provider_txn_ref": provider_txn_ref,  # opaque; never a secret
        "actor": actor,
        "created_at": now_iso or _now_iso(),
        "metadata": safe_metadata,
    }


# ---------------------------------------------------------------------------
# PAYMENT_EVENT persistence (append-only, conditional, tenant-owned)
# ---------------------------------------------------------------------------
#
# This is the ONLY part of the module that touches the repository, and it does so
# through the existing application table helpers (`common.db`) — NO new table, NO GSI,
# NO Terraform, NO Stripe/network coupling. The repository is imported LAZILY inside the
# function so the pure domain above stays import-clean (and so a static import scan of
# the domain sees no boto3/db coupling at module top level).
#
# Canonical key conventions (observed from the existing handlers):
#   REQUEST item: PK=REQ#{request_id}, SK=CLIENT#{client_id}
#   PAYMENT_EVENT: PK=REQ#{request_id}, SK=PAYEVENT#{idempotency_key}  (same collection)
# Tenant ownership on the REQUEST is `company_id` (absent -> DEFAULT_COMPANY_ID, matching
# stripe_webhook_handler's convention).

#: Persistence result contract.
PERSIST_CREATED = "CREATED"
PERSIST_DUPLICATE_SAME_EVENT = "DUPLICATE_SAME_EVENT"
PERSIST_CONFLICTING_IDEMPOTENCY_KEY = "CONFLICTING_IDEMPOTENCY_KEY"

#: Semantic fields that define a PAYMENT_EVENT's identity for duplicate-vs-conflict
#: classification. A replay with the same idempotency_key must carry the same values.
_EVENT_SEMANTIC_FIELDS = (
    "event_type",
    "payment_provider",
    "previous_payment_status",
    "resulting_payment_status",
    "amount_delta_cents",
    "currency",
    "request_id",
    "company_id",
    "client_id",
    "provider_txn_ref",
)


def _events_semantically_equal(stored, candidate):
    """True iff two PAYMENT_EVENT items agree on every semantic field.

    Amounts are compared as canonical integer cents so a stored ``Decimal('5000')`` and
    a candidate ``5000`` match. Other fields compare by value.
    """
    for field in _EVENT_SEMANTIC_FIELDS:
        sv = stored.get(field)
        cv = candidate.get(field)
        if field == "amount_delta_cents":
            try:
                sv = normalize_stored_cents(sv)
                cv = normalize_stored_cents(cv)
            except QuoteContractError:
                return False
        if sv != cv:
            return False
    return True


def load_owned_request(request_id, client_id, company_id):
    """Load the canonical REQUEST and fail CLOSED unless it is owned by the tenant.

    Enforcement (not merely a non-empty ``company_id`` argument):
      1. load REQUEST by its canonical key (PK=REQ#{request_id}, SK=CLIENT#{client_id});
      2. it must exist;
      3. its trusted ownership (``company_id``, defaulting to DEFAULT_COMPANY_ID when
         absent — the live convention) must equal the supplied trusted ``company_id``;
      4. its ``client_id`` (when present on the record) must match the supplied one.

    Raises ``PaymentDomainError`` on any mismatch (caller maps to 403/404). The supplied
    ``company_id`` is the trusted caller context; a spoofed ``event.company_id`` cannot
    widen access because ownership is decided by the stored REQUEST, not the event body.
    """
    if not request_id or not client_id or not company_id:
        raise PaymentDomainError("request_id, client_id and trusted company_id are required")

    from common.db import get_item  # lazy: repo access only in the persistence layer
    from common.auth import DEFAULT_COMPANY_ID

    request_item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
    if not request_item:
        raise PaymentDomainError(f"request not found: REQ#{request_id}/CLIENT#{client_id}")

    request_company = request_item.get("company_id") or DEFAULT_COMPANY_ID
    if request_company != company_id:
        # Fail closed; do not disclose the owning tenant.
        raise PaymentDomainError("cross-tenant request ownership mismatch")

    record_client = request_item.get("client_id")
    if record_client is not None and record_client != client_id:
        raise PaymentDomainError("client ownership mismatch for request")

    return request_item


def persist_payment_event(
    request_id,
    company_id,
    client_id,
    event_type,
    idempotency_key,
    previous_status,
    resulting_status,
    provider=PaymentProvider.MANUAL_EXTERNAL,
    amount_delta_cents=0,
    currency=DEFAULT_CURRENCY,
    provider_txn_ref=None,
    actor="system",
    metadata=None,
    now_iso=None,
):
    """Append-only, tenant-verified, conditional persist of one PAYMENT_EVENT.

    Returns ``(result, event_item)`` where ``result`` is one of:
      - ``PERSIST_CREATED`` — the event was written (conditional put succeeded);
      - ``PERSIST_DUPLICATE_SAME_EVENT`` — an event already exists at this key with the
        SAME semantic payload -> idempotent no-op (treated as success);
      - ``PERSIST_CONFLICTING_IDEMPOTENCY_KEY`` — an event exists at this key but with a
        DIFFERENT semantic payload -> NOT success; caller must treat as a 409 conflict.

    Guarantees:
      - tenant/request ownership is enforced via :func:`load_owned_request` BEFORE any
        write (fail closed; no write on mismatch / missing request);
      - the write is conditional (``attribute_not_exists(PK) AND attribute_not_exists(SK)``)
        so an existing event is NEVER overwritten — deterministic SK alone is not relied
        on for idempotency;
      - active provider must be executable (``MANUAL_EXTERNAL`` in W3-B);
      - no new table / GSI / infrastructure.
    """
    # 1. Ownership (fail closed before building or writing anything).
    load_owned_request(request_id, client_id, company_id)

    # 2. Build the validated, sanitized, canonical-cents event item.
    event_item = build_payment_event(
        request_id=request_id,
        company_id=company_id,
        event_type=event_type,
        idempotency_key=idempotency_key,
        previous_status=previous_status,
        resulting_status=resulting_status,
        client_id=client_id,
        provider=provider,
        amount_delta_cents=amount_delta_cents,
        currency=currency,
        provider_txn_ref=provider_txn_ref,
        actor=actor,
        metadata=metadata,
        now_iso=now_iso,
    )

    # 3. Conditional append-only write.
    from common.db import table, get_item  # lazy repo access
    from botocore.exceptions import ClientError

    try:
        table.put_item(
            Item=event_item,
            ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
        )
        return PERSIST_CREATED, event_item
    except ClientError as exc:
        code = (exc.response or {}).get("Error", {}).get("Code")
        if code != "ConditionalCheckFailedException":
            # Do not reinterpret arbitrary DynamoDB errors as business semantics.
            raise PaymentDomainError(f"payment event persistence failed: {code}") from exc

    # 4. Key already exists -> classify duplicate vs conflict by semantic payload.
    existing = get_item(event_item["PK"], event_item["SK"])
    if existing and _events_semantically_equal(existing, event_item):
        return PERSIST_DUPLICATE_SAME_EVENT, existing
    # Same idempotency key, different meaning -> explicit conflict, NOT success.
    return PERSIST_CONFLICTING_IDEMPOTENCY_KEY, existing
