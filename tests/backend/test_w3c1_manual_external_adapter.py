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
    from common.payment_domain import build_payment_event
    kw = dict(
        request_id="req-1", company_id="co-1",
        event_type="PAYMENT_SETTLED", idempotency_key="idem-1",
        previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
        client_id="cli-1", provider=PaymentProvider.MANUAL_EXTERNAL,
        amount_delta_cents=5000, currency="USD", provider_txn_ref=None,
        actor="manual_external:owner@example.com",
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
    # Event item keyed under REQUEST collection.
    assert put["Item"]["PK"] == "REQ#req-1"
    assert put["Item"]["SK"].startswith("PAYEVENT#")
    assert put["Item"]["payment_provider"] == "MANUAL_EXTERNAL"


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
    assert upd["ExpressionAttributeValues"][":exprev"] == 1


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
    assert put["Item"]["payment_provider"] == "MANUAL_EXTERNAL"


def test_no_target_status_input_accepted():
    # record_external_payment has no payment_status / resulting_status parameter.
    import inspect
    params = set(inspect.signature(mx.record_external_payment).parameters)
    assert "payment_status" not in params
    assert "resulting_status" not in params
    assert "company_id" not in params  # tenant is server-derived
