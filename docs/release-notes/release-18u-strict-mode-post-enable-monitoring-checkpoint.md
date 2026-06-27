# Release 18U: Strict Mode Post-Enable Monitoring Checkpoint

**Status:** Completed (Monitoring Checkpoint)  
**Type:** Operations & Observability Checkpoint  
**Date:** 2026-06-26  

---

## 1. Goal

The goal of this release was to perform a read-only post-enable monitoring checkpoint following the activation of strict tenant-resolution mode (`TENANT_RESOLUTION_MODE=multi`). This checkpoint confirms that no tenant-resolution failures or unexpected fallbacks occurred in production since the activation.

---

## 2. Telemetry & Monitoring Analysis

### A. CloudWatch Fallback & Failure Metrics
Queried metrics under the `togs-and-dogs-prod/TenantResolution` namespace starting from the Release 18T apply time (`2026-06-27T01:40:00Z`) to the current execution time (`2026-06-27T01:50:00Z`):
*   **`TenantResolutionFallback` total sum:** `0.0`
*   **`TenantResolutionFailed` total sum:** `0.0`
*   **Analysis:** No fallback activity or access failures occurred after enabling strict multi-tenant resolution mode.

### B. CloudWatch Alarm States
All platform monitoring alarms remain in a stable, healthy state:
*   `togs-and-dogs-prod-tenant-resolution-fallback` = 🟢 **OK**
*   `togs-and-dogs-prod-tenant-resolution-failed` = 🟢 **OK**
*   `togs-and-dogs-prod-entitlement-denied` = 🟢 **OK**
*   `togs-and-dogs-prod-calendar-sync-failures` = 🟢 **OK**
*   `togs-and-dogs-prod-calendar-token-revoked` = 🟢 **OK**
*   `togs-and-dogs-prod-calendar-health-check-failed` = 🟢 **OK**

---

## 3. Operations Smoke Check

*   **Portal Status:**
    *   `/admin` loads normally (HTTP `200`).
    *   `/platform-admin` loads normally (HTTP `200`).
*   **Integration Health:**
    *   Google Calendar connection remains `CONNECTED` and healthy.
*   **Database & Tenant Integrity:**
    *   Tenant count remains exactly `1` (`tog_and_dogs` only).
    *   No second tenant records exist.
*   **Regressions:** No authentication or access regressions were observed. Matthew's manual verification was successful.

---

## 4. Rollback Plan

The rollback plan remains fully active and verified:
1.  Revert `TENANT_RESOLUTION_MODE` to `"single"` in `locals.tf` and `main.tf`.
2.  Execute `terraform apply`.
3.  This immediately restores fallback routing to `"tog_and_dogs"` for all backend handlers.
