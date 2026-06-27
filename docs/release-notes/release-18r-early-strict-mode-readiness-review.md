# Release 18R: Early Strict Mode Readiness Review

**Status:** Completed (Read-only Checkpoint)  
**Type:** Operations & Observability Checkpoint  
**Date:** 2026-06-26  

---

## 1. Goal

The goal of this release was to perform an early, read-only strict-mode readiness review of the production environment. Although the 7+ day observation period was originally scheduled to run until June 30, 2026, the absence of active customer traffic meant waiting would provide limited additional signal. This review validates Cognito user pools, DynamoDB tenant records, CloudWatch logs, and alarm states to determine if strict tenant resolution mode (`TENANT_RESOLUTION_MODE=multi`) can be safely approved for enablement.

---

## 2. Validation Checks & Telemetry Analysis

### A. Cognito User custom:company_id Audit
- Checked all users in the production Cognito user pool `us-east-1_counlsXGU`.
- **Result:** **100% Ready (PASS)**.
- All 5 active Cognito users have `custom:company_id = tog_and_dogs` successfully configured. There are no users defaulting to fallback values.

### B. DynamoDB Tenant Record Audit
- Scanned the production database table `togs-and-dogs-prod-data` for tenant metadata.
- **Result:** **100% Ready (PASS)**.
- Exactly 1 tenant metadata record exists: `TENANT#tog_and_dogs / METADATA`. No second tenant exists.

### C. CloudWatch Fallback & Failure Metrics
- Queried CloudWatch metrics under namespace `togs-and-dogs-prod/TenantResolution` from the start of the observation window (`2026-06-23T15:20:00Z`) to the current execution time (`2026-06-27T01:30:00Z`):
  - **`TenantResolutionFailed` total sum:** `0.0`
  - **`TenantResolutionFallback` total sum:** `1.0`
- **Analysis of the single fallback event:**
  - The fallback occurred on **2026-06-23 at 19:13:00.553 UTC** (about 4 hours after the observation window started) in the `togs-and-dogs-prod-cancellation` Lambda.
  - Log details: `{"event": "TENANT_RESOLUTION_FALLBACK", "mode": "single", "is_empty_company_id": true, "has_claims": true, "default_company_id": "tog_and_dogs"}`.
  - The event indicates a logged-in user who had claims but lacked `custom:company_id` in their JWT. This occurred immediately after the backfill script completed and was due to an active, un-refreshed user session that had not yet fetched the new Cognito attributes.
  - **Zero** fallback events have occurred in the subsequent 3+ days.

### D. CloudWatch Alarm States
Checked the current status of all platform observability alarms:
*   `togs-and-dogs-prod-tenant-resolution-fallback` = 🟢 **OK**
*   `togs-and-dogs-prod-tenant-resolution-failed` = 🟢 **OK**
*   `togs-and-dogs-prod-entitlement-denied` = 🟢 **OK**
*   `togs-and-dogs-prod-calendar-sync-failures` = 🟢 **OK**
*   `togs-and-dogs-prod-calendar-token-revoked` = 🟢 **OK**
*   `togs-and-dogs-prod-calendar-health-check-failed` = 🟢 **OK**

### E. Portal & Integration Health
- **Admin Dashboard (`/admin`):** Loads successfully (HTTP `200`).
- **Platform Admin Dashboard (`/platform-admin`):** Loads successfully (HTTP `200`).
- **Google Calendar Sync Health:** `CONNECTED` (daily health check Lambda runs clean).

---

## 3. Decision Model

*   **Decision:** **PASS** (Strict mode enablement is highly recommended).
*   **Rationale:** All Cognito users are correctly backfilled. The single fallback event is fully understood (active session refresh delay) and occurred over 3 days ago. Alarms are OK, and portals are healthy.
*   **Recommendation:** Matthew may approve strict-mode enablement (`TENANT_RESOLUTION_MODE=multi`) in a separate, subsequent release (Release 18S).

---

## 4. Rollback Path
If strict mode is enabled in the future and encounters unexpected failures (e.g., users getting blocked with `403 Forbidden` / `PermissionError` due to missing claims in edge cases):
1. Revert `TENANT_RESOLUTION_MODE` to `"single"` in `infra/prod` Terraform variables.
2. Execute `terraform apply`.
3. This immediately restores the compatibility fallback behavior, routing any users with un-refreshed tokens back to `"tog_and_dogs"` dynamically using the default fallback path. Rollback is safe and takes under 5 minutes.
