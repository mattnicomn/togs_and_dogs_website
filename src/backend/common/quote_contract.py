"""
OPS-3A.1 — Canonical commercial Quote Contract (backend foundation).

This module is the pure, framework-free foundation for the approved OPS-3A quote
contract (see docs/planning/petcare-hero-quote-contract.md, approved by Matthew on
2026-10-03). It is intentionally free of AWS / HTTP / DynamoDB coupling so it can be
unit-tested in isolation and consumed later by:

  - owner/admin quote draft/update/send handling (OPS-3A.1 remainder — requires a new
    API Gateway route, which is deploy-gated and NOT wired in this slice);
  - the client-safe quote read projection (OPS-3A.1 remainder — same routing gate);
  - client Accept/Decline (OPS-3A.2);
  - web/mobile quote UI (OPS-3A.3).

Authoritative decisions implemented here (all approved 2026-10-03):
  - Canonical quote ownership = REQUEST / BOOKING record.
  - Canonical commercial lifecycle = ``quote_status`` (QuoteStatus below).
  - ``SUPERSEDED`` is history-only and must never be the current ``quote_status``.
  - Canonical money = integer minor units (cents) + currency; primary field
    ``quote_amount_cents``.
  - ``payment_requirement`` = NONE | DEPOSIT | FULL.
  - No quote expiration in MVP; one total booking price in MVP; line items deferred.
  - Reuse existing ``APPROVED``; no ``BOOKING_CONFIRMED``.
  - Quote acceptance does NOT auto-approve the booking.
  - ``quote_status`` wins over legacy RequestStatus for commercial decisions.
  - Legacy PET ``quote_amount`` (Decimal major units) is converted to cents at read
    time (dual-read); no destructive migration is performed by this module.

Out of scope for this module (and this slice): Stripe calls, payment collection,
new API Gateway routes, DynamoDB migrations, Visit/JOB changes, tenant-resolution
changes, and client Accept/Decline mutation (OPS-3A.2).
"""

from decimal import Decimal, ROUND_HALF_UP


# ---------------------------------------------------------------------------
# Enumerations (string constants; DynamoDB/JSON friendly)
# ---------------------------------------------------------------------------

class QuoteStatus:
    """Authoritative commercial quote lifecycle (current-state values).

    ``SUPERSEDED`` is history-only: it may appear ONLY on entries inside
    ``quote_history`` and must never be the REQUEST's current ``quote_status``.
    """
    NOT_REQUIRED = "NOT_REQUIRED"
    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    SUPERSEDED = "SUPERSEDED"  # history-only; never current

    #: Values valid as the REQUEST's current ``quote_status``.
    CURRENT_VALID = frozenset({NOT_REQUIRED, DRAFT, SENT, ACCEPTED, DECLINED})
    #: All values that may appear anywhere (current or in history).
    ALL = frozenset({NOT_REQUIRED, DRAFT, SENT, ACCEPTED, DECLINED, SUPERSEDED})


class PaymentRequirement:
    """What settlement (if any) gates booking confirmation."""
    NONE = "NONE"
    DEPOSIT = "DEPOSIT"
    FULL = "FULL"

    ALL = frozenset({NONE, DEPOSIT, FULL})


class PaymentStatus:
    """Normalized single payment vocabulary (approved R2/R4)."""
    NOT_REQUIRED = "NOT_REQUIRED"
    UNPAID = "UNPAID"
    PAYMENT_LINK_SENT = "PAYMENT_LINK_SENT"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    REFUNDED = "REFUNDED"

    ALL = frozenset({NOT_REQUIRED, UNPAID, PAYMENT_LINK_SENT, PARTIALLY_PAID, PAID, REFUNDED})


DEFAULT_CURRENCY = "USD"

#: RequestStatus values that are quote-phase workflow-summary/compatibility states.
#: These remain authoritative ONLY for workflow display, never for the commercial
#: lifecycle (``quote_status`` wins — see ``resolve_commercial_quote_status``).
REQUEST_STATUS_QUOTE_SUMMARY = frozenset({"QUOTE_NEEDED", "QUOTE_SENT", "QUOTED"})

