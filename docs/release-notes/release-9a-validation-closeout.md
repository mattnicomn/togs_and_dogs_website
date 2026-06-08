# Release 9A Validation Closeout

## 1. Release Purpose
The purpose of Release 9A (Admin Booking Lifecycle & Test Data Controls) is to introduce safe admin-only controls for marking test bookings, soft-archiving bookings, unarchiving bookings, and cascading these transitions safely to child jobs without altering or deleting completed visit data or audit history.

* **Planning Commit**: `0eecd02 docs: plan release 9a admin booking lifecycle controls`
* **Implementation Commit**: `6ad0fa1 feat(admin): add booking lifecycle and test data controls`

---

## 2. Files Changed
The following repository files were modified or added for this release:
* [src/backend/common/cascade.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/cascade.py)
* [src/backend/common/auth.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/auth.py)
* [src/backend/handlers/admin_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py)
* [tests/backend/test_r9a_admin_lifecycle.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r9a_admin_lifecycle.py)
* [web/src/api/client.js](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/api/client.js)
* [web/src/components/AdminDashboard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx)
* [web/src/components/CareCard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/CareCard.jsx)

---

## 3. Detailed Behavior

### Backend Behavior
* **MARK_TEST / UNMARK_TEST**: Allows admins/owners to flag a booking as a validation/test record. This sets `is_test_booking = true/false` on the parent request and cascades the flag to all linked child jobs in the database.
* **ARCHIVE**: Allows admins/owners to soft-archive a booking. It marks the parent request as `ARCHIVED` and cascades the status to active child jobs. It explicitly preserves completed child jobs (keeping them `COMPLETED`), retaining completed notes, `completed_by`, and `completed_at` values.
* **UNARCHIVE**: Allows admins/owners to restore a soft-archived booking back to `ASSIGNED`/`APPROVED` status. Active child jobs are restored to `ASSIGNED`, while completed child jobs remain untouched.
* **Archive Metadata**: Tracks who archived the booking (`archived_by`), when it was archived (`archived_at`), and the reason (`archive_reason`).
* **Client/Staff Redaction**: Sanitizes client and staff role responses to hide internal metadata (`is_test_booking`, `archived_by`, `archived_at`, `archive_reason`).

### Web UI Behavior
* **Highlighter & Badges**: Displays a clear `[TEST DATA]` badge and custom row highlighting (dashed red borders) for test bookings in the Admin Dashboard.
* **Archive Confirmation Modal**: Prompts the admin to enter an archive reason before confirming the action.
* **Completed Visit Warnings**: Displays warning badges/texts if the booking contains completed child jobs, explaining that completed data will be preserved.
* **Booking Controls**: Adds controls in the `CareCard` panel for admins/owners to toggle test data status, archive, unarchive, or soft-delete (Move to Trash) bookings.

---

## 4. Test Verification
All automated test suites were successfully run and verified locally:
* **Targeted Release 9A tests**: **Passed (6/6)** in [test_r9a_admin_lifecycle.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r9a_admin_lifecycle.py)
* **Related lifecycle/per-visit/purge tests**: **Passed (46/46)**
* **Full backend test suite**: **Passed (319/319)**
* **Web production build**: **Passed** (`npm run build` compiled client bundle successfully)

---

## 5. Production Deployment
* **Terraform Apply**: `0 added, 11 changed, 0 destroyed`
  * Deployed strictly in-place Lambda package updates.
  * Verified successful updates for all handlers, including the admin Lambda (`togs-and-dogs-prod-admin`).
* **Web Build & S3 Sync**: The production build was successfully synced to `s3://togs-and-dogs-prod-toganddogs-hosting`.
* **CloudFront Invalidation**: Created successfully for distribution `E35L00QPA2IRCY` with paths `/*`.
  * **Invalidation ID**: `I566YHTM5QOW2FVEYEQ1ABRINP`

---

## 6. Production Validation
Validation was performed on the active production booking `REQ#cd211318-aa72-4bfc-829c-f450e6ffe6c2` (Jun 19–21 booking):
1. **Mark Test Booking**: Triggered `MARK_TEST` successfully. Verified `is_test_booking = true` was set on the parent and cascaded to all child jobs in DynamoDB. Confirmed `is_test_booking` is redacted for client roles.
2. **Archive Booking**: Executed `ARCHIVE` with reason `"Cleanup of Release 8Y/8Z/9A validation booking"`.
   * Parent transitioned to `ARCHIVED`.
   * Active child jobs (Jun 19 & Jun 21) transitioned to `ARCHIVED`.
   * Completed child job (Jun 20) remained `COMPLETED` with its visit notes (`"Jun 20 per-visit test"`), `completed_by` (`mattnicomn10@yahoo.com`), and `completed_at` intact.
   * Google Calendar events for the active jobs (Jun 19 & Jun 21) were deleted, while the completed job's (Jun 20) calendar event was preserved.
   * Confirmed archive metadata is redacted for client roles.
3. **Unarchive Booking**: Restored the booking via `UNARCHIVE` to verify correct restoration of active child jobs back to `ASSIGNED` while keeping Jun 20 as `COMPLETED` and clearing out archive metadata.
4. **Final Cleanup**: Re-archived the booking at the end to leave it in the final archived state for cleanup.
5. **Notifications**: Verified no notifications were sent to Postmark during these lifecycle transitions.

---

## 7. Guardrails & Safety
* **Zero Mobile Changes**: Confirmed no changes to mobile files or EAS builds were executed.
* **No Cognito Changes**: Confirmed user directories were not altered.
* **No Manual Database Edits**: All verification was performed through the approved admin API workflow.
* **Hard Purge Guardrails**: Confirmed that `test_rbac_and_purge_safety.py` continues to pass, ensuring active bookings cannot be hard-purged.

---

## 8. Final State & Cleanup
* **Jun 19–21 validation booking**: Left in an `ARCHIVED` state as a safe, clean cleanup outcome.
* **Repository Status**: Clean and synchronized with `origin/main`.

---

## 9. Deferred Items
* Optional future UI/UX polish after Ryan's admin portal review.
* Optional audit history log/portal tab to view archived entries.
* Optional CSV/JSON exports including custom archive reason fields.
