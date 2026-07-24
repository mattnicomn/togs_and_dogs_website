import json
import logging
import sys
import io
import pytest
from unittest.mock import patch, MagicMock, call
from boto3.dynamodb.conditions import Key

# Import handlers and common utilities
from handlers.pet_handler import handler as pet_handler
from common.pet_profile import _get_client_pets, create_or_link_pets_from_request, _rebuild_pet_summary

# Setup helper for event creation
def create_event(role, path="/admin/pets", method="GET", query_params=None, client_id=None):
    claims = {"email": f"{role.lower()}@usmissionhero.com", "sub": "test-sub-123"}
    if role == "Admin":
        claims["cognito:groups"] = "Admin"
    elif role == "Owner":
        claims["cognito:groups"] = "owner"
    elif role == "Staff":
        claims["cognito:groups"] = "Staff"
    elif role == "Client":
        claims["cognito:groups"] = "client"
        if client_id:
            claims["sub"] = client_id

    event = {
        "requestContext": {"authorizer": {"claims": claims}},
        "httpMethod": method,
        "path": path,
    }
    if query_params:
        event["queryStringParameters"] = query_params
    return event


@pytest.fixture
def mock_db_table():
    with patch('common.db.table') as mock_table:
        yield mock_table


# --- 1. Canonical Client Ownership Success / Missing / Denial (Req 1, 2, 3, 24, 26) ---

def test_admin_list_pets_canonical_client_found(mock_db_table):
    """Req 1: Mocks get_item client validation with correct PK/SK and returns success on success."""
    event = create_event("Admin", query_params={"clientId": "client_123"})

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }
    mock_db_table.query.return_value = {"Items": []}

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    mock_db_table.get_item.assert_called_with(Key={"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"})
    mock_db_table.query.assert_called_once()


def test_admin_list_pets_canonical_client_missing(mock_db_table):
    """Req 2, 24: Client not found returns success empty list immediately without query/scan."""
    event = create_event("Admin", query_params={"clientId": "client_123"})

    mock_db_table.get_item.return_value = {} # Item not in response

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body == {"pets": []}
    mock_db_table.query.assert_not_called()
    mock_db_table.scan.assert_not_called()


def test_admin_list_pets_cross_tenant_denial(mock_db_table):
    """Req 3, 26: Mocks get_item to return empty (not found in tenant's company), preventing cross-tenant discovery.
       Ensures no query/scan is executed and no raw identifiers are logged on denial.
    """
    event = create_event("Admin", query_params={"clientId": "client_foreign"})

    # Client exists in DB but not under caller's company (tog_and_dogs)
    # PK will be COMPANY#tog_and_dogs, SK=CLIENT#client_foreign. It returns None because it's not found in that company context.
    mock_db_table.get_item.return_value = {}

    # Capture stdout/stderr/logs to verify no raw identifiers leak
    stdout_capture = io.StringIO()
    sys.stdout = stdout_capture

    try:
        with patch('handlers.pet_handler.table', mock_db_table), \
             patch('common.entitlement.require_active_tenant', return_value=None):
            resp = pet_handler(event, None)
    finally:
        sys.stdout = sys.__stdout__

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body == {"pets": []} # Silently returns empty list, does not expose cross-tenant existence
    mock_db_table.query.assert_not_called()
    mock_db_table.scan.assert_not_called()

    # Assert logs/stdout don't leak identifiers
    log_output = stdout_capture.getvalue()
    assert "client_foreign" not in log_output


# --- 2. Query Configuration (Req 4, 5, 6, 7, 25) ---

