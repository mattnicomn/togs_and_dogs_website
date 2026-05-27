import json
import os
import boto3
from datetime import datetime, timezone
from common.db import get_item, update_status, table
from common.response import success, bad_request, internal_error, not_found
from common.status import RequestStatus, WorkflowType, is_valid_transition, determine_workflow_type
from common.google_calendar import sync_calendar_event, delete_event
from common.email import send_transactional_email, get_approval_email_body, get_rejection_email_body
from common.audit import log_action
from common.notifications.service import notify_event

def handle_notifications(workflow_type, current_status, new_status, request_item, body):
    """
    Modular, fail-safe notification dispatcher.
    Returns: { "success": bool, "message": str }
    """
    result = {"success": True, "message": "No notification needed."}
    
    # 1. Customer Intake Notifications
    if workflow_type == WorkflowType.CUSTOMER_INTAKE:
        if new_status == 'APPROVED':
            result = notify_event('CUSTOMER_APPROVED', request_item)
        elif new_status == 'MG_SCHEDULED':
            # Placeholder for future M&G specific template
            pass
        elif new_status == 'DECLINED':
            # Placeholder for modular REJECTION
            pass
            
    # 2. Visit Booking Notifications
    elif workflow_type == WorkflowType.VISIT_BOOKING:
        if new_status == 'APPROVED':
            result = notify_event('CUSTOMER_APPROVED', request_item)
        elif new_status == 'ASSIGNED':
            notify_event('STAFF_ASSIGNED', request_item)
            notify_event('VISIT_SCHEDULED', request_item)
        elif new_status == 'CANCELLED':
            notify_event('VISIT_CANCELLED', request_item)

    return result

