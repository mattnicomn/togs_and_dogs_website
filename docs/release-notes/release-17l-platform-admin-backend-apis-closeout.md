# Release 17L: Platform Admin Backend APIs — Closeout

**Status:** Completed (Infrastructure Deployed, API stage redeployment pending approval)  
**Type:** Backend Features & API Gateway Security  
**Date:** 2026-06-21  
**Baseline Commit:** `aeaa00b2718118037c2510775efad9602ae607ff` (Release 17J)

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

## 3. Operational Guarantees
- `ENTITLEMENT_ENFORCEMENT_ENABLED` remains true in production for the `admin` and `google-auth` Lambdas.
- No entitlement behaviors were altered, and no Phase 2 entitlement gates were added.
- No production tenant metadata was modified during validation.
- No Stripe Dashboard, Postmark, or live payment/email actions were performed.

---

## 4. Next Release
- **Release 17M:** Platform Management Console CLI scripts and initial administration tools.
