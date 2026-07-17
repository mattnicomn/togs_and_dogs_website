#!/usr/bin/env python3
"""
Production-safe legacy pet attribute remediation utility.
Defaults to dry-run and performs strict AWS profile, account, region, and table validations.
Uses concurrent-safe conditional updates to enrich missing fields (pet_id, client_id, company_id, entity_type).
Deliberately excludes is_active from automatic remediation.
"""
import argparse
import sys
import re
import boto3
from botocore.exceptions import ClientError

# Hardcoded production approval gate safeguards
APPROVED_ACCOUNT_ID = "358604342897"
APPROVED_TABLE_NAME = "togs-and-dogs-prod-data"
APPROVED_REGION = "us-east-1"
APPROVED_CONFIRM_WRITE = "PET-LEGACY-REMEDIATION"

PET_PK_RE = re.compile(r"^PET#([a-zA-Z0-9-]+)$")
CLIENT_SK_RE = re.compile(r"^CLIENT#([a-zA-Z0-9-]+)$")


def verify_aws_identity(session, expected_account_id, expected_region):
    """
    Call STS GetCallerIdentity and verify AWS account.
    """
    sts = session.client('sts', region_name=expected_region)
    try:
        identity = sts.get_caller_identity()
        caller_account = identity.get('Account')
    except Exception as e:
        raise RuntimeError(f"Failed to verify AWS identity via STS: {e}")
        
    if caller_account != expected_account_id:
        raise ValueError(f"STS verification failed: caller account {caller_account} does not match expected {expected_account_id}")
    return caller_account


def scan_table_data(table, limit):
    """
    Scan all records using paginated scan, projecting only target attributes.
    Note: ProjectionExpression only filters returned fields; it does not reduce read capacity consumption.
    """
    items = []
    scan_kwargs = {
        "ProjectionExpression": "PK, SK, pet_id, client_id, company_id, entity_type, is_active, #n",
        "ExpressionAttributeNames": {"#n": "name"}
    }
    
    evaluated_count = 0
    response = table.scan(**scan_kwargs)
    while True:
        batch = response.get('Items', [])
        items.extend(batch)
        evaluated_count += len(batch)
        
        if evaluated_count > limit:
            print(f"WARNING: Safety limit of {limit} evaluated items exceeded. Stopping scan.")
            break
            
        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
            
        scan_kwargs["ExclusiveStartKey"] = last_key
        response = table.scan(**scan_kwargs)
        
    return items, evaluated_count


def classify_and_propose(items):
    """
    Classify scanned items and propose missing attributes to populate.
    """
    # 1. Identify CLIENT records to build company ownership map
    client_ownership = {}  # client_id -> set of company_ids
    
    for item in items:
        pk = item.get('PK', '')
        sk = item.get('SK', '')
        
        if pk.startswith('COMPANY#') and sk.startswith('CLIENT#'):
            parts_pk = pk.split('#')
            parts_sk = sk.split('#')
            if len(parts_pk) > 1 and len(parts_sk) > 1:
                comp_id = parts_pk[1]
                cl_id = parts_sk[1]
                if cl_id not in client_ownership:
                    client_ownership[cl_id] = set()
                client_ownership[cl_id].add(comp_id)

    # Classification counters
    counters = {
        'total_evaluated': len(items),
        'total_pets': 0,
        'complete': 0,
        'missing_pet_id': 0,
        'missing_client_id': 0,
        'missing_company_id': 0,
        'missing_entity_type': 0,
        'missing_is_active': 0,
        'malformed_pk': 0,
        'malformed_sk': 0,
        'ambiguous_client_ownership': 0,
        'client_ownership_not_found': 0,
        'eligible_for_remediation': 0,
        'requires_manual_review': 0,
        'total_remediations_proposed': 0,
    }

    proposed_updates = []

    for item in items:
        pk = item.get('PK', '')
        sk = item.get('SK', '')
        entity_type = item.get('entity_type')
        
        is_pet_pk = pk.startswith('PET#')
        is_pet_entity = entity_type == 'PET'
        
        if not (is_pet_pk or is_pet_entity):
            continue
            
        counters['total_pets'] += 1
        
        pk_match = PET_PK_RE.match(pk)
        sk_match = CLIENT_SK_RE.match(sk)
        
        is_malformed = False
        missing_fields = []
        
        if not pk_match:
            counters['malformed_pk'] += 1
            is_malformed = True
        if not sk_match:
            counters['malformed_sk'] += 1
            is_malformed = True
            
        if 'pet_id' not in item:
            counters['missing_pet_id'] += 1
            missing_fields.append('pet_id')
        if 'client_id' not in item:
            counters['missing_client_id'] += 1
            missing_fields.append('client_id')
        if 'company_id' not in item:
            counters['missing_company_id'] += 1
            missing_fields.append('company_id')
        if 'entity_type' not in item:
            counters['missing_entity_type'] += 1
            missing_fields.append('entity_type')
        if 'is_active' not in item:
            counters['missing_is_active'] += 1
            missing_fields.append('is_active')

        has_entity_conflict = False
        if entity_type and entity_type != 'PET':
            has_entity_conflict = True
            
        derived_client_id = sk_match.group(1) if sk_match else item.get('client_id')
        resolved_company_id = None
        
        if 'company_id' not in item and derived_client_id:
            owners = client_ownership.get(derived_client_id, set())
            if len(owners) == 1:
                resolved_company_id = list(owners)[0]
            elif len(owners) > 1:
                counters['ambiguous_client_ownership'] += 1
            else:
                counters['client_ownership_not_found'] += 1
                
        # Remediability check
        eligible_fields_to_add = {}
        if not is_malformed and not has_entity_conflict:
            if 'pet_id' not in item and pk_match:
                eligible_fields_to_add['pet_id'] = pk_match.group(1)
            if 'client_id' not in item and sk_match:
                eligible_fields_to_add['client_id'] = sk_match.group(1)
            if 'entity_type' not in item:
                eligible_fields_to_add['entity_type'] = 'PET'
            if 'company_id' not in item:
                if resolved_company_id:
                    eligible_fields_to_add['company_id'] = resolved_company_id

        # Categorize item
        is_unresolved_company = ('company_id' not in item and not resolved_company_id and derived_client_id)
        
        if not missing_fields:
            counters['complete'] += 1
        elif is_malformed or has_entity_conflict or is_unresolved_company:
            counters['requires_manual_review'] += 1
        else:
            if eligible_fields_to_add:
                counters['eligible_for_remediation'] += 1
                proposed_updates.append({
                    'PK': pk,
                    'SK': sk,
                    'updates': eligible_fields_to_add
                })
                counters['total_remediations_proposed'] += len(eligible_fields_to_add)
                
    return counters, proposed_updates


