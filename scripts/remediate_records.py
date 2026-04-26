import boto3
import os
import json
from datetime import datetime, timezone

# Configuration
TABLE_NAME = "togs-and-dogs-prod-data"
DRY_RUN = True # Set to False to actually update records

# Standard Statuses (from src/backend/common/status.py)
VALID_STATUSES = [
    "PENDING_REVIEW", "MEET_GREET_REQUIRED", "READY_FOR_APPROVAL", 
    "APPROVED", "ASSIGNED", "DECLINED", "CANCELLATION_REQUESTED", 
    "CANCELLATION_DENIED", "CANCELLED", "COMPLETED", "PROFILE_CREATED", 
    "ARCHIVED", "DELETED"
]

LEGACY_MAP = {
    "REQUEST_SUBMITTED": "PENDING_REVIEW",
    "REQUEST_UNDER_REVIEW": "PENDING_REVIEW",
    "REQUEST_APPROVED": "APPROVED",
    "REQUEST_DECLINED": "DECLINED",
    "MEET_AND_GREET": "MEET_GREET_REQUIRED",
    "READY": "READY_FOR_APPROVAL"
}

def remediate():
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.Table(TABLE_NAME)
    
    print(f"Starting remediation on table: {TABLE_NAME} (DRY_RUN={DRY_RUN})")
    
    scan_kwargs = {}
    done = False
    start_key = None
    
    processed_count = 0
    updated_count = 0
    deleted_count = 0
    
    while not done:
        if start_key:
            scan_kwargs['ExclusiveStartKey'] = start_key
        
        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])
        
        for item in items:
            processed_count += 1
            pk = item.get('PK')
            sk = item.get('SK')
            status = item.get('status')
            client_name = item.get('client_name', '').lower()
            pet_names = str(item.get('pet_names', '')).lower()
            
            needs_update = False
            new_status = status
            
            # 1. Normalize Legacy Statuses
            if status in LEGACY_MAP:
                new_status = LEGACY_MAP[status]
                print(f"INFO: [Record {pk}/{sk}] Normalizing legacy status: {status} -> {new_status}")
                needs_update = True
            
            # 2. Identify Test Records and mark as DELETED
            # Patterns: "test", "dummy", "asdf", etc.
            is_test = any(pattern in client_name for pattern in ["test", "dummy", "fake"]) or \
                      any(pattern in pet_names for pattern in ["test", "dummy", "asdf", "qwerty"])
            
            if is_test and status != 'DELETED':
                new_status = 'DELETED'
                print(f"INFO: [Record {pk}/{sk}] Marking test record as DELETED: {client_name} / {pet_names}")
                needs_update = True
            
            # 3. Ensure DELETED records don't stay in active states if they were mistakenly labeled
            # (Already handled by step 1 and 2 if status was legacy)
            
            if needs_update:
                updated_count += 1
                if not DRY_RUN:
                    try:
                        now = datetime.now(timezone.utc).isoformat()
                        table.update_item(
                            Key={'PK': pk, 'SK': sk},
                            UpdateExpression="SET #stat = :s, updated_at = :now, remediation_flag = :f",
                            ExpressionAttributeNames={"#stat": "status"},
                            ExpressionAttributeValues={
                                ":s": new_status,
                                ":now": now,
                                ":f": "REMEDIATED_2026_04_26"
                            }
                        )
                    except Exception as e:
                        print(f"ERROR: Failed to update record {pk}/{sk}: {e}")
        
        start_key = response.get('LastEvaluatedKey')
        done = start_key is None
        
    print(f"\nRemediation Complete.")
    print(f"Total Processed: {processed_count}")
    print(f"Total Needing Update: {updated_count}")
    if DRY_RUN:
        print("Note: This was a DRY RUN. No records were modified.")
    else:
        print(f"Successfully updated {updated_count} records.")

if __name__ == "__main__":
    remediate()