#: Client-visible fields in the quote projection (hard allowlist — see
#: ``build_client_quote_projection``). Anything not listed here is excluded.
CLIENT_QUOTE_ALLOWLIST = (
    "request_id",
    "quote_status",
    "quote_revision",
    "quote_amount_cents",
    "currency",
    "deposit_amount_cents",
    "payment_requirement",
    "payment_status",
    "payment_required",      # derived boolean
    "quote_notes_client",
    "quote_sent_at",
    "quote_accepted_at",
    "quote_accepted_revision",
    "service_type",
    "pet_names",
    "selected_dates",
    "start_date",
    "end_date",
)

#: Fields that must NEVER appear in a client projection (defense-in-depth; these are
#: explicitly dropped even if a future caller passes them in).
CLIENT_QUOTE_FORBIDDEN = frozenset({
    "quote_notes_internal",
    "internal_pricing_notes",
    "quote_history",
    "audit_log",
    "stripe_checkout_session_id",
    "stripe_payment_url",
    "stripe_payment_intent_id",
    "stripe_customer_id",
    "payment_amount_cents",
    "payment_requested_by",
    "company_id",
    "updated_by",
    "worker_id",
    "worker_name",
})

#: Legacy PET ``payment_status`` values that indicate the customer accepted the quote.
_LEGACY_ACCEPTED_PET_PAYMENT = frozenset({"Accepted", "Deposit Paid", "Paid in Full"})

#: Fields whose change on a SENT/ACCEPTED quote constitutes a client-visible
#: commercial change (and therefore creates a new revision + invalidates acceptance).
COMMERCIAL_QUOTE_FIELDS = (
    "quote_amount_cents",
    "currency",
    "deposit_amount_cents",
    "payment_requirement",
    "quote_notes_client",
)


class QuoteContractError(ValueError):
    """Raised for invalid quote-contract operations (caller maps to HTTP 400/409)."""


# ---------------------------------------------------------------------------
# Money (integer minor units / cents)
# ---------------------------------------------------------------------------

def to_cents(value):
    """Normalize a money value to a non-negative integer number of cents.

    Accepts int (already cents), Decimal/float/str in MAJOR units (dollars), or
    None. Major-unit values are rounded half-up to the nearest cent. Raises
    QuoteContractError for negative or non-numeric input.

    NOTE: a bare ``int`` is treated as already-cents (canonical new storage). Legacy
    Decimal/float major-unit conversion is handled by ``legacy_quote_amount_to_cents``
    which is explicit about the major-unit source; use that for legacy PET records.
    """
    if value is None:
        return 0
    if isinstance(value, bool):  # bool is an int subclass — reject explicitly
        raise QuoteContractError("amount must be numeric, not boolean")
    if isinstance(value, int):
        cents = value
    elif isinstance(value, (Decimal, float, str)):
        try:
            dec = Decimal(str(value))
        except Exception as exc:  # noqa: BLE001 - normalize to contract error
            raise QuoteContractError(f"invalid money value: {value!r}") from exc
        cents = int((dec * 100).to_integral_value(rounding=ROUND_HALF_UP))
    else:
        raise QuoteContractError(f"unsupported money type: {type(value).__name__}")
    if cents < 0:
        raise QuoteContractError("amount must not be negative")
    return cents


def legacy_quote_amount_to_cents(legacy_amount):
    """Convert a legacy PET ``quote_amount`` (Decimal MAJOR units) to integer cents.

    Read-time only. Returns 0 for None/empty. Does not mutate any record.
    """
    if legacy_amount in (None, ""):
        return 0
    try:
        dec = Decimal(str(legacy_amount))
    except Exception as exc:  # noqa: BLE001
        raise QuoteContractError(f"invalid legacy quote_amount: {legacy_amount!r}") from exc
    if dec < 0:
        raise QuoteContractError("legacy quote_amount must not be negative")
    return int((dec * 100).to_integral_value(rounding=ROUND_HALF_UP))


