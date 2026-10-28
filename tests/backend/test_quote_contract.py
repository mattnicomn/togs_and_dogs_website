"""OPS-3A.1 — Backend quote contract foundation tests (pure, framework-free).

Covers the approved OPS-3A quote contract (docs/planning/petcare-hero-quote-contract.md,
approved 2026-10-03): canonical cents money, legacy Decimal dual-read, client-safe
projection allowlist + internal-field exclusion, quote_status precedence over legacy
RequestStatus, SUPERSEDED-not-current, revision semantics (commercial vs internal),
draft/send transitions, invalid-value rejection, and the booking-approval predicate
(no implicit APPROVED).
"""

import json
from decimal import Decimal

import pytest

from common.quote_contract import (
    QuoteStatus,
    PaymentRequirement,
    PaymentStatus,
    QuoteContractError,
    DEFAULT_CURRENCY,
    CLIENT_QUOTE_ALLOWLIST,
    CLIENT_QUOTE_FORBIDDEN,
    to_cents,
    normalize_stored_cents,
    legacy_quote_amount_to_cents,
    cents_to_major_string,
    validate_quote_status_current,
    validate_payment_requirement,
    validate_payment_status,
    normalize_legacy_payment_status,
    resolve_quote_from_record,
    resolve_commercial_quote_status,
    build_client_quote_projection,
    apply_quote_update,
    apply_quote_send,
    evaluate_booking_approval_predicate,
)

NOW = "2026-10-03T12:00:00Z"


# ---------------------------------------------------------------------------
# Money / integer cents + serialization
# ---------------------------------------------------------------------------

def test_to_cents_accepts_int_as_cents():
    assert to_cents(1234) == 1234
    assert to_cents(0) == 0
    assert to_cents(None) == 0


def test_to_cents_converts_major_units_half_up():
    assert to_cents(Decimal("12.34")) == 1234
    assert to_cents("10.005") == 1001  # round half up
    assert to_cents(10.00) == 1000


def test_to_cents_rejects_negative_and_bool_and_junk():
    with pytest.raises(QuoteContractError):
        to_cents(-1)
    with pytest.raises(QuoteContractError):
        to_cents(True)
    with pytest.raises(QuoteContractError):
        to_cents("not-money")


def test_legacy_decimal_major_units_to_cents():
    assert legacy_quote_amount_to_cents(Decimal("45.00")) == 4500
    assert legacy_quote_amount_to_cents("12.50") == 1250
    assert legacy_quote_amount_to_cents(None) == 0
    assert legacy_quote_amount_to_cents("") == 0
    with pytest.raises(QuoteContractError):
        legacy_quote_amount_to_cents(Decimal("-1"))


def test_cents_serialize_as_plain_json_integers():
    projection = build_client_quote_projection({
        "request_id": "r1", "quote_status": QuoteStatus.SENT,
        "quote_amount_cents": 4500, "currency": "USD",
        "payment_requirement": PaymentRequirement.FULL,
    })
    # Integer cents must round-trip through JSON as a plain int (no Decimal).
    encoded = json.dumps(projection)
    assert '"quote_amount_cents": 4500' in encoded
    assert isinstance(json.loads(encoded)["quote_amount_cents"], int)


def test_cents_to_major_string_display():
    assert cents_to_major_string(1234) == "12.34"
    assert cents_to_major_string(0) == "0.00"


# ---------------------------------------------------------------------------
# Validation / invalid values
# ---------------------------------------------------------------------------

def test_superseded_cannot_be_current_quote_status():
    with pytest.raises(QuoteContractError):
        validate_quote_status_current(QuoteStatus.SUPERSEDED)


def test_invalid_quote_status_rejected():
    with pytest.raises(QuoteContractError):
        validate_quote_status_current("WHATEVER")


def test_valid_current_quote_statuses_accepted():
    for status in (QuoteStatus.NOT_REQUIRED, QuoteStatus.DRAFT, QuoteStatus.SENT,
                   QuoteStatus.ACCEPTED, QuoteStatus.DECLINED):
        assert validate_quote_status_current(status) == status


