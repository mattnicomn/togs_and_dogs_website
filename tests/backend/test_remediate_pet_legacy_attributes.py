import sys
import os
import pytest
from unittest.mock import MagicMock, patch
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


def test_command_line_mutual_exclusion_and_defaults():
    # Specifying both --dry-run and --apply is rejected by argparse
    test_args = [
        "remediate_pet_legacy_attributes.py",
        "--profile", "usmissionhero-website-prod",
        "--region", "us-east-1",
        "--table", "togs-and-dogs-prod-data",
        "--expected-account-id", "358604342897",
        "--dry-run",
        "--apply"
    ]
    with patch.object(sys, 'argv', test_args), pytest.raises(SystemExit) as excinfo:
        remediate_tool.main()
    assert excinfo.value.code != 0


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


def test_aws_identity_verification_redacted_errors():
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
    assert "account ID mismatch" in str(exc.value)
    # Ensure no details leaked
    assert "111111111111" not in str(exc.value)

    # STS fails completely with ClientError containing sensitive data
    mock_sts.get_caller_identity.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "SecretAccountKeyIdStuff"}},
        "GetCallerIdentity"
    )
    with pytest.raises(RuntimeError) as exc:
        remediate_tool.verify_aws_identity(mock_session, "358604342897", "us-east-1")
    assert "Failed to verify AWS identity (ClientError: AccessDenied)" in str(exc.value)
    assert "SecretAccountKeyIdStuff" not in str(exc.value)

    # Unexpected exception
    mock_sts.get_caller_identity.side_effect = Exception("very sensitive traceback information")
    with pytest.raises(RuntimeError) as exc:
        remediate_tool.verify_aws_identity(mock_session, "358604342897", "us-east-1")
    assert "unexpected error" in str(exc.value)
    assert "very sensitive" not in str(exc.value)


def test_parse_key_value_grammar():
    # Valid IDs
    assert remediate_tool.parse_key_value("PET#a1b2c3d4-e5f6-7890-abcd-ef1234567890", "PET") == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    assert remediate_tool.parse_key_value("CLIENT#client_a1b2c3d4", "CLIENT") == "client_a1b2c3d4"
    assert remediate_tool.parse_key_value("CLIENT#cognito_username", "CLIENT") == "cognito_username"
    assert remediate_tool.parse_key_value("CLIENT#cognito_user@example.com", "CLIENT") == "cognito_user@example.com"
    assert remediate_tool.parse_key_value("CLIENT#cognito_first.last", "CLIENT") == "cognito_first.last"
    assert remediate_tool.parse_key_value("CLIENT#cognito_first+last", "CLIENT") == "cognito_first+last"
    assert remediate_tool.parse_key_value("COMPANY#tog_and_dogs", "COMPANY") == "tog_and_dogs"
    assert remediate_tool.parse_key_value("COMPANY#test_tenant_alpha", "COMPANY") == "test_tenant_alpha"

    # Invalid IDs
    assert remediate_tool.parse_key_value("PET#", "PET") is None
    assert remediate_tool.parse_key_value("PET#a#b", "PET") is None
    assert remediate_tool.parse_key_value("CLIENT#", "CLIENT") is None
    assert remediate_tool.parse_key_value("OTHER#123", "PET") is None
    assert remediate_tool.parse_key_value(None, "PET") is None
    assert remediate_tool.parse_key_value(12345, "PET") is None