def test_query_configuration_parameters(mock_db_table):
    """Req 4, 5, 6, 7, 25: Verify query arguments: ClientPetIndex, key condition, no ConsistentRead, no scan fallback."""
    event = create_event("Admin", query_params={"clientId": "client_123"})

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }
    mock_db_table.query.return_value = {"Items": []}

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        pet_handler(event, None)

    mock_db_table.query.assert_called_once()
    kwargs = mock_db_table.query.call_args[1]

    # Assert GSI IndexName is exactly ClientPetIndex
    assert kwargs.get("IndexName") == "ClientPetIndex"

    # Assert partition key targets client_id
    assert kwargs.get("KeyConditionExpression") == Key('client_id').eq('client_123')

    # Assert ConsistentRead is not set or not True
    assert kwargs.get("ConsistentRead") is not True

    # Assert scan fallback is never used
    mock_db_table.scan.assert_not_called()


# --- 3. Pagination (Req 8, 9, 10) ---

def test_query_pagination_single_page(mock_db_table):
    """Req 8: Loop terminates on single page without LastEvaluatedKey."""
    event = create_event("Admin", query_params={"clientId": "client_123"})

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }
    mock_db_table.query.return_value = {
        "Items": [
            {"PK": "PET#pet_1", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "tog_and_dogs", "is_active": True}
        ]
    }

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    assert len(json.loads(resp["body"])["pets"]) == 1
    assert mock_db_table.query.call_count == 1


def test_query_pagination_multiple_pages(mock_db_table):
    """Req 9: Loop processes multiple pages via ExclusiveStartKey and returns accumulated results."""
    event = create_event("Admin", query_params={"clientId": "client_123"})

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }

    # Mock query returning a second page
    mock_db_table.query.side_effect = [
        {"Items": [{"PK": "PET#pet_1", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "tog_and_dogs", "is_active": True}], "LastEvaluatedKey": {"PK": "PET#pet_1", "SK": "CLIENT#client_123"}},
        {"Items": [{"PK": "PET#pet_2", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "tog_and_dogs", "is_active": True}]}
    ]

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body["pets"]) == 2
    assert mock_db_table.query.call_count == 2

    # Assert correct propagation of ExclusiveStartKey
    calls = mock_db_table.query.call_args_list
    assert "ExclusiveStartKey" not in calls[0][1]
    assert calls[1][1]["ExclusiveStartKey"] == {"PK": "PET#pet_1", "SK": "CLIENT#client_123"}


def test_query_pagination_empty_first_page(mock_db_table):
    """Req 10: Loop processes empty page with LastEvaluatedKey followed by populated page."""
    event = create_event("Admin", query_params={"clientId": "client_123"})

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }

    mock_db_table.query.side_effect = [
        {"Items": [], "LastEvaluatedKey": {"PK": "PET#dummy", "SK": "CLIENT#client_123"}},
        {"Items": [{"PK": "PET#pet_1", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "tog_and_dogs", "is_active": True}]}
    ]

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body["pets"]) == 1
    assert mock_db_table.query.call_count == 2

    calls = mock_db_table.query.call_args_list
    assert calls[1][1]["ExclusiveStartKey"] == {"PK": "PET#dummy", "SK": "CLIENT#client_123"}


# --- 4. company_id and is_active filtering (Req 11, 12, 13, 14, 15, 16) ---

def test_company_id_and_is_active_filtering(mock_db_table):
    """Req 11, 12, 13, 14, 15, 16: Verify filtering rules:
       - Missing company_id: Excluded
       - Mismatched company_id: Excluded
       - Matching company_id: Included
       - is_active=False: Excluded
       - is_active=True: Included
       - Missing is_active: Included (default to active)
    """
    event = create_event("Admin", query_params={"clientId": "client_123"})

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }

    mock_pets = [
        {"PK": "PET#p1", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "tog_and_dogs", "is_active": True}, # OK
        {"PK": "PET#p2", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "tog_and_dogs"}, # missing is_active (default True) -> OK
        {"PK": "PET#p3", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "tog_and_dogs", "is_active": False}, # is_active False -> EXCLUDE
        {"PK": "PET#p4", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "different_company", "is_active": True}, # mismatched company -> EXCLUDE
        {"PK": "PET#p5", "SK": "CLIENT#client_123", "entity_type": "PET", "is_active": True}, # missing company -> EXCLUDE
        {"PK": "NONPET#1", "SK": "CLIENT#client_123", "entity_type": "CLIENT", "company_id": "tog_and_dogs", "is_active": True} # non-PET entity -> EXCLUDE
    ]
    mock_db_table.query.return_value = {"Items": mock_pets}

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body["pets"]) == 2
    pet_ids = [p["PK"] for p in body["pets"]]
    assert "PET#p1" in pet_ids
    assert "PET#p2" in pet_ids