def test_invalid_payment_requirement_rejected():
    with pytest.raises(QuoteContractError):
        validate_payment_requirement("SOMETIMES")
    for value in (PaymentRequirement.NONE, PaymentRequirement.DEPOSIT, PaymentRequirement.FULL):
        assert validate_payment_requirement(value) == value


def test_invalid_payment_status_rejected():
    with pytest.raises(QuoteContractError):
        validate_payment_status("kinda-paid")


# ---------------------------------------------------------------------------
# Legacy payment-status normalization
# ---------------------------------------------------------------------------

def test_legacy_payment_status_normalization():
    assert normalize_legacy_payment_status(None) == PaymentStatus.NOT_REQUIRED
    assert normalize_legacy_payment_status("") == PaymentStatus.NOT_REQUIRED
    assert normalize_legacy_payment_status("Not Quoted") == PaymentStatus.NOT_REQUIRED
    assert normalize_legacy_payment_status("Accepted") == PaymentStatus.UNPAID
    assert normalize_legacy_payment_status("Deposit Paid") == PaymentStatus.PARTIALLY_PAID
    assert normalize_legacy_payment_status("Paid in Full") == PaymentStatus.PAID
    assert normalize_legacy_payment_status("paid") == PaymentStatus.PAID


# ---------------------------------------------------------------------------
# Dual-read resolution + quote_status precedence
# ---------------------------------------------------------------------------

def test_canonical_quote_status_wins_over_legacy_request_status():
    # REQUEST has canonical quote_status ACCEPTED but a legacy summary status QUOTE_SENT.
    req = {
        "request_id": "r1", "status": "QUOTE_SENT",
        "quote_status": QuoteStatus.ACCEPTED, "quote_amount_cents": 5000,
        "quote_revision": 2, "currency": "USD",
    }
    assert resolve_commercial_quote_status(req) == QuoteStatus.ACCEPTED
    resolved = resolve_quote_from_record(req)
    assert resolved["source"] == "canonical"
    assert resolved["quote_amount_cents"] == 5000
    assert resolved["quote_revision"] == 2


def test_legacy_fallback_derives_quote_from_pet_pricing():
    req = {"request_id": "r1", "status": "QUOTE_SENT"}
    pet = {"quote_amount": Decimal("45.00"), "payment_status": "Quote Sent"}
    resolved = resolve_quote_from_record(req, pet)
    assert resolved["source"] == "legacy"
    assert resolved["quote_amount_cents"] == 4500
    assert resolved["quote_status"] == QuoteStatus.SENT
    assert resolved["payment_status"] == PaymentStatus.UNPAID


def test_legacy_fallback_accepted_and_not_required():
    req = {"request_id": "r1", "status": "QUOTED"}
    accepted = resolve_quote_from_record(req, {"quote_amount": Decimal("30.00"), "payment_status": "Paid in Full"})
    assert accepted["quote_status"] == QuoteStatus.ACCEPTED
    assert accepted["payment_status"] == PaymentStatus.PAID
    none_req = resolve_quote_from_record({"request_id": "r2", "status": "PENDING_REVIEW"}, {})
    assert none_req["quote_status"] == QuoteStatus.NOT_REQUIRED
    assert none_req["quote_amount_cents"] == 0


def test_request_status_quote_values_are_not_commercially_authoritative():
    # Legacy summary status alone (no acceptance signal) resolves to SENT, never
    # ACCEPTED — RequestStatus is a workflow summary, not commercial authority.
    for summary in ("QUOTE_NEEDED", "QUOTE_SENT", "QUOTED"):
        resolved = resolve_quote_from_record(
            {"request_id": "r", "status": summary},
            {"quote_amount": Decimal("20.00"), "payment_status": "Payment Pending"},
        )
        assert resolved["quote_status"] in (QuoteStatus.SENT, QuoteStatus.DRAFT)
        assert resolved["quote_status"] != QuoteStatus.ACCEPTED


# ---------------------------------------------------------------------------
# Client-safe projection (allowlist + internal exclusion)
# ---------------------------------------------------------------------------

