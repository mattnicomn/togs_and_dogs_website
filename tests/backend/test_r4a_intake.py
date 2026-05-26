import pytest
import json
from unittest.mock import patch
from handlers.intake_handler import handler as intake_handler

@pytest.fixture
def mock_db():
    with patch('handlers.intake_handler.put_item') as mock_put:
        mock_put.return_value = True
        yield mock_put

@pytest.fixture
def mock_sfn():
    with patch('handlers.intake_handler.sfn') as mock_sfn_client:
        yield mock_sfn_client

def test_multi_pet_intake_succeeds(mock_db, mock_sfn):
    event = {
        "body": json.dumps({
            "client_name": "R4A Multi Pet Client",
            "client_email": "r4a@example.com",
            "start_date": "2026-06-20",
            "pets": [
                {"name": "Scout", "species": "DOG", "breed": "Beagle"},
                {"name": "Luna", "species": "CAT", "breed": "Siamese"}
            ]
        })
    }
    
    resp = intake_handler(event, None)
    
    # Debug print if fails
    if resp["statusCode"] != 200:
        print(f"DEBUG: Response body: {resp['body']}")
        
    assert resp["statusCode"] == 200
    
    # Verify DB write
    mock_db.assert_called_once()
    saved_item = mock_db.call_args[0][0]
    assert saved_item['pet_names'] == "Scout, Luna"
    assert saved_item['pets'][0]['name'] == "Scout"
    assert saved_item['pets'][1]['name'] == "Luna"
