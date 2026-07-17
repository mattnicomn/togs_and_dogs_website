#!/usr/bin/env python3
"""
Production-safe legacy pet attribute remediation utility.
Defaults to dry-run and performs strict AWS profile, account, region, and table validations.
Uses concurrent-safe conditional updates to enrich missing fields (pet_id, client_id, company_id, entity_type).
Deliberately excludes is_active from automatic remediation.
"""
import argparse
import sys
import boto3
from botocore.exceptions import ClientError

# Hardcoded production approval gate safeguards
APPROVED_ACCOUNT_ID = "358604342897"
APPROVED_TABLE_NAME = "togs-and-dogs-prod-data"
APPROVED_REGION = "us-east-1"
APPROVED_CONFIRM_WRITE = "PET-LEGACY-REMEDIATION"


class SafetyLimitExceededError(Exception):
    """Raised when the scan evaluates more items than the safety limit threshold."""
    pass


def parse_key_value(key_str, prefix):
    """
    Safely parses a DynamoDB PK/SK string.
    Must match exactly '{prefix}#{suffix}', where prefix matches the prefix parameter,
    and suffix is a non-empty string that does not contain any '#' characters.
    Returns the suffix if valid, otherwise None.
    """
    if not isinstance(key_str, str):
        return None
    if not key_str.startswith(f"{prefix}#"):
        return None
    if key_str.count('#') != 1:
        return None
    suffix = key_str[len(prefix)+1:]
    if not suffix:
        return None
    return suffix


def verify_aws_identity(session, expected_account_id, expected_region):
    """
    Call STS GetCallerIdentity and verify AWS account.
    All exception details are redacted for security.
    """
    try:
        sts = session.client('sts', region_name=expected_region)
        identity = sts.get_caller_identity()
        caller_account = identity.get('Account')
    except ClientError as e:
        code = e.response.get('Error', {}).get('Code', 'Unknown')
        raise RuntimeError(f"Failed to verify AWS identity (ClientError: {code})")
    except Exception:
        raise RuntimeError("Failed to verify AWS identity due to an unexpected error")

    if caller_account != expected_account_id:
        raise ValueError("STS verification failed: account ID mismatch")
    return caller_account


def scan_table_data(table, limit):
    """
    Scan all records using paginated scan, projecting only target attributes.
    Note: ProjectionExpression minimizes returned private data; it does not reduce DynamoDB Scan capacity consumed.
    All exception details are redacted for security.
    """
    items = []
    scan_kwargs = {
        "ProjectionExpression": "PK, SK, pet_id, client_id, company_id, entity_type, is_active"
    }

    evaluated_count = 0
    try:
        response = table.scan(**scan_kwargs)
    except ClientError as e:
        code = e.response.get('Error', {}).get('Code', 'Unknown')
        raise RuntimeError(f"DynamoDB Scan failed (ClientError: {code})")
    except Exception:
        raise RuntimeError("DynamoDB Scan failed due to an unexpected error")

    while True:
        batch = response.get('Items', [])
        items.extend(batch)
        evaluated_count += len(batch)

        if evaluated_count > limit:
            raise SafetyLimitExceededError(
                f"Safety limit of {limit} evaluated items exceeded (evaluated so far: {evaluated_count})."
            )

        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break

        scan_kwargs["ExclusiveStartKey"] = last_key
        try:
            response = table.scan(**scan_kwargs)
        except ClientError as e:
            code = e.response.get('Error', {}).get('Code', 'Unknown')
            raise RuntimeError(f"DynamoDB Scan failed (ClientError: {code})")
        except Exception:
            raise RuntimeError("DynamoDB Scan failed due to an unexpected error")

    return items, evaluated_count


