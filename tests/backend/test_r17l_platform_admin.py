import pytest
import json
import base64
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, ANY
from handlers.platform_handler import handler as platform_handler
from handlers.admin_handler import handler as admin_handler

@pytest.fixture
def mock_db():
    with patch('handlers.platform_handler.table') as mock_table, \
         patch('handlers.platform_handler.get_item') as mock_get, \
         patch('handlers.platform_handler.put_item') as mock_put, \
         patch('handlers.platform_handler.update_item') as mock_update:
        yield {
            "table": mock_table,
            "get_item": mock_get,
            "put_item": mock_put,
            "update_item": mock_update
        }

def create_event(role, path, method="GET", body_dict=None, query_params=None, path_params=None, email="platform-admin@test.com", sub="platform-sub"):
    claims = {
        "email": email,
        "sub": sub
    }
    if role == "platform_admin":
        claims["cognito:groups"] = "platform_admin"
    elif role == "owner":
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
            }
        },
        "httpMethod": method,
        "path": path,
        "queryStringParameters": query_params,
        "pathParameters": path_params,
        "body": json.dumps(body_dict or {}) if body_dict is not None else None
    }

# ---------------------------------------------------------------------------
# 1. Authorization Tests
# ---------------------------------------------------------------------------

def test_platform_admin_group_allowed(mock_db):
    event = create_event("platform_admin", "/platform/tenants")
    mock_db["table"].scan.return_value = {"Items": []}
    
    resp = platform_handler(event, None)
    assert resp["statusCode"] == 200

def test_other_roles_denied(mock_db):
    roles = ["owner", "Admin", "Staff", "Client", "unknown"]
    for role in roles:
        event = create_event(role, "/platform/tenants")
        resp = platform_handler(event, None)
        assert resp["statusCode"] == 403
        assert "Forbidden" in json.loads(resp["body"])["error"]

def test_missing_claims_denied(mock_db):
    event = {
        "requestContext": {},
        "httpMethod": "GET",
        "path": "/platform/tenants"
    }
    resp = platform_handler(event, None)
    assert resp["statusCode"] == 403

def test_platform_only_admin_denied_from_normal_admin_endpoints(mock_db):
    # Platform admin tries to hit /admin/requests -> should get 403 Forbidden
    event = create_event("platform_admin", "/admin/requests", method="GET")
    resp = admin_handler(event, None)
    assert resp["statusCode"] == 403
    assert "Forbidden" in json.loads(resp["body"])["error"]

# ---------------------------------------------------------------------------
# 2. GET /platform/tenants
# ---------------------------------------------------------------------------

def test_get_tenants_returns_safe_summary_only(mock_db):
    mock_db["table"].scan.return_value = {
        "Items": [
            {
                "PK": "TENANT#tog_and_dogs",
                "SK": "METADATA",
                "company_id": "tog_and_dogs",
                "display_name": "Togs & Dogs",
                "subscription_tier": "professional",
                "subscription_status": "active",
                "stripe_customer_id": "cust_1234",
                "stripe_subscription_id": "sub_5678",
                "owner_email": "owner@dogs.com",
                "created_at": "2026-01-01T00:00:00Z"
            }
        ]
    }
    
    event = create_event("platform_admin", "/platform/tenants")
    resp = platform_handler(event, None)
    assert resp["statusCode"] == 200
    
    body = json.loads(resp["body"])
    assert "tenants" in body
    assert len(body["tenants"]) == 1
    tenant = body["tenants"][0]
    
    # Safe fields only
    assert tenant["company_id"] == "tog_and_dogs"
    assert tenant["display_name"] == "Togs & Dogs"
    assert tenant["subscription_tier"] == "professional"
    assert tenant["subscription_status"] == "active"
    assert tenant["created_at"] == "2026-01-01T00:00:00Z"
    
    # Exclude sensitive fields
    assert "stripe_customer_id" not in tenant
    assert "stripe_subscription_id" not in tenant
    assert "owner_email" not in tenant

