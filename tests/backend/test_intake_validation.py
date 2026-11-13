import pytest
import json
from contextlib import ExitStack
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


@pytest.fixture
def no_network():
    """Fail loudly if any test reaches a real AWS/boto3 network call.

    This is a scoped safety net for THIS module only (not autouse, not global):
    if an unmocked DynamoDB/boto3 operation slips through, the botocore HTTP
    transport raises instead of silently returning an error that the handler
    would convert into a misleading 500.
    """
    def _blocked(*args, **kwargs):
        raise AssertionError(
            "Unmocked AWS network call attempted during an isolated intake test. "
            "Add an explicit scoped mock for the operation the handler reached."
        )

    with patch('botocore.httpsession.URLLib3Session.send', _blocked):
        yield


@pytest.fixture
def intake_isolation(no_network):
    """Explicit, scoped isolation of the public-intake tenant-resolution and
    entitlement/DB preamble that runs BEFORE field validation in the handler.

    Models the documented 'active tenant resolves successfully' state so the
    handler can reach its real validation logic, without reaching AWS. Patches
    are targeted at the exact boundaries the public-intake handler path calls
    (common.auth / common.entitlement are imported lazily inside handler(), so
    they are patched at their source modules; `table` is bound at module import
    so it is patched on the handler module). Nothing here fabricates a success
    response — put_item/sfn remain controlled by the mock_db/mock_sfn fixtures,
    and all validation/acceptance assertions still execute for real.

    Yields the resolver mock so a test may assert tenant resolution occurred.
    """
    COMPANY_ID = "tog_and_dogs"
    mock_table = MagicMock(name="intake_handler.table")
    # No pre-existing client with the test email -> exercises the new-client
    # entitlement path (which is then allowed by the check_limit patch below).
    mock_table.query.return_value = {"Items": []}

    with ExitStack() as stack:
        resolver = stack.enter_context(
            patch('common.auth.resolve_public_intake_tenant', return_value=COMPANY_ID)
        )
        # Active tenant: require_active_tenant returns None (no block).
        stack.enter_context(
            patch('common.entitlement.require_active_tenant', return_value=None)
        )
        stack.enter_context(patch('handlers.intake_handler.table', mock_table))
        # Entitlement gates: allow (no limit breach) without touching DynamoDB.
        stack.enter_context(patch('common.entitlement.check_limit', return_value=None))
        stack.enter_context(patch('common.entitlement.get_active_client_count', return_value=0))
        stack.enter_context(patch('common.entitlement.get_monthly_bookings_count', return_value=0))
        stack.enter_context(patch('common.entitlement.increment_monthly_bookings', return_value=None))
        yield resolver

# --- Test Cases ---

def test_valid_intake_succeeds(mock_db, mock_sfn, intake_isolation):
    event = {
        "body": json.dumps({
            "client_name": "Regression Test Client",
            "client_email": "test@example.com",
            "start_date": "2024-01-01",
            "pet_names": "Regression Pet",
            "service_type": "PET_SITTING",
            "accepted_terms": True,
            "accepted_privacy": True,
            "terms_version": "1.0",
            "privacy_version": "1.0"
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

def test_missing_pet_names_rejected(mock_db, intake_isolation):
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

def test_empty_pet_names_rejected(mock_db, intake_isolation):
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

def test_status_injection_ignored(mock_db, mock_sfn, intake_isolation):
    # Try to inject a terminal status
    event = {
        "body": json.dumps({
            "client_name": "Hacker",
            "client_email": "hacker@example.com",
            "start_date": "2024-01-01",
            "pet_names": "Dog",
            "status": "APPROVED", # Should be ignored
            "accepted_terms": True,
            "accepted_privacy": True,
            "terms_version": "1.0",
            "privacy_version": "1.0"
        })
    }
    
    resp = intake_handler(event, None)
    
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["status"] == "PENDING_REVIEW"
    
    saved_item = mock_db.call_args[0][0]
    assert saved_item['status'] == "PENDING_REVIEW"

def test_missing_client_name_rejected(mock_db, intake_isolation):
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

def test_whitespace_pet_names_validation(mock_db, intake_isolation):
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
