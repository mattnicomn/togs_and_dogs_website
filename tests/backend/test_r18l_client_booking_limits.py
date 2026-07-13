import pytest
import json
import os
import uuid
from unittest.mock import patch, MagicMock, ANY
from handlers.admin_handler import handler as admin_handler
from handlers.intake_handler import handler as intake_handler
from common.client_profile import auto_create_or_link_client_profile
from common.entitlement import get_active_client_count, get_monthly_bookings_count, increment_monthly_bookings, check_limit


@pytest.fixture(autouse=True)
def clean_env():
    """Ensure environment is reset between tests."""
    old_enforcement = os.environ.get('ENTITLEMENT_ENFORCEMENT_ENABLED')
    old_stripe_env = os.environ.get('STRIPE_ENV')
    old_domain_map = os.environ.get('PUBLIC_INTAKE_DOMAIN_MAP')
    
    os.environ['ENTITLEMENT_ENFORCEMENT_ENABLED'] = 'true'
    os.environ['STRIPE_ENV'] = 'production'
    # Provide a trusted domain map for public intake routing in tests
    os.environ['PUBLIC_INTAKE_DOMAIN_MAP'] = json.dumps({
        "test-api.execute-api.us-east-1.amazonaws.com": {
            "tenant_id": "test_company",
            "active": True,
            "public_intake_enabled": True
        }
    })
    
    yield
    
    if old_enforcement is not None:
        os.environ['ENTITLEMENT_ENFORCEMENT_ENABLED'] = old_enforcement
    else:
        os.environ.pop('ENTITLEMENT_ENFORCEMENT_ENABLED', None)
        
    if old_stripe_env is not None:
        os.environ['STRIPE_ENV'] = old_stripe_env
    else:
        os.environ.pop('STRIPE_ENV', None)
    
    if old_domain_map is not None:
        os.environ['PUBLIC_INTAKE_DOMAIN_MAP'] = old_domain_map
    else:
        os.environ.pop('PUBLIC_INTAKE_DOMAIN_MAP', None)


@pytest.fixture
def mock_db():
    with patch('common.db.table') as mock_table, \
         patch('handlers.admin_handler.table', mock_table, create=True), \
         patch('handlers.intake_handler.table', mock_table, create=True), \
         patch('common.client_profile.table', mock_table, create=True), \
         patch('common.db.get_item') as mock_get, \
         patch('handlers.admin_handler.get_item', mock_get, create=True), \
         patch('handlers.intake_handler.get_item', mock_get, create=True), \
         patch('common.client_profile.get_item', mock_get, create=True):
        
        # Default mock tenant response (Professional tier: max_active_clients=100, max_monthly_bookings=250)
        mock_get.return_value = {
            "PK": "TENANT#test_company",
            "SK": "METADATA",
            "company_id": "test_company",
            "subscription_tier": "professional",
            "subscription_status": "active",
            "is_active": True
        }
        
        yield {"table": mock_table, "get_item": mock_get}


def create_event(role, path, method="GET", body_dict=None, company_id="test_company", email="admin@test.com", sub="admin-sub"):
    claims = {
        "email": email,
        "sub": sub,
        "custom:company_id": company_id
    }
    if role == "owner":
        claims["cognito:groups"] = "owner"
    elif role == "Admin":
        claims["cognito:groups"] = "Admin"
    elif role == "Staff":
        claims["cognito:groups"] = "Staff"
    elif role == "Client":
        claims["cognito:groups"] = "Client"
        
    return {
        "requestContext": {
            "authorizer": {
                "claims": claims
            },
            "domainName": "test-api.execute-api.us-east-1.amazonaws.com"
        },
        "httpMethod": method,
        "path": path,
        "body": json.dumps(body_dict or {})
    }


# ---------------------------------------------------------------------------
# 1. DynamoDB Count and Increment Helpers Tests
# ---------------------------------------------------------------------------

