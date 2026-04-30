import pytest
import json
from unittest.mock import patch, MagicMock, ANY
from handlers.intake_handler import handler as intake_handler

# --- Fixtures & Mocks ---

@pytest.fixture
def mock_db():
    with patch('handlers.intake_handler.put_item') as mock_put:
        mock_put.return_value = True
        yield mock_put

@pytest.fixture
def mock_sfn():
    with patch('handlers.intake_handler.sfn') as mock_sfn_client:
        yield mock_sfn_client

# --- Test Cases ---

def test_valid_intake_succeeds(mock_db, mock_sfn):
    event = {
        "body": json.dumps({
            "client_name": "Regression Test Client",
            "client_email": "test@example.com",
            "start_date": "2024-01-01",
            "pet_names": "Regression Pet",
            "service_type": "PET_SITTING"
        }),
        "requestContext": {
            "authorizer": {
                "claims": {
                    "email": "test@example.com",
                    "custom:role": "client",
                    "sub": "user-sub-123"
                }
            }
        }
    }
    
    resp = intake_handler(event, None)
    
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["message"] == "Request submitted successfully"
    assert "request_id" in body
    assert body["status"] == "PENDING_REVIEW"
    
    # Verify DB write
    mock_db.assert_called_once()
    saved_item = mock_db.call_args[0][0]
    assert saved_item['client_name'] == "Regression Test Client"
    assert saved_item['pet_names'] == "Regression Pet"
    assert saved_item['status'] == "PENDING_REVIEW"
    assert "request_id" in saved_item
    assert "created_at" in saved_item

def test_missing_pet_names_rejected(mock_db):
    event = {
        "body": json.dumps({
            "client_name": "Test Client",
            "client_email": "test@example.com",
            "start_date": "2024-01-01"
            # pet_names missing
        })
    }
    
    resp = intake_handler(event, None)
    
    assert resp["statusCode"] == 400
    assert "Missing or invalid required fields" in resp["body"]
    mock_db.assert_not_called()

def test_empty_pet_names_rejected(mock_db):
    event = {
        "body": json.dumps({
            "client_name": "Test Client",
            "client_email": "test@example.com",
            "start_date": "2024-01-01",
            "pet_names": ""
        })
    }
    
    resp = intake_handler(event, None)
    
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()

def test_status_injection_ignored(mock_db, mock_sfn):
    # Try to inject a terminal status
    event = {
        "body": json.dumps({
            "client_name": "Hacker",
            "client_email": "hacker@example.com",
            "start_date": "2024-01-01",
            "pet_names": "Dog",
            "status": "APPROVED" # Should be ignored
        })
    }
    
    resp = intake_handler(event, None)
    
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "PENDING_REVIEW"
    
    saved_item = mock_db.call_args[0][0]
    assert saved_item['status'] == "PENDING_REVIEW"

def test_missing_client_name_rejected(mock_db):
    event = {
        "body": json.dumps({
            "client_email": "test@example.com",
            "start_date": "2024-01-01",
            "pet_names": "Dog"
            # client_name missing
        })
    }
    
    resp = intake_handler(event, None)
    
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()

def test_whitespace_pet_names_validation(mock_db):
    # This test might fail if current code doesn't strip/check whitespace
    event = {
        "body": json.dumps({
            "client_name": "Test Client",
            "client_email": "test@example.com",
            "start_date": "2024-01-01",
            "pet_names": "   "
        })
    }
    
    resp = intake_handler(event, None)
    
    # If the current code only does 'if not pet_names', "   " is truthy.
    # We want to ensure it's rejected.
    # Note: I might need to update intake_handler.py if this fails.
    if resp["statusCode"] == 200:
        pytest.fail("Intake accepted whitespace-only pet names")
    
    assert resp["statusCode"] == 400
    mock_db.assert_not_called()
