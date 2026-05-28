# Release 7G: Multi-Day Assignment Handler Fix

**Status:** Planning
**Priority:** High (Resolves limitation discovered in 7F)
**Risk to Production:** Low-Medium (Updates existing assignment logic)
**Terraform Required:** No
**Frontend Changes:** No

---

## 1. Problem Statement

During the production validation of Release 7F, it was discovered that assigning a worker to a multi-day booking via the Admin UI does not assign all child JOBs. 

When the Admin UI assigns a worker from the parent request view, it sends the parent `req_id` to `/assign`. The `assignment_handler.py` correctly detects that it was given a `req_id`, but it resolves this to a single `job_id` using a DynamoDB scan (grabbing `items[0]`). 

As a result:
- Only the **first** child job gets assigned.
- Google Calendar is only synced for the first child job.
- Notifications are only fired once (which ironically prevented duplicate spam, but the assignment state is incomplete).
- The remaining child jobs stay stuck in `JOB_CREATED` status.

---

## 2. Requirements

1. **Preserve Single-Day Behavior:** If a single child `job_id` is passed, or if the request only has one child job, it should assign just that job.
2. **Assign All Child Jobs:** For multi-day parent requests, detect `job_ids` on the parent request and apply the assignment to *every* child JOB.
3. **Database Consistency:** Update each child JOB with the assigned `worker_id`, `worker_name`, and `status = ASSIGNED`. Also update the parent REQ to reflect the assignment.
4. **Google Calendar Consistency:** Ensure `sync_calendar_event` is called for every child job so all child events show the assigned worker.
5. **Smart Notification Deduplication:** Prevent spamming the worker/client with N identical notifications for the N child jobs. We will use an in-memory tracking set during the loop, with the Release 7F DynamoDB dedup guard acting as a secondary safety net for cross-invocation duplicates.
6. **Graceful Failures:** If one child JOB is missing from the database, skip it and continue assigning the rest.

---

## 3. Implementation Plan

### `src/backend/handlers/assignment_handler.py`

Modify the job resolution logic to compile a list of `target_job_ids`:

```python
target_job_ids = []
request_rec = None

# If UI passed a REQ ID
if job_id == req_id or job_id.startswith('REQ#'):
    print(f"INFO: Attempting to resolve Job IDs from Request REQ#{req_id}")
    request_rec = get_item(f"REQ#{req_id}", f"CLIENT#{client_id}")
    if request_rec:
        if request_rec.get('job_ids'):
            target_job_ids = request_rec.get('job_ids')
        elif request_rec.get('job_id'):
            target_job_ids = [request_rec.get('job_id')]
    
    # Fallback scan for orphaned jobs
    if not target_job_ids:
        # scan with Attr('SK').eq(f"REQ#{req_id}")
        # target_job_ids = [item.get('PK').replace('JOB#', '')]
else:
    # Single job assignment directly from UI
    target_job_ids = [job_id]

if not target_job_ids:
    return not_found(...)
```

Then, loop over `target_job_ids` to update each job and sync calendar:

```python
assigned_jobs = []
calendar_results = []
notified = False  # In-memory dedup flag

for j_id in target_job_ids:
    item = get_item(f"JOB#{j_id}", f"REQ#{req_id}")
    if not item: continue
    
    # Check valid transition
    # Update JOB in DB
    # Sync Google Calendar
    assigned_jobs.append(j_id)
    
    # Trigger notifications exactly once for the batch
    if not notified:
        item['worker_id'] = worker_id
        item['worker_name'] = worker_name
        notify_event('STAFF_ASSIGNED', item)
        notify_event('VISIT_SCHEDULED', item)
        notified = True

# Update Parent REQ record (status & worker_id)
if assigned_jobs:
    # Update REQ in DB
```

### In-Memory vs Ledger Dedup
DynamoDB GSI queries (used in the 7F dedup guard) are eventually consistent. If we relied solely on the 7F guard inside a fast Python loop, the second iteration might query the ledger *before* the first iteration's write has propagated, resulting in duplicate emails. The `notified` boolean ensures safe batch deduplication, while the 7F guard catches external duplicate API calls.

---

## 4. Testing Plan

A new test file `tests/backend/test_r7g_assignment_multiday.py` will be created with the following cases:

1. **`test_single_day_assignment`**: UI passes single `job_id`, updates exactly one job.
2. **`test_multi_day_parent_assignment`**: UI passes `req_id`, resolves `job_ids` list, updates all child jobs and syncs calendar for each.
3. **`test_missing_child_job_graceful`**: Parent has 3 `job_ids`, but one is missing from DB. Should update the other 2 and succeed.
4. **`test_notification_in_memory_dedup`**: Assert that `notify_event` is called exactly twice (once for STAFF, once for VISIT) regardless of how many child jobs are updated.

---

## 5. Next Steps
Please review this plan. Upon approval, AG will execute the code changes, run the tests, and push for deployment.