def test_client_projection_allowlist_only():
    req = {
        "request_id": "r1", "quote_status": QuoteStatus.SENT, "quote_amount_cents": 5000,
        "currency": "USD", "payment_requirement": PaymentRequirement.DEPOSIT,
        "deposit_amount_cents": 1000, "quote_notes_client": "Welcome!",
        "service_type": "DROPIN_1HR", "pet_names": "Rex", "selected_dates": ["2026-11-01"],
        # Internal / forbidden fields that must NEVER appear:
        "quote_notes_internal": "margin 40%", "internal_pricing_notes": "cost basis",
        "quote_history": [{"quote_status": "SUPERSEDED"}], "audit_log": [{"x": 1}],
        "stripe_payment_url": "https://stripe", "stripe_checkout_session_id": "cs_1",
        "payment_amount_cents": 5000, "company_id": "tog_and_dogs", "worker_id": "w1",
    }
    projection = build_client_quote_projection(req)
    # Every emitted key is in the allowlist.
    for key in projection:
        assert key in CLIENT_QUOTE_ALLOWLIST
    # No forbidden/internal key leaks.
    for forbidden in CLIENT_QUOTE_FORBIDDEN:
        assert forbidden not in projection
    assert "quote_notes_internal" not in projection
    assert "internal_pricing_notes" not in projection
    assert "quote_history" not in projection
    assert "audit_log" not in projection
    assert "stripe_payment_url" not in projection
    # Client-visible commercial fields present.
    assert projection["quote_amount_cents"] == 5000
    assert projection["quote_notes_client"] == "Welcome!"
    assert projection["payment_required"] is True


def test_client_projection_payment_required_false_when_none_or_zero():
    none_req = build_client_quote_projection({
        "request_id": "r", "quote_status": QuoteStatus.NOT_REQUIRED,
        "quote_amount_cents": 0, "payment_requirement": PaymentRequirement.NONE,
    })
    assert none_req["payment_required"] is False


def test_client_projection_from_legacy_record():
    req = {"request_id": "r1", "status": "QUOTE_SENT", "service_type": "OVERNIGHT",
           "pet_names": "Milo", "selected_dates": ["2026-12-10"]}
    pet = {"quote_amount": Decimal("120.00"), "payment_status": "Quote Sent",
           "quote_notes": "Holiday rate", "internal_pricing_notes": "SHOULD NOT LEAK"}
    projection = build_client_quote_projection(req, pet)
    assert projection["quote_amount_cents"] == 12000
    assert projection["quote_notes_client"] == "Holiday rate"
    assert "internal_pricing_notes" not in projection
    assert projection["service_type"] == "OVERNIGHT"


# ---------------------------------------------------------------------------
# Owner/admin quote mutation: draft / update / send + revision semantics
# ---------------------------------------------------------------------------

def test_first_draft_sets_draft_status_without_revision_bump():
    result = apply_quote_update({}, {"quote_amount_cents": 5000, "quote_notes_client": "hi"}, NOW)
    assert result["quote_status"] == QuoteStatus.DRAFT
    assert result["quote_amount_cents"] == 5000
    assert result.get("quote_revision", 1) == 1
    assert "quote_history" not in result


def test_internal_only_note_change_does_not_create_revision_or_clear_acceptance():
    current = {
        "quote_status": QuoteStatus.ACCEPTED, "quote_revision": 2,
        "quote_amount_cents": 5000, "currency": "USD",
        "quote_accepted_at": "2026-10-01T00:00:00Z", "quote_accepted_revision": 2,
    }
    result = apply_quote_update(current, {"quote_notes_internal": "new internal note"}, NOW)
    assert result["quote_notes_internal"] == "new internal note"
    assert "quote_revision" not in result  # no bump
    assert "quote_history" not in result
    assert "quote_accepted_at" not in result  # acceptance untouched
    assert result.get("quote_status") is None or result.get("quote_status") == QuoteStatus.ACCEPTED


