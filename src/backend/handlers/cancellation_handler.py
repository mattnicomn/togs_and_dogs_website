import json
import os
import boto3
from datetime import datetime, timezone
from common.db import get_item, update_status, update_item, table
from common.response import success, error, bad_request, internal_error
from common.status import RequestStatus, is_valid_transition
from common.google_calendar import delete_event

# SNS client
sns = boto3.client('sns')

def handler(event, context):
    try:
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
        return error(404, "Booking request not found", event)

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

    if not request_id or not client_id or not decision:
        return bad_request("Missing required decision fields", event)

    item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
    if not item:
        return error(404, "Booking request not found", event)

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
        success_db = True
    except Exception as e:
        print(f"Error updating cancellation decision: {e}")
        success_db = False

    if not success_db:
        return internal_error("Failed to update cancellation decision", event)

    # IF APPROVED: Clean up external dependencies
    message_id = None
    if decision == 'APPROVE':
        # 1. Google Calendar Removal
        google_event_id = item.get('google_event_id')
        if google_event_id:
            try:
                if not delete_event(google_event_id, request_id):
                    raise Exception("delete_event returned False")
            except Exception as ex:
                fail_msg = f"GCal cleanup failed: {str(ex)}"
                print(fail_msg)
                record_sync_failure(request_id, client_id, "GOOGLE_CALENDAR", fail_msg)

        # 2. Worker Notification (SNS)
        worker_id = item.get('worker_id')
        if worker_id:
            try:
                message_id = notify_worker(worker_id, item)
            except Exception as ex:
                fail_msg = f"SNS notification failed: {str(ex)}"
                print(fail_msg)
                record_sync_failure(request_id, client_id, "SNS_NOTIFICATION", fail_msg)

    msg_action = f"{decision.lower()}ed" if decision != 'DENY' else "denied"
    return success({
        "message": f"Cancellation request {msg_action}.",
        "new_status": new_status,
        "sns_message_id": message_id
    }, event)

def notify_worker(worker_id, item):
    """Sends SMS notification via AWS SNS."""
    topic_arn = os.environ.get('STAFF_COORDINATION_SNS_ARN')
    if not topic_arn:
        raise Exception("STAFF_COORDINATION_SNS_ARN environment variable not set")

    message = (
        f"Togs & Dogs ALERT: Visit for {item.get('client_name')} on {item.get('start_date')} "
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
