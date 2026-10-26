"""
W3-C1 — tests for the MANUAL_EXTERNAL payment settlement adapter
(`common.manual_external_adapter`).

Server-only, mock/local-data only. NO live AWS, NO Stripe, NO network, NO route/UI.
The DynamoDB transaction client and auth/tenant/ownership helpers are mocked.
"""

import ast
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

from botocore.exceptions import ClientError

from common.payment_domain import (
    PaymentStatus, PaymentRequirement, PaymentProvider, QuoteStatus,
    PaymentDomainError,
)
import common.manual_external_adapter as mx

# Shared-domain helpers (load_owned_request, canonical_cents, metadata sanitizer) raise
# the parent PaymentDomainError; adapter-originated errors raise ManualExternalError
# (a PaymentDomainError subclass). Use this alias where the rejection originates in a
# reused W3-B helper so the assertion matches either the parent or the subclass.
DomainReject = PaymentDomainError


# ---------------------------------------------------------------------------
# Test-isolation guard (autouse)
# ---------------------------------------------------------------------------
# `tests/backend/test_w3b_payment_domain.py` calls ``importlib.reload`` on
# ``common.payment_domain`` inside two of its coupling tests. A reload constructs a
# BRAND-NEW ``PaymentDomainError`` class object and rebinds it on the live module. When
# the full suite runs W3-B before W3-C1 (alphabetical collection order), our import-time
# alias ``DomainReject = PaymentDomainError`` is left pointing at the STALE pre-reload
# class, while the adapter (which imports the symbol lazily / by attribute) raises the
# POST-reload class. ``pytest.raises(DomainReject)`` then fails to match an exception that
# is, by identity, a different class — so the rejection-path assertions leak the very
# error they assert. This is pure cross-test state bleed, invisible in isolation.
#
# Fix (test-file-local only): before every test, re-resolve the exception classes from
# the currently-live modules and rebind the module globals used in assertions. This makes
# the W3-C1 assertions robust to any earlier reload of the shared domain module, without
# touching product code or any other test.
@pytest.fixture(autouse=True)
def _rebind_live_exception_classes():
    import importlib
    live_pd = importlib.import_module("common.payment_domain")
    live_mx = importlib.import_module("common.manual_external_adapter")
    g = globals()
    g["PaymentDomainError"] = live_pd.PaymentDomainError
    g["DomainReject"] = live_pd.PaymentDomainError
    # Keep the adapter alias (`mx`) and its error type pointing at the live objects too,
    # so `pytest.raises(mx.ManualExternalError)` matches the adapter-raised subclass.
    g["mx"] = live_mx
    yield


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _event():
    return {"requestContext": {"authorizer": {"claims": {
        "email": "owner@example.com", "cognito:groups": "owner",
        "custom:company_id": "co-1",
    }}}}


def _request(**over):
    base = {
        "PK": "REQ#req-1", "SK": "CLIENT#cli-1", "entity_type": "REQUEST",
        "company_id": "co-1", "client_id": "cli-1",
        "payment_requirement": PaymentRequirement.FULL,
        "payment_status": PaymentStatus.UNPAID,
        "amount_required_cents": 5000,
        "deposit_amount_cents": 0,
        "amount_paid_cents": 0,
        "currency": "USD",
        "quote_status": QuoteStatus.ACCEPTED,
    }
    base.update(over)
    return base


def _cond_failed():
    return ClientError(
        {"Error": {"Code": "TransactionCanceledException", "Message": "cancelled"}},
        "TransactWriteItems",
    )


class _FakeClient:
    """Captures transact_write_items calls; optionally raises."""
    def __init__(self, raise_exc=None):
        self.raise_exc = raise_exc
        self.calls = []

    def transact_write_items(self, **kwargs):
        self.calls.append(kwargs)
        if self.raise_exc:
            raise self.raise_exc


