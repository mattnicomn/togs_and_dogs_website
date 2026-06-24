# Release 18N: Phase 2 Entitlement Controlled Validation Report

**Release Name:** 18N — Phase 2 Entitlement Controlled Validation Execution  
**Date:** 2026-06-24  
**Status:** ✅ **Complete (No Code/Infra Changes)**  
**Plan Baseline:** [Release 18M Plan](../planning/release-18m-phase-2-entitlement-controlled-validation-plan.md) (`46d9a4a`)  
**Code Baseline:** [Release 18L Implementation](release-18l-monthly-booking-counter-and-client-limit-implementation.md) (`8082362`)

---

## 🔍 Pre-Execution Status (Gate 1 Pre-checks)

We executed pre-checks on the active production account to establish our baseline:
1. **Tenant Validation:** Confirmed only **one** tenant exists in DynamoDB:
   - **Tenant ID:** `tog_and_dogs`
   - **Tier:** `professional` (Professional limits: `max_active_clients = 100`, `max_monthly_bookings = 250`)
   - **Status:** `active`
   - **Strict Mode:** Confirmed disabled (`TENANT_RESOLUTION_MODE` env var is not configured, defaulting to `single`).
2. **Initial Client Count:** Confirmed there were exactly **2** active client records (safely below the 100-client limit).
3. **Initial Monthly Bookings Count:** Confirmed that the bookings counter for `2026-06` was **0** (Usage record did not exist yet, defaulting to 0).
4. **Portal Verification:** Verified `/admin` and `/platform-admin` loaded successfully (HTTP 200).
5. **Calendar Health:** Invoked the daily health check Lambda asynchronously and verified that Google Calendar returns `CONNECTED` and healthy.
6. **CloudWatch Alarms:** Confirmed all alarms (including tenant fallbacks, sync failures, and entitlement denials) were in the **OK** state.

---

## 🧪 Controlled Validation Execution

We executed the validation sequence through targeted Lambda invokes mimicking the production API endpoints:

### Gate 2: Client Creation
* **Action:** Posted a new client creation request to the Admin Lambda.
  - **Display Name:** `Phase2Test_18N_Client`
  - **Email/Phone:** Blank (omitted to guarantee notification isolation)
  - **Notes:** `Release 18N controlled Phase 2 entitlement validation. Internal test only. No client contact.`
* **Result:** Successfully created client with ID `client_68c8ecb4` (HTTP 200).
* **Count Check:** Verified active client count increased from **2 to 3**. No external email/SMS/payment calls occurred.

### Gate 3: Test Booking Exemption (`is_test_booking=true`)
* **Action:** Posted an admin-created booking request to the Intake Lambda.
  - **Client ID:** `client_68c8ecb4`
  - **Pet Name:** `TestPet_Phase2_Exempt_18N`
  - **Flag:** `is_test_booking = true`
* **Result:** Request `176a9310-2406-4337-bf86-c91a46573989` successfully created (HTTP 200). Google Calendar event `usgbjknbn57e3pkv3daf6vjq0k` was synced.
* **Booking Counter Check:** Verified the monthly booking counter for `2026-06` **remained at 0** (correctly exempted).

### Gate 4: Normal Booking (`is_test_booking=false`)
* **Action:** Posted an admin-created booking request to the Intake Lambda.
  - **Client ID:** `client_68c8ecb4`
  - **Pet Name:** `TestPet_Phase2_Counter_18N`
  - **Flag:** `is_test_booking = false` (or omitted)
* **Result:** Request `f404bfb6-3c4b-4810-a120-61ac7cd0afed` successfully created (HTTP 200). Google Calendar event `b86qoe0g7jv6d4vuq765dj6n54` was synced.
* **Booking Counter Check:** Verified the monthly booking counter for `2026-06` **incremented exactly once (from 0 to 1)**.

---

## 🧹 Cleanup and Re-verification (Gate 5)

1. **Standard Cancellations:**
   - Approved cancellation decisions for both booking requests:
     - `176a9310-2406-4337-bf86-c91a46573989` (Exempt) -> cancelled (HTTP 200)
     - `f404bfb6-3c4b-4810-a120-61ac7cd0afed` (Normal) -> cancelled (HTTP 200)
   - Both request and child job records successfully transitioned to `CANCELLED` status.
2. **Google Calendar Event Removal:**
   - **Exempt Booking Event (`usgbjknbn57e3pkv3daf6vjq0k`):** Automatically deleted on cancellation.
   - **Normal Booking Event (`b86qoe0g7jv6d4vuq765dj6n54`):** Did not delete automatically due to an asynchronous race condition.
     - *Race Details:* The asynchronous Job Lambda processed the request approval and created the child job before the intake handler's calendar sync wrote the event ID back to the request item. As a result, the Job record did not inherit the `google_event_id` attribute. When the cancellation cascade ran, it deleted GCal events associated with child jobs, but since the Job record lacked the event ID, it was skipped.
     - *Remediation:* Manually deleted event `b86qoe0g7jv6d4vuq765dj6n54` via the Google Calendar API using our token.
   - **Verification:** direct GCal API checks confirmed **both events are cancelled (deleted)**.
3. **Notification Verification:**
   - Verified that no client-facing notifications occurred (no email or phone was configured).
   - Confirmed only two admin cancellation notifications were sent to Matthew (`mbn@usmissionhero.com`) via Postmark (Message IDs: `42d70de6-8555-4cc6-9c09-bbba3aacd648` and `369f47b2-7f92-4b1c-bcd7-2aed8d34c84d`). This was acceptable.
4. **Client Archiving/Marking:**
   - Disabled the test client profile and updated the metadata:
     - **Display Name:** `Phase2Test_18N_Client [ARCHIVED]`
     - **Active Status:** `is_active = false` (disabled)
     - **Notes:** `Release 18N controlled Phase 2 entitlement validation. Internal test only. No client contact. ARCHIVED.`
   - No raw database deletes were performed.

---

## 🚦 System Status & Telemetry Summary

* **Admin Portal (`/admin`):** ✅ Loading successfully (HTTP 200)
* **Platform Admin Portal (`/platform-admin`):** ✅ Loading successfully (HTTP 200)
* **Google Calendar Connection:** Connected & Healthy
* **CloudWatch Alarms:** All alarms remain in `OK` state.
* **Final Database Usage Metrics:**
  - Active Clients: 3 (including the disabled/archived test client, which counts toward the tier limit by design).
  - Monthly Bookings: 1 (Normal booking incremented the counter, which counts creations and is not decremented on cancellation).

---

## 🏁 Guardrail & Compliance Check

* **No Code Changes:** Yes (only verification and validation run)
* **No Terraform Apply/Deploy:** Yes
* **No Stripe/Payment Activity:** Yes (dry-run Stripe env)
* **No Second Tenant Created:** Yes
* **No Strict Mode Enabled:** Yes
* **No Secrets/Tokens Exposed:** Yes (Secrets remained hidden in log files)
* **No Client Data Involved:** Yes (completely fictional names and empty addresses)

---

## 🚀 Recommended Next Step

Proceed with multi-tenant readiness backlog items and prepare for the final strict mode gate review on or after June 30, 2026.
