# Release 19K — Backend Tenant Isolation Remediation Plan (Pre-Deploy Checkpoint)

This release implements backend-only remediation to address the tenant isolation issues discovered during Release 19H manual validation.

## 🛠️ Summary of Changes

### 1. Google Calendar Tenant Gate
- Restricts Google Calendar functionality strictly to the default tenant (`tog_and_dogs`).
- Updated `src/backend/common/google_calendar.py` token helpers (`_get_stored_tokens`, `_save_tokens`, `_mark_token_revoked`, `_get_valid_token`) to accept `company_id`.
- Gated these helpers to return empty token sets and avoid accessing the global Secret Manager token secret (`GOOGLE_USER_TOKENS_NAME`) if requested by a non-default company.
- Updates `sync_calendar_event` to skip synchronization and return status `calendar_skipped` when called by non-default tenants.
- Gated `get_status`, `calendar_health_check`, `initiate_auth`, `handle_callback`, and `disconnect_auth` in `src/backend/handlers/google_auth_handler.py` to bypass operations for non-default tenants and return `NOT_CONNECTED` or `403 Forbidden` as appropriate.

### 2. Cognito User Group/Company Filtering
- Added helper `is_cognito_user_in_company(user, company_id, mode)` in `src/backend/handlers/admin_handler.py` to determine if a Cognito user belongs to the active tenant.
  - Under `multi` mode: Strictly matches `custom:company_id` claim.
  - Under `single` mode: Allows fallback to default company if `custom:company_id` is missing.
- Filtered `GET /admin/staff` list to exclude Cognito users that do not belong to the caller's tenant.
- Filtered `GET /admin/clients` list to exclude Cognito client users that do not belong to the caller's tenant.

### 3. Safe Tenant Info Endpoint
- Added `GET /admin/tenant-info` route in `src/backend/handlers/admin_handler.py`.
- Queries the active tenant's DB metadata and returns safe display attributes (`company_id`, `display_name`, `subscription_tier`, `subscription_status`, and `google_calendar_status`).
- Guarantees zero leakage of credentials, tokens, or live keys.

### 4. API Gateway Configuration
- Added Terraform resource configurations for `/admin/tenant-info` in `modules/api/main.tf` to define the API resources, Cognito authorizers, and Lambda integrations for future deployment.

---

## 🔍 Verification & Test Results

### 1. New Unit Tests
A new comprehensive unit test suite `tests/backend/test_r19k_tenant_isolation.py` was created to verify all remediation logic:
- Non-default tenant status endpoint returns `NOT_CONNECTED` and bypasses Secrets Manager.
- Non-default tenant health endpoint returns `NOT_CONNECTED`.
- Non-default tenant oauth initiation and callback are rejected with `403`.
- Cognito user filtering in `GET /admin/staff` correctly matches `custom:company_id` in both `single` and `multi` resolution modes.
- Cognito user filtering in `GET /admin/clients` matches `custom:company_id`.
- `/admin/tenant-info` resolves active company, queries DB, and returns safe metadata without leaking credentials.

### 2. Execution Result
Running the backend test suite inside the test environment:
```bash
py -m pytest tests/backend/test_r19k_tenant_isolation.py
```
**Status: 9 Passed / 9 Total (100% Success)**

Regression checks for existing token health and company resolution tests:
```bash
py -m pytest tests/backend/test_r17w_company_id_resolution.py tests/backend/test_r6g_calendar_health.py
```
**Status: 41 Passed / 41 Total (100% Success)**
