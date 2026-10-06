"""OPS-3A.2A — Pure quote-contract Accept/Decline tests (framework-free).

Covers the approved OPS-3A.2 contract (docs/planning/petcare-hero-quote-contract.md,
"OPS-3A.2 — Client Accept / Decline — APPROVED BY MATTHEW (2026-10-05)"):

  - Accept/Decline eligible ONLY from SENT; transition to ACCEPTED/DECLINED.
  - Neither increments quote_revision (lifecycle event on the current revision).
  - Accept binds quote_accepted_revision; Decline binds quote_declined_revision.
  - expected_revision mismatch is rejected at the pure layer.
  - decline_reason normalization: trim, blank -> absent, >500 -> error.
  - No payment / booking-status fields are produced by either function.
"""

import pytest

from common.quote_contract import (
    QuoteStatus,
    QuoteContractError,
    MAX_DECLINE_REASON_LEN,
    normalize_decline_reason,
    apply_quote_accept,
    apply_quote_decline,
)

NOW = "2026-10-05T12:00:00Z"

# Fields that must NEVER be produced by accept/decline (payment / booking lifecycle).
_FORBIDDEN_OUTPUT_FIELDS = frozenset({
    "payment_status",
    "payment_requirement",
    "payment_amount_cents",
    "status",            # the request/booking workflow status
    "quote_amount_cents",
    "deposit_amount_cents",
})