def cents_to_major_string(cents, currency=DEFAULT_CURRENCY):
    """Format integer cents as a major-unit display string (e.g. 1234 -> '12.34').

    Presentation helper only; storage remains integer cents.
    """
    cents = int(cents or 0)
    return f"{Decimal(cents) / 100:.2f}"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_quote_status_current(status):
    """Validate a value intended as the REQUEST's CURRENT ``quote_status``.

    Rejects ``SUPERSEDED`` (history-only) and any unknown value.
    """
    if status not in QuoteStatus.CURRENT_VALID:
        if status == QuoteStatus.SUPERSEDED:
            raise QuoteContractError("SUPERSEDED is history-only and cannot be the current quote_status")
        raise QuoteContractError(f"invalid current quote_status: {status!r}")
    return status


def validate_payment_requirement(value):
    if value not in PaymentRequirement.ALL:
        raise QuoteContractError(f"invalid payment_requirement: {value!r}")
    return value


def validate_payment_status(value):
    if value not in PaymentStatus.ALL:
        raise QuoteContractError(f"invalid payment_status: {value!r}")
    return value


# ---------------------------------------------------------------------------
# Legacy dual-read resolution
# ---------------------------------------------------------------------------

def normalize_legacy_payment_status(raw):
    """Map any legacy PET/REQ payment_status string to the canonical PaymentStatus.

    Returns a canonical PaymentStatus value. Unknown/empty -> UNPAID is NOT assumed;
    an unmapped non-empty value falls back to UNPAID only when it is clearly a
    not-yet-paid state, otherwise it is returned mapped conservatively. None/''
    -> NOT_REQUIRED.
    """
    if raw in (None, ""):
        return PaymentStatus.NOT_REQUIRED
    key = str(raw).strip().lower()
    mapping = {
        # canonical (idempotent)
        "not_required": PaymentStatus.NOT_REQUIRED,
        "unpaid": PaymentStatus.UNPAID,
        "payment_link_sent": PaymentStatus.PAYMENT_LINK_SENT,
        "partially_paid": PaymentStatus.PARTIALLY_PAID,
        "paid": PaymentStatus.PAID,
        "refunded": PaymentStatus.REFUNDED,
        # legacy PET vocabulary
        "not quoted": PaymentStatus.NOT_REQUIRED,
        "quote sent": PaymentStatus.UNPAID,
        "payment pending": PaymentStatus.UNPAID,
        "accepted": PaymentStatus.UNPAID,          # quote accepted, not yet paid
        "deposit paid": PaymentStatus.PARTIALLY_PAID,
        "paid in full": PaymentStatus.PAID,
        "waived": PaymentStatus.NOT_REQUIRED,
    }
    return mapping.get(key, PaymentStatus.UNPAID)


def resolve_quote_from_record(request_item, legacy_pet_item=None):
    """Resolve the canonical quote view for a REQUEST, with legacy dual-read.

    Precedence (approved R1): if the REQUEST carries a canonical ``quote_status``,
    it wins. Otherwise fall back to legacy signals — the legacy PET ``quote_amount``
    / ``payment_status`` and the REQUEST's quote-summary status.

    Returns a dict of canonical quote fields (never mutates inputs). This is a pure
    read resolver; it performs no persistence and no migration.
    """
    req = request_item or {}
    pet = legacy_pet_item or {}

    has_canonical = "quote_status" in req and req.get("quote_status") is not None

    if has_canonical:
        amount_cents = to_cents(req.get("quote_amount_cents"))
        quote_status = validate_quote_status_current(req.get("quote_status"))
        payment_requirement = req.get("payment_requirement") or (
            PaymentRequirement.NONE if amount_cents == 0 else PaymentRequirement.FULL
        )
        validate_payment_requirement(payment_requirement)
        payment_status = normalize_legacy_payment_status(req.get("payment_status"))
        return {
            "request_id": req.get("request_id"),
            "quote_status": quote_status,
            "quote_revision": int(req.get("quote_revision") or 1),
            "quote_amount_cents": amount_cents,
            "currency": req.get("currency") or DEFAULT_CURRENCY,
            "deposit_amount_cents": to_cents(req.get("deposit_amount_cents")),
            "payment_requirement": payment_requirement,
            "payment_status": payment_status,
            "quote_notes_client": req.get("quote_notes_client"),
            "quote_sent_at": req.get("quote_sent_at"),
            "quote_accepted_at": req.get("quote_accepted_at"),
            "quote_accepted_revision": req.get("quote_accepted_revision"),
            "source": "canonical",
        }

    # Legacy fallback: derive from PET pricing + REQ summary status.
    legacy_amount_cents = legacy_quote_amount_to_cents(pet.get("quote_amount"))
    legacy_pet_payment = pet.get("payment_status")
    legacy_accepted = legacy_pet_payment in _LEGACY_ACCEPTED_PET_PAYMENT

    if legacy_amount_cents == 0:
        derived_status = QuoteStatus.NOT_REQUIRED
    elif legacy_accepted:
        derived_status = QuoteStatus.ACCEPTED
    elif (req.get("status") in REQUEST_STATUS_QUOTE_SUMMARY) or legacy_pet_payment:
        derived_status = QuoteStatus.SENT
    else:
        derived_status = QuoteStatus.DRAFT

    payment_requirement = (
        PaymentRequirement.NONE if legacy_amount_cents == 0 else PaymentRequirement.FULL
    )
    return {
        "request_id": req.get("request_id"),
        "quote_status": derived_status,
        "quote_revision": 1,
        "quote_amount_cents": legacy_amount_cents,
        "currency": DEFAULT_CURRENCY,
        "deposit_amount_cents": legacy_quote_amount_to_cents(pet.get("deposit_amount")),
        "payment_requirement": payment_requirement,
        "payment_status": normalize_legacy_payment_status(legacy_pet_payment),
        "quote_notes_client": pet.get("quote_notes"),
        "quote_sent_at": pet.get("quote_sent_date"),
        "quote_accepted_at": pet.get("quote_accepted_date"),
        "quote_accepted_revision": None,
        "source": "legacy",
    }


