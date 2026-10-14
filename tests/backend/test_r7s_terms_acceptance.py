"""
Release 7S: Unit tests for Terms of Use and Privacy Policy acceptance validation.

Covers the CUSTOMER_INTAKE path in intake_handler.handler().
The acceptance block is only executed when workflow_type == CUSTOMER_INTAKE,
i.e. public submissions via POST /requests (not /client/requests portal path
and not admin-created bookings).

Admin-created bookings and portal-path (VISIT_BOOKING) submissions bypass
acceptance validation by design — this is documented by an exemption test below.

Test isolation (Gate C3b.3a / V3c)
----------------------------------
The public-intake path runs a tenant-resolution + entitlement + DB preamble
BEFORE the terms/privacy acceptance block:

    require_active_tenant -> resolve_public_intake_tenant -> (acceptance block)
    -> client-count table.query -> entitlement gates -> put_item

Those boundaries reach live AWS in CI, where the handler correctly fails closed
with PUBLIC_INTAKE_TENANT_RESOLUTION_FAILED and the outer handler returns 500 —
masking the real 200/400 acceptance outcomes. The `intake_isolation` fixture
below (reused from the V3a/V3b pattern) models the "active tenant resolves,
limits not breached" state so the handler reaches the REAL acceptance
validation. It never mocks the acceptance logic itself and never fabricates a
success response: put_item/sfn stay under mock_db/mock_sfn, and every
accept/reject assertion still executes against the handler's own logic.
"""
import json
import pytest
from contextlib import ExitStack
from unittest.mock import patch, MagicMock
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


@pytest.fixture
def no_network():
    """Fail loudly if any test in this module reaches a real AWS/boto3 call.

    Scoped safety net for THIS module only (not autouse, not global): if an
    unmocked DynamoDB/boto3 operation slips through, the botocore HTTP
    transport raises instead of silently returning an error the handler would
    convert into a misleading 500 (which is exactly how the acceptance outcomes
    were being masked before this isolation).
    """
    def _blocked(*args, **kwargs):
        raise AssertionError(
            "Unmocked AWS network call attempted during an isolated terms-"
            "acceptance test. Add an explicit scoped mock for the operation the "
            "handler reached."
        )

    with patch('botocore.httpsession.URLLib3Session.send', _blocked):
        yield


@pytest.fixture
def intake_isolation(no_network):
    """Explicit, scoped isolation of the public-intake tenant-resolution and
    entitlement/DB preamble that runs BEFORE and AFTER the acceptance block.

    Models the documented 'active tenant resolves, limits not breached' state
    so the handler reaches its REAL terms/privacy acceptance validation without
    touching AWS. Patches target the exact boundaries the public-intake path
    calls: common.auth / common.entitlement are imported lazily inside
    handler(), so they are patched at their source modules; `table` is bound at
    module import (from common.db import ... table) so it is patched on the
    handler module.

    The acceptance validation logic itself is NOT mocked. Rejected submissions
    still return the handler's genuine 400 before any put_item/table.query, and
    accepted submissions still flow through the real record build.

    Yields the resolver mock so a test may assert tenant resolution occurred.
    """
    COMPANY_ID = "tog_and_dogs"
    mock_table = MagicMock(name="intake_handler.table")
    # No pre-existing client with the test email -> exercises the new-client
    # entitlement path, which is then allowed by the check_limit patch below.
    mock_table.query.return_value = {"Items": []}

    with ExitStack() as stack:
        resolver = stack.enter_context(
            patch('common.auth.resolve_public_intake_tenant', return_value=COMPANY_ID)
        )
        # Active tenant: require_active_tenant returns None (no block).
        stack.enter_context(
            patch('common.entitlement.require_active_tenant', return_value=None)
        )
        stack.enter_context(patch('handlers.intake_handler.table', mock_table))
        # Entitlement gates: allow (no limit breach) without touching DynamoDB.
        stack.enter_context(patch('common.entitlement.check_limit', return_value=None))
        stack.enter_context(patch('common.entitlement.get_active_client_count', return_value=0))
        stack.enter_context(patch('common.entitlement.get_monthly_bookings_count', return_value=0))
        stack.enter_context(patch('common.entitlement.increment_monthly_bookings', return_value=None))
        yield resolver


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

