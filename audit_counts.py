import boto3
import os
from boto3.dynamodb.conditions import Attr

# Set environment variables for the script
os.environ['DATA_TABLE_NAME'] = 'togs-and-dogs-prod-data'

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
table = dynamodb.Table('togs-and-dogs-prod-data')

def count_records():
    # 1. Count Data Issues
    # (Based on isDataIssue logic in JS)
    known_statuses = [
        'PENDING_REVIEW', 'NEEDS_REVIEW', 'READY_FOR_APPROVAL', 'NEW_REQUEST',
        'MEET_GREET_REQUIRED', 'NEEDS_MG', 'VERIFY_MEET_GREET', 'MG_SCHEDULED',
        'QUOTE_NEEDED', 'QUOTED', 'QUOTE_SENT', 'APPROVED', 'BOOKED',
        'ASSIGNED', 'SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED',
        'REJECTED', 'DECLINED', 'DENIED', 'ARCHIVED', 'ARCHIVE', 'DELETED', 'TRASH',
        'PROFILE_CREATED', 'CANCELLATION_REQUESTED', 'CANCELLATION_DENIED'
    ]
    
    scan_kwargs = {}
    items = []
    response = table.scan(**scan_kwargs)
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))

    data_issues = []
    trash_records = []
    active_records = []

    for item in items:
        status = (item.get('status') or "").upper()
        
        if status in ['DELETED', 'TRASH']:
            trash_records.append(item)
            continue
            
        if status == 'ARCHIVED':
            continue

        # Data Issue logic
        pet_names = item.get('pet_names') or item.get('pet_name') or ""
        client_name = item.get('client_name') or ""
        
        is_issue = (
            not status or 
            status == "UNKNOWN" or 
            not pet_names.strip() or 
            not client_name.strip() or
            (pet_names == "---" and client_name == "No Client Name") or
            status not in known_statuses
        )
        
        if is_issue:
            data_issues.append(item)
        else:
            active_records.append(item)

    print(f"Total Records Scanned: {len(items)}")
    print(f"Data Issues: {len(data_issues)}")
    print(f"Trash Records: {len(trash_records)}")
    print(f"Active Records: {len(active_records)}")

if __name__ == "__main__":
    try:
        count_records()
    except Exception as e:
        print(f"Error: {e}")