def test_classification_ownership_and_independent_proposals():
    mock_items = [
        # 1. Complete PET
        {
            "PK": "PET#pet-1",
            "SK": "CLIENT#client-1",
            "pet_id": "pet-1",
            "client_id": "client-1",
            "company_id": "tog_and_dogs",
            "entity_type": "PET",
            "is_active": True
        },
        # 2. Canonical CLIENT record proving ownership of client-2 (no entity_type, accepts as fallback)
        {
            "PK": "COMPANY#tog_and_dogs",
            "SK": "CLIENT#client-2"
        },
        # 3. Canonical CLIENT record proving ownership of client-3 (has entity_type = CLIENT)
        {
            "PK": "COMPANY#test_tenant_alpha",
            "SK": "CLIENT#client-3",
            "entity_type": "CLIENT"
        },
        # 4. Canonical CLIENT record proving ownership of client-4 (ambiguous: exists in two companies)
        {
            "PK": "COMPANY#tog_and_dogs",
            "SK": "CLIENT#client-4",
            "entity_type": "CLIENT"
        },
        {
            "PK": "COMPANY#another_company",
            "SK": "CLIENT#client-4",
            "entity_type": "CLIENT"
        },
        # 5. Non-canonical CLIENT record due to conflicting entity_type (must be rejected)
        {
            "PK": "COMPANY#tog_and_dogs",
            "SK": "CLIENT#client-5",
            "entity_type": "NOT_CLIENT"
        },
        # 6. PET record eligible for full auto-remediation (resolves client_id, pet_id, company_id, entity_type)
        {
            "PK": "PET#pet-2",
            "SK": "CLIENT#client-2"
        },
        # 7. PET record eligible for partial auto-remediation (pet_id, client_id, entity_type resolved, but company_id is unresolved because client-4 is ambiguous)
        {
            "PK": "PET#pet-3",
            "SK": "CLIENT#client-4"
        },
        # 8. PET record eligible for partial auto-remediation (company_id unresolved because client-5 has no canonical owner)
        {
            "PK": "PET#pet-4",
            "SK": "CLIENT#client-5"
        },
        # 9. Compatibility handled is_active missing only
        {
            "PK": "PET#pet-5",
            "SK": "CLIENT#client-3",
            "pet_id": "pet-5",
            "client_id": "client-3",
            "company_id": "test_tenant_alpha",
            "entity_type": "PET"
        },
        # 10. Requires manual review (malformed SK)
        {
            "PK": "PET#pet-6",
            "SK": "CLIENT#malformed#123"
        },
        # 11. Requires manual review (conflicting entity_type)
        {
            "PK": "PET#pet-7",
            "SK": "CLIENT#client-3",
            "entity_type": "NOT_PET"
        },
        # 12. Requires manual review (conflicting identifiers)
        {
            "PK": "PET#pet-8",
            "SK": "CLIENT#client-3",
            "pet_id": "mismatched-id",
            "client_id": "client-3"
        }
    ]

    diag, dispo, proposed, accounting = remediate_tool.classify_and_propose(mock_items)

    # Accounting Verification
    assert diag['total_pets'] == 8

    # Invariant Verification: sum of dispositions must equal total pets
    assert sum(dispo.values()) == 8

    assert dispo['complete'] == 1
    assert dispo['compatibility_handled_missing_is_active_only'] == 1
    assert dispo['eligible_for_full_remediation'] == 1
    assert dispo['eligible_for_partial_remediation'] == 2
    assert dispo['requires_manual_review'] == 3

    # Check independent safe-field proposals
    # pet-2 (eligible_for_full_remediation): proposals for all 4 needed attributes
    # pet-3 (eligible_for_partial_remediation): proposes pet_id, client_id, entity_type (no company_id)
    # pet-4 (eligible_for_partial_remediation): proposes pet_id, client_id, entity_type (no company_id)
    assert len(proposed) == 3

    pet_2_props = [p for p in proposed if p['PK'] == "PET#pet-2"][0]
    assert pet_2_props['updates'] == {
        'pet_id': 'pet-2',
        'client_id': 'client-2',
        'entity_type': 'PET',
        'company_id': 'tog_and_dogs'
    }

    pet_3_props = [p for p in proposed if p['PK'] == "PET#pet-3"][0]
    assert pet_3_props['updates'] == {
        'pet_id': 'pet-3',
        'client_id': 'client-4',
        'entity_type': 'PET'
    }

    assert accounting['proposed_pet_id'] == 3
    assert accounting['proposed_client_id'] == 3
    assert accounting['proposed_entity_type'] == 3
    assert accounting['proposed_company_id'] == 1
    assert accounting['total_items_with_proposals'] == 3
    assert accounting['total_attribute_additions'] == 10


