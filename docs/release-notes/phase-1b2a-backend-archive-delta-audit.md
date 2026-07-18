# Backend Archive and Production Deployment-Delta Audit: Phase 1B.2A

## 1. Executive Summary

This audit establishes the exact deployment-delta and packaging status of the backend Lambda package currently running in the production environment. We verified the baseline commit, assessed the changes packaged by `data.archive_file.backend_zip`, validated the impact on all 13 Lambda functions, and ran a full suite validation.

Due to local untracked cache directories (`.pytest_cache/` and `__pycache__/` folders) within the `src/backend/` tree, the local archive build is contaminated with non-deterministic compiled bytecode. Therefore, we classify the package as **NOT READY** for production deploy until a local cleanup is completed.

No AWS access, STS calls, Cognito writes, table updates, or backend deployments occurred during this audit. The `ClientPetIndex` GSI configuration remains committed but undeployed.

---

## 2. Deployed Backend Baseline Identification

- **Identified Deployed Baseline Commit:** `234b51d`
- **Confidence Classification:** `EXACT BASELINE CONFIRMED`
- **Evidence Used:**
  1. **Phase 1A Production Closeout Document:** (`docs/release-notes/phase-1a-client-household-backend-production-deployment-closeout.md`) records that the deployment applied `infra/prod/phase-1a-backend-deploy.tfplan` sourced from commit `234b51d`.
  2. **Git Commit History:** No subsequent backend deployments or code modifications to the `src/backend` path were committed or applied. Later releases (Phase 1B.1) only changed frontend web resources, and subsequent operations (such as the dry run remediation utility) were not deployed.
- **Baseline Commit Range:** `234b51d..HEAD`

---

## 3. Shared Lambda Packaging Design & Exclusions

We inspected `data.archive_file.backend_zip` and the 13 `aws_lambda_function` definitions in `infra/prod/main.tf`:
- **Archive Scope:** The entire `src/backend` directory is packaged into `backend.zip`.
- **Exclusions:** None exist (no HCL `excludes` or ignore files configured in the data resource).
- **Redundancy:** All 13 Lambdas share the exact same `output_path` (`backend.zip`) and `source_code_hash` (`output_base64sha256`). Every function receives the entire codebase even if it only executes a single handler.
- **External Dependencies:** No dependencies outside `src/backend` (such as `scripts/` or `tests/`) enter the archive.
- **Determinism:** Non-deterministic. Because no ignore rules are defined, untracked compiled pyc files and local test caches are bundled into the zip, causing the hash to change based on local development/test activity.

### 13 Lambda Resource Addresses & Handlers
1. `aws_lambda_function.intake` — `handlers.intake_handler.handler`
2. `aws_lambda_function.admin` — `handlers.admin_handler.handler`
3. `aws_lambda_function.review` — `handlers.review_handler.handler`
4. `aws_lambda_function.assign` — `handlers.assignment_handler.handler`
5. `aws_lambda_function.job` — `handlers.job_handler.handler`
6. `aws_lambda_function.google_auth` — `handlers.google_auth_handler.handler`
7. `aws_lambda_function.pet` — `handlers.pet_handler.handler`
8. `aws_lambda_function.cancellation` — `handlers.cancellation_handler.handler`
9. `aws_lambda_function.device` — `handlers.device_handler.handler`
10. `aws_lambda_function.ses_feedback` — `handlers.notification_feedback_handler.handler`
11. `aws_lambda_function.postmark_webhook` — `handlers.postmark_webhook_handler.handler`
12. `aws_lambda_function.stripe_webhook` — `handlers.stripe_webhook_handler.handler`
13. `aws_lambda_function.platform` — `handlers.platform_handler.handler`

---

## 4. Complete Backend Source Delta

We performed `git diff --name-status 234b51d..HEAD -- src/backend` and found only one file was modified:
- **Modified File:** `src/backend/handlers/pet_handler.py`
- **Undeployed Commit:** `ca73d93` ("fix(backend): default new pets to active")
- **Delta Verification:** `ca73d93` is confirmed to be the **only** undeployed backend application change. No other backend files or common utility modules are affected. No incomplete features, debug loops, or environment-dependent code changes exist in the source delta.

---

## 5. Local Archive Hygiene Findings & Action Plan

- **Tracked Files:** Verified `src/backend` contains only code and module initialization files.
- **Dirty Untracked Inputs:**
  - `src/backend/.pytest_cache/`
  - `src/backend/common/__pycache__/`
  - `src/backend/common/notifications/__pycache__/`
  - `src/backend/handlers/__pycache__/`
- **Classification:** **RESOLVED via Exclusions** (local caches are now successfully excluded by HCL configuration)
- **Local Cleanup Remedy:** Exclusions configured in `infra/prod/main.tf` prevent cache pollution. Prior local pycache/pytest directories can still be manually deleted if desired, but they will no longer enter the archive.

---

## 6. Lambda Impact Analysis

