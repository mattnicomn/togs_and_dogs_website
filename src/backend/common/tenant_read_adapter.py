"""
src/backend/common/tenant_read_adapter.py
Preview-Only V1: Tenant Onboarding Orchestrator — Read-Only DynamoDB Adapter

Provides read-only DynamoDB operations needed for the onboarding preview
conflict-detection step:

  - Fetch an existing tenant by company_id (existence check)
  - Scan for display-name collision detection (case-insensitive, exact)

DESIGN CONSTRAINTS (enforced by dedicated IAM role in platform_preview_iam.tf):
  - GetItem only (no PutItem, UpdateItem, DeleteItem, TransactWriteItems)
  - Scan only (no Query GSI writes, no secondary index creation)
  - No Cognito, Secrets Manager, SES, Lambda invoke
  - No logging of user data, tokens, or credential values

USAGE:
  This module is imported by platform_onboarding_handler.py ONLY.
  It must never be imported by the write-path handlers (intake, admin, etc.).
"""

import os
from botocore.exceptions import ClientError


def _get_table():
    """
    Return the DynamoDB table resource.

    Lazy initialization so the module can be imported without
    DATABASE_TABLE_NAME in test environments that mock at a higher level.
    """
    import boto3
    table_name = os.environ.get('DATA_TABLE_NAME')
    if not table_name:
        raise RuntimeError(
            "DATA_TABLE_NAME environment variable is not set"
        )
    dynamodb = boto3.resource('dynamodb')
    return dynamodb.Table(table_name)


# ---------------------------------------------------------------------------
# Public Read Operations
# ---------------------------------------------------------------------------


def get_tenant_by_company_id(company_id: str) -> dict | None:
    """
    Fetch the tenant metadata record for the given company_id.

    Returns:
        The DynamoDB item dict if found, else None.

    This is a GetItem (read-only) operation only.
    """
    try:
        table = _get_table()
        response = table.get_item(
            Key={'PK': f'TENANT#{company_id}', 'SK': 'METADATA'}
        )
        return response.get('Item')
    except ClientError as e:
        print(f"ONBOARDING READ ERROR: get_tenant_by_company_id({company_id!r}): {e}")
        raise
    except Exception as e:
        print(f"ONBOARDING READ ERROR: get_tenant_by_company_id({company_id!r}): {e}")
        raise


def check_display_name_conflict(display_name: str) -> list:
    """
    Scan the tenant table for existing METADATA records whose display_name
    matches the given value (case-insensitive, strip-normalized).

    Returns:
        List of conflicting company_id strings (empty if no conflict).

    Performance note: This is a full-table Scan with FilterExpression.
    Acceptable for V1 (few tenants); if tenant count grows significantly,
    a display-name GSI should be added separately.

    This is a Scan (read-only) operation only. No writes.
    """
    from boto3.dynamodb.conditions import Attr
    target = display_name.strip().lower()
    conflicts = []

    try:
        table = _get_table()
        scan_kwargs = {
            'FilterExpression': (
                Attr('entity_type').eq('TENANT') &
                Attr('SK').eq('METADATA')
            )
        }

        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])

        while 'LastEvaluatedKey' in response:
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
            response = table.scan(**scan_kwargs)
            items.extend(response.get('Items', []))

        for item in items:
            existing_name = (item.get('display_name') or '').strip().lower()
            if existing_name == target:
                conflicts.append(item.get('company_id', ''))

    except ClientError as e:
        print(f"ONBOARDING READ ERROR: check_display_name_conflict: {e}")
        raise
    except Exception as e:
        print(f"ONBOARDING READ ERROR: check_display_name_conflict: {e}")
        raise

    return [c for c in conflicts if c]
