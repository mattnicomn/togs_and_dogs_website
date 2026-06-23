# Release 18L: Monthly Booking Counter and Client Limit Implementation

**Status:** Completed (Code/Tests/Docs/Terraform Apply)  
**Type:** Backend Integration & Feature Gate Implementation  
**Date:** 2026-06-23  

---

## 1. Goal

The goal of this release was to implement Phase 2 entitlement gates:
1. **Client count limit (`max_active_clients`):** Gate client creation based on the active + disabled client profiles, excluding archived client profiles.
2. **Monthly booking limit (`max_monthly_bookings`):** Gate booking creation on a monthly booking usage counter tracked atomically in DynamoDB.

Enforcement continues to respect the existing `ENTITLEMENT_ENFORCEMENT_ENABLED` environment variable (set to `"false"` in production for zero user disruption).

---

## 2. Technical Details & Logic

### A. Client Limit Gating
- **Client Count Helper:** `get_active_client_count(company_id)` queries all client records (`PK = COMPANY#{company_id}` and `SK` begins with `"CLIENT#"`) and counts all records except those where `status == "ARCHIVED"` or `is_archived == true`.
- **Admin Client Creation Gated:** Checks the limit before creation inside both `POST /admin/clients` and `POST /admin/clients/onboard` in [admin_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py). Returns a `403 Forbidden` response on denial.
- **Client Profile Auto-Creation Gated:** Inside `auto_create_or_link_client_profile` in [client_profile.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/client_profile.py), the limit is checked before saving the profile. If exceeded, it fails gracefully with `FAILED_LIMIT_EXCEEDED` status on the request record and appends a structured audit log entry.
- **Public Intake Submission Gated:** Inside `intake_handler.py` [intake_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/intake_handler.py), when a new client submits a request (`CUSTOMER_INTAKE`), if their email does not match any existing client profile, it gates submission on `max_active_clients` to avoid registration overflow.

### B. Monthly Booking Counter & Gating
- **DynamoDB Usage Key Pattern:** Uses `PK = USAGE#{company_id}` and `SK = BOOKINGS#{YYYY-MM}`.
- **Atomic Counter Increment:** `increment_monthly_bookings(company_id)` atomically adds `1` to `booking_count` in DynamoDB using `ADD booking_count :val`. Runs only after successful database save of the parent booking request.
- **Multi-day Bookings:** Counts once because only the parent `REQ#` record is saved, representing the parent request.
- **Test Booking Exemption:** Bypasses limits and counter increments if the request body is explicitly marked as test (where `is_test_booking` or `is_test` is true).

---

## 3. Verification & Testing

We created a new unit test suite [test_r18l_client_booking_limits.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r18l_client_booking_limits.py) covering 15 test cases:
*   Client count calculation (including active/disabled, excluding archived).
*   Gating on admin client creation and onboarding.
*   Gating on public intake for new emails, bypassing for existing.
*   Monthly booking limits and atomic counter increments.
*   Test booking exemptions (bypass limits and increments).
*   Multi-day booking counted once.
*   Tenant isolation of usage keys.
*   Missing usage record defaults to zero.
*   Entitlement enforcement flag support.

### Test Execution Results
All test suites passed successfully:
*   **`test_r18l_client_booking_limits.py`:** 🟢 **15/15 passed**
*   **Regression Validation suites:** 🟢 **74/74 passed**
    *   `test_r17d_entitlement_wiring.py` (15/15 passed)
    *   `test_r17b_entitlement_enforcement.py` (9/9 passed)
    *   `test_r6f_offline_booking.py` (17/17 passed)
    *   `test_r17w_company_id_resolution.py` (33/33 passed)

---

## 4. Deployment Summary

- **Deployment Method:** Terraform Apply (`infra/prod`)
- **Resources Changed:** 0 added, 13 changed (in-place Lambda code updates via updated `backend.zip`), 0 destroyed.
- **Lambdas Deployed:**
  - `togs-and-dogs-prod-admin`
  - `togs-and-dogs-prod-intake`
  - `togs-and-dogs-prod-review`
  - `togs-and-dogs-prod-job`
  - `togs-and-dogs-prod-assign`
  - `togs-and-dogs-prod-cancellation`
  - `togs-and-dogs-prod-google-auth`
  - `togs-and-dogs-prod-pet`
  - `togs-and-dogs-prod-device`
  - `togs-and-dogs-prod-platform`
  - `togs-and-dogs-prod-stripe-webhook`
  - `togs-and-dogs-prod-postmark-webhook`
  - `togs-and-dogs-prod-ses-feedback`
- **Frontend / Mobile:** Bypassed (no web assets compiled or synced).

---

## 5. Scope Guardrails Compliance

*   No Cognito schema, user pool, or attributes changed.
*   No strict mode enabled (`TENANT_RESOLUTION_MODE=multi` remains off).
*   No second tenant created.
*   No production writes/test bookings/clients were created in the production database.
*   No Stripe Dashboard or Postmark live notifications were triggered.
