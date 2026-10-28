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

def _module_toplevel_import_roots(tree):
    """Root module names imported at MODULE TOP LEVEL (not inside functions)."""
    roots = set()
    for node in tree.body:  # only direct children of the module = top level
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


import ast  # noqa: E402 (used by the coupling tests below)


def test_domain_module_has_no_stripe_at_any_level():
    """The provider-neutral domain must never import Stripe/HTTP, at ANY level.

    Stripe/HTTP coupling is forbidden outright. (DB access is allowed only as a lazy
    function-local import inside the persistence layer — see the next test.) Prose in the
    module docstring deliberately *names* the forbidden coupling to document what it
    avoids, so a plain substring scan would false-positive; we inspect real imports.
    """
    importlib.reload(pd)
    with open(pd.__file__, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    forbidden_anywhere = {"stripe", "requests", "urllib", "http"}
    imported_roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_roots.add(node.module.split(".")[0])

    leaked = forbidden_anywhere & imported_roots
    assert not leaked, f"provider-neutral domain must never import {sorted(leaked)}"
    assert not hasattr(pd, "stripe")


def test_domain_module_toplevel_is_db_import_clean():
    """The pure domain must not couple to the repository at MODULE TOP LEVEL.

    Persistence (`persist_payment_event`/`load_owned_request`) imports `common.db` and
    `botocore` lazily *inside* the function, so the module top level stays import-clean
    and the pure domain can be reasoned about without a DynamoDB/boto3 dependency.
    """
    importlib.reload(pd)
    with open(pd.__file__, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    toplevel = _module_toplevel_import_roots(tree)
    for root in ("boto3", "botocore", "db", "common"):
        # `from common.quote_contract import ...` is allowed (root "common"); but no
        # top-level boto3/botocore, and no top-level `from common.db import ...`.
        pass
    assert "boto3" not in toplevel
    assert "botocore" not in toplevel
    # The only top-level `common.*` import is quote_contract; db/auth are lazy.
    with open(pd.__file__, "r", encoding="utf-8") as fh:
        src = fh.read()
    assert "\nfrom common.db import" not in src  # db import must be indented (lazy)
    assert "\nfrom common.auth import" not in src


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


# ===========================================================================
# W3-B HARDENING COVERAGE (PR #29 review findings)
# ===========================================================================

from decimal import Decimal
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError


# ---------------------------------------------------------------------------
# 1. Canonical cents magnitude preservation (no ×100 inflation).
# ---------------------------------------------------------------------------

def test_canonical_cents_int_preserved():
    assert pd.canonical_cents(5000) == 5000


def test_canonical_cents_decimal_integer_preserved_not_multiplied():
    # The bug: to_cents(Decimal('5000')) would return 500000. canonical_cents must not.
    assert pd.canonical_cents(Decimal("5000")) == 5000


def test_canonical_cents_string_integral_preserved():
    assert pd.canonical_cents("5000") == 5000


def test_canonical_cents_zero_and_none():
    assert pd.canonical_cents(0) == 0
    assert pd.canonical_cents(None) == 0


@pytest.mark.parametrize("bad", [Decimal("50.5"), 50.5, "50.5", Decimal("0.01")])
def test_canonical_cents_non_integral_rejected(bad):
    with pytest.raises(pd.PaymentDomainError):
        pd.canonical_cents(bad)


@pytest.mark.parametrize("bad", [-1, Decimal("-1"), "-100"])
def test_canonical_cents_negative_rejected(bad):
    with pytest.raises(pd.PaymentDomainError):
        pd.canonical_cents(bad)


@pytest.mark.parametrize("bad", [True, False])
def test_canonical_cents_bool_rejected(bad):
    with pytest.raises(pd.PaymentDomainError):
        pd.canonical_cents(bad)


def test_validate_payment_amounts_preserves_decimal_magnitude():
    out = pd.validate_payment_amounts(
        PaymentRequirement.FULL, Decimal("5000"), Decimal("5000"), "USD"
    )
    assert out["amount_required_cents"] == 5000
    assert out["amount_paid_cents"] == 5000  # NOT 500000


def test_validate_payment_amounts_decimal_deposit_magnitude():
    out = pd.validate_payment_amounts(
        PaymentRequirement.DEPOSIT, Decimal("10000"), Decimal("3000"), "USD",
        deposit_amount_cents=Decimal("3000"),
    )
    assert out["amount_required_cents"] == 10000
    assert out["deposit_amount_cents"] == 3000


def test_amount_delta_cents_decimal_magnitude_preserved_in_event():
    evt = pd.build_payment_event(
        request_id="req-1", company_id="co-1",
        event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="delta-dec",
        previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
        amount_delta_cents=Decimal("5000"),
    )
    assert evt["amount_delta_cents"] == 5000  # NOT 500000


def test_amount_delta_cents_non_integral_decimal_rejected():
    with pytest.raises(pd.PaymentDomainError):
        pd.build_payment_event(
            request_id="req-1", company_id="co-1",
            event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="delta-bad",
            previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
            amount_delta_cents=Decimal("50.5"),
        )


def test_is_booking_payment_ready_decimal_amounts_not_inflated():
    # FULL: paid Decimal('5000') must satisfy total Decimal('5000') (not be 100x short/over).
    ready, _ = pd.is_booking_payment_ready(
        QuoteStatus.ACCEPTED, PaymentRequirement.FULL, PaymentStatus.PAID,
        quote_amount_cents=Decimal("5000"), amount_paid_cents=Decimal("5000"),
    )
    assert ready is True


# ---------------------------------------------------------------------------
# 2. Provider execution boundary — known vs active.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("provider", sorted(pd.PaymentProvider.ALL))
def test_validate_known_provider_accepts_all_known(provider):
    assert pd.validate_known_provider(provider) == provider


def test_validate_active_provider_accepts_manual_external():
    assert pd.validate_active_provider(pd.PaymentProvider.MANUAL_EXTERNAL) == "MANUAL_EXTERNAL"


@pytest.mark.parametrize("provider", [
    pd.PaymentProvider.STRIPE_CONNECT_DIRECT,
    pd.PaymentProvider.STRIPE_CONNECT_MARKETPLACE,
])
def test_validate_active_provider_rejects_known_but_inactive(provider):
    # Known identifier, but NOT executable in W3-B.
    assert pd.validate_known_provider(provider) == provider
    with pytest.raises(pd.PaymentDomainError):
        pd.validate_active_provider(provider)


@pytest.mark.parametrize("bad", ["PAYPAL", "stripe", "", None])
def test_validate_active_provider_rejects_unknown(bad):
    with pytest.raises(pd.PaymentDomainError):
        pd.validate_active_provider(bad)


def test_build_payment_event_rejects_connect_direct_as_active():
    with pytest.raises(pd.PaymentDomainError):
        pd.build_payment_event(
            request_id="req-1", company_id="co-1",
            event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="k",
            previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
            provider=pd.PaymentProvider.STRIPE_CONNECT_DIRECT,
        )


def test_build_payment_event_rejects_marketplace_as_active():
    with pytest.raises(pd.PaymentDomainError):
        pd.build_payment_event(
            request_id="req-1", company_id="co-1",
            event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="k",
            previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
            provider=pd.PaymentProvider.STRIPE_CONNECT_MARKETPLACE,
        )


def test_build_payment_summary_rejects_connect_direct_as_active():
    with pytest.raises(pd.PaymentDomainError):
        pd.build_payment_summary(
            payment_provider=pd.PaymentProvider.STRIPE_CONNECT_DIRECT,
            payment_requirement=PaymentRequirement.NONE,
        )


# ---------------------------------------------------------------------------
# 3. Audit metadata safety — recursive, allowlist-oriented.
# ---------------------------------------------------------------------------

def test_metadata_safe_scalars_allowed():
    out = pd.sanitize_payment_event_metadata(
        {"note": "ok", "count": 3, "ratio": 1.5, "flag": True, "none": None}
    )
    assert out == {"note": "ok", "count": 3, "ratio": 1.5, "flag": True, "none": None}


def test_metadata_safe_nested_and_list_allowed():
    out = pd.sanitize_payment_event_metadata(
        {"outer": {"inner": "v"}, "items": ["a", "b", 1]}
    )
    assert out["outer"]["inner"] == "v"
    assert out["items"] == ["a", "b", 1]


def test_metadata_nested_sensitive_key_rejected():
    with pytest.raises(pd.PaymentDomainError):
        pd.sanitize_payment_event_metadata({"details": {"access_token": "x"}})


def test_metadata_deeply_nested_secret_rejected():
    with pytest.raises(pd.PaymentDomainError):
        pd.sanitize_payment_event_metadata({"a": {"b": {"client_secret": "x"}}})


@pytest.mark.parametrize("key", [
    "card_pan", "cvv2", "auth_token", "client_secret", "x_api_key",
    "user_password", "bearer_token", "private_key",
])
def test_metadata_sensitive_pattern_keys_rejected(key):
    with pytest.raises(pd.PaymentDomainError):
        pd.sanitize_payment_event_metadata({key: "x"})


def test_metadata_raw_provider_payload_object_rejected():
    class RawPayload:
        pass
    with pytest.raises(pd.PaymentDomainError):
        pd.sanitize_payment_event_metadata({"provider_obj": RawPayload()})


def test_metadata_bytes_rejected():
    with pytest.raises(pd.PaymentDomainError):
        pd.sanitize_payment_event_metadata({"blob": b"\x00\x01"})


def test_metadata_too_deep_rejected():
    deep = {"l1": {"l2": {"l3": {"l4": "x"}}}}
    with pytest.raises(pd.PaymentDomainError):
        pd.sanitize_payment_event_metadata(deep)


def test_metadata_non_dict_toplevel_rejected():
    with pytest.raises(pd.PaymentDomainError):
        pd.sanitize_payment_event_metadata(["not", "a", "dict"])


def test_metadata_non_string_key_rejected():
    with pytest.raises(pd.PaymentDomainError):
        pd.sanitize_payment_event_metadata({1: "x"})


def test_metadata_empty_or_none_becomes_none():
    assert pd.sanitize_payment_event_metadata(None) is None
    assert pd.sanitize_payment_event_metadata({}) is None


def test_build_payment_event_rejects_nested_secret_metadata():
    with pytest.raises(pd.PaymentDomainError):
        pd.build_payment_event(
            request_id="req-1", company_id="co-1",
            event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="k",
            previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
            metadata={"details": {"access_token": "leak"}},
        )


# ---------------------------------------------------------------------------
# 4. Tenant / request ownership enforcement (load_owned_request).
# ---------------------------------------------------------------------------

_REQUEST_OWNED = {
    "PK": "REQ#req-1", "SK": "CLIENT#cli-1", "entity_type": "REQUEST",
    "company_id": "co-1", "client_id": "cli-1",
}


def test_load_owned_request_allows_correct_tenant():
    with patch("common.db.get_item", return_value=dict(_REQUEST_OWNED)):
        item = pd.load_owned_request("req-1", "cli-1", "co-1")
    assert item["company_id"] == "co-1"


def test_load_owned_request_wrong_tenant_rejected():
    with patch("common.db.get_item", return_value=dict(_REQUEST_OWNED)):
        with pytest.raises(pd.PaymentDomainError):
            pd.load_owned_request("req-1", "cli-1", "ATTACKER-CO")


def test_load_owned_request_nonexistent_rejected():
    with patch("common.db.get_item", return_value=None):
        with pytest.raises(pd.PaymentDomainError):
            pd.load_owned_request("req-missing", "cli-1", "co-1")


def test_load_owned_request_client_mismatch_rejected():
    rec = dict(_REQUEST_OWNED)
    rec["client_id"] = "other-client"
    with patch("common.db.get_item", return_value=rec):
        with pytest.raises(pd.PaymentDomainError):
            pd.load_owned_request("req-1", "cli-1", "co-1")


def test_load_owned_request_defaults_company_when_absent():
    # Record without company_id falls back to DEFAULT_COMPANY_ID (live convention).
    from common.auth import DEFAULT_COMPANY_ID
    rec = {"PK": "REQ#req-1", "SK": "CLIENT#cli-1", "client_id": "cli-1"}
    with patch("common.db.get_item", return_value=rec):
        item = pd.load_owned_request("req-1", "cli-1", DEFAULT_COMPANY_ID)
    assert item is not None


# ---------------------------------------------------------------------------
# 5. PAYMENT_EVENT persistence — conditional, append-only, idempotent.
# ---------------------------------------------------------------------------

def _conditional_failed_error():
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}},
        "PutItem",
    )


