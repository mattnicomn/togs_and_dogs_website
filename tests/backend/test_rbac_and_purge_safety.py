"""RBAC and purge-safety tests for the admin handler.

Test isolation (Gate C3b.3e / V3e)
----------------------------------
Every route here first passes through the handler's active-tenant precondition
(require_active_tenant -> common.entitlement._get_entitlement_safely ->
common.db.get_item -> billing._build_entitlement) BEFORE the route's real role
gates run. The earlier version of this module mocked common.db.get_item as a
bare MagicMock, so _build_entitlement received a MagicMock "tenant" and the
billing date helpers called datetime.fromisoformat(<MagicMock>), raising
TypeError (which billing only guards for ValueError/AttributeError). That
propagated to the handler's outer except and returned 500, masking the real
403/200 authorization outcomes.

The fix is TEST-ONLY and deliberately minimal: the get_item mock now returns a
realistic ACTIVE tenant-metadata dict so the REAL entitlement logic executes
and require_active_tenant returns None (no block) without touching AWS. The
real role gates, tenant-ownership guard, purge status gate, and active-record
DELETE protection are NOT mocked — they continue to run and decide every
outcome. For the DELETE-path tests, the event carries a valid custom:company_id
and the records carry a matching company_id so the handler's real tenant-
ownership guard is SATISFIED (not bypassed).
"""
import pytest
import json
from unittest.mock import patch, MagicMock, ANY
from handlers.admin_handler import handler as admin_handler

# Company used consistently across claims and records so the handler's real
# tenant-ownership guard (admin_handler: caller custom:company_id must equal the
# resolved record company_id) is satisfied rather than bypassed.
TEST_COMPANY = "tog_and_dogs"

# Realistic ACTIVE tenant metadata. Returning this from the entitlement lookup
# lets billing._build_entitlement / TenantEntitlement run for real: no date
# fields -> the fromisoformat helpers short-circuit, status 'active' ->
# is_access_allowed True, is_blocked False -> require_active_tenant returns None.
ACTIVE_TENANT_METADATA = {
    "PK": f"TENANT#{TEST_COMPANY}",
    "SK": "METADATA",
    "company_id": TEST_COMPANY,
    "subscription_tier": "starter",
    "subscription_status": "active",
    "is_active": True,
}

# --- Fixtures & Mocks ---

@pytest.fixture
def no_network():
    """Module-local, non-autouse guard: fail loudly if any test reaches a real
    AWS/boto3 call. Ensures the active-tenant precondition and all role/ownership
    logic run entirely against in-memory mocks, never the network."""
    def _blocked(*args, **kwargs):
        raise AssertionError(
            "Unmocked AWS network call attempted during an isolated RBAC/purge "
            "test. Add an explicit scoped mock for the operation the handler reached."
        )
    with patch('botocore.httpsession.URLLib3Session.send', _blocked):
        yield


@pytest.fixture
def mock_db(no_network):
    """Mock the DynamoDB boundary only.

    get_item returns realistic ACTIVE tenant metadata for the entitlement
    precondition lookup (so the REAL billing/entitlement logic runs and allows
    the request to proceed to the real role gates). table is a MagicMock so the
    purge path's delete_item calls can be asserted. No authorization logic is
    mocked here.
    """
    with patch('common.db.table') as mock_table:
        with patch('common.db.get_item') as mock_get:
            mock_get.return_value = dict(ACTIVE_TENANT_METADATA)
            yield {"table": mock_table, "get_item": mock_get}

@pytest.fixture
def mock_audit():
    with patch('handlers.admin_handler.log_action') as mock_log:
        yield mock_log

# --- Events ---