def test_get_active_client_count(mock_db):
    """Verify get_active_client_count counts active/disabled and excludes archived profiles."""
    mock_db["table"].query.return_value = {
        "Items": [
            {"SK": "CLIENT#1", "is_active": True},
            {"SK": "CLIENT#2", "is_active": False}, # Counts (disabled)
            {"SK": "CLIENT#3", "is_active": True, "status": "ARCHIVED"}, # Excluded
            {"SK": "CLIENT#4", "is_active": True, "is_archived": True}, # Excluded
        ]
    }
    count = get_active_client_count("test_company")
    assert count == 2
    mock_db["table"].query.assert_called_once()


def test_get_monthly_bookings_count_missing_defaults_to_zero(mock_db):
    """Verify get_monthly_bookings_count returns 0 when no record is found in DB."""
    mock_db["table"].get_item.return_value = {}
    count = get_monthly_bookings_count("test_company", "2026-06")
    assert count == 0


def test_get_monthly_bookings_count_existing(mock_db):
    """Verify get_monthly_bookings_count parses and returns the current booking count."""
    mock_db["table"].get_item.return_value = {
        "Item": {
            "PK": "USAGE#test_company",
            "SK": "BOOKINGS#2026-06",
            "booking_count": 45
        }
    }
    count = get_monthly_bookings_count("test_company", "2026-06")
    assert count == 45


def test_increment_monthly_bookings(mock_db):
    """Verify increment_monthly_bookings atomically updates DynamoDB using ADD."""
    mock_db["table"].update_item.return_value = {}
    success = increment_monthly_bookings("test_company", "2026-06")
    assert success is True
    mock_db["table"].update_item.assert_called_once_with(
        Key={"PK": "USAGE#test_company", "SK": "BOOKINGS#2026-06"},
        UpdateExpression="ADD booking_count :val",
        ExpressionAttributeValues={":val": 1}
    )


# ---------------------------------------------------------------------------
# 2. Client Creation Gate Tests
# ---------------------------------------------------------------------------

def test_post_admin_clients_below_limit(mock_db):
    """Verify that posting to /admin/clients succeeds when below the limit."""
    event = create_event("Admin", "/admin/clients", method="POST", body_dict={
        "display_name": "New Client",
        "email": "new@test.com"
    })
    
    # 99 clients -> below limit of 100
    mock_db["table"].query.return_value = {
        "Items": [{"SK": f"CLIENT#{i}"} for i in range(99)]
    }
    mock_db["table"].put_item.return_value = {}
    
    resp = admin_handler(event, None)
    assert resp["statusCode"] == 200


def test_post_admin_clients_at_limit_denied(mock_db):
    """Verify that posting to /admin/clients is denied when at the limit."""
    event = create_event("Admin", "/admin/clients", method="POST", body_dict={
        "display_name": "New Client",
        "email": "new@test.com"
    })
    
    # 100 clients -> at limit of 100
    mock_db["table"].query.return_value = {
        "Items": [{"SK": f"CLIENT#{i}"} for i in range(100)]
    }
    
    resp = admin_handler(event, None)
    assert resp["statusCode"] == 403
    body = json.loads(resp["body"])
    assert "Client limit reached (100/100)" in body["error"]


def test_post_admin_clients_onboard_at_limit_denied(mock_db):
    """Verify that client onboarding is denied when at the limit before Cognito calls."""
    event = create_event("Admin", "/admin/clients/onboard", method="POST", body_dict={
        "display_name": "New Client",
        "email": "new@test.com"
    })
    
    # 100 clients -> at limit
    mock_db["table"].query.return_value = {
        "Items": [{"SK": f"CLIENT#{i}"} for i in range(100)]
    }
    
    with patch('boto3.client') as mock_boto:
        resp = admin_handler(event, None)
        assert resp["statusCode"] == 403
        body = json.loads(resp["body"])
        assert "Client limit reached" in body["error"]
        # Cognito client shouldn't be created or invoked
        mock_boto.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Public Intake Client Creation Gate Tests