def test_commercial_change_to_sent_quote_creates_revision_and_resets_acceptance():
    current = {
        "quote_status": QuoteStatus.ACCEPTED, "quote_revision": 1,
        "quote_amount_cents": 5000, "currency": "USD",
        "quote_accepted_at": "2026-10-01T00:00:00Z", "quote_accepted_revision": 1,
    }
    result = apply_quote_update(current, {"quote_amount_cents": 6000}, NOW)
    assert result["quote_revision"] == 2
    assert result["quote_status"] == QuoteStatus.DRAFT
    assert result["quote_amount_cents"] == 6000
    assert result["quote_accepted_at"] is None
    assert result["quote_accepted_revision"] is None
    # Prior revision snapshotted as SUPERSEDED (history-only).
    assert len(result["quote_history"]) == 1
    assert result["quote_history"][0]["quote_status"] == QuoteStatus.SUPERSEDED
    assert result["quote_history"][0]["quote_amount_cents"] == 5000


def test_client_note_change_is_commercial_revision():
    current = {"quote_status": QuoteStatus.SENT, "quote_revision": 1, "quote_amount_cents": 5000}
    result = apply_quote_update(current, {"quote_notes_client": "updated client note"}, NOW)
    assert result["quote_revision"] == 2
    assert result["quote_status"] == QuoteStatus.DRAFT


def test_apply_quote_update_rejects_invalid_payment_requirement():
    with pytest.raises(QuoteContractError):
        apply_quote_update({"quote_status": QuoteStatus.DRAFT},
                           {"payment_requirement": "LATER"}, NOW)


def test_apply_quote_update_does_not_mutate_input():
    current = {"quote_status": QuoteStatus.SENT, "quote_revision": 1, "quote_amount_cents": 5000}
    snapshot = dict(current)
    apply_quote_update(current, {"quote_amount_cents": 7000}, NOW)
    assert current == snapshot


def test_send_transitions_draft_to_sent():
    result = apply_quote_send({"quote_status": QuoteStatus.DRAFT, "quote_amount_cents": 5000}, NOW)
    assert result["quote_status"] == QuoteStatus.SENT
    assert result["quote_sent_at"] == NOW


def test_send_rejects_zero_amount_and_wrong_status():
    with pytest.raises(QuoteContractError):
        apply_quote_send({"quote_status": QuoteStatus.DRAFT, "quote_amount_cents": 0}, NOW)
    with pytest.raises(QuoteContractError):
        apply_quote_send({"quote_status": QuoteStatus.ACCEPTED, "quote_amount_cents": 5000}, NOW)


def test_quote_operations_never_emit_approved_or_request_status():
    # No quote operation output may approve the booking or set a RequestStatus.
    update = apply_quote_update({}, {"quote_amount_cents": 5000}, NOW)
    send = apply_quote_send({"quote_status": QuoteStatus.DRAFT, "quote_amount_cents": 5000}, NOW)
    for result in (update, send):
        assert "status" not in result  # never writes RequestStatus
        assert "APPROVED" not in json.dumps(result)


# ---------------------------------------------------------------------------
# Booking-approval predicate (R4) — no implicit approval
# ---------------------------------------------------------------------------

def test_predicate_no_quote_required_satisfied():
    ok, _ = evaluate_booking_approval_predicate(
        QuoteStatus.NOT_REQUIRED, PaymentRequirement.NONE, PaymentStatus.NOT_REQUIRED, 0)
    assert ok is True


def test_predicate_quote_required_not_accepted_blocked():
    ok, reason = evaluate_booking_approval_predicate(
        QuoteStatus.SENT, PaymentRequirement.NONE, PaymentStatus.UNPAID, 5000)
    assert ok is False
    assert "not accepted" in reason


def test_predicate_accepted_none_payment_satisfied():
    ok, _ = evaluate_booking_approval_predicate(
        QuoteStatus.ACCEPTED, PaymentRequirement.NONE, PaymentStatus.UNPAID, 5000)
    assert ok is True