def test_valid_acceptance_succeeds(mock_db, mock_sfn, intake_isolation):
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
    # Record ownership / classification remain correct under isolation.
    assert saved["company_id"] == "tog_and_dogs"
    assert saved["workflow_type"] == "CUSTOMER_INTAKE"
    assert saved["status"] == "PENDING_REVIEW"


# ---------------------------------------------------------------------------
# accepted_terms failures
# ---------------------------------------------------------------------------

def test_missing_accepted_terms_rejected(mock_db, intake_isolation):
    """accepted_terms absent → 400."""
    event = _public_intake_event({"accepted_terms": None})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    assert "Terms of Use" in resp["body"] or "terms" in resp["body"].lower()
    mock_db.assert_not_called()


def test_accepted_terms_false_rejected(mock_db, intake_isolation):
    """accepted_terms=False → 400."""
    event = _public_intake_event({"accepted_terms": False})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_accepted_terms_string_truthy_rejected(mock_db, intake_isolation):
    """accepted_terms='true' (string, not bool True) → 400.
    The handler checks `is not True`, so only the boolean True passes."""
    event = _public_intake_event({"accepted_terms": "true"})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


# ---------------------------------------------------------------------------
# accepted_privacy failures
# ---------------------------------------------------------------------------

def test_missing_accepted_privacy_rejected(mock_db, intake_isolation):
    """accepted_privacy absent → 400."""
    event = _public_intake_event({"accepted_privacy": None})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_accepted_privacy_false_rejected(mock_db, intake_isolation):
    """accepted_privacy=False → 400."""
    event = _public_intake_event({"accepted_privacy": False})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


# ---------------------------------------------------------------------------
# terms_version failures
# ---------------------------------------------------------------------------

def test_missing_terms_version_rejected(mock_db, intake_isolation):
    """terms_version absent (empty string) → 400."""
    event = _public_intake_event({"terms_version": ""})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_null_terms_version_rejected(mock_db, intake_isolation):
    """terms_version=None → 400."""
    event = _public_intake_event({"terms_version": None})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_oversized_terms_version_rejected(mock_db, intake_isolation):
    """terms_version longer than 20 chars → 400."""
    event = _public_intake_event({"terms_version": "v" * 21})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_terms_version_at_max_length_accepted(mock_db, mock_sfn, intake_isolation):
    """terms_version exactly 20 chars → 200 (boundary: max allowed)."""
    event = _public_intake_event({"terms_version": "v" * 20})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    mock_db.assert_called_once()
    saved = mock_db.call_args[0][0]
    assert saved["terms_version"] == "v" * 20


# ---------------------------------------------------------------------------
# privacy_version failures
# ---------------------------------------------------------------------------

def test_missing_privacy_version_rejected(mock_db, intake_isolation):
    """privacy_version absent (empty string) → 400."""
    event = _public_intake_event({"privacy_version": ""})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_null_privacy_version_rejected(mock_db, intake_isolation):
    """privacy_version=None → 400."""
    event = _public_intake_event({"privacy_version": None})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_oversized_privacy_version_rejected(mock_db, intake_isolation):
    """privacy_version longer than 20 chars → 400."""
    event = _public_intake_event({"privacy_version": "v" * 21})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()


def test_privacy_version_at_max_length_accepted(mock_db, mock_sfn, intake_isolation):
    """privacy_version exactly 20 chars → 200 (boundary: max allowed)."""
    event = _public_intake_event({"privacy_version": "v" * 20})
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 200
    mock_db.assert_called_once()
    saved = mock_db.call_args[0][0]
    assert saved["privacy_version"] == "v" * 20


# ---------------------------------------------------------------------------
# Exemption: admin-created bookings bypass acceptance validation
# ---------------------------------------------------------------------------

def test_admin_created_booking_bypasses_acceptance(mock_db):
    """Admin-created bookings (source=admin_created) do NOT go through the
    acceptance validation block — they use a separate handler path.
    This test documents and verifies that exemption is in place.

    get_effective_role is imported locally inside _handle_admin_created_booking
    from common.auth, so we patch it there (not at intake_handler module level).

    This case has its own self-contained isolation (it patches get_item,
    put_item, sfn and boto3.client), so it intentionally does NOT use the
    intake_isolation fixture — the admin-created path does not call
    resolve_public_intake_tenant.
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
