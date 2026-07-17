import sys
import os
import pytest
from unittest.mock import MagicMock, patch, call
from botocore.exceptions import ClientError

# Add scripts directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../scripts')))
import remediate_pet_legacy_attributes as remediate_tool


def test_command_line_rejection_wrong_parameters():
    # Wrong expected-account-id
    test_args = [
        "remediate_pet_legacy_attributes.py",
        "--profile", "usmissionhero-website-prod",
        "--region", "us-east-1",
        "--table", "togs-and-dogs-prod-data",
        "--expected-account-id", "000000000000"
    ]
    with patch.object(sys, 'argv', test_args), pytest.raises(SystemExit) as excinfo:
        remediate_tool.main()
    assert excinfo.value.code == 1

    # Wrong table
    test_args = [
        "remediate_pet_legacy_attributes.py",
        "--profile", "usmissionhero-website-prod",
        "--region", "us-east-1",
        "--table", "wrong-table-name",
        "--expected-account-id", "358604342897"
    ]
    with patch.object(sys, 'argv', test_args), pytest.raises(SystemExit) as excinfo:
        remediate_tool.main()
    assert excinfo.value.code == 1

    # Wrong region
    test_args = [
        "remediate_pet_legacy_attributes.py",
        "--profile", "usmissionhero-website-prod",
        "--region", "us-west-2",
        "--table", "togs-and-dogs-prod-data",
        "--expected-account-id", "358604342897"
    ]
    with patch.object(sys, 'argv', test_args), pytest.raises(SystemExit) as excinfo:
        remediate_tool.main()
    assert excinfo.value.code == 1


def test_apply_without_confirmation_rejected():
    test_args = [
        "remediate_pet_legacy_attributes.py",
        "--profile", "usmissionhero-website-prod",
        "--region", "us-east-1",
        "--table", "togs-and-dogs-prod-data",
        "--expected-account-id", "358604342897",
        "--apply"
    ]
    with patch.object(sys, 'argv', test_args), pytest.raises(SystemExit) as excinfo:
        remediate_tool.main()
    assert excinfo.value.code == 1


def test_aws_identity_verification():
    # Successful STS check
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {"Account": "358604342897"}
    mock_session = MagicMock()
    mock_session.client.return_value = mock_sts

    account = remediate_tool.verify_aws_identity(mock_session, "358604342897", "us-east-1")
    assert account == "358604342897"

    # STS returns wrong account
    mock_sts.get_caller_identity.return_value = {"Account": "111111111111"}
    with pytest.raises(ValueError) as exc:
        remediate_tool.verify_aws_identity(mock_session, "358604342897", "us-east-1")
    assert "does not match expected" in str(exc.value)

    # STS fails completely
    mock_sts.get_caller_identity.side_effect = Exception("STS error")
    with pytest.raises(RuntimeError) as exc:
        remediate_tool.verify_aws_identity(mock_session, "358604342897", "us-east-1")
    assert "Failed to verify AWS identity" in str(exc.value)


def test_classification_logic():
    mock_items = [
        # 1. Complete PET item
        {
            "PK": "PET#pet-1",
            "SK": "CLIENT#client-1",
            "pet_id": "pet-1",
            "client_id": "client-1",
            "company_id": "tog_and_dogs",
            "entity_type": "PET",
            "is_active": True
        },
        # 2. Canonical CLIENT record proving ownership of client-2
        {
            "PK": "COMPANY#tog_and_dogs",
            "SK": "CLIENT#client-2",
            "entity_type": "CLIENT"
        },
        # 3. Canonical CLIENT record proving ownership of client-3 (ambiguous: exists in two companies)
        {
            "PK": "COMPANY#tog_and_dogs",
            "SK": "CLIENT#client-3",
            "entity_type": "CLIENT"
        },
        {
            "PK": "COMPANY#another_company",
            "SK": "CLIENT#client-3",
            "entity_type": "CLIENT"
        },
        # 4. PET record eligible for remediation (missing client_id, pet_id, company_id, entity_type)
        # Unique CLIENT record client-2 will resolve company_id -> tog_and_dogs
        {
            "PK": "PET#pet-2",
            "SK": "CLIENT#client-2"
        },
        # 5. PET record missing company_id where client_id is ambiguous (client-3)
        {
            "PK": "PET#pet-3",
            "SK": "CLIENT#client-3",
            "pet_id": "pet-3",
            "client_id": "client-3"
        },
        # 6. PET record missing company_id where client_id is not found
        {
            "PK": "PET#pet-4",
            "SK": "CLIENT#client-4",
            "pet_id": "pet-4",
            "client_id": "client-4"
        },
        # 7. Malformed PK
        {
            "PK": "PET#malformed#123",
            "SK": "CLIENT#client-1"
        },
        # 8. Malformed SK
        {
            "PK": "PET#pet-1",
            "SK": "CLIENT#malformed#123"
        },
        # 9. Conflicting entity_type
        {
            "PK": "PET#pet-5",
            "SK": "CLIENT#client-1",
            "entity_type": "OTHER_TYPE"
        },
        # 10. Missing is_active only (should not be automatically remediated, but is not requires_manual_review)
        {
            "PK": "PET#pet-6",
            "SK": "CLIENT#client-2",
            "pet_id": "pet-6",
            "client_id": "client-2",
            "company_id": "tog_and_dogs",
            "entity_type": "PET"
        }
    ]

    counters, proposed_updates = remediate_tool.classify_and_propose(mock_items)

    assert counters['total_pets'] == 8 # All items starting with PET# or entity_type = PET
    assert counters['complete'] == 1
    assert counters['malformed_pk'] == 1
    assert counters['malformed_sk'] == 1
    assert counters['ambiguous_client_ownership'] == 1
    assert counters['client_ownership_not_found'] == 3
    assert counters['missing_is_active'] == 7
    
    # Check proposed updates
    # Only pet-2 is eligible for auto-remediation (resolves client_id, pet_id, company_id, entity_type)
    assert len(proposed_updates) == 1
    update = proposed_updates[0]
    assert update['PK'] == "PET#pet-2"
    assert update['SK'] == "CLIENT#client-2"
    assert update['updates'] == {
        'pet_id': 'pet-2',
        'client_id': 'client-2',
        'entity_type': 'PET',
        'company_id': 'tog_and_dogs'
    }


