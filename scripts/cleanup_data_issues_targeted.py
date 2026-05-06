"""
Data Issues Cleanup Script
Approved actions:
  - DELETE JOB#1da26dbb (orphaned duplicate job)
  - DELETE PET#45691f4a (orphaned test pet, no status)
  - UPDATE JOB#0c353779 status: JOB_CREATED -> SCHEDULED
  - ENRICH PET#1eee3233: add client_name = 'Test Validation'
"""
import boto3
import json
import os
from datetime import datetime, timezone

PROFILE = 'usmissionhero-website-prod'
REGION = 'us-east-1'
TABLE = 'togs-and-dogs-prod-data'

TARGETS = {
    'JOB#1da26dbb-6db7-4bbd-91e7-00aa569273b7': {
        'SK': 'REQ#98394347-960a-4b8c-a305-5c9229ede605',
        'action': 'DELETE',
        'reason': 'Orphaned duplicate job superseded by JOB#0c353779; not referenced by REQ#98394347 as active job_id.'
    },
    'JOB#0c353779-a12a-42e1-a2da-df19d047b4d7': {
        'SK': 'REQ#98394347-960a-4b8c-a305-5c9229ede605',
        'action': 'UPDATE_STATUS',
        'new_status': 'SCHEDULED',
        'reason': 'Active job_id on REQ#98394347. JOB_CREATED is not a valid UI lifecycle status.'
    },
    'PET#45691f4a-7343-4209-ac2e-6b09ff28029d': {
        'SK': 'CLIENT#e9857fd0-d46a-4484-b0cb-814cd0bd38b7',
        'action': 'DELETE',
        'reason': 'Orphaned test pet with no status and no active REQ/JOB references.'
    },
    'PET#1eee3233-e09d-4ac5-9562-ce0c93cccff7': {
        'SK': 'CLIENT#e0eda09c-8fd5-4d52-bc14-f1056f713245',
        'action': 'ENRICH',
        'add_fields': {'client_name': 'Test Validation'},
        'reason': 'Active test pet missing client_name field; causes Data Issue flag. REQ#98394347 client_name = Test Validation.'
    },
}

ALSO_INSPECT = [
    ('REQ#98394347-960a-4b8c-a305-5c9229ede605', 'CLIENT#e0eda09c-8fd5-4d52-bc14-f1056f713245'),
    ('CLIENT#e9857fd0-d46a-4484-b0cb-814cd0bd38b7', 'METADATA'),
]

# Safety: never allow deletion of these prefixes as primary targets
PROTECTED_PREFIXES = ['REQ#', 'CLIENT#', 'STAFF#', 'COMPANY#', 'CONFIG#', 'PROFILE#', 'AUDIT#']


def run(execute=False):
    session = boto3.Session(profile_name=PROFILE)
    dynamodb = session.resource('dynamodb', region_name=REGION)
    table = dynamodb.Table(TABLE)

    timestamp = datetime.now().strftime('%Y-%m-%d-%H%M%S')
    backup_dir = 'backups/data-issues-cleanup'
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = f'{backup_dir}/data-issues-backup-{timestamp}.json'

    print(f'Mode: {"EXECUTE" if execute else "DRY RUN"}')
    print(f'Backup path: {backup_path}')
    print('-' * 60)

    # --- BACKUP ---
    backup_items = []
    print('\nFetching records for backup...')
    for pk, meta in TARGETS.items():
        resp = table.get_item(Key={'PK': pk, 'SK': meta['SK']})
        item = resp.get('Item')
        if item:
            backup_items.append({'record': item, 'planned_action': meta['action'], 'reason': meta['reason']})
            print(f'  Backed up: {pk} / {meta["SK"]}')
        else:
            print(f'  NOT FOUND: {pk} / {meta["SK"]}')

    for pk, sk in ALSO_INSPECT:
        resp = table.get_item(Key={'PK': pk, 'SK': sk})
        item = resp.get('Item')
        if item:
            backup_items.append({'record': item, 'planned_action': 'READ_ONLY', 'reason': 'Inspected for context'})
            print(f'  Backed up (read-only): {pk} / {sk}')

    with open(backup_path, 'w') as f:
        json.dump(backup_items, f, indent=2, default=str)
    print(f'\nBackup written: {backup_path}')

    # --- DRY RUN PLAN ---
    print('\n--- Planned Actions ---')
    for pk, meta in TARGETS.items():
        print(f'  [{meta["action"]}] {pk}')
        print(f'    SK: {meta["SK"]}')
        print(f'    Reason: {meta["reason"]}')
        if meta['action'] == 'UPDATE_STATUS':
            print(f'    New status: {meta["new_status"]}')
        if meta['action'] == 'ENRICH':
            print(f'    Add fields: {meta["add_fields"]}')

    if not execute:
        print('\nDRY RUN COMPLETE. No changes made.')
        return backup_path

    # --- SAFETY CHECK ---
    for pk, meta in TARGETS.items():
        if meta['action'] == 'DELETE':
            for prefix in PROTECTED_PREFIXES:
                if pk.startswith(prefix):
                    raise RuntimeError(f'SAFETY ABORT: Attempted to delete protected record {pk}')

    # --- EXECUTE ---
    print('\n--- Executing Changes ---')

    for pk, meta in TARGETS.items():
        sk = meta['SK']

        if meta['action'] == 'DELETE':
            table.delete_item(Key={'PK': pk, 'SK': sk})
            print(f'  DELETED: {pk} / {sk}')

        elif meta['action'] == 'UPDATE_STATUS':
            table.update_item(
                Key={'PK': pk, 'SK': sk},
                UpdateExpression='SET #s = :s, updated_at = :ts',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={
                    ':s': meta['new_status'],
                    ':ts': datetime.now(timezone.utc).isoformat()
                }
            )
            print(f'  UPDATED STATUS: {pk} -> {meta["new_status"]}')

        elif meta['action'] == 'ENRICH':
            update_expr_parts = []
            expr_names = {}
            expr_vals = {}
            for i, (field, val) in enumerate(meta['add_fields'].items()):
                placeholder = f'#f{i}'
                val_placeholder = f':v{i}'
                update_expr_parts.append(f'{placeholder} = {val_placeholder}')
                expr_names[placeholder] = field
                expr_vals[val_placeholder] = val
            expr_names['#ts'] = 'updated_at'
            expr_vals[':ts'] = datetime.now(timezone.utc).isoformat()
            update_expr_parts.append('#ts = :ts')
            table.update_item(
                Key={'PK': pk, 'SK': sk},
                UpdateExpression='SET ' + ', '.join(update_expr_parts),
                ExpressionAttributeNames=expr_names,
                ExpressionAttributeValues=expr_vals
            )
            print(f'  ENRICHED: {pk} added {list(meta["add_fields"].keys())}')

    print('\nExecution complete.')
    return backup_path


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    run(execute=args.execute)
