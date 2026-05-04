import json

def handler(event, context):
    print("HANDLER_STARTED")
    # Lazy imports to avoid initialization overhead/failures
    from datetime import datetime
    try:
        from common.db import get_item, table
        from common.response import success, bad_request, internal_error, not_found
        from common.status import JobStatus, is_valid_transition
        from common.google_calendar import sync_calendar_event
        from common.notifications.service import notify_event
    except ImportError as e:
        print(f"FATAL_IMPORT_ERROR: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Import failure: {str(e)}"})
        }

    try:
        body = json.loads(event.get('body', '{}'))
        print(f"DEBUG_PAYLOAD: {body}")
        
        job_id = body.get('job_id')
        req_id = body.get('req_id') or body.get('request_id')
        client_id = body.get('client_id')
        worker_id = body.get('worker_id')
        worker_name = body.get('worker_name') or worker_id

        from common.auth import get_effective_role, get_claims
        from common.response import error
        role = get_effective_role(event)
        if role not in ['owner', 'admin']:
            return error(403, "Forbidden: Only owners and admins can assign workers", event)
            
        claims = get_claims(event)
        user_email = (claims.get('email') or "").lower().strip()


        updated_by = user_email or claims.get('username') or 'admin-api'
        
        if not (job_id and req_id and client_id and worker_id):
            print(f"ERROR: Missing fields. job_id={job_id}, req_id={req_id}, client_id={client_id}, worker_id={worker_id}")
            from common.response import bad_request
            return bad_request(f"Missing fields. Required: [job_id, req_id, client_id, worker_id]", event)

        # Get current state
        # ROBUSTNESS: Handle case where UI sends REQ ID as JOB ID before sync
        actual_job_id = job_id
        if job_id == req_id or job_id.startswith('REQ#'):
            print(f"INFO: Attempting to resolve Job ID from Request REQ#{req_id}")
            request_rec = get_item(f"REQ#{req_id}", f"CLIENT#{body.get('client_id')}")
            if request_rec and request_rec.get('job_id'):
                actual_job_id = request_rec.get('job_id')
                print(f"INFO: Resolved Job ID: {actual_job_id}")

        item = get_item(f"JOB#{actual_job_id}", f"REQ#{req_id}")
        if not item:
            # Fallback: Maybe it's still a REQUEST and hasn't been turned into a JOB yet?
            # Or the job_id mapping is truly missing.
            print(f"ERROR: Job JOB#{actual_job_id} REQ#{req_id} not found")
            return not_found(f"Job {actual_job_id} not found. Please ensure request is approved.", event)

        job_id = actual_job_id # Ensure we use the resolved one for updates
        current_status = item.get('status')
        new_status = JobStatus.ASSIGNED.value
        
        # Validate transition
        if not is_valid_transition('JOB', current_status, new_status):
            return bad_request(f"Invalid transition: {current_status} -> {new_status}", event)

        # Update DB
        try:
            now = datetime.utcnow().isoformat()
            # 1. Update JOB record
            table.update_item(
                Key={'PK': f"JOB#{job_id}", 'SK': f"REQ#{req_id}"},
                UpdateExpression="SET #stat = :s, worker_id = :w, assigned_at = :a, updated_at = :now, updated_by = :ub, audit_log = list_append(if_not_exists(audit_log, :empty_list), :n)",
                ExpressionAttributeNames={"#stat": "status"},
                ExpressionAttributeValues={
                    ":s": new_status,
                    ":w": worker_id,
                    ":a": now,
                    ":now": now,
                    ":ub": updated_by,
                    ":n": [{
                        "action": "WORKER_ASSIGNED",
                        "worker_id": worker_id,
                        "timestamp": now,
                        "updated_by": updated_by
                    }],
                    ":empty_list": []
                }
            )

            # 2. Update REQ record (so it reflects in the admin list view)
            try:
                table.update_item(
                    Key={'PK': f"REQ#{req_id}", 'SK': f"CLIENT#{item.get('client_id')}"},
                    UpdateExpression="SET #stat = :s, worker_id = :w, updated_at = :now, updated_by = :ub",
                    ExpressionAttributeNames={"#stat": "status"},
                    ExpressionAttributeValues={
                        ":s": new_status,
                        ":w": worker_id,
                        ":now": now,
                        ":ub": updated_by
                    }
                )
            except Exception as req_err:
                print(f"REQ_UPDATE_WARNING: {req_err}")

            # Sync to Google Calendar
            google_event_id = item.get('google_event_id')
            
            # Fallback: Check the Request record if it's missing from the Job record (e.g. due to race condition during creation)
            if not google_event_id:
                print(f"INFO: [Req:{req_id}] google_event_id missing from Job record, checking Request record.")
                request_rec = get_item(f"REQ#{req_id}", f"CLIENT#{client_id}")
                if request_rec:
                    google_event_id = request_rec.get('google_event_id')
                    if google_event_id:
                        print(f"INFO: [Req:{req_id}] Found google_event_id in Request record: {google_event_id}")
            
            sync_warning = None
            try:
                new_event_id = sync_calendar_event(item, google_event_id=google_event_id, assigned_worker=worker_name)
                if new_event_id and new_event_id != google_event_id:
                    # Persist the new event ID back to DB
                    try:
                        # Update Request record
                        table.update_item(
                            Key={'PK': f"REQ#{req_id}", 'SK': f"CLIENT#{client_id}"},
                            UpdateExpression="SET google_event_id = :gid",
                            ExpressionAttributeValues={":gid": new_event_id}
                        )
                        # Update Job record if job_id exists
                        if job_id:
                            table.update_item(
                                Key={'PK': f"JOB#{job_id}", 'SK': f"REQ#{req_id}"},
                                UpdateExpression="SET google_event_id = :gid",
                                ExpressionAttributeValues={":gid": new_event_id}
                            )
                    except Exception as db_err:
                        print(f"WARNING: Failed to save google_event_id to DB: {db_err}")
            except Exception as g_err:
                print(f"CALENDAR_SYNC_WARNING: {g_err}")
                sync_warning = "Assigned successfully, but calendar sync is not connected."

            response_body = {
                "message": "Worker assigned successfully" if not sync_warning else sync_warning,
                "job_id": job_id,
                "worker_id": worker_id,
                "status": new_status
            }
            if sync_warning:
                response_body["warning"] = sync_warning

            # Trigger modular notifications
            # ROBUSTNESS: Ensure notify_event has access to the newly assigned worker_id
            item['worker_id'] = worker_id
            item['worker_name'] = body.get('worker_name')
            notify_event('STAFF_ASSIGNED', item)
            notify_event('VISIT_SCHEDULED', item)

            return success(response_body, event)
        except Exception as e:
            print(f"DB_UPDATE_ERROR: {e}")
            return internal_error(f"DB Update failed: {str(e)}", event)
            
    except Exception as e:
        print(f"UNHANDLED_ERROR: {e}")
        import traceback
        print(traceback.format_exc())
        return internal_error(str(e), event)