def test_dry_run_does_no_writes():
    mock_table = MagicMock()
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

    with patch.object(sys, 'argv', test_args), \
         patch('boto3.Session', return_value=mock_session), \
         patch('remediate_pet_legacy_attributes.scan_table_data', return_value=([], 0)):
        remediate_tool.main()

    mock_table.update_item.assert_not_called()


def test_apply_mode_success_and_conditional_skip():
    mock_table = MagicMock()
    mock_table.update_item.side_effect = [
        None,
        ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException", "Message": "Conditional check failed"}},
            "UpdateItem"
        )
    ]

    proposed = [
        {
            'PK': 'PET#pet-1',
            'SK': 'CLIENT#client-1',
            'updates': {'pet_id': 'pet-1'}
        },
        {
            'PK': 'PET#pet-2',
            'SK': 'CLIENT#client-2',
            'updates': {'pet_id': 'pet-2'}
        }
    ]

    success, cond_fail, failed = remediate_tool.apply_remediations(mock_table, proposed)
    assert success == 1
    assert cond_fail == 1
    assert failed == 0


def test_pagination_and_safety_limit_abort():
    mock_table = MagicMock()
    # 1. Limit crossed on first page
    mock_table.scan.side_effect = [
        {"Items": [{"PK": "PET#pet-1"}, {"PK": "PET#pet-2"}]}
    ]
    with pytest.raises(remediate_tool.SafetyLimitExceededError):
        remediate_tool.scan_table_data(mock_table, 1)

    # 2. Limit crossed on later page
    mock_table.scan.side_effect = [
        {"Items": [{"PK": "PET#pet-1"}], "LastEvaluatedKey": "key-1"},
        {"Items": [{"PK": "PET#pet-2"}]}
    ]
    with pytest.raises(remediate_tool.SafetyLimitExceededError):
        remediate_tool.scan_table_data(mock_table, 1)


def test_safety_limit_command_line_abort(capsys):
    mock_table = MagicMock()
    mock_table.scan.side_effect = [
        {"Items": [{"PK": "PET#pet-1"}, {"PK": "PET#pet-2"}]}
    ]

    test_args = [
        "remediate_pet_legacy_attributes.py",
        "--profile", "usmissionhero-website-prod",
        "--region", "us-east-1",
        "--table", "togs-and-dogs-prod-data",
        "--expected-account-id", "358604342897",
        "--limit", "1",
        "--dry-run"
    ]

    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {"Account": "358604342897"}
    mock_session = MagicMock()
    mock_session.client.return_value = mock_sts
    mock_session.resource.return_value.Table.return_value = mock_table

    with patch.object(sys, 'argv', test_args), \
         patch('boto3.Session', return_value=mock_session), pytest.raises(SystemExit) as excinfo:
        remediate_tool.main()

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "Safety limit exceeded" in captured.out
    assert "INCOMPLETE RESULT" in captured.out
    # Confirm no writes
    mock_table.update_item.assert_not_called()


def test_exception_redaction(capsys):
    mock_table = MagicMock()
    # Synthetic ClientError with highly sensitive information
    mock_table.update_item.side_effect = ClientError(
        {
            "Error": {
                "Code": "ValidationException",
                "Message": "PK=PET#secret-pet, SK=CLIENT#secret-client, pet_id=secret-id, name=Buddy"
            }
        },
        "UpdateItem"
    )

    proposed = [
        {
            'PK': 'PET#secret-pet',
            'SK': 'CLIENT#secret-client',
            'updates': {'pet_id': 'secret-id'}
        }
    ]

    success, cond_fail, failed = remediate_tool.apply_remediations(mock_table, proposed)
    assert failed == 1
    assert success == 0

    captured = capsys.readouterr()
    # Confirm error code is reported, but sensitive message content is redacted
    assert "ClientError: ValidationException" in captured.out
    assert "secret-pet" not in captured.out
    assert "secret-client" not in captured.out
    assert "secret-id" not in captured.out
    assert "Buddy" not in captured.out
