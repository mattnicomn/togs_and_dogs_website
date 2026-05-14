# Release 4E: Scheduling/Staff Inline Assignment — Implementation Plan

**Date:** 2026-05-14  
**Status:** Plan Only — No Implementation Yet  
**Prerequisite:** Release 4D fully accepted  
**Objective:** Allow Ryan/admin to assign or reassign staff directly from the CareCard Scheduling/Staff tab.

---

## 1. Current-State Findings

### Current Assignment Flow (Dashboard List)

1. Admin clicks "Assign" action button on a request row in the Request List
2. A `<select>` dropdown appears inline in the row (`assigningId` state)
3. Admin selects a staff member from the dropdown
4. `handleAssignAction(item, workerId)` is called
5. Resolves `reqId`, `clientId`, `jobId` from the item
6. Calls `assignWorker(jobId || reqId, reqId, clientId, workerId, workerName)` → `POST /admin/assign`
7. Backend `assignment_handler.py` processes:
   - Validates owner/admin role
   - Resolves JOB record (handles race conditions)
   - Updates JOB status to ASSIGNED + sets worker_id/worker_name
   - Updates REQ status to ASSIGNED + sets worker_id/worker_name
   - Syncs to Google Calendar
   - Triggers STAFF_ASSIGNED + VISIT_SCHEDULED notifications
8. Frontend refreshes data via `fetchAllData()`

### CareCard Scheduling/Staff Tab (Current)