def _patched(adapter_request=None, get_item_side=None, raise_exc=None,
             role_ok=True, company="co-1"):
    """Return a contextmanager stack patching auth + db for the adapter."""
    fake_client = _FakeClient(raise_exc=raise_exc)
    fake_table = MagicMock()
    fake_table.name = "test-table"          # authoritative table-resource name
    fake_table.meta.client = fake_client

    patches = []
    # Authorization
    if role_ok:
        patches.append(patch("common.auth.require_owner_or_admin", return_value="owner"))
    else:
        patches.append(patch("common.auth.require_owner_or_admin",
                             side_effect=PermissionError("denied")))
    patches.append(patch("common.auth.get_current_company_id", return_value=company))
    patches.append(patch("common.auth.get_claims",
                         return_value={"email": "owner@example.com"}))
    # DB: load_owned_request uses common.db.get_item for the REQUEST (SK=CLIENT#...),
    # and the adapter's idempotency pre-check uses it for the PAYMENT_EVENT
    # (SK=PAYEVENT#...). The default (no explicit side) returns the REQUEST for the
    # CLIENT# key and None (no existing event) for the PAYEVENT# key.
    if get_item_side is not None:
        patches.append(patch("common.db.get_item", side_effect=get_item_side))
    else:
        def _default_get(pk, sk):
            if isinstance(sk, str) and sk.startswith("CLIENT#"):
                return adapter_request
            return None
        patches.append(patch("common.db.get_item", side_effect=_default_get))
    patches.append(patch("common.db.table", fake_table))
    patches.append(patch("common.auth.DEFAULT_COMPANY_ID", "tog_and_dogs"))
    return patches, fake_client


def _run(adapter_request=None, get_item_side=None, raise_exc=None, role_ok=True,
         company="co-1", **kwargs):
    patches, fake_client = _patched(adapter_request, get_item_side, raise_exc, role_ok, company)
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        out = mx.record_external_payment(**kwargs)
    return out, fake_client


_BASE_OP = dict(
    event=_event(), request_id="req-1", client_id="cli-1",
    amount_delta_cents=5000, currency="USD", idempotency_key="idem-1",
)


# ---------------------------------------------------------------------------
# No network / no route coupling
# ---------------------------------------------------------------------------