def apply_remediations(table, proposed_updates):
    """
    Apply proposed updates conditionally.
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
            code = e.response.get('Error', {}).get('Code')
            if code == 'ConditionalCheckFailedException':
                conditional_fail_count += 1
                print("INFO: Skip concurrent update for an item (ConditionalCheckFailedException)")
            else:
                failure_count += 1
                print(f"ERROR: Failed to update item: {e}")
        except Exception as e:
            failure_count += 1
            print(f"ERROR: Unexpected update failure: {e}")
            
    return success_count, conditional_fail_count, failure_count


def main():
    parser = argparse.ArgumentParser(description="Remediate legacy PET attributes in DynamoDB.")
    parser.add_argument('--profile', required=True, help="AWS profile name")
    parser.add_argument('--region', required=True, help="AWS region")
    parser.add_argument('--table', required=True, help="AWS table name")
    parser.add_argument('--expected-account-id', required=True, help="Expected AWS account ID")
    parser.add_argument('--dry-run', action='store_true', default=True, help="Dry run mode (default: True)")
    parser.add_argument('--apply', action='store_true', default=False, help="Explicitly enable apply mode")
    parser.add_argument('--confirm-write', help="Confirm write validation value")
    parser.add_argument('--limit', type=int, default=5000, help="Max items safety scan limit")
    
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
        
    is_dry_run = args.dry_run
    if args.apply:
        is_dry_run = False
        
    if not is_dry_run:
        # Strict validation checks for write mode
        if not args.apply:
            print("ERROR: Apply mode requires '--apply'")
            sys.exit(1)
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
    scanned_items, eval_count = scan_table_data(table, args.limit)
    print(f"Scan complete. Evaluated {eval_count} items.")
    
    # Classify
    counters, proposed_updates = classify_and_propose(scanned_items)
    
    print("\n=== CLASSIFICATION REPORT ===")
    print(f"Total Evaluated Table Items:    {counters['total_evaluated']}")
    print(f"Total PET Items Identified:     {counters['total_pets']}")
    print(f"Complete PET Items:             {counters['complete']}")
    print(f"PETs Missing pet_id:            {counters['missing_pet_id']}")
    print(f"PETs Missing client_id:         {counters['missing_client_id']}")
    print(f"PETs Missing company_id:        {counters['missing_company_id']}")
    print(f"PETs Missing entity_type:       {counters['missing_entity_type']}")
    print(f"PETs Missing is_active:         {counters['missing_is_active']}")
    print("-" * 30)
    print(f"PETs Malformed PK:              {counters['malformed_pk']}")
    print(f"PETs Malformed SK:              {counters['malformed_sk']}")
    print(f"PETs Ambiguous Client:          {counters['ambiguous_client_ownership']}")
    print(f"PETs Client Not Found:          {counters['client_ownership_not_found']}")
    print("-" * 30)
    print(f"Eligible for Auto-Remediation:  {counters['eligible_for_remediation']}")
    print(f"Requires Manual Review:         {counters['requires_manual_review']}")
    print(f"Total Proposed Field Changes:   {counters['total_remediations_proposed']}")
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