# ---------------------------------------------------------------------------
# 3. GET /platform/tenants/{company_id}
# ---------------------------------------------------------------------------

def test_get_tenant_details_success(mock_db):
    tenant_metadata = {
        "PK": "TENANT#tog_and_dogs",
        "SK": "METADATA",
        "company_id": "tog_and_dogs",
        "display_name": "Togs & Dogs",
        "subscription_tier": "professional",
        "subscription_status": "active",
        "primary_color": "#123456",
        "secondary_color": "#789abc",
        "timezone": "America/New_York",
        "logo_url": "https://dogs.com/logo.png",
        "portal_url": "https://dogs.com",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-06-12T00:00:00Z",
        "notes": "Platform note",
        "admin_override_until": "2026-12-31T00:00:00Z",
        "stripe_customer_id": "cust_1234"
    }
    mock_db["get_item"].return_value = tenant_metadata
    
    # Query return values for staff and clients called sequentially:
    # 1. Staff count query
    # 2. Client count query
    mock_db["table"].query.side_effect = [
        {
            "Items": [
                {"staff_id": "staff_1", "is_active": True},
                {"staff_id": "staff_2", "is_active": True},
                {"staff_id": "staff_3", "is_active": False}
            ]
        },
        {
            "Items": [
                {"client_id": "client_1", "is_active": True},
                {"client_id": "client_2", "is_active": True},
                {"client_id": "client_3", "is_active": True},
                {"client_id": "client_4", "is_active": False}
            ]
        }
    ]
    # Scan called for monthly bookings
    mock_db["table"].scan.return_value = {
        "Items": [
            {"request_id": "req_1"},
            {"request_id": "req_2"}
        ]
    }
    
    event = create_event(
        role="platform_admin",
        path="/platform/tenants/tog_and_dogs",
        path_params={"company_id": "tog_and_dogs"}
    )
    
    resp = platform_handler(event, None)
    assert resp["statusCode"] == 200
    
    body = json.loads(resp["body"])
    assert body["company_id"] == "tog_and_dogs"
    
    # Safe Profile
    profile = body["profile"]
    assert profile["display_name"] == "Togs & Dogs"
    assert profile["primary_color"] == "#123456"
    assert profile["logo_url"] == "https://dogs.com/logo.png"
    assert profile["notes"] == "Platform note"
    assert profile["admin_override_until"] == "2026-12-31T00:00:00Z"
    assert "stripe_customer_id" not in profile # excluded
    
    # Subscription
    assert body["subscription"]["tier"] == "professional"
    assert body["subscription"]["status"] == "active"
    
    # Entitlement Summary
    ent = body["entitlement_summary"]
    assert ent["subscription_tier"] == "professional"
    assert ent["subscription_status"] == "active"
    assert ent["limits"]["max_staff"] == 5
    assert ent["limits"]["google_calendar_enabled"] is True
    
    # Usage Counts
    counts = body["usage_counts"]
    assert counts["active_staff"] == 2
    assert counts["active_clients"] == 3
    assert counts["monthly_bookings"] == 2

def test_get_tenant_not_found(mock_db):
    mock_db["get_item"].return_value = None
    event = create_event(
        role="platform_admin",
        path="/platform/tenants/missing_tenant",
        path_params={"company_id": "missing_tenant"}
    )
    resp = platform_handler(event, None)
    assert resp["statusCode"] == 404

# ---------------------------------------------------------------------------
# 4. PATCH /platform/tenants/{company_id}
# ---------------------------------------------------------------------------

