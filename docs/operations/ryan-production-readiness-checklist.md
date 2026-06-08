# Ryan Production Readiness Checklist

This document is a practical validation guide and operational checklist for Matthew and Ryan to execute before opening the Tog & Dogs scheduling portal to broader business testing. It covers end-to-end user paths, admin controls, integrations, and disaster recovery procedures.

---

## Do Not Start Broad Testing Until These Critical Checks Pass
Before inviting external sitters or clients, the following core flows **must** pass verification:
1. **Admin & Sitter Authentication**: Successful secure logins to the Admin Dashboard and Sitter schedules.
2. **Calendar Sync**: Booking creation properly maps to the connected Google Calendar and is visible to staff.
3. **Notifications**: Client intake and cancellation emails are dispatched and received.
4. **Basic Intake Workflow**: Client can sign up, accept terms, and create a single-day booking.
5. **Staff Per-Visit Completion**: Staff can successfully complete a visit from the mobile schedule view.

---

## 1. Authentication & Access

| ID | Checklist Item | What to Verify | Where to Verify | Expected Ready Result | Verification Type | Priority | Status (Pass/Fail/Notes) |
|---|---|---|---|---|---|---|---|
| 1.1 | Admin Login | Admin credentials successfully authenticate. | Web browser `/admin/login` | Renders Admin Dashboard containing active and scheduled bookings. | Manual | Required | `[ ]` |
| 1.2 | Staff Login | Staff/Sitter credentials successfully authenticate. | Web browser `/sitter/login` or preview app | Sitter schedule page displays with "Upcoming Visits" list. | Manual | Required | `[ ]` |
| 1.3 | Client Login | Client credentials successfully authenticate. | Web browser `/login` | Client dashboard displays with intake history and booking request button. | Manual | Required | `[ ]` |
| 1.4 | RBAC Restrictions | Staff or Clients trying to access admin pages directly receive an access denied error. | Access `/admin` route with client session token | Returns `403 Forbidden` error in API and displays access error page in UI. | Manual | Required | `[ ]` |

---

## 2. Google Calendar Integration

| ID | Checklist Item | What to Verify | Where to Verify | Expected Ready Result | Verification Type | Priority | Status (Pass/Fail/Notes) |
|---|---|---|---|---|---|---|---|
| 2.1 | Event Creation | Approving/assigning a booking creates events on the linked Google Calendar. | Google Calendar UI & Admin Dashboard | Events appear with correct dates, times, client names, and notes. | Observable | Required | `[ ]` |
| 2.2 | Staff Scheduling | Staff assignment syncs the Google Calendar event to the assigned staff member. | Google Calendar UI | Assigned staff member is added to the event or synced. | Observable | Required | `[ ]` |
| 2.3 | Active Job Deletion | Deleting/Cancelling/Archiving active bookings deletes events on the Google Calendar. | Google Calendar UI | Active events are deleted automatically. | Observable | Required | `[ ]` |
| 2.4 | Completed Event Guard | Archiving a parent booking preserves the Google Calendar event for completed child jobs. | Google Calendar UI & admin logs | Completed visit events remain intact on the calendar; active ones are removed. | Observable | Required | `[ ]` |

---

## 3. Notification System

| ID | Checklist Item | What to Verify | Where to Verify | Expected Ready Result | Verification Type | Priority | Status (Pass/Fail/Notes) |
|---|---|---|---|---|---|---|---|
| 3.1 | Intake Received | Client receives confirmation email when requesting a booking. | Client email inbox (Postmark) | Structured email containing requested dates, pets, and next steps. | Manual | Required | `[ ]` |
| 3.2 | Booking Approval | Client receives email when booking request is approved by Admin. | Client email inbox (Postmark) | Confirmation email containing scheduled dates, service type, and terms link. | Manual | Required | `[ ]` |
| 3.3 | Visit Cancellation | Client receives cancellation alert if a booking is cancelled. | Client email inbox | Clear cancellation notification. | Manual | Optional | `[ ]` |

---

## 4. Client Intake Flow

| ID | Checklist Item | What to Verify | Where to Verify | Expected Ready Result | Verification Type | Priority | Status (Pass/Fail/Notes) |
|---|---|---|---|---|---|---|---|
| 4.1 | Pet Profile Creation | Client can successfully create pet profiles with details and vet info. | Client dashboard -> Add Pet | Pet record is saved and visible in the client profile. | Observable | Required | `[ ]` |
| 4.2 | Booking Request | Client can request walking/sitting services. | Client dashboard -> Request Booking | Booking request is sent; status shows as `PENDING_REVIEW`. | Observable | Required | `[ ]` |
| 4.3 | Terms Acceptance | Client is prompted to accept Terms of Service & Privacy Policy before submitting. | Booking request page | Checkbox must be ticked; accepted timestamp is saved in the record. | Manual | Required | `[ ]` |

