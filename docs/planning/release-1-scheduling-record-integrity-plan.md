# Release 1: Scheduling & Record Integrity — Implementation Plan

**Date:** 2026-05-11  
**Status:** Plan Only — No Implementation Yet  
**Prerequisite:** Discovery document (`intake-client-scheduling-modernization-evaluation.md`)  
**Objective:** Fix workflow integrity and admin list clarity before adding new intake/client features.

---

## 1. Recommended Approach for Request List Visibility

### Three Options Evaluated

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A. Parent-only list | Request List shows only `REQ#` records. JOB records are internal/hidden. | Simplest mental model. One row = one booking. No confusion. | Loses direct JOB-level visibility in the list. |
| B. Job-only scheduler | Request List shows REQ#. MasterScheduler shows JOB# only. | Clean separation of concerns. | Two different data sources for two views — more complex state management. |
| C. Labeled parent/child | Both appear with visual distinction (badge, indent, grouping). | Full visibility. | Adds UI complexity. Still confusing for a small-team admin tool. |

### Recommendation: Option A — Parent-Only Request List

**Rationale:**

1. **Ryan's mental model is "one booking = one row."** The JOB record is an internal implementation detail for worker assignment and calendar sync. It should not surface as a separate row in the admin request list.

2. **The REQ record already mirrors all relevant JOB data** (status, worker_id, worker_name) because the assignment handler explicitly syncs both. There is no information on the JOB record that isn't also on the REQ record.

3. **The MasterScheduler already works from the same `allRequests` pool** and filters by `start_date`. It can continue using REQ records (which have `start_date`, `end_date`, `worker_id`, `service_type`). No separate JOB-specific view is needed.

4. **Lowest risk.** Filtering out JOB records from the list view is a single filter change. No data migration, no schema change, no new UI components.

5. **Future-compatible.** If multi-visit expansion is added later (Phase 2+), JOB records can be surfaced as grouped child rows under the parent REQ. But that's a future enhancement, not a Release 1 concern.

### Implementation Detail

- **Backend**: Add `entity_type != 'JOB'` filter to the admin request scan, OR
- **Frontend**: Filter out records where `PK.startsWith('JOB#')` from the request list view
- **MasterScheduler**: Continue using REQ records (they have all scheduling data)
- **CareCard/Detail View**: When a REQ record is opened, the linked JOB record can be fetched for internal reference if needed

---

## 2. Exact Frontend Files/Functions to Change

### `web/src/components/AdminDashboard.jsx`

