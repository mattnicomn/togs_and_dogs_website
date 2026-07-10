# Triage and Planning — Release 22K: Booking/Cancellation Request Visibility and Data Integrity Triage

**Status:** Triage Complete & Plan Prepared  
**Type:** Read-Only Investigation & Proposal  
**Date:** 2026-07-10  

---

## 1. Executive Summary

A visibility bug has been identified in the Admin Portal where clients' pending booking cancellation requests (`CANCELLATION_REQUESTED`) are completely invisible to administrators. This prevents administrators from seeing, reviewing, or approving/rejecting cancellation requests. 

This document details the root causes (both backend querying behavior and frontend filter predicates) and recommends a clean frontend-only fix to restore visibility.

---

## 2. Root Cause Analysis

### A. Backend Data Model
* **Record Representation:** Cancellation requests are stored as parent request records (`REQ#[request_id]`) in the primary DynamoDB table.
* **Status Field:** When a client requests a cancellation, the record's `status` field is set to `"CANCELLATION_REQUESTED"`. Details (e.g. reason, timestamp, by) are stored on the same record.
* **Child Jobs:** Any associated child job records (`JOB#[job_id]`) remain in their active status (e.g., `ASSIGNED` or `SCHEDULED`) until an administrator approves the cancellation, which triggers the cascading update to `"CANCELLED"`.

### B. Why They Do Not Show in the "Cancelled" Admin Queue
* When the admin views the "Cancelled" tab, the frontend sets `statusFilter = 'CANCELLED'`.
* Since `'CANCELLED'` is a terminal lifecycle state, `isActiveFilter` evaluates to `false` in `fetchAllData()`.
* The frontend then calls the backend endpoint `getAdminRequests('CANCELLED')`.
* The backend handler queries the DynamoDB `StatusIndex` GSI using `KeyConditionExpression=Key('status').eq('CANCELLED')`.
* Since the pending request has `status = 'CANCELLATION_REQUESTED'` in the database (not `'CANCELLED'`), it is not returned by the DynamoDB query. Therefore, it does not show up in the "Cancelled" view.

### C. Why They Do Not Show in "Needs Action" or "All Active" Queues
* When the admin is in the "Needs Action" or "All Active" views, `isActiveFilter` is `true`, so the frontend calls `getAdminRequests('ALL')`.
* The backend scan returns all non-terminal records, which includes `CANCELLATION_REQUESTED` items.
* However, the frontend filters them out due to conflicting predicates in `web/src/components/AdminDashboard.jsx`:
  1. `isCancelledRecord(item)` returns `true` if status is `'CANCELLATION_REQUESTED'`.
  2. `isActiveRecord(item)` returns `false` if `isCancelledRecord` is `true`.
  3. In the `'NEEDS_ACTION'` filter predicate, the code does:
     ```javascript
     if (!isActiveRecord(r)) return false; // Returns false for CANCELLATION_REQUESTED!
     return (
       ...
       stat === 'CANCELLATION_REQUESTED' // Never reached!
     );
     ```
* Consequently, `CANCELLATION_REQUESTED` records are filtered out of all active views (`NEEDS_ACTION`, `ALL`) on the client-side, while being ignored by the backend query for terminal status (`CANCELLED`). They are effectively invisible in the Admin Portal.

---

## 3. Answers to Triage Questions

1. **Are cancellation-pending records stored as REQUEST records, JOB records, cancellation subrecords, or a combination?**
   * They are stored directly on the parent `REQ#` record with `status` set to `"CANCELLATION_REQUESTED"`. Associated child `JOB#` records remain active until admin approval.
2. **Are they under `tog_and_dogs` tenant?**
   * Yes, they are correctly scoped to the tenant (under `company_id = 'tog_and_dogs'`).
3. **Are they omitted from the admin Request List because the admin view only shows final `cancelled` status?**
   * Yes, both because GSI queries for `"CANCELLED"` only return exact matches, and active frontend filters exclude them.
4. **Should there be a separate admin queue/view?**
   * No separate tab is necessary. Pending cancellations are actionable and belong in the **"Needs Action"** queue (which is where they were intended to be).
5. **Should "Cancelled" mean final cancelled only?**
   * Yes, `"Cancelled"` should remain final cancelled only (or include denied), while pending reviews live in `"Needs Action"`.
6. **Are sidebar counts correct?**
   * No, they are incorrect because they use the same filter predicates and exclude `CANCELLATION_REQUESTED`.
7. **Is there any stale/test production data that should be documented?**
   * We will list any found records in the walkthrough.

---

## 4. Proposed Solution (Frontend-Only)

We propose the following frontend changes in `web/src/components/AdminDashboard.jsx`:

1. **Redefine `isCancelledRecord`** to only include final states:
   ```diff
   - const isCancelledRecord = (item) => {
   -   const s = (item.status || "").toUpperCase();
   -   return s === 'CANCELLED' || s === 'DECLINED' || s === 'REJECTED' || s === 'CANCELLATION_REQUESTED' || s === 'CANCELLATION_DENIED';
   - };
   + const isCancelledRecord = (item) => {
   +   const s = (item.status || "").toUpperCase();
   +   return s === 'CANCELLED' || s === 'DECLINED' || s === 'REJECTED' || s === 'CANCELLATION_DENIED';
   + };
   ```

2. **Define a helper `isCancellationPendingRecord`**:
   ```javascript
   const isCancellationPendingRecord = (item) => (item.status || "").toUpperCase() === 'CANCELLATION_REQUESTED';
   ```

3. **Include `isCancellationPendingRecord` in `isActiveRecord`**:
   ```diff
   - const isActiveRecord = (item) => {
   -   if (isDeletedRecord(item) || isArchivedRecord(item) || isCompletedRecord(item) || isCancelledRecord(item) || isDataIssue(item)) return false;
   -   return true;
   - };
   + const isActiveRecord = (item) => {
   +   if (isDeletedRecord(item) || isArchivedRecord(item) || isCompletedRecord(item) || isCancelledRecord(item) || isDataIssue(item)) return false;
   +   return true; // Now returns true for CANCELLATION_REQUESTED because it is not in isCancelledRecord
   + };
   ```

4. **Verify `'NEEDS_ACTION'` Predicate** works automatically:
   Now that `isActiveRecord` returns `true` for `CANCELLATION_REQUESTED`, it will bypass the early return and successfully match:
   ```javascript
   stat === 'CANCELLATION_REQUESTED'
   ```

5. **Expose Cancellation Action Buttons in the Admin UI:**
   Verify that when an admin views a `CANCELLATION_REQUESTED` record, the appropriate action buttons (Approve/Deny) are available.
   * Let's check `getWorkflowState` in `AdminDashboard.jsx`. Currently:
     ```javascript
     // There is no case for CANCELLATION_REQUESTED in the switch (status) statement!
     // We should add a case for CANCELLATION_REQUESTED to return actions:
     // ["APPROVE_CANCELLATION", "DENY_CANCELLATION"] or reuse existing decision modals.
     ```

---

## 5. Next Steps
1. Request Matthew's approval on this triage report.
2. If approved, we will update the implementation plan to target `AdminDashboard.jsx`.
3. Validate by running local build and verifying visibility.
