# Ryan Production Trial Handoff

**Last Updated:** Release 7R  
**Operations Portal Link:** [https://toganddogs.usmissionhero.com](https://toganddogs.usmissionhero.com)  

Welcome to the production release of the Tog & Dogs Operations Portal. The portal is fully set up, secured, and ready for you to use in daily business operations. This handoff document provides a structured path for your **production trial**, helping you get familiar with key workflows during a controlled rollout.

---

## 1. Production Trial Purpose

The purpose of this trial is to use the operations portal with a **small number of real, active client workflows** first. By running a controlled 2-week trial, we can verify that calendar synchronization, booking lifecycles, and automated email confirmations operate flawlessly on your day-to-day schedule before rolling it out to your entire customer base.

---

## 2. Onboarding Schedule: Recommended Test Actions

### 📋 Week 1: Basic Lifecycle & Single-Day Bookings
Get comfortable with daily operations, manual client creation, and staff assignments:
* [ ] **Create One Offline Client Profile:** Open **Client Management** $\to$ click **Create Profile**. Input client and pet details, leaving the email field blank (creates an *Offline Client*).
* [ ] **Create One Real Single-Day Booking:** For the offline client, click **+ New Visit** from your dashboard. Book a single walk on a specific date.
* [ ] **Verify Google Calendar Sync:** Assign a staff member to that booking. Check their Google Calendar to confirm the walk event appears automatically with all notes.
* [ ] **Approve One Public Intake Submission:** If a client submits a new booking via the public portal, locate it in your **Intake Queue** and click **Approve Request**.
* [ ] **Assign Staff to One Booking:** Complete staff assignment for any active, approved request to verify the email notification flow.
* [ ] **Cancel One Test Booking:** Create a temporary test booking, assign it, and then click **Cancel Request** to verify that calendar cleanup and cancellation emails operate correctly.

### 📋 Week 2: Advanced Scheduling & Full Lifecycles
Explore multi-day dispatching and restorative action tools:
* [ ] **Create One Consecutive Multi-Day Booking:** Use **+ New Visit** to schedule a continuous date range (e.g. 5 days of pet sitting).
* [ ] **Create One Selected-Date / Non-Consecutive Booking:** Use the **Pick Days** scheduling calendar mode to book non-consecutive days (e.g., Mon, Wed, Fri walks).
* [ ] **Complete a Full Lifecycle:** Walk a single test booking through the entire sequence: **Intake Submited** $\to$ **Admin Approved** $\to$ **Staff Assigned** $\to$ **Completed** $\to$ **Archived** (verifying that your dashboard remains clean and organized).
* [ ] **Test Restoring a Trashed/Cancelled Record:** Intentionally move a test request to **Trash** (Delete), then navigate to the Trash filter view and select **Restore to Approved** to verify that your record and calendar slots are immediately restored.

---

## ⚠️ What Ryan Should Avoid (Operational Safety Rules)

To protect the integrity of your production database, please follow these safety rules:
1. **Do NOT Purge Real Client Records:** Moving records to *Trash* is safe. However, *Purging Forever* permanently deletes them. Only use Purge on temporary test records you created.
2. **Do NOT Edit Google Calendar Events Directly:** Avoid deleting, dragging, or editing synced booking events directly within your Google Calendar app. Always make scheduling changes directly inside the **Operations Portal** to prevent sync conflicts.
3. **Do NOT Bulk-Delete Active Records:** Avoid applying bulk status transitions to delete active, scheduled requests without cancelling them first.
4. **Do NOT Disable Real Staff Profiles:** Deactivating a staff profile immediately locks them out of their portal login.
5. **Do NOT Change Technical Settings:** Do not modify the environment variables, AWS parameters, or database connections in the Settings panel unless instructed.

---

## 🛠️ What Matthew Should Monitor (Backend Telemetry)

During the production trial, Matthew should actively monitor the following telemetry layers to confirm system health:
* **Postmark Delivery Status:** Verify email confirmation send rates, bounce ledger records, and ensure no spam blockages occur.
* **Google Calendar Connection Status:** Check for any reauthorization errors or API sync failures.
* **AWS CloudWatch Log Streams:** Review `/aws/lambda/` function logs to ensure no unhandled exceptions are raised during intake handler validations.
* **Failed Notification Records:** Scan the DynamoDB ledger table (`togs-and-dogs-prod-data`) for any notification entries that fail to transition to `sent`.
* **AWS Quota and Usage Limits:** Monitor API Gateway thresholds and database read/write capacity units.

---

## 📝 How Ryan Should Report Issues

If you encounter a layout glitch, sync issue, or any unexpected behavior, please record the following information before escalating so we can diagnose and resolve it quickly:

1. **Client & Pet Name:** Who the booking or profile is for.
2. **Request Date & Time:** The exact date and timeframe of the booking.
3. **What Action You Were Taking:** Describe exactly what button you clicked or what form page you were editing.
4. **Screenshot:** Capture a visual image of the error message or layout issue.
5. **Expected Output:** Let us know whether an email notification, database record, or Google Calendar event was expected but did not appear.

---

## 📚 Essential Reference Materials

For detailed step-by-step instructions and runbooks, please refer to the following local operations documents:
* **Dashboard Operations Guide:** [docs/operations/admin-quick-reference.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/operations/admin-quick-reference.md)
* **Incident Emergency Playbook:** [docs/operations/emergency-response-checklist.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/operations/emergency-response-checklist.md)
* **E2E Production Smoke Test:** [docs/validation/production-smoke-test-checklist.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/validation/production-smoke-test-checklist.md)
