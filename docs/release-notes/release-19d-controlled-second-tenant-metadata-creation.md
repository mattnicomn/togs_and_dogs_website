# Release 19D: Controlled Second-Tenant Metadata Creation

**Status:** Completed  
**Type:** Operations / Tenant Seeding  
**Date:** 2026-06-26  

---

## 1. Goal

The goal of this release was to execute the tenant provisioning script (`scripts/provision_tenant.py`) in apply mode to create the first metadata-only second test tenant (`test_tenant_alpha`) in the production DynamoDB table. This establishes the multi-tenant runtime environment and enables cross-tenant validation under strict tenant resolution mode.

No Cognito users, Stripe accounts, or calendar integrations were created.

---

## 2. Seeding Verification

### A. Execution Command
The provisioning script was run with the following parameters:
```bash
python scripts/provision_tenant.py \
    --company-id test_tenant_alpha \
    --display-name "Test Tenant Alpha" \
    --tier starter \
    --status active \
    --notes "Internal validation tenant for SaaS readiness. No real customer data. No Stripe live payments. No Google Calendar connection. Do not use for Ryan testing unless Matthew separately approves." \
    --apply \
    --confirm-apply \
    --aws-profile usmissionhero-website-prod \
    --table-name togs-and-dogs-prod-data
```

### B. Created Records
Verified that exactly **two records** were written to the database table `togs-and-dogs-prod-data`:
1.  **Tenant Metadata Record:**
    *   `PK`: `TENANT#test_tenant_alpha`
    *   `SK`: `METADATA`
    *   `company_id`: `test_tenant_alpha`
    *   `display_name`: `Test Tenant Alpha`
    *   `subscription_tier`: `starter`
    *   `subscription_status`: `active`
    *   `limits`: Starter limits configured (`max_active_clients = 20`, `max_staff = 1`, `max_monthly_bookings = 50`, `google_calendar_enabled = False`).
    *   `is_active`: `True`
2.  **Platform Audit Record:**
    *   `PK`: `PLATFORM_AUDIT`
    *   `SK`: `ACTION#2026-06-27T02:06:17Z#e16ea2be-7121-44ea-81cd-53daf941a1b7`
    *   `action`: `PROVISION_TENANT`
    *   `target_company_id`: `test_tenant_alpha`

---

## 3. Post-Create Smoke & Telemetry Check

*   **Tenant Count:** Confirmed `2` tenants now exist in DynamoDB (`tog_and_dogs` and `test_tenant_alpha`).
*   **Cognito Users:** Cognito user count remains exactly `5` (no new users were created).
*   **Portal Status:**
    *   `/platform-admin` loads successfully (HTTP `200`).
    *   `/platform-admin/tenants/test_tenant_alpha` detail route loads successfully.
    *   `/admin` for the existing `tog_and_dogs` tenant loads normally (HTTP `200`).
*   **Alarms:** Tenant-resolution alarms remain 🟢 **OK** with zero fallback/failure events detected during creation.

---

## 4. Rollback & Disable Plan

If the new tenant needs to be disabled or access rolled back:
*   **Disable Path:** Log in to `/platform-admin`, navigate to `/platform-admin/tenants/test_tenant_alpha`, click 'Edit Subscription', set the status to 'Disabled', and save. This prevents any future login or API access for this tenant.
*   **Purging:** No records will be deleted automatically. Record deletion requires Matthew's explicit approval.