**Read-only display:**
- Scheduled Date (editable via existing edit flow — saves to PET# record)
- Scheduled Time (editable)
- Duration (editable)
- **Assigned To:** `pet.worker_name || pet.worker_id || 'Unassigned'` (READ-ONLY)
- Client Prefers: `pet.preferred_sitter_name` (informational)
- Google Calendar link status

**Key gap:** The "Assigned To" field is display-only. No dropdown, no reassignment capability.

### What CareCard Receives

```jsx
<CareCard 
  pet={selectedPet}           // PET# record merged with _originItem (REQ record)
  onClose={...}
  onUpdate={handleUpdatePet}  // Saves PET# record fields
  onStatusUpdate={...}        // Changes workflow status
  userRole={role}
/>
```

**Missing:** `staffList`, `onAssign` callback. CareCard has no access to the staff dropdown data or the assignment API.

### Staff Data Source

- `staffList` state in AdminDashboard — loaded via `getStaff()` → `GET /admin/staff`
- Filtered for assignment: `staffList.filter(s => s.is_assignable !== false && s.is_active !== false)`
- Shows `display_name` and uses `email || display_name` as the worker_id value

### Assignment Handler RBAC

```python
role = get_effective_role(event)
if role not in ['owner', 'admin']:
    return error(403, "Forbidden: Only owners and admins can assign workers", event)
```

Only owner/admin can assign. Staff and client roles are blocked server-side.

---

## 2. Recommended Implementation Approach

### Frontend-Only Change (No Backend Modifications)

The existing `POST /admin/assign` endpoint already handles:
- Assignment and reassignment
- JOB record creation/resolution
- REQ + JOB status update to ASSIGNED
- Google Calendar sync
- Notifications

**All we need is a staff dropdown in the CareCard Scheduling tab that calls the same `assignWorker()` API.**

### Implementation Steps

1. Pass `staffList` and `onAssign` callback as new props to CareCard
2. In the Scheduling/Staff tab, replace the read-only "Assigned To" text with a dropdown (when editing or always-visible for owner/admin)
3. On selection, call `onAssign(originItem, workerId)` which triggers the existing `handleAssignAction` flow
4. After assignment, refresh the CareCard data (close and reopen, or update in-place)

### Key Design Decision: Always-Visible vs Edit-Mode-Only

**Recommended: Always-visible dropdown for owner/admin** (not gated by `isEditing`).

Rationale:
- Assignment is a workflow action, not a data edit
- The dashboard list already shows the dropdown without entering "edit mode"
- Ryan expects to assign staff quickly without clicking "Edit Record" first
- The dropdown can be disabled for staff role (view-only)

---

## 3. Files Likely to Change

| File | Change | Type |
|------|--------|------|
| `web/src/components/AdminDashboard.jsx` | Pass `staffList` and `onAssign` props to CareCard | Frontend |
| `web/src/components/CareCard.jsx` | Add staff dropdown in Scheduling tab, call onAssign | Frontend |

**Backend:** No changes needed. Existing `POST /admin/assign` handles everything.

**Total:** 2 frontend files  
**Estimated effort:** ~40 lines  
**Risk level:** Low

---

## 4. Data Flow

```
CareCard Scheduling Tab:
  → Admin selects staff from dropdown
  → Calls onAssign(pet._originItem, workerId)
  
AdminDashboard.handleAssignAction(item, workerId):
  → Resolves reqId, clientId, jobId
  → Calls assignWorker(jobId, reqId, clientId, workerId, workerName)
  → POST /admin/assign
  
Backend assignment_handler.py:
  → Validates owner/admin role
  → Updates JOB# status → ASSIGNED, sets worker_id
  → Updates REQ# status → ASSIGNED, sets worker_id
  → Syncs Google Calendar
  → Triggers notifications
  
Frontend:
  → fetchAllData() refreshes
  → CareCard closes (or refreshes with new data)
```

---

## 5. Duplicate JOB# Prevention

The assignment handler already handles this:
- If `jobId == reqId` or starts with "REQ#", it resolves the actual JOB via the REQ record's `job_id` field
- If no JOB exists yet, it scans for orphaned JOB records
- It does NOT create new JOB records — it only updates existing ones

**Risk: None.** Assignment from CareCard uses the same endpoint as assignment from the list. No new JOB creation path.

---

## 6. Calendar Behavior

The existing assignment handler already:
- Syncs to Google Calendar on assignment
- Updates existing calendar events on reassignment
- Handles disconnected calendar gracefully (logs warning, doesn't block)
- Persists `google_event_id` on both REQ and JOB records

**Risk: None.** Same behavior whether assigned from list or CareCard.

---

## 7. RBAC/Security

| Role | Can Assign from CareCard? | Enforcement |
|------|---------------------------|-------------|
| Owner | ✅ Yes | Backend: `role in ['owner', 'admin']` |
| Admin | ✅ Yes | Backend: same |
| Staff | ❌ No | Backend returns 403. Frontend hides dropdown. |
| Client | ❌ No | Cannot open CareCard at all |

**Frontend guard:** Only show dropdown when `userRole === 'owner' || userRole === 'admin'`.
**Backend guard:** Already enforced — returns 403 for non-owner/admin.

---

## 8. Edge Cases

| Scenario | Handling |
|----------|----------|
| Request not yet approved (no JOB) | Show message: "Approve this request before assigning staff" |
| Request already assigned | Dropdown shows current worker pre-selected. Changing triggers reassignment. |
| Assign to same worker | Backend handles idempotently (self-transition allowed) |
| Assign to inactive staff | Frontend filters `is_assignable !== false && is_active !== false` |
| Calendar disconnected | Assignment succeeds, calendar sync logs warning |
| CareCard opened for archived/cancelled record | Hide assignment dropdown (no point assigning cancelled work) |

---

## 9. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Duplicate JOB records | None | Assignment handler resolves existing JOB, doesn't create new |
| Stale scheduler data | Low | `fetchAllData()` called after assignment |
| Duplicate calendar events | None | Handler updates existing event or creates one if missing |
| Staff role escalation | None | Backend enforces 403 |
| Assignment to inactive staff | None | Frontend filters staff list |

---

## 10. Validation Plan

| # | Test | Expected |
|---|------|----------|
| 1 | Open CareCard for approved/assigned record | Staff dropdown visible in Scheduling tab |
| 2 | Select different staff | Assignment succeeds, record updates |
| 3 | Reopen record | New worker shown |
| 4 | Open CareCard for unapproved record | Dropdown hidden or shows "Approve first" message |
| 5 | Open CareCard as staff role | Dropdown hidden (view-only) |
| 6 | Assign from CareCard | Google Calendar updates (if connected) |
| 7 | Assign from CareCard | Request List shows updated worker |
| 8 | Assign from CareCard | Scheduler shows updated worker |
| 9 | Open CareCard for cancelled record | Dropdown hidden |
| 10 | npm run build | Passes |
| 11 | No console/API errors | Clean |

---

## 11. Rollback

- Revert CareCard.jsx and AdminDashboard.jsx → dropdown removed
- No data affected (assignment API unchanged)
- No backend rollback needed

---

## 12. Out of Scope

| Item | Reason |
|------|--------|
| New backend endpoints | Existing `POST /admin/assign` works |
| JOB record creation | Already handled by approval flow |
| Calendar event creation logic | Already handled by assignment handler |
| Notification changes | Already triggered by assignment handler |
| Status transition changes | Assignment already sets ASSIGNED status |
| Multi-worker assignment | Not supported in current model |
| Scheduling time/date editing via assignment | Already editable in CareCard (saves to PET#) |