def test_patch_tenant_success(mock_db):
    tenant_metadata = {
        "PK": "TENANT#tog_and_dogs",
        "SK": "METADATA",
        "company_id": "tog_and_dogs",
        "display_name": "Togs & Dogs",
        "subscription_tier": "starter",
        "subscription_status": "disabled",
        "admin_override_until": None,
        "notes": "Old note"
    }
    mock_db["get_item"].return_value = tenant_metadata
    mock_db["update_item"].return_value = True
    mock_db["put_item"].return_value = True
    
    # Mocking counts as 0
    mock_db["table"].query.return_value = {"Items": []}
    mock_db["table"].scan.return_value = {"Items": []}
    
    future_override = (datetime.now(timezone.utc) + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    patch_payload = {
        "display_name": "Togs & Dogs Updated",
        "subscription_tier": "professional",
        "subscription_status": "active",
        "admin_override_until": future_override,
        "notes": "New note"
    }
    
    event = create_event(
        role="platform_admin",
        path="/platform/tenants/tog_and_dogs",
        method="PATCH",
        body_dict=patch_payload,
        path_params={"company_id": "tog_and_dogs"},
        email="platform-tester@test.com"
    )
    
    # Return old metadata first, then the updated metadata on get_item calls
    old_meta = {
        "PK": "TENANT#tog_and_dogs",
        "SK": "METADATA",
        "company_id": "tog_and_dogs",
        "display_name": "Togs & Dogs",
        "subscription_tier": "starter",
        "subscription_status": "disabled",
        "admin_override_until": None,
        "notes": "Old note"
    }
    new_meta = {
        "PK": "TENANT#tog_and_dogs",
        "SK": "METADATA",
        "company_id": "tog_and_dogs",
        "display_name": "Togs & Dogs Updated",
        "subscription_tier": "professional",
        "subscription_status": "active",
        "admin_override_until": future_override,
        "notes": "New note"
    }
    mock_db["get_item"].side_effect = [old_meta, new_meta]
    
    with patch('handlers.platform_handler.invalidate_entitlement_cache') as mock_invalidate:
        resp = platform_handler(event, None)
        assert resp["statusCode"] == 200
        mock_invalidate.assert_called_once_with("tog_and_dogs")
        
    # Verify update_item parameters
    mock_db["update_item"].assert_called_once()
    called_pk, called_sk, called_attrs = mock_db["update_item"].call_args[0]
    assert called_pk == "TENANT#tog_and_dogs"
    assert called_sk == "METADATA"
    assert called_attrs["display_name"] == "Togs & Dogs Updated"
    assert called_attrs["subscription_tier"] == "professional"
    assert called_attrs["subscription_status"] == "active"
    assert called_attrs["admin_override_until"] == future_override
    assert called_attrs["notes"] == "New note"
    assert "updated_at" in called_attrs
    assert called_attrs["updated_by"] == "platform_admin:platform-tester@test.com"
    
    # Verify audit record is written
    mock_db["put_item"].assert_called_once()
    audit_rec = mock_db["put_item"].call_args[0][0]
    assert audit_rec["PK"] == "PLATFORM_AUDIT"
    assert audit_rec["SK"].startswith("ACTION#")
    assert audit_rec["action"] == "UPDATE_TENANT"
    assert audit_rec["target_company_id"] == "tog_and_dogs"
    assert audit_rec["actor"] == "platform-tester@test.com"
    assert set(audit_rec["changed_fields"]) == {"display_name", "subscription_tier", "subscription_status", "admin_override_until", "notes"}
    assert audit_rec["old_values"]["display_name"] == "Togs & Dogs"
    assert audit_rec["new_values"]["display_name"] == "Togs & Dogs Updated"

def test_patch_tenant_rejects_unsupported_fields(mock_db):
    tenant_metadata = {"PK": "TENANT#tog_and_dogs", "SK": "METADATA"}
    mock_db["get_item"].return_value = tenant_metadata
    
    event = create_event(
        role="platform_admin",
        path="/platform/tenants/tog_and_dogs",
        method="PATCH",
        body_dict={
            "stripe_customer_id": "cust_unauthorized_override",
            "subscription_tier": "starter"
        },
        path_params={"company_id": "tog_and_dogs"}
    )
    resp = platform_handler(event, None)
    assert resp["statusCode"] == 400
    assert "Unsupported fields" in json.loads(resp["body"])["error"]

def test_patch_tenant_validation_display_name(mock_db):
    tenant_metadata = {"PK": "TENANT#tog_and_dogs", "SK": "METADATA"}
    mock_db["get_item"].return_value = tenant_metadata
    
    # 1. Reject non-string
    event = create_event(
        role="platform_admin",
        path="/platform/tenants/tog_and_dogs",
        method="PATCH",
        body_dict={"display_name": 123},
        path_params={"company_id": "tog_and_dogs"}
    )
    assert platform_handler(event, None)["statusCode"] == 400
    
    # 2. Reject empty/spaces
    event = create_event(
        role="platform_admin",
        path="/platform/tenants/tog_and_dogs",
        method="PATCH",
        body_dict={"display_name": "   "},
        path_params={"company_id": "tog_and_dogs"}
    )
    assert platform_handler(event, None)["statusCode"] == 400
    
    # 3. Reject too long
    event = create_event(
        role="platform_admin",
        path="/platform/tenants/tog_and_dogs",
        method="PATCH",
        body_dict={"display_name": "A" * 101},
        path_params={"company_id": "tog_and_dogs"}
    )
    assert platform_handler(event, None)["statusCode"] == 400

def test_patch_tenant_validation_override_until(mock_db):
    tenant_metadata = {"PK": "TENANT#tog_and_dogs", "SK": "METADATA"}
    mock_db["get_item"].return_value = tenant_metadata
    
    # 1. Reject past timestamp
    past_ts = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
    event = create_event(
        role="platform_admin",
        path="/platform/tenants/tog_and_dogs",
        method="PATCH",
        body_dict={"admin_override_until": past_ts},
        path_params={"company_id": "tog_and_dogs"}
    )
    assert platform_handler(event, None)["statusCode"] == 400
    
    # 2. Reject invalid ISO format
    event = create_event(
        role="platform_admin",
        path="/platform/tenants/tog_and_dogs",
        method="PATCH",
        body_dict={"admin_override_until": "not-a-date"},
        path_params={"company_id": "tog_and_dogs"}
    )
    assert platform_handler(event, None)["statusCode"] == 400

# ---------------------------------------------------------------------------
# 5. GET /platform/audit
# ---------------------------------------------------------------------------

def test_get_audit_history_pagination(mock_db):
    # Returns 2 audits and a pagination key
    mock_db["table"].query.return_value = {
        "Items": [
            {"PK": "PLATFORM_AUDIT", "SK": "ACTION#2026-06-21T00:00:00Z#1", "action": "UPDATE_TENANT"},
            {"PK": "PLATFORM_AUDIT", "SK": "ACTION#2026-06-21T00:01:00Z#2", "action": "UPDATE_TENANT"}
        ],
        "LastEvaluatedKey": {"PK": "PLATFORM_AUDIT", "SK": "ACTION#2026-06-21T00:01:00Z#2"}
    }
    
    event = create_event(
        role="platform_admin",
        path="/platform/audit"
    )
    
    resp = platform_handler(event, None)
    assert resp["statusCode"] == 200
    
    body = json.loads(resp["body"])
    assert len(body["audits"]) == 2
    assert "lastKey" in body
    
    # Decode lastKey
    decoded_key = json.loads(base64.b64decode(body["lastKey"].encode('utf-8')).decode('utf-8'))
    assert decoded_key["SK"] == "ACTION#2026-06-21T00:01:00Z#2"
    
    # Verify pagination input works
    event_paginated = create_event(
        role="platform_admin",
        path="/platform/audit",
        query_params={"lastKey": body["lastKey"]}
    )
    
    platform_handler(event_paginated, None)
    mock_db["table"].query.assert_called_with(
        KeyConditionExpression=ANY,
        ScanIndexForward=False,
        Limit=50,
        ExclusiveStartKey=decoded_key
    )