def test_predicate_deposit_requires_partial_or_paid():
    assert evaluate_booking_approval_predicate(
        QuoteStatus.ACCEPTED, PaymentRequirement.DEPOSIT, PaymentStatus.PARTIALLY_PAID, 5000)[0] is True
    assert evaluate_booking_approval_predicate(
        QuoteStatus.ACCEPTED, PaymentRequirement.DEPOSIT, PaymentStatus.PAID, 5000)[0] is True
    assert evaluate_booking_approval_predicate(
        QuoteStatus.ACCEPTED, PaymentRequirement.DEPOSIT, PaymentStatus.UNPAID, 5000)[0] is False


def test_predicate_full_requires_paid_and_partial_never_satisfies_full():
    assert evaluate_booking_approval_predicate(
        QuoteStatus.ACCEPTED, PaymentRequirement.FULL, PaymentStatus.PAID, 5000)[0] is True
    # PARTIALLY_PAID must NEVER satisfy FULL.
    ok, reason = evaluate_booking_approval_predicate(
        QuoteStatus.ACCEPTED, PaymentRequirement.FULL, PaymentStatus.PARTIALLY_PAID, 5000)
    assert ok is False
    assert "full payment required" in reason


def test_predicate_authorized_waiver_satisfies_payment():
    ok, reason = evaluate_booking_approval_predicate(
        QuoteStatus.ACCEPTED, PaymentRequirement.FULL, PaymentStatus.UNPAID, 5000, payment_waived=True)
    assert ok is True
    assert "waived" in reason


def test_predicate_is_read_only_eligibility_not_an_approval():
    # The predicate returns a boolean/reason and never performs or implies the
    # APPROVED transition (acceptance does not auto-approve — approved decision 13).
    ok, reason = evaluate_booking_approval_predicate(
        QuoteStatus.ACCEPTED, PaymentRequirement.NONE, PaymentStatus.UNPAID, 5000)
    assert isinstance(ok, bool)
    assert isinstance(reason, str)


def test_predicate_rejects_invalid_payment_requirement():
    # An invalid payment_requirement is rejected (not silently treated as satisfied),
    # once the quote condition is met so the payment branch is reached.
    with pytest.raises(QuoteContractError):
        evaluate_booking_approval_predicate(
            QuoteStatus.ACCEPTED, "SOMEDAY", PaymentStatus.PAID, 5000)


def test_predicate_unknown_payment_status_fails_closed():
    # An unrecognized payment_status must never satisfy a payment requirement
    # (fail-closed): it is treated as "not paid", blocking approval eligibility.
    ok, _ = evaluate_booking_approval_predicate(
        QuoteStatus.ACCEPTED, PaymentRequirement.FULL, "garbage", 5000)
    assert ok is False


# ---------------------------------------------------------------------------
# Additional approved-contract boundary cases (review hardening)
# ---------------------------------------------------------------------------

def test_canonical_wins_even_when_legacy_pet_present_and_disagrees():
    # Both canonical and legacy signals present and DISAGREEING: canonical wins
    # for every commercial field (amount, status, revision), legacy is ignored.
    req = {
        "request_id": "r1", "status": "QUOTE_SENT",
        "quote_status": QuoteStatus.ACCEPTED, "quote_amount_cents": 8000,
        "quote_revision": 3, "currency": "USD",
    }
    legacy_pet = {"quote_amount": Decimal("10.00"), "payment_status": "Not Quoted"}
    resolved = resolve_quote_from_record(req, legacy_pet)
    assert resolved["source"] == "canonical"
    assert resolved["quote_status"] == QuoteStatus.ACCEPTED  # not NOT_REQUIRED from legacy
    assert resolved["quote_amount_cents"] == 8000            # not 1000 from legacy
    assert resolved["quote_revision"] == 3
    assert resolve_commercial_quote_status(req, legacy_pet) == QuoteStatus.ACCEPTED


def test_resend_from_sent_is_idempotent_and_keeps_revision():
    # Re-sending an already-SENT quote (no commercial change) is benign: it stays
    # SENT, does not bump the revision, and never approves.
    result = apply_quote_send(
        {"quote_status": QuoteStatus.SENT, "quote_amount_cents": 5000, "quote_revision": 2}, NOW)
    assert result["quote_status"] == QuoteStatus.SENT
    assert result["quote_revision"] == 2
    assert "status" not in result


