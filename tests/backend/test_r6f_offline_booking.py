"""
Release 6F: Tests for admin-created offline booking path.
"""
import pytest
import json
from unittest.mock import patch, MagicMock, ANY
from handlers.intake_handler import handler as intake_handler


def create_event(role, body_dict, path="/requests", method="POST"):
    claims = {"email": f"{role.lower()}@usmissionhero.com", "sub": "test-sub-123"}
    if role == "Admin":
        claims["cognito:groups"] = "Admin"
    elif role == "Owner":
        claims["cognito:groups"] = "owner"
    elif role == "Staff":
        claims["cognito:groups"] = "Staff"
    elif role == "Client":
        claims["cognito:groups"] = "client"

    return {
        "requestContext": {"authorizer": {"claims": claims}},
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body_dict),
    }


VALID_ADMIN_BOOKING = {
    "source": "admin_created",
    "client_id": "client_abc123",
    "client_name": "Jane Smith",
    "client_email": "jane@example.com",
    "client_phone": "555-123-4567",
    "pet_names": "Buddy",
    "pet_ids": ["pet_001"],
    "service_type": "WALK_30MIN",
    "start_date": "2026-07-01",
    "visit_windows": ["MIDDAY"],
    "details": "Back gate code: 1234",
}

MOCK_CLIENT_PROFILE = {
    "PK": "COMPANY#tog_and_dogs",
    "SK": "CLIENT#client_abc123",
    "client_id": "client_abc123",
    "company_id": "tog_and_dogs",
    "display_name": "Jane Smith",
    "email": "jane@example.com",
    "is_active": True,
}


# --- Authorization Tests ---

def test_owner_can_create_admin_booking():
    """Owner role should be able to create admin bookings."""
    event = create_event("Owner", VALID_ADMIN_BOOKING)

    with patch('handlers.intake_handler.get_item', return_value=MOCK_CLIENT_PROFILE), \
         patch('handlers.intake_handler.put_item', return_value=True), \
         patch('handlers.intake_handler.table') as mock_table, \
         patch('boto3.client') as mock_boto:
        mock_lambda = MagicMock()
        mock_boto.return_value = mock_lambda
        resp = intake_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "APPROVED"
    assert body["workflow_type"] == "VISIT_BOOKING"
    assert body["source"] == "admin_created"


def test_admin_can_create_admin_booking():
    """Admin role should be able to create admin bookings."""
    event = create_event("Admin", VALID_ADMIN_BOOKING)

    with patch('handlers.intake_handler.get_item', return_value=MOCK_CLIENT_PROFILE), \
         patch('handlers.intake_handler.put_item', return_value=True), \
         patch('handlers.intake_handler.table') as mock_table, \
         patch('boto3.client') as mock_boto:
        mock_lambda = MagicMock()
        mock_boto.return_value = mock_lambda
        resp = intake_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "APPROVED"


def test_staff_cannot_create_admin_booking():
    """Staff role should be rejected."""
    event = create_event("Staff", VALID_ADMIN_BOOKING)

    resp = intake_handler(event, None)
    assert resp["statusCode"] == 403
    assert "Forbidden" in resp["body"]


def test_client_cannot_create_admin_booking():
    """Client role should be rejected."""
    event = create_event("Client", VALID_ADMIN_BOOKING)

    resp = intake_handler(event, None)
    assert resp["statusCode"] == 403
    assert "Forbidden" in resp["body"]


# --- Validation Tests ---

def test_missing_client_id_fails():
    """Missing client_id should return 400."""
    body = {**VALID_ADMIN_BOOKING}
    del body["client_id"]
    event = create_event("Owner", body)

    resp = intake_handler(event, None)
    assert resp["statusCode"] == 400
    assert "client_id" in resp["body"]


def test_missing_pets_fails():
    """Missing both pet_names and pet_ids should return 400."""
    body = {**VALID_ADMIN_BOOKING}
    del body["pet_names"]
    del body["pet_ids"]
    event = create_event("Owner", body)

    with patch('handlers.intake_handler.get_item', return_value=MOCK_CLIENT_PROFILE):
        resp = intake_handler(event, None)

    assert resp["statusCode"] == 400
    assert "pet" in resp["body"].lower()