def _persist_kwargs(**over):
    base = dict(
        request_id="req-1", company_id="co-1", client_id="cli-1",
        event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="idem-1",
        previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
        amount_delta_cents=5000, currency="USD", provider_txn_ref="EXT-1",
    )
    base.update(over)
    return base


def test_persist_payment_event_created():
    mock_table = MagicMock()
    mock_table.put_item = MagicMock()
    with patch("common.db.get_item", return_value=dict(_REQUEST_OWNED)), \
         patch("common.db.table", mock_table):
        result, item = pd.persist_payment_event(**_persist_kwargs())
    assert result == pd.PERSIST_CREATED
    assert item["SK"] == "PAYEVENT#idem-1"
    # Conditional write used (append-only, never overwrite).
    _, kwargs = mock_table.put_item.call_args
    assert "attribute_not_exists(PK)" in kwargs["ConditionExpression"]
    assert "attribute_not_exists(SK)" in kwargs["ConditionExpression"]


def test_persist_payment_event_no_write_on_tenant_mismatch():
    mock_table = MagicMock()
    with patch("common.db.get_item", return_value=dict(_REQUEST_OWNED)), \
         patch("common.db.table", mock_table):
        with pytest.raises(pd.PaymentDomainError):
            pd.persist_payment_event(**_persist_kwargs(company_id="ATTACKER"))
    mock_table.put_item.assert_not_called()


