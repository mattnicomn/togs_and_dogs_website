# Release 9A Planning: Admin Booking Lifecycle & Test Data Controls

## 1. Executive Summary
As we transition from implementing staff per-visit completions to operational hardening, the admin panel requires robust lifecycle controls. Multiple production validation bookings currently exist in the database (such as the `Jun 19–21` booking used for Release 8Y/8Z). Admin tools must be updated to easily archive, mark as test data, and safely clean up validation records without requiring manual DynamoDB intervention.

---

## 2. Current Lifecycle & Data Model Analysis

### 2.1. Status Mappings & Transitions
* **Parent Request (`REQ#`) Statuses**: `APPROVED`, `BOOKED`, `ASSIGNED`, `COMPLETED`, `CANCELLED`, `CANCELLATION_REQUESTED`, `CANCELLATION_DENIED`, `ARCHIVED`, `DELETED`, `PENDING_REVIEW`, `DECLINED`, `PROFILE_CREATED`, `READY_FOR_APPROVAL`, `QUOTED`.
* **Child Job (`JOB#`) Statuses**: `JOB_CREATED`, `ASSIGNED`, `COMPLETED`, `CANCELLED`, `ARCHIVED`, `DELETED`.
* **Transition Logic**: Currently, when an admin changes a parent request status, the utility `cascade_status_to_job` maps the new parent status to a job equivalent and updates all child jobs.

### 2.2. Archive, Delete, and Purge Operations
* **ARCHIVE**: Sets the parent `status = ARCHIVED` and cascades it to all child jobs.
* **DELETE (Soft Delete)**: Sets the parent `status = DELETED` and adds `deleted_at`. Accidental deletes are prevented on active requests (`ASSIGNED`, `SCHEDULED`, `BOOKED`).
* **PURGE (Hard Delete)**: Permanently deletes the parent `REQ#` record and does a best-effort delete of all child jobs listed in `job_ids`. Only allowed if the record is already in `DELETED` or `TRASH` status.

---

## 3. Current Test Data Challenges
* **Identification**: Test bookings are currently identified ad-hoc via placeholder text (e.g. `"test closing visit"`) or mock emails. There is no structured attribute to flag test records.
* **Metadata & Notes**: Test records contain actual completion metadata (`completed_at`, `completed_by`) and visit notes (`"Jun 20 per-visit test"`).
* **Risks**: Leaving test bookings active causes them to pollute staff schedule views, clutter Google Calendar, and distort operational reports or billing metrics.

---

## 4. Proposed Admin Controls

### 4.1. Booking Archive & Restoration Rules
* **Archive Entire Booking**: When archiving a parent request, the system should soft-archive child jobs but **skip child jobs that are already in `COMPLETED` status**. This preserves historical completed visits and notes for audit purposes.
* **Archive Reason**: Admins must be prompted to enter an `archive_reason` (e.g., "Validation complete", "Customer cancelled", "Duplicate").
* **Restoration**: Restoring an archived booking will transition the parent request and previously pending child jobs back to active status, while leaving completed child jobs untouched.

### 4.2. Test Booking Flag
* Introduce `is_test_booking` boolean attribute on `REQ#` and `JOB#` records.
* Mark bookings as test data to filter them out from standard operational queues and reports.

### 4.3. Delete Guardrails
* Prevent hard purge of any record unless it is already in `DELETED` or `TRASH` status.

---

## 5. Per-Visit Lifecycle Controls
* **Status Visibility**: Display the daily status of each individual visit within the request detail CareCard drawer.
* **Visit-Level Cancellation**: Enable admins to archive or cancel individual child jobs without archiving the entire parent request.
* **Undo Completion (Deferred)**: Correcting mistaken completions (e.g. reverting a child job from `COMPLETED` back to `ASSIGNED`) requires recalculating `completed_count` and rolling back parent status. To minimize risk, this will be deferred to a future release.

---

## 6. Implementation Architecture

### 6.1. Backend API Extensions
We will extend the existing `POST /admin/requests` handler actions rather than creating new endpoints:
1. **`ARCHIVE` Action**:
   * Accepts an optional `archive_reason` in the payload.
   * Updates `archive_reason`, `archived_at` (ISO timestamp), and `archived_by` (admin email) on the parent request.
   * Updates `cascade_status_to_job` to skip child jobs in `COMPLETED` status.
2. **`MARK_TEST` Action**:
   * Sets `is_test_booking = true` on the parent request and cascades the flag to all linked child jobs.
3. **`UNARCHIVE` Action**:
   * Clears `archive_reason`, `archived_at`, and `archived_by`.
   * Restores parent and pending child jobs to `ASSIGNED` or `APPROVED` based on their assignment state.

### 6.2. Web Admin UX updates
* **Row-Level Actions**: Add "Mark as Test" and "Archive Booking" options to the Request list row dropdowns.
* **CareCard Detail Drawer**:
  * Add a lifecycle action group (Archive, Move to Trash, Toggle Test status).
  * Display a prominent **"TEST DATA"** watermark or badge on test bookings.
  * Prompt for an archive reason when performing an archive action.
  * Display warning if archiving a request that contains completed visits.