def classify_and_propose(items):
    """
    Classify scanned items and propose missing attributes to populate.
    Every PET record is placed into exactly one mutually exclusive disposition.
    """
    # 1. Identify CLIENT records to build company ownership map
    client_ownership = {}  # client_id -> set of company_ids

    for item in items:
        pk = item.get('PK', '')
        sk = item.get('SK', '')

        comp_id = parse_key_value(pk, 'COMPANY')
        cl_id = parse_key_value(sk, 'CLIENT')
        if comp_id and cl_id:
            entity_type = item.get('entity_type')
            # Accept if entity_type is absent or is exactly 'CLIENT'
            if entity_type is None or entity_type == 'CLIENT':
                if cl_id not in client_ownership:
                    client_ownership[cl_id] = set()
                client_ownership[cl_id].add(comp_id)

    # Classification counters
    diagnostic_counters = {
        'total_evaluated': len(items),
        'total_pets': 0,
        'missing_pet_id': 0,
        'missing_client_id': 0,
        'missing_company_id': 0,
        'missing_entity_type': 0,
        'missing_is_active': 0,
        'malformed_pk': 0,
        'malformed_sk': 0,
        'ambiguous_client_ownership': 0,
        'client_ownership_not_found': 0,
    }

    disposition_counters = {
        'complete': 0,
        'eligible_for_full_remediation': 0,
        'eligible_for_partial_remediation': 0,
        'compatibility_handled_missing_is_active_only': 0,
        'requires_manual_review': 0,
    }

    proposed_updates = []

    # Proposed update accounting
    proposed_accounting = {
        'proposed_pet_id': 0,
        'proposed_client_id': 0,
        'proposed_company_id': 0,
        'proposed_entity_type': 0,
        'total_items_with_proposals': 0,
        'total_attribute_additions': 0,
    }

    for item in items:
        pk = item.get('PK', '')
        sk = item.get('SK', '')
        entity_type = item.get('entity_type')

        is_pet_pk = pk.startswith('PET#') if isinstance(pk, str) else False
        is_pet_entity = entity_type == 'PET'

        if not (is_pet_pk or is_pet_entity):
            continue

        diagnostic_counters['total_pets'] += 1

        parsed_pk = parse_key_value(pk, 'PET')
        parsed_sk = parse_key_value(sk, 'CLIENT')

        is_malformed = False
        missing_needed_fields = []

        if not parsed_pk:
            diagnostic_counters['malformed_pk'] += 1
            is_malformed = True
        if not parsed_sk:
            diagnostic_counters['malformed_sk'] += 1
            is_malformed = True

        if 'pet_id' not in item:
            diagnostic_counters['missing_pet_id'] += 1
            missing_needed_fields.append('pet_id')
        if 'client_id' not in item:
            diagnostic_counters['missing_client_id'] += 1
            missing_needed_fields.append('client_id')
        if 'company_id' not in item:
            diagnostic_counters['missing_company_id'] += 1
            missing_needed_fields.append('company_id')
        if 'entity_type' not in item:
            diagnostic_counters['missing_entity_type'] += 1
            missing_needed_fields.append('entity_type')
        if 'is_active' not in item:
            diagnostic_counters['missing_is_active'] += 1

        has_entity_conflict = False
        if entity_type and entity_type != 'PET':
            has_entity_conflict = True

        has_id_conflict = False
        if 'pet_id' in item and parsed_pk and item['pet_id'] != parsed_pk:
            has_id_conflict = True
        if 'client_id' in item and parsed_sk and item['client_id'] != parsed_sk:
            has_id_conflict = True

        effective_client_id = parsed_sk if parsed_sk else item.get('client_id')
        resolved_company_id = None
        has_ownership_issue = False

        if 'company_id' not in item:
            if effective_client_id:
                owners = client_ownership.get(effective_client_id, set())
                if len(owners) == 1:
                    resolved_company_id = list(owners)[0]
                elif len(owners) > 1:
                    diagnostic_counters['ambiguous_client_ownership'] += 1
                    has_ownership_issue = True
                else:
                    diagnostic_counters['client_ownership_not_found'] += 1
                    has_ownership_issue = True
            else:
                has_ownership_issue = True

        # Independent proposals logic
        eligible_fields_to_add = {}
        if not is_malformed and not has_entity_conflict and not has_id_conflict:
            if 'pet_id' not in item and parsed_pk:
                eligible_fields_to_add['pet_id'] = parsed_pk
            if 'client_id' not in item and parsed_sk:
                eligible_fields_to_add['client_id'] = parsed_sk
            if 'entity_type' not in item:
                eligible_fields_to_add['entity_type'] = 'PET'
            if 'company_id' not in item and resolved_company_id:
                eligible_fields_to_add['company_id'] = resolved_company_id

        # Mutually exclusive dispositions classification
        has_fundamental_conflict = is_malformed or has_entity_conflict or has_id_conflict

        all_fields_present = (
            'pet_id' in item and
            'client_id' in item and
            'company_id' in item and
            'entity_type' in item and
            'is_active' in item
        )

        missing_is_active_only = (
            'pet_id' in item and
            'client_id' in item and
            'company_id' in item and
            'entity_type' in item and
            'is_active' not in item
        )

        if has_fundamental_conflict:
            disposition_counters['requires_manual_review'] += 1
        elif all_fields_present:
            disposition_counters['complete'] += 1
        elif missing_is_active_only:
            disposition_counters['compatibility_handled_missing_is_active_only'] += 1
        else:
            # We are missing some needed attributes (pet_id, client_id, company_id, entity_type)
            if eligible_fields_to_add:
                # Check if all missing needed attributes are proposed
                if set(missing_needed_fields) == set(eligible_fields_to_add.keys()):
                    disposition_counters['eligible_for_full_remediation'] += 1
                else:
                    disposition_counters['eligible_for_partial_remediation'] += 1

                proposed_updates.append({
                    'PK': pk,
                    'SK': sk,
                    'updates': eligible_fields_to_add
                })

                # Update accounting
                if 'pet_id' in eligible_fields_to_add:
                    proposed_accounting['proposed_pet_id'] += 1
                if 'client_id' in eligible_fields_to_add:
                    proposed_accounting['proposed_client_id'] += 1
                if 'company_id' in eligible_fields_to_add:
                    proposed_accounting['proposed_company_id'] += 1
                if 'entity_type' in eligible_fields_to_add:
                    proposed_accounting['proposed_entity_type'] += 1

                proposed_accounting['total_items_with_proposals'] += 1
                proposed_accounting['total_attribute_additions'] += len(eligible_fields_to_add)
            else:
                # Needed attributes missing but nothing could be safely proposed (e.g. company_id missing and unresolved)
                disposition_counters['requires_manual_review'] += 1

    # Verify disposition invariant
    sum_dispositions = sum(disposition_counters.values())
    if sum_dispositions != diagnostic_counters['total_pets']:
        print(f"CRITICAL: Disposition invariant check failed! Sum of dispositions: {sum_dispositions}, Total pets: {diagnostic_counters['total_pets']}")
        sys.exit(3)

    return diagnostic_counters, disposition_counters, proposed_updates, proposed_accounting


