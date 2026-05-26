# Offline Client Management — Operations Guide

**Applies to:** Admin, Owner roles
**Last Updated:** Release 7B Phase 4
**Related Releases:** 7A Phase 2, 7A Phase 3, 7B Phase 1, 7B Phase 2, 7B Phase 3

---

## 1. Purpose & When to Use Offline Client Profiles

An **offline client** is a client who is managed entirely by staff and administrators without using the self-service web portal. Offline clients:

- Do not have a Cognito login account.
- May or may not have an email address on file.
- Cannot log in, view their own bookings, or fill out intake forms.

### When to create an offline profile

Use an offline client profile for clients who:

- Are elderly or prefer to coordinate all scheduling by phone or text.
- Are not comfortable using websites or technology in general.
- Explicitly prefer not to create an account.
- Are referrals or word-of-mouth clients who you need to track in the system without waiting for them to complete an intake form.
- Need to be booked immediately and can complete account setup later.

Offline clients are **fully manageable by staff and admins.** Visits, pets, job records, staff assignments, and calendar sync all work normally — the only difference is that the client does not have self-service portal access.

---

## 2. Offline Client Creation Workflow

### Step-by-step

1. Navigate to **Admin Dashboard → Client Management**.
2. Click **+ New Client**.
3. In the creation mode selector, choose **"Create Profile Only (No Login)"**.
4. Fill in:
   - **Display Name** *(required)*
   - **Email Address** *(optional for profile-only clients)*
   - Phone, address, emergency contact, notes *(all optional)*
5. Click **Save Client**.

### What happens

- A client profile record is created in the database with a unique `client_id`.
- If no email is provided, no Cognito user is created. The client cannot log in.
- The client appears in Client Management and is immediately available for booking and pet management.

### Understanding client card badges

| Badge | Meaning |
|---|---|
| **Active** | Client has a confirmed Cognito login account and portal access. |
| **Invited** | Client was sent a setup email but has not yet confirmed their account. |
| **No Login** | Client has an email on file, but no Cognito account has been created yet. Can be linked/onboarded later. |
| **Offline Client** | Client has no email and no Cognito account. Fully managed offline by staff only. |
| **Disabled** | Client's login access has been turned off. Profile is still accessible to admins. |

### Email field indicators

- If a client card shows **"No email on file"** in italic text, the client is fully offline and cannot receive email notifications.
- If an email address is displayed normally, the client has an email on file and may be able to receive notifications or be linked to a Cognito login later.

---

## 3. Manual Visit Booking Workflow

Admin-created bookings bypass the standard client intake form and are immediately placed into the active operational workflow.

### Step-by-step

1. Navigate to **Admin Dashboard → Scheduler** or **Request List**.
2. Click **+ New Visit**.
3. In the modal:
   - **Select Client** — Search for and select the offline client from the dropdown.
   - **Select Pet** — Choose an existing linked pet from the list.
   - **Date and Service** — Fill in the visit start date and service type.
4. Click **Create Visit**.

### What happens after booking

- A booking request is created with `source: admin_created` and starts in **APPROVED** status — it skips the pending intake review queue.
- A child **JOB** record is automatically created for staff assignment.
- **Google Calendar sync** is attempted for any linked staff calendar.
- The booking appears in both the **Request List** and the **Scheduler** view.
- An **"Admin Created"** badge is shown on the booking row in the Request List for easy identification.

> **Note:** No booking confirmation email is sent to the client for admin-created visits. Staff must coordinate scheduling with the client directly.

---

## 4. Pet Management Expectations

### Adding pets to an offline client

Pets can be added to offline clients in two ways:

**From Client Management:**
1. Click the offline client card to select it.
2. Use the **"Add Pet"** form in the expanded client panel.
3. Fill in the pet name, species, breed, and age.
4. Save. The pet is immediately available for booking.

**Inline from the + New Visit modal:**
1. Open **+ New Visit** and select the client.
2. If no pets are listed, click **"+ Add New Pet"** inside the modal.
3. Fill in the pet fields inline and save.
4. The new pet is auto-selected for the current booking.

### Fallback behavior for unavailable pets

If a booking or care record references a pet record that has since been deleted or is otherwise unresolvable, the system will now display:

> **"Deleted/Unavailable pet record"**

This replaces the old technical placeholder text. Additionally:
- The pet's tab in the CareCard displays a **warning banner** explaining the record is no longer available.
- The **"Edit Record"** action button is disabled for unavailable pets to prevent erroneous save operations.
- Page loading is **not blocked** — all other pets and booking details still display correctly.

Admins do not need to take any action for unavailable pet references unless the data integrity issue needs to be investigated.

---

## 5. Login / Linking Behavior

### Offline clients with no email

- The **"Link Login Account"** button is **not shown** for clients without an email address.
- Instead, the client card shows: _"Offline client — add email to enable login."_
- This prevents accidentally attempting a login link action that would fail due to missing email.

### Upgrading an offline client to portal access

If an offline client later decides they want portal access:

