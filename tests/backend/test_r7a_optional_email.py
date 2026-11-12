"""
Release 7A Phase 3: Targeted tests for optional email client creation & manual booking.
"""
import pytest
import json
from unittest.mock import patch, MagicMock, ANY
from handlers.admin_handler import handler as admin_handler
from handlers.intake_handler import handler as intake_handler

# The admin and intake handlers load the tenant's TENANT#<id>/METADATA record through
# common.db (entitlement/billing). A bare MagicMock table would hand MagicMock values to
# the billing date parsing, so tests that patch common.db.table supply a realistic
# active-tenant metadata item, matching the authoritative read path.
def _active_tenant_metadata(company_id="tog_and_dogs"):
    return {
        "Item": {
            "PK": f"TENANT#{company_id}",
            "SK": "METADATA",
            "company_id": company_id,
            "subscription_tier": "professional",
            "subscription_status": "active",
            "is_active": True,
        }
    }

# Public /requests resolves its tenant only from a trusted, server-configured
# PUBLIC_INTAKE_DOMAIN_MAP keyed by requestContext.domainName (fail closed otherwise).
PUBLIC_TEST_DOMAIN = "test-api.execute-api.us-east-1.amazonaws.com"
PUBLIC_TEST_DOMAIN_MAP = json.dumps({
    PUBLIC_TEST_DOMAIN: {"tenant_id": "tog_and_dogs", "active": True, "public_intake_enabled": True}
})

# --- Helper functions to mock events ---

def create_admin_event(method, path, body=None, email="admin@usmissionhero.com"):
    claims = {
        "email": email,
        "sub": "admin-sub-123",
        "cognito:groups": "Admin"
    }
    return {
        "requestContext": {
            "authorizer": {
                "claims": claims
            }
        },
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body) if body else "{}"
    }

def create_public_event(method, path, body=None):
    return {
        "requestContext": {
            "authorizer": {},
            "domainName": PUBLIC_TEST_DOMAIN
        },
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body) if body else "{}"
    }

# --- Test Cases ---

def test_profile_only_client_can_be_created_without_email():
    """Verify that admin can successfully create a profile-only client without an email."""
    event = create_admin_event("POST", "/admin/clients", {
        "display_name": "John Offline",
        "phone": "555-0199",
        "notes": "No email or tech access."
    })
    
    mock_table = MagicMock()
    mock_table.get_item.return_value = _active_tenant_metadata()
    # Mock DynamoDB put_item success
    mock_table.put_item.return_value = {}
    
    with patch('common.db.table', mock_table), \
         patch('handlers.admin_handler.is_protected_email', return_value=False):
        resp = admin_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["display_name"] == "John Offline"
    assert body["email"] is None
    assert body["cognito_status"] == "not_linked"
    assert body["portal_enabled"] is False
    assert body["phone"] == "555-0199"
    
    # Assert that put_item was called with email = None
    mock_table.put_item.assert_called_once()
    saved_item = mock_table.put_item.call_args[1]["Item"]
    assert saved_item["display_name"] == "John Offline"
    assert saved_item["email"] is None


def test_onboard_client_still_requires_email():
    """Verify that client onboarding (Cognito invitation) still strictly requires an email."""
    event = create_admin_event("POST", "/admin/clients/onboard", {
        "display_name": "Jane Onboard",
        # email is missing
    })
    
    resp = admin_handler(event, None)
    assert resp["statusCode"] == 400
    assert "email are required" in resp["body"]


def test_manual_booking_can_be_created_for_a_client_without_email():
    """Verify that admins can create a manual booking for a client who has no email address."""
    event = create_admin_event("POST", "/requests", {
        "source": "admin_created",
        "client_id": "client_offline_123",
        "client_name": "John Offline",
        "start_date": "2026-06-01",
        "pet_names": "Bella",
        "pet_ids": ["pet_123"],
        "service_type": "PET_SITTING"
    })
    
    mock_client_profile = {
        "PK": "COMPANY#tog_and_dogs",
        "SK": "CLIENT#client_offline_123",
        "client_id": "client_offline_123",
        "company_id": "tog_and_dogs",
        "display_name": "John Offline",
        "email": None, # Offline client profile has no email
        "is_active": True
    }
    
    with patch('handlers.intake_handler.get_item', return_value=mock_client_profile), \
         patch('handlers.intake_handler.put_item', return_value=True) as mock_put, \
         patch('handlers.intake_handler.table') as mock_table, \
         patch('boto3.client') as mock_boto, \
         patch('common.google_calendar.sync_calendar_event', return_value={"event_id": "mock_event"}):
        mock_lambda = MagicMock()
        mock_boto.return_value = mock_lambda
        
        resp = intake_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "APPROVED"
    assert body["workflow_type"] == "VISIT_BOOKING"
    
    # Verify that the booking item was saved with client_email = None
    mock_put.assert_called_once()
    saved_booking = mock_put.call_args[0][0]
    assert saved_booking["client_name"] == "John Offline"
    assert saved_booking["client_email"] is None
    assert saved_booking["start_date"] == "2026-06-01"


def test_public_intake_still_requires_email(monkeypatch):
    """Verify that the public customer intake form still strictly enforces email requirement."""
    monkeypatch.setenv("PUBLIC_INTAKE_DOMAIN_MAP", PUBLIC_TEST_DOMAIN_MAP)
    event = create_public_event("POST", "/requests", {
        "client_name": "Public Submitter",
        "start_date": "2026-06-01",
        "pet_names": "Daisy"
        # client_email is missing
    })
    
    mock_table = MagicMock()
    mock_table.get_item.return_value = _active_tenant_metadata()
    with patch('common.db.table', mock_table):
        resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    assert "Missing or invalid required fields" in resp["body"]
    assert "client_email" in resp["body"]


def test_duplicate_and_protected_checks_work_when_email_present():
    """Verify that duplicate email and protected admin account validation still run when email is provided."""
    # 1. Duplicate email check
    event_dup = create_admin_event("POST", "/admin/clients", {
        "display_name": "Duplicate User",
        "email": "duplicate@test.com"
    })
    
    mock_table_dup = MagicMock()
    mock_table_dup.get_item.return_value = _active_tenant_metadata()
    mock_table_dup.query.return_value = {
        "Items": [
            {
                "PK": "COMPANY#tog_and_dogs",
                "SK": "CLIENT#client_abc",
                "email": "duplicate@test.com",
                "is_active": True
            }
        ]
    }
    
    with patch('common.db.table', mock_table_dup):
        resp_dup = admin_handler(event_dup, None)
        
    assert resp_dup["statusCode"] == 409
    assert "already exists" in resp_dup["body"]
    
    # 2. Protected admin account check
    event_prot = create_admin_event("POST", "/admin/clients", {
        "display_name": "Fake Admin",
        # The hardcoded, always-protected fallback identity in common.protected_accounts
        # (_FALLBACK_EMAILS); it stays protected regardless of PROTECTED_ADMIN_EMAILS.
        "email": "support@usmissionhero.com"
    })
    
    mock_table_prot = MagicMock()
    mock_table_prot.get_item.return_value = _active_tenant_metadata()
    mock_table_prot.query.return_value = {"Items": []} # No duplicate active clients
    
    with patch('common.db.table', mock_table_prot):
        resp_prot = admin_handler(event_prot, None)
        
    assert resp_prot["statusCode"] == 403
    assert "protected account identity" in resp_prot["body"]