| Function/Section | Current Behavior | Target Behavior |
|-----------------|-----------------|-----------------|
| `fetchAllData()` | Merges all returned records (REQ# and JOB#) into `allRequests` by PK | Filter out JOB# records before merging, OR filter in `visibleRecords` |
| `visibleRecords` (useMemo) | Filters by status/workflow only | Add `!item.PK.startsWith('JOB#')` guard for LIST view |
| `isRequestLikeRecord()` | Returns true for anything with REQ# or JOB# in PK/SK | For list view purposes, only match REQ# in PK |
| `filterCounts` (useMemo) | Counts include JOB# records | Exclude JOB# from counts |
| `getWorkflowState()` | No change needed | No change — still works on individual items |
| `isDataIssue()` | Catches JOB# records with missing data | Exclude JOB# records from Data Issues detection |

### `web/src/components/MasterScheduler.jsx`

| Function/Section | Current Behavior | Target Behavior |
|-----------------|-----------------|-----------------|
| `filteredJobs` | Filters `items` prop by date/status/staff | No change — receives filtered items from parent |
| Component props | Receives `items` from AdminDashboard | Parent should pass only REQ# records (already filtered) |

### `web/src/api/client.js`

No changes needed. The API calls remain the same.

---

## 3. Exact Backend Files/Functions to Change

### `src/backend/handlers/admin_handler.py`

| Function/Section | Current Behavior | Target Behavior |
|-----------------|-----------------|-----------------|
| GET /admin/requests (status=ALL) scan filter | `contains(PK, "REQ#") OR contains(PK, "JOB#")` | `contains(PK, "REQ#")` only |
| GET /admin/requests (StatusIndex query) | Returns all records matching status (REQ# and JOB#) | Add `FilterExpression` to exclude `entity_type = 'JOB'` |

### `src/backend/handlers/review_handler.py`

| Function/Section | Current Behavior | Target Behavior |
|-----------------|-----------------|-----------------|
| Status update cascade to JOB | Updates JOB status when REQ status changes (for APPROVED, ASSIGNED, rollback) | Ensure ALL transitions cascade: CANCELLED, ARCHIVED, DELETED, COMPLETED |
| worker_id removal on rollback | `ASSIGNED → APPROVED` removes worker_id from REQ only | Also remove worker_id from linked JOB record |

### `src/backend/handlers/cancellation_handler.py`

| Function/Section | Current Behavior | Target Behavior |
|-----------------|-----------------|-----------------|
| `handle_admin_decision()` | Updates REQ record to CANCELLED. Does NOT update JOB record. | Also update linked JOB record to CANCELLED |
| `handle_customer_request()` | Updates REQ to CANCELLATION_REQUESTED. Does NOT update JOB. | Also update linked JOB to CANCELLATION_REQUESTED |

### `src/backend/handlers/assignment_handler.py`

| Function/Section | Current Behavior | Target Behavior |
|-----------------|-----------------|-----------------|
| Worker assignment | Updates both JOB and REQ records | No change needed — already correct |
| Race condition scan | Scans for orphaned JOB records | No change needed |

### `src/backend/handlers/job_handler.py`

| Function/Section | Current Behavior | Target Behavior |
|-----------------|-----------------|-----------------|
| Job creation | Copies `start_date` but NOT `end_date` | Also copy `end_date` and `visit_window` |

### `src/backend/common/status.py`

No changes to the transition matrix. Recovery paths already exist.

---

## 4. Current Behavior vs Target Behavior

### Request List — Scheduled with Staff View

| Aspect | Current | Target |
|--------|---------|--------|
| Records shown | Both REQ# and JOB# with ASSIGNED status | Only REQ# records with ASSIGNED status |
| Row count for one booking | 2 rows (REQ + JOB) | 1 row (REQ only) |
| Date display | Row 1: "2026-05-15 to 2026-05-17", Row 2: "2026-05-15" | Single row: "2026-05-15 to 2026-05-17" |
| Worker display | Both show same worker | Single row shows worker |

### Cancel Action

| Aspect | Current | Target |
|--------|---------|--------|
| Cancel via review_handler | Updates REQ + JOB | Updates REQ + JOB (no change) |
| Cancel via cancellation_handler | Updates REQ only, JOB orphaned | Updates REQ + JOB |
| Google Calendar cleanup | Only on REQ path | On both paths (already handled by REQ having google_event_id) |

### Rollback (ASSIGNED → APPROVED)

| Aspect | Current | Target |
|--------|---------|--------|
| worker_id removal | Removed from REQ only | Removed from both REQ and JOB |
| JOB status | May stay ASSIGNED | Cascades to JOB_CREATED |

### Data Issues

| Aspect | Current | Target |
|--------|---------|--------|
| JOB# records in Data Issues | Appear if missing worker_id or client_name | JOB# records excluded from Data Issues view entirely |
| Orphaned JOB records | Silently exist | Excluded from list; future cleanup utility |

---

## 5. Proposed Data-Shape or Metadata Additions

### No schema migration required. Only additive field copies:

| Record | Field | Change |
|--------|-------|--------|
| JOB# | `end_date` | Copy from REQ on creation (currently missing) |
| JOB# | `visit_window` | Copy from REQ on creation (currently missing) |

### No new fields required on REQ records.

### No new GSIs required.

### Optional future addition (not Release 1):
- `parent_request_id` on JOB records (currently implicit via SK `REQ#<id>`)
- `child_job_ids[]` on REQ records (currently only `job_id` singular)

---

## 6. How Cancel/Archive/Trash Should Apply

### Recommended: Parent-Cascades-to-Children

When a lifecycle action is performed on a REQ# record, it MUST cascade to all linked JOB# records.

| Action on REQ | Effect on linked JOB |
|---------------|---------------------|
| CANCELLED | JOB → CANCELLED |
| ARCHIVED | JOB → ARCHIVED |
| DELETED | JOB → DELETED |
| PURGE (permanent delete) | JOB also permanently deleted |
| APPROVED (recovery) | JOB → JOB_CREATED |
| ASSIGNED | JOB → ASSIGNED (already works) |
| COMPLETED | JOB → COMPLETED |

### Implementation

Add a shared cascade utility function:

```python
# In common/db.py or a new common/cascade.py
def cascade_status_to_job(request_item, new_status, extra_attrs=None):
    """
    Cascades a status change from a REQ record to its linked JOB record.
    Maps REQ statuses to JOB equivalents.
    """
    job_id = request_item.get('job_id')
    request_id = request_item.get('request_id')
    if not job_id or not request_id:
        return  # No linked job

    # Map REQ status to JOB status
    status_map = {
        'APPROVED': 'JOB_CREATED',
        'ASSIGNED': 'ASSIGNED',
        'COMPLETED': 'COMPLETED',
        'CANCELLED': 'CANCELLED',
        'ARCHIVED': 'ARCHIVED',
        'DELETED': 'DELETED',
        'CANCELLATION_REQUESTED': 'CANCELLED',  # JOB doesn't have this status
    }
    job_status = status_map.get(new_status, new_status)

    # Update JOB record
    update_expr = "SET #stat = :s, updated_at = :now"
    expr_vals = {":s": job_status, ":now": datetime.now(timezone.utc).isoformat()}
    
    if extra_attrs:
        # e.g., REMOVE worker_id
        pass

    table.update_item(
        Key={'PK': f"JOB#{job_id}", 'SK': f"REQ#{request_id}"},
        UpdateExpression=update_expr,
        ExpressionAttributeNames={"#stat": "status"},
        ExpressionAttributeValues=expr_vals
    )
```

### Where to call it:
- `review_handler.py` — after every successful REQ status update (replace current inline JOB update)
- `cancellation_handler.py` — after admin decision updates REQ
- `admin_handler.py` — after bulk ARCHIVE/DELETE/status actions on REQ records

---

## 7. How Rollback/Recovery Should Work

### Current State

The transition matrix already allows:
- `CANCELLED → PENDING_REVIEW` (reopen)
- `CANCELLED → APPROVED` (direct re-approval)
- `ARCHIVED → PENDING_REVIEW` (reopen)
- `DELETED → PENDING_REVIEW` (reopen)

The frontend exposes only `REOPEN_PENDING` (→ PENDING_REVIEW) for CANCELLED/ARCHIVED/DELETED records.

### Target State

Add a "Recover" action that offers contextual recovery options:

| Current Status | Recovery Options |
|---------------|-----------------|
| CANCELLED | Reopen to Pending Review, Restore to Approved |
| ARCHIVED | Reopen to Pending Review |
| DELETED (Trash) | Reopen to Pending Review |
| Data Issues (ASSIGNED without worker) | Assign Worker, Revert to Approved |

### Frontend Changes

In `getWorkflowState()`:

```javascript
// Current:
if (isArchivedRecord(item)) {
    state.actions = ["REOPEN_PENDING", "DELETE"];
}
if (isDeletedRecord(item)) {
    state.actions = ["REOPEN_PENDING", "PURGE_FOREVER"];
}

// Target:
if (isArchivedRecord(item)) {
    state.actions = ["REOPEN_PENDING", "RESTORE_APPROVED", "DELETE"];
}
if (isCancelledRecord(item)) {
    // Already has ARCHIVE, DELETE — add recovery
    state.actions = ["REOPEN_PENDING", "RESTORE_APPROVED", "ARCHIVE", "DELETE"];
}
if (isDeletedRecord(item)) {
    state.actions = ["REOPEN_PENDING", "RESTORE_APPROVED", "PURGE_FOREVER"];
}
```

### Backend Changes

The `performAdminAction` POST endpoint already supports arbitrary status targets (`APPROVED`, `PENDING_REVIEW`, etc.). The frontend just needs to send the correct action.

### Cascade on Recovery

When a REQ is recovered to APPROVED:
- Linked JOB should be set to JOB_CREATED
- `worker_id` should be cleared from both (since the booking needs re-assignment)
- Google Calendar event should NOT be recreated automatically (admin re-assigns manually)

---

## 8. How to Handle ASSIGNED Records Without worker_id

### Root Cause

The `ASSIGNED → APPROVED` rollback on REQ removes `worker_id` from REQ but not from JOB. If the JOB stays in ASSIGNED without worker_id, it becomes a "Data Issue."

### Fix (Two Parts)

**Part A: Prevent future occurrences**

In `review_handler.py`, the rollback special case:
```python
# Current:
if current_status == 'ASSIGNED' and new_status == 'APPROVED':
    update_expr += " REMOVE worker_id"

# Target: Also cascade to JOB
if current_status == 'ASSIGNED' and new_status == 'APPROVED':
    update_expr += " REMOVE worker_id"
    # Cascade: JOB → JOB_CREATED, REMOVE worker_id
    cascade_status_to_job(request_item, 'APPROVED', remove_fields=['worker_id'])
```

**Part B: Exclude JOB records from Data Issues**

In `AdminDashboard.jsx`:
```javascript
// Current isDataIssue():
// Catches any record with missing data

// Target: Add exclusion
if (item.PK && item.PK.startsWith('JOB#')) return false;  // JOB records are internal
```

This means JOB records can never appear in Data Issues. If a JOB is orphaned or inconsistent, it's invisible to the admin and will be cleaned up by the cascade fix.

---

## 9. Test Cases

### TC-01: Normal Single-Day Request

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Submit intake for 2026-06-01, PET_SITTING | REQ created, status=PENDING_REVIEW |
| 2 | Admin approves | REQ→APPROVED, JOB created, PET created |
| 3 | Admin assigns worker | REQ→ASSIGNED, JOB→ASSIGNED, both have worker_id |
| 4 | View Request List → Scheduled with Staff | **1 row** showing the booking |
| 5 | View MasterScheduler | 1 visit card on 2026-06-01 |

### TC-02: Overnight/Date-Range Request

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Submit intake for 2026-06-01 to 2026-06-03, OVERNIGHT | REQ created with start_date + end_date |
| 2 | Admin approves and assigns | REQ→ASSIGNED, JOB→ASSIGNED |
| 3 | View Request List → Scheduled with Staff | **1 row** showing "2026-06-01 to 2026-06-03" |
| 4 | View MasterScheduler | 1 visit card (start_date = 2026-06-01) |

### TC-03: Exact Scheduled Date/Time (Future Enhancement Context)

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | Booking exists in APPROVED status | 1 row in Booking Queue |
| 2 | Admin assigns worker with specific time | REQ→ASSIGNED with worker_id |
| 3 | View Scheduled with Staff | **1 row** — no duplicate created |
| 4 | No new REQ or JOB record is created | Record count unchanged |

### TC-04: Staff Assignment

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | REQ in APPROVED, JOB in JOB_CREATED | 1 row in list |
| 2 | Admin clicks Assign, selects worker | Both REQ and JOB update to ASSIGNED with worker_id |
| 3 | View Scheduled with Staff | **1 row** |
| 4 | Admin clicks Change Worker | Both REQ and JOB update worker_id |
| 5 | Admin clicks Revert to Approved | Both REQ→APPROVED and JOB→JOB_CREATED, worker_id removed from both |

### TC-05: Cancellation

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | REQ in ASSIGNED, JOB in ASSIGNED | 1 row in Scheduled with Staff |
| 2 | Admin cancels via review action | REQ→CANCELLED, JOB→CANCELLED |
| 3 | View Cancelled filter | **1 row** (REQ only) |
| 4 | Customer requests cancellation | REQ→CANCELLATION_REQUESTED, JOB→CANCELLED |
| 5 | Admin approves cancellation | REQ→CANCELLED, JOB→CANCELLED, calendar deleted |
| 6 | Google Calendar event removed | Confirmed |
| 7 | Worker notification sent | Confirmed |

### TC-06: Restore/Recovery

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | REQ in CANCELLED | 1 row in Cancelled filter |
| 2 | Admin clicks "Restore to Approved" | REQ→APPROVED, JOB→JOB_CREATED, worker_id cleared |
| 3 | View Booking Queue | 1 row ready for re-assignment |
| 4 | REQ in ARCHIVED | 1 row in Archive |
| 5 | Admin clicks "Reopen to Pending" | REQ→PENDING_REVIEW, JOB→JOB_CREATED |
| 6 | REQ in DELETED (Trash) | 1 row in Trash |
| 7 | Admin clicks "Reopen to Pending" | REQ→PENDING_REVIEW, JOB→JOB_CREATED |

### TC-07: Data Issues Filter

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | JOB record exists with ASSIGNED status but no worker_id | **Does NOT appear** in Data Issues |
| 2 | REQ record exists with empty client_name | Appears in Data Issues |
| 3 | REQ record exists with unknown status value | Appears in Data Issues |
| 4 | JOB record with any issue | Never appears in Data Issues (excluded) |

### TC-08: Scheduled with Staff Filter

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1 | One booking: REQ=ASSIGNED + JOB=ASSIGNED | **1 row** in filter |
| 2 | Two separate bookings both ASSIGNED | **2 rows** in filter |
| 3 | One booking cancelled, one active | **1 row** in filter |
| 4 | Overnight booking (start + end date) | **1 row** showing date range |

---

## 10. Risks and Rollback Plan

### Risk 1: MasterScheduler Breaks

**Risk:** Filtering JOB# records from the data pool might affect the MasterScheduler if it relies on JOB-specific fields.

**Assessment:** LOW. The MasterScheduler uses `start_date`, `worker_id`, `client_name`, `pet_name`, `service_type`, `status` — all of which exist on REQ records after assignment cascade.

**Mitigation:** Verify MasterScheduler renders correctly with REQ-only data before deploying.

**Rollback:** Revert the frontend filter (one line change). No data affected.

### Risk 2: Cascade Creates Infinite Loop

**Risk:** REQ update cascades to JOB, JOB update cascades back to REQ.

**Assessment:** LOW. The cascade is one-directional (REQ → JOB only). The assignment_handler updates JOB first then REQ, but does not trigger the review_handler cascade.

**Mitigation:** The cascade utility only writes to JOB records. JOB record updates do NOT trigger REQ updates (no reverse cascade).

**Rollback:** Remove cascade calls from handlers. JOB records may become stale but no data loss.

### Risk 3: Existing Orphaned JOB Records

**Risk:** JOB records already in inconsistent states (ASSIGNED without worker, or ASSIGNED while REQ is CANCELLED) will remain in DynamoDB.

**Assessment:** LOW IMPACT. Since JOB records are now hidden from the admin list, orphaned JOBs are invisible. They don't affect user experience.

**Mitigation:** After Release 1 deploys successfully, run a one-time read-only audit script to identify orphaned JOBs. Present findings to admin for manual cleanup decision.

**Rollback:** N/A — orphaned records are pre-existing.

### Risk 4: Bulk Actions on Mixed Record Types

**Risk:** The bulk action system (`performAdminAction`) currently operates on whatever records are selected. If JOB records are hidden from the list, they can't be accidentally bulk-actioned.

**Assessment:** POSITIVE. Hiding JOB records from the list means they can't be selected for bulk actions, which is the desired behavior.

**Rollback:** N/A.

### Risk 5: Google Calendar Sync on Recovery

**Risk:** Recovering a CANCELLED record to APPROVED might trigger calendar sync for a booking that was already deleted from Google Calendar.

**Assessment:** MEDIUM. The review_handler syncs to Google Calendar on APPROVED/ASSIGNED transitions.

**Mitigation:** On recovery to APPROVED, the `google_event_id` field will be empty (it was removed on cancellation). The calendar sync will create a NEW event, which is correct behavior.

**Rollback:** If calendar creates duplicates, manually delete from Google Calendar. No data corruption.

---

## 11. Recommended Implementation Order

### Step 1: Backend — Cascade Utility (Lowest Risk, Foundation)

**Files:** New `src/backend/common/cascade.py` or add to `db.py`

Create the `cascade_status_to_job()` utility function. This is pure additive code with no side effects until called.

### Step 2: Backend — Fix Cancellation Handler Cascade

**Files:** `src/backend/handlers/cancellation_handler.py`

Add cascade call after admin decision updates REQ to CANCELLED. This fixes the root cause of orphaned JOB records going forward.

### Step 3: Backend — Fix Review Handler Rollback Cascade

**Files:** `src/backend/handlers/review_handler.py`

Ensure the `ASSIGNED → APPROVED` rollback also cascades to JOB (status → JOB_CREATED, REMOVE worker_id). This prevents future Data Issues from rollback.

### Step 4: Backend — Fix Job Handler (Copy end_date)

**Files:** `src/backend/handlers/job_handler.py`

Copy `end_date` and `visit_window` from REQ to JOB on creation. Minor additive change.

### Step 5: Backend — Filter JOB Records from Admin Request Scan

**Files:** `src/backend/handlers/admin_handler.py`

Change the scan filter from `contains(PK, "REQ#") OR contains(PK, "JOB#")` to `contains(PK, "REQ#")` only. This is the single change that eliminates duplicate rows.

### Step 6: Frontend — Exclude JOB Records from List View

**Files:** `web/src/components/AdminDashboard.jsx`

Add `!item.PK.startsWith('JOB#')` guard in:
- `visibleRecords` memo
- `filterCounts` memo
- `isDataIssue()` function

This is a safety net in case any JOB records slip through the backend filter (e.g., StatusIndex query path).

### Step 7: Frontend — Add Recovery Actions

**Files:** `web/src/components/AdminDashboard.jsx`

Add `RESTORE_APPROVED` to the action lists for CANCELLED, ARCHIVED, and DELETED records. Wire it to call `performAdminAction(pk, sk, 'APPROVED')`.

### Step 8: Verification

- Manual testing against all 8 test case groups
- Verify MasterScheduler still renders correctly
- Verify CareCard still opens from list rows
- Verify bulk actions still work on REQ records
- Verify Google Calendar sync on assign/cancel/recover

---

## 12. Summary

| Item | Decision |
|------|----------|
| List visibility | REQ-only in Request List. JOB records are internal. |
| MasterScheduler | Uses REQ records (already has all scheduling data). |
| Cancel/Archive/Trash scope | Always cascades from REQ to linked JOB. |
| Recovery | Add "Restore to Approved" action for CANCELLED/ARCHIVED/DELETED. |
| Data Issues | JOB records excluded entirely. Only REQ records can be Data Issues. |
| ASSIGNED without worker_id | Prevented by cascade fix. Existing orphans hidden (JOB excluded from list). |
| Schema changes | None required. Only additive field copies (end_date, visit_window on JOB). |
| RBAC | No changes. All existing role checks preserved. |
| Protected accounts | No changes. PROTECTED_SUBS and PROTECTED_EMAILS unchanged. |
| Destructive operations | None. No data migration. No production data modification. |

---

## Appendix: Files Changed Summary

| File | Type | Steps |
|------|------|-------|
| `src/backend/common/cascade.py` (NEW) | Backend | Step 1 |
| `src/backend/handlers/cancellation_handler.py` | Backend | Step 2 |
| `src/backend/handlers/review_handler.py` | Backend | Step 3 |
| `src/backend/handlers/job_handler.py` | Backend | Step 4 |
| `src/backend/handlers/admin_handler.py` | Backend | Step 5 |
| `web/src/components/AdminDashboard.jsx` | Frontend | Steps 6, 7 |

**Total files modified:** 5 existing + 1 new  
**Lines of code estimated:** ~80 backend, ~30 frontend  
**Risk level:** Low (no schema migration, no destructive operations, fully reversible)