def create_event(role, body_dict=None, path="/admin/requests", method="POST",
                 company_id=None):
    claims = {"email": f"{role.lower()}@test.com"}
    if role == "Admin":
        claims["cognito:groups"] = "Admin"
    elif role == "Owner":
        claims["cognito:groups"] = "owner"
    elif role == "Staff":
        claims["cognito:groups"] = "Staff"
    elif role == "Client":
        claims["cognito:groups"] = "Client"

    # Only attach a tenant claim when a test explicitly needs the handler's real
    # tenant-ownership guard to be satisfied (DELETE/ARCHIVE soft-transition path).
    if company_id is not None:
        claims["custom:company_id"] = company_id

    return {
        "requestContext": {
            "authorizer": {
                "claims": claims
            }
        },
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body_dict or {})
    }

# --- RBAC Tests ---

def test_admin_access_allowed(mock_db, mock_audit):
    event = create_event("Admin", {"action": "LIST"})
    resp = admin_handler(event, None)
    assert resp["statusCode"] != 403

def test_staff_access_denied_to_admin_requests(mock_db, mock_audit):
    event = create_event("Staff", {"action": "DELETE", "PK": "REQ#1", "SK": "CLIENT#1"})
    resp = admin_handler(event, None)
    # Genuine 403 from the handler's real lifecycle-action role gate
    # (action in [DELETE/...] and role not in [owner, admin]), reached only
    # because the entitlement precondition now resolves cleanly.
    assert resp["statusCode"] == 403
    assert "Forbidden" in resp["body"]
    # Denied request performs zero destructive side effects.
    mock_db["table"].delete_item.assert_not_called()

def test_client_access_denied_to_admin_requests(mock_db, mock_audit):
    event = create_event("Client", {"action": "DELETE", "PK": "REQ#1", "SK": "CLIENT#1"})
    resp = admin_handler(event, None)
    # Genuine 403 from the real outer POST /admin/requests role gate
    # (role not in [owner, admin, staff]).
    assert resp["statusCode"] == 403
    assert "Forbidden" in resp["body"]
    mock_db["table"].delete_item.assert_not_called()

# --- Purge Safety Tests ---

def test_purge_safety_requires_deleted_status(mock_db, mock_audit):
    """Non-DELETED records must be skipped (not purged) by the bulk-compatible API."""
    mock_record = {"PK": "REQ#1", "SK": "CLIENT#1", "status": "APPROVED"}

    event = create_event("Admin", {"action": "PURGE", "PK": "REQ#1", "SK": "CLIENT#1"})

    # Patch _resolve_admin_record to return the mock record with correct keys
    with patch('handlers.admin_handler._resolve_admin_record', return_value=(mock_record, "REQ#1", "CLIENT#1")):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        # Record was skipped (not purged) because status is APPROVED
        assert body["skipped"] >= 1
        assert body["success"] == 0
        # Verify the skip reason mentions the status
        assert any("APPROVED" in f.get("reason", "") for f in body.get("failures", []))
        # Table delete_item should NOT have been called
        mock_db["table"].delete_item.assert_not_called()

def test_purge_safety_allows_deleted_status(mock_db, mock_audit):
    """DELETED records should be purged successfully."""
    mock_record = {"PK": "REQ#1", "SK": "CLIENT#1", "status": "DELETED", "client_name": "Test"}

    event = create_event("Admin", {"action": "PURGE", "PK": "REQ#1", "SK": "CLIENT#1"})

    with patch('handlers.admin_handler._resolve_admin_record', return_value=(mock_record, "REQ#1", "CLIENT#1")):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        # Record was successfully purged
        assert body["success"] == 1
        assert body["skipped"] == 0
        # Table delete_item should have been called
        mock_db["table"].delete_item.assert_called_once_with(Key={'PK': 'REQ#1', 'SK': 'CLIENT#1'})
        # Verify audit log was written
        mock_audit.assert_called_with(ANY, 'PURGE', 'REQ#1', 'CLIENT#1',
                                      previous_status='DELETED', bulk_op_id=None)

# --- Malformed Record Cleanup Tests ---

