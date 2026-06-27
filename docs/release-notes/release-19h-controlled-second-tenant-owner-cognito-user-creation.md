# Release 19H: Controlled Second-Tenant Owner Cognito User Creation

**Status:** Completed  
**Type:** Operations / Security & Identity  
**Date:** 2026-06-26  

---

## 1. Goal

The goal of this release was to execute the creation of the Cognito owner user for the newly provisioned second test tenant (`test_tenant_alpha`) using AG-assisted Cognito CLI tools, while suppressing explicit password parameters in reports and using Cognito-generated temporary invitations.

This user establishes tenant-level administrative ownership, enabling full tenant isolation testing under strict multi-tenant resolution mode (`TENANT_RESOLUTION_MODE=multi`).

---

## 2. Creation Verification (Redacted)

### A. Execution Parameters
*   **Tenant Scoping:** `test_tenant_alpha`
*   **Email Address:** Scoped to the private test owner email address (`matt***@yahoo.com`).
*   **Cognito Custom Attribute:** `custom:company_id = test_tenant_alpha`
*   **Desired Delivery Mediums:** `EMAIL`
*   **Temporary Password:** Generated and managed directly by AWS Cognito, sent securely to the test owner's inbox. No password values were printed, documented, or committed.
*   **Invitation Message:** Supression was disabled, allowing Cognito to send the invitation with the temporary password.

### B. Group Mapping & Security Constraints
*   **Assigned Group:** `owner` (grants full tenant-level admin control for `test_tenant_alpha`).
*   **Forbidden Groups:** Verified the user is **not** assigned to `platform_admin` (global operator role), `staff`, or `client`.

---

## 3. Post-Create Verification & Telemetry Check

*   **Cognito User Count:** Confirmed `6` users exist in Cognito.
    *   `tog_and_dogs` Users: `5` (unchanged).
    *   `test_tenant_alpha` Users: `1` (new owner).
*   **Tenant Count:** Confirmed `2` tenants exist in DynamoDB (`tog_and_dogs`, `test_tenant_alpha`).
*   **Alarms:** CloudWatch tenant-resolution failed/fallback alarms remain in 🟢 **OK** status.
*   **Integrations & Sandbox State:** No Google Calendar OAuth setup, Stripe Dashboard product adjustments, Postmark SMS notifications, or client/booking/job creations occurred.

---

## 4. Manual Matthew Login Validation Checklist

Matthew is requested to verify the login and access boundaries:
1.  Check the test owner email inbox (`mattnico10@yahoo.com`) for the Cognito email invitation and temporary password.
2.  Navigate to `https://toganddogs.usmissionhero.com/admin` and log out of any current session.
3.  Log in using the test owner credentials and complete the first-time login password change.
4.  Confirm the `/admin` dashboard loads successfully under the `test_tenant_alpha` context.
5.  Verify the dashboard is empty of any clients, pets, bookings, or staff records, and that **no** data belonging to the `tog_and_dogs` tenant is visible.
6.  Verify no 401/403 errors are generated in the browser console.
7.  Log out after verification is complete.

---

## 5. Rollback & Disable Plan

If access issues or data leakage are found:
*   **Deactivate Owner User:**
    ```bash
    aws cognito-idp admin-disable-user \
        --user-pool-id us-east-1_counlsXGU \
        --username "<redacted-owner-email>" \
        --profile usmissionhero-website-prod \
        --region us-east-1
    ```
*   **Remove Group Assignment:**
    ```bash
    aws cognito-idp admin-remove-user-from-group \
        --user-pool-id us-east-1_counlsXGU \
        --username "<redacted-owner-email>" \
        --group-name owner \
        --profile usmissionhero-website-prod \
        --region us-east-1
    ```
