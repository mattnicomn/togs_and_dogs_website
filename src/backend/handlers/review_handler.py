import json
import os
import boto3
from datetime import datetime, timezone
from common.db import get_item, update_status, table
from common.response import success, bad_request, internal_error, not_found
from common.status import RequestStatus, is_valid_transition
from common.google_calendar import sync_calendar_event
from common.email import send_transactional_email, get_approval_email_body, get_rejection_email_body

def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        request_id = body.get('request_id')
        client_id = body.get('client_id')
        new_status = body.get('status')
        
        # request_id is optional for client-level verification
        if not (client_id and new_status) or (new_status != 'VERIFY_MEET_GREET' and not request_id):
            return bad_request("Missing required fields: client_id, status (and request_id for status transitions)", event)

        # 4. Handle VERIFY_MEET_GREET pseudo-status (updates Client Metadata)
        if new_status == 'VERIFY_MEET_GREET':
            try:
                table.update_item(
                    Key={'PK': f"CLIENT#{client_id}", 'SK': "METADATA"},
                    UpdateExpression="SET meet_and_greet_completed = :t, entity_type = :et",
                    ExpressionAttributeValues={":t": True, ":et": "CLIENT"}
                )
                print(f"INFO: [Client:{client_id}] Meet & Greet manually verified by admin.")
                
                if request_id:
                    audit_note = {
                        "action": "STATUS_CHANGE",
                        "from": "MEET_GREET_REQUIRED",
                        "to": "READY_FOR_APPROVAL",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "reason": "M&G Verified",
                        "metadata": {"request_id": request_id, "client_id": client_id}
                    }
                    update_status(f"REQ#{request_id}", f"CLIENT#{client_id}", "READY_FOR_APPROVAL", audit_note)

                return success({
                    "message": "Meet & Greet status updated successfully",
                    "client_id": client_id,
                    "meet_and_greet_completed": True
                }, event)
            except Exception as db_err:
                print(f"ERROR: [Client:{client_id}] Failed to update M&G status: {db_err}")
                return internal_error("Failed to update client metadata", event)
 
        # 1. Get current Request state
        request_item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
        if not request_item:
            return not_found(f"Request {request_id} not found", event)
 
        current_status = request_item.get('status')
        
        # 2. Validate transition
        if not is_valid_transition('REQUEST', current_status, new_status):
            return bad_request(f"Invalid transition from {current_status} to {new_status}", event)
 
        # 3. Enforce Meet-and-Greet gate for APPROVED status
        if new_status == 'APPROVED':
            # Check Client metadata
            client_metadata = get_item(f"CLIENT#{client_id}", "METADATA")
            
            # If client record doesn't exist yet or isn't marked as completed
            is_verified = client_metadata and client_metadata.get('meet_and_greet_completed')
            
            if not is_verified:
                # Decision: Prevent approval if no meet-and-greet is on file
                # Suggest move to MEET_GREET_REQUIRED instead
                return bad_request(
                    "Cannot approve first-time request: Meet-and-Greet required.", 
                    event
                )

        # 4. Perform update
        audit_note = {
            "action": "STATUS_CHANGE",
            "from": current_status,
            "to": new_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": body.get('reason', 'Admin review'),
            "metadata": {
                "request_id": request_id,
                "client_id": client_id
            }
        }
        

        if update_status(f"REQ#{request_id}", f"CLIENT#{client_id}", new_status, audit_note):
            
            # 5. If APPROVED, sync to Google Calendar AND trigger Job creation
            google_event_id = None
            if new_status == 'APPROVED':
                # Use existing event ID if this is a retry
                existing_event_id = request_item.get('google_event_id')
                google_event_id = sync_calendar_event(request_item, google_event_id=existing_event_id)
                
                if google_event_id and google_event_id != existing_event_id:
                    # Persist the new event ID back to DB
                    try:
                        table.update_item(
                            Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                            UpdateExpression="SET google_event_id = :gid",
                            ExpressionAttributeValues={":gid": google_event_id}
                        )
                    except Exception as db_err:
                        print(f"WARNING: [Req:{request_id}] Failed to save google_event_id to DB: {db_err}")

                # 6. Trigger Job Creation Lambda
                try:
                    lambda_client = boto3.client('lambda')
                    job_fn_name = os.environ.get('JOB_FUNCTION_NAME')
                    if job_fn_name:
                        payload = {
                            "request_id": request_id,
                            "client_id": client_id
                        }
                        lambda_client.invoke(
                            FunctionName=job_fn_name,
                            InvocationType='Event', # Async
                            Payload=json.dumps(payload)
                        )
                        print(f"INFO: [Req:{request_id}] Triggered Job creation (Lambda: {job_fn_name})")
                except Exception as invoke_err:
                    print(f"ERROR: [Req:{request_id}] Failed to trigger job creation: {invoke_err}")

            # 7. Send Customer Email (APPROVAL or REJECTION)
            if new_status in ['APPROVED', 'DECLINED']:
                client_name = request_item.get('client_name', 'Client')
                client_email = request_item.get('client_email')
                start_date = request_item.get('start_date', 'your requested date')
                custom_message = body.get('reason', '') # Use the same 'reason' field for the email body

                if client_email:
                    try:
                        if new_status == 'APPROVED':
                            subject = "Your Togs & Dogs Booking Request: APPROVED!"
                            html = get_approval_email_body(client_name, start_date, custom_message)
                        else:
                            subject = "Update regarding your Togs & Dogs request"
                            html = get_rejection_email_body(client_name, start_date, custom_message)
                        
                        send_transactional_email(client_email, subject, html)
                    except Exception as email_err:
                        # FAIL GRACEFULLY: Log but don't block the response
                        print(f"WARNING: [Req:{request_id}] Email notification failed: {email_err}")
                else:
                    print(f"INFO: [Req:{request_id}] No client email on file. Skipping notification.")

            return success({
                "message": f"Request {new_status}",
                "request_id": request_id,
                "status": new_status,
                "google_event_id": google_event_id
            }, event)
        else:
            return internal_error("Failed to update status in database", event)
            
    except Exception as e:
        print(f"Unhandled error: {e}")
        return internal_error(str(e), event)