# --- 5. Response Contracts (Req 17, 18, 19, 20) ---

def test_admin_response_contract_format(mock_db_table):
    """Req 18: Admin path returns 200, {"pets": [...]}, and no pagination token or metadata."""
    event = create_event("Admin", query_params={"clientId": "client_123"})

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }
    mock_db_table.query.return_value = {"Items": []}

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "pets" in body
    assert isinstance(body["pets"], list)
    assert len(body.keys()) == 1  # Only "pets" key should be present in the body


def test_client_portal_response_contract_format(mock_db_table):
    """Req 19: Client portal path returns 200, {"pets": [...]}, and sanitizes fields (e.g. quote_amount, internal_pricing_notes)."""
    # Create client event
    event = create_event("Client", path="/client/pets", client_id="client_123")

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }

    # Mock client resolve identity
    mock_pets = [
        {
            "PK": "PET#pet_1",
            "SK": "CLIENT#client_123",
            "entity_type": "PET",
            "company_id": "tog_and_dogs",
            "name": "Buddy",
            "is_active": True,
            "internal_pricing_notes": "sensitive admin notes",
            "quote_amount": 150
        }
    ]
    mock_db_table.query.return_value = {"Items": mock_pets}

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.auth.resolve_client_identity', return_value="client_123"), \
         patch('common.auth.get_current_company_id', return_value="tog_and_dogs"), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "pets" in body
    assert len(body["pets"]) == 1

    pet = body["pets"][0]
    assert pet["name"] == "Buddy"
    # Verify client role sanitization: sensitive fields are completely absent from allowlist response
    assert "internal_pricing_notes" not in pet
    assert "notes_redacted" not in pet


# --- 6. Internal Helper _get_client_pets (Req 20, 21) ---

def test_internal_helper_get_client_pets_success(mock_db_table):
    """Req 20: _get_client_pets returns raw list, filters and handles empty correctly."""
    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}
    }
    mock_db_table.query.return_value = {
        "Items": [
            {"PK": "PET#pet_1", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "tog_and_dogs", "is_active": True},
            {"PK": "PET#pet_2", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "tog_and_dogs", "is_active": False}
        ]
    }

    with patch('common.pet_profile.table', mock_db_table):
        pets = _get_client_pets("client_123", "tog_and_dogs")

    assert isinstance(pets, list)
    assert len(pets) == 1
    assert pets[0]["PK"] == "PET#pet_1"


def test_internal_helper_get_client_pets_empty_on_client_missing(mock_db_table):
    """Req 20: _get_client_pets returns [] if client does not exist, no query executed."""
    mock_db_table.get_item.return_value = {} # Client missing

    with patch('common.pet_profile.table', mock_db_table):
        pets = _get_client_pets("client_123", "tog_and_dogs")

    assert pets == []
    mock_db_table.query.assert_not_called()


