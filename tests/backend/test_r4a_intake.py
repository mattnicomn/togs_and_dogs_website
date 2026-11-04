import pytest
import json
from contextlib import ExitStack
from unittest.mock import patch, MagicMock
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


@pytest.fixture
def no_network():
    """Fail loudly if any test in this module reaches a real AWS/boto3 call.

    Scoped safety net for THIS module only (not autouse, not global): if an
    unmocked DynamoDB/boto3 operation slips through, the botocore HTTP
    transport raises instead of silently returning an error that the handler
    would convert into a misleading 500. This mirrors the V3a intake-isolation
    guard so the multi-pet path cannot pass by accidentally reaching AWS.
    """
    def _blocked(*args, **kwargs):
        raise AssertionError(
            "Unmocked AWS network call attempted during an isolated multi-pet "
            "intake test. Add an explicit scoped mock for the operation the "
            "handler reached."
        )

    with patch('botocore.httpsession.URLLib3Session.send', _blocked):
        yield


@pytest.fixture
def intake_isolation(no_network):
    """Explicit, scoped isolation of the public-intake tenant-resolution and
    entitlement/DB preamble that runs BEFORE field validation and the record
    write in the handler.

    Models the documented 'active tenant resolves successfully, limits not
    breached' state so the handler reaches its real multi-pet normalization and
    record-build logic, without reaching AWS. Patches target the exact
    boundaries the public-intake path calls: common.auth / common.entitlement
    are imported lazily inside handler(), so they are patched at their source
    modules; `table` is bound at module import (from common.db import ... table)
    so it is patched on the handler module. Nothing here fabricates a success
    response — put_item/sfn remain controlled by mock_db/mock_sfn, and all
    validation plus the real pet-name/pets assembly still execute for real.

    Yields the resolver mock so a test may assert tenant resolution occurred.
    """
    COMPANY_ID = "tog_and_dogs"
    mock_table = MagicMock(name="intake_handler.table")
    # No pre-existing client with the test email -> exercises the new-client
    # entitlement path, which is then allowed by the check_limit patch below.
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


def test_multi_pet_intake_succeeds(mock_db, mock_sfn, intake_isolation):
    event = {
        "body": json.dumps({
            "client_name": "R4A Multi Pet Client",
            "client_email": "r4a@example.com",
            "start_date": "2026-06-20",
            "accepted_terms": True,
            "accepted_privacy": True,
            "terms_version": "1.0",
            "privacy_version": "1.0",
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

    # Tenant resolution really ran through the public-intake resolver.
    intake_isolation.assert_called_once()

    # Verify DB write happened exactly once and captured the real record the
    # handler built (not a fixture-fabricated value).
    mock_db.assert_called_once()
    saved_item = mock_db.call_args[0][0]

    # Legacy compatibility string is generated from the pets[] array, in order.
    assert saved_item['pet_names'] == "Scout, Luna"

    # Structured multi-pet payload is preserved with correct count, order,
    # and per-pet contents.
    assert isinstance(saved_item['pets'], list)
    assert len(saved_item['pets']) == 2
    assert saved_item['pets'][0]['name'] == "Scout"
    assert saved_item['pets'][0]['species'] == "DOG"
    assert saved_item['pets'][0]['breed'] == "Beagle"
    assert saved_item['pets'][1]['name'] == "Luna"
    assert saved_item['pets'][1]['species'] == "CAT"
    assert saved_item['pets'][1]['breed'] == "Siamese"

    # Record ownership / tenant identity and public-intake classification.
    assert saved_item['company_id'] == "tog_and_dogs"
    assert saved_item['client_name'] == "R4A Multi Pet Client"
    assert saved_item['client_email'] == "r4a@example.com"
    assert saved_item['status'] == "PENDING_REVIEW"
    assert saved_item['workflow_type'] == "CUSTOMER_INTAKE"
    assert saved_item['source'] == "public_intake"

    # Response surface matches the created record.
    body = json.loads(resp["body"])
    assert body["message"] == "Request submitted successfully"
    assert body["status"] == "PENDING_REVIEW"
    assert "request_id" in body
