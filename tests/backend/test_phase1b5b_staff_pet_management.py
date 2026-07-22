import sys
import os
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'backend'))

from handlers.pet_handler import handler as pet_handler

def make_event(role='admin', company_id='tog_and_dogs', method='GET', path='/admin/pets', path_params=None, query_params=None, body=None):
    return {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "cognito:groups": role,
                    "custom:company_id": company_id,
                    "email": "user@example.com"
                }
            }
        },
        "httpMethod": method,
        "path": path,
        "pathParameters": path_params or {},
        "queryStringParameters": query_params or {},
        "body": json.dumps(body) if body else "{}"
    }

@patch('common.db.table')
def test_staff_can_list_client_pets_endpoint(mock_table):
    """Staff role should be allowed to list all pets of a client via admin route."""
    event = make_event(role='staff', method='GET', query_params={"clientId": "client_123"})
    
    mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
    mock_table.query.return_value = {"Items": []}
    
    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "pets" in body

@patch('common.db.table')
def test_admin_gets_all_pets_when_include_inactive(mock_table):
    """GET /admin/pets returns both active and inactive pets when includeInactive is true."""
    event = make_event(role='admin', method='GET', query_params={"clientId": "client_123", "includeInactive": "true"})
    
    mock_pets = [
        {"PK": "PET#pet_1", "SK": "CLIENT#client_123", "client_id": "client_123", "entity_type": "PET", "name": "Buddy", "is_active": True, "company_id": "tog_and_dogs"},
        {"PK": "PET#pet_2", "SK": "CLIENT#client_123", "client_id": "client_123", "entity_type": "PET", "name": "Max", "is_active": False, "company_id": "tog_and_dogs"}
    ]
    mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
    mock_table.query.return_value = {"Items": mock_pets}
    
    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body["pets"]) == 2

@patch('common.db.table')
def test_admin_filters_inactive_pets_by_default(mock_table):
    """GET /admin/pets filters out inactive pets by default (includeInactive=false)."""
    event = make_event(role='admin', method='GET', query_params={"clientId": "client_123"})
    
    mock_pets = [
        {"PK": "PET#pet_1", "SK": "CLIENT#client_123", "client_id": "client_123", "entity_type": "PET", "name": "Buddy", "is_active": True, "company_id": "tog_and_dogs"},
        {"PK": "PET#pet_2", "SK": "CLIENT#client_123", "client_id": "client_123", "entity_type": "PET", "name": "Max", "is_active": False, "company_id": "tog_and_dogs"}
    ]
    mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
    mock_table.query.return_value = {"Items": mock_pets}
    
    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body["pets"]) == 1
    assert body["pets"][0]["name"] == "Buddy"

@patch('common.db.table')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_admin_create_pet_succeeds(mock_put, mock_get, mock_table):
    """Admin creates pet under a valid same-tenant client successfully."""
    event = make_event(role='admin', method='POST', body={
        "client_id": "client_123",
        "name": "Buddy",
        "species": "DOG"
    })
    
    mock_get.return_value = {} # New pet
    mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
    mock_put.return_value = True
    
    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["name"] == "Buddy"
    assert body["is_active"] is True
    assert body["company_id"] == "tog_and_dogs"

@patch('common.db.table')
@patch('handlers.pet_handler.get_item')
def test_admin_create_pet_denies_cross_tenant(mock_get, mock_table):
    """POST /admin/pets rejects when target client is not in same tenant."""
    event = make_event(role='admin', company_id='tog_and_dogs', method='POST', body={
        "client_id": "client_cross_tenant",
        "name": "Buddy"
    })
    
    mock_get.return_value = {}
    mock_table.get_item.return_value = {"Item": None} # Not found under tog_and_dogs company
    
    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 403

@patch('common.db.table')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_admin_create_pet_ignores_company_id_override(mock_put, mock_get, mock_table):
    """POST /admin/pets ignores caller-supplied company ownership override."""
    event = make_event(role='admin', company_id='tog_and_dogs', method='POST', body={
        "client_id": "client_123",
        "name": "Buddy",
        "company_id": "hacker_company"
    })
    
    mock_get.return_value = {}
    mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
    mock_put.return_value = True
    
    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["company_id"] == "tog_and_dogs"