def test_cross_company_client_rejected():
    """Client from a different company should be rejected."""
    cross_tenant_profile = {**MOCK_CLIENT_PROFILE, "company_id": "other_company"}
    event = create_event("Owner", VALID_ADMIN_BOOKING)

    with patch('handlers.intake_handler.get_item', return_value=cross_tenant_profile):
        resp = intake_handler(event, None)

    assert resp["statusCode"] == 403
    assert "Cross-tenant" in resp["body"]


def test_nonexistent_client_rejected():
    """Client not found should return 400."""
    event = create_event("Owner", VALID_ADMIN_BOOKING)

    with patch('handlers.intake_handler.get_item', return_value=None):
        resp = intake_handler(event, None)

    assert resp["statusCode"] == 400
    assert "not found" in resp["body"]


# --- Behavior Tests ---

def test_request_created_as_approved_visit_booking():
    """Admin booking should be created with APPROVED status and VISIT_BOOKING workflow."""
    event = create_event("Owner", VALID_ADMIN_BOOKING)
    saved_item = {}

    def capture_put(item):
        saved_item.update(item)
        return True

    with patch('handlers.intake_handler.get_item', return_value=MOCK_CLIENT_PROFILE), \
         patch('handlers.intake_handler.put_item', side_effect=capture_put), \
         patch('handlers.intake_handler.table') as mock_table, \
         patch('boto3.client') as mock_boto:
        mock_lambda = MagicMock()
        mock_boto.return_value = mock_lambda
        resp = intake_handler(event, None)

    assert resp["statusCode"] == 200
    assert saved_item["status"] == "APPROVED"
    assert saved_item["workflow_type"] == "VISIT_BOOKING"
    assert saved_item["source"] == "admin_created"
    assert saved_item["created_by"] == "owner@usmissionhero.com"
    assert saved_item["linked_client_profile_id"] == "client_abc123"


def test_request_received_notification_skipped():
    """Admin-created bookings should NOT trigger REQUEST_RECEIVED notification."""
    event = create_event("Owner", VALID_ADMIN_BOOKING)

    with patch('handlers.intake_handler.get_item', return_value=MOCK_CLIENT_PROFILE), \
         patch('handlers.intake_handler.put_item', return_value=True), \
         patch('handlers.intake_handler.table') as mock_table, \
         patch('handlers.intake_handler.notify_event') as mock_notify, \
         patch('boto3.client') as mock_boto:
        mock_lambda = MagicMock()
        mock_boto.return_value = mock_lambda
        resp = intake_handler(event, None)

    assert resp["statusCode"] == 200
    # notify_event should NOT have been called with REQUEST_RECEIVED
    for call in mock_notify.call_args_list:
        assert call[0][0] != 'REQUEST_RECEIVED', "REQUEST_RECEIVED should not be triggered for admin-created bookings"


def test_job_function_invoked():
    """JOB_FUNCTION_NAME should be invoked asynchronously."""
    event = create_event("Owner", VALID_ADMIN_BOOKING)

    with patch('handlers.intake_handler.get_item', return_value=MOCK_CLIENT_PROFILE), \
         patch('handlers.intake_handler.put_item', return_value=True), \
         patch('handlers.intake_handler.table') as mock_table, \
         patch('boto3.client') as mock_boto, \
         patch.dict('os.environ', {'JOB_FUNCTION_NAME': 'test-job-lambda'}):
        mock_lambda = MagicMock()
        mock_boto.return_value = mock_lambda
        resp = intake_handler(event, None)

    assert resp["statusCode"] == 200
    # Lambda invoke should have been called
    mock_lambda.invoke.assert_called()
    call_kwargs = mock_lambda.invoke.call_args
    assert call_kwargs[1]['InvocationType'] == 'Event' or call_kwargs.kwargs.get('InvocationType') == 'Event'


def test_calendar_sync_attempted():
    """Google Calendar sync should be attempted (non-blocking)."""
    event = create_event("Owner", VALID_ADMIN_BOOKING)

    with patch('handlers.intake_handler.get_item', return_value=MOCK_CLIENT_PROFILE), \
         patch('handlers.intake_handler.put_item', return_value=True), \
         patch('handlers.intake_handler.table') as mock_table, \
         patch('boto3.client') as mock_boto, \
         patch('common.google_calendar.sync_calendar_event', return_value={"event_id": "gcal_123"}) as mock_cal:
        mock_lambda = MagicMock()
        mock_boto.return_value = mock_lambda
        resp = intake_handler(event, None)

    assert resp["statusCode"] == 200
    mock_cal.assert_called_once()