def test_internal_helper_callers_pass_company_id(mock_db_table):
    """Req 21: Verify both callers create_or_link_pets_from_request and _rebuild_pet_summary pass company_id."""
    request_item = {
        "PK": "REQ#req_123",
        "SK": "CLIENT#client_123",
        "pets": [{"name": "Buddy", "breed": "Golden"}]
    }

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}
    }
    mock_db_table.query.return_value = {"Items": []}
    mock_db_table.update_item.return_value = {}

    with patch('common.pet_profile.table', mock_db_table), \
         patch('common.pet_profile.put_item', return_value=True):
        create_or_link_pets_from_request(request_item, "req_123", "client_123", "tog_and_dogs")

    # Assert get_item was called twice: once in create_or_link_pets_from_request's internal call to _get_client_pets,
    # and once in _rebuild_pet_summary's internal call to _get_client_pets. Both should validate client.
    assert mock_db_table.get_item.call_count == 2
    mock_db_table.get_item.assert_has_calls([
        call(Key={"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}),
        call(Key={"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"})
    ])


# --- 7. DynamoDB Query Exception / Error Handling (Req 22) ---

def test_handler_query_exception_returns_safe_error(mock_db_table):
    """Req 22: Handler catches DynamoDB exceptions on query and returns 500 error response without Scan fallback."""
    event = create_event("Admin", query_params={"clientId": "client_123"})

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }
    mock_db_table.query.side_effect = Exception("DynamoDB Query Failed")

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 500
    mock_db_table.scan.assert_not_called()


def test_helper_query_exception_fallback(mock_db_table):
    """Req 22: Helper catches DynamoDB exceptions and returns empty list [] safely."""
    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}
    }
    mock_db_table.query.side_effect = Exception("DynamoDB Query Failed")

    with patch('common.pet_profile.table', mock_db_table):
        pets = _get_client_pets("client_123", "tog_and_dogs")

    assert pets == []
    mock_db_table.scan.assert_not_called()


# --- Phase 1B.5A.1 GET /client/pets Route & Branching Tests ---

def test_linked_client_list_success(mock_db_table):
    """1. Linked client GET /client/pets returns the client's pets."""
    event = create_event("Client", path="/client/pets")

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }
    mock_db_table.query.return_value = {
        "Items": [
            {"PK": "PET#pet1", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "tog_and_dogs", "name": "Buddy", "is_active": True}
        ]
    }

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.auth.resolve_client_identity', return_value="client_123"), \
         patch('common.auth.get_current_company_id', return_value="tog_and_dogs"), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "pets" in body
    assert len(body["pets"]) == 1
    assert body["pets"][0]["name"] == "Buddy"


def test_linked_client_list_tenant_scoped(mock_db_table):
    """2. Linked client response remains tenant-scoped (filters out cross-tenant pets)."""
    event = create_event("Client", path="/client/pets")

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }
    mock_db_table.query.return_value = {
        "Items": [
            {"PK": "PET#pet1", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "tog_and_dogs", "name": "Buddy", "is_active": True},
            {"PK": "PET#pet2", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "other_company", "name": "Spy", "is_active": True}
        ]
    }

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.auth.resolve_client_identity', return_value="client_123"), \
         patch('common.auth.get_current_company_id', return_value="tog_and_dogs"), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body["pets"]) == 1
    assert body["pets"][0]["name"] == "Buddy"


def test_linked_client_list_sanitized(mock_db_table):
    """3. Linked client response remains sanitized for client visibility."""
    event = create_event("Client", path="/client/pets")

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }
    mock_db_table.query.return_value = {
        "Items": [
            {"PK": "PET#pet1", "SK": "CLIENT#client_123", "entity_type": "PET", "company_id": "tog_and_dogs", "name": "Buddy", "is_active": True, "internal_pricing_notes": "sensitive", "quote_amount": 100}
        ]
    }

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.auth.resolve_client_identity', return_value="client_123"), \
         patch('common.auth.get_current_company_id', return_value="tog_and_dogs"), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    pet = body["pets"][0]
    assert pet["name"] == "Buddy"
    assert "internal_pricing_notes" not in pet or pet["internal_pricing_notes"] is None


def test_linked_client_list_empty(mock_db_table):
    """4. Linked client with no pets returns HTTP 200 and pets: []."""
    event = create_event("Client", path="/client/pets")

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }
    mock_db_table.query.return_value = {"Items": []}

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.auth.resolve_client_identity', return_value="client_123"), \
         patch('common.auth.get_current_company_id', return_value="tog_and_dogs"), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["pets"] == []
    assert "message" not in body or body["message"] is None