def resolve_commercial_quote_status(request_item, legacy_pet_item=None):
    """Return the authoritative commercial quote status (``quote_status`` wins).

    This is the single decision point for commercial logic: when a canonical
    ``quote_status`` exists it is authoritative; the RequestStatus quote-summary
    values (QUOTE_NEEDED/QUOTE_SENT/QUOTED) are NEVER authoritative for the
    commercial lifecycle.
    """
    return resolve_quote_from_record(request_item, legacy_pet_item)["quote_status"]


# ---------------------------------------------------------------------------
# Client-safe projection
# ---------------------------------------------------------------------------

def build_client_quote_projection(request_item, legacy_pet_item=None):
    """Build the client-safe quote projection (hard allowlist).

    Combines REQUEST booking context (service/dates/pets) with the resolved
    canonical quote, exposing ONLY ``CLIENT_QUOTE_ALLOWLIST`` fields and never any
    ``CLIENT_QUOTE_FORBIDDEN`` field. ``payment_required`` is a derived boolean.

    This builder does NOT perform authorization — the caller MUST enforce tenant
    context and authenticated client ownership of the request before calling it
    (OPS-3A.1 handler wiring / OPS-3A.2). It is a pure projection.
    """
    req = request_item or {}
    resolved = resolve_quote_from_record(req, legacy_pet_item)

    payment_required = (
        resolved["payment_requirement"] in (PaymentRequirement.DEPOSIT, PaymentRequirement.FULL)
        and resolved["quote_amount_cents"] > 0
    )

    candidate = {
        "request_id": req.get("request_id"),
        "quote_status": resolved["quote_status"],
        "quote_revision": resolved["quote_revision"],
        "quote_amount_cents": resolved["quote_amount_cents"],
        "currency": resolved["currency"],
        "deposit_amount_cents": resolved["deposit_amount_cents"],
        "payment_requirement": resolved["payment_requirement"],
        "payment_status": resolved["payment_status"],
        "payment_required": payment_required,
        "quote_notes_client": resolved["quote_notes_client"],
        "quote_sent_at": resolved["quote_sent_at"],
        "quote_accepted_at": resolved["quote_accepted_at"],
        "quote_accepted_revision": resolved["quote_accepted_revision"],
        "service_type": req.get("service_type"),
        "pet_names": req.get("pet_names"),
        "selected_dates": req.get("selected_dates"),
        "start_date": req.get("start_date"),
        "end_date": req.get("end_date"),
    }

    # Hard allowlist: only emit allowed keys, and never emit a forbidden key.
    projection = {
        key: candidate[key]
        for key in CLIENT_QUOTE_ALLOWLIST
        if key in candidate and key not in CLIENT_QUOTE_FORBIDDEN
    }
    return projection


