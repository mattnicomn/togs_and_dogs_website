# Release 21H — Google Per-Tenant Token Isolation Production Deployment and Validation

**Release Date:** 2026-07-09  
**Status:** Closed & Manually Validated (PASS)  
**Author:** Antigravity  

---

## Executive Summary

Release 21H deploys the Release 21G backend implementation of Google Calendar per-tenant token isolation to production. It updates all 13 backend Lambdas to resolve token credentials dynamically based on tenant metadata configurations while maintaining compatibility fallback for the default tenant (`tog_and_dogs`).

---

## Pre-Deploy Verification Checks

All pre-deploy verification steps passed successfully before execution:
* **AWS Identity:** Confirmed active workload profile `usmissionhero-website-prod` (Account `358604342897`).
* **Git Status:** Verified clean.
* **Commit Reference:** Confirmed current local/remote commit is `27594e7` (which includes pre-deploy implementation `fceccf4`).
* **Tenant Configuration:** Confirmed exactly 2 tenants:
  * `tog_and_dogs` (Status: `active`)
  * `test_tenant_alpha` (Status: `active`)
* **Strict Resolution Mode:** Confirmed `TENANT_RESOLUTION_MODE` is `"multi"` across production Lambdas.
* **No Untracked Files:** Verified no `.tfplan`, credentials, or test artifacts were present in the repository.

---

## Test Execution Results

Prior to deployment, the targeted test suite and regression tests were executed and passed completely:
* **Total Tests Run:** 110 passed (0 failed).
* **Test Suites Validated:**
  * `tests/backend/test_r21g_google_token_isolation.py`
  * `tests/backend/test_r21d_calendar_metadata_defaults.py`
  * `tests/backend/test_r20e_disabled_tenant_enforcement.py`
  * `tests/backend/test_r19k_tenant_isolation.py`
  * `tests/backend/test_r17b_entitlement_enforcement.py`
  * `tests/backend/test_r6g_calendar_health.py`
  * `tests/backend/test_r6g_calendar_retry.py`
  * `tests/backend/test_r6g_calendar_token.py`
  * `tests/backend/test_r9c_google_calendar_banner.py`
  * `tests/backend/test_r6g_calendar_all_day.py`
  * `tests/backend/test_r7d_calendar_hardening.py`

---

## Terraform Deployment Summary

* **Plan Generation:** Generated named plan `release-21h.tfplan`.
* **Changes Count:** `0 to add, 13 to change, 0 to destroy`.
* **Plan Scope:** limited to in-place updates of the 13 backend Lambda function resources (`admin`, `assign`, `cancellation`, `device`, `google-auth`, `intake`, `job`, `pet`, `platform`, `postmark-webhook`, `review`, `ses-feedback`, `stripe-webhook`) due to package code changes.
* **Apply Status:** Applied successfully.
* **Cleanup:** The local `release-21h.tfplan` file was immediately deleted after apply and was not committed.

---

## Production Validation Results

### A. Default Tenant (`tog_and_dogs`) Compatibility Validation
* **Admin Info Endpoint:** `/admin/tenant-info` loaded successfully (200 OK).
* **Google Calendar Status:** Returned status `CONNECTED`, matching provider `google`.
* **Credential Shielding:** Verified no raw secrets, tokens, or authorization codes were exposed.
* **Compatibility:** Existing token storage pathing and calendar functionality remains intact.

### B. Second Tenant (`test_tenant_alpha`) Isolation Validation
* **Admin Info Endpoint:** `/admin/tenant-info` loaded successfully (200 OK).
* **Calendar State:** Returned status `not_configured`, provider `none`.
* **UI Banner & Popups:** Preserved clean unconfigured status; no warnings or popups.
* **Action Blocking:** Connection endpoints blocked OAuth initiation for `test_tenant_alpha`, returning 400.
* **Data Scoping:** No default calendar data or secrets were queried or exposed.

### C. Platform Admin Console Validation
* **Tenant List:** `/platform/tenants` successfully lists both active tenants.
* **tog_and_dogs Metadata:** Details verified as `google` provider with `error` connection status (securely blocked from reading tokens by platform role IAM limits).
* **test_tenant_alpha Metadata:** Details verified as `none` / `not_configured`.
* **Secrets Shielding:** No raw token values visible in response objects.

### D. Observability & Platform Safety
* **Tenant Count:** 2 active tenants.
* **DynamoDB Writes:** Zero backfills or metadata updates performed.
* **Secrets Manager:** No token modifications or migrations performed.
* **CloudWatch Alarms:** Checked active metrics; 0 active alarms.
* **Data Deletion:** Zero customer or database data deleted.

---

## Matthew Manual Validation Checklist Results — PASS

### Checklist A — `test_tenant_alpha` owner: PASS
* Logged in using a fresh incognito/private browser session.
* `/admin` loaded properly.
* Calendar card displayed provider-neutral `NOT CONFIGURED`.
* No Google Calendar popup or connected calendar warning banner appeared.
* No `Connect Calendar` primary action was visible or clickable.
* Branding displayed correctly for `Test Tenant Alpha`.
* No Togs & Dogs staff, client, booking, pet, job, calendar, or operational data was visible.
* No 401/403/auth/session errors observed.
* Logged out.

### Checklist B — existing `tog_and_dogs` admin / platform user: PASS
* Logged in successfully.
* `/admin` loaded normally.
* Google Calendar connection status remained intact and healthy.
* Existing staff, client, and booking views worked normally.
* `/platform-admin` loaded.
* Both tenants displayed correctly with safe provider/status fields only.
* No raw token or secret values were visible.
* No 401/403/auth/session errors observed.
* Logged out.

