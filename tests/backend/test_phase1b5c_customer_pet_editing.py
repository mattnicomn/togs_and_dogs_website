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
    assert body["health"]["some_private_field"] == "hidden"  # preserved
    
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