# ---------------------------------------------------------------------------
# Owner/admin quote mutation foundation (draft / update / send)
# ---------------------------------------------------------------------------

def _snapshot_for_history(req):
    """Build an immutable SUPERSEDED history entry from the current quote state."""
    return {
        "quote_status": QuoteStatus.SUPERSEDED,
        "quote_revision": int(req.get("quote_revision") or 1),
        "quote_amount_cents": to_cents(req.get("quote_amount_cents")),
        "currency": req.get("currency") or DEFAULT_CURRENCY,
        "deposit_amount_cents": to_cents(req.get("deposit_amount_cents")),
        "payment_requirement": req.get("payment_requirement") or PaymentRequirement.NONE,
        "quote_notes_client": req.get("quote_notes_client"),
        "quote_accepted_at": req.get("quote_accepted_at"),
        "quote_accepted_revision": req.get("quote_accepted_revision"),
        "quote_sent_at": req.get("quote_sent_at"),
    }


def _is_commercial_change(current_req, incoming):
    """True if ``incoming`` changes any client-visible commercial field."""
    for field in COMMERCIAL_QUOTE_FIELDS:
        if field not in incoming:
            continue
        new_val = incoming[field]
        if field in ("quote_amount_cents", "deposit_amount_cents"):
            if to_cents(new_val) != to_cents(current_req.get(field)):
                return True
        else:
            if new_val != current_req.get(field):
                return True
    return False


def apply_quote_update(current_req, incoming, now_iso):
    """Compute the next quote field-set for an owner/admin DRAFT/UPDATE.

    Pure function: returns a NEW dict of quote fields to persist (the caller writes
    them to the REQUEST). It never mutates ``current_req`` and never sets the
    RequestStatus or approves anything.

    Semantics (approved R3):
      - A client-visible COMMERCIAL change to an already SENT/ACCEPTED quote starts a
        new revision: the prior quote is snapshotted into ``quote_history`` as
        SUPERSEDED, ``quote_revision`` increments, acceptance is cleared, and
        ``quote_status`` returns to DRAFT (re-send required).
      - On a DRAFT (or first draft), fields are set in place with no revision bump.
      - Internal-only note changes never bump the revision or clear acceptance.

    ``incoming`` may include: quote_amount_cents, currency, deposit_amount_cents,
    payment_requirement, quote_notes_client, quote_notes_internal,
    internal_pricing_notes.
    """
    cur = dict(current_req or {})
    cur_status = cur.get("quote_status") or QuoteStatus.DRAFT
    if cur_status != QuoteStatus.DRAFT:
        validate_quote_status_current(cur_status)

    # Validate incoming commercial values up-front.
    if "payment_requirement" in incoming:
        validate_payment_requirement(incoming["payment_requirement"])

    result = {}
    # Internal-only notes always pass through (never commercial).
    for internal_field in ("quote_notes_internal", "internal_pricing_notes"):
        if internal_field in incoming:
            result[internal_field] = incoming[internal_field]

    commercial = _is_commercial_change(cur, incoming)
    was_live = cur_status in (QuoteStatus.SENT, QuoteStatus.ACCEPTED)

    # Apply commercial fields.
    if "quote_amount_cents" in incoming:
        result["quote_amount_cents"] = to_cents(incoming["quote_amount_cents"])
    if "currency" in incoming:
        result["currency"] = incoming["currency"] or DEFAULT_CURRENCY
    if "deposit_amount_cents" in incoming:
        result["deposit_amount_cents"] = to_cents(incoming["deposit_amount_cents"])
    if "payment_requirement" in incoming:
        result["payment_requirement"] = incoming["payment_requirement"]
    if "quote_notes_client" in incoming:
        result["quote_notes_client"] = incoming["quote_notes_client"]

    if commercial and was_live:
        # New revision: snapshot prior, bump revision, reset acceptance, back to DRAFT.
        history = list(cur.get("quote_history") or [])
        history.append(_snapshot_for_history(cur))
        result["quote_history"] = history
        result["quote_revision"] = int(cur.get("quote_revision") or 1) + 1
        result["quote_status"] = QuoteStatus.DRAFT
        result["quote_accepted_at"] = None
        result["quote_accepted_revision"] = None
        result["updated_at"] = now_iso
    else:
        # In-place draft edit (or internal-only / no commercial change).
        if cur.get("quote_revision") is None and (
            "quote_amount_cents" in result or cur_status == QuoteStatus.DRAFT
        ):
            result["quote_revision"] = int(cur.get("quote_revision") or 1)
        # First time a quote is drafted, establish DRAFT status.
        if cur.get("quote_status") is None and (
            "quote_amount_cents" in incoming or "quote_notes_client" in incoming
        ):
            result["quote_status"] = QuoteStatus.DRAFT
        result["updated_at"] = now_iso

    return result


