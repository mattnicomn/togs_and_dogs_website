import json

def handler(event, context):
    print("HANDLER_STARTED")
    from common.entitlement import require_active_tenant
    block_resp = require_active_tenant(event)
    if block_resp:
        return block_resp

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

        # Release 8U: Validate worker_id against a real active/assignable staff profile.
        # This prevents typo emails or phantom profiles from being persisted as worker_id.
        try:
            import re as _re
            _VALID_EMAIL_RE = _re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
            if not _VALID_EMAIL_RE.match((worker_id or '').strip()):
                print(f"ERROR: worker_id '{worker_id}' is not a valid email format.")
                return bad_request(f"Invalid worker_id format: '{worker_id}'. Must be a valid email address.", event)

            from common.auth import get_current_company_id
            _company_id = get_current_company_id(event)
            from boto3.dynamodb.conditions import Key as _Key
            _staff_resp = table.query(
                KeyConditionExpression=_Key('PK').eq(f"COMPANY#{_company_id}") & _Key('SK').begins_with("STAFF#")
            )
            _staff_items = _staff_resp.get('Items', [])
            _worker_email = worker_id.lower().strip()
            _eligible = any(
                (s.get('email') or '').lower().strip() == _worker_email
                and s.get('is_active') is not False
                and s.get('is_assignable') is not False
                and s.get('cognito_sub')
                and s.get('cognito_sub') != 'unlinked'
                for s in _staff_items
            )
            if not _eligible:
                print(f"ERROR: worker_id '{worker_id}' does not match any eligible assignable staff profile.")
                return bad_request(
                    f"No eligible assignable staff profile found for worker_id: '{worker_id}'. "
                    "Ensure the staff profile exists, is active, is assignable, and has a linked Cognito account.",
                    event
                )
        except Exception as _val_err:
            print(f"WARNING: worker_id validation query failed: {_val_err}. Proceeding with assignment.")
            # Non-fatal: if the validation query itself fails (e.g., DynamoDB unavailable),
            # we log a warning and allow the assignment to proceed rather than blocking it.

        # ROBUSTNESS: Handle case where UI sends REQ ID as JOB ID before sync

        target_job_ids = []
        request_rec = get_item(f"REQ#{req_id}", f"CLIENT#{client_id}")

        # Release 11E: Post-read tenant ownership validation
        if request_rec:
            from common.auth import validate_tenant_ownership as _vto, get_claims as _gc
            try:
                _vto(request_rec, event)
            except PermissionError:
                _c = _gc(event)
                print(f"SECURITY: Cross-tenant assign attempt by {_c.get('email')} for REQ#{req_id}")
                from common.response import error as _error
                return _error(403, "Forbidden", event)
        
        if request_rec:
            parent_job_ids = request_rec.get('job_ids') or []
            primary_job_id = request_rec.get('job_id')
            is_multi_day = request_rec.get('is_multi_day')
            
            # Cascade to all jobs if it is a multi-day booking and we target the parent request or the booking's primary job ID
            if is_multi_day and (job_id == req_id or job_id.startswith('REQ#') or job_id == primary_job_id):
                target_job_ids = parent_job_ids
                print(f"INFO: Resolved {len(target_job_ids)} Job IDs for multi-day booking assignment cascade")
            elif job_id == req_id or job_id.startswith('REQ#'):
                target_job_ids = parent_job_ids if parent_job_ids else ([primary_job_id] if primary_job_id else [])
                print(f"INFO: Resolved parent request target to Job IDs: {target_job_ids}")
            else:
                target_job_ids = [job_id]
        else:
            if job_id == req_id or job_id.startswith('REQ#'):
                target_job_ids = []
            else:
                target_job_ids = [job_id]

        # Scan fallback for race conditions (if request didn't have jobs linked yet)
        if (job_id == req_id or job_id.startswith('REQ#')) and not target_job_ids:
            print("INFO: RACE_CONDITION_DETECTED - Request has no job_ids yet. Attempting table scan for orphaned JOB records.")
            from boto3.dynamodb.conditions import Attr
            response = table.scan(
                FilterExpression=Attr('SK').eq(f"REQ#{req_id}") & Attr('entity_type').eq('JOB')
            )
            items = response.get('Items', [])
            if items:
                target_job_ids = [item.get('PK').replace('JOB#', '') for item in items]
                print(f"WARNING: RESOLVED_CANONICAL_JOBS via scan: {target_job_ids}")

        if not target_job_ids:
            print(f"ERROR: Jobs for REQ#{req_id} not found")
            return not_found(f"Jobs for request {req_id} not found. Please wait a moment for the request to be approved and initialized.", event)

        new_status = JobStatus.ASSIGNED.value
        now = datetime.utcnow().isoformat()
        
        assigned_jobs = []
        calendar_results = []
        notified = False  # In-memory batch dedup guard
        
        try:
            for j_id in target_job_ids:
                item = get_item(f"JOB#{j_id}", f"REQ#{req_id}")
                if not item:
                    print(f"WARNING: Job JOB#{j_id} not found, skipping.")
                    continue

                # Release 11E: Post-read tenant ownership validation on each JOB record
                from common.auth import validate_tenant_ownership as _vto_j
                try:
                    _vto_j(item, event)
                except PermissionError:
                    print(f"SECURITY: Cross-tenant JOB access blocked for JOB#{j_id}")
                    continue  # Skip this job rather than blocking the entire batch

                current_status = item.get('status')
                
                # Validate transition
                if not is_valid_transition('JOB', current_status, new_status):
                    print(f"WARNING: Invalid transition for {j_id}: {current_status} -> {new_status}, skipping.")
                    continue

                # 1. Update JOB record
                table.update_item(
                    Key={'PK': f"JOB#{j_id}", 'SK': f"REQ#{req_id}"},
                    UpdateExpression="SET #stat = :s, worker_id = :w, worker_name = :wn, assigned_at = :a, updated_at = :now, updated_by = :ub, audit_log = list_append(if_not_exists(audit_log, :empty_list), :n)",
                    ExpressionAttributeNames={"#stat": "status"},
                    ExpressionAttributeValues={
                        ":s": new_status,
                        ":w": worker_id,
                        ":wn": worker_name,
                        ":a": now,
                        ":now": now,
                        ":ub": updated_by,
                        ":n": [{
                            "action": "WORKER_ASSIGNED",
                            "worker_id": worker_id,
                            "worker_name": worker_name,
                            "timestamp": now,
                            "updated_by": updated_by
                        }],
                        ":empty_list": []
                    }
                )
                assigned_jobs.append(j_id)

                # Merge body updates into item for sync logic (e.g. worker_id, schedule changes)
                sync_data = {**item, **body}

                # Sync to Google Calendar
                google_event_id = item.get('google_event_id')
                
                # Fallback: Check the Request record if it's missing from the Job record
                if not google_event_id and request_rec:
                    google_event_id = request_rec.get('google_event_id')
                
                cal_res = None
                try:
                    cal_res = sync_calendar_event(sync_data, google_event_id=google_event_id, assigned_worker=worker_name)
                    if cal_res.get('event_id') and cal_res.get('event_id') != google_event_id:
                        # Persist the new event ID back to DB
                        try:
                            # Update Job record
                            table.update_item(
                                Key={'PK': f"JOB#{j_id}", 'SK': f"REQ#{req_id}"},
                                UpdateExpression="SET google_event_id = :gid",
                                ExpressionAttributeValues={":gid": cal_res['event_id']}
                            )
                        except Exception as db_err:
                            print(f"WARNING: Failed to save google_event_id to Job DB: {db_err}")
                except Exception as g_err:
                    print(f"CALENDAR_SYNC_WARNING: {g_err}")
                    cal_res = {"status": "calendar_failed", "message": str(g_err)}
                
                if cal_res:
                    calendar_results.append(cal_res)

                # Trigger modular notifications
                # ROBUSTNESS: Ensure notify_event has access to the newly assigned worker_id
                # Only notify once per batch assignment (in-memory dedup)
                if not notified:
                    item['worker_id'] = worker_id
                    item['worker_name'] = body.get('worker_name')
                    notify_event('STAFF_ASSIGNED', item)
                    notify_event('VISIT_SCHEDULED', item)
                    notified = True

            if not assigned_jobs:
                return bad_request("No valid jobs could be assigned. Check statuses.", event)

            # 2. Update REQ record (so it reflects in the admin list view)
            try:
                table.update_item(
                    Key={'PK': f"REQ#{req_id}", 'SK': f"CLIENT#{client_id}"},
                    UpdateExpression="SET #stat = :s, worker_id = :w, worker_name = :wn, updated_at = :now, updated_by = :ub",
                    ExpressionAttributeNames={"#stat": "status"},
                    ExpressionAttributeValues={
                        ":s": new_status,
                        ":w": worker_id,
                        ":wn": worker_name,
                        ":now": now,
                        ":ub": updated_by
                    }
                )
            except Exception as req_err:
                print(f"REQ_UPDATE_WARNING: {req_err}")

            final_msg = f"Worker assigned to {len(assigned_jobs)} job(s) successfully."
            
            # Use the first job ID for backward compatibility with older UI
            response_body = {
                "message": final_msg,
                "job_id": assigned_jobs[0] if assigned_jobs else job_id,
                "job_ids": assigned_jobs,
                "worker_id": worker_id,
                "status": new_status,
                "calendar_results": calendar_results
            }

            return success(response_body, event)
        except Exception as e:
            print(f"DB_UPDATE_ERROR: {e}")
            return internal_error(f"DB Update failed: {str(e)}", event)
            
    except Exception as e:
        print(f"UNHANDLED_ERROR: {e}")
        import traceback
        print(traceback.format_exc())
        return internal_error(str(e), event)