# ---------------------------------------------------------------------------

def test_public_intake_new_client_at_limit_denied(mock_db):
    """Public intake for a new client email should be denied when at the client limit."""
    event = create_event("Client", "/requests", method="POST", body_dict={
        "client_name": "New Client",
        "client_email": "new_intake@test.com",
        "start_date": "2026-06-25",
        "pet_names": "Buddy",
        "accepted_terms": True,
        "accepted_privacy": True,
        "terms_version": "1.0",
        "privacy_version": "1.0"
    })
    
    # Existing client query has 100 active clients, none matching this new email
    mock_db["table"].query.return_value = {
        "Items": [{"SK": f"CLIENT#{i}", "email": f"existing{i}@test.com"} for i in range(100)]
    }
    
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 403
    body = json.loads(resp["body"])
    assert "Client limit reached" in body["error"]


def test_public_intake_existing_client_at_limit_allowed(mock_db):
    """Public intake for an existing client email should bypass client limit check."""
    event = create_event("Client", "/requests", method="POST", body_dict={
        "client_name": "Existing Client",
        "client_email": "existing_intake@test.com",
        "start_date": "2026-06-25",
        "pet_names": "Buddy",
        "accepted_terms": True,
        "accepted_privacy": True,
        "terms_version": "1.0",
        "privacy_version": "1.0"
    })
    
    # Existing client list has 100 active clients, including the matching email
    mock_db["table"].query.return_value = {
        "Items": [{"SK": f"CLIENT#{i}", "email": f"existing{i}@test.com", "is_active": True} for i in range(99)] + [
            {"SK": "CLIENT#match", "email": "existing_intake@test.com", "is_active": True}
        ]
    }
    
    # Mock monthly bookings to be low (e.g. 5)
    mock_db["table"].get_item.side_effect = lambda Key: (
        {"Item": {"booking_count": 5}} if Key.get("PK", "").startswith("USAGE#") else {"Item": mock_db["get_item"](Key.get("PK"), Key.get("SK"))}
    )
    
    mock_db["table"].put_item.return_value = True
    
    with patch('boto3.client') as mock_sfn:
        resp = intake_handler(event, None)
        assert resp["statusCode"] == 200


# ---------------------------------------------------------------------------
# 4. Monthly Booking Limit Gate Tests
# ---------------------------------------------------------------------------

def test_booking_limit_below_limit_allowed(mock_db):
    """Verify booking is allowed and increments counter when below booking limit."""
    event = create_event("Client", "/requests", method="POST", body_dict={
        "client_name": "Client A",
        "client_email": "clienta@test.com",
        "start_date": "2026-06-25",
        "pet_names": "Buddy",
        "accepted_terms": True,
        "accepted_privacy": True,
        "terms_version": "1.0",
        "privacy_version": "1.0"
    })
    
    # 1. Mock existing clients to match email (avoid client count gate)
    mock_db["table"].query.return_value = {
        "Items": [{"SK": "CLIENT#match", "email": "clienta@test.com", "is_active": True}]
    }
    
    # 2. Mock current monthly bookings: 249 (limit is 250)
    mock_db["table"].get_item.side_effect = lambda Key: (
        {"Item": {"booking_count": 249}} if Key.get("PK", "").startswith("USAGE#") else {"Item": mock_db["get_item"](Key.get("PK"), Key.get("SK"))}
    )
    
    mock_db["table"].put_item.return_value = True
    mock_db["table"].update_item.return_value = {}
    
    with patch('boto3.client'):
        resp = intake_handler(event, None)
        assert resp["statusCode"] == 200
        
        # Verify atomic increment was called
        mock_db["table"].update_item.assert_any_call(
            Key={"PK": "USAGE#test_company", "SK": f"BOOKINGS#2026-06"},
            UpdateExpression="ADD booking_count :val",
            ExpressionAttributeValues={":val": 1}
        )


