# Release 19C: Matthew Approval Checkpoint for Controlled Second-Tenant Metadata Creation

**Status:** Plan Approved / Execution Pending Approval  
**Type:** Operations / Security Checkpoint  
**Date:** 2026-06-26  

---

## 1. Goal

The goal of this checkpoint is to present the final execution plan for creating the first metadata-only second test tenant (`test_tenant_alpha`) in the production environment. Matthew has approved the parameters and shape, but creation remains paused until this checkpoint is reviewed and explicitly approved.

No second tenant has been created yet.

---

## 2. Execution Parameters & Commands

### A. Exact CLI Command for Future Execution
The following command will be run in the workspace to write the tenant metadata to the production DynamoDB table:
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

---

## 3. Scope of Impact

### A. Expected Records to Create (DynamoDB only)
Executing the apply command will write exactly **two items** to the production DynamoDB table `togs-and-dogs-prod-data`:
1.  **Tenant Metadata Record:**
    *   `PK`: `TENANT#test_tenant_alpha`
    *   `SK`: `METADATA`
    *   `subscription_tier`: `starter`
    *   `subscription_status`: `active`
    *   `is_active`: `True`
2.  **Platform Audit Record:**
    *   `PK`: `PLATFORM_AUDIT`
    *   `SK`: `ACTION#<TIMESTAMP>#<UUID>`
    *   `action`: `PROVISION_TENANT`
    *   `target_company_id`: `test_tenant_alpha`

### B. Confirmed Non-Actions (No other resource changes)
*   **Cognito:** No Cognito users, attributes, groups, or credentials will be created or modified. (CLI command templates for Matthew's manual use will only be printed as instructions).
*   **Existing Tenant:** The existing tenant metadata for `tog_and_dogs` will not be accessed or modified.
*   **Integrations:** No Google Calendar OAuth, tokens, or sync events will be created. No Stripe customers, subscriptions, products, or webhooks will be configured. No Postmark emails, SMS, or notification pipelines will be executed.
*   **Application Data:** No clients, pets, bookings, requests, or jobs will be created.
*   **Tenant Resolution Mode:** Strict mode remains active (`TENANT_RESOLUTION_MODE=multi` on all 13 backend Lambdas) and will not be modified.

---

## 4. Rollback & Disable Plan

If the new tenant needs to be disabled or access rolled back:
*   **Primary Path:** Log in to `https://toganddogs.usmissionhero.com/platform-admin`, navigate to `/platform-admin/tenants/test_tenant_alpha`, click 'Edit Subscription', set the status to 'Disabled', and save.
*   **API Path:** Perform a `PATCH` request to `/platform/tenants/test_tenant_alpha` with body `{"subscription_status": "disabled"}` using a valid platform admin operator JWT.
*   *Note:* The system is designed to retain tenant metadata for audit integrity; disabling the subscription blocks all client-side and API access for that tenant immediately.
