# Release 18T: Strict Mode Enablement Apply and Smoke Validation

**Status:** Completed  
**Type:** Infrastructure / Security Hardening  
**Date:** 2026-06-26  

---

## 1. Goal

The goal of this release was to execute the Terraform apply command to transition all 13 production backend Lambda functions to strict tenant-resolution mode (`TENANT_RESOLUTION_MODE=multi`). This completes the strict mode enablement gate, ensuring Cognito users must have a valid `custom:company_id` matching their tenant or their requests will be denied with `403 Forbidden` (`PermissionError`).

---

## 2. Execution Results

### A. Terraform Apply
- The pre-reviewed plan `infra/prod/release18s-strict-mode.tfplan` was successfully applied in the production environment.
- **Resource Summary:** `0 added, 13 changed, 0 destroyed` (in-place environment variable updates only).
- **Cleanup:** The plan file was successfully deleted, and no `.tfplan` files remain in `infra/prod`.

### B. Lambda Environment Verification
Verified using the AWS Lambda API that all 13 backend Lambdas have `TENANT_RESOLUTION_MODE` set to `"multi"`:
1.  `togs-and-dogs-prod-admin` — `TENANT_RESOLUTION_MODE: multi`
2.  `togs-and-dogs-prod-assign` — `TENANT_RESOLUTION_MODE: multi`
3.  `togs-and-dogs-prod-cancellation` — `TENANT_RESOLUTION_MODE: multi`
4.  `togs-and-dogs-prod-device` — `TENANT_RESOLUTION_MODE: multi`
5.  `togs-and-dogs-prod-google-auth` — `TENANT_RESOLUTION_MODE: multi`
6.  `togs-and-dogs-prod-intake` — `TENANT_RESOLUTION_MODE: multi`
7.  `togs-and-dogs-prod-job` — `TENANT_RESOLUTION_MODE: multi`
8.  `togs-and-dogs-prod-pet` — `TENANT_RESOLUTION_MODE: multi`
9.  `togs-and-dogs-prod-platform` — `TENANT_RESOLUTION_MODE: multi`
10. `togs-and-dogs-prod-postmark-webhook` — `TENANT_RESOLUTION_MODE: multi`
11. `togs-and-dogs-prod-review` — `TENANT_RESOLUTION_MODE: multi`
12. `togs-and-dogs-prod-ses-feedback` — `TENANT_RESOLUTION_MODE: multi`
13. `togs-and-dogs-prod-stripe-webhook` — `TENANT_RESOLUTION_MODE: multi`

---

## 3. Smoke Validation

*   **Portal Status:**
    *   `/admin` loaded successfully (HTTP `200`).
    *   `/platform-admin` loaded successfully (HTTP `200`).
*   **Integration Status:**
    *   Google Calendar remains `CONNECTED` and healthy.
*   **Alarms Status:** All 6 alarms remain 🟢 **OK** (no breaches):
    *   `togs-and-dogs-prod-tenant-resolution-fallback` = `OK`
    *   `togs-and-dogs-prod-tenant-resolution-failed` = `OK`
    *   `togs-and-dogs-prod-entitlement-denied` = `OK`
    *   `togs-and-dogs-prod-calendar-sync-failures` = `OK`
    *   `togs-and-dogs-prod-calendar-token-revoked` = `OK`
    *   `togs-and-dogs-prod-calendar-health-check-failed` = `OK`
*   **Guardrail Enforcement:**
    *   Confirmed no Cognito users/passwords/attributes were altered.
    *   Confirmed no DynamoDB records were written or modified (except standard AWS state locking).
    *   Confirmed no calendar events, clients, bookings, or jobs were created or deleted.
    *   Confirmed no Stripe sandbox/live mode parameters or Postmark keys were modified.
    *   Confirmed no second tenant was created.

---

## 4. Matthew Manual Validation (PASS)

Matthew successfully completed manual validation of strict-mode tenant routing:
1.  Logged out and logged back in successfully to obtain a fresh access token containing `custom:company_id`.
2.  Verified that `/admin` loaded successfully and dashboard data displayed normally.
3.  Verified that `/platform-admin` loaded successfully and platform tenant/audit views displayed normally.
4.  No `401 Unauthorized`, `403 Forbidden`, or auth/session errors were observed.

Strict-mode tenant resolution is fully operational and verified end-to-end.


---

## 5. Rollback Plan

If Matthew's manual verification fails and access is blocked:
1.  Revert `TENANT_RESOLUTION_MODE` to `"single"` in `locals.tf` and `main.tf`.
2.  Re-run `terraform plan` and `terraform apply`.
3.  Confirm all Lambdas are restored to `"single"` mode.
4.  Have Matthew log out and log back in, and verify endpoints.
