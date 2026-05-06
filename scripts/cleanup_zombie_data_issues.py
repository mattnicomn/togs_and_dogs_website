import boto3
import os
import argparse
import sys
import json
import uuid
from datetime import datetime
from boto3.dynamodb.conditions import Attr

# --- CONFIGURATION ---
TABLE_NAME = os.environ.get('DATA_TABLE_NAME', 'togs-and-dogs-prod-data')
REGION = 'us-east-1'

KNOWN_STATUSES = [
    'PENDING_REVIEW', 'NEEDS_REVIEW', 'READY_FOR_APPROVAL', 'NEW_REQUEST',
    'MEET_GREET_REQUIRED', 'NEEDS_MG', 'VERIFY_MEET_GREET', 'MG_SCHEDULED',
    'QUOTE_NEEDED', 'QUOTED', 'QUOTE_SENT', 'APPROVED', 'BOOKED',
    'ASSIGNED', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED',
    'REJECTED', 'DECLINED', 'DENIED', 'ARCHIVED', 'ARCHIVE', 'DELETED', 'TRASH',
    'PROFILE_CREATED', 'CANCELLATION_REQUESTED', 'CANCELLATION_DENIED'
]

TERMINAL_STATUSES = ['DELETED', 'TRASH', 'ARCHIVED', 'ARCHIVE']

CONFIRMATION_PHRASE = "DELETE_ZOMBIE_DATA_ISSUES"

# --- CORE LOGIC ---

def matches_ui_data_issue(item):
    """
    Implements the same logic used in the Admin Portal for the 'Data Issues' filter.
    Now hardened to exclude non-request system records.
    """
    pk = (item.get('PK') or "").upper()
    status = (item.get('status') or "").upper()
    
    # 1. System/Audit Record Exclusion (New Guardrail)
    system_prefixes = ['AUDIT#', 'COMPANY#', 'STAFF#', 'CLIENT#', 'CONFIG#', 'PROFILE#']
    if any(pk.startswith(pref) for pref in system_prefixes) or item.get('type') == 'AUDIT':
        return False

    # 2. Terminal State Exclusion
    if status in TERMINAL_STATUSES or item.get('deleted_at'):
        return False
        
    pet_names = (item.get('pet_names') or item.get('pet_name') or "").strip()
    client_name = (item.get('client_name') or "").strip()
    
    is_issue = (
        not status or 
        status == "UNKNOWN" or 
        not pet_names or 
        not client_name or
        (pet_names == "---" and client_name == "No Client Name") or
        status not in KNOWN_STATUSES
    )
    return is_issue

def is_zombie_candidate(item, scope='visible-data-issues'):
    """
    Identifies if a record is a candidate for deletion based on the selected scope.
    """
    pk = item.get('PK', '')
    sk = item.get('SK', '')
    status = (item.get('status') or "").upper()
    
    # Safety Check: Must have PK and SK
    if not pk or not sk:
        return False, None, "Missing PK or SK"

    # Safety Check: Do not touch protected system records or staff/clients profiles
    if any(pk.startswith(prefix) for prefix in ["COMPANY#", "STAFF#", "CLIENT#", "CONFIG#", "PROFILE#"]):
        return False, None, "System or Profile record"

    # Identify corruption patterns
    is_malformed_audit = pk.startswith("AUDIT#AUDIT#")
    is_malformed_req = pk.count("REQ#") > 1 or pk.count("JOB#") > 1
    is_normal_audit = (pk.startswith("AUDIT#") or item.get('type') == 'AUDIT') and not is_malformed_audit

    if scope == 'malformed-audit':
        if is_malformed_audit:
            return True, "Malformed Audit prefix (multi-prefix)", None
        return False, None, "Not a malformed audit"

    if scope == 'visible-data-issues':
        # 1. Must match UI Data Issue logic
        if not matches_ui_data_issue(item):
            return False, None, "Does not match UI Data Issue pattern or is Terminal/Deleted"
            
        # 2. Safety: Must not be a normal audit
        if is_normal_audit:
            return False, None, "Normal Audit record"
            
        # 3. Target malformed or missing transition IDs
        # (This is implicit in the Data Issue pattern usually, but we check PK/SK here)
        reasons = []
        if is_malformed_audit:
            reasons.append("Malformed Audit prefix in visible issues")
        if is_malformed_req:
            reasons.append("Malformed Request/Job prefix in visible issues")
        if not status or status == "UNKNOWN" or status not in KNOWN_STATUSES:
            reasons.append(f"Invalid/Missing status: '{status}'")
            
        return True, "; ".join(reasons) if reasons else "UI Data Issue pattern", None

    if scope == 'deleted-zombies':
        # Target records already in terminal/deleted state that are still zombies
        if status not in ['DELETED', 'TRASH'] and not item.get('deleted_at'):
            return False, None, "Not in Deleted state"
            
        if is_malformed_audit or is_malformed_req:
            return True, "Malformed prefix in Deleted state", None
            
        if matches_ui_data_issue(item): # This would be true if we removed the status check in matches_ui_data_issue
             # Re-checking with the specific issue pattern but allowing DELETED status
             pet_names = (item.get('pet_names') or item.get('pet_name') or "").strip()
             client_name = (item.get('client_name') or "").strip()
             if not pet_names or not client_name:
                 return True, "Missing names in Deleted state", None

    return False, None, "Healthy or out of scope"

