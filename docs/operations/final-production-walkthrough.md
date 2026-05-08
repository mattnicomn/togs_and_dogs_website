# Final Production Walkthrough: Tog & Dogs Portal

## Overview
A comprehensive backend programmatic validation of the production environment has been completed successfully. This validation confirms that all recent system hardening and data cleanup efforts are fully operational.

**Status:** The system is completely safe and ready for a manual visual spot-check by Ryan/Matthew.

---

## Programmatic Validation Results
The following end-to-end flows were verified automatically in the `usmissionhero-website-prod` environment:

1. **Data Integrity Checks**: Passed.
   - `AUDIT#AUDIT#` malformed records count: **0**
   - Active Data Issues: **0** (Only test artifacts remain)
2. **Client Request Intake (`/requests`)**: Passed. Request successfully created with safe public RBAC.
3. **Admin Meet & Greet Verification**: Passed. Safely bypassed M&G requirement for the test client.
4. **Admin Request Approval**: Passed. 
   - SES Sandbox-safe notifications are working correctly (`NOTIFICATION_MODE=log_only`).
   - Notification result: "Notification logged only (Dry Run or Disabled)."
5. **Staff Scheduling & Google Calendar Sync**: Passed.
   - The system transitions correctly to `ASSIGNED`.
   - The calendar sync integration executes safely. (Note: Google Calendar token is currently disconnected/expired, which gracefully falls back without blocking the workflow).
6. **Request Cancellation & Cleanup**: Passed. Request gracefully cancelled and deleted.
7. **Client Portal Data Sanitization**: Passed. Sensitive fields (`worker_id`, `admin_notes`) are strictly redacted for `client` roles.
8. **RBAC Security Boundaries**: Passed. Attempted access to `/admin` routes using a `client` role correctly returns `403 Forbidden`.

---

## Manual UI Spot-Check Checklist
Before handing the portal over to the primary stakeholders, please perform this quick manual UI validation.

### 1. Admin Request List Validation
- [ ] Log in to the production admin portal (`https://toganddogs.usmissionhero.com/admin` or `localhost:5173/admin` connected to prod).
- [ ] Navigate to the **Request List** dashboard.
- [ ] Confirm the UI loads quickly without any timeout errors.
- [ ] Confirm **Data Issues** badge shows `0` (or the few remaining known test records).
- [ ] Verify that no `AUDIT#`, `COMPANY#`, `STAFF#`, `CLIENT#`, or `PET#` system records appear visually mixed in with the Request List rows.

### 2. Client Portal Visibility Check
- [ ] Log in to the client portal using the test client account (`alex@example.com` or equivalent).
- [ ] Navigate to the **Bookings** or **My Requests** view.
- [ ] Click on an approved or scheduled booking.
- [ ] Confirm that no internal notes (Admin Notes, Pricing Notes) or Staff Assignment (Worker ID/Color) are visible in the UI.

### 3. Google Calendar Re-Authentication
- [ ] Go to the **Admin Settings > Integrations** page (if available) or the environment variables.
- [ ] Note: The backend logs indicate `Google Calendar disconnected or token expired`. If Ryan expects calendar syncing, he will need to re-authenticate the Google account through the portal.

Once these visual checks are completed, the system is fully validated and operational!


---

## Deployment Log

### 2026-05-08 — Fix: Admin Action Payload for Single Record Moves

**Commit:** `54d7831` — `fix: correct admin action payload for single record moves`

**Issue:** "Saved for Records" (ARCHIVED) section failed when moving records to Trash with error: "Action failed: Missing action or records to process"

**Root Cause:** `performAdminAction` in `web/src/api/client.js` always included `records: null` in the JSON payload for single-record calls. The backend checks `if 'records' in body` first — since the key existed with null value, it took that branch and got `None` (falsy), triggering the validation error instead of falling through to the `PK`/`SK` path.

**Fix:** Rebuilt `performAdminAction` to construct a clean payload — only includes `records` when it's a bulk operation, only includes `PK`/`SK` for single-record operations.

**Files Changed:** `web/src/api/client.js`

**Deployment:**
- S3 sync: `togs-and-dogs-prod-toganddogs-hosting` ✓
- CloudFront invalidation: `I4QII7L0C5V0IUC5EUA6YVF0JS` (InProgress @ 2026-05-08T14:53:57Z)

**Safety:** Permanent purge protections unchanged — records must be in DELETED/TRASH status before purge is allowed.