def handler(event, context):
    try:
        # Extract user context
        from common.auth import get_effective_role, get_claims
        from common.response import error
        role = get_effective_role(event)
        if role not in ['owner', 'admin', 'staff']:
            return error(403, "Forbidden", event)
            
        claims = get_claims(event)
        user_email = (claims.get('email') or "").lower().strip()



        updated_by = user_email or claims.get('username') or 'admin-api'

        body = json.loads(event.get('body', '{}'))
        request_id = body.get('request_id')
        client_id = body.get('client_id')
        new_status = body.get('status')
        
        # request_id is optional for client-level verification
        if not (client_id and new_status) or (new_status != 'VERIFY_MEET_GREET' and not request_id):
            return bad_request("Missing required fields: client_id, status (and request_id for status transitions)", event)

        request_item = {}
        if request_id:
            request_item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}") or {}

        if new_status in ['APPROVED', 'BOOKED', 'DECLINED', 'CANCELLED', 'ARCHIVED', 'DELETED'] and role not in ['owner', 'admin']:
            return error(403, "Forbidden: Only owners and admins can perform sensitive transitions", event)

        # 4. Handle VERIFY_MEET_GREET pseudo-status (updates Client Metadata)
        if new_status == 'VERIFY_MEET_GREET':
            try:
                from common.auth import get_current_company_id
                company_id = get_current_company_id(event)

                table.update_item(
                    Key={'PK': f"CLIENT#{client_id}", 'SK': "METADATA"},
                    UpdateExpression="SET meet_and_greet_completed = :t, entity_type = :et, company_id = :cid",
                    ExpressionAttributeValues={":t": True, ":et": "CLIENT", ":cid": company_id}
                )

                pet_id = request_item.get('pet_id')
                if pet_id:
                    table.update_item(
                        Key={'PK': f"PET#{pet_id}", 'SK': f"CLIENT#{client_id}"},
                        UpdateExpression="SET meet_and_greet_completed = :t",
                        ExpressionAttributeValues={":t": True}
                    )

                print(f"INFO: [Client:{client_id}] Meet & Greet manually verified by admin.")
                
                if request_id:
                    now = datetime.now(timezone.utc).isoformat()
                    audit_note = {
                        "action": "STATUS_CHANGE",
                        "from": request_item.get('status', 'MEET_GREET_REQUIRED'),
                        "to": "MG_COMPLETED",
                        "timestamp": now,
                        "reason": "M&G Verified",
                        "metadata": {"request_id": request_id, "client_id": client_id}
                    }
                    table.update_item(
                        Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                        UpdateExpression="SET #stat = :s, updated_at = :now, audit_log = list_append(if_not_exists(audit_log, :empty_list), :n)",
                        ExpressionAttributeNames={"#stat": "status"},
                        ExpressionAttributeValues={
                            ":s": "MG_COMPLETED",
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
 
        current_status = request_item.get('status') or 'PENDING_REVIEW'
        workflow_type = determine_workflow_type(request_item)
        print(f"INFO: [Req:{request_id}] Workflow: {workflow_type.value}, Transition: {current_status} -> {new_status}")
        
        # 2. Validate transition
        if not is_valid_transition('REQUEST', current_status, new_status):
            print(f"REJECTED: Invalid transition from {current_status} to {new_status}")
            return bad_request(f"Invalid transition from {current_status} to {new_status}", event)
 
        # 3. Enforce validation rules for specific statuses
        if current_status != new_status:
            if new_status in ['APPROVED', 'BOOKED']:
                pet_id = request_item.get('pet_id')
                pet_metadata = {}
                if pet_id:
                    pet_metadata = get_item(f"PET#{pet_id}", f"CLIENT#{client_id}") or {}
                
                # Check M&G requirements
                if current_status not in ['QUOTED', 'QUOTE_SENT', 'MG_COMPLETED', 'QUOTE_NEEDED']:
                    mg_required = pet_metadata.get('meet_and_greet_required')
                    if mg_required is None:
                        mg_required = True # Default to true for safety
                        
                    mg_completed = pet_metadata.get('meet_and_greet_completed', False)
                    
                    if mg_required and not mg_completed:
                        return bad_request(
                            "Meet & Greet must be marked completed before this request can move forward to Approved.", 
                            event
                        )
                
                # Check Quote requirements
                quote_amount = float(pet_metadata.get('quote_amount', 0))
                payment_status = pet_metadata.get('payment_status', 'Not Quoted')
                
                if quote_amount > 0 and payment_status not in ['Accepted', 'Deposit Paid', 'Paid in Full']:
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
            
            # Audit log
            log_action(
                event, 
                f"REVIEW_{new_status}", 
                f"REQ#{request_id}", 
                f"CLIENT#{client_id}", 
                previous_status=current_status, 
                new_status=new_status,
                metadata={"client_name": request_item.get('client_name'), "pet_names": request_item.get('pet_names'), "workflow_type": workflow_type.value}
            )
            
            # 4b. Trigger modular notifications
            notif_result = handle_notifications(workflow_type, current_status, new_status, request_item, body)
            
            # Release 1: Cascade REQ → JOB status change via shared utility.
            # This replaces the previous inline JOB update and ensures ALL transitions
            # cascade consistently (including CANCELLED, ARCHIVED, DELETED, rollback).
            # Cascade is one-directional (REQ → JOB only) to prevent loops.
            from common.cascade import cascade_status_to_job
            remove_worker_on_cascade = (current_status == 'ASSIGNED' and new_status == 'APPROVED')
            cascade_status_to_job(
                request_item,
                new_status,
                updated_by=updated_by,
                remove_worker=remove_worker_on_cascade
            )

            # 5. Trigger Job Creation Lambda if APPROVED
            # --- GOOGLE CALENDAR SYNC LOGIC ---
            calendar_result = None
            
            # Merge body updates into request_item for sync logic (e.g. worker_id, schedule changes)
            sync_data = {**request_item, **body}
            
            if new_status in ['APPROVED', 'ASSIGNED', 'BOOKED', 'SCHEDULED']:
                try:
                    existing_event_id = request_item.get('google_event_id')
                    assigned_worker = sync_data.get('worker_id')
                    
                    is_multi_day_req = False
                    if request_item.get('end_date') and request_item.get('start_date') != request_item.get('end_date'):
                        is_multi_day_req = True
                    if request_item.get('job_ids'):
                        is_multi_day_req = True
                        
                    if not is_multi_day_req:
                        print(f"INFO: [Req:{request_id}] Attempting Google Calendar sync (Status: {new_status})")
                        calendar_result = sync_calendar_event(sync_data, google_event_id=existing_event_id, assigned_worker=assigned_worker)
                        
                        if calendar_result.get('event_id') and calendar_result.get('event_id') != existing_event_id:
                            # Persist the event ID back to the Request record
                            table.update_item(
                                Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                                UpdateExpression="SET google_event_id = :gid",
                                ExpressionAttributeValues={":gid": calendar_result['event_id']}
                            )
                            print(f"INFO: [Req:{request_id}] Persisted new google_event_id: {calendar_result['event_id']}")
                        
                        # Update Job record if it exists
                        job_id = request_item.get('job_id')
                        if job_id and calendar_result.get('event_id'):
                            table.update_item(
                                Key={'PK': f"JOB#{job_id}", 'SK': f"REQ#{request_id}"},
                                UpdateExpression="SET google_event_id = :gid",
                                ExpressionAttributeValues={":gid": calendar_result['event_id']}
                            )
                    else:
                        print(f"INFO: [Req:{request_id}] Suppressing parent REQ Google Calendar sync for multi-day request.")
                        calendar_result = {"status": "skipped", "message": "Multi-day jobs sync their own calendar events."}
                except Exception as sync_err:
                    print(f"WARNING: [Req:{request_id}] Google Calendar sync failed: {sync_err}")
                    calendar_result = {"status": "calendar_failed", "message": str(sync_err)}

            elif new_status in ['CANCELLED', 'ARCHIVED', 'DELETED']:
                is_multi_day_req = False
                if request_item.get('end_date') and request_item.get('start_date') != request_item.get('end_date'):
                    is_multi_day_req = True
                if request_item.get('job_ids'):
                    is_multi_day_req = True

                if not is_multi_day_req:
                    existing_event_id = request_item.get('google_event_id')
                    if existing_event_id:
                        try:
                            success_delete = delete_event(existing_event_id, request_id)
                            if success_delete:
                                calendar_result = {"status": "calendar_deleted", "message": "Calendar event deleted."}
                                table.update_item(
                                    Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                                    UpdateExpression="REMOVE google_event_id"
                                )
                            else:
                                calendar_result = {"status": "calendar_failed", "message": "Failed to delete calendar event."}
                        except Exception as del_err:
                            print(f"WARNING: [Req:{request_id}] Calendar delete failed: {del_err}")
                            calendar_result = {"status": "calendar_failed", "message": str(del_err)}
                else:
                    if request_item.get('job_ids'):
                        from common.db import get_item
                        deleted_count = 0
                        for jid in request_item.get('job_ids'):
                            job_item = get_item(f"JOB#{jid}", f"REQ#{request_id}")
                            if job_item and job_item.get('google_event_id'):
                                try:
                                    delete_event(job_item['google_event_id'], request_id)
                                    table.update_item(
                                        Key={'PK': f"JOB#{jid}", 'SK': f"REQ#{request_id}"},
                                        UpdateExpression="REMOVE google_event_id"
                                    )
                                    deleted_count += 1
                                except Exception as del_err:
                                    print(f"WARNING: [Job:{jid}] Calendar delete failed: {del_err}")
                        calendar_result = {"status": "calendar_deleted", "message": f"Deleted {deleted_count} child calendar events."}

            # --- JOB CREATION LAMBDA TRIGGER ---
            if new_status == 'APPROVED':
                try:
                    lambda_client = boto3.client('lambda')
                    job_fn_name = os.environ.get('JOB_FUNCTION_NAME')
                    if job_fn_name:
                        payload = {
                            "request_id": request_id,
                            "client_id": client_id,
                            "google_event_id": calendar_result.get('event_id') if calendar_result else request_item.get('google_event_id')
                        }
                        lambda_client.invoke(
                            FunctionName=job_fn_name,
                            InvocationType='Event', # Async
                            Payload=json.dumps(payload)
                        )
                        print(f"INFO: [Req:{request_id}] Triggered Job creation (Lambda: {job_fn_name})")
                except Exception as invoke_err:
                    print(f"ERROR: [Req:{request_id}] Failed to trigger job creation: {invoke_err}")

            # --- Release 3: CLIENT PROFILE AUTO-CREATION ---
            # When a CUSTOMER_INTAKE request is approved, auto-create or link a Client Management profile.
            # This is fail-safe: if it fails, approval still succeeds.
            # Only runs for CUSTOMER_INTAKE workflow (not VISIT_BOOKING — those clients already have profiles).
            # Idempotency: Skip if request already has a linked_client_profile_id (prevents duplicate
            # processing on Restore to Approved or re-approval scenarios).
            if new_status == 'APPROVED' and workflow_type == WorkflowType.CUSTOMER_INTAKE:
                already_linked = request_item.get('linked_client_profile_id')
                if already_linked:
                    print(f"INFO: [Req:{request_id}] Auto-profile skipped — already linked to {already_linked}")
                    profile_result = {"link_status": "ALREADY_LINKED", "message": "Already linked to client profile."}
                else:
                    try:
                        from common.client_profile import auto_create_or_link_client_profile
                        from common.auth import get_current_company_id
                        profile_company_id = request_item.get('company_id') or get_current_company_id(event)
                        profile_result = auto_create_or_link_client_profile(
                            request_item=request_item,
                            request_id=request_id,
                            client_id=client_id,
                            company_id=profile_company_id,
                            updated_by=updated_by
                        )
                    except Exception as profile_err:
                        # FAIL-SAFE: Log but do not block approval
                        print(f"WARNING: [Req:{request_id}] Client profile automation failed: {profile_err}")
                        try:
                            table.update_item(
                                Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                                UpdateExpression="SET client_profile_link_status = :s",
                                ExpressionAttributeValues={":s": "FAILED"}
                            )
                        except:
                            pass  # Even this failure shouldn't block
                        profile_result = {"link_status": "FAILED", "message": str(profile_err)}

            # Prepare final message
            final_msg = f"Request {new_status}."
            if calendar_result and calendar_result.get('message'):
                final_msg += f" {calendar_result['message']}"
            
            if notif_result and notif_result.get('message'):
                # Append notification status if it's informative
                if "logged" in notif_result['message'].lower() or "sent" in notif_result['message'].lower():
                    final_msg += f" ({notif_result['message']})"
            
            # Release 3: Include client profile automation result in response
            if new_status == 'APPROVED' and workflow_type == WorkflowType.CUSTOMER_INTAKE:
                try:
                    if profile_result and profile_result.get('message'):
                        final_msg += f" Client profile: {profile_result['message']}"
                except NameError:
                    pass  # profile_result not defined if workflow wasn't CUSTOMER_INTAKE

            return success({
                "message": final_msg,
                "request_id": request_id,
                "status": new_status,
                "calendar_result": calendar_result,
                "notification_result": notif_result
            }, event)

        except Exception as db_err:
            print(f"ERROR: [Req:{request_id}] DB update failed: {db_err}")
            return internal_error("Failed to update status in database", event)
            
    except Exception as e:
        print(f"Unhandled error: {e}")
        return internal_error(str(e), event)