def test_admin_can_trash_malformed_record(mock_db, mock_audit):
    """Malformed records (missing status) can be moved to Trash.

    DELETE path: the record carries a company_id matching the caller's
    custom:company_id so the real tenant-ownership guard is satisfied.
    """
    mock_record = {"PK": "REQ#MALFORMED", "SK": "CLIENT#1",
                   "client_name": "Bad Data", "company_id": TEST_COMPANY}

    event = create_event("Admin", {"action": "DELETE", "PK": "REQ#MALFORMED", "SK": "CLIENT#1"},
                         company_id=TEST_COMPANY)

    with patch('handlers.admin_handler._resolve_admin_record', return_value=(mock_record, "REQ#MALFORMED", "CLIENT#1")), \
         patch('handlers.admin_handler.update_status', return_value=True):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["success"] >= 1
        mock_audit.assert_called()

# --- Bulk Purge Safety Tests ---

def test_bulk_purge_filters_non_deleted(mock_db, mock_audit):
    """Bulk purge must skip non-DELETED records and only purge DELETED ones."""
    items = {
        "REQ#DELETED": ({"PK": "REQ#DELETED", "SK": "CLIENT#1", "status": "DELETED"}, "REQ#DELETED", "CLIENT#1"),
        "REQ#ACTIVE": ({"PK": "REQ#ACTIVE", "SK": "CLIENT#2", "status": "PENDING_REVIEW"}, "REQ#ACTIVE", "CLIENT#2")
    }

    def resolve_side_effect(pk, sk, *args, **kwargs):
        return items.get(pk, (None, pk, sk))

    event = create_event("Admin", {
        "action": "PURGE",
        "records": [
            {"PK": "REQ#DELETED", "SK": "CLIENT#1"},
            {"PK": "REQ#ACTIVE", "SK": "CLIENT#2"}
        ]
    })

    with patch('handlers.admin_handler._resolve_admin_record', side_effect=resolve_side_effect):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        # One purged, one skipped
        assert body["success"] == 1
        assert body["skipped"] == 1
        # Table delete_item called only for the DELETED record
        mock_db["table"].delete_item.assert_called_once_with(Key={'PK': 'REQ#DELETED', 'SK': 'CLIENT#1'})

# --- Release 6D: Active Record Delete Protection ---

def test_delete_rejects_active_assigned_record(mock_db, mock_audit):
    """DELETE action must reject records in ASSIGNED status.

    DELETE path: record carries a matching company_id so the tenant-ownership
    guard passes and the real active-record protection makes the decision.
    """
    mock_record = {"PK": "REQ#1", "SK": "CLIENT#1", "status": "ASSIGNED",
                   "worker_id": "staff@test.com", "company_id": TEST_COMPANY}

    event = create_event("Admin", {"action": "DELETE", "PK": "REQ#1", "SK": "CLIENT#1"},
                         company_id=TEST_COMPANY)

    with patch('handlers.admin_handler._resolve_admin_record', return_value=(mock_record, "REQ#1", "CLIENT#1")), \
         patch('handlers.admin_handler.update_status', return_value=True) as mock_update:
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        # Record should be skipped, not deleted
        assert body["skipped"] >= 1
        assert any("Cannot delete active record" in f.get("reason", "") for f in body.get("failures", []))
        # update_status should NOT have been called for this record
        mock_update.assert_not_called()
        # And no hard delete occurred either.
        mock_db["table"].delete_item.assert_not_called()

def test_delete_allows_cancelled_record(mock_db, mock_audit):
    """DELETE action should allow CANCELLED records to be moved to Trash."""
    mock_record = {"PK": "REQ#1", "SK": "CLIENT#1", "status": "CANCELLED",
                   "company_id": TEST_COMPANY}

    event = create_event("Admin", {"action": "DELETE", "PK": "REQ#1", "SK": "CLIENT#1"},
                         company_id=TEST_COMPANY)

    with patch('handlers.admin_handler._resolve_admin_record', return_value=(mock_record, "REQ#1", "CLIENT#1")), \
         patch('handlers.admin_handler.update_status', return_value=True):
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 200
        body = json.loads(resp["body"])
        assert body["success"] >= 1