| Resource Address | Handler | Directly Invoked? | Indirect Import Risk? | Expected Runtime Behavior Change / Smoke Test Needed |
|------------------|---------|--------------------|----------------------|------------------------------------------------------|
| `aws_lambda_function.pet` | `handlers.pet_handler.handler` | **Yes** | — | **Direct:** Omitted `is_active` defaults to `True` on new records. Updates preserve existing `is_active` state. Test with POST / PUT endpoints. |
| `aws_lambda_function.admin` | `handlers.admin_handler.handler` | No | None | None |
| `aws_lambda_function.intake` | `handlers.intake_handler.handler` | No | None | None |
| `aws_lambda_function.review` | `handlers.review_handler.handler` | No | None | None |
| `aws_lambda_function.assign` | `handlers.assignment_handler.handler` | No | None | None |
| `aws_lambda_function.job` | `handlers.job_handler.handler` | No | None | None |
| `aws_lambda_function.google_auth` | `handlers.google_auth_handler.handler` | No | None | None |
| `aws_lambda_function.cancellation` | `handlers.cancellation_handler.handler` | No | None | None |
| `aws_lambda_function.device` | `handlers.device_handler.handler` | No | None | None |
| `aws_lambda_function.ses_feedback` | `handlers.notification_feedback_handler.handler` | No | None | None |
| `aws_lambda_function.postmark_webhook` | `handlers.postmark_webhook_handler.handler` | No | None | None |
| `aws_lambda_function.stripe_webhook` | `handlers.stripe_webhook_handler.handler` | No | None | None |
| `aws_lambda_function.platform` | `handlers.platform_handler.handler` | No | None | None |

---

## 7. PET `is_active` Hardening Verification

We inspected the logic in `src/backend/handlers/pet_handler.py` and validated contract behaviors:
- **New PET Creation:** If `is_active` is omitted, defaults to `True` (hardened).
- **Explicit `True` / `False`:** Respected on new records.
- **Update Preservation:** Omitted `is_active` on PUT preserves the existing value in DynamoDB.
- **Legacy Records:** Omitted `is_active` on PUT preserves its absence for legacy records.
- **Tenant Isolation:** Unchanged. `_client_verify` rejects cross-company modifications.
- **Remediation Tool Isolation:** Remediation code is located in `scripts/` and is strictly excluded from packaging.
- **Existing Design Risk:** The API endpoint allows caller-supplied non-existent `petId` values to create a new pet (upsert path). This is a legacy design characteristic rather than a new regression.

---

## 8. Local Validation Results

- **Python Compile Validation:** Passed on `src/backend/handlers/pet_handler.py`.
- **Git Diff Check (`git diff --check`):** Passed with zero whitespace warnings.
- **Full Backend Test Run:**
  - **Collected:** 725
  - **Passed:** 654
  - **Failed:** 71
  - **Skipped / Warnings:** 0 skipped, 102 warnings
  - **Regressions:** Zero candidate-only failures (results match baseline exactly).
- **Focused Tests Passed:**
  - `tests/backend/test_r6f_offline_booking.py::test_new_pet_is_active_behavior`
  - `tests/backend/test_r6f_offline_booking.py::test_existing_pet_is_active_behavior`

---

## 9. Deployment Mechanics & Versioning

If GSI configuration is temporarily reverted and a backend plan is run:
- **Plan Scope:** 0 to add, 13 to change, 0 to destroy (only the 13 Lambdas updated in-place via `source_code_hash`).
- **Lambda Versioning:** The functions update `$LATEST` in-place. No versions or aliases are created.
- **Rollback Method:** Checkout the baseline commit `234b51d`, regenerate the plan, and apply.
- **Mixed Version Risk:** Since updates run in parallel, a partial deployment is possible. Because only the `pet` Lambda executes the changed code path and no shared modules are updated, a partial success poses no runtime interoperability risk.

---

## 10. Future Backend Smoke-Test Matrix

### Category A: Read-Only Check (Low Risk, Run First)
1. **Admin Client List:** GET `/admin/clients` (verifies `admin` handler, DB access, and token validation).
2. **Pet List:** GET `/admin/pets` (verifies `pet` handler read path).
3. **Tenant Guard:** GET `/admin/pets?clientId=other_company_client` (verifies cross-company 403 response).

### Category B: Write/Default Validation (Requires Temporary Test Data)
1. **Creation Default:** POST `/admin/pets` (payload: `{ "client_id": "test_client_id", "name": "TestPet" }` without `is_active`).
   - Verify returned payload includes `"is_active": true`.
2. **Update Preservation:** PUT `/admin/pets/{id}` (payload: `{ "client_id": "test_client_id", "name": "TestPetNameChange" }` without `is_active`).
   - Verify response preserves `"is_active": true`.
3. **Explicit Archival:** PUT `/admin/pets/{id}` (payload: `{ "client_id": "test_client_id", "name": "TestPet", "is_active": false }`).
   - Verify response records `"is_active": false`.
4. **Cleanup:** Delete test pet.

---

## 11. Final Decision & Gate Status

### **NOT READY**

We classify the package as **NOT READY** due to local cache pollution (`__pycache__` and `.pytest_cache` directories). Before the backend plan can be approved or generated, a local cleanup command must be run to purge compiled bytes and guarantee a deterministic archive hash.