def test_booking_limit_at_limit_denied(mock_db):
    """Verify booking is blocked and doesn't increment when at the monthly booking limit."""
    event = create_event("Client", "/requests", method="POST", body_dict={
        "client_name": "Client A",
        "client_email": "clienta@test.com",
        "start_date": "2026-06-25",
        "pet_names": "Buddy",
        "accepted_terms": True,
        "accepted_privacy": True,
        "terms_version": "1.0",
        "privacy_version": "1.0"
    })
    
    mock_db["table"].query.return_value = {
        "Items": [{"SK": "CLIENT#match", "email": "clienta@test.com", "is_active": True}]
    }
    
    # Current monthly bookings: 250 (at limit)
    mock_db["table"].get_item.side_effect = lambda Key: (
        {"Item": {"booking_count": 250}} if Key.get("PK", "").startswith("USAGE#") else {"Item": mock_db["get_item"](Key.get("PK"), Key.get("SK"))}
    )
    
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 403
    body = json.loads(resp["body"])
    assert "Monthly booking limit reached (250/250)" in body["error"]
    
    # Assert put_item and increment were NOT called
    mock_db["table"].put_item.assert_not_called()
    assert not any("ADD booking_count" in str(call) for call in mock_db["table"].update_item.call_args_list)


# ---------------------------------------------------------------------------
# 5. Exemptions and Edge Cases Tests
# ---------------------------------------------------------------------------

def test_test_booking_exempt_from_limits(mock_db):
    """Test bookings should bypass booking limits and not increment the counter."""
    event = create_event("Client", "/requests", method="POST", body_dict={
        "client_name": "Client A",
        "client_email": "clienta@test.com",
        "start_date": "2026-06-25",
        "pet_names": "Buddy",
        "accepted_terms": True,
        "accepted_privacy": True,
        "terms_version": "1.0",
        "privacy_version": "1.0",
        "is_test_booking": True # EXEMPT
    })
    
    mock_db["table"].query.return_value = {
        "Items": [{"SK": "CLIENT#match", "email": "clienta@test.com", "is_active": True}]
    }
    
    # Booking count is 300 (over limit)
    mock_db["table"].get_item.side_effect = lambda Key: (
        {"Item": {"booking_count": 300}} if Key.get("PK", "").startswith("USAGE#") else {"Item": mock_db["get_item"](Key.get("PK"), Key.get("SK"))}
    )
    
    mock_db["table"].put_item.return_value = True
    
    with patch('boto3.client'):
        resp = intake_handler(event, None)
        assert resp["statusCode"] == 200
        
        # Verify the saved request has is_test_booking set
        kwargs = mock_db["table"].put_item.call_args_list[0][1]
        saved_item = kwargs.get("Item")
        assert saved_item.get("is_test_booking") is True
        
        # Verify no increment was called
        assert not any("ADD booking_count" in str(call) for call in mock_db["table"].update_item.call_args_list)


def test_entitlement_enforcement_flag_behavior(mock_db):
    """When ENTITLEMENT_ENFORCEMENT_ENABLED is false, limits should not be blocked but counter increments."""
    os.environ['ENTITLEMENT_ENFORCEMENT_ENABLED'] = 'false'
    
    event = create_event("Client", "/requests", method="POST", body_dict={
        "client_name": "Client A",
        "client_email": "clienta@test.com",
        "start_date": "2026-06-25",
        "pet_names": "Buddy",
        "accepted_terms": True,
        "accepted_privacy": True,
        "terms_version": "1.0",
        "privacy_version": "1.0"
    })
    
    mock_db["table"].query.return_value = {
        "Items": [{"SK": "CLIENT#match", "email": "clienta@test.com", "is_active": True}]
    }
    
    # Over limit
    mock_db["table"].get_item.side_effect = lambda Key: (
        {"Item": {"booking_count": 300}} if Key.get("PK", "").startswith("USAGE#") else {"Item": mock_db["get_item"](Key.get("PK"), Key.get("SK"))}
    )
    
    mock_db["table"].put_item.return_value = True
    mock_db["table"].update_item.return_value = {}
    
    with patch('boto3.client'):
        resp = intake_handler(event, None)
        assert resp["statusCode"] == 200 # Allowed because enforcement is disabled
        
        # But counter still increments for auditing/reporting
        mock_db["table"].update_item.assert_any_call(
            Key={"PK": "USAGE#test_company", "SK": f"BOOKINGS#2026-06"},
            UpdateExpression="ADD booking_count :val",
            ExpressionAttributeValues={":val": 1}
        )


