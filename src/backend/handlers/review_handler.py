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
        # Extract user context
        authorizer = event.get('requestContext', {}).get('authorizer', {})
        claims = authorizer.get('claims', {})
        user_email = (claims.get('email') or "").lower().strip()
        groups = claims.get('cognito:groups', [])
        is_admin = 'Staff' in groups or 'Admin' in groups or user_email in ['mattnicomn10@gmail.com', 'support@toganddogs.usmissionhero.com']
        
        if not is_admin:
            return bad_request("Administrative access required.", event)

        updated_by = user_email or claims.get('username') or 'admin-api'

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
                    now = datetime.now(timezone.utc).isoformat()
                    audit_note = {
                        "action": "STATUS_CHANGE",
                        "from": "MEET_GREET_REQUIRED",
                        "to": "READY_FOR_APPROVAL",
                        "timestamp": now,
                        "reason": "M&G Verified",
                        "metadata": {"request_id": request_id, "client_id": client_id}
                    }
                    table.update_item(
                        Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                        UpdateExpression="SET #stat = :s, updated_at = :now, audit_log = list_append(if_not_exists(audit_log, :empty_list), :n)",
                        ExpressionAttributeNames={"#stat": "status"},
                        ExpressionAttributeValues={
                            ":s": "READY_FOR_APPROVAL",
                            ":now": now,
                            ":n": [audit_note],
                            ":empty_list": []
                        }
                    )

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
            print(f"ERROR: Request {request_id} (Client {client_id}) not found.")
            return not_found(f"Request {request_id} not found", event)
 
        current_status = request_item.get('status')
        print(f"INFO: [Req:{request_id}] Transition attempt: {current_status} -> {new_status}")
        
        # 2. Validate transition
        if not is_valid_transition('REQUEST', current_status, new_status):
            print(f"REJECTED: Invalid transition from {current_status} to {new_status}")
            return bad_request(f"Invalid transition from {current_status} to {new_status}", event)
 
        # 3. Enforce validation rules for specific statuses
        if new_status in ['APPROVED', 'BOOKED']:
            # Check Client metadata for Meet-and-Greet
            client_metadata = get_item(f"CLIENT#{client_id}", "METADATA")
            mg_required = client_metadata.get('meet_and_greet_required', True) # Default to true for safety
            mg_completed = client_metadata.get('meet_and_greet_completed', False)
            
            if mg_required and not mg_completed:
                return bad_request(
                    "Meet & Greet must be marked completed before this request can move forward to Approved.", 
                    event
                )
            
            # Check Quote requirements
            quote_required = request_item.get('quote_required', False)
            payment_status = request_item.get('payment_status', 'Not Quoted')
            
            if quote_required and payment_status not in ['Accepted', 'Deposit Paid', 'Paid in Full']:
                return bad_request(
                    "Quote must be accepted and payment status updated before this request can move forward to Approved.",
                    event
                )

        if new_status == 'ASSIGNED':
            # Ensure a worker is assigned
            has_worker = request_item.get('worker_id') or body.get('worker_id')
            if not has_worker:
                return bad_request(
                    "Cannot move to Assigned status without a selected team member.",
                    event
                )

        # 4. Perform update
        now = datetime.now(timezone.utc).isoformat()
        audit_note = {
            "action": "STATUS_CHANGE",
            "from": current_status,
            "to": new_status,
            "timestamp": now,
            "reason": body.get('reason', 'Admin review'),
            "updated_by": updated_by,
            "metadata": {
                "request_id": request_id,
                "client_id": client_id
            }
        }
        
        # Prepare Update Expression
        update_expr = "SET #stat = :s, updated_at = :now, updated_by = :ub, audit_log = list_append(if_not_exists(audit_log, :empty_list), :n)"
        expr_attr_names = {"#stat": "status"}
        expr_attr_vals = {
            ":s": new_status,
            ":now": now,
            ":ub": updated_by,
            ":n": [audit_note],
            ":empty_list": []
        }

        # SPECIAL CASE: Rollback ASSIGNED -> APPROVED clears worker_id
        if current_status == 'ASSIGNED' and new_status == 'APPROVED':
            update_expr += " REMOVE worker_id"
        
        # SPECIAL CASE: Transition to ASSIGNED from body worker_id
        if new_status == 'ASSIGNED' and body.get('worker_id'):
            update_expr += ", worker_id = :w"
            expr_attr_vals[":w"] = body.get('worker_id')

        try:
            table.update_item(
                Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                UpdateExpression=update_expr,
                ExpressionAttributeNames=expr_attr_names,
                ExpressionAttributeValues=expr_attr_vals
            )
            
            # Also update the Job record if it exists
            job_id = request_item.get('job_id')
            if job_id:
                try:
                    # Map Request status to Job equivalent
                    job_status = new_status
                    if new_status == 'APPROVED':
                        job_status = 'JOB_CREATED'
                        
                    job_update_expr = "SET #stat = :s, updated_at = :now, updated_by = :ub"
                    job_attr_vals = {":s": job_status, ":now": now, ":ub": updated_by}
                    
                    if current_status == 'ASSIGNED' and job_status == 'JOB_CREATED':
                         job_update_expr += " REMOVE worker_id"
                    
                    table.update_item(
                        Key={'PK': f"JOB#{job_id}", 'SK': f"REQ#{request_id}"},
                        UpdateExpression=job_update_expr,
                        ExpressionAttributeNames={"#stat": "status"},
                        ExpressionAttributeValues=job_attr_vals
                    )
                except Exception as job_err:
                    print(f"WARNING: [Req:{request_id}] Failed to update linked job: {job_err}")

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
                            subject = "Your Tog and Dogs Booking Request: APPROVED!"
                            html = get_approval_email_body(client_name, start_date, custom_message)
                        else:
                            subject = "Update regarding your Tog and Dogs request"
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

        except Exception as db_err:
            print(f"ERROR: [Req:{request_id}] DB update failed: {db_err}")
            return internal_error("Failed to update status in database", event)
            
    except Exception as e:
        print(f"Unhandled error: {e}")
        return internal_error(str(e), event)
