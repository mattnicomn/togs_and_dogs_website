import json
import os
import boto3
from datetime import datetime, timezone
from common.db import get_item, update_status, update_item, table
from common.response import success, error, bad_request, internal_error
from common.status import RequestStatus, is_valid_transition
from common.google_calendar import delete_event
from common.audit import log_action
from common.notifications.service import notify_event

# SNS client
sns = boto3.client('sns')

def handler(event, context):
    try:
        from common.entitlement import require_active_tenant
        block_resp = require_active_tenant(event)
        if block_resp:
            return block_resp

        http_method = event.get('httpMethod')
        path = event.get('path', '')
        body = json.loads(event.get('body', '{}'))

        # 1. Customer Request Path
        if http_method == 'POST' and 'cancel' in path:
            return handle_customer_request(body, event)
        
        # 2. Admin Decision Path
        if http_method == 'PUT' and 'decision' in path:
            return handle_admin_decision(body, event)

        return bad_request("Invalid endpoint for cancellation management", event)

    except Exception as e:
        print(f"Cancellation Handler Error: {str(e)}")
        return internal_error(str(e), event)

def handle_customer_request(body, event):
    request_id = body.get('request_id')
    client_id = body.get('client_id')
    reason = body.get('reason', 'No reason provided.')

    if not request_id or not client_id:
        return bad_request("Missing request_id or client_id", event)

    item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
    if not item:
        return error(403, "Forbidden", event)

    # Release 11E: Post-read tenant ownership validation
    from common.auth import validate_tenant_ownership, get_claims as _get_claims
    try:
        validate_tenant_ownership(item, event)
    except PermissionError:
        _claims = _get_claims(event)
        print(f"SECURITY: Cross-tenant cancel attempt by {_claims.get('email')} for REQ#{request_id}")
        return error(403, "Forbidden", event)

    from common.auth import require_client_booking_access
    try:
        require_client_booking_access(event, item)
    except PermissionError:
        return error(403, "Forbidden", event)


    # 24-hour warning logic check
    service_start_str = item.get('start_date')
    is_urgent = False
    if service_start_str:
        try:
            # Handle start_date which is often just YYYY-MM-DD for MVP
            if len(service_start_str) == 10:
                # Assume start of day if no time
                start_dt = datetime.fromisoformat(service_start_str).replace(tzinfo=timezone.utc)
            else:
                start_dt = datetime.fromisoformat(service_start_str.replace('Z', '+00:00'))
            
            now = datetime.now(timezone.utc)
            hours_diff = (start_dt - now).total_seconds() / 3600
            if hours_diff < 24:
                is_urgent = True
        except ValueError:
            pass

    # Update record with requested status
    audit_entry = {
        "status": "CANCELLATION_REQUESTED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "by": f"CLIENT#{client_id}",
        "reason": reason
    }

    # Atomically update status and append to audit log
    try:
        table.update_item(
            Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
            UpdateExpression="SET #stat = :s, cancellation_reason = :r, cancellation_requested_at = :t, cancellation_requested_by = :b, audit_log = list_append(if_not_exists(audit_log, :empty_list), :a)",
            ExpressionAttributeNames={"#stat": "status"},
            ExpressionAttributeValues={
                ":s": "CANCELLATION_REQUESTED",
                ":r": reason,
                ":t": audit_entry["timestamp"],
                ":b": audit_entry["by"],
                ":a": [audit_entry],
                ":empty_list": []
            }
        )
        success_db = True
    except Exception as e:
        print(f"Error recording cancellation request: {e}")
        success_db = False

    if not success_db:
        return internal_error("Failed to record cancellation request", event)

    return success({
        "message": "Cancellation request submitted for review.",
        "urgent_warning": is_urgent
    }, event)

