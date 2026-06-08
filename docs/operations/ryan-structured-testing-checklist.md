# Ryan Structured Testing Checklist — Production Validation

## 1. Testing Purpose
This checklist is designed for you (Ryan) to verify the system's live operation on the production environment. This structured test ensures that the administrative workflows, staff scheduling, Google Calendar syncing, email notifications, and Daily Sitter Dispatch Excel exports function perfectly prior to rolling out the system to actual clients and sitters.

## 2. Test Accounts and Sign-in Expectations
Please use only the following verified production test accounts:

* **Administrator Account**:
  * **Email**: `admin@toganddogs.com`
  * **URL**: [Admin Portal](https://toganddogs.usmissionhero.com/admin)
* **Client Test Account** (for intake submissions):
  * **Email**: `brearockwell@gmail.com`
  * **Client Name**: Justbeingbrea (Brea Rockwell)
  * **Pet Name**: Joey Rockwell
* **Staff / Sitter Test Account** (for schedule & completions):
  * **Email**: `mattnicomn10@yahoo.com`
  * **Staff Name**: Staff Test User

---

## 3. Scope of Testing

### 3.1. What to Test
* Google Calendar Integration status display.
* Submitting new service requests from the Client Portal.
* Approving request transitions from `Pending Review` to `Meet Greet Completed` to `Approved`.
* Assigning sitters and verifying schedule updates.
* Verifying automated emails (intake received, booking approved, staff assigned).
* Checking sitter visibility and per-visit completions.
* Generating and checking the **Daily Dispatch** Excel export.
* Archiving test data to restore the database to a clean state.

### 3.2. What NOT to Touch
* **No Real Customers**: Do not modify, edit, or delete any real customer accounts, actual client profiles, or scheduled jobs.
* **No Real Emails**: Do not input any actual customer email addresses in your test bookings.
* **No Disconnections**: Do not disconnect the Google Calendar account from the Admin dashboard status card.
* **No Purge Actions**: Do not perform any manual deletions of database tables or records.

---

## 4. Step-by-Step Testing Walkthrough

### Phase 1: Admin Health Check
1. Log into the [Admin Portal](https://toganddogs.usmissionhero.com/admin) as `admin@toganddogs.com`.
2. Look at the top banner or the **System Integrations** card on the dashboard.
3. Confirm that the status badge displays a green **CONNECTED** state.

### Phase 2: Client Intake & Policy Acceptance
1. Log into the Client Portal as `brearockwell@gmail.com` (or submit a public intake form).
2. Create a new test request for **Joey Rockwell**:
   * **Single-day walk**: Scheduled for tomorrow.
   * **Multi-day care**: Scheduled for 3 consecutive days starting the day after tomorrow.
3. Check the **Terms of Use** and **Privacy Policy** boxes to accept.
4. Submit the requests and verify that a confirmation pop-up is shown.

### Phase 3: Administrative Approval (Meet & Greet Rule)
1. Go back to the Admin Dashboard.
2. Select your newly submitted test request (it will display a status of `Pending Review`).
3. **Verify Meet & Greet**:
   * *Note: The system blocks approvals for clients who haven't completed a Meet & Greet.*
   * In the request detail view, click the **Verify Meet & Greet** button.
   * Confirm the request status updates to `M&G Completed`.
4. **Approve Request**:
   * Click the **Approve Request** button.
   * Verify the status changes to `Approved` and individual child visits (jobs) are generated.

### Phase 4: Sitter Assignment & Sync Checks
1. Select the approved request.
2. Under the assignment dropdown, assign **Staff Test User** (`mattnicomn10@yahoo.com`).
3. Click **Save Assignment** and confirm the status changes to `Assigned`.
4. **Google Calendar Check**:
   * Log into the calendar associated with `mattnicomn10@yahoo.com` or check the Admin synced calendar.
   * Confirm that new event blocks have been created matching the visit dates and details.
5. **Postmark/Email Check**:
   * Check the inbox of `mattnicomn10@yahoo.com` (Sitter) and `brearockwell@gmail.com` (Client).
   * Confirm they received their respective sitter assignment and booking approval emails.

### Phase 5: Sitter Workflows & Completions
1. Log into the Staff view as `mattnicomn10@yahoo.com`.
2. Confirm the assigned test visits appear in the agenda list.
3. Open the first visit.
4. Click **Complete Visit** and type feedback notes (e.g., *"Walk completed. Joey did great!"*).
5. Submit the completion.
6. Switch back to the Admin Dashboard and verify:
   * The visit status shows **Completed** (green checkmark).
   * The parent request progress count displays completion progress (e.g., `1/1` or `1/3`).
   * The notes you typed are visible to you in the admin history.

### Phase 6: Daily Dispatch Export
1. On the Admin Dashboard, click the **Export Data** button.
2. Download the generated Excel workbook.
3. Open the spreadsheet and verify:
   * **First Sheet**: Confirm the first sheet is titled **Daily Dispatch**.
   * **Rows**: Check that the active test bookings are listed under the correct date, sorted by sitter, and display their current status (e.g., "✅ Done" or "⏳ Pending").
   * **Filters**: Confirm that test data marked test and archived bookings are excluded from the first sheet.

### Phase 7: Archive and Test Data Cleanup
1. In the Admin Portal, find your test request.
2. Click **Archive Request** and type a cleanup reason (e.g., *"Ryan test cleanup"*).
3. **Calendar Check**: Confirm that future active calendar events for this request are deleted from Google Calendar, while the completed visit event remains preserved.
4. **Data Verification**: Confirm that completed visit details are preserved in the archive logs.

---

## 5. Pass/Fail Definitions and Reporting Issues

### 5.1. Success Criteria (PASS)
* You can log in, accept policies, submit requests, satisfy Meet & Greet, approve, assign, complete, and archive without any errors.
* Google Calendar events sync automatically on assignment and delete on archive.
* The Excel export places `Daily Dispatch` on the first tab and filters items correctly.

### 5.2. Failure Criteria (FAIL)
* System returns a `500 Server Error` or hangs during any button press.
* Meet & Greet cannot be completed or blocks approval even after verification.
* Calendar events are duplicated, fail to sync, or are not deleted on archiving.
* Sitter feedback notes fail to save or display in the Admin Dashboard.
* The Daily Dispatch export does not show the first sheet or includes archived data.

### 5.3. When to Stop and Report
> [!IMPORTANT]
> Stop immediately and report the issue to Matthew if:
> * A real client/customer receives an email notification unexpectedly.
> * A real client's calendar events are deleted or modified.
> * You observe any data belonging to real customers that looks incorrect or vulnerable.
