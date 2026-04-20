import json
from datetime import datetime
from common.db import get_item, update_status, table
from common.response import success, bad_request, internal_error, not_found
from common.status import JobStatus, is_valid_transition
from common.google_calendar import sync_calendar_event

def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        job_id = body.get('job_id')
        req_id = body.get('req_id')
        worker_id = body.get('worker_id')

        if not (job_id and req_id and worker_id):
            return bad_request("Missing required fields: job_id, req_id, worker_id", event)
 
        # Get current state
        item = get_item(f"JOB#{job_id}", f"REQ#{req_id}")
        if not item:
            return not_found(f"Job {job_id} not found", event)
 
        current_status = item.get('status')
        new_status = JobStatus.JOB_ASSIGNED.value
        
        # Validate transition
        if not is_valid_transition('JOB', current_status, new_status):
            return bad_request(f"Invalid transition from {current_status} to {new_status}", event)
 
        # Perform update
        try:
            # 1. Update DB with worker assignment
            table.update_item(
                Key={'PK': f"JOB#{job_id}", 'SK': f"REQ#{req_id}"},
                UpdateExpression="SET #stat = :s, worker_id = :w, assigned_at = :a, audit_log = list_append(if_not_exists(audit_log, :empty_list), :n)",
                ExpressionAttributeNames={"#stat": "status"},
                ExpressionAttributeValues={
                    ":s": new_status,
                    ":w": worker_id,
                    ":a": datetime.utcnow().isoformat(),
                    ":n": [{
                        "action": "WORKER_ASSIGNED",
                        "worker_id": worker_id,
                        "timestamp": datetime.utcnow().isoformat()
                    }],
                    ":empty_list": []
                }
            )

            # 2. Sync to Google Calendar
            google_event_id = item.get('google_event_id')
            if google_event_id:
                sync_calendar_event(item, google_event_id=google_event_id, assigned_worker=worker_id)
            else:
                print(f"WARNING: [Job:{job_id}] No google_event_id found to update on assignment.")

            return success({
                "message": "Worker assigned successfully",
                "job_id": job_id,
                "worker_id": worker_id,
                "status": new_status
            }, event)
        except Exception as e:
            print(f"Error updating job assignment: {e}")
            return internal_error("Failed to assign worker in database", event)
            
    except Exception as e:
        print(f"Unhandled error: {e}")
        return internal_error(str(e), event)
