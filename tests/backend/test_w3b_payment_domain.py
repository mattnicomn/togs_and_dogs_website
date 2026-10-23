"""
W3-B — tests for the provider-neutral payment domain (`common.payment_domain`).

Pure, provider-neutral, mock/local-data only. NO Stripe API, NO network, NO secrets,
NO deploy. These tests assert the canonical domain behaviors selected under W3 Option D:
status normalization, the payment state machine, amount invariants, provider
abstraction, amount-aware booking readiness, the hybrid REQUEST-summary + append-only
PAYMENT_EVENT model (deterministic idempotent SK keying, forbidden-metadata rejection),
the MANUAL_EXTERNAL boundary, and legacy/live payment-status compatibility.
"""

import importlib

import pytest

from common.quote_contract import (
    PaymentRequirement,
    PaymentStatus,
    QuoteStatus,
    DEFAULT_CURRENCY,
)
import common.payment_domain as pd


# ---------------------------------------------------------------------------
# Hard boundary: the domain module imports NO Stripe / network coupling.
# ---------------------------------------------------------------------------

def test_domain_module_has_no_stripe_or_network_coupling():
    """The provider-neutral domain must not IMPORT Stripe/HTTP/DB at the code level.

    We parse the module's AST and inspect only real ``import`` / ``from ... import``
    statements (prose in the module docstring deliberately *names* the forbidden
    coupling to document what it avoids, so a plain substring scan would false-positive).
    """
    import ast

    # Import (re)loads cleanly.
    importlib.reload(pd)
    with open(pd.__file__, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    forbidden_roots = {"stripe", "requests", "urllib", "http", "boto3", "botocore"}
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_roots.add(node.module.split(".")[0])

    leaked = forbidden_roots & imported_roots
    assert not leaked, f"provider-neutral domain must not import {sorted(leaked)}"
    # No stripe module object is referenced via this module.
    assert not hasattr(pd, "stripe")


def test_reused_canonical_enums_are_shared_not_redefined():
    """W3-B reuses quote_contract enums rather than defining competing ones."""
    assert pd.PaymentStatus is PaymentStatus
    assert pd.PaymentRequirement is PaymentRequirement
    assert pd.QuoteStatus is QuoteStatus
    assert pd.DEFAULT_CURRENCY == DEFAULT_CURRENCY


# ---------------------------------------------------------------------------
# PAYMENT_STATUS_SET — exactly the existing six canonical values.
# ---------------------------------------------------------------------------

def test_payment_status_set_is_exactly_the_canonical_six():
    assert pd.PAYMENT_STATUS_SET == frozenset({
        PaymentStatus.NOT_REQUIRED,
        PaymentStatus.UNPAID,
        PaymentStatus.PAYMENT_LINK_SENT,
        PaymentStatus.PARTIALLY_PAID,
        PaymentStatus.PAID,
        PaymentStatus.REFUNDED,
    })
    # No speculative statuses were introduced.
    for banned in ("PENDING", "FAILED", "PARTIALLY_REFUNDED"):
        assert banned not in pd.PAYMENT_STATUS_SET


# ---------------------------------------------------------------------------
# normalize_payment_status
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", sorted(pd.PAYMENT_STATUS_SET))
def test_normalize_canonical_passthrough(value):
    assert pd.normalize_payment_status(value) == value


@pytest.mark.parametrize("raw,expected", [
    ("paid", PaymentStatus.PAID),
    ("PAID", PaymentStatus.PAID),
    ("payment_link_sent", PaymentStatus.PAYMENT_LINK_SENT),
    ("unpaid", PaymentStatus.UNPAID),
    ("partially_paid", PaymentStatus.PARTIALLY_PAID),
    ("refunded", PaymentStatus.REFUNDED),
    ("not_required", PaymentStatus.NOT_REQUIRED),
])
def test_normalize_lowercase_and_live_values(raw, expected):
    """Lowercase values written by the current deployed Stripe path normalize up."""
    assert pd.normalize_payment_status(raw) == expected


@pytest.mark.parametrize("missing", [None, ""])
def test_normalize_missing_is_not_required(missing):
    assert pd.normalize_payment_status(missing) == PaymentStatus.NOT_REQUIRED


@pytest.mark.parametrize("junk", ["bogus", "APPROVED", "charged", "succeeded", "weird"])
def test_normalize_unknown_is_unknown_never_paid(junk):
    """An unrecognized status must fail safe: never PAID, never NOT_REQUIRED."""
    result = pd.normalize_payment_status(junk)
    assert result == pd.PAYMENT_STATUS_UNKNOWN
    assert result != PaymentStatus.PAID
    assert result != PaymentStatus.NOT_REQUIRED


# ---------------------------------------------------------------------------
# State machine — permitted / illegal / backward / terminal.
# ---------------------------------------------------------------------------

_PERMITTED = [
    (PaymentStatus.UNPAID, PaymentStatus.PAYMENT_LINK_SENT),
    (PaymentStatus.UNPAID, PaymentStatus.PARTIALLY_PAID),
    (PaymentStatus.UNPAID, PaymentStatus.PAID),
    (PaymentStatus.PAYMENT_LINK_SENT, PaymentStatus.UNPAID),
    (PaymentStatus.PAYMENT_LINK_SENT, PaymentStatus.PARTIALLY_PAID),
    (PaymentStatus.PAYMENT_LINK_SENT, PaymentStatus.PAID),
    (PaymentStatus.PARTIALLY_PAID, PaymentStatus.PAID),
    (PaymentStatus.PARTIALLY_PAID, PaymentStatus.REFUNDED),
    (PaymentStatus.PAID, PaymentStatus.REFUNDED),
]

_ILLEGAL = [
    # Backward / fabricated-money transitions.
    (PaymentStatus.PAID, PaymentStatus.PAYMENT_LINK_SENT),
    (PaymentStatus.PAID, PaymentStatus.UNPAID),
    (PaymentStatus.PAID, PaymentStatus.PARTIALLY_PAID),
    (PaymentStatus.REFUNDED, PaymentStatus.PAID),
    (PaymentStatus.REFUNDED, PaymentStatus.UNPAID),
    # NOT_REQUIRED is terminal: a provider event can never flip it to PAID.
    (PaymentStatus.NOT_REQUIRED, PaymentStatus.PAID),
    (PaymentStatus.NOT_REQUIRED, PaymentStatus.UNPAID),
    (PaymentStatus.PARTIALLY_PAID, PaymentStatus.PAYMENT_LINK_SENT),
    (PaymentStatus.PARTIALLY_PAID, PaymentStatus.UNPAID),
    (PaymentStatus.UNPAID, PaymentStatus.REFUNDED),
]


@pytest.mark.parametrize("src,dst", _PERMITTED)
def test_permitted_transitions(src, dst):
    assert pd.can_transition(src, dst) is True
    assert pd.validate_transition(src, dst) == dst


@pytest.mark.parametrize("src,dst", _ILLEGAL)
def test_illegal_transitions_rejected(src, dst):
    assert pd.can_transition(src, dst) is False
    with pytest.raises(pd.PaymentDomainError):
        pd.validate_transition(src, dst)


@pytest.mark.parametrize("status", sorted(pd.PAYMENT_STATUS_SET))
def test_same_status_transition_is_idempotent(status):
    """A same-status transition (replayed event) is always allowed."""
    assert pd.can_transition(status, status) is True
    assert pd.validate_transition(status, status) == status


def test_transition_with_unknown_status_rejected():
    assert pd.can_transition("bogus", PaymentStatus.PAID) is False
    with pytest.raises(pd.PaymentDomainError):
        pd.validate_transition("bogus", PaymentStatus.PAID)
    with pytest.raises(pd.PaymentDomainError):
        pd.validate_transition(PaymentStatus.UNPAID, "bogus")


# ---------------------------------------------------------------------------
# Amount invariants (integer minor units; no float authority; no overpayment).
# ---------------------------------------------------------------------------

def test_amounts_none_requirement_ok():
    out = pd.validate_payment_amounts(PaymentRequirement.NONE, 0, 0)
    assert out["amount_required_cents"] == 0
    assert out["amount_paid_cents"] == 0
    assert out["currency"] == DEFAULT_CURRENCY


def test_amounts_full_exact_ok():
    out = pd.validate_payment_amounts(PaymentRequirement.FULL, 5000, 5000, "USD")
    assert out["amount_required_cents"] == 5000
    assert out["amount_paid_cents"] == 5000


def test_amounts_full_partial_ok_is_allowed_at_amount_layer():
    # Being short is a readiness concern, not an amount-invariant violation.
    out = pd.validate_payment_amounts(PaymentRequirement.FULL, 5000, 2500, "USD")
    assert out["amount_paid_cents"] == 2500


def test_amounts_full_overpayment_rejected():
    with pytest.raises(pd.PaymentDomainError):
        pd.validate_payment_amounts(PaymentRequirement.FULL, 5000, 5001, "USD")


def test_amounts_deposit_exceeding_total_rejected():
    with pytest.raises(pd.PaymentDomainError):
        pd.validate_payment_amounts(
            PaymentRequirement.DEPOSIT, 5000, 0, "USD", deposit_amount_cents=6000
        )


def test_amounts_deposit_overpayment_rejected():
    with pytest.raises(pd.PaymentDomainError):
        pd.validate_payment_amounts(
            PaymentRequirement.DEPOSIT, 5000, 5001, "USD", deposit_amount_cents=2000
        )


def test_amounts_currency_required_when_money_required():
    with pytest.raises(pd.PaymentDomainError):
        pd.validate_payment_amounts(PaymentRequirement.FULL, 5000, 0, "")


def test_amounts_currency_not_required_when_none():
    out = pd.validate_payment_amounts(PaymentRequirement.NONE, 0, 0, "")
    assert out["currency"] == DEFAULT_CURRENCY


def test_amounts_invalid_requirement_rejected():
    with pytest.raises(pd.PaymentDomainError):
        pd.validate_payment_amounts("SOMETHING", 5000, 0, "USD")


# ---------------------------------------------------------------------------
# Provider abstraction / MANUAL_EXTERNAL boundary.
# ---------------------------------------------------------------------------

def test_provider_enum_values():
    assert pd.PaymentProvider.MANUAL_EXTERNAL == "MANUAL_EXTERNAL"
    assert pd.PaymentProvider.STRIPE_CONNECT_DIRECT == "STRIPE_CONNECT_DIRECT"
    assert pd.PaymentProvider.STRIPE_CONNECT_MARKETPLACE == "STRIPE_CONNECT_MARKETPLACE"


def test_only_manual_external_is_w3b_supported():
    assert pd.PaymentProvider.W3B_SUPPORTED == frozenset({"MANUAL_EXTERNAL"})
    assert pd.PaymentProvider.MANUAL_EXTERNAL in pd.PaymentProvider.W3B_SUPPORTED
    # Marketplace is a forward label only, never a supported MVP boundary.
    assert pd.PaymentProvider.STRIPE_CONNECT_MARKETPLACE not in pd.PaymentProvider.W3B_SUPPORTED


@pytest.mark.parametrize("provider", sorted(pd.PaymentProvider.ALL))
def test_validate_provider_accepts_known(provider):
    assert pd.validate_provider(provider) == provider


@pytest.mark.parametrize("bad", ["STRIPE", "manual", "paypal", "", None])
def test_validate_provider_rejects_unknown(bad):
    with pytest.raises(pd.PaymentDomainError):
        pd.validate_provider(bad)


# ---------------------------------------------------------------------------
# Booking readiness (amount-aware; preserves accept != paid != APPROVED).
# ---------------------------------------------------------------------------

def test_ready_none_requirement_when_accepted():
    ready, _ = pd.is_booking_payment_ready(
        QuoteStatus.ACCEPTED, PaymentRequirement.NONE, PaymentStatus.NOT_REQUIRED
    )
    assert ready is True


@pytest.mark.parametrize("qs", [QuoteStatus.DRAFT, QuoteStatus.SENT, QuoteStatus.DECLINED])
def test_not_ready_when_quote_not_accepted(qs):
    ready, reason = pd.is_booking_payment_ready(
        qs, PaymentRequirement.NONE, PaymentStatus.NOT_REQUIRED
    )
    assert ready is False
    assert "not accepted" in reason


def test_deposit_ready_when_threshold_met_and_partial():
    ready, _ = pd.is_booking_payment_ready(
        QuoteStatus.ACCEPTED, PaymentRequirement.DEPOSIT, PaymentStatus.PARTIALLY_PAID,
        quote_amount_cents=10000, deposit_amount_cents=3000, amount_paid_cents=3000,
    )
    assert ready is True


def test_deposit_ready_when_fully_paid():
    ready, _ = pd.is_booking_payment_ready(
        QuoteStatus.ACCEPTED, PaymentRequirement.DEPOSIT, PaymentStatus.PAID,
        quote_amount_cents=10000, deposit_amount_cents=3000, amount_paid_cents=10000,
    )
    assert ready is True


def test_deposit_not_ready_when_below_threshold():
    ready, reason = pd.is_booking_payment_ready(
        QuoteStatus.ACCEPTED, PaymentRequirement.DEPOSIT, PaymentStatus.PARTIALLY_PAID,
        quote_amount_cents=10000, deposit_amount_cents=3000, amount_paid_cents=2999,
    )
    assert ready is False
    assert "deposit amount not met" in reason


def test_deposit_not_ready_when_status_unpaid():
    ready, reason = pd.is_booking_payment_ready(
        QuoteStatus.ACCEPTED, PaymentRequirement.DEPOSIT, PaymentStatus.UNPAID,
        quote_amount_cents=10000, deposit_amount_cents=3000, amount_paid_cents=3000,
    )
    assert ready is False
    assert "deposit not settled" in reason


def test_full_ready_when_paid_in_full():
    ready, _ = pd.is_booking_payment_ready(
        QuoteStatus.ACCEPTED, PaymentRequirement.FULL, PaymentStatus.PAID,
        quote_amount_cents=5000, amount_paid_cents=5000,
    )
    assert ready is True


def test_full_not_ready_when_partial():
    ready, reason = pd.is_booking_payment_ready(
        QuoteStatus.ACCEPTED, PaymentRequirement.FULL, PaymentStatus.PARTIALLY_PAID,
        quote_amount_cents=5000, amount_paid_cents=2500,
    )
    assert ready is False
    assert "full payment not settled" in reason


def test_full_not_ready_when_status_paid_but_amount_short():
    # Defense in depth: even if status claims PAID, a short amount is not ready.
    ready, reason = pd.is_booking_payment_ready(
        QuoteStatus.ACCEPTED, PaymentRequirement.FULL, PaymentStatus.PAID,
        quote_amount_cents=5000, amount_paid_cents=4999,
    )
    assert ready is False
    assert "full amount not met" in reason


def test_readiness_never_returns_approved_or_mutates():
    # The predicate returns only (bool, str); it cannot approve/book/schedule.
    result = pd.is_booking_payment_ready(
        QuoteStatus.ACCEPTED, PaymentRequirement.NONE, PaymentStatus.NOT_REQUIRED
    )
    assert isinstance(result, tuple) and len(result) == 2
    assert isinstance(result[0], bool) and isinstance(result[1], str)


# ---------------------------------------------------------------------------
# REQUEST payment summary (provider-neutral; validated).
# ---------------------------------------------------------------------------

def test_build_payment_summary_fields_exact():
    summary = pd.build_payment_summary(
        payment_requirement=PaymentRequirement.FULL,
        payment_status=PaymentStatus.PAID,
        amount_required_cents=5000,
        amount_paid_cents=5000,
        currency="USD",
        payment_provider=pd.PaymentProvider.MANUAL_EXTERNAL,
    )
    assert set(summary.keys()) == set(pd.PAYMENT_SUMMARY_FIELDS)
    assert summary["payment_status"] == PaymentStatus.PAID
    assert summary["payment_provider"] == "MANUAL_EXTERNAL"


def test_build_payment_summary_normalizes_legacy_status():
    summary = pd.build_payment_summary(
        payment_requirement=PaymentRequirement.FULL,
        payment_status="paid",
        amount_required_cents=5000,
        amount_paid_cents=5000,
    )
    assert summary["payment_status"] == PaymentStatus.PAID


def test_build_payment_summary_rejects_unknown_status():
    with pytest.raises(pd.PaymentDomainError):
        pd.build_payment_summary(
            payment_requirement=PaymentRequirement.FULL,
            payment_status="bogus",
            amount_required_cents=5000,
            amount_paid_cents=0,
        )


def test_build_payment_summary_rejects_bad_provider():
    with pytest.raises(pd.PaymentDomainError):
        pd.build_payment_summary(
            payment_provider="PAYPAL",
            payment_requirement=PaymentRequirement.NONE,
        )


# ---------------------------------------------------------------------------
# PAYMENT_EVENT — append-only, deterministic idempotent SK, forbidden metadata.
# ---------------------------------------------------------------------------

def test_payment_event_sk_deterministic():
    assert pd.payment_event_sk("abc-123") == "PAYEVENT#abc-123"
    assert pd.payment_event_sk("  abc-123  ") == "PAYEVENT#abc-123"


@pytest.mark.parametrize("bad", ["", None, 123, 0])
def test_payment_event_sk_rejects_bad_key(bad):
    with pytest.raises(pd.PaymentDomainError):
        pd.payment_event_sk(bad)


def test_build_payment_event_keys_under_request_collection():
    evt = pd.build_payment_event(
        request_id="req-1",
        company_id="co-1",
        event_type=pd.PaymentEventType.PAYMENT_SETTLED,
        idempotency_key="idem-1",
        previous_status=PaymentStatus.UNPAID,
        resulting_status=PaymentStatus.PAID,
        client_id="cli-1",
        provider=pd.PaymentProvider.MANUAL_EXTERNAL,
        amount_delta_cents=5000,
        currency="USD",
        provider_txn_ref="EXT-REF-OPAQUE",
    )
    assert evt["PK"] == "REQ#req-1"
    assert evt["SK"] == "PAYEVENT#idem-1"
    assert evt["entity_type"] == "PAYMENT_EVENT"
    assert evt["company_id"] == "co-1"
    assert evt["previous_payment_status"] == PaymentStatus.UNPAID
    assert evt["resulting_payment_status"] == PaymentStatus.PAID
    assert evt["payment_provider"] == "MANUAL_EXTERNAL"
    assert evt["provider_txn_ref"] == "EXT-REF-OPAQUE"
    assert "created_at" in evt


def test_build_payment_event_duplicate_key_same_sk():
    """Idempotency: the same idempotency_key yields the same deterministic SK, so a
    conditional put naturally dedupes replays."""
    common = dict(
        request_id="req-1", company_id="co-1",
        event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="idem-dup",
        previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
    )
    a = pd.build_payment_event(**common)
    b = pd.build_payment_event(**common)
    assert a["SK"] == b["SK"] == "PAYEVENT#idem-dup"


def test_build_payment_event_illegal_transition_rejected():
    with pytest.raises(pd.PaymentDomainError):
        pd.build_payment_event(
            request_id="req-1", company_id="co-1",
            event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="idem-x",
            previous_status=PaymentStatus.REFUNDED, resulting_status=PaymentStatus.PAID,
        )


def test_build_payment_event_requires_trusted_identity():
    with pytest.raises(pd.PaymentDomainError):
        pd.build_payment_event(
            request_id="", company_id="co-1",
            event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="k",
            previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
        )
    with pytest.raises(pd.PaymentDomainError):
        pd.build_payment_event(
            request_id="req-1", company_id="",
            event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="k",
            previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
        )


def test_build_payment_event_invalid_event_type_rejected():
    with pytest.raises(pd.PaymentDomainError):
        pd.build_payment_event(
            request_id="req-1", company_id="co-1",
            event_type="SOMETHING_ELSE", idempotency_key="k",
            previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
        )


@pytest.mark.parametrize("bad_key", [
    "pan", "card_number", "cvc", "cvv", "secret", "stripe_secret_key",
    "api_key", "authorization", "jwt", "token", "access_token", "password",
])
def test_build_payment_event_rejects_forbidden_metadata(bad_key):
    with pytest.raises(pd.PaymentDomainError):
        pd.build_payment_event(
            request_id="req-1", company_id="co-1",
            event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="k",
            previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
            metadata={bad_key: "leak"},
        )


def test_build_payment_event_allows_safe_metadata():
    evt = pd.build_payment_event(
        request_id="req-1", company_id="co-1",
        event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="k",
        previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
        metadata={"note": "confirmed by owner", "channel": "bank_transfer"},
    )
    assert evt["metadata"]["note"] == "confirmed by owner"
    assert evt["metadata"]["channel"] == "bank_transfer"


def test_build_payment_event_idempotent_same_status_replay_allowed():
    evt = pd.build_payment_event(
        request_id="req-1", company_id="co-1",
        event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="replay",
        previous_status=PaymentStatus.PAID, resulting_status=PaymentStatus.PAID,
    )
    assert evt["resulting_payment_status"] == PaymentStatus.PAID


# ---------------------------------------------------------------------------
# MANUAL_EXTERNAL boundary — no client self-assertion / opaque refs only.
# ---------------------------------------------------------------------------

def test_manual_external_event_carries_opaque_ref_not_secret():
    evt = pd.build_payment_event(
        request_id="req-1", company_id="co-1",
        event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="m1",
        previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
        provider=pd.PaymentProvider.MANUAL_EXTERNAL,
        provider_txn_ref="CHECK-10482",
        actor="owner:admin-1",
    )
    assert evt["provider_txn_ref"] == "CHECK-10482"
    assert evt["actor"] == "owner:admin-1"
    # The event never carries a client-provided PAID assertion field.
    assert "client_marked_paid" not in evt


def test_payment_event_types_small_and_explicit():
    assert pd.PaymentEventType.ALL == frozenset({
        "PAYMENT_REQUESTED", "PAYMENT_SETTLED", "PAYMENT_PARTIALLY_SETTLED",
        "PAYMENT_REFUNDED", "PAYMENT_FAILED", "PAYMENT_VOIDED",
    })