def test_adapter_has_no_stripe_or_route_imports():
    with open(mx.__file__, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(node.module.split(".")[0])
    for forbidden in ("stripe", "requests", "urllib", "http", "flask", "fastapi"):
        assert forbidden not in roots


def test_provider_is_manual_external_only():
    assert PaymentProvider.W3B_SUPPORTED == frozenset({"MANUAL_EXTERNAL"})


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

def test_owner_allowed():
    out, client = _run(adapter_request=_request(), **_BASE_OP)
    assert out["result"] == mx.RECORD_CREATED
    assert len(client.calls) == 1


def test_admin_allowed():
    # role_ok True simulates require_owner_or_admin passing (owner or admin).
    out, client = _run(adapter_request=_request(), **_BASE_OP)
    assert out["result"] == mx.RECORD_CREATED


def test_staff_denied_no_write():
    patches, client = _patched(adapter_request=_request(), role_ok=False)
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(mx.ManualExternalError):
            mx.record_external_payment(**_BASE_OP)
    assert client.calls == []


def test_client_denied_no_write():
    # Same mechanism: require_owner_or_admin raises for a client caller.
    patches, client = _patched(adapter_request=_request(), role_ok=False)
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(mx.ManualExternalError):
            mx.record_external_payment(**_BASE_OP)
    assert client.calls == []


# ---------------------------------------------------------------------------
# Tenant / request ownership
# ---------------------------------------------------------------------------

def test_wrong_tenant_rejected_no_write():
    # REQUEST belongs to co-1 but trusted caller company is attacker.
    patches, client = _patched(adapter_request=_request(), company="attacker-co")
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(DomainReject):
            mx.record_external_payment(**_BASE_OP)
    assert client.calls == []


def test_missing_request_rejected_no_write():
    patches, client = _patched(adapter_request=None)
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(DomainReject):
            mx.record_external_payment(**_BASE_OP)
    assert client.calls == []


def test_wrong_client_association_rejected_no_write():
    patches, client = _patched(adapter_request=_request(client_id="other-client"))
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(DomainReject):
            mx.record_external_payment(**_BASE_OP)
    assert client.calls == []


# ---------------------------------------------------------------------------
# Money / canonical cents
# ---------------------------------------------------------------------------

def test_canonical_int_cents_full_paid():
    out, _ = _run(adapter_request=_request(), **_BASE_OP)
    assert out["amount_paid_cents"] == 5000
    assert out["resulting_status"] == PaymentStatus.PAID


def test_decimal_cents_not_inflated():
    op = dict(_BASE_OP, amount_delta_cents=Decimal("5000"))
    out, _ = _run(adapter_request=_request(amount_required_cents=Decimal("5000")), **op)
    assert out["amount_paid_cents"] == 5000  # not 500000


def test_zero_delta_rejected():
    op = dict(_BASE_OP, amount_delta_cents=0)
    patches, client = _patched(adapter_request=_request())
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(mx.ManualExternalError):
            mx.record_external_payment(**op)
    assert client.calls == []


def test_negative_delta_rejected():
    op = dict(_BASE_OP, amount_delta_cents=-100)
    patches, client = _patched(adapter_request=_request())
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(DomainReject):
            mx.record_external_payment(**op)
    assert client.calls == []


def test_non_integral_delta_rejected():
    op = dict(_BASE_OP, amount_delta_cents=Decimal("50.5"))
    patches, client = _patched(adapter_request=_request())
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(DomainReject):
            mx.record_external_payment(**op)
    assert client.calls == []


def test_currency_mismatch_rejected():
    op = dict(_BASE_OP, currency="EUR")
    patches, client = _patched(adapter_request=_request(currency="USD"))
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(mx.ManualExternalError):
            mx.record_external_payment(**op)
    assert client.calls == []


def test_overpayment_rejected():
    op = dict(_BASE_OP, amount_delta_cents=5001)
    patches, client = _patched(adapter_request=_request(amount_required_cents=5000))
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(mx.ManualExternalError):
            mx.record_external_payment(**op)
    assert client.calls == []


# ---------------------------------------------------------------------------
# FULL payment derivation
# ---------------------------------------------------------------------------

def test_full_partial_then_balance():
    # Partial first.
    op1 = dict(_BASE_OP, amount_delta_cents=2500, idempotency_key="k1")
    out1, _ = _run(adapter_request=_request(amount_required_cents=5000), **op1)
    assert out1["resulting_status"] == PaymentStatus.PARTIALLY_PAID
    assert out1["payment_completed_at"] is None
    # Balance (existing paid 2500 already on record).
    op2 = dict(_BASE_OP, amount_delta_cents=2500, idempotency_key="k2")
    out2, _ = _run(adapter_request=_request(amount_required_cents=5000,
                                            amount_paid_cents=2500,
                                            payment_status=PaymentStatus.PARTIALLY_PAID),
                   **op2)
    assert out2["resulting_status"] == PaymentStatus.PAID
    assert out2["payment_completed_at"] is not None


def test_full_exact_paid():
    out, _ = _run(adapter_request=_request(amount_required_cents=5000), **_BASE_OP)
    assert out["resulting_status"] == PaymentStatus.PAID


# ---------------------------------------------------------------------------
# DEPOSIT payment derivation + partial reconciliation
# ---------------------------------------------------------------------------

def test_deposit_below_threshold_is_partially_paid_not_unpaid():
    # Reconciliation: any recorded positive payment -> PARTIALLY_PAID, never UNPAID.
    op = dict(_BASE_OP, amount_delta_cents=1000, idempotency_key="dk")
    out, _ = _run(adapter_request=_request(
        payment_requirement=PaymentRequirement.DEPOSIT,
        amount_required_cents=10000, deposit_amount_cents=3000, amount_paid_cents=0,
    ), **op)
    assert out["resulting_status"] == PaymentStatus.PARTIALLY_PAID


def test_deposit_exact_threshold_partially_paid():
    op = dict(_BASE_OP, amount_delta_cents=3000, idempotency_key="dk2")
    out, _ = _run(adapter_request=_request(
        payment_requirement=PaymentRequirement.DEPOSIT,
        amount_required_cents=10000, deposit_amount_cents=3000, amount_paid_cents=0,
    ), **op)
    assert out["resulting_status"] == PaymentStatus.PARTIALLY_PAID


def test_deposit_above_deposit_below_total_partially_paid():
    op = dict(_BASE_OP, amount_delta_cents=5000, idempotency_key="dk3")
    out, _ = _run(adapter_request=_request(
        payment_requirement=PaymentRequirement.DEPOSIT,
        amount_required_cents=10000, deposit_amount_cents=3000, amount_paid_cents=0,
    ), **op)
    assert out["resulting_status"] == PaymentStatus.PARTIALLY_PAID


def test_deposit_full_total_paid():
    op = dict(_BASE_OP, amount_delta_cents=10000, idempotency_key="dk4")
    out, _ = _run(adapter_request=_request(
        payment_requirement=PaymentRequirement.DEPOSIT,
        amount_required_cents=10000, deposit_amount_cents=3000, amount_paid_cents=0,
    ), **op)
    assert out["resulting_status"] == PaymentStatus.PAID


# ---------------------------------------------------------------------------
# Status guards
# ---------------------------------------------------------------------------

def test_none_requirement_rejected():
    patches, client = _patched(adapter_request=_request(
        payment_requirement=PaymentRequirement.NONE, amount_required_cents=0,
        payment_status=PaymentStatus.NOT_REQUIRED))
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(mx.ManualExternalError):
            mx.record_external_payment(**_BASE_OP)
    assert client.calls == []


def test_paid_rejects_further_payment():
    patches, client = _patched(adapter_request=_request(
        payment_status=PaymentStatus.PAID, amount_paid_cents=5000))
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(mx.ManualExternalError):
            mx.record_external_payment(**_BASE_OP)
    assert client.calls == []


def test_refunded_rejects_settlement():
    patches, client = _patched(adapter_request=_request(
        payment_status=PaymentStatus.REFUNDED))
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(mx.ManualExternalError):
            mx.record_external_payment(**_BASE_OP)
    assert client.calls == []


def test_payment_link_sent_can_settle():
    out, _ = _run(adapter_request=_request(payment_status=PaymentStatus.PAYMENT_LINK_SENT),
                  **_BASE_OP)
    assert out["resulting_status"] == PaymentStatus.PAID


# ---------------------------------------------------------------------------
# payment_completed_at
# ---------------------------------------------------------------------------

def test_completed_at_absent_on_partial():
    op = dict(_BASE_OP, amount_delta_cents=2500)
    out, _ = _run(adapter_request=_request(amount_required_cents=5000), **op)
    assert out["payment_completed_at"] is None


def test_completed_at_set_on_paid():
    out, _ = _run(adapter_request=_request(amount_required_cents=5000), **_BASE_OP)
    assert out["payment_completed_at"] is not None


# ---------------------------------------------------------------------------
# Idempotency / transaction-cancellation classification
# ---------------------------------------------------------------------------

def _existing_event(**over):
    from common.payment_domain import build_payment_event, sanitize_payment_event_metadata
    # Default metadata matches what _BASE_OP (no external_reference, no method category)
    # produces: {"payment_method_category": "OTHER"}, so an exact replay binds.
    md = over.pop("metadata", sanitize_payment_event_metadata({"payment_method_category": "OTHER"}))
    kw = dict(
        request_id="req-1", company_id="co-1",
        event_type="PAYMENT_SETTLED", idempotency_key="idem-1",
        previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
        client_id="cli-1", provider=PaymentProvider.MANUAL_EXTERNAL,
        amount_delta_cents=5000, currency="USD", provider_txn_ref=None,
        actor="manual_external:owner@example.com", metadata=md,
    )
    kw.update(over)
    return build_payment_event(**kw)


def test_duplicate_same_event_idempotent_no_reapply():
    existing_evt = _existing_event()
    paid_request = _request(payment_status=PaymentStatus.PAID, amount_paid_cents=5000,
                            payment_summary_revision=1, payment_completed_at="2026-10-23T10:00:00Z")

    def get_side(pk, sk):
        if sk.startswith("CLIENT#"):
            return paid_request
        if sk.startswith("PAYEVENT#"):
            return existing_evt
        return None

    out, client = _run(get_item_side=get_side, raise_exc=_cond_failed(), **_BASE_OP)
    assert out["result"] == mx.RECORD_DUPLICATE_SAME_EVENT
    # Money NOT reapplied; revision not bumped beyond the committed 1.
    assert out["amount_paid_cents"] == 5000
    assert out["payment_summary_revision"] == 1
    assert out["payment_completed_at"] == "2026-10-23T10:00:00Z"


def test_conflicting_idempotency_key_no_write():
    conflicting = _existing_event(amount_delta_cents=9999, provider_txn_ref="DIFF")

    def get_side(pk, sk):
        if sk.startswith("CLIENT#"):
            return _request()
        if sk.startswith("PAYEVENT#"):
            return conflicting
        return None

    patches, client = _patched(get_item_side=get_side, raise_exc=_cond_failed())
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(mx.ManualExternalError):
            mx.record_external_payment(**_BASE_OP)


def test_stale_summary_conflict_no_event():
    def get_side(pk, sk):
        if sk.startswith("CLIENT#"):
            return _request()
        return None  # no PAYMENT_EVENT exists

    patches, client = _patched(get_item_side=get_side, raise_exc=_cond_failed())
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(mx.StaleSummaryConflict):
            mx.record_external_payment(**_BASE_OP)


# ---------------------------------------------------------------------------
# Transaction contract: two conditional items
# ---------------------------------------------------------------------------

def test_transaction_has_two_conditional_items():
    out, client = _run(adapter_request=_request(), **_BASE_OP)
    assert len(client.calls) == 1
    items = client.calls[0]["TransactItems"]
    assert len(items) == 2
    put = next(i for i in items if "Put" in i)["Put"]
    upd = next(i for i in items if "Update" in i)["Update"]
    assert put["ConditionExpression"] == "attribute_not_exists(PK) AND attribute_not_exists(SK)"
    assert "attribute_exists(PK)" in upd["ConditionExpression"]
    # Low-level AttributeValue-encoded Item keyed under REQUEST collection.
    assert put["Item"]["PK"] == {"S": "REQ#req-1"}
    assert put["Item"]["SK"]["S"].startswith("PAYEVENT#")
    assert put["Item"]["payment_provider"] == {"S": "MANUAL_EXTERNAL"}


def test_revision_zero_guard_allows_absent_field():
    out, client = _run(adapter_request=_request(), **_BASE_OP)  # no revision field => 0
    upd = next(i for i in client.calls[0]["TransactItems"] if "Update" in i)["Update"]
    assert "attribute_not_exists(#rev)" in upd["ConditionExpression"]
    assert out["payment_summary_revision"] == 1


def test_revision_increment_from_existing():
    out, client = _run(adapter_request=_request(
        amount_required_cents=5000, amount_paid_cents=2500,
        payment_status=PaymentStatus.PARTIALLY_PAID, payment_summary_revision=1),
        event=_event(), request_id="req-1", client_id="cli-1",
        amount_delta_cents=2500, currency="USD", idempotency_key="k9")
    assert out["payment_summary_revision"] == 2
    upd = next(i for i in client.calls[0]["TransactItems"] if "Update" in i)["Update"]
    assert upd["ExpressionAttributeValues"][":exprev"] == {"N": "1"}


# ---------------------------------------------------------------------------
# Evidence model
# ---------------------------------------------------------------------------

def test_method_category_validation():
    assert mx.validate_payment_method_category(None) == "OTHER"
    assert mx.validate_payment_method_category("CHECK") == "CHECK"
    with pytest.raises(mx.ManualExternalError):
        mx.validate_payment_method_category("BITCOIN")


def test_external_reference_opaque_ok():
    assert mx.validate_external_reference("CHECK-10482") == "CHECK-10482"
    assert mx.validate_external_reference(None) is None


def test_external_reference_rejects_account_like_number():
    with pytest.raises(mx.ManualExternalError):
        mx.validate_external_reference("4111111111111111")  # PAN-like


def test_note_sensitive_metadata_rejected():
    # The note is sanitized; a dict-y sensitive structure is not a plain note, but the
    # adapter wraps note under metadata -> sensitive content must be rejected upstream.
    # Here we assert the sanitizer path rejects a sensitive provider payload reference.
    op = dict(_BASE_OP, note={"access_token": "leak"})
    patches, client = _patched(adapter_request=_request())
    import contextlib
    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with pytest.raises(DomainReject):
            mx.record_external_payment(**op)
    assert client.calls == []


# ---------------------------------------------------------------------------
# Booking readiness + no auto-approval
# ---------------------------------------------------------------------------

def test_booking_ready_informational_on_full_paid():
    out, client = _run(adapter_request=_request(amount_required_cents=5000,
                                                quote_status=QuoteStatus.ACCEPTED),
                       **_BASE_OP)
    assert out["booking_ready"] is True
    # No extra writes beyond the single transaction (no JOB/approval/schedule).
    assert len(client.calls) == 1


def test_booking_not_ready_when_partial():
    op = dict(_BASE_OP, amount_delta_cents=2500)
    out, _ = _run(adapter_request=_request(amount_required_cents=5000), **op)
    assert out["booking_ready"] is False


def test_provider_always_manual_external():
    out, client = _run(adapter_request=_request(), **_BASE_OP)
    assert out["payment_provider"] == PaymentProvider.MANUAL_EXTERNAL
    put = next(i for i in client.calls[0]["TransactItems"] if "Put" in i)["Put"]
    assert put["Item"]["payment_provider"] == {"S": "MANUAL_EXTERNAL"}


def test_no_target_status_input_accepted():
    # record_external_payment has no payment_status / resulting_status parameter.
    import inspect
    params = set(inspect.signature(mx.record_external_payment).parameters)
    assert "payment_status" not in params
    assert "resulting_status" not in params
    assert "company_id" not in params  # tenant is server-derived


# ===========================================================================
# W3-C1 HARDENING COVERAGE (PR #31 review)
# ===========================================================================

# ---------------------------------------------------------------------------
# Low-level DynamoDB TransactWriteItems SDK shape (AttributeValue encoding).
# ---------------------------------------------------------------------------

def _transact_items(client):
    return client.calls[0]["TransactItems"]


def test_lowlevel_put_item_attributevalue_encoded():
    _, client = _run(adapter_request=_request(), **_BASE_OP)
    put = next(i for i in _transact_items(client) if "Put" in i)["Put"]
    item = put["Item"]
    # Every value is an AttributeValue wrapper, not a native Python value.
    assert item["PK"] == {"S": "REQ#req-1"}
    assert item["entity_type"] == {"S": "PAYMENT_EVENT"}
    assert item["amount_delta_cents"] == {"N": "5000"}
    for k, v in item.items():
        assert isinstance(v, dict) and len(v) == 1, f"{k} not AttributeValue-encoded: {v!r}"
        assert next(iter(v)) in {"S", "N", "BOOL", "NULL", "L", "M", "SS", "NS", "B"}


def test_lowlevel_update_key_and_values_encoded_names_plain():
    _, client = _run(adapter_request=_request(), **_BASE_OP)
    upd = next(i for i in _transact_items(client) if "Update" in i)["Update"]
    # Key AttributeValue-encoded.
    assert upd["Key"]["PK"] == {"S": "REQ#req-1"}
    assert upd["Key"]["SK"] == {"S": "CLIENT#cli-1"}
    # ExpressionAttributeValues AttributeValue-encoded.
    for k, v in upd["ExpressionAttributeValues"].items():
        assert isinstance(v, dict) and len(v) == 1, f"{k} not encoded: {v!r}"
    assert upd["ExpressionAttributeValues"][":rev"] == {"N": "1"}
    assert upd["ExpressionAttributeValues"][":ps"] == {"S": PaymentStatus.PAID}
    # ExpressionAttributeNames remain plain string maps (NOT encoded).
    for k, v in upd["ExpressionAttributeNames"].items():
        assert isinstance(v, str)
    # UpdateExpression / ConditionExpression remain strings.
    assert isinstance(upd["UpdateExpression"], str)
    assert isinstance(upd["ConditionExpression"], str)


def test_lowlevel_both_operands_carry_table_name():
    _, client = _run(adapter_request=_request(), **_BASE_OP)
    items = _transact_items(client)
    put = next(i for i in items if "Put" in i)["Put"]
    upd = next(i for i in items if "Update" in i)["Update"]
    assert put["TableName"] == "test-table"
    assert upd["TableName"] == "test-table"


def test_serializer_rejects_nothing_valid_and_round_trips():
    # The serializer helper is exercised directly for a representative item.
    from boto3.dynamodb.types import TypeDeserializer
    enc = mx._serialize_item({"PK": "REQ#x", "n": 42, "none": None, "flag": True})
    deser = TypeDeserializer()
    back = {k: deser.deserialize(v) for k, v in enc.items()}
    assert back["PK"] == "REQ#x"
    assert int(back["n"]) == 42
    assert back["none"] is None
    assert back["flag"] is True


def test_table_name_missing_raises_clear_error():
    import contextlib
    fake_client = _FakeClient()
    fake_table = MagicMock()
    fake_table.name = None
    fake_table.meta.client = fake_client
    with patch("common.db.table", fake_table), \
         patch.dict("os.environ", {}, clear=False):
        import os
        old = os.environ.pop("DATA_TABLE_NAME", None)
        try:
            with pytest.raises(mx.ManualExternalError):
                mx._resolve_table_and_name()
        finally:
            if old is not None:
                os.environ["DATA_TABLE_NAME"] = old


# ---------------------------------------------------------------------------
# Idempotency evidence binding (current inputs, not copied-from-stored).
# ---------------------------------------------------------------------------

def _stored_event_for_replay(**over):
    from common.payment_domain import build_payment_event, sanitize_payment_event_metadata
    md = sanitize_payment_event_metadata({"payment_method_category": over.pop("method", "CHECK")})
    kw = dict(
        request_id="req-1", company_id="co-1",
        event_type="PAYMENT_SETTLED", idempotency_key="idem-1",
        previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
        client_id="cli-1", provider=PaymentProvider.MANUAL_EXTERNAL,
        amount_delta_cents=5000, currency="USD", provider_txn_ref="CHECK-100",
        actor="manual_external:owner@example.com", metadata=md,
    )
    kw.update(over)
    return build_payment_event(**kw)


def _replay_run(stored_event, paid_request, **op_over):
    def get_side(pk, sk):
        if sk.startswith("CLIENT#"):
            return paid_request
        if sk.startswith("PAYEVENT#"):
            return stored_event
        return None
    op = dict(_BASE_OP, external_reference="CHECK-100", payment_method_category="CHECK")
    op.update(op_over)
    return _run(get_item_side=get_side, raise_exc=_cond_failed(), **op)


_PAID_REQ = dict(
    PK="REQ#req-1", SK="CLIENT#cli-1", entity_type="REQUEST",
    company_id="co-1", client_id="cli-1",
    payment_requirement=PaymentRequirement.FULL, payment_status=PaymentStatus.PAID,
    amount_required_cents=5000, deposit_amount_cents=0, amount_paid_cents=5000,
    currency="USD", quote_status=QuoteStatus.ACCEPTED, payment_summary_revision=1,
    payment_completed_at="2026-10-23T10:00:00Z",
)


def test_replay_identical_is_duplicate():
    stored = _stored_event_for_replay()
    out, client = _replay_run(stored, dict(_PAID_REQ))
    assert out["result"] == mx.RECORD_DUPLICATE_SAME_EVENT
    assert out["amount_paid_cents"] == 5000
    assert out["payment_summary_revision"] == 1
    assert client.calls == []  # no transaction attempted on exact replay


def test_replay_different_amount_is_conflict():
    stored = _stored_event_for_replay(amount_delta_cents=5000)
    patches, client = _patched()
    # Different current amount under same key.
    with pytest.raises(mx.ManualExternalError):
        _replay_run(stored, dict(_PAID_REQ), amount_delta_cents=2500)


def test_replay_different_external_reference_is_conflict():
    stored = _stored_event_for_replay(provider_txn_ref="CHECK-100")
    with pytest.raises(mx.ManualExternalError):
        _replay_run(stored, dict(_PAID_REQ), external_reference="CHECK-999")


def test_replay_different_method_category_is_conflict():
    stored = _stored_event_for_replay(method="CHECK")
    with pytest.raises(mx.ManualExternalError):
        _replay_run(stored, dict(_PAID_REQ), payment_method_category="CASH")


def test_replay_different_note_metadata_is_conflict():
    from common.payment_domain import build_payment_event, sanitize_payment_event_metadata
    md = sanitize_payment_event_metadata({"payment_method_category": "CHECK", "note": "first"})
    stored = build_payment_event(
        request_id="req-1", company_id="co-1", event_type="PAYMENT_SETTLED",
        idempotency_key="idem-1", previous_status=PaymentStatus.UNPAID,
        resulting_status=PaymentStatus.PAID, client_id="cli-1",
        provider=PaymentProvider.MANUAL_EXTERNAL, amount_delta_cents=5000, currency="USD",
        provider_txn_ref="CHECK-100", actor="x", metadata=md,
    )
    with pytest.raises(mx.ManualExternalError):
        _replay_run(stored, dict(_PAID_REQ), note="second")


# ---------------------------------------------------------------------------
# Legacy concurrency guard: raw status + raw paid pinned in the condition.
# ---------------------------------------------------------------------------

def test_guard_pins_raw_status_and_paid():
    # Legacy lowercase stored status must be pinned RAW in the condition values.
    # required 10000, existing paid 1000, delta 5000 -> 6000 (< total, no overpayment).
    _, client = _run(adapter_request=_request(
        payment_status="payment_link_sent", amount_paid_cents=1000,
        amount_required_cents=10000), **_BASE_OP)
    upd = next(i for i in _transact_items(client) if "Update" in i)["Update"]
    vals = upd["ExpressionAttributeValues"]
    # Raw (lowercase) status pinned, not the normalized uppercase.
    assert vals[":eps"] == {"S": "payment_link_sent"}
    assert vals[":eap"] == {"N": "1000"}
    cond = upd["ConditionExpression"]
    assert "#eps = :eps" in cond
    assert "#eap = :eap" in cond


def test_guard_absent_paid_uses_attribute_not_exists():
    # A settleable record (UNPAID) with no amount_paid_cents field present -> logical 0,
    # guarded via attribute_not_exists so a concurrently-added nonzero value is not lost.
    req = _request(amount_required_cents=5000, payment_status=PaymentStatus.UNPAID)
    req.pop("amount_paid_cents", None)
    _, client = _run(adapter_request=req, **_BASE_OP)
    upd = next(i for i in _transact_items(client) if "Update" in i)["Update"]
    cond = upd["ConditionExpression"]
    assert "attribute_not_exists(#eap)" in cond
    assert ":eap" not in upd["ExpressionAttributeValues"]
    # Status is present (UNPAID) so it is pinned by value.
    assert upd["ExpressionAttributeValues"][":eps"] == {"S": PaymentStatus.UNPAID}


def test_guard_revision_pinned_with_status_and_paid():
    _, client = _run(adapter_request=_request(
        amount_required_cents=5000, amount_paid_cents=2500,
        payment_status=PaymentStatus.PARTIALLY_PAID, payment_summary_revision=1),
        event=_event(), request_id="req-1", client_id="cli-1",
        amount_delta_cents=2500, currency="USD", idempotency_key="k10")
    upd = next(i for i in _transact_items(client) if "Update" in i)["Update"]
    cond = upd["ConditionExpression"]
    assert "#rev = :exprev" in cond
    assert "#eps = :eps" in cond
    assert "#eap = :eap" in cond
    vals = upd["ExpressionAttributeValues"]
    assert vals[":exprev"] == {"N": "1"}
    assert vals[":eps"] == {"S": PaymentStatus.PARTIALLY_PAID}
    assert vals[":eap"] == {"N": "2500"}


# ---------------------------------------------------------------------------
# Malformed revision normalization.
# ---------------------------------------------------------------------------

def test_malformed_revision_raises_manual_external_error():
    with pytest.raises(mx.ManualExternalError):
        mx._current_summary_revision({"payment_summary_revision": "not-a-number"})


def test_fractional_revision_raises_manual_external_error():
    from decimal import Decimal
    with pytest.raises(mx.ManualExternalError):
        mx._current_summary_revision({"payment_summary_revision": Decimal("1.5")})


# ---------------------------------------------------------------------------
# Post-commit supplementary audit (EXTERNAL_PAYMENT_RECORDED).
# ---------------------------------------------------------------------------
# The adapter writes a supplementary AUDIT# entry AFTER the authoritative two-item
# transaction commits, and ONLY on a freshly-created settlement (result == RECORD_CREATED).
# It imports common.audit.log_action lazily inside the function, so patching
# "common.audit.log_action" intercepts the real call. The audit write is non-authoritative:
# a failure must NOT roll back, re-apply money, bump the revision, or fail the operation.

def test_audit_entry_written_on_created():
    # On a successful RECORD_CREATED settlement, exactly one EXTERNAL_PAYMENT_RECORDED audit
    # call is made, carrying the REQUEST identity and the previous/new status.
    with patch("common.audit.log_action") as audit:
        out, client = _run(adapter_request=_request(), **_BASE_OP)
    assert out["result"] == mx.RECORD_CREATED
    # Exactly one authoritative transaction, and exactly one supplementary audit call.
    assert len(client.calls) == 1
    audit.assert_called_once()
    args, kwargs = audit.call_args
    # Positional contract: (event, action, target_pk).
    assert args[1] == "EXTERNAL_PAYMENT_RECORDED"
    assert args[2] == "REQ#req-1"
    # Request identity + status metadata.
    assert kwargs["target_sk"] == "CLIENT#cli-1"
    assert kwargs["previous_status"] == PaymentStatus.UNPAID
    assert kwargs["new_status"] == PaymentStatus.PAID


def test_audit_failure_is_non_fatal():
    # A supplementary audit failure must not fail the already-committed settlement, must not
    # re-apply money, and must not bump the revision. The single payment transaction stands.
    with patch("common.audit.log_action", side_effect=RuntimeError("audit sink down")) as audit:
        out, client = _run(adapter_request=_request(), **_BASE_OP)
    # The audit path was actually reached (so the raised side_effect genuinely exercised
    # the non-fatal handling, rather than the test passing vacuously because audit was
    # never called).
    audit.assert_called_once()
    # Settlement still reports success with the committed state.
    assert out["result"] == mx.RECORD_CREATED
    assert out["resulting_status"] == PaymentStatus.PAID
    assert out["amount_paid_cents"] == 5000
    # Exactly one transaction attempted (no retry/second apply) and revision committed once.
    assert len(client.calls) == 1
    assert out["payment_summary_revision"] == 1


def test_audit_not_written_on_duplicate_replay():
    # An idempotent duplicate (same event already committed) returns RECORD_DUPLICATE_SAME_EVENT
    # and must NOT emit another audit event (audit fires only on RECORD_CREATED).
    existing_evt = _existing_event()
    paid_request = _request(payment_status=PaymentStatus.PAID, amount_paid_cents=5000,
                            payment_summary_revision=1,
                            payment_completed_at="2026-10-23T10:00:00Z")

    def get_side(pk, sk):
        if sk.startswith("CLIENT#"):
            return paid_request
        if sk.startswith("PAYEVENT#"):
            return existing_evt
        return None

    with patch("common.audit.log_action") as audit:
        out, client = _run(get_item_side=get_side, raise_exc=_cond_failed(), **_BASE_OP)
    assert out["result"] == mx.RECORD_DUPLICATE_SAME_EVENT
    # No new money applied and, critically, no supplementary audit event for a replay.
    assert out["amount_paid_cents"] == 5000
    audit.assert_not_called()
