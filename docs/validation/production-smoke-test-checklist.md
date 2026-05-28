# Repeatable E2E Production Smoke Test Checklist

This repeatable manual validation checklist provides step-by-step instructions to verify both single-day and multi-day booking, scheduling, calendar synchronization, and notification workflows on the Tog & Dogs production system after active code deployments.

---

## 🛠 Prerequisites

1. **Test Accounts:**
   - Active production Client user account (e.g. email registered in Cognito).
   - Active production Staff worker account (with access to staff portal).
2. **Access Required:**
   * AWS Console (CloudWatch logs, DynamoDB table `togs-and-dogs-prod-data`).
   * Google Calendar interface for the assigned staff member.

---

## 📋 Scenario A: Single-Day Booking Flow

Verify that single-day bookings behave backward-compatibly, synchronize with Google Calendar, and trigger friendly single-date notifications.

### 1. Booking Submission
- [ ] Log in as a **Client** in the Client Portal.
- [ ] Submit a single-day request (e.g. for `DOG_WALKING`, June 9, 2026).
- [ ] Confirm request is successfully submitted and displays under the client's request history.

### 2. Admin Approval & Request List Display
- [ ] Log in to the **Admin Dashboard**.
- [ ] Locate the request in the Request List.
- [ ] **Check Service Label:** Confirm the service displays as a friendly label (e.g., *Dog Walking*) instead of the raw database key (`DOG_WALKING`).
- [ ] **Check Date Display:** Confirm it renders as a single day (e.g. *Jun 9, 2026*).
- [ ] Click **Approve Request**. Confirm status changes to `APPROVED`.

### 3. Staff Assignment
- [ ] Click **Assign** next to the approved request.
- [ ] Select your test Staff member and assign.
- [ ] Confirm status changes to `Scheduled with Staff` (`ASSIGNED`).

### 4. Verification Check
- [ ] **Google Calendar:** Confirm exactly one calendar event is created on the assigned worker's Google Calendar with correct dates and notes.
- [ ] **DynamoDB Ledger:** Query `StatusIndex` on `togs-and-dogs-prod-data` for status `sent`. Confirm `VISIT_SCHEDULED` (client) and `STAFF_ASSIGNED` (staff) notifications exist.
- [ ] **Email Content Wording:** Confirm the email contains:
  - Singular terminology ("visit", "sitter will arrive at the scheduled time").
  - The date formatted exactly as: **Jun 9, 2026**.
  - No duplicate notification records.

---

## 📋 Scenario B: Multi-Day Non-Consecutive Booking Flow

Verify that multi-day non-consecutive bookings cascade successfully, merge date context in-memory, format date ranges/lists compactly, and deduplicate notifications.

### 1. Booking Submission
- [ ] Log in as a **Client** in the Client Portal.
- [ ] Submit a multi-day booking with non-consecutive dates (e.g. `OVERNIGHT` care for `Jun 9, Jun 11, Jun 13, 2026`).
- [ ] Confirm submission completes.

### 2. Admin UI Display & Tooltip
- [ ] Log in to the **Admin Dashboard**.
- [ ] **Check Compact Listing:** Confirm the Date column displays the dates compactly as: **Jun 9, 11, 13, 2026** (no repeating month names).
- [ ] **Check Hover Tooltip:** Hover over the date text in the table. Confirm a browser tooltip appears showing the full, unabbreviated list: **Jun 9, Jun 11, Jun 13, 2026**.
- [ ] **Check Service Label:** Confirm the service displays as a friendly label (e.g., *Overnight Care*) instead of the raw database key (`OVERNIGHT`).
- [ ] Click **Approve**.

### 3. Staff Assignment
- [ ] Click **Assign** for the approved parent request.
- [ ] Assign your test Staff member.
- [ ] Confirm all child `JOB` records transition to `ASSIGNED` in the backend.

### 4. Verification Check
- [ ] **Google Calendar Sync:** Confirm exactly **three** distinct calendar events are created/updated on the assigned worker's calendar (one for each of June 9, June 11, and June 13).
- [ ] **Deduplication Check (CloudWatch):** Check `togs-and-dogs-prod-assign` log stream. Confirm that exactly **one** `STAFF_ASSIGNED` and **one** `VISIT_SCHEDULED` notification were dispatched for the entire batch.
- [ ] **In-Memory Context Merging:** Confirm the ledger entry status is `sent`.
- [ ] **Email Content Wording:** Verify in the received emails that:
  - Subject and body are plural-friendly ("booking spanning multiple visits", "complete visit schedule", "visits").
  - Date rendering shows the compact multi-day list: **Jun 9, Jun 11, Jun 13, 2026** (or range if consecutive).