* **Excel Export**: Exclude test bookings from standard tabs and export them only if requested, or tag them clearly in the export.

---

## 7. Security, Permissions & Safety
* **Role Enforcement**: Restrict archive, delete, and test actions to the `owner` and `admin` roles in the backend.
* **Client Redaction**: Ensure `is_test_booking` and `archive_reason` are added to `client_sensitive_fields` in `auth.py` so they are never leaked to client portal responses.
* **Notifications**: Ensure no Postmark email notifications are triggered when archiving or marking a booking as test data.
* **Google Calendar**: Google Calendar events for pending child jobs will be deleted when archived. Completed child job events will remain on the calendar for staff audit records.

---

## 8. Verification & Test Plan
* **Targeted unit tests** (`tests/backend/test_r9a_admin_lifecycle.py`):
  * Test parent archiving cascades to pending child jobs but skips completed ones.
  * Test un-archiving restores pending child jobs and preserves completed jobs.
  * Test `is_test_booking` and `archive_reason` validation and audit logging.
  * Test client role redaction of lifecycle metadata.
* **Web Build Verification**:
  * Run `npm run build` in `/web` to ensure no frontend bundle compilation issues.

---

## 9. Deployment & Rollback

### 9.1. Deployment Scope
* **Backend Lambda**: Yes (redeploy `admin` Lambda function).
* **Terraform Configuration**: No infrastructure changes expected (reuses existing `/admin/requests` POST route).
* **Web Frontend**: Yes (sync static assets to S3 and invalidate CloudFront cache).
* **Mobile / EAS build**: No mobile updates required.

### 9.2. Rollback
* **Backend**: Revert the `admin` Lambda to the previous zip package.
* **Frontend**: Restore the S3 hosting bucket to the prior build release.

---

## 10. Clean Up Workflow for Jun 19-21 Booking
Once Release 9A is deployed, the `Jun 19–21` booking (`REQ#cd211318-aa72-4bfc-829c-f450e6ffe6c2`) will be cleaned up safely via the UI using these steps:
1. Mark the booking as a test booking (`is_test_booking = true`).
2. Perform the Archive action, entering the reason: `"Completed Release 8Y/8Z validation"`.
3. Verify that the parent request and child jobs for Jun 19 and Jun 21 are archived.
4. Verify that the Jun 20 completed child job remains `COMPLETED` with its visit notes intact.

---

## 11. AG Implementation Prompt

> [!WARNING]
> **DO NOT RUN THIS IMPLEMENTATION PROMPT UNTIL APPROVED BY MATTHEW**

```
AG — implement Release 9A: Admin Booking Lifecycle & Test Data Controls.

Backend + web frontend changes. No Terraform resource changes. No mobile changes.

=== PHASE 1: Backend Lifecycle & Cascade Updates ===

1. In src/backend/common/cascade.py, update cascade_status_to_job to:
   - Check if a child job status is COMPLETED before updating.
   - Skip updating status to ARCHIVED or DELETED if the job is already COMPLETED.
   - Support cascading an 'is_test_booking' attribute to child jobs.

2. In src/backend/handlers/admin_handler.py, update the POST /admin/requests handler (where action in ['ARCHIVE', 'DELETE', 'PURGE'] is processed):
   - For 'ARCHIVE':
     * Read 'archive_reason' from the request body.
     * Update the parent request with 'archive_reason', 'archived_at' (timestamp), and 'archived_by' (caller email).
   - Add a 'MARK_TEST' action that sets 'is_test_booking = true' on the parent REQ and cascades it to all child jobs.
   - Add an 'UNARCHIVE' action that clears 'archive_reason', 'archived_at', and 'archived_by' and restores status.

3. In src/backend/common/auth.py, add 'is_test_booking', 'archive_reason', 'archived_at', and 'archived_by' to client_sensitive_fields so they are redacted from client responses.

=== PHASE 2: Web Frontend — List & Drawer Controls ===

4. In web/src/components/AdminDashboard.jsx:
   - Add "Mark as Test" and "Archive" options to the individual request row action dropdown.
   - Highlight test bookings with a prominent visual badge or row style.

5. In web/src/components/CareCard.jsx:
   - Display the daily status of each individual child job in the Visit Schedule.
   - Add a lifecycle control section in the Overview tab enabling admins to Archive, Move to Trash, or Toggle Test status of the booking.
   - Prompt with a text input for 'Archive Reason' when archiving.
   - Warn the user if they are archiving a booking with completed visits.

=== PHASE 3: Tests & Validation ===

6. Create tests/backend/test_r9a_admin_lifecycle.py verifying:
   - Archiving parent request cascades to pending jobs but skips completed ones.
   - Restoring parent booking preserves completed jobs.
   - Client role redacts test and archive metadata.
   - Owner/admin authorization checks.

7. Run:
   C:\Users\mattn\Desktop\lambda_package\python.exe -m pytest tests/ -v
   npm run build (in web/)

Report results and pause for approval.
```
