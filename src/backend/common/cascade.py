"""
Release 1: REQ → JOB Cascade Utility

This module provides one-directional cascade from parent REQ records to linked JOB records.
All lifecycle transitions on a REQ record should cascade to the linked JOB record to prevent
orphaned or inconsistent JOB states.

Design decisions:
- Cascade flows REQ → JOB ONLY. No reverse cascade (JOB → REQ) to prevent loops.
- If no linked job_id exists on the request, cascade is a no-op.
- Failures are logged but do not block the parent operation (fail-safe).

Future enhancement: Track previous_status on the REQ record so recovery can restore
to the exact prior workflow state instead of always defaulting to APPROVED/PENDING_REVIEW.
"""

from datetime import datetime, timezone
from common.db import table


# Maps REQ statuses to their JOB equivalents.
# JOB records use a simpler status set than REQ records.
REQ_TO_JOB_STATUS_MAP = {
    'APPROVED': 'JOB_CREATED',
    'BOOKED': 'JOB_CREATED',
    'ASSIGNED': 'ASSIGNED',
    'COMPLETED': 'COMPLETED',
    'CANCELLED': 'CANCELLED',
    'CANCELLATION_REQUESTED': 'CANCELLED',
    'CANCELLATION_DENIED': 'ASSIGNED',  # Deny cancel = stay assigned
    'ARCHIVED': 'ARCHIVED',
    'DELETED': 'DELETED',
    'PENDING_REVIEW': 'JOB_CREATED',  # Recovery/reopen resets job
}


def cascade_status_to_job(request_item, new_req_status, updated_by='system', remove_worker=False):
    """
    Cascades a status change from a parent REQ record to its linked JOB record(s).

    Args:
        request_item: The REQ record dict (must contain 'job_ids' or 'job_id', and 'request_id').
        new_req_status: The new status being applied to the REQ record.
        updated_by: Who triggered the change (for audit trail).
        remove_worker: If True, removes worker_id from the JOB record (used on rollback).

    Returns:
        dict: {"success": bool, "message": str}
    """
    job_ids = request_item.get('job_ids') or []
    if not job_ids and request_item.get('job_id'):
        job_ids = [request_item.get('job_id')]
        
    request_id = request_item.get('request_id')

    if not job_ids or not request_id:
        # No linked job — cascade is a no-op
        return {"success": True, "message": "No linked jobs to cascade to."}

    # Resolve the JOB-equivalent status
    job_status = REQ_TO_JOB_STATUS_MAP.get(new_req_status, new_req_status)

    now = datetime.now(timezone.utc).isoformat()
    
    success_count = 0
    fail_count = 0

    for job_id in job_ids:
        try:
            # Build update expression
            update_expr = "SET #stat = :s, updated_at = :now, updated_by = :ub"
            expr_attr_names = {"#stat": "status"}
            expr_attr_vals = {
                ":s": job_status,
                ":now": now,
                ":ub": updated_by,
            }

            # Remove worker_id on rollback (e.g., ASSIGNED → APPROVED)
            if remove_worker:
                update_expr += " REMOVE worker_id, worker_name"

            table.update_item(
                Key={'PK': f"JOB#{job_id}", 'SK': f"REQ#{request_id}"},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_vals
            )

            print(f"INFO: [Cascade] JOB#{job_id} updated to {job_status} (from REQ#{request_id} → {new_req_status})")
            success_count += 1

        except Exception as e:
            # Fail-safe: log but do not block the parent operation
            print(f"WARNING: [Cascade] Failed to update JOB#{job_id} for REQ#{request_id}: {e}")
            fail_count += 1
            
    if fail_count > 0:
        return {"success": False, "message": f"Cascade partially failed: {success_count} succeeded, {fail_count} failed."}
    return {"success": True, "message": f"Cascaded to {success_count} JOB(s) with status {job_status}."}
