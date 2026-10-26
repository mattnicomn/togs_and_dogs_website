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
from common.quote_contract import QuoteStatus, normalize_stored_cents, QuoteContractError


# ---------------------------------------------------------------------------
# Result contract (reuses the W3-B persistence vocabulary)
# ---------------------------------------------------------------------------

RECORD_CREATED = PERSIST_CREATED
RECORD_DUPLICATE_SAME_EVENT = PERSIST_DUPLICATE_SAME_EVENT
RECORD_CONFLICTING_IDEMPOTENCY_KEY = PERSIST_CONFLICTING_IDEMPOTENCY_KEY


# ---------------------------------------------------------------------------
# Stable error codes (W3-C2 hardening)
# ---------------------------------------------------------------------------
# Callers (HTTP routes) MUST map on these stable codes, never on exception message
# text. Messages are developer-facing/log-only and may change; codes are the contract.
# Grouping by intended caller disposition:
#   *_VALIDATION   -> 400 (bad caller input)
#   NOT_AUTHORIZED -> 403 (role/authorization)
#   OWNERSHIP      -> 403 (tenant/client ownership; non-disclosing)
#   NOT_FOUND      -> 404 (request does not exist for this caller; non-disclosing)
#   STATE_CONFLICT -> 409 (terminal/illegal state, overpayment)
#   IDEMPOTENCY_CONFLICT -> 409 (key reused with different evidence)
#   STALE_CONFLICT -> 409 (concurrent writer / stale summary revision)
#   INFRASTRUCTURE -> 500 (server/config/transaction failure; never a client 4xx)
ERR_VALIDATION = "VALIDATION"
ERR_NOT_AUTHORIZED = "NOT_AUTHORIZED"
ERR_OWNERSHIP = "OWNERSHIP"
ERR_NOT_FOUND = "NOT_FOUND"
ERR_STATE_CONFLICT = "STATE_CONFLICT"
ERR_IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
ERR_STALE_CONFLICT = "STALE_CONFLICT"
ERR_INFRASTRUCTURE = "INFRASTRUCTURE"


class ManualExternalError(PaymentDomainError):
    """Raised for invalid MANUAL_EXTERNAL settlement operations.

    Carries a STABLE ``code`` (one of the ``ERR_*`` constants above) so HTTP callers can
    map to a status without parsing the human-readable message. ``code`` defaults to
    ``ERR_VALIDATION`` (the safe 400 default) when not specified.
    """

    def __init__(self, message, code=ERR_VALIDATION):
        super().__init__(message)
        self.code = code