def apply_quote_send(current_req, now_iso):
    """Compute the field-set to transition a DRAFT quote to SENT.

    Pure function. Requires the current ``quote_status`` to be DRAFT (or legacy/None
    with an amount already present). Sets ``quote_sent_at`` and leaves acceptance and
    RequestStatus to the caller (RequestStatus QUOTE_SENT is a derived summary the
    caller sets; this function never approves anything).
    """
    cur = dict(current_req or {})
    cur_status = cur.get("quote_status") or QuoteStatus.DRAFT
    if cur_status not in (QuoteStatus.DRAFT, QuoteStatus.SENT):
        raise QuoteContractError(f"cannot send a quote in status {cur_status!r}; must be DRAFT")
    amount_cents = to_cents(cur.get("quote_amount_cents"))
    if amount_cents <= 0:
        raise QuoteContractError("cannot send a quote with no amount")
    return {
        "quote_status": QuoteStatus.SENT,
        "quote_sent_at": now_iso,
        "quote_revision": int(cur.get("quote_revision") or 1),
        "updated_at": now_iso,
    }


# ---------------------------------------------------------------------------
# Client Accept / Decline (OPS-3A.2 — approved 2026-10-05)
# ---------------------------------------------------------------------------

#: Maximum length of a client-supplied decline reason (approved A2-3).
MAX_DECLINE_REASON_LEN = 500