1. Open the client profile in **Client Management → Edit**.
2. Add a valid email address and save.
3. The client card badge will update from **"Offline Client"** to **"No Login"**.
4. The **"Link Login Account"** button will now appear.
5. Use the button to initiate the Cognito onboarding flow (invite email, account setup).

---

## 6. Notifications Behavior

### Clients without email

- **No email notifications are sent** for any system event (booking confirmation, approval, updates, etc.).
- The notification system safely detects missing email recipients and skips dispatch without errors or failed records.
- Staff must manually communicate all scheduling, updates, and confirmations to the client via phone or text.

### Clients with email (No Login or Active)

- Clients with an email address on file will receive notifications as configured in the system, regardless of whether they have a Cognito login account.
- Notification delivery depends on active Postmark integration and per-notification type settings.

### Audit note

- The notification ledger will not record attempted dispatches for clients with no email, since the recipient resolution step requires an email address before any dispatch entry is written.

---

## 7. Data Cleanup and Safety Guidelines

### General principles

- **Always prefer Admin Dashboard workflows** for record lifecycle management:
  - Cancel active bookings before moving them to Trash.
  - Use the Trash → Purge progression for permanent deletion.
  - Use the client disable/delete controls from Client Management.
- **Do not directly delete DynamoDB records** using AWS console or API tools unless the Admin Dashboard has no exposed route for that specific record type (e.g., orphaned child `JOB#` or `PET#` records tied to already-deleted parents).
- **Preserve real client data.** Before deleting any record, verify it is clearly a test or smoke-testing artifact, not a real customer.

### Test record naming conventions

When creating test records for validation purposes:
- Use clearly identifiable names such as: `test-client`, `offline-test`, `validation-pet`, etc.
- Do not use names that could be confused with real clients.
- Clean up all test records after validation is complete using the Admin Dashboard (cancel → trash → purge).

### Reference cleanup process (Release 7B Phase 1)

The cleanup order that preserves referential integrity:

1. Cancel or move REQ# booking records to **DELETED/Trash** status.
2. Purge REQ# records permanently.
3. Archive or delete orphaned **PET#** records.
4. Disable and delete test **CLIENT#** profiles.
5. Verify no orphaned child records remain.

---

## 8. Troubleshooting

### "Offline Client badge not showing"

- **Check:** Does the client have an email address on file?
- Clients with an email will show **"No Login"**, not **"Offline Client"**, even without a Cognito account. This is correct behavior.
- If the badge is wrong after a recent profile edit, try refreshing the Client Management view to reload the client list.

### "No pets appear for client"

- Verify that pets were added as individual **PET#** records via Client Management or the + New Visit inline form.
- Legacy bookings (pre-Release 4) stored pets as plain text strings on the request, not as individual PET# records. These will show a legacy summary but cannot be edited as individual records.
- If a pet was recently archived, check the **Archived Pets** toggle in Client Management.

### "Cannot link login account"

- The "Link Login Account" button only appears for clients who have an email address **and** no existing Cognito account.
- If the client has no email, add one first (Edit client profile), then return to Client Management. The button will appear after saving.
- If the button still does not appear after adding an email, refresh the client list.

### "Admin-created booking does not appear in Request List"

- Admin-created bookings start in **APPROVED** status. Make sure the **Status Filter** in the Request List is not set to a filter that excludes APPROVED records.
- Check the **Scheduler** view as an alternative — admin-created visits appear there immediately.
- If neither shows the booking after 30 seconds, try refreshing the page and check for any error notifications.

### "Email notifications skipped for a client"

- Confirm the client has an email address on file. Clients without email never receive notifications — this is correct behavior.
- If the client has an email but notifications are not arriving, check the Postmark integration status in **Admin Dashboard → Settings**.
- Also verify the specific notification type (booking approval, new request, etc.) is enabled in the notification configuration.

### "Pet unavailable warning appears in CareCard"

- This warning appears when a booking's `pet_ids` array references a pet record that no longer loads from the database.
- This is typically caused by a PET# record being deleted (e.g., during test cleanup) while the parent REQ# record still contains the pet reference.
- The warning is informational — it does not block booking display or other pet tabs.
- If this warning appears for a real production client, investigate whether the pet record was accidentally deleted. If the pet needs to be restored, it must be recreated manually in Client Management.

---

## 9. Release References

| Release | Description |
|---|---|
| **Release 7A Phase 2** | Inline pet creation from the "+ New Visit" booking modal. |
| **Release 7A Phase 3** | Made email optional for offline/profile-only client creation. Booking system made resilient to missing client email. |
| **Release 7B Phase 1** | Production test record cleanup after 7A validation. Established safe cleanup procedures and referential integrity ordering. |
| **Release 7B Phase 2** | Frontend fallback hardening for orphaned/deleted pet references. Replaced "Pet 1 (loading failed)" with "Deleted/Unavailable pet record" and disabled edit actions for unavailable pets. |
| **Release 7B Phase 3** | Admin Dashboard UX polish for offline clients. Added "Offline Client" badge, "No email on file" indicator, conditional "Link Login Account" visibility, and "Admin Created" badge on Request List rows. |

---

*This guide reflects the production state of the Tog and Dogs Admin Dashboard as of Release 7B Phase 4.*