def _sent_req(revision=1, **overrides):
    base = {
        "request_id": "req-001",
        "client_id": "client-001",
        "quote_status": QuoteStatus.SENT,
        "quote_revision": revision,
        "quote_amount_cents": 5000,
        "currency": "USD",
        "payment_requirement": "NONE",
        "payment_status": "NOT_REQUIRED",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# normalize_decline_reason
# ---------------------------------------------------------------------------

def test_normalize_decline_reason_none_is_absent():
    assert normalize_decline_reason(None) is None


def test_normalize_decline_reason_trims():
    assert normalize_decline_reason("  too expensive  ") == "too expensive"


def test_normalize_decline_reason_blank_is_absent():
    assert normalize_decline_reason("   ") is None
    assert normalize_decline_reason("") is None


def test_normalize_decline_reason_max_len_ok():
    s = "x" * MAX_DECLINE_REASON_LEN
    assert normalize_decline_reason(s) == s


def test_normalize_decline_reason_over_len_rejected():
    with pytest.raises(QuoteContractError):
        normalize_decline_reason("x" * (MAX_DECLINE_REASON_LEN + 1))


def test_normalize_decline_reason_non_string_rejected():
    with pytest.raises(QuoteContractError):
        normalize_decline_reason(123)


# ---------------------------------------------------------------------------
# apply_quote_accept
# ---------------------------------------------------------------------------

def test_accept_sent_to_accepted():
    out = apply_quote_accept(_sent_req(revision=1), 1, NOW)
    assert out["quote_status"] == QuoteStatus.ACCEPTED
    assert out["quote_accepted_at"] == NOW
    assert out["quote_accepted_revision"] == 1


def test_accept_does_not_increment_revision():
    out = apply_quote_accept(_sent_req(revision=3), 3, NOW)
    assert out["quote_revision"] == 3  # unchanged
    assert out["quote_accepted_revision"] == 3


def test_accept_binds_current_revision():
    out = apply_quote_accept(_sent_req(revision=7), 7, NOW)
    assert out["quote_accepted_revision"] == 7


def test_accept_rejects_non_sent_status():
    for bad in (QuoteStatus.DRAFT, QuoteStatus.ACCEPTED, QuoteStatus.DECLINED,
                QuoteStatus.NOT_REQUIRED):
        with pytest.raises(QuoteContractError):
            apply_quote_accept(_sent_req(quote_status=bad), 1, NOW)


def test_accept_rejects_revision_mismatch():
    with pytest.raises(QuoteContractError):
        apply_quote_accept(_sent_req(revision=2), 1, NOW)


def test_accept_produces_no_payment_or_booking_fields():
    out = apply_quote_accept(_sent_req(revision=1), 1, NOW)
    assert _FORBIDDEN_OUTPUT_FIELDS.isdisjoint(out.keys())


def test_accept_does_not_mutate_input():
    req = _sent_req(revision=1)
    snapshot = dict(req)
    apply_quote_accept(req, 1, NOW)
    assert req == snapshot


# ---------------------------------------------------------------------------
# apply_quote_decline
# ---------------------------------------------------------------------------

def test_decline_sent_to_declined():
    out = apply_quote_decline(_sent_req(revision=1), 1, NOW)
    assert out["quote_status"] == QuoteStatus.DECLINED
    assert out["quote_declined_at"] == NOW
    assert out["quote_declined_revision"] == 1


def test_decline_does_not_increment_revision():
    out = apply_quote_decline(_sent_req(revision=4), 4, NOW)
    assert out["quote_revision"] == 4


def test_decline_optional_reason_stored_client_visible():
    out = apply_quote_decline(_sent_req(revision=1), 1, NOW, decline_reason="  changed mind ")
    assert out["quote_declined_reason_client"] == "changed mind"


def test_decline_blank_reason_absent():
    out = apply_quote_decline(_sent_req(revision=1), 1, NOW, decline_reason="   ")
    assert "quote_declined_reason_client" not in out


def test_decline_over_len_reason_rejected():
    with pytest.raises(QuoteContractError):
        apply_quote_decline(_sent_req(revision=1), 1, NOW,
                            decline_reason="x" * (MAX_DECLINE_REASON_LEN + 1))


def test_decline_rejects_non_sent_status():
    for bad in (QuoteStatus.DRAFT, QuoteStatus.ACCEPTED, QuoteStatus.DECLINED,
                QuoteStatus.NOT_REQUIRED):
        with pytest.raises(QuoteContractError):
            apply_quote_decline(_sent_req(quote_status=bad), 1, NOW)


def test_decline_rejects_revision_mismatch():
    with pytest.raises(QuoteContractError):
        apply_quote_decline(_sent_req(revision=5), 4, NOW)


def test_decline_produces_no_payment_or_booking_fields():
    out = apply_quote_decline(_sent_req(revision=1), 1, NOW, decline_reason="nope")
    assert _FORBIDDEN_OUTPUT_FIELDS.isdisjoint(out.keys())


def test_decline_does_not_mutate_input():
    req = _sent_req(revision=1)
    snapshot = dict(req)
    apply_quote_decline(req, 1, NOW, decline_reason="x")
    assert req == snapshot


# ---------------------------------------------------------------------------
# quote_history invariants (OPS-3A.2A review): Accept/Decline are lifecycle
# events on the current revision and MUST NOT snapshot a SUPERSEDED offer
# revision into quote_history. Only a commercial OFFER change does that
# (apply_quote_update, covered by test_quote_contract.py).
# ---------------------------------------------------------------------------

def test_accept_never_produces_quote_history_key():
    out = apply_quote_accept(_sent_req(revision=2), 2, NOW)
    assert "quote_history" not in out


def test_decline_never_produces_quote_history_key():
    out = apply_quote_decline(_sent_req(revision=2), 2, NOW, decline_reason="too much")
    assert "quote_history" not in out


def test_accept_leaves_existing_quote_history_untouched():
    # A record already carrying history (from a prior offer revision) must have its
    # history preserved verbatim and NOT referenced in the accept field-set.
    existing_history = [{"quote_status": QuoteStatus.SUPERSEDED, "quote_revision": 1,
                         "quote_amount_cents": 4000}]
    req = _sent_req(revision=2, quote_history=existing_history)
    snapshot = [dict(h) for h in existing_history]
    out = apply_quote_accept(req, 2, NOW)
    assert "quote_history" not in out          # not rewritten
    assert req["quote_history"] == snapshot      # input unchanged


def test_decline_leaves_existing_quote_history_untouched():
    existing_history = [{"quote_status": QuoteStatus.SUPERSEDED, "quote_revision": 1,
                         "quote_amount_cents": 4000}]
    req = _sent_req(revision=2, quote_history=existing_history)
    snapshot = [dict(h) for h in existing_history]
    out = apply_quote_decline(req, 2, NOW)
    assert "quote_history" not in out
    assert req["quote_history"] == snapshot


def test_accept_does_not_produce_superseded_status_anywhere():
    out = apply_quote_accept(_sent_req(revision=1), 1, NOW)
    assert QuoteStatus.SUPERSEDED not in out.values()


def test_decline_does_not_produce_superseded_status_anywhere():
    out = apply_quote_decline(_sent_req(revision=1), 1, NOW)
    assert QuoteStatus.SUPERSEDED not in out.values()