def apply_remediations(table, proposed_updates):
    """
    Apply proposed updates conditionally.
    All exception messages are redacted for security.
    """
    success_count = 0
    failure_count = 0
    conditional_fail_count = 0

    for update in proposed_updates:
        pk = update['PK']
        sk = update['SK']
        fields = update['updates']

        if not fields:
            continue

        update_expr_parts = []
        expression_attribute_names = {}
        expression_attribute_values = {}
        condition_expression_parts = []

        for idx, (k, v) in enumerate(fields.items()):
            attr_name = f"#attr_{idx}"
            val_name = f":val_{idx}"
            update_expr_parts.append(f"{attr_name} = {val_name}")
            expression_attribute_names[attr_name] = k
            expression_attribute_values[val_name] = v
            condition_expression_parts.append(f"attribute_not_exists({attr_name})")

        update_expression = "SET " + ", ".join(update_expr_parts)
        condition_expression = " AND ".join(condition_expression_parts)

        try:
            table.update_item(
                Key={'PK': pk, 'SK': sk},
                UpdateExpression=update_expression,
                ConditionExpression=condition_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )
            success_count += 1
        except ClientError as e:
            code = e.response.get('Error', {}).get('Code', 'Unknown')
            if code == 'ConditionalCheckFailedException':
                conditional_fail_count += 1
                print("INFO: Skip concurrent update for an item (ConditionalCheckFailedException)")
            else:
                failure_count += 1
                print(f"ERROR: Failed to update item (ClientError: {code})")
        except Exception:
            failure_count += 1
            print("ERROR: Failed to update item due to an unexpected error")

    return success_count, conditional_fail_count, failure_count