def test_half_cent_rounds_down_below_boundary():
    # Explicit sub-half-cent rounding: 10.004 -> 1000 (down), complementing the
    # existing 10.005 -> 1001 (half-up) boundary test.
    assert to_cents("10.004") == 1000


def test_negative_deposit_rejected():
    with pytest.raises(QuoteContractError):
        apply_quote_update({"quote_status": QuoteStatus.DRAFT},
                           {"deposit_amount_cents": -500}, NOW)


# ---------------------------------------------------------------------------
# M4-B1 — canonical stored-cents read normalization (DynamoDB Decimal defect)
# ---------------------------------------------------------------------------
#
# Root cause of the Android "$20,000.00" (expected "$200.00") defect: canonical
# ``*_cents`` fields are stored as integer cents, but DynamoDB returns every stored
# number as a Decimal. The canonical read path fed that Decimal through the generic
# ``to_cents`` (which treats a non-int as MAJOR units and multiplies ×100), so a
# stored ``Decimal('20000')`` became ``2_000_000`` and the correct ÷100 mobile
# formatter rendered "$20,000.00". ``normalize_stored_cents`` preserves already-cents
# magnitude for both int and Decimal, while the generic ``to_cents`` (used for inbound
# caller values) and ``legacy_quote_amount_to_cents`` (used for legacy MAJOR-unit PET
# fields) keep their distinct semantics.


def test_normalize_stored_cents_int_and_decimal_are_identical():
    # The core proof: int cents and DynamoDB-style Decimal cents normalize the SAME,
    # with NO ×100 scaling of the Decimal.
    assert normalize_stored_cents(20000) == 20000
    assert normalize_stored_cents(Decimal("20000")) == 20000
    assert normalize_stored_cents(20000) == normalize_stored_cents(Decimal("20000"))
    assert normalize_stored_cents(0) == 0
    assert normalize_stored_cents(Decimal("0")) == 0
    assert normalize_stored_cents(None) == 0


def test_normalize_stored_cents_rejects_non_integral_and_bad_input():
    # Cents are whole units; a fractional stored "cents" value is a contract breach.
    with pytest.raises(QuoteContractError):
        normalize_stored_cents(Decimal("200.5"))
    with pytest.raises(QuoteContractError):
        normalize_stored_cents(-1)
    with pytest.raises(QuoteContractError):
        normalize_stored_cents(Decimal("-1"))
    with pytest.raises(QuoteContractError):
        normalize_stored_cents(True)
    with pytest.raises(QuoteContractError):
        normalize_stored_cents("not-money")


def test_generic_to_cents_major_unit_semantics_are_unchanged():
    # Guard: the generic to_cents must STILL treat a non-int as MAJOR units (×100).
    # This is what makes a GLOBAL to_cents change unsafe, so the two helpers must
    # remain distinct.
    assert to_cents(Decimal("12.34")) == 1234      # major units -> cents
    assert to_cents(20000) == 20000                # bare int already cents
    assert to_cents(Decimal("20000")) == 2000000   # major units ×100 (unchanged)


def test_legacy_major_unit_compatibility_preserved():
    # LEGACY_MAJOR_UNIT_COMPATIBILITY: the explicit legacy converter still turns
    # MAJOR-unit Decimal/str into cents (×100), untouched by the M4-B1 fix.
    assert legacy_quote_amount_to_cents(Decimal("200.00")) == 20000
    assert legacy_quote_amount_to_cents("12.50") == 1250
    assert legacy_quote_amount_to_cents(Decimal("45.00")) == 4500
    assert legacy_quote_amount_to_cents(None) == 0