def handle_admin_decision(body, event):
    request_id = body.get('request_id')
    client_id = body.get('client_id')
    decision = body.get('decision') # 'APPROVE' or 'DENY'
    note = body.get('note', '')

    from common.auth import get_effective_role
    role = get_effective_role(event)
    if role not in ['owner', 'admin']:
        return error(403, "Forbidden: Only owners and admins can process cancellation decisions", event)


    if not request_id or not client_id or not decision:
        return bad_request("Missing required decision fields", event)

    item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
    if not item:
        return error(404, "Booking request not found", event)

    # Release 11E: Post-read tenant ownership validation
    from common.auth import validate_tenant_ownership, get_claims as _get_claims
    try:
        validate_tenant_ownership(item, event)
    except PermissionError:
        _claims = _get_claims(event)
        print(f"SECURITY: Cross-tenant cancel decision attempt by {_claims.get('email')} for REQ#{request_id}")
        return error(403, "Forbidden", event)

    new_status = "CANCELLED" if decision == 'APPROVE' else "CANCELLATION_DENIED"
    ts = datetime.now(timezone.utc).isoformat()
    
    audit_entry = {
        "status": new_status,
        "timestamp": ts,
        "by": "ADMIN",
        "note": note,
        "sync_failures": []
    }

    # Atomic Update with Audit Log
    try:
        table.update_item(
            Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
            UpdateExpression="SET #stat = :s, cancellation_decision_at = :t, cancellation_decision_by = :b, cancellation_decision_note = :n, audit_log = list_append(if_not_exists(audit_log, :empty_list), :a)",
            ExpressionAttributeNames={"#stat": "status"},
            ExpressionAttributeValues={
                ":s": new_status,
                ":t": ts,
                ":b": "ADMIN",
                ":n": note,
                ":a": [audit_entry],
                ":empty_list": []
            }
        )
        
        # Release 1: Cascade REQ → JOB status change
        # This fixes the gap where cancellation_handler did not cascade to JOB records,
        # causing orphaned JOB records to remain in ASSIGNED status after parent was cancelled.
        from common.cascade import cascade_status_to_job
        cascade_status_to_job(item, new_status, updated_by="ADMIN")
        
        # Audit log
        log_action(
            event, 
            f"CANCEL_DECISION_{decision}", 
            f"REQ#{request_id}", 
            f"CLIENT#{client_id}", 
            previous_status=item.get('status'), 
            new_status=new_status,
            metadata={"client_name": item.get('client_name'), "pet_names": item.get('pet_names'), "decision": decision, "note": note}
        )
        
        success_db = True
    except Exception as e:
        print(f"Error updating cancellation decision: {e}")
        success_db = False

    if not success_db:
        return internal_error("Failed to update cancellation decision", event)

    # IF APPROVED: Clean up external dependencies
    message_id = None
    calendar_msg = ""
    if decision == 'APPROVE':
        # 1. Google Calendar Removal
        from common.google_calendar import delete_event_detailed
        
        # Collect event IDs from parent Request and all child Jobs
        event_to_records = {} # unique_event_id -> list of record keys to update
        job_ids = item.get('job_ids') or []
        company_id = item.get('company_id') or 'tog_and_dogs'
        
        parent_event_id = item.get('google_event_id')
        if parent_event_id:
            event_to_records.setdefault(parent_event_id, []).append({
                "PK": f"REQ#{request_id}",
                "SK": f"CLIENT#{client_id}"
            })
            
        for jid in job_ids:
            job_item = get_item(f"JOB#{jid}", f"REQ#{request_id}")
            if job_item and job_item.get('google_event_id'):
                jid_event_id = job_item['google_event_id']
                event_to_records.setdefault(jid_event_id, []).append({
                    "PK": f"JOB#{jid}",
                    "SK": f"REQ#{request_id}"
                })
                
        # Deduplicate and count unique event IDs
        unique_event_ids = list(event_to_records.keys())
        event_id_count = len(unique_event_ids)
        
        if event_id_count > 0:
            # Structured log for collection
            print(json.dumps({
                "event": "CALENDAR_CLEANUP_COLLECTED",
                "company_id": company_id,
                "request_id": request_id,
                "job_count": len(job_ids),
                "event_id_count": event_id_count
            }))
            
            deleted_count = 0
            for event_id in unique_event_ids:
                try:
                    gcal_success, already_gone, err_msg = delete_event_detailed(event_id, request_id)
                    if gcal_success:
                        if already_gone:
                            print(json.dumps({
                                "event": "CALENDAR_CLEANUP_ALREADY_GONE",
                                "company_id": company_id,
                                "request_id": request_id,
                                "event_id": event_id,
                                "deletion_status": "already_gone"
                            }))
                        else:
                            print(json.dumps({
                                "event": "CALENDAR_CLEANUP_DELETED",
                                "company_id": company_id,
                                "request_id": request_id,
                                "event_id": event_id,
                                "deletion_status": "deleted"
                            }))
                            deleted_count += 1
                        
                        # Remove google_event_id from all associated records in DynamoDB
                        for rec in event_to_records[event_id]:
                            try:
                                table.update_item(
                                    Key={'PK': rec['PK'], 'SK': rec['SK']},
                                    UpdateExpression="REMOVE google_event_id"
                                )
                            except Exception as db_err:
                                print(f"WARNING: Failed to remove google_event_id from {rec['PK']}: {db_err}")
                    else:
                        raise Exception(err_msg or "Unknown error")
                except Exception as ex:
                    fail_msg = str(ex)
                    print(json.dumps({
                        "event": "CALENDAR_CLEANUP_WARNING",
                        "company_id": company_id,
                        "request_id": request_id,
                        "event_id": event_id,
                        "deletion_status": "failed",
                        "error_type": fail_msg
                    }))
                    record_sync_failure(request_id, client_id, "GOOGLE_CALENDAR", f"Event ID {event_id} cleanup failed: {fail_msg}")
            
            if deleted_count > 0:
                calendar_msg = f"Deleted {deleted_count} calendar event(s)."
        else:
            # Structured log for no events
            print(json.dumps({
                "event": "CALENDAR_CLEANUP_NONE",
                "company_id": company_id,
                "request_id": request_id,
                "job_count": len(job_ids),
                "event_id_count": 0
            }))

        # 2. Worker Notification (SNS)
        worker_id = item.get('worker_id')
        if worker_id:
            try:
                message_id = notify_worker(worker_id, item)
            except Exception as ex:
                fail_msg = f"SNS notification failed: {str(ex)}"
                print(fail_msg)
                record_sync_failure(request_id, client_id, "SNS_NOTIFICATION", fail_msg)
        
        # 3. New modular notification system
        notify_event('VISIT_CANCELLED', item)

    msg_action = f"{decision.lower()}ed" if decision != 'DENY' else "denied"
    final_msg = f"Cancellation request {msg_action}."
    if calendar_msg:
        final_msg += f" {calendar_msg}"

    return success({
        "message": final_msg,
        "new_status": new_status,
        "sns_message_id": message_id
    }, event)