def main():
    parser = argparse.ArgumentParser(description="Remediate legacy PET attributes in DynamoDB.")
    parser.add_argument('--profile', required=True, help="AWS profile name")
    parser.add_argument('--region', required=True, help="AWS region")
    parser.add_argument('--table', required=True, help="AWS table name")
    parser.add_argument('--expected-account-id', required=True, help="Expected AWS account ID")
    parser.add_argument('--confirm-write', help="Confirm write validation value")
    parser.add_argument('--limit', type=int, default=5000, help="Max items safety scan limit")

    # Mutually exclusive mode group
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--dry-run', action='store_true', help="Dry run mode")
    group.add_argument('--apply', action='store_true', help="Apply mode")

    args = parser.parse_args()

    # 1. Parameter guards
    if args.expected_account_id != APPROVED_ACCOUNT_ID:
        print(f"ERROR: Expected account ID '{args.expected_account_id}' does not match approved '{APPROVED_ACCOUNT_ID}'")
        sys.exit(1)
    if args.table != APPROVED_TABLE_NAME:
        print(f"ERROR: Table name '{args.table}' does not match approved '{APPROVED_TABLE_NAME}'")
        sys.exit(1)
    if args.region != APPROVED_REGION:
        print(f"ERROR: Region '{args.region}' does not match approved '{APPROVED_REGION}'")
        sys.exit(1)

    # Default to dry-run if not specified
    is_dry_run = True
    if args.apply:
        is_dry_run = False

    if not is_dry_run:
        # Strict validation checks for write mode
        if args.confirm_write != APPROVED_CONFIRM_WRITE:
            print(f"ERROR: Apply mode requires '--confirm-write {APPROVED_CONFIRM_WRITE}'")
            sys.exit(1)

    print("=== DYNAMODB PET LEGACY REMEDIATION UTILITY ===")
    print(f"AWS Profile: {args.profile}")
    print(f"AWS Region:  {args.region}")
    print(f"Table Name:  {args.table}")
    print(f"Mode:        {'DRY RUN' if is_dry_run else 'APPLY WRITE'}")
    print("===============================================")

    try:
        session = boto3.Session(profile_name=args.profile)
        # STS Verification Identity Safeguard
        verify_aws_identity(session, APPROVED_ACCOUNT_ID, APPROVED_REGION)
    except Exception as e:
        print(f"ERROR: Identity verification failed: {e}")
        sys.exit(1)

    # Initialize DynamoDB Table
    dynamodb = session.resource('dynamodb', region_name=args.region)
    table = dynamodb.Table(args.table)

    # Execute Scan
    print("\nScanning table data...")
    try:
        scanned_items, eval_count = scan_table_data(table, args.limit)
    except SafetyLimitExceededError as e:
        print(f"\nERROR: Safety limit exceeded. Scan aborted. {e}")
        print("INCOMPLETE RESULT: Performing zero writes. Exiting.")
        sys.exit(2)
    except Exception as e:
        print(f"\nERROR: Scan failed. {e}")
        sys.exit(1)

    print(f"Scan complete. Evaluated {eval_count} items.")

    # Classify
    diagnostic_counters, disposition_counters, proposed_updates, proposed_accounting = classify_and_propose(scanned_items)

    print("\n=== DIAGNOSTIC REPORT ===")
    print(f"Total Evaluated Table Items:    {diagnostic_counters['total_evaluated']}")
    print(f"Total PET Items Identified:     {diagnostic_counters['total_pets']}")
    print(f"PETs Missing pet_id:            {diagnostic_counters['missing_pet_id']}")
    print(f"PETs Missing client_id:         {diagnostic_counters['missing_client_id']}")
    print(f"PETs Missing company_id:        {diagnostic_counters['missing_company_id']}")
    print(f"PETs Missing entity_type:       {diagnostic_counters['missing_entity_type']}")
    print(f"PETs Missing is_active:         {diagnostic_counters['missing_is_active']}")
    print("-" * 30)
    print(f"PETs Malformed PK:              {diagnostic_counters['malformed_pk']}")
    print(f"PETs Malformed SK:              {diagnostic_counters['malformed_sk']}")
    print(f"PETs Ambiguous Client:          {diagnostic_counters['ambiguous_client_ownership']}")
    print(f"PETs Client Not Found:          {diagnostic_counters['client_ownership_not_found']}")
    print("=========================")

    print("\n=== FINAL DISPOSITION REPORT ===")
    print(f"Complete PET Items:             {disposition_counters['complete']}")
    print(f"Eligible for Full Remediation:  {disposition_counters['eligible_for_full_remediation']}")
    print(f"Eligible for Partial Remediation: {disposition_counters['eligible_for_partial_remediation']}")
    print(f"Compatibility Handled is_active: {disposition_counters['compatibility_handled_missing_is_active_only']}")
    print(f"Requires Manual Review:         {disposition_counters['requires_manual_review']}")
    print("================================")

    print("\n=== PROPOSED CHANGES REPORT ===")
    print(f"Proposed pet_id additions:      {proposed_accounting['proposed_pet_id']}")
    print(f"Proposed client_id additions:    {proposed_accounting['proposed_client_id']}")
    print(f"Proposed company_id additions:   {proposed_accounting['proposed_company_id']}")
    print(f"Proposed entity_type additions:  {proposed_accounting['proposed_entity_type']}")
    print("-" * 30)
    print(f"Total Items with Proposed updates: {proposed_accounting['total_items_with_proposals']}")
    print(f"Total Proposed Attribute additions: {proposed_accounting['total_attribute_additions']}")
    print("================================")

    if is_dry_run:
        print("\nDRY RUN: No write operations were performed.")
        return

    if not proposed_updates:
        print("\nNo updates proposed. Nothing to do.")
        return

    print(f"\nApplying conditional updates to {len(proposed_updates)} records...")
    success, cond_fail, failed = apply_remediations(table, proposed_updates)
    print("\n=== EXECUTION SUMMARY ===")
    print(f"Successfully remediated:       {success}")
    print(f"Skipped (concurrent change):  {cond_fail}")
    print(f"Failed updates:                {failed}")
    print("=========================")


if __name__ == "__main__":
    main()
