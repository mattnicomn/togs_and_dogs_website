# Release Notes: Workflow Calendar Sync & Message Fix

## Issue 1: Stale M&G Errors Persisting After Success
**Root Cause:**
Action handlers in `AdminDashboard.jsx` were not clearing their error states at the beginning of an execution. As a result, if a previous interaction resulted in an error (e.g. M&G validation), the stale error text would occasionally remain on the screen even after the underlying record had successfully moved forward (e.g. `QUOTED → APPROVED`).

**Resolution:**
- Added `setError(null)` and `setModalError(null)` to the beginning of all asynchronous action handlers (`handleBulkUpdate`, `submitDecision`, `handleQuickVerify`, `_handleAdminAction`, `handlePurgeRecord`, `handleBulkPurge`).
- Confirmed that successful actions properly set success toasts and dismiss stale errors.

---

## Issue 2: Google Calendar Event Creation Timing & Formatting
**Root Cause:**
Previously, the backend (`review_handler.py`) was automatically creating a Google Calendar event the moment a request moved to `APPROVED`. This is functionally incorrect because an "Approved" request has not yet been scheduled with a specific staff member. Additionally, the event was missing important details and used a hardcoded `[TEST]` prefix.

**Decision & Resolution:**
- Removed Calendar sync from the `APPROVED` step. `APPROVED` now means the request is accepted and ready for staffing, but not yet scheduled.
- Migrated Calendar sync to the **Staff Assignment** workflow (`assignment_handler.py`). Calendar events are now created or updated when a request moves to `ASSIGNED` or `SCHEDULED`.
- Upgraded the Calendar event structure in `google_calendar.py`:
  - **Title:** `Tog and Dogs - {Pet Name} / {Client Name} - {Service Type}`
  - **Date:** Uses the requested `start_date`
  - **Description:** Now includes Client Name, Pet Name, Service Type, Assigned Staff, Service Window (`preferred_time`), Request ID, and Pet Notes.
- Implemented **Graceful Degradation** for the Calendar integration: If the Google OAuth token is disconnected or expired, the backend now catches the error, allows the staff assignment to complete successfully, and returns a warning: `"Assigned successfully, but calendar sync is not connected."`
- **Idempotency:** When a staff assignment is updated, the system reuses the existing `google_event_id` to update the calendar instead of creating duplicates.

## Deployment Details
- **Production URL:** https://toganddogs.usmissionhero.com/admin
- **Commit Hash:** [to be populated]
- **CloudFront Invalidation ID:** `IA0X2Q2GFE2GE0I13EV1ZZ5IIB`

## Validation Results
- [x] `QUOTED → APPROVED` correctly shows success and NO calendar event is created.
- [x] APPROVED records properly sit in the "Approved" queue.
- [x] "Assign Staff" moves the record to `ASSIGNED` and creates the rich Google Calendar event.
- [x] Re-assigning staff updates the existing calendar event (duplicate protection).
- [x] Stale errors disappear immediately when actions begin.