def test_persist_payment_event_no_write_on_missing_request():
    mock_table = MagicMock()
    with patch("common.db.get_item", return_value=None), \
         patch("common.db.table", mock_table):
        with pytest.raises(pd.PaymentDomainError):
            pd.persist_payment_event(**_persist_kwargs(request_id="missing"))
    mock_table.put_item.assert_not_called()


def test_persist_payment_event_duplicate_same_event_is_idempotent():
    # Build the exact item that would already be stored.
    existing = pd.build_payment_event(
        request_id="req-1", company_id="co-1",
        event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="idem-1",
        previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
        client_id="cli-1", amount_delta_cents=5000, currency="USD",
        provider_txn_ref="EXT-1",
    )
    mock_table = MagicMock()
    mock_table.put_item.side_effect = _conditional_failed_error()

    # get_item: first call returns the REQUEST (ownership), second returns the existing event.
    def get_side_effect(pk, sk):
        if sk.startswith("CLIENT#"):
            return dict(_REQUEST_OWNED)
        if sk.startswith("PAYEVENT#"):
            return existing
        return None

    with patch("common.db.get_item", side_effect=get_side_effect), \
         patch("common.db.table", mock_table):
        result, item = pd.persist_payment_event(**_persist_kwargs())
    assert result == pd.PERSIST_DUPLICATE_SAME_EVENT