class StaleSummaryConflict(ManualExternalError):
    """The REQUEST summary changed under us (stale revision / concurrent writer)."""

    def __init__(self, message, code=ERR_STALE_CONFLICT):
        super().__init__(message, code=code)


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
    except (PaymentDomainError, QuoteContractError) as exc:
        # normalize_stored_cents raises the quote-contract error type; normalize any
        # malformed-revision failure to ManualExternalError so no lower-level type leaks.
        raise ManualExternalError(
            f"invalid {PAYMENT_SUMMARY_REVISION_FIELD}: {raw!r} ({exc})"
        ) from exc


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
                               next_revision, expected_raw_status, expected_raw_paid):
    """Build the TransactWriteItems `Update` operand for the REQUEST summary.

    Conditional guard pins the exact payment state the settlement was computed from:
    the REQUEST exists, ``payment_summary_revision`` equals ``expected_revision`` (absent
    accepted as 0), the RAW persisted ``payment_status`` equals ``expected_raw_status``
    (``None`` -> attribute absent), and the RAW persisted ``amount_paid_cents`` equals
    ``expected_raw_paid`` (``None`` -> attribute absent). The raw values are the exact
    stored forms (e.g. lowercase ``paid`` from the legacy path), so a concurrent legacy
    writer that changes status/amount without bumping the revision still fails the
    transaction stale instead of being overwritten.
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

    # Concurrency guard: the REQUEST must exist, and the payment state this settlement
    # was computed from must be UNCHANGED at commit time. Besides the W3-C1 revision we
    # also pin the RAW persisted payment_status and amount_paid_cents, because the legacy
    # Stripe path mutates those WITHOUT incrementing payment_summary_revision — pinning
    # revision alone would let a concurrent legacy write be silently overwritten.
    conditions = ["attribute_exists(PK)"]

    # Revision guard (legacy/first-write records may omit the field -> logical 0).
    if expected_revision == 0:
        conditions.append("(attribute_not_exists(#rev) OR #rev = :exprev)")
    else:
        conditions.append("#rev = :exprev")

    # Raw-status guard. expected_raw_status is the UNNORMALIZED value read from the
    # REQUEST (e.g. lowercase "paid"/"payment_link_sent" from the legacy path), so the
    # condition compares against what is actually stored. Absent -> treat as "no status".
    names["#eps"] = "payment_status"
    if expected_raw_status is None:
        conditions.append("attribute_not_exists(#eps)")
    else:
        values[":eps"] = expected_raw_status
        conditions.append("#eps = :eps")

    # Raw paid-amount guard. Absent -> logical 0; a legacy record omitting the field must
    # not be overwritten if some other path has since written a nonzero value.
    names["#eap"] = "amount_paid_cents"
    if expected_raw_paid is None:
        conditions.append("attribute_not_exists(#eap)")
    else:
        values[":eap"] = expected_raw_paid
        conditions.append("#eap = :eap")

    return {
        "Update": {
            "Key": {"PK": request_pk(request_id), "SK": request_sk(client_id)},
            "UpdateExpression": "SET " + ", ".join(set_clauses),
            "ConditionExpression": " AND ".join(conditions),
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


def _resolve_table_and_name():
    """Return (low_level_client, table_name) for the low-level transaction.

    Prefers the authoritative Table-resource name over the environment variable. Fails
    clearly (ManualExternalError) if no table/name is configured — every low-level
    transaction operand requires a valid TableName.

    IMPORTANT (serialization boundary): the operands are **already** AttributeValue-encoded
    by ``_serialize_item`` (TypeSerializer). We therefore use a GENUINE bare low-level
    DynamoDB client (``boto3.client("dynamodb")``) rather than the resource's attached
    client (``resource.Table(...).meta.client``). The resource-attached client carries
    boto3's high-level DynamoDB attribute-value input transformer, which would serialize
    the already-serialized operands a SECOND time and raise ``TypeError: unhashable type:
    'dict'`` at the transaction call. The bare client performs no such transformation, so
    pre-serialized operands are sent exactly once. AWS configuration (region / endpoint) is
    copied from the existing resource client so the target is unchanged (incl. test/mocked
    or local-DynamoDB endpoints).
    """
    from common.db import table as _table
    if _table is None:
        raise ManualExternalError(
            "DynamoDB table resource is not configured", code=ERR_INFRASTRUCTURE
        )
    table_name = getattr(_table, "name", None)
    if not table_name:
        import os
        table_name = os.environ.get("DATA_TABLE_NAME")
    if not table_name:
        raise ManualExternalError(
            "DynamoDB table name is not configured", code=ERR_INFRASTRUCTURE
        )
    return _lowlevel_dynamodb_client(_table), table_name


def _lowlevel_dynamodb_client(table_resource):
    """Build a bare low-level DynamoDB client matching the resource's AWS config.

    Returns a ``boto3.client("dynamodb")`` configured with the SAME region and endpoint as
    the repository Table resource's attached client, but WITHOUT the resource's high-level
    attribute-value transformer. This is the correct partner for the adapter's explicit
    ``_serialize_item`` encoding (single serialization). If the resource meta cannot be
    introspected for any reason, fall back to a default-config client (same default
    resolver the resource itself uses).
    """
    import boto3
    try:
        src = table_resource.meta.client.meta
        region = src.region_name
        endpoint = src.endpoint_url
        return boto3.client("dynamodb", region_name=region, endpoint_url=endpoint)
    except Exception:  # noqa: BLE001 - config introspection fallback only
        return boto3.client("dynamodb")


def _serialize_item(mapping):
    """AttributeValue-encode a flat/native Python dict for the low-level DynamoDB API.

    Uses ``boto3.dynamodb.types.TypeSerializer`` so native values (str/int/Decimal/None/
    bool/list/dict) become the ``{"S":..}``/``{"N":..}``/``{"NULL":..}`` wire form the
    low-level ``transact_write_items`` requires. Centralized rather than hand-built.
    """
    from boto3.dynamodb.types import TypeSerializer
    ser = TypeSerializer()
    return {k: ser.serialize(v) for k, v in mapping.items()}


def _to_lowlevel_transact_items(event_item, summary_update, table_name):
    """Transform resource-style operands into low-level AttributeValue-encoded operands.

    Expressions stay as strings and ``ExpressionAttributeNames`` stay as normal string
    maps; only ``Item`` / ``Key`` / ``ExpressionAttributeValues`` are AttributeValue
    encoded. Both operands carry ``TableName``.
    """
    put = {
        "TableName": table_name,
        "Item": _serialize_item(event_item),
        "ConditionExpression": "attribute_not_exists(PK) AND attribute_not_exists(SK)",
    }
    upd_src = summary_update["Update"]
    update = {
        "TableName": table_name,
        "Key": _serialize_item(upd_src["Key"]),
        "UpdateExpression": upd_src["UpdateExpression"],
        "ConditionExpression": upd_src["ConditionExpression"],
        "ExpressionAttributeNames": dict(upd_src["ExpressionAttributeNames"]),
        "ExpressionAttributeValues": _serialize_item(upd_src["ExpressionAttributeValues"]),
    }
    return [{"Put": put}, {"Update": update}]


def _execute_transaction(event_item, summary_update):
    """Execute the two-item atomic transaction via the low-level DynamoDB client.

    Lazy client acquisition keeps imports clean and tests AWS-free. The operands are
    AttributeValue-encoded (TypeSerializer) because ``transact_write_items`` is the
    LOW-LEVEL API — native Python values would be rejected at runtime. Returns the
    serialized TransactItems on success (for assertions); raises the botocore ClientError
    on cancellation so the caller can classify.
    """
    client, table_name = _resolve_table_and_name()
    transact_items = _to_lowlevel_transact_items(event_item, summary_update, table_name)
    client.transact_write_items(TransactItems=transact_items)
    return transact_items


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
        raise ManualExternalError(
            "not authorized to record external payment", code=ERR_NOT_AUTHORIZED
        ) from exc

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
    try:
        delta = canonical_cents(amount_delta_cents)
    except PaymentDomainError as exc:
        # canonical_cents rejects negative / non-integral / bool / unparseable amounts with
        # a bare PaymentDomainError. That is caller-input invalidity: normalize it to a
        # coded ManualExternalError (400) so it never escapes uncoded (which an HTTP caller
        # would otherwise see as a 500).
        raise ManualExternalError(
            "amount_delta_cents must be a positive integer of cents",
            code=ERR_VALIDATION,
        ) from exc
    if delta <= 0:
        raise ManualExternalError(
            "amount_delta_cents must be a positive integer of cents", code=ERR_VALIDATION
        )
    if not currency:
        raise ManualExternalError("currency is required")
    method_category = validate_payment_method_category(payment_method_category)
    opaque_ref = validate_external_reference(external_reference)
    # Sanitized evidence metadata is computed from CURRENT inputs (before the replay
    # check) so it participates in idempotency-key binding — a caller cannot reuse a key
    # and silently change the method category / note.
    safe_metadata = sanitize_payment_event_metadata(
        {"payment_method_category": method_category, "note": note} if note is not None
        else {"payment_method_category": method_category}
    )

    # 4. Load + validate REQUEST ownership (fail closed; no write on mismatch).
    #    load_owned_request (W3-B shared domain, unchanged) fails CLOSED with a bare
    #    PaymentDomainError on ANY of: record missing, cross-tenant ownership mismatch, or
    #    client mismatch. We translate ALL of these to the SAME stable code (ERR_NOT_FOUND)
    #    so a caller can never distinguish "this request does not exist" from "this request
    #    exists but is not yours" — both yield one identical non-disclosing response at the
    #    HTTP layer, preventing cross-tenant request-existence enumeration. We deliberately
    #    do NOT probe the bare REQUEST key to classify the two cases: that would add an extra
    #    read and a TOCTOU race, and would only exist to produce a distinction we must never
    #    expose anyway. (Role/authorization denial is a separate, earlier ERR_NOT_AUTHORIZED
    #    path and is unaffected: it stays a 403 and is not request-scoped.)
    try:
        request_item = load_owned_request(request_id, client_id, company_id)
    except ManualExternalError:
        raise
    except PaymentDomainError as exc:
        raise ManualExternalError(
            "request not found or not accessible", code=ERR_NOT_FOUND
        ) from exc

    # 4a. Early idempotency pre-check: if a PAYMENT_EVENT already exists for this
    # (request, idempotency_key), this is a replay. A legitimately-applied prior
    # settlement may have driven the summary to a terminal state (e.g. PAID), so we must
    # classify the replay BEFORE the terminal-state guard rejects it. We short-circuit
    # ONLY on an exact match of the CURRENT normalized operation inputs against the stored
    # event (W3-C1 evidence-bound comparison — NOT a copy of the stored values). A
    # different payload under the same key is a conflict (no write). A brand-new key falls
    # through to normal processing; the conditional transaction remains the authoritative
    # idempotency guard against races between this pre-check and the write.
    from common.db import get_item as _get_item
    existing_evt = _get_item(request_pk(request_id), payment_event_sk(idempotency_key))
    if existing_evt:
        if _settlement_matches_stored_event(
            existing_evt,
            request_id=request_id, company_id=company_id, client_id=client_id,
            amount_delta_cents=delta, currency=currency, provider_txn_ref=opaque_ref,
            payment_method_category=method_category, metadata=safe_metadata,
        ):
            return _idempotent_replay_result(request_id, client_id, company_id, request_item)
        raise ManualExternalError(
            "idempotency_key reused with a different payment payload",
            code=ERR_IDEMPOTENCY_CONFLICT,
        )

    # 5. Read canonical current summary (both RAW persisted and normalized forms).
    raw_status = request_item.get("payment_status")      # exact stored form (may be lowercase)
    raw_paid = request_item.get("amount_paid_cents")     # exact stored form (may be absent)
    req = request_item.get("payment_requirement")
    if req not in (PaymentRequirement.DEPOSIT, PaymentRequirement.FULL):
        # NONE / unknown → no collection to record.
        raise ManualExternalError(
            f"request does not require collectible payment (payment_requirement={req!r})",
            code=ERR_STATE_CONFLICT,
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
        # Caller-supplied currency differs from the canonical request currency: this is a
        # bad-input validation error (400), not a state conflict.
        raise ManualExternalError(
            f"currency mismatch: operation {currency!r} != request {req_currency!r}",
            code=ERR_VALIDATION,
        )

    # 7. Reject settlement from terminal/illegal states up front (clear errors).
    if prev_status in (PaymentStatus.PAID, PaymentStatus.REFUNDED, PaymentStatus.NOT_REQUIRED):
        raise ManualExternalError(
            f"cannot record settlement from status {prev_status}",
            code=ERR_STATE_CONFLICT,
        )

    # 8. Compute new total + reject overpayment (W3-C1 does not model overpayment).
    new_amount_paid = existing_paid + delta
    if required_cents > 0 and new_amount_paid > required_cents:
        raise ManualExternalError(
            "amount_paid would exceed required total (overpayment not modeled in W3-C1)",
            code=ERR_STATE_CONFLICT,
        )

    # 9. Derive resulting status (never from the caller).
    resulting_status = derive_resulting_status(
        req, prev_status, new_amount_paid, required_cents, deposit_cents
    )

    # 10. Build immutable PAYMENT_EVENT (validates transition/provider/metadata/amount).
    event_type = (PaymentEventType.PAYMENT_SETTLED
                  if resulting_status == PaymentStatus.PAID
                  else PaymentEventType.PAYMENT_PARTIALLY_SETTLED)
    # safe_metadata was computed from current inputs at step 3 (evidence binding).
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

    # 11. Build the conditional summary update (pins revision + RAW status + RAW paid).
    expected_revision = _current_summary_revision(request_item)
    next_revision = expected_revision + 1
    summary_update = _build_summary_update_item(
        request_id, client_id, resulting_status, new_amount_paid, currency,
        payment_completed_at, expected_revision, next_revision,
        expected_raw_status=raw_status, expected_raw_paid=raw_paid,
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
            # Unexpected DynamoDB/transaction failure: server-side infrastructure problem.
            # The raw AWS error code is kept in logs (via the chained exception) but NOT in
            # the exception message, so it can never surface to an API caller.
            raise ManualExternalError(
                "payment transaction failed", code=ERR_INFRASTRUCTURE
            ) from exc
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
                "idempotency_key reused with a different payment payload",
                code=ERR_IDEMPOTENCY_CONFLICT,
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


def _event_method_category(event_item):
    """Extract the stored payment_method_category from an event's sanitized metadata."""
    md = event_item.get("metadata")
    if isinstance(md, dict):
        return md.get("payment_method_category")
    return None