@patch('common.db.table')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_admin_update_pet_fields_succeeds(mock_put, mock_get, mock_table):
    """PUT /admin/pets/{petId} successfully updates permitted fields."""
    event = make_event(role='admin', method='PUT', path_params={"petId": "pet_abc"}, body={
        "client_id": "client_123",
        "name": "Buddy Changed",
        "species": "CAT",
        "breed": "Siamese"
    })
    
    existing_pet = {
        "PK": "PET#pet_abc",
        "SK": "CLIENT#client_123",
        "pet_id": "pet_abc",
        "client_id": "client_123",
        "name": "Buddy",
        "species": "DOG",
        "company_id": "tog_and_dogs"
    }
    
    mock_get.return_value = existing_pet
    mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
    mock_table.query.return_value = {"Items": [existing_pet]}
    mock_put.return_value = True
    
    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["name"] == "Buddy Changed"
    assert body["species"] == "CAT"
    assert body["breed"] == "Siamese"

@patch('common.db.table')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_admin_update_ignores_client_reassignment(mock_put, mock_get, mock_table):
    """PUT /admin/pets/{petId} cannot reassign client ownership (client_id change ignored in SK)."""
    event = make_event(role='admin', method='PUT', path_params={"petId": "pet_abc"}, body={
        "client_id": "client_new_owner",
        "name": "Buddy"
    })
    
    existing_pet = {
        "PK": "PET#pet_abc",
        "SK": "CLIENT#client_123",
        "pet_id": "pet_abc",
        "client_id": "client_123",
        "name": "Buddy",
        "company_id": "tog_and_dogs"
    }
    
    mock_get.return_value = None
    mock_table.get_item.side_effect = lambda Key: {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": Key["SK"]}}
    mock_table.query.return_value = {"Items": [existing_pet]}
    
    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert "Cannot reassign client ownership" in body["error"]
    mock_put.assert_not_called()

@patch('common.db.table')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_unknown_pet_put_returns_404_and_no_put(mock_put, mock_get, mock_table):
    """PUT /admin/pets/{petId} for non-existent pet ID returns 404 and does not create a record."""
    event = make_event(role='admin', method='PUT', path_params={"petId": "pet_unknown"}, body={
        "client_id": "client_123",
        "name": "Ghost Pet"
    })
    
    mock_get.return_value = None
    mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
    mock_table.query.return_value = {"Items": []}
    
    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 404
    body = json.loads(resp["body"])
    assert "not found" in body["error"].lower()
    mock_put.assert_not_called()

@patch('common.db.table')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_admin_archive_pet(mock_put, mock_get, mock_table):
    """PUT /admin/pets/{petId} setting is_active=False archives pet."""
    event = make_event(role='admin', method='PUT', path_params={"petId": "pet_abc"}, body={
        "client_id": "client_123",
        "is_active": False
    })
    
    existing_pet = {
        "PK": "PET#pet_abc",
        "SK": "CLIENT#client_123",
        "pet_id": "pet_abc",
        "client_id": "client_123",
        "name": "Buddy",
        "is_active": True,
        "company_id": "tog_and_dogs"
    }
    
    mock_get.return_value = existing_pet
    mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
    mock_table.query.return_value = {"Items": [existing_pet]}
    mock_put.return_value = True
    
    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["is_active"] is False

@patch('common.db.table')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_admin_restore_pet(mock_put, mock_get, mock_table):
    """PUT /admin/pets/{petId} setting is_active=True restores pet."""
    event = make_event(role='admin', method='PUT', path_params={"petId": "pet_abc"}, body={
        "client_id": "client_123",
        "is_active": True
    })
    
    existing_pet = {
        "PK": "PET#pet_abc",
        "SK": "CLIENT#client_123",
        "pet_id": "pet_abc",
        "client_id": "client_123",
        "name": "Buddy",
        "is_active": False,
        "company_id": "tog_and_dogs"
    }
    
    mock_get.return_value = existing_pet
    mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
    mock_table.query.return_value = {"Items": [existing_pet]}
    mock_put.return_value = True
    
    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["is_active"] is True

@patch('common.db.table')
def test_owner_can_list_client_pets_endpoint(mock_table):
    """Owner role should be allowed to list all pets of a client via admin route."""
    event = make_event(role='owner', method='GET', query_params={"clientId": "client_123"})
    
    mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
    mock_table.query.return_value = {"Items": []}
    
    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "pets" in body

def test_unauthorized_role_denied():
    """Unauthorized role (e.g. unknown or random) is denied access with 403."""
    event = make_event(role='anonymous_role', method='POST', body={"client_id": "c1", "name": "Fido"})
    resp = pet_handler(event, None)
    assert resp["statusCode"] == 403

def test_client_facing_get_pets_always_excludes_archived():
    """Client route /client/pets always excludes archived pets."""
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "cognito:groups": "client",
                    "custom:company_id": "tog_and_dogs",
                    "email": "client@example.com"
                }
            }
        },
        "httpMethod": "GET",
        "path": "/client/pets",
        "queryStringParameters": {"includeInactive": "true"} # Client route must ignore this!
    }
    
    mock_pets = [
        {"PK": "PET#pet_1", "SK": "CLIENT#client_123", "client_id": "client_123", "entity_type": "PET", "name": "Buddy", "is_active": True, "company_id": "tog_and_dogs"},
        {"PK": "PET#pet_2", "SK": "CLIENT#client_123", "client_id": "client_123", "entity_type": "PET", "name": "Max", "is_active": False, "company_id": "tog_and_dogs"}
    ]
    
    with patch('common.auth.resolve_client_identity', return_value="client_123"), \
         patch('common.db.table') as mock_table, \
         patch('common.entitlement.require_active_tenant', return_value=None):
        mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
        mock_table.query.return_value = {"Items": mock_pets}
        resp = pet_handler(event, None)
        
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body["pets"]) == 1
    assert body["pets"][0]["name"] == "Buddy"