def test_persist_payment_event_conflicting_idempotency_key_not_success():
    # Existing event at same key but DIFFERENT semantic payload (different amount).
    existing = pd.build_payment_event(
        request_id="req-1", company_id="co-1",
        event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="idem-1",
        previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
        client_id="cli-1", amount_delta_cents=9999, currency="USD",
        provider_txn_ref="DIFFERENT",
    )
    mock_table = MagicMock()
    mock_table.put_item.side_effect = _conditional_failed_error()

    def get_side_effect(pk, sk):
        if sk.startswith("CLIENT#"):
            return dict(_REQUEST_OWNED)
        if sk.startswith("PAYEVENT#"):
            return existing
        return None

    with patch("common.db.get_item", side_effect=get_side_effect), \
         patch("common.db.table", mock_table):
        result, item = pd.persist_payment_event(**_persist_kwargs())
    assert result == pd.PERSIST_CONFLICTING_IDEMPOTENCY_KEY
    assert result != pd.PERSIST_CREATED


def test_persist_payment_event_conditional_write_never_overwrites():
    # Even when a conflicting event exists, put_item is attempted exactly once with the
    # conditional guard, and the result is NOT reported as created.
    existing = dict(_REQUEST_OWNED)
    mock_table = MagicMock()
    mock_table.put_item.side_effect = _conditional_failed_error()

    stored_event = pd.build_payment_event(
        request_id="req-1", company_id="co-1",
        event_type=pd.PaymentEventType.PAYMENT_SETTLED, idempotency_key="idem-1",
        previous_status=PaymentStatus.UNPAID, resulting_status=PaymentStatus.PAID,
        client_id="cli-1", amount_delta_cents=1, currency="USD", provider_txn_ref="X",
    )

    def get_side_effect(pk, sk):
        if sk.startswith("CLIENT#"):
            return existing
        return stored_event

    with patch("common.db.get_item", side_effect=get_side_effect), \
         patch("common.db.table", mock_table):
        result, _ = pd.persist_payment_event(**_persist_kwargs())
    assert mock_table.put_item.call_count == 1
    assert result != pd.PERSIST_CREATED


def test_persist_payment_event_non_conditional_dynamo_error_raises_domain_error():
    mock_table = MagicMock()
    mock_table.put_item.side_effect = ClientError(
        {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "x"}},
        "PutItem",
    )
    with patch("common.db.get_item", return_value=dict(_REQUEST_OWNED)), \
         patch("common.db.table", mock_table):
        with pytest.raises(pd.PaymentDomainError):
            pd.persist_payment_event(**_persist_kwargs())


def test_persist_payment_event_rejects_inactive_provider_before_write():
    mock_table = MagicMock()
    with patch("common.db.get_item", return_value=dict(_REQUEST_OWNED)), \
         patch("common.db.table", mock_table):
        with pytest.raises(pd.PaymentDomainError):
            pd.persist_payment_event(
                **_persist_kwargs(provider=pd.PaymentProvider.STRIPE_CONNECT_DIRECT)
            )
    mock_table.put_item.assert_not_called()