---

## 5. Admin Approval & Assignment

| ID | Checklist Item | What to Verify | Where to Verify | Expected Ready Result | Verification Type | Priority | Status (Pass/Fail/Notes) |
|---|---|---|---|---|---|---|---|
| 5.1 | Review Requests | Admin can view pending booking requests. | Admin Dashboard -> Requests View | Admin can see the requested dates, pets, and client information. | Observable | Required | `[ ]` |
| 5.2 | Sitter Assignment | Admin can assign an eligible staff member to a request. | Admin Dashboard -> Care Card | Dropdown lists available sitters; selecting one updates request status to `ASSIGNED`. | Observable | Required | `[ ]` |
| 5.3 | Status Updates | Request transitions to the correct workflow state in real time. | Admin Dashboard | Booking status changes from `PENDING_REVIEW` to `ASSIGNED` / `APPROVED`. | Observable | Required | `[ ]` |

---

## 6. Multi-Day Booking

| ID | Checklist Item | What to Verify | Where to Verify | Expected Ready Result | Verification Type | Priority | Status (Pass/Fail/Notes) |
|---|---|---|---|---|---|---|---|
| 6.1 | Child Job Expansion | Multi-day request (e.g. Jun 19–21) expands to individual daily child job records. | Admin Dashboard | Single parent request displays, but details panel shows individual day rows. | Observable | Required | `[ ]` |
| 6.2 | Assignment Cascade | Assigning a sitter to a multi-day parent booking cascades the sitter assignment to all child jobs. | Admin Dashboard / DynamoDB | Sitter ID and Sitter Name are populated in all child jobs. | Observable | Required | `[ ]` |
| 6.3 | Rollback Cascade | Changing parent booking status back to `APPROVED` removes the sitter assignment from child jobs. | Admin Dashboard | Sitter name is removed from active child jobs; completed child jobs remain assigned. | Observable | Required | `[ ]` |

---

## 7. Staff Mobile Workflow

| ID | Checklist Item | What to Verify | Where to Verify | Expected Ready Result | Verification Type | Priority | Status (Pass/Fail/Notes) |
|---|---|---|---|---|---|---|---|
| 7.1 | Sitter Schedule View | Sitter can see assigned walks grouped by date on their mobile schedule page. | Sitter preview portal | List shows dates, times, pet name, client details, and "Complete" button. | Manual | Required | `[ ]` |
| 7.2 | Sitter Visit Notes | Sitter can input visit notes when completing a walk. | Sitter preview portal -> Complete | Input text box is functional and notes are required or optional. | Manual | Required | `[ ]` |
| 7.3 | Visit Completion | Sitter completes a visit; the specific day walk disappears from Sitter Upcoming. | Sitter preview portal | Success message displays; completed day disappears from Sitter dashboard. | Manual | Required | `[ ]` |

---

## 8. Per-Visit Completion Visibility

| ID | Checklist Item | What to Verify | Where to Verify | Expected Ready Result | Verification Type | Priority | Status (Pass/Fail/Notes) |
|---|---|---|---|---|---|---|---|
| 8.1 | Progress Indicator | Admin can view completion progress on multi-day bookings. | Admin Dashboard request rows | Displays as `(X/Y Completed)` (e.g. `(1/3 Completed)`). | Observable | Required | `[ ]` |
| 8.2 | Child Job Details | Admin can view individual completion states for child jobs. | Admin Dashboard -> Care Card | Detail list shows Jun 20 as `COMPLETED` by Sitter, and others as `ASSIGNED`. | Observable | Required | `[ ]` |
| 8.3 | Visit Notes View | Admin can view the visit notes submitted by the sitter for completed days. | Admin Dashboard -> Care Card | Visit notes text appears next to the completed job in the details section. | Observable | Required | `[ ]` |
| 8.4 | Client Sanitization | Clients cannot see internal visit notes or sitter metadata until approved. | Client dashboard / API | API response payload does not return `job_completion_summary` or `visit_notes` to clients. | Manual | Required | `[ ]` |

---

## 9. Test Data Cleanup