def run_cleanup(scope='visible-data-issues', execute=False):
    session = boto3.Session(profile_name='usmissionhero-website-prod')
    dynamodb = session.resource('dynamodb', region_name=REGION)
    table = dynamodb.Table(TABLE_NAME)

    print(f"--- Togs and Dogs Zombie Cleanup ---")
    print(f"Table: {TABLE_NAME}")
    print(f"Scope: {scope}")
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
    blocked = []

    for item in items:
        is_cand, reason, block_reason = is_zombie_candidate(item, scope=scope)
        if is_cand:
            candidates.append((item, reason))
        elif block_reason and block_reason != "Healthy or out of scope":
            blocked.append((item, block_reason))

    # 2. Output Dry Run Results
    print(f"Total records scanned: {total_scanned}")
    print(f"Total candidate records found for scope '{scope}': {len(candidates)}")
    print(f"Total records blocked/skipped: {len(blocked)}")
    
    if candidates:
        print("\nSample candidates (max 10):")
        for item, reason in candidates[:10]:
            print(f"  PK: {item.get('PK')}, SK: {item.get('SK')}")
            print(f"    Reason: {reason}")
            print(f"    Status: {item.get('status')}, Client: {item.get('client_name')}, Pets: {item.get('pet_names') or item.get('pet_name')}")
    
    # Breakdown by PK prefix
    prefixes = {}
    for item, _ in candidates:
        pk = item.get('PK', '')
        pref = pk.split('#')[0] if '#' in pk else 'OTHER'
        if pk.startswith('AUDIT#AUDIT#'): pref = 'MALFORMED_AUDIT'
        prefixes[pref] = prefixes.get(pref, 0) + 1
    
    if prefixes:
        print("\nCandidate Type Breakdown:")
        for p, count in prefixes.items():
            print(f"  {p}: {count}")

    print("-" * 40)

    # 3. Execution Phase
    if execute:
        if not candidates:
            print("\nNo candidates to delete. Aborting.")
            return

        print(f"\nCRITICAL: You are about to delete {len(candidates)} records in scope '{scope}'.")
        print(f"To proceed, type the confirmation phrase exactly: {CONFIRMATION_PHRASE}")
        
        user_input = input("Confirmation: ")
        if user_input != CONFIRMATION_PHRASE:
            print("Confirmation failed. Aborting.")
            return

        success_count = 0
        fail_count = 0
        failed_keys = []

        print(f"\nDeleting {len(candidates)} records...")
        for item, reason in candidates:
            pk = item.get('PK')
            sk = item.get('SK')
            try:
                table.delete_item(Key={'PK': pk, 'SK': sk})
                success_count += 1
                if success_count % 20 == 0:
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

        # 4. Final Validation
        print("\nRe-scanning for validation...")
        val_items = []
        response = table.scan()
        val_items.extend(response.get('Items', []))
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            val_items.extend(response.get('Items', []))

        remaining = 0
        for item in val_items:
            is_cand, _, _ = is_zombie_candidate(item, scope=scope)
            if is_cand:
                remaining += 1
        
        print(f"Remaining candidates in scope '{scope}': {remaining}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cleanup zombie Data Issue records from DynamoDB.")
    parser.add_argument("--execute", action="store_true", help="Actually execute the deletion.")
    parser.add_argument("--dry-run", action="store_true", help="Explicit dry run (default).")
    parser.add_argument("--scope", choices=['visible-data-issues', 'deleted-zombies', 'malformed-audit'], 
                        default='visible-data-issues', help="Scope of cleanup.")
    
    args = parser.parse_args()
    run_cleanup(scope=args.scope, execute=args.execute)