def normalize_decline_reason(raw):
    """Normalize an optional client-supplied decline reason (approved A2-3).

    Rules: trim leading/trailing whitespace; a value that is None or becomes empty
    after trimming is treated as ABSENT and returns ``None``; a value longer than
    ``MAX_DECLINE_REASON_LEN`` characters (after trimming) raises
    ``QuoteContractError`` (caller maps to HTTP 400). Non-string input is rejected.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise QuoteContractError("decline_reason must be a string")
    trimmed = raw.strip()
    if trimmed == "":
        return None
    if len(trimmed) > MAX_DECLINE_REASON_LEN:
        raise QuoteContractError(
            f"decline_reason exceeds {MAX_DECLINE_REASON_LEN} characters"
        )
    return trimmed


def apply_quote_accept(current_req, expected_revision, now_iso):
    """Compute the field-set for a client ACCEPT of the current SENT quote.

    Pure function (no DynamoDB I/O). Returns a NEW dict of fields the caller persists
    with an atomic conditional write guarding (quote_revision, quote_status==SENT).
    Never mutates ``current_req``; never approves the booking; never touches payment.

    Approved semantics (A2-1 / A2-2):
      - Eligible ONLY from current ``quote_status == SENT``.
      - Transition SENT -> ACCEPTED.
      - ``quote_revision`` is NOT incremented (acceptance is a lifecycle event on the
        current revision, not a new commercial offer).
      - Binds acceptance to the current revision: ``quote_accepted_revision ==
        quote_revision``.
      - ``expected_revision`` must equal the current ``quote_revision`` (caller also
        enforces this atomically; this is the pure-layer guard).

    Raises ``QuoteContractError`` on an ineligible status or a revision mismatch
    (caller maps a status error to 409 and the atomic conditional write is the
    authoritative race guard).
    """
    cur = dict(current_req or {})
    cur_status = cur.get("quote_status")
    if cur_status != QuoteStatus.SENT:
        raise QuoteContractError(
            f"cannot accept a quote in status {cur_status!r}; must be SENT"
        )
    cur_revision = int(cur.get("quote_revision") or 1)
    if int(expected_revision) != cur_revision:
        raise QuoteContractError(
            "expected_revision does not match the current quote_revision"
        )
    return {
        "quote_status": QuoteStatus.ACCEPTED,
        "quote_accepted_at": now_iso,
        "quote_accepted_revision": cur_revision,
        "quote_revision": cur_revision,  # unchanged; written for explicitness
        "updated_at": now_iso,
    }


def apply_quote_decline(current_req, expected_revision, now_iso, decline_reason=None):
    """Compute the field-set for a client DECLINE of the current SENT quote.

    Pure function (no DynamoDB I/O). Mirrors ``apply_quote_accept``: eligible only
    from SENT, transitions SENT -> DECLINED, does NOT increment ``quote_revision``,
    binds the decline to the current revision (``quote_declined_revision``), records
    ``quote_declined_at``, and never touches payment or the request/booking lifecycle.

    ``decline_reason`` is normalized via ``normalize_decline_reason`` (trim; blank ->
    absent; >MAX_DECLINE_REASON_LEN -> QuoteContractError). When present it is stored
    as the client-visible ``quote_declined_reason_client``.
    """
    cur = dict(current_req or {})
    cur_status = cur.get("quote_status")
    if cur_status != QuoteStatus.SENT:
        raise QuoteContractError(
            f"cannot decline a quote in status {cur_status!r}; must be SENT"
        )
    cur_revision = int(cur.get("quote_revision") or 1)
    if int(expected_revision) != cur_revision:
        raise QuoteContractError(
            "expected_revision does not match the current quote_revision"
        )
    reason = normalize_decline_reason(decline_reason)
    fields = {
        "quote_status": QuoteStatus.DECLINED,
        "quote_declined_at": now_iso,
        "quote_declined_revision": cur_revision,
        "quote_revision": cur_revision,  # unchanged
        "updated_at": now_iso,
    }
    if reason is not None:
        fields["quote_declined_reason_client"] = reason
    return fields


# ---------------------------------------------------------------------------
# Booking-confirmation predicate (approved R4) — read gate foundation
# ---------------------------------------------------------------------------

def evaluate_booking_approval_predicate(
    quote_status,
    payment_requirement,
    payment_status,
    quote_amount_cents=0,
    payment_waived=False,
):
    """Evaluate whether a booking MAY be approved (quote + payment predicate).

    Returns ``(ok: bool, reason: str)``. This is a READ gate foundation — it does NOT
    perform the APPROVED transition and does NOT itself approve anything. Quote
    acceptance alone never approves a booking (approved decision 13); APPROVED stays
    an explicit tenant action, and this predicate only reports eligibility.

    Rules (approved R4):
      - Quote condition: NOT_REQUIRED (or amount 0) OR ACCEPTED.
      - Payment condition by requirement: NONE -> satisfied; DEPOSIT ->
        PARTIALLY_PAID or PAID; FULL -> PAID; an authorized owner/admin waiver
        satisfies the payment condition regardless of payment_status.
      - PARTIALLY_PAID never satisfies FULL.
    """
    amount_cents = to_cents(quote_amount_cents)
    no_quote = (quote_status == QuoteStatus.NOT_REQUIRED) or amount_cents == 0

    # Quote condition.
    if not no_quote and quote_status != QuoteStatus.ACCEPTED:
        return False, f"quote not accepted (quote_status={quote_status})"

    if payment_requirement is not None:
        validate_payment_requirement(payment_requirement)

    # Payment condition.
    if no_quote or payment_requirement in (None, PaymentRequirement.NONE):
        return True, "ok: no payment required"
    if payment_waived:
        return True, "ok: payment waived by authorized owner/admin"
    if payment_requirement == PaymentRequirement.DEPOSIT:
        if payment_status in (PaymentStatus.PARTIALLY_PAID, PaymentStatus.PAID):
            return True, "ok: deposit satisfied"
        return False, f"deposit required; payment_status={payment_status}"
    if payment_requirement == PaymentRequirement.FULL:
        if payment_status == PaymentStatus.PAID:
            return True, "ok: paid in full"
        return False, f"full payment required; payment_status={payment_status}"
    return False, f"unknown payment_requirement={payment_requirement}"