| ID | Checklist Item | What to Verify | Where to Verify | Expected Ready Result | Verification Type | Priority | Status (Pass/Fail/Notes) |
|---|---|---|---|---|---|---|---|
| 9.1 | Mark Test Booking | Admin can flag test bookings to separate them from real customer data. | Admin Dashboard / Care Card | Highlighted row/border appears in dashboard UI; `is_test_booking = true` in DB. | Observable | Required | `[ ]` |
| 9.2 | Client Redaction | Test data status is hidden from standard client portals. | Client Dashboard | Client does not see the "Test Booking" highlighting or status indicator. | Manual | Required | `[ ]` |
| 9.3 | Archive Booking | Soft-archiving a test booking hides it from active dashboards. | Admin Dashboard | Booking disappears from active dashboard list but remains in database archives. | Observable | Required | `[ ]` |
| 9.4 | Completed Job Safety | Soft-archiving a test booking preserves completed child jobs and notes. | Admin Dashboard / DynamoDB | Completed child job status remains `COMPLETED` and notes are preserved. | Observable | Required | `[ ]` |

---

## 10. Export / Offline Backup

| ID | Checklist Item | What to Verify | Where to Verify | Expected Ready Result | Verification Type | Priority | Status (Pass/Fail/Notes) |
|---|---|---|---|---|---|---|---|
| 10.1 | Export Bookings | Admin can download active schedules for offline backup. | Admin Dashboard -> Export | Downloads a CSV or XLSX file containing active bookings, clients, and sitters. | Observable | Required | `[ ]` |
| 10.2 | Offline Schedule | Exported schedule contains all critical fields for staff dispatch. | Local file reader | File contains client phone, address, scheduled date/time, and pet details. | Manual | Required | `[ ]` |

---

## 11. Known Limitations / Not Yet Ready Items

| ID | Checklist Item | What to Verify | Where to Verify | Expected Ready Result | Verification Type | Priority | Status (Pass/Fail/Notes) |
|---|---|---|---|---|---|---|---|
| 11.1 | Client Visit View | Clients cannot view completed visit notes or progress summaries natively. | Client Portal | Client must contact admin for notes; dashboard shows parent status. | Manual | Optional | `[ ]` |
| 11.2 | Real-time GPS | GPS tracking is not implemented for walks. | Mobile App | Map and GPS elements do not display. | Manual | Optional | `[ ]` |
| 11.3 | Automatic Billing | Automated billing/invoice generation is not integrated. | Client Portal / Admin Portal | Admin handles billing manually outside Tog & Dogs portal. | Manual | Optional | `[ ]` |

---

## Known Limitations Acceptable for Early Testing
Matthew and Ryan can proceed with testing despite the following features being out of scope for early testing:
* **No Client Progress Tracking**: Clients will only see `ASSIGNED` or `COMPLETED` parent status. Sibling progress (`1/3 completed`) is currently admin-only.
* **No Push Notifications**: Sitter alerts are email-only (via Postmark/Google Calendar invites). Device token registrations exist but push payloads are not configured.
* **Manual Billing**: Invoicing is completed manually via email/external platforms.
* **Offline Access**: Sitter mobile workflow requires active network connectivity.

---

## Stop Testing and Escalate If...
If any of these behaviors occur during testing, **stop and escalate immediately**:
* **Data Leakage**: Sitter A is able to see Sitter B's assigned walks, or Client A is able to view Client B's address or phone number.
* **Google Calendar Lockout / Rate Limits**: System fails to write any calendar events or errors out with `Rate Limit Exceeded` during normal status updates.
* **Missing Visit Notes**: Sitter completes a walk with notes, but the notes are blank or fail to save in the Admin Dashboard details panel.
* **Hard Deletions**: Running `Move to Trash` or `Archive` hard-deletes completed jobs from DynamoDB (causing audit history loss).
* **Cognito Session Failures**: Sitters or clients are repeatedly logged out during active tasks, or registration fails to generate profiles.

---

## Post-Test Cleanup Procedure
After completing validation or testing, clean up all test records using the Release 9A controls:
1. **Locate Test Booking**: Select the test booking row in the Admin Dashboard.
2. **Mark as Test**: If not already marked, toggle **Enable Test Mode** in the CareCard controls.
3. **Archive Record**: Click **Archive** and type the reason (e.g., `"Cleanup of testing data"`).
4. **Verify Calendar Cleanup**: Confirm that calendar events for active/uncompleted dates on the Google Calendar have been removed. Completed visit events will remain for historical logging.
5. **Move to Trash**: If permanent removal from main archives is required, click **Move to Trash** on the archived parent booking.
