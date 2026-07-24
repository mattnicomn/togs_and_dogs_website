import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers.pet_handler import handler as pet_handler

def make_event(role='client', company_id='tog_and_dogs', method='PUT', path='/client/pets/pet_123', path_params=None, body=None, email="client@example.com", cognito_sub="sub_123", email_verified=True):
    claims = {
        "email": email,
        "custom:company_id": company_id
    }
    if role and role != 'unknown':
        claims["cognito:groups"] = role
    if cognito_sub:
        claims["sub"] = cognito_sub
    if email_verified is not None:
        claims["email_verified"] = "true" if email_verified else "false"

    return {
        "requestContext": {
            "authorizer": {
                "claims": claims
            }
        },
        "httpMethod": method,
        "path": path,
        "pathParameters": path_params or {"petId": path.split('/')[-1]},
        "body": json.dumps(body) if body is not None else "{}"
    }

@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
@patch('common.db.table')
def test_customer_pet_update_success(mock_table, mock_put, mock_get, mock_resolve_id):
    """A client can update their own active pet with allowed fields."""
    mock_resolve_id.return_value = "client_123"
    mock_get.return_value = {
        "PK": "PET#pet_123",
        "SK": "CLIENT#client_123",
        "company_id": "tog_and_dogs",
        "client_id": "client_123",
        "pet_id": "pet_123",
        "name": "Buddy",
        "species": "DOG",
        "breed": "Golden Retriever",
        "age": "3",
        "is_active": True,
        "health": {
            "vet_name": "Dr. Smith",
            "vet_phone": "123-456-7890",
            "some_private_field": "hidden"
        }
    }
    mock_put.return_value = True

    event = make_event(
        body={
            "name": "Buddy Jr.",
            "species": "DOG",
            "health": {
                "vet_name": "Dr. Jones"
            }
        }
    )

    with patch('common.entitlement.require_active_tenant', return_value=None), \
         patch('common.audit.log_action') as mock_log, \
         patch('common.pet_profile._rebuild_pet_summary') as mock_rebuild:
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    
    # Assert return object is sanitized for client (e.g. no sensitive stuff, but contains update)
    assert body["name"] == "Buddy Jr."
    assert body["species"] == "DOG"
    assert body["health"]["vet_name"] == "Dr. Jones"
    assert body["health"]["vet_phone"] == "123-456-7890"  # preserved
    assert "some_private_field" not in body["health"]  # redacted for client
    
    # Assert mock audit logging occurred
    mock_log.assert_called_once()
    args, kwargs = mock_log.call_args
    assert kwargs["action"] == "CUSTOMER_PET_UPDATE"
    assert kwargs["target_pk"] == "PET#pet_123"
    assert kwargs["target_sk"] == "CLIENT#client_123"
    assert "name" in kwargs["metadata"]["changed_fields"]
    assert "health.vet_name" in kwargs["metadata"]["changed_fields"]

    # Assert rebuild summary was called
    mock_rebuild.assert_called_once_with("client_123", "tog_and_dogs")


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
@patch('common.db.table')
def test_customer_pet_update_unauthenticated(mock_table, mock_get, mock_resolve_id):
    """An unauthenticated request returns 401."""
    event = make_event(role='unknown')

    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 401
    assert "Unauthenticated" in json.loads(resp["body"])["error"]


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
@patch('common.db.table')
def test_customer_pet_update_unauthorized_role(mock_table, mock_get, mock_resolve_id):
    """Staff role is forbidden from using the client endpoint."""
    event = make_event(role='staff')

    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 403
    assert "Forbidden" in json.loads(resp["body"])["error"]


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
@patch('common.db.table')
def test_customer_pet_update_cross_client(mock_table, mock_get, mock_resolve_id):
    """A client cannot update another client's pet (returns 404)."""
    mock_resolve_id.return_value = "client_123"
    
    # Pet exists but is owned by client_999
    mock_get.return_value = {
        "PK": "PET#pet_123",
        "SK": "CLIENT#client_999",
        "company_id": "tog_and_dogs",
        "client_id": "client_999",
        "pet_id": "pet_123",
        "name": "Buddy",
        "is_active": True
    }

    event = make_event(body={"name": "New Name"})

    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 404


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
@patch('common.db.table')
def test_customer_pet_update_cross_tenant(mock_table, mock_get, mock_resolve_id):
    """A client cannot update a pet under a different tenant (returns 404)."""
    mock_resolve_id.return_value = "client_123"
    
    # Pet exists under different company
    mock_get.return_value = {
        "PK": "PET#pet_123",
        "SK": "CLIENT#client_123",
        "company_id": "other_company",
        "client_id": "client_123",
        "pet_id": "pet_123",
        "name": "Buddy",
        "is_active": True
    }

    event = make_event(body={"name": "New Name"})

    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 404


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
@patch('common.db.table')
def test_customer_pet_update_archived_pet(mock_table, mock_get, mock_resolve_id):
    """An archived pet cannot be updated (returns 404)."""
    mock_resolve_id.return_value = "client_123"
    mock_get.return_value = {
        "PK": "PET#pet_123",
        "SK": "CLIENT#client_123",
        "company_id": "tog_and_dogs",
        "client_id": "client_123",
        "pet_id": "pet_123",
        "name": "Buddy",
        "is_active": False  # Archived
    }

    event = make_event(body={"name": "New Name"})

    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 404


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
@patch('common.db.table')
def test_customer_pet_update_prohibited_field(mock_table, mock_get, mock_resolve_id):
    """Reject requests containing prohibited fields (e.g. photo_url, color, weight, is_active)."""
    mock_resolve_id.return_value = "client_123"
    mock_get.return_value = {
        "PK": "PET#pet_123",
        "SK": "CLIENT#client_123",
        "company_id": "tog_and_dogs",
        "client_id": "client_123",
        "pet_id": "pet_123",
        "name": "Buddy",
        "is_active": True
    }

    # photo_url is prohibited for customer update in this phase
    event = make_event(body={"name": "Buddy", "photo_url": "http://example.com/photo.jpg"})

    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 400
    assert "not allowed" in json.loads(resp["body"])["error"]


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
@patch('common.db.table')
def test_customer_pet_update_prohibited_health_field(mock_table, mock_get, mock_resolve_id):
    """Reject requests modifying non-vet health fields."""
    mock_resolve_id.return_value = "client_123"
    mock_get.return_value = {
        "PK": "PET#pet_123",
        "SK": "CLIENT#client_123",
        "company_id": "tog_and_dogs",
        "client_id": "client_123",
        "pet_id": "pet_123",
        "name": "Buddy",
        "is_active": True,
        "health": {}
    }

    # Only vet_name and vet_phone are allowed. medical_conditions is prohibited.
    event = make_event(body={"health": {"vet_name": "Dr. Smith", "medical_conditions": "asthma"}})

    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 400
    assert "not allowed" in json.loads(resp["body"])["error"]


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
@patch('common.db.table')
def test_customer_pet_update_blank_name_rejected(mock_table, mock_get, mock_resolve_id):
    """Blank pet name is rejected."""
    mock_resolve_id.return_value = "client_123"
    mock_get.return_value = {
        "PK": "PET#pet_123",
        "SK": "CLIENT#client_123",
        "company_id": "tog_and_dogs",
        "client_id": "client_123",
        "pet_id": "pet_123",
        "name": "Buddy",
        "is_active": True
    }

    event = make_event(body={"name": "   "})

    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 400
    assert "Name cannot be empty" in json.loads(resp["body"])["error"]


