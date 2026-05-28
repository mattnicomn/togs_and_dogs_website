import uuid
import time
from datetime import datetime, timezone, timedelta
import boto3
from common.db import put_item, get_item, table
from common.status import JobStatus

MAX_MULTI_DAY_OCCURRENCES = 14

def handler(event, context):
    """
    Intended to be triggered by Step Function or Review Handler.
    Creates a JOB record when a REQUEST is APPROVED.
    Ensures a PET entity exists and is linked.
    """
    try:
        # Extract metadata from event
        request_id = event.get('request_id')
        client_id = event.get('client_id')
        
        if not (request_id and client_id):
            print("Error: Missing request_id or client_id in event")
            return {"error": "Missing metadata"}

        # Fetch original request to get metadata
        request_item = get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")
        if not request_item:
            print(f"Error: Request REQ#{request_id} not found")
            return {"error": "Request not found"}

        # Idempotency Guard
        existing_job_id = request_item.get('job_id')
        existing_job_ids = request_item.get('job_ids')
        if existing_job_id or existing_job_ids:
            print(f"INFO: JOBs already exist for REQ#{request_id}. Skipping creation.")
            return {
                "job_id": existing_job_id,
                "job_ids": existing_job_ids,
                "pet_id": None,
                "status": "EXISTING_JOBS_SKIPPED",
                "message": "JOB records already exist for this request."
            }

        from common.auth import get_current_company_id
        company_id = request_item.get('company_id') or get_current_company_id(event if 'event' in locals() else {})

        # Release 4: Use multi-pet profile utility for PET# record creation.
        # This replaces the inline single-pet creation with a utility that:
        # - Supports multiple pets from the 'pets' array
        # - Falls back to legacy pet_names string for old requests
        # - Uses pet_ids array as idempotency guard
        # - Links PET# records to client profile ID when available
        # - Handles name matching and duplicate detection
        from common.pet_profile import create_or_link_pets_from_request
        pet_result = create_or_link_pets_from_request(
            request_item=request_item,
            request_id=request_id,
            client_id=client_id,
            company_id=company_id,
            updated_by='system_job_handler'
        )
        pet_ids = pet_result.get('pet_ids', [])
        pet_id = pet_ids[0] if pet_ids else None

        # Release 7E Phase 1: Multi-Day JOB Expansion
        start_date_str = request_item.get('start_date')
        end_date_str = request_item.get('end_date')

        job_dates = []
        selected_dates = request_item.get('selected_dates')

        if selected_dates and isinstance(selected_dates, list) and len(selected_dates) > 1:
            def _is_valid_date(date_str):
                if not isinstance(date_str, str): return False
                try:
                    datetime.strptime(date_str, '%Y-%m-%d')
                    return True
                except ValueError:
                    return False
            valid_dates = sorted(set(d for d in selected_dates if _is_valid_date(d)))
            if len(valid_dates) > MAX_MULTI_DAY_OCCURRENCES:
                return {"error": f"Selected dates ({len(valid_dates)}) exceeds maximum of {MAX_MULTI_DAY_OCCURRENCES}"}
            if valid_dates:
                job_dates = valid_dates
            else:
                job_dates = [start_date_str] if start_date_str else [None]
        elif start_date_str and end_date_str:
            try:
                start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                if end_dt > start_dt:
                    days_diff = (end_dt - start_dt).days + 1
                    if days_diff > MAX_MULTI_DAY_OCCURRENCES:
                        return {"error": f"Date range exceeds maximum of {MAX_MULTI_DAY_OCCURRENCES} days"}
                    for i in range(days_diff):
                        current_date = start_dt + timedelta(days=i)
                        job_dates.append(current_date.strftime('%Y-%m-%d'))
                else:
                    job_dates = [start_date_str]
            except ValueError:
                job_dates = [start_date_str]
        else:
            job_dates = [start_date_str] if start_date_str else [None]

        is_multi_day = len(job_dates) > 1
        created_job_ids = []
        first_job_id = None

        event_id = event.get('google_event_id') or request_item.get('google_event_id')

        for idx, occurrence_date in enumerate(job_dates):
            job_id = str(uuid.uuid4())
            
            # 2. Create the Job record linked to the PET
            item = {
                'PK': f"JOB#{job_id}",
                'SK': f"REQ#{request_id}",
                'company_id': company_id,
                'request_id': request_id,
                'client_id': client_id,
                'pet_id': pet_id,
                'pet_name': request_item.get('pet_names') or "Unnamed Pet",

                'client_name': request_item.get('client_name'),
                'client_email': request_item.get('client_email'),
                'service_type': request_item.get('service_type'),
                'start_date': occurrence_date if occurrence_date else request_item.get('start_date'),
                'end_date': occurrence_date if is_multi_day else request_item.get('end_date'),
                'visit_window': request_item.get('visit_window'),
                'visit_windows': request_item.get('visit_windows'),
                'preferred_sitter': request_item.get('preferred_sitter'),
                'preferred_sitter_name': request_item.get('preferred_sitter_name'),
                'pet_info': request_item.get('pet_info'),
                'status': JobStatus.JOB_CREATED.value,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'entity_type': 'JOB',
                'audit_log': [{
                    "action": "JOB_INITIALIZED",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "note": f"Automatically created from approved request. Linked Pet: {pet_id}"
                }]
            }
            
            if is_multi_day:
                item['occurrence_date'] = occurrence_date
                item['scheduled_date'] = occurrence_date
                item['occurrence_index'] = idx + 1
                item['total_occurrences'] = len(job_dates)
                item['is_multi_day'] = True
                
                # R7E Phase 1A: Sync each child JOB directly
                try:
                    from common.google_calendar import sync_calendar_event
                    cal_res = sync_calendar_event(item)
                    if cal_res and cal_res.get('event_id'):
                        item['google_event_id'] = cal_res['event_id']
                except Exception as e:
                    print(f"WARNING: Multi-day child JOB calendar sync failed for date {occurrence_date}: {e}")
            elif event_id:
                # Do not inherit google_event_id for multi-day jobs (handled individually above)
                item['google_event_id'] = event_id
            
            if put_item(item):
                if first_job_id is None:
                    first_job_id = job_id
                created_job_ids.append(job_id)
                print(f"Job {job_id} created successfully. Pet: {pet_id} Date: {occurrence_date}")
            else:
                print(f"WARNING: Failed to save job {job_id} for date {occurrence_date}")

            if is_multi_day and idx < len(job_dates) - 1:
                time.sleep(0.1) # 100ms delay between calls
                
        if not created_job_ids:
            return {"error": "Failed to create any JOB records."}
                
        # Link back to original request
        try:
            update_expr = "SET job_id = :jid, job_ids = :jids"
            expr_vals = {":jid": first_job_id, ":jids": created_job_ids}
            if is_multi_day:
                update_expr += ", is_multi_day = :imd, total_occurrences = :to"
                expr_vals[":imd"] = True
                expr_vals[":to"] = len(job_dates)

            table.update_item(
                Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_vals
            )
        except Exception as e:
            print(f"WARNING: Failed to link job_ids back to request: {e}")
            
        return {
            "job_id": first_job_id,
            "job_ids": created_job_ids,
            "pet_id": pet_id,
            "status": JobStatus.JOB_CREATED.value
        }
            
    except Exception as e:
        print(f"Unhandled error: {e}")
        return {"error": str(e)}
