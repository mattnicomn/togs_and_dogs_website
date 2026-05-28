# Tog & Dogs Operations Portal — Admin Operations Quick Reference

**Last Updated:** Release 7Q  
**Audience:** Ryan (Business Owner), Admins, and Operations Staff  
**System Status:** Production Ready  

Welcome to your Operations Portal. This quick-reference guide is designed to help you confidently manage the day-to-day pet care schedule, client records, and service requests. It is written in plain language to serve as a reliable daily companion.

---

## 1. Purpose of the Operations Portal

The portal (accessible at [toganddogs.usmissionhero.com](https://toganddogs.usmissionhero.com)) is the central hub for Togs & Dogs operations. It handles:
* Managing client intake and pet profile information.
* Processing bookings (single-day, consecutive multi-day, or non-consecutive dates).
* Assigning staff and automating synchronization with Google Calendar.
* Dispatching transactional email notifications via Postmark.
* Organizing client profiles, including both self-service portal users and offline clients managed by staff.

---

## 2. Public Intake Flow Overview

When a new client visits the public site and registers their details on the intake form:
1. **Intake Data & Pet Details:** The client inputs contact information, pet emergency profiles, and schedules.
2. **Acceptance Required:** To submit the form, clients must check the box to agree to the **Terms of Use** and acknowledge the **Privacy Policy**. This is strictly enforced by both the web page and the secure backend server.
3. **Queue Placement:** Once submitted, the request is placed directly into the **Intake Queue** (marked as `PENDING_REVIEW` in the backend database) for admin evaluation.

---

## 3. Request List Basics

The **Request List** tab is your main dashboard. It lists all active bookings, intake forms, and scheduling records.
* **Filter Views:** You can filter the list using the filter panel (e.g., *Intake Queue*, *Needs Assignment*, *Scheduled*, *Completed*, *All*, *Trash*, *Data Issues*).
* **Multi-Day Badge:** If a client request spans multiple dates, a **Multi-Day** badge displays next to the date column, warning you that this request covers multiple scheduled visits.
* **Friendly Service Labels:** All raw system codes are automatically displayed as clean, readable text (e.g., `PET_SITTING` is displayed as **Pet Sitting**).
* **Time Windows:** Visit windows are presented with helpful time slots:
  * `Morning (7–10 AM)`
  * `Midday (10 AM–2 PM)`
  * `Afternoon (2–5 PM)`
  * `Evening (5–8 PM)`
  * `Anytime`
* **Actions Dropdown:** Clicking the **Actions** button opens a menu of guided workflows specific to the item's current state.

---

## 4. Request Statuses and What They Mean

Every request moves through a controlled lifecycle. Understanding the statuses helps you keep operations moving:

| Status Label (UI) | Raw Database Status | Operational Meaning |
|-------------------|---------------------|---------------------|
| **Needs Action** | `PENDING_REVIEW` | A newly submitted request that needs admin review. |
| **Needs M&G** | `MEET_GREET_REQUIRED` | Request is on hold until a Meet & Greet is scheduled or completed. |
| **Quoted** | `QUOTED` | Pricing quote has been calculated and sent to the client. |
| **Approved** | `APPROVED` | Request is approved and ready for staff assignment. |
| **Scheduled with Staff** | `ASSIGNED` | Request has a staff member assigned and is fully synced to Google Calendar. |
| **Completed** | `COMPLETED` | Service was delivered successfully. |
| **Cancelled** | `CANCELLED` | Booking was cancelled (by admin or client). Calendar events are cleared. |
| **Archived** | `ARCHIVED` | Saved historical record (safely hidden from standard queues). |
| **Trash** | `DELETED` | Moved to the trash bin (can be restored or permanently purged). |

### Text-Based Status Lifecycle Flowchart
```text
  [Intake Form Submissions]
             ↓
     PENDING_REVIEW  ←─────────── (Restore) ────────────┐
             │                                          │
             ├──→ MEET_GREET_REQUIRED                   │
             │            ↓                             │
             │       APPROVED  ←────────── (Restore) ───┼───┐
             │            │                             │   │
             └───────────┬┴─────────────┐               │   │
                         │              │               │   │
                         ↓              ↓               │   │
                      APPROVED       CANCELLED ─────────┤   │
                         │              │               │   │
                         ↓              ↓               │   │
                      ASSIGNED ─────→ CANCELLED ────────┘   │
                         │                                  │
                         ├─→ COMPLETED ─────────────────────┤
                         │                                  │
                         └─→ ARCHIVED / DELETED (Trash) ────┘
                                        │
                                        ↓
                                  PURGED FOREVER
```

---

## 5. Multi-Day Bookings and Child "JOB" Behavior

When a client submits a request covering multiple non-consecutive or consecutive dates:
1. **Parent Request:** A single parent request (`REQ`) acts as the container holding overall customer choices, selected dates, and notes.
2. **Child Jobs:** The backend system automatically spawns a separate child Job record (`JOB`) for each scheduled date.
3. **Operational Alignment:**
   - **Scheduling:** You manage and assign staff at the parent level, and the system cascades that assignment to all child jobs automatically.
   - **Status Cascade:** Moving the parent request to `CANCELLED`, `ARCHIVED`, or `DELETED` automatically cascades the status change to every child job, ensuring calendar slots are immediately freed up.

---

## 6. Approving Requests

To approve a new client booking:
1. Navigate to the **Intake Queue** tab.
2. Select **Actions** $\to$ **Approve** next to the target request.
3. The system will transition the request to `APPROVED`, writing a notification ledger entry to queue the client's confirmation email.

---

## 7. Assigning Staff

Staff assignment triggers important backend updates:
1. Select **Assign Staff** on an approved request.
2. Choose the staff member from the dropdown menu.
3. **Automated Calendar Sync:** The portal instantly syncs the dates, times, and care instructions to the assigned staff member's Google Calendar.
4. **Automated Notification:** A single `STAFF_ASSIGNED` email is dispatched to the staff member, and a `VISIT_SCHEDULED` email is dispatched to the client (multi-day bookings are automatically merged into a single consolidated email to avoid inbox spam).

---

## 8. Google Calendar Expectations

* **Automatic Updates:** Any staff assignment, reassignment, or cancellation automatically creates or deletes events on the staff Google Calendar.
* **Manual Alteration Warning:** Avoid deleting or editing system-synced events directly within the Google Calendar interface. Doing so can cause synchronization gaps. If you need to change a booking, always perform the action inside the **Operations Portal**.
* **Reconnection Badge:** If the Google integration loses access, a red alert badge will appear in the settings panel. Click **Reconnect** to securely restore the link.

---

## 9. Postmark/Email Notification Expectations

* **Automated Transactions:** Emails are sent automatically for request reviews, approvals, worker assignments, schedule modifications, and cancellations.
* **Ledger Auditing:** Every email is logged in the database ledger before sending. If a client claims they did not receive an email, you can check the logs to verify delivery status.
* **Suppression Protection:** Postmark protects against spamming. If a client address bounces repeatedly, Postmark will place it on a suppression list. You can contact support to clear bouncers.

---

## 10. Offline / Staff-Assisted Client Handling

For clients who prefer calling or texting instead of using the online client portal:
1. Navigate to **Client Management** and click **Create Profile**.
2. Leave the email field blank. The system will flag this profile as an **Offline Client**.
3. **Manual Bookings:** You can now click **+ New Visit** from the dashboard, select the offline client, and book care on their behalf.
4. **Communication:** Automated emails will not be sent to offline profiles. Staff must communicate booking updates to these clients directly via phone or text.

---

## 11. Client & Staff Management Basics

* **Staff Dispatch Colors:** When creating staff profiles, select a distinct scheduling color (e.g. green, orange, rust) to help you visualize assignments on the calendar.
* **Worker Login Credentials:** You can invite staff members to link their Cognito profiles. If a staff member forgets their password, you can click **Reset Password** or **Set Temp Password** to assist them.
* **Disabling Profiles:** If a client leaves Togs & Dogs or a staff member resigns, click **Disable Profile** to securely block them from logging in, while preserving their historical booking logs for recordkeeping.

---

## 12. Cancel / Archive / Delete / Restore / Purge Safety Guidance

Managing request cleanup is governed by strict safety rules:

* **Cancel:** Use this when a scheduled booking is cancelled. It cleans up calendar slots and emails the client.
* **Archive:** Use this for historical, completed bookings that you want to keep for auditing but hide from the active Request list.
* **Delete (Move to Trash):** Moves a cancelled or archived record to the **Trash** view. Active, scheduled bookings cannot be deleted without being cancelled first.
* **Purge Forever (Dangerous):** Permanently deletes the record from the database. This action **cannot be undone**. To prevent accidents, the portal forces you to manually type the record's ID to confirm.
* **Restore:** If you accidentally trash or cancel a record, select **Restore to Approved** or **Reopen to Pending** to immediately revive the request and restore sync.

---

## 13. Recommended Daily & Weekly Operating Rhythm

To maintain smooth business operations, we recommend the following routine:

### Daily Checklist (Morning & Afternoon)
* [ ] **Review Intake Queue:** Process any newly submitted client requests.
* [ ] **Assign Pending Bookings:** Ensure all approved requests are assigned to staff (checking that no "Needs Assignment" alerts are active).
* [ ] **Calendar Check:** Visually review the Master Scheduler to make sure staff bookings align.

### Weekly Checklist (Friday)
* [ ] **Historical Archive:** Archive completed visits from the past week to keep the dashboard clean.
* [ ] **Verification:** Confirm Google Calendar sync and email logs are clean with no active alerts.
* [ ] **Export Data:** Click the **Export** button to download a weekly spreadsheet backup of client records and visit summaries.

---

## 14. When to Contact Technical Support

> [!IMPORTANT]
> **Who to Contact:**
> * For business operations or standard client questions: **Ryan**
> * For database errors, hosting issues, or developer requests: **Matthew / Support**

Contact technical support immediately if:
1. The portal displays continuous 500 error pages.
2. The Settings panel indicates that Google Calendar connection is blocked or failing to authorize despite multiple reconnection attempts.
3. The Postmark email ledger indicates that emails have stopped sending completely.
4. An accidental database deletion has occurred and requires recovery.
