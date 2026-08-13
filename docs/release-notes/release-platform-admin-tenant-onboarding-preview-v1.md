# Release Note: Preview-Only V1 Gated Platform Admin Tenant-Onboarding Orchestrator

**Release:** Platform Admin Tenant-Onboarding Orchestrator (V1 Preview Mode)

**Date:** August 12, 2026

**Scope:** Gated, locally complete, read-only preview implementation for platform tenant onboarding validation and end-state visualization.

**LOCAL IMPLEMENTATION COMPLETE**

**PREVIEW-ONLY**

**NO TENANT CREATION**

**NOT DEPLOYED**

---

## Executive Summary

This release introduces the **V1 Preview-Only Platform Admin Tenant-Onboarding Orchestrator**. The orchestrator enables platform administrators to validate proposed business identity, subscription tier limits, and initial status, and to generate a comprehensive preview of the proposed tenant metadata record, audit entry, and pre-apply approval checklist before any provision operation is submitted.

**CRITICAL SAFETY GUARDRAILS IN EFFECT:**
- **Zero Database Writes:** No records are written to DynamoDB.
- **No Apply / Creation Path:** V1 ends strictly at preview generation.
- **Read-Only IAM Role:** Dedicated preview Lambda infrastructure uses a strict read-only policy (`dynamodb:GetItem` and `dynamodb:Scan` only).
- **Explicit Matthew Approval Required:** Production tenant creation remains gated on explicit Matthew approval.

---

## Architecture & Implementation Overview

### 1. Pure Domain Modules
- **`src/backend/common/tenant_catalog.py`**
  Canonical source of truth for tier entitlement limits (Starter, Professional, Premium, Enterprise) and valid subscription statuses. Provides fail-closed tier validation and copy-protected limit dictionaries.
- **`src/backend/common/tenant_provisioning.py`**
  Pure Python domain logic for company ID regex validation (`^[a-z0-9_]{3,64}$`), reserved ID checks (`tog_and_dogs`), display name sanitization (max 100 chars, control character rejection), proposed metadata record building, proposed audit record building, and deterministic SHA-256 preview hashing.

### 2. Read-Only Backend & Handlers
- **`src/backend/common/tenant_read_adapter.py`**
  Dedicated read-only DynamoDB adapter implementing `GetItem` for tenant existence checks and filtered `Scan` for display-name collision detection.
- **`src/backend/handlers/platform_onboarding_handler.py`**
  API handler exposing two routes:
  - `POST /platform/onboarding/validate`: Validates input fields and performs read-only conflict checks.
  - `POST /platform/onboarding/preview`: Performs independent re-validation, builds the proposed metadata/audit records, constructs the pre-apply approval checklist, and computes the preview hash. Returns `no_writes: true`.
  - Requires `platform_admin` Cognito group authorization.

### 3. Dedicated Read-Only Infrastructure
- **`infra/prod/platform_preview_iam.tf`**
  Defines the `{name_prefix}-platform-preview-exec` IAM role and `{name_prefix}-platform-preview-dynamodb-readonly` policy, granting strictly `dynamodb:GetItem` and `dynamodb:Scan`.
- **`infra/prod/platform_preview_lambda.tf`**
  Defines the `{name_prefix}-platform-preview` Lambda function linked to the read-only IAM role. API Gateway wiring exposes only authenticated `POST /platform/onboarding/validate` and `POST /platform/onboarding/preview`, with route-scoped invocation permissions.

### 4. Platform Admin UI & API Client
- **`web/src/api/platform.js`**
  Added `validateOnboardingTenant` and `previewOnboardingTenant` helper functions.
- **`web/src/components/PlatformAdminOnboarding.jsx`**
  React component providing a 3-step wizard (Business Identity → Field Validation → Proposed End State Preview). Features prominent no-writes safety warnings, edit-after-preview stale state detection, server-provided tier limits rendering, and confirmation that no Apply button exists in V1.
- **`web/src/App.jsx`**
  Registered route `/platform-admin/onboarding` guarded by `PlatformAdminGuard`.

---

## Verification & Testing Matrix

| Test Suite | Coverage Focus | Result |
|------------|----------------|--------|
| `test_tenant_catalog.py` | Tier limits, valid statuses, copy protection, billing catalog reuse, fail-closed handling | PASSED (13/13) |
| `test_tenant_provisioning.py` | Company ID regex, reserved ID guard, display name limits, metadata/audit builders, preview hash | PASSED (16/16) |
| `test_platform_onboarding_api.py` | 403 authorization, 400 validation, existence conflicts, preview hash, no-writes assertion | PASSED (8/8) |
| `test_platform_preview_iam.py` | IAM, dedicated-role, authenticated-route, and forbidden-route static checks | PASSED (6/6) |
| `test_r17w_tenant_provisioning.py` | Existing CLI dry-run/apply-gate compatibility plus shared catalog/domain reuse | PASSED (48/48) |
| Focused backend aggregate | All five backend files above | PASSED (91/91) |
| `PlatformAdminOnboarding.test.jsx` | UI rendering, safety banner, field validation errors, preview state display, stale-preview warning, absence of Apply button | PASSED (5/5) |
| Full web Vitest suite | Web regression suite | PASSED (22 files, 256/256 tests) |
| `web build` | Vite production build compilation | PASSED |
| Full backend suite | Repository backend regression suite in the available local Python environment | 835 passed, 97 baseline-equivalent failures, 0 skipped; clean baseline had the identical 97 failures and 790 passes, with 0 candidate-only failures |
| Backend regression comparison | Exact failing-node-ID comparison against clean baseline `28ceb803ce7bcbca09726119e911e36e5cdf9188` | PASSED — `BACKEND_REGRESSION_GATE_PASS_BASELINE_EQUIVALENT` |
| `terraform fmt -check` | Candidate Terraform formatting with Terraform v1.14.8 | PASSED |
| `terraform validate` | Candidate Terraform configuration validation with Terraform v1.14.8 | PASSED |

---

## Gate & Governance Summary

- **Tenant Provisioning:** Gated. No tenant creation path activated.
- **Apply Path:** Deferred to future release pending explicit approval from Matthew.
- **Environment Status:** Local implementation complete and approved for commit from baseline `28ceb803ce7bcbca09726119e911e36e5cdf9188`. No production deployment or modification was executed.
- **Validation Gate:** Focused backend, backend baseline-equivalence, focused and full web, web build, Terraform formatting, Terraform validation, IAM, no-write, and diff-hygiene gates passed. The environment-dependent backend suite is not universally green, but it has zero candidate-only failures relative to the clean baseline.
