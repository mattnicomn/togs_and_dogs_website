# Release 11E — Tenant Enforcement Hardening Implementation

**Status:** ✅ Complete — All Backend Changes Implemented & 340/340 Tests Green  
**Date:** 2026-06-14  
**Scope:** Hardening the backend against cross-tenant data leaks and boundary violations by implementing post-read/write checking on all endpoints.

---

## Proposed Changes Implemented

We hardened the backend handlers against cross-tenant access, ensuring that even if a caller supplies an ID (like a request ID or pet ID) belonging to another company/tenant, the system rejects it with a `403 Forbidden` error.

### 1. `review_handler.py`
- Added post-read tenant ownership validation (`validate_tenant_ownership`) immediately following the main `get_item` call for `REQ#` records.
- Blocks cross-tenant approvals/declines with `403 Forbidden`.

### 2. `cancellation_handler.py`
- Hardened both the customer cancellation path and the admin cancellation decision path.
- Added post-read tenant ownership checks on the retrieved `REQ#` record to block cross-tenant cancellation actions.

### 3. `admin_handler.py`
- **GET single request**: Hardened with post-read validation.
- **POST `/admin/job/complete`**: Hardened with post-read validation on the target job.
- **Export endpoint**: Filtered DynamoDB scan using `FilterExpression` to target only the caller's `company_id`.
- **`_resolve_admin_record` fallback**: Added an optional `company_id` parameter to the scan fallback to restrict resolution to the caller's tenant, preventing cross-tenant data recovery.

### 4. `assignment_handler.py`
- Added post-read tenant ownership checks on the retrieved `REQ#` record before assigning workers to job tasks.

### 5. `pet_handler.py`
- **Indirect PET validation**: Since `PET` records may not carry a direct `company_id` attribute, the handler now executes a lookup on the `COMPANY#<company_id> / CLIENT#<client_id>` metadata record to verify the referenced client belongs to the caller's company.
- Hardened GET single pet and PUT pet actions to return `403 Forbidden` if the client verification query returns empty.

### 6. `common/notifications/service.py`
- Parameterized the monthly notification quota limit.
- Updated `_get_monthly_send_count` and `_increment_monthly_send_count` to accept an optional `company_id` (defaulting to `"tog_and_dogs"`).
- Resolved the `company_id` from the record in `notify_event` to update and check the quota count per-tenant (i.e. `QUOTA#<company_id>`).

---

## Test Verification

We added a comprehensive test suite to prevent regressions and verify correct cross-tenant protection:

### 1. New Test File: `tests/backend/test_r11e_tenant_enforcement.py`
- Tested same-tenant success scenarios (ensures zero regressions for the active `"tog_and_dogs"` single-tenant setup).
- Tested cross-tenant access block scenarios for all 6 hardened endpoints (asserts `403 Forbidden`).
- Tested notification quota per-tenant scoping.
- Tested pet handler indirect checks.
- Implemented a `@sync_mocks` decorator with robust `finally` restoration to dynamically copy mocked DynamoDB targets to module-cached handlers without mock pollution or test leaks.

### 2. Regression Runs
- Updated `tests/backend/test_r6j_quota_controls.py` to target `"tog_and_dogs"` specifically (as it asserts fallback quota behaviors).
- Updated `tests/backend/test_rbac_and_purge_safety.py` to match the new signature of `_resolve_admin_record`.
- Ran the full test suite: **340/340 tests passed successfully (100% green).**