@patch('common.db.table')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_put_multiple_records_fails_safely_500(mock_put, mock_get, mock_table):
    """PUT /admin/pets/{petId} returns 500 when multiple records exist for same pet partition."""
    event = make_event(role='admin', method='PUT', path_params={"petId": "pet_corrupted"}, body={
        "client_id": "client_123",
        "name": "Buddy"
    })

    existing_pets = [
        {"PK": "PET#pet_corrupted", "SK": "CLIENT#client_123", "client_id": "client_123", "company_id": "tog_and_dogs"},
        {"PK": "PET#pet_corrupted", "SK": "CLIENT#client_456", "client_id": "client_456", "company_id": "tog_and_dogs"}
    ]

    mock_get.return_value = None
    mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
    mock_table.query.return_value = {"Items": existing_pets}

    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 500
    mock_put.assert_not_called()

@patch('common.db.table')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_put_cross_tenant_pet_mismatch_denied(mock_put, mock_get, mock_table):
    """PUT /admin/pets/{petId} returns 403 when pet belongs to another tenant."""
    event = make_event(role='admin', method='PUT', path_params={"petId": "pet_other_tenant"}, body={
        "client_id": "client_123",
        "name": "Buddy"
    })

    other_tenant_pet = {
        "PK": "PET#pet_other_tenant",
        "SK": "CLIENT#client_other",
        "pet_id": "pet_other_tenant",
        "client_id": "client_other",
        "company_id": "other_company"
    }

    mock_get.return_value = None
    mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
    mock_table.query.return_value = {"Items": [other_tenant_pet]}

    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 403
    mock_put.assert_not_called()

@patch('common.db.table')
@patch('handlers.pet_handler.get_item')
@patch('handlers.pet_handler.put_item')
def test_put_preserves_pk_sk_client_id_company_id(mock_put, mock_get, mock_table):
    """PUT /admin/pets/{petId} preserves original PK, SK, client_id, and company_id."""
    event = make_event(role='admin', company_id='tog_and_dogs', method='PUT', path_params={"petId": "pet_abc"}, body={
        "client_id": "client_123",
        "name": "Buddy Preserved",
        "company_id": "hacker_override"
    })

    existing_pet = {
        "PK": "PET#pet_abc",
        "SK": "CLIENT#client_123",
        "pet_id": "pet_abc",
        "client_id": "client_123",
        "company_id": "tog_and_dogs",
        "name": "Buddy"
    }

    mock_get.return_value = existing_pet
    mock_table.get_item.return_value = {"Item": {"PK": "COMPANY#tog_and_dogs", "SK": "CLIENT#client_123"}}
    mock_table.query.return_value = {"Items": [existing_pet]}
    mock_put.return_value = True

    with patch('common.entitlement.require_active_tenant', return_value=None):
        resp = pet_handler(event, None)

    assert resp["statusCode"] == 200
    mock_put.assert_called_once()
    saved_item = mock_put.call_args[0][0]
    assert saved_item["PK"] == "PET#pet_abc"
    assert saved_item["SK"] == "CLIENT#client_123"
    assert saved_item["client_id"] == "client_123"
    assert saved_item["company_id"] == "tog_and_dogs"
