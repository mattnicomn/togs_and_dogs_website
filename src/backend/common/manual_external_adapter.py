"""
W3-C1 — MANUAL_EXTERNAL payment settlement adapter (server-only, local).

This is the FIRST selected provider adapter under W3 Option D
(`PROVIDER_ABSTRACTION + MANUAL_EXTERNAL`). It records an externally-collected payment
(cash / check / bank transfer / tenant-owned external processor) against a REQUEST,
updating the canonical W3-B payment summary and appending an immutable PAYMENT_EVENT
**atomically**. It integrates the merged W3-B provider-neutral domain
(`common.payment_domain`) and performs NO payment-processor integration.

Hard boundaries (W3-C1):
  - Server-only service; NOT an HTTP endpoint. No route/API Gateway/UI registration.
  - Owner/admin only; staff and clients can never record a settlement. A client can
    never self-assert PAID.
  - The caller is NEVER authoritative for company/tenant, actor, current or resulting
    payment status, the paid total, or payment_completed_at — all derived server-side.
  - Money is strict integer minor units via ``payment_domain.canonical_cents`` (no ×100).
  - No Stripe / Connect / OAuth / Checkout / PaymentIntent / webhook / secret.
  - No refunds (deferred). No auto-approval / booking / scheduling / notification.
  - The REQUEST summary + PAYMENT_EVENT are two distinct items committed all-or-nothing
    via DynamoDB ``TransactWriteItems``. (Runtime requires the Lambda role to carry
    ``dynamodb:TransactWriteItems``; that IAM grant is NOT part of W3-C1 and is a future,
    separately-authorized change — ``W3C1_RUNTIME_IAM_CHANGE_REQUIRED=YES``.)

All AWS access is acquired LAZILY inside functions so the module stays import-clean and
unit-testable with mocks (no live AWS in tests).
"""

from datetime import datetime, timezone

from common.payment_domain import (
    PaymentDomainError,
    PaymentProvider,
    PaymentStatus,
    PaymentRequirement,
    PaymentEventType,
    DEFAULT_CURRENCY,
    canonical_cents,
    normalize_payment_status,
    validate_transition,
    can_transition,
    build_payment_event,
    sanitize_payment_event_metadata,
    is_booking_payment_ready,
    load_owned_request,
    payment_event_sk,
    _events_semantically_equal,
    PERSIST_CREATED,
    PERSIST_DUPLICATE_SAME_EVENT,
    PERSIST_CONFLICTING_IDEMPOTENCY_KEY,
)
from common.quote_contract import QuoteStatus, normalize_stored_cents


# ---------------------------------------------------------------------------
# Result contract (reuses the W3-B persistence vocabulary)
# ---------------------------------------------------------------------------

RECORD_CREATED = PERSIST_CREATED
RECORD_DUPLICATE_SAME_EVENT = PERSIST_DUPLICATE_SAME_EVENT
RECORD_CONFLICTING_IDEMPOTENCY_KEY = PERSIST_CONFLICTING_IDEMPOTENCY_KEY


class ManualExternalError(PaymentDomainError):
    """Raised for invalid MANUAL_EXTERNAL settlement operations (caller maps to 4xx)."""


class StaleSummaryConflict(ManualExternalError):
    """The REQUEST summary changed under us (stale revision / concurrent writer)."""


# ---------------------------------------------------------------------------
# Payment-method category (small, provider-neutral enum)
# ---------------------------------------------------------------------------

class PaymentMethodCategory:
    CASH = "CASH"
    CHECK = "CHECK"
    BANK_TRANSFER = "BANK_TRANSFER"
    EXTERNAL_PROCESSOR = "EXTERNAL_PROCESSOR"
    OTHER = "OTHER"

    ALL = frozenset({CASH, CHECK, BANK_TRANSFER, EXTERNAL_PROCESSOR, OTHER})


#: Max length for the opaque external_reference (short, non-sensitive identifier).
EXTERNAL_REFERENCE_MAX_LEN = 128


def validate_payment_method_category(value):
    """None -> OTHER; a known category passes; anything else is rejected."""
    if value is None:
        return PaymentMethodCategory.OTHER
    if value in PaymentMethodCategory.ALL:
        return value
    raise ManualExternalError(f"invalid payment_method_category: {value!r}")