def test_calendar_failure_does_not_crash():
    """Calendar sync failure should not prevent booking creation."""
    event = create_event("Owner", VALID_ADMIN_BOOKING)

    with patch('handlers.intake_handler.get_item', return_value=MOCK_CLIENT_PROFILE), \
         patch('handlers.intake_handler.put_item', return_value=True), \
         patch('handlers.intake_handler.table') as mock_table, \
         patch('boto3.client') as mock_boto, \
         patch('common.google_calendar.sync_calendar_event', side_effect=Exception("Token expired")):
        mock_lambda = MagicMock()
        mock_boto.return_value = mock_lambda
        resp = intake_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "APPROVED"


def test_no_duplicate_client_profile_created():
    """Admin-created bookings should NOT trigger auto_create_or_link_client_profile."""
    event = create_event("Owner", VALID_ADMIN_BOOKING)

    with patch('handlers.intake_handler.get_item', return_value=MOCK_CLIENT_PROFILE), \
         patch('handlers.intake_handler.put_item', return_value=True), \
         patch('handlers.intake_handler.table') as mock_table, \
         patch('boto3.client') as mock_boto:
        mock_lambda = MagicMock()
        mock_boto.return_value = mock_lambda

        # Ensure client_profile module is NOT called
        with patch('common.client_profile.auto_create_or_link_client_profile') as mock_auto:
            resp = intake_handler(event, None)
            mock_auto.assert_not_called()

    assert resp["statusCode"] == 200


# --- Admin Pet Listing Tests (Release 6F) ---

def test_admin_can_list_client_pets():
    """Owner/Admin should be able to query all pets for a client."""
    from handlers.pet_handler import handler as pet_handler
    
    event = {
        "requestContext": {"authorizer": {"claims": {"cognito:groups": "Admin"}}},
        "httpMethod": "GET",
        "path": "/admin/pets",
        "queryStringParameters": {"clientId": "client_abc123"}
    }
    
    mock_pets = [
        {"PK": "PET#pet_1", "SK": "CLIENT#client_abc123", "client_id": "client_abc123", "entity_type": "PET", "name": "Buddy", "is_active": True, "company_id": "tog_and_dogs"},
        {"PK": "PET#pet_2", "SK": "CLIENT#client_abc123", "client_id": "client_abc123", "entity_type": "PET", "name": "Max", "is_active": False, "company_id": "tog_and_dogs"} # inactive
    ]
    
    mock_table = MagicMock()
    mock_table.scan.return_value = {"Items": mock_pets}
    
    with patch('common.db.table', mock_table):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "pets" in body
    # Only active pets should be returned
    assert len(body["pets"]) == 1
    assert body["pets"][0]["name"] == "Buddy"


def test_client_pets_tenant_isolation():
    """Admin pet listing should filter out cross-tenant pets."""
    from handlers.pet_handler import handler as pet_handler
    
    event = {
        "requestContext": {"authorizer": {"claims": {"cognito:groups": "owner"}}}, # Company default: tog_and_dogs
        "httpMethod": "GET",
        "path": "/admin/pets",
        "queryStringParameters": {"clientId": "client_abc123"}
    }
    
    mock_pets = [
        {"PK": "PET#pet_1", "SK": "CLIENT#client_abc123", "client_id": "client_abc123", "entity_type": "PET", "name": "Buddy", "company_id": "tog_and_dogs"},
        {"PK": "PET#pet_2", "SK": "CLIENT#client_abc123", "client_id": "client_abc123", "entity_type": "PET", "name": "Scruffy", "company_id": "different_company"} # cross-tenant
    ]
    
    mock_table = MagicMock()
    mock_table.scan.return_value = {"Items": mock_pets}
    
    with patch('common.db.table', mock_table):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    # Cross-tenant Scruffy should be filtered out
    assert len(body["pets"]) == 1
    assert body["pets"][0]["name"] == "Buddy"


def test_staff_cannot_list_client_pets():
    """Staff role should not be allowed to list all pets of a client via admin route."""
    from handlers.pet_handler import handler as pet_handler
    
    event = {
        "requestContext": {"authorizer": {"claims": {"cognito:groups": "Staff"}}},
        "httpMethod": "GET",
        "path": "/admin/pets",
        "queryStringParameters": {"clientId": "client_abc123"}
    }
    
    resp = pet_handler(event, None)
    # Rejects because path parameters (petId) is missing/None for GET and it is not a client role
    assert resp["statusCode"] == 400
    assert "Missing petId" in resp["body"]
