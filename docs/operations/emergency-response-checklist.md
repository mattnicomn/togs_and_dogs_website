# Tog & Dogs Operations Portal — Emergency Response Checklist

**Last Updated:** Release 7Q  
**Audience:** Ryan (Business Owner), Matthew, and Operations Staff  
**Status:** Operational Runbook  

This emergency checklist provides practical, step-by-step instructions to follow when something goes wrong with the Tog & Dogs Operations Portal in production. Keep calm and follow the steps below before escalating to technical support.

---

## 🚨 Incident Severity Guide

* **Severity 1 (Critical):** The main site or admin dashboard is completely down (500 error pages), blocking bookings and scheduling.
* **Severity 2 (High):** The portal loads, but core sync services are failing (e.g. Google Calendar is disconnected, or email notifications are not sending).
* **Severity 3 (Medium/Low):** A visual bug, layout problem, or minor record error that does not halt business operations.

---

## 📋 Emergency Response Scenarios

### Scenario 1: Website / Public Booking Form Not Loading
If clients report that the intake form or client portal is not loading:
1. **Verify the Issue:** Access [toganddogs.usmissionhero.com/book](https://toganddogs.usmissionhero.com/book) from a mobile device (using cellular data, not local Wi-Fi) to rule out local network problems.
2. **Rule Out Browser Issues:** Try opening the page in a private/Incognito window or using a different browser (Chrome, Safari, Firefox).
3. **Check HTTPS Status:** Ensure the URL starts with `https://`. If you see certificate warnings, the hosting domain may need renewal or re-authorization.
4. **Escalate to Matthew/Technical Support:** If the page shows a "502 Bad Gateway" or "500 Internal Server Error" across all devices, the hosting server is down.

---

### Scenario 2: Admin Dashboard Not Loading
If the admin interface fails to open or displays a blank screen:
1. **Try Incognito Mode:** Often, stale browser caches or expired cookies block the dashboard. Logging in via a private window will bypass this.
2. **Clear Application Site Data:**
   - In Chrome: Right-click $\to$ **Inspect** $\to$ Go to the **Application** tab $\to$ Click **Clear site data**.
3. **Verify Cognito Link:** If you see a login failure, check that your email is correctly registered and active. Have another admin verify your account status in Client/Staff Management if possible.

---

### Scenario 3: Google Calendar Disconnected or Events Missing
If scheduled visits are not syncing or calendar events are missing from staff schedules:
1. **Check Admin Settings Panel:** Open the Operations Portal $\to$ navigate to **Settings**. Look for the Google integration status card.
2. **Trigger Reconnection:** If the card shows an alert, click **Disconnect Google**, followed immediately by **Initiate Authorization**. Follow the Google authentication prompts to re-authorize the link.
3. **Manual Sync Request:** To force-refresh a missing event, open the target booking card, make a minor change (such as updating the notes), and click **Save**. This triggers a fresh calendar synchronization.
4. **Do NOT Edit Calendar Events Directly:** Avoid manually adding or editing events within the Google Calendar app. This can cause sync conflicts.

---

### Scenario 4: Client or Staff Notification Not Received
If a user claims they did not receive a confirmation or assignment email:
1. **Check the Notifications Ledger:** Search the request ID in the database or dashboard to verify if a notification record was written and marked as `sent`.
2. **Rule Out Spam/Junk Filters:** Ask the recipient to inspect their Spam, Junk, or Promotions folders.
3. **Check Address Spelling:** Open their client/staff profile and confirm their email address is spelled correctly.
4. **Postmark Suppression:** If the email is correct but fails repeatedly, the address may have bounced in the past and been added to the Postmark suppression list. Contact support to have the address unblocked.

---

### Scenario 5: Wrong Request Status or Accidental Status Change
If you accidentally click the wrong action and change a request's status:
1. **Refer to the Status Flowchart:** Identify the target state you need to return to.
2. **Use Restorative Actions:**
   - If accidentally **Cancelled**: Open the dropdown $\to$ select **Restore to Approved** or **Reopen to Pending**.
   - If accidentally **Completed**: Select **Reopen** to transition it back to active status.
3. **Check Calendar Status:** Changing statuses back to active will automatically re-create the calendar events. Verify that the events are restored on the Google Calendar.

---

### Scenario 6: Accidental Archive / Delete
If a record was archived or moved to the trash by mistake:
1. **Change Filters:** Toggle your Request List filter to **Archived** or **Trash** to locate the missing record.
2. **Restore:**
   - For archived: Click **Actions** $\to$ **Restore to Active**.
   - For deleted: Click **Actions** $\to$ **Restore to Approved**.
3. **Confirm Child Cascade:** Open the request card to verify that all child jobs have also successfully transitioned back to their active states.

---

### Scenario 7: Suspected Duplicate / Malformed Records
If you see duplicate client profiles or malformed request lists:
1. **Identify the Parent:** Open the records and identify which one contains the correct, complete pet details and date history.
2. **Archive or Trash the Duplicate:** Move the duplicate or empty record to the Trash. **Do not use Purge Forever** until you are absolutely certain that no active child jobs are tied to it.
3. **Use the Data Issues Filter:** Check the **Data Issues** filter view. The portal automatically flags orphaned child jobs or incomplete requests here.

---

## 🛑 What NOT to Do During an Incident

1. **Do NOT Panic-Delete:** Do not delete database records, staff members, or active client profiles in an attempt to fix a layout or listing error.
2. **Do NOT Execute Raw Code or Unapproved Scripts:** Do not run backend scripts or execute manual database operations without prior testing in a sandbox environment.
3. **Do NOT Edit Google Calendar Events Manually:** Modifying synchronized events in Google Calendar will create synchronization drift. Always make scheduling changes directly inside the portal.
4. **Do NOT Toggle Notification DRY_RUN in Production Without Notice:** Toggling dry-runs stops all emails. Only do this if directed by a developer during active maintenance.

---

## 📝 What to Capture Before Escalating

When escalating an issue to technical support (Matthew), please capture the following details to ensure a rapid resolution:

* [ ] **What is broken:** The specific feature or page affected.
* [ ] **Step-by-step description:** What actions you took immediately before the error occurred.
* [ ] **Exact error messages:** Copy and paste any error codes, alert boxes, or 500 error descriptions.
* [ ] **Record IDs:** The request ID, client name, or pet names associated with the issue.
* [ ] **Screenshots/Recordings:** Capture a visual image or quick screen recording of the error.
* [ ] **Browser & Device:** Note whether you are using Chrome, Safari, or an iPhone/Android device.