---

## 📋 Scenario C: Visit Cancellation Cascade & Cleanup

Verify that cancellations cascade to all occurrences, clean up calendars, and deliver client-friendly notifications.

### 1. Request Cancellation
- [ ] In the **Admin Dashboard**, click **Cancel** next to your active test booking.
- [ ] Provide a cancellation reason (e.g., "Client schedule change").
- [ ] Confirm status transitions to `Cancelled`.

### 2. Verification Check
- [ ] **Google Calendar Cleanup:** Confirm all 3 child calendar events have been successfully **deleted** from the assigned worker's Google Calendar.
- [ ] **Client-Friendly Subject:** Review the `VISIT_CANCELLED` ledger entry or email. Confirm the subject line is client-oriented (e.g., *Your Overnight Care Visit Has Been Cancelled — Tog & Dogs*) and does not expose internal admin-oriented strings or raw user names in the subject line.
- [ ] **Cancellation Ledger Entry:** Confirm a single cancellation notification record is written to the DynamoDB ledger table with status `sent`.

---

## 📋 Scenario D: Policy Pages & Acceptance Checkbox Validation

Verify that direct navigation to policy pages works correctly, visual formatting displays cleanly, and the client-facing intake form requires legal acceptance before submission.

### 1. Direct Policy Page Navigation
- [ ] Navigate directly to the live production Terms of Use: `/terms` (e.g. `toganddogs.usmissionhero.com/terms`).
- [ ] **Check Rendering & Version:** Confirm the page loads cleanly and displays the `Version v1.0` badge.
- [ ] **Check Layout:** Confirm that bullet lists and numbered sections display with proper spacing and margins (verifying `whiteSpace: 'pre-line'` formatting works).
- [ ] Navigate directly to the live production Privacy Policy: `/privacy`.
- [ ] **Check Rendering & Version:** Confirm the page loads and displays the `Version v1.0` badge.
- [ ] **Check Third-Party Grid:** Confirm the third-party integrations block (detailing Postmark, Google Calendar, AWS, and Cognito) renders formatting cleanly.

### 2. Client Intake Acceptance Check
- [ ] Open the public care booking form: `/book`.
- [ ] Proceed through Steps 1 and 2 to reach Step 3 (Confirmation).
- [ ] **Verify Checklist Links:** Confirm the checkbox label correctly displays links to the **Terms of Use** and **Privacy Policy** that open in a separate browser tab when clicked.
- [ ] **Verify Required Field:** Leave the checkbox unchecked and click **Submit Request**.
- [ ] **Confirm Blocked:** Confirm that the submission is blocked, a red validation error is displayed, and the submit button remains disabled.
- [ ] Check the checkbox and click **Submit Request**. Confirm submission passes.

---

## 📋 Scenario E: Admin Selected-Date Multi-Day Booking Flow

Verify that the administrative "Pick Days" calendar date selector works correctly, creates multiple child jobs, displays the Multi-Day row badge, and synchronizes individual events.

### 1. Manual Booking Creation
- [ ] Log in to the **Admin Dashboard**.
- [ ] Click the **+ New Visit** button to open the administrative booking modal.
- [ ] Choose a test client and pet. Select a service (e.g., *Pet Sitting*).
- [ ] **Change Scheduling Mode:** Toggle the date selector to **Pick Days** mode.
- [ ] Select three non-consecutive dates on the calendar picker grid (e.g. June 10, June 12, June 14, 2026).
- [ ] Confirm the date range summary text displays the selected count correctly (e.g., *3 dates selected*).
- [ ] Click **Create Booking**.

### 2. Request List & Multi-Day Row Badge
- [ ] Navigate to the **Request List** tab.
- [ ] Locate the newly created booking.
- [ ] **Verify Multi-Day Badge:** Confirm a styled, gray **Multi-Day** badge is displayed directly next to the date string.
- [ ] **Verify Window Description:** Confirm the visit window is mapped to a readable label (e.g., *Morning (7–10 AM)* instead of raw `MORNING`).

### 3. Google Calendar & Actions Validation
- [ ] Open the Actions dropdown for this row.
- [ ] **Keyboard dismiss:** Press the **Escape** key. Confirm the actions menu instantly closes.
- [ ] Open the Actions dropdown again. Confirm screen readers announce descriptive contextual options (e.g., *Actions for [Pet Name]*).
- [ ] Click **Assign** and select a test staff member.
- [ ] **Google Calendar Sync:** Check the staff member's Google Calendar. Confirm exactly **three** individual calendar events are created (one for each of June 10, June 12, and June 14) with all care details synced.
