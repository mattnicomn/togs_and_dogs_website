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
    to_cents,
    normalize_stored_cents,
    normalize_legacy_payment_status,
    QuoteContractError,
)


class PaymentDomainError(ValueError):
    """Raised for invalid payment-domain operations (caller maps to HTTP 400/409)."""


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


def validate_provider(value):
    if value not in PaymentProvider.ALL:
        raise PaymentDomainError(f"invalid payment_provider: {value!r}")
    return value


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
      - all amounts are non-negative integer cents (via quote_contract.to_cents);
      - currency is required whenever money is required (requirement != NONE and a
        positive required amount);
      - overpayment is NOT modeled in W3-B: ``amount_paid_cents`` must not exceed the
        relevant required amount (deposit for DEPOSIT, total for FULL);
      - NONE requires no payment (required/paid normalized but not gating).

    Raises ``PaymentDomainError`` on any violation. Pure; no I/O.
    """
    if payment_requirement is not None and payment_requirement not in PaymentRequirement.ALL:
        raise PaymentDomainError(f"invalid payment_requirement: {payment_requirement!r}")

    req = to_cents(amount_required_cents)
    paid = to_cents(amount_paid_cents)
    dep = to_cents(deposit_amount_cents)

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
    exactly ``PAYMENT_SUMMARY_FIELDS``. Does not persist.
    """
    validate_provider(payment_provider)
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


#: Fields that must NEVER appear in a PAYMENT_EVENT (defense-in-depth — a caller
#: passing these in metadata is rejected).
PAYMENT_EVENT_FORBIDDEN_METADATA = frozenset({
    "pan", "card_number", "cvc", "cvv", "payment_method", "raw", "secret",
    "stripe_secret_key", "api_key", "authorization", "jwt", "token", "id_token",
    "access_token", "password",
})


def payment_event_sk(idempotency_key):
    """Deterministic, append-only SK for a PAYMENT_EVENT under its REQUEST item.

    Events live in the SAME application table, in the REQUEST's item collection:
      PK = ``REQ#{request_id}``   (tenant/request-scoped; same as the REQUEST record)
      SK = ``PAYEVENT#{idempotency_key}``
    The idempotency key makes the SK deterministic, so a conditional
    ``attribute_not_exists(PK)`` put is naturally duplicate-safe, and events are
    queryable with ``begins_with(SK, 'PAYEVENT#')``. No new table or GSI is required.
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

    Validates identity/type/transition/amount and strips any forbidden metadata keys.
    The resulting status must be a legal transition from the previous status (an
    idempotent same-status event is allowed, e.g. a replayed settlement).

    Never stores PAN/CVC/payment-method/secrets/auth material.
    """
    if not request_id or not company_id:
        raise PaymentDomainError("request_id and company_id (trusted) are required")
    if event_type not in PaymentEventType.ALL:
        raise PaymentDomainError(f"invalid payment event_type: {event_type!r}")
    validate_provider(provider)

    prev = normalize_payment_status(previous_status)
    result = normalize_payment_status(resulting_status)
    if result == PAYMENT_STATUS_UNKNOWN or result not in PAYMENT_STATUS_SET:
        raise PaymentDomainError(f"invalid resulting payment_status: {resulting_status!r}")
    # Transition legality (same-status replay allowed).
    validate_transition(prev, result)

    delta = to_cents(amount_delta_cents)

    safe_metadata = {}
    if metadata:
        if not isinstance(metadata, dict):
            raise PaymentDomainError("metadata must be a dict")
        for k, v in metadata.items():
            if str(k).strip().lower() in PAYMENT_EVENT_FORBIDDEN_METADATA:
                raise PaymentDomainError(f"forbidden metadata key: {k!r}")
            safe_metadata[k] = v

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
        "metadata": safe_metadata or None,
    }
