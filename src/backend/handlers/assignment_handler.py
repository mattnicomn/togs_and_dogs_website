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
        worker_id = body.get('worker_id')

        if not (job_id and req_id and worker_id):
            return bad_request(f"Missing fields. Got: {list(body.keys())}", event)

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
                UpdateExpression="SET #stat = :s, worker_id = :w, assigned_at = :a, audit_log = list_append(if_not_exists(audit_log, :empty_list), :n)",
                ExpressionAttributeNames={"#stat": "status"},
                ExpressionAttributeValues={
                    ":s": new_status,
                    ":w": worker_id,
                    ":a": now,
                    ":n": [{
                        "action": "WORKER_ASSIGNED",
                        "worker_id": worker_id,
                        "timestamp": now
                    }],
                    ":empty_list": []
                }
            )

            # 2. Update REQ record (so it reflects in the admin list view)
            try:
                table.update_item(
                    Key={'PK': f"REQ#{req_id}", 'SK': f"CLIENT#{item.get('client_id')}"},
                    UpdateExpression="SET #stat = :s, worker_id = :w",
                    ExpressionAttributeNames={"#stat": "status"},
                    ExpressionAttributeValues={
                        ":s": new_status,
                        ":w": worker_id
                    }
                )
            except Exception as req_err:
                print(f"REQ_UPDATE_WARNING: {req_err}")

            # Sync to Google Calendar
            google_event_id = item.get('google_event_id')
            if google_event_id:
                try:
                    sync_calendar_event(item, google_event_id=google_event_id, assigned_worker=worker_id)
                except Exception as g_err:
                    print(f"CALENDAR_SYNC_WARNING: {g_err}")

            return success({
                "message": "Worker assigned successfully",
                "job_id": job_id,
                "worker_id": worker_id,
                "status": new_status
            }, event)
        except Exception as e:
            print(f"DB_UPDATE_ERROR: {e}")
            return internal_error(f"DB Update failed: {str(e)}", event)
            
    except Exception as e:
        print(f"UNHANDLED_ERROR: {e}")
        import traceback
        print(traceback.format_exc())
        return internal_error(str(e), event)