def validate_external_reference(value):
    """A short, opaque reference string, or None. Never instrument/secret data.

    We reject obviously-sensitive content defensively (long digit runs that look like a
    card/account number). This is a reference label (e.g. 'CHECK-10482'), not a data field.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManualExternalError("external_reference must be a string")
    ref = value.strip()
    if not ref:
        return None
    if len(ref) > EXTERNAL_REFERENCE_MAX_LEN:
        raise ManualExternalError("external_reference too long")
    digits = [c for c in ref if c.isdigit()]
    if len(digits) >= 12:
        # 12+ digits looks like a PAN/account/routing number — refuse.
        raise ManualExternalError(
            "external_reference must be an opaque label, not an account/card number"
        )
    return ref


# ---------------------------------------------------------------------------
# REQUEST key + summary revision helpers
# ---------------------------------------------------------------------------

#: Attribute name for the optimistic-concurrency guard on the REQUEST summary.
PAYMENT_SUMMARY_REVISION_FIELD = "payment_summary_revision"


def request_pk(request_id):
    return f"REQ#{request_id}"


def request_sk(client_id):
    return f"CLIENT#{client_id}"


def _current_summary_revision(request_item):
    """Logical current revision; a record without the field is revision 0."""
    raw = request_item.get(PAYMENT_SUMMARY_REVISION_FIELD)
    if raw is None:
        return 0
    try:
        return int(normalize_stored_cents(raw))  # integer, non-negative, no ×100
    except PaymentDomainError:
        raise ManualExternalError(
            f"invalid {PAYMENT_SUMMARY_REVISION_FIELD}: {raw!r}"
        )


def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Derived resulting status (never accepts a caller-provided target)
# ---------------------------------------------------------------------------

def derive_resulting_status(payment_requirement, prev_status, new_amount_paid,
                            required_cents, deposit_cents):
    """Derive the resulting canonical status from amounts; validate against the machine.

    W3-C1 reconciliation: any recorded positive settlement that does not reach the full
    required amount results in ``PARTIALLY_PAID`` — the canonical status must never remain
    ``UNPAID`` while ``amount_paid_cents > 0`` (below-deposit contributions included). A
    settlement that reaches the full required amount results in ``PAID``. ``NONE`` requires
    no collection and is rejected by the caller before this point.
    """
    if new_amount_paid >= required_cents and required_cents > 0:
        resulting = PaymentStatus.PAID
    elif new_amount_paid > 0:
        resulting = PaymentStatus.PARTIALLY_PAID
    else:
        # No positive money recorded — not a valid settlement operation.
        raise ManualExternalError("no positive payment recorded")

    # The computed transition must be legal from the (normalized) previous status.
    validate_transition(prev_status, resulting)
    return resulting


# ---------------------------------------------------------------------------
# Transaction orchestration (lazy AWS; mockable)
# ---------------------------------------------------------------------------

def _build_summary_update_item(request_id, client_id, resulting_status, new_amount_paid,
                               currency, payment_completed_at, expected_revision,
                               next_revision):
    """Build the TransactWriteItems `Update` operand for the REQUEST summary.

    Conditional guard: the REQUEST exists AND its revision equals ``expected_revision``.
    For ``expected_revision == 0`` the guard also accepts a record where the revision
    attribute is absent (legacy/first-settlement), via ``attribute_not_exists``.
    """
    names = {
        "#ps": "payment_status",
        "#ap": "amount_paid_cents",
        "#cur": "currency",
        "#pp": "payment_provider",
        "#rev": PAYMENT_SUMMARY_REVISION_FIELD,
        "#ua": "updated_at",
    }
    values = {
        ":ps": resulting_status,
        ":ap": new_amount_paid,
        ":cur": currency,
        ":pp": PaymentProvider.MANUAL_EXTERNAL,
        ":rev": next_revision,
        ":ua": payment_completed_at or _now_iso(),
        ":exprev": expected_revision,
    }
    set_clauses = [
        "#ps = :ps", "#ap = :ap", "#cur = :cur", "#pp = :pp",
        "#rev = :rev", "#ua = :ua",
    ]
    if payment_completed_at is not None:
        names["#pca"] = "payment_completed_at"
        values[":pca"] = payment_completed_at
        set_clauses.append("#pca = :pca")

    if expected_revision == 0:
        # First settlement / legacy record: revision absent OR explicitly 0.
        condition = (
            "attribute_exists(PK) AND "
            "(attribute_not_exists(#rev) OR #rev = :exprev)"
        )
    else:
        condition = "attribute_exists(PK) AND #rev = :exprev"

    return {
        "Update": {
            "Key": {"PK": request_pk(request_id), "SK": request_sk(client_id)},
            "UpdateExpression": "SET " + ", ".join(set_clauses),
            "ConditionExpression": condition,
            "ExpressionAttributeNames": names,
            "ExpressionAttributeValues": values,
        }
    }


def _build_event_put_item(event_item, table_name):
    """Build the TransactWriteItems `Put` operand for the append-only PAYMENT_EVENT."""
    put = {
        "Item": event_item,
        "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)",
    }
    if table_name:
        put["TableName"] = table_name
    return {"Put": put}


def _execute_transaction(event_item, summary_update):
    """Execute the two-item atomic transaction via the low-level DynamoDB client.

    Lazy client acquisition keeps imports clean and tests AWS-free. Returns None on
    success; raises the botocore ClientError on cancellation so the caller can classify.
    Note: the TransactWriteItems `Put` built here is resource-form; for execution we route
    through the table's meta client with an explicit TableName, matching repo conventions.
    """
    import os
    from common.db import table as _table

    table_name = os.environ.get("DATA_TABLE_NAME")
    client = _table.meta.client

    # Event Put needs TableName in low-level form.
    event_put = _build_event_put_item(event_item, table_name)
    # Summary Update needs TableName in low-level form.
    summary_update = dict(summary_update)
    summary_update["Update"] = dict(summary_update["Update"])
    summary_update["Update"]["TableName"] = table_name

    client.transact_write_items(TransactItems=[event_put, summary_update])
    return None


# ---------------------------------------------------------------------------
# Public operation
# ---------------------------------------------------------------------------

def record_external_payment(
    event,
    request_id,
    client_id,
    amount_delta_cents,
    currency=DEFAULT_CURRENCY,
    idempotency_key=None,
    external_reference=None,
    payment_method_category=None,
    note=None,
):
    """Record one externally-collected (MANUAL_EXTERNAL) payment against a REQUEST.

    Server-only. Owner/admin only. Returns a dict:
      {result, previous_status, resulting_status, amount_paid_cents,
       payment_completed_at, payment_summary_revision, booking_ready,
       booking_ready_reason}
    where ``result`` is ``RECORD_CREATED`` / ``RECORD_DUPLICATE_SAME_EVENT`` /
    ``RECORD_CONFLICTING_IDEMPOTENCY_KEY``.

    Raises ``ManualExternalError`` (authorization/validation/state) or
    ``StaleSummaryConflict`` (concurrent writer) with no write on any failure.
    """
    # Lazy auth import (keeps module import-clean; mockable).
    from common.auth import require_owner_or_admin, get_current_company_id, get_claims

    # 1. Authorization — owner/admin only; raises PermissionError otherwise.
    try:
        require_owner_or_admin(event)
    except PermissionError as exc:
        raise ManualExternalError("not authorized to record external payment") from exc

    # 2. Trusted tenant + actor (never from caller body).
    company_id = get_current_company_id(event)
    claims = get_claims(event) or {}
    actor_email = (claims.get("email") or claims.get("username") or "admin-api")
    actor = f"manual_external:{actor_email}"

    # 3. Operation-input validation.
    if not request_id or not client_id:
        raise ManualExternalError("request_id and client_id are required")
    if not idempotency_key or not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ManualExternalError("idempotency_key (non-empty string) is required")
    delta = canonical_cents(amount_delta_cents)
    if delta <= 0:
        raise ManualExternalError("amount_delta_cents must be a positive integer of cents")
    if not currency:
        raise ManualExternalError("currency is required")
    method_category = validate_payment_method_category(payment_method_category)
    opaque_ref = validate_external_reference(external_reference)

    # 4. Load + validate REQUEST ownership (fail closed; no write on mismatch).
    request_item = load_owned_request(request_id, client_id, company_id)

    # 4a. Early idempotency pre-check: if a PAYMENT_EVENT already exists for this
    # (request, idempotency_key), this is a replay. A legitimately-applied prior
    # settlement may have driven the summary to a terminal state (e.g. PAID), so we must
    # classify the replay BEFORE the terminal-state guard rejects it. We only short-
    # circuit on an EXACT semantic match (same event payload); a different payload under
    # the same key is a conflict. A brand-new key falls through to normal processing, and
    # the conditional transaction remains the authoritative idempotency guard against
    # races between this pre-check and the write.
    from common.db import get_item as _get_item
    existing_evt = _get_item(request_pk(request_id), payment_event_sk(idempotency_key))
    if existing_evt:
        # Rebuild a candidate strictly for semantic comparison (no write).
        candidate = _build_replay_candidate(
            request_id, company_id, client_id, idempotency_key, existing_evt, delta, currency
        )
        if _events_semantically_equal(existing_evt, candidate):
            return _idempotent_replay_result(request_id, client_id, company_id, request_item)
        raise ManualExternalError(
            "idempotency_key reused with a different payment payload"
        )

    # 5. Read canonical current summary.
    req = request_item.get("payment_requirement")
    if req not in (PaymentRequirement.DEPOSIT, PaymentRequirement.FULL):
        # NONE / unknown → no collection to record.
        raise ManualExternalError(
            f"request does not require collectible payment (payment_requirement={req!r})"
        )
    prev_status = normalize_payment_status(request_item.get("payment_status"))
    required_cents = canonical_cents(request_item.get("amount_required_cents")
                                     if request_item.get("amount_required_cents") is not None
                                     else request_item.get("quote_amount_cents"))
    deposit_cents = canonical_cents(request_item.get("deposit_amount_cents"))
    existing_paid = canonical_cents(request_item.get("amount_paid_cents"))
    req_currency = request_item.get("currency") or DEFAULT_CURRENCY

    # 6. Currency must match the canonical REQUEST currency (no FX).
    if currency != req_currency:
        raise ManualExternalError(
            f"currency mismatch: operation {currency!r} != request {req_currency!r}"
        )

    # 7. Reject settlement from terminal/illegal states up front (clear errors).
    if prev_status in (PaymentStatus.PAID, PaymentStatus.REFUNDED, PaymentStatus.NOT_REQUIRED):
        raise ManualExternalError(
            f"cannot record settlement from status {prev_status}"
        )

    # 8. Compute new total + reject overpayment (W3-C1 does not model overpayment).
    new_amount_paid = existing_paid + delta
    if required_cents > 0 and new_amount_paid > required_cents:
        raise ManualExternalError(
            "amount_paid would exceed required total (overpayment not modeled in W3-C1)"
        )

    # 9. Derive resulting status (never from the caller).
    resulting_status = derive_resulting_status(
        req, prev_status, new_amount_paid, required_cents, deposit_cents
    )

    # 10. Build immutable PAYMENT_EVENT (validates transition/provider/metadata/amount).
    event_type = (PaymentEventType.PAYMENT_SETTLED
                  if resulting_status == PaymentStatus.PAID
                  else PaymentEventType.PAYMENT_PARTIALLY_SETTLED)
    safe_metadata = sanitize_payment_event_metadata(
        {"payment_method_category": method_category, "note": note} if note is not None
        else {"payment_method_category": method_category}
    )
    now_iso = _now_iso()
    payment_completed_at = now_iso if resulting_status == PaymentStatus.PAID else None

    event_item = build_payment_event(
        request_id=request_id,
        company_id=company_id,
        event_type=event_type,
        idempotency_key=idempotency_key,
        previous_status=prev_status,
        resulting_status=resulting_status,
        client_id=client_id,
        provider=PaymentProvider.MANUAL_EXTERNAL,
        amount_delta_cents=delta,
        currency=currency,
        provider_txn_ref=opaque_ref,
        actor=actor,
        metadata=safe_metadata,
        now_iso=now_iso,
    )

    # 11. Build the conditional summary update.
    expected_revision = _current_summary_revision(request_item)
    next_revision = expected_revision + 1
    summary_update = _build_summary_update_item(
        request_id, client_id, resulting_status, new_amount_paid, currency,
        payment_completed_at, expected_revision, next_revision,
    )

    # 12. Atomic two-item transaction.
    from botocore.exceptions import ClientError
    try:
        _execute_transaction(event_item, summary_update)
        result = RECORD_CREATED
        committed_completed_at = payment_completed_at
        committed_paid = new_amount_paid
        committed_status = resulting_status
        committed_revision = next_revision
    except ClientError as exc:
        code = (exc.response or {}).get("Error", {}).get("Code")
        if code not in ("TransactionCanceledException", "ConditionalCheckFailedException"):
            raise ManualExternalError(f"payment transaction failed: {code}") from exc
        # Classify: read the event key.
        result, existing = _classify_cancellation(request_id, idempotency_key, event_item)
        if result == RECORD_DUPLICATE_SAME_EVENT:
            # Idempotent replay: the prior event+summary already committed atomically.
            # Return current persisted state; DO NOT reapply money or bump revision.
            current = load_owned_request(request_id, client_id, company_id)
            committed_paid = canonical_cents(current.get("amount_paid_cents"))
            committed_status = normalize_payment_status(current.get("payment_status"))
            committed_completed_at = current.get("payment_completed_at")
            committed_revision = _current_summary_revision(current)
        elif result == RECORD_CONFLICTING_IDEMPOTENCY_KEY:
            raise ManualExternalError(
                "idempotency_key reused with a different payment payload"
            )
        else:  # stale / concurrent REQUEST summary conflict, no event exists
            raise StaleSummaryConflict(
                "request payment summary changed concurrently; reload and retry"
            )

    # 13. Supplementary (non-authoritative) audit log — AFTER the committed transaction.
    if result == RECORD_CREATED:
        try:
            from common.audit import log_action
            log_action(
                event,
                "EXTERNAL_PAYMENT_RECORDED",
                request_pk(request_id),
                target_sk=request_sk(client_id),
                previous_status=prev_status,
                new_status=committed_status,
            )
        except Exception as audit_exc:  # noqa: BLE001 - supplementary only
            # Authoritative payment state already committed; a supplementary audit
            # failure must NOT roll back or re-apply money. Log and continue.
            print(f"WARN: supplementary AUDIT# write failed for REQ#{request_id}: {audit_exc}")

    # 14. Informational booking readiness (never mutates/approves).
    ready, reason = is_booking_payment_ready(
        request_item.get("quote_status"),
        req,
        committed_status,
        quote_amount_cents=required_cents,
        deposit_amount_cents=deposit_cents,
        amount_paid_cents=committed_paid,
        currency=currency,
    )

    return {
        "result": result,
        "previous_status": prev_status,
        "resulting_status": committed_status,
        "amount_paid_cents": committed_paid,
        "payment_completed_at": committed_completed_at,
        "payment_summary_revision": committed_revision,
        "payment_provider": PaymentProvider.MANUAL_EXTERNAL,
        "booking_ready": ready,
        "booking_ready_reason": reason,
    }


def _build_replay_candidate(request_id, company_id, client_id, idempotency_key,
                            stored_event, delta, currency):
    """Build a comparison-only event dict for the early idempotency pre-check.

    Compares the operation-derived identity (provider, amount delta, currency, request/
    company/client ids, opaque reference) against the stored event, reusing the stored
    event's status/type fields (a genuine replay recomputes the same transition). This
    is NOT persisted; it exists solely for ``_events_semantically_equal``.
    """
    return {
        "event_type": stored_event.get("event_type"),
        "payment_provider": PaymentProvider.MANUAL_EXTERNAL,
        "previous_payment_status": stored_event.get("previous_payment_status"),
        "resulting_payment_status": stored_event.get("resulting_payment_status"),
        "amount_delta_cents": delta,
        "currency": currency,
        "request_id": request_id,
        "company_id": company_id,
        "client_id": client_id,
        "provider_txn_ref": stored_event.get("provider_txn_ref"),
    }


def _idempotent_replay_result(request_id, client_id, company_id, request_item):
    """Return the current persisted state for an idempotent replay (no re-apply)."""
    status = normalize_payment_status(request_item.get("payment_status"))
    req = request_item.get("payment_requirement")
    required_cents = canonical_cents(
        request_item.get("amount_required_cents")
        if request_item.get("amount_required_cents") is not None
        else request_item.get("quote_amount_cents")
    )
    deposit_cents = canonical_cents(request_item.get("deposit_amount_cents"))
    paid = canonical_cents(request_item.get("amount_paid_cents"))
    currency = request_item.get("currency") or DEFAULT_CURRENCY
    ready, reason = is_booking_payment_ready(
        request_item.get("quote_status"), req, status,
        quote_amount_cents=required_cents, deposit_amount_cents=deposit_cents,
        amount_paid_cents=paid, currency=currency,
    )
    return {
        "result": RECORD_DUPLICATE_SAME_EVENT,
        "previous_status": status,
        "resulting_status": status,
        "amount_paid_cents": paid,
        "payment_completed_at": request_item.get("payment_completed_at"),
        "payment_summary_revision": _current_summary_revision(request_item),
        "payment_provider": PaymentProvider.MANUAL_EXTERNAL,
        "booking_ready": ready,
        "booking_ready_reason": reason,
    }


def _classify_cancellation(request_id, idempotency_key, candidate_event):
    """Classify a transaction cancellation by inspecting the PAYMENT_EVENT key.

    Does not rely on SDK cancellation-reason availability. Returns
    ``(result, existing_event_or_None)``.
    """
    from common.db import get_item
    sk = payment_event_sk(idempotency_key)
    existing = get_item(request_pk(request_id), sk)
    if existing:
        if _events_semantically_equal(existing, candidate_event):
            return RECORD_DUPLICATE_SAME_EVENT, existing
        return RECORD_CONFLICTING_IDEMPOTENCY_KEY, existing
    # No event written → the REQUEST summary condition failed (stale/concurrent).
    return "STALE_SUMMARY_CONFLICT", None
