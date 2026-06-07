# Release 8Z: Admin Web Per-Visit Completion Visibility Closeout

## 1. Release Purpose
Implementation of Admin Web Per-Visit Completion Visibility for multi-day bookings. This release introduces a completion progress indicator in the request list view and a visual daily breakdown schedule within the request details CareCard drawer. It also implements backend enrichment to provide detailed per-visit statistics for admin users while ensuring strict data isolation and redaction for clients.

## 2. Key Commits
* **Planning**: `3b590f9 docs: plan release 8z admin per visit completion visibility`
* **Implementation**: `c36bcd2 feat(admin): show per-visit completion progress`

## 3. Files Changed Across Release
* **Backend**:
  * [admin_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py)
  * [auth.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/auth.py)
  * [test_r8z_admin_per_visit_visibility.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r8z_admin_per_visit_visibility.py) (New file)
* **Web Frontend**:
  * [AdminDashboard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx)
  * [CareCard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/CareCard.jsx)

## 4. Backend Behavior
* **Single Request GET Enrichment**: When retrieving single request details, the backend queries each child job's ID and aggregates them into a `job_completion_summary` field. It contains counts (`total`, `completed`, `pending`) and a list of jobs containing `job_id`, `occurrence_date`, `occurrence_index`, `status`, `worker_id`, `worker_name`, `completed_at`, `completed_by`, and `visit_notes` (sorted chronologically).
* **Client Role Sanitization**: The `job_completion_summary` and `visit_notes` fields are added to `client_sensitive_fields` in `auth.py`. If a client role initiates a request, these fields are set to `None`/`null` to prevent exposure of internal sitter completion data and notes.
* **Parent request completed_count**: The job completion handler (`POST /admin/job/complete`) was updated to update `completed_count` using DynamoDB's `if_not_exists` atomically and idempotently.

## 5. Web Frontend Behavior
* **Request List Badge**: Progress indicator (`X/N visits done`) is shown on multi-day request rows. Utilizes green color-coding for fully completed bookings and blue/indigo for active/partial bookings.
* **CareCard Detail Drawer Breakdown**: Renders a dedicated "Visit Schedule" section in the Overview tab displaying checkmarks (✅) for completed dates and hourglass icons (⏳) for pending dates.
  * *Completed Visits*: Show date, status, completed by, timestamp, and notes.
  * *Pending Visits*: Show date, status, and assigned worker.
* **Preservation of 8V Notes**: The parent-level completion information and notes remain separate and preserved for backward compatibility.
* **Excel Export Mapping**: Added `Completed At`, `Completed By`, and `Visit Notes` columns to the **Staff Assignments** sheet, and `Visits Completed` summary count to the **All Requests** sheet.

## 6. Deployment Details
* **Terraform Plan**: `Plan: 0 to add, 11 to change, 0 to destroy` (Lambda package and source hash updates).
* **Terraform Apply**: `Resources: 0 added, 11 changed, 0 destroyed` (Successfully updated the `admin` Lambda function).
* **Web Frontend Build**: Vite production build completed successfully via `npm run build` in `/web`.
* **S3 Hosting Sync**: Synced Vite distribution folder (`dist/`) to `s3://togs-and-dogs-prod-toganddogs-hosting`.
* **CloudFront Invalidation**: Invalidation `I30QOLSMASEBVA9OFQQEBQP796` created for distribution `E35L00QPA2IRCY` with paths `/*`.

## 7. Production Validation Results
Validation performed using the partially completed Jun 19–21 booking (`REQ#cd211318-aa72-4bfc-829c-f450e6ffe6c2`):
* **Admin Detail Fetch**: Returns `job_completion_summary` containing `total = 3`, `completed = 1`, and `pending = 2`.
* **Jun 20 Child Job Status**: `COMPLETED`, completed by `mattnicomn10@yahoo.com`, with notes `"Jun 20 per-visit test"`.
* **Jun 19 and Jun 21 Child Job Statuses**: `ASSIGNED` to `Staff Test User` (`mattnicomn10@yahoo.com`).
* **Parent Request Status**: Correctly remains in `ASSIGNED` status.
* **Client Redaction**: Invoking GET with a client role successfully redacts `job_completion_summary` and `visit_notes`.
* **Side-Effects**: Zero email notifications (Postmark) or calendar synchronizations (Google Calendar) were triggered.

## 8. Validation Checks Summary
* **Targeted visibility tests**: ✅ **PASS** (5/5 passed).
* **Full backend suite**: ✅ **PASS** (313/313 passed).
* **Web production build**: ✅ **PASS** (Vite build successful).

## 9. Compliance & Guardrails
* **No Mobile changes**: Decoupled from the mobile repository; no EAS builds required.
* **No Infrastructure changes**: No new routes or API Gateway resources were created.
* **Data Isolation**: Internal sitter notes are redacted for clients.
* **Zero notification/calendar operations**: Partial completion logic runs silently without customer or calendar updates.

## 10. Deferred Items
* Optional additional web polish after Admin/Ryan review.
* Optional cleanup/archiving of test bookings later.