def notify_worker(worker_id, item):
    """Sends SMS notification via AWS SNS."""
    topic_arn = os.environ.get('STAFF_COORDINATION_SNS_ARN')
    if not topic_arn:
        raise Exception("STAFF_COORDINATION_SNS_ARN environment variable not set")

    message = (
        f"Tog and Dogs ALERT: Visit for {item.get('client_name')} on {item.get('start_date')} "
        f"has been CANCELLED. Please update your schedule accordingly."
    )
    
    response = sns.publish(
        TopicArn=topic_arn,
        Message=message,
        Subject="Visit Cancellation Alert"
    )
    
    msg_id = response.get('MessageId')
    print(f"SUCCESS: SNS Alert sent to {worker_id}, MessageId: {msg_id}")
    return msg_id

def record_sync_failure(request_id, client_id, sync_type, error_msg):
    """Records a synchronization failure in the audit log of the record."""
    try:
        failure_log = {
            "type": sync_type,
            "error": error_msg,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # We append to the last audit_log entry or just generally to a failure field
        table.update_item(
            Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
            UpdateExpression="SET sync_failures = list_append(if_not_exists(sync_failures, :empty_list), :f)",
            ExpressionAttributeValues={
                ":f": [failure_log],
                ":empty_list": []
            }
        )
    except Exception as e:
        print(f"CRITICAL: Failed to record sync failure for {request_id}: {e}")