def _settlement_matches_stored_event(stored_event, *, request_id, company_id, client_id,
                                     amount_delta_cents, currency, provider_txn_ref,
                                     payment_method_category, metadata):
    """W3-C1 evidence-bound idempotency comparison (CURRENT inputs vs stored event).

    Unlike a copy-of-stored comparison, every field below comes from the CURRENT
    normalized operation inputs, so reusing one idempotency key with any materially
    different settlement is detected as a conflict (not a false duplicate). Compared:
    request/company/client identity, provider (always MANUAL_EXTERNAL), amount delta
    (canonical cents), currency, opaque external reference, payment_method_category, and
    the full sanitized evidence metadata. ``note`` is covered because it lives inside the
    sanitized ``metadata`` that is compared in full.
    """
    try:
        cur_delta = canonical_cents(amount_delta_cents)
        stored_delta = canonical_cents(stored_event.get("amount_delta_cents"))
    except PaymentDomainError:
        return False

    if stored_event.get("payment_provider") != PaymentProvider.MANUAL_EXTERNAL:
        return False
    if stored_event.get("request_id") != request_id:
        return False
    if stored_event.get("company_id") != company_id:
        return False
    if stored_event.get("client_id") != client_id:
        return False
    if stored_delta != cur_delta:
        return False
    if (stored_event.get("currency") or DEFAULT_CURRENCY) != (currency or DEFAULT_CURRENCY):
        return False
    if stored_event.get("provider_txn_ref") != provider_txn_ref:
        return False
    if _event_method_category(stored_event) != payment_method_category:
        return False
    # Full sanitized evidence metadata must match (covers note + method category).
    if (stored_event.get("metadata") or None) != (metadata or None):
        return False
    return True


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
