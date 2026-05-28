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
