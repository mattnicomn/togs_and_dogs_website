# Phase 1B.5B-A: Pet PUT Validation Order Correction Release Notes

## Overview
This bounded backend correction addresses the two candidate regressions identified during Kiro's review of commit `8de7953`.

Starting Parent Commit: `8de7953`

## Root Cause & Correction

### Kiro Finding
In commit `c51b59f`, pet existence and ownership resolution logic was evaluated before client tenant validation in `src/backend/handlers/pet_handler.py`. Consequently:
1. `test_pet_handler_put_same_tenant_succeeds` returned `400` instead of `200`.
2. `test_pet_handler_put_cross_tenant_blocked` returned `400` instead of `403`.

### Validation Order Restored
1. **Role Authorization**: Verify caller role in `['owner', 'admin', 'staff']`.
2. **Trusted Tenant Resolution**: Derive `company_id` from the authenticated request context (`get_current_company_id(event)`). Body-supplied `company_id` overrides are strictly ignored.
3. **Client Tenant Validation (First Business Check)**: Validate the submitted `client_id` against `COMPANY#<company_id> / CLIENT#<client_id>`. If the client does not belong to the caller's tenant, immediately return `403 Forbidden`. No pet lookup or ownership error can override this cross-tenant check.
4. **Pet Resolution**:
   - `POST` / `pet_id == 'NEW'`: Creates a new record with a generated UUID.
   - `PUT` for existing pet: Looks up `PET#<pet_id> / CLIENT#<client_id>`. If not found, performs a bounded partition-key Query (`PK = PET#<pet_id>`).
     - **0 items**: Returns `404 Not Found` ("Pet not found"). Performs no write.
     - **1 item under another same-tenant client**: Returns `400 Bad Request` ("Cannot reassign client ownership of a pet"). Performs no write.
     - **1 item under another tenant**: Returns `403 Forbidden`. Performs no write.
     - **>1 items (data corruption)**: Returns `500 Internal Server Error` safely without selecting an arbitrary item. Performs no write.
5. **Same-Tenant Execution**: Returns `200 OK` on successful update, preserving original `PK`, `SK`, `client_id`, `company_id`, and `pet_id`.

## Verification & Audit Results

### Backend Tests
- `test_r11e_tenant_enforcement.py::test_pet_handler_put_same_tenant_succeeds`: **PASSED (200 OK)**
- `test_r11e_tenant_enforcement.py::test_pet_handler_put_cross_tenant_blocked`: **PASSED (403 Forbidden)**
- `tests/backend/test_phase1b5b_staff_pet_management.py`: 17 passed / 0 failed (+3 new focused tests).
- **Full Backend Suite (`py -3 -m pytest tests/backend -q`):** 700 passed, 69 pre-existing baseline failures, **0 candidate regressions**.

### Frontend Tests & Build
- `npm run test:legacy`: 96 passed.
- `npm run test:components`: 96 passed.
- Combined frontend tests: **192 passed / 0 failed**.
- `npm run build`: Succeeded without compilation errors.
- **Frontend Source Changes**: Zero changes.

## Status
- **Phase 1B.5B-A Status:** Local correction complete — Pending Kiro re-review.
- **Latest Deployed Production Release:** Phase 1B.5A.1 (No AWS deployment occurred during this task).
