# Release 19G: Second-Tenant Owner Cognito User Creation Approval Checkpoint and Runbook

**Status:** Plan Approved / Execution Pending Approval  
**Type:** Operations / User Seeding Runbook  
**Date:** 2026-06-26  

---

## 1. Goal

The goal of this release is to establish the approval checkpoint and future execution runbook for creating the Cognito user that will own the newly provisioned second test tenant (`test_tenant_alpha`). 

No Cognito user has been created yet.

---

## 2. Environment Pre-Flight Status

*   **Tenant Count:** `2` active tenants exist in DynamoDB (`tog_and_dogs` and `test_tenant_alpha`).
*   **Strict Resolution Mode:** Active (`TENANT_RESOLUTION_MODE=multi` on all 13 backend Lambdas).
*   **Cognito User Pool ID:** `us-east-1_counlsXGU` (togs-and-dogs-prod-admin-pool).
*   **Target Group:** `owner` (grants full tenant-level administrative privileges).
*   **Reserved Group:** `platform_admin` (reserved globally for usmissionhero operators only; must **never** be assigned to tenant owners).
*   **Tenant Isolation Check:** Confirmed that exactly 0 Cognito users are currently associated with `test_tenant_alpha`.

---

## 3. Cognito Seeding Runbook (Future Execution)

The following commands use placeholders. All commands must be executed using the profile `<aws-profile>` and user pool `<user-pool-id>`.

### Step 1: Create the Cognito User
Run the following CLI command to create the user, verify their email, and assign the `custom:company_id` attribute:
```bash
aws cognito-idp admin-create-user \
    --user-pool-id <user-pool-id> \
    --username "<owner-email-provided-privately>" \
    --user-attributes Name=email,Value="<owner-email-provided-privately>" \
                      Name=email_verified,Value=true \
                      Name=custom:company_id,Value=test_tenant_alpha \
    --temporary-password "<temporary-password-provided-privately>" \
    --message-action SUPPRESS \
    --profile <aws-profile> \
    --region us-east-1
```
*   *Note on email suppression:* `--message-action SUPPRESS` is specified to prevent Cognito from sending an automatic welcome email, as the owner is an internal test profile.

### Step 2: Assign Owner Group
Run the following command to place the new user in the `owner` group:
```bash
aws cognito-idp admin-add-user-to-group \
    --user-pool-id <user-pool-id> \
    --username "<owner-email-provided-privately>" \
    --group-name owner \
    --profile <aws-profile> \
    --region us-east-1
```

### Step 3: Verify User Details and Security Constraints
Run these commands to verify properties and group isolation:
```bash
# 1. Verify custom:company_id attribute is exactly 'test_tenant_alpha'
aws cognito-idp admin-get-user \
    --user-pool-id <user-pool-id> \
    --username "<owner-email-provided-privately>" \
    --profile <aws-profile> \
    --region us-east-1

# 2. Verify group membership (must include 'owner', must NOT include 'platform_admin')
aws cognito-idp admin-list-groups-for-user \
    --user-pool-id <user-pool-id> \
    --username "<owner-email-provided-privately>" \
    --profile <aws-profile> \
    --region us-east-1
```

---

## 4. Post-Execution Login Validation Checklist (Matthew)

Once the user is created in Release 19H, Matthew should validate the login flow manually:
1.  Navigate to `https://toganddogs.usmissionhero.com/admin`.
2.  Log out of any active session.
3.  Log back in using the `<owner-email-provided-privately>` and `<temporary-password-provided-privately>`.
4.  Confirm the prompt to set a new password on first login succeeds.
5.  Confirm that the `/admin` portal loads successfully under the `test_tenant_alpha` context.
6.  Verify that **no** data belonging to the `tog_and_dogs` tenant (clients, bookings, staff) is visible in this session.
7.  Check console and network logs to verify that no `401 Unauthorized` or `403 Forbidden` API errors occur.

---

## 5. Rollback & Disable Plan

If validation fails or wrong access is detected:
*   **Disable User:**
    ```bash
    aws cognito-idp admin-disable-user \
        --user-pool-id <user-pool-id> \
        --username "<owner-email-provided-privately>" \
        --profile <aws-profile> \
        --region us-east-1
    ```
*   **Remove Group Access:**
    ```bash
    aws cognito-idp admin-remove-user-from-group \
        --user-pool-id <user-pool-id> \
        --username "<owner-email-provided-privately>" \
        --group-name owner \
        --profile <aws-profile> \
        --region us-east-1
    ```

---

## 6. Required Approval Gates

The execution in Release 19H requires Matthew's approval on:
1.  [ ] **Owner Email:** Explicitly approved privately.
2.  [ ] **Creation Method:** AG-assisted CLI execution in the terminal.
3.  [ ] **Temporary Password approach:** Generated randomly by the agent outside the repo history.
4.  [ ] **Email Suppression:** Welcome email suppressed (`--message-action SUPPRESS`).
5.  [ ] **Group Assignment:** Scoped strictly to `owner` group.
6.  [ ] **Login Validation Scope:** Validated on `/admin` dashboard.
7.  [ ] **Rollback Plan:** Accepted as documented.

To execute, Matthew must reply:  
`Approved: create the test_tenant_alpha owner user`