def test_admin_created_booking_checks_booking_limit(mock_db):
    """Verify admin created offline booking path check limit and increments count."""
    event = create_event("Admin", "/requests", method="POST", body_dict={
        "source": "admin_created",
        "client_id": "client_abc",
        "client_name": "Offline Client",
        "start_date": "2026-06-25",
        "pet_names": "Max"
    })
    
    # Configure mock_get to return appropriate items based on arguments
    def get_item_side_effect(pk, sk):
        if pk.startswith("COMPANY#") and sk.startswith("CLIENT#"):
            return {
                "PK": pk,
                "SK": sk,
                "company_id": "test_company",
                "client_id": "client_abc",
                "is_active": True
            }
        elif pk.startswith("TENANT#"):
            return {
                "PK": pk,
                "SK": "METADATA",
                "company_id": "test_company",
                "subscription_tier": "professional",
                "subscription_status": "active"
            }
        return None

    mock_db["get_item"].side_effect = get_item_side_effect
    
    # Over limit (300/250)
    mock_db["table"].get_item.side_effect = lambda Key: (
        {"Item": {"booking_count": 300}} if Key.get("PK", "").startswith("USAGE#")
        else {"Item": get_item_side_effect(Key.get("PK"), Key.get("SK"))}
    )
    
    resp = intake_handler(event, None)
    assert resp["statusCode"] == 403
    body = json.loads(resp["body"])
    assert "Monthly booking limit reached" in body["error"]


# ---------------------------------------------------------------------------
# 6. Auto-Create Client Profile Gate Tests
# ---------------------------------------------------------------------------

def test_auto_create_profile_at_limit_fails_gracefully(mock_db):
    """Verify auto_create_or_link_client_profile fails with FAILED_LIMIT_EXCEEDED when at limit."""
    request_item = {
        "client_name": "Intake Client",
        "client_email": "intake@test.com",
        "client_phone": "555-0199"
    }
    
    # 1. Mock existing clients to be at limit (100 active clients)
    mock_db["table"].query.return_value = {
        "Items": [{"SK": f"CLIENT#{i}", "email": f"other{i}@test.com"} for i in range(100)]
    }
    
    mock_db["table"].update_item.return_value = {}
    
    result = auto_create_or_link_client_profile(
        request_item=request_item,
        request_id="req-123",
        client_id="client-temp",
        company_id="test_company"
    )
    
    assert result["action"] == "failed"
    assert result["link_status"] == "FAILED_LIMIT_EXCEEDED"
    assert "Client limit reached" in result["message"]
    
    # Verify request record updated with status FAILED_LIMIT_EXCEEDED
    mock_db["table"].update_item.assert_any_call(
        Key={"PK": "REQ#req-123", "SK": "CLIENT#client-temp"},
        UpdateExpression="SET client_profile_link_status = :ls, client_profile_linked_at = :t, client_profile_link_method = :m",
        ExpressionAttributeValues={
            ":ls": "FAILED_LIMIT_EXCEEDED",
            ":t": ANY,
            ":m": "failed_limit_exceeded"
        }
    )
