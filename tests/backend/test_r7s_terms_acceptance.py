"""
Release 7S: Unit tests for Terms of Use and Privacy Policy acceptance validation.

Covers the CUSTOMER_INTAKE path in intake_handler.handler().
The acceptance block is only executed when workflow_type == CUSTOMER_INTAKE,
i.e. public submissions via POST /requests (not /client/requests portal path
and not admin-created bookings).

Admin-created bookings and portal-path (VISIT_BOOKING) submissions bypass
acceptance validation by design — this is documented by an exemption test below.
"""
import json
import pytest
from unittest.mock import patch
from handlers.intake_handler import handler as intake_handler

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    with patch('handlers.intake_handler.put_item') as mock_put:
        mock_put.return_value = True
        yield mock_put


@pytest.fixture
def mock_sfn():
    with patch('handlers.intake_handler.sfn') as mock_sfn_client:
        yield mock_sfn_client


def _public_intake_event(overrides=None):
    """Build a minimal valid public-intake (CUSTOMER_INTAKE) event body."""
    body = {
        "client_name": "Test Client",
        "client_email": "test@example.com",
        "start_date": "2026-06-01",
        "pet_names": "Biscuit",
        "accepted_terms": True,
        "accepted_privacy": True,
        "terms_version": "1.0",
        "privacy_version": "1.0",
    }
    if overrides:
        body.update(overrides)
    # No path key → public path → CUSTOMER_INTAKE
    return {"body": json.dumps(body)}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_valid_acceptance_succeeds(mock_db, mock_sfn):
    """accepted_terms=True, accepted_privacy=True, valid versions → 200."""
    event = _public_intake_event()
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "PENDING_REVIEW"
    mock_db.assert_called_once()

    # Verify acceptance fields persisted to DB item
    saved = mock_db.call_args[0][0]
    assert saved["accepted_terms"] is True
    assert saved["accepted_privacy"] is True
    assert saved["terms_version"] == "1.0"
    assert saved["privacy_version"] == "1.0"
    assert "accepted_at" in saved
    assert saved["source"] == "public_intake"


# ---------------------------------------------------------------------------
# accepted_terms failures
# ---------------------------------------------------------------------------

def test_missing_accepted_terms_rejected(mock_db):
    """accepted_terms absent → 400."""
    event = _public_intake_event({"accepted_terms": None})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    assert "Terms of Use" in resp["body"] or "terms" in resp["body"].lower()
    mock_db.assert_not_called()


def test_accepted_terms_false_rejected(mock_db):
    """accepted_terms=False → 400."""
    event = _public_intake_event({"accepted_terms": False})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_accepted_terms_string_truthy_rejected(mock_db):
    """accepted_terms='true' (string, not bool True) → 400.
    The handler checks `is not True`, so only the boolean True passes."""
    event = _public_intake_event({"accepted_terms": "true"})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


# ---------------------------------------------------------------------------
# accepted_privacy failures
# ---------------------------------------------------------------------------

def test_missing_accepted_privacy_rejected(mock_db):
    """accepted_privacy absent → 400."""
    event = _public_intake_event({"accepted_privacy": None})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_accepted_privacy_false_rejected(mock_db):
    """accepted_privacy=False → 400."""
    event = _public_intake_event({"accepted_privacy": False})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


# ---------------------------------------------------------------------------
# terms_version failures
# ---------------------------------------------------------------------------

def test_missing_terms_version_rejected(mock_db):
    """terms_version absent (empty string) → 400."""
    event = _public_intake_event({"terms_version": ""})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_null_terms_version_rejected(mock_db):
    """terms_version=None → 400."""
    event = _public_intake_event({"terms_version": None})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_oversized_terms_version_rejected(mock_db):
    """terms_version longer than 20 chars → 400."""
    event = _public_intake_event({"terms_version": "v" * 21})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_terms_version_at_max_length_accepted(mock_db, mock_sfn):
    """terms_version exactly 20 chars → 200 (boundary: max allowed)."""
    event = _public_intake_event({"terms_version": "v" * 20})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    mock_db.assert_called_once()


# ---------------------------------------------------------------------------
# privacy_version failures
# ---------------------------------------------------------------------------

def test_missing_privacy_version_rejected(mock_db):
    """privacy_version absent (empty string) → 400."""
    event = _public_intake_event({"privacy_version": ""})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_null_privacy_version_rejected(mock_db):
    """privacy_version=None → 400."""
    event = _public_intake_event({"privacy_version": None})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_oversized_privacy_version_rejected(mock_db):
    """privacy_version longer than 20 chars → 400."""
    event = _public_intake_event({"privacy_version": "v" * 21})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_privacy_version_at_max_length_accepted(mock_db, mock_sfn):
    """privacy_version exactly 20 chars → 200 (boundary: max allowed)."""
    event = _public_intake_event({"privacy_version": "v" * 20})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    mock_db.assert_called_once()


# ---------------------------------------------------------------------------
# Exemption: admin-created bookings bypass acceptance validation
# ---------------------------------------------------------------------------

def test_admin_created_booking_bypasses_acceptance(mock_db):
    """Admin-created bookings (source=admin_created) do NOT go through the
    acceptance validation block — they use a separate handler path.
    This test documents and verifies that exemption is in place.

    get_effective_role is imported locally inside _handle_admin_created_booking
    from common.auth, so we patch it there (not at intake_handler module level).
    """
    with patch('common.auth.get_effective_role', return_value='owner'), \
         patch('common.auth.get_claims', return_value={'email': 'admin@example.com'}), \
         patch('common.auth.get_current_company_id', return_value='co-123'), \
         patch('handlers.intake_handler.get_item', return_value={
             'company_id': 'co-123',
             'client_id': 'client-abc',
         }), \
         patch('handlers.intake_handler.put_item', return_value=True), \
         patch('handlers.intake_handler.sfn'), \
         patch('boto3.client'):  # suppress Lambda/calendar side-effects

        event = {
            "body": json.dumps({
                "source": "admin_created",
                "client_id": "client-abc",
                "client_name": "Admin Client",
                "start_date": "2026-06-01",
                "pet_names": "Max",
                # Deliberately omit accepted_terms / accepted_privacy / versions
            }),
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "email": "admin@example.com",
                        "custom:role": "owner",
                        "sub": "admin-sub-123"
                    }
                }
            }
        }
        resp = intake_handler(event, None)
        # Should NOT return the acceptance error
        assert "Terms of Use and Privacy Policy acceptance is required" not in resp.get("body", "")