def test_dry_run_does_no_writes():
    mock_table = MagicMock()
    proposed = [
        {
            'PK': 'PET#pet-2',
            'SK': 'CLIENT#client-2',
            'updates': {'pet_id': 'pet-2'}
        }
    ]

    test_args = [
        "remediate_pet_legacy_attributes.py",
        "--profile", "usmissionhero-website-prod",
        "--region", "us-east-1",
        "--table", "togs-and-dogs-prod-data",
        "--expected-account-id", "358604342897",
        "--dry-run"
    ]
    
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {"Account": "358604342897"}
    mock_session = MagicMock()
    mock_session.client.return_value = mock_sts
    mock_session.resource.return_value.Table.return_value = mock_table
    
    # Mock scanning & classifying
    with patch.object(sys, 'argv', test_args), \
         patch('boto3.Session', return_value=mock_session), \
         patch('remediate_pet_legacy_attributes.scan_table_data', return_value=([], 0)), \
         patch('remediate_pet_legacy_attributes.classify_and_propose', return_value=({'total_evaluated': 0, 'total_pets': 0, 'complete': 0, 'missing_pet_id': 0, 'missing_client_id': 0, 'missing_company_id': 0, 'missing_entity_type': 0, 'missing_is_active': 0, 'malformed_pk': 0, 'malformed_sk': 0, 'ambiguous_client_ownership': 0, 'client_ownership_not_found': 0, 'eligible_for_remediation': 0, 'requires_manual_review': 0, 'total_remediations_proposed': 0}, [])):
        remediate_tool.main()
        
    # Verify no update calls were made on table
    mock_table.update_item.assert_not_called()


def test_apply_mode_success_and_conditional_skip():
    mock_table = MagicMock()
    
    # Mock update_item calls: first succeeds, second raises ConditionalCheckFailedException
    mock_table.update_item.side_effect = [
        None,
        ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Conditional check failed"}},
            "UpdateItem"
        ),
        ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Some validation failed"}},
            "UpdateItem"
        )
    ]
    
    proposed = [
        {
            'PK': 'PET#pet-1',
            'SK': 'CLIENT#client-1',
            'updates': {'pet_id': 'pet-1', 'company_id': 'tog_and_dogs'}
        },
        {
            'PK': 'PET#pet-2',
            'SK': 'CLIENT#client-2',
            'updates': {'pet_id': 'pet-2'}
        },
        {
            'PK': 'PET#pet-3',
            'SK': 'CLIENT#client-3',
            'updates': {'pet_id': 'pet-3'}
        }
    ]
    
    success, cond_fail, failed = remediate_tool.apply_remediations(mock_table, proposed)
    
    assert success == 1
    assert cond_fail == 1
    assert failed == 1
    
    assert mock_table.update_item.call_count == 3
    
    # Verify conditional check was passed
    first_call = mock_table.update_item.call_args_list[0]
    kwargs = first_call[1]
    assert "ConditionExpression" in kwargs
    assert "#attr_0" in kwargs["ExpressionAttributeNames"]
    assert "attribute_not_exists" in kwargs["ConditionExpression"]


def test_pagination_and_limit():
    mock_table = MagicMock()
    mock_table.scan.side_effect = [
        {"Items": [{"PK": "PET#pet-1"}], "LastEvaluatedKey": "key-1"},
        {"Items": [{"PK": "PET#pet-2"}]} # no LastEvaluatedKey -> stops pagination
    ]
    
    items, count = remediate_tool.scan_table_data(mock_table, 100)
    assert len(items) == 2
    assert count == 2
    assert mock_table.scan.call_count == 2

    # Test safety limit abort
    mock_table.scan.reset_mock()
    mock_table.scan.side_effect = [
        {"Items": [{"PK": "PET#pet-1"}, {"PK": "PET#pet-2"}], "LastEvaluatedKey": "key-1"},
        {"Items": [{"PK": "PET#pet-3"}]}
    ]
    items, count = remediate_tool.scan_table_data(mock_table, 1) # Limit set to 1
    assert len(items) == 2 # evaluates first batch of 2, then exceeds limit and stops
    assert count == 2
    assert mock_table.scan.call_count == 1