# --- Bounded Corrections Phase 1B.5C-A Additional Tests ---

@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
def test_customer_pet_update_unauthorized_roles(mock_get, mock_resolve_id):
    """Owner, admin, and platform_admin roles are forbidden on client endpoints (403)."""
    mock_resolve_id.return_value = "client_123"
    with patch('common.entitlement.require_active_tenant', return_value=None):
        for role in ['owner', 'admin', 'platform_admin']:
            event = make_event(role=role)
            resp = pet_handler(event, None)
            assert resp["statusCode"] == 403
            assert "Forbidden" in json.loads(resp["body"])["error"]


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
def test_customer_pet_update_invalid_bodies(mock_get, mock_resolve_id):
    """Invalid request bodies (missing, malformed, null, arrays, strings, empty object) return controlled 400 responses."""
    mock_resolve_id.return_value = "client_123"
    mock_get.return_value = {
        "PK": "PET#pet_123",
        "SK": "CLIENT#client_123",
        "company_id": "tog_and_dogs",
        "client_id": "client_123",
        "pet_id": "pet_123",
        "name": "Buddy",
        "is_active": True
    }

    with patch('common.entitlement.require_active_tenant', return_value=None):
        # 1. Missing body (None body key)
        event = make_event(body=None)
        del event['body']
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "Missing request body" in json.loads(resp["body"])["error"]

        # 2. Malformed JSON
        event = make_event(body=None)
        event['body'] = "{invalid_json}"
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "Malformed JSON" in json.loads(resp["body"])["error"]

        # 3. JSON Null body
        event = make_event(body=None)
        event['body'] = "null"
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "cannot be null" in json.loads(resp["body"])["error"]

        # 4. JSON Array body
        event = make_event(body=None)
        event['body'] = "[1, 2, 3]"
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "must be a JSON object" in json.loads(resp["body"])["error"]

        # 5. JSON String body
        event = make_event(body=None)
        event['body'] = '"just a string"'
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "must be a JSON object" in json.loads(resp["body"])["error"]

        # 6. JSON Number body
        event = make_event(body=None)
        event['body'] = '123.45'
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "must be a JSON object" in json.loads(resp["body"])["error"]

        # 7. Empty body object
        event = make_event(body={})
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "cannot be empty" in json.loads(resp["body"])["error"]


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
def test_customer_pet_update_invalid_types_and_limits(mock_get, mock_resolve_id):
    """Field types and generous max limits are strictly validated, rejecting invalid fields with 400."""
    mock_resolve_id.return_value = "client_123"
    mock_get.return_value = {
        "PK": "PET#pet_123",
        "SK": "CLIENT#client_123",
        "company_id": "tog_and_dogs",
        "client_id": "client_123",
        "pet_id": "pet_123",
        "name": "Buddy",
        "is_active": True
    }

    with patch('common.entitlement.require_active_tenant', return_value=None):
        # Invalid type for name (dict instead of string)
        event = make_event(body={"name": {"first": "Buddy"}})
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "must be a string" in json.loads(resp["body"])["error"]

        # Oversized top-level field (name > 100 characters)
        event = make_event(body={"name": "A" * 101})
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "exceeds maximum length" in json.loads(resp["body"])["error"]

        # Oversized text notes field (care_instructions > 2000 characters)
        event = make_event(body={"care_instructions": "A" * 2001})
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "exceeds maximum length" in json.loads(resp["body"])["error"]

        # Non-object health field
        event = make_event(body={"health": "not an object"})
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "health must be a non-null JSON object" in json.loads(resp["body"])["error"]

        # Prohibited health key
        event = make_event(body={"health": {"vet_name": "Dr. Smith", "invalid_key": "some value"}})
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "not allowed" in json.loads(resp["body"])["error"]

        # Invalid type inside health
        event = make_event(body={"health": {"vet_name": 12345}})
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "must be a string" in json.loads(resp["body"])["error"]

        # Oversized field inside health (vet_name > 100 characters)
        event = make_event(body={"health": {"vet_name": "Dr. " + "A" * 100}})
        resp = pet_handler(event, None)
        assert resp["statusCode"] == 400
        assert "exceeds maximum length" in json.loads(resp["body"])["error"]


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_customer_pet_update_unrelated_fields_preserved_and_sanitized(mock_put, mock_get, mock_resolve_id):
    """Unrelated/internal fields remain unchanged in database but are excluded from customer responses."""
    mock_resolve_id.return_value = "client_123"
    mock_get.return_value = {
        "PK": "PET#pet_123",
        "SK": "CLIENT#client_123",
        "company_id": "tog_and_dogs",
        "client_id": "client_123",
        "pet_id": "pet_123",
        "name": "Buddy",
        "photo_url": "http://example.com/buddy.jpg",  # Prohibited from client writes but exists
        "vet_notes": "Internal veterinary notes",
        "is_active": True,
        "health": {
            "vet_name": "Dr. Smith",
            "vet_phone": "123-456-7890",
            "some_private_field": "hidden"
        }
    }
    mock_put.return_value = True

    event = make_event(body={"name": "Buddy New"})

    with patch('common.entitlement.require_active_tenant', return_value=None), \
         patch('common.audit.log_action'), \
         patch('common.pet_profile._rebuild_pet_summary'):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    # Ensure prohibited fields are NOT leaked in response
    assert "photo_url" not in body
    assert "vet_notes" not in body
    assert "PK" not in body
    assert "SK" not in body
    assert "company_id" not in body
    assert "client_id" not in body
    assert "some_private_field" not in body["health"]

    # Verify put_item still preserves the fields in database
    mock_put.assert_called_once()
    put_arg = mock_put.call_args[0][0]
    assert put_arg["name"] == "Buddy New"  # updated
    assert put_arg["photo_url"] == "http://example.com/buddy.jpg"  # preserved
    assert put_arg["vet_notes"] == "Internal veterinary notes"  # preserved
    assert put_arg["health"]["some_private_field"] == "hidden"  # preserved


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_customer_pet_update_summary_rebuild_failure_resilience(mock_put, mock_get, mock_resolve_id):
    """If _rebuild_pet_summary fails, the operation still succeeds and reports success with a warning."""
    mock_resolve_id.return_value = "client_123"
    mock_get.return_value = {
        "PK": "PET#pet_123",
        "SK": "CLIENT#client_123",
        "company_id": "tog_and_dogs",
        "client_id": "client_123",
        "pet_id": "pet_123",
        "name": "Buddy",
        "is_active": True
    }
    mock_put.return_value = True

    event = make_event(body={"name": "Buddy New"})

    # _rebuild_pet_summary raises an exception
    with patch('common.entitlement.require_active_tenant', return_value=None), \
         patch('common.audit.log_action') as mock_log, \
         patch('common.pet_profile._rebuild_pet_summary', side_effect=Exception("Database connection timeout")):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["name"] == "Buddy New"
    assert "_warning" in body
    assert "summary refresh failed" in body["_warning"]
    
    # Audit log was still written
    mock_log.assert_called_once()


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_customer_pet_update_write_failure(mock_put, mock_get, mock_resolve_id):
    """If put_item fails, return 500 internal server error."""
    mock_resolve_id.return_value = "client_123"
    mock_get.return_value = {
        "PK": "PET#pet_123",
        "SK": "CLIENT#client_123",
        "company_id": "tog_and_dogs",
        "client_id": "client_123",
        "pet_id": "pet_123",
        "name": "Buddy",
        "is_active": True
    }
    mock_put.return_value = False

    event = make_event(body={"name": "Buddy New"})

    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 500
    assert "Failed to save pet record" in json.loads(resp["body"])["error"]


@patch('common.auth.resolve_client_identity')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_customer_pet_update_audit_failure_resilience(mock_put, mock_get, mock_resolve_id):
    """If audit log_action fails, the operation still succeeds (audit failure behavior is safe)."""
    mock_resolve_id.return_value = "client_123"
    mock_get.return_value = {
        "PK": "PET#pet_123",
        "SK": "CLIENT#client_123",
        "company_id": "tog_and_dogs",
        "client_id": "client_123",
        "pet_id": "pet_123",
        "name": "Buddy",
        "is_active": True
    }
    mock_put.return_value = True

    event = make_event(body={"name": "Buddy New"})

    with patch('common.entitlement.require_active_tenant', return_value=None), \
         patch('common.audit.log_action', side_effect=Exception("Audit system down")), \
         patch('common.pet_profile._rebuild_pet_summary') as mock_rebuild:
        resp = pet_handler(event, None)

    # The save operation succeeds even if logging throws an error
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["name"] == "Buddy New"
    mock_rebuild.assert_called_once()