def test_resolve_canonical_decimal_amount_not_scaled():
    # Canonical SENT record whose amounts arrive as DynamoDB Decimals must resolve to
    # the SAME integer cents as plain-int input — not ×100.
    req_decimal = {
        "request_id": "r1", "quote_status": QuoteStatus.SENT, "quote_revision": 1,
        "quote_amount_cents": Decimal("20000"), "currency": "USD",
        "deposit_amount_cents": Decimal("5000"),
        "payment_requirement": PaymentRequirement.NONE,
    }
    resolved = resolve_quote_from_record(req_decimal)
    assert resolved["quote_amount_cents"] == 20000      # $200.00, NOT 2_000_000
    assert resolved["quote_amount_cents"] != 2000000
    assert resolved["deposit_amount_cents"] == 5000     # $50.00, NOT 500_000

    # Int-typed canonical record resolves identically.
    req_int = dict(req_decimal, quote_amount_cents=20000, deposit_amount_cents=5000)
    resolved_int = resolve_quote_from_record(req_int)
    assert resolved_int["quote_amount_cents"] == resolved["quote_amount_cents"]
    assert resolved_int["deposit_amount_cents"] == resolved["deposit_amount_cents"]


def test_client_projection_decimal_amount_renders_as_200_dollars_worth_of_cents():
    # Projection-level regression at the exact layer the M4-B defect occurred: the
    # client-safe projection of a canonical SENT quote stored as Decimal('20000')
    # must expose quote_amount_cents == 20000 (mobile ÷100 -> $200.00), never
    # 2_000_000 (which rendered $20,000.00).
    req = {
        "request_id": "req-m4", "quote_status": QuoteStatus.SENT, "quote_revision": 1,
        "quote_amount_cents": Decimal("20000"), "currency": "USD",
        "deposit_amount_cents": Decimal("0"),
        "payment_requirement": PaymentRequirement.NONE,
        "service_type": "WALK_20MIN", "pet_names": "Rex",
    }
    projection = build_client_quote_projection(req)
    assert projection["quote_amount_cents"] == 20000
    assert projection["quote_amount_cents"] != 2000000
    assert projection["currency"] == "USD"
    assert projection["payment_required"] is False


def test_history_snapshot_decimal_amount_not_scaled():
    # A commercial change to a SENT quote stored as Decimal snapshots the PRIOR amount
    # into quote_history; that snapshot must keep stored-cents magnitude (not ×100).
    current = {
        "quote_status": QuoteStatus.SENT, "quote_revision": 1,
        "quote_amount_cents": Decimal("20000"), "currency": "USD",
    }
    result = apply_quote_update(current, {"quote_amount_cents": 25000}, NOW)
    assert result["quote_revision"] == 2
    assert result["quote_history"][0]["quote_amount_cents"] == 20000  # not 2_000_000
    assert result["quote_amount_cents"] == 25000  # inbound int stays cents


def test_dirty_check_no_false_commercial_change_on_decimal_roundtrip():
    # Re-submitting the SAME amount a client already has (stored Decimal vs inbound
    # int, same value) must NOT be seen as a commercial change (which would wrongly
    # bump the revision and reset acceptance). Pre-fix, to_cents(Decimal) ×100 made
    # every edit look changed.
    current = {
        "quote_status": QuoteStatus.ACCEPTED, "quote_revision": 3,
        "quote_amount_cents": Decimal("20000"), "currency": "USD",
        "quote_accepted_at": "2026-10-06T00:00:00Z", "quote_accepted_revision": 3,
    }
    # Only an internal-note change; amount resubmitted identically as int cents.
    result = apply_quote_update(
        current, {"quote_amount_cents": 20000, "quote_notes_internal": "n"}, NOW)
    assert "quote_revision" not in result       # no bump
    assert "quote_history" not in result        # nothing superseded
    assert "quote_accepted_at" not in result    # acceptance preserved


def test_apply_quote_send_decimal_amount_allowed():
    # A DRAFT whose stored amount is a Decimal must be sendable (amount read as
    # stored cents, > 0).
    result = apply_quote_send(
        {"quote_status": QuoteStatus.DRAFT, "quote_amount_cents": Decimal("20000")}, NOW)
    assert result["quote_status"] == QuoteStatus.SENT
