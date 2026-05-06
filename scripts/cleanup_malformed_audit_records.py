import boto3
import os
import argparse
import sys
import json
import uuid
from datetime import datetime

# --- CONFIGURATION ---
DEFAULT_TABLE_NAME = 'togs-and-dogs-prod-data'
DEFAULT_REGION = 'us-east-1'
DEFAULT_PROFILE = 'usmissionhero-website-prod'

# Safety Exclusion List
EXCLUSION_PREFIXES = [
    'REQ#', 'JOB#', 'CLIENT#', 'STAFF#', 'COMPANY#', 
    'CONFIG#', 'PROFILE#', 'USER#', 'PET#'
]

def is_malformed_audit(item):
    """
    Identifies if a record is a malformed audit record.
    Pattern: Repeated AUDIT# prefixes in PK or SK.
    """
    pk = item.get('PK', '')
    sk = item.get('SK', '')
    
    # Check for malformed patterns
    patterns = [
        pk.startswith("AUDIT#AUDIT#"),
        pk.count("AUDIT#") > 1,
        sk.startswith("AUDIT#AUDIT#"),
        sk.count("AUDIT#") > 1
    ]
    
    return any(patterns)

def is_safety_excluded(item):
    """
    Checks if a record should be explicitly excluded from deletion.
    """
    pk = item.get('PK', '')
    sk = item.get('SK', '')
    
    for prefix in EXCLUSION_PREFIXES:
        if pk.startswith(prefix) or sk.startswith(prefix):
            return True, prefix
            
    return False, None

def run_cleanup(table_name, profile, region, execute=False):
    session = boto3.Session(profile_name=profile)
    dynamodb = session.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)

    print(f"--- Togs and Dogs Malformed Audit Cleanup ---")
    print(f"Table: {table_name}")
    print(f"Profile: {profile}")
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN'}")
    print("-" * 40)

    # 1. Scan Table
    print("Scanning table...")
    items = []
    scan_kwargs = {}
    response = table.scan(**scan_kwargs)
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))

    total_scanned = len(items)
    candidates = []
    safety_exclusions = []
    other_records = 0

    for item in items:
        if is_malformed_audit(item):
            excluded, prefix = is_safety_excluded(item)
            if excluded:
                safety_exclusions.append((item, prefix))
            else:
                candidates.append(item)
        else:
            other_records += 1

    # 2. Results Summary
    print(f"Total records scanned: {total_scanned}")
    print(f"Malformed audit candidates: {len(candidates)}")
    print(f"Safety exclusions (malformed but protected): {len(safety_exclusions)}")
    print(f"Healthy/Other records: {other_records}")
    
    if safety_exclusions:
        print("\nSafety Exclusions Found (CRITICAL):")
        for item, prefix in safety_exclusions:
            print(f"  PK: {item.get('PK')}, SK: {item.get('SK')} (Matched Exclusion: {prefix})")

    if candidates:
        print("\nSample candidates (max 10):")
        for item in candidates[:10]:
            print(f"  PK: {item.get('PK')}, SK: {item.get('SK')}")

    # 3. Backup Phase
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    backup_dir = "backups/malformed-audit-records"
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    backup_path = f"{backup_dir}/malformed-audit-backup-{timestamp}.json"
    summary_path = f"{backup_dir}/malformed-audit-summary-{timestamp}.json"

    print(f"\nCreating backups...")
    with open(backup_path, 'w') as f:
        json.dump(candidates, f, indent=2)
    
    summary = {
        "timestamp": timestamp,
        "total_scanned": total_scanned,
        "malformed_count": len(candidates),
        "safety_exclusions": len(safety_exclusions),
        "backup_file": backup_path,
        "candidates": [ {"PK": c.get('PK'), "SK": c.get('SK')} for c in candidates ]
    }
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"  Backup saved to: {backup_path}")
    print(f"  Summary saved to: {summary_path}")

    # 4. Execution Phase
    if execute:
        if not candidates:
            print("\nNo candidates to delete. Aborting.")
            return

        print(f"\nCRITICAL: You are about to delete {len(candidates)} records.")
        print("This operation is IRREVERSIBLE.")
        confirm = input("Type 'CONFIRM DELETE' to proceed: ")
        
        if confirm != 'CONFIRM DELETE':
            print("Confirmation failed. Aborting.")
            return

        success_count = 0
        fail_count = 0
        failed_keys = []

        print(f"\nDeleting records...")
        for item in candidates:
            pk = item.get('PK')
            sk = item.get('SK')
            try:
                table.delete_item(Key={'PK': pk, 'SK': sk})
                success_count += 1
                if success_count % 50 == 0:
                    print(f"  Deleted {success_count}...")
            except Exception as e:
                fail_count += 1
                failed_keys.append((pk, sk, str(e)))

        print(f"\nResults:")
        print(f"  Successful deletes: {success_count}")
        print(f"  Failed deletes: {fail_count}")
        
        if failed_keys:
            print("\nFailed keys:")
            for pk, sk, err in failed_keys:
                print(f"  PK: {pk}, SK: {sk} -> {err}")

    print("-" * 40)
    return {
        "total_scanned": total_scanned,
        "malformed_count": len(candidates),
        "safety_exclusions": len(safety_exclusions),
        "backup_path": backup_path,
        "summary_path": summary_path
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup malformed audit records from DynamoDB.")
    parser.add_argument("--execute", action="store_true", help="Actually execute the deletion.")
    parser.add_argument("--dry-run", action="store_true", help="Explicit dry run.")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="AWS Profile name.")
    parser.add_argument("--table", default=DEFAULT_TABLE_NAME, help="DynamoDB table name.")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS Region.")
    
    args = parser.parse_args()
    
    # If neither or both specified, default to dry run
    is_execute = args.execute
    
    run_cleanup(
        table_name=args.table, 
        profile=args.profile, 
        region=args.region, 
        execute=is_execute
    )