def test_unlinked_client_list(mock_db_table):
    """5. Unlinked client identity returns HTTP 200, pets: [], and unlinked message/status."""
    event = create_event("Client", path="/client/pets")

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.auth.resolve_client_identity', return_value=None), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["pets"] == []
    assert body["message"] == "No local profile linked"
    assert body["linked_profile"] is False


def test_owner_client_list_unlinked(mock_db_table):
    """6. Owner identity requesting GET /client/pets receives the same safe unlinked contract."""
    event = create_event("Owner", path="/client/pets")

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.auth.resolve_client_identity', return_value=None), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["pets"] == []
    assert body["message"] == "No local profile linked"
    assert body["linked_profile"] is False


def test_admin_client_list_unlinked(mock_db_table):
    """7. Admin identity requesting GET /client/pets receives the same safe unlinked contract."""
    event = create_event("Admin", path="/client/pets")

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.auth.resolve_client_identity', return_value=None), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["pets"] == []
    assert body["message"] == "No local profile linked"
    assert body["linked_profile"] is False


def test_client_list_never_missing_pet_id(mock_db_table):
    """8. GET /client/pets never returns 'Missing petId in path'."""
    # Even if client resolution fails completely, it should return unlinked response, not "Missing petId in path"
    event = create_event("Client", path="/client/pets")

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.auth.resolve_client_identity', return_value=None), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "Missing petId in path" not in resp.get("body", "")
    assert body["message"] == "No local profile linked"


def test_admin_pets_query_param_unchanged(mock_db_table):
    """9. GET /admin/pets?clientId remains unchanged."""
    event = create_event("Admin", path="/admin/pets", query_params={"clientId": "client_123"})

    mock_db_table.get_item.return_value = {
        "Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}
    }
    mock_db_table.query.return_value = {"Items": []}

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.auth.get_current_company_id', return_value="tog_and_dogs"), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "pets" in body


def test_admin_pet_detail_unchanged(mock_db_table):
    """10. GET /admin/pets/{petId} remains unchanged."""
    event = create_event("Admin", path="/admin/pets/pet_123", query_params={"clientId": "client_123"})
    event["pathParameters"] = {"petId": "pet_123"}

    mock_db_table.get_item.side_effect = [
        {"Item": {"PK": "PET#pet_123", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs", "name": "Buddy"}},
        {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs"}}
    ]

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.auth.get_current_company_id', return_value="tog_and_dogs"), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["name"] == "Buddy"


def test_cross_tenant_admin_detail_denied(mock_db_table):
    """11. Cross-tenant admin/client pet access remains denied or filtered according to existing rules."""
    # Try accessing a pet belonging to client_123, but caller belongs to different company
    event = create_event("Admin", path="/admin/pets/pet_123", query_params={"clientId": "client_123"})
    event["pathParameters"] = {"petId": "pet_123"}

    # First call: get PET record
    # Second call: get CLIENT record (it returns None or company mismatch)
    mock_db_table.get_item.side_effect = [
        {"Item": {"PK": "PET#pet_123", "SK": "CLIENT#client_123", "company_id": "tog_and_dogs", "name": "Buddy"}},
        {} # CLIENT verify fails safely by returning empty dict
    ]

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.auth.get_current_company_id', return_value="other_company"), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 403


def test_malformed_detail_requests_missing_client_id(mock_db_table):
    """12. Malformed detail requests (missing clientId query parameter) still use the existing safe detail error path."""
    event = create_event("Admin", path="/admin/pets/pet_123") # No clientId in query params
    event["pathParameters"] = {"petId": "pet_123"}

    with patch('handlers.pet_handler.table', mock_db_table), \
         patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["error"] == "Missing clientId in query params"
