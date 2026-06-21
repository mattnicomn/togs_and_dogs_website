# Release 17L: Platform Admin Backend APIs — Closeout

**Status:** ✅ Completed  
**Type:** Backend Features & API Gateway Security  
**Date:** 2026-06-21  
**Implementation Commit:** `c24cf9f` (all source, test, terraform, and docs)  
**Finalization Commit:** see Section 4 below

---

## 1. Summary of Changes

We implemented the backend foundation for the platform admin management console, ensuring platform admin routes are securely restricted to the Cognito `platform_admin` group.

### Backend Handlers & Common Code
- **[auth.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/auth.py):**
  - Added role priority definition for `platform_admin` (priority 0.5, sits above client but keeps separation from normal tenant administration).
  - Implemented `is_platform_admin` helper based on group membership.
- **[platform_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/platform_handler.py):**
  - Implemented the routing and request handlers for all 17L platform endpoints:
    - `GET /platform/tenants` (returns safe summaries only).
    - `GET /platform/tenants/{company_id}` (returns company metadata profile, active count of staff/clients, request volume, and entitlement summaries).
    - `PATCH /platform/tenants/{company_id}` (updates company settings such as tier, status, display name, etc., writes platform audit logs, and invalidates entitlement caches).
    - `GET /platform/audit` (returns platform audit history in reverse chronological order, supporting pagination with cursor tokens).
  - Wired security verification to ensure requests must originate from users in the `platform_admin` Cognito group.

### Infrastructure Changes (Terraform)
- **[auth/main.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/modules/auth/main.tf):**
  - Added Cognito user group `platform_admin` to the admin user pool.
- **[prod/main.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/infra/prod/main.tf):**
  - Declared `platform` Lambda function, IAM permissions, environment variables (`DATA_TABLE_NAME`, `DEFAULT_COMPANY_ID`), and API Gateway method permissions.
- **[api/variables.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/modules/api/variables.tf) & [api/main.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/modules/api/main.tf):**
  - Declared `platform_handler_invoke_arn`.
  - Added resource paths, methods, integrations, and authorizers for:
    - `/platform/tenants` (GET)
    - `/platform/tenants/{company_id}` (GET, PATCH)
    - `/platform/audit` (GET)
  - Wired these routes to the Cognito User Pool Authorizer.
  - Linked them with the `platform_handler` Lambda function.

---

## 2. Verification & Testing

### Automated Tests
- **Platform Admin Test Suite (`tests/backend/test_r17l_platform_admin.py`):**
  - All **12/12** tests passed successfully. Tests validate token group claims, access control, route parsing, pagination logic, cache invalidation, and platform audit trail logging.
- **Entitlement Test Suites:**
  - All **29/29** tests in `test_r17b_entitlement_enforcement.py`, `test_r17d_entitlement_wiring.py`, and `test_r17g_entitlement_observability.py` passed successfully.
- **Full Backend Suite:**
  - All **454/454** tests in the full test suite passed.

### Security Smoke Validation
- **Unauthenticated Check:**
  - Sent an unauthenticated GET request to `https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/platform/tenants`.
  - **Result:** Successfully returned `HTTP 401 Unauthorized` with body `{"message":"Unauthorized"}`, verifying that API Gateway authorization is wired properly.
- **Cognito Group Membership:**
  - Confirmed that Cognito User Group `platform_admin` was created in user pool `us-east-1_counlsXGU`.
  - Verified via the AWS CLI that **no users** are in the `platform_admin` group.

---

## 3. API Gateway Stage Redeployment (Finalization)

After implementation commit `c24cf9f` was pushed, one final Terraform action remained to publish the new platform routes to the `prod` stage.

### Pre-Apply Plan
```
Plan: 1 to add, 1 to change, 1 to destroy
  +/- module.api.aws_api_gateway_deployment.main (forced replacement via redeployment trigger hash change)
  ~   module.api.aws_api_gateway_stage.main (deployment_id update in-place)
```
No Lambda code changes, no Cognito user changes, no DynamoDB, no tenant metadata — plan scope confirmed within guardrails.

### Apply Result
```
Apply complete! Resources: 1 added, 1 changed, 1 destroyed.
  module.api.aws_api_gateway_deployment.main: Created [id=5zoib8]
  module.api.aws_api_gateway_stage.main: Modifications complete [id=ags-a022yxuiue-prod]
  module.api.aws_api_gateway_deployment.main (deposed whh7sc): Destroyed
```

### Post-Apply Drift Check
```
No changes. Your infrastructure matches the configuration.
```

### Post-Apply Security Re-Validation
- **Unauthenticated GET `/platform/tenants`:** `HTTP 401 Unauthorized` — `{"message":"Unauthorized"}` ✅
- **`platform_admin` Cognito group:** Exists in `us-east-1_counlsXGU` ✅
- **Users in `platform_admin`:** `[]` (zero users) ✅
- **Generated `.tfplan` file:** `tfplan_17l_final` deleted immediately after apply ✅

---

## 4. Operational Guarantees
- `ENTITLEMENT_ENFORCEMENT_ENABLED` remains `true` in production for the `admin` and `google-auth` Lambdas.
- No entitlement behaviors were altered, and no Phase 2 entitlement gates were added.
- No production tenant metadata was modified.
- No second tenant was created.
- No Stripe Dashboard, Postmark, live key, payment, email/SMS, frontend, mobile, EAS, TestFlight, App Store Connect, Ryan/tester, Cognito user membership, or Apple Beta Review changes occurred.

---

## 5. Next Release
- **Release 17M:** Platform Management Console CLI scripts and initial administration tools.
